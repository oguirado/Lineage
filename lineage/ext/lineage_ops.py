"""Frozen breeding tool descriptors over the installed shared dispatcher."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from lineage.core.errors import LineageError
from lineage.core.registry import ToolSpec
from lineage.domain.breeding import Command, _check
from lineage.domain.breeding.clone import clone
from lineage.domain.breeding.distill import distill, retire
from lineage.domain.tree import TreeFold, tree

_AGENT = {'type': 'string', 'minLength': 3, 'maxLength': 64,
          'pattern': r'^[a-z][a-z0-9-]{2,63}(?![\s\S])'}
_ID = {'type': 'string', 'minLength': 8, 'maxLength': 64,
       'pattern': r'^[A-Za-z0-9_-]{8,64}(?![\s\S])'}
_OP = {'type': 'string', 'minLength': 1, 'maxLength': 128,
       'pattern': r'^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\s\S])'}
_HEAD = {'type': 'integer', 'minimum': 0, 'maximum': 9007199254740991}


def _object(properties, required):
    return {'type': 'object', 'properties': deepcopy(properties),
            'required': list(required), 'additionalProperties': False}


_SHARED = {'agent': _AGENT, 'op_id': _OP, 'expected_head': _HEAD}
_BIRTH = {'parent_id': _AGENT, 'child_id': _AGENT,
          'display_name': {'type': 'string', 'minLength': 1, 'maxLength': 128}}
_SELECTION = {'type': 'array', 'items': _ID, 'minItems': 0, 'maxItems': 256, 'uniqueItems': True}
_SCHEMAS = {
    'agent_clone': _object({**_BIRTH, **_SHARED}, ('parent_id', 'child_id', 'agent', 'op_id')),
    'agent_distill': _object({**_BIRTH, 'unit_ids': _SELECTION, **_SHARED},
                             ('parent_id', 'child_id', 'agent', 'op_id')),
    'agent_retire': _object({'agent_id': _AGENT,
                             'reason': {'type': 'string', 'minLength': 1, 'maxLength': 2048},
                             **_SHARED}, ('agent_id', 'reason', 'agent', 'op_id')),
    'lineage_tree': _object({'root_id': _AGENT, 'include_retired': {'type': 'boolean'}, 'agent': _AGENT}, ()),
}


def _context(args, context):
    changes = {'actor': args.get('agent', 'system')}
    if hasattr(context, 'op_id'):
        changes['op_id'] = args.get('op_id')
    if hasattr(context, 'authority'):
        changes['authority'] = 'tool'
    try:
        return replace(context, **changes)
    except (TypeError, ValueError):
        raise LineageError('internal', 'breeding runtime context unavailable') from None


def _mutation(name, args, context):
    _check(name, args)
    effective = deepcopy(args)
    command = Command(name, effective, effective['agent'], effective['op_id'], effective.get('expected_head'))
    ctx = _context(effective, context)
    params = {key: value for key, value in effective.items() if key not in _SHARED}
    function = {'agent_clone': clone, 'agent_distill': distill, 'agent_retire': retire}[name]
    return function(**params, command=command, ctx=ctx).value


def _clone(args, *, context):
    return _mutation('agent_clone', args, context)


def _distill(args, *, context):
    return _mutation('agent_distill', args, context)


def _retire(args, *, context):
    return _mutation('agent_retire', args, context)


def _tree(args, *, context):
    _check('lineage_tree', args)
    effective = deepcopy(args)
    effective.setdefault('agent', 'system')
    effective.setdefault('include_retired', True)
    return tree(root_id=effective.get('root_id'), include_retired=effective['include_retired'],
                ctx=_context(effective, context))


TOOLS = (
    ToolSpec('agent_clone', 'Clone verified agent context and captured version inputs.',
             _SCHEMAS['agent_clone'], _clone, True),
    ToolSpec('agent_distill', 'Derive an agent by selecting receipt-backed context.',
             _SCHEMAS['agent_distill'], _distill, True),
    ToolSpec('agent_retire', 'Retire a committed agent without deleting its history.',
             _SCHEMAS['agent_retire'], _retire, True),
    ToolSpec('lineage_tree', 'Read structured ancestry and effective lifecycle from the journal.',
             _SCHEMAS['lineage_tree'], _tree, False),
)
VALIDATORS = {}
FOLDS = {'tree': TreeFold()}
