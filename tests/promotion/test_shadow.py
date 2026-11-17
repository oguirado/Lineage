"""Shadow evidence, frozen thresholds, continuity and held-out isolation."""
from copy import deepcopy

from tests.promotion.test_evaluate import (BASE, CHILD, CONFIRM, SELECT, SEAT,
    OTHER_SEAT, Fixture, PolicyCase)


class ShadowTests(PolicyCase):
    def test_a8_exact_frozen_clean_run_count_admits(self):
        self.admits(Fixture().confirmed(), "shadow", "promoted", CONFIRM)

    def test_a9_one_clean_run_below_threshold(self):
        self.rejects(Fixture().confirmed(clean=1), bench=CONFIRM)

    def test_a9_pre_shadow_success_does_not_count(self):
        f = Fixture(); f.run(); f.confirmed(clean=1)
        self.rejects(f, bench=CONFIRM)

    def test_a9_pre_shadow_open_post_shadow_close_does_not_count(self):
        f = Fixture(); r = f.run(); run_id = r["run_id"]
        tail = f.events[2:]; f.events = f.events[:2]
        opening = tail.pop(0); f.events.append(opening)
        f.shadow(); f.events.extend(tail); f.run()
        f.bench(CONFIRM, purpose="confirm")
        self.assertTrue(run_id)
        for i, event in enumerate(f.events, 1):
            event["id"] = f"e-{i:016x}"
        self.rejects(f, bench=CONFIRM)

    def test_a9_open_run_does_not_count(self):
        f = Fixture().shadow(); f.run(close=False); f.run(); f.bench(CONFIRM, purpose="confirm")
        self.rejects(f, bench=CONFIRM)

    def test_a9_close_after_confirm_declaration_does_not_count(self):
        f = Fixture().confirmed(clean=1)
        f.run()
        self.rejects(f, bench=CONFIRM)

    def test_a9_benchmark_result_run_id_excludes_standalone_looking_run(self):
        f = Fixture().shadow(); f.run(); r = f.run()
        # A result reference is independently sufficient to exclude a run,
        # even if hostile task metadata omits bench_id.
        f.bench(CONFIRM, purpose="confirm")
        row = deepcopy(f.payload("bench.result", CONFIRM)); row["run_id"] = r["run_id"]
        f.add("bench.result", row)
        self.rejects(f, bench=CONFIRM)

    def test_a9_benchmark_task_excludes_run_without_result(self):
        f = Fixture().shadow(); f.run()
        f.run(task={"id": "bench_task_01", "kind": "unit", "language": "python",
                    "bank_id": "demo-offline", "bench_id": "other_001", "split": "select"})
        f.bench(CONFIRM, purpose="confirm")
        self.rejects(f, bench=CONFIRM)

    def test_a9_duplicate_receipt_is_not_a_distinct_clean_run(self):
        f = Fixture().shadow(); r = f.run()
        close = deepcopy(next(e for e in f.events if e["kind"] == "run.close" and e["payload"]["record"]["run_id"] == r["run_id"]))
        # Re-observation uses the same committed event id and run id.
        f.events.append(close); f.bench(CONFIRM, purpose="confirm")
        self.rejects(f, bench=CONFIRM)

    def test_a9_qualifying_run_fills_deficit(self):
        f = Fixture().shadow(); f.run(); f.run()
        f.bench(CONFIRM, purpose="confirm")
        self.admits(f, "shadow", "promoted", CONFIRM)

    def test_a10_confirm_cannot_lower_selection_threshold(self):
        self.rejects(Fixture().confirmed(n=3, clean=1, confirm_n=1), bench=CONFIRM)

    def test_a10_original_threshold_exact_boundary(self):
        self.admits(Fixture().confirmed(n=3, clean=3, confirm_n=1), "shadow", "promoted", CONFIRM)

    def test_a11_missing_confirmation_verdict(self):
        f = Fixture().confirmed(); f.events.pop()
        self.rejects(f, "no_benchmark", bench=CONFIRM)

    def test_a11_original_selection_cannot_confirm_shadow(self):
        self.rejects(Fixture().shadow(), bench=SELECT)

    def test_a11_confirm_declared_before_shadow(self):
        f = Fixture().bench(CONFIRM, purpose="confirm"); f.shadow(); f.run(); f.run()
        self.rejects(f, bench=CONFIRM)

    def test_a12_same_pinned_bank_disjoint_heldout_tasks(self):
        self.admits(Fixture().confirmed(), "shadow", "promoted", CONFIRM)

    def test_a12_overlap_with_contributing_selection(self):
        f = Fixture().confirmed()
        for e in f.events:
            p = e["payload"]
            task = p.get("task") if e["kind"] == "run.open" else p.get("record", {}).get("task") if e["kind"] == "run.close" else None
            if task and task.get("bench_id") == CONFIRM:
                task["id"] = task["id"].replace("holdout", "select")
            if e["kind"] == "bench.result" and p["bench_id"] == CONFIRM:
                p["task_id"] = p["task_id"].replace("holdout", "select")
            if e["kind"] == "memory.put" and p["unit"]["kind"] == "episode":
                p["unit"]["body"]["task_id"] = p["unit"]["body"]["task_id"].replace("holdout", "select")
        self.rejects(f, "heldout_forbidden", bench=CONFIRM)

    def test_a12_other_bank_hash_cannot_prove_independence(self):
        f = Fixture().confirmed(); f.payload("bench.declared", CONFIRM)["bank_sha256"] = "9" * 64
        self.rejects(f, "internal", bench=CONFIRM)

    def test_a12_renamed_bank_cannot_prove_independence(self):
        f = Fixture().confirmed()
        f.payload("bench.declared", CONFIRM).update(bank_id="renamed-bank", bank_sha256="9" * 64)
        for event in f.events:
            p = event["payload"]
            task = p.get("task") if event["kind"] == "run.open" else p.get("record", {}).get("task") if event["kind"] == "run.close" else None
            if task and task.get("bench_id") == CONFIRM:
                task["bank_id"] = "renamed-bank"
        self.rejects(f, "internal", bench=CONFIRM)

    def test_a12_exploratory_unlinked_selection_does_not_contaminate(self):
        f = Fixture().bench("explore_001")
        # This deliberately failed exploratory benchmark is not a qualification.
        f.payload("bench.verdict", "explore_001")["decision"] = "inconclusive"
        f.confirmed()
        self.admits(f, "shadow", "promoted", CONFIRM)

    def test_a13_fresh_transition_of_promoted_agent(self):
        f = Fixture().confirmed(); f.status("shadow", "promoted", CONFIRM)
        self.rejects(f, bench=CONFIRM)

    def test_a13_retired_agent_cannot_resurrect(self):
        f = Fixture().bench(); f.status("draft", "retired")
        self.rejects(f)

    def test_a7_changed_constitution_requires_new_selection(self):
        f = Fixture().confirmed()
        # A changed declaration snapshot cannot be smuggled through run.version.
        declaration_index = next(i for i,e in enumerate(f.events) if e["kind"] == "bench.declared" and e["payload"]["bench_id"] == CONFIRM)
        changed = deepcopy(f.events[1]); changed["id"] = "e-eeeeeeeeeeeeeeee"
        changed["payload"]["record"]["constitution_sha256"] = "a" * 64
        f.events.insert(declaration_index, changed)
        self.rejects(f, bench=CONFIRM)

    def test_a24_missing_threshold_provenance(self):
        f = Fixture().confirmed(); f.payload("bench.declared")["promotion"].pop("n_shadow_runs")
        self.rejects(f, bench=CONFIRM)


def _excluded_run(**run_args):
    def test(self):
        f = Fixture().shadow(); f.run(); f.run(**deepcopy(run_args))
        f.bench(CONFIRM, purpose="confirm")
        self.rejects(f, bench=CONFIRM)
    return test


for _name, _args in {
    "repaired_success": {"repair": 1},
    "another_seat": {"seat": OTHER_SEAT},
    "another_version": {"frozen_version": "a" * 64},
    "another_agent": {"agent": BASE},
    "failed_memory": {"memory": False},
}.items():
    setattr(ShadowTests, "test_a9_excludes_" + _name, _excluded_run(**_args))


def _bad_confirmation(field, value, credit=False):
    def test(self):
        f = Fixture().confirmed(); p = f.payload("bench.verdict", CONFIRM)
        (p["credit"] if credit else p)[field] = value
        self.rejects(f, bench=CONFIRM)
    return test


for _name, _field, _value, _credit in [
    ("losing", "decision", "not_superior", False),
    ("inconclusive", "decision", "inconclusive", False),
    ("uncredited", "credited", False, True),
    ("negative_reward", "minimum_reward", -1, True),
]:
    setattr(ShadowTests, "test_a11_" + _name + "_confirmation", _bad_confirmation(_field, _value, _credit))
