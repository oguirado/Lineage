"""A16-A20, A22, A33: storage faults injected at standard-library syscall seams."""
import json
import os
import stat
from unittest.mock import patch
from ._support import CoreCase, independent_verify, line


class DurabilityTests(CoreCase):
    def target(self, fd):
        try:
            return os.path.samestat(os.fstat(fd), self.path.stat())
        except OSError:
            return False

    def test_a16_eintr_and_short_writes_persist_exactly_one_line(self):
        self.install()
        real_write, real_sync = os.write, os.fsync
        attempts, synced = [], []
        def write(fd, data):
            if self.target(fd):
                attempts.append(len(data))
                if len(attempts) <= 2:
                    raise InterruptedError("interrupted write")
                return real_write(fd, data[:11])
            return real_write(fd, data)
        def sync(fd):
            if self.target(fd):
                synced.append(self.bytes())
            return real_sync(fd)
        with patch.object(os, "write", write), patch.object(os, "fsync", sync):
            result = self.tx()
        self.assertGreater(len(attempts), 3, "Short-write/EINTR instrumentation was not exercised")
        self.assertEqual(self.bytes(), line(result))
        self.assertIn(line(result), synced)
        independent_verify(self.bytes())
        self.lock_released()

    def test_a17_nonpositive_and_partial_error_restore_exact_bytes(self):
        self.tx()
        baseline = self.bytes()
        real_write = os.write
        for failure in (0, -1, "partial"):
            calls = []
            def write(fd, data):
                if self.target(fd):
                    calls.append(len(data))
                    if failure == "partial":
                        if len(calls) == 1:
                            return real_write(fd, data[:5])
                        if len(calls) == 2:
                            raise OSError("injected write failure")
                    elif len(calls) == 1:
                        return failure
                return real_write(fd, data)
            with patch.object(os, "write", write):
                self.rejects("internal", self.tx, op_id="failed-append")
            self.assertTrue(calls, "Write fault not reached")
            self.assertEqual(self.bytes(), baseline)
            self.lock_released()
        result = self.tx(op_id="failed-append")
        self.assertEqual(result["lamport"], 2)
        self.assertEqual(len(independent_verify(self.bytes())), 2)

    def test_a18_commit_fsync_failure_restores_and_syncs_before_retry(self):
        self.tx()
        baseline = self.bytes()
        real_sync = os.fsync
        calls = []
        def sync(fd):
            if self.target(fd):
                calls.append(self.bytes())
                if len(calls) == 1:
                    raise OSError("injected commit fsync failure")
            return real_sync(fd)
        with patch.object(os, "fsync", sync):
            self.rejects("internal", self.tx, op_id="sync-request")
        self.assertGreaterEqual(len(calls), 2, "Rollback restoration was not synced")
        self.assertEqual(calls[-1], baseline)
        self.lock_released()
        self.assertEqual(self.tx(op_id="sync-request")["lamport"], 2)

    def test_a19_failed_rollback_reports_uncertainty_and_releases_lock(self):
        real_sync, real_truncate, real_write = os.fsync, os.ftruncate, os.write
        for mode in ("truncate", "suffix_restore", "rollback_sync"):
            self.install()
            self.tx()
            baseline = self.bytes()
            if mode == "suffix_restore":
                self.path.write_bytes(baseline + b'{"torn":')
            sync_calls = []
            faults = []
            def sync(fd):
                if self.target(fd):
                    sync_calls.append(1)
                    if len(sync_calls) == 1 or mode == "rollback_sync":
                        faults.append("fsync")
                        raise OSError("injected initiating commit fsync failure")
                return real_sync(fd)
            def truncate(fd, length):
                if self.target(fd) and sync_calls and mode == "truncate":
                    faults.append("truncate")
                    raise OSError("injected rollback truncate failure")
                return real_truncate(fd, length)
            def write(fd, data):
                if self.target(fd) and sync_calls and mode == "suffix_restore":
                    faults.append("suffix_restore")
                    raise OSError("injected suffix restoration failure")
                return real_write(fd, data)
            with patch.object(os, "fsync", sync), patch.object(os, "ftruncate", truncate), patch.object(os, "write", write):
                with self.assertRaises(self.error) as caught:
                    self.tx(op_id="uncertain-append")
            exc = caught.exception
            self.assertEqual(exc.code, "internal")
            self.assertIsInstance(exc.detail, dict)
            self.assertIs(exc.detail.get("rollback_failed"), True)
            self.assertIs(exc.detail.get("recovery_required"), True)
            self.assertIn("sync", json.dumps(exc.detail).lower())
            self.assertTrue(faults)
            self.lock_released()
            # No assertion of restored bytes: the injected primitives prevented restoration.

    def test_a20_creation_directories_synced_and_ordinary_inodes_preserved(self):
        real_sync = os.fsync
        synced = []
        def sync(fd):
            info = os.fstat(fd)
            synced.append((info.st_dev, info.st_ino, stat.S_ISDIR(info.st_mode)))
            return real_sync(fd)
        with patch.object(os, "fsync", sync):
            self.tx()
        event_stat = self.path.stat()
        lock_stat = (self.home / "ledger/main/events.lock").stat()
        self.assertIn((event_stat.st_dev, event_stat.st_ino, False), synced)
        for directory in (self.home.parent, self.home, self.home / "ledger", self.path.parent):
            info = directory.stat()
            self.assertIn((info.st_dev, info.st_ino, True), synced,
                          "New authority entry needs parent directory durability")
        self.tx()
        self.assertTrue(os.path.samestat(event_stat, self.path.stat()))
        self.assertTrue(os.path.samestat(lock_stat, (self.home / "ledger/main/events.lock").stat()))
        with patch.object(os, "fsync", side_effect=AssertionError("Replay synced")):
            self.tx(op_id="request0001")

    def test_a20_creation_directory_fsync_failure_never_succeeds(self):
        real_sync = os.fsync
        failures = []
        def sync(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode) and not failures:
                failures.append(True)
                raise OSError("injected creation directory fsync failure")
            return real_sync(fd)
        with patch.object(os, "fsync", sync):
            with self.assertRaises(self.error) as caught:
                self.tx()
        self.assertEqual(caught.exception.code, "internal")
        self.assertTrue(failures, "Creation durability fault was not reached")
        if (self.home / "ledger/main/events.lock").exists():
            self.lock_released()

    def test_a22_failed_tail_continuation_restores_suffix_and_syncs_it(self):
        self.tx()
        original = self.bytes() + bytes([226, 130]) + b'{"tail":'
        self.path.write_bytes(original)
        real_sync = os.fsync
        calls = []
        def sync(fd):
            if self.target(fd):
                calls.append(self.bytes())
                if len(calls) == 1:
                    raise OSError("injected continuation fsync failure")
            return real_sync(fd)
        with patch.object(os, "fsync", sync):
            self.rejects("internal", self.tx, op_id="continue-tail")
        self.assertGreaterEqual(len(calls), 2)
        self.assertEqual(calls[-1], original)
        self.lock_released()
        self.assertEqual(self.tx(op_id="continue-tail")["lamport"], 2)
        independent_verify(self.bytes())
