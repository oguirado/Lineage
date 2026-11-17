"""Independent fixtures. No production replacement, stub, or seed fallback."""
import copy
import hashlib
import importlib
import importlib.util
import inspect
import itertools
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import time
import unittest

EVENT_PATH = "ledger/main/events.jsonl"
LOCK_PATH = "ledger/main/events.lock"
ZERO = "0" * 64
FIELDS = {"schema", "id", "lamport", "ts", "ledger", "agent", "kind",
          "payload", "op_id", "request_sha256", "evidence", "prev_sha256", "sha256"}
REPORT_FIELDS = {"ok", "exists", "ledger", "events", "head", "head_sha256", "torn_tail", "errors"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def accept(history, event):
    return None


def forbidden(*args, **kwargs):
    raise AssertionError("Replay must not invoke this hook")


def event(number=1, *, previous=ZERO, agent="agent-one", op_id=None,
          kind="claim", payload=None, evidence=(), ts=1700000000000, identifier=None):
    payload = {"value": number} if payload is None else copy.deepcopy(payload)
    request = {"ledger": "main", "agent": agent,
               "op_id": op_id or f"request{number:04d}", "kind": kind,
               "payload": payload, "evidence": list(evidence)}
    value = {"schema": "lineage.event/v1", "id": identifier or f"e-{number:016x}",
             "lamport": number, "ts": ts, "prev_sha256": previous,
             **request, "request_sha256": sha(canonical(request))}
    value["sha256"] = sha(canonical(value))
    return value


def rehash(value):
    value = copy.deepcopy(value)
    value.pop("sha256", None)
    value["sha256"] = sha(canonical(value))
    return value


def line(value):
    return canonical(value) + b"\n"


def chain(count=3):
    result = []
    previous = ZERO
    for index in range(1, count + 1):
        value = event(index, previous=previous,
                      payload={"value": index, "text": "é雪"})
        result.append(line(value))
        previous = sha(result[-1])
    return result


def independent_verify(raw):
    """Assertion oracle for exact canonical lines, two hashes, order and identities."""
    previous = ZERO
    ids, operations, events = set(), set(), []
    def pairs(items):
        result = {}
        for key, value in items:
            assert key not in result, "duplicate JSON key"
            result[key] = value
        return result
    assert not raw or raw.endswith(b"\n"), "incomplete fixture"
    for number, record in enumerate(raw.splitlines(keepends=True), 1):
        value = json.loads(record.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=lambda value: (_ for _ in ()).throw(AssertionError(value)))
        assert set(value) == FIELDS
        assert line(value) == record, "noncanonical bytes"
        assert type(value["lamport"]) is int and value["lamport"] == number
        assert type(value["ts"]) is int and value["ts"] >= 0
        assert value["schema"] == "lineage.event/v1" and value["ledger"] == "main"
        assert value["prev_sha256"] == previous, "raw-line predecessor digest"
        assert value == rehash(value), "event digest"
        identity = (value["agent"], value["op_id"])
        assert value["id"] not in ids and identity not in operations
        ids.add(value["id"])
        operations.add(identity)
        previous = sha(record)
        events.append(value)
    return tuple(events)


def load_module(case, name):
    try:
        available = importlib.util.find_spec(name)
    except ModuleNotFoundError:
        available = None
    case.assertIsNotNone(available, name.replace(".", "/") + ".py is absent; "
                         "behavioral fail-first prerequisite unavailable (no stub permitted)")
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        case.fail("Public module cannot load its prerequisites: " + type(exc).__name__)


class CoreCase(unittest.TestCase):
    def setUp(self):
        self.journal = load_module(self, "lineage.core.journal")
        self.errors = load_module(self, "lineage.core.errors")
        self.locking = load_module(self, "lineage.core.locking")
        for name in ("transact", "snapshot", "verify", "canonical_bytes"):
            self.assertTrue(callable(getattr(self.journal, name, None)),
                            "Missing U03 public behavior: " + name)
        self.assertIn("validators", inspect.signature(self.journal.transact).parameters,
                      "U03/K0 public interface reconciliation is required")
        self.error = self.errors.LineageError
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name) / "runtime"
        self.ids = itertools.count(1)
        self.ops = itertools.count(1)

    @property
    def path(self):
        return self.home / EVENT_PATH

    def bytes(self):
        return self.path.read_bytes() if self.path.exists() else b""

    def install(self, raw=b""):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(raw)
        (self.home / LOCK_PATH).touch()

    def tx(self, **overrides):
        options = dict(agent="agent-one", op_id=f"request{next(self.ops):04d}",
                       kind="claim", payload={"value": 1}, validators={"claim": accept},
                       clock=lambda: 1700000000000,
                       id_factory=lambda: f"e-{next(self.ids):016x}")
        options.update(overrides)
        home = options.pop("home", self.home)
        return self.journal.transact(home, **options)

    def rejects(self, code, function, *args, **kwargs):
        before = self.bytes()
        with self.assertRaises(self.error) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.bytes(), before, "Rejected operation changed authority bytes")
        return caught.exception

    def bad_record(self, raw, *, count=0, number=1, offset=0):
        self.install(raw)
        report = self.journal.verify(self.home)
        self.assertEqual(set(report), REPORT_FIELDS)
        self.assertIs(report["ok"], False)
        self.assertIs(report["exists"], True)
        self.assertEqual(report["events"], count)
        self.assertEqual(len(report["errors"]), 1)
        issue = report["errors"][0]
        self.assertEqual(set(issue), {"code", "detail", "path", "line", "byte_offset"})
        self.assertEqual((issue["code"], issue["path"], issue["line"], issue["byte_offset"]),
                         ("hash_mismatch", EVENT_PATH, number, offset))
        self.assertTrue(issue["detail"])
        self.rejects("hash_mismatch", self.journal.snapshot, self.home)
        self.rejects("hash_mismatch", self.tx, op_id="later-request")
        self.assertEqual(self.bytes(), raw)
        return report

    def child(self, action, **options):
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe()
        process = context.Process(target=worker, args=(child, str(self.home), action, options))
        process.start()
        child.close()
        self.addCleanup(self.reap, process, parent)
        return process, parent

    @staticmethod
    def reap(process, connection=None):
        if process.is_alive() and process.pid is not None and process.pid > 1:
            process.terminate()
        process.join(timeout=0.25)
        if process.is_alive() and process.pid is not None and process.pid > 1:
            process.kill()
            process.join(timeout=0.25)
        if connection is not None:
            connection.close()

    def receive(self, connection, timeout=1.5):
        self.assertTrue(connection.poll(timeout), "Child did not acknowledge before deadline")
        return connection.recv()

    def finished(self, process, timeout=1.5):
        process.join(timeout)
        self.assertFalse(process.is_alive(), "Child exceeded bounded join")
        self.assertEqual(process.exitcode, 0)

    def lock_released(self):
        process, pipe = self.child("probe")
        self.assertEqual(self.receive(pipe), ("ok", "acquired"))
        self.finished(process)


def worker(pipe, home, action, options):
    """Independent process; acknowledgements and commands replace scheduler sleeps."""
    try:
        from lineage.core import journal
        from lineage.core.errors import LineageError
        if action in {"probe", "hold"}:
            import fcntl
            fd = os.open(Path(home) / LOCK_PATH, os.O_RDONLY)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if action == "hold":
                    pipe.send(("ready", "locked"))
                    if not pipe.poll(1.5):
                        raise AssertionError("Lock release acknowledgement missing")
                    assert pipe.recv() == "release"
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
            pipe.send(("ok", "acquired"))
            return
        if options.pop("wait", False):
            pipe.send(("ready", action))
            if not pipe.poll(1.5):
                raise AssertionError("Start acknowledgement missing")
            assert pipe.recv() == "go"
        def gate(history, candidate):
            if options.get("claim_gate"):
                pipe.send(("entered", len(history)))
                if options.get("pause"):
                    if not pipe.poll(1.5):
                        raise AssertionError("Gate release acknowledgement missing")
                    assert pipe.recv() == "release"
                if any(item["kind"] == "claim" for item in history):
                    raise LineageError("conflict", "claim already committed")
        if action in {"snapshot", "verify"}:
            pipe.send(("ok", getattr(journal, action)(home, lock_timeout_s=0)))
        elif action == "batch":
            events = []
            for index in range(16):
                events.append(journal.transact(home, agent="agent-one",
                    op_id=f"writer{options['index']:02d}-{index:04d}", kind="claim",
                    payload={"writer": options["index"], "item": index},
                    validators={"claim": accept}, clock=lambda: 1234))
            pipe.send(("ok", events))
        elif action == "paused_write":
            from unittest.mock import patch
            real_write = os.write
            paused = False
            def write(fd, data):
                nonlocal paused
                if not paused and os.path.samestat(os.fstat(fd), os.stat(Path(home) / EVENT_PATH)):
                    paused = True
                    written = real_write(fd, data[:7])
                    pipe.send(("partial", written))
                    if not pipe.poll(1.5):
                        raise AssertionError("Append release acknowledgement missing")
                    assert pipe.recv() == "release"
                    return written
                return real_write(fd, data)
            with patch.object(os, "write", write):
                result = journal.transact(home, agent="agent-one", op_id="paused-write",
                    kind="claim", payload={"value": 2}, validators={"claim": accept})
            assert paused, "write fault seam was not exercised"
            pipe.send(("ok", result))
        else:
            hooks = forbidden if action == "replay" else None
            result = journal.transact(home, agent=options.get("agent", "agent-one"),
                op_id=options.get("op_id", "shared-request"), kind="claim",
                payload=options.get("payload", {"value": 1}),
                validators={} if hooks else {"claim": gate},
                prepare=hooks, clock=hooks or (lambda: 1234),
                id_factory=hooks or (lambda: options.get("id", "e-123456789abcdef0")),
                lock_timeout_s=options.get("timeout", 0.5))
            if action == "lost_return":
                pipe.send(("committed", None))
            else:
                pipe.send(("ok", result))
    except Exception as exc:
        pipe.send(("error", getattr(exc, "code", type(exc).__name__)))
    finally:
        pipe.close()
