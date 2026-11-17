"""Deterministic passive agent context, independent of runtime projections."""
from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256

from lineage.core.errors import LineageError
from .version import _AGENT, _canonical, _inputs, _match


def _eligible(agent, unit, memory_arm):
    scope = unit.get('scope', {})
    return (memory_arm != 'none' and unit.get('status') == 'active'
            and type(unit.get('level')) is int and unit['level'] in (1, 2)
            and unit.get('privacy') in ('public', 'internal')
            and unit.get('kind') in ('ruling', 'lesson', 'negative', 'workflow')
            and scope.get('workflow') == agent['workflow']
            and scope.get('language') in (agent['language'], 'general')
            and (memory_arm == 'inherited'
                 or 'inherited_from' not in unit.get('provenance', {})))


def _bounded(raw):
    if type(raw) is not bytes:
        raise LineageError('internal', 'brief bytes unavailable')
    try:
        text = raw.decode('utf-8')
    except UnicodeError:
        raise LineageError('internal', 'brief encoding invalid') from None
    if len(text) > 65536:
        raise LineageError('internal', 'brief exceeds result capacity')
    return text


def build(agent: dict, units: Sequence[dict], *, rule_ids: Sequence[str],
          memory_arm: str = 'own') -> bytes:
    """Render the frozen line template using explicit verified citation ids."""
    if type(memory_arm) is not str or memory_arm not in ('none', 'own', 'inherited'):
        raise LineageError('bad_args', 'invalid memory arm')
    if (not isinstance(rule_ids, Sequence) or isinstance(rule_ids, (str, bytes, bytearray))
            or any(type(rule) is not str or not rule or any(c in rule for c in '\n\r\x00')
                   for rule in rule_ids)):
        raise LineageError('bad_args', 'invalid rule ids')
    if not isinstance(units, Sequence) or isinstance(units, (str, bytes, bytearray)):
        raise LineageError('bad_args', 'invalid memory units')
    try:
        _match(agent['agent_id'], _AGENT)
        inputs = _inputs(agent['constitution_sha256'], agent['skills'], agent['memory_gen'])
        def text(value):
            return _canonical(value).decode('utf-8')
        selected = sorted((unit for unit in units if _eligible(agent, unit, memory_arm)),
                          key=lambda unit: (unit['kind'], unit['id']))
        if len({unit['id'] for unit in selected}) != len(selected):
            raise LineageError('bad_args', 'duplicate memory unit')
        lines = ['# Agent brief', '## Identity',
                 'agent_id: ' + text(agent['agent_id']),
                 'workflow: ' + text(agent['workflow']),
                 'language: ' + text(agent['language']),
                 'version_inputs: ' + text(inputs), '## Constitution',
                 'sha256: ' + agent['constitution_sha256'], 'rule_ids:']
        lines += ['- ' + text(rule) for rule in sorted(set(rule_ids))] or ['(none)']
        lines += ['## Skills']
        lines += ['- ' + text(pin) for pin in inputs['skills']] or ['(none)']
        lines += ['## Memory']
        lines += ['- ' + text(unit) for unit in selected] or ['(none)']
        raw = ('\n'.join(lines) + '\n').encode('utf-8')
    except (KeyError, TypeError, AttributeError, ValueError, UnicodeError):
        raise LineageError('bad_args', 'invalid brief input') from None
    _bounded(raw)
    return raw


def get(agent_id: str, *, memory_arm: str = 'own', ctx) -> dict:
    """Query one verified prefix; mutable brief files are never consulted."""
    from . import agents
    agents._target(agent_id)
    if type(memory_arm) is not str or memory_arm not in ('none', 'own', 'inherited'):
        raise LineageError('bad_args', 'invalid memory arm')
    history = agents._history(ctx)
    state = agents._state(history, ctx)
    record = agents._record(state, agent_id)
    source = agents._source(state, agent_id)
    agents._verify_immutable(record, ctx=ctx)
    agents._constitution_integrity(record, source)
    raw = build(record, agents._units(state, agent_id),
                rule_ids=source['rule_ids'], memory_arm=memory_arm)
    return {'agent_id': agent_id, 'agent_version': record['agent_version'],
            'text': _bounded(raw), 'sha256': sha256(raw).hexdigest(),
            'memory_gen': record['memory_gen']}
