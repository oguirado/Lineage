"""Passive, immutable skill packages backed by the shared journal.

The installed journal accepts request payloads and a locked prepare callback.
Request files retain their original order until that callback canonicalizes the
persisted payload. Retirement reasons likewise bind requests without becoming
additional event fields. No package text is ever imported or executed.
"""
from __future__ import annotations

from collections.abc import Sequence
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import dataclass
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
from typing import Any, TYPE_CHECKING

from lineage.core import journal
from lineage.core.errors import LineageError

if TYPE_CHECKING:
    from lineage.core.app import CallContext

JSONObject = dict[str, Any]
Data = JSONObject
_MAX_BYTES = 1048576
_SAFE_INT = 9007199254740991
_AGENT = re.compile(r"[a-z][a-z0-9-]{2,63}")
_HASH = re.compile(r"[0-9a-f]{64}")
_OP = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}")
_PATH = re.compile(r"[A-Za-z0-9._/-]{1,512}")
_KINDS = frozenset({"skill.published", "skill.retired"})
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


@dataclass(frozen=True)
class _Command:
    """Private adaptation of effective arguments to the installed journal."""

    tool: str
    args: JSONObject
    agent: str
    op_id: str
    expected_head: int | None = None


@dataclass(frozen=True)
class _Committed:
    event: JSONObject
    value: Data
    head: int
    sha256: str


def _bad(detail: str = "invalid skill arguments") -> None:
    raise LineageError("bad_args", detail)


def _match(value: Any, pattern: re.Pattern) -> None:
    if type(value) is not str or pattern.fullmatch(value) is None:
        _bad()


def _text(value: Any, minimum: int, maximum: int) -> None:
    if type(value) is not str or not minimum <= len(value) <= maximum:
        _bad()
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError:
        _bad("invalid skill text encoding")


def package(files: Sequence[JSONObject]) -> tuple[bytes, str]:
    """Return canonical package bytes and their digest without touching disk."""
    if (not isinstance(files, Sequence) or isinstance(files, (str, bytes, bytearray))
            or not 1 <= len(files) <= 256):
        _bad("invalid skill file collection")
    copied = []
    paths = set()
    for item in files:
        if type(item) is not dict or set(item) != {"path", "content"}:
            _bad("invalid skill file object")
        path, content = item["path"], item["content"]
        _match(path, _PATH)
        segments = path.split("/")
        if any(part in ("", ".", "..") for part in segments):
            _bad("invalid skill relative path")
        if segments[-1] == "SKILL.md" and path != "SKILL.md":
            _bad("skill entry point must be at package root")
        if path in paths:
            _bad("duplicate skill path")
        _text(content, 0, 65536)
        paths.add(path)
        copied.append({"path": path, "content": content})
    if "SKILL.md" not in paths:
        _bad("missing skill entry point")
    for path in paths:
        parts = path.split("/")
        if any("/".join(parts[:n]) in paths for n in range(1, len(parts))):
            _bad("skill file and directory collision")
    copied.sort(key=lambda item: item["path"])
    raw = json.dumps(copied, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(raw) > _MAX_BYTES:
        _bad("skill package byte limit exceeded")
    return raw, hashlib.sha256(raw).hexdigest()


def _payload(event: JSONObject, state: JSONObject) -> None:
    """Validate skill domain invariants using only an already-folded prefix."""
    kind = event.get("kind")
    data = event.get("payload")
    fields = {"skill_id", "sha256", "files"} if kind == "skill.published" else {"skill_id", "sha256"}
    if kind not in _KINDS or type(data) is not dict or set(data) != fields:
        _bad("invalid skill event payload")
    _match(data["skill_id"], _AGENT)
    _match(data["sha256"], _HASH)
    versions = state.get(data["skill_id"], {})
    previous = versions.get(data["sha256"])
    if kind == "skill.published":
        if type(data["files"]) is not list:
            _bad("event files must be an array")
        raw, pin = package(data["files"])
        if pin != data["sha256"]:
            raise LineageError("hash_mismatch", "skill event digest disagrees with package")
        ordered = json.loads(raw)
        if data["files"] != ordered:
            _bad("skill event files must be in canonical path order")
        if previous is not None and previous["files"] != ordered:
            raise LineageError("hash_mismatch", "immutable skill version disagrees with history")
    elif previous is None:
        _bad("skill version does not exist")
    lamport = event.get("lamport")
    if type(lamport) is not int or not 1 <= lamport <= _SAFE_INT:
        _bad("invalid skill publication order")


def _apply(state: JSONObject, event: JSONObject) -> None:
    """Change only the skills namespace and detach every event-owned value."""
    if event.get("kind") not in _KINDS:
        return
    data = event["payload"]
    versions = state.setdefault("skills", {}).setdefault(data["skill_id"], {})
    previous = versions.get(data["sha256"])
    if event["kind"] == "skill.published":
        versions[data["sha256"]] = {
            "skill_id": data["skill_id"], "sha256": data["sha256"],
            "files": deepcopy(data["files"]),
            "retired": previous["retired"] if previous is not None else False,
            "publication": event["lamport"],
        }
    else:
        versions[data["sha256"]] = {**previous, "retired": True,
                                      "files": deepcopy(previous["files"])}


def _catalogue(events: Sequence[JSONObject]) -> JSONObject:
    state: JSONObject = {"skills": {}}
    for event in events:
        if event.get("kind") in _KINDS:
            try:
                _payload(event, state["skills"])
                _apply(state, event)
            except LineageError:
                raise LineageError("hash_mismatch", "invalid committed skill history") from None
    return state["skills"]


def _validate_published(history: tuple[JSONObject, ...], event: JSONObject) -> None:
    if event.get("kind") != "skill.published":
        _bad("incorrect skill event validator")
    _payload(event, _catalogue(history))


def _validate_retired(history: tuple[JSONObject, ...], event: JSONObject) -> None:
    if event.get("kind") != "skill.retired":
        _bad("incorrect skill event validator")
    _payload(event, _catalogue(history))


class _SkillsFold:
    kinds = _KINDS
    order = 20

    def __call__(self, state: JSONObject, event: JSONObject) -> JSONObject:
        _apply(state, event)
        return state


def _home(ctx: CallContext) -> Path:
    try:
        return Path(ctx.home).resolve()
    except (AttributeError, TypeError, ValueError, OSError, RuntimeError):
        _bad("invalid skill context")


def _history(ctx: CallContext) -> tuple[JSONObject, ...]:
    try:
        return journal.snapshot(_home(ctx))
    except LineageError as exc:
        raise LineageError(exc.code, "skill journal history was refused") from None


def _skill(row: JSONObject) -> JSONObject:
    raw, pin = package(row["files"])
    if pin != row["sha256"]:
        raise LineageError("hash_mismatch", "skill digest disagrees with authoritative bytes")
    return {"skill_id": row["skill_id"], "sha256": pin,
            "retired": row["retired"], "files": json.loads(raw)}


def list_skills(*, include_retired: bool = False, ctx: CallContext) -> Data:
    """List all selected version pins from verified events, without I/O writes."""
    if type(include_retired) is not bool:
        _bad()
    try:
        catalogue = _catalogue(_history(ctx))
    except LineageError as exc:
        if exc.code in {"hash_mismatch", "internal", "bad_args"}:
            raise LineageError("internal", "skill catalogue history is unavailable") from None
        raise
    rows = [{"skill_id": skill_id, "sha256": pin, "retired": row["retired"]}
            for skill_id, versions in sorted(catalogue.items())
            for pin, row in sorted(versions.items())
            if include_retired or not row["retired"]]
    if len(rows) > 10000:
        raise LineageError("internal", "skill listing exceeds result capacity")
    return {"skills": rows}


def get(skill_id: str, *, sha256: str | None = None, ctx: CallContext) -> Data:
    """Resolve a pin, or the most recently published active version."""
    _match(skill_id, _AGENT)
    if sha256 is not None:
        _match(sha256, _HASH)
    versions = _catalogue(_history(ctx)).get(skill_id, {})
    if sha256 is None:
        active = [row for row in versions.values() if not row["retired"]]
        if not active:
            _bad("active skill version does not exist")
        row = max(active, key=lambda item: item["publication"])
    else:
        row = versions.get(sha256)
        if row is None:
            _bad("skill version does not exist")
    value = _skill(row)
    _verify_projection(_home(ctx), skill_id, value["sha256"], value["files"])
    return {"skill": value}


def _agreement(tool: str, supplied: JSONObject, command: Any,
               ctx: CallContext) -> _Command:
    try:
        args = command.args
        if type(args) is not dict or set(args) not in (
                set(supplied) | {"agent", "op_id"},
                set(supplied) | {"agent", "op_id", "expected_head"}):
            _bad("invalid skill command keys")
        if type(command.tool) is not str or command.tool != tool or any(
                args[key] != val for key, val in supplied.items()):
            _bad("skill command arguments disagree")
        _match(args["agent"], _AGENT)
        _match(args["op_id"], _OP)
        if (command.agent != args["agent"] or ctx.actor != args["agent"]
                or command.op_id != args["op_id"]):
            _bad("skill command actor or operation disagrees")
        if ctx.op_id is not None and ctx.op_id != args["op_id"]:
            _bad("skill context operation disagrees")
        revision = args.get("expected_head")
        if "expected_head" in args and (
                type(revision) is not int or not 0 <= revision <= _SAFE_INT):
            _bad("invalid expected skill revision")
        if ((command.expected_head is not None and type(command.expected_head) is not int)
                or command.expected_head != revision):
            _bad("skill command revision disagrees")
        return _Command(tool, deepcopy(args), args["agent"], args["op_id"], revision)
    except (AttributeError, KeyError, TypeError, ValueError, UnicodeError):
        _bad("invalid skill command")


def _transaction(command: _Command, request: JSONObject, *,
                 kind: str, ctx: CallContext) -> _Committed:
    def prepare(history: tuple[JSONObject, ...], draft: JSONObject) -> JSONObject:
        head = history[-1]["lamport"] if history else 0
        if command.expected_head is not None and command.expected_head != head:
            raise LineageError("stale_rev", "skill revision differs from current journal head")
        if head >= _SAFE_INT:
            raise LineageError("internal", "journal head exceeds result capacity")
        catalogue = _catalogue(history)
        if kind == "skill.published":
            raw, pin = package(request["files"])
            payload = {"skill_id": request["skill_id"], "sha256": pin,
                       "files": json.loads(raw)}
        else:
            payload = {"skill_id": request["skill_id"], "sha256": request["sha256"]}
        _payload({"kind": kind, "payload": payload, "lamport": head + 1}, catalogue)
        return payload

    try:
        event = journal.transact(
            _home(ctx), agent=command.agent, op_id=command.op_id, kind=kind,
            payload=deepcopy(request), validators=ctx.validators, prepare=prepare,
        )
    except LineageError as exc:
        raise LineageError(exc.code, "skill journal transaction was refused") from None
    # The installed journal returns an event, without a render callback. Fold
    # only its original prefix so retries cannot observe later retirement.
    history = _history(ctx)
    prefix = tuple(item for item in history if item["lamport"] <= event["lamport"])
    if not prefix or prefix[-1] != event:
        raise LineageError("internal", "skill commit prefix is unavailable")
    catalogue = _catalogue(prefix)
    data = event["payload"]
    commit = {"event_ids": [event["id"]], "head": event["lamport"], "sha256": event["sha256"]}
    if kind == "skill.published":
        value = {"skill": _skill(catalogue[data["skill_id"]][data["sha256"]]), "commit": commit}
    else:
        value = {"skill_id": data["skill_id"], "sha256": data["sha256"],
                 "retired": True, "commit": commit}
    return _Committed(deepcopy(event), value, event["lamport"], event["sha256"])


def publish(skill_id: str, files: Sequence[JSONObject], *, command: Any,
            ctx: CallContext) -> _Committed:
    """Commit canonical context, then publish its confined immutable projection."""
    _match(skill_id, _AGENT)
    raw, pin = package(files)
    original = [dict(item) for item in files]
    effective = _agreement("skill_publish", {"skill_id": skill_id, "files": original}, command, ctx)
    ordered = json.loads(raw)
    _verify_projection(_home(ctx), skill_id, pin, ordered)
    result = _transaction(effective, {"skill_id": skill_id, "files": original},
                          kind="skill.published", ctx=ctx)
    _materialize(_home(ctx), skill_id, pin, ordered)
    return result


def retire(skill_id: str, sha256: str, reason: str, *, command: Any,
           ctx: CallContext) -> _Committed:
    """Retire exactly one pin, preserving its bytes and original receipts."""
    _match(skill_id, _AGENT)
    _match(sha256, _HASH)
    _text(reason, 1, 2048)
    request = {"skill_id": skill_id, "sha256": sha256, "reason": reason}
    effective = _agreement("skill_retire", request, command, ctx)
    return _transaction(effective, request, kind="skill.retired", ctx=ctx)


def _entry(parent: int, name: str):
    try:
        return os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _directory(stack: ExitStack, parent: int, name: str, *, create: bool = False,
               final: bool = False) -> int | None:
    info = _entry(parent, name)
    if info is None and create:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent)
            os.fsync(parent)
        except FileExistsError:
            pass
        info = _entry(parent, name)
    if info is None:
        return None
    if stat.S_ISLNK(info.st_mode):
        _bad("symlinked skill projection component")
    if not stat.S_ISDIR(info.st_mode):
        raise LineageError("hash_mismatch" if final else "bad_args", "invalid skill projection directory")
    try:
        fd = os.open(name, _DIR_FLAGS, dir_fd=parent)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            _bad("unsafe skill projection component")
        raise
    stack.callback(os.close, fd)
    opened = os.fstat(fd)
    if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
        _bad("skill projection component changed during access")
    return fd


def _verify_tree(root: int, files: Sequence[JSONObject]) -> None:
    expected = {item["path"]: item["content"].encode("utf-8") for item in files}
    directories = set()
    for path in expected:
        parts = path.split("/")
        directories.update("/".join(parts[:n]) for n in range(1, len(parts)))
    found = set()

    def walk(fd: int, prefix: str) -> None:
        for name in sorted(os.listdir(fd)):
            path = prefix + name
            info = _entry(fd, name)
            if info is None:
                raise LineageError("hash_mismatch", "skill projection entry disappeared")
            if stat.S_ISLNK(info.st_mode):
                _bad("symlinked skill projection entry")
            if stat.S_ISDIR(info.st_mode):
                if path not in directories:
                    raise LineageError("hash_mismatch", "unexpected skill projection directory")
                with ExitStack() as stack:
                    child = _directory(stack, fd, name)
                    if child is None:
                        raise LineageError("hash_mismatch", "skill projection directory disappeared")
                    walk(child, path + "/")
            elif stat.S_ISREG(info.st_mode) and path in expected:
                if info.st_size != len(expected[path]):
                    raise LineageError("hash_mismatch", "skill projection bytes changed")
                try:
                    leaf = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
                except OSError as exc:
                    if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                        _bad("unsafe skill projection entry")
                    raise
                try:
                    opened = os.fstat(leaf)
                    if (not stat.S_ISREG(opened.st_mode)
                            or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)):
                        _bad("skill projection entry changed during access")
                    chunks = []
                    remaining = len(expected[path]) + 1
                    while remaining:
                        chunk = os.read(leaf, min(65536, remaining))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        remaining -= len(chunk)
                    if b"".join(chunks) != expected[path]:
                        raise LineageError("hash_mismatch", "skill projection bytes changed")
                finally:
                    os.close(leaf)
                found.add(path)
            else:
                raise LineageError("hash_mismatch", "unexpected skill projection entry")
    walk(root, "")
    if found != set(expected):
        raise LineageError("hash_mismatch", "skill projection file set is incomplete")


def _verify_projection(home: Path, skill_id: str, pin: str,
                       files: Sequence[JSONObject]) -> bool:
    try:
        with ExitStack() as stack:
            try:
                home_fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            except FileNotFoundError:
                return False
            stack.callback(os.close, home_fd)
            parent = home_fd
            for index, name in enumerate(("skills", skill_id, pin)):
                parent = _directory(stack, parent, name, final=index == 2)
                if parent is None:
                    return False
            _verify_tree(parent, files)
            return True
    except LineageError:
        raise
    except OSError:
        raise LineageError("internal", "skill projection cannot be inspected") from None


def _write_tree(root: int, files: Sequence[JSONObject]) -> None:
    for item in files:
        parts = item["path"].split("/")
        with ExitStack() as stack:
            parent = root
            for name in parts[:-1]:
                parent = _directory(stack, parent, name, create=True)
            fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=parent)
            try:
                pending = memoryview(item["content"].encode("utf-8"))
                while pending:
                    size = os.write(fd, pending)
                    if size <= 0:
                        raise OSError(errno.EIO, "skill projection write failed")
                    pending = pending[size:]
                os.fsync(fd)
            finally:
                os.close(fd)
            os.fsync(parent)
    os.fsync(root)


def _materialize(home: Path, skill_id: str, pin: str,
                 files: Sequence[JSONObject]) -> None:
    """Stage outside the immutable final directory; never repair existing bytes."""
    if _verify_projection(home, skill_id, pin, files):
        return
    try:
        with ExitStack() as stack:
            home_fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            stack.callback(os.close, home_fd)
            root = _directory(stack, home_fd, "skills", create=True)
            parent = _directory(stack, root, skill_id, create=True)
            existing = _directory(stack, parent, pin, final=True)
            if existing is not None:
                _verify_tree(existing, files)
                return
            stage = ".stage-" + secrets.token_hex(16)
            os.mkdir(stage, mode=0o700, dir_fd=parent)
            try:
                with ExitStack() as staged:
                    stage_fd = _directory(staged, parent, stage)
                    _write_tree(stage_fd, files)
                # A completed competing directory is nonempty because every
                # package contains SKILL.md. Rename cannot replace that directory.
                existing = _directory(stack, parent, pin, final=True)
                if existing is None:
                    try:
                        os.rename(stage, pin, src_dir_fd=parent, dst_dir_fd=parent)
                    except OSError as exc:
                        if exc.errno not in (errno.EEXIST, errno.ENOTEMPTY):
                            raise
                        existing = _directory(stack, parent, pin, final=True)
                        if existing is None:
                            raise LineageError("internal", "concurrent skill projection disappeared")
                        _verify_tree(existing, files)
                else:
                    _verify_tree(existing, files)
                os.fsync(parent)
            finally:
                if _entry(parent, stage) is not None:
                    shutil.rmtree(stage, dir_fd=parent)
    except LineageError:
        raise
    except OSError:
        raise LineageError("internal", "committed skill projection could not be published") from None
