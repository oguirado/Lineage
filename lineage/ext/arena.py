"""Arena discovery and strict adapters for the integrated registry boundary."""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from types import MappingProxyType

from lineage.core import registry, schema
from lineage.domain.memory import schema as memory_schema
from lineage.domain.arena import bank, bench

_SCHEMAS = {'bench_list': {'type': 'object',
                'properties': {'after': {'type': 'string',
                                         'minLength': 8,
                                         'maxLength': 64,
                                         'pattern': '^[A-Za-z0-9_-]{8,64}(?![\\s\\S])'},
                               'limit': {'type': 'integer', 'minimum': 1, 'maximum': 1000},
                               'agent': {'type': 'string',
                                         'minLength': 3,
                                         'maxLength': 64,
                                         'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'}},
                'required': [],
                'additionalProperties': False},
 'bench_declare': {'type': 'object',
                   'properties': {'declaration': {'$ref': 'bench_declared.schema.json'},
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
                   'required': ['declaration', 'agent', 'op_id'],
                   'additionalProperties': False},
 'bench_run': {'type': 'object',
               'properties': {'bench_id': {'type': 'string',
                                           'minLength': 8,
                                           'maxLength': 64,
                                           'pattern': '^[A-Za-z0-9_-]{8,64}(?![\\s\\S])'},
                              'runner': {'oneOf': [{'type': 'object',
                                                    'properties': {'kind': {'const': 'fake'},
                                                                   'seed': {'type': 'integer',
                                                                            'minimum': 0,
                                                                            'maximum': 4294967295}},
                                                    'required': ['kind', 'seed'],
                                                    'additionalProperties': False},
                                                   {'type': 'object',
                                                    'properties': {'kind': {'const': 'command'},
                                                                   'argv': {'type': 'array',
                                                                            'items': {'type': 'string',
                                                                                      'minLength': 1,
                                                                                      'maxLength': 4096},
                                                                            'minItems': 1,
                                                                            'maxItems': 128},
                                                                   'timeout_ms': {'type': 'integer',
                                                                                  'minimum': 1,
                                                                                  'maximum': 3600000}},
                                                    'required': ['kind', 'argv', 'timeout_ms'],
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
               'required': ['bench_id', 'runner', 'agent', 'op_id'],
               'additionalProperties': False},
 'bench_status': {'type': 'object',
                  'properties': {'bench_id': {'type': 'string',
                                              'minLength': 8,
                                              'maxLength': 64,
                                              'pattern': '^[A-Za-z0-9_-]{8,64}(?![\\s\\S])'},
                                 'agent': {'type': 'string',
                                           'minLength': 3,
                                           'maxLength': 64,
                                           'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'}},
                  'required': ['bench_id'],
                  'additionalProperties': False},
 'bench_verdict': {'type': 'object',
                   'properties': {'bench_id': {'type': 'string',
                                               'minLength': 8,
                                               'maxLength': 64,
                                               'pattern': '^[A-Za-z0-9_-]{8,64}(?![\\s\\S])'},
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
                   'required': ['bench_id', 'agent', 'op_id'],
                   'additionalProperties': False}}

# The installed schema facade lacks oneOf/exclusive bounds. Extend only the
# exact arena descriptor shapes; all other core schemas keep their native API.
# Discovery and dispatch still consume the unchanged contract descriptors.
_previous_validate = memory_schema._validate
_previous_preflight = memory_schema._preflight


def _ours(definition):
    return type(definition) is dict and any(definition == value for value in _SCHEMAS.values())


def _lower(definition):
    if isinstance(definition, list):
        return [_lower(child) for child in definition]
    if not isinstance(definition, dict):
        return definition
    result = {}
    for key, value in definition.items():
        key = {'oneOf': 'anyOf', 'exclusiveMinimum': 'minimum',
               'exclusiveMaximum': 'maximum'}.get(key, key)
        result[key] = _lower(value)
    return result


@wraps(_previous_validate)
def _validate(value, definition, *, store=None, base=None):
    if _ours(definition):
        memory_schema._native_validate(value, {})
        return bank._check(value, definition)
    return _previous_validate(value, definition, store=store, base=base)


def _preflight(definition, store):
    return _previous_preflight(_lower(definition) if _ours(definition) else definition, store)


memory_schema._validate = _validate
memory_schema._preflight = _preflight
schema.validate = _validate


def _handler(name):
    def handle(args, *, context):
        effective = deepcopy(args)
        effective.setdefault('agent', 'system')
        ctx = bench._context(bank._context(context, actor=effective['agent']))
        if name == 'bench_list':
            return bench.list_benches(after=effective.get('after'), limit=effective.get('limit', 100), ctx=ctx)
        if name == 'bench_status':
            return bench.status(effective['bench_id'], ctx=ctx)
        command = registry.Command(name, effective, effective['agent'], effective['op_id'],
                                   effective.get('expected_head'))
        if name == 'bench_declare':
            return bench.declare(effective['declaration'], command=command, ctx=ctx).value
        if name == 'bench_run':
            return bench.run(effective['bench_id'], effective['runner'], command=command, ctx=ctx)
        return bench.verdict(effective['bench_id'], command=command, ctx=ctx).value
    return handle


TOOLS = tuple(registry.ToolSpec(name, description, deepcopy(_SCHEMAS[name]), effect, _handler(name))
              for name, description, effect in (
                  ('bench_list', 'List journal-backed benchmark declarations.', 'read'),
                  ('bench_declare', 'Declare an immutable benchmark before execution.', 'journal'),
                  ('bench_run', 'Execute declared cells through mandatory task memory.', 'journal'),
                  ('bench_status', 'Inspect committed benchmark progress.', 'read'),
                  ('bench_verdict', 'Record a declared statistical verdict.', 'journal')))
VALIDATORS = MappingProxyType({'bench.declared': bench._validate_declared,
    'bench.result': bench._validate_result, 'bench.verdict': bench._validate_verdict})
FOLDS = MappingProxyType({'arena': bench._ArenaFold()})
