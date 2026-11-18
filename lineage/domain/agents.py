"""Journal-authoritative agent identities and disposable, confined projections.

The installed journal allocates an id before its prepare callback. Request
identity and revision checks are composed inside that transaction; publication
runs only after its durable return. No projection is an admission authority.
Call refresh_projections(agent_id, ctx=ctx) after committing any event that
changes the agent record or scorecard. It rebuilds the current verified prefix.
"""
from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
from types import SimpleNamespace

from lineage.core import journal, locking, schema
from lineage.core.errors import LineageError
from . import brief, layout, scorecard
from .version import _AGENT, _HASH, _SAFE, _canonical, _match, _pins, agent_version

_ROOT = Path(__file__).resolve().parents[2]
_OP = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}')
_EVENT_ID = re.compile(r'e-[0-9a-f]{16}')
_CITATION = re.compile(r'\[GOLD-S1/PM-1001\.1/([^;\]\r\n]+); (§[^\]\r\n]+)\]')
_WORKFLOWS = ('develop', 'test', 'review', 'harden', 'research', 'orchestrate')
_STATUSES = ('draft', 'shadow', 'promoted', 'retired')
# Workflow resolution is U12 policy; authority remains the bundled U08 matrix.
_ROLES = {'develop': 'author', 'test': 'oracle_writer', 'review': 'cross_reviewer',
          'harden': 'repairer', 'research': 'researcher', 'orchestrate': 'orchestrator'}
_FILES = layout.PROJECTION_FILES


@dataclass(frozen=True)
class _Command:
    tool: str
    args: dict
    agent: str
    op_id: str
    expected_head: int | None = None


@dataclass(frozen=True)
class _Committed:
    event: dict
    value: dict
    head: int
    sha256: str


def _target(agent_id):
    _match(agent_id, _AGENT)
    if agent_id in ('operator', 'system'):
        raise LineageError('bad_args', 'reserved target identity')


def _text(value, maximum):
    if (type(value) is not str or not 1 <= len(value) <= maximum
            or not value.strip() or any(c in value for c in '\n\r\x00')):
        raise LineageError('bad_args', 'invalid agent text')
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise LineageError('bad_args', 'invalid text encoding') from None


def _sequence(value):
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise LineageError('bad_args', 'invalid collection')
    return deepcopy(list(value))


def _check(tool, args):
    # Descriptor and direct-domain validation share the exact frozen shape.
    from lineage.ext.agents import _SCHEMAS
    try:
        schema.validate(args, _SCHEMAS[tool])
    except schema.SchemaError:
        raise LineageError('bad_args', 'invalid agent arguments') from None


def _create_args(agent_id, display_name, workflow, language, allowed_seats,
                 references, skills, overlays):
    _target(agent_id)
    _text(display_name, 128)
    _text(language, 64)
    seats, refs, pins, overlay_ids = map(_sequence, (allowed_seats, references, skills, overlays))
    for overlay in overlay_ids:
        _text(overlay, 64)
    data = {'agent_id': agent_id, 'display_name': display_name,
            'workflow': workflow, 'language': language, 'allowed_seats': seats,
            'references': refs, 'skills': pins, 'overlays': overlay_ids}
    _check('agent_create', {**data, 'agent': 'system', 'op_id': 'validation'})
    for seat in seats:
        model = seat['model']
        if not model.strip() or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in model):
            raise LineageError('bad_args', 'invalid seat model')
    if sorted(pin['id'] for pin in refs) != ['gold_s1', 'memory_v21']:
        raise LineageError('bad_args', 'founding reference membership differs')
    _pins(pins)
    return data


def _home(ctx):
    try:
        raw = ctx.services.home if hasattr(ctx, 'services') else ctx.home
        return Path(raw)
    except (AttributeError, TypeError, ValueError):
        raise LineageError('internal', 'agent runtime unavailable') from None


def _history(ctx):
    try:
        return journal.snapshot(_home(ctx))
    except LineageError as exc:
        raise LineageError(exc.code, 'authoritative agent history unavailable') from None
    except Exception:
        raise LineageError('internal', 'authoritative agent history unavailable') from None


def _events(snapshot):
    events = snapshot.events if hasattr(snapshot, 'events') else snapshot
    if not isinstance(events, (list, tuple)):
        raise LineageError('internal', 'committed snapshot unavailable')
    return tuple(deepcopy(events))


def _state(events, ctx):
    try:
        folds = ctx.services.registry.folds if hasattr(ctx, 'services') else ctx.folds
        if not callable(folds.get('agents')) or not callable(folds.get('memory')):
            raise LineageError('internal', 'required agent fold unavailable')
        state = {}
        for event in events:
            for _, callback in sorted(folds.items(), key=lambda p: (getattr(p[1], 'order', 0), p[0])):
                callback(state, deepcopy(event))
        return state
    except LineageError:
        raise
    except Exception:
        raise LineageError('internal', 'agent fold unavailable') from None


def _units(state, agent_id):
    from .memory.fold import units_for
    return units_for(state, agent_id)


def _record(state, agent_id):
    try:
        value = state.get('agents', {}).get(agent_id)
        if value is None:
            raise LineageError('no_agent', 'committed agent does not exist')
        result = deepcopy(value)
        # U11's historical reconstruction retains the captured birth hash.
        # Keep that fact in its consumed record view; the effective agent view
        # overlays the independently folded current own-brief digest.
        current = state['agents'].get('_brief_heads', {}).get(agent_id)
        if current is not None:
            result['brief_head_sha256'] = current
        return result
    except (TypeError, AttributeError):
        raise LineageError('internal', 'agent state unavailable') from None


def _source(state, agent_id):
    try:
        return deepcopy(state['agents']['_sources'][agent_id])
    except (KeyError, TypeError):
        raise LineageError('internal', 'birth constitution unavailable') from None


def _peer(name):
    try:
        return importlib.import_module('lineage.domain.' + name)
    except (ImportError, AttributeError):
        raise LineageError('internal', 'required agent dependency unavailable') from None


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except LineageError as exc:
        raise LineageError(exc.code, 'agent dependency refused the operation') from None
    except Exception as exc:
        code = getattr(exc, 'code', 'internal')
        if code not in ('bad_args', 'conflict', 'hash_mismatch', 'memory_debt'):
            code = 'internal'
        raise LineageError(code, 'agent dependency refused the operation') from None


def _verify_immutable(record, *, ctx, history=None):
    references = _peer('references')
    _call(references.require_pins, record['references'], ctx=ctx)
    skills = _peer('skills')
    for pin in record['skills']:
        if history is None:
            # Public queries recheck immutable package bytes with the owner's API.
            skill_ctx = ctx if hasattr(ctx, 'home') else SimpleNamespace(home=_home(ctx))
            value = _call(skills.get, pin['skill_id'], sha256=pin['sha256'], ctx=skill_ctx)['skill']
        else:
            # A public skill query would recursively take the journal lock.
            versions = skills._catalogue(history).get(pin['skill_id'], {})
            row = versions.get(pin['sha256'])
            if row is None:
                raise LineageError('bad_args', 'pinned skill does not exist')
            value = _call(skills._skill, row)
            if ctx is not None:
                _call(skills._verify_projection, _home(ctx), pin['skill_id'], pin['sha256'], value['files'])
        raw, digest = _call(skills.package, value['files'])
        if digest != pin['sha256']:
            raise LineageError('hash_mismatch', 'pinned skill bytes differ')


def _data(name):
    path = _ROOT / 'lineage' / 'domain' / 'data' / name
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError
        with os.fdopen(fd, 'rb') as stream:
            fd = None
            raw = stream.read(1048577)
            if len(raw) > 1048576:
                raise ValueError
            def pairs(items):
                result = {}
                for key, value in items:
                    if key in result:
                        raise ValueError
                    result[key] = value
                return result
            def nonfinite(value):
                raise ValueError
            # U02's transport decoder caps bytes below this bundled policy's
            # size. Decode local data strictly, then use its JSON validator.
            value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                               parse_constant=nonfinite)
            schema.validate(value, {})
            return value
    except Exception:
        raise LineageError('internal', 'bundled constitution policy unavailable') from None
    finally:
        if fd is not None:
            os.close(fd)


def _compile(record, overlays, *, ctx):
    compiler, references = _peer('constitution'), _peer('references')
    if overlays:
        # The installed overlay package has policy entries, but no named-id seam.
        raise LineageError('bad_args', 'named constitution overlay unavailable')
    rules = _call(references.load_gold_rules)
    raw = _canonical(rules)
    compiled = _call(compiler.compile_constitution,
                     registry_bytes=raw, expected_registry_sha256=sha256(raw).hexdigest(),
                     expected_source_sha256=rules['source']['sha256'],
                     role_ids=(_ROLES[record['workflow']],),
                     language=(record['language'] if record['language'] in compiler._LANGUAGES else 'general'),
                     role_matrix=_data('role_matrix.json'), overlays=_data('overlays.json'))
    try:
        result = compiled.markdown
        if (type(result) is not bytes or not result.endswith(b'\n') or b'\r' in result
                or sha256(result).hexdigest() != compiled.sha256):
            raise ValueError
        text = result.decode('utf-8')
        citations = _CITATION.findall(text)
        by_id = {row['id']: row for row in rules['rules']}
        for rule_id, section in citations:
            row = by_id.get(rule_id)
            if row is None or section != row['section'] + ':L' + str(row['lines'][0]) + '-L' + str(row['lines'][1]):
                raise ValueError
        included = sorted(disposition.rule_id for disposition in compiled.dispositions
                          if disposition.decision == 'included')
        if sorted(rule for rule, _ in citations) != included:
            raise ValueError
        return {'text': text, 'overlays': list(overlays), 'rule_ids': included}
    except (AttributeError, TypeError, KeyError, ValueError, UnicodeError):
        raise LineageError('internal', 'compiled constitution evidence invalid') from None


def _constitution_integrity(record, source):
    if type(source) is not dict or set(source) != {'text', 'overlays', 'rule_ids'}:
        raise LineageError('bad_args', 'invalid constitution source fields')
    try:
        raw = source['text'].encode('utf-8')
        if (not raw.endswith(b'\n') or b'\r' in raw
                or sha256(raw).hexdigest() != record['constitution_sha256']):
            raise LineageError('hash_mismatch', 'constitution bytes differ')
        parsed = sorted(set(rule for rule, _ in _CITATION.findall(source['text'])))
        if type(source['rule_ids']) is not list or parsed != sorted(source['rule_ids']):
            raise LineageError('bad_args', 'constitution citation ids differ')
    except (AttributeError, TypeError, KeyError, UnicodeError):
        raise LineageError('bad_args', 'invalid constitution source') from None


def _entry_capacity(record):
    entry = _peer('memory.entry')
    try:
        return entry.build(record, (), token_count=None)
    except LineageError:
        # A-TOK1 is enforced by U11, including refusal when its proven byte
        # bound is insufficient and no verified token counter is available.
        raise
    except Exception:
        raise LineageError('internal', 'candidate memory entry unavailable') from None


def _validate_born(history, event, ctx=None):
    payload = event.get('payload')
    if type(payload) is not dict or set(payload) != {'record', 'inherited_units', 'rejected_units', 'constitution'}:
        raise LineageError('bad_args', 'invalid birth payload fields')
    record = payload['record']
    if type(record) is not dict:
        raise LineageError('bad_args', 'invalid agent record')
    if type(record.get('born')) is not dict:
        raise LineageError('bad_args', 'invalid birth provenance')
    if record['born'].get('op') != 'genesis':
        # A-U12-2: this module owns the agent.born validator; inheritance births
        # (clone/distill/cross/mutate/specialize) are admitted by their owner,
        # lineage.domain.breeding, which needs the runtime home-aware context.
        # Without a context, or without an integrated breeding peer, refuse.
        if ctx is None:
            raise LineageError('internal', 'pure inheritance admission unavailable')
        _peer('breeding').validate_birth(history, event, ctx=ctx)
        return
    # Reuse U10's installed closed-record schema adapter over the U02 validator.
    from .memory.schema import _shape
    _shape(record, 'agent.schema.json')
    if type(payload['constitution']) is not dict:
        raise LineageError('bad_args', 'invalid constitution source')
    args = _create_args(*(record[key] for key in ('agent_id', 'display_name', 'workflow', 'language',
                         'allowed_seats', 'references', 'skills')), payload['constitution'].get('overlays', ()))
    if any(old['kind'] == 'agent.born' and old['payload']['record']['agent_id'] == record['agent_id']
           for old in history):
        raise LineageError('conflict', 'agent identity already exists')
    if (record['parents'] or record['generation'] != 0 or record['memory_gen'] != 0
            or record['status'] != 'draft' or 'promoted_seat' in record or 'rule_overrides' in record
            or payload['inherited_units'] or payload['rejected_units']
            or record['born'] != {'op': 'genesis', 'event_id': event.get('id')}):
        raise LineageError('bad_args', 'invalid genesis facts')
    _constitution_integrity(record, payload['constitution'])
    if record['agent_version'] != agent_version(record['constitution_sha256'], record['skills'], record['memory_gen']):
        raise LineageError('hash_mismatch', 'agent version differs')
    raw = brief.build(record, (), rule_ids=payload['constitution']['rule_ids'])
    brief._bounded(raw)
    if sha256(raw).hexdigest() != record['brief_head_sha256']:
        raise LineageError('hash_mismatch', 'birth brief digest differs')
    _verify_immutable(record, ctx=ctx, history=history)
    source = _compile(record, args['overlays'], ctx=ctx)
    if source != payload['constitution']:
        raise LineageError('hash_mismatch', 'birth constitution differs from compilation')
    _entry_capacity(record)


def _validate_status(history, event, ctx=None):
    # A-U12-2: delegate each status transition to the integrated owner of its
    # policy (retirement: lineage.domain.breeding; promotion: lineage.domain.
    # promotion). Fields never prove admission; without an owner or a runtime
    # context the transition is refused.
    payload = event.get('payload')
    if ctx is None or type(payload) is not dict:
        raise LineageError('internal', 'status policy and selected-seat contract unavailable')
    if payload.get('to') == 'retired' and 'seat' not in payload:
        _peer('breeding').validate_retirement(history, event, ctx=ctx)
        return
    owner = getattr(_peer('promotion'), 'validate_status', None)
    if not callable(owner):
        raise LineageError('internal', 'status policy and selected-seat contract unavailable')
    owner(history, event, ctx=ctx)


class _AgentsFold:
    order = 40
    kinds = frozenset(('agent.born', 'agent.status', 'memory.put', 'memory.retire'))

    def __call__(self, state, event):
        if event['kind'] not in self.kinds:
            return
        namespace = state.setdefault('agents', {})
        payload = event['payload']
        if event['kind'] == 'agent.born':
            record = deepcopy(payload['record'])
            agent_id = record['agent_id']
            if agent_id in namespace:
                raise LineageError('internal', 'duplicate committed identity')
            namespace[agent_id] = record
            namespace.setdefault('_sources', {})[agent_id] = deepcopy(payload['constitution'])
            # Admission established these captured facts. A fold must not
            # rewrite the immutable birth result while initializing its state.
            return
        else:
            agent_id = payload['agent_id']
            if agent_id not in namespace:
                raise LineageError('internal', 'event has no committed agent')
            record = namespace[agent_id]
            if event['kind'] == 'agent.status':
                record['status'] = payload['to']
                if 'seat' in payload:
                    if payload['seat'] not in record['allowed_seats']:
                        raise LineageError('seat_not_allowed', 'selected seat is not admitted')
                    record['promoted_seat'] = deepcopy(payload['seat'])
                return
        record = namespace[agent_id]
        counter = state.get('memory', {}).get(agent_id, {}).get('memory_gen', record['memory_gen'])
        if counter == record['memory_gen']:
            return
        record['memory_gen'] = counter
        record['agent_version'] = agent_version(record['constitution_sha256'], record['skills'], counter)
        raw = brief.build(record, _units(state, agent_id), rule_ids=_source(state, agent_id)['rule_ids'])
        namespace.setdefault('_brief_heads', {})[agent_id] = sha256(raw).hexdigest()


def _agreement(data, command, ctx):
    try:
        supplied = deepcopy(command.args)
        supplied.setdefault('overlays', [])
        _check('agent_create', supplied)
        _match(command.agent, _AGENT)
        _match(command.op_id, _OP)
        if (command.agent != supplied['agent'] or command.op_id != supplied['op_id']
                or command.expected_head != supplied.get('expected_head')
                or any(supplied[key] != val for key, val in data.items())):
            raise ValueError
        if (type(command.tool) is not str or not command.tool
                or getattr(ctx, 'actor', None) != command.agent
                or (getattr(ctx, 'op_id', None) is not None and ctx.op_id != command.op_id)):
            raise ValueError
        _canonical(supplied)
        return _Command(command.tool, supplied, command.agent, command.op_id, command.expected_head)
    except LineageError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError):
        raise LineageError('bad_args', 'command differs from effective arguments') from None


def create(agent_id: str, display_name: str, workflow: str, language: str,
           allowed_seats: Sequence[dict], references: Sequence[dict],
           skills: Sequence[dict], *, overlays: Sequence[str] = (), command, ctx) -> _Committed:
    data = _create_args(agent_id, display_name, workflow, language, allowed_seats, references, skills, overlays)
    effective = _agreement(data, command, ctx)
    request = {key: value for key, value in effective.args.items() if key not in ('op_id', 'expected_head')}
    request = {'tool': effective.tool, 'args': request}
    # Public dependency reads occur outside the ledger callback. Retain any
    # refusal until prepare: U03 must first get the chance to recognize replay
    # or changed content, ahead of mutable current-state admission.
    dependency_error = None
    try:
        _verify_immutable(data, ctx=ctx)
    except LineageError as exc:
        dependency_error = exc

    def prepare(history, draft):
        head = history[-1]['lamport'] if history else 0
        if effective.expected_head is not None and effective.expected_head != head:
            raise LineageError('stale_rev', 'expected head differs')
        if effective.tool != 'agent_create':
            raise LineageError('bad_args', 'creation command has a different tool')
        if head >= _SAFE or not _EVENT_ID.fullmatch(draft.get('id', '')):
            raise LineageError('internal', 'journal-owned birth identity unavailable')
        if any(old['kind'] == 'agent.born' and old['payload']['record']['agent_id'] == agent_id for old in history):
            raise LineageError('conflict', 'agent identity already exists')
        if dependency_error is not None:
            raise dependency_error
        _verify_immutable(data, ctx=ctx, history=history)
        source = _compile(data, data['overlays'], ctx=ctx)
        record = {key: deepcopy(data[key]) for key in ('agent_id', 'display_name', 'workflow', 'language',
                                                       'allowed_seats', 'references')}
        record.update(schema='lineage.agent/v1', skills=_pins(data['skills']),
                      constitution_sha256=sha256(source['text'].encode()).hexdigest(),
                      memory_gen=0, generation=0, parents=[],
                      born={'op': 'genesis', 'event_id': draft['id']}, status='draft')
        record['agent_version'] = agent_version(record['constitution_sha256'], record['skills'], 0)
        raw = brief.build(record, (), rule_ids=source['rule_ids'])
        brief._bounded(raw)
        record['brief_head_sha256'] = sha256(raw).hexdigest()
        _entry_capacity(record)
        return {'record': record, 'constitution': source, 'inherited_units': [], 'rejected_units': []}

    def validate(history, event):
        validators = ctx.services.registry.validators if hasattr(ctx, 'services') else ctx.validators
        callback = validators.get('agent.born')
        if callback is None:
            raise LineageError('internal', 'registered birth admission unavailable')
        callback(history, event)
    try:
        # The integrated journal admits K0 operation ids unchanged; transport
        # commit witnesses and journal replay share this exact identity.
        event = journal.transact(_home(ctx), agent=effective.agent,
                                 op_id=effective.op_id,
                                 kind='agent.born', payload=request,
                                 validators={'agent.born': validate}, prepare=prepare,
                                 clock=getattr(getattr(ctx, 'services', None), 'clock', None),
                                 id_factory=getattr(getattr(ctx, 'services', None), 'id_factory', None))
        result = {'record': deepcopy(event['payload']['record']),
                  'commit': {'event_ids': [event['id']], 'head': event['lamport'], 'sha256': event['sha256']}}
        _canonical(result)
    except LineageError as exc:
        raise LineageError(exc.code, 'agent creation refused') from None
    except Exception:
        raise LineageError('internal', 'agent creation unavailable') from None
    try:
        # Replay repairs the present prefix while returning the original result.
        materialize(agent_id, snapshot=_history(ctx), ctx=ctx, _preserve_unchanged=True)
    except Exception:
        raise LineageError('internal', 'committed agent projections unavailable') from None
    return _Committed(deepcopy(event), deepcopy(result), event['lamport'], event['sha256'])


def get(agent_id: str, *, ctx) -> dict:
    _target(agent_id)
    return {'record': _record(_state(_history(ctx), ctx), agent_id)}


def list_agents(*, workflow: str | None = None, language: str | None = None,
                status: str | None = None, include_retired: bool = False,
                after: str | None = None, limit: int = 100, ctx) -> dict:
    args = {'include_retired': include_retired, 'limit': limit}
    for key, value in (('workflow', workflow), ('language', language), ('status', status), ('after', after)):
        if value is not None:
            args[key] = value
    _check('agent_list', args)
    if language is not None:
        _text(language, 64)
    if after is not None:
        _target(after)
    history = _history(ctx)
    state = _state(history, ctx)
    selected = []
    for agent_id in sorted(state.get('agents', {})):
        if agent_id.startswith('_'):
            continue
        record = _record(state, agent_id)
        if (workflow is not None and record['workflow'] != workflow
                or language is not None and record['language'] != language
                or status is not None and record['status'] != status
                or not include_retired and status != 'retired' and record['status'] == 'retired'
                or after is not None and agent_id <= after):
            continue
        selected.append(record)
    page = selected[:limit]
    return {'agents': deepcopy(page),
            'next_after': page[-1]['agent_id'] if len(selected) > limit else None,
            'head': history[-1]['lamport'] if history else 0}


def _same(a, b):
    return (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)


@contextmanager
def _directory(path, *, create=False, relative_root=None):
    """Pin every component; validate ancestry again at each publication gate."""
    descriptors, links = [], []
    try:
        path = Path(path)
        if not path.is_absolute():
            raise OSError
        fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        coordinate = Path(path.anchor)
        for name in path.parts[1:]:
            coordinate /= name
            if name in ('', '.', '..'):
                raise OSError
            try:
                before = os.stat(name, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                if not create:
                    yield None, lambda: None
                    return
                os.mkdir(name, 0o700, dir_fd=fd)
                os.fsync(fd)
                before = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                if relative_root is not None:
                    raise LineageError('internal', 'unsafe projection path: ' +
                                       coordinate.relative_to(relative_root).as_posix())
                raise OSError
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(child)
            links.append((fd, name, child))
            if not _same(before, os.fstat(child)):
                raise OSError
            fd = child
        def guard():
            for parent, name, child in links:
                current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if not stat.S_ISDIR(current.st_mode) or not _same(current, os.fstat(child)):
                    raise OSError
        guard()
        yield fd, guard
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def _destinations(fd):
    for name in _FILES:
        try:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise LineageError('internal', 'unsafe agent projection: ' + name)


def _unchanged_projection(fd, name, raw, guard):
    try:
        source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    except FileNotFoundError:
        return False
    try:
        before = os.fstat(source)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise OSError
        chunks, remaining = [], len(raw) + 1
        while remaining:
            block = os.read(source, min(remaining, 65536))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        named = os.stat(name, dir_fd=fd, follow_symlinks=False)
        after = os.fstat(source)
        stamp = lambda info: (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
                              info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if stamp(before) != stamp(after) or stamp(before) != stamp(named):
            raise OSError
        guard()
        return b''.join(chunks) == raw
    finally:
        os.close(source)


def _publish(fd, name, raw, guard):
    # Replacing regular entries avoids following a swapped symlink; all writes
    # and renames remain relative to the same pinned directory descriptor.
    guard()
    _destinations(fd)
    temporary = '.agent-stage-' + secrets.token_hex(16)
    target = None
    try:
        target = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        view = memoryview(raw)
        while view:
            written = os.write(target, view)
            if written <= 0:
                raise OSError
            view = view[written:]
        os.fsync(target)
        os.close(target)
        target = None
        guard()
        _destinations(fd)
        os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
        guard()
        _destinations(fd)
        os.fsync(fd)
    finally:
        if target is not None:
            os.close(target)
        try:
            os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError:
            pass


def _memory_context(ctx):
    from lineage.core import registry
    if hasattr(ctx, 'services'):
        return ctx
    services = registry.Services(home=_home(ctx), repo_root=_ROOT,
                                 registry=SimpleNamespace(folds=ctx.folds, validators=ctx.validators),
                                 token_count=None)
    return registry.Context(services=services, actor=ctx.actor or 'system')


def materialize(agent_id: str, *, snapshot, ctx, _preserve_unchanged=False) -> tuple[Path, ...]:
    """Publish derived files only for an authenticated current committed prefix."""
    _target(agent_id)
    history = _events(snapshot)
    if history != _history(ctx):
        raise LineageError('internal', 'stale projection snapshot')
    state = _state(history, ctx)
    record, source = _record(state, agent_id), _source(state, agent_id)
    _constitution_integrity(record, source)
    raw = brief.build(record, _units(state, agent_id), rule_ids=source['rule_ids'])
    brief._bounded(raw)
    if sha256(raw).hexdigest() != record['brief_head_sha256']:
        raise LineageError('hash_mismatch', 'authoritative brief digest differs')
    contents = _projection_bytes(history, agent_id=agent_id, state=state)
    directory = layout.agent_dir(_home(ctx), workflow=record['workflow'],
                                 language=record['language'], agent_id=agent_id)
    try:
        # Unsafe existing destinations must refuse before any coordination file
        # or projection is created, including a sibling destination symlink.
        with _directory(directory, relative_root=_home(ctx)) as (fd, guard):
            if fd is not None:
                _destinations(fd)
                guard()
        with _directory(_home(ctx) / '.agent-locks', create=True) as (locks, lock_guard):
            lock = os.open(agent_id + '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=locks)
            try:
                identity = os.fstat(lock)
                if not stat.S_ISREG(identity.st_mode) or identity.st_nlink != 1:
                    raise OSError
                locking.lock_exclusive(lock)
                try:
                    lock_guard()
                    named = os.stat(agent_id + '.lock', dir_fd=locks, follow_symlinks=False)
                    if not stat.S_ISREG(named.st_mode) or not _same(identity, named):
                        raise OSError
                    if history != _history(ctx):
                        raise LineageError('internal', 'stale projection snapshot')
                    with _directory(directory, create=True, relative_root=_home(ctx)) as (fd, guard):
                        _destinations(fd)
                        for name in _FILES:
                            if not _preserve_unchanged or not _unchanged_projection(fd, name, contents[name], guard):
                                _publish(fd, name, contents[name], guard)
                        guard()
                    # Memory rebuilds ledger-derived generations inside the same agent home.
                    store = _peer('memory.store')
                    memory_ctx = _memory_context(ctx)
                    from .memory import _snapshot_of
                    memory_snapshot = _snapshot_of(history, memory_ctx)
                    memory_files = store.rebuild(agent_id, snapshot=memory_snapshot, ctx=memory_ctx)
                finally:
                    locking.unlock(lock)
            finally:
                os.close(lock)
        return tuple(directory / name for name in _FILES) + tuple(memory_files)
    except LineageError as exc:
        detail = (exc.detail if exc.detail and 'projection' in exc.detail
                  else 'agent projection publication refused')
        if detail.startswith('unsafe agent projection: '):
            coordinate = directory.relative_to(_home(ctx)) / detail.split(': ', 1)[1]
            detail = 'agent projection publication refused: ' + coordinate.as_posix()
        code = exc.code if exc.code == 'hash_mismatch' else 'internal'
        raise LineageError(code, detail) from None
    except Exception:
        raise LineageError('internal', 'agent projection publication refused') from None


def _scorecard_bytes(history, *, agent_id):
    try:
        return scorecard.projection_bytes(history, agent_id=agent_id)
    except LineageError as exc:
        # The integrated telemetry fold rejects path-like languages although
        # agent language is arbitrary text. Adapt only that unused birth field;
        # retain every seat, outcome, cost and other scoring input unchanged.
        if exc.code != 'internal':
            raise
        languages = [event['payload']['record']['language'] for event in history
                     if event['kind'] == 'agent.born']
        if not any(language in ('.', '..') or any(c in language for c in ('/', '\\', '\x00'))
                   or re.match(r'[A-Za-z]:', language) for language in languages):
            raise
    telemetry = deepcopy(history)
    for event in telemetry:
        if event['kind'] == 'agent.born':
            record = event['payload']['record']
            record['language'] = layout.language_component(record['language'])
    return scorecard.projection_bytes(telemetry, agent_id=agent_id)


def _projection_bytes(history, *, agent_id, state=None):
    """Rebuild the four projection files from one verified committed prefix."""
    if state is None:
        from .memory import fold as memory_fold
        state, agent_fold = {}, _AgentsFold()
        for event in history:
            memory_fold.apply(state, deepcopy(event))
            agent_fold(state, deepcopy(event))
    record, source = _record(state, agent_id), _source(state, agent_id)
    return {'agent.json': _canonical(record),
            'CONSTITUTION.md': source['text'].encode('utf-8'),
            'BRIEF_HEAD.md': brief.build(record, _units(state, agent_id), rule_ids=source['rule_ids']),
            'scorecard.json': _scorecard_bytes(history, agent_id=agent_id)}


def refresh_projections(agent_id: str, *, ctx) -> tuple[Path, ...]:
    """Publish the current verified record, scorecard, brief and memory files."""
    return materialize(agent_id, snapshot=_history(ctx), ctx=ctx, _preserve_unchanged=True)
