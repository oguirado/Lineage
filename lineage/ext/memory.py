"""The memory tool surface; policy stays in the domain validators."""
from lineage.domain.memory import units, fold
from lineage.core.registry import Command, ToolSpec, FoldSpec

_INPUTS = {'memory_put': {'type': 'object',
                'properties': {'agent_id': {'type': 'string',
                                            'minLength': 3,
                                            'maxLength': 64,
                                            'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                               'unit': {'$ref': 'mem_unit.schema.json'},
                               'run_id': {'type': 'string',
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
                'required': ['agent_id', 'unit', 'agent', 'op_id'],
                'additionalProperties': False},
 'memory_get': {'type': 'object',
                'properties': {'agent_id': {'type': 'string',
                                            'minLength': 3,
                                            'maxLength': 64,
                                            'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                               'unit_id': {'type': 'string',
                                           'minLength': 8,
                                           'maxLength': 64,
                                           'pattern': '^[A-Za-z0-9_-]{8,64}(?![\\s\\S])'},
                               'agent': {'type': 'string',
                                         'minLength': 3,
                                         'maxLength': 64,
                                         'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'}},
                'required': ['agent_id', 'unit_id'],
                'additionalProperties': False},
 'memory_history': {'type': 'object',
                    'properties': {'agent_id': {'type': 'string',
                                                'minLength': 3,
                                                'maxLength': 64,
                                                'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                   'unit_id': {'type': 'string',
                                               'minLength': 8,
                                               'maxLength': 64,
                                               'pattern': '^[A-Za-z0-9_-]{8,64}(?![\\s\\S])'},
                                   'after': {'type': 'integer',
                                             'minimum': 0,
                                             'maximum': 9007199254740991},
                                   'limit': {'type': 'integer', 'minimum': 1, 'maximum': 1000},
                                   'agent': {'type': 'string',
                                             'minLength': 3,
                                             'maxLength': 64,
                                             'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'}},
                    'required': ['agent_id'],
                    'additionalProperties': False}}


def _put(args, ctx):
    command = Command('memory_put', args, ctx.actor, args['op_id'], args.get('expected_head'))
    return units.put(args['agent_id'], args['unit'], run_id=args.get('run_id'),
                     command=command, ctx=ctx).value


def _get(args, ctx):
    return units.get(args['agent_id'], args['unit_id'], ctx=ctx)


def _history(args, ctx):
    return units.history(args['agent_id'], unit_id=args.get('unit_id'),
                         after=args.get('after', 0), limit=args.get('limit', 100), ctx=ctx)


for _handler in (_put, _get, _history):
    _handler._memory_contract = True

TOOLS = (
    ToolSpec('memory_put', 'Write validated agent memory.', _INPUTS['memory_put'], 'journal', _put),
    ToolSpec('memory_get', 'Inspect an explicit memory unit.', _INPUTS['memory_get'], 'read', _get),
    ToolSpec('memory_history', 'Inspect authoritative memory events.', _INPUTS['memory_history'], 'read', _history),
)
VALIDATORS = {'memory.put': units._validate_put, 'memory.retire': units._validate_retire}
FOLDS = {'memory': FoldSpec(frozenset({'agent.born', 'memory.put', 'memory.retire'}), 30, fold.apply)}
