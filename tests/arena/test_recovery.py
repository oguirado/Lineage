"""Deterministic stages, frozen retries, races, direct append and crash recovery."""
from copy import deepcopy
from dataclasses import replace
import json
import re
import threading
from unittest import mock

from lineage.core import journal
from lineage.core.errors import LineageError
from .helpers import (ArenaCase, Interrupted, bank_data, bench, canonical,
                      command_source, declaration, runner, task)


class RecoveryTests(ArenaCase):
    def single(self):
        self.bank = bank_data([task(1, baseline="green")])
        self.write_bank(self.bank)
        self.decl = declaration(self.bank)

    def run_command(self, config=None, op="root-operation"):
        config = config or {"kind": "fake", "seed": 3}
        return config, self.command("bench_run", {"bench_id": "bench0001", "runner": config}, op=op)

    def test_a24_stale_initial_head_refuses_before_open(self):
        self.declare()
        config, command = self.run_command()
        self.rejects("stale_rev", bench.run, "bench0001", config,
                     command=replace(command, expected_head=0), ctx=self.ctx)
        self.assertFalse(self.events("run.open"))
        command = replace(command, expected_head=self.events()[-1]["lamport"])
        first = self.execute(config, command)
        before = self.raw()
        self.assertEqual(self.execute(config, replace(command, expected_head=0)), first)
        self.assertEqual(self.raw(), before)

    def test_a24_seed_argv_timeout_changes_are_bad_op_before_reexecution(self):
        self.single()
        self.declare()
        config, command = self.run_command()
        self.execute(config, command)
        changed = [{"kind": "fake", "seed": 4},
                   {"kind": "command", "argv": ["literal-program"], "timeout_ms": 1}]
        for value in changed:
            with mock.patch.object(runner, "run_task", side_effect=AssertionError("reexecution")) as spy:
                self.rejects("bad_op", bench.run, "bench0001", value,
                    command=replace(command, args={**command.args, "runner": value}), ctx=self.ctx)
                spy.assert_not_called()

    def test_a24_child_ids_bounded_and_request_fields_not_polluted(self):
        self.single()
        self.declare()
        config, command = self.run_command()
        self.execute(config, command)
        children = [e for e in self.events() if e["kind"] in ("run.open", "memory.put", "run.close", "bench.result")]
        self.assertTrue(children)
        self.assertEqual(len({(e["agent"], e["op_id"]) for e in children}), len(children))
        for event in children:
            self.assertRegex(event["op_id"], r"\A[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
            self.assertNotIn("stage", event["payload"])
            self.assertNotIn("runner", event["payload"])
        for event in self.events("run.open"):
            self.assertRegex(event["payload"]["run_id"], r"\A[A-Za-z0-9_-]{8,64}\Z")

    def test_a25_fake_crash_after_open_resumes_without_second_run(self):
        self.single()
        self.declare()
        config, command = self.run_command()
        with self.interrupted_at("run.open"), self.assertRaises(Interrupted):
            self.execute(config, command)
        opened = deepcopy(self.events("run.open")[0])
        self.execute(config, command)
        self.assertEqual(self.events("run.open")[0], opened)
        self.assertEqual(len(self.events("run.open")), 2)
        self.assertEqual(len(self.events("bench.result")), 2)
        self.assert_lifecycle()

    def test_a25_command_crash_after_open_is_ambiguous_not_rerun(self):
        self.single()
        self.declare()
        config, command = self.run_command(self.child(command_source()))
        with self.interrupted_at("run.open"), self.assertRaises(Interrupted):
            self.execute(config, command)
        with mock.patch.object(runner, "run_task", side_effect=AssertionError("ambiguous rerun")) as spy:
            self.rejects("conflict", bench.run, "bench0001", config, command=command, ctx=self.ctx)
            spy.assert_not_called()
        self.assert_open_without_result()

    def stage_output(self):
        self.single()
        receipt = self.home / "evidence/fixture.txt"
        receipt.parent.mkdir()
        receipt.write_bytes(b"fixture\n")
        self.declare()
        config, command = self.run_command(self.child(command_source()))
        with self.interrupted_at("memory.put", after=False), self.assertRaises(Interrupted):
            self.execute(config, command)
        self.assertTrue(self.events("run.open"))
        self.assertFalse(self.events("memory.put"))
        return config, command

    def test_a26_durable_output_recovery_never_reexecutes_completed_cell(self):
        config, command = self.stage_output()
        run_id = self.events("run.open")[0]["payload"]["run_id"]
        original = runner.run_task
        def only_new(task_value, **kwargs):
            self.assertNotEqual(task_value["run_id"], run_id, "Durable output must be reused")
            return original(task_value, **kwargs)
        with mock.patch.object(runner, "run_task", side_effect=only_new):
            self.execute(config, command)
        self.assert_lifecycle()
        self.assertEqual(len(self.events("bench.result")), 2)

    def test_a26_tampered_staging_cannot_authorize_completion(self):
        config, command = self.stage_output()
        candidates = []
        for path in self.home.rglob("*"):
            if not path.is_file() or path.is_symlink() or path.is_relative_to(self.home / "ledger"):
                continue
            try:
                value = json.loads(path.read_bytes())
            except (ValueError, UnicodeError):
                continue
            if isinstance(value, dict) and ("memory_units" in str(value) or "runner" in value):
                candidates.append(path)
        self.assertTrue(candidates, "Recovery needs verifiable durable command output")
        for path in candidates:
            path.write_bytes(path.read_bytes() + b"tampered")
        before = self.raw()
        with self.assertRaises(LineageError) as error:
            self.invoke(bench.run, "bench0001", config, command=command, ctx=self.ctx)
        self.assertIn(error.exception.code, ("conflict", "hash_mismatch", "internal"))
        self.assertEqual(self.raw(), before)
        self.assert_open_without_result()

    def test_a27_crash_after_memory_reuses_committed_units(self):
        self.single()
        self.declare()
        config, command = self.run_command()
        with self.interrupted_at("memory.put"), self.assertRaises(Interrupted):
            self.execute(config, command)
        first_memory = deepcopy(self.events("memory.put")[0])
        self.execute(config, command)
        self.assertEqual(self.events("memory.put")[0], first_memory)
        ids = [e["payload"]["unit"]["id"] for e in self.events("memory.put")]
        self.assertEqual(len(ids), len(set(ids)))
        self.assert_lifecycle()

    def test_a27_crash_after_close_appends_result_without_runner(self):
        self.single()
        self.declare()
        config, command = self.run_command()
        with self.interrupted_at("run.close"), self.assertRaises(Interrupted):
            self.execute(config, command)
        closed = deepcopy(self.events("run.close")[0])
        closed_id = closed["payload"]["record"]["run_id"]
        original = runner.run_task
        def only_new(task_value, **kwargs):
            self.assertNotEqual(task_value["run_id"], closed_id)
            return original(task_value, **kwargs)
        with mock.patch.object(runner, "run_task", side_effect=only_new):
            self.execute(config, command)
        self.assertEqual(self.events("run.close")[0], closed)
        self.assertEqual(len(self.events("run.close")), 2)
        self.assertEqual(len(self.events("bench.result")), 2)

    def test_a28_frozen_compound_replay_and_event_digest(self):
        self.single()
        self.declare()
        config, command = self.run_command()
        first = self.execute(config, command)
        results = self.events("bench.result")
        self.assertEqual(first["commit"], {"event_ids": [e["id"] for e in results],
            "head": results[-1]["lamport"], "sha256": results[-1]["sha256"]})
        self.tx("unrelated", {"passive": True})
        before = self.raw()
        self.assertEqual(canonical(self.execute(config, command)), canonical(first))
        self.assertEqual(self.raw(), before)
        self.assertGreater(self.status()["head"], first["commit"]["head"])
        self.assertNotIn("bench.complete", {e["kind"] for e in self.events()})

    def test_a23_runner_unlocked_while_unrelated_mutation_commits(self):
        self.single()
        self.declare()
        entered, release = threading.Event(), threading.Event()
        replies = []
        original = runner.run_task
        def blocked(*args, **kwargs):
            entered.set()
            release.wait()
            return original(*args, **kwargs)
        def execute():
            try:
                replies.append(self.execute())
            except BaseException as exc:
                replies.append(exc)
        thread = threading.Thread(target=execute, daemon=True)
        with mock.patch.object(runner, "run_task", side_effect=blocked):
            thread.start()
            try:
                self.assertTrue(entered.wait(60), "Runner did not reach the barrier")
                event = self.tx("unrelated", {"during_runner": True})
                self.assertEqual(event["kind"], "unrelated")
            finally:
                release.set()
                thread.join(60)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(replies), 1)
        if isinstance(replies[0], BaseException):
            raise replies[0]
        self.assert_lifecycle()

    def test_a29_identical_callers_never_start_same_cell_twice(self):
        self.single()
        self.declare()
        receipt = self.home / "evidence/fixture.txt"
        receipt.parent.mkdir()
        receipt.write_bytes(b"fixture\n")
        config, command = self.run_command(self.child(command_source(), timeout=60000))
        entered, release = threading.Event(), threading.Event()
        starts, replies = [], []
        contender_done = threading.Event()
        original = runner.run_task
        def blocked(value, **kwargs):
            starts.append(value["run_id"])
            entered.set()
            release.wait()
            return original(value, **kwargs)
        def execute():
            try:
                replies.append(self.execute(config, command))
            except BaseException as exc:
                replies.append(exc)
        def contend():
            try:
                execute()
            finally:
                contender_done.set()
        threads = [threading.Thread(target=target, daemon=True)
                   for target in (execute, contend)]
        with mock.patch.object(runner, "run_task", side_effect=blocked):
            threads[0].start()
            try:
                self.assertTrue(entered.wait(60))
                threads[1].start()
                # Keep the first runner blocked until contention is observed.
                self.assertTrue(contender_done.wait(60), "Contender did not finish its claim")
            finally:
                release.set()
                for thread in threads:
                    if thread.ident:
                        thread.join(60)
        self.assertTrue(all(not t.is_alive() for t in threads))
        self.assertEqual(len(starts), len(set(starts)))
        self.assertEqual(len(self.events("bench.result")), 2)
        successes = [x for x in replies if isinstance(x, dict)]
        self.assertTrue(successes)
        for value in replies:
            if isinstance(value, LineageError):
                self.assertIn(value.code, ("busy", "conflict"))
            else:
                self.assertEqual(value, successes[0])

    def test_a30_spoofed_result_matrix_direct_registered_admission(self):
        self.single()
        self.declare()
        self.execute()
        good = self.status()["results"][0]
        variants = []
        for field, value in (("agent_id", "other-agent"), ("run_id", "unknown1"),
                             ("task_id", "wrongtask"), ("memory_arm", "inherited"),
                             ("verdict", "error"), ("correctness", True)):
            variants.append({**deepcopy(good), field: value})
        for field, value in (("effort", "other"), ("mode", "interactive")):
            changed = deepcopy(good)
            changed["seat"][field] = value
            variants.append(changed)
        for field in good["cost"]:
            changed = deepcopy(good)
            changed["cost"][field] = 9 if good["cost"][field] != 9 else 10
            variants.append(changed)
        for changed in variants:
            with self.subTest(changed=changed):
                before = self.raw()
                with self.assertRaises(LineageError) as error:
                    self.direct("bench.result", changed)
                self.assertIn(error.exception.code, ("bad_args", "conflict"))
                self.assertEqual(self.raw(), before)
        self.rejects("conflict", self.direct, "bench.result", good)

    def test_a41_result_without_actual_close_witness_is_rejected(self):
        self.declare()
        self.rejects("conflict", self.direct, "bench.result", self.result())
        self.assertFalse(self.events("bench.result"))

    def test_a31_pagination_defensive_reads_and_no_cache_authority(self):
        self.declare()
        for identifier in ("bench0003", "bench0002"):
            self.declare({**self.decl, "bench_id": identifier})
        before = self.raw()
        page = self.invoke(bench.list_benches, limit=2, ctx=self.ctx)
        self.assertEqual([b["declaration"]["bench_id"] for b in page["benches"]], ["bench0001", "bench0002"])
        self.assertEqual(page["next_after"], "bench0002")
        last = self.invoke(bench.list_benches, after=page["next_after"], limit=2, ctx=self.ctx)
        self.assertEqual([b["declaration"]["bench_id"] for b in last["benches"]], ["bench0003"])
        self.assertIsNone(last["next_after"])
        page["benches"][0]["declaration"]["agents"].clear()
        self.assertEqual(self.status()["declaration"], self.decl)
        self.assertEqual(self.raw(), before)

    def test_a31_unreadable_journal_is_internal_never_empty(self):
        self.declare()
        self.ledger.unlink()
        self.ledger.mkdir()
        with self.assertRaises(LineageError) as error:
            self.invoke(bench.list_benches, ctx=self.ctx)
        self.assertEqual(error.exception.code, "internal")

    def test_a32_declared_running_complete_and_explicit_verdict(self):
        self.single()
        self.declare()
        self.assertEqual(self.status()["state"], "declared")
        self.assertIsNone(self.status()["verdict"])
        config, command = self.run_command()
        with self.interrupted_at("run.open"), self.assertRaises(Interrupted):
            self.execute(config, command)
        self.assertEqual(self.status()["state"], "running")
        self.rejects("conflict", bench.verdict, "bench0001",
                     command=self.command("bench_verdict", {"bench_id": "bench0001"}), ctx=self.ctx)
        self.execute(config, command)
        self.assertEqual(self.status()["state"], "complete")
        self.assertIsNone(self.status()["verdict"])
        self.verdict()
        self.assertIsNotNone(self.status()["verdict"])

    def test_a7_direct_result_without_declaration_is_refused(self):
        self.rejects("rule_not_declared", self.direct, "bench.result", self.result())
        self.assertFalse(self.events())

    def test_a30_open_run_cannot_be_consumed_as_closed_result(self):
        self.single()
        self.declare()
        config, command = self.run_command()
        with self.interrupted_at("run.open"), self.assertRaises(Interrupted):
            self.execute(config, command)
        opened = self.events("run.open")[0]["payload"]
        result = {**self.result(), "run_id": opened["run_id"], "task_id": opened["task"]["id"],
                  "verdict": "green", "correctness": 1}
        self.rejects("conflict", self.direct, "bench.result", result)
        self.assert_open_without_result()

    def test_a31_rebuild_after_deleting_non_authoritative_caches(self):
        import shutil
        self.single()
        self.declare()
        self.execute()
        expected = deepcopy(self.status())
        for path in self.home.iterdir():
            if path.name in ("ledger", "evidence", "rulings"):
                continue
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        before = self.raw()
        self.assertEqual(self.status(), expected)
        self.assertEqual(self.raw(), before)

    def test_a24_command_argv_and_timeout_changed_under_retained_identity(self):
        self.single()
        self.declare()
        receipt = self.home / "evidence/fixture.txt"
        receipt.parent.mkdir()
        receipt.write_bytes(b"fixture\n")
        config, command = self.run_command(self.child(command_source()))
        self.execute(config, command)
        for field, value in (("argv", [*config["argv"], "changed"]), ("timeout_ms", config["timeout_ms"] + 1)):
            changed = {**config, field: value}
            with mock.patch.object(runner, "run_task", side_effect=AssertionError("changed-root rerun")) as spy:
                self.rejects("bad_op", bench.run, "bench0001", changed,
                             command=replace(command, args={**command.args, "runner": changed}), ctx=self.ctx)
                spy.assert_not_called()
