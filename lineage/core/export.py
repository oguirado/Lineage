"""Descriptor-confined, durable exports of a verified local journal snapshot.

Exports preserve opaque cache bytes without certifying their semantics. A final
MANIFEST.json is the completion marker. Interrupted exports remain incomplete;
cleanup only removes the marker created by this invocation at its pinned inode.
"""
from contextlib import contextmanager
import errno
import hashlib
import os
import re
import stat

from . import journal
from .errors import LineageError
from .schema import SchemaError, strict_loads
from lineage.domain import agents, layout, scorecard

_TREES = (("agents",), ("skills",), ("arena", "banks"))
_AUTHORITY = ("ledger", "main", "events.jsonl")
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _identity(info):
    return info.st_dev, info.st_ino


def _signature(info):
    return (_identity(info), info.st_mode, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_nlink)


def _error(code, reason):
    raise LineageError(code, reason)


def _stat(parent, name):
    try:
        return os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _open(name, flags, *, parent=None, mode=0o600):
    try:
        return os.open(name, flags, mode, dir_fd=parent)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            _error("bad_args", "unsafe filesystem component")
        raise


def _safe_component(name):
    if (type(name) is not str or name in ("", ".", "..")
            or any(c in name for c in ("/", "\\", "\x00"))
            or re.match(r"[A-Za-z]:", name) is not None):
        return False
    try:
        name.encode("utf-8", "strict")
    except UnicodeError:
        return False
    return True


class _Tree:
    """Pin every traversed component and prove its directory entry still agrees."""

    def __init__(self, home):
        self.home = journal.resolve_home(home)
        self.fds = []
        self.links = []
        self.dirs = {}
        self.observed = {}
        self.missing = set()
        self.listings = {}
        self.root = None

    def __enter__(self):
        try:
            # As in U03, ancestors above the runtime home are outside the
            # controlled boundary. The home itself must be a real directory.
            before = os.lstat(self.home)
            if not stat.S_ISDIR(before.st_mode):
                _error("bad_args", "unsafe runtime home")
            current = _open(self.home, _DIR_FLAGS)
            self.fds.append(current)
            after = os.lstat(self.home)
            if (_identity(before) != _identity(os.fstat(current))
                    or _identity(after) != _identity(before)):
                _error("busy", "runtime home changed during capture")
            self.root = current
            self.dirs[()] = current
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *unused):
        failure = None
        while self.fds:
            try:
                os.close(self.fds.pop())
            except OSError:
                failure = True
        if failure:
            _error("internal", "filesystem close failed")

    def _child(self, parent, name, create=False):
        before = _stat(parent, name)
        if before is None and create:
            try:
                os.mkdir(name, 0o700, dir_fd=parent)
                os.fsync(parent)
            except FileExistsError:
                pass
            before = _stat(parent, name)
        if before is None:
            raise FileNotFoundError
        if not stat.S_ISDIR(before.st_mode):
            _error("bad_args", "unsafe filesystem directory")
        fd = _open(name, _DIR_FLAGS, parent=parent)
        self.fds.append(fd)
        after = _stat(parent, name)
        if (after is None or _identity(before) != _identity(os.fstat(fd))
                or _identity(after) != _identity(before)):
            _error("busy", "directory changed during capture")
        self.links.append((parent, name, fd))
        return fd

    def directory(self, parts, *, create=False):
        parts = tuple(parts)
        if parts in self.dirs:
            return self.dirs[parts]
        parent = self.directory(parts[:-1], create=create)
        fd = self._child(parent, parts[-1], create)
        self.dirs[parts] = fd
        return fd

    def stable(self):
        try:
            current = os.lstat(self.home)
        except FileNotFoundError:
            _error("busy", "runtime home disappeared during capture")
        if _identity(current) != _identity(os.fstat(self.root)):
            _error("busy", "runtime home changed during capture")
        for parent, name, fd in self.links:
            entry = _stat(parent, name)
            if entry is None or _identity(entry) != _identity(os.fstat(fd)):
                _error("busy", "filesystem component changed during capture")

    def read_file(self, parts):
        parts = tuple(parts)
        try:
            parent = self.directory(parts[:-1])
        except FileNotFoundError:
            self.missing.add(parts)
            return None
        before = _stat(parent, parts[-1])
        if before is None:
            self.missing.add(parts)
            return None
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            _error("bad_args", "unsafe filesystem file")
        fd = _open(parts[-1], _FILE_FLAGS, parent=parent)
        try:
            opened = os.fstat(fd)
            after = _stat(parent, parts[-1])
            if (after is None or _signature(before) != _signature(opened)
                    or _signature(before) != _signature(after)):
                _error("busy", "file changed during capture")
            chunks = []
            while True:
                try:
                    block = os.read(fd, 65536)
                except InterruptedError:
                    continue
                if not block:
                    break
                chunks.append(block)
            after = _stat(parent, parts[-1])
            if (after is None or _signature(before) != _signature(os.fstat(fd))
                    or _signature(before) != _signature(after)):
                _error("busy", "file changed during capture")
            self.observed[parts] = _signature(before)
            self.stable()
            return b"".join(chunks)
        finally:
            os.close(fd)

    def walk(self, parts):
        """Return all regular file bytes; missing trees are distinguished."""
        parts = tuple(parts)
        try:
            fd = self.directory(parts)
        except FileNotFoundError:
            self.missing.add(parts)
            return None
        before = os.fstat(fd)
        names = tuple(sorted(os.listdir(fd)))
        self.listings[parts] = (names, _signature(before))
        result = {}
        for name in names:
            if not _safe_component(name):
                _error("bad_args", "unsupported application path")
            info = _stat(fd, name)
            if info is None:
                _error("busy", "application entry disappeared")
            path = parts + (name,)
            if stat.S_ISDIR(info.st_mode):
                children = self.walk(path)
                if children is None:
                    _error("busy", "application tree disappeared")
                result.update(children)
            elif stat.S_ISREG(info.st_mode):
                data = self.read_file(path)
                if data is None:
                    _error("busy", "application file disappeared")
                result["/".join(path)] = data
            else:
                _error("bad_args", "unsafe application entry")
        if _signature(os.fstat(fd)) != _signature(before):
            _error("busy", "application directory changed during capture")
        self.stable()
        return result

    def unchanged(self):
        self.stable()
        for parts, signature in self.observed.items():
            entry = _stat(self.directory(parts[:-1]), parts[-1])
            if entry is None or _signature(entry) != signature:
                _error("busy", "source file changed during capture")
        for parts, (names, signature) in self.listings.items():
            fd = self.directory(parts)
            if tuple(sorted(os.listdir(fd))) != names or _signature(os.fstat(fd)) != signature:
                _error("busy", "source directory changed during capture")
        for parts in self.missing:
            try:
                parent = self.directory(parts[:-1])
            except FileNotFoundError:
                continue
            if _stat(parent, parts[-1]) is not None:
                _error("busy", "previously absent source appeared")


@contextmanager
def _io_boundary():
    try:
        yield
    except LineageError:
        raise
    except Exception:
        raise LineageError("internal", "ledger filesystem operation failed") from None


def _head(history):
    return {"lamport": history[-1]["lamport"] if history else 0,
            "sha256": _sha(journal.canonical_bytes(history[-1]) + b"\n") if history else "0" * 64}


def _verify_journal(home=None, **kwargs):
    # D-VER1 composes projection checks onto the installed public facade. The
    # capture/recheck legs must use its native authority-only verifier.
    verify = vars(journal.verify).get('_lineage_native', journal.verify)
    return verify(home, **kwargs)


def _capture(home, *, expected_head=None, lock_timeout_s=journal.LOCK_TIMEOUT_S):
    """Use the public verifier/snapshot and bind them with raw-head witnesses."""
    report = _verify_journal(home, expected_head=expected_head, lock_timeout_s=lock_timeout_s)
    if not report["ok"]:
        return report, ()
    history = journal.snapshot(home, lock_timeout_s=lock_timeout_s)
    witness = _head(history)
    if witness != {"lamport": report["head"], "sha256": report["head_sha256"]}:
        _error("busy", "journal changed during capture")
    current = _verify_journal(home, expected_head=witness, lock_timeout_s=lock_timeout_s)
    if current != report:
        _error("busy", "journal changed during capture")
    return report, history


def _agent_files(history):
    records = {event['payload']['record']['agent_id']: event['payload']['record']
               for event in history if event['kind'] == 'agent.born'}
    if not records:
        scorecard.fold_scorecards(history)
    result = {}
    for identifier, record in sorted(records.items()):
        directory = layout.agent_dir('.', workflow=record['workflow'],
                                     language=record['language'], agent_id=identifier)
        contents = agents._projection_bytes(history, agent_id=identifier)
        result.update(((directory / name).as_posix(), contents[name])
                      for name in layout.PROJECTION_FILES)
    return result


def _scorecard_files(history):
    return {path: raw for path, raw in _agent_files(history).items()
            if path.endswith('/scorecard.json')}


def _projections(history, files):
    expected = _agent_files(history)
    errors = []
    for path, raw in sorted(expected.items()):
        data = files.get(path)
        reason = None
        if data is None:
            reason = 'missing'
        else:
            if path.endswith('.json'):
                try:
                    strict_loads(data)
                except SchemaError:
                    reason = 'invalid_json'
            if reason is None and data != raw:
                reason = 'content_mismatch'
        if reason:
            errors.append({'code': 'projection_drift', 'path': path, 'reason': reason})
    return {'scope': 'agents', 'checked': sorted(expected), 'errors': errors,
            'unverified': sorted(set(files) - set(expected))}


def _application_files(tree):
    files, missing = {}, []
    for parts in _TREES:
        found = tree.walk(parts)
        if found is None:
            missing.append("/".join(parts))
        else:
            files.update(found)
    return files, sorted(missing)


def _destination(out):
    if (type(out) is not str or re.fullmatch(r"[A-Za-z0-9._/-]{1,512}", out) is None
            or not out.startswith("exports/")
            or any(not _safe_component(part) for part in out.split("/"))):
        _error("bad_args", "invalid export destination")
    return tuple(out.split("/"))


def _write(parent, name, data, *, created):
    fd = _open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
               parent=parent)
    slot = None
    try:
        owned = os.fstat(fd)
        slot = len(created)
        created.append((parent, name, owned))
        pending = memoryview(data)
        while pending:
            try:
                n = os.write(fd, pending)
            except InterruptedError:
                continue
            if type(n) is not int or n <= 0 or n > len(pending):
                raise OSError(errno.EIO, "invalid export write")
            pending = pending[n:]
        os.fsync(fd)
    finally:
        try:
            # Retain the final identity and metadata even on a failed write.
            if slot is not None:
                try:
                    final = os.fstat(fd)
                except OSError:
                    # Preserve cleanup ownership when the descriptor-stat itself
                    # fails after writing a complete marker. A replaced inode
                    # is never adopted, and the original failure still escapes.
                    entry = _stat(parent, name)
                    if entry is not None and _identity(entry) == _identity(owned):
                        created[slot] = (parent, name, entry)
                    raise
                created[slot] = (parent, name, final)
        finally:
            os.close(fd)


def _assert_owned(created):
    for parent, name, before in created:
        after = _stat(parent, name)
        if after is None or _signature(after) != _signature(before):
            _error("busy", "export file changed during publication")


def _check_output(tree, parts, expected):
    """Compare one file at a time, retaining metadata rather than another copy."""
    seen, directories = set(), set()

    def check(current):
        fd = tree.directory(current)
        before = os.fstat(fd)
        names = tuple(sorted(os.listdir(fd)))
        tree.listings[current] = (names, _signature(before))
        directories.add(current[len(parts):])
        matches = True
        for name in names:
            if not _safe_component(name):
                _error("bad_args", "unsafe export entry")
            path = current + (name,)
            info = _stat(fd, name)
            if info is None:
                _error("busy", "export entry disappeared")
            if stat.S_ISDIR(info.st_mode):
                matches = check(path) and matches
            elif stat.S_ISREG(info.st_mode):
                relative = "/".join(path[len(parts):])
                data = tree.read_file(path)
                seen.add(relative)
                matches = relative in expected and data == expected[relative] and matches
            else:
                _error("bad_args", "unsafe export entry")
        if _signature(os.fstat(fd)) != _signature(before):
            _error("busy", "export directory changed during check")
        tree.stable()
        return matches

    matches = check(parts)
    expected_dirs = {()}
    for path in expected:
        components = tuple(path.split("/"))
        expected_dirs.update(components[:n] for n in range(1, len(components)))
    return matches and seen == set(expected) and directories == expected_dirs


def _remove_marker(created):
    # Descriptor-relative ownership check: never unlink a substituted entry.
    for parent, name, before in reversed(created):
        if name != "MANIFEST.json":
            continue
        after = _stat(parent, name)
        if after is not None and _signature(after) == _signature(before):
            os.unlink(name, dir_fd=parent)
            os.fsync(parent)


def _check_source(tree, report):
    tree.unchanged()
    current = _verify_journal(tree.home, expected_head={"lamport": report["head"],
                                                     "sha256": report["head_sha256"]})
    if current != report:
        _error("busy", "journal changed during export")
    tree.unchanged()


def _cleanup_completion(home, parts, marker):
    """Reopen safely after a close failure; never remove a replacement tree."""
    if marker is None:
        return
    root_identity, marker_signature = marker
    try:
        with _Tree(home) as tree:
            root = tree.directory(parts)
            if _identity(os.fstat(root)) != root_identity:
                return
            entry = _stat(root, "MANIFEST.json")
            tree.stable()
            if entry is not None and _signature(entry) == marker_signature:
                os.unlink("MANIFEST.json", dir_fd=root)
                os.fsync(root)
    except Exception:
        # An unsafe or inaccessible replacement is never followed for cleanup.
        pass


def _prepare_contents(source, report, history, out):
    raw = source.read_file(_AUTHORITY)
    if raw is None:
        _error("busy", "journal disappeared during export")
    authority = b"".join(journal.canonical_bytes(event) + b"\n" for event in history)
    # U03 proves every completed raw record canonical. Compare the
    # captured bytes as well, preserving (and disclosing) torn tails.
    tail = report["torn_tail"]
    suffix = bytes.fromhex(tail["bytes_hex"]) if tail else b""
    if raw != authority + suffix:
        _error("busy", "journal changed during export")
    files, missing = _application_files(source)
    # Rebuild every canonical agent projection for the exported
    # prefix. Source projections remain untouched; verification
    # reports their actual drift or absence separately.
    files.update(_agent_files(history))
    projections = _projections(history, files)
    if projections["errors"]:
        from .events import _verification_data, _verification_detail
        failure = {"ok": False, "journal": report, "projections": projections}
        raise LineageError("hash_mismatch", _verification_detail(_verification_data(failure)))
    files["ledger/main/events.jsonl"] = authority
    files["projections/scorecards.json"] = journal.canonical_bytes({
        "schema": "lineage.scorecards/v1", "scorecards": scorecard.fold(history)}) + b"\n"
    entries = []
    for path, data in sorted(files.items()):
        role = ("authority" if path == "ledger/main/events.jsonl" else
                "scorecard" if path == "projections/scorecards.json" or
                path.endswith('/scorecard.json') else
                "agent_projection" if path in projections['checked'] else "opaque_cache")
        entries.append({"path": path, "bytes": len(data), "sha256": _sha(data), "role": role})
    manifest = journal.canonical_bytes({
        "schema": "lineage.export/v1", "source": {
            "ledger": "main", "head": report["head"], "head_sha256": report["head_sha256"],
            "events": report["events"], "torn_tail": report["torn_tail"]},
        "projection_scope": "agents", "missing_optional_trees": missing, "files": entries}) + b"\n"
    result = {"out": out, "head": report["head"],
              "manifest": [{"path": entry["path"], "sha256": entry["sha256"]}
                           for entry in entries]}
    return files, manifest, result


def _export(home=None, *, out):
    """Capture full authority and caches; publish a manifest only after durability."""
    parts = _destination(out)
    created = []
    marker = None
    try:
        with _io_boundary():
            report, history = _capture(home)
            if not report["ok"]:
                from .events import _verification_data, _verification_detail
                failure = {"ok": False, "journal": report,
                           "projections": {"errors": []}}
                code = "internal" if not report["exists"] else "hash_mismatch"
                raise LineageError(code, _verification_detail(_verification_data(failure)))
            with _Tree(home) as source:
                files, manifest, result = _prepare_contents(source, report, history, out)
                _check_source(source, report)
                with _Tree(home) as destination:
                    parent = destination.directory(parts[:-1], create=True)
                    destination.stable()
                    try:
                        os.mkdir(parts[-1], 0o700, dir_fd=parent)
                    except FileExistsError:
                        if not _check_output(destination, parts, {**files, "MANIFEST.json": manifest}):
                            _error("conflict", "export destination differs or is incomplete")
                        destination.unchanged()
                        _check_source(source, report)
                        return result
                    os.fsync(parent)
                    root = destination.directory(parts)
                    for path, data in sorted(files.items()):
                        target = parts + tuple(path.split("/"))
                        fd = destination.directory(target[:-1], create=True)
                        destination.stable()
                        _write(fd, target[-1], data, created=created)
                    # Sync all directories, children before parents, before the
                    # completion marker. No existing destination is ever repaired.
                    for key in sorted(destination.dirs, key=lambda x: (-len(x), x)):
                        os.fsync(destination.dirs[key])
                    destination.stable()
                    _assert_owned(created)
                    if not _check_output(destination, parts, files):
                        _error("busy", "export files changed before publication")
                    _assert_owned(created)
                    _check_source(source, report)
                    try:
                        _write(root, "MANIFEST.json", manifest, created=created)
                        marker = (_identity(os.fstat(root)), _signature(created[-1][2]))
                        os.fsync(root)
                        os.fsync(parent)
                        destination.stable()
                        _assert_owned(created)
                        if not _check_output(destination, parts, {**files, "MANIFEST.json": manifest}):
                            _error("busy", "export files changed during publication")
                        destination.unchanged()
                        _assert_owned(created)
                        _check_source(source, report)
                    except BaseException:
                        _remove_marker(created)
                        raise
                    # Close failures are failures too, while the directory fd is
                    # still available to remove this invocation's marker safely.
                    try:
                        source.__exit__(None, None, None)
                        # Keep root/parent descriptors pinned through all closes.
                        keep = {root, parent}
                        for fd in list(reversed(destination.fds)):
                            if fd not in keep:
                                destination.fds.remove(fd)
                                os.close(fd)
                    except BaseException:
                        _remove_marker(created)
                        raise
                    return result
    except LineageError:
        _cleanup_completion(home, parts, marker)
        raise
    except Exception:
        _cleanup_completion(home, parts, marker)
        raise LineageError("internal", "ledger export failed") from None


def prepare_export(home=None, *, out):
    """Validate the exact export plan without creating or publishing anything."""
    parts = _destination(out)
    with _io_boundary():
        report, history = _capture(home)
        if not report['ok']:
            _error('internal' if not report['exists'] else 'hash_mismatch', 'export authority unavailable')
        with _Tree(home) as source:
            files, manifest, result = _prepare_contents(source, report, history, out)
            _check_source(source, report)
            with _Tree(home) as destination:
                try:
                    destination.directory(parts)
                except FileNotFoundError:
                    pass
                else:
                    if not _check_output(destination, parts, {**files, 'MANIFEST.json': manifest}):
                        _error('conflict', 'export destination differs or is incomplete')
                destination.unchanged()
            _check_source(source, report)
            source.unchanged()
            return {'head': report['head'], 'payload': {
                'out': out, 'manifest_sha256': _sha(manifest)}}


def export_ledger(home=None, *, out):
    """Return the public export result, with the durable manifest stored on disk."""
    return _export(home, out=out)


def export(out, *, context):
    """Context adapter retaining exactly the public library result."""
    return export_ledger(context.home, out=out)


def main(argv, *, context, registry, stdin, stdout, stderr):
    from .events import _delegate
    if len(argv) != 2 or argv[0] != "--out" or type(argv[1]) is not str:
        return _delegate(None, {}, context=context, registry=registry, stdout=stdout)
    return _delegate("ledger_export", {"out": argv[1]}, context=context,
                     registry=registry, stdout=stdout)
