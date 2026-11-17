"""A26–A29: manifest admission and fixture-only reads, never a live fallback."""
from pathlib import Path

from tests.serve._support import (
    LineageError, ServerCase, canonical, cases, cursor, decode, fixture, rehash, snapshot,
)


class FixtureTests(ServerCase):
    def setUp(self):
        super().setUp()
        self.fixtures = fixture(self.root)

    def manifest(self, **changes):
        path = self.fixtures / 'manifest.json'
        value = decode(path.read_bytes())
        value.update(changes)
        path.write_bytes(canonical(value))

    def test_a26_empty_synthetic_manifest_admission(self):
        server = self.start(fixtures=True, forbid_live=True)
        self.assertEqual(server.request('/api/health').json(),
            {'ok': True, 'protocol': 'lineage.family/1', 'head': 0, 'fixtures': True})
        self.assertEqual(server.state['live'].value, 0)

    def test_a27_effective_args_lookup_and_detached_discovery(self):
        before = snapshot(self.root / 'home')
        server = self.start(fixtures=True, forbid_live=True)
        response = server.call('agent_list')
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json(), {'untrusted': {'agents': [], 'next_after': None, 'head': 0}})
        self.assertEqual(server.call('agent_list', {'agent': 'system', 'include_retired': False, 'limit': 100}).body, response.body)
        from tests.serve._support import list_tools, make_context
        expected = list_tools(ctx=make_context(self.root, server.state, {}))
        self.assertEqual(server.request('/api/tools').json(), {'tools': expected})
        self.assertEqual(server.state['live'].value, 0)
        self.assertEqual(server.state['home_access'].value, 0)
        self.assertEqual(server.state['registry_changes'].value, 0)
        self.assertEqual(snapshot(self.root / 'home'), before)

    def test_a27_missing_read_case_never_calls_live(self):
        server = self.start(fixtures=True, forbid_live=True)
        self.assert_error(server.call('agent_list', {'limit': 7}), 400)
        self.assertEqual(server.state['live'].value, 0)
        self.assertEqual(server.state['home_access'].value, 0)

    def test_a27_clock_and_cwd_do_not_change_fixture_read(self):
        before = snapshot(self.fixtures)
        server = self.start(fixtures=True, forbid_live=True)
        responses = [server.call('agent_list').body for _ in range(2)]
        self.assertEqual(responses[0], responses[1])
        self.assertEqual(snapshot(self.fixtures), before)
        self.assertEqual(server.state['live'].value, 0)
        self.assertEqual(server.state['home_access'].value, 0)

    def test_a28_refusal_precedes_token_and_lookup(self):
        before = snapshot(self.root)
        server = self.start(fixtures=True, forbid_live=True)
        response = server.call('write_sample', {'agent': 'operator', 'op_id': 'fixture-write-1'})
        self.assert_error(response, 403, 'fixture_readonly')
        self.assertEqual(server.state['live'].value, 0)
        self.assertEqual(snapshot(self.root), before)
        self.assert_error(server.call('unknown_sample', {'agent': 'operator'}), 400)
        self.assert_error(server.call(raw=b'{}'), 400)

    def test_a28_host_and_origin_precede_readonly(self):
        server = self.start(fixtures=True, forbid_live=True)
        body = canonical({'tool': 'write_sample', 'args': {'agent': 'sample-agent', 'op_id': 'fixture-1'}})
        headers = [('Host', server.authority), ('Origin', 'null'),
                   ('Content-Type', 'application/json'), ('Content-Length', str(len(body)))]
        self.assert_error(server.call(raw=body, headers=headers), 403, 'bad_args')
        self.assertEqual(server.state['live'].value, 0)

    def test_a29_fixture_health_cursor_and_immediate_wait(self):
        before = snapshot(self.fixtures)
        server = self.start(fixtures=True, forbid_live=True, head=23)
        self.assertEqual(server.request('/api/health').json()['head'], 0)
        self.assertIs(server.request('/api/health').json()['fixtures'], True)
        for target, expected in [('/api/events', cursor()),
                ('/api/events?after=1', cursor(1)),
                ('/api/events?after=0&wait_ms=30000', cursor())]:
            response = server.request(target)
            self.assertEqual(response.status, 200)
            self.assertEqual(response.json(), {'untrusted': expected})
        self.assertEqual(server.state['live'].value, 0)
        self.assertEqual(server.state['home_access'].value, 0)
        self.assertFalse(server.state['waiting'].is_set())
        self.assertEqual(snapshot(self.fixtures), before)

    def test_a29_no_scenario_or_directory_api(self):
        before = snapshot(self.root)
        server = self.start(fixtures=True, forbid_live=True)
        self.assert_error(server.request('/api/events?scenario=other'), 400)
        self.assert_error(server.request('/api/health?directory=other'), 400)
        self.assert_error(server.request('/api/scenario'), 404)
        self.assertEqual(snapshot(self.root), before)

    def test_a29_index_query_never_selects_dataset(self):
        server = self.start(fixtures=True, forbid_live=True)
        for path in ('/?scenario=other', '/index.html?directory=other'):
            response = server.request(path)
            self.assertIn(response.status, (200, 400))
            if response.status == 400:
                self.assert_error(response, 400)
            else:
                self.assertIn(server.token().encode(), response.body)
        self.assertEqual(server.request('/api/health').json()['head'], 0)
        self.assertIs(server.request('/api/health').json()['fixtures'], True)


def invalid_manifest(self, value):
    label, expected = value
    if label == 'missing_manifest':
        (self.fixtures / 'manifest.json').unlink()
    elif label == 'missing_inventory_file':
        (self.fixtures / 'agents.json').unlink()
    elif label == 'version':
        self.manifest(fixture_version=2)
    elif label == 'boolean_version':
        self.manifest(fixture_version=True)
    elif label == 'unknown_metadata':
        self.manifest(extra=True)
    elif label == 'unknown_clock':
        path = self.fixtures / 'clock.json'
        path.write_bytes(canonical({**decode(path.read_bytes()), 'extra': True}))
        rehash(self.fixtures)
    elif label == 'capture_shape':
        self.manifest(capture={'device_scale_factor': 1})
    elif label == 'artifact_hash':
        (self.fixtures / 'artifacts/lesson.txt').write_bytes(b'Altered synthetic bytes')
    elif label == 'duplicate_response':
        path = self.fixtures / 'responses.json'
        value = decode(path.read_bytes())
        path.write_bytes(canonical(value + value))
        rehash(self.fixtures)
    elif label == 'mutation_response':
        path = self.fixtures / 'responses.json'
        value = decode(path.read_bytes())
        value.append({'tool': 'write_sample', 'args': {'agent': 'sample-agent', 'op_id': 'forged-1'}, 'data': {}})
        path.write_bytes(canonical(value))
        rehash(self.fixtures)
    elif label == 'export_response':
        path = self.fixtures / 'responses.json'
        path.write_bytes(canonical([{'tool': 'ledger_export', 'args': {'agent': 'system', 'out': 'exports/sample'}, 'data': {}}]))
        rehash(self.fixtures)
    elif label == 'unknown_response':
        path = self.fixtures / 'responses.json'
        path.write_bytes(canonical([{'tool': 'unknown_sample', 'args': {}, 'data': {}}]))
        rehash(self.fixtures)
    elif label == 'unvalidated_args':
        path = self.fixtures / 'responses.json'
        path.write_bytes(canonical([{'tool': 'agent_list', 'args': {'agent': 'system', 'include_retired': False, 'limit': True}, 'data': {}}]))
        rehash(self.fixtures)
    elif label == 'inventory_escape':
        value = decode((self.fixtures / 'manifest.json').read_bytes())
        value['files'][0]['path'] = '../outside/theme.css'
        self.manifest(files=value['files'])
    elif label == 'symlink':
        target = self.fixtures / 'artifacts/lesson.txt'
        target.unlink()
        target.symlink_to(self.root / 'outside/theme.css')
        rehash(self.fixtures)
    elif label == 'unlisted':
        (self.fixtures / 'unlisted.json').write_bytes(b'{}')
    elif label == 'unknown_event_field':
        (self.fixtures / 'events.jsonl').write_bytes(b'{"schema":"lineage.event/v1","extra":true}\n')
        rehash(self.fixtures)
    elif label == 'wrong_agent_shape':
        (self.fixtures / 'agents.json').write_bytes(b'[{"schema":"lineage.agent/v1","id":false}]')
        rehash(self.fixtures)
    elif label == 'inconsistent_head':
        self.manifest(head=1)
    elif label == 'unresolved_baseline':
        self.manifest(baseline='scenarios/missing.json')
    with self.assertRaises(LineageError) as caught:
        self.start(fixtures=True, forbid_live=True)
    self.assertIn(caught.exception.code, expected if isinstance(expected, tuple) else (expected,))


cases(FixtureTests, 'a26_invalid', [(name, (name, code)) for name, code in [
    ('missing_manifest', 'bad_args'), ('missing_inventory_file', 'bad_args'),
    ('version', 'bad_args'), ('boolean_version', 'bad_args'), ('unknown_metadata', 'bad_args'),
    ('unknown_clock', 'bad_args'), ('capture_shape', 'bad_args'), ('artifact_hash', 'hash_mismatch'),
    ('duplicate_response', 'bad_args'), ('mutation_response', 'bad_args'), ('export_response', 'bad_args'),
    ('unknown_response', 'bad_args'), ('unvalidated_args', 'bad_args'), ('inventory_escape', 'bad_args'),
    ('symlink', 'bad_args'), ('unlisted', 'bad_args'), ('unknown_event_field', 'bad_args'),
    ('wrong_agent_shape', 'bad_args'), ('inconsistent_head', ('bad_args', 'hash_mismatch')), ('unresolved_baseline', 'bad_args'),
]], invalid_manifest)


def writes(self, value):
    tool, credentials = value
    before = snapshot(self.root)
    server = self.start(fixtures=True, forbid_live=True)
    args = {'out': 'exports/sample'} if tool == 'ledger_export' else {'agent': 'operator', 'op_id': 'fixture-write-2'}
    self.assert_error(server.call(tool, args, protected=credentials), 403, 'fixture_readonly')
    self.assertEqual(server.state['live'].value, 0)
    self.assertEqual(server.state['home_access'].value, 0)
    self.assertEqual(snapshot(self.root), before)


cases(FixtureTests, 'a28_write', [(tool + ('_valid_token' if token else '_no_token'), (tool, token))
    for tool in ('write_sample', 'external_sample', 'ledger_export') for token in (False, True)], writes)
