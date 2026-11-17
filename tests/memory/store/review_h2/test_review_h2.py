"""Regression coverage for U11 seams across integrated provider refreshes."""
from unittest import mock

from lineage.core import app, journal, mcp, registry
from lineage.domain.memory import schema, store, units
from tests.memory.store import AGENT, OracleCase, unit_record
from tests.memory.store import test_memory_resume as fixtures


class ProviderRefreshTests(OracleCase):
    # A-U11: reuse integrated transaction fixtures, without inheriting test cases.
    transaction_context = fixtures.MemoryResumeOracle.transaction_context
    command = fixtures.MemoryResumeOracle.command

    def refresh_provider(self):
        # Model the provider generation installed by a newly loaded transport.
        native_main = getattr(mcp.main, '_lineage_native', mcp.main)
        with mock.patch.object(mcp, 'main', native_main):
            schema._sync_boundary()

    def test_refresh_retains_postcommit_publication_and_exact_replay(self):
        self.publish()
        ctx = self.transaction_context()
        candidate = unit_record('Review001', 'refresh preserves publication', level=2)
        command = self.command(registry, candidate, 'review-refresh')
        self.refresh_provider()
        with mock.patch.object(store, 'rebuild', wraps=store.rebuild) as publish:
            first = units.put(AGENT, candidate, command=command, ctx=ctx)
            raw = self.ledger.read_bytes()
            self.refresh_provider()
            replay = units.put(AGENT, candidate, command=command, ctx=ctx)
        self.assertEqual(publish.call_count, 2)
        self.assertEqual(first.value, replay.value)
        self.assertEqual(self.ledger.read_bytes(), raw)
        self.assertEqual(store.verify_projection(AGENT, snapshot=journal.snapshot(ctx=ctx),
                                                 ctx=ctx), ())

    def test_refresh_retains_defaults_and_boot_error_detail(self):
        self.refresh_provider()
        before = self.disk_tree()
        result = app.dispatch('memory_route', {'agent_id': AGENT, 'query': 'needle'},
                              ctx=self.ctx)
        self.assertEqual(result, {'untrusted': {'units': [], 'answer': 'NOT IN MEMORY',
                                               'head': self.snapshot.head}})
        malformed = app.dispatch('memory_bootcheck', {'agent_id': AGENT, 'observed': {}},
                                 ctx=self.ctx)
        self.assertIs(malformed['ok'], False)
        self.assertEqual(malformed['code'], 'bad_args')
        self.assertTrue(malformed['detail'].startswith('E_BOOTCHECK'))
        absent = app.dispatch('memory_route', {'agent_id': 'agent-absent', 'query': 'needle'},
                              ctx=self.ctx)
        self.assertEqual(absent['code'], 'no_agent')
        self.assertEqual(self.disk_tree(), before)
