"""Language specialization delegates eligibility to the shared selector."""
from __future__ import annotations

from .cross import _birth_payload, _command, _transact


def specialize(parent_id: str, child_id: str, language: str, *,
               display_name: str | None = None, command, ctx):
    data = {'parent_id': parent_id, 'child_id': child_id, 'language': language}
    if display_name is not None:
        data['display_name'] = display_name
    effective = _command('agent_specialize', data, command)

    def prepare(history, draft):
        return _birth_payload(history, parent_ids=[parent_id], child_id=child_id, op='specialize',
                              display_name=display_name, language=language,
                              event_id=draft['id'], ctx=ctx)

    return _transact(effective, prepare, ctx)
