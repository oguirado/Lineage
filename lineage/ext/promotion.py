"""Closed promotion tool over the shared dispatch and journal boundary."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from lineage.core import schema
from lineage.core.errors import LineageError
from lineage.core.registry import ToolSpec
from lineage.domain import promotion

INPUT_SCHEMA = {
    'type': 'object',
    'properties': {
        'agent_id': {'type': 'string', 'minLength': 3, 'maxLength': 64,
                     'pattern': r'^[a-z][a-z0-9-]{2,63}(?![\s\S])'},
        'bench_id': {'type': 'string', 'minLength': 8, 'maxLength': 64,
                     'pattern': r'^[A-Za-z0-9_-]{8,64}(?![\s\S])'},
        'agent': {'type': 'string', 'minLength': 3, 'maxLength': 64,
                  'pattern': r'^[a-z][a-z0-9-]{2,63}(?![\s\S])'},
        'op_id': {'type': 'string', 'minLength': 1, 'maxLength': 128,
                  'pattern': r'^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\s\S])'},
        'expected_head': {'type': 'integer', 'minimum': 0, 'maximum': 9007199254740991}},
    'required': ['agent_id', 'bench_id', 'agent', 'op_id'],
    'additionalProperties': False}


def agent_promote(args, *, context):
    try:
        schema.validate(args, INPUT_SCHEMA)
        effective = deepcopy(args)
        changes = {'actor': effective['agent']}
        if hasattr(context, 'op_id'):
            changes['op_id'] = effective['op_id']
        if hasattr(context, 'authority'):
            changes['authority'] = 'tool'
        ctx = replace(context, **changes)
    except schema.SchemaError:
        raise LineageError('bad_args', 'invalid promotion arguments') from None
    except (TypeError, AttributeError, ValueError):
        raise LineageError('internal', 'promotion runtime unavailable') from None
    command = {'tool': 'agent_promote', 'args': effective,
               'agent': effective['agent'], 'op_id': effective['op_id']}
    if 'expected_head' in effective:
        command['expected_head'] = effective['expected_head']
    return promotion.promote(effective['agent_id'], effective['bench_id'], command=command, ctx=ctx)


TOOLS = (ToolSpec('agent_promote', 'Promote an agent using committed measured qualification.',
                  INPUT_SCHEMA, agent_promote, True),)
VALIDATORS = {}
FOLDS = {'promotion': promotion.apply}

# Adapt the integrated owner readers; apply still owns only promotion state.
promotion._install_reader_adapters()
promotion._install_family_adapter()
