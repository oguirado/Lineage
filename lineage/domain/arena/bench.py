"""Journal-authoritative arena admission, compound execution and recovery.

Only ledger events establish completion. Runtime claims serialize invocations;
immutable output spools merely preserve untrusted command data between stages.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import replace
import fcntl
import hashlib
import itertools
import math
import os
import stat

from lineage.core import journal, registry
from lineage.core.errors import LineageError
from lineage.domain import agents, gate_close, runs
from lineage.domain.memory import units
from . import bank, runner as task_runner

# The integrated validator protocol omits Context. Bind runtime services, never
# application state, for direct admission on the same execution context.
_RUNTIME = ContextVar('arena_runtime', default=None)


def _context(ctx):
    result = bank._context(ctx)
    _RUNTIME.set(result)
    return result


def _history(ctx):
    try:
        return journal.snapshot(ctx.services.home)
    except LineageError as exc:
        if exc.code in ('bad_args', 'internal'):
            raise LineageError('internal', 'authoritative arena history unavailable') from None
        raise
    except Exception:
        raise LineageError('internal', 'authoritative arena history unavailable') from None


def _validator_context(history, ctx):
    if ctx is not None:
        return bank._context(ctx)
    ctx = _RUNTIME.get()
    if ctx is None:
        raise LineageError('internal', 'arena admission requires bound runtime services')
    # A stale service binding must not authorize another journal. Safe reading
    # does not acquire the ledger lock or invoke another transaction callback.
    expected = b''.join(bank._canonical(event) + b'\n' for event in history)
    raw = bank._read(ctx.services.home, 'ledger/main/events.jsonl',
                     maximum=max(1048576, len(expected)), code='internal')
    if raw[:len(expected)] != expected or raw[len(expected):].endswith(b'\n'):
        raise LineageError('internal', 'arena runtime does not match committed history')
    return ctx


def _head(history):
    return history[-1]['lamport'] if history else 0


def _find(history, bench_id, *, code='no_benchmark'):
    for event in history:
        if event['kind'] == 'bench.declared' and event['payload']['bench_id'] == bench_id:
            return event
    raise LineageError(code, 'benchmark declaration unavailable')


def _results(history, bench_id):
    return [e for e in history if e['kind'] == 'bench.result' and e['payload']['bench_id'] == bench_id]


def _final(history, bench_id):
    return next((e for e in history if e['kind'] == 'bench.verdict'
                 and e['payload']['bench_id'] == bench_id), None)


def _commit(events):
    return {'event_ids': [e['id'] for e in events], 'head': events[-1]['lamport'],
            'sha256': events[-1]['sha256']}


def _status(history, bench_id):
    declaration = _find(history, bench_id)['payload']
    results, final = _results(history, bench_id), _final(history, bench_id)
    opened = [e for e in history if e['kind'] == 'run.open'
              and e['payload']['task'].get('bench_id') == bench_id]
    consumed = {e['payload']['run_id'] for e in results}
    state = 'declared'
    if opened or results:
        state = 'running'
        # Prove root completion from its matching child opening. Caller OpIds
        # are unrestricted by our private prefix and must remain unchanged.
        terminal = False
        for event in results:
            value = event['payload']
            cell = [value['task_id'], value['agent_id'], value['seat'], value['memory_arm']]
            key = bank._digest([event['agent'], event['op_id']])[:40]
            expected_open = 'ar-' + key + '/open/' + bank._digest(cell)[:40]
            if any(item['payload']['run_id'] == value['run_id']
                   and item['op_id'] == expected_open for item in opened):
                terminal = True
                break
        if terminal and opened and all(e['payload']['run_id'] in consumed for e in opened):
            state = 'complete'
    if final:
        state = 'complete'
    return {'declaration': deepcopy(declaration), 'state': state,
            'results': [deepcopy(e['payload']) for e in results],
            'verdict': deepcopy(final['payload']) if final else None, 'head': _head(history)}


def status(bench_id: str, *, ctx) -> dict:
    bank._validate(bench_id, bank._ID)
    ctx = _context(ctx)
    return {'bench': _status(_history(ctx), bench_id)}


def list_benches(*, after: str | None = None, limit: int = 100, ctx) -> dict:
    bank._validate(limit, {'type': 'integer', 'minimum': 1, 'maximum': 1000})
    if after is not None:
        bank._validate(after, bank._ID)
    ctx = _context(ctx)
    history = _history(ctx)
    ids = sorted(e['payload']['bench_id'] for e in history if e['kind'] == 'bench.declared'
                 and (after is None or e['payload']['bench_id'] > after))
    chosen = ids[:limit]
    result = {'benches': [_status(history, key) for key in chosen],
              'next_after': chosen[-1] if len(ids) > limit else None, 'head': _head(history)}
    _bounded(result)
    return deepcopy(result)


def _bounded(value, *, code='bad_args'):
    if len(bank._canonical(value)) > 1048576:
        raise LineageError(code, 'arena result exceeds transport byte capacity')


def _effective(command, ctx):
    if command.agent != ctx.actor:
        raise LineageError('bad_args', 'actor_mismatch')
    args = deepcopy(command.args)
    if type(args) is not dict or args.get('agent', command.agent) != command.agent:
        raise LineageError('bad_args', 'actor_mismatch')
    args.setdefault('agent', command.agent)
    args.pop('op_id', None)
    args.pop('expected_head', None)
    if command.expected_head is not None:
        bank._validate(command.expected_head, {'type': 'integer', 'minimum': 0, 'maximum': bank._SAFE})
    bank._validate(command.op_id, {'type': 'string', 'minLength': 1, 'maxLength': 128,
                                'pattern': r'^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\s\S])'})
    return {'tool': command.tool, 'args': args}


def _request(command, ctx, kind, payload):
    return bank._digest({'ledger': 'main', 'agent': command.agent, 'op_id': command.op_id,
        'kind': kind, 'payload': payload, 'evidence': []})


def _transaction(kind, payload, *, command, ctx, render):
    effective = _effective(command, ctx)
    request = {**deepcopy(payload), **effective} if kind == 'bench.result' else effective
    def prepare(history, draft):
        if command.expected_head is not None and command.expected_head != _head(history):
            raise LineageError('stale_rev', 'expected head differs')
        return deepcopy(payload)
    def validate(history, event):
        callback = ctx.services.registry.validators.get(kind)
        if not callable(callback):
            raise LineageError('internal', 'arena validator unavailable')
        # Context is supplied through the runtime binding because wrappers of
        # registered validators retain the installed (history,event) signature.
        callback(history, event)
        value = render((*history, event), event)
        _bounded(value)
    event = journal.transact(ctx.services.home, agent=command.agent, op_id=command.op_id,
        kind=kind, payload=request, validators={kind: validate}, prepare=prepare,
        clock=getattr(ctx.services, 'clock', None), id_factory=getattr(ctx.services, 'id_factory', None))
    history = tuple(e for e in _history(ctx) if e['lamport'] <= event['lamport'])
    value = render(history, event)
    _bounded(value)
    return registry.Committed(event=deepcopy(event), value=deepcopy(value),
                              head=event['lamport'], sha256=event['sha256'])


def _admitted_bank(declaration, ctx):
    loaded = bank.load(declaration['bank_id'], ctx=ctx)
    bank.verify(loaded, declaration['bank_sha256'])
    return loaded, bank.tasks(loaded, purpose=declaration['purpose'])


def _subject(history, agent_id, ctx):
    snapshot = gate_close._snapshot(history, ctx)
    record = deepcopy(gate_close._agent(snapshot, agent_id))
    runs._version(record)
    return record


def _validate_declared(history, event, ctx=None):
    ctx = _validator_context(history, ctx)
    declaration = event['payload']
    bank._validate(declaration, bank._definition('bench_declared.schema.json'))
    probabilities = declaration['sprt']
    if probabilities['p0'] >= probabilities['p1']:
        raise LineageError('bad_args', 'require p0 < p1')
    for old in history:
        if old['kind'] == 'bench.declared' and old['payload']['bench_id'] == declaration['bench_id']:
            code = 'conflict' if old['payload'] == declaration else 'bad_op'
            raise LineageError(code, 'benchmark declaration is immutable')
    _admitted_bank(declaration, ctx)
    for agent_id in declaration['agents']:
        agent = _subject(history, agent_id, ctx)
        if agent['status'] == 'retired':
            raise LineageError('conflict', 'benchmark subject is retired')
        if any(seat not in agent['allowed_seats'] for seat in declaration['seats']):
            raise LineageError('seat_not_allowed', 'complete seat is not admitted')
    _bounded({'bench': _status((*history, event), declaration['bench_id']), 'commit': _commit([event])})


def declare(declaration: dict, *, command, ctx):
    ctx = _context(ctx)
    bank._validate(declaration, bank._definition('bench_declared.schema.json'))
    if command.tool != 'bench_declare' or command.args.get('declaration') != declaration:
        raise LineageError('bad_args', 'declaration differs from command')
    return _transaction('bench.declared', declaration, command=command, ctx=ctx,
        render=lambda prefix, event: {'bench': _status(prefix, declaration['bench_id']), 'commit': _commit([event])})


def _payload_schema(kind):
    for branch in bank._definition('event.schema.json')['allOf']:
        if branch.get('if', {}).get('properties', {}).get('kind', {}).get('const') == kind:
            return branch['then']['properties']['payload']
    raise LineageError('internal', 'arena event schema unavailable')


def _version_identity(history, declaration_event, subject_id, ctx):
    prefix = tuple(e for e in history if e['lamport'] < declaration_event['lamport'])
    original = _subject(prefix, subject_id, ctx)
    current = _subject(history, subject_id, ctx)
    for key in ('constitution_sha256', 'skills', 'references'):
        if original[key] != current[key]:
            raise LineageError('conflict', 'subject differs from declared version')
    # Memory generation may advance only through this benchmark's real runs.
    for event in history:
        if event['lamport'] <= declaration_event['lamport'] or event['kind'] != 'memory.put':
            continue
        payload = event['payload']
        if payload['agent_id'] != subject_id or payload['unit']['kind'] not in ('ruling', 'lesson', 'negative', 'workflow'):
            continue
        opening = next((e for e in history if e['kind'] == 'run.open'
                        and e['payload']['run_id'] == payload.get('run_id')), None)
        if opening is None or opening['payload']['task'].get('bench_id') != declaration_event['payload']['bench_id']:
            raise LineageError('conflict', 'unrelated memory changed the declared version')
    return current


def _validate_result(history, event, ctx=None):
    result = event['payload']
    declaration_event = _find(history, result.get('bench_id'), code='rule_not_declared')
    ctx = _validator_context(history, ctx)
    declaration = declaration_event['payload']
    loaded, _ = _admitted_bank(declaration, ctx)
    task = next((task for task in loaded['tasks'] if task['id'] == result.get('task_id')), None)
    if task and task['split'] == 'heldout' and declaration['purpose'] == 'select':
        raise LineageError('heldout_forbidden', 'selection cannot consume held-out tasks')
    bank._validate(result, _payload_schema('bench.result'))
    if (task is None or result['agent_id'] not in declaration['agents']
            or result['seat'] not in declaration['seats'] or result['memory_arm'] not in declaration['memory_arms']):
        raise LineageError('conflict', 'result cell was not declared')
    if _final(history, result['bench_id']):
        raise LineageError('conflict', 'benchmark is finalized')
    if any(e['kind'] == 'bench.result' and e['payload']['run_id'] == result['run_id'] for e in history):
        raise LineageError('conflict', 'closed run has already been consumed')
    closed = next((e for e in history if e['kind'] == 'run.close'
                   and e['payload']['record']['run_id'] == result['run_id']), None)
    if closed is None:
        raise LineageError('conflict', 'actual closed run witness required')
    record = closed['payload']['record']
    common = {key: task[key] for key in ('id', 'kind', 'language', 'split')}
    common.update(bank_id=declaration['bank_id'], bench_id=declaration['bench_id'])
    if (record['task'] != common or record['agent_id'] != result['agent_id']
            or record['seat'] != result['seat'] or record['memory_arm'] != result['memory_arm']
            or record['outcome']['verdict'] != result['verdict'] or record['cost'] != result['cost']
            or record['memory']['gate_passed'] is not True
            or result['correctness'] != int(result['verdict'] in ('ADMIT', 'green'))):
        raise LineageError('conflict', 'result differs from closed run witness')
    _version_identity(history[:closed['lamport']], declaration_event, result['agent_id'], ctx)
    subject_ctx = bank._context(ctx, actor=result['agent_id'])
    before_close = tuple(e for e in history if e['lamport'] < closed['lamport'])
    runs._validate_close(before_close, closed, ctx=subject_ctx)


def record_result(result: dict, *, command, ctx):
    ctx = _context(ctx)
    _find(_history(ctx), result.get('bench_id'), code='rule_not_declared')
    bank._validate(result, _payload_schema('bench.result'))
    return _transaction('bench.result', result, command=command, ctx=ctx,
        render=lambda prefix, event: {'bench': _status(prefix, result['bench_id']), 'commit': _commit([event])})


def _root_key(command):
    return bank._digest([command.agent, command.op_id])[:40]


def _child_op(root, cell, stage):
    return 'ar-' + _root_key(root) + '/' + stage + '/' + bank._digest(cell)[:40]


def _child(root, cell, stage, actor, *, expected=None, args=None, final=False):
    op_id = root.op_id if final else _child_op(root, cell, stage)
    effective = deepcopy(root.args if args is None else args)
    effective['agent'], effective['op_id'] = actor, op_id
    effective.pop('expected_head', None)
    return registry.Command(root.tool, effective, actor, op_id, expected)


def _plan(declaration, eligible):
    for task in eligible:
        for seat, arm, agent_id in itertools.product(declaration['seats'], declaration['memory_arms'], declaration['agents']):
            yield task, agent_id, seat, arm


def _plan_bound(declaration, plan, history):
    count = len(plan)
    existing = [deepcopy(e['payload']) for e in _results(history, declaration['bench_id'])]
    if count > 10000 or count + len(existing) > 1000000:
        raise LineageError('bad_args', 'execution plan exceeds result collection capacity')
    worst = []
    for task, agent_id, seat, arm in plan:
        worst.append({'bench_id': declaration['bench_id'], 'task_id': task['id'],
            'agent_id': agent_id, 'seat': seat, 'memory_arm': arm, 'run_id': 'r' * 64,
            'verdict': 'error', 'correctness': 0, 'cost': dict.fromkeys(task_runner._COST_FIELDS, bank._SAFE)})
    value = {'bench': {'declaration': declaration, 'state': 'complete',
        'results': existing + worst, 'verdict': None, 'head': bank._SAFE},
        'commit': {'event_ids': ['e-' + 'f' * 16] * count, 'head': bank._SAFE, 'sha256': 'f' * 64}}
    _bounded(value)


@contextmanager
def _claim(ctx, root):
    descriptors = []
    try:
        fd = os.open(ctx.services.home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        for part in ('arena-runtime', _root_key(root)):
            try:
                os.mkdir(part, 0o700, dir_fd=fd)
            except FileExistsError:
                pass
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(fd)
        lock = os.open('claim.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=fd)
        descriptors.append(lock)
        info = os.fstat(lock)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise OSError
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LineageError('busy', 'benchmark operation is already executing') from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
    except (OSError, ValueError, TypeError):
        raise LineageError('internal', 'benchmark claim unavailable') from None
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def _stage_path(command, run_id):
    return 'arena-runtime/' + _root_key(command) + '/output-' + run_id + '.json'


def _stage_identity(command, task, agent, seat, arm, ctx):
    return {'request_sha256': bank._digest(_effective(command, ctx)), 'task': task,
            'agent_id': agent['agent_id'], 'seat': seat, 'memory_arm': arm}


def _staged(command, identity, run_id, ctx):
    path = _stage_path(command, run_id)
    try:
        raw = bank._read(ctx.services.home, path, maximum=2097152, code='conflict')
    except LineageError:
        # Only an actually absent regular path means no staging. All other
        # resolution failures, including dangling links, refuse recovery.
        try:
            os.lstat(ctx.services.home / path)
        except FileNotFoundError:
            return None
        except OSError:
            pass
        raise
    try:
        value = bank._decode(raw, max_bytes=2097152)
        if (set(value) != {'identity', 'output', 'sha256'} or value['identity'] != identity
                or value['sha256'] != bank._digest(value['output'])):
            raise ValueError
        return task_runner._validate_output(value['output'])
    except (LineageError, ValueError, TypeError, KeyError):
        raise LineageError('conflict', 'durable runner output failed identity validation') from None


def _open_replay(event, child, ctx):
    request = _effective(child, bank._context(ctx, actor=child.agent))
    if event['request_sha256'] != _request(child, ctx, 'run.open', request):
        raise LineageError('bad_op', 'root benchmark request changed')


def _compound_replay(history, command, ctx):
    final = next((e for e in history if e['agent'] == command.agent and e['op_id'] == command.op_id), None)
    if final is None:
        return None
    if final['kind'] != 'bench.result':
        raise LineageError('bad_op', 'operation identity belongs to another command')
    prefix = tuple(e for e in history if e['lamport'] <= final['lamport'])
    result_events = [e for e in prefix if e['kind'] == 'bench.result' and e['agent'] == command.agent
        and (e['op_id'] == command.op_id or e['op_id'].startswith('ar-' + _root_key(command) + '/result/'))]
    for result in result_events:
        cell_result = result['payload']
        opened = next(e for e in prefix if e['kind'] == 'run.open' and e['payload']['run_id'] == cell_result['run_id'])
        data = opened['payload']
        cell = [data['task']['id'], data['agent_id'], data['seat'], data['memory_arm']]
        child = _child(command, cell, 'open', data['agent_id'])
        _open_replay(opened, child, ctx)
    return {'bench': _status(prefix, final['payload']['bench_id']), 'commit': _commit(result_events)}


def _preflight_memory(output, subject, task, seat, ctx):
    for unit in output['memory_units']:
        if unit['level'] == 1:
            raise LineageError('forbidden_level', 'operator authority required')
        if unit['provenance']['actor'] != subject['agent_id']:
            raise LineageError('bad_args', 'actor_mismatch')
        if (unit['provenance'].get('run_id') != task['run_id'] or unit['kind'] == 'episode'
                and (unit['body']['run_id'] != task['run_id'] or unit['body']['task_id'] != task['id']
                     or unit['body']['seat'] != seat or unit['body']['outcome'] != output['outcome']
                     or unit['body']['cost'] != output['cost'])):
            raise LineageError('bad_args', 'runner memory differs from its execution binding')
        for receipt in unit['receipts']:
            gate_close._coordinate(receipt['path'])
            gate_close._evidence(receipt, ctx)


def run(bench_id: str, runner: dict, *, command, ctx) -> dict:
    ctx = _context(ctx)
    bank._validate(bench_id, bank._ID)
    bank._validate(runner, task_runner._RUNNER)
    if (command.tool != 'bench_run' or command.args.get('bench_id') != bench_id
            or command.args.get('runner') != runner):
        raise LineageError('bad_args', 'benchmark request differs from command')
    _effective(command, ctx)
    history = _history(ctx)
    replay = _compound_replay(history, command, ctx)
    if replay is not None:
        return deepcopy(replay)
    declaration_event = _find(history, bench_id, code='rule_not_declared')
    declaration = declaration_event['payload']
    if _final(history, bench_id):
        raise LineageError('conflict', 'benchmark is finalized')
    _, eligible = _admitted_bank(declaration, ctx)
    plan = list(_plan(declaration, eligible))
    _plan_bound(declaration, plan, history)
    with _claim(ctx, command):
        history = _history(ctx)
        replay = _compound_replay(history, command, ctx)
        if replay is not None:
            return deepcopy(replay)
        result_events = []
        admitted = False
        for index, (task, agent_id, seat, arm) in enumerate(plan):
            cell = [task['id'], agent_id, seat, arm]
            run_id = 'r-' + bank._digest([command.agent, command.op_id, cell])[:48]
            history = _history(ctx)
            opening = next((e for e in history if e['kind'] == 'run.open'
                            and e['payload']['run_id'] == run_id), None)
            child = _child(command, cell, 'open', agent_id,
                           expected=None if admitted else command.expected_head)
            subject_ctx = bank._context(ctx, actor=agent_id)
            if opening is not None:
                _open_replay(opening, child, ctx)
                admitted = True
            else:
                subject = _version_identity(history, declaration_event, agent_id, ctx)
                common = {key: task[key] for key in ('id', 'kind', 'language', 'split')}
                common.update(bank_id=declaration['bank_id'], bench_id=bench_id)
                opening = runs.open_run(run_id, agent_id, seat, common,
                    parents_context=[], memory_arm=arm, command=child, ctx=subject_ctx).event
                admitted = True
            current = _history(ctx)
            result_event = next((e for e in current if e['kind'] == 'bench.result' and e['payload']['run_id'] == run_id), None)
            if result_event is not None:
                result_events.append(result_event)
                continue
            closed = next((e for e in current if e['kind'] == 'run.close'
                           and e['payload']['record']['run_id'] == run_id), None)
            if closed is None:
                prefix = tuple(e for e in current if e['lamport'] < opening['lamport'])
                subject = _subject(prefix, agent_id, ctx)
                execution = {**deepcopy(task), 'bank_id': declaration['bank_id'], 'bench_id': bench_id, 'run_id': run_id}
                identity = _stage_identity(command, execution, subject, seat, arm, ctx)
                output = _staged(command, identity, run_id, ctx)
                if output is None:
                    # A retained command opening without output is ambiguous,
                    # even if the caller believes the child never started.
                    retained = any(e['id'] == opening['id'] for e in history)
                    if runner['kind'] == 'command' and retained:
                        raise LineageError('conflict', 'command completion is ambiguous')
                    output = task_runner.run_task(execution, agent=subject,
                        seat=deepcopy(seat), memory_arm=arm, runner=deepcopy(runner), ctx=subject_ctx)
                    _preflight_memory(output, subject, execution, seat, subject_ctx)
                    task_runner._validate_output(output)
                    staged = {'identity': identity, 'output': output, 'sha256': bank._digest(output)}
                    task_runner._publish(ctx.services.home, _stage_path(command, run_id), bank._canonical(staged))
                _preflight_memory(output, subject, execution, seat, subject_ctx)
                generation = subject['memory_gen']
                for unit in output['memory_units']:
                    # The integrated memory API binds its own payload rather
                    # than accepting root bench arguments. Retained root identity
                    # is independently verified by the actual run.open witness.
                    data = {'agent_id': agent_id, 'unit': unit, 'run_id': run_id}
                    memory_command = _child(command, cell + [unit['id']], 'memory', agent_id, args=data)
                    existing = next((e for e in _history(ctx) if e['kind'] == 'memory.put'
                                     and e['agent'] == agent_id and e['payload']['unit']['id'] == unit['id']), None)
                    if existing is not None:
                        if existing['payload'] != data:
                            raise LineageError('conflict', 'retained memory differs from runner output')
                        continue
                    committed_memory = units.put(agent_id, unit, run_id=run_id,
                                                 command=memory_command, ctx=subject_ctx)
                    current_generation = committed_memory.value['memory_gen']
                    if current_generation != generation:
                        agents.refresh_projections(agent_id, ctx=subject_ctx)
                    generation = current_generation
                # Classify absence of an admissible episode before the full U13
                # gate. Private/inactive records never satisfy the episode duty.
                snapshot = gate_close._snapshot(_history(ctx), subject_ctx)
                if not any(unit['kind'] == 'episode' and unit['status'] == 'active'
                           and unit['privacy'] in ('public', 'internal')
                           and unit['provenance'].get('run_id') == run_id
                           for unit in gate_close._units(snapshot, agent_id).values()):
                    raise LineageError('memory_required', 'current-run episode required')
                close_command = _child(command, cell, 'close', agent_id)
                closed = runs.close(run_id, output['outcome'], output['cost'], evidence=output['evidence'],
                                    command=close_command, ctx=subject_ctx).event
            record = closed['payload']['record']
            result = {'bench_id': bench_id, 'task_id': task['id'], 'agent_id': agent_id,
                'seat': deepcopy(seat), 'memory_arm': arm, 'run_id': run_id,
                'verdict': record['outcome']['verdict'],
                'correctness': int(record['outcome']['verdict'] in ('ADMIT', 'green')), 'cost': deepcopy(record['cost'])}
            result_command = _child(command, cell, 'result', command.agent, final=index == len(plan) - 1)
            committed = record_result(result, command=result_command, ctx=ctx)
            result_events.append(committed.event)
        prefix = tuple(e for e in _history(ctx) if e['lamport'] <= result_events[-1]['lamport'])
        return {'bench': _status(prefix, bench_id), 'commit': _commit(result_events)}


def _sprt(observations, parameters):
    """Use U15 likelihoods while retaining every K0-admitted error probability.

    The installed engine adds alpha+beta<1. Overlapping declared boundaries
    therefore use its likelihood/count report with neutral bounds, then apply
    the declared bounds at the same complete-task prefixes. No observations
    or probability values in the declaration are changed.
    """
    from . import sprt
    if parameters['alpha'] + parameters['beta'] < 1:
        return sprt.evaluate_sprt(observations, **parameters)
    upper = math.log1p(-parameters['beta']) - math.log(parameters['alpha'])
    lower = math.log(parameters['beta']) - math.log1p(-parameters['alpha'])
    report = None
    for count in range(1, len(observations) + 1):
        report = sprt.evaluate_sprt(observations[:count], **{
            **parameters, 'alpha': 0.25, 'beta': 0.25})
        report['upper'], report['lower'] = upper, lower
        llr = report['llr']
        decision = ('superior' if llr >= upper else 'not_superior' if llr <= lower
                    else 'inconclusive' if report['n_tasks'] >= parameters['cap'] else 'continue')
        report['decision'] = decision
        if decision != 'continue':
            report['stopped_at'] = observations[report['n_tasks'] - 1]['task_id']
            break
    if report is None:
        raise LineageError('conflict', 'no complete task observations')
    return report


def _credit(candidate, baseline, *, rule):
    """Adapt U15's scalar/sample API without changing the declared population rule.

    Feed the installed engine the actual task means, then convert its measured
    sample variance to population variance. A singleton has zero dispersion;
    no repeated observation is invented to meet U15's minimum sample size.
    """
    from . import credit
    values = [row['correctness'] for row in baseline]
    rewards = [new['correctness'] - old['correctness']
               for new, old in zip(candidate, baseline)]
    count = len(values)
    candidate_mean = math.fsum(row['correctness'] for row in candidate) / count
    report = credit.evaluate_credit(candidate_mean, values, rule={
        'metric': 'correctness', 'direction': 'higher',
        'dispersion': 'sample_stddev', 'min_baseline': 2})
    if count == 1:
        gain, dispersion = rewards[0], 0.0
    else:
        if not report['eligible']:
            raise LineageError('internal', 'complete correctness evidence was refused')
        sample = report['baseline_dispersion']
        gain = report['gain']
        dispersion = math.sqrt(sample * sample * (count - 1) / count)
    return {'gain': gain, 'baseline_dispersion': dispersion,
            'minimum_reward': min(rewards),
            'credited': gain > dispersion and gain > rule['minimum_gain']}


def _verdict_data(history, bench_id, ctx):
    declared_event = _find(history, bench_id)
    declaration = declared_event['payload']
    if _final(history, bench_id):
        raise LineageError('conflict', 'benchmark is finalized')
    _, eligible = _admitted_bank(declaration, ctx)
    results = [e['payload'] for e in _results(history, bench_id)]
    consumed = {r['run_id'] for r in results}
    if not results or any(e['kind'] == 'run.open' and e['payload']['task'].get('bench_id') == bench_id
                          and e['payload']['run_id'] not in consumed for e in history):
        raise LineageError('conflict', 'benchmark contains unfinished cells')
    aggregated, observations = [], []
    incomplete = False
    for task in eligible:
        rows = [r for r in results if r['task_id'] == task['id']]
        if not rows:
            incomplete = True
            continue
        means = []
        for agent_id in declaration['agents']:
            groups = [[r for r in rows if r['agent_id'] == agent_id and r['seat'] == seat and r['memory_arm'] == arm]
                      for seat, arm in itertools.product(declaration['seats'], declaration['memory_arms'])]
            if any(not group for group in groups) or len({len(group) for group in groups}) != 1:
                raise LineageError('conflict', 'task cell grid is incomplete')
            values = [r['correctness'] for group in groups for r in group]
            means.append(sum(values) / len(values))
        for seat, arm in itertools.product(declaration['seats'], declaration['memory_arms']):
            counts = [sum(r['agent_id'] == agent and r['seat'] == seat and r['memory_arm'] == arm for r in rows)
                      for agent in declaration['agents']]
            if counts[0] != counts[1]:
                raise LineageError('conflict', 'repeated cells are unmatched')
        if incomplete:
            raise LineageError('conflict', 'complete evidence is not a bank-order prefix')
        reward = means[1] - means[0]
        aggregated.append((task['id'], means))
        observations.append({'task_id': task['id'], 'seed': 0,
                             'outcome': 'win' if reward > 0 else 'loss' if reward < 0 else 'tie'})
    if not observations:
        raise LineageError('conflict', 'no complete task observations')
    parameters = declaration['sprt']
    report = _sprt(observations, parameters)
    n = report['n_tasks']
    if report['decision'] == 'continue' and incomplete:
        raise LineageError('conflict', 'benchmark evidence has not reached a terminal boundary')
    chosen = aggregated[:n]
    baseline = [{'task_id': task_id, 'correctness': means[0], 'cost': dict.fromkeys(task_runner._COST_FIELDS)}
                for task_id, means in chosen]
    candidate = [{'task_id': task_id, 'correctness': means[1], 'cost': dict.fromkeys(task_runner._COST_FIELDS)}
                 for task_id, means in chosen]
    credit_result = _credit(candidate, baseline, rule=declaration['credit_rule'])
    value = {'bench_id': bench_id, 'decision': 'inconclusive' if report['decision'] == 'continue' else report['decision'],
             'llr': report['llr'], 'n_discordant': report['n_discordant'], 'credit': credit_result}
    bank._validate(value, _payload_schema('bench.verdict'))
    return value


def _validate_verdict(history, event, ctx=None):
    _find(history, event['payload'].get('bench_id'))
    ctx = _validator_context(history, ctx)
    bank._validate(event['payload'], _payload_schema('bench.verdict'))
    expected = _verdict_data(history, event['payload']['bench_id'], ctx)
    if event['payload'] != expected:
        raise LineageError('conflict', 'verdict differs from committed task evidence')


def verdict(bench_id: str, *, command, ctx):
    ctx = _context(ctx)
    bank._validate(bench_id, bank._ID)
    if command.tool != 'bench_verdict' or command.args.get('bench_id') != bench_id:
        raise LineageError('bad_args', 'verdict differs from command')
    history = _history(ctx)
    _find(history, bench_id)
    retained = next((e for e in history if e['agent'] == command.agent and e['op_id'] == command.op_id), None)
    value = deepcopy(retained['payload']) if retained else _verdict_data(history, bench_id, ctx)
    return _transaction('bench.verdict', value, command=command, ctx=ctx,
                        render=lambda prefix, event: {'verdict': deepcopy(event['payload']), 'commit': _commit([event])})


class _ArenaFold:
    order = 60
    kinds = frozenset({'bench.declared', 'bench.result', 'bench.verdict'})

    def __call__(self, state, event):
        if event['kind'] not in self.kinds:
            return
        arena = state.setdefault('arena', {})
        payload = event['payload']
        if event['kind'] == 'bench.declared':
            arena[payload['bench_id']] = {'declaration': deepcopy(payload), 'results': [],
                                         'verdict': None, 'declared_at': event['lamport']}
        elif event['kind'] == 'bench.result':
            arena[payload['bench_id']]['results'].append(deepcopy(payload))
        else:
            arena[payload['bench_id']]['verdict'] = deepcopy(payload)
