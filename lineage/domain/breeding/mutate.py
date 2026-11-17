"""Single pinned-skill replacement or verified rule-inclusion mutation."""
from __future__ import annotations

from copy import deepcopy

from lineage.core import journal
from lineage.core.errors import LineageError
from .cross import _birth_payload, _command, _protected, _rule, _transact


def _change(record, source, change, overrides, ctx):
    record = deepcopy(record)
    overrides = deepcopy(overrides)
    if change['kind'] == 'skill':
        pins = record['skills']
        found = [p for p in pins if p['skill_id'] == change['skill_id']]
        if len(found) != 1:
            raise LineageError('bad_args', 'source skill identity is not present')
        old = found[0]
        if old['sha256'] != change['from_sha256']:
            raise LineageError('hash_mismatch', 'source skill hash differs')
        target = change['to']
        if old == target:
            raise LineageError('bad_args', 'identical skill replacement')
        remaining = [p for p in pins if p['skill_id'] != old['skill_id']]
        if any(p['skill_id'] == target['skill_id'] for p in remaining):
            raise LineageError('conflict', 'replacement skill identity collision')
        record['skills'] = remaining + [deepcopy(target)]
    else:
        rule_id, action = change['rule_id'], change['text']
        _rule(rule_id)
        if _protected(rule_id):
            raise LineageError('bad_args', 'authority rule cannot be mutated')
        if action not in ('add', 'remove'):
            raise LineageError('bad_args', 'rule action must be add or remove')
        if (rule_id in source['rule_ids']) == (action == 'add'):
            raise LineageError('bad_args', 'rule action has no effective change')
        overrides[rule_id] = action
    return record, overrides


def _exact_difference(before, after, change):
    a, b = set(before['rule_ids']), set(after['rule_ids'])
    if change['kind'] == 'skill':
        if before != after:
            raise LineageError('bad_args', 'skill replacement changes normative rules')
    else:
        rule = change['rule_id']
        removed, added = (set(), {rule}) if change['text'] == 'add' else ({rule}, set())
        if a - b != removed or b - a != added:
            raise LineageError('bad_args', 'mutation must change exactly one effective rule')
        # Unchanged bullets and compilation headers must remain byte-identical.
        def without(source):
            return [line for line in source['text'].splitlines()
                    if not line.startswith('- ' + rule + ': ')]
        if without(before) != without(after):
            raise LineageError('bad_args', 'mutation changes additional normative text')


def _infer_change(parent, source, child, constitution):
    old = {p['skill_id']: p for p in parent['skills']}
    new = {p['skill_id']: p for p in child['skills']}
    removed = [p for k, p in old.items() if new.get(k) != p]
    added = [p for k, p in new.items() if old.get(k) != p]
    before = parent.get('rule_overrides', {})
    after = child.get('rule_overrides', {})
    changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
    if len(removed) == len(added) == 1 and not changed:
        return {'kind': 'skill', 'skill_id': removed[0]['skill_id'],
                'from_sha256': removed[0]['sha256'], 'to': deepcopy(added[0])}
    if not removed and not added and len(changed) == 1 and changed[0] in after:
        key = changed[0]
        return {'kind': 'rule', 'rule_id': key, 'text': after[key]}
    raise LineageError('bad_args', 'mutation must contain exactly one configuration change')


def mutate(parent_id: str, child_id: str, change: dict, *,
           display_name: str | None = None, command, ctx):
    data = {'parent_id': parent_id, 'child_id': child_id, 'change': deepcopy(change)}
    if display_name is not None:
        data['display_name'] = display_name
    effective = _command('agent_mutate', data, command)

    def prepare(history, draft):
        return _birth_payload(history, parent_ids=[parent_id], child_id=child_id, op='mutate',
                              display_name=display_name, change=data['change'],
                              event_id=draft['id'], ctx=ctx)

    return _transact(effective, prepare, ctx)
