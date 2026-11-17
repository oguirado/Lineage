"""Deterministic selection without paraphrasing, and immutable retirement."""
from __future__ import annotations

from collections.abc import Sequence

from lineage.core.errors import LineageError
from lineage.domain import agents
from . import _birth_payload, _command, _retirement_payload, _transact


def distill(parent_id: str, child_id: str, *, display_name: str | None = None,
            unit_ids: Sequence[str] | None = None, command, ctx):
    data = {'parent_id': parent_id, 'child_id': child_id}
    if display_name is not None:
        data['display_name'] = display_name
    if unit_ids is not None:
        if not isinstance(unit_ids, Sequence) or isinstance(unit_ids, (str, bytes, bytearray)):
            raise LineageError('bad_args', 'invalid selected unit collection')
        data['unit_ids'] = list(unit_ids)
    effective = _command('agent_distill', data, command)
    agents._target(child_id)
    selected = data.get('unit_ids')

    def prepare(history, draft):
        return _birth_payload(history, parent_id=parent_id, child_id=child_id,
                              op='distill', display_name=display_name, selected_ids=selected,
                              event_id=draft['id'], ctx=ctx)

    return _transact(effective, 'agent.born', prepare, ctx)


def retire(agent_id: str, reason: str, *, command, ctx):
    effective = _command('agent_retire', {'agent_id': agent_id, 'reason': reason}, command)
    agents._target(agent_id)

    def prepare(history, draft):
        return _retirement_payload(history, agent_id, reason, ctx)

    return _transact(effective, 'agent.status', prepare, ctx)
