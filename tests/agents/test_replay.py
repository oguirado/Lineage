"""Operation identity, lock serialization, replay prefixes and atomic refusal."""
from copy import deepcopy
import fcntl
from queue import Queue
import threading
from lineage.core import journal
from lineage.core.errors import LineageError
from . import OracleCase, agents, canonical, unit


class ReplayTests(OracleCase):
    def test_a13_exact_retry_returns_original_prefix_after_later_activity(self):
        args = self.arguments()
        command = self.command(args)
        first = self.create(command=command)
        original = canonical(first.value)
        self.append_fixture("memory.put", {"agent_id": "agent-one", "unit": unit()})
        before = self.ledger()
        replay = self.create(command=command)
        self.assertEqual(canonical(replay.value), original)
        self.assertEqual(self.ledger(), before)
        self.assertEqual(replay.value["commit"]["head"], first.value["commit"]["head"])
        self.assertLess(first.value["commit"]["head"], len(journal.snapshot(self.home)))

    def test_a14_changed_effective_content_is_bad_op(self):
        args = self.arguments()
        command = self.command(args)
        self.create(command=command)
        for change in ({"display_name": "Changed"}, {"language": "general"},
                       {"workflow": "review"}, {"allowed_seats": [{"model": "other", "effort": "medium", "mode": "headless"}]},
                       {"references": [{**args["references"][0], "sha256": "f" * 64}, args["references"][1]]},
                       {"skills": [{"skill_id": "other-skill", "sha256": "f" * 64}]}):
            changed = self.arguments(**change)
            reused = self.command(changed, op_id=command.op_id)
            self.reject("bad_op", agents.create, **changed, command=reused, ctx=self.ctx)

    def test_a14_tool_identity_binds_request_digest(self):
        args = self.arguments()
        command = self.command(args)
        self.create(command=command)
        changed = self.command(args, op_id=command.op_id, tool="agent_clone")
        self.reject("bad_op", agents.create, **args, command=changed, ctx=self.ctx)

    def test_a14_expected_head_change_does_not_defeat_replay(self):
        args = self.arguments()
        command = self.command(args)
        first = self.create(command=command)
        self.seed("later-one")
        changed = self.command(args, op_id=command.op_id, expected_head=900)
        before = self.ledger()
        self.assertEqual(self.create(command=changed).value, first.value)
        self.assertEqual(self.ledger(), before)

    def test_a15_duplicate_id_distinct_operations_conflict_even_retired(self):
        self.create()
        args = self.arguments(display_name="Replacement")
        self.reject("conflict", agents.create, **args, command=self.command(args), ctx=self.ctx)
        self.seed("retired-one", status="retired")
        args = self.arguments(agent_id="retired-one")
        self.reject("conflict", agents.create, **args, command=self.command(args), ctx=self.ctx)

    def test_a16_real_journal_concurrent_duplicate_identity(self):
        barrier, results = threading.Barrier(2, timeout=1), Queue()
        args = self.arguments()
        commands = [self.command(args), self.command(args)]
        def worker(command):
            try:
                barrier.wait()
                value = agents.create(**deepcopy(args), command=command, ctx=self.ctx)
                results.put(("committed", value))
            except Exception as exc:
                results.put(("error", exc))
        threads = [threading.Thread(target=worker, args=(command,), daemon=True) for command in commands]
        for thread in threads:
            thread.start()
        replies = [results.get(timeout=1.5), results.get(timeout=1.5)]
        for thread in threads:
            thread.join(timeout=0.2)
            self.assertFalse(thread.is_alive(), "owned worker exceeded lock deadline")
        for status, value in replies:
            if isinstance(value, NotImplementedError):
                self.fail("U12 stub: concurrent genesis is not implemented")
        self.assertEqual(sum(status == "committed" for status, _ in replies), 1)
        failures = [value for status, value in replies if status == "error"]
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], LineageError)
        self.assertEqual(failures[0].code, "conflict")
        self.assertEqual(len(self.assert_chain()), 1)

    def test_a17_stale_expected_head_is_atomic(self):
        self.seed("first-one")
        args = self.arguments()
        self.reject("stale_rev", agents.create, **args,
                    command=self.command(args, expected_head=0), ctx=self.ctx)

    def test_a17_real_held_ledger_lock_is_busy(self):
        self.seed("first-one")
        lock = self.home / "ledger/main/events.lock"
        with lock.open("r+b") as owned:
            fcntl.flock(owned.fileno(), fcntl.LOCK_EX)
            try:
                args = self.arguments()
                self.reject("busy", agents.create, **args, command=self.command(args), ctx=self.ctx)
            finally:
                fcntl.flock(owned.fileno(), fcntl.LOCK_UN)
