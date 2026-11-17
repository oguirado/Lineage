"""The single authoritative, transactional, hash-chained Lineage journal.

Complete canonical LF-terminated records are committed history. An unterminated
suffix is excluded from every state calculation and is replaced only after a
new operation has passed preparation and validation under the stable flock.
"""

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import threading
import time
from typing import TypeAlias

from .errors import JSONValue, LineageError
from .locking import LOCK_TIMEOUT_S, _validate_timeout, lock_exclusive, unlock
from .schema import strict_loads

Event: TypeAlias = dict[str, JSONValue]
EventDraft: TypeAlias = dict[str, JSONValue]
History: TypeAlias = tuple[Event, ...]
Validator: TypeAlias = Callable[[History, Event], None]
Prepare: TypeAlias = Callable[[History, EventDraft], dict[str, JSONValue]]

_EVENT_PATH = "ledger/main/events.jsonl"
_ZERO = "0" * 64
_FIELDS = frozenset({"schema", "id", "lamport", "ts", "ledger", "agent",
                     "kind", "payload", "op_id", "request_sha256", "evidence",
                     "prev_sha256", "sha256"})
_AGENT = re.compile(r"[a-z][a-z0-9-]{2,63}")
_OP = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}")
_ID = re.compile(r"e-[0-9a-f]{16}")
_HASH = re.compile(r"[0-9a-f]{64}")
_CALLBACK = threading.local()


def _json(value: JSONValue, active: set[int]) -> None:
    concrete = type(value)
    if concrete is str:
        value.encode("utf-8", errors="strict")
    elif concrete is float:
        if not math.isfinite(value):
            raise ValueError("non-finite JSON number")
    elif concrete in (int, bool, type(None)):
        return
    elif concrete in (dict, list):
        if id(value) in active:
            raise ValueError("cyclic JSON value")
        active.add(id(value))
        try:
            if concrete is dict:
                for key, item in value.items():
                    if type(key) is not str:
                        raise ValueError("JSON object keys must be strings")
                    key.encode("utf-8", errors="strict")
                    _json(item, active)
            else:
                for item in value:
                    _json(item, active)
        finally:
            active.remove(id(value))
    else:
        raise ValueError("unsupported JSON value")


def _encode(value: JSONValue) -> bytes:
    """Serialize data already checked by the JSON boundary."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_bytes(value: JSONValue) -> bytes:
    """Encode exact JSON builtins without normalization, BOM, or final LF."""
    try:
        _json(value, set())
        return _encode(value)
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise LineageError("bad_args", "value is not strict JSON") from None


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _text(value: JSONValue) -> bool:
    if type(value) is not str or not value:
        return False
    try:
        value.encode("utf-8", errors="strict")
        return True
    except UnicodeError:
        return False


def _matches(pattern: re.Pattern, value: JSONValue) -> bool:
    return type(value) is str and pattern.fullmatch(value) is not None


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _evidence(value: JSONValue) -> None:
    _require(type(value) is list, "evidence must be a list")
    for item in value:
        _require(type(item) is dict and set(item) == {"path", "sha256"},
                 "evidence must contain only path and sha256")
        path = item["path"]
        _require(_text(path), "evidence path must be nonempty UTF-8")
        _require(not path.startswith("/") and "\\" not in path and "\x00" not in path
                 and not re.match(r"[A-Za-z]:", path)
                 and all(part not in ("", ".", "..") for part in path.split("/")),
                 "evidence path must be normalized and relative")
        _require(_matches(_HASH, item["sha256"]), "invalid evidence digest")


def _envelope(event: Event) -> None:
    _require(type(event) is dict and set(event) == _FIELDS, "closed event envelope")
    _require(event["schema"] == "lineage.event/v1", "invalid event schema")
    _require(event["ledger"] == "main", "invalid ledger")
    _require(_matches(_ID, event["id"]), "invalid event id")
    _require(type(event["lamport"]) is int and event["lamport"] >= 1,
             "invalid Lamport value")
    _require(type(event["ts"]) is int and event["ts"] >= 0, "invalid timestamp")
    _require(_matches(_AGENT, event["agent"]), "invalid actor")
    _require(_matches(_OP, event["op_id"]), "invalid operation identity")
    _require(_text(event["kind"]), "invalid event kind")
    _require(type(event["payload"]) is dict, "payload must be a JSON object")
    for name in ("request_sha256", "prev_sha256", "sha256"):
        _require(_matches(_HASH, event[name]), "invalid " + name)
    _evidence(event["evidence"])


def resolve_home(home: str | os.PathLike[str] | None = None) -> Path:
    """Explicit home, nonempty LINEAGE_HOME, then the user's .lineage."""
    try:
        value = os.fspath(home) if home is not None else (os.environ.get("LINEAGE_HOME") or str(Path.home() / ".lineage"))
        if type(value) is not str or not value or "\x00" in value:
            raise ValueError
        value.encode("utf-8", errors="strict")
        return Path(os.path.abspath(value))
    except (TypeError, ValueError, OSError, RuntimeError):
        raise LineageError("bad_args", "invalid runtime home") from None


def _guard() -> None:
    if getattr(_CALLBACK, "active", False):
        raise LineageError("internal", "recursive journal operation in callback")


def _stat(parent: int, name: str):
    try:
        return os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _same(left, right) -> bool:
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _open_checked(path, flags: int, mode: int = 0o777, *, dir_fd=None) -> int:
    """Keep no-follow failures at the unsafe-path argument boundary."""
    try:
        return os.open(path, flags, mode, dir_fd=dir_fd)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            raise LineageError("bad_args", "unsafe journal storage node") from None
        raise


@contextmanager
def _directory(home: Path, create: bool):
    """Pin home, then walk only controlled directories without symlinks."""
    descriptors = []
    try:
        base = home
        missing = []
        while True:
            try:
                before = os.lstat(base)
                break
            except FileNotFoundError:
                if not create:
                    yield None
                    return
                missing.append(base.name)
                base = base.parent
            except NotADirectoryError:
                raise LineageError("bad_args", "unsafe journal directory") from None
        # Ancestors above home are outside the controlled storage boundary.
        # Resolve an existing ancestor link when home still needs creation.
        if missing and stat.S_ISLNK(before.st_mode):
            base = base.resolve(strict=True)
            before = os.lstat(base)
        if not stat.S_ISDIR(before.st_mode):
            raise LineageError("bad_args", "unsafe journal directory")
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        current = _open_checked(base, flags)
        descriptors.append(current)
        after = os.lstat(base)
        if not _same(before, os.fstat(current)) or not _same(after, os.fstat(current)):
            raise LineageError("bad_args", "journal directory changed during open")
        for name in (*reversed(missing), "ledger", "main"):
            before = _stat(current, name)
            if before is None and create:
                try:
                    os.mkdir(name, mode=0o700, dir_fd=current)
                    os.fsync(current)
                except FileExistsError:
                    pass
                before = _stat(current, name)
            if before is None:
                yield None
                return
            if not stat.S_ISDIR(before.st_mode):
                raise LineageError("bad_args", "unsafe journal directory")
            child = _open_checked(name, flags, dir_fd=current)
            descriptors.append(child)
            after = _stat(current, name)
            if after is None or not _same(before, os.fstat(child)) or not _same(after, os.fstat(child)):
                raise LineageError("bad_args", "journal directory changed during open")
            current = child
        yield current
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def _regular(parent: int, name: str, create: bool, writable: bool):
    """Open a regular entry without following symlinks or blocking on a FIFO."""
    before = _stat(parent, name)
    created = False
    flags = (os.O_RDWR if writable else os.O_RDONLY) | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    if before is not None and not stat.S_ISREG(before.st_mode):
        raise LineageError("bad_args", "unsafe journal authority entry")
    if before is None:
        if not create:
            return None, False
        try:
            fd = _open_checked(name, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent)
            created = True
        except FileExistsError:
            return _regular(parent, name, False, writable)
    else:
        fd = _open_checked(name, flags, dir_fd=parent)
    try:
        info = os.fstat(fd)
        after = _stat(parent, name)
        if (not stat.S_ISREG(info.st_mode) or after is None or not _same(info, after)
                or (before is not None and not _same(before, info))):
            raise LineageError("bad_args", "journal authority changed during open")
        return fd, created
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def _authority(home: Path, write: bool, timeout: float):
    """Own descriptors and hold one stable lock for the entire transaction."""
    lock_fd = event_fd = None
    acquired = False
    try:
        with _directory(home, write) as parent:
            if parent is None:
                if write:
                    raise LineageError("internal", "journal authority disappeared during open")
                yield None
                return
            existing_events = _stat(parent, "events.jsonl")
            existing_lock = _stat(parent, "events.lock")
            for info in (existing_events, existing_lock):
                if info is not None and not stat.S_ISREG(info.st_mode):
                    raise LineageError("bad_args", "unsafe journal authority entry")
            if existing_events is not None and existing_lock is None:
                raise LineageError("internal", "existing journal has no stable lock")
            lock_fd, new_lock = _regular(parent, "events.lock", write, write)
            if lock_fd is None:
                if write:
                    raise LineageError("internal", "journal authority disappeared during open")
                yield None
                return
            lock_exclusive(lock_fd, timeout)
            acquired = True
            # Pin the lock's directory entry again after potentially waiting.
            lock_entry = _stat(parent, "events.lock")
            if lock_entry is None or not _same(lock_entry, os.fstat(lock_fd)):
                raise LineageError("internal", "stable journal lock was replaced")
            if new_lock:
                os.fsync(lock_fd)
                os.fsync(parent)
            event_fd, new_events = _regular(parent, "events.jsonl", write, write)
            if write and event_fd is None:
                raise LineageError("internal", "journal authority disappeared during open")
            if new_events:
                os.fsync(event_fd)
                os.fsync(parent)
            yield event_fd
    except LineageError:
        raise
    except Exception:
        raise LineageError("internal", "journal authority I/O failure") from None
    finally:
        try:
            if event_fd is not None:
                os.close(event_fd)
        finally:
            if lock_fd is not None:
                try:
                    if acquired:
                        unlock(lock_fd)
                finally:
                    os.close(lock_fd)


def _read(fd: int | None) -> bytes:
    if fd is None:
        return b""
    os.lseek(fd, 0, os.SEEK_SET)
    chunks = []
    while True:
        try:
            chunk = os.read(fd, 65536)
        except InterruptedError:
            continue
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _issue(code: str, detail: str, line: int, offset: int) -> dict[str, JSONValue]:
    return {"code": code, "detail": detail, "path": _EVENT_PATH,
            "line": line, "byte_offset": offset}


def _scan(raw: bytes, exists: bool, *,
          canonical_history: list[bytes] | None = None) -> tuple[dict[str, JSONValue], History, int]:
    boundary = raw.rfind(b"\n") + 1
    suffix = raw[boundary:]
    tail = None
    if suffix:
        tail = {"line": raw[:boundary].count(b"\n") + 1, "byte_offset": boundary,
                "byte_length": len(suffix), "bytes_hex": suffix.hex()}
    report = {"ok": exists, "exists": exists, "ledger": "main", "events": 0,
              "head": 0, "head_sha256": _ZERO, "torn_tail": tail, "errors": []}
    events = []
    ids, operations = set(), set()
    offset = 0
    if not exists:
        report["errors"].append(_issue("internal", "missing journal authority", 1, 0))
    for number, body in enumerate(raw[:boundary].split(b"\n")[:-1], 1):
        record = body + b"\n"
        try:
            value = strict_loads(body)
            _envelope(value)
            # Apply the same canonical boundary used by callback mutation checks.
            _require(canonical_bytes(value) + b"\n" == record, "noncanonical stored bytes")
            _require(value["lamport"] == number, "noncontiguous Lamport order")
            _require(value["prev_sha256"] == report["head_sha256"], "raw-line predecessor hash mismatch")
            content = {key: item for key, item in value.items() if key != "sha256"}
            _require(value["sha256"] == _sha(_encode(content)), "event content hash mismatch")
            identity = (value["agent"], value["op_id"])
            _require(value["id"] not in ids, "duplicate event id")
            _require(identity not in operations, "duplicate operation identity")
        except Exception as exc:
            # All diagnostic strings originate here, never in decoded content.
            reason = str(exc) if type(exc) is ValueError else "invalid strict JSON event"
            report["ok"] = False
            report["errors"].append(_issue("hash_mismatch", reason, number, offset))
            break
        ids.add(value["id"])
        operations.add(identity)
        events.append(value)
        if canonical_history is not None:
            canonical_history.append(body)
        report.update(events=number, head=value["lamport"], head_sha256=_sha(record))
        offset += len(record)
    return report, tuple(events), boundary


def _verified(report: dict[str, JSONValue]) -> None:
    if report["exists"] and not report["ok"]:
        raise LineageError("hash_mismatch", report["errors"][0])


def _callback(function, before_history: tuple[bytes, ...], event: Event):
    # Reuse the exact canonical history bytes already checked under the lock.
    # Each callback still receives a fresh copy, checked for mutation afterward.
    # Keep records separate so the history container adds no nesting limit.
    before_event = _encode(event)
    copied_history = tuple(json.loads(item) for item in before_history)
    copied_event = json.loads(before_event)
    _CALLBACK.active = True
    failure = None
    result = None
    try:
        try:
            result = function(copied_history, copied_event)
        except Exception as exc:
            failure = exc
        try:
            # Callback output is untrusted: recheck exact types and JSON bytes.
            unchanged = (tuple(canonical_bytes(item) for item in copied_history) == before_history
                         and canonical_bytes(copied_event) == before_event)
        except Exception:
            unchanged = False
        if not unchanged:
            raise LineageError("internal", "callback mutated its input")
        if isinstance(failure, LineageError):
            raise failure
        if failure is not None:
            raise LineageError("internal", "journal callback failed") from None
        return result
    finally:
        _CALLBACK.active = False


def _write_all(fd: int, data: bytes) -> None:
    pending = memoryview(data)
    while pending:
        try:
            written = os.write(fd, pending)
        except InterruptedError:
            continue
        if type(written) is not int or written <= 0 or written > len(pending):
            raise OSError(errno.EIO, "nonpositive or invalid journal write")
        pending = pending[written:]


def _failure(exc: Exception) -> dict[str, JSONValue]:
    detail: dict[str, JSONValue] = {"type": type(exc).__name__}
    if isinstance(exc, OSError) and type(exc.errno) is int:
        detail["errno"] = exc.errno
    return detail


def _commit(fd: int, original: bytes, boundary: int, record: bytes) -> None:
    stage = "append"
    try:
        if len(original) != boundary:
            stage = "tail_truncate"
            os.ftruncate(fd, boundary)
        stage = "append"
        os.lseek(fd, boundary, os.SEEK_SET)
        _write_all(fd, record)
        stage = "commit_fsync"
        os.fsync(fd)
    except Exception as cause:
        detail: dict[str, JSONValue] = {"operation": stage, "cause": _failure(cause)}
        try:
            os.ftruncate(fd, boundary)
            os.lseek(fd, boundary, os.SEEK_SET)
            _write_all(fd, original[boundary:])
            os.fsync(fd)
        except Exception as rollback:
            detail.update(rollback_failed=True, recovery_required=True,
                          rollback_cause=_failure(rollback))
        raise LineageError("internal", detail) from None


def transact(
    home: str | os.PathLike[str] | None = None, *, agent: str, op_id: str,
    kind: str, payload: dict[str, JSONValue], validators: Mapping[str, Validator],
    evidence: Sequence[dict[str, str]] = (), prepare: Prepare | None = None,
    clock: Callable[[], int] | None = None,
    id_factory: Callable[[], str] | None = None,
    lock_timeout_s: float = LOCK_TIMEOUT_S,
) -> Event:
    """Validate and durably append one event, or return its original replay."""
    _guard()
    resolved = resolve_home(home)
    _validate_timeout(lock_timeout_s)
    if not _matches(_AGENT, agent):
        raise LineageError("bad_args", "invalid actor")
    if not _matches(_OP, op_id):
        raise LineageError("bad_op", "invalid required operation identity")
    if not _text(kind) or type(payload) is not dict:
        raise LineageError("bad_args", "invalid kind or payload")
    try:
        if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes, bytearray)):
            raise ValueError
        evidence_list = list(evidence)
        _evidence(evidence_list)
        request = {"ledger": "main", "agent": agent, "op_id": op_id,
                   "kind": kind, "payload": payload, "evidence": evidence_list}
        canonical_bytes(request)
        request = deepcopy(request)
        request_bytes = canonical_bytes(request)
        if not isinstance(validators, Mapping):
            raise ValueError
        selected = dict(validators)
    except LineageError:
        raise
    except Exception:
        raise LineageError("bad_args", "invalid transaction arguments") from None
    request_digest = _sha(request_bytes)
    with _authority(resolved, True, lock_timeout_s) as fd:
        raw = _read(fd)
        canonical_history = []
        report, history, boundary = _scan(raw, True, canonical_history=canonical_history)
        history_bytes = tuple(canonical_history)
        _verified(report)
        for old in history:
            if old["agent"] == agent and old["op_id"] == op_id:
                if old["request_sha256"] != request_digest:
                    raise LineageError("bad_op", "operation identity has different request content")
                return deepcopy(old)
        validator = selected.get(kind)
        if validator is None or not callable(validator):
            raise LineageError("bad_args", "new event kind requires a validator")
        try:
            timestamp = time.time_ns() // 1_000_000 if clock is None else clock()
            identifier = "e-" + secrets.token_hex(8) if id_factory is None else id_factory()
            if type(timestamp) is not int or timestamp < 0 or not _matches(_ID, identifier):
                raise ValueError
        except Exception:
            raise LineageError("internal", "invalid event generator output") from None
        if any(old["id"] == identifier for old in history):
            raise LineageError("conflict", "generated event id already exists")
        draft = {"schema": "lineage.event/v1", "id": identifier,
                 "lamport": report["head"] + 1, "ts": timestamp,
                 **request, "request_sha256": request_digest,
                 "prev_sha256": report["head_sha256"]}
        if prepare is not None:
            prepared = _callback(prepare, history_bytes, draft)
            try:
                if type(prepared) is not dict:
                    raise ValueError
                canonical_bytes(prepared)
                draft["payload"] = deepcopy(prepared)
            except Exception:
                raise LineageError("internal", "preparation must return a strict JSON object") from None
        try:
            event = {**draft, "sha256": _sha(canonical_bytes(draft))}
            _envelope(event)
            record = canonical_bytes(event) + b"\n"
            # Never commit a record that the installed strict reader refuses.
            strict_loads(record[:-1])
        except Exception:
            code = "internal" if prepare is not None else "bad_args"
            raise LineageError(code, "event exceeds the strict JSON encoding contract") from None
        if _callback(validator, history_bytes, event) is not None:
            raise LineageError("internal", "validator must return None")
        _commit(fd, raw, boundary, record)
        return deepcopy(event)


def snapshot(home: str | os.PathLike[str] | None = None, *,
             lock_timeout_s: float = LOCK_TIMEOUT_S) -> History:
    """Read a verified detached complete prefix without repairing or creating."""
    _guard()
    resolved = resolve_home(home)
    _validate_timeout(lock_timeout_s)
    with _authority(resolved, False, lock_timeout_s) as fd:
        report, history, _ = _scan(_read(fd), fd is not None)
        _verified(report)
        return deepcopy(history)


def verify(home: str | os.PathLike[str] | None = None, *,
           expected_head: Mapping[str, JSONValue] | None = None,
           lock_timeout_s: float = LOCK_TIMEOUT_S) -> dict[str, JSONValue]:
    """Report internal consistency, optionally anchored to a trusted raw head."""
    _guard()
    resolved = resolve_home(home)
    _validate_timeout(lock_timeout_s)
    witness = None
    if expected_head is not None:
        try:
            if not isinstance(expected_head, Mapping):
                raise ValueError
            witness = dict(expected_head)
            _require(set(witness) == {"lamport", "sha256"}, "invalid witness fields")
            _require(type(witness["lamport"]) is int and witness["lamport"] >= 0,
                     "invalid witness Lamport")
            _require(_matches(_HASH, witness["sha256"]), "invalid witness hash")
        except Exception:
            raise LineageError("bad_args", "invalid expected head witness") from None
    with _authority(resolved, False, lock_timeout_s) as fd:
        raw = _read(fd)
        report, _, _ = _scan(raw, fd is not None)
        if report["ok"] and witness is not None and (
                witness["lamport"] != report["head"] or witness["sha256"] != report["head_sha256"]):
            report["ok"] = False
            next_line = raw.count(b"\n") + 1 + int(bool(raw) and not raw.endswith(b"\n"))
            report["errors"].append(_issue("hash_mismatch", "expected complete head mismatch",
                                           next_line, len(raw)))
        return deepcopy(report)
