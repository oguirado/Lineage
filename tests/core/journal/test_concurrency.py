"""A6, A10, A14, A34: real independent processes; no fixed sleeps or groups."""
import time
from ._support import CoreCase, independent_verify


class ConcurrencyTests(CoreCase):
    def test_a6_eight_independent_writers_sixteen_operations_each(self):
        self.install()
        children = [self.child("batch", index=index, wait=True) for index in range(8)]
        deadline = time.monotonic() + 3.5
        for process, pipe in children:
            self.assertEqual(self.receive(pipe, max(0, deadline - time.monotonic())), ("ready", "batch"))
        for process, pipe in children:
            pipe.send("go")
        returned = []
        for process, pipe in children:
            status, result = self.receive(pipe, max(0, deadline - time.monotonic()))
            self.assertEqual(status, "ok", result)
            returned.extend(result)
            self.finished(process, max(0, deadline - time.monotonic()))
        history = independent_verify(self.bytes())
        self.assertEqual(len(history), 128)
        self.assertEqual(len({entry["id"] for entry in history}), 128)
        self.assertEqual([entry["lamport"] for entry in history], list(range(1, 129)))
        self.assertEqual({(e["payload"]["writer"], e["payload"]["item"]) for e in history},
                         {(writer, item) for writer in range(8) for item in range(16)})
        self.assertEqual({e["id"] for e in returned}, {e["id"] for e in history})
        self.assertIs(self.journal.verify(self.home)["ok"], True)

    def test_a10_gate_stays_inside_fence_through_commit(self):
        self.install()
        first, first_pipe = self.child("call", claim_gate=True, pause=True, op_id="first-claim")
        self.assertEqual(self.receive(first_pipe), ("entered", 0))
        try:
            contender, contender_pipe = self.child("call", claim_gate=True, timeout=0,
                                                  op_id="second-claim", id="e-ffffffffffffffff")
            self.assertEqual(self.receive(contender_pipe), ("error", "busy"),
                             "A contender entered validation outside the lock")
            self.finished(contender)
        finally:
            first_pipe.send("release")
        self.assertEqual(self.receive(first_pipe)[0], "ok")
        self.finished(first)
        contender, contender_pipe = self.child("call", claim_gate=True, op_id="second-claim",
                                              id="e-ffffffffffffffff")
        self.assertEqual(self.receive(contender_pipe), ("entered", 1))
        self.assertEqual(self.receive(contender_pipe), ("error", "conflict"))
        self.finished(contender)
        self.assertEqual(len(independent_verify(self.bytes())), 1)

    def test_a14_simultaneous_identical_requests_commit_once(self):
        self.install()
        children = [self.child("call", wait=True) for _ in range(2)]
        for process, pipe in children:
            self.assertEqual(self.receive(pipe), ("ready", "call"))
        for process, pipe in children:
            pipe.send("go")
        results = []
        for process, pipe in children:
            status, value = self.receive(pipe)
            self.assertEqual(status, "ok", value)
            results.append(value)
            self.finished(process)
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(independent_verify(self.bytes())), 1)

    def test_a14_simultaneous_conflicting_requests_have_one_winner(self):
        self.install()
        children = [self.child("call", wait=True, payload={"value": value}) for value in (1, 2)]
        for process, pipe in children:
            self.assertEqual(self.receive(pipe), ("ready", "call"))
        for process, pipe in children:
            pipe.send("go")
        results = [self.receive(pipe) for process, pipe in children]
        for process, pipe in children:
            self.finished(process)
        self.assertEqual(sum(status == "ok" for status, value in results), 1)
        self.assertIn(("error", "bad_op"), results)
        winner = next(value for status, value in results if status == "ok")
        self.assertEqual(independent_verify(self.bytes()), (winner,))

    def test_a34_readers_never_observe_locked_partial_append(self):
        self.tx()
        process, pipe = self.child("paused_write")
        self.assertEqual(self.receive(pipe), ("partial", 7))
        try:
            for read in (self.journal.snapshot, self.journal.verify):
                with self.assertRaises(self.error) as caught:
                    read(self.home, lock_timeout_s=0)
                self.assertEqual(caught.exception.code, "busy")
        finally:
            pipe.send("release")
        self.assertEqual(self.receive(pipe)[0], "ok")
        self.finished(process)
        self.assertEqual(len(self.journal.snapshot(self.home)), 2)
        self.assertIs(self.journal.verify(self.home)["ok"], True)
        independent_verify(self.bytes())
