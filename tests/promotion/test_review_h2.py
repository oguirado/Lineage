"""Promotion metadata stays consistent across integrated projection readers."""
from copy import deepcopy
import json
import unittest
from types import SimpleNamespace

from lineage.core import envelope, family, journal
from lineage.domain import agents, layout, promotion
from lineage.domain.memory import fold as memory_fold, store
from tests.promotion.test_evaluate import CHILD, SELECT, SEAT, Fixture
from tests.promotion import test_transaction as transaction_helpers


class ReviewH2Tests(unittest.TestCase):
    def setUp(self):
        # A-U19: reuse real integrated owner fixtures without replacing validators.
        self.fixture = transaction_helpers.TransactionTests("test_a28_synthetic_lifecycle_integration_prerequisites")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_status_seat_refreshes_agent_and_memory_projections(self):
        # A-U19: A-LAY1 requires the installed materializer and canonical layout.
        fixture = self.fixture
        fixture.seed_selection()
        result, args, event = fixture.commit_promotion()
        before = fixture.ledger_bytes()
        prefix = journal.snapshot(fixture.context.home)
        record = fixture.public("agent_get", {"agent_id": CHILD})["record"]
        directory = layout.agent_dir(fixture.context.home, workflow=record["workflow"],
                                     language=record["language"], agent_id=CHILD)
        self.assertEqual(json.loads((directory / "agent.json").read_bytes()), record)
        self.assertEqual(record["status"], "shadow")
        self.assertEqual(record["promoted_seat"], SEAT)
        memory = directory / "memory"
        current = (memory / "CURRENT").read_text().strip()
        manifest = json.loads((memory / current / "manifest.json").read_bytes())
        self.assertEqual(manifest["source_head"], event["lamport"])
        self.assertEqual(manifest["agent_version"], record["agent_version"])
        memory_state = {}
        for item in prefix:
            memory_fold.apply(memory_state, item)
        before_state = deepcopy(memory_state)
        historical = store._agent_at(CHILD, prefix, memory_state)
        self.assertEqual(historical["status"], record["status"])
        self.assertEqual(historical["promoted_seat"], record["promoted_seat"])
        self.assertEqual(historical["agent_version"], record["agent_version"])
        self.assertEqual(memory_state, before_state)
        agents.refresh_projections(CHILD, ctx=fixture.context)
        replay = fixture.public("agent_promote", dict(args, expected_head=0))
        self.assertEqual(replay, result)
        self.assertEqual(fixture.ledger_bytes(), before)
        self.assertEqual(journal.snapshot(fixture.context.home), prefix)

    def test_reader_adapters_expose_sticky_retirement_without_mutating_state(self):
        # A-U19: U12/U11 reader APIs consume the U19 namespace, not new wire fields.
        # The existing pure retirement fixture preserves valid open/close witnesses.
        fixture = Fixture().shadow()
        for verdict in ("error", "HOLD", "red"):
            fixture.run(verdict=verdict)
        events = fixture.history()
        state = {}
        for event in events:
            promotion.apply(state, event)
        native = deepcopy(events[1]["payload"]["record"])
        native.update(status="shadow", promoted_seat=dict(SEAT))
        state["agents"] = {CHILD: native}
        before = deepcopy(state)
        record = agents._record(state, CHILD)
        self.assertEqual(record["status"], "retired")
        self.assertNotIn("promoted_seat", record)
        self.assertEqual(state, before)
        record["status"] = "draft"
        self.assertEqual(agents._record(state, CHILD)["status"], "retired")

    def test_committed_birth_status_is_preserved_by_readers(self):
        # A-U19: the integrated readers must preserve captured owner records.
        fixture = Fixture()
        fixture.events[1]["payload"]["record"]["status"] = "retired"
        events = fixture.history()
        state = {}
        for event in events:
            promotion.apply(state, event)
        state["agents"] = {CHILD: deepcopy(events[1]["payload"]["record"])}
        before = deepcopy(state)
        self.assertEqual(agents._record(state, CHILD)["status"], "retired")
        self.assertEqual(state, before)

    def test_family_witness_requires_prefix_digest_and_native_operation_ownership(self):
        # A-U19: adapt only digest representation; preserve all native witness checks.
        fixture = self.fixture
        fixture.seed_selection()
        request = {"schema": "lineage.family/1", "source": "oracle-source",
                   "target": "oracle-target", "id": "witness_h2", "kind": "call",
                   "agent": "creator-agent", "payload": {"tool": "agent_promote",
                       "args": {"agent_id": CHILD, "bench_id": SELECT}}}
        result, args, event = fixture.commit_promotion(op_id=envelope.operation_id(request))
        mailbox = family.Mailbox.__new__(family.Mailbox)
        mailbox.runtime = SimpleNamespace(context=fixture.context, registry=fixture.registry)
        wrapped = {"untrusted": result}
        before = deepcopy(wrapped)
        mailbox._witness(request, wrapped, "agent_promote")
        self.assertEqual(wrapped, before)
        for changes in ({"sha256": "0" * 64}, {"sha256": event["sha256"]},
                        {"head": event["lamport"] + 1}, {"event_ids": []}):
            with self.subTest(changes=changes):
                corrupt = deepcopy(wrapped)
                corrupt["untrusted"]["commit"].update(changes)
                with self.assertRaises(family.RecoveryError):
                    mailbox._witness(request, corrupt, "agent_promote")
        with self.assertRaises(family.RecoveryError):
            mailbox._witness(dict(request, agent="another-agent"), wrapped, "agent_promote")
        fixture.mutation("agent_retire", {"agent_id": CHILD, "reason": "synthetic witness replay"})
        mailbox._witness(request, wrapped, "agent_promote")
        self.assertEqual(fixture.public("agent_promote", args), result)
