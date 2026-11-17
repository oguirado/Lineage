"""Isolated K0 doubles and owned loopback resources; no real-domain certification."""
from __future__ import annotations

import copy
import hashlib
import http.client
import importlib
import io
import json
import math
import multiprocessing
import os
from pathlib import Path
import re
import selectors
import signal
import socket
import sys
import time
import types
import unittest

import lineage
from contextlib import contextmanager
from dataclasses import dataclass, replace
from html.parser import HTMLParser
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
CAP = 1048576
SAFE = 9007199254740991
ERROR_STATUS = {
    'bad_args': 400, 'bad_op': 409, 'stale_rev': 409, 'busy': 503,
    'internal': 500, 'conflict': 409, 'no_agent': 404, 'no_run': 404,
    'run_closed': 409, 'memory_required': 409, 'memory_debt': 409,
    'forbidden_level': 403, 'not_inheritable': 409, 'hash_mismatch': 409,
    'rule_not_declared': 409, 'no_benchmark': 404, 'heldout_forbidden': 409,
    'seat_not_allowed': 409, 'fixture_readonly': 403, 'timeout': 504,
}


class LineageError(Exception):
    def __init__(self, code: str, detail: str = '') -> None:
        self.code, self.detail = code, detail
        super().__init__(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':')).encode('utf-8')


def decode(raw, *, max_bytes=CAP):
    if not isinstance(raw, bytes) or len(raw) > max_bytes:
        raise LineageError('bad_args')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise LineageError('bad_args')
            result[key] = value
        return result
    def check(value):
        if isinstance(value, str):
            value.encode('utf-8', 'strict')
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError('finite JSON required')
        elif isinstance(value, dict):
            for key, item in value.items():
                check(key)
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        check(value)
        return value
    except (ValueError, UnicodeError, TypeError):
        raise LineageError('bad_args') from None


def same_json(left, right):
    if isinstance(left, bool) != isinstance(right, bool):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(same_json(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(same_json(a, b) for a, b in zip(left, right))
    return left == right


class SchemaStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self, name: str) -> dict:
        if not name or Path(name).name != name or not name.endswith('.schema.json'):
            raise LineageError('bad_args')
        return decode((self.root / name).read_bytes())

    def resolve(self, reference: str, *, base: str):
        name, _, fragment = reference.partition('#')
        result = self.load(name or base)
        if fragment and not fragment.startswith('/'):
            raise LineageError('bad_args')
        for part in fragment.strip('/').split('/') if fragment else ():
            result = result[part.replace('~1', '/').replace('~0', '~')]
        return result


def validate(value, schema, *, store, base, pointer=''):
    """Documented K0 subset for doubles, not a replacement production validator."""
    annotations = {'$schema', '$id', 'title', 'description', 'default', '$defs'}
    assertions = {'$ref', 'type', 'properties', 'patternProperties', 'required', 'additionalProperties',
        'items', 'minItems', 'maxItems', 'uniqueItems', 'minLength', 'maxLength', 'pattern',
        'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'const', 'enum',
        'allOf', 'anyOf', 'oneOf', 'not', 'if', 'then', 'else'}
    root_schema = schema
    def check(item, rule, current_base):
        if rule is True:
            return
        if rule is False or not isinstance(rule, dict) or set(rule) - annotations - assertions:
            raise LineageError('bad_args')
        if '$ref' in rule:
            reference = rule['$ref']
            if reference.startswith('#') and not current_base:
                selected = root_schema
                for part in reference[2:].split('/') if reference[2:] else ():
                    selected = selected[part.replace('~1', '/').replace('~0', '~')]
            else:
                selected = store.resolve(reference, base=current_base)
            check(item, selected, reference.partition('#')[0] or current_base)
        def accepts(candidate):
            try:
                check(item, candidate, current_base)
                return True
            except LineageError:
                return False
        for candidate in rule.get('allOf', ()):
            check(item, candidate, current_base)
        if 'anyOf' in rule and not any(accepts(r) for r in rule['anyOf']):
            raise LineageError('bad_args')
        if 'oneOf' in rule and sum(accepts(r) for r in rule['oneOf']) != 1:
            raise LineageError('bad_args')
        if 'not' in rule and accepts(rule['not']):
            raise LineageError('bad_args')
        if 'if' in rule:
            branch = 'then' if accepts(rule['if']) else 'else'
            if branch in rule:
                check(item, rule[branch], current_base)
        if 'const' in rule and not same_json(item, rule['const']):
            raise LineageError('bad_args')
        if 'enum' in rule and not any(same_json(item, candidate) for candidate in rule['enum']):
            raise LineageError('bad_args')
        types_ = {'object': dict, 'array': list, 'string': str, 'integer': int,
                  'number': (int, float), 'boolean': bool, 'null': type(None)}
        kinds = rule.get('type')
        if kinds:
            kinds = kinds if isinstance(kinds, list) else [kinds]
            if not any(isinstance(item, types_[kind]) and
                       not (isinstance(item, bool) and kind in ('integer', 'number')) for kind in kinds):
                raise LineageError('bad_args')
        if isinstance(item, dict):
            if not set(rule.get('required', ())) <= item.keys():
                raise LineageError('bad_args')
            for key, child in item.items():
                matches = [candidate for expression, candidate in rule.get('patternProperties', {}).items()
                           if re.search(expression, key)]
                if key in rule.get('properties', {}):
                    matches.append(rule['properties'][key])
                if not matches:
                    matches.append(rule.get('additionalProperties', True))
                for candidate in matches:
                    check(child, candidate, current_base)
        if isinstance(item, list):
            if not rule.get('minItems', 0) <= len(item) <= rule.get('maxItems', SAFE):
                raise LineageError('bad_args')
            if rule.get('uniqueItems') and any(same_json(a, b) for i, a in enumerate(item) for b in item[:i]):
                raise LineageError('bad_args')
            for child in item:
                check(child, rule.get('items', True), current_base)
        if isinstance(item, str):
            item.encode('utf-8', 'strict')
            if not rule.get('minLength', 0) <= len(item) <= rule.get('maxLength', SAFE):
                raise LineageError('bad_args')
            if 'pattern' in rule and not re.search(rule['pattern'], item):
                raise LineageError('bad_args')
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            if not math.isfinite(item) or (isinstance(item, int) and abs(item) > SAFE):
                raise LineageError('bad_args')
            if not rule.get('minimum', -float('inf')) <= item <= rule.get('maximum', float('inf')):
                raise LineageError('bad_args')
            if ('exclusiveMinimum' in rule and item <= rule['exclusiveMinimum']) or ('exclusiveMaximum' in rule and item >= rule['exclusiveMaximum']):
                raise LineageError('bad_args')
    check(value, schema, base)


def _validate(value, schema, *, schemas):
    validate(value, schema, store=SchemaStore(ROOT / 'schemas'), base='')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def load_record(raw, name, *, store, max_bytes=CAP):
    value = decode(raw, max_bytes=max_bytes)
    validate(value, store.load(name), store=store, base=name)
    if not isinstance(value, dict):
        raise LineageError('bad_args')
    return value


def error_payload(exc):
    result = {'ok': False, 'code': exc.code if isinstance(exc, LineageError) else 'internal'}
    if isinstance(exc, LineageError) and exc.detail:
        result['detail'] = exc.detail[:2048]
    return result


@dataclass(frozen=True)
class Services:
    home: Path
    repo_root: Path
    registry: 'Registry'
    clock: object
    id_factory: object
    token_count: object | None


@dataclass(frozen=True)
class Context:
    services: Services
    actor: str
    authority: str = 'tool'
    transport: str = 'library'


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    effect: str
    handler: object


class Registry:
    def __init__(self, tools=()):
        self.tools = {tool.name: tool for tool in tools}
        self.validators, self.folds = {}, {}

    def descriptors(self):
        return copy.deepcopy([{'name': item.name, 'description': item.description,
                               'inputSchema': item.input_schema}
                              for _, item in sorted(self.tools.items())])

    def names(self):
        return frozenset(self.tools)


def list_tools(*, ctx):
    return ctx.services.registry.descriptors()


def dispatch(name, args, *, ctx):
    if not isinstance(args, dict) or name not in ctx.services.registry.tools:
        return {'ok': False, 'code': 'bad_args'}
    spec = ctx.services.registry.tools[name]
    effective = copy.deepcopy(args)
    effective.setdefault('agent', 'system')
    if name == 'ledger_events':
        for key, value in {'after': 0, 'limit': 100, 'wait_ms': 0}.items():
            effective.setdefault(key, value)
    if name == 'agent_list':
        effective.setdefault('include_retired', False)
        effective.setdefault('limit', 100)
    try:
        _validate(effective, spec.input_schema, schemas={})
        actor_ctx = replace(ctx, actor=effective['agent'])
        return {'untrusted': spec.handler(effective, actor_ctx)}
    except LineageError as exc:
        return error_payload(exc)


@contextmanager
def load_surface():
    """Replace only missing provider seams, locally; restore imports on exit."""
    import lineage
    package = types.ModuleType('lineage.core')
    package.__path__ = [str(ROOT / 'lineage' / 'core')]
    serve_package = types.ModuleType('lineage.serve')
    serve_package.__path__ = [str(ROOT / 'lineage' / 'serve')]
    modules = {'lineage.core': package, 'lineage.serve': serve_package}
    bindings = {
        'registry': dict(Context=Context, Services=Services, Registry=Registry, ToolSpec=ToolSpec),
        'errors': dict(LineageError=LineageError, error_payload=error_payload),
        'schema': dict(decode=decode, canonical=canonical, validate=validate, SchemaStore=SchemaStore, load_record=load_record,
                       JSONValue=object, JSONObject=dict, digest=digest),
        'app': dict(list_tools=list_tools, dispatch=dispatch),
    }
    for name, values in bindings.items():
        mod = types.ModuleType('lineage.core.' + name)
        mod.__dict__.update(values)
        modules[mod.__name__] = mod
        setattr(package, name, mod)
    with patch.dict(sys.modules, modules), patch.object(lineage, 'core', package, create=True), \
            patch.object(lineage, 'serve', serve_package, create=True):
        for name in ('http', 'session', 'static', 'fixtures'):
            sys.modules.pop('lineage.serve.' + name, None)
        yield types.SimpleNamespace(**{
            name: importlib.import_module('lineage.serve.' + name)
            for name in ('http', 'session', 'static', 'fixtures')})


def input_schema(effect='read', extra=None, required=()):
    props = {'agent': {'type': 'string', 'minLength': 3}, **(extra or {})}
    needs = list(required)
    if effect != 'read':
        props.update(op_id={'type': 'string', 'minLength': 1},
                     expected_head={'type': 'integer', 'minimum': 0, 'maximum': SAFE})
        needs.extend(('agent', 'op_id'))
    return {'type': 'object', 'properties': props, 'required': needs,
            'additionalProperties': False}


def event(number):
    value = {'schema': 'lineage.event/v1', 'id': 'e-' + format(number, '016x'),
             'lamport': number, 'ts': 1700000000000 + number, 'ledger': 'main',
             'agent': 'sample-agent', 'kind': 'run.beat', 'payload': {'run_id': 'run_0001'},
             'op_id': 'operation-' + str(number), 'request_sha256': hashlib.sha256(str(number).encode()).hexdigest(),
             'evidence': [], 'prev_sha256': '0' * 64}
    value['sha256'] = hashlib.sha256(canonical(value)).hexdigest()
    return value


def cursor(after=0, head=0, limit=100):
    if after > head:
        return dict(events=[], next_after=0, head=head, has_more=False, resync=True)
    end = min(head, after + limit)
    return dict(events=[event(i) for i in range(after + 1, end + 1)],
                next_after=end, head=head, has_more=end < head, resync=False)


def make_context(root, state, options):
    replay = {}
    def observe(name, args, ctx):
        with state['calls'].get_lock():
            state['calls'].value += 1
        state['observed'].put((name, args, ctx.actor, ctx.authority, ctx.transport))
        if options.get('forbid_live'):
            with state['live'].get_lock():
                state['live'].value += 1
            raise AssertionError('live fixture handler invoked')
    def read(args, ctx):
        observe('read_sample', args, ctx)
        return {'text': args.get('text'), 'count': args.get('count'), 'unknown': None}
    def agents(args, ctx):
        observe('agent_list', args, ctx)
        return {'agents': [], 'next_after': None, 'head': state['head'].value}
    def ledger(args, ctx):
        observe('ledger_events', args, ctx)
        if options.get('health_error'):
            raise LineageError(options['health_error'])
        if args.get('wait_ms', 0) and state['head'].value <= args['after']:
            state['waiting'].set()
            state['advanced'].wait(min(args['wait_ms'] / 1000, 1))
        return cursor(args['after'], state['head'].value, args['limit'])
    def verify(args, ctx):
        observe('ledger_verify', args, ctx)
        if options.get('health_error'):
            raise LineageError(options['health_error'])
        return {'valid': True, 'head': state['head'].value, 'issues': []}
    def write(args, ctx):
        observe('write_sample', args, ctx)
        key = args['agent'], args['op_id']
        digest = canonical({k: v for k, v in args.items() if k not in ('op_id', 'expected_head')})
        if key in replay:
            if replay[key][0] != digest:
                raise LineageError('bad_op')
            return replay[key][1]
        with state['head'].get_lock():
            state['head'].value += 1
            head = state['head'].value
        state['advanced'].set()
        data = {'commit': {'event_ids': [event(head)['id']], 'head': head,
                           'sha256': event(head)['sha256']}, 'unknown': None}
        replay[key] = digest, data
        return data
    def external(args, ctx):
        observe('external_sample', args, ctx)
        return {'state': 'launched', 'unknown': None}
    def export(args, ctx):
        observe('ledger_export', args, ctx)
        return {'out': args['out'], 'head': state['head'].value}
    tools = [ToolSpec('read_sample', 'Synthetic read', input_schema(extra={
        'text': {'type': ['string', 'null']},
        'count': {'type': 'integer', 'minimum': 0, 'maximum': SAFE}}), 'read', read),
        ToolSpec('write_sample', 'Synthetic journal', input_schema('journal', {'text': {'type': 'string'}}), 'journal', write),
        ToolSpec('external_sample', 'Synthetic external', input_schema('external'), 'external', external),
        ToolSpec('ledger_export', 'Synthetic export', input_schema(extra={'out': {'type': 'string'}}, required=('out',)), 'read', export),
        ToolSpec('ledger_events', 'Synthetic cursor', input_schema(extra={
            'after': {'type': 'integer', 'minimum': 0, 'maximum': SAFE},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 1000},
            'wait_ms': {'type': 'integer', 'minimum': 0, 'maximum': 30000},
            'agent_id': {'type': 'string'}, 'kinds': {'type': 'array', 'items': {'type': 'string'}}}), 'read', ledger),
        ToolSpec('ledger_verify', 'Synthetic verifier', input_schema(), 'read', verify),
        ToolSpec('agent_list', 'Synthetic agent list', input_schema(extra={
            'include_retired': {'type': 'boolean'}, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 1000}}), 'read', agents)]
    for code in ERROR_STATUS:
        def failure(args, ctx, code=code):
            observe('error_' + code, args, ctx)
            raise LineageError(code, 'Synthetic failure.')
        tools.append(ToolSpec('error_' + code, 'Synthetic failure', input_schema(), 'read', failure))
    def unsafe(args, ctx):
        observe('unsafe', args, ctx)
        raise OSError(str(root / 'sentinel-private') + ' SYNTHETIC_SECRET')
    tools.append(ToolSpec('unsafe', 'Synthetic internal failure', input_schema(), 'read', unsafe))
    registry = Registry(tools)
    if options.get('missing_cursor'):
        for name in ('ledger_events', 'ledger_verify', 'agent_list'):
            registry.tools.pop(name)
    if options.get('legacy_result'):
        registry.tools['read_sample'] = replace(registry.tools['read_sample'], handler=lambda a, c: object())
    return Context(Services(root / 'home', root, registry, lambda: 1700000000000,
                            lambda: 'synthetic_0001', None), 'system', 'operator')


def run_server(connection, root, state, options, output_fds):
    sys.dont_write_bytecode = True
    for target, (reader, writer) in zip((1, 2), output_fds):
        os.close(reader)
        os.dup2(writer, target)
        os.close(writer)
    sys.stdout = io.TextIOWrapper(os.fdopen(os.dup(1), 'wb', buffering=0), encoding='utf-8', write_through=True)
    sys.stderr = io.TextIOWrapper(os.fdopen(os.dup(2), 'wb', buffering=0), encoding='utf-8', write_through=True)
    try:
        os.chdir(root / 'unrelated')
        original_bind = socket.socket.bind
        def observed_bind(sock, address):
            result = original_bind(sock, address)
            connection.send(('bound', sock.getsockname()))
            return result
        socket.socket.bind = observed_bind
        if options.get('fast_timeouts'):
            original_timeout = socket.socket.settimeout
            def accelerated_timeout(sock, value):
                if value is not None and value > 0:
                    try:
                        sock.getpeername()
                    except OSError:
                        pass
                    else:
                        state['read_deadline'].set()
                        value = min(value, 0.1)
                return original_timeout(sock, value)
            socket.socket.settimeout = accelerated_timeout
        if options.get('race'):
            original_open = os.open
            def racing(path, flags, mode=0o777, *, dir_fd=None):
                if Path(path).name == 'assets' and not state['raced'].is_set():
                    state['raced'].set()
                    (root / 'ui/dist/assets').rename(root / 'safe-assets')
                    (root / 'ui/dist/assets').symlink_to(root / 'outside', target_is_directory=True)
                return original_open(path, flags, mode, dir_fd=dir_fd)
            os.open = racing
        with load_surface() as modules:
            caller_ctx = make_context(root, state, options)
            original_tools = dict(caller_ctx.services.registry.tools)
            original_descriptors = caller_ctx.services.registry.descriptors()
            def check_registry():
                current = caller_ctx.services.registry
                changed = current.tools.keys() != original_tools.keys()
                changed = changed or any(current.tools[k] is not v for k, v in original_tools.items())
                changed = changed or current.descriptors() != original_descriptors
                if changed:
                    with state['registry_changes'].get_lock():
                        state['registry_changes'].value += 1
            def watched_dispatch(name, args, *, ctx):
                check_registry()
                try:
                    if options.get('raised_error'):
                        raise LineageError(options['raised_error'], 'Synthetic failure.')
                    return dispatch(name, args, ctx=ctx)
                finally:
                    check_registry()
            sys.modules['lineage.core.app'].dispatch = watched_dispatch
            for module in vars(modules).values():
                for name, value in list(vars(module).items()):
                    if value is dispatch:
                        setattr(module, name, watched_dispatch)
            if options.get('fixtures'):
                import builtins
                def watch(original):
                    def wrapped(path, *args, **kwargs):
                        if isinstance(path, (str, bytes, os.PathLike)):
                            candidate = Path(os.fsdecode(path)).absolute()
                            if candidate.is_relative_to(root / 'home'):
                                with state['home_access'].get_lock():
                                    state['home_access'].value += 1
                        return original(path, *args, **kwargs)
                    return wrapped
                builtins.open = watch(builtins.open)
                io.open = watch(io.open)
                os.open = watch(os.open)
                os.stat = watch(os.stat)
            original_token = modules.session.new_token
            def token():
                with state['tokens'].get_lock():
                    state['tokens'].value += 1
                return original_token()
            modules.session.new_token = token
            for module in vars(modules).values():
                for name, value in list(vars(module).items()):
                    if value is original_token:
                        setattr(module, name, token)
            kwargs = {'ctx': caller_ctx}
            if 'port' in options:
                kwargs['port'] = options['port']
            if options.get('fixtures'):
                kwargs['fixtures'] = root / 'fixtures'
            modules.http.serve(**kwargs)
        connection.send(('stopped', None))
    except BaseException as exc:
        connection.send(('exception', type(exc).__name__, getattr(exc, 'code', None), str(exc)))
    finally:
        connection.close()


@dataclass
class Response:
    status: int
    headers: dict
    body: bytes

    def json(self):
        return decode(self.body)


class RunningServer:
    def __init__(self, root, **options):
        self.root, self.options = root, options
        mp = multiprocessing.get_context('fork')
        self.state = {name: mp.Value('i', options.get('head', 0) if name == 'head' else 0)
                      for name in ('head', 'calls', 'live', 'tokens', 'home_access', 'registry_changes')}
        self.state.update({name: mp.Event() for name in ('waiting', 'advanced', 'raced', 'read_deadline')})
        self.state['observed'] = mp.Queue()
        self.connection, child = mp.Pipe()
        output_fds = (os.pipe(), os.pipe())
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.connection.fileno(), selectors.EVENT_READ, 'control')
        self.pending_output = {'stdout': b'', 'stderr': b''}
        self.output_readers = []
        for channel, (reader, writer) in zip(('stdout', 'stderr'), output_fds):
            os.set_blocking(reader, False)
            self.selector.register(reader, selectors.EVENT_READ, channel)
            self.output_readers.append(reader)
        self.process = mp.Process(target=run_server, args=(child, root, self.state, options, output_fds))
        self.records = []
        self.process.start()
        child.close()
        for reader, writer in output_fds:
            os.close(writer)
        self.port = None
        try:
            deadline = time.monotonic() + 1.5
            while self.port is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError('No bounded startup record')
                new_records = self.receive(remaining)
                if not new_records and time.monotonic() >= deadline:
                    raise AssertionError('No bounded startup record')
                for record in new_records:
                    self.records.append(record)
                    if record[0] == 'exception':
                        if record[1] == 'NotImplementedError':
                            raise NotImplementedError(record[3])
                        if record[2]:
                            raise LineageError(record[2])
                        raise AssertionError('Server exception: ' + record[1])
                    if record[0] == 'stderr':
                        try:
                            value = json.loads(record[1])
                        except ValueError:
                            continue
                        if isinstance(value, dict) and set(value) == {'port'}:
                            self.port = value['port']
            self.authority = '127.0.0.1:' + str(self.port)
            self.origin = 'http://' + self.authority
        except BaseException as exc:
            self.close()
            exc.records = list(self.records)
            raise

    def request(self, target='/', *, method='GET', body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=0.8)
        try:
            connection.putrequest(method, target, skip_host=True, skip_accept_encoding=True)
            for key, value in ([('Host', self.authority)] if headers is None else headers):
                connection.putheader(key, value)
            connection.endheaders(body)
            response = connection.getresponse()
            return Response(response.status, {k.lower(): v for k, v in response.getheaders()}, response.read())
        finally:
            connection.close()

    def call(self, tool='read_sample', args=None, *, protected=False, raw=None, headers=None):
        body = canonical({'tool': tool, 'args': args or {}}) if raw is None else raw
        if headers is None:
            headers = [('Host', self.authority), ('Content-Type', 'application/json'), ('Content-Length', str(len(body)))]
            if protected:
                headers += [('Origin', self.origin), ('X-Lineage-Session', self.token())]
        return self.request('/api/call', method='POST', body=body, headers=headers)

    def token(self, target='/'):
        response = self.request(target)
        if response.status != 200:
            raise AssertionError('Bootstrap status: ' + str(response.status))
        parser = TokenParser()
        parser.feed(response.body.decode())
        if len(parser.tokens) != 1 or not parser.tokens[0]:
            raise AssertionError('Exactly one nonempty session meta required')
        return parser.tokens[0]

    def raw(self, data, *, truncate=False):
        connection = socket.create_connection(('127.0.0.1', self.port), timeout=0.8)
        try:
            connection.sendall(data)
            if truncate:
                connection.shutdown(socket.SHUT_WR)
            response = http.client.HTTPResponse(connection)
            response.begin()
            return Response(response.status, {k.lower(): v for k, v in response.getheaders()}, response.read())
        finally:
            connection.close()

    def receive(self, timeout=0):
        records = []
        for key, mask in sorted(self.selector.select(timeout), key=lambda event: event[0].data != 'control'):
            if key.data == 'control':
                try:
                    records.append(self.connection.recv())
                except EOFError:
                    self.selector.unregister(key.fd)
                continue
            try:
                data = os.read(key.fd, 65536)
            except BlockingIOError:
                continue
            if not data:
                self.selector.unregister(key.fd)
                continue
            self.pending_output[key.data] += data
            while b'\n' in self.pending_output[key.data]:
                line, self.pending_output[key.data] = self.pending_output[key.data].split(b'\n', 1)
                records.append((key.data, line.decode('utf-8', 'replace')))
        return records

    def drain(self):
        while True:
            records = self.receive()
            if not records:
                break
            self.records.extend(records)
        return self.records + [(name + '_fragment', data.decode('utf-8', 'replace'))
                               for name, data in self.pending_output.items() if data]

    def close(self):
        if getattr(self, "closed", False):
            return
        self.closed = True
        if self.process.is_alive():
            self.process.terminate()
        self.process.join(0.5)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(0.5)
        self.selector.close()
        for reader in self.output_readers:
            os.close(reader)
        self.connection.close()
        self.state['observed'].close()
        self.state['observed'].join_thread()


class TokenParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tokens, self.in_head, self.positions = [], False, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'head':
            self.in_head = True
        if tag == 'meta' and attrs.get('name', '').casefold() == 'lineage-session-token':
            self.tokens.append(attrs.get('content'))
            self.positions.append(self.in_head)

    def handle_endtag(self, tag):
        if tag == 'head':
            self.in_head = False


def build_assets(root):
    dist = root / 'ui/dist'
    (dist / 'assets').mkdir(parents=True)
    files = {
        'index.html': b'<!doctype html><html><head><META content="old-one" NAME="LINEAGE-SESSION-TOKEN"><meta name=lineage-session-token content=old-two><title>Sample</title></head><body><main data-lin-screen="agents">Synthetic</main></body></html>',
        'assets/theme.css': b'body{color:#123456}',
        'app.js': b'export const sample = "unchanged";',
        'app.mjs': b'export default 1;',
        'icon.svg': b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        'data.json': b'{"sample":true}', 'pixel.png': b'\x89PNG\r\n\x1a\n',
        'font.woff2': b'wOF2synthetic',
    }
    for path, data in files.items():
        (dist / path).write_bytes(data)
    (root / 'home').mkdir()
    (root / 'unrelated').mkdir()
    (root / 'outside').mkdir()
    (root / 'outside/theme.css').write_bytes(b'OUTSIDE_SENTINEL')
    (root / 'home/sentinel.txt').write_bytes(b'HOME_SENTINEL')
    return files


def fixture(root):
    """Minimal empty dataset using the README's manifest/read-response formats."""
    target = root / 'fixtures'
    target.mkdir()
    clock = dict(epoch_ms=1700000000000, tick_ms=1, locale='en-GB', timezone='UTC', theme='light', reduced_motion=True)
    values = {name: [] for name in ('agents', 'runs', 'benches', 'skills', 'references', 'constitutions', 'scorecards', 'lineage')}
    values['memory'] = {}
    values['clock'] = clock
    values['responses'] = [{'tool': 'agent_list', 'args': {'agent': 'system', 'include_retired': False, 'limit': 100},
                            'data': {'agents': [], 'next_after': None, 'head': 0}}]
    for name, value in values.items():
        (target / (name + '.json')).write_bytes(canonical(value))
    (target / 'events.jsonl').write_bytes(b'')
    (target / 'artifacts').mkdir()
    for name in ('lesson', 'negative', 'ruling'):
        (target / 'artifacts' / (name + '.txt')).write_text('Synthetic ' + name + '.\n', encoding='utf-8')
    (target / 'scenarios').mkdir()
    (target / 'scenarios/baseline.json').write_bytes(canonical(dict(name='baseline', dataset='baseline', frames=[], expect={})))
    manifest = dict(fixture_version=1, files=[], baseline='scenarios/baseline.json', clock='clock.json', head=0, roots=[],
                    capture=dict(device_scale_factor=1, viewport=dict(width=1440, height=900), theme='light', reduced_motion=True))
    (target / 'manifest.json').write_bytes(canonical(manifest))
    rehash(target)
    return target


def rehash(target):
    path = target / 'manifest.json'
    manifest = decode(path.read_bytes())
    manifest['files'] = [{'path': p.relative_to(target).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                         for p in sorted(target.rglob('*')) if p.is_file() and p != path]
    path.write_bytes(canonical(manifest))


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


class BoundedCase(unittest.TestCase):
    def setUp(self):
        previous_handler = signal.getsignal(signal.SIGALRM)
        previous_timer = signal.getitimer(signal.ITIMER_REAL)
        def deadline(signum, frame):
            raise AssertionError('Owned oracle exceeded its per-test deadline')
        signal.signal(signal.SIGALRM, deadline)
        signal.setitimer(signal.ITIMER_REAL, 3.5)
        def restore():
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)
            signal.signal(signal.SIGALRM, previous_handler)
        self.addCleanup(restore)


class ServerCase(BoundedCase):
    def setUp(self):
        super().setUp()
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = build_assets(self.root)
        self.server = None

    def start(self, **options):
        server = RunningServer(self.root, **options)
        self.addCleanup(server.close)
        self.server = server
        return server

    def assert_error(self, response, status, code='bad_args'):
        self.assertEqual(response.status, status)
        self.assertEqual(response.headers.get('content-type', '').split(';')[0], 'application/json')
        self.assertEqual(response.headers.get('cache-control'), 'no-store')
        self.assertFalse(any(k.startswith('access-control-allow-') for k in response.headers))
        value = response.json()
        self.assertIs(value.get('ok'), False)
        self.assertEqual(value.get('code'), code)
        self.assertTrue(set(value) <= {'ok', 'code', 'detail'})
        if 'detail' in value:
            self.assertIsInstance(value['detail'], str)
            self.assertTrue(0 < len(value['detail']) <= 2048)
        self.assertEqual(response.body, canonical(value))
        self.assertNotIn(str(self.root).encode(), response.body)
        self.assertNotIn(b'SYNTHETIC_SECRET', response.body)
        return value


def cases(cls, prefix, rows, function):
    """Generate separately reported cases with stable semantic identifiers."""
    for label, value in rows:
        def test(self, value=value):
            function(self, value)
        test.__name__ = 'test_' + prefix + '_' + label
        setattr(cls, test.__name__, test)
