"""Current-prefix memory witnesses for mandatory task closure.

Only committed memory.put content can earn credit. The folded view determines
whether that original content is still active; receipts are read again at close.
No projections, token estimates or inherited context waive the closing duty.
"""
from __future__ import annotations

from copy import deepcopy
import errno
import hashlib
import os
from pathlib import Path
import re
import stat
from types import SimpleNamespace

from lineage.core import journal
from lineage.core.errors import LineageError
from .memory import fold as memory_fold, schema as memory_schema
from .version import agent_version

_PATH = re.compile(r'[A-Za-z0-9._/-]{1,512}')


def _home(ctx):
    services = getattr(ctx, 'services', None)
    home = getattr(services, 'home', None) if services is not None else getattr(ctx, 'home', None)
    if home is None:
        raise LineageError('internal', 'evidence runtime unavailable')
    return Path(home)


def _snapshot(history, ctx):
    """Adapt the installed history API without taking another journal lock."""
    history = tuple(deepcopy(getattr(history, 'events', history)))
    services = getattr(ctx, 'services', None)
    registry = getattr(services, 'registry', None)
    folds = registry.folds if registry is not None else getattr(ctx, 'folds', None)
    if folds is None or not callable(folds.get('agents')) or not callable(folds.get('memory')):
        raise LineageError('internal', 'required committed folds unavailable')
    state = {}
    ordered = sorted(folds.items(), key=lambda item: (getattr(item[1], 'order', 0), item[0]))
    for event in history:
        for _, callback in ordered:
            callback(state, deepcopy(event))
    return SimpleNamespace(events=history, state=state,
        head=history[-1]['lamport'] if history else 0)


def _opening(snapshot, run_id):
    for event in snapshot.events:
        if event['kind'] == 'run.open' and event['payload']['run_id'] == run_id:
            return event
    raise LineageError('no_run', 'committed opening unavailable')


def _agent(snapshot, agent_id):
    record = snapshot.state.get('agents', {}).get(agent_id)
    if record is None or agent_id in ('operator', 'system'):
        raise LineageError('no_agent', 'committed agent unavailable')
    return record


def _eligible(snapshot, run_id, actor, ctx, *, closing=True):
    opening = _opening(snapshot, run_id)
    agent_id = opening['payload']['agent_id']
    if actor != getattr(ctx, 'actor', actor):
        raise LineageError('bad_args', 'actor_mismatch')
    if getattr(ctx, 'authority', 'tool') == 'tool' and actor != agent_id:
        raise LineageError('bad_args', 'actor_mismatch')
    if any(event['kind'] == 'run.close' and event['payload']['record']['run_id'] == run_id
           for event in snapshot.events):
        raise LineageError('run_closed', 'run is already closed')
    agent = _agent(snapshot, agent_id)
    if closing and agent['status'] == 'retired':
        raise LineageError('conflict', 'agent is retired')
    promotion = snapshot.state.get('promotion', {}).get(agent_id, {})
    if closing and isinstance(promotion, dict) and promotion.get('status') == 'retired':
        raise LineageError('conflict', 'agent is retired')
    return opening, agent


def _coordinate(path):
    if (type(path) is not str or _PATH.fullmatch(path) is None
            or any(part in ('', '.', '..') for part in path.split('/'))
            or path.split('/')[0] in ('ledger', 'family')):
        raise LineageError('bad_args', 'invalid evidence path')


def _evidence(receipt, ctx):
    """Pin directories, refuse links, and never block on a non-regular file."""
    _coordinate(receipt['path'])
    descriptors = []
    try:
        directory = os.open(_home(ctx), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(directory)
        parts = receipt['path'].split('/')
        for index, part in enumerate(parts):
            before = os.stat(part, dir_fd=directory, follow_symlinks=False)
            if stat.S_ISLNK(before.st_mode):
                raise LineageError('bad_args', 'symlink evidence path')
            final = index == len(parts) - 1
            if final and not stat.S_ISREG(before.st_mode):
                raise LineageError('hash_mismatch', 'evidence is not a regular file')
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if not final:
                flags |= os.O_DIRECTORY
            source = os.open(part, flags, dir_fd=directory)
            descriptors.append(source)
            actual = os.fstat(source)
            if (before.st_dev, before.st_ino) != (actual.st_dev, actual.st_ino):
                raise LineageError('hash_mismatch', 'evidence changed during resolution')
            directory = source
        initial = os.fstat(source)
        if not stat.S_ISREG(initial.st_mode):
            raise LineageError('hash_mismatch', 'evidence is not a regular file')
        digest = hashlib.sha256()
        while True:
            chunk = os.read(source, 65536)
            if not chunk:
                break
            digest.update(chunk)
        final = os.fstat(source)
        if ((initial.st_size, initial.st_mtime_ns, initial.st_ctime_ns)
                != (final.st_size, final.st_mtime_ns, final.st_ctime_ns)
                or digest.hexdigest() != receipt['sha256']):
            raise LineageError('hash_mismatch', 'evidence digest mismatch')
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise LineageError('bad_args', 'symlink evidence path') from None
        raise LineageError('hash_mismatch', 'evidence unavailable') from None
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _units(snapshot, agent_id):
    owner = snapshot.state.get('memory', {}).get(agent_id, {})
    if 'units' in owner:
        values = memory_fold.units_for(snapshot.state, agent_id,
            include_inactive=True, include_private=True)
        return {unit['id']: unit for unit in values}
    # Callable folds in the native registry may expose a flat unit-id map.
    return deepcopy(owner)


def _graph_valid(unit, units):
    """Check the selected unit's reciprocal replacement ancestry."""
    active, visited = set(), set()
    def visit(current):
        identifier = current['id']
        if identifier in active:
            return False
        if identifier in visited:
            return True
        active.add(identifier)
        for predecessor_id in current['supersedes']:
            predecessor = units.get(predecessor_id)
            if (predecessor is None or predecessor.get('status') != 'superseded'
                    or predecessor.get('superseded_by') != identifier or not visit(predecessor)):
                return False
        active.remove(identifier)
        visited.add(identifier)
        return True
    return 'superseded_by' not in unit and visit(unit)


def _valid(snapshot, event, opening, agent, kind, outcome, cost, ctx):
    payload, frozen = event['payload'], opening['payload']
    unit = payload.get('unit')
    if type(unit) is not dict:
        return None
    units = _units(snapshot, payload['agent_id'])
    current = units.get(unit.get('id'))
    if (current is None or current != unit or unit.get('status') != 'active'
            or unit.get('privacy') not in ('public', 'internal')
            or unit.get('kind') != kind or unit.get('level') not in (2, 3)):
        return None
    provenance = unit.get('provenance', {})
    if (event['agent'] != payload['agent_id'] or payload['agent_id'] != frozen['agent_id']
            or provenance.get('actor') != frozen['agent_id']
            or provenance.get('run_id') != frozen['run_id']):
        return None
    scope = unit.get('scope', {})
    if (scope.get('workflow') != agent['workflow']
            or scope.get('language') not in (agent['language'], 'general')):
        return None
    try:
        # Check excluded coordinates before U10 can read any receipt.
        for receipt in unit.get('receipts', ()):
            _coordinate(receipt['path'])
        memory_schema.validate_unit(unit, authority='tool', actor=event['agent'], ctx=ctx)
        if not _graph_valid(unit, units):
            return None
        if unit['level'] == 2 and not unit['receipts']:
            return None
        for receipt in unit['receipts']:
            _evidence(receipt, ctx)
    except LineageError as exc:
        if exc.code == 'internal':
            raise
        return None
    except (KeyError, TypeError, ValueError, RecursionError):
        return None
    if kind == 'episode':
        body = unit['body']
        if (body['run_id'] != frozen['run_id'] or body['task_id'] != frozen['task']['id']
                or body['seat'] != frozen['seat'] or body['parents_context'] != frozen['parents_context']
                or body['outcome'] != outcome or body['cost'] != cost):
            return None
    return deepcopy(unit)


def _selection(snapshot, run_id, outcome, cost, *, actor, ctx):
    """Return the minimal witnesses, or distinguish absence from invalid proof."""
    opening, agent = _eligible(snapshot, run_id, actor, ctx)
    candidates, original_ids = [], set()
    for event in snapshot.events:
        payload = event['payload']
        if event['kind'] == 'agent.born':
            for inherited in payload.get('inherited_units', ()):
                original_ids.add((payload['record']['agent_id'], inherited['unit']['id']))
        if event['kind'] != 'memory.put':
            continue
        identity = (payload.get('agent_id'), payload.get('unit', {}).get('id'))
        if identity in original_ids:
            continue
        original_ids.add(identity)
        if (event['lamport'] <= opening['lamport']
                or payload.get('agent_id') != opening['payload']['agent_id']
                or payload.get('run_id') != run_id):
            continue
        candidates.append(event)
    episodes = [event for event in candidates if event['payload'].get('unit', {}).get('kind') == 'episode']
    if not episodes:
        raise LineageError('memory_required', 'current-run episode required')
    kinds = ['episode']
    if outcome['verdict'] in ('error', 'HOLD', 'red') or outcome['repair_loops'] > 0:
        kinds.append('lesson')
    if outcome['verdict'] in ('HOLD', 'red'):
        kinds.append('negative')
    selected = []
    for kind in kinds:
        alternatives = sorted((event for event in candidates
            if event['payload'].get('unit', {}).get('kind') == kind),
            key=lambda event: event['payload']['unit'].get('id', ''))
        for event in alternatives:
            unit = _valid(snapshot, event, opening, agent, kind, outcome, cost, ctx)
            if unit is not None:
                selected.append(unit)
                break
        else:
            raise LineageError('memory_debt', 'valid current-run ' + kind + ' required')
    return tuple(sorted(selected, key=lambda unit: unit['id']))


def check(snapshot, run_id: str, outcome: dict, cost: dict, *, actor: str, ctx) -> dict:
    # Use U02 for direct callers too; tool argument validation is not authority.
    properties = memory_schema._STORE.load('run.schema.json')['properties']
    try:
        memory_schema._validate(outcome, properties['outcome'], store=memory_schema._STORE)
        memory_schema._validate(cost, properties['cost'], store=memory_schema._STORE)
    except memory_schema.boundary.SchemaError:
        raise LineageError('bad_args', 'invalid close values') from None
    selected = _selection(snapshot, run_id, outcome, cost, actor=actor, ctx=ctx)
    receipts = sorted({(receipt['path'], receipt['sha256'])
        for unit in selected for receipt in unit['receipts']})
    if len(receipts) > 256:
        raise LineageError('memory_debt', 'memory receipt capacity exceeded')
    return {'passed': True,
        'checks': [{'id': unit['kind'], 'passed': True} for unit in selected]
            + [{'id': 'token_ceiling', 'passed': True, 'detail': 'not measured'}],
        'memory_receipts': [{'path': path, 'sha256': digest} for path, digest in receipts]}
