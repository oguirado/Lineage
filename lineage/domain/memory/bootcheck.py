"""Independent resume observations and positive, read-only evidence checks."""
from __future__ import annotations

import hashlib
import os
import re

from lineage.core.errors import LineageError
from . import entry, fold, store

_HASH = re.compile(r'[0-9a-f]{64}')
_FIELDS = {'agent_version', 'memory_gen', 'head', 'entry_sha256'}


def _fail(code, detail):
    raise LineageError(code, ('E_BOOTCHECK ' + detail)[:2048])


def _observed(observed):
    if type(observed) is not dict or set(observed) != _FIELDS:
        _fail('bad_args', 'observed values must have exactly the required fields')
    for field in ('agent_version', 'entry_sha256'):
        if type(observed[field]) is not str or _HASH.fullmatch(observed[field]) is None:
            _fail('bad_args', 'invalid observed ' + field)
    for field in ('memory_gen', 'head'):
        if type(observed[field]) is not int or not 0 <= observed[field] <= store._SAFE:
            _fail('bad_args', 'invalid observed ' + field)


def expected(agent_id, *, snapshot, ctx):
    """Derive values from authority, without consulting mutable projections."""
    agent = store._snapshot_agent(agent_id, snapshot)
    try:
        units = fold.units_for(snapshot.state, agent_id)
        raw = entry.build(agent, units, token_count=ctx.services.token_count)
    except LineageError as exc:
        if exc.code == 'memory_debt':
            _fail('bad_op', 'entry capacity cannot be verified')
        raise
    return {'agent_version': agent['agent_version'], 'memory_gen': agent['memory_gen'],
            'head': snapshot.head, 'entry_sha256': hashlib.sha256(raw).hexdigest()}


def _receipts(agent_id, snapshot):
    agent = store._snapshot_agent(agent_id, snapshot)
    result = {}
    for unit in fold.units_for(snapshot.state, agent_id):
        if not entry.eligible(agent, unit):
            continue
        receipts = unit['receipts']
        if unit['level'] == 2 and not receipts:
            _fail('hash_mismatch', 'required unit receipt is absent')
        for evidence in receipts:
            key = evidence['path']
            if key in result and result[key] != evidence['sha256']:
                _fail('hash_mismatch', 'conflicting required evidence hashes')
            result[key] = evidence['sha256']
    runs, born = {}, False
    for event in snapshot.events:
        payload = event['payload']
        if event['kind'] == 'run.open':
            runs[payload['run_id']] = payload['agent_id']
        if event['kind'] == 'agent.born' and payload['record']['agent_id'] == agent_id:
            born = True
        if born and store._selected(event, agent_id, runs):
            for evidence in event['evidence']:
                path, digest = evidence['path'], evidence['sha256']
                if path in result and result[path] != digest:
                    _fail('hash_mismatch', 'conflicting required evidence hashes')
                result[path] = digest
    return result


def _evidence(ctx, required):
    witnesses = {}
    try:
        with store._directory(ctx.services.home) as root:
            for path, expected_hash in sorted(required.items()):
                parts = store._parts(path)
                if parts[0] in {'ledger', 'family'}:
                    _fail('hash_mismatch', 'required evidence has a forbidden relative root')
                with store._file(root, path) as fd:
                    digest = hashlib.sha256()
                    before = store._stamp(os.fstat(fd))
                    while True:
                        chunk = os.read(fd, 65536)
                        if not chunk:
                            break
                        digest.update(chunk)
                    if digest.hexdigest() != expected_hash:
                        _fail('hash_mismatch', 'required evidence digest differs: ' + path)
                    witnesses[path] = before
        return witnesses
    except (OSError, LineageError) as exc:
        error = store._io_error(exc)
        if error.code == 'internal':
            raise LineageError('internal', 'required evidence I/O unavailable') from None
        _fail('hash_mismatch', 'required evidence absent, changed or unsafe')


def _projection(agent_id, snapshot, ctx):
    issues = store.verify_projection(agent_id, snapshot=snapshot, ctx=ctx)
    if issues is None or not isinstance(issues, tuple):
        _fail('bad_op', 'projection verification incomplete')
    if issues:
        if any(issue.get('code') == 'internal' for issue in issues):
            raise LineageError('internal', 'projection verification I/O unavailable')
        _fail('hash_mismatch', 'required projection differs: ' + issues[0]['path'])


def _entry_bytes(agent_id, snapshot, values, ctx):
    """Verify pointer and both entry copies independently of supplied hashes."""
    mapping = store._mapping(agent_id, snapshot, ctx)
    pointer = mapping['CURRENT']
    selected = pointer.decode('ascii').rstrip('\n')
    try:
        with store._directory(store._root(agent_id, ctx)) as root:
            if store._read(root, 'CURRENT', maximum=len(pointer)) != pointer:
                _fail('hash_mismatch', 'CURRENT does not select the committed generation')
            for path in (selected + '/MEMORY_ENTRY.static.md', 'MEMORY_ENTRY.static.md'):
                raw = store._read(root, path, maximum=6000)
                if hashlib.sha256(raw).hexdigest() != values['entry_sha256']:
                    _fail('hash_mismatch', 'required entry bytes differ: ' + path)
        return pointer
    except (OSError, LineageError) as exc:
        error = store._io_error(exc)
        if error.code == 'internal':
            raise error from None
        _fail('hash_mismatch', 'selected entry or mirror absent, changed or unsafe')


def check(agent_id, observed, *, ctx):
    _observed(observed)
    try:
        store._identity(agent_id)
        snapshot = store._snapshot(ctx)
        values = expected(agent_id, snapshot=snapshot, ctx=ctx)
        for field in ('agent_version', 'memory_gen', 'head', 'entry_sha256'):
            if observed[field] != values[field]:
                _fail('bad_op', 'observed ' + field + ' differs from committed expectation')
        _projection(agent_id, snapshot, ctx)
        pointer = _entry_bytes(agent_id, snapshot, values, ctx)
        required = _receipts(agent_id, snapshot)
        witnesses = _evidence(ctx, required)
        # Reopen by name after reading evidence; the old descriptor alone cannot
        # prove that the required path still names those verified bytes.
        if _evidence(ctx, required) != witnesses:
            _fail('hash_mismatch', 'required evidence changed during bootcheck')
        _projection(agent_id, snapshot, ctx)
        if _entry_bytes(agent_id, snapshot, values, ctx) != pointer:
            _fail('hash_mismatch', 'selected generation changed during bootcheck')
        final = store._snapshot(ctx)
        if final.head != snapshot.head or final.events != snapshot.events:
            _fail('bad_op', 'authoritative prefix changed during bootcheck')
        checks = [{'id': name, 'passed': True} for name in (
            'agent_version', 'memory_gen', 'head', 'entry_sha256',
            'projection_integrity', 'required_evidence', 'coherent_prefix')]
        checks.append({'id': 'entry_capacity', 'passed': True})
        return {'passed': True, 'code': 'OK', 'checks': checks, 'head': snapshot.head}
    except LineageError as exc:
        if exc.code == 'memory_debt':
            _fail('bad_op', 'entry capacity cannot be verified')
        if exc.code in {'bad_args', 'bad_op', 'hash_mismatch'} and not str(exc.detail).startswith('E_BOOTCHECK'):
            _fail(exc.code, 'required bootcheck precondition failed')
        raise
    except Exception:
        raise LineageError('internal', 'bootcheck verification unavailable') from None
