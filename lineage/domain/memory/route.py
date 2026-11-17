"""Read-only lexical recall over one verified committed snapshot."""
from copy import deepcopy
import re

from lineage.core.errors import LineageError
from . import entry, fold, store


def route(agent_id, query, *, limit=10, ctx):
    store._identity(agent_id)
    if type(query) is not str or not 1 <= len(query) <= 512:
        raise LineageError('bad_args', 'query must contain between 1 and 512 characters')
    try:
        query.encode('utf-8', errors='strict')
    except UnicodeError:
        raise LineageError('bad_args', 'query must be valid UTF-8') from None
    if type(limit) is not int or not 1 <= limit <= 50:
        raise LineageError('bad_args', 'invalid memory result limit')
    snapshot = store._snapshot(ctx)
    agent = store._snapshot_agent(agent_id, snapshot)
    try:
        units = fold.units_for(snapshot.state, agent_id)
        terms = set(re.findall(r'\w+', query.casefold()))
        ranked = []
        for unit in units:
            if not entry.eligible(agent, unit):
                continue
            score = len(terms & set(re.findall(r'\w+', unit['statement'].casefold())))
            if score:
                ranked.append((-score, unit['id'], unit))
        selected = [deepcopy(unit) for _, _, unit in sorted(ranked, key=lambda item: item[:2])[:limit]]
        return {'units': selected,
                'answer': selected[0]['statement'] if selected else 'NOT IN MEMORY',
                'head': snapshot.head}
    except LineageError:
        raise
    except Exception:
        raise LineageError('internal', 'authoritative memory unavailable') from None
