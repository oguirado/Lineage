# A-U01R: Test the integrated fcntl lock API and structured errors explicitly.
import errno
import os
from types import SimpleNamespace
from unittest import mock

from lineage.core import journal, locking
from lineage.core.errors import LineageError
from ._support import JournalCase


class LockingRegression(JournalCase):
    def test_nonblocking_exclusive_and_unlock_preserve_file_position(self):
        fd = os.open(self.path.with_name("events.lock"), os.O_RDWR)
        try:
            os.lseek(fd, 7, os.SEEK_SET)
            real = locking.fcntl.flock
            with mock.patch.object(locking.fcntl, "flock", wraps=real) as flock:
                locking.lock_exclusive(fd)
                locking.unlock(fd)
            self.assertEqual(flock.call_args_list,
                             [mock.call(fd, locking.fcntl.LOCK_EX | locking.fcntl.LOCK_NB),
                              mock.call(fd, locking.fcntl.LOCK_UN)])
            self.assertEqual(os.lseek(fd, 0, os.SEEK_CUR), 7)
        finally:
            os.close(fd)

    def test_deadline_is_bounded_and_returns_busy(self):
        clock = SimpleNamespace(now=0.0)
        sleeps = []
        def sleep(delay):
            self.assertGreater(delay, 0)
            self.assertLessEqual(delay, 0.001)
            sleeps.append(delay)
            clock.now += delay
        with mock.patch.object(locking.fcntl, "flock", side_effect=BlockingIOError(errno.EAGAIN, "busy")), \
             mock.patch.object(locking.time, "monotonic", side_effect=lambda: clock.now), \
             mock.patch.object(locking.time, "sleep", side_effect=sleep):
            with self.assertRaises(LineageError) as caught:
                locking.lock_exclusive(17, timeout_s=0.0025)
        self.assertEqual(caught.exception.code, "busy")
        self.assertAlmostEqual(clock.now, 0.0025)
        self.assertAlmostEqual(sleeps[-1], 0.0005)

    def test_interrupted_attempt_retries_without_sleep(self):
        with mock.patch.object(locking.fcntl, "flock", side_effect=[InterruptedError(errno.EINTR, "interrupt"), None]) as flock, \
             mock.patch.object(locking.time, "sleep") as sleep:
            locking.lock_exclusive(17)
        self.assertEqual(flock.call_count, 2)
        sleep.assert_not_called()

    def test_backend_failure_is_structured_and_not_retried(self):
        with mock.patch.object(locking.fcntl, "flock", side_effect=OSError(errno.EIO, "failure")) as flock:
            with self.assertRaises(LineageError) as caught:
                locking.lock_exclusive(17)
        self.assertEqual(caught.exception.code, "internal")
        self.assertEqual(flock.call_count, 1)

    def test_missing_backend_fails_closed(self):
        with mock.patch.object(locking, "fcntl", None):
            for operation in (locking.lock_exclusive, locking.unlock):
                with self.assertRaises(LineageError) as caught:
                    operation(17)
                self.assertEqual(caught.exception.code, "internal")

    def test_failed_acquisition_never_unlocks_or_appends(self):
        before = self.raw()
        with mock.patch.object(journal, "lock_exclusive", side_effect=LineageError("busy")), \
             mock.patch.object(journal, "unlock") as unlock:
            with self.assertRaises(LineageError) as caught:
                self.append()
        self.assertEqual(caught.exception.code, "busy")
        self.assertEqual(self.raw(), before)
        unlock.assert_not_called()
        self.assertTrue(self.append())
