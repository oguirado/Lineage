"""Journal-derived qualification and lifecycle policy.

Qualification uses detached committed witnesses only. Runtime admission shares
that policy with the agent-status owner and runs inside journal preparation.
The frozen event schema remains a hard gate: a qualification is never stored
without its complete measured seat.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from functools import wraps
import hashlib
import math
from pathlib import Path
import re
import statistics
from typing import Any

from lineage.core import journal, schema
from lineage.core.errors import LineageError
from lineage.domain.memory import fold as memory_fold
from lineage.domain.version import agent_version

JSONObject = dict[str, Any]
_FAILURES = frozenset(('error', 'HOLD', 'red'))
_SUCCESSES = frozenset(('ADMIT', 'green'))
_CODES = frozenset(('bad_args', 'no_agent', 'no_benchmark', 'heldout_forbidden',
                    'bad_op', 'conflict', 'stale_rev', 'busy', 'internal'))
_SAFE = 9007199254740991
_SEAT = {'type': 'object', 'properties': {
    'model': {'type': 'string', 'minLength': 1, 'maxLength': 128},
    'effort': {'type': 'string', 'minLength': 1, 'maxLength': 32,
               'pattern': r'^[a-z0-9_-]+(?![\s\S])'},
    'mode': {'enum': ['headless', 'interactive']}},
    'required': ['model', 'effort', 'mode'], 'additionalProperties': False}


def _refuse(code='conflict', detail='committed promotion evidence does not qualify'):
    raise LineageError(code, detail)


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        _refuse()
    return value


def _integer(value, low=0, high=_SAFE):
    if type(value) is not int or not low <= value <= high:
        _refuse()
    return value


def _seat(value):
    try:
        schema.validate(value, _SEAT)
        journal.canonical_bytes(value)
    except (schema.SchemaError, ValueError, TypeError, LineageError):
        _refuse('bad_args', 'a complete closed seat is required')
    return value


def _events(snapshot):
    value = getattr(snapshot, 'events', snapshot)
    if not isinstance(value, (tuple, list)):
        _refuse('internal', 'committed history unavailable')
    return tuple(value)


def _identities(history):
    """Capture exact version inputs without reading agent projections."""
    records, memory = {}, {}
    for event in history:
        kind, payload = event['kind'], event['payload']
        if kind == 'agent.born':
            record = deepcopy(payload['record'])
            if record['agent_id'] in records:
                _refuse()
            records[record['agent_id']] = record
        if kind in ('agent.born', 'memory.put', 'memory.retire'):
            memory_fold.apply(memory, event)
    for key, record in records.items():
        generation = memory.get('memory', {}).get(key, {}).get('memory_gen')
        if generation is None:
            _refuse()
        record['memory_gen'] = generation
        record['agent_version'] = agent_version(record['constitution_sha256'], record['skills'], generation)
    return records


def _entry():
    return {'status': 'draft', 'promoted_seat': None, 'shadow_event_id': None,
            'shadow_lamport': None, 'selection_bench_id': None,
            'n_shadow_runs': None, 'failure_streak': 0}


def apply(state: JSONObject, event: JSONObject) -> JSONObject:
    """Fold only the promotion namespace; committed closes are counted once.

    Auxiliary declaration and run maps keep the callback independent of other
    folds, their execution order, and mutable projections. Per-agent entries
    retain a closed shape. Qualification provenance survives retirement.
    """
    kind, payload = event['kind'], event['payload']
    if kind not in ('agent.born', 'agent.status', 'bench.declared', 'run.open', 'run.close'):
        return state
    namespace = state.setdefault('promotion', {})
    seen = namespace.setdefault('_events', {})
    if event['id'] in seen:
        return state
    seen[event['id']] = True
    if kind == 'agent.born':
        record = payload['record']
        initial = _entry()
        initial.update(status=record['status'], promoted_seat=deepcopy(record.get('promoted_seat')))
        namespace.setdefault(record['agent_id'], initial)
    elif kind == 'bench.declared':
        seats = payload.get('seats', [])
        namespace.setdefault('_benchmarks', {})[payload['bench_id']] = {
            'n_shadow_runs': payload.get('promotion', {}).get('n_shadow_runs'),
            'seat': deepcopy(seats[0]) if len(seats) == 1 else None}
    elif kind == 'run.open':
        namespace.setdefault('_opens', {}).setdefault(payload['run_id'], deepcopy(payload))
    elif kind == 'agent.status':
        entry = namespace.get(payload['agent_id'])
        if entry is None or entry['status'] == 'retired':
            return state
        target = payload['to']
        if target == 'retired':
            namespace.setdefault('_prior_seats', {})[payload['agent_id']] = deepcopy(entry['promoted_seat'])
            entry.update(status='retired', promoted_seat=None)
        elif (entry['status'], target) in (('draft', 'shadow'), ('shadow', 'promoted')):
            bench = namespace.get('_benchmarks', {}).get(payload.get('bench_id'), {})
            # Legacy frozen status payloads have no seat. Declaration-derived
            # metadata is sufficient for a pure fold, never for new admission.
            selected = payload.get('seat', bench.get('seat'))
            if selected is not None:
                _seat(selected)
            entry.update(status=target, promoted_seat=deepcopy(selected))
            if target == 'shadow':
                entry.update(shadow_event_id=event['id'], shadow_lamport=event['lamport'],
                             selection_bench_id=payload.get('bench_id'),
                             n_shadow_runs=bench.get('n_shadow_runs'))
    else:
        record = payload['record']
        run_id = record['run_id']
        closes = namespace.setdefault('_closed', {})
        if run_id in closes:
            return state
        opening = namespace.get('_opens', {}).get(run_id)
        if (opening is None or event.get('agent') != record.get('agent_id')
                or payload.get('gate', {}).get('passed') is not True
                or record.get('memory', {}).get('gate_passed') is not True
                or any(record.get(key) != opening.get(key) for key in
                       ('run_id', 'agent_id', 'agent_version', 'seat', 'task', 'memory_arm', 'parents_context'))):
            return state
        closes[run_id] = True
        entry = namespace.get(record['agent_id'])
        if entry is None or entry['status'] == 'retired':
            return state
        # A-PRM1: benchmark cells (task carries bench_id) are measurements of the
        # agent, not its work: they neither count toward nor reset the
        # three-consecutive-failures retirement streak. Retiring an agent in the
        # middle of its own evaluation would abort or bias the benchmark.
        if 'bench_id' in record.get('task', {}):
            return state
        outcome = record['outcome']['verdict']
        if outcome in _FAILURES:
            entry['failure_streak'] += 1
            if entry['failure_streak'] >= 3:
                namespace.setdefault('_prior_seats', {})[record['agent_id']] = deepcopy(entry['promoted_seat'])
                entry.update(status='retired', promoted_seat=None)
        elif outcome in _SUCCESSES:
            entry['failure_streak'] = 0
    return state


# The installed callable-fold registry uses order attributes, not FoldSpec.
apply.order = 90


def _lifecycle(history):
    state = {}
    for event in history:
        apply(state, event)
    return state.get('promotion', {})



def _effective_record(record, namespace):
    """Overlay qualification metadata without changing the owner's record."""
    result = deepcopy(record)
    lifecycle = namespace.get(result['agent_id'])
    if lifecycle is not None:
        result['status'] = lifecycle['status']
        if lifecycle['promoted_seat'] is None:
            result.pop('promoted_seat', None)
        else:
            result['promoted_seat'] = deepcopy(lifecycle['promoted_seat'])
    return result


def _install_reader_adapters():
    """Bridge the integrated agent and historical-memory reader signatures.

    U12 reads its own namespace; U11 rebuilds historical generations using
    only its memory fold. Both must consume U19's effective status and seat,
    including when no explicit status event represents automatic retirement.
    Keep their identity/version checks and materializers intact. The adapters
    return detached records and never change a fold's namespace ownership.
    """
    from lineage.domain import agents
    from lineage.domain.memory import store

    if not getattr(agents._record, '_promotion_reader', False):
        native_record = agents._record

        @wraps(native_record)
        def record(state, agent_id):
            return _effective_record(native_record(state, agent_id), state.get('promotion', {}))

        record._promotion_reader = True
        agents._record = record

    if not getattr(store._agent_at, '_promotion_reader', False):
        native_agent_at = store._agent_at

        @wraps(native_agent_at)
        def agent_at(agent_id, events, state):
            record = native_agent_at(agent_id, events, state)
            namespace = state.get('promotion')
            if namespace is None:
                namespace = _lifecycle(events)
            return _effective_record(record, namespace)

        agent_at._promotion_reader = True
        store._agent_at = agent_at



def _install_family_adapter():
    """Translate U19's prefix digest at the installed family witness seam.

    The native mailbox expects an event digest. U19's frozen Commit requires
    the hash of the original committed prefix. Verify that prefix first,
    then let the native witness check event ownership and unchanged OpId.
    Only its detached input is translated; public and retained results keep
    the required prefix digest on every carrier and replay.
    """
    from lineage.core import family

    if getattr(family.Mailbox._witness, '_promotion_witness', False):
        return
    native_witness = family.Mailbox._witness

    @wraps(native_witness)
    def witness(mailbox, value, result, name):
        if name != 'agent_promote' or 'untrusted' not in result:
            return native_witness(mailbox, value, result, name)
        try:
            commit = result['untrusted']['commit']
            history = journal.snapshot(mailbox.runtime.context.home)
            selected = [event for event in history if event['id'] in commit['event_ids']]
            if len(selected) != 1 or [selected[0]['id']] != commit['event_ids']:
                raise ValueError
            event = selected[0]
            if event['kind'] != 'agent.status' or event['lamport'] != commit['head']:
                raise ValueError
            prefix = tuple(item for item in history if item['lamport'] <= event['lamport'])
            digest = hashlib.sha256(b''.join(journal.canonical_bytes(item) + b'\n'
                                            for item in prefix)).hexdigest()
            if commit['sha256'] != digest:
                raise ValueError
            translated = deepcopy(result)
            translated['untrusted']['commit']['sha256'] = event['sha256']
            return native_witness(mailbox, value, translated, name)
        except Exception:
            raise family.RecoveryError('missing verified application witness') from None

    witness._promotion_witness = True
    family.Mailbox._witness = witness


def _bench(history, bench_id):
    declarations = [e for e in history if e['kind'] == 'bench.declared'
                    and e['payload'].get('bench_id') == bench_id]
    verdicts = [e for e in history if e['kind'] == 'bench.verdict'
                and e['payload'].get('bench_id') == bench_id]
    if not declarations or not verdicts:
        _refuse('no_benchmark', 'a committed declaration and verdict are required')
    if len(declarations) != 1 or len(verdicts) != 1:
        _refuse()
    if declarations[0]['lamport'] >= verdicts[0]['lamport']:
        _refuse()
    return declarations[0], verdicts[0]


def _runs(history):
    opens, closes = {}, {}
    for event in history:
        if event['kind'] == 'run.open':
            key = event['payload']['run_id']
            if key in opens:
                _refuse()
            opens[key] = event
        elif event['kind'] == 'run.close':
            key = event['payload']['record']['run_id']
            if key in closes:
                # A repeated receipt cannot manufacture independent evidence.
                if closes[key] != event:
                    _refuse()
                continue
            closes[key] = event
    return opens, closes


def _valid_run(history, opening, closing):
    """Check consistency of witnesses already admitted by the memory owner."""
    if opening is None or closing is None:
        return False
    start, end = opening['payload'], closing['payload']
    record = end['record']
    if (opening['lamport'] >= closing['lamport']
            or end.get('gate', {}).get('passed') is not True
            or record.get('memory', {}).get('gate_passed') is not True
            or opening['agent'] != start['agent_id'] or closing['agent'] != start['agent_id']
            or any(record.get(k) != start.get(k) for k in
                   ('run_id', 'agent_id', 'agent_version', 'seat', 'task', 'memory_arm', 'parents_context'))):
        return False
    ids = record['memory'].get('unit_ids')
    if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids):
        return False
    witnesses = {}
    for event in history:
        if not opening['lamport'] < event['lamport'] < closing['lamport'] or event['kind'] != 'memory.put':
            continue
        payload, owner = event['payload'], start['agent_id']
        unit = payload['unit']
        if (payload.get('agent_id') != owner or payload.get('run_id') != start['run_id']
                or event['agent'] != owner or unit.get('status') != 'active'
                or unit.get('privacy') == 'private'
                or unit.get('provenance', {}).get('run_id') != start['run_id']):
            continue
        witnesses[unit['id']] = unit
    if any(key not in witnesses for key in ids):
        return False
    kinds = set()
    for key in ids:
        unit = witnesses[key]
        if unit['kind'] == 'episode':
            body = unit['body']
            if (body.get('run_id') != start['run_id'] or body.get('task_id') != start['task']['id']
                    or any(body.get(k) != record.get(k) for k in ('seat', 'outcome', 'cost', 'parents_context'))):
                return False
        kinds.add(unit['kind'])
    outcome = record['outcome']
    return ('episode' in kinds
            and (outcome['verdict'] not in _FAILURES and outcome['repair_loops'] == 0 or 'lesson' in kinds)
            and (outcome['verdict'] not in ('HOLD', 'red') or 'negative' in kinds))


def _benchmark_version(history, declaration_event, opening, declared, opens):
    """Reconcile U16 run versions with the immutable declaration identity.

    The installed arena opens later cells with the current memory generation.
    Only memory originating in this benchmark may bridge that difference;
    qualification itself continues to return the declaration-prefix record.
    """
    start = opening['payload']
    if start['agent_version'] == declared['agent_version']:
        return True
    before = tuple(e for e in history if e['lamport'] < opening['lamport'])
    current = _identities(before).get(start['agent_id'])
    if current is None or start['agent_version'] != current['agent_version']:
        return False
    for event in before:
        if event['lamport'] <= declaration_event['lamport']:
            continue
        payload = event['payload']
        if event['kind'] not in ('memory.put', 'memory.retire') or payload.get('agent_id') != start['agent_id']:
            continue
        if event['kind'] == 'memory.retire':
            return False
        source = opens.get(payload.get('run_id'))
        if (source is None or source['lamport'] >= event['lamport']
                or source['payload']['agent_id'] != start['agent_id']
                or source['payload']['task'].get('bench_id') != declaration_event['payload']['bench_id']):
            return False
    return all(current[key] == declared[key] for key in ('constitution_sha256', 'skills'))


def _equal_stat(actual, expected):
    # Only reconciliation tolerates floating arithmetic rounding. Admission
    # inequalities below remain strict, with no epsilon or rounded reward.
    return math.isclose(_number(actual), expected, rel_tol=1e-12, abs_tol=1e-15)


def _qualification(history, agent_id, bench_id, seat):
    declaration_event, final = _bench(history, bench_id)
    declaration, verdict = declaration_event['payload'], final['payload']
    seats = declaration.get('seats')
    if not isinstance(seats, list) or len(seats) != 1 or _seat(seats[0]) != _seat(seat):
        _refuse('bad_args', 'promotion requires the sole declared seat')
    participants = declaration['agents']
    if len(participants) != 2 or participants[0] == participants[1] or participants[1] != agent_id:
        _refuse()
    before = tuple(e for e in history if e['lamport'] < declaration_event['lamport'])
    records = _identities(before)
    if any(key not in records for key in participants) or seat not in records[agent_id]['allowed_seats']:
        _refuse()
    pin = declaration.get('bank_sha256')
    if type(pin) is not str or re.fullmatch('[0-9a-f]{64}', pin) is None:
        _refuse('internal', 'immutable bank provenance unavailable')
    purpose = declaration.get('purpose')
    if purpose not in ('select', 'confirm'):
        _refuse()
    arms = declaration.get('memory_arms')
    if (not isinstance(arms, list) or not arms or len(set(arms)) != len(arms)
            or any(arm not in ('none', 'own', 'inherited') for arm in arms)):
        _refuse()
    opens, closes = _runs(history)
    rows = [e for e in history if e['kind'] == 'bench.result' and e['payload'].get('bench_id') == bench_id]
    if not rows:
        _refuse()
    tasks, used = {}, set()
    for event in rows:
        row = event['payload']
        rid = row['run_id']
        if rid in used:
            _refuse()
        used.add(rid)
        opening, closing = opens.get(rid), closes.get(rid)
        if not _valid_run(history, opening, closing):
            _refuse()
        start, record = opening['payload'], closing['payload']['record']
        if not declaration_event['lamport'] < opening['lamport'] < closing['lamport'] < event['lamport'] < final['lamport']:
            _refuse()
        task = start['task']
        split = task.get('split')
        if split is None:
            _refuse('internal', 'verified source split unavailable')
        if split not in ('select', 'heldout'):
            _refuse('internal', 'verified source split unavailable')
        if split != ('select' if purpose == 'select' else 'heldout'):
            _refuse('heldout_forbidden', 'benchmark consumed a forbidden source split')
        if (row['agent_id'] not in participants or row['seat'] != seat or row['memory_arm'] not in arms
                or task.get('id') != row['task_id'] or task.get('bench_id') != bench_id
                or task.get('bank_id') != declaration['bank_id']
                or any(row.get(k) != record.get(k) for k in ('agent_id', 'seat', 'memory_arm', 'cost'))
                or row.get('verdict') != record['outcome']['verdict']
                or not _benchmark_version(history, declaration_event, opening, records[row['agent_id']], opens)):
            _refuse()
        correctness = _number(row.get('correctness'))
        if correctness != int(row['verdict'] in _SUCCESSES):
            _refuse()
        cells = tasks.setdefault(row['task_id'], {})
        cells.setdefault((row['agent_id'], row['memory_arm']), []).append(correctness)
    if any(start['payload']['task'].get('bench_id') == bench_id and rid not in used
           for rid, start in opens.items()):
        _refuse()
    means = []
    for task_id, cells in tasks.items():
        groups = [cells.get((agent, arm), []) for agent in participants for arm in arms]
        if not all(groups) or len({len(group) for group in groups}) != 1:
            _refuse()
        pair = [statistics.mean(value for arm in arms for value in cells[(agent, arm)]) for agent in participants]
        means.append((task_id, pair))
    parameters = declaration['sprt']
    for key in ('p0', 'p1', 'alpha', 'beta'):
        if not 0 < _number(parameters.get(key)) < 1:
            _refuse()
    if parameters['p0'] >= parameters['p1']:
        _refuse()
    _integer(parameters.get('cap'), 1, 1000000)
    from lineage.domain.arena.bench import _sprt
    observations = [{'task_id': key, 'seed': 0,
                     'outcome': 'win' if pair[1] > pair[0] else 'loss' if pair[1] < pair[0] else 'tie'}
                    for key, pair in means]
    report = _sprt(observations, parameters)
    if (report['decision'] != 'superior' or verdict.get('decision') != report['decision']
            or _integer(verdict.get('n_discordant')) != report['n_discordant']
            or not _equal_stat(verdict.get('llr'), report['llr'])):
        _refuse()
    chosen = means[:report['n_tasks']]
    baseline = [pair[0] for _, pair in chosen]
    candidate = [pair[1] for _, pair in chosen]
    rewards = [new - old for new, old in zip(candidate, baseline)]
    gain = statistics.mean(candidate) - statistics.mean(baseline)
    dispersion = statistics.pstdev(baseline)
    minimum = min(rewards)
    rule = declaration['credit_rule']
    if rule.get('metric') != 'correctness_first' or rule.get('dispersion') != 'population_stddev':
        _refuse()
    minimum_gain = _number(rule.get('minimum_gain'))
    credit = verdict.get('credit')
    if (type(credit) is not dict or credit.get('credited') is not True
            or not _equal_stat(credit.get('gain'), gain)
            or not _equal_stat(credit.get('baseline_dispersion'), dispersion)
            or not _equal_stat(credit.get('minimum_reward'), minimum)
            or _number(credit.get('minimum_reward')) < 0
            or minimum < 0 or any(pair[1] < pair[0] for _, pair in means)
            or gain <= 0 or gain <= dispersion or gain <= minimum_gain):
        _refuse()
    return declaration_event, records[agent_id], set(tasks)


def evaluate(snapshot, agent_id: str, bench_id: str, *, seat: JSONObject) -> JSONObject:
    """Admit a transition from a verified prefix, with no I/O or side effects."""
    try:
        history = _events(snapshot)
        if not any(e['kind'] == 'agent.born' and e['payload']['record']['agent_id'] == agent_id for e in history):
            _refuse('no_agent', 'committed agent does not exist')
        _bench(history, bench_id)
        _seat(seat)
        declaration_event, identity, tasks = _qualification(history, agent_id, bench_id, seat)
        declaration = declaration_event['payload']
        entry = _lifecycle(history)[agent_id]
        status = entry['status']
        if status == 'draft':
            if declaration['purpose'] != 'select':
                _refuse()
            target, reason = 'shadow', 'qualified selection benchmark'
        elif status == 'shadow':
            if declaration['purpose'] != 'confirm' or declaration_event['lamport'] <= entry['shadow_lamport']:
                _refuse()
            shadow_index = next(i for i, e in enumerate(history) if e['id'] == entry['shadow_event_id'])
            selection_id = entry['selection_bench_id']
            if selection_id == bench_id:
                _refuse()
            selection, old_identity, selected = _qualification(history[:shadow_index], agent_id, selection_id, seat)
            if selection['payload']['purpose'] != 'select':
                _refuse()
            required = _integer(selection['payload'].get('promotion', {}).get('n_shadow_runs'), 1, 1000000)
            if any(identity[key] != old_identity[key] for key in ('constitution_sha256', 'skills')):
                _refuse()
            if entry['promoted_seat'] != seat:
                _refuse()
            if selection['payload']['bank_sha256'] != declaration['bank_sha256']:
                _refuse('internal', 'cross-bank independence provenance unavailable')
            if tasks & selected:
                _refuse('heldout_forbidden', 'confirmation overlaps contributing selection evidence')
            opens, closes = _runs(history)
            benchmark_runs = {e['payload']['run_id'] for e in history if e['kind'] == 'bench.result'}
            clean = set()
            for rid, close in closes.items():
                opening = opens.get(rid)
                if opening is None or rid in benchmark_runs:
                    continue
                start, record = opening['payload'], close['payload']['record']
                if (entry['shadow_lamport'] < opening['lamport'] < close['lamport'] < declaration_event['lamport']
                        and start['agent_id'] == agent_id and start['seat'] == seat
                        and start['agent_version'] == identity['agent_version']
                        and 'bench_id' not in start['task'] and 'bench_id' not in record['task']
                        and record['outcome']['verdict'] in _SUCCESSES
                        and type(record['outcome']['repair_loops']) is int and record['outcome']['repair_loops'] == 0
                        and _valid_run(history, opening, close)):
                    clean.add(rid)
            if len(clean) < required:
                _refuse()
            target, reason = 'promoted', 'qualified independent confirmation and clean shadow runs'
        else:
            _refuse()
        return {'from': status, 'to': target, 'reason': reason, 'bench_id': bench_id}
    except LineageError as exc:
        if exc.code in _CODES:
            raise
        _refuse('conflict')
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        _refuse()
    except (ImportError, OSError):
        _refuse('internal', 'required promotion policy dependency unavailable')

def _status_schema():
    try:
        root = Path(__file__).resolve().parents[2]
        document = schema.strict_loads((root / 'schemas/event.schema.json').read_bytes())
        return next(rule['then']['properties']['payload'] for rule in document['allOf']
                    if rule.get('if', {}).get('properties', {}).get('kind', {}).get('const') == 'agent.status')
    except Exception:
        _refuse('internal', 'status schema unavailable')


def validate_status(history, event, *, ctx=None):
    """Policy seam called by U12's sole agent.status validator."""
    payload = event['payload']
    if type(payload) is not dict:
        _refuse('internal', 'status payload unavailable')
    declaration, _ = _bench(history, payload.get('bench_id'))
    seats = declaration['payload'].get('seats', [])
    if len(seats) != 1:
        _refuse('bad_args', 'promotion requires a singleton seat')
    selected = payload.get('seat', seats[0])
    expected = evaluate(history, payload.get('agent_id'), payload.get('bench_id'), seat=selected)
    if any(payload.get(key) != expected[key] for key in ('from', 'to', 'bench_id')):
        _refuse()
    if 'seat' not in payload:
        _refuse('internal', 'complete status seat contract unavailable')
    try:
        schema.validate(payload, _status_schema())
    except schema.SchemaError:
        _refuse('internal', 'complete status seat contract unavailable')


def _render(history, event, ctx):
    from lineage.domain import agents
    prefix = tuple(e for e in history if e['lamport'] <= event['lamport'])
    state = agents._state(prefix, ctx)
    record = agents._record(state, event['payload']['agent_id'])
    lifecycle = _lifecycle(prefix)[record['agent_id']]
    record['status'] = lifecycle['status']
    if lifecycle['promoted_seat'] is None:
        record.pop('promoted_seat', None)
    else:
        record['promoted_seat'] = deepcopy(lifecycle['promoted_seat'])
    digest = hashlib.sha256(b''.join(journal.canonical_bytes(e) + b'\n' for e in prefix)).hexdigest()
    value = {'record': record, 'commit': {'event_ids': [event['id']], 'head': event['lamport'], 'sha256': digest}}
    if len(journal.canonical_bytes(value)) > 1048576:
        _refuse('internal', 'promotion result exceeds transport capacity')
    return deepcopy(value)


def promote(agent_id: str, bench_id: str, *, seat: JSONObject | None = None,
            command: JSONObject, ctx) -> JSONObject:
    """Resolve and qualify under the existing lock; preserve original replay."""
    from lineage.ext.promotion import INPUT_SCHEMA
    from lineage.domain import agents
    try:
        if type(command) is not dict or set(command) - {'tool', 'args', 'agent', 'op_id', 'expected_head'}:
            _refuse('bad_args', 'invalid promotion command')
        args = deepcopy(command['args'])
        schema.validate(args, INPUT_SCHEMA)
        if (command['tool'] != 'agent_promote' or args['agent_id'] != agent_id or args['bench_id'] != bench_id
                or command['agent'] != args['agent'] or command['op_id'] != args['op_id']
                or command.get('expected_head', args.get('expected_head')) != args.get('expected_head')):
            _refuse('bad_args', 'command differs from effective request')
    except LineageError:
        raise
    except Exception:
        _refuse('bad_args', 'invalid promotion arguments')
    try:
        changes = {'actor': args['agent']}
        if hasattr(ctx, 'op_id'):
            changes['op_id'] = args['op_id']
        if hasattr(ctx, 'authority'):
            changes['authority'] = 'tool'
        ctx = replace(ctx, **changes)
        services = getattr(ctx, 'services', None)
        validators = services.registry.validators if services is not None else ctx.validators
    except Exception:
        _refuse('internal', 'required promotion runtime unavailable')
    effective = {key: value for key, value in args.items() if key not in ('op_id', 'expected_head')}
    request = {'tool': 'agent_promote', 'args': effective}
    rendered = []

    def prepare(history, draft):
        head = history[-1]['lamport'] if history else 0
        if 'expected_head' in args and args['expected_head'] != head:
            _refuse('stale_rev', 'expected head differs')
        required = ('agent.born', 'agent.status', 'run.open', 'run.close',
                    'bench.declared', 'bench.result', 'bench.verdict')
        if any(not callable(validators.get(key)) for key in required):
            _refuse('internal', 'required promotion owner unavailable')
        if not any(e['kind'] == 'agent.born' and e['payload']['record']['agent_id'] == agent_id for e in history):
            _refuse('no_agent', 'committed agent does not exist')
        declaration, _ = _bench(history, bench_id)
        seats = declaration['payload'].get('seats', [])
        if len(seats) != 1:
            _refuse('bad_args', 'promotion requires a singleton seat')
        selected = deepcopy(seats[0] if seat is None else seat)
        transition = evaluate(history, agent_id, bench_id, seat=selected)
        payload = {'agent_id': agent_id, **transition, 'seat': selected}
        try:
            schema.validate(payload, _status_schema())
        except schema.SchemaError:
            _refuse('internal', 'complete status seat contract unavailable')
        return payload

    def validate(history, event):
        owner = validators.get('agent.status')
        if not callable(owner):
            _refuse('internal', 'shared status validator unavailable')
        owner(history, event, ctx=ctx)
        rendered.append(_render((*history, event), event, ctx))

    try:
        event = journal.transact(agents._home(ctx), agent=args['agent'], op_id=args['op_id'],
                                 kind='agent.status', payload=request,
                                 validators={'agent.status': validate}, prepare=prepare,
                                 clock=getattr(services, 'clock', None),
                                 id_factory=getattr(services, 'id_factory', None))
        value = rendered[0] if rendered else _render(journal.snapshot(agents._home(ctx)), event, ctx)
        agents.refresh_projections(agent_id, ctx=ctx)
        return deepcopy(value)
    except LineageError as exc:
        code = exc.code if exc.code in _CODES else 'internal'
        # Native JSON intentionally omits optional diagnostics; keep domain
        # refusals identical across carriers without losing their fixed code.
        raise LineageError(code) from None
    except Exception:
        _refuse('internal', 'promotion operation unavailable')
