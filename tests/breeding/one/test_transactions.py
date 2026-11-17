"""Real journal/dispatch integration gates. Missing U10/U12 never means ADMIT.

All admission-sensitive assertions use registry validators, not fixture validators.
The nominal source setup is identified in helpers and ORACLE.md.
"""
from contextlib import ExitStack
from copy import deepcopy
import fcntl
import hashlib
import importlib
import importlib.util
import multiprocessing
from pathlib import Path
import shutil
from unittest.mock import patch

from lineage.core import journal
from lineage.core.app import ToolError
from lineage.core.errors import LineageError
from lineage.domain.tree import tree
from .helpers import OracleCase, ROOT, SURFACE, TEST_ROOT, breed_process, canonical


class TransactionOracle(OracleCase):
    def source(self):
        self.seed(self.parent, units=[self.unit()])

    def successful_birth(self):
        self.source()
        result = self.breed()
        self.assert_commit(result)
        return result

    def owned_workers(self, requests):
        """Only exact Process objects started here can be terminated."""
        context = multiprocessing.get_context("spawn")
        start = context.Event()
        output = context.Queue()
        processes = []
        ready = []
        for parent_id, child_id, op_id in requests:
            signal = context.Event()
            process = context.Process(target=breed_process,
                                      args=(str(self.home), signal, start, output,
                                            parent_id, child_id, op_id))
            process.start()
            self.assertIsNotNone(process.pid)
            self.assertGreater(process.pid, 1)
            processes.append(process)
            ready.append(signal)
        def cleanup():
            for process in processes:
                if process.is_alive():
                    if process.pid is None or process.pid <= 1:
                        raise AssertionError("Refuse an unverified child PID")
                    process.terminate()
                process.join(.25)
                if process.is_alive():
                    raise AssertionError("Owned child did not terminate within bound")
            output.close()
            output.join_thread()
        self.addCleanup(cleanup)
        for signal in ready:
            self.assertTrue(signal.wait(.75), "Child readiness timed out")
        return start, output, processes

    def test_a15_actual_prepare_receives_assigned_id_mapping(self):
        """Gate: measured installed draft key; contrast: nonexistent event_id attribute."""
        observed = []
        def prepare(history, draft):
            observed.append((len(history), draft["id"]))
            return {"fixture_event_id": draft["id"]}
        event = journal.transact(self.home, agent="creator-one", op_id="draft-id-0001",
                                 kind="fixture.identity", payload={},
                                 validators={"fixture.identity": lambda history, event: None},
                                 prepare=prepare, clock=lambda: 1700000000000,
                                 id_factory=lambda: "e-1234567890abcdef")
        self.assertEqual(observed, [(0, event["id"])])
        self.assertEqual(event["payload"]["fixture_event_id"], event["id"])

    def test_a19_stale_expected_head_on_new_request_appends_nothing(self):
        self.source()
        self.refused("stale_rev", lambda: self.breed(expected_head=0))

    def test_a19_real_held_ledger_lock_gives_busy(self):
        self.source()
        with (self.home / "ledger" / "main" / "events.lock").open("rb") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                self.refused("busy", lambda: self.breed())
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def test_a19_short_and_punctuation_opids_are_not_silently_remapped(self):
        self.source()
        for index, op_id in enumerate(("x", "op:1/path.test", "a" * 128)):
            result = self.breed(child_id=f"child-{index}", op_id=op_id)
            event = self.assert_commit(result)
            self.assertEqual(event["op_id"], op_id)
            self.assertEqual(canonical(self.breed(child_id=f"child-{index}", op_id=op_id)), canonical(result))

    def test_a20_distinct_operations_competing_for_child_commit_once(self):
        self.successful_birth()
        self.require_owners()
        before = len(journal.snapshot(self.home))
        start, output, processes = self.owned_workers([
            ("child-one", "race-child", "race-operation-0001"),
            ("child-one", "race-child", "race-operation-0002")])
        start.set()
        results = [output.get(timeout=1) for _ in processes]
        self.assertEqual(sum("result" in result for result in results), 1)
        self.assertEqual([r["code"] for r in results if "code" in r], ["conflict"])
        after = journal.snapshot(self.home)
        self.assertEqual(len(after), before + 1)
        self.assertEqual(sum(e["kind"] == "agent.born" and e["payload"]["record"]["agent_id"] == "race-child" for e in after), 1)
        for process in processes:
            process.join(.25)
            self.assertEqual(process.exitcode, 0)

    def test_a20_identical_operation_racers_converge_on_original_prefix(self):
        self.successful_birth()
        self.require_owners()
        before = len(journal.snapshot(self.home))
        request = ("child-one", "race-child", "same-operation-0001")
        start, output, processes = self.owned_workers([request, request])
        start.set()
        results = [output.get(timeout=1) for _ in processes]
        self.assertTrue(all("result" in result for result in results), results)
        self.assertEqual(canonical(results[0]["result"]), canonical(results[1]["result"]))
        self.assertEqual(len(journal.snapshot(self.home)), before + 1)

    def test_a16_retirement_committed_before_waiting_child_breeds(self):
        """Gate: new authoritative lifecycle after captured prefix; contrast: cached eligibility."""
        self.successful_birth()
        self.require_owners()
        captured = journal.snapshot(self.home)
        start, output, _ = self.owned_workers([("child-one", "late-child", "late-operation-0001")])
        self.retire_agent("child-one", op_id="retire-child-0001")
        before = self.ledger_bytes()
        start.set()
        self.assertEqual(output.get(timeout=1), {"code": "conflict"})
        self.assertEqual(self.ledger_bytes(), before)
        self.assertLess(len(captured), len(journal.snapshot(self.home)))

    def forged_birth(self, mutate, *, actor="creator-one"):
        self.successful_birth()
        self.require_owners()
        event = deepcopy(journal.snapshot(self.home)[-1])
        # Restore the actual pre-birth prefix; duplicate-child refusal cannot mask
        # a missing inheritance validator. Projections deliberately remain stale.
        path = self.home / "ledger" / "main" / "events.jsonl"
        lines = path.read_bytes().splitlines(keepends=True)
        path.write_bytes(b"".join(lines[:-1]))
        candidate = deepcopy(event["payload"])
        mutate(candidate)
        before = self.ledger_bytes()
        with self.assertRaises((LineageError, ToolError)) as caught:
            journal.transact(self.home, agent=actor, op_id="forged-operation-0001",
                             kind="agent.born", payload=candidate,
                             # A-U17: installed U12 owners require home-aware ctx binding.
                             validators=self.admission_validators(),
                             clock=lambda: event["ts"], id_factory=lambda: event["id"])
        self.assertIn(caught.exception.code, {"bad_args", "hash_mismatch", "not_inheritable", "conflict", "memory_debt"})
        self.assertEqual(self.ledger_bytes(), before)

    def test_a17_false_source_hash_bare_event_is_refused(self):
        self.forged_birth(lambda p: p["inherited_units"][0].__setitem__("unit_sha256", "0" * 64))

    def test_a17_false_provenance_bare_event_is_refused(self):
        self.forged_birth(lambda p: p["inherited_units"][0]["unit"]["provenance"]["inherited_from"].__setitem__("unit_sha256", "0" * 64))

    def test_a17_private_child_unit_bare_event_is_refused(self):
        self.forged_birth(lambda p: p["inherited_units"][0]["unit"].__setitem__("privacy", "private"))

    def test_a17_level_three_bare_event_is_refused(self):
        self.forged_birth(lambda p: p["inherited_units"][0]["unit"].__setitem__("level", 3))

    def test_a17_operator_actor_cannot_inject_rulings(self):
        def mutate(payload):
            unit = payload["inherited_units"][0]["unit"]
            unit.update(kind="ruling", level=1,
                        body={"quote_sha256": "0" * 64, "how_to_apply": "Hostile authority"})
        self.forged_birth(mutate, actor="operator")

    def test_a15_promoted_child_bare_event_is_refused(self):
        self.forged_birth(lambda p: p["record"].__setitem__("status", "promoted"))

    def test_a15_missing_founding_pin_bare_event_is_refused(self):
        self.forged_birth(lambda p: p["record"]["references"].pop())

    def test_a15_extra_birth_key_bare_event_is_refused(self):
        self.forged_birth(lambda p: p.__setitem__("gate", {"passed": True}))

    def test_a15_wrong_version_bare_event_is_refused(self):
        self.forged_birth(lambda p: p["record"].__setitem__("agent_version", "0" * 64))

    def test_a15_altered_constitution_bare_event_is_refused(self):
        self.forged_birth(lambda p: p["constitution"].__setitem__("text", "Forged constitution\n"))

    def test_a17_unrestricted_status_bare_event_is_refused(self):
        self.successful_birth()
        self.require_owners()
        self.refused("conflict", lambda: journal.transact(
            self.home, agent="creator-one", op_id="forged-status-0001", kind="agent.status",
            payload={"agent_id": "child-one", "from": "draft", "to": "promoted", "reason": "No benchmark"},
            # A-U17: use the same production context binding as breeding tools.
            validators=self.admission_validators(), clock=lambda: 1700000001000))

    def projection_bytes(self):
        return {p.relative_to(self.home).as_posix(): p.read_bytes() for p in self.home.rglob("*")
                if p.is_file() and not p.is_symlink() and
                p.relative_to(self.home).parts[0] not in {"ledger", "receipts", "family"}}

    def test_a28_projection_tamper_delete_and_exact_retry_rebuild(self):
        self.source()
        before = self.projection_bytes()
        first = self.breed()
        self.require_owners()
        original = self.projection_bytes()
        new = set(original) - set(before)
        self.assertTrue(new, "HOLD: child projection service/artifacts AUSENTE")
        for rel in sorted(new):
            (self.home / rel).write_bytes(b"tampered disposable projection")
        self.assertEqual(self.public_call("agent_get", {"agent_id": "child-one"})["untrusted"]["record"], first["record"])
        for rel in sorted(new):
            (self.home / rel).unlink()
        replay = self.breed()
        self.assertEqual(canonical(replay), canonical(first))
        self.assertEqual(self.projection_bytes(), original)
        for rel, data in before.items():
            self.assertEqual((self.home / rel).read_bytes(), data)

    def test_a29_durable_birth_then_partial_projection_failure_retry_repairs(self):
        self.successful_birth()
        self.require_owners()
        self.assertIsNotNone(importlib.util.find_spec("lineage.domain.agents"),
                             "HOLD: U12 projection service AUSENTE")
        owner = importlib.import_module("lineage.domain.agents")
        self.assertTrue(callable(getattr(owner, "materialize", None)),
                        "HOLD: installed projection adapter unproven")
        original = owner.materialize
        projected = {}
        def injected(*args, **kwargs):
            paths = original(*args, **kwargs)
            for path in paths:
                path = Path(path)
                if path.is_file():
                    projected[path] = path.read_bytes()
            self.assertTrue(projected, "No projected files to fault")
            next(iter(projected)).unlink()
            raise OSError("Fixture projection fault")
        previous_head = len(journal.snapshot(self.home))
        modules = [owner] + [importlib.import_module(name) for name in (
            "lineage.domain.breeding", "lineage.domain.breeding.clone", "lineage.domain.breeding.distill")]
        with ExitStack() as stack:
            for module in modules:
                for name, value in list(vars(module).items()):
                    if value is original:
                        stack.enter_context(patch.object(module, name, injected))
            with self.assertRaises((LineageError, ToolError)) as caught:
                self.breed(child_id="partial-child", op_id="partial-operation-0001")
            self.assertEqual(caught.exception.code, "internal")
        self.assertEqual(len(journal.snapshot(self.home)), previous_head + 1)
        event = journal.snapshot(self.home)[-1]
        result = self.breed(child_id="partial-child", op_id="partial-operation-0001")
        self.assertEqual(result["commit"], {"event_ids": [event["id"]], "head": event["lamport"], "sha256": event["sha256"]})
        self.assertEqual(len(journal.snapshot(self.home)), previous_head + 1)
        for path, data in projected.items():
            self.assertEqual(path.read_bytes(), data)

    def test_a33_public_surface_has_no_private_coordinates_or_new_dependencies(self):
        tree(ctx=self.ctx)
        import ast
        import re
        files = [ROOT / rel for rel in SURFACE] + list(TEST_ROOT.glob("*.py")) + [TEST_ROOT / "ORACLE.md"]
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"/(?:home|Users)/[A-Za-z0-9]", text), path.name)
            # A-U17: construct the forbidden fixture token without self-matching.
            self.assertNotIn("receipt" + "_spool", text)
            if path.suffix == ".py":
                ast.parse(text)
                for node in ast.walk(ast.parse(text)):
                    if isinstance(node, ast.Import):
                        imports = [alias.name.split(".")[0] for alias in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.level == 0:
                        imports = [(node.module or "").split(".")[0]]
                    else:
                        continue
                    import sys
                    for name in imports:
                        self.assertTrue(name == "lineage" or name in sys.stdlib_module_names,
                                        "New dependency: " + name)


def _episode_bypass(self):
    def mutate(payload):
        original_id = payload["inherited_units"][0]["unit"]["id"]
        episode = self.unit(original_id, kind="episode")
        episode["provenance"]["inherited_from"] = deepcopy(payload["inherited_units"][0]["unit"]["provenance"]["inherited_from"])
        payload["inherited_units"][0]["unit"] = episode
    self.forged_birth(mutate)
TransactionOracle.test_a17_episode_bare_event_is_refused = _episode_bypass


def _promoted_seat_bypass(self):
    from .helpers import SEAT
    self.forged_birth(lambda p: p["record"].__setitem__("promoted_seat", deepcopy(SEAT)))
TransactionOracle.test_a15_inherited_promoted_seat_bare_event_is_refused = _promoted_seat_bypass
