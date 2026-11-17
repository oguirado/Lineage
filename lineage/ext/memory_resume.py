"""Read-only memory recall and verified resume; no state or event ownership."""
from lineage.domain.memory import bootcheck, route, store
from lineage.core.registry import ToolSpec

_AGENT = {'type': 'string', 'minLength': 3, 'maxLength': 64,
          'pattern': r'^[a-z][a-z0-9-]{2,63}(?![\s\S])'}
_HASH = {'type': 'string', 'minLength': 64, 'maxLength': 64,
         'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
_COUNT = {'type': 'integer', 'minimum': 0, 'maximum': 9007199254740991}


def _route(args, ctx):
    return route.route(args['agent_id'], args['query'], limit=args.get('limit', 10), ctx=ctx)


def _bootcheck(args, ctx):
    return bootcheck.check(args['agent_id'], args['observed'], ctx=ctx)


# The installed U10 dispatch facade uses this marker for positional handlers.
_route._memory_contract = True
_bootcheck._memory_contract = True
_route._memory_resume = True
_bootcheck._memory_resume = True

TOOLS = (
    ToolSpec('memory_route', 'Search eligible committed agent memory.', {
        'type': 'object', 'properties': {
            'agent_id': dict(_AGENT), 'query': {'type': 'string', 'minLength': 1, 'maxLength': 512},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50}, 'agent': dict(_AGENT)},
        'required': ['agent_id', 'query'], 'additionalProperties': False}, 'read', _route),
    ToolSpec('memory_bootcheck', 'Verify independently observed agent memory.', {
        'type': 'object', 'properties': {
            'agent_id': dict(_AGENT), 'observed': {
                'type': 'object', 'properties': {
                    'agent_version': dict(_HASH), 'memory_gen': dict(_COUNT),
                    'head': dict(_COUNT), 'entry_sha256': dict(_HASH)},
                'required': ['agent_version', 'memory_gen', 'head', 'entry_sha256'],
                'additionalProperties': False}, 'agent': dict(_AGENT)},
        'required': ['agent_id', 'observed'], 'additionalProperties': False}, 'read', _bootcheck),
)
VALIDATORS = {}
FOLDS = {}

# A-K0-9: compose the installed positional-dispatch API without replacing owners.
store._install_resume_dispatch()
store._install_memory_publication()
store._install_resume_json()

store._install_resume_lifecycle()
