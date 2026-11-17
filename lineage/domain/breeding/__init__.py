"""Locked breeding adapters for the installed journal and dependency services.

U12 owns the shared birth/status validators. The pure admission functions here
are integration seams for that owner, not replacement registry registrations.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from functools import partial

from lineage.core import journal, schema
from lineage.core.errors import LineageError
from lineage.domain import agents, brief
from lineage.domain.memory import entry, fold as memory_fold, schema as memory_schema
from lineage.domain.version import _SAFE, agent_version
from . import inherit


@dataclass(frozen=True)
class Command:
    tool: str
    args: dict
    agent: str
    op_id: str
    expected_head: int | None = None


@dataclass(frozen=True)
class Committed:
    event: dict
    value: dict
    head: int
    sha256: str


def _check(tool, args):
    from lineage.ext.lineage_ops import _SCHEMAS
    try:
        schema.validate(args, _SCHEMAS[tool])
    except schema.SchemaError:
        raise LineageError('bad_args', 'invalid breeding arguments') from None


def _command(tool, data, command):
    try:
        args = deepcopy(command.args)
        _check(tool, args)
        if (command.tool != tool or command.agent != args['agent']
                or command.op_id != args['op_id']
                or command.expected_head != args.get('expected_head')
                or {key: val for key, val in args.items()
                    if key not in ('agent', 'op_id', 'expected_head')} != data):
            raise ValueError
        journal.canonical_bytes(args)
        return Command(tool, args, args['agent'], args['op_id'], args.get('expected_head'))
    except LineageError:
        raise
    except (AttributeError, TypeError, KeyError, ValueError):
        raise LineageError('bad_args', 'command differs from operation arguments') from None


def _validators(ctx):
    try:
        value = ctx.services.registry.validators if hasattr(ctx, 'services') else ctx.validators
        if not isinstance(value, Mapping):
            raise TypeError
        # U12 owns these validators and accepts a runtime-only ctx argument.
        # Bind that argument outside the journal callback; neither a payload
        # field nor a second registration can supply admission authority.
        bound = dict(value)
        for kind in ('agent.born', 'agent.status'):
            owner = bound.get(kind)
            if not callable(owner):
                raise TypeError
            bound[kind] = partial(_admission, kind=kind, owner=owner, ctx=ctx)
        return bound
    except (AttributeError, TypeError):
        raise LineageError('internal', 'shared admission registry unavailable') from None


def _admission(history, event, *, kind, owner, ctx):
    """Compose U17's capability with the genuine shared owner, without replacing it.

    This binding is for breeding births and retirement only. A bare event does
    not acquire promotion authority by choosing the shared status event kind.
    The owning U12 validator independently delegates every admitted operation.
    """
    if kind == 'agent.born':
        validate_birth(history, event, ctx=ctx)
    else:
        validate_retirement(history, event, ctx=ctx)
    owner(history, event, ctx=ctx)


def _shape_agent(record):
    # U10's schema adapter predates propertyNames/maxProperties in rule_overrides.
    # Validate that one map explicitly, then use its closed-record evaluator for
    # all remaining assertions. No public field is dropped from persisted data.
    value = deepcopy(record)
    if type(value) is dict and 'rule_overrides' in value:
        overrides = value.pop('rule_overrides')
        if (type(overrides) is not dict or len(overrides) > 64
                or any(type(key) is not str or not 1 <= len(key) <= 64
                       or type(val) is not str or val not in ('add', 'remove')
                       for key, val in overrides.items())):
            raise LineageError('bad_args', 'invalid constitution rule overrides')
    definition = memory_schema._STORE.load('agent.schema.json')
    definition['properties'].pop('rule_overrides', None)
    try:
        memory_schema._validate(value, definition, store=memory_schema._STORE,
                                base='agent.schema.json')
    except schema.SchemaError:
        raise LineageError('bad_args', 'invalid agent record') from None


def _parent(history, parent_id, child_id, ctx):
    state = agents._state(history, ctx)
    parent = agents._record(state, parent_id)
    _shape_agent(parent)
    if child_id == parent_id or child_id in state.get('agents', {}):
        raise LineageError('conflict', 'child identity already exists')
    if parent['status'] == 'retired':
        raise LineageError('conflict', 'source agent is retired')
    if parent['generation'] >= _SAFE:
        raise LineageError('conflict', 'lineage generation capacity exceeded')
    source = agents._source(state, parent_id)
    agents._constitution_integrity(parent, source)
    if parent['agent_version'] != agent_version(parent['constitution_sha256'], parent['skills'], parent['memory_gen']):
        raise LineageError('hash_mismatch', 'source version inputs differ')
    # This branch is inside the journal callback. U12's history-aware skill
    # path avoids reacquiring the journal lock while verifying immutable bytes.
    try:
        agents._verify_immutable(parent, ctx=ctx, history=history)
    except LineageError as exc:
        if exc.code in ('bad_args', 'hash_mismatch'):
            raise LineageError('hash_mismatch', 'source immutable inputs unavailable') from None
        raise
    units = memory_fold.units_for(state, parent_id, include_inactive=True, include_private=True)
    return parent, source, units


def _birth_payload(history, *, parent_id, child_id, op, display_name,
                   selected_ids, event_id, ctx):
    agents._target(child_id)
    parent, source, units = _parent(history, parent_id, child_id, ctx)
    selection = inherit.select([parent], {parent_id: units}, workflow=parent['workflow'],
                               language=parent['language'], selected_ids=selected_ids, ctx=ctx)
    if len(selection.inherited) > 256:
        raise LineageError('memory_debt', 'inherited unit capacity exceeded; cuts required')
    if len(selection.rejected) > 10000:
        raise LineageError('conflict', 'rejection audit capacity exceeded')
    wrappers = inherit._adopt(selection, child_id)
    record = {key: deepcopy(parent[key]) for key in (
        'schema', 'workflow', 'language', 'allowed_seats', 'references',
        'constitution_sha256', 'skills')}
    if 'rule_overrides' in parent:
        record['rule_overrides'] = deepcopy(parent['rule_overrides'])
    record.update(agent_id=child_id, display_name=parent['display_name'] if display_name is None else display_name,
                  memory_gen=parent['memory_gen'] if op == 'clone' else len(wrappers),
                  generation=parent['generation'] + 1, parents=[parent_id],
                  born={'op': op, 'event_id': event_id}, status='draft')
    record['agent_version'] = agent_version(record['constitution_sha256'], record['skills'], record['memory_gen'])
    adopted = [wrapper['unit'] for wrapper in wrappers]
    # Check memory bytes before the brief renderer's separate output ceiling.
    # Large valid selections must report memory_debt, never a render failure.
    entry.build(record, adopted, token_count=None)
    own = brief.build(record, adopted, rule_ids=source['rule_ids'], memory_arm='own')
    record['brief_head_sha256'] = sha256(own).hexdigest()
    _shape_agent(record)
    # The own brief excludes inherited memory. Capacity must include that arm,
    # as well as the installed entry builder, with no invented token counter.
    inherited_brief = brief.build(record, adopted, rule_ids=source['rule_ids'], memory_arm='inherited')
    if len(inherited_brief) > 6000:
        raise LineageError('memory_debt', 'inherited brief byte capacity exceeded; cuts required')
    payload = {'record': record, 'constitution': deepcopy(source),
               'inherited_units': wrappers, 'rejected_units': list(selection.rejected)}
    journal.canonical_bytes(payload)
    return payload


def validate_birth(history, event, *, ctx):
    """Recompute U17 birth facts for the owning shared agent.born validator.

    The owner must supply a runtime-owned home-aware context. A two-argument
    validator cannot infer that authority from event contents or process globals.
    """
    payload = event.get('payload')
    if type(payload) is not dict or set(payload) != {'record', 'constitution', 'inherited_units', 'rejected_units'}:
        raise LineageError('bad_args', 'invalid birth payload fields')
    record = payload['record']
    _shape_agent(record)
    op = record['born']['op']
    if op not in ('clone', 'distill') or len(record['parents']) != 1:
        raise LineageError('bad_args', 'unsupported breeding operation')
    selected = None
    if op == 'distill':
        # A known eligible exclusion fixes the subset, while a selected unsafe
        # source still keeps its safety reason. No request flags prove admission.
        wrappers, rejected = payload['inherited_units'], payload['rejected_units']
        if type(wrappers) is not list or type(rejected) is not list:
            raise LineageError('bad_args', 'invalid inheritance audit')
        try:
            selected = [wrapper['source_unit_id'] for wrapper in wrappers]
        except (TypeError, KeyError):
            raise LineageError('bad_args', 'invalid inherited source identity') from None
    expected = _birth_payload(history, parent_id=record['parents'][0], child_id=record['agent_id'],
                              op=op, display_name=record['display_name'], selected_ids=selected,
                              event_id=event.get('id'), ctx=ctx)
    if journal.canonical_bytes(payload) != journal.canonical_bytes(expected):
        raise LineageError('not_inheritable', 'birth facts differ from authoritative admission')


def _retirement_payload(history, agent_id, reason, ctx):
    state = agents._state(history, ctx)
    record = agents._record(state, agent_id)
    _shape_agent(record)
    if record['status'] not in ('draft', 'shadow', 'promoted'):
        raise LineageError('conflict', 'target agent is already retired')
    return {'agent_id': agent_id, 'from': record['status'], 'to': 'retired', 'reason': reason}


def validate_retirement(history, event, *, ctx):
    """Pure status admission seam for U12; no general set-status capability."""
    payload = event.get('payload')
    if type(payload) is not dict or set(payload) != {'agent_id', 'from', 'to', 'reason'}:
        raise LineageError('bad_args', 'invalid retirement payload fields')
    _check('agent_retire', {'agent_id': payload['agent_id'], 'reason': payload['reason'],
                            'agent': event['agent'], 'op_id': event['op_id']})
    if payload != _retirement_payload(history, payload['agent_id'], payload['reason'], ctx):
        raise LineageError('conflict', 'retirement transition differs from current lifecycle')


def _commit(event):
    return {'event_ids': [event['id']], 'head': event['lamport'], 'sha256': event['sha256']}


def _render(history, event, ctx):
    if event['kind'] == 'agent.born':
        payload = event['payload']
        data = {key: deepcopy(payload[key]) for key in ('record', 'inherited_units', 'rejected_units')}
    else:
        state = agents._state((*history, event), ctx)
        data = {'record': agents._record(state, event['payload']['agent_id'])}
    data['commit'] = _commit(event)
    journal.canonical_bytes(data)
    return data


def _transact(command, kind, prepare, ctx):
    request = {'tool': command.tool, 'args': {
        key: deepcopy(value) for key, value in command.args.items() if key not in ('op_id', 'expected_head')}}
    rendered = []
    validators = _validators(ctx)

    def prepared(history, draft):
        head = history[-1]['lamport'] if history else 0
        if command.expected_head is not None and command.expected_head != head:
            raise LineageError('stale_rev', 'expected head differs')
        if head >= _SAFE:
            raise LineageError('conflict', 'journal prefix capacity exceeded')
        return prepare(history, draft)

    def validated(history, event):
        owner = validators.get(kind)
        if not callable(owner):
            raise LineageError('internal', 'shared agent admission unavailable')
        # Preserve the installed owner. A missing U12 delegation is a refusal,
        # never permission to replace or mutate the registry's validators.
        owner(history, event)
        rendered.append(_render(history, event, ctx))

    try:
        services = getattr(ctx, 'services', None)
        event = journal.transact(agents._home(ctx), agent=command.agent, op_id=command.op_id,
                                 kind=kind, payload=request, validators={kind: validated}, prepare=prepared,
                                 clock=getattr(services, 'clock', None),
                                 id_factory=getattr(services, 'id_factory', None))
        if rendered:
            value = rendered[0]
        else:
            history = agents._history(ctx)
            prefix = tuple(old for old in history if old['lamport'] < event['lamport'])
            value = _render(prefix, event, ctx)
        child_id = event['payload']['record']['agent_id'] if kind == 'agent.born' else event['payload']['agent_id']
        # Refresh through the owning service after commit or exact replay.
        # It selects the current prefix and canonical layout, repairing partial
        # projections without changing the operation's original logical result.
        agents.refresh_projections(child_id, ctx=ctx)
        return Committed(deepcopy(event), deepcopy(value), event['lamport'], event['sha256'])
    except LineageError as exc:
        detail = 'breeding operation refused'
        if exc.code == 'memory_debt':
            detail = 'memory capacity insufficient; cuts required'
        raise LineageError(exc.code, detail) from None
    except Exception:
        raise LineageError('internal', 'breeding service unavailable') from None
