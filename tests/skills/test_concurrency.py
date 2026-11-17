"""Bounded independent-process races, synchronized with barriers and lock callbacks."""
import copy
import hashlib
import importlib
import itertools
import multiprocessing
from pathlib import Path
import time

from tests.skills import FILES, PIN, ROOT, RuntimeCase, Command, independent_pin, one, skills


def child_context(home, tag, actor="tester"):
    # A-U09: use integrated CallContext rather than absent Services/Context exports.
    from lineage.core.app import create_context
    from lineage.core.registry import load
    return create_context(home, registry=load(), actor=actor)


def worker(home, tag, tool, args, barrier, connection):
    try:
        regmod = importlib.import_module("lineage.core.registry")
        ctx = child_context(home, tag, args["agent"])
        # A-U09: independent command fixture feeds the domain adapter.
        command = Command(tool=tool, args=args, agent=args["agent"],
                                 op_id=args["op_id"], expected_head=args.get("expected_head"))
        barrier.wait(timeout=1.5)
        if tool == "skill_publish":
            result = skills.publish(args["skill_id"], args["files"], command=command, ctx=ctx)
        else:
            result = skills.retire(args["skill_id"], args["sha256"], args["reason"], command=command, ctx=ctx)
        connection.send(("ok", result.value))
    except Exception as exc:
        connection.send(("error", getattr(exc, "code", type(exc).__name__)))
    finally:
        connection.close()


def lock_owner(home, ready, release, connection):
    try:
        # A-U09: block the real integrated two-argument prepare callback under its lock.
        journal = importlib.import_module("lineage.core.journal")
        ctx = child_context(home, "lock-owner")
        payload = {"skill_id": "lock-holder", "sha256": independent_pin(one("held")),
                   "files": one("held")}
        def prepare(history, draft):
            ready.set()
            if not release.wait(timeout=2.5):
                raise RuntimeError("lock fixture release timeout")
            return payload
        journal.transact(ctx.home, agent="tester", op_id="lock-owner",
                         kind="skill.published", payload=payload,
                         validators=ctx.validators, prepare=prepare)
        connection.send(("ok", None))
    except Exception as exc:
        connection.send(("error", getattr(exc, "code", type(exc).__name__)))
    finally:
        connection.close()


class ConcurrencyOracle(RuntimeCase):
    def reap_owned(self, process):
        # multiprocessing owns this exact child; no process groups or broad signals.
        if process.pid is not None:
            self.assertGreater(process.pid, 1)
            if process.is_alive():
                process.terminate()
            process.join(timeout=0.2)
            if process.is_alive():
                process.kill()
                process.join(timeout=0.2)

    def race(self, requests):
        engine = multiprocessing.get_context("fork")
        barrier = engine.Barrier(len(requests) + 1, timeout=1.5)
        processes = []
        pipes = []
        deadline = time.monotonic() + 3.5
        for index, (tool, args) in enumerate(requests):
            receiving, sending = engine.Pipe(duplex=False)
            process = engine.Process(target=worker, args=(str(self.home), self.id() + str(index),
                                                         tool, args, barrier, sending))
            process.start()
            sending.close()
            self.addCleanup(self.reap_owned, process)
            self.addCleanup(receiving.close)
            processes.append(process)
            pipes.append(receiving)
        barrier.wait(timeout=1.5)
        results = []
        for pipe in pipes:
            self.assertTrue(pipe.poll(max(0, deadline - time.monotonic())), "worker response exceeded bound")
            results.append(pipe.recv())
        for process in processes:
            process.join(timeout=max(0, deadline - time.monotonic()))
            self.assertFalse(process.is_alive())
            self.assertEqual(process.exitcode, 0)
        self.assert_chain()
        return results

    def publication(self, op, files=None, skill_id="sample"):
        return "skill_publish", {"skill_id": skill_id, "files": copy.deepcopy(FILES if files is None else files),
                                 "agent": "tester", "op_id": op}

    def test_a23_same_identity_identical_requests_have_one_event(self):
        request = self.publication("same-operation")
        results = self.race([request, copy.deepcopy(request)])
        self.assertEqual([r[0] for r in results], ["ok", "ok"])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(len(self.events()), 1)
        self.assert_projection()
        self.assertEqual(self.publish(op="same-operation").value, results[0][1])

    def test_a23_same_identity_changed_request_admits_exactly_one(self):
        results = self.race([self.publication("contended", one("first")),
                             self.publication("contended", one("second"))])
        self.assertEqual(sorted(r[0] for r in results), ["error", "ok"])
        self.assertEqual([r[1] for r in results if r[0] == "error"], ["bad_op"])
        self.assertEqual(len(self.events()), 1)
        value = next(r[1] for r in results if r[0] == "ok")
        self.assertEqual(skills.get("sample", ctx=self.ctx)["skill"], value["skill"])
        self.assert_projection(value["skill"]["sha256"], files=value["skill"]["files"])

    def test_a23_distinct_operations_same_pin_keep_both_commits(self):
        results = self.race([self.publication("distinct-one"), self.publication("distinct-two")])
        self.assertEqual([r[0] for r in results], ["ok", "ok"])
        self.assertEqual(len(self.events()), 2)
        self.assertNotEqual(results[0][1]["commit"], results[1][1]["commit"])
        self.assertEqual(skills.list_skills(ctx=self.ctx), {"skills": [{"skill_id": "sample", "sha256": PIN, "retired": False}]})
        self.assert_projection()

    def test_a23_publication_retirement_race_preserves_all_pins(self):
        self.publish()
        changed = one("new-version")
        retired = ("skill_retire", {"skill_id": "sample", "sha256": PIN, "reason": "retire old",
                                    "agent": "tester", "op_id": "retiring"})
        results = self.race([self.publication("same-pin"), self.publication("new-pin", changed), retired])
        self.assertEqual([r[0] for r in results], ["ok", "ok", "ok"])
        self.assertEqual(len(self.events()), 4)
        self.assertTrue(skills.get("sample", sha256=PIN, ctx=self.ctx)["skill"]["retired"])
        self.assertFalse(skills.get("sample", sha256=independent_pin(changed), ctx=self.ctx)["skill"]["retired"])
        self.assert_projection()
        self.assert_projection(independent_pin(changed), files=changed)
        self.assertEqual(len(skills.list_skills(include_retired=True, ctx=self.ctx)["skills"]), 2)

    def test_a24_real_lock_contention_is_busy_then_release_succeeds(self):
        engine = multiprocessing.get_context("fork")
        ready, release = engine.Event(), engine.Event()
        receiving, sending = engine.Pipe(duplex=False)
        owner = engine.Process(target=lock_owner, args=(str(self.home), ready, release, sending))
        owner.start()
        sending.close()
        self.addCleanup(self.reap_owned, owner)
        self.addCleanup(receiving.close)
        self.addCleanup(release.set)
        self.assertTrue(ready.wait(timeout=1), "real locked prepare callback was not reached")
        try:
            self.assert_code("busy", lambda: self.publish(op="blocked"))
            self.assertEqual(self.raw(), b"")
            self.assertFalse(self.projection().exists())
        finally:
            release.set()
        self.assertTrue(receiving.poll(1))
        self.assertEqual(receiving.recv(), ("ok", None))
        owner.join(timeout=0.5)
        self.assertEqual(owner.exitcode, 0)
        result = self.publish(op="blocked")
        self.assert_receipt(result)
        self.assertEqual(len(self.events()), 2)
