"""A1/A15/A16: public mailbox APIs and non-takeover ownership."""

import inspect
import multiprocessing
import os
from lineage.core import family, jsonlane
from tests.core.family import WireCase, RuntimeCase, require_k0, request


def owner_child(ctx, pipe):
    box = family.Mailbox("Endpoint_1", ctx=ctx)
    try:
        box.open()
        pipe.send("owned")
        command = pipe.recv()
        if command == "crash":
            os._exit(0)
        box.release()
        pipe.send("released")
    except BaseException as exc:
        pipe.send(type(exc).__name__)
    finally:
        pipe.close()


class APIAndDependencyTests(WireCase):
    def test_a1_mailbox_context_signature(self):
        signature = inspect.signature(family.Mailbox)
        self.assertEqual(list(signature.parameters), ["endpoint", "ctx"])
        self.assertEqual(signature.parameters["ctx"].kind, inspect.Parameter.KEYWORD_ONLY)

    def test_a1_jsonlane_dispatch_signature(self):
        signature = inspect.signature(jsonlane.dispatch)
        self.assertEqual(list(signature.parameters), ["envelope", "config", "ctx"])
        self.assertEqual(signature.parameters["ctx"].kind, inspect.Parameter.KEYWORD_ONLY)

    def test_a32_dependency_gate(self):
        require_k0(self)


class OwnershipTests(RuntimeCase):
    def test_a12_empty_sweep_ignores_publication_names(self):
        box = self.mailbox()
        ignored = []
        for directory in (p for p in self.endpoint.iterdir() if p.is_dir()):
            for name in ("publication.tmp", ".hidden.tmp", "README"):
                path = directory / name
                path.write_bytes(b"ignored")
                ignored.append(path)
        self.assertEqual(box.sweep(), 0)
        self.assertEqual(self.extension.SEEN, [])
        for path in ignored:
            self.assertEqual(path.read_bytes(), b"ignored")

    def child_owner(self):
        runtime = multiprocessing.get_context("fork")
        parent, child = runtime.Pipe()
        process = runtime.Process(target=owner_child, args=(self.ctx, child))
        process.start()
        child.close()
        def cleanup():
            if process.is_alive():
                self.assertGreater(process.pid, 1)
                process.terminate()
            process.join(timeout=0.5)
            parent.close()
        self.addCleanup(cleanup)
        self.assertTrue(parent.poll(1), "owner handshake timed out")
        self.assertEqual(parent.recv(), "owned")
        return process, parent

    def test_a15_independent_process_owner_refused(self):
        process, pipe = self.child_owner()
        second = family.Mailbox("Endpoint_1", ctx=self.ctx)
        self.addCleanup(second.release)
        with self.assertRaises(family.Refusal):
            second.open()
        pipe.send("release")
        self.assertTrue(pipe.poll(1), "release handshake timed out")
        self.assertEqual(pipe.recv(), "released")
        process.join(timeout=0.5)
        self.assertFalse(process.is_alive())

    def test_a15_abrupt_exit_requires_explicit_test_lock_recovery(self):
        process, pipe = self.child_owner()
        lock = self.endpoint / "consumer.lock"
        identity = lock.stat()
        pipe.send("crash")
        process.join(timeout=1)
        self.assertFalse(process.is_alive())
        contender = family.Mailbox("Endpoint_1", ctx=self.ctx)
        with self.assertRaises(family.Refusal):
            contender.open()
        current = lock.stat()
        self.assertEqual((current.st_dev, current.st_ino), (identity.st_dev, identity.st_ino))
        # Explicit harness recovery is restricted to this temporary test-owned lock.
        lock.unlink()
        recovered = family.Mailbox("Endpoint_1", ctx=self.ctx)
        recovered.open()
        recovered.release()

    def test_a15_second_owner_refused(self):
        first = self.mailbox()
        second = family.Mailbox("Endpoint_1", ctx=self.ctx)
        self.addCleanup(second.release)
        with self.assertRaises(family.Refusal):
            second.open()
        first.check_tree()

    def test_a15_stale_looking_lock_never_taken(self):
        lock = self.endpoint / "consumer.lock"
        lock.write_bytes(b"1\n")
        os.utime(lock, (0, 0))
        box = family.Mailbox("Endpoint_1", ctx=self.ctx)
        self.addCleanup(box.release)
        with self.assertRaises(family.Refusal):
            box.open()
        self.assertEqual(lock.read_bytes(), b"1\n")

    def test_a16_normal_release_removes_owned_lock(self):
        box = family.Mailbox("Endpoint_1", ctx=self.ctx)
        box.open()
        lock = self.endpoint / "consumer.lock"
        self.assertTrue(lock.is_file())
        box.release()
        self.assertFalse(lock.exists())

    def test_a16_replacement_lock_survives_release(self):
        box = family.Mailbox("Endpoint_1", ctx=self.ctx)
        box.open()
        lock = self.endpoint / "consumer.lock"
        old = lock.stat()
        replacement = self.endpoint / "replacement.lock"
        replacement.write_bytes(b"replacement")
        os.replace(replacement, lock)
        self.assertNotEqual((old.st_dev, old.st_ino), (lock.stat().st_dev, lock.stat().st_ino))
        with self.assertRaises((family.Refusal, family.UnsafeEntry, family.RecoveryError, OSError)):
            box.release()
        self.assertEqual(lock.read_bytes(), b"replacement")

    def test_a6_direct_mailbox_revocation(self):
        box = self.mailbox()
        self.assertIn("untrusted", box.dispatch(request("call")))
        seen = len(self.extension.SEEN)
        self.write_config({"endpoint": "Endpoint_1", "sources": [], "tools": ["skill_list"]})
        result = box.dispatch(request("call"))
        self.assert_error(result, "bad_args")
        self.assertEqual(len(self.extension.SEEN), seen)
