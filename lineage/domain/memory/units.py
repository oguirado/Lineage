"""Locked memory admission, explicit inspection and auditable history."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib
import os
import secrets
from pathlib import Path

from lineage.core import journal
from lineage.core.errors import LineageError
from lineage.core.registry import Command, EventDraft
from . import fold, schema


def _identity(value, field):
    definition = schema._STORE.load('mem_unit.schema.json')['properties']
    chosen = definition['provenance']['properties']['actor'] if field == 'agent' else definition['id']
    try:
        schema._native_validate(value, chosen)
    except schema.boundary.SchemaError:
        raise LineageError('bad_args', 'invalid identifier') from None


def _agent(snapshot, agent_id, *, writing=False):
    _identity(agent_id, 'agent')
    record = snapshot.state.get('agents', {}).get(agent_id)
    if record is None or agent_id in {'system', 'operator'}:
        raise LineageError('no_agent', 'committed target agent unavailable')
    if writing and record['status'] == 'retired':
        raise LineageError('conflict', 'target agent is retired')
    return record


def _operator(ctx):
    return ctx.actor == 'operator' and ctx.authority == 'operator'


def _owner(snapshot, agent_id, actor, ctx):
    record = _agent(snapshot, agent_id, writing=True)
    if actor != ctx.actor or (actor != agent_id and not _operator(ctx)):
        raise LineageError('conflict', 'memory owner mismatch')
    return record


def _memory(snapshot, agent_id):
    return snapshot.state.get('memory', {}).get(agent_id, {'units': {}, 'originals': {}, 'memory_gen': 0})


def _capacity(state, agent, ctx):
    try:
        module = importlib.import_module('lineage.domain.memory.entry')
    except ModuleNotFoundError as exc:
        if exc.name != 'lineage.domain.memory.entry':
            raise LineageError('internal', 'entry dependency failed') from None
        raise LineageError('memory_debt', 'cuts: entry admission unavailable') from None
    except Exception:
        raise LineageError('internal', 'entry dependency failed') from None
    builder = getattr(module, 'build', None)
    counter = ctx.services.token_count
    # A-TOK1: an absent counter is admissible; entry.build proves the token
    # ceiling from the byte bound (tokens <= bytes) or refuses memory_debt.
    if not callable(builder) or (counter is not None and not callable(counter)):
        raise LineageError('memory_debt', 'cuts: verified entry admission unavailable')

    def counted(text):
        try:
            value = counter(text)
            if type(value) is not int or value < 0:
                raise ValueError
            return value
        except Exception:
            raise LineageError('memory_debt', 'cuts: verified counting failed') from None
    try:
        result = builder(deepcopy(agent), fold.units_for(state, agent['agent_id']),
                         token_count=counted if counter is not None else None,
                         max_bytes=6000, max_tokens=4000)
        if type(result) is not bytes:
            raise LineageError('internal', 'invalid entry admission result')
        over = (len(result) > 4000) if counter is None else (counted(result.decode('utf-8')) > 4000)
        if len(result) > 6000 or over:
            raise LineageError('memory_debt', 'cuts: entry capacity exceeded')
    except LineageError as exc:
        if exc.code == 'memory_debt':
            detail = exc.detail[:2048] if isinstance(exc.detail, str) else 'cuts: verified entry capacity refused'
            raise LineageError('memory_debt', detail) from None
        raise LineageError('internal', 'entry admission failed') from None
    except Exception:
        raise LineageError('internal', 'entry admission failed') from None


def _inherited(snapshot, unit, ctx):
    claim = unit['provenance'].get('inherited_from')
    if claim is None:
        return
    _agent(snapshot, claim['agent_id'])
    source = _memory(snapshot, claim['agent_id'])['originals'].get(claim['unit_id'])
    if source is None:
        raise LineageError('conflict', 'inherited source unit unavailable')
    if hashlib.sha256(journal.canonical_bytes(source)).hexdigest() != claim['unit_sha256']:
        raise LineageError('hash_mismatch', 'inherited source digest differs')
    if (source['status'] != 'active' or source['privacy'] == 'private' or source['level'] != 2
            or source['kind'] not in {'lesson', 'negative', 'workflow'}
            or (source['kind'] == 'workflow' and source['body']['status'] != 'promoted')):
        raise LineageError('conflict', 'inherited source is ineligible')
    for receipt in source['receipts']:
        schema._evidence(receipt, ctx)


def _run(snapshot, unit, agent_id, supplied):
    provenance = unit['provenance'].get('run_id')
    bindings = [value for value in (supplied, provenance) if value is not None]
    if unit['kind'] == 'episode':
        if provenance != unit['body']['run_id']:
            raise LineageError('conflict', 'run attribution differs')
        bindings.append(unit['body']['run_id'])
    if not bindings:
        return
    if any(value != bindings[0] for value in bindings):
        raise LineageError('conflict', 'run attribution differs')
    opened = snapshot.state.get('runs', {}).get(bindings[0])
    if opened is None:
        raise LineageError('no_run', 'committed open run unavailable')
    if opened['agent_id'] != agent_id or unit['provenance']['actor'] != agent_id:
        raise LineageError('conflict', 'run owner differs')
    if opened.get('ts_close') is not None:
        raise LineageError('run_closed', 'bound run is closed')
    if unit['kind'] == 'episode':
        body = unit['body']
        if (body['task_id'] != opened['task']['id'] or body['seat'] != opened['seat']
                or body['parents_context'] != opened['parents_context']):
            raise LineageError('conflict', 'episode differs from opened run')


def _graph(existing, unit, ctx):
    if unit['id'] in existing:
        raise LineageError('conflict', 'unit identity is immutable')
    if unit['status'] == 'superseded' or 'superseded_by' in unit:
        raise LineageError('conflict', 'new unit cannot supply a backlink')
    for predecessor_id in unit['supersedes']:
        predecessor = existing.get(predecessor_id)
        if predecessor is not None and predecessor['kind'] == 'ruling' and not _operator(ctx):
            raise LineageError('forbidden_level', 'operator ruling cannot be deactivated')
        if (predecessor_id == unit['id'] or predecessor is None
                or predecessor['status'] != 'active'):
            raise LineageError('conflict', 'replacement requires an active owned predecessor')
    # Immutable new ids and existing active predecessors make backward cycles
    # impossible. Check every existing reciprocal edge as well, including birth.
    candidate = deepcopy(existing)
    candidate[unit['id']] = deepcopy(unit)
    for predecessor in unit['supersedes']:
        candidate[predecessor].update(status='superseded', superseded_by=unit['id'])
    for uid, value in candidate.items():
        for predecessor in value['supersedes']:
            old = candidate.get(predecessor)
            if old is None or predecessor == uid or old.get('superseded_by') != uid or old['status'] != 'superseded':
                raise LineageError('conflict', 'inconsistent reciprocal replacement')
        if value['status'] == 'superseded':
            successor = candidate.get(value.get('superseded_by'))
            if successor is None or uid not in successor['supersedes']:
                raise LineageError('conflict', 'unjustified replacement backlink')
    visited, active = set(), set()
    def visit(uid):
        if uid in active:
            raise LineageError('conflict', 'cyclic replacement graph')
        if uid in visited:
            return
        active.add(uid)
        for predecessor in candidate[uid]['supersedes']:
            visit(predecessor)
        active.remove(uid)
        visited.add(uid)
    for uid in candidate:
        visit(uid)


def _validate_put(snapshot, event, ctx):
    schema._shape(event, 'event.schema.json')
    payload = event['payload']
    agent_id, unit = payload['agent_id'], payload['unit']
    schema.validate_unit(unit, authority=ctx.authority, actor=ctx.actor, ctx=ctx)
    agent = _owner(snapshot, agent_id, event['agent'], ctx)
    if ctx.actor != agent_id and unit['kind'] != 'ruling':
        raise LineageError('conflict', 'only rulings permit an operator owner exception')
    if unit['provenance']['actor'] != ctx.actor:
        raise LineageError('conflict', 'provenance actor differs')
    if (unit['scope']['workflow'] != agent['workflow']
            or unit['scope']['language'] not in {agent['language'], 'general'}):
        raise LineageError('conflict', 'memory scope differs')
    if unit['kind'] == 'ruling':
        quote = unit['statement'].encode('utf-8')
        digest = hashlib.sha256(quote).hexdigest()
        if (unit['body']['how_to_apply'] != unit['statement']
                or unit['body']['quote_sha256'] != digest
                or not any(receipt['sha256'] == digest for receipt in unit['receipts'])):
            raise LineageError('hash_mismatch', 'ruling quote evidence differs')
    _run(snapshot, unit, agent_id, payload.get('run_id'))
    _inherited(snapshot, unit, ctx)
    _graph(_memory(snapshot, agent_id)['units'], unit, ctx)
    candidate = deepcopy(snapshot.state)
    fold.apply(candidate, event)
    _capacity(candidate, agent, ctx)


def _validate_retire(snapshot, event, ctx):
    schema._shape(event, 'event.schema.json')
    payload = event['payload']
    agent_id = payload['agent_id']
    agent = _owner(snapshot, agent_id, event['agent'], ctx)
    existing = _memory(snapshot, agent_id)['units']
    unit = existing.get(payload['unit_id'])
    if unit is None:
        raise LineageError('bad_args', 'requested unit unavailable')
    if unit['kind'] == 'ruling' and not _operator(ctx):
        raise LineageError('forbidden_level', 'operator ruling cannot be retired')
    if unit['status'] in {'retired', 'superseded'}:
        raise LineageError('conflict', 'unit is already inactive')
    successor_id = payload.get('superseded_by')
    if successor_id is not None:
        successor = existing.get(successor_id)
        if successor is None or unit['id'] not in successor['supersedes']:
            raise LineageError('conflict', 'retirement cannot manufacture a replacement')
    candidate = deepcopy(snapshot.state)
    fold.apply(candidate, event)
    _capacity(candidate, agent, ctx)


def put(agent_id, unit, *, run_id=None, command, ctx):
    _identity(agent_id, 'agent')
    # Structural validation may precede replay; mutable current-state admission
    # and evidence are exclusively inside the locked registered validator.
    schema._shape(unit, 'mem_unit.schema.json')
    if run_id is not None:
        _identity(run_id, 'id')
    payload = {'agent_id': agent_id, 'unit': deepcopy(unit)}
    if run_id is not None:
        payload['run_id'] = run_id
    supplied = {key: value for key, value in command.args.items()
                if key not in {'op_id', 'expected_head', 'agent'}}
    if supplied != payload:
        raise LineageError('bad_args', 'command content differs from memory arguments')
    def prepare(snapshot):
        return EventDraft('memory.put', deepcopy(payload))
    prepare.kind = 'memory.put'
    def render(snapshot, current):
        return {'unit': deepcopy(current['payload']['unit']),
                'memory_gen': _memory(snapshot, agent_id)['memory_gen'],
                'commit': {'event_ids': [current['id']], 'head': current['lamport'], 'sha256': current['sha256']}}
    return journal.transact(command, prepare, render, ctx=ctx)


def get(agent_id, unit_id, *, ctx):
    _identity(unit_id, 'id')
    snapshot = journal.snapshot(ctx=ctx)
    _agent(snapshot, agent_id)
    unit = _memory(snapshot, agent_id)['units'].get(unit_id)
    if unit is None:
        raise LineageError('bad_args', 'requested unit unavailable')
    return {'unit': deepcopy(unit), 'head': snapshot.head}


def history(agent_id, *, unit_id=None, after=0, limit=100, ctx):
    if type(after) is not int or not 0 <= after <= schema.SAFE or type(limit) is not int or not 1 <= limit <= 1000:
        raise LineageError('bad_args', 'invalid history cursor')
    if unit_id is not None:
        _identity(unit_id, 'id')
    snapshot = journal.snapshot(ctx=ctx)
    _agent(snapshot, agent_id)
    result = {'events': [], 'next_after': 0 if after > snapshot.head else after,
              'head': snapshot.head, 'has_more': False, 'resync': after > snapshot.head}
    if result['resync']:
        return result
    for current in snapshot.events:
        if current['lamport'] <= after:
            continue
        result['next_after'] = current['lamport']
        payload, kind = current['payload'], current['kind']
        matched = False
        if kind == 'memory.put' and payload['agent_id'] == agent_id:
            unit = payload['unit']
            matched = unit_id is None or unit_id == unit['id'] or unit_id in unit['supersedes'] or unit_id == unit.get('superseded_by')
        elif kind == 'memory.retire' and payload['agent_id'] == agent_id:
            matched = unit_id is None or unit_id in {payload['unit_id'], payload.get('superseded_by')}
        elif kind == 'agent.born' and payload['record']['agent_id'] == agent_id and payload['inherited_units']:
            matched = unit_id is None or any(unit_id == item['unit']['id'] or unit_id in item['unit']['supersedes']
                                            for item in payload['inherited_units'])
        if matched:
            result['events'].append(deepcopy(current))
            if len(result['events']) == limit:
                result['has_more'] = current['lamport'] < snapshot.head
                break
    return result


def _publish_quote(quote, receipt, ctx):
    descriptors = []
    temporary = None
    try:
        fd = os.open(ctx.services.home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        parts = receipt['path'].split('/')
        for part in parts[:-1]:
            try:
                os.mkdir(part, 0o700, dir_fd=fd)
                os.fsync(fd)
            except FileExistsError:
                pass
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(fd)
        # Never expose the final evidence name until every quote byte is
        # durable. Existing artifacts are immutable and must verify unchanged.
        try:
            os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            schema._evidence(receipt, ctx)
            return
        name = '.quote-' + secrets.token_hex(16) + '.tmp'
        target = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=fd)
        temporary = name
        descriptors.append(target)
        view = memoryview(quote)
        while view:
            written = os.write(target, view)
            if written <= 0:
                raise OSError
            view = view[written:]
        os.fsync(target)
        try:
            os.link(temporary, parts[-1], src_dir_fd=fd, dst_dir_fd=fd,
                    follow_symlinks=False)
        except FileExistsError:
            # A competing publisher exposes only a complete, fsynced file.
            schema._evidence(receipt, ctx)
        os.fsync(fd)
    except LineageError:
        raise
    except OSError:
        raise LineageError('hash_mismatch', 'immutable quote publication failed') from None
    finally:
        try:
            if temporary is not None:
                os.unlink(temporary, dir_fd=fd)
        except OSError:
            raise LineageError('hash_mismatch', 'immutable quote cleanup failed') from None
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
    schema._evidence(receipt, ctx)


def operator_ruling(agent_id, quote, *, command, ctx):
    if not _operator(ctx) or command.agent != 'operator':
        raise LineageError('forbidden_level', 'operator authority required')
    if type(quote) is not bytes or not quote:
        raise LineageError('bad_args', 'nonempty UTF-8 quote required')
    try:
        text = quote.decode('utf-8', 'strict')
    except UnicodeError:
        raise LineageError('bad_args', 'valid UTF-8 quote required') from None
    snapshot = journal.snapshot(ctx=ctx)
    # Resolve scope without rejecting an exact retry on current agent status.
    # The locked validator enforces writable status for every new operation.
    agent = _agent(snapshot, agent_id)
    digest = hashlib.sha256(quote).hexdigest()
    identity = hashlib.sha256((agent_id + ':' + digest).encode('utf-8')).hexdigest()
    receipt = {'path': 'evidence/quotes/' + digest + '.txt', 'sha256': digest}
    unit = {'schema': 'lineage.mem.unit/v1', 'id': 'ruling_' + identity[:57],
            'kind': 'ruling', 'level': 1, 'statement': text, 'status': 'active', 'privacy': 'internal',
            'scope': {'workflow': agent['workflow'], 'language': agent['language']},
            'provenance': {'origin': 'operator', 'actor': 'operator'}, 'receipts': [receipt], 'supersedes': [],
            'body': {'quote_sha256': digest, 'how_to_apply': text}}
    if len(journal.canonical_bytes(unit)) > 6000:
        raise LineageError('memory_debt', 'cuts: ruling byte capacity exceeded')
    schema._shape(unit, 'mem_unit.schema.json')
    _publish_quote(quote, receipt, ctx)
    args = {'agent_id': agent_id, 'unit': unit, 'agent': 'operator', 'op_id': 'ruling_' + identity[:57]}
    # Quote identity intentionally replaces the caller's operation identity.
    deterministic = Command('operator_ruling', args, 'operator', args['op_id'], command.expected_head)
    return put(agent_id, unit, command=deterministic, ctx=ctx)
