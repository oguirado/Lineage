"""Deadline-bounded, nonblocking interprocess flock locks."""

import errno
import math
import time

from .errors import LineageError

try:
    import fcntl
except ImportError:
    fcntl = None

LOCK_TIMEOUT_S: float = 1.0


def _validate_timeout(timeout_s: float) -> None:
    if type(timeout_s) not in (int, float):
        raise LineageError("bad_args", "lock_timeout_s must be finite and nonnegative")
    try:
        valid = math.isfinite(timeout_s) and timeout_s >= 0
    except (OverflowError, ValueError):
        valid = False
    if not valid:
        raise LineageError("bad_args", "lock_timeout_s must be finite and nonnegative")


def lock_exclusive(fd: int, timeout_s: float = LOCK_TIMEOUT_S) -> None:
    """Attempt immediately, then retry only before the monotonic deadline."""
    if type(fd) is not int:
        raise LineageError("bad_args", "fd must be an integer")
    _validate_timeout(timeout_s)
    if fcntl is None:
        raise LineageError("internal", "locking backend unavailable")
    deadline = time.monotonic() + timeout_s
    first = True
    while True:
        if not first and time.monotonic() >= deadline:
            raise LineageError("busy", "journal lock deadline expired")
        first = False
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError as exc:
            if exc.errno == errno.EINTR or isinstance(exc, InterruptedError):
                continue
            if exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise LineageError("internal", "locking backend failure") from None
        except Exception:
            raise LineageError("internal", "locking backend failure") from None
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LineageError("busy", "journal lock deadline expired")
        # Poll promptly enough for contending writers to observe releases.
        time.sleep(min(0.001, remaining))


def unlock(fd: int) -> None:
    """Release without unlinking or replacing the stable lock file."""
    if type(fd) is not int:
        raise LineageError("bad_args", "fd must be an integer")
    if fcntl is None:
        raise LineageError("internal", "locking backend unavailable")
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
            return
        except OSError as exc:
            if exc.errno == errno.EINTR or isinstance(exc, InterruptedError):
                continue
            raise LineageError("internal", "locking backend release failure") from None
        except Exception:
            raise LineageError("internal", "locking backend release failure") from None
