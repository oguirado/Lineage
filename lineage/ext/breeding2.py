"""Closed breeding tool descriptors over the shared application boundary."""
from copy import deepcopy
from dataclasses import replace

from lineage.core.registry import ToolSpec
from lineage.domain.breeding import Command
from lineage.domain.breeding.cross import cross, _check
from lineage.domain.breeding.mutate import mutate
from lineage.domain.breeding.specialize import specialize


def _install_one_of():
    """Supply the frozen change union through the installed schema evaluator.

    Keep native JSON, type, closure and scalar checks. The older mini-validator
    lacks oneOf; a union must preflight every branch and match exactly one.
    This adapter is shared by discovery, domain and strict transport checks.
    """
    from lineage.core import schema
    from lineage.domain.memory import schema as memory_schema
    memory_schema._sync_boundary()
    if getattr(schema._schema_node, '_breeding_union', False):
        return
    native_node, native_assert = schema._schema_node, schema._assertions

    def node(definition, pointer, depth, active, patterns):
        if type(definition) is not dict or 'oneOf' not in definition:
            return native_node(definition, pointer, depth, active, patterns)
        branches = definition['oneOf']
        if type(branches) is not list or not branches:
            raise schema.SchemaError('invalid_schema', schema_pointer=pointer + '/oneOf')
        native_node({k: v for k, v in definition.items() if k != 'oneOf'},
                    pointer, depth, active, patterns)
        for index, branch in enumerate(branches):
            node(branch, pointer + '/oneOf/' + str(index), depth + 1, active, patterns)

    def assertions(value, definition, pointer, patterns):
        if 'oneOf' not in definition:
            return native_assert(value, definition, pointer, patterns)
        native_assert(value, {k: v for k, v in definition.items() if k != 'oneOf'}, pointer, patterns)
        matches = 0
        for branch in definition['oneOf']:
            try:
                assertions(value, branch, pointer, patterns)
            except schema.SchemaError:
                continue
            matches += 1
        if matches != 1:
            raise schema.SchemaError('oneOf', pointer=pointer)

    node._breeding_union = True
    schema._schema_node, schema._assertions = node, assertions
    # The installed memory facade composes conditionals around native scalar
    # validation. Its union branch must enforce the same exact-one rule.
    from lineage.domain.memory import schema as memory_schema
    if getattr(memory_schema._check, '_breeding_union', False):
        return
    native_check = memory_schema._check

    def check(value, definition, store, base):
        if type(definition) is not dict or 'oneOf' not in definition:
            return native_check(value, definition, store, base)
        native_check(value, {k: v for k, v in definition.items() if k != 'oneOf'}, store, base)
        branches = definition['oneOf']
        if type(branches) is not list or not branches:
            raise schema.SchemaError('invalid_schema', schema_pointer='/oneOf')
        matches = 0
        for branch in branches:
            try:
                check(value, branch, store, base)
            except schema.SchemaError:
                continue
            matches += 1
        if matches != 1:
            raise schema.SchemaError('oneOf')

    check._breeding_union = True
    memory_schema._check = check


_install_one_of()


def _install_discovery():
    """Rebind union evaluation after an integrated schema-provider refresh."""
    from lineage.core import registry
    if getattr(registry._descriptor, '_breeding_discovery', False):
        return
    original = registry._descriptor

    def descriptor(spec):
        from lineage.core import schema
        if (not getattr(schema._schema_node, '_breeding_union', False)
                or registry.SchemaError is not schema.SchemaError):
            _install_one_of()
        return original(spec)

    descriptor._breeding_discovery = True
    registry._descriptor = descriptor


_install_discovery()

_SCHEMAS = {'agent_cross': {'type': 'object',
                 'properties': {'parent_ids': {'type': 'array',
                                               'items': {'type': 'string',
                                                         'minLength': 3,
                                                         'maxLength': 64,
                                                         'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                               'minItems': 2,
                                               'maxItems': 2,
                                               'uniqueItems': True},
                                'child_id': {'type': 'string',
                                             'minLength': 3,
                                             'maxLength': 64,
                                             'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                'display_name': {'type': 'string',
                                                 'minLength': 1,
                                                 'maxLength': 128},
                                'agent': {'type': 'string',
                                          'minLength': 3,
                                          'maxLength': 64,
                                          'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                'op_id': {'type': 'string',
                                          'minLength': 1,
                                          'maxLength': 128,
                                          'pattern': '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])'},
                                'expected_head': {'type': 'integer',
                                                  'minimum': 0,
                                                  'maximum': 9007199254740991}},
                 'required': ['parent_ids', 'child_id', 'agent', 'op_id'],
                 'additionalProperties': False},
 'agent_mutate': {'type': 'object',
                  'properties': {'parent_id': {'type': 'string',
                                               'minLength': 3,
                                               'maxLength': 64,
                                               'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                 'child_id': {'type': 'string',
                                              'minLength': 3,
                                              'maxLength': 64,
                                              'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                 'display_name': {'type': 'string',
                                                  'minLength': 1,
                                                  'maxLength': 128},
                                 'change': {'oneOf': [{'type': 'object',
                                                       'properties': {'kind': {'const': 'skill'},
                                                                      'skill_id': {'type': 'string',
                                                                                   'minLength': 3,
                                                                                   'maxLength': 64,
                                                                                   'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                                                      'from_sha256': {'type': 'string',
                                                                                      'minLength': 64,
                                                                                      'maxLength': 64,
                                                                                      'pattern': '^[0-9a-f]{64}(?![\\s\\S])'},
                                                                      'to': {'type': 'object',
                                                                             'properties': {'skill_id': {'type': 'string',
                                                                                                         'minLength': 3,
                                                                                                         'maxLength': 64,
                                                                                                         'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                                                                            'sha256': {'type': 'string',
                                                                                                       'minLength': 64,
                                                                                                       'maxLength': 64,
                                                                                                       'pattern': '^[0-9a-f]{64}(?![\\s\\S])'}},
                                                                             'required': ['skill_id',
                                                                                          'sha256'],
                                                                             'additionalProperties': False}},
                                                       'required': ['kind',
                                                                    'skill_id',
                                                                    'from_sha256',
                                                                    'to'],
                                                       'additionalProperties': False},
                                                      {'type': 'object',
                                                       'properties': {'kind': {'const': 'rule'},
                                                                      'rule_id': {'type': 'string',
                                                                                  'minLength': 1,
                                                                                  'maxLength': 64},
                                                                      'text': {'type': 'string',
                                                                               'minLength': 1,
                                                                               'maxLength': 16000}},
                                                       'required': ['kind', 'rule_id', 'text'],
                                                       'additionalProperties': False}]},
                                 'agent': {'type': 'string',
                                           'minLength': 3,
                                           'maxLength': 64,
                                           'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                 'op_id': {'type': 'string',
                                           'minLength': 1,
                                           'maxLength': 128,
                                           'pattern': '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])'},
                                 'expected_head': {'type': 'integer',
                                                   'minimum': 0,
                                                   'maximum': 9007199254740991}},
                  'required': ['parent_id', 'child_id', 'change', 'agent', 'op_id'],
                  'additionalProperties': False},
 'agent_specialize': {'type': 'object',
                      'properties': {'parent_id': {'type': 'string',
                                                   'minLength': 3,
                                                   'maxLength': 64,
                                                   'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                     'child_id': {'type': 'string',
                                                  'minLength': 3,
                                                  'maxLength': 64,
                                                  'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                     'display_name': {'type': 'string',
                                                      'minLength': 1,
                                                      'maxLength': 128},
                                     'language': {'type': 'string',
                                                  'minLength': 1,
                                                  'maxLength': 64},
                                     'agent': {'type': 'string',
                                               'minLength': 3,
                                               'maxLength': 64,
                                               'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                     'op_id': {'type': 'string',
                                               'minLength': 1,
                                               'maxLength': 128,
                                               'pattern': '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])'},
                                     'expected_head': {'type': 'integer',
                                                       'minimum': 0,
                                                       'maximum': 9007199254740991}},
                      'required': ['parent_id', 'child_id', 'language', 'agent', 'op_id'],
                      'additionalProperties': False}}


def _mutation(name, args, context):
    _check(name, args)
    effective = deepcopy(args)
    command = Command(name, effective, effective['agent'], effective['op_id'], effective.get('expected_head'))
    changes = {'actor': effective['agent']}
    if hasattr(context, 'op_id'):
        changes['op_id'] = effective['op_id']
    if hasattr(context, 'authority'):
        changes['authority'] = 'tool'
    ctx = replace(context, **changes)
    params = {k: v for k, v in effective.items() if k not in ('agent', 'op_id', 'expected_head')}
    function = {'agent_cross': cross, 'agent_mutate': mutate, 'agent_specialize': specialize}[name]
    return function(**params, command=command, ctx=ctx).value


def _cross(args, ctx=None, *, context=None):
    return _mutation('agent_cross', args, context if context is not None else ctx)


def _mutate(args, ctx=None, *, context=None):
    return _mutation('agent_mutate', args, context if context is not None else ctx)


def _specialize(args, ctx=None, *, context=None):
    return _mutation('agent_specialize', args, context if context is not None else ctx)


# Select the integrated full-schema facade, which also emits bounded textual
# argument errors. Native keyword-only handlers remain callable by every lane.
for _handler in (_cross, _mutate, _specialize):
    _handler._memory_contract = True

TOOLS = (
    ToolSpec('agent_cross', 'Compose two compatible receipt-backed agent contexts.',
             _SCHEMAS['agent_cross'], _cross, True),
    ToolSpec('agent_mutate', 'Change one verified skill pin or permitted rule inclusion.',
             _SCHEMAS['agent_mutate'], _mutate, True),
    ToolSpec('agent_specialize', 'Derive context within an exact language scope.',
             _SCHEMAS['agent_specialize'], _specialize, True),
)
VALIDATORS = {}
FOLDS = {}
