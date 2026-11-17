"""Journal-authoritative run lifecycle over the installed U03 transaction API.

Native prepare/validator callbacks receive history and a journal-owned event.
This adapter validates results before append and leaves replay, locking, event
identity, chain integrity and durable rollback to that implementation.
"""
from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from types import SimpleNamespace

from lineage.core import journal, registry, schema
from lineage.core.errors import LineageError
from . import gate_close
from .memory import schema as memory_schema
from .version import agent_version

_FROZEN = ('agent_id', 'agent_version', 'seat', 'task', 'parents_context', 'memory_arm')
_SAFE = 9007199254740991


def _sequence(value):
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise LineageError('bad_args', 'invalid collection')
    return deepcopy(list(value))


def _check_args(tool, args):
    from lineage.ext.runs import _SCHEMAS
    try:
        memory_schema._validate(args, _SCHEMAS[tool], store=memory_schema._STORE)
    except schema.SchemaError:
        raise LineageError('bad_args', 'invalid run arguments') from None
    task = args.get('task')
    if task is not None:
        present = set(task) & {'bank_id', 'bench_id', 'split'}
        if present and present != {'bank_id', 'bench_id', 'split'}:
            raise LineageError('bad_args', 'benchmark fields must be supplied together')
    try:
        if len(journal.canonical_bytes(args)) > 1048576:
            raise LineageError('bad_args', 'run arguments exceed byte capacity')
    except LineageError:
        raise LineageError('bad_args', 'invalid run arguments') from None


def _context(context, *, actor=None, op_id=None, tool=False):
    services = getattr(context, 'services', None)
    if services is None:
        if not hasattr(context, 'home'):
            raise LineageError('internal', 'run runtime unavailable')
        services = SimpleNamespace(home=context.home,
            registry=registry.Registry({}, context.validators, context.folds),
            clock=getattr(context, 'clock', None), id_factory=getattr(context, 'id_factory', None),
            token_count=getattr(context, 'token_count', None))
    return SimpleNamespace(services=services,
        actor=getattr(context, 'actor', None) if actor is None else actor,
        authority='tool' if tool else getattr(context, 'authority', 'tool'),
        op_id=getattr(context, 'op_id', None) if op_id is None else op_id,
        transport=getattr(context, 'transport', 'library'))


def _validator_context(event, ctx):
    if ctx is not None:
        return _context(ctx)
    # Native direct journal admission supplies no runtime context. Rebuild from
    # committed events and registered folds. Evidence without a root fails closed.
    return SimpleNamespace(actor=event['agent'], authority='tool',
        services=SimpleNamespace(home=None, registry=registry.load(), token_count=None))


def _command(tool, data, command, ctx):
    try:
        # Open admission checks the complete seat before actor binding under
        # the journal lock; an inadmissible seat retains its contract error.
        if tool != 'run_open' and command.agent != ctx.actor:
            raise LineageError('bad_args', 'actor_mismatch')
        effective = deepcopy(command.args)
        if type(effective) is not dict:
            raise ValueError
        effective.setdefault('agent', command.agent)
        if effective['agent'] != command.agent:
            raise LineageError('bad_args', 'actor_mismatch')
        if 'op_id' in effective and effective['op_id'] != command.op_id:
            raise ValueError
        if getattr(ctx, 'op_id', None) not in (None, command.op_id):
            raise ValueError
        if command.tool == tool:
            if tool == 'run_close':
                effective.setdefault('evidence', [])
            for key, value in data.items():
                if key not in effective or effective[key] != value:
                    raise ValueError
            _check_args(tool, {**effective, 'op_id': command.op_id})
        else:
            # Compound callers retain their validated root request and use
            # distinct suboperation identities. Admission still binds the owner.
            if type(command.tool) is not str or not command.tool:
                raise ValueError
            schema.validate(effective, {})
            _check_args(tool, {**data, 'agent': command.agent, 'op_id': command.op_id})
        expected = command.expected_head
        if expected is not None and (type(expected) is not int or not 0 <= expected <= _SAFE):
            raise ValueError
        effective.pop('op_id', None)
        effective.pop('expected_head', None)
        return {'tool': command.tool, 'args': effective}
    except LineageError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError):
        raise LineageError('bad_args', 'command differs from run arguments') from None


def _commit(event):
    return {'event_ids': [event['id']], 'head': event['lamport'], 'sha256': event['sha256']}


def _result(tool, event, *, validate=None):
    from lineage.ext.runs import _RESULTS
    field = {'run_open': 'opened', 'run_beat': 'event', 'run_close': 'run'}[tool]
    value = event['payload']['record'] if tool == 'run_close' else event
    data = {field: deepcopy(value), 'commit': _commit(event)}
    # Invoke the installed U02 boundary on the bounded rendered result before
    # durability; the memory facade supplies bundled $ref/conditional support.
    (schema.validate if validate is None else validate)(data, _RESULTS[tool], store=memory_schema._STORE)
    if len(journal.canonical_bytes(data)) > 1048576:
        raise LineageError('internal', 'run result exceeds byte capacity')
    return data


def _version(record):
    try:
        actual = agent_version(record['constitution_sha256'], record['skills'], record['memory_gen'])
    except (LineageError, KeyError, TypeError):
        raise LineageError('hash_mismatch', 'agent version inputs invalid') from None
    if actual != record['agent_version']:
        raise LineageError('hash_mismatch', 'agent version digest mismatch')


def _open_eligible(snapshot, data, actor, ctx):
    if any(event['kind'] == 'run.open' and event['payload']['run_id'] == data['run_id']
           for event in snapshot.events):
        raise LineageError('conflict', 'run identity already exists')
    agent = gate_close._agent(snapshot, data['agent_id'])
    if data['seat'] not in agent['allowed_seats']:
        raise LineageError('seat_not_allowed', 'complete seat is not allowed')
    if getattr(ctx, 'authority', 'tool') == 'tool' and actor != data['agent_id']:
        raise LineageError('bad_args', 'actor_mismatch')
    if actor != ctx.actor:
        raise LineageError('bad_args', 'actor_mismatch')
    if agent['status'] == 'retired':
        raise LineageError('conflict', 'agent is retired')
    promotion = snapshot.state.get('promotion', {}).get(data['agent_id'], {})
    if isinstance(promotion, dict) and promotion.get('status') == 'retired':
        raise LineageError('conflict', 'agent is retired')
    _version(agent)
    return agent


def _opening_version(snapshot, opening, ctx):
    prefix = []
    for event in snapshot.events:
        if event['id'] == opening['id']:
            break
        prefix.append(event)
    original = gate_close._snapshot(prefix, ctx)
    agent = gate_close._agent(original, opening['payload']['agent_id'])
    _version(agent)
    if opening['payload']['agent_version'] != agent['agent_version']:
        raise LineageError('hash_mismatch', 'opening version digest mismatch')


def _record(snapshot, event, outcome, cost, evidence, report, ctx):
    run_id = event['payload'].get('run_id')
    if run_id is None:
        run_id = event['payload']['record']['run_id']
    opening = gate_close._opening(snapshot, run_id)
    if event['ts'] < opening['ts']:
        raise LineageError('conflict', 'run timestamp precedes opening')
    selected = gate_close._selection(snapshot, run_id, outcome, cost, actor=event['agent'], ctx=ctx)
    return {'schema': 'lineage.run/v1', 'run_id': run_id,
        'ts_open': opening['ts'], 'ts_close': event['ts'],
        **{key: deepcopy(opening['payload'][key]) for key in _FROZEN},
        'outcome': deepcopy(outcome), 'cost': deepcopy(cost), 'evidence': deepcopy(evidence),
        'memory': {'unit_ids': sorted(unit['id'] for unit in selected),
                   'levels': sorted({unit['level'] for unit in selected}), 'gate_passed': True}}


def _validate_open(history, event, ctx=None):
    ctx = _validator_context(event, ctx)
    memory_schema._shape(event, 'event.schema.json')
    data = event['payload']
    _check_args('run_open', {key: deepcopy(value) for key, value in
        {**data, 'agent': event['agent'], 'op_id': event['op_id']}.items() if key != 'agent_version'})
    agent = _open_eligible(gate_close._snapshot(history, ctx), data, event['agent'], ctx)
    if data['agent_version'] != agent['agent_version']:
        raise LineageError('conflict', 'opening differs from committed version')
    _result('run_open', event)


def _validate_beat(history, event, ctx=None):
    ctx = _validator_context(event, ctx)
    memory_schema._shape(event, 'event.schema.json')
    data = event['payload']
    _check_args('run_beat', {'run_id': data['run_id'], 'progress': data['progress'],
                          'agent': event['agent'], 'op_id': event['op_id']})
    opening, _ = gate_close._eligible(gate_close._snapshot(history, ctx),
        data['run_id'], event['agent'], ctx, closing=False)
    if data['agent_id'] != opening['payload']['agent_id']:
        raise LineageError('conflict', 'heartbeat owner differs')
    if event['ts'] < opening['ts']:
        raise LineageError('conflict', 'run timestamp precedes opening')
    _result('run_beat', event)


def _validate_close(history, event, ctx=None):
    ctx = _validator_context(event, ctx)
    memory_schema._shape(event, 'event.schema.json')
    payload, snapshot = event['payload'], gate_close._snapshot(history, ctx)
    record = payload['record']
    run_id, outcome, cost = record['run_id'], record['outcome'], record['cost']
    opening, _ = gate_close._eligible(snapshot, run_id, event['agent'], ctx)
    _opening_version(snapshot, opening, ctx)
    if event['evidence'] != record['evidence']:
        raise LineageError('conflict', 'task evidence differs')
    for receipt in record['evidence']:
        gate_close._evidence(receipt, ctx)
    report = gate_close.check(snapshot, run_id, outcome, cost, actor=event['agent'], ctx=ctx)
    expected = _record(snapshot, event, outcome, cost, record['evidence'], report, ctx)
    if (record != expected or payload['gate'] != {key: report[key] for key in ('passed', 'checks')}
            or payload['memory_receipts'] != report['memory_receipts']):
        raise LineageError('conflict', 'proposed close differs from validated witnesses')
    _result('run_close', event)


def _transact(tool, data, command, ctx):
    ctx = _context(ctx)
    request = _command(tool, data, command, ctx)
    kind = {'run_open': 'run.open', 'run_beat': 'run.beat', 'run_close': 'run.close'}[tool]
    result_validator, rendered = schema.validate, []

    def prepare(history, draft):
        head = history[-1]['lamport'] if history else 0
        if command.expected_head is not None and command.expected_head != head:
            raise LineageError('stale_rev', 'expected head differs')
        snapshot = gate_close._snapshot(history, ctx)
        if tool == 'run_open':
            agent = _open_eligible(snapshot, data, command.agent, ctx)
            return {**deepcopy(data), 'agent_version': agent['agent_version']}
        opening, _ = gate_close._eligible(snapshot, data['run_id'], command.agent, ctx,
                                           closing=tool == 'run_close')
        if draft['ts'] < opening['ts']:
            raise LineageError('conflict', 'run timestamp precedes opening')
        if tool == 'run_beat':
            return {**deepcopy(data), 'agent_id': opening['payload']['agent_id']}
        _opening_version(snapshot, opening, ctx)
        for receipt in data['evidence']:
            gate_close._evidence(receipt, ctx)
        report = gate_close.check(snapshot, data['run_id'], data['outcome'], data['cost'],
                                  actor=command.agent, ctx=ctx)
        # Projection refresh renders every retained memory generation. Prove
        # their byte/token capacity while PREPARE still holds the journal lock,
        # before a close or any projection bytes can become durable. Closing
        # changes scorecards, but not the units or entry version inputs.
        from .memory import fold, store
        agent_id = opening['payload']['agent_id']
        store.generation_files(gate_close._agent(snapshot, agent_id),
            fold.units_for(snapshot.state, agent_id, include_private=True), snapshot.events,
            token_count=getattr(ctx.services, 'token_count', None))
        return {'record': _record(snapshot, {**draft, 'payload': data},
            data['outcome'], data['cost'], data['evidence'], report, ctx),
            'gate': {key: report[key] for key in ('passed', 'checks')},
            'memory_receipts': deepcopy(report['memory_receipts'])}

    def validate(history, event):
        callback = ctx.services.registry.validators.get(kind)
        if callback is None:
            raise LineageError('internal', 'registered run validator unavailable')
        callback(history, event, ctx=ctx)
        rendered.append(_result(tool, event, validate=result_validator))

    try:
        event = journal.transact(gate_close._home(ctx), agent=command.agent,
            op_id=command.op_id, kind=kind, payload=request, validators={kind: validate},
            evidence=data.get('evidence', ()), prepare=prepare,
            clock=getattr(ctx.services, 'clock', None),
            id_factory=getattr(ctx.services, 'id_factory', None))
        # Native replay returns its original event without executing callbacks.
        value = rendered[0] if rendered else _result(tool, event, validate=result_validator)
        if tool == 'run_close':
            # Closing changes the scorecard. Publish only after journal durability,
            # including retries recovering a failed postcommit publication.
            from . import agents
            try:
                agents.refresh_projections(event['payload']['record']['agent_id'], ctx=ctx)
            except Exception:
                raise LineageError('internal', 'run projection publication failed') from None
        return registry.Committed(event=deepcopy(event), value=deepcopy(value),
                                  head=event['lamport'], sha256=event['sha256'])
    except LineageError:
        raise
    except Exception:
        raise LineageError('internal', 'run transaction failed') from None


def open_run(run_id: str, agent_id: str, seat: dict, task: dict, *,
             parents_context: Sequence[dict], memory_arm: str, command, ctx):
    data = {'run_id': run_id, 'agent_id': agent_id, 'seat': deepcopy(seat),
            'task': deepcopy(task), 'parents_context': _sequence(parents_context), 'memory_arm': memory_arm}
    return _transact('run_open', data, command, ctx)


def beat(run_id: str, progress: str, *, command, ctx):
    return _transact('run_beat', {'run_id': run_id, 'progress': progress}, command, ctx)


def close(run_id: str, outcome: dict, cost: dict, *, evidence: Sequence[dict] = (), command, ctx):
    return _transact('run_close', {'run_id': run_id, 'outcome': deepcopy(outcome),
        'cost': deepcopy(cost), 'evidence': _sequence(evidence)}, command, ctx)


def get(run_id: str, *, ctx) -> dict:
    _check_args('run_get', {'run_id': run_id})
    ctx = _context(ctx)
    try:
        history = journal.snapshot(gate_close._home(ctx))
        snapshot = gate_close._snapshot(history, ctx)
        opening = gate_close._opening(snapshot, run_id)
        closed = next((event['payload']['record'] for event in history
            if event['kind'] == 'run.close' and event['payload']['record']['run_id'] == run_id), None)
        data = {'opened': deepcopy(opening), 'closed': deepcopy(closed), 'head': snapshot.head}
        from lineage.ext.runs import _RESULTS
        schema.validate(data, _RESULTS['run_get'], store=memory_schema._STORE)
        return deepcopy(data)
    except LineageError:
        raise
    except Exception:
        raise LineageError('internal', 'run inspection failed') from None


class _RunsFold:
    order = 50
    kinds = frozenset({'run.open', 'run.beat', 'run.close'})

    def __call__(self, state, event):
        if event['kind'] not in self.kinds:
            return
        namespace = state.setdefault('runs', {})
        payload = event['payload']
        if event['kind'] == 'run.open':
            namespace[payload['run_id']] = {**deepcopy(payload), 'opened': deepcopy(event),
                'ts_open': event['ts'], 'ts_close': None, 'closed': None, 'beats': []}
        elif event['kind'] == 'run.beat':
            namespace[payload['run_id']]['beats'].append(deepcopy(event))
        else:
            record = deepcopy(payload['record'])
            row = namespace[record['run_id']]
            row.update(record)
            row['closed'] = deepcopy(record)
