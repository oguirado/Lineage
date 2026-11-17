"""Deterministic distillation, capacity and request identity oracles."""
from copy import deepcopy
from .helpers import OracleCase, canonical, version


class DistillOracle(OracleCase):
    def source(self):
        units = [self.unit("unit0001"), self.unit("unit0002", kind="negative"),
                 self.unit("unit0003", kind="episode")]
        self.parent = self.seed(self.parent, units=units)
        return units

    def test_a13_subset_counter_is_accepted_brief_affecting_count(self):
        self.source()
        before = deepcopy(self.parent)
        result = self.breed(op="distill", unit_ids=["unit0002"])
        self.assert_commit(result)
        self.assertEqual(result["record"]["memory_gen"], 1)
        self.assertEqual(result["record"]["agent_version"], version(result["record"]))
        self.assertNotEqual(result["record"]["agent_version"], self.parent["agent_version"])
        self.assertEqual(result["record"]["born"]["op"], "distill")
        self.assertEqual([w["source_unit_id"] for w in result["inherited_units"]], ["unit0002"])
        self.assertEqual([r["reason"] for r in result["rejected_units"]], ["not_selected", "episode"])
        self.assertEqual(self.parent, before)

    def test_a13_empty_selection_birth_is_valid_with_zero_counter(self):
        self.source()
        result = self.breed(op="distill", unit_ids=[])
        self.assert_commit(result)
        self.assertEqual(result["inherited_units"], [])
        self.assertEqual(result["record"]["memory_gen"], 0)
        self.assertEqual(result["record"]["agent_version"], version(result["record"]))
        self.assertEqual(len(result["rejected_units"]), 3)

    def test_a07_omission_selects_all_eligible_without_paraphrase(self):
        source = self.source()
        result = self.breed(op="distill")
        self.assertEqual(result["record"]["memory_gen"], 2)
        self.assertEqual([w["unit"]["body"] for w in result["inherited_units"]], [u["body"] for u in source[:2]])
        self.assertEqual([w["unit"]["statement"] for w in result["inherited_units"]], [u["statement"] for u in source[:2]])

    def test_a07_unknown_selected_id_is_bad_args_without_birth(self):
        self.source()
        self.refused("bad_args", lambda: self.breed(op="distill", unit_ids=["unknown1"]))

    def test_a07_existing_excluded_selection_is_audited_and_birth_succeeds(self):
        self.source()
        result = self.breed(op="distill", unit_ids=["unit0003"])
        self.assertEqual(result["inherited_units"], [])
        self.assertEqual(result["rejected_units"][-1]["reason"], "episode")
        self.assert_commit(result)

    def test_a14_absent_token_counter_does_not_block_within_byte_budget(self):
        self.source()
        result = self.breed(op="distill", unit_ids=["unit0001"])
        self.assert_commit(result)
        self.assertEqual(len(result["inherited_units"]), 1)

    def test_a14_inherited_arm_capacity_is_checked_before_commit(self):
        units = [self.unit(f"unit000{i}", statement="x" * 3600) for i in (1, 2)]
        for unit in units:
            self.assertLessEqual(len(canonical(unit)), 6000)
        self.seed(self.parent, units=units)
        self.refused("memory_debt", lambda: self.breed(op="distill"))
        self.assertFalse(any(p.name == "agent.json" for p in self.home.rglob("*")))

    def test_a14_provenance_growth_over_unit_bytes_refuses_before_birth(self):
        unit = self.unit(statement="x")
        unit["statement"] += "x" * (5950 - len(canonical(unit)))
        self.assertEqual(len(canonical(unit)), 5950)
        self.seed(self.parent, units=[unit])
        self.refused("memory_debt", lambda: self.breed(op="distill"))

    def test_a18_same_operation_changed_selection_is_bad_op(self):
        self.source()
        self.breed(op="distill", unit_ids=[])
        self.refused("bad_op", lambda: self.breed(op="distill", unit_ids=["unit0001"]))

    def test_a18_exact_empty_selection_replay_does_not_become_omitted(self):
        self.source()
        first = self.breed(op="distill", unit_ids=[])
        before = self.ledger_bytes()
        self.assertEqual(canonical(self.breed(op="distill", unit_ids=[], expected_head=0)), canonical(first))
        self.assertEqual(self.ledger_bytes(), before)
        self.refused("bad_op", lambda: self.breed(op="distill"))
