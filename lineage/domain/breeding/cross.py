"""Deterministic context composition and locked, receipt-backed birth admission.

Adapters use the installed journal, compiler, selector and agent projection
services. No caller-supplied measurement or authority enters a child record.
"""
from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from hashlib import sha256

from lineage.core import journal, schema
from lineage.core.errors import LineageError
from lineage.domain import agents, brief, references
from lineage.domain.memory import entry
from lineage.domain.version import _SAFE, agent_version
from . import Command, Committed, _parent, _shape_agent, inherit


def _text(value, maximum):
    if (type(value) is not str or not 1 <= len(value) <= maximum
            or not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise LineageError('bad_args', 'invalid child text')
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise LineageError('bad_args', 'invalid child text') from None


def _check(tool, args):
    from lineage.ext.breeding2 import _SCHEMAS
    try:
        schema.validate(args, _SCHEMAS[tool])
    except schema.SchemaError:
        raise LineageError('bad_args', 'invalid breeding arguments') from None
    agents._target(args['child_id'])
    if 'display_name' in args:
        _text(args['display_name'], 128)
    if 'language' in args:
        _text(args['language'], 64)


def _command(tool, data, command):
    try:
        args = deepcopy(command.args)
        _check(tool, args)
        if (command.tool != tool or command.agent != args['agent']
                or command.op_id != args['op_id']
                or command.expected_head != args.get('expected_head')
                or {k: v for k, v in args.items()
                    if k not in ('agent', 'op_id', 'expected_head')} != data):
            raise ValueError
        journal.canonical_bytes(args)
        return Command(tool, args, args['agent'], args['op_id'], args.get('expected_head'))
    except LineageError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError):
        raise LineageError('bad_args', 'command differs from operation arguments') from None


def _rules():
    return {row['id']: row for row in references.load_gold_rules()['rules']}


def _rule(rule_id):
    rules = _rules()
    if rule_id not in rules:
        raise LineageError('bad_args', 'unknown source rule')
    return rules[rule_id]


def _protected(rule_id):
    row = _rule(rule_id)
    return row['text'].split()[0] in ('I20', 'I21', 'I22')


def _overrides(parents):
    result = {}
    for parent in parents:
        for key, value in parent.get('rule_overrides', {}).items():
            _rule(key)
            if _protected(key):
                raise LineageError('bad_args', 'authority rule cannot be overridden')
            if value not in ('add', 'remove'):
                raise LineageError('bad_args', 'invalid rule inclusion')
            if key in result and result[key] != value:
                raise LineageError('conflict', 'contradictory rule inclusions')
            result[key] = value
    return dict(sorted(result.items()))


def _compile(record, overlays, *, ctx):
    """Adapt inclusion overrides to verified compiler output, never source prose.

    The installed compiler accepts pinned registry bytes and policy mappings,
    rather than workflow/pins or rule_overrides. Its complete role, language and
    authority checks run first. Overrides select only those verified bullets;
    they cannot make a rule from another role/language applicable.
    """
    source = agents._compile(record, overlays, ctx=ctx)
    overrides = _overrides([record])
    if not overrides:
        return source
    included = set(source['rule_ids'])
    for rule_id, action in overrides.items():
        if action == 'add' and rule_id not in included:
            raise LineageError('bad_args', 'source rule is inapplicable to this constitution')
        if action == 'remove':
            included.discard(rule_id)
    lines = source['text'].splitlines()
    source['text'] = '\n'.join(line for line in lines if not (
        line.startswith('- ') and ': ' in line and line[2:].split(': ', 1)[0] not in included)) + '\n'
    source['rule_ids'] = sorted(included)
    return source


def _claims(wrappers):
    """Conservative same-kind overlap; source bodies stay byte-exact."""
    def norm(text):
        return ' '.join(text.split()).casefold()

    def subject(unit):
        body = unit['body']
        if unit['kind'] == 'lesson':
            return norm(body['tempting_use'])
        if unit['kind'] == 'negative':
            return (norm(body['gate_id']), norm(body['coordinate']))
        return norm(body['trigger_sig'])

    def behavior(unit):
        body = {k: v for k, v in unit['body'].items()
                if unit['kind'] != 'workflow' or k != 'stats'}
        return journal.canonical_bytes({'kind': unit['kind'],
                                        'statement': norm(unit['statement']), 'body': body})

    ordered = sorted(wrappers, key=lambda w: (w['source_agent_id'], w['source_unit_id']))
    for index, left in enumerate(ordered):
        one = left['unit']
        for right in ordered[index + 1:]:
            two = right['unit']
            a, b = one['scope'], two['scope']
            if (one['kind'] != two['kind'] or a['workflow'] != b['workflow']
                    or not (a['language'] == b['language'] or 'general' in (a['language'], b['language']))):
                continue
            overlap = norm(one['statement']) == norm(two['statement']) or subject(one) == subject(two)
            if overlap and behavior(one) != behavior(two):
                identities = [(w['source_agent_id'], w['source_unit_id']) for w in (left, right)]
                raise LineageError('conflict', 'incompatible claims: ' +
                                   '; '.join(a + '/' + u for a, u in identities))


def _configuration(parents, sources, op, language, change, ctx, compile_source):
    first = parents[0]
    record = {k: deepcopy(first[k]) for k in ('schema', 'workflow', 'language',
                                               'allowed_seats', 'references', 'skills')}
    overlays = sorted({overlay for source in sources for overlay in source['overlays']})
    overrides = _overrides(parents)
    if op == 'cross':
        other = parents[1]
        if first['workflow'] != other['workflow']:
            raise LineageError('bad_args', 'incompatible workflows')
        a, b = first['language'], other['language']
        if a != b and 'general' not in (a, b):
            raise LineageError('bad_args', 'incompatible languages')
        record['language'] = b if a == 'general' else a
        seats = {tuple(seat[k] for k in ('model', 'effort', 'mode'))
                 for seat in first['allowed_seats']}
        seats &= {tuple(seat[k] for k in ('model', 'effort', 'mode'))
                  for seat in other['allowed_seats']}
        if not seats:
            raise LineageError('bad_args', 'no shared complete seat')
        record['allowed_seats'] = [dict(zip(('model', 'effort', 'mode'), seat)) for seat in sorted(seats)]
        skills = {}
        for parent in parents:
            for pin in parent['skills']:
                sid = pin['skill_id']
                if sid in skills and skills[sid] != pin:
                    raise LineageError('conflict', 'competing pinned skill hashes')
                skills[sid] = deepcopy(pin)
        record['skills'] = list(skills.values())
        if sorted(first['references'], key=lambda p: p['id']) != sorted(other['references'], key=lambda p: p['id']):
            raise LineageError('hash_mismatch', 'founding reference pins differ')
    elif op == 'specialize':
        _text(language, 64)
        record['language'] = language
    elif op == 'mutate':
        from .mutate import _change
        record, overrides = _change(record, sources[0], change, overrides, ctx)
    else:
        raise LineageError('bad_args', 'unknown birth operation')
    record['skills'] = sorted(record['skills'], key=lambda p: (p['skill_id'], p['sha256']))
    record['references'] = sorted(record['references'], key=lambda p: p['id'])
    if overrides:
        record['rule_overrides'] = dict(sorted(overrides.items()))
    source = compile_source(record, overlays)
    if op == 'mutate':
        from .mutate import _exact_difference
        _exact_difference(sources[0], source, change)
    return record, source


def _birth_payload(history, *, parent_ids, child_id, op, display_name, event_id,
                   ctx, language=None, change=None):
    agents._target(child_id)
    if not history:
        raise LineageError('no_agent', 'committed parent does not exist')
    parents, sources, units = [], [], {}
    compiled = {}

    def compile_source(record, overlays):
        # Memoization lives only within this one locked reconstruction. The
        # independent shared-validator reconstruction gets a fresh cache.
        inputs = {k: deepcopy(record[k]) for k in ('workflow', 'language', 'references', 'skills')}
        inputs['rule_overrides'] = record.get('rule_overrides', {})
        inputs['overlays'] = list(overlays)
        key = journal.canonical_bytes(inputs)
        if key not in compiled:
            compiled[key] = _compile(record, overlays, ctx=ctx)
        return deepcopy(compiled[key])

    for parent_id in parent_ids:
        parent, source, owned = _parent(history, parent_id, child_id, ctx)
        _text(parent['display_name'], 128)
        _text(parent['language'], 64)
        # Immutable source hashes alone do not prove its normative text.
        expected = compile_source(parent, source['overlays'])
        if expected != source:
            raise LineageError('hash_mismatch', 'parent constitution differs from verified compilation')
        parents.append(parent)
        sources.append(source)
        units[parent_id] = owned
    record, constitution = _configuration(parents, sources, op, language, change, ctx, compile_source)
    try:
        agents._verify_immutable(record, ctx=ctx, history=history)
    except LineageError as exc:
        if exc.code in ('bad_args', 'hash_mismatch'):
            raise LineageError('hash_mismatch', 'child immutable inputs unavailable') from None
        raise
    selection = inherit.select(parents, units, workflow=record['workflow'],
                               language=record['language'], selected_ids=None, ctx=ctx)
    if len(selection.inherited) > 256:
        raise LineageError('memory_debt', 'inherited unit capacity exceeded; cuts required')
    if len(selection.rejected) > 10000:
        raise LineageError('conflict', 'rejected audit capacity exceeded')
    wrappers = inherit._adopt(selection, child_id)
    record.update(agent_id=child_id,
                  display_name=parents[0]['display_name'] if display_name is None else display_name,
                  memory_gen=len(wrappers), generation=max(p['generation'] for p in parents) + 1,
                  parents=list(parent_ids), born={'op': op, 'event_id': event_id}, status='draft',
                  constitution_sha256=sha256(constitution['text'].encode('utf-8')).hexdigest())
    _text(record['display_name'], 128)
    record['agent_version'] = agent_version(record['constitution_sha256'], record['skills'], record['memory_gen'])
    adopted = [wrapper['unit'] for wrapper in wrappers]
    entry.build(record, adopted, token_count=None, max_bytes=6000)
    _claims(selection.inherited)
    raw = brief.build(record, adopted, memory_arm='own', rule_ids=constitution['rule_ids'])
    brief._bounded(raw)
    record['brief_head_sha256'] = sha256(raw).hexdigest()
    _shape_agent(record)
    result = {'record': record, 'constitution': constitution, 'inherited_units': wrappers,
              'rejected_units': list(deepcopy(selection.rejected))}
    journal.canonical_bytes(result)
    return result


def _request_witness(event, record, change):
    """Bind independently reconstructed facts to the journal's original request.

    The installed journal hashes the pre-prepare request envelope. Reconstruct
    both permitted display-name spellings; omitted defaults remain distinct in
    replay identity. No operation identity is rewritten.
    """
    op = record['born']['op']
    args = {'agent': event['agent'], 'child_id': record['agent_id']}
    if op == 'cross':
        args['parent_ids'] = record['parents']
    else:
        args['parent_id'] = record['parents'][0]
    if op == 'mutate':
        args['change'] = change
    elif op == 'specialize':
        args['language'] = record['language']
    for named in (False, True):
        candidate = deepcopy(args)
        if named:
            candidate['display_name'] = record['display_name']
        request = {key: deepcopy(event[key]) for key in
                   ('ledger', 'agent', 'op_id', 'kind', 'evidence')}
        request['payload'] = {'tool': 'agent_' + op, 'args': candidate}
        if sha256(journal.canonical_bytes(request)).hexdigest() == event['request_sha256']:
            return named
    raise LineageError('not_inheritable', 'birth differs from original request')


def validate_birth(history, event, *, ctx):
    """Independently reconstruct the complete candidate from its locked prefix."""
    payload = event.get('payload')
    if type(payload) is not dict or set(payload) != {'record', 'constitution', 'inherited_units', 'rejected_units'}:
        raise LineageError('bad_args', 'invalid birth payload')
    record = payload['record']
    _shape_agent(record)
    op = record['born']['op']
    parents = record['parents']
    if (op not in ('cross', 'mutate', 'specialize')
            or len(parents) != (2 if op == 'cross' else 1) or len(set(parents)) != len(parents)):
        raise LineageError('bad_args', 'invalid birth parent membership')
    change = None
    if op == 'mutate':
        from .mutate import _infer_change
        parent, source, _ = _parent(history, parents[0], record['agent_id'], ctx)
        change = _infer_change(parent, source, record, payload['constitution'])
    named = _request_witness(event, record, change)
    expected = _birth_payload(history, parent_ids=parents, child_id=record['agent_id'], op=op,
                              display_name=record['display_name'] if named else None, event_id=event['id'], ctx=ctx,
                              language=record['language'], change=change)
    if journal.canonical_bytes(payload) != journal.canonical_bytes(expected):
        raise LineageError('not_inheritable', 'birth differs from authoritative admission')


def _refresh(agent_id, *, ctx):
    """Retry publication only when a concurrent durable append proves staleness."""
    for attempt in range(3):
        before = journal.snapshot(agents._home(ctx))
        try:
            return agents.refresh_projections(agent_id, ctx=ctx)
        except LineageError as exc:
            if (exc.code != 'internal' or attempt == 2
                    or journal.snapshot(agents._home(ctx)) == before):
                raise


def _transact(command, prepare, ctx):
    request = {'tool': command.tool, 'args': {k: deepcopy(v) for k, v in command.args.items()
                                           if k not in ('op_id', 'expected_head')}}

    admission_started = []

    def prepared(history, draft):
        admission_started.append(True)
        head = history[-1]['lamport'] if history else 0
        if command.expected_head is not None and command.expected_head != head:
            raise LineageError('stale_rev', 'expected head differs')
        if head >= _SAFE:
            raise LineageError('conflict', 'journal capacity exceeded')
        return prepare(history, draft)

    def validated(history, event):
        validators = ctx.services.registry.validators if hasattr(ctx, 'services') else ctx.validators
        owner = validators.get('agent.born')
        if not callable(owner):
            raise LineageError('internal', 'shared birth validator unavailable')
        # Call the unique owner, which delegates to the pure admission adapter.
        owner(history, event, ctx=ctx)
        _render(event)

    try:
        services = getattr(ctx, 'services', None)
        event = journal.transact(agents._home(ctx), agent=command.agent, op_id=command.op_id,
                                 kind='agent.born', payload=request, validators={'agent.born': validated},
                                 prepare=prepared, clock=getattr(services, 'clock', None),
                                 id_factory=getattr(services, 'id_factory', None))
        result = _render(event)
        _refresh(event['payload']['record']['agent_id'], ctx=ctx)
        return Committed(deepcopy(event), deepcopy(result), event['lamport'], event['sha256'])
    except LineageError as exc:
        # Only locally constructed source identities may appear in diagnostics.
        detail = 'breeding operation refused'
        if exc.code == 'memory_debt':
            detail = 'memory capacity insufficient; cuts required'
        if exc.code == 'conflict' and type(exc.detail) is str and exc.detail.startswith('incompatible claims: '):
            detail = exc.detail
        code = 'internal' if exc.code == 'bad_args' and not admission_started else exc.code
        raise LineageError(code, detail) from None
    except Exception:
        raise LineageError('internal', 'breeding service unavailable') from None


def _render(event):
    payload = event['payload']
    result = {k: deepcopy(payload[k]) for k in ('record', 'inherited_units', 'rejected_units')}
    result['commit'] = {'event_ids': [event['id']], 'head': event['lamport'], 'sha256': event['sha256']}
    journal.canonical_bytes(result)
    return result


def cross(parent_ids: Sequence[str], child_id: str, *, display_name: str | None = None,
          command, ctx):
    if not isinstance(parent_ids, Sequence) or isinstance(parent_ids, (str, bytes, bytearray)):
        raise LineageError('bad_args', 'invalid parent collection')
    data = {'parent_ids': list(parent_ids), 'child_id': child_id}
    if display_name is not None:
        data['display_name'] = display_name
    effective = _command('agent_cross', data, command)

    def prepare(history, draft):
        return _birth_payload(history, parent_ids=data['parent_ids'], child_id=child_id, op='cross',
                              display_name=display_name, event_id=draft['id'], ctx=ctx)

    return _transact(effective, prepare, ctx)


def _install_admission():
    """Extend U12's existing delegation seam without a second registry owner.

    U17 predates the three operators. Preserve its admission implementation for
    clone/distill; route only the new closed birth operators to their helpers.
    No home, caller authority or mutable event is captured by this adapter.
    """
    from lineage.domain import breeding
    original = breeding.validate_birth
    if getattr(original, '_u18_adapter', False):
        return

    def admission(history, event, *, ctx):
        op = event.get('payload', {}).get('record', {}).get('born', {}).get('op')
        if op in ('cross', 'mutate', 'specialize'):
            return validate_birth(history, event, ctx=ctx)
        return original(history, event, ctx=ctx)

    admission._u18_adapter = True
    breeding.validate_birth = admission


_install_admission()
