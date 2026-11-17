"""Actual ledger-backed run/memory/close ordering and mandatory memory arms."""
from copy import deepcopy
from dataclasses import replace
import itertools
from pathlib import Path
from unittest import mock

from .helpers import (ArenaCase, COST, Interrupted, SEAT, SEAT2, bank_data, bench,
                      command_source, declaration, digest, output_for, runner, task)


class ExecutionTests(ArenaCase):
    def single(self, baseline="green", candidate="green", split="select"):
        self.bank = bank_data([task(1, split, baseline, candidate)])
        self.write_bank(self.bank)
        self.decl = declaration(self.bank, purpose="confirm" if split == "heldout" else "select")

    def test_a12_real_lifecycle_and_actual_closed_run_witness(self):
        self.single()
        self.declare()
        result = self.execute()
        self.assert_lifecycle()
        self.assertEqual(len(result["bench"]["results"]), 2)
        self.assertEqual(len(self.events("run.open")), 2)
        self.assertEqual(len(self.events("run.close")), 2)
        self.assertEqual(result["bench"]["state"], "complete")
        self.assertIsNone(result["bench"]["verdict"])
        # A missing U13 is an unverified integration, never substituted here.
        import importlib
        runs = importlib.import_module("lineage.domain.runs")
        for cell in result["bench"]["results"]:
            # A-U16: integrated run_get exposes the gated record as closed, alongside opened/head.
            record = runs.get(cell["run_id"], ctx=replace(self.ctx, actor=cell["agent_id"]))["closed"]
            self.assertIsNotNone(record)
            self.assertIs(record["memory"]["gate_passed"], True)

    def test_a11_paired_grid_and_full_seat_arm_identity(self):
        self.single()
        self.decl.update(seats=[SEAT, SEAT2], memory_arms=["none", "own", "inherited"])
        self.declare()
        result = self.execute()["bench"]["results"]
        expected = {(agent, tuple(sorted(seat.items())), arm) for agent, seat, arm in
                    itertools.product(self.decl["agents"], self.decl["seats"], self.decl["memory_arms"])}
        actual = {(r["agent_id"], tuple(sorted(r["seat"].items())), r["memory_arm"]) for r in result}
        self.assertEqual(actual, expected)
        self.assertEqual(len(result), len(expected))
        self.assert_lifecycle()

    def test_a11_crossed_grid_and_task_order_are_complete(self):
        self.single()
        self.decl.update(protocol="crossed", seats=[SEAT, SEAT2], memory_arms=["none", "own", "inherited"])
        self.declare()
        result = self.execute()["bench"]["results"]
        self.assertEqual(len(result), 12)
        self.assertEqual(len({(r["agent_id"], str(r["seat"]), r["memory_arm"]) for r in result}), 12)
        for event in self.events("run.open"):
            self.assertIn(event["payload"]["memory_arm"], self.decl["memory_arms"])
        self.assert_lifecycle()

    def test_a5_only_eligible_tasks_execute_in_bank_order(self):
        self.declare()
        self.execute()
        expected = [t["id"] for t in self.bank["tasks"] if t["split"] == "select"]
        for agent in self.decl["agents"]:
            self.assertEqual([e["payload"]["task"]["id"] for e in self.events("run.open")
                              if e["payload"]["agent_id"] == agent], expected)
        self.assertNotIn("task00000001", [r["task_id"] for r in self.status()["results"]])

    def test_a6_confirm_admits_heldout_tasks(self):
        self.single(split="heldout")
        self.declare()
        self.execute()
        self.assertEqual({r["task_id"] for r in self.status()["results"]}, {"task00000001"})
        self.assert_lifecycle()

    def test_a5_empty_split_refuses_before_open(self):
        self.single(split="heldout")
        self.decl["purpose"] = "select"
        self.subjects()
        self.rejects("bad_args", bench.declare, self.decl,
                     command=self.command("bench_declare", {"declaration": self.decl}), ctx=self.ctx)
        self.assertFalse(self.events("run.open"))

    def poisoned_memory(self, transform, error):
        self.single()
        self.declare()
        original = runner.run_task
        def execute(*args, **kwargs):
            value = original(*args, **kwargs)
            return transform(deepcopy(value))
        with mock.patch.object(runner, "run_task", side_effect=execute):
            self.rejects(error, self.execute, unchanged=False)
        self.assert_open_without_result()

    def test_a14_missing_episode_leaves_run_open(self):
        def remove(value):
            value["memory_units"] = []
            return value
        self.poisoned_memory(remove, "memory_required")

    def test_a14_private_episode_cannot_close_run(self):
        def private(value):
            for unit in value["memory_units"]:
                unit["privacy"] = "private"
            return value
        self.poisoned_memory(private, "memory_required")

    def test_a13_other_actor_memory_refused(self):
        def foreign(value):
            value["memory_units"][0]["provenance"]["actor"] = "other-agent"
            return value
        self.poisoned_memory(foreign, "bad_args")

    def test_a14_other_run_episode_refused(self):
        def foreign(value):
            value["memory_units"][0]["body"]["run_id"] = "otherrun1"
            return value
        self.poisoned_memory(foreign, "bad_args")

    def test_a13_level_one_never_gains_tool_authority(self):
        def escalate(value):
            value["memory_units"][0]["level"] = 1
            return value
        self.poisoned_memory(escalate, "forbidden_level")

    def test_a13_operator_named_caller_still_tool_authority(self):
        self.single()
        self.declare()
        original = runner.run_task
        def execute(*args, **kwargs):
            self.assertEqual(kwargs["ctx"].authority, "tool")
            self.assertEqual(kwargs["ctx"].actor, kwargs["agent"]["agent_id"])
            result = original(*args, **kwargs)
            result["memory_units"][0]["level"] = 1
            return result
        config = {"kind": "fake", "seed": 1}
        command = self.command("bench_run", {"bench_id": "bench0001", "runner": config}, actor="operator")
        with mock.patch.object(runner, "run_task", side_effect=execute):
            self.rejects("forbidden_level", bench.run, "bench0001", config, command=command,
                         ctx=replace(self.ctx, actor="operator"), unchanged=False)
        self.assert_open_without_result()

    def test_a15_error_without_lesson_is_memory_debt(self):
        self.single(baseline="error")
        self.declare()
        original = runner.run_task
        def execute(*args, **kwargs):
            result = original(*args, **kwargs)
            result["memory_units"] = [u for u in result["memory_units"] if u["kind"] != "lesson"]
            return result
        with mock.patch.object(runner, "run_task", side_effect=execute):
            self.rejects("memory_debt", self.execute, unchanged=False)
        self.assert_open_without_result()

    def test_a15_repaired_green_requires_same_run_lesson(self):
        self.single()
        self.bank["tasks"][0]["expected"]["baseline"]["repair_loops"] = 1
        self.write_bank(self.bank)
        self.decl["bank_sha256"] = digest(self.bank)
        self.declare()
        original = runner.run_task
        def execute(*args, **kwargs):
            result = original(*args, **kwargs)
            result["memory_units"] = [u for u in result["memory_units"] if u["kind"] == "episode"]
            return result
        with mock.patch.object(runner, "run_task", side_effect=execute):
            self.rejects("memory_debt", self.execute, unchanged=False)
        self.assert_open_without_result()

    def test_a15_hold_and_red_require_negative(self):
        self.single(baseline="HOLD")
        self.declare()
        original = runner.run_task
        def execute(*args, **kwargs):
            result = original(*args, **kwargs)
            result["memory_units"] = [u for u in result["memory_units"] if u["kind"] != "negative"]
            return result
        with mock.patch.object(runner, "run_task", side_effect=execute):
            self.rejects("memory_debt", self.execute, unchanged=False)
        self.assert_open_without_result()

    def test_a15_failure_memory_preserves_failed_outcomes(self):
        self.single(baseline="red", candidate="error")
        self.declare()
        data = self.execute()
        self.assertEqual([r["verdict"] for r in data["bench"]["results"]], ["red", "error"])
        self.assertTrue(all(r["correctness"] == 0 for r in data["bench"]["results"]))
        self.assert_lifecycle()

    def test_a16_missing_or_changed_evidence_refuses_admission(self):
        def changed(value):
            for unit in value["memory_units"]:
                for receipt in unit["receipts"]:
                    receipt["sha256"] = "0" * 64
            return value
        self.poisoned_memory(changed, "hash_mismatch")

    def test_a16_reserved_evidence_storage_is_not_a_receipt(self):
        def reserved(value):
            value["memory_units"][0]["receipts"][0]["path"] = "ledger/main/events.jsonl"
            return value
        self.poisoned_memory(reserved, "bad_args")

    def test_a16_symlink_evidence_is_confined(self):
        outside = self.base / "outside.txt"
        outside.write_text("fixture")
        (self.home / "escape.txt").symlink_to(outside)
        def escaping(value):
            value["memory_units"][0]["receipts"][0]["path"] = "escape.txt"
            return value
        self.poisoned_memory(escaping, "bad_args")

    def test_a16_oversize_memory_fails_byte_budget(self):
        def oversized(value):
            value["memory_units"][0]["statement"] = "é" * 4000
            return value
        self.poisoned_memory(oversized, "memory_debt")

    def test_a16_token_count_none_does_not_create_memory_debt(self):
        self.single()
        self.assertIsNone(self.ctx.services.token_count)
        self.declare()
        self.execute()
        self.assert_lifecycle()
        self.assertTrue(self.events("run.close"))

    def test_a18_command_memory_roundtrip_through_real_close(self):
        self.single()
        receipt = self.home / "evidence/fixture.txt"
        receipt.parent.mkdir()
        receipt.write_bytes(b"fixture\n")
        self.declare()
        self.execute(self.child(command_source()))
        self.assert_lifecycle()
        self.assertEqual(self.status()["state"], "complete")

    def test_a2_malformed_stdout_keeps_real_open_witness(self):
        self.single()
        self.declare()
        self.rejects("bad_args", self.execute, self.child("print('{}')"), unchanged=False)
        self.assert_open_without_result()

    def test_a21_completed_timeout_returns_failed_benchmark_datum(self):
        self.single()
        self.declare()
        data = self.execute(self.child("import threading;threading.Event().wait()", timeout=20))
        self.assertTrue(data["bench"]["results"])
        for result in data["bench"]["results"]:
            self.assertEqual(result["verdict"], "error")
            self.assertEqual(result["correctness"], 0)
            self.assertEqual(result["cost"], COST)
        self.assert_lifecycle()

    def test_a22_timeout_memory_failure_leaves_open_and_no_result(self):
        self.single()
        self.declare()
        # Evidence staging is unavailable beneath this otherwise usable home.
        original = runner.run_task
        def remove_lesson(*args, **kwargs):
            value = original(*args, **kwargs)
            value["memory_units"] = [u for u in value["memory_units"] if u["kind"] != "lesson"]
            return value
        with mock.patch.object(runner, "run_task", side_effect=remove_lesson):
            self.rejects("memory_debt", self.execute,
                         self.child("import threading;threading.Event().wait()", timeout=20), unchanged=False)
        self.assert_open_without_result()

    def test_a17_fresh_homes_reproduce_exact_ledger_bytes(self):
        self.single()
        self.declare()
        self.execute()
        first = self.raw()
        other = self.base / "second-home"
        other.mkdir()
        services = type(self.ctx.services)(**{**vars(self.ctx.services), "home": other,
                   "id_factory": lambda c=itertools.count(1): f"e-{next(c):016x}"})
        previous = self.home, self.ctx
        self.home, self.ctx = other, replace(self.ctx, home=other, services=services)
        self.operations = itertools.count(1)
        self.declare()
        self.execute()
        self.assertEqual(self.raw(), first)
        self.home, self.ctx = previous

    def test_a14_episode_only_before_open_cannot_satisfy_gate(self):
        self.single()
        self.declare()
        config = {"kind": "fake", "seed": 9}
        command = self.command("bench_run", {"bench_id": "bench0001", "runner": config}, op="before-open")
        original_prefix = self.raw()
        with self.interrupted_at("run.open"), self.assertRaises(Interrupted):
            self.execute(config, command)
        opened = self.events("run.open")[0]["payload"]
        subject = self.events("agent.born")[0]["payload"]["record"]
        enriched = {**self.bank["tasks"][0], "bank_id": "demo-offline", "bench_id": "bench0001", "run_id": opened["run_id"]}
        early = output_for(enriched, subject)["memory_units"][0]
        # A hostile historical fixture, not a simulated passing memory gate.
        self.ledger.write_bytes(original_prefix)
        self.tx("memory.put", {"agent_id": subject["agent_id"], "run_id": opened["run_id"], "unit": early}, actor=subject["agent_id"])
        original = runner.run_task
        def no_new_episode(*args, **kwargs):
            value = original(*args, **kwargs)
            value["memory_units"] = []
            return value
        with mock.patch.object(runner, "run_task", side_effect=no_new_episode):
            self.rejects("memory_required", self.execute, config, command, unchanged=False)
        self.assert_open_without_result()

    def test_a16_missing_receipt_file_is_not_valid_memory(self):
        def missing(value):
            value["memory_units"][0]["receipts"][0]["path"] = "evidence/missing.txt"
            return value
        self.poisoned_memory(missing, "hash_mismatch")

    def test_a15_red_without_negative_is_memory_debt(self):
        self.single(baseline="red")
        self.declare()
        original = runner.run_task
        def no_negative(*args, **kwargs):
            value = original(*args, **kwargs)
            value["memory_units"] = [u for u in value["memory_units"] if u["kind"] != "negative"]
            return value
        with mock.patch.object(runner, "run_task", side_effect=no_negative):
            self.rejects("memory_debt", self.execute, unchanged=False)
        self.assert_open_without_result()

    def test_a10_required_failure_memory_does_not_rebase_declaration(self):
        self.single(baseline="red", candidate="HOLD")
        self.declare()
        declaration_event = deepcopy(self.events("bench.declared")[0])
        self.execute()
        self.assertTrue(any(e["payload"]["unit"]["kind"] == "lesson" for e in self.events("memory.put")))
        self.assertEqual(self.events("bench.declared")[0], declaration_event)
        self.assertEqual(self.status()["declaration"], self.decl)
        self.verdict()
        self.assertFalse(self.events("agent.status"))

    def test_a13_run_open_actor_subject_mismatch_is_actor_mismatch(self):
        import importlib
        self.single()
        self.declare()
        runs = importlib.import_module("lineage.domain.runs")
        value = self.bank["tasks"][0]
        common = {k: value[k] for k in ("id", "kind", "language", "split")}
        common.update(bank_id="demo-offline", bench_id="bench0001")
        args = {"run_id": "wrongact1", "agent_id": "baseline-one", "seat": SEAT,
                "task": common, "parents_context": [], "memory_arm": "none"}
        error = self.rejects("bad_args", runs.open_run, "wrongact1", "baseline-one", SEAT, common,
                             parents_context=[], memory_arm="none",
                             command=self.command("run_open", args, actor="arena-caller"), ctx=self.ctx)
        self.assertEqual(error.detail, "actor_mismatch")
        self.assertFalse(self.events("run.open"))

    def test_a22_allowed_memory_repair_allows_timeout_recovery(self):
        import importlib
        self.single()
        self.declare()
        config = self.child("import threading;threading.Event().wait()", timeout=20)
        command = self.command("bench_run", {"bench_id": "bench0001", "runner": config}, op="repair-timeout")
        original = runner.run_task
        def no_lesson(*args, **kwargs):
            value = original(*args, **kwargs)
            value["memory_units"] = [u for u in value["memory_units"] if u["kind"] != "lesson"]
            return value
        with mock.patch.object(runner, "run_task", side_effect=no_lesson):
            self.rejects("memory_debt", self.execute, config, command, unchanged=False)
        self.assert_open_without_result()
        opened = self.events("run.open")[0]["payload"]
        owner = opened["agent_id"]
        subject = next(e["payload"]["record"] for e in self.events("agent.born") if e["payload"]["record"]["agent_id"] == owner)
        episode = next(e["payload"]["unit"] for e in self.events("memory.put") if e["payload"]["unit"]["kind"] == "episode")
        execution = {**self.bank["tasks"][0], "run_id": opened["run_id"], "bench_id": "bench0001", "bank_id": "demo-offline"}
        lesson = next(u for u in output_for(execution, subject, "error", receipt=episode["receipts"][0])["memory_units"] if u["kind"] == "lesson")
        units = importlib.import_module("lineage.domain.memory.units")
        self.invoke(units.put, owner, lesson, run_id=opened["run_id"],
                    command=self.command("memory_put", {"agent_id": owner, "unit": lesson, "run_id": opened["run_id"]}, actor=owner),
                    ctx=replace(self.ctx, actor=owner))
        def only_other(task_value, **kwargs):
            self.assertNotEqual(task_value["run_id"], opened["run_id"], "Recovered timeout must not rerun")
            return original(task_value, **kwargs)
        with mock.patch.object(runner, "run_task", side_effect=only_other):
            self.execute(config, command)
        self.assert_lifecycle()
        self.assertTrue(all(r["correctness"] == 0 for r in self.status()["results"]))
