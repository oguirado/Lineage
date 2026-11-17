"""Pure, bounded rendering of passive memory records.

Trusted Services construction supplies tokenizer provenance. Missing or invalid
counters refuse admission; byte capacity never substitutes for token capacity.
"""
from __future__ import annotations

from lineage.core.errors import LineageError
from lineage.core.journal import canonical_bytes


def eligible(agent, unit):
    """Apply recall scope to units already attributed by the memory fold."""
    scope = unit.get('scope', {})
    return (unit.get('status') == 'active'
            and unit.get('privacy') in {'public', 'internal'}
            and scope.get('workflow') == agent['workflow']
            and scope.get('language') in {agent['language'], 'general'})


def _render(agent, units):
    fields = ('agent_id', 'workflow', 'language', 'agent_version', 'memory_gen')
    header = '# Agent memory\n\n' + ''.join(
        key + ': ' + canonical_bytes(agent[key]).decode('utf-8') + '\n'
        for key in fields)
    records = ''.join('\n<!-- untrusted_content -->\n```json\n'
                      + canonical_bytes(unit).decode('utf-8')
                      + '\n```\n<!-- /untrusted_content -->\n' for unit in units)
    return (header + records).encode('utf-8')


def _overflow(budget, units):
    # Report candidates, never silently apply a lossy reduction. Largest records
    # are first, with a lexical tie break independent of caller iteration order.
    ordered = sorted(units, key=lambda u: (-len(canonical_bytes(u)), u['id']))
    detail = budget + ' capacity exceeded; cuts candidates: '
    suffix = ' [cut list bounded; remaining ids omitted]'
    for index, unit in enumerate(ordered):
        addition = (', ' if index else '') + unit['id']
        if len(detail) + len(addition) + len(suffix) > 2048:
            detail += suffix
            break
        detail += addition
    if not ordered:
        detail += '(entry header alone exceeds capacity)'
    raise LineageError('memory_debt', detail)


def build(agent, units, *, token_count, max_bytes=6000, max_tokens=4000):
    """Render all eligible units or refuse; input containers are never changed.

    Header fields appear in the order in ``_render``. Each canonical, single-line
    unit has its own fenced passive-data block. UTF-8 and the final LF count
    toward both independent budgets. Custom limits can only reduce ceilings.
    """
    for name, value in (('max_bytes', max_bytes), ('max_tokens', max_tokens)):
        if type(value) is not int or value <= 0:
            raise LineageError('bad_args', 'invalid entry limit: ' + name)
    max_bytes, max_tokens = min(max_bytes, 6000), min(max_tokens, 4000)
    try:
        selected = sorted((unit for unit in units if eligible(agent, unit)),
                          key=lambda unit: unit['id'])
        if len({unit['id'] for unit in selected}) != len(selected):
            raise LineageError('bad_args', 'duplicate memory unit id')
        raw = _render(agent, selected)
    except (KeyError, TypeError, UnicodeError, ValueError):
        raise LineageError('bad_args', 'invalid entry input') from None
    if len(raw) > max_bytes:
        _overflow('byte', selected)
    if token_count is None and len(raw) <= max_tokens:
        # A-TOK1: byte-level BPE tokenizers (o200k_base, Claude BPE) emit tokens
        # that each cover at least one UTF-8 byte, so tokens <= bytes. An entry
        # within max_tokens bytes provably meets the token ceiling: a proven
        # bound, not an estimate. Larger entries still require a verified counter.
        pass
    elif not callable(token_count):
        raise LineageError('memory_debt', 'token counter unavailable or invalid; cuts unavailable')
    else:
        try:
            count = token_count(raw.decode('utf-8'))
            if type(count) is not int or count < 0:
                raise ValueError
        except Exception:
            raise LineageError('memory_debt', 'token counter unavailable or invalid; cuts unavailable') from None
        if count > max_tokens:
            _overflow('token', selected)
    return raw
