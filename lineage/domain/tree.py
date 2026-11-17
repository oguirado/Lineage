"""Deterministic structured ancestry reconstructed from committed history."""
from __future__ import annotations

from collections import deque
from copy import deepcopy

from lineage.core import journal
from lineage.core.errors import LineageError
from lineage.domain import agents
from lineage.domain.version import _AGENT, _SAFE, _match

_OPS = frozenset(('genesis', 'clone', 'distill', 'cross', 'mutate', 'specialize'))
_STATUSES = frozenset(('draft', 'shadow', 'promoted', 'retired'))


class TreeFold:
    """Own only the tree namespace; lifecycle authority remains with agents."""
    order = 80
    kinds = frozenset(('agent.born', 'agent.status'))

    def __call__(self, state, event):
        if event['kind'] not in self.kinds:
            return
        nodes = state.setdefault('tree', {})
        payload = event['payload']
        if event['kind'] == 'agent.born':
            record = payload['record']
            agent_id = record['agent_id']
            if agent_id in nodes:
                raise LineageError('internal', 'duplicate committed lineage identity')
            nodes[agent_id] = {'agent_id': agent_id, 'parents': deepcopy(record['parents']),
                               'generation': record['generation'], 'op': record['born']['op'],
                               'status': record['status']}
        else:
            agent_id = payload['agent_id']
            if agent_id not in nodes:
                raise LineageError('internal', 'lifecycle event has no lineage identity')
            nodes[agent_id]['status'] = payload['to']


def _graph(nodes):
    if type(nodes) is not dict or len(nodes) > 1000000:
        raise LineageError('internal', 'lineage node capacity exceeded')
    children = {agent_id: [] for agent_id in nodes}
    pending = {}
    try:
        for agent_id, node in nodes.items():
            _match(agent_id, _AGENT)
            if (agent_id in ('operator', 'system') or type(node) is not dict
                    or set(node) != {'agent_id', 'parents', 'generation', 'op', 'status'}
                    or node['agent_id'] != agent_id or type(node['parents']) is not list
                    or len(node['parents']) > 2 or type(node['generation']) is not int
                    or not 0 <= node['generation'] <= _SAFE
                    or node['op'] not in _OPS or node['status'] not in _STATUSES):
                raise ValueError
            parents = node['parents']
            for parent in parents:
                _match(parent, _AGENT)
            if len(set(parents)) != len(parents) or agent_id in parents:
                raise ValueError
            expected_count = 0 if node['op'] == 'genesis' else 2 if node['op'] == 'cross' else 1
            if len(parents) != expected_count:
                raise ValueError
            for parent in parents:
                if parent not in nodes:
                    raise ValueError
                children[parent].append(agent_id)
            pending[agent_id] = len(parents)
        ready = deque(sorted(key for key in nodes if not pending[key]))
        visited = 0
        while ready:
            agent_id = ready.popleft()
            node = nodes[agent_id]
            expected = max((nodes[key]['generation'] for key in node['parents']), default=-1) + 1
            if node['generation'] != expected:
                raise ValueError
            visited += 1
            for child in children[agent_id]:
                pending[child] -= 1
                if pending[child] == 0:
                    ready.append(child)
        if visited != len(nodes):
            raise ValueError
    except (KeyError, TypeError, ValueError, LineageError):
        raise LineageError('internal', 'committed lineage graph is inconsistent') from None
    return children


def tree(*, root_id: str | None = None, include_retired: bool = True, ctx) -> dict:
    if root_id is not None:
        _match(root_id, _AGENT)
    if type(include_retired) is not bool:
        raise LineageError('bad_args', 'invalid retirement filter')
    try:
        home = agents._home(ctx)
        if not home.is_dir():
            raise LineageError('internal', 'authoritative runtime home unavailable')
        history = journal.snapshot(home)
        state = agents._state(history, ctx)
        nodes = deepcopy(state.get('tree', {}))
        if type(nodes) is not dict or len(nodes) != sum(event['kind'] == 'agent.born' for event in history):
            raise LineageError('internal', 'authoritative tree fold is incomplete')
        # Consult the owning effective lifecycle fold, including automatic
        # retirement if that owner implements it. Never invent a status event.
        for agent_id, node in nodes.items():
            node['status'] = agents._record(state, agent_id)['status']
        children = _graph(nodes)
        if root_id is None:
            chosen = set(nodes)
        else:
            if root_id not in nodes:
                raise LineageError('no_agent', 'lineage root does not exist')
            chosen, pending = set(), [root_id]
            while pending:
                key = pending.pop()
                if key not in chosen:
                    chosen.add(key)
                    pending.extend(children[key])
        result = [node for key, node in nodes.items() if key in chosen
                  and (include_retired or node['status'] != 'retired')]
        result.sort(key=lambda node: (node['generation'], node['agent_id']))
        head = history[-1]['lamport'] if history else 0
        if type(head) is not int or not 0 <= head <= _SAFE:
            raise LineageError('internal', 'lineage prefix is invalid')
        return {'nodes': result, 'head': head}
    except LineageError as exc:
        if exc.code in ('no_agent', 'hash_mismatch', 'busy'):
            raise LineageError(exc.code, 'authoritative lineage read refused') from None
        raise LineageError('internal', 'authoritative lineage unavailable') from None
    except Exception:
        raise LineageError('internal', 'authoritative lineage unavailable') from None
