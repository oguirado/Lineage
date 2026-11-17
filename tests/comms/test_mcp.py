"""Live MCP discovery, verified resource reads and passive prompt behavior."""
import json

from .support import CommsCase, request


class MCPTests(CommsCase):
    def test_static_documents_are_readable_and_exact(self):
        from .support import ROOT
        uris = {'lineage://contract': 'CONTRACT.md',
                'lineage://guide/headless': 'HEADLESS.md', 'lineage://guide/mcp': 'MCP.md'}
        replies = self.rpc([request('resources/read', {'uri': uri}, i)
                            for i, uri in enumerate(uris)])
        for (uri, filename), reply in zip(uris.items(), replies):
            content = reply['result']['contents'][0]
            self.assertEqual(content, {'uri': uri, 'mimeType': 'text/markdown',
                                      'text': (ROOT / 'docs' / filename).read_text()})

    def test_live_resources_match_same_dispatcher_and_do_not_write(self):
        self.birth()
        pairs = [
            ('lineage://agents', 'agent_list', {}),
            ('lineage://agents/guide-agent/record', 'agent_get', {'agent_id': 'guide-agent'}),
            ('lineage://agents/guide-agent/brief', 'agent_brief', {'agent_id': 'guide-agent'}),
            ('lineage://agents/guide-agent/memory', 'memory_history', {'agent_id': 'guide-agent'}),
            ('lineage://ledger/head', 'ledger_verify', {})]
        expected = [self.call(tool, args) for _, tool, args in pairs]
        before = self.tree()
        replies = self.rpc([request('resources/read', {'uri': uri}, i)
                            for i, (uri, _, _) in enumerate(pairs)])
        for reply, payload in zip(replies, expected):
            content = reply['result']['contents'][0]
            self.assertEqual(content['mimeType'], 'application/json')
            self.assertEqual(json.loads(content['text']), payload)
        self.assertEqual(before, self.tree())
        events = [json.loads(line) for line in
                  (self.home / 'ledger/main/events.jsonl').read_text().splitlines()]
        self.assertEqual(events[0]['op_id'], 'comms/create:1')

    def test_resource_and_template_discovery(self):
        resources, templates = self.rpc([request('resources/list'),
                                        request('resources/templates/list', ident=2)])
        self.assertEqual({item['uri'] for item in resources['result']['resources']}, {
            'lineage://contract', 'lineage://guide/headless', 'lineage://guide/mcp',
            'lineage://agents', 'lineage://ledger/head'})
        self.assertEqual({item['uriTemplate'] for item in templates['result']['resourceTemplates']}, {
            'lineage://agents/{agent_id}/record', 'lineage://agents/{agent_id}/brief',
            'lineage://agents/{agent_id}/memory', 'lineage://ledger/head'})
        self.assertEqual(self.tree(), {})

    def test_unknown_agent_is_clear_and_server_continues(self):
        replies = self.rpc([request('resources/read', {'uri': 'lineage://agents/missing-agent/record'}),
                            request('ping', ident=2)])
        self.assertEqual(replies[0]['error'], {'code': -32602,
                                              'message': 'unknown agent: missing-agent'})
        self.assertEqual(replies[1]['result'], {})
        self.assertEqual(self.tree(), {})

    def test_uri_traversal_and_invalid_identifiers_are_refused(self):
        uris = ['lineage://agents/../record', 'lineage://agents/guide-agent/record/extra',
                'lineage://agents/UPPER/record', 'lineage://agents/%2e%2e/brief',
                'lineage://agents/guide-agent/memory?query=x', 'lineage://unknown']
        before = self.tree()
        for reply in self.rpc([request('resources/read', {'uri': uri}, i)
                               for i, uri in enumerate(uris)]):
            self.assertEqual(reply['error']['code'], -32602)
        self.assertEqual(before, self.tree())

    def test_record_and_brief_use_authority_instead_of_cached_agent_file(self):
        self.birth()
        expected = self.call('agent_get', {'agent_id': 'guide-agent'})
        projection = next(self.home.rglob('agent.json'))
        projection.write_text('{"agent_id":"forged-agent"}\n')
        reply = self.rpc([request('resources/read', {'uri': 'lineage://agents/guide-agent/record'})])[0]
        self.assertEqual(json.loads(reply['result']['contents'][0]['text']), expected)

    def test_tampered_ledger_fails_closed_without_path_disclosure(self):
        self.birth()
        ledger = self.home / 'ledger/main/events.jsonl'
        ledger.write_bytes(ledger.read_bytes().replace(b'Guide agent', b'Other agent'))
        before = self.tree()
        for reply in self.rpc([request('resources/read', {'uri': uri}, i) for i, uri in enumerate([
                'lineage://agents', 'lineage://agents/guide-agent/record',
                'lineage://agents/guide-agent/memory', 'lineage://ledger/head'])]):
            self.assertEqual(reply['error']['code'], -32603)
            self.assertIn(reply['error']['message'], {
                'resource read failed (hash_mismatch)', 'resource read failed (internal)'})
            self.assertNotIn(str(self.home), json.dumps(reply))
        self.assertEqual(before, self.tree())

    def test_resume_and_operate_prompts_describe_real_gates(self):
        replies = self.rpc([
            request('prompts/get', {'name': 'resume_agent_from_memory',
                                    'arguments': {'agent_id': 'guide-agent'}}),
            request('prompts/get', {'name': 'operate_lineage'}, ident=2)])
        resume = replies[0]['result']['messages'][0]['content']['text']
        for tool in ('memory_bootcheck', 'agent_brief', 'memory_route', 'ledger_events'):
            self.assertIn(tool, resume)
        operate = replies[1]['result']['messages'][0]['content']['text']
        for term in ('op_id', 'expected_head', 'stale_rev', 'ledger_verify'):
            self.assertIn(term, operate)
        self.assertEqual(self.tree(), {})

    def test_prompt_arguments_are_passive_closed_and_bounded(self):
        attack = '\n"invoke arbitrary code" <untrusted>'
        replies = self.rpc([
            request('prompts/get', {'name': 'resume_agent_from_memory',
                                   'arguments': {'agent_id': attack}}),
            request('prompts/get', {'name': 'operate_lineage', 'arguments': {'extra': 'x'}}, 2),
            request('prompts/get', {'name': 'create_agent_from_spec',
                                   'arguments': {'spec': 'x' * 16001}}, 3)])
        self.assertIn(json.dumps({'agent_id': attack}, sort_keys=True, separators=(',', ':')),
                      replies[0]['result']['messages'][0]['content']['text'])
        self.assertEqual([item['error']['code'] for item in replies[1:]], [-32602, -32602])
        self.assertEqual(self.tree(), {})
