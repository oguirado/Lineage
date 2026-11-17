"""Frozen ABI, lifecycle, discovery, shared-error and dispatch parity oracles."""
import inspect
import signal
import socket
import unittest
from pathlib import Path
from typing import get_type_hints

from tests.serve._support import (
    Context, ERROR_STATUS, LineageError, ROOT, ServerCase, canonical,
    cases, input_schema, list_tools, load_surface, make_context,
)


class ContractTests(ServerCase):
    def test_a01_exact_frozen_signatures_and_types(self):
        with load_surface() as modules:
            functions = [
                (modules.session.new_token, [], {}, {'return': str}),
                (modules.session.authorize,
                 ['host', 'origin', 'token', 'expected_authority', 'expected_token', 'mutation'], {},
                 dict(host=str, origin=str | None, token=str | None, expected_authority=str,
                      expected_token=str, mutation=bool, **{'return': type(None)})),
                (modules.static.resolve_asset, ['url_path', 'root'], {},
                 dict(url_path=str, root=Path, **{'return': Path})),
                (modules.http.serve, ['ctx', 'port', 'fixtures'], {'port': 0, 'fixtures': None},
                 dict(ctx=Context, port=int, fixtures=Path | None, **{'return': type(None)})),
            ]
            for function, parameters, defaults, hints in functions:
                signature = inspect.signature(function)
                self.assertEqual(list(signature.parameters), parameters)
                for name, parameter in signature.parameters.items():
                    expected = inspect.Parameter.POSITIONAL_OR_KEYWORD if name == 'url_path' else inspect.Parameter.KEYWORD_ONLY
                    self.assertEqual(parameter.kind, expected)
                    self.assertEqual(parameter.default, defaults.get(name, inspect.Parameter.empty))
                self.assertEqual(get_type_hints(function, globalns={**function.__globals__, 'Context': Context}), hints)
            # ABI inspection alone cannot pass an unimplemented token boundary.
            self.assertEqual(get_type_hints(modules.http.serve, globalns={**modules.http.serve.__globals__, 'Context': Context})['ctx'], Context)
            self.assertTrue(modules.session.new_token())

    def test_a01_no_legacy_result_adaptation(self):
        server = self.start(legacy_result=True)
        self.assert_error(server.call(), 500, 'internal')

    def test_a01_client_object_cannot_become_context(self):
        with load_surface() as modules:
            with self.assertRaises(LineageError) as caught:
                modules.http.serve(ctx={'authority': 'operator', 'services': {}}, port=0)
        self.assertIn(caught.exception.code, ('bad_args', 'internal'))

    def test_a02_default_and_explicit_ephemeral_bind(self):
        server = self.start()
        self.assertIs(type(server.port), int)
        self.assertTrue(0 < server.port <= 65535)
        with socket.create_connection(('127.0.0.1', server.port), timeout=0.5) as connection:
            self.assertEqual(connection.getpeername(), ('127.0.0.1', server.port))
        self.assertEqual(server.request('/api/health').status, 200)
        self.assertEqual([r[1][0] for r in server.records if r[0] == 'bound'], ['127.0.0.1'])

    def test_a02_explicit_available_port(self):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        server = self.start(port=port)
        self.assertEqual(server.port, port)
        self.assertEqual(server.request('/api/tools').status, 200)

    def test_a02_no_bind_address_parameter(self):
        with load_surface() as modules:
            self.assertNotIn('host', inspect.signature(modules.http.serve).parameters)
            self.assertNotIn('bind', inspect.signature(modules.http.serve).parameters)
            self.assertTrue(modules.session.new_token())

    def test_a03_startup_stderr_closed_shape_stdout_empty(self):
        server = self.start(port=0)
        self.assertEqual(server.request('/api/health').status, 200)
        records = server.drain()
        self.assertEqual([r for r in records if r[0] == 'stdout'], [])
        startup = [r for r in records if r[0] == 'stderr']
        self.assertEqual(startup, [('stderr', canonical({'port': server.port}).decode())])

    def test_a03_occupied_listener_is_internal(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            with self.assertRaises(LineageError) as caught:
                self.start(port=listener.getsockname()[1])
        self.assertEqual(caught.exception.code, 'internal')
        self.assertFalse(any(r[0] == 'stderr' and '"port"' in r[1] for r in caught.exception.records))

    def test_a07_http_context_always_tool_authority(self):
        server = self.start()
        response = server.call(args={'agent': 'operator'})
        self.assertEqual(response.status, 200)
        _, args, actor, authority, transport = server.state['observed'].get(timeout=0.3)
        self.assertEqual(args['agent'], 'operator')
        self.assertEqual((actor, authority, transport), ('operator', 'tool', 'http'))
        self.assert_error(server.call('error_forbidden_level', {'agent': 'operator'}), 403, 'forbidden_level')

    def test_a12_mutation_cannot_acquire_identity(self):
        server = self.start()
        self.assert_error(server.call('write_sample', {'agent': 'sample-agent'}, protected=True), 400)
        self.assertEqual(server.state['calls'].value, 0)
        self.assertEqual(server.state['head'].value, 0)

    def test_a16_exact_replay_retains_original_prefix(self):
        server = self.start()
        args = {'agent': 'sample-agent', 'op_id': 'replay-1', 'expected_head': 0, 'text': 'first'}
        first = server.call('write_sample', args, protected=True)
        self.assertEqual(first.status, 200)
        self.assertEqual(first.json()['untrusted']['commit']['head'], 1)
        self.assertEqual(server.call('write_sample', {'agent': 'sample-agent', 'op_id': 'later-2'}, protected=True).status, 200)
        replay = server.call('write_sample', args, protected=True)
        self.assertEqual(replay.body, first.body)
        self.assertEqual(server.state['head'].value, 2)
        changed = server.call('write_sample', {**args, 'text': 'changed'}, protected=True)
        self.assert_error(changed, 409, 'bad_op')
        self.assertEqual(server.state['head'].value, 2)
        observations = [server.state['observed'].get(timeout=0.3) for _ in range(4)]
        self.assertEqual(observations[0][1], args)
        self.assertEqual(observations[-1][1]['op_id'], 'replay-1')

    def test_a16_read_and_external_wrapper_fidelity(self):
        server = self.start()
        response = server.call(args={'text': 'sample'})
        self.assertEqual(response.json(), {'untrusted': {'text': 'sample', 'count': None, 'unknown': None}})
        result = server.call('external_sample', {'agent': 'sample-agent', 'op_id': 'external-1'}, protected=True)
        self.assertEqual(result.status, 200)
        self.assertEqual(result.json(), {'untrusted': {'state': 'launched', 'unknown': None}})
        self.assertEqual(server.state['head'].value, 0)

    def test_a16_disconnect_after_dispatch_does_not_retry(self):
        server = self.start()
        body = canonical({'tool': 'write_sample', 'args': {'agent': 'sample-agent', 'op_id': 'disconnect-1'}})
        token = server.token()
        with socket.create_connection(('127.0.0.1', server.port), timeout=0.8) as connection:
            connection.sendall(('POST /api/call HTTP/1.1\r\nHost: ' + server.authority +
                '\r\nOrigin: ' + server.origin + '\r\nX-Lineage-Session: ' + token +
                '\r\nContent-Type: application/json\r\nContent-Length: ' + str(len(body)) + '\r\n\r\n').encode() + body)
            self.assertTrue(server.state['advanced'].wait(0.5), 'No dispatch witness before disconnect')
        self.assertEqual(server.call().status, 200)
        self.assertEqual(server.state['head'].value, 1)
        self.assertEqual(server.state['calls'].value, 2)

    def test_a17_detached_lexical_discovery_matches_registry(self):
        server = self.start()
        expected = list_tools(ctx=make_context(self.root, server.state, {}))
        response = server.request('/api/tools')
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json(), {'tools': expected})
        names = [row['name'] for row in expected]
        self.assertEqual(names, sorted(names))
        self.assertIn('write_sample', names)
        for row in expected:
            self.assertEqual(set(row), {'name', 'description', 'inputSchema'})
        response.json()['tools'][0]['inputSchema']['properties'].clear()
        self.assertEqual(server.request('/api/tools').json(), {'tools': expected})
        self.assertEqual(server.call().status, 200)

    def test_a18_health_tracks_actual_shared_head(self):
        server = self.start(head=3)
        self.assertEqual(server.request('/api/health').json(),
            {'ok': True, 'protocol': 'lineage.family/1', 'head': 3, 'fixtures': False})
        self.assertEqual(server.call('write_sample', {'agent': 'sample-agent', 'op_id': 'health-1'}, protected=True).status, 200)
        self.assertEqual(server.request('/api/health').json()['head'], 4)

    def test_a18_verified_empty_head_is_zero(self):
        response = self.start().request('/api/health')
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json(), {'ok': True, 'protocol': 'lineage.family/1', 'head': 0, 'fixtures': False})

    def test_a18_missing_provider_never_fabricates_empty(self):
        response = self.start(missing_cursor=True).request('/api/health')
        self.assert_error(response, 503, 'internal')

    def test_a25_unknown_exception_sanitized(self):
        self.assert_error(self.start().call('unsafe'), 500, 'internal')

    def test_a33_package_and_stdlib_surface(self):
        import ast
        allowed = {'lineage', '__future__', *getattr(__import__('sys'), 'stdlib_module_names')}
        self.assertTrue((ROOT / 'tests/serve/__init__.py').is_file())
        for path in (ROOT / 'lineage/serve').glob('*.py'):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(alias.name.split('.')[0] in allowed for alias in node.names))
                if isinstance(node, ast.ImportFrom) and node.level == 0:
                    self.assertIn(node.module.split('.')[0], allowed)
        with load_surface() as modules:
            self.assertTrue(modules.session.new_token())


def port(self, value):
    with self.assertRaises(LineageError) as caught:
        self.start(port=value)
    self.assertEqual(caught.exception.code, 'bad_args')


cases(ContractTests, 'a02_invalid_port', [('bool', True), ('negative', -1), ('above_max', 65536),
    ('string', '0'), ('float', 0.0), ('null', None), ('wildcard', '0.0.0.0:0')], port)


def shutdown(self, number):
    server = self.start()
    with socket.socket() as unrelated:
        unrelated.bind(('127.0.0.1', 0))
        unrelated.listen()
        server.process.send_signal(number) if hasattr(server.process, 'send_signal') else __import__('os').kill(server.process.pid, number)
        server.process.join(1)
        self.assertFalse(server.process.is_alive())
        self.assertEqual(server.process.exitcode, 0)
        records = server.drain()
        self.assertFalse(any(r[0] == 'exception' for r in records))
        self.assertIn(('stopped', None), records)
        with socket.socket() as probe:
            probe.settimeout(0.2)
            self.assertNotEqual(probe.connect_ex(('127.0.0.1', server.port)), 0)
        self.assertGreater(unrelated.fileno(), -1)


cases(ContractTests, 'a03_shutdown', [('sigint', signal.SIGINT), ('sigterm', signal.SIGTERM)], shutdown)


def protected(self, value):
    tool, mode = value
    server = self.start()
    args = {'out': 'exports/sample'} if tool == 'ledger_export' else {'agent': 'operator', 'op_id': 'effect-1'}
    if mode == 'valid':
        response = server.call(tool, args, protected=True)
        self.assertEqual(response.status, 200)
        self.assertEqual(server.state['calls'].value, 1)
    else:
        body = canonical({'tool': tool, 'args': args})
        headers = [('Host', server.authority), ('Content-Type', 'application/json'), ('Content-Length', str(len(body)))]
        if mode != 'missing_origin':
            headers.append(('Origin', server.origin))
        if mode == 'wrong':
            headers.append(('X-Lineage-Session', 'wrong'))
        elif mode in ('missing_origin', 'duplicate'):
            headers.append(('X-Lineage-Session', server.token()))
            if mode == 'duplicate':
                headers.append(('X-Lineage-Session', server.token()))
        self.assert_error(server.call(raw=body, headers=headers), 403)
        self.assertEqual(server.state['calls'].value, 0)
        self.assertEqual(server.state['head'].value, 0)


cases(ContractTests, 'a06_effect', [(tool + '_' + mode, (tool, mode))
    for tool in ('write_sample', 'external_sample', 'ledger_export')
    for mode in ('valid', 'missing', 'wrong', 'missing_origin', 'duplicate')], protected)


def mapping(self, value):
    code, status, raised = value
    server = self.start(**({'raised_error': code} if raised else {}))
    response = server.call('error_' + code)
    self.assert_error(response, status, code)
    self.assertEqual(response.json(), {'ok': False, 'code': code, 'detail': 'Synthetic failure.'})


cases(ContractTests, 'a25_returned', [(code, (code, status, False)) for code, status in ERROR_STATUS.items()], mapping)
cases(ContractTests, 'a25_raised', [(code, (code, status, True)) for code, status in ERROR_STATUS.items()], mapping)


def unavailable(self, code):
    response = self.start(health_error=code).request('/api/health')
    self.assert_error(response, 503, code)


cases(ContractTests, 'a18_unavailable', [('busy', 'busy'), ('internal', 'internal')], unavailable)
