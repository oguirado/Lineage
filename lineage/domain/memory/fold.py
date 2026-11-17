"""Deterministic authoritative memory projection, without artifact I/O."""
from copy import deepcopy

_BRIEF_KINDS = frozenset({'ruling', 'lesson', 'negative', 'workflow'})


def empty():
    return {}


def _owner(state, agent_id):
    return state.setdefault('memory', {}).setdefault(agent_id, {
        'units': {}, 'originals': {}, 'memory_gen': 0})


def _brief(units):
    return {key: value for key, value in units.items()
            if value['status'] == 'active' and value['privacy'] != 'private'
            and value['kind'] in _BRIEF_KINDS}


def apply(state, event):
    kind = event['kind']
    if kind not in {'agent.born', 'memory.put', 'memory.retire'}:
        return
    payload = event['payload']
    if kind == 'agent.born':
        record = payload['record']
        target = _owner(state, record['agent_id'])
        for inherited in payload['inherited_units']:
            unit = deepcopy(inherited['unit'])
            target['units'][unit['id']] = unit
            target['originals'][unit['id']] = deepcopy(unit)
        target['memory_gen'] = record['memory_gen']
        return
    target = _owner(state, payload['agent_id'])
    before = deepcopy(_brief(target['units']))
    if kind == 'memory.put':
        unit = deepcopy(payload['unit'])
        target['units'][unit['id']] = unit
        target['originals'][unit['id']] = deepcopy(unit)
        for predecessor in unit['supersedes']:
            target['units'][predecessor].update(status='superseded', superseded_by=unit['id'])
    else:
        unit = target['units'][payload['unit_id']]
        if 'superseded_by' in payload:
            unit.update(status='superseded', superseded_by=payload['superseded_by'])
        else:
            unit['status'] = 'retired'
            unit.pop('superseded_by', None)
    if before != _brief(target['units']):
        target['memory_gen'] += 1


def units_for(state, agent_id, *, include_inactive=False, include_private=False):
    units = state.get('memory', {}).get(agent_id, {}).get('units', {})
    return tuple(deepcopy(value) for _, value in sorted(units.items())
                 if (include_inactive or value['status'] == 'active')
                 and (include_private or value['privacy'] != 'private'))
