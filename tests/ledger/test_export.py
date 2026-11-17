"""Contract manifest parity, reproducibility, rebuilt scorecards and confinement."""
import hashlib
from lineage.core import export, journal
from tests.ledger._support import LedgerCase


class ExportTests(LedgerCase):
    def test_library_dispatch_and_cli_return_identical_manifest(self):
        self.append()
        args = {'out': 'exports/check', 'agent': 'caller'}
        before = (self.home / 'ledger/main/events.jsonl').read_bytes()
        value = self.data('ledger_export', args)
        self.check_result('ledger_export', value)
        self.assertEqual(export.export_ledger(self.home, out=args['out']), value)
        self.assertEqual(self.cli('ledger_export', args), {'untrusted': value})
        for entry in value['manifest']:
            content = (self.home / args['out'] / entry['path']).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), entry['sha256'])
        self.assertEqual((self.home / args['out'] / 'ledger/main/events.jsonl').read_bytes(), before)
        self.assertEqual((self.home / 'ledger/main/events.jsonl').read_bytes(), before)

    def test_empty_journal_exports(self):
        self.check_result('ledger_export', self.data('ledger_export', {'out': 'exports/empty'}))

    def test_export_rebuilds_scorecard_from_schema_record_payloads(self):
        self.birth()
        self.close(cost={'cost_micro_usd': 9007199254740991})
        self.close(cost={'cost_micro_usd': 9007199254740991})
        from lineage.domain import scorecard
        path = self.home / 'agents/develop/python/agent-one/scorecard.json'
        path.parent.mkdir(parents=True)
        # No materialized scorecard is required: export must rebuild it.
        value = self.data('ledger_export', {'out': 'exports/agents'})
        self.check_result('ledger_export', value)
        projected = self.home / value['out'] / 'projections/scorecards.json'
        self.assertTrue(projected.is_file())
        self.assertFalse(path.exists())
        expected = scorecard.projection_bytes(journal.snapshot(self.home), agent_id='agent-one')
        self.assertEqual((self.home / value['out'] / path.relative_to(self.home)).read_bytes(), expected)
        self.assertEqual(self.cli('ledger_export', {'out': value['out']}), {'untrusted': value})

    def test_stale_projection_is_rebuilt_without_changing_source_cache(self):
        self.birth()
        path = self.home / 'agents/develop/python/agent-one/scorecard.json'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'{}\n')
        value = self.data('ledger_export', {'out': 'exports/rebuilt'})
        self.check_result('ledger_export', value)
        self.assertEqual(path.read_bytes(), b'{}\n')
        self.assertNotEqual((self.home / value['out'] / path.relative_to(self.home)).read_bytes(), b'{}\n')
        self.assertEqual(self.cli('ledger_verify', {}, 3)['code'], 'hash_mismatch')

    def test_unsafe_paths_symlinks_and_changed_destinations_refused(self):
        for out in ('../escape', 'exports//bad', 'exports/../bad', 'outside/result'):
            result = self.dispatch('ledger_export', {'out': out})
            self.assertEqual(result.payload['code'], 'bad_args', result.payload)
        target = self.home / 'target'
        target.mkdir()
        (self.home / 'exports').symlink_to(target, target_is_directory=True)
        self.assertEqual(self.dispatch('ledger_export', {'out': 'exports/bad'}).payload['code'], 'bad_args')
        (self.home / 'exports').unlink()
        self.data('ledger_export', {'out': 'exports/fixed'})
        self.append()
        self.assertEqual(self.cli('ledger_export', {'out': 'exports/fixed'}, 3)['code'], 'conflict')

    def test_corrupt_authority_returns_string_error_instead_of_internal(self):
        self.append()
        path = self.home / 'ledger/main/events.jsonl'
        path.write_bytes(path.read_bytes().replace(b'working', b'changed'))
        result = self.dispatch('ledger_export', {'out': 'exports/corrupt'})
        self.assertEqual(result.payload['code'], 'hash_mismatch')
        self.assertIsInstance(result.payload['detail'], str)
        self.assertEqual(self.cli('ledger_export', {'out': 'exports/corrupt'}, 3), result.payload)
