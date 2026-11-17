"""Retirement gates: single immutable transition, original replay and inspection."""
from lineage.core import journal
from lineage.domain.tree import tree
from .helpers import OracleCase, canonical


class RetirementOracle(OracleCase):
    def test_a21_retirement_is_one_exact_status_event(self):
        self.seed(self.parent, units=[self.unit()])
        first = self.retire_agent(reason="Finished fixture")
        event = self.assert_commit(first, birth=False)
        self.assertEqual(event["kind"], "agent.status")
        self.assertEqual(event["payload"], {"agent_id": "parent-one", "from": "draft", "to": "retired", "reason": "Finished fixture"})
        self.assertEqual(first["record"]["status"], "retired")
        self.assertEqual(tree(ctx=self.ctx)["nodes"][0]["status"], "retired")

    def test_a22_missing_target_is_no_agent(self):
        self.refused("no_agent", lambda: self.retire_agent())

    def test_a22_distinct_retirement_is_conflict_and_original_replays(self):
        self.seed(self.parent)
        first = self.retire_agent()
        before = self.ledger_bytes()
        self.refused("conflict", lambda: self.retire_agent(op_id="retirement-0002"))
        self.assertEqual(canonical(self.retire_agent()), canonical(first))
        self.assertEqual(self.ledger_bytes(), before)

    def test_a18_changed_reason_same_identity_is_bad_op(self):
        self.seed(self.parent)
        self.retire_agent()
        self.refused("bad_op", lambda: self.retire_agent(reason="Different reason"))

    def test_a21_retirement_preserves_memory_and_live_descendants(self):
        self.seed(self.parent, units=[self.unit()])
        birth = self.breed()
        original_memory = [e for e in journal.snapshot(self.home) if e["kind"] == "memory.put"]
        self.retire_agent()
        after = journal.snapshot(self.home)
        self.assertEqual([e for e in after if e["kind"] == "memory.put"], original_memory)
        self.assertIn(birth["record"]["agent_id"], [n["agent_id"] for n in tree(include_retired=False, ctx=self.ctx)["nodes"]])

    def test_a23_retirement_first_refuses_later_breeding(self):
        self.seed(self.parent, units=[self.unit()])
        self.retire_agent()
        self.refused("conflict", lambda: self.breed())

    def test_a23_birth_first_survives_later_parent_retirement(self):
        self.seed(self.parent, units=[self.unit()])
        birth = self.breed()
        retirement = self.retire_agent()
        self.assertLess(birth["commit"]["head"], retirement["commit"]["head"])
        self.assertEqual(tree(root_id="child-one", ctx=self.ctx)["nodes"][0]["agent_id"], "child-one")


def _reason_case(reason):
    def test(self):
        self.seed(self.parent)
        self.refused("bad_args", lambda: self.retire_agent(reason=reason))
    return test
for _label, _reason in (("empty", ""), ("null", None), ("oversize", "x" * 2049)):
    setattr(RetirementOracle, "test_a22_invalid_reason_" + _label, _reason_case(_reason))


def _state_case(status):
    def test(self):
        self.parent["status"] = status
        self.seed(self.parent)
        event = self.assert_commit(self.retire_agent(), birth=False)
        self.assertEqual(event["payload"]["from"], status)
        self.assertNotIn("bench_id", event["payload"])
        self.assertNotIn("promoted_seat", event["payload"])
    return test
for _status in ("draft", "shadow", "promoted"):
    setattr(RetirementOracle, "test_a21_retires_from_" + _status, _state_case(_status))


def _operator_retirement(self):
    """Gate: actor spelling changes no memory authority; contrast: operator spoof."""
    self.seed(self.parent, units=[self.unit(kind="ruling")])
    original = [e for e in journal.snapshot(self.home) if e["kind"] == "memory.put"]
    result = self.retire_agent(actor="operator")
    event = self.assert_commit(result, birth=False)
    self.assertEqual(event["kind"], "agent.status")
    self.assertEqual([e for e in journal.snapshot(self.home) if e["kind"] == "memory.put"], original)
RetirementOracle.test_a02_operator_retire_does_not_create_ruling_authority = _operator_retirement
