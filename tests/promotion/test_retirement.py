"""Journal-only deterministic retirement, isolation and namespace ownership."""
from copy import deepcopy
from unittest.mock import patch

from lineage.domain import promotion
from tests.promotion.test_evaluate import (BASE, CHILD, SELECT, SEAT, OTHER_SEAT,
    Fixture, PolicyCase, canonical)


class RetirementTests(PolicyCase):
    def fold(self, fixture, seed=None):
        state = deepcopy(seed or {"agents": {"untouched": [1]}, "runs": {"sentinel": True},
                                  "memory": {"sentinel": None}, "arena": {"sentinel": "opaque"}})
        original_other = {k: deepcopy(v) for k,v in state.items() if k != "promotion"}
        history = fixture.history(); original_history = deepcopy(history)
        with patch("builtins.open", side_effect=AssertionError("fold performed I/O")), \
             patch("os.open", side_effect=AssertionError("fold performed I/O")):
            for event in history:
                state = self.invoke(promotion.apply, state, event)
                self.assertIsInstance(state, dict)
                self.assertEqual({k:v for k,v in state.items() if k != "promotion"}, original_other)
        self.assertEqual(history, original_history)
        return state

    def entry(self, fixture):
        return self.fold(fixture)["promotion"][CHILD]

    def test_a14_third_failure_retires_across_seats_and_arms(self):
        f = Fixture()
        for seat, arm, verdict in [(SEAT, "none", "error"), (OTHER_SEAT, "own", "HOLD"),
                                   (SEAT, "inherited", "red")]:
            f.run(seat=seat, arm=arm, verdict=verdict)
        before = f.history()
        entry = self.entry(f)
        self.assertEqual(entry["status"], "retired")
        self.assertEqual(entry["failure_streak"], 3)
        self.assertIsNone(entry["promoted_seat"])
        self.assertEqual(f.history(), before)
        self.assertFalse(any(e["kind"] == "agent.status" for e in before))

    def test_a15_two_failures_do_not_retire(self):
        f = Fixture(); f.run(verdict="error"); f.run(verdict="red")
        self.assertEqual(self.entry(f)["status"], "draft")
        self.assertEqual(self.entry(f)["failure_streak"], 2)

    def test_a15_status_transition_does_not_reset_streak(self):
        f = Fixture().bench(); f.run(verdict="error"); f.run(verdict="HOLD")
        f.status("draft", "shadow", SELECT)
        f.run(verdict="red")
        entry = self.entry(f)
        self.assertEqual(entry["status"], "retired")
        self.assertEqual(entry["selection_bench_id"], SELECT)
        self.assertIsNotNone(entry["shadow_event_id"])

    def test_a15_other_agent_close_neither_increments_nor_resets(self):
        f = Fixture(); f.run(verdict="error"); f.run(agent=BASE); f.run(verdict="error")
        self.assertEqual(self.entry(f)["failure_streak"], 2)

    def test_a15_open_and_heartbeat_neither_increment_nor_reset(self):
        f = Fixture(); f.run(verdict="error"); r = f.run(close=False)
        f.add("run.beat", {"run_id": r["run_id"], "progress": "synthetic heartbeat"}, actor=CHILD)
        f.run(verdict="red")
        self.assertEqual(self.entry(f)["failure_streak"], 2)

    def test_a15_bench_result_is_not_a_close(self):
        f = Fixture().bench(); f.run(verdict="error")
        row = deepcopy(f.payload("bench.result"))
        for _ in range(4):
            f.add("bench.result", row)
        self.assertEqual(self.entry(f)["failure_streak"], 1)

    def test_a15_rejected_close_is_absent_and_cannot_count(self):
        f = Fixture(); f.run(verdict="error"); f.run(close=False)
        self.assertEqual(self.entry(f)["failure_streak"], 1)

    def test_a15_explicit_retirement_is_sticky(self):
        f = Fixture(); f.status("draft", "retired")
        r = f.run(agent=BASE, close=False)
        f.add("run.beat", {"run_id": r["run_id"], "progress": "other agent"}, actor=BASE)
        self.assertEqual(self.entry(f)["status"], "retired")
        self.assertEqual(self.entry(f)["status"], "retired")

    def test_a16_fold_is_deterministic_and_owns_only_promotion(self):
        f = Fixture().confirmed()
        first = self.fold(f); second = self.fold(f)
        self.assertEqual(canonical(first), canonical(second))
        entry = first["promotion"][CHILD]
        self.assertEqual(set(entry), {"status", "promoted_seat", "shadow_event_id", "shadow_lamport",
                                     "selection_bench_id", "n_shadow_runs", "failure_streak"})
        self.assertEqual(entry["n_shadow_runs"], 2)
        self.assertEqual(entry["selection_bench_id"], SELECT)
        shadow = next(e for e in f.events if e["kind"] == "agent.status")
        self.assertEqual(entry["shadow_event_id"], shadow["id"])
        self.assertEqual(entry["shadow_lamport"], shadow["lamport"])

    def test_a16_fold_does_not_read_foreign_namespaces_or_import_order(self):
        f = Fixture().shadow()
        plain = self.fold(f, {"arena": {"poison": "not a benchmark projection"}, "memory": {}})
        reverse = self.fold(f, {"memory": {}, "arena": {"poison": "not a benchmark projection"}})
        self.assertEqual(plain["promotion"], reverse["promotion"])

    def test_a21_mutating_fold_result_does_not_change_rebuild(self):
        f = Fixture().shadow(); result = self.fold(f)
        result["promotion"][CHILD]["status"] = "retired"
        self.assertEqual(self.entry(f)["status"], "shadow")


def _reset(verdict):
    def test(self):
        f = Fixture(); f.run(verdict="error"); f.run(verdict="HOLD")
        f.run(verdict=verdict); f.run(verdict="red")
        self.assertEqual(self.entry(f)["status"], "draft")
        self.assertEqual(self.entry(f)["failure_streak"], 1)
    return test


for _verdict in ("green", "ADMIT"):
    setattr(RetirementTests, "test_a15_" + _verdict.lower() + "_resets_streak", _reset(_verdict))
