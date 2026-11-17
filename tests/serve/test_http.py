"""Wire oracles: actual owned loopback requests, closed routes and adversarial framing."""
from concurrent.futures import ThreadPoolExecutor
import socket

from tests.serve._support import CAP, SAFE, ServerCase, TokenParser, canonical, cases, cursor


class HTTPTests(ServerCase):
    def test_a04_exact_host_all_surfaces(self):
        server = self.start()
        for path in ('/', '/index.html', '/app.js', '/api/health', '/api/tools'):
            self.assertEqual(server.request(path).status, 200)
        self.assertEqual(server.call().status, 200)

    def test_a05_same_origin_and_optional_read_origin(self):
        server = self.start()
        for headers in ([('Host', server.authority)],
                        [('Host', server.authority), ('Origin', server.origin)]):
            self.assertEqual(server.request('/api/tools', headers=headers).status, 200)
            self.assertEqual(server.request('/', headers=headers).status, 200)
        self.assertEqual(server.call().status, 200)

    def test_a08_bootstrap_all_index_spellings(self):
        server = self.start()
        tokens = []
        for path in ('/', '/index.html', '/%69ndex.html'):
            response = server.request(path)
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get('cache-control'), 'no-store')
            self.assertEqual(response.headers.get('content-type', '').lower().replace(' ', '').replace(chr(34), ''), 'text/html;charset=utf-8')
            parser = TokenParser()
            parser.feed(response.body.decode())
            self.assertEqual(len(parser.tokens), 1)
            self.assertEqual(parser.positions, [True])
            self.assertTrue(parser.tokens[0])
            self.assertNotIn(b'old-one', response.body)
            self.assertNotIn(b'old-two', response.body)
            self.assertIn(b'<title>Sample</title>', response.body)
            self.assertIn(b'data-lin-screen="agents"', response.body)
            tokens.extend(parser.tokens)
        self.assertEqual(len(set(tokens)), 1)
        self.assertEqual(server.state['tokens'].value, 1)

    def test_a08_headless_index_inserts_at_document_start(self):
        (self.root / 'ui/dist/index.html').write_text('<body>Sample</body>', encoding='utf-8')
        server = self.start()
        response = server.request('/')
        parser = TokenParser()
        parser.feed(response.body.decode())
        self.assertEqual(len(parser.tokens), 1)
        self.assertTrue(response.body.lstrip().lower().startswith(b'<meta'))
        self.assertTrue(response.body.endswith(b'<body>Sample</body>'))

    def test_a08_foreign_lifecycle_token_refused(self):
        first = self.start()
        token = first.token()
        first.close()
        # A new process and listener, using the same build, must have new entropy.
        second = self.start()
        self.assertNotEqual(second.token(), token)
        body = canonical({'tool': 'write_sample', 'args': {'agent': 'sample-agent', 'op_id': 'mutation-1'}})
        headers = [('Host', second.authority), ('Origin', second.origin), ('X-Lineage-Session', token),
                   ('Content-Type', 'application/json'), ('Content-Length', str(len(body)))]
        self.assert_error(second.call(raw=body, headers=headers), 403)
        self.assertEqual(second.state['calls'].value, 0)
        self.assertEqual(second.state['head'].value, 0)

    def test_a09_conditional_request_always_fresh_index(self):
        server = self.start()
        token = server.token()
        for path in ('/', '/index.html'):
            response = server.request(path, headers=[('Host', server.authority),
                ('If-None-Match', '*'), ('If-Modified-Since', 'Wed, 01 Jan 2031 00:00:00 GMT')])
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get('cache-control'), 'no-store')
            self.assertIn(token.encode(), response.body)
            self.assertFalse(any(k.startswith('access-control-allow-') for k in response.headers))

    def test_a09_api_success_and_failure_no_store(self):
        server = self.start()
        for response in (server.request('/api/health'), server.request('/api/tools'),
                         server.request('/api/events'), server.call(), server.call('absent')):
            self.assertEqual(response.headers.get('cache-control'), 'no-store')
            self.assertFalse(any(k.startswith('access-control-allow-') for k in response.headers))

    def test_a10_exact_byte_limit_accepted(self):
        server = self.start()
        body = canonical({'tool': 'read_sample', 'args': {'text': 'é'}})
        body += b' ' * (CAP - len(body))
        self.assertEqual(len(body), CAP)
        response = server.call(raw=body)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json()['untrusted']['text'], 'é')
        self.assertEqual(server.state['calls'].value, 1)

    def test_a10_next_byte_rejected(self):
        server = self.start()
        body = canonical({'tool': 'read_sample', 'args': {}})
        body += b' ' * (CAP + 1 - len(body))
        # Advertise without sending bytes; the cap must be checked before a read.
        response = server.call(raw=b'', headers=[('Host', server.authority),
            ('Content-Length', str(len(body))), ('Content-Type', 'application/json')])
        self.assert_error(response, 413)
        self.assertEqual(server.state['calls'].value, 0)

    def test_a10_huge_length_rejected_before_read(self):
        server = self.start()
        self.assert_error(server.call(raw=b'', headers=[('Host', server.authority),
            ('Content-Length', '999999999999999999999999'), ('Content-Type', 'application/json')]), 413)
        self.assertEqual(server.state['calls'].value, 0)

    def test_a11_truncated_body_closes(self):
        server = self.start()
        request = ('POST /api/call HTTP/1.1\r\nHost: ' + server.authority +
                   '\r\nContent-Type: application/json\r\nContent-Length: 128\r\n\r\n{').encode()
        response = server.raw(request, truncate=True)
        self.assert_error(response, 400)
        self.assertEqual(response.headers.get('connection', '').lower(), 'close')
        self.assertEqual(server.state['calls'].value, 0)

    def test_a11_stalled_sender_does_not_block_health(self):
        server = self.start(fast_timeouts=True)
        connection = socket.create_connection(('127.0.0.1', server.port), timeout=0.8)
        self.addCleanup(connection.close)
        connection.sendall(('POST /api/call HTTP/1.1\r\nHost: ' + server.authority +
            '\r\nContent-Type: application/json\r\nContent-Length: 50\r\n\r\n{').encode())
        self.assertEqual(server.request('/api/health').status, 200)
        # Test bound applies to this owned connection, not a new timeout option.
        connection.settimeout(1.5)
        import http.client
        response = http.client.HTTPResponse(connection)
        response.begin()
        data = response.read()
        self.assertEqual(response.status, 400)
        self.assertTrue(server.state['read_deadline'].is_set())
        self.assertEqual(response.headers.get('Connection', '').lower(), 'close')
        self.assertEqual(__import__('json').loads(data)['code'], 'bad_args')

    def test_a13_unicode_null_and_safe_integer_preserved(self):
        server = self.start()
        response = server.call(args={'text': None, 'count': SAFE})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json(), {'untrusted': {'text': None, 'count': SAFE, 'unknown': None}})
        self.assertEqual(response.body, canonical(response.json()))

    def test_a15_unknown_api_has_no_spa_fallback(self):
        server = self.start()
        for path in ('/api/absent', '/api/health/extra', '/api/scenario', '/api/healthx'):
            self.assert_error(server.request(path), 404)
        self.assertEqual(server.state['calls'].value, 0)

    def test_a19_cursor_pages_exact_head_and_resync(self):
        server = self.start(head=205)
        for after in (0, 100, 200, 205, 206):
            response = server.request('/api/events?after=' + str(after))
            self.assertEqual(response.status, 200)
            self.assertEqual(response.json(), {'untrusted': cursor(after, 205)})
        seen = [server.state['observed'].get(timeout=0.3) for _ in range(5)]
        for item in seen:
            self.assertEqual(item[0], 'ledger_events')
            self.assertEqual(item[1]['limit'], 100)
            self.assertEqual(item[1]['wait_ms'], 0)

    def test_a19_cursor_default_empty_prefix(self):
        response = self.start().request('/api/events')
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json(), {'untrusted': cursor()})

    def test_a19_filters_remain_available_via_post(self):
        server = self.start()
        response = server.call('ledger_events', {'after': 0, 'limit': 7, 'agent_id': 'sample-agent', 'kinds': ['run.beat']})
        self.assertEqual(response.status, 200)
        observed = server.state['observed'].get(timeout=0.3)
        self.assertEqual(observed[1]['limit'], 7)
        self.assertEqual(observed[1]['agent_id'], 'sample-agent')

    def test_a20_long_poll_allows_concurrent_read_and_advances(self):
        server = self.start()
        token = server.token()
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(server.request, '/api/events?after=0&wait_ms=30000')
            self.assertTrue(server.state['waiting'].wait(0.5), 'Poll did not enter shared read provider')
            self.assertEqual(server.request('/api/health').status, 200)
            self.assertEqual(server.call().status, 200)
            result = server.call('write_sample', {'agent': 'sample-agent', 'op_id': 'advance-1'}, protected=True)
            self.assertEqual(result.status, 200)
            response = pending.result(timeout=1)
        self.assertEqual(response.json()['untrusted']['head'], 1)
        self.assertEqual(response.json()['untrusted']['events'][0]['lamport'], 1)
        self.assertEqual(server.token(), token)

    def test_a20_long_poll_no_advancement_returns_fresh_cursor(self):
        server = self.start()
        result = server.request('/api/events?after=0&wait_ms=1')
        self.assertEqual(result.status, 200)
        self.assertEqual(result.json(), {'untrusted': cursor()})

    def test_a30_markup_is_json_data_and_never_index(self):
        server = self.start()
        text = '<script>SYNTHETIC_MARKUP</script>'
        response = server.call(args={'text': text})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json()['untrusted']['text'], text)
        self.assertEqual(response.headers.get('content-type', '').split(';')[0], 'application/json')
        self.assertNotIn(text.encode(), server.request('/').body)

    def test_a30_no_token_path_or_secret_in_observations(self):
        server = self.start()
        token = server.token()
        for path in ('/api/health', '/api/tools', '/api/events', '/api/absent'):
            self.assertNotIn(token.encode(), server.request(path).body)
        self.assert_error(server.call('unsafe'), 500, 'internal')
        log = repr(server.drain())
        for forbidden in (token, str(self.root), 'SYNTHETIC_SECRET'):
            self.assertNotIn(forbidden, log)

    def test_a31_bootstrap_preserves_ui_owned_markup(self):
        server = self.start()
        for route in ('#/agents', '#/agents/sample-agent', '#/lineage', '#/arena', '#/arena/bench_0001', '#/ledger'):
            # Fragments never travel on the HTTP wire; the supplied UI owns them.
            response = server.request(route.split('#', 1)[0] or '/')
            self.assertEqual(response.status, 200)
            self.assertIn(b'data-lin-screen="agents"', response.body)
            self.assertNotIn(b'data-lin-ready="true"', response.body)
            self.assertNotIn(b'data-lin-rev=', response.body)


def host_case(self, value):
    server = self.start()
    if value == 'missing':
        headers = []
    elif value == 'duplicate':
        headers = [('Host', server.authority), ('Host', server.authority)]
    elif value == 'forwarded':
        headers = [('Host', server.authority + '.extra'), ('X-Forwarded-Host', server.authority)]
    else:
        host = {'no_port': '127.0.0.1', 'other_port': '127.0.0.1:' + str(server.port + 1),
                'other_ip': '127.0.0.2:' + str(server.port), 'space': server.authority + ' ',
                'credentials': 'user@' + server.authority}[value]
        headers = [('Host', host)]
    for path in ('/', '/app.js', '/api/health', '/api/tools', '/api/absent'):
        self.assert_error(server.request(path, headers=headers), 403)
    body = canonical({'tool': 'read_sample', 'args': {}})
    self.assert_error(server.call(raw=body, headers=headers + [('Content-Type', 'application/json'), ('Content-Length', str(len(body)))]), 403)
    self.assertEqual(server.state['calls'].value, 0)


cases(HTTPTests, 'a04_wire_host', [(name, name) for name in
    ('missing', 'duplicate', 'forwarded', 'no_port', 'other_port', 'other_ip', 'space', 'credentials')], host_case)


def origin_case(self, kind):
    server = self.start()
    foreign = {'opaque': 'null', 'port': 'http://127.0.0.1:' + str(server.port + 1),
               'suffix': server.origin + '.extra', 'credentials': 'http://user@' + server.authority,
               'trailing': server.origin + '/', 'prefix': 'x' + server.origin}
    headers = [('Host', server.authority)]
    headers += [('Origin', server.origin), ('Origin', server.origin)] if kind == 'duplicate' else [('Origin', foreign[kind])]
    for method, path in (('GET', '/'), ('GET', '/api/tools'), ('OPTIONS', '/api/call')):
        self.assert_error(server.request(path, method=method, headers=headers), 403)
    body = canonical({'tool': 'read_sample', 'args': {}})
    self.assert_error(server.call(raw=body, headers=headers + [('Content-Type', 'application/json'), ('Content-Length', str(len(body)))]), 403)
    self.assertEqual(server.state['calls'].value, 0)


cases(HTTPTests, 'a05_wire_origin', [(name, name) for name in
    ('opaque', 'port', 'suffix', 'credentials', 'trailing', 'prefix', 'duplicate')], origin_case)


def framing(self, headers):
    server = self.start()
    data = ('POST /api/call HTTP/1.1\r\nHost: ' + server.authority + '\r\nContent-Type: application/json\r\n' +
            headers + '\r\n\r\n{}GET /api/health HTTP/1.1\r\nHost: ' + server.authority + '\r\n\r\n').encode()
    response = server.raw(data)
    self.assert_error(response, 400)
    self.assertEqual(response.headers.get('connection', '').lower(), 'close')
    self.assertEqual(server.state['calls'].value, 0)
    self.assertEqual(server.request('/api/health').status, 200)


cases(HTTPTests, 'a11_framing', [
    ('missing_length', ''), ('negative', 'Content-Length: -1'), ('fraction', 'Content-Length: 2.0'),
    ('letters', 'Content-Length: nope'), ('comma', 'Content-Length: 2, 2'),
    ('duplicate_equal', 'Content-Length: 2\r\nContent-Length: 2'),
    ('duplicate_conflict', 'Content-Length: 2\r\nContent-Length: 99'),
    ('chunked', 'Transfer-Encoding: chunked'),
    ('combined', 'Content-Length: 2\r\nTransfer-Encoding: chunked'),
    ('expect', 'Content-Length: 2\r\nExpect: 100-continue'),
    ('upgrade', 'Content-Length: 2\r\nUpgrade: websocket'),
    ('duplicate_type', 'Content-Length: 2\r\nContent-Type: application/json'),
], framing)


def content_type(self, value):
    media, status = value
    server = self.start()
    body = canonical({'tool': 'write_sample', 'args': {'agent': 'sample-agent', 'op_id': 'type-1'}})
    headers = [('Host', server.authority), ('Content-Length', str(len(body))), ('Origin', server.origin),
               ('X-Lineage-Session', server.token())]
    if media is not None:
        headers += [('Content-Type', media)]
    response = server.call(raw=body, headers=headers)
    if status == 200:
        self.assertEqual(response.status, 200)
        self.assertEqual(server.state['head'].value, 1)
    else:
        self.assert_error(response, status)
        self.assertEqual(server.state['calls'].value, 0)


cases(HTTPTests, 'a12_media', [
    ('json', ('application/json', 200)), ('case', ('APPLICATION/JSON', 200)),
    ('charset', ('application/json; charset=UTF-8', 200)),
    ('quoted_charset', ('application/json; charset="utf-8"', 200)),
    ('missing', (None, 415)), ('text', ('text/plain', 415)),
    ('form', ('application/x-www-form-urlencoded', 415)), ('other_charset', ('application/json; charset=latin-1', 415)),
], content_type)


def malformed_json(self, raw):
    server = self.start()
    self.assert_error(server.call(raw=raw), 400)
    self.assertEqual(server.state['calls'].value, 0)


cases(HTTPTests, 'a13_decode', [
    ('duplicate_nested', b'{"tool":"read_sample","args":{"text":"x","text":"y"}}'),
    ('duplicate_actor', b'{"tool":"read_sample","args":{"agent":"first","agent":"second"}}'),
    ('duplicate_op', b'{"tool":"write_sample","args":{"op_id":"one","op_id":"two"}}'),
    ('utf8', b'{"tool":"read_sample","args":{"text":"\xff"}}'),
    ('surrogate', b'{"tool":"read_sample","args":{"text":"\\ud800"}}'),
    ('nan', b'{"tool":"read_sample","args":{"count":NaN}}'),
    ('infinity', b'{"tool":"read_sample","args":{"count":Infinity}}'),
    ('overflow', b'{"tool":"read_sample","args":{"count":1e999}}'),
    ('trailing', b'{"tool":"read_sample","args":{}}{}'),
    ('boolean_integer', b'{"tool":"read_sample","args":{"count":true}}'),
    ('unsafe_integer', canonical({'tool': 'read_sample', 'args': {'count': SAFE + 1}})),
], malformed_json)
cases(HTTPTests, 'a14_shape', [(name, canonical(value)) for name, value in [
    ('array', []), ('scalar', 'text'), ('missing_tool', {'args': {}}), ('missing_args', {'tool': 'read_sample'}),
    ('wrong_tool', {'tool': 7, 'args': {}}), ('wrong_args', {'tool': 'read_sample', 'args': []}),
    ('unknown_tool', {'tool': 'absent', 'args': {}}),
    ('extra_context', {'tool': 'read_sample', 'args': {}, 'context': {}}),
    ('extra_authority', {'tool': 'read_sample', 'args': {}, 'authority': 'operator'}),
    ('extra_gate', {'tool': 'read_sample', 'args': {}, 'gate': True}),
    ('extra_effect', {'tool': 'read_sample', 'args': {}, 'effect': 'read'}),
    ('unknown_arg', {'tool': 'read_sample', 'args': {'gate': True}}),
    ('family', {'schema': 'lineage.family/1', 'id': 'sample_1', 'kind': 'call', 'payload': {'tool': 'read_sample', 'args': {}}}),
    ('rpc', {'jsonrpc': '2.0', 'method': 'tools/call', 'params': {'name': 'read_sample', 'arguments': {}}}),
]], malformed_json)


def method(self, value):
    verb, path, allow = value
    response = self.start().request(path, method=verb)
    # HEAD carries the status and headers but, per HTTP, no entity bytes.
    if verb == 'HEAD':
        self.assertEqual(response.status, 405)
        self.assertEqual(response.headers.get('cache-control'), 'no-store')
        self.assertEqual(response.headers.get('content-type', '').split(';')[0], 'application/json')
    else:
        self.assert_error(response, 405)
    self.assertEqual(response.headers.get('allow'), allow)


cases(HTTPTests, 'a15_method', [(verb.lower() + '_' + name, (verb, path, allow))
    for name, path, allow, verbs in [('call', '/api/call', 'POST', ('GET', 'HEAD', 'OPTIONS', 'PUT')),
        ('health', '/api/health', 'GET', ('POST', 'HEAD', 'OPTIONS')),
        ('tools', '/api/tools', 'GET', ('POST', 'OPTIONS')),
        ('events', '/api/events', 'GET', ('POST', 'OPTIONS')),
        ('index', '/', 'GET', ('POST', 'OPTIONS')),
        ('asset', '/app.js', 'GET', ('POST', 'OPTIONS'))]
    for verb in verbs], method)


def bad_query(self, query):
    server = self.start()
    self.assert_error(server.request('/api/events?' + query), 400)
    self.assertEqual(server.state['calls'].value, 0)


cases(HTTPTests, 'a19_query', [(name, value) for name, value in [
    ('empty', 'after='), ('negative', 'after=-1'), ('sign', 'after=%2B1'), ('space', 'after=%201'),
    ('leading_zero', 'after=01'), ('exponent', 'after=1e2'), ('float', 'after=1.0'),
    ('duplicate', 'after=0&after=1'), ('duplicate_wait', 'wait_ms=0&wait_ms=0'),
    ('unsafe', 'after=' + str(SAFE + 1)), ('wait_over', 'wait_ms=30001'),
    ('wait_negative', 'wait_ms=-1'), ('wait_empty', 'wait_ms='), ('limit', 'limit=1'),
    ('actor', 'agent=operator'), ('token', 'token=forged'), ('filter', 'kinds=run.close'),
    ('scenario', 'scenario=other'), ('directory', 'directory=other'), ('bad_percent', 'after=%xx'),
]], bad_query)


def forbidden_query(self, path):
    self.assert_error(self.start().request(path), 400)


cases(HTTPTests, 'a15_discovery_query', [('health', '/api/health?after=0'),
    ('tools', '/api/tools?scenario=other'), ('health_empty', '/api/health?'), ('tools_empty', '/api/tools?')], forbidden_query)
