"""Context-only clone preserving the parent's captured version inputs."""
from __future__ import annotations

from . import _birth_payload, _command, _transact
from lineage.domain import agents


def clone(parent_id: str, child_id: str, *, display_name: str | None = None,
          command, ctx):
    data = {'parent_id': parent_id, 'child_id': child_id}
    if display_name is not None:
        data['display_name'] = display_name
    effective = _command('agent_clone', data, command)
    agents._target(child_id)

    def prepare(history, draft):
        return _birth_payload(history, parent_id=parent_id, child_id=child_id,
                              op='clone', display_name=display_name, selected_ids=None,
                              event_id=draft['id'], ctx=ctx)

    return _transact(effective, 'agent.born', prepare, ctx)
