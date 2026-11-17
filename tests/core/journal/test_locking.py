"""A30-A33: stable interprocess flock, immediate attempts and monotonic deadlines."""
import errno
import fcntl
import os
from pathlib import Path
import json
import subprocess
import sys
import time
from unittest.mock import patch
from ._support import CoreCase


class LockingTests(CoreCase):
    def test_a30_held_lock_is_busy_then_same_operation_commits(self):
        self.install()
        holder, pipe = self.child("hold")
        self.assertEqual(self.receive(pipe), ("ready", "locked"))
        try:
            contender, result_pipe = self.child("call", timeout=0.1)
            self.assertEqual(self.receive(result_pipe, 1.1), ("error", "busy"))
            self.finished(contender, 0.2)
            self.assertEqual(self.bytes(), b"")
        finally:
            pipe.send("release")
        self.assertEqual(self.receive(pipe), ("ok", "acquired"))
        self.finished(holder)
        self.assertEqual(self.tx(op_id="shared-request")["lamport"], 1)

    def test_a31_zero_timeout_attempts_available_and_held_lock(self):
        self.install()
        self.tx(lock_timeout_s=0)
        holder, pipe = self.child("hold")
        self.assertEqual(self.receive(pipe), ("ready", "locked"))
        try:
            self.rejects("busy", self.tx, lock_timeout_s=0)
        finally:
            pipe.send("release")
        self.assertEqual(self.receive(pipe), ("ok", "acquired"))
        self.finished(holder)

    def test_a31_invalid_timeouts_precede_all_storage(self):
        for timeout in (-1, float("nan"), float("inf"), True, False, "0", None):
            for operation in (self.tx, lambda **kw: self.journal.snapshot(self.home, **kw),
                              lambda **kw: self.journal.verify(self.home, **kw)):
                self.rejects("bad_args", operation, lock_timeout_s=timeout)
        self.assertFalse(self.home.exists())

    def test_a30_monotonic_deadline_limits_wait_and_eintr(self):
        self.install()
        fd = os.open(self.home / "ledger/main/events.lock", os.O_RDONLY)
        self.addCleanup(os.close, fd)
        for interrupted in (False, True):
            now = [0.0]
            attempts, pauses = [], []
            def monotonic():
                now[0] += 0.01
                return now[0]
            def flock(descriptor, flags):
                self.assertEqual(descriptor, fd)
                self.assertTrue(flags & fcntl.LOCK_NB)
                attempts.append(now[0])
                self.assertLess(len(attempts), 100, "Interrupted acquisition has no deadline")
                if interrupted:
                    raise InterruptedError(errno.EINTR, "interrupt")
                raise BlockingIOError(errno.EAGAIN, "held lock")
            def sleep(duration):
                self.assertGreaterEqual(duration, 0)
                self.assertLessEqual(duration, max(0, 0.11 - now[0]) + 1e-9)
                pauses.append(duration)
                now[0] += duration
            with patch.object(time, "monotonic", monotonic), patch.object(time, "sleep", sleep), patch.object(fcntl, "flock", flock):
                with self.assertRaises(self.error) as caught:
                    self.locking.lock_exclusive(fd, timeout_s=0.1)
            self.assertEqual(caught.exception.code, "busy")
            self.assertTrue(attempts)
            self.assertLessEqual(now[0], 0.15)

    def test_a32_noncontention_backend_error_is_internal(self):
        self.install()
        for failure in (OSError(errno.EBADF, "backend failed"), AttributeError("backend unavailable")):
            with patch.object(fcntl, "flock", side_effect=failure) as called:
                self.rejects("internal", self.tx)
            self.assertTrue(called.called)
            self.lock_released()

    def test_a32_missing_backend_cannot_become_lockless_success(self):
        self.install()
        script = """
import builtins, json, os, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == 'fcntl':
        raise ImportError('backend unavailable')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
fd = os.open(sys.argv[1], os.O_RDONLY)
try:
    try:
        from lineage.core.locking import lock_exclusive
        lock_exclusive(fd, timeout_s=0)
    except Exception as exc:
        print(json.dumps({'code': getattr(exc, 'code', None)}))
    else:
        print(json.dumps({'success': True}))
finally:
    os.close(fd)
"""
        root = Path(__file__).resolve().parents[3]
        result = subprocess.run([sys.executable, "-B", "-c", script,
                                 str(self.home / "ledger/main/events.lock")],
                                cwd=root, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(root)),
                                capture_output=True, text=True, timeout=2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"code": "internal"})

    def test_a32_interrupted_acquisition_then_success_and_unlock(self):
        self.install()
        real_flock = fcntl.flock
        operations = []
        def flock(fd, flags):
            operations.append(flags)
            if len(operations) == 1:
                raise InterruptedError(errno.EINTR, "interrupt once")
            return real_flock(fd, flags)
        with patch.object(fcntl, "flock", flock):
            self.tx()
        self.assertGreaterEqual(len(operations), 3)
        self.assertTrue(operations[-1] & fcntl.LOCK_UN)
        self.lock_released()

    def test_a33_success_replay_rejection_crash_and_corruption_release_lock(self):
        self.tx()
        inode = (self.home / "ledger/main/events.lock").stat().st_ino
        self.lock_released()
        self.tx(op_id="request0001")
        self.lock_released()
        def reject(history, event):
            raise self.error("memory_required", "missing memory")
        def crash(history, event):
            raise RuntimeError("unexpected callback crash")
        for callback, code in ((reject, "memory_required"), (crash, "internal")):
            self.rejects(code, self.tx, validators={"claim": callback})
            self.lock_released()
        self.path.write_bytes(self.bytes() + b"broken\n")
        self.rejects("hash_mismatch", self.tx)
        self.lock_released()
        self.assertEqual((self.home / "ledger/main/events.lock").stat().st_ino, inode)
