"""Stdlib prune_ax_v1: document order, opaque articles and serialized-name bound.

Only roles, names and ARIA states participate in completion hashes. CDP node
handles are retained for actuation, never included in those hashes.
"""
from __future__ import annotations
import hashlib
import re
import unicodedata

MAX_NAME_BYTES = 64
CHASSIS_ROLES = frozenset((
    "RootWebArea", "main", "navigation", "banner", "contentinfo", "complementary",
    "region", "search", "form", "dialog", "alertdialog", "toolbar", "menu",
    "menubar", "menuitem", "menuitemcheckbox", "menuitemradio", "tablist", "tab",
    "tabpanel", "heading", "button", "link", "textbox", "searchbox", "combobox",
    "listbox", "option", "checkbox", "radio", "switch", "slider", "spinbutton",
    "status", "alert", "log", "progressbar", "timer", "marquee", "article",
    "note", "group", "application",
))
OPAQUE_ROLES = frozenset(("article",))
STATE_ATTRS = ("busy", "checked", "current", "disabled", "expanded", "hidden",
               "pressed", "selected")
ACTIONABLE_ROLES = frozenset((
    "button", "link", "textbox", "searchbox", "combobox", "listbox", "option",
    "checkbox", "radio", "switch", "slider", "spinbutton", "menuitem",
    "menuitemcheckbox", "menuitemradio", "tab",
))


def normalize_name(raw):
    if not raw:
        return ""
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(raw))).strip()
    text = text.replace("\\", "\\\\").replace("|", "\\|")
    if len(text.encode("utf-8")) > MAX_NAME_BYTES:
        text = text.encode("utf-8")[:MAX_NAME_BYTES].decode("utf-8", "ignore")
        if (len(text) - len(text.rstrip("\\"))) % 2:
            text = text[:-1]
    return text


def _value(value):
    if not isinstance(value, dict):
        return ""
    item = value.get("value")
    if isinstance(item, bool):
        return "true" if item else "false"
    return "" if item is None else str(item)


def prune(raw_nodes):
    """Emit the same role/name/state/depth projection as prune_ax_v1."""
    by_id = {n.get("nodeId"): n for n in raw_nodes if n.get("nodeId") is not None}
    children = {c for n in raw_nodes for c in (n.get("childIds") or [])}
    roots = [n for n in raw_nodes if n.get("nodeId") not in children] or raw_nodes[:1]
    output, seen = [], set()
    for root in roots:
        stack = [(root, 0, ())]
        while stack:
            node, depth, ancestors = stack.pop()
            node_id = node.get("nodeId")
            if node_id in seen:
                continue
            seen.add(node_id)
            role = _value(node.get("role"))
            if not node.get("ignored") and role in CHASSIS_ROLES:
                props = {p.get("name"): _value(p.get("value"))
                         for p in (node.get("properties") or [])}
                output.append(dict(role=role, name=normalize_name(_value(node.get("name"))),
                                   attrs=tuple((k, props[k]) for k in STATE_ATTRS if k in props),
                                   depth=depth, ancestors=ancestors, node_id=node_id,
                                   backend_id=node.get("backendDOMNodeId")))
                if role in OPAQUE_ROLES:
                    continue
                depth += 1
                ancestors += (role,)
            for child in reversed(node.get("childIds") or []):
                if child in by_id:
                    stack.append((by_id[child], depth, ancestors))
    counts = {}
    for node in output:
        key = (node['role'], node['name'])
        node['ordinal'] = counts.get(key, 0)
        counts[key] = node['ordinal'] + 1
    for node in output:
        node['cardinality'] = counts[(node['role'], node['name'])]
    return output


prune_ax_v1 = prune


def canonical_tree(nodes, *, with_state=True):
    return "\n".join("%d|%s|%s|%s" % (
        n['depth'], n['role'], n['name'],
        ",".join("%s=%s" % item for item in n['attrs']) if with_state else ""
    ) for n in nodes) + "\n"


def tree_hash(nodes):
    return hashlib.sha256(canonical_tree(nodes).encode('utf-8')).hexdigest()


def violations(nodes, ready_name):
    """Checks consume the pruned projection only, never DOM selectors."""
    failures = []
    pairs = {(n['role'], n['name']) for n in nodes}
    if not nodes:
        return ['empty_tree']
    if ('status', ready_name) not in pairs:
        failures.append('missing_ready_status')
    seen = set()
    for n in nodes:
        if n['role'] == 'progressbar':
            failures.append('progress_after_ready')
        if n['role'] not in ACTIONABLE_ROLES:
            continue
        key = (n['role'], n['name'])
        if key in seen:
            failures.append('duplicate_action:' + repr(key))
        seen.add(key)
        if not n['name'] or n['name'].isdecimal() or len(n['name'].encode('utf-8')) > MAX_NAME_BYTES:
            failures.append('invalid_action_name')
    if not any(n['role'] == 'link' and dict(n['attrs']).get('current') == 'page' for n in nodes):
        failures.append('missing_current_navigation')
    for role in ('banner', 'navigation', 'main', 'contentinfo'):
        if not any(n['role'] == role for n in nodes):
            failures.append('missing_landmark:' + role)
    if not any(n['role'] == 'main' and n['name'] for n in nodes):
        failures.append('unnamed_screen')
    return failures
