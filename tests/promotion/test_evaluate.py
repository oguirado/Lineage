"""Pure-policy oracles. Synthetic prevalidated History fixtures are not receipts."""
from __future__ import annotations

import builtins
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import statistics
import unittest
from unittest.mock import patch

from lineage.core.errors import LineageError
from lineage.domain import promotion

SEAT = {"model": "fixture-model", "effort": "medium", "mode": "headless"}
OTHER_SEAT = dict(SEAT, effort="high")
BASE = "baseline-agent"
CHILD = "candidate-agent"
SELECT = "select_001"
CONFIRM = "confirm_001"
BANK_HASH = "1" * 64
UNKNOWN_COST = dict.fromkeys(("tokens_in", "tokens_out", "tokens_cache",
                              "duration_ms", "cost_micro_usd"))
TEST_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TEST_ROOT.parents[1]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def version(record):
    return digest({"constitution_sha256": record["constitution_sha256"],
                   "skills": sorted(record["skills"], key=lambda x: (x["skill_id"], x["sha256"])),
                   "memory_gen": record["memory_gen"]})


class Fixture:
    """An explicit, detached, synthetic already-admitted prefix, never appended.

    The frozen wire schema lacks a promotion seat. Pure status fixtures use
    payload['_u19_fixture_seat']; that key is NEVER used in a real transaction.
    Bank membership/splits stand for U16's prevalidated journal witnesses.
    """

    def __init__(self):
        self.events = []
        self.records = {}
        self.serial = 0
        self.birth(BASE)
        self.birth(CHILD)

    def add(self, kind, payload, actor="creator-agent"):
        n = len(self.events) + 1
        request = {"ledger": "main", "agent": actor, "op_id": f"op_{n:08d}",
                   "kind": kind, "payload": deepcopy(payload), "evidence": []}
        event = {"schema": "lineage.event/v1", "id": f"e-{n:016x}",
                 "lamport": n, "ts": n, **request,
                 "request_sha256": digest(request),
                 "prev_sha256": hashlib.sha256(canonical(self.events[-1]) + b"\n").hexdigest()
                 if self.events else "0" * 64}
        event["sha256"] = digest(event)
        self.events.append(event)
        return event

    def birth(self, agent_id):
        constitution = "Synthetic U19 constitution.\n"
        record = {"schema": "lineage.agent/v1", "agent_id": agent_id,
                  "display_name": agent_id, "workflow": "test", "language": "python",
                  "allowed_seats": [deepcopy(SEAT), deepcopy(OTHER_SEAT)],
                  "references": [{"id": "gold_s1", "sha256": "2" * 64},
                                 {"id": "memory_v21", "sha256": "3" * 64}],
                  "constitution_sha256": hashlib.sha256(constitution.encode()).hexdigest(),
                  "skills": [], "memory_gen": 0, "brief_head_sha256": "4" * 64,
                  "generation": 0, "parents": [],
                  "born": {"op": "genesis", "event_id": f"e-{len(self.events)+1:016x}"},
                  "status": "draft"}
        record["agent_version"] = version(record)
        self.records[agent_id] = deepcopy(record)
        self.add("agent.born", {"record": record, "inherited_units": [],
                               "rejected_units": [], "constitution": {
                                   "text": constitution, "overlays": [], "rule_ids": []}})

    def unit(self, run, kind="episode"):
        self.serial += 1
        unit_id = f"unit_{self.serial:08d}"
        body = {"run_id": run["run_id"], "task_id": run["task"]["id"],
                "seat": deepcopy(run["seat"]), "outcome": deepcopy(run["outcome"]),
                "cost": deepcopy(run["cost"]), "parents_context": []}
        if kind == "lesson":
            body = {"tempting_use": "Treat a synthetic failure as real fitness.",
                    "failure_mode": "Synthetic outcomes do not measure a real seat.",
                    "safer_action": "Keep fixture and real-seat evidence distinct.", "blocked_use": []}
        elif kind == "negative":
            body = {"gate_id": "synthetic-memory", "verdict": run["outcome"]["verdict"],
                    "cause": "Synthetic fixture failure.", "coordinate": "fixtures/synthetic.txt",
                    "safer_action": "Inspect the synthetic fixture."}
        unit = {"schema": "lineage.mem.unit/v1", "id": unit_id, "kind": kind,
                "level": 3 if kind == "episode" else 2,
                "statement": "Synthetic U19 memory witness.", "status": "active",
                "privacy": "internal", "scope": {"workflow": "test", "language": "python"},
                "provenance": {"origin": "synthetic-fixture", "actor": run["agent_id"],
                               "run_id": run["run_id"]},
                "receipts": [{"path": "fixtures/synthetic.txt", "sha256": "5" * 64}],
                "supersedes": [], "body": body}
        self.add("memory.put", {"agent_id": run["agent_id"], "unit": unit,
                                "run_id": run["run_id"]}, actor=run["agent_id"])
        if kind != "episode":
            r = self.records[run["agent_id"]]
            r["memory_gen"] += 1
            r["agent_version"] = version(r)
        return unit_id

    def run(self, *, agent=CHILD, seat=None, arm="own", verdict="green",
            repair=0, task=None, frozen_version=None, close=True, memory=True):
        self.serial += 1
        run_id = f"run_{self.serial:08d}"
        task = deepcopy(task or {"id": f"task_{self.serial:08d}", "kind": "unit", "language": "python"})
        opened = self.add("run.open", {"run_id": run_id, "agent_id": agent,
                       "agent_version": frozen_version or self.records[agent]["agent_version"],
                       "seat": deepcopy(seat or SEAT), "task": task,
                       "parents_context": [], "memory_arm": arm}, actor=agent)
        record = {"schema": "lineage.run/v1", **deepcopy(opened["payload"]),
                  "ts_open": opened["ts"], "ts_close": opened["ts"],
                  "outcome": {"verdict": verdict, "repair_loops": repair,
                              "findings": {"confirmed": 0, "refuted": 0}},
                  "cost": deepcopy(UNKNOWN_COST), "evidence": [],
                  "memory": {"unit_ids": [], "levels": [3], "gate_passed": True}}
        if not close:
            return record
        if memory:
            ids = [self.unit(record)]
            if verdict in ("error", "HOLD", "red") or repair:
                ids.append(self.unit(record, "lesson"))
            if verdict in ("HOLD", "red"):
                ids.append(self.unit(record, "negative"))
            record["memory"] = {"unit_ids": ids, "levels": [2, 3] if len(ids) > 1 else [3],
                                "gate_passed": True}
        record["ts_close"] = len(self.events) + 1
        self.add("run.close", {"record": record, "memory_receipts": [
                 {"path": "fixtures/synthetic.txt", "sha256": "5" * 64}],
                 "gate": {"passed": memory, "checks": [{"id": "memory", "passed": memory}]}}, actor=agent)
        return record

    def bench(self, bench_id=SELECT, *, purpose="select", n=2,
              pairs=((1, 1), (0, 1), (0, 1)), arms=("own",), bank_hash=BANK_HASH, cells=None):
        declaration = {"schema": "lineage.bench.declared/v1", "bench_id": bench_id,
             "bank_id": "demo-offline", "bank_sha256": bank_hash, "protocol": "paired",
             "purpose": purpose, "agents": [BASE, CHILD], "seats": [deepcopy(SEAT)],
             "memory_arms": list(arms), "credit_rule": {"metric": "correctness_first",
             "minimum_gain": 0.0, "dispersion": "population_stddev", "cost_tiebreaker": False},
             "sprt": {"p0": 0.2, "p1": 0.8, "alpha": 0.1, "beta": 0.1, "cap": len(pairs)},
             "promotion": {"n_shadow_runs": n}}
        self.add("bench.declared", declaration)
        snapshots = {a: self.records[a]["agent_version"] for a in (BASE, CHILD)}
        split = "select" if purpose == "select" else "heldout"
        prefix = "select" if purpose == "select" else "holdout"
        for i, pair in enumerate(pairs):
            task = {"id": f"{prefix}_{i:04d}", "kind": "unit", "language": "python",
                    "bank_id": "demo-offline", "bench_id": bench_id, "split": split}
            for arm in arms:
                for agent, correct in zip((BASE, CHILD), (cells or {}).get((i, arm), pair)):
                    r = self.run(agent=agent, arm=arm, task=task,
                                 verdict="green" if correct else "error",
                                 frozen_version=snapshots[agent])
                    self.add("bench.result", {"bench_id": bench_id, "task_id": task["id"],
                        "agent_id": agent, "seat": deepcopy(SEAT), "memory_arm": arm,
                        "run_id": r["run_id"], "verdict": r["outcome"]["verdict"],
                        "correctness": correct, "cost": deepcopy(UNKNOWN_COST)})
        task_means = [tuple(statistics.mean((cells or {}).get((i, arm), pair)[side]
                       for arm in arms) for side in (0, 1)) for i, pair in enumerate(pairs)]
        rewards = [c-b for b, c in task_means]
        gain = statistics.mean(c for b, c in task_means) - statistics.mean(b for b, c in task_means)
        dispersion = statistics.pstdev(b for b, c in task_means)
        llr = sum(math.log(4) if r > 0 else -math.log(4) if r < 0 else 0 for r in rewards)
        decision = "superior" if llr >= math.log(9) else "not_superior" if llr <= -math.log(9) else "inconclusive"
        self.add("bench.verdict", {"bench_id": bench_id, "decision": decision,
                  "llr": llr, "n_discordant": sum(r != 0 for r in rewards),
                  "credit": {"gain": gain, "baseline_dispersion": dispersion,
                             "minimum_reward": min(rewards),
                             "credited": gain > max(dispersion, declaration["credit_rule"]["minimum_gain"])}})
        return self

    def shadow(self, n=2):
        self.bench(n=n)
        self.status("draft", "shadow", SELECT)
        return self

    def status(self, old, new, bench_id=None):
        payload = {"agent_id": CHILD, "from": old, "to": new, "reason": "synthetic qualification"}
        if bench_id:
            payload.update(bench_id=bench_id, _u19_fixture_seat=deepcopy(SEAT))
        return self.add("agent.status", payload)

    def confirmed(self, *, n=2, clean=2, confirm_n=1):
        self.shadow(n)
        for _ in range(clean):
            self.run()
        self.bench(CONFIRM, purpose="confirm", n=confirm_n)
        return self

    def history(self):
        # Recompute envelope hashes after intentional semantic mutations.
        previous = "0" * 64
        run_times = {}
        for i, e in enumerate(self.events, 1):
            e.update(lamport=i, ts=i, prev_sha256=previous)
            if e["kind"] == "run.open":
                run_times[e["payload"]["run_id"]] = i
            elif e["kind"] == "run.close":
                record = e["payload"]["record"]
                record["ts_open"] = run_times.get(record["run_id"], record["ts_open"])
                record["ts_close"] = i
            e.pop("sha256", None)
            try:
                e["sha256"] = digest(e)
                previous = hashlib.sha256(canonical(e) + b"\n").hexdigest()
            except ValueError:
                # Non-finite hostile direct-policy fixtures cannot be journal
                # events. Keep them explicit; never serialize them to disk.
                e["sha256"] = "0" * 64
                previous = "0" * 64
        return tuple(deepcopy(self.events))

    def payload(self, kind, bench_id=SELECT):
        return next(e["payload"] for e in reversed(self.events)
                    if e["kind"] == kind and e["payload"].get("bench_id") == bench_id)


class PolicyCase(unittest.TestCase):
    def invoke(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except NotImplementedError as exc:
            self.fail(f"U19 stub: required behavior is absent ({exc})")

    def evaluate(self, fixture, *, bench=SELECT, agent=CHILD, seat=None):
        history = fixture.history()
        before = deepcopy(history)
        internal_seat = deepcopy(SEAT if seat is None else seat)
        seat_before = deepcopy(internal_seat)
        # Policy is pure: no filesystem, subprocess, ambient snapshot or lock.
        with patch.object(builtins, "open", side_effect=AssertionError("evaluate performed I/O")), \
             patch("os.open", side_effect=AssertionError("evaluate performed I/O")), \
             patch("subprocess.Popen", side_effect=AssertionError("evaluate launched a process")), \
             patch("lineage.core.journal.snapshot", side_effect=AssertionError("evaluate reread journal")):
            try:
                result = self.invoke(promotion.evaluate, history, agent, bench, seat=internal_seat)
            finally:
                self.assertEqual(history, before, "policy mutated its authoritative prefix")
                self.assertEqual(internal_seat, seat_before, "policy mutated the supplied seat")
        return result

    def rejects(self, fixture, code="conflict", **kwargs):
        before = fixture.history()
        with self.assertRaises(LineageError) as caught:
            self.evaluate(fixture, **kwargs)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(fixture.history(), before)

    def admits(self, fixture, old="draft", new="shadow", bench=SELECT):
        result = self.evaluate(fixture, bench=bench)
        self.assertEqual(set(result), {"from", "to", "reason", "bench_id"})
        self.assertEqual((result["from"], result["to"], result["bench_id"]), (old, new, bench))
        self.assertIsInstance(result["reason"], str)
        self.assertTrue(result["reason"])
        return result


class EvaluateTests(PolicyCase):
    def test_a2_zero_minimum_reward_and_strict_credited_gain_admit(self):
        f = Fixture().bench()
        self.assertEqual(f.payload("bench.verdict")["credit"]["minimum_reward"], 0)
        self.admits(f)

    def test_a3_unknown_agent_precedes_missing_benchmark(self):
        self.rejects(Fixture(), "no_agent", agent="unknown-agent", bench="unknown_001")

    def test_a3_unknown_benchmark(self):
        self.rejects(Fixture(), "no_benchmark", bench="unknown_001")

    def test_a3_declaration_without_verdict(self):
        f = Fixture().bench(); f.events = f.events[:3]
        self.rejects(f, "no_benchmark")

    def test_a3_results_without_verdict(self):
        f = Fixture().bench(); f.events.pop()
        self.rejects(f, "no_benchmark")

    def test_a4_negative_task_reward_even_with_aggregate_gain(self):
        self.rejects(Fixture().bench(pairs=((1, 0), (0, 1), (0, 1), (0, 1), (0, 1))))

    def test_a4_equal_minimum_gain_is_not_credited(self):
        f = Fixture().bench()
        f.payload("bench.declared")["credit_rule"]["minimum_gain"] = f.payload("bench.verdict")["credit"]["gain"]
        self.rejects(f)

    def test_a4_gain_equal_population_dispersion_is_not_credited(self):
        f = Fixture().bench(pairs=((1, 1), (0, 1)))
        f.payload("bench.declared")["sprt"]["alpha"] = 0.3
        f.payload("bench.verdict")["decision"] = "superior"
        f.payload("bench.verdict")["credit"]["credited"] = True
        self.rejects(f)

    def test_a4_cost_only_advantage_cannot_qualify(self):
        f = Fixture().bench(pairs=((1, 1), (1, 1), (1, 1)))
        f.payload("bench.declared")["credit_rule"]["cost_tiebreaker"] = True
        for e in f.events:
            if e["kind"] == "bench.result":
                e["payload"]["cost"]["cost_micro_usd"] = 0 if e["payload"]["agent_id"] == CHILD else 999
        self.rejects(f)

    def test_a5_missing_paired_result_is_not_zero(self):
        f = Fixture().bench()
        f.events.remove(next(e for e in f.events if e["kind"] == "bench.result"))
        self.rejects(f)

    def test_a5_duplicate_result_is_not_an_independent_cell(self):
        f = Fixture().bench()
        f.add("bench.result", deepcopy(f.payload("bench.result")))
        self.rejects(f)

    def test_a5_missing_close_witness(self):
        f = Fixture().bench()
        rid = f.payload("bench.result")["run_id"]
        f.events = [e for e in f.events if not (e["kind"] == "run.close" and e["payload"]["record"]["run_id"] == rid)]
        self.rejects(f)

    def test_a5_result_close_correctness_disagreement(self):
        f = Fixture().bench(); f.payload("bench.result")["correctness"] = 0
        self.rejects(f)

    def test_a5_invalid_memory_gate_excludes_benchmark_run(self):
        f = Fixture().bench()
        next(e for e in f.events if e["kind"] == "run.close")["payload"]["gate"]["passed"] = False
        self.rejects(f)

    def test_a5_run_open_version_is_declaration_snapshot(self):
        f = Fixture().bench()
        next(e for e in f.events if e["kind"] == "run.open" and e["payload"]["agent_id"] == CHILD)["payload"]["agent_version"] = "a" * 64
        self.rejects(f)

    def test_a6_singleton_and_admitted_complete_seat(self):
        self.admits(Fixture().bench())

    def test_a6_multiple_seats(self):
        f = Fixture().bench(); f.payload("bench.declared")["seats"].append(deepcopy(OTHER_SEAT))
        self.rejects(f, "bad_args")

    def test_a6_effort_mismatch(self):
        self.rejects(Fixture().bench(), "bad_args", seat=OTHER_SEAT)

    def test_a6_mode_mismatch(self):
        self.rejects(Fixture().bench(), "bad_args", seat=dict(SEAT, mode="interactive"))

    def test_a6_baseline_cannot_claim_candidate_win(self):
        self.rejects(Fixture().bench(), agent=BASE)

    def test_a6_self_benchmark(self):
        f = Fixture().bench(); f.payload("bench.declared")["agents"] = [CHILD, CHILD]
        self.rejects(f)

    def test_a6_unadmitted_seat(self):
        f = Fixture().bench()
        f.events[1]["payload"]["record"]["allowed_seats"] = [deepcopy(OTHER_SEAT)]
        self.rejects(f)

    def test_a7_post_declaration_benchmark_memory_drift_is_allowed(self):
        f = Fixture().bench()
        r = next(e["payload"]["record"] for e in f.events if e["kind"] == "run.close" and e["payload"]["record"]["agent_id"] == CHILD)
        # Move this valid lesson between the run's episode and close.
        f.unit(r, "lesson")
        unit_event = f.events.pop()
        close_index = next(i for i,e in enumerate(f.events) if e["kind"] == "run.close" and e["payload"]["record"]["run_id"] == r["run_id"])
        f.events.insert(close_index, unit_event)
        self.admits(f)

    def test_a12_select_consuming_heldout_is_forbidden(self):
        f = Fixture().bench()
        for e in f.events:
            if e["kind"] == "run.open":
                e["payload"]["task"]["split"] = "heldout"
            elif e["kind"] == "run.close":
                e["payload"]["record"]["task"]["split"] = "heldout"
        self.rejects(f, "heldout_forbidden")

    def test_a12_missing_split_is_internal(self):
        f = Fixture().bench()
        for e in f.events:
            if e["kind"] == "run.open":
                e["payload"]["task"].pop("split")
            elif e["kind"] == "run.close":
                e["payload"]["record"]["task"].pop("split")
        self.rejects(f, "internal")

    def test_a12_missing_bank_pin_is_internal(self):
        f = Fixture().bench(); f.payload("bench.declared").pop("bank_sha256")
        self.rejects(f, "internal")

    def test_a13_confirm_cannot_admit_draft(self):
        self.rejects(Fixture().bench(purpose="confirm"))

    def test_a21_policy_result_is_defensive(self):
        f = Fixture().bench(); result = self.admits(f)
        result["from"] = "retired"
        self.admits(f)

    def test_a24_unknown_cost_remains_null_and_does_not_block(self):
        f = Fixture().bench()
        self.admits(f)
        self.assertTrue(all(v is None for e in f.events if e["kind"] == "bench.result" for v in e["payload"]["cost"].values()))

    def test_a24_arms_are_cells_not_independent_tasks(self):
        f = Fixture().bench(arms=("none", "own", "inherited"))
        self.admits(f)
        self.assertEqual(f.payload("bench.verdict")["n_discordant"], 2)

    def test_a24_crossed_cells_aggregate_before_population_dispersion(self):
        cells = {(i, arm): (0 if arm == "none" else 1, 1)
                 for i in range(2) for arm in ("none", "own")}
        f = Fixture().bench(pairs=((0, 1), (0, 1)), arms=("none", "own"), cells=cells)
        f.payload("bench.declared")["protocol"] = "crossed"
        self.assertEqual(f.payload("bench.verdict")["credit"]["baseline_dispersion"], 0)
        self.assertEqual(f.payload("bench.verdict")["credit"]["gain"], 0.5)
        self.admits(f)

    def test_a6_seat_unknown_field(self):
        self.rejects(Fixture().bench(), "bad_args", seat=dict(SEAT, authority="operator"))

    def test_a5_wrong_result_candidate_identity(self):
        f = Fixture().bench(); f.payload("bench.result")["agent_id"] = "another-agent"
        self.rejects(f)

    def test_a28_telemetry_without_correctness_does_not_qualify(self):
        f = Fixture().bench()
        for e in f.events:
            if e["kind"] == "bench.result":
                e["payload"].pop("correctness")
        self.rejects(f)

    def test_a28_launch_acknowledgement_is_not_benchmark_evidence(self):
        self.rejects(Fixture(), "no_benchmark")


def _verdict_case(field, value, credit=False):
    def test(self):
        f = Fixture().bench(); verdict = f.payload("bench.verdict")
        (verdict["credit"] if credit else verdict)[field] = value
        self.rejects(f)
    return test


for _name, _field, _value, _credit in [
    ("a4_not_superior", "decision", "not_superior", False),
    ("a4_inconclusive", "decision", "inconclusive", False),
    ("a4_uncredited", "credited", False, True),
    ("a5_forged_gain", "gain", 1.0, True),
    ("a5_forged_minimum_reward", "minimum_reward", 1.0, True),
    ("a5_forged_dispersion", "baseline_dispersion", 0.0, True),
    ("a5_forged_llr", "llr", 0.0, False),
    ("a5_forged_discordant_count", "n_discordant", 99, False),
    ("a24_null_minimum_reward", "minimum_reward", None, True),
    ("a24_boolean_gain", "gain", True, True),
    ("a24_nonfinite_gain", "gain", float("nan"), True),
    ("a24_infinite_dispersion", "baseline_dispersion", float("inf"), True),
    ("a24_null_credited", "credited", None, True),
]:
    setattr(EvaluateTests, "test_" + _name, _verdict_case(_field, _value, _credit))


def _missing_credit(field):
    def test(self):
        f = Fixture().bench()
        f.payload("bench.verdict")["credit"].pop(field)
        self.rejects(f)
    return test


for _field in ("gain", "minimum_reward", "credited", "baseline_dispersion"):
    setattr(EvaluateTests, "test_a24_missing_" + _field, _missing_credit(_field))
