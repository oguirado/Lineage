"""Frozen agent tools over the installed shared registry and dispatch API."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from lineage.core.errors import LineageError
from lineage.core.registry import ToolSpec
from lineage.domain import agents, brief

# These are the exact K0 discovery descriptors, without runtime document reads.
_SCHEMAS = {'agent_create': {'type': 'object',
                  'properties': {'agent_id': {'type': 'string',
                                              'minLength': 3,
                                              'maxLength': 64,
                                              'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                 'display_name': {'type': 'string',
                                                  'minLength': 1,
                                                  'maxLength': 128},
                                 'workflow': {'enum': ['develop',
                                                       'test',
                                                       'review',
                                                       'harden',
                                                       'research',
                                                       'orchestrate']},
                                 'language': {'type': 'string', 'minLength': 1, 'maxLength': 64},
                                 'allowed_seats': {'type': 'array',
                                                   'items': {'type': 'object',
                                                             'properties': {'model': {'type': 'string',
                                                                                      'minLength': 1,
                                                                                      'maxLength': 128},
                                                                            'effort': {'type': 'string',
                                                                                       'minLength': 1,
                                                                                       'maxLength': 32,
                                                                                       'pattern': '^[a-z0-9_-]+(?![\\s\\S])'},
                                                                            'mode': {'enum': ['headless',
                                                                                              'interactive']}},
                                                             'required': ['model',
                                                                          'effort',
                                                                          'mode'],
                                                             'additionalProperties': False},
                                                   'minItems': 1,
                                                   'maxItems': 16,
                                                   'uniqueItems': True},
                                 'references': {'type': 'array',
                                                'items': {'type': 'object',
                                                          'properties': {'id': {'enum': ['gold_s1',
                                                                                         'memory_v21']},
                                                                         'sha256': {'type': 'string',
                                                                                    'minLength': 64,
                                                                                    'maxLength': 64,
                                                                                    'pattern': '^[0-9a-f]{64}(?![\\s\\S])'}},
                                                          'required': ['id', 'sha256'],
                                                          'additionalProperties': False},
                                                'minItems': 2,
                                                'maxItems': 2,
                                                'uniqueItems': True},
                                 'skills': {'type': 'array',
                                            'items': {'type': 'object',
                                                      'properties': {'skill_id': {'type': 'string',
                                                                                  'minLength': 3,
                                                                                  'maxLength': 64,
                                                                                  'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                                                     'sha256': {'type': 'string',
                                                                                'minLength': 64,
                                                                                'maxLength': 64,
                                                                                'pattern': '^[0-9a-f]{64}(?![\\s\\S])'}},
                                                      'required': ['skill_id', 'sha256'],
                                                      'additionalProperties': False},
                                            'minItems': 0,
                                            'maxItems': 256,
                                            'uniqueItems': True},
                                 'overlays': {'type': 'array',
                                              'items': {'type': 'string',
                                                        'minLength': 1,
                                                        'maxLength': 64},
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
                  'required': ['agent_id',
                               'display_name',
                               'workflow',
                               'language',
                               'allowed_seats',
                               'references',
                               'skills',
                               'agent',
                               'op_id'],
                  'additionalProperties': False},
 'agent_get': {'type': 'object',
               'properties': {'agent_id': {'type': 'string',
                                           'minLength': 3,
                                           'maxLength': 64,
                                           'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                              'agent': {'type': 'string',
                                        'minLength': 3,
                                        'maxLength': 64,
                                        'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'}},
               'required': ['agent_id'],
               'additionalProperties': False},
 'agent_list': {'type': 'object',
                'properties': {'workflow': {'enum': ['develop',
                                                     'test',
                                                     'review',
                                                     'harden',
                                                     'research',
                                                     'orchestrate']},
                               'language': {'type': 'string', 'minLength': 1, 'maxLength': 64},
                               'status': {'enum': ['draft', 'shadow', 'promoted', 'retired']},
                               'include_retired': {'type': 'boolean'},
                               'after': {'type': 'string',
                                         'minLength': 3,
                                         'maxLength': 64,
                                         'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                               'limit': {'type': 'integer', 'minimum': 1, 'maximum': 1000},
                               'agent': {'type': 'string',
                                         'minLength': 3,
                                         'maxLength': 64,
                                         'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'}},
                'required': [],
                'additionalProperties': False},
 'agent_brief': {'type': 'object',
                 'properties': {'agent_id': {'type': 'string',
                                             'minLength': 3,
                                             'maxLength': 64,
                                             'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'},
                                'memory_arm': {'enum': ['none', 'own', 'inherited']},
                                'agent': {'type': 'string',
                                          'minLength': 3,
                                          'maxLength': 64,
                                          'pattern': '^[a-z][a-z0-9-]{2,63}(?![\\s\\S])'}},
                 'required': ['agent_id'],
                 'additionalProperties': False}}


def _context(args, context):
    actor = args.get('agent', 'system')
    agents._match(actor, agents._AGENT)
    try:
        if hasattr(context, 'services'):
            return replace(context, actor=actor, authority='tool')
        return replace(context, actor=actor, op_id=args.get('op_id'))
    except (TypeError, AttributeError, ValueError):
        raise LineageError('bad_args', 'invalid agent call context') from None


def _create(args, *, context):
    agents._check('agent_create', args)
    effective = deepcopy(args)
    effective.setdefault('overlays', [])
    command = agents._Command('agent_create', effective, effective['agent'],
                              effective['op_id'], effective.get('expected_head'))
    data = {key: effective[key] for key in ('agent_id', 'display_name', 'workflow',
            'language', 'allowed_seats', 'references', 'skills', 'overlays')}
    return agents.create(**data, command=command, ctx=_context(effective, context)).value


def _get(args, *, context):
    agents._check('agent_get', args)
    return agents.get(args['agent_id'], ctx=_context(args, context))


def _list(args, *, context):
    agents._check('agent_list', args)
    return agents.list_agents(**{key: value for key, value in args.items() if key != 'agent'},
                              ctx=_context(args, context))


def _brief(args, *, context):
    agents._check('agent_brief', args)
    return brief.get(args['agent_id'], memory_arm=args.get('memory_arm', 'own'),
                     ctx=_context(args, context))


TOOLS = (
    ToolSpec('agent_create', 'Create a journal-authoritative genesis agent.',
             _SCHEMAS['agent_create'], _create, True),
    ToolSpec('agent_get', 'Read a committed agent identity.',
             _SCHEMAS['agent_get'], _get, False),
    ToolSpec('agent_list', 'List committed agents in lexical identity order.',
             _SCHEMAS['agent_list'], _list, False),
    ToolSpec('agent_brief', 'Build verified deterministic passive agent context.',
             _SCHEMAS['agent_brief'], _brief, False),
)
VALIDATORS = {'agent.born': agents._validate_born, 'agent.status': agents._validate_status}
FOLDS = {'agents': agents._AgentsFold()}
