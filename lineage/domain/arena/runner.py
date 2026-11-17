"""Deterministic fixtures and a bounded, shell-free command protocol."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import os
import selectors
import stat
import subprocess
import time

from lineage.core import journal
from lineage.core.errors import LineageError
from . import bank

_LIMIT = 1048576
_STDERR_LIMIT = 65536
_RUNNER = {'oneOf': [bank._object({'kind': {'const': 'fake'},
    'seed': {'type': 'integer', 'minimum': 0, 'maximum': 4294967295}}),
    bank._object({'kind': {'const': 'command'},
        'argv': {'type': 'array', 'minItems': 1, 'maxItems': 128,
                 'items': {'type': 'string', 'minLength': 1, 'maxLength': 4096}},
        'timeout_ms': {'type': 'integer', 'minimum': 1, 'maximum': 3600000}})]}
_COST_FIELDS = ('tokens_in', 'tokens_out', 'tokens_cache', 'duration_ms', 'cost_micro_usd')


def _output_schema():
    props = bank._definition('run.schema.json')['properties']
    return bank._object({'outcome': props['outcome'], 'cost': props['cost'],
        'evidence': props['evidence'],
        'memory_units': {'type': 'array', 'maxItems': 256,
                         'items': {'$ref': 'mem_unit.schema.json'}}})


def _validate_output(value):
    bank._validate(value, _output_schema())
    if len(bank._canonical(value)) > _LIMIT:
        raise LineageError('bad_args', 'runner output exceeds byte capacity')
    return deepcopy(value)


def _publish(home, relative, raw):
    """Publish immutable runtime bytes using pinned, no-follow descriptors."""
    descriptors = []
    try:
        parts = relative.split('/')
        if any(part in ('', '.', '..') for part in parts) or parts[0] in ('ledger', 'family'):
            raise OSError
        directory = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(directory)
        for part in parts[:-1]:
            try:
                os.mkdir(part, 0o700, dir_fd=directory)
                os.fsync(directory)
            except FileExistsError:
                pass
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            descriptors.append(directory)
        try:
            fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
        except FileExistsError:
            if bank._read(home, relative, maximum=max(len(raw), 1), code='conflict') != raw:
                raise LineageError('conflict', 'immutable runtime artifact differs')
            return
        try:
            view = memoryview(raw)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(directory)
    except LineageError:
        raise
    except (OSError, ValueError, TypeError):
        raise LineageError('internal', 'runtime artifact publication failed') from None
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def _binding(task, agent, seat, arm, ctx):
    shape = deepcopy(bank._bank_shape()['properties']['tasks']['items'])
    shape['properties'].update(bank_id=bank._AGENT, bench_id=bank._ID, run_id=bank._ID)
    shape['required'] += ['bank_id', 'bench_id', 'run_id']
    bank._validate(task, shape)
    bank._validate(agent, bank._definition('agent.schema.json'))
    bank._validate(seat, bank._definition('bench_declared.schema.json')['properties']['seats']['items'])
    bank._validate(arm, {'enum': ['none', 'own', 'inherited']})
    history = journal.snapshot(ctx.services.home)
    opened = next((e for e in history if e['kind'] == 'run.open'
                   and e['payload']['run_id'] == task['run_id']), None)
    if opened is None:
        raise LineageError('bad_args', 'execution has no matching open run')
    frozen = opened['payload']
    common = {key: task[key] for key in ('id', 'kind', 'language', 'bank_id', 'bench_id', 'split')}
    if (frozen['agent_id'] != agent['agent_id'] or frozen['agent_version'] != agent['agent_version']
            or frozen['seat'] != seat or frozen['memory_arm'] != arm or frozen['task'] != common
            or any(e['kind'] == 'run.close' and e['payload']['record']['run_id'] == task['run_id']
                   for e in history)):
        raise LineageError('bad_args', 'execution binding differs from open run')
    declared = next((e['payload'] for e in history if e['kind'] == 'bench.declared'
                     and e['payload']['bench_id'] == task['bench_id']), None)
    if declared is None:
        raise LineageError('rule_not_declared', 'benchmark declaration required')
    if (agent['agent_id'] not in declared['agents'] or seat not in declared['seats']
            or arm not in declared['memory_arms'] or task['bank_id'] != declared['bank_id']):
        raise LineageError('bad_args', 'execution is outside the declaration')
    if task['split'] == 'heldout' and declared['purpose'] == 'select':
        raise LineageError('heldout_forbidden', 'selection cannot consume held-out tasks')
    return declared, frozen


def _predecessors(task, agent, ctx):
    """Replace only this benchmark's closed synthetic summaries, never open duties.

    Use the opening prefix so recovery generates the same output after some
    new units have committed. Superseded records remain immutable ledger facts.
    """
    from lineage.domain import gate_close
    history = journal.snapshot(ctx.services.home)
    opening = next(event for event in history if event['kind'] == 'run.open'
                   and event['payload']['run_id'] == task['run_id'])
    prefix = tuple(event for event in history if event['lamport'] < opening['lamport'])
    closed = {event['payload']['record']['run_id'] for event in prefix
              if event['kind'] == 'run.close'}
    owned = {event['payload']['run_id'] for event in prefix
             if event['kind'] == 'run.open' and event['payload']['agent_id'] == agent['agent_id']
             and event['payload']['task'].get('bench_id') == task['bench_id']}
    snapshot = gate_close._snapshot(prefix, ctx)
    units = snapshot.state.get('memory', {}).get(agent['agent_id'], {}).get('units', {})
    result = {}
    for unit in units.values():
        provenance = unit['provenance']
        run_id, kind = provenance.get('run_id'), unit['kind']
        if (run_id not in closed or run_id not in owned or unit['status'] != 'active'
                or unit['privacy'] != 'internal' or unit['level'] != 2
                or kind not in ('episode', 'lesson', 'negative')
                or provenance.get('origin') != 'offline'
                or provenance['actor'] != agent['agent_id']
                or unit['id'] != 'u-' + bank._digest([run_id, agent['agent_id'], kind])[:32]):
            continue
        result.setdefault(kind, []).append(unit['id'])
    return {kind: sorted(ids) for kind, ids in result.items()}


def _synthetic(task, agent, seat, outcome, *, identity, ctx, parents=()):
    """A fixture receipt supports memory; only the journal can prove closure."""
    clock = getattr(ctx.services, 'clock', None)
    if not callable(clock):
        raise LineageError('internal', 'synthetic runner requires an injected clock')
    timestamp = clock()
    if type(timestamp) is not int or not 0 <= timestamp <= bank._SAFE:
        raise LineageError('internal', 'invalid virtual clock')
    cost = dict.fromkeys(_COST_FIELDS)
    content = bank._canonical({'schema': 'lineage.arena.fixture/v1', 'task': task,
        'agent_id': agent['agent_id'], 'seat': seat, 'identity': identity,
        'outcome': outcome, 'ts': timestamp}) + b'\n'
    digest = hashlib.sha256(content).hexdigest()
    path = 'evidence/arena/' + digest + '.json'
    _publish(ctx.services.home, path, content)
    receipt = {'path': path, 'sha256': digest}
    kinds = ['episode']
    if outcome['verdict'] in ('error', 'HOLD', 'red') or outcome['repair_loops']:
        kinds.append('lesson')
    if outcome['verdict'] in ('HOLD', 'red'):
        kinds.append('negative')
    predecessors = _predecessors(task, agent, ctx)
    units = []
    for kind in kinds:
        if kind == 'episode':
            body = {'run_id': task['run_id'], 'task_id': task['id'], 'seat': deepcopy(seat),
                    'outcome': deepcopy(outcome), 'cost': deepcopy(cost), 'parents_context': list(parents)}
        elif kind == 'lesson':
            body = {'tempting_use': 'Assume success', 'failure_mode': 'Synthetic failure',
                    'safer_action': 'Check task evidence', 'blocked_use': []}
        else:
            body = {'gate_id': 'offline', 'verdict': outcome['verdict'], 'cause': 'Synthetic failure',
                    'coordinate': 'fixture:1', 'safer_action': 'Retain failure memory'}
        units.append({'schema': 'lineage.mem.unit/v1',
            'id': 'u-' + bank._digest([task['run_id'], agent['agent_id'], kind])[:32],
            'kind': kind, 'level': 2, 'statement': 'Synthetic offline benchmark',
            'status': 'active', 'privacy': 'internal',
            'scope': {key: agent[key] for key in ('workflow', 'language')},
            'provenance': {'origin': 'offline', 'actor': agent['agent_id'], 'run_id': task['run_id']},
            'receipts': [deepcopy(receipt)], 'supersedes': predecessors.get(kind, []), 'body': body})
    return _validate_output({'outcome': deepcopy(outcome), 'cost': cost,
                            'evidence': [receipt], 'memory_units': units})


def _stop(process):
    if process.pid is None or process.pid <= 1:
        raise LineageError('internal', 'invalid owned child identity')
    if process.poll() is None:
        process.kill()
    process.wait(timeout=1)


def _command(argv, stdin, timeout_ms):
    if len(stdin) > _LIMIT or any('\x00' in arg for arg in argv):
        raise LineageError('bad_args', 'invalid command protocol input')
    process = None
    selector = selectors.DefaultSelector()
    try:
        process = subprocess.Popen(argv, shell=False, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        if process.pid <= 1:
            raise LineageError('internal', 'invalid owned child identity')
        for stream, events, tag in ((process.stdin, selectors.EVENT_WRITE, 'in'),
                (process.stdout, selectors.EVENT_READ, 'out'),
                (process.stderr, selectors.EVENT_READ, 'err')):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, events, tag)
        deadline, offset, stdout, stderr = time.monotonic() + timeout_ms / 1000, 0, bytearray(), bytearray()
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _stop(process)
                return None
            for key, _ in selector.select(remaining):
                stream, tag = key.fileobj, key.data
                if tag == 'in':
                    try:
                        offset += os.write(stream.fileno(), stdin[offset:offset + 65536])
                    except BrokenPipeError:
                        offset = len(stdin)
                    except BlockingIOError:
                        continue
                    if offset == len(stdin):
                        selector.unregister(stream)
                        stream.close()
                else:
                    try:
                        data = os.read(stream.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    if not data:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    if tag == 'out':
                        stdout.extend(data)
                        if len(stdout) > _LIMIT:
                            _stop(process)
                            raise LineageError('bad_args', 'runner stdout exceeds byte capacity')
                    else:
                        stderr.extend(data[:max(0, _STDERR_LIMIT - len(stderr))])
        try:
            code = process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            _stop(process)
            return None
        if code != 0:
            raise LineageError('bad_args', 'runner child did not complete its protocol')
        return bytes(stdout)
    except LineageError:
        raise
    except (OSError, ValueError, subprocess.SubprocessError):
        raise LineageError('internal', 'runner command I/O failed') from None
    finally:
        selector.close()
        if process is not None:
            if process.pid is not None and process.pid > 1 and process.poll() is None:
                _stop(process)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()


def run_task(task: dict, *, agent: dict, seat: dict, memory_arm: str,
             runner: dict, ctx) -> dict:
    bank._validate(runner, _RUNNER)
    ctx = bank._context(ctx)
    declaration, opened = _binding(task, agent, seat, memory_arm, ctx)
    if runner['kind'] == 'fake':
        role = 'baseline' if declaration['agents'][0] == agent['agent_id'] else 'candidate'
        return _synthetic(task, agent, seat, task['expected'][role],
            identity={'seed': runner['seed'], 'memory_arm': memory_arm},
            parents=opened['parents_context'], ctx=ctx)
    stdin = bank._canonical({'task': task, 'agent': agent, 'seat': seat, 'memory_arm': memory_arm}) + b'\n'
    stdout = _command(runner['argv'], stdin, runner['timeout_ms'])
    if stdout is None:
        try:
            return _synthetic(task, agent, seat, {'verdict': 'error', 'repair_loops': 0,
                'findings': {'confirmed': 0, 'refuted': 0}}, identity={'timeout': runner['timeout_ms']},
                parents=opened['parents_context'], ctx=ctx)
        except LineageError:
            raise LineageError('memory_debt', 'timeout failure memory unavailable') from None
    return _validate_output(bank._decode(stdout))
