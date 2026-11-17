"""Run tools and the journal admission/fold registrations."""
from __future__ import annotations

from lineage.domain import runs
from lineage.domain.memory import schema as memory_schema
from lineage.core.registry import Command, ToolSpec
from lineage.core.errors import LineageError

_SCHEMAS = {'run_open': {'type': 'object',
              'properties': {'run_id': {'type': 'string',
                                        'minLength': 8,
                                        'maxLength': 64,
                                        'pattern': '^[A-Za-z0-9_-]{8,64}(?![\\s\\S])'},
                             'agent_id': {'type': 'string',
                                          'minLength': 3,
                                          'maxLength': 64,
                                          'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                             'seat': {'type': 'object',
                                      'properties': {'model': {'type': 'string',
                                                               'minLength': 1,
                                                               'maxLength': 128},
                                                     'effort': {'type': 'string',
                                                                'minLength': 1,
                                                                'maxLength': 32,
                                                                'pattern': '^[a-z0-9_-]+(?![\\s\\S])'},
                                                     'mode': {'enum': ['headless', 'interactive']}},
                                      'required': ['model', 'effort', 'mode'],
                                      'additionalProperties': False},
                             'task': {'type': 'object',
                                      'properties': {'id': {'type': 'string',
                                                            'minLength': 8,
                                                            'maxLength': 64,
                                                            'pattern': '^[A-Za-z0-9_-]{8,64}(?![\\s\\S])'},
                                                     'kind': {'type': 'string',
                                                              'minLength': 1,
                                                              'maxLength': 64},
                                                     'language': {'type': 'string',
                                                                  'minLength': 1,
                                                                  'maxLength': 64},
                                                     'bank_id': {'type': 'string',
                                                                 'minLength': 3,
                                                                 'maxLength': 64,
                                                                 'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                                     'bench_id': {'type': 'string',
                                                                  'minLength': 8,
                                                                  'maxLength': 64,
                                                                  'pattern': '^[A-Za-z0-9_-]{8,64}(?![\\s\\S])'},
                                                     'split': {'enum': ['select', 'heldout']}},
                                      'required': ['id', 'kind', 'language'],
                                      'additionalProperties': False},
                             'parents_context': {'type': 'array',
                                                 'items': {'type': 'object',
                                                           'properties': {'agent_id': {'type': 'string',
                                                                                       'minLength': 3,
                                                                                       'maxLength': 64,
                                                                                       'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                                                          'agent_version': {'type': 'string',
                                                                                            'minLength': 64,
                                                                                            'maxLength': 64,
                                                                                            'pattern': '^[0-9a-f]{64}(?![\\s\\S])'},
                                                                          'run_id': {'type': 'string',
                                                                                     'minLength': 8,
                                                                                     'maxLength': 64,
                                                                                     'pattern': '^[A-Za-z0-9_-]{8,64}(?![\\s\\S])'}},
                                                           'required': ['agent_id',
                                                                        'agent_version',
                                                                        'run_id'],
                                                           'additionalProperties': False},
                                                 'minItems': 0,
                                                 'maxItems': 64,
                                                 'uniqueItems': True},
                             'memory_arm': {'enum': ['none', 'own', 'inherited']},
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
              'required': ['run_id',
                           'agent_id',
                           'seat',
                           'task',
                           'parents_context',
                           'memory_arm',
                           'agent',
                           'op_id'],
              'additionalProperties': False},
 'run_beat': {'type': 'object',
              'properties': {'run_id': {'type': 'string',
                                        'minLength': 8,
                                        'maxLength': 64,
                                        'pattern': '^[A-Za-z0-9_-]{8,64}(?![\\s\\S])'},
                             'progress': {'type': 'string', 'minLength': 1, 'maxLength': 2048},
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
              'required': ['run_id', 'progress', 'agent', 'op_id'],
              'additionalProperties': False},
 'run_close': {'type': 'object',
               'properties': {'run_id': {'type': 'string',
                                         'minLength': 8,
                                         'maxLength': 64,
                                         'pattern': '^[A-Za-z0-9_-]{8,64}(?![\\s\\S])'},
                              'outcome': {'type': 'object',
                                          'properties': {'verdict': {'enum': ['ADMIT',
                                                                              'HOLD',
                                                                              'red',
                                                                              'green',
                                                                              'error']},
                                                         'repair_loops': {'type': 'integer',
                                                                          'minimum': 0,
                                                                          'maximum': 1000000},
                                                         'findings': {'type': 'object',
                                                                      'properties': {'confirmed': {'type': 'integer',
                                                                                                   'minimum': 0,
                                                                                                   'maximum': 1000000},
                                                                                     'refuted': {'type': 'integer',
                                                                                                 'minimum': 0,
                                                                                                 'maximum': 1000000}},
                                                                      'required': ['confirmed',
                                                                                   'refuted'],
                                                                      'additionalProperties': False}},
                                          'required': ['verdict', 'repair_loops', 'findings'],
                                          'additionalProperties': False},
                              'cost': {'type': 'object',
                                       'properties': {'tokens_in': {'anyOf': [{'type': 'integer',
                                                                               'minimum': 0,
                                                                               'maximum': 9007199254740991},
                                                                              {'type': 'null'}]},
                                                      'tokens_out': {'anyOf': [{'type': 'integer',
                                                                                'minimum': 0,
                                                                                'maximum': 9007199254740991},
                                                                               {'type': 'null'}]},
                                                      'tokens_cache': {'anyOf': [{'type': 'integer',
                                                                                  'minimum': 0,
                                                                                  'maximum': 9007199254740991},
                                                                                 {'type': 'null'}]},
                                                      'duration_ms': {'anyOf': [{'type': 'integer',
                                                                                 'minimum': 0,
                                                                                 'maximum': 9007199254740991},
                                                                                {'type': 'null'}]},
                                                      'cost_micro_usd': {'anyOf': [{'type': 'integer',
                                                                                    'minimum': 0,
                                                                                    'maximum': 9007199254740991},
                                                                                   {'type': 'null'}]}},
                                       'required': ['tokens_in',
                                                    'tokens_out',
                                                    'tokens_cache',
                                                    'duration_ms',
                                                    'cost_micro_usd'],
                                       'additionalProperties': False},
                              'evidence': {'type': 'array',
                                           'items': {'type': 'object',
                                                     'properties': {'path': {'type': 'string',
                                                                             'minLength': 1,
                                                                             'maxLength': 512,
                                                                             'pattern': '^(?!/)(?!.*(?:^|/)\\.{1,2}(?:/|$))(?!.*\\\\)[A-Za-z0-9._/-]+(?![\\s\\S])'},
                                                                    'sha256': {'type': 'string',
                                                                               'minLength': 64,
                                                                               'maxLength': 64,
                                                                               'pattern': '^[0-9a-f]{64}(?![\\s\\S])'}},
                                                     'required': ['path', 'sha256'],
                                                     'additionalProperties': False},
                                           'minItems': 0,
                                           'maxItems': 64,
                                           'uniqueItems': True},
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
               'required': ['run_id', 'outcome', 'cost', 'agent', 'op_id'],
               'additionalProperties': False},
 'run_get': {'type': 'object',
             'properties': {'run_id': {'type': 'string',
                                       'minLength': 8,
                                       'maxLength': 64,
                                       'pattern': '^[A-Za-z0-9_-]{8,64}(?![\\s\\S])'},
                            'agent': {'type': 'string',
                                      'minLength': 3,
                                      'maxLength': 64,
                                      'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'}},
             'required': ['run_id'],
             'additionalProperties': False}}

_RESULTS = {'run_open': {'type': 'object',
              'properties': {'opened': {'$ref': 'event.schema.json'},
                             'commit': {'type': 'object',
                                        'properties': {'event_ids': {'type': 'array',
                                                                     'items': {'type': 'string',
                                                                               'minLength': 18,
                                                                               'maxLength': 18,
                                                                               'pattern': '^e-[0-9a-f]{16}(?![\\s\\S])'},
                                                                     'minItems': 1,
                                                                     'maxItems': 10000},
                                                       'head': {'type': 'integer',
                                                                'minimum': 1,
                                                                'maximum': 9007199254740991},
                                                       'sha256': {'type': 'string',
                                                                  'minLength': 64,
                                                                  'maxLength': 64,
                                                                  'pattern': '^[0-9a-f]{64}(?![\\s\\S])'}},
                                        'required': ['event_ids', 'head', 'sha256'],
                                        'additionalProperties': False}},
              'required': ['opened', 'commit'],
              'additionalProperties': False},
 'run_beat': {'type': 'object',
              'properties': {'event': {'$ref': 'event.schema.json'},
                             'commit': {'type': 'object',
                                        'properties': {'event_ids': {'type': 'array',
                                                                     'items': {'type': 'string',
                                                                               'minLength': 18,
                                                                               'maxLength': 18,
                                                                               'pattern': '^e-[0-9a-f]{16}(?![\\s\\S])'},
                                                                     'minItems': 1,
                                                                     'maxItems': 10000},
                                                       'head': {'type': 'integer',
                                                                'minimum': 1,
                                                                'maximum': 9007199254740991},
                                                       'sha256': {'type': 'string',
                                                                  'minLength': 64,
                                                                  'maxLength': 64,
                                                                  'pattern': '^[0-9a-f]{64}(?![\\s\\S])'}},
                                        'required': ['event_ids', 'head', 'sha256'],
                                        'additionalProperties': False}},
              'required': ['event', 'commit'],
              'additionalProperties': False},
 'run_close': {'type': 'object',
               'properties': {'run': {'$ref': 'run.schema.json'},
                              'commit': {'type': 'object',
                                         'properties': {'event_ids': {'type': 'array',
                                                                      'items': {'type': 'string',
                                                                                'minLength': 18,
                                                                                'maxLength': 18,
                                                                                'pattern': '^e-[0-9a-f]{16}(?![\\s\\S])'},
                                                                      'minItems': 1,
                                                                      'maxItems': 10000},
                                                        'head': {'type': 'integer',
                                                                 'minimum': 1,
                                                                 'maximum': 9007199254740991},
                                                        'sha256': {'type': 'string',
                                                                   'minLength': 64,
                                                                   'maxLength': 64,
                                                                   'pattern': '^[0-9a-f]{64}(?![\\s\\S])'}},
                                         'required': ['event_ids', 'head', 'sha256'],
                                         'additionalProperties': False}},
               'required': ['run', 'commit'],
               'additionalProperties': False},
 'run_get': {'type': 'object',
             'properties': {'opened': {'$ref': 'event.schema.json'},
                            'closed': {'anyOf': [{'$ref': 'run.schema.json'}, {'type': 'null'}]},
                            'head': {'type': 'integer', 'minimum': 0, 'maximum': 9007199254740991}},
             'required': ['opened', 'closed', 'head'],
             'additionalProperties': False}}


def _invoke(name, args, context):
    runs._check_args(name, args)
    effective = dict(args)
    if name == 'run_get':
        effective.setdefault('agent', 'system')
    if name == 'run_close':
        effective.setdefault('evidence', [])
    ctx = runs._context(context, actor=effective['agent'], op_id=effective.get('op_id'), tool=True)
    if name == 'run_get':
        return runs.get(effective['run_id'], ctx=ctx)
    command = Command(name, effective, ctx.actor, effective['op_id'], effective.get('expected_head'))
    data = {key: value for key, value in effective.items() if key not in ('agent', 'op_id', 'expected_head')}
    function = {'run_open': runs.open_run, 'run_beat': runs.beat, 'run_close': runs.close}[name]
    return function(**data, command=command, ctx=ctx).value


def _open(args, ctx=None, *, context=None):
    return _invoke('run_open', args, ctx if ctx is not None else context)


def _beat(args, ctx=None, *, context=None):
    return _invoke('run_beat', args, ctx if ctx is not None else context)


def _close(args, ctx=None, *, context=None):
    return _invoke('run_close', args, ctx if ctx is not None else context)


def _get(args, ctx=None, *, context=None):
    return _invoke('run_get', args, ctx if ctx is not None else context)


# U10's installed facade supports the bundled contract assertions and both
# positional K0 and keyword native handler calls. No decoder is replaced here.
for _handler in (_open, _beat, _close, _get):
    _handler._memory_contract = True

TOOLS = (
    ToolSpec('run_open', 'Open a run with frozen agent and seat identity.',
             _SCHEMAS['run_open'], 'journal', _open),
    ToolSpec('run_beat', 'Record owner progress on an open run.',
             _SCHEMAS['run_beat'], 'journal', _beat),
    ToolSpec('run_close', 'Close a run with validated current-run memory.',
             _SCHEMAS['run_close'], 'journal', _close),
    ToolSpec('run_get', 'Inspect an immutable run and its current ledger head.',
             _SCHEMAS['run_get'], 'read', _get),
)
VALIDATORS = {'run.open': runs._validate_open, 'run.beat': runs._validate_beat,
              'run.close': runs._validate_close}
FOLDS = {'runs': runs._RunsFold()}


def _install_argument_boundary():
    """Keep semantic argument refusals in the shared carriers' request lane.

    The installed facade validates the literal discovery schema before invoking
    a handler. Task's all-or-none benchmark rule is specified alongside that
    schema, so it needs the same request classification before domain execution.
    Delegate wrapping, context checks and execution to the installed dispatcher.
    """
    from functools import wraps
    from lineage.core import app

    previous = app.dispatch
    if getattr(previous, '_run_argument_boundary', False):
        return

    @wraps(previous)
    def dispatch(name, args, *, ctx=None, context=None, registry=None):
        chosen = ctx.services.registry if ctx is not None else registry
        if chosen is None:
            chosen = getattr(getattr(context, 'services', None), 'registry', None)
        if chosen is None and context is not None:
            from lineage.core.registry import load
            try:
                chosen = load()
            except Exception:
                # Preserve the installed dispatcher's configuration error handling.
                pass
        spec = chosen.tools.get(name) if chosen is not None and type(name) is str else None
        if spec is not None and getattr(spec.handler, '_run_contract', False):
            try:
                runs._check_args(name, args)
            except LineageError as exc:
                if exc.code == 'bad_args':
                    payload = {'ok': False, 'code': 'bad_args'}
                    return payload if ctx is not None else app.DispatchResult(payload, 'request')
                raise
        return previous(name, args, ctx=ctx, context=context, registry=registry)

    dispatch._run_argument_boundary = True
    app.dispatch = dispatch


for _handler in (_open, _beat, _close, _get):
    _handler._run_contract = True
_install_argument_boundary()
