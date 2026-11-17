"""Contract verification results and bounded string diagnostics."""
from tests.ledger._support import LedgerCase


class VerifyTests(LedgerCase):
    def test_empty_and_populated_reports_match_result_schema_and_cli(self):
        for populated in (False, True):
            if populated:
                self.append()
            value = self.data('ledger_verify', {'agent': 'caller'})
            self.check_result('ledger_verify', value)
            self.assertTrue(value['valid'])
            self.assertEqual(value['head'], int(populated))
            self.assertIsNone(value['sha256']) if not populated else self.assertEqual(len(value['sha256']), 64)
            self.assertEqual(value['issues'], [])
            self.assertEqual(self.cli('ledger_verify', {}), {'untrusted': value})

    def test_torn_tail_is_warning_not_corruption_and_does_not_modify_history(self):
        self.append()
        path = self.home / 'ledger/main/events.jsonl'
        raw = path.read_bytes() + b'{"unfinished"'
        path.write_bytes(raw)
        value = self.data('ledger_verify', {})
        self.check_result('ledger_verify', value)
        self.assertEqual(value['torn_tail_bytes'], len(b'{"unfinished"'))
        self.assertEqual(value['issues'][0]['code'], 'torn_tail')
        self.assertEqual(self.cli('ledger_verify', {}), {'untrusted': value})
        self.assertEqual(path.read_bytes(), raw)

    def test_tamper_reports_relative_coordinate_as_string(self):
        self.append()
        path = self.home / 'ledger/main/events.jsonl'
        path.write_bytes(path.read_bytes().replace(b'working', b'changed'))
        result = self.dispatch('ledger_verify', {})
        self.assertEqual(result.payload['code'], 'hash_mismatch')
        self.assertIsInstance(result.payload['detail'], str)
        self.assertIn('ledger/main/events.jsonl:1', result.payload['detail'])
        self.assertLessEqual(len(result.payload['detail']), 2048)
        self.assertEqual(self.cli('ledger_verify', {}, 3), result.payload)

    def test_expected_head_is_not_a_public_argument(self):
        self.assertEqual(self.cli('ledger_verify', {'expected_head': {}}, 2)['code'], 'bad_args')

    def test_projection_drift_and_unverified_cache_not_certified(self):
        self.birth()
        from lineage.core import journal
        from lineage.domain import scorecard
        path = self.home / 'agents/develop/python/agent-one/scorecard.json'
        path.parent.mkdir(parents=True)
        from lineage.core.export import _agent_files
        for relative, raw in _agent_files(journal.snapshot(self.home)).items():
            (self.home / relative).write_bytes(raw)
        (path.parent / 'opaque.json').write_bytes(b'opaque cache')
        self.check_result('ledger_verify', self.data('ledger_verify', {}))
        path.write_bytes(b'{}\n')
        result = self.dispatch('ledger_verify', {})
        self.assertEqual(result.payload['code'], 'hash_mismatch')
        self.assertIsInstance(result.payload['detail'], str)
        self.assertIn('scorecard.json', result.payload['detail'])
        self.assertEqual(self.cli('ledger_verify', {}, 3), result.payload)
