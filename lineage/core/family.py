"""Recipient-owned, durable family mailbox shared by drain and stdio."""
from __future__ import annotations

from collections.abc import Sequence
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import time

from . import envelope as wire, journal, jsonlane as lane
from .errors import LineageError


class _PathError(Exception):
    def __init__(self, reason, path="."):
        super().__init__(reason)
        self.path = path


class Refusal(_PathError):
    """Configuration or consumer ownership was refused."""


class UnsafeEntry(_PathError):
    """An unsafe or replaced filesystem object must not be followed."""


class RecoveryError(Exception):
    """Retained completion or durability cannot be established."""


def _diagnostic(carrier, error):
    # Only fixed reasons and validated, home-relative control names reach here.
    return f"lineage {carrier}: refused {error.path}: {error}\n"


def _identity(info):
    return info.st_dev, info.st_ino


def _stamp(info):
    return (_identity(info), info.st_mode, info.st_nlink, info.st_uid,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _stat(directory, name):
    try:
        return os.stat(name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _regular(info, path="."):
    if info is None:
        raise UnsafeEntry("missing file", path)
    if stat.S_ISLNK(info.st_mode):
        raise UnsafeEntry("symlink", path)
    if not stat.S_ISREG(info.st_mode):
        raise UnsafeEntry("not a regular file", path)
    if info.st_nlink != 1:
        raise UnsafeEntry("hard-linked file", path)
    if info.st_uid != os.geteuid():
        raise UnsafeEntry("not owned by current user", path)
    if info.st_mode & 0o022:
        raise UnsafeEntry("group/world writable (chmod 600)", path)


def _owned(info, path="."):
    if info is None:
        raise UnsafeEntry("missing directory", path)
    if stat.S_ISLNK(info.st_mode):
        raise UnsafeEntry("symlink", path)
    if not stat.S_ISDIR(info.st_mode):
        raise UnsafeEntry("not a directory", path)
    if info.st_uid != os.geteuid():
        raise UnsafeEntry("not owned by current user", path)
    if info.st_mode & 0o022:
        raise UnsafeEntry("group/world writable (chmod 700)", path)


def _same_entry(directory, name, before):
    current = _stat(directory, name)
    if current is None or _stamp(current) != _stamp(before):
        raise UnsafeEntry("entry changed")


def _read_regular(directory, name, cap=None, *, path="."):
    before = _stat(directory, name)
    if before is None:
        raise FileNotFoundError(name)
    _regular(before, path)  # Classify FIFOs and symlinks before opening anything.
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=directory)
    except OSError:
        raise UnsafeEntry("entry replaced before open", path) from None
    try:
        opened = os.fstat(fd)
        _regular(opened, path)
        if _stamp(opened) != _stamp(before):
            raise UnsafeEntry("entry replaced")
        _same_entry(directory, name, opened)
        chunks, size = [], 0
        while cap is None or size <= cap:
            try:
                chunk = os.read(fd, 65536 if cap is None else min(65536, cap + 1 - size))
            except InterruptedError:
                continue
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        _same_entry(directory, name, opened)
        if _stamp(os.fstat(fd)) != _stamp(opened):
            raise UnsafeEntry("entry modified")
        return b"".join(chunks), opened
    finally:
        os.close(fd)


def _write_all(fd, raw):
    view = memoryview(raw)
    while view:
        try:
            count = os.write(fd, view)
        except InterruptedError:
            continue
        if count <= 0:
            raise RecoveryError("incomplete write")
        view = view[count:]


def _atomic_write(directory, name, value, guard, *, raw=None):
    """Publish a complete LF record; never overwrite an unsafe destination."""
    raw = wire.canonical(value) + b"\n" if raw is None else raw
    guard()
    before = _stat(directory, name)
    if before is not None:
        _regular(before)
    temporary = ".family-" + secrets.token_hex(16) + ".tmp"
    fd = None
    created = None
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
        created = os.fstat(fd)
        _write_all(fd, raw)
        os.fsync(fd)
        written = os.fstat(fd)
        os.close(fd)
        fd = None
        guard()
        _same_entry(directory, temporary, written)
        current = _stat(directory, name)
        if before is None:
            if current is not None:
                raise UnsafeEntry("destination appeared")
        else:
            _regular(current)
            _same_entry(directory, name, before)
        os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        published = _stat(directory, name)
        _regular(published)
        if _identity(published) != _identity(written):
            raise UnsafeEntry("published entry replaced")
        os.fsync(directory)
    finally:
        if fd is not None:
            os.close(fd)
        if created is not None:
            current = _stat(directory, temporary)
            if current is not None and _identity(current) == _identity(created):
                os.unlink(temporary, dir_fd=directory)


def _transient(result, effect):
    return (result.get("ok") is False and
            (result.get("code") in {"busy", "internal"}
             or result.get("code") == "timeout" and effect == "external"))


class Mailbox:
    def __init__(self, endpoint: str, *, ctx) -> None:
        self.endpoint = endpoint
        self.runtime = lane._runtime(ctx)
        self._fds = []
        self._links = []
        self._paths = {}
        self._lock = None
        self._config_stamp = None
        self._request = None
        self._retry = {}
        self.root = self.base = self.spool = self.state = self.dedup = None

    def _directory(self, parent, name, *, create=False):
        path = "/".join(part for part in (self._paths[parent], name) if part != ".")
        before = _stat(parent, name)
        if before is None and create:
            self._guard()
            try:
                os.mkdir(name, mode=0o700, dir_fd=parent)
                os.fsync(parent)
            except FileExistsError:
                pass
            before = _stat(parent, name)
        if before is None:
            raise Refusal("missing directory", path)
        _owned(before, path)
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                     dir_fd=parent)
        self._fds.append(fd)
        self._paths[fd] = path
        after = os.fstat(fd)
        _owned(after, path)
        linked = _stat(parent, name)
        if (_identity(before) != _identity(after) or linked is None
                or _identity(linked) != _identity(after)):
            raise UnsafeEntry("directory replaced", path)
        self._links.append((parent, name, fd))
        return fd

    def open(self) -> None:
        if self._fds:
            raise Refusal("consumer already open")
        try:
            if (type(self.endpoint) is not str
                    or wire.ENDPOINT_RE.fullmatch(self.endpoint) is None):
                raise Refusal("invalid endpoint")
            self.home = Path(self.runtime.context.home)
            try:
                before = os.stat(self.home, follow_symlinks=False)
            except FileNotFoundError:
                raise Refusal("missing directory") from None
            _owned(before)
            self.root = os.open(self.home, os.O_RDONLY | os.O_DIRECTORY
                                | os.O_NOFOLLOW | os.O_CLOEXEC)
            self._fds.append(self.root)
            self._paths[self.root] = "."
            if _identity(os.fstat(self.root)) != _identity(before):
                raise UnsafeEntry("home replaced")
            family = self._directory(self.root, "family")
            self.base = self._directory(family, self.endpoint)
            self._configuration()
            self.spool = self._directory(self.base, "spool", create=True)
            self.state = self._directory(self.base, "state", create=True)
            self.dedup = self._directory(self.base, "dedup", create=True)
            self._guard()
            if _stat(self.base, "consumer.lock") is not None:
                raise Refusal("consumer lock exists", f"family/{self.endpoint}/consumer.lock")
            try:
                lock = os.open("consumer.lock", os.O_WRONLY | os.O_CREAT | os.O_EXCL
                               | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.base)
            except FileExistsError:
                raise Refusal("consumer lock exists", f"family/{self.endpoint}/consumer.lock") from None
            self._lock = (lock, os.fstat(lock))
            _write_all(lock, b"owned\n")
            os.fsync(lock)
            os.fsync(self.base)
            self.check_tree()
        except BaseException as exc:
            try:
                self.release()
            except Exception:
                raise Refusal("startup ownership changed") from None
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            if isinstance(exc, (UnsafeEntry, Refusal)):
                raise Refusal(str(exc), exc.path) from None
            if isinstance(exc, (OSError, wire.InvalidEnvelope)):
                raise Refusal("recipient configuration or ownership refused") from None
            raise

    def check_tree(self) -> None:
        if not self._fds:
            raise Refusal("consumer is not open")
        current = os.stat(self.home, follow_symlinks=False)
        _owned(current)
        if _identity(current) != _identity(os.fstat(self.root)):
            raise UnsafeEntry("home replaced")
        for parent, name, fd in self._links:
            path = self._paths[fd]
            info = os.fstat(fd)
            _owned(info, path)
            linked = _stat(parent, name)
            if linked is None or _identity(linked) != _identity(info):
                raise UnsafeEntry("directory replaced", path)
            _owned(linked, path)
        if self._lock is not None:
            fd, original = self._lock
            current = _stat(self.base, "consumer.lock")
            _regular(current, f"family/{self.endpoint}/consumer.lock")
            if (_identity(current) != _identity(original)
                    or _identity(os.fstat(fd)) != _identity(original)):
                raise UnsafeEntry("consumer ownership changed")

    def _guard(self):
        self.check_tree()
        if self._config_stamp is not None:
            _same_entry(self.base, "config.json", self._config_stamp)
        if self._request is not None:
            name, info = self._request
            _same_entry(self.spool, name, info)

    def _configuration(self):
        self.check_tree()
        path = f"family/{self.endpoint}/config.json"
        try:
            raw, info = _read_regular(self.base, "config.json", wire.MAX_REQUEST_BYTES,
                                      path=path)
            config = wire.configuration(raw, self.endpoint)
        except UnsafeEntry as exc:
            raise Refusal(str(exc), exc.path) from None
        except FileNotFoundError:
            raise Refusal("missing configuration", path) from None
        except wire.InvalidEnvelope:
            raise Refusal("invalid configuration", path) from None
        except OSError:
            raise Refusal("cannot read configuration", path) from None
        self._config_stamp = info
        self._guard()
        return config

    def release(self) -> None:
        failure = None
        try:
            if self._lock is not None:
                self.check_tree()
                fd, info = self._lock
                current = _stat(self.base, "consumer.lock")
                if current is None or _identity(current) != _identity(info):
                    raise UnsafeEntry("consumer ownership changed")
                os.unlink("consumer.lock", dir_fd=self.base)
                os.fsync(self.base)
        except Exception as exc:
            failure = exc
        finally:
            if self._lock is not None:
                try:
                    os.close(self._lock[0])
                except OSError as exc:
                    failure = failure or exc
                self._lock = None
            for fd in reversed(self._fds):
                try:
                    os.close(fd)
                except OSError as exc:
                    failure = failure or exc
            self._fds.clear()
            self._links.clear()
            self._paths.clear()
            self._config_stamp = self._request = None
        if failure is not None:
            raise failure

    def quarantine(self, name: str) -> None:
        if type(name) is not str or "/" in name or name in {"", ".", ".."}:
            raise UnsafeEntry("invalid entry name")
        self._guard()
        before = _stat(self.spool, name)
        if before is None:
            return
        # Rename the entry itself, including a symlink or FIFO, without opening it.
        destination = "quarantine-" + secrets.token_hex(16)
        current = _stat(self.spool, name)
        if current is None or _stamp(current) != _stamp(before):
            raise UnsafeEntry("entry replaced")
        os.rename(name, destination, src_dir_fd=self.spool, dst_dir_fd=self.state)
        os.fsync(self.state)
        os.fsync(self.spool)

    def publish(self, identity: str, result: wire.JSONObject,
                envelope: wire.JSONObject | None = None) -> None:
        if (type(identity) is not str or wire.ID_RE.fullmatch(identity) is None
                or identity == "invalid0"):
            raise RecoveryError("invalid publication identity")
        if envelope is not None and envelope.get("id") != identity:
            raise RecoveryError("publication identity mismatch")
        try:
            receipt = lane._receipt(identity, result, envelope)
        except wire.InvalidEnvelope:
            raise RecoveryError("invalid result") from None
        marker = identity + '.done'
        if _stat(self.state, marker) is not None:
            existing, info = _read_regular(self.state, marker, 128)
            if existing != ('<!-- ' + identity + '_DONE -->\n').encode():
                raise RecoveryError('invalid completion marker')
            self._guard()
            _same_entry(self.state, marker, info)
            os.unlink(marker, dir_fd=self.state)
            os.fsync(self.state)
        _atomic_write(self.state, identity + ".result.json", receipt, self._guard)
        _atomic_write(self.state, marker, None, self._guard,
                      raw=('<!-- ' + identity + '_DONE -->\n').encode())

    def completed(self, identity):
        """A visible receipt without its exact completion marker is in progress."""
        if type(identity) is not str or wire.ID_RE.fullmatch(identity) is None or identity == 'invalid0':
            raise RecoveryError('invalid publication identity')
        try:
            marker, marker_info = _read_regular(self.state, identity + '.done', 128)
        except FileNotFoundError:
            return None
        if marker != ('<!-- ' + identity + '_DONE -->\n').encode():
            raise RecoveryError('invalid completion marker')
        raw, _ = _read_regular(self.state, identity + '.result.json')
        result = wire._parse(raw, bounded=False)
        if result.get('id') != identity or not lane._result_valid(result.get('result')):
            raise RecoveryError('invalid completed receipt')
        lane._receipt(identity, result['result'], result)
        self._guard()
        try:
            _same_entry(self.state, identity + '.done', marker_info)
        except UnsafeEntry:
            return None
        return result

    def _aborted(self, value):
        name = value['id'] + '.abort'
        try:
            raw, _ = _read_regular(self.spool, name, wire.MAX_REQUEST_BYTES)
            if len(raw) > wire.MAX_REQUEST_BYTES:
                self.quarantine(name)
                raise LineageError('bad_args')
        except FileNotFoundError:
            return False
        except UnsafeEntry:
            self.quarantine(name)
            raise LineageError('bad_args') from None
        self._guard()
        return True

    def _committed(self, value, name):
        if name is None or lane._effect(name, self.runtime) != 'journal':
            return False
        operation = wire.operation_id(value)
        return any(event['agent'] == value['agent'] and event['op_id'] == operation
                   for event in journal.snapshot(self.runtime.context.home))


    def _admitted(self, value):
        if self._lock is None:
            raise Refusal("consumer ownership required")
        config = self._configuration()
        value, name, args = lane._admit(value, config, self.runtime)
        self._guard()
        return value, config, name, args

    def retained(self, envelope: wire.JSONObject) -> wire.JSONObject | None:
        value, _, tool, _ = self._admitted(envelope)
        name = value["id"] + ".json"
        try:
            raw, _ = _read_regular(self.dedup, name)
        except FileNotFoundError:
            return None
        except (OSError, UnsafeEntry):
            raise RecoveryError("unreadable retention") from None
        try:
            record = wire._parse(raw, bounded=False)
            required = {"identity", "digest", "op_id", "phase"}
            if not required <= record.keys() or record.keys() - required - {"result"}:
                raise ValueError
            identity = record["identity"]
            if type(identity) is not dict or set(identity) != {"source", "target", "id"}:
                raise ValueError
            if (identity["id"] != value["id"] or identity["target"] != self.endpoint
                    or type(identity["source"]) is not str
                    or wire.ENDPOINT_RE.fullmatch(identity["source"]) is None):
                raise ValueError
            if (type(record["digest"]) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", record["digest"]) is None
                    or record["op_id"] != wire.operation_id(identity)):
                raise ValueError
            if record["phase"] == "pending":
                if "result" in record:
                    raise ValueError
            elif record["phase"] == "complete":
                if ("result" not in record or not lane._result_valid(record["result"])
                        or record['result'].get('untrusted', {}).get('dry_run') is True):
                    raise ValueError
            else:
                raise ValueError
        except (ValueError, TypeError, KeyError):
            raise RecoveryError("corrupt retention") from None
        expected = {key: value[key] for key in ("source", "target", "id")}
        if record["identity"] != expected or record["digest"] != wire.digest(value):
            raise LineageError("bad_op")
        if record["phase"] == "complete":
            effect = "read" if tool is None else lane._effect(tool, self.runtime)
            if (not lane._valid_for(record["result"], tool)
                    or _transient(record["result"], effect)):
                raise RecoveryError("invalid completed result")
        self._guard()
        return record

    def _witness(self, value, result, name):
        if (name is None or "untrusted" not in result
                or lane._effect(name, self.runtime) != "journal"):
            return
        try:
            commit = result["untrusted"]["commit"]
            # snapshot verifies the authoritative complete prefix and releases
            # its ledger lock before this function returns or any redispatch.
            events = journal.snapshot(self.runtime.context.home)
            selected = [event for event in events if event["id"] in commit["event_ids"]]
            if not selected or [event["id"] for event in selected] != commit["event_ids"]:
                raise ValueError
            last = selected[-1]
            if last["lamport"] != commit["head"] or last["sha256"] != commit["sha256"]:
                raise ValueError
            root = wire.operation_id(value)
            for event in selected:
                op = event["op_id"]
                child = (type(op) is str and op.startswith(root + "-")
                         and re.fullmatch(r"[A-Za-z0-9_-]{1,15}", op[len(root) + 1:]))
                if event["agent"] != value["agent"] or not (op == root or child):
                    raise ValueError
        except Exception:
            raise RecoveryError("missing verified application witness") from None

    def _process(self, envelope):
        value, config, name, _ = self._admitted(envelope)
        destination = _stat(self.state, value["id"] + ".result.json")
        if destination is not None:
            _regular(destination)
        if value['kind'] == 'call' and value['payload'].get('dry_run', False):
            if self._aborted(value):
                return {'ok': False, 'code': 'bad_op', 'detail': 'cancelled by order'}
            result = lane._dispatch(value, config, self.runtime)
            if self._aborted(value):
                return {'ok': False, 'code': 'bad_op', 'detail': 'cancelled by order'}
            return result
        record = self.retained(value)  # Admission always precedes this lookup.
        if record is not None and record["phase"] == "complete":
            value, config, name, _ = self._admitted(value)
            self._witness(value, record["result"], name)
            self._guard()
            if value["kind"] == "capabilities":
                return lane._dispatch(value, config, self.runtime)
            return record["result"]
        committed = self._committed(value, name)
        def cancel_before_commit():
            if not committed and self._aborted(value):
                raise LineageError('bad_op', 'cancelled by order')
        cancelled = False
        try:
            cancel_before_commit()
        except LineageError as exc:
            if exc.code != 'bad_op':
                raise
            cancelled = True
        pending = {"identity": {key: value[key] for key in ("source", "target", "id")},
                   "digest": wire.digest(value), "op_id": wire.operation_id(value),
                   "phase": "pending"}
        # Republish an existing pending record too: a prior directory fsync may
        # have failed. Observing a visible file cannot establish durability.
        _atomic_write(self.dedup, value["id"] + ".json", pending, self._guard)
        # Reload admission at the final boundary before invoking a domain tool.
        value, config, name, _ = self._admitted(value)
        self._guard()
        try:
            if cancelled:
                result = {'ok': False, 'code': 'bad_op', 'detail': 'cancelled by order'}
            else:
                with lane.app.before_commit(cancel_before_commit):
                    result = lane._dispatch(value, config, self.runtime)
        except lane.app._Cancelled:
            result = {'ok': False, 'code': 'bad_op', 'detail': 'cancelled by order'}
        except Exception as exc:
            result = lane._exception(exc)
        effect = "read" if name is None else lane._effect(name, self.runtime)
        if _transient(result, effect):
            return result
        self._witness(value, result, name)
        complete = {**pending, "phase": "complete", "result": result}
        _atomic_write(self.dedup, value["id"] + ".json", complete, self._guard)
        return result

    def dispatch(self, envelope: wire.JSONObject) -> wire.JSONObject:
        try:
            return self._process(envelope)
        except (wire.InvalidEnvelope, Refusal):
            return lane._error("bad_args")
        except Exception as exc:
            return lane._exception(exc)

    def _remove_request(self, name, info):
        self._guard()
        _same_entry(self.spool, name, info)
        os.unlink(name, dir_fd=self.spool)
        os.fsync(self.spool)
        self._retry.pop(name, None)

    def _consume(self, name):
        self._configuration()
        if type(name) is not str or "/" in name or not name.endswith(".json"):
            return None, False
        stem = name[:-5]
        if name.startswith(".") or name.endswith(".result.json"):
            return None, False
        if wire.ID_RE.fullmatch(stem) is None or stem == "invalid0":
            self.quarantine(name)
            return None, False
        try:
            raw, info = _read_regular(self.spool, name, wire.MAX_REQUEST_BYTES)
        except FileNotFoundError:
            return None, False
        except UnsafeEntry:
            self.quarantine(name)
            return None, False
        self._request = (name, info)
        value = None
        try:
            try:
                value = lane.validate_request(raw, self.endpoint, stem)
                result = self._process(value)
            except wire.InvalidEnvelope:
                result = lane._error("bad_args")
            except Refusal:
                result = lane._error("bad_args")
            except LineageError as exc:
                result = lane._exception(exc)
            # Uncertain I/O or corrupt recovery propagates, preserving the
            # request and original retention rather than caching completion.
            self.publish(stem, result, value)
            name_effect = (None if value is None or value["kind"] == "capabilities" else
                           "ledger_events" if value["kind"] == "events.read" else value["payload"]["tool"])
            effect = (lane._effect(name_effect, self.runtime)
                      if name_effect in self.runtime.registry.tools else "read")
            if _transient(result, effect):
                previous = self._retry.get(name)
                attempt = 1 if previous is None else min(previous[2] + 1, 6)
                self._retry[name] = (_stamp(info), time.monotonic() + 2 ** (attempt - 1), attempt)
                return result, False
            self._remove_request(name, info)
            return result, True
        finally:
            self._request = None

    def consume(self, name: str) -> None:
        self._consume(name)

    def _receive(self, value):
        value, _, _, _ = self._admitted(value)
        if not (value['kind'] == 'call' and value['payload'].get('dry_run', False)):
            self.retained(value)  # Refuse a collision before touching a request file.
        name = value["id"] + ".json"
        try:
            raw, _ = _read_regular(self.spool, name, wire.MAX_REQUEST_BYTES)
        except FileNotFoundError:
            _atomic_write(self.spool, name, value, self._guard)
        else:
            old = lane.validate_request(raw, self.endpoint, value["id"])
            if wire.digest(old) != wire.digest(value):
                raise LineageError("bad_op")
        result, _ = self._consume(name)
        if result is None:
            raise RecoveryError("delivery did not produce a result")
        return result

    def sweep(self) -> int:
        self._configuration()
        count = 0
        for name in sorted(os.listdir(self.spool)):
            if name.startswith(".") or not name.endswith(".json") or name.endswith(".result.json"):
                continue
            retry = self._retry.get(name)
            info = _stat(self.spool, name)
            if retry and info is not None and retry[0] == _stamp(info) and time.monotonic() < retry[1]:
                continue
            _, consumed = self._consume(name)
            count += int(consumed)
        return count


def main(argv: Sequence[str] | None = None, *, context=None, registry=None,
         stdin=None, stdout=None, stderr=None) -> int:
    stderr = sys.stderr if stderr is None else stderr
    box = None
    status = 0
    try:
        args = list(sys.argv[1:] if argv is None else argv)
        if any(type(arg) is not str for arg in args) or len(args) not in (2, 4):
            raise Refusal("invalid drain arguments")
        if args[:1] != ["--endpoint"]:
            raise Refusal("invalid drain arguments")
        poll = 25
        if len(args) == 4:
            if args[2] != "--poll-ms" or re.fullmatch(r"[0-9]{1,5}", args[3]) is None:
                raise Refusal("invalid poll interval")
            poll = int(args[3])
        if not 1 <= poll <= 60000:
            raise Refusal("invalid poll interval")
        runtime = lane._runtime(context, registry)
        box = Mailbox(args[1], ctx=runtime)
        box.open()
        while True:
            box.sweep()
            time.sleep(poll / 1000)
    except KeyboardInterrupt:
        pass
    except (wire.InvalidEnvelope, Refusal, UnsafeEntry):
        stderr.write("recipient configuration or consumer ownership refused\n")
        status = 2
    except Exception:
        stderr.write("mailbox recovery or I/O failure\n")
        status = 3
    finally:
        if box is not None:
            try:
                box.release()
            except Exception:
                stderr.write("consumer ownership changed during release\n")
                status = 3
    return status


if __name__ == "__main__":
    raise SystemExit(main())
