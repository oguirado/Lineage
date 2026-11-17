# A-U01R: Real journal fixtures and the A-FLK1 immediate-caller sleep guard.
"""Small test-only adapters; journal policy always remains in production."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

from lineage.core import app, cli, journal, mcp
from lineage.core.errors import LineageError
from lineage.core.registry import Registry, ToolSpec

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
TS = 1700000000000
_REAL_SLEEP = time.sleep


def _sleep_guard(message="real sleep forbidden"):
    def guarded_sleep(delay):
        # A-U01R: Match actual stdlib module globals, never a spoofed __name__
        # or any ancestor frame; product callbacks must still be rejected.
        caller_globals = sys._getframe(1).f_globals
        if any(caller_globals is vars(sys.modules[name])
               for name in ("subprocess", "threading", "selectors")
               if name in sys.modules):
            return _REAL_SLEEP(delay)
        raise AssertionError(message)
    return guarded_sleep


def accept(history, event):
    return None


def registry(handler=None):
    def echo(args, *, context):
        return copy.deepcopy(args)
    spec = ToolSpec("regression_echo", "Echo passive regression data.",
                    {"type": "object"}, handler or echo, False)
    return Registry({spec.name: spec}, {}, {})


def exchange(frames, *, installed=None, home=None):
    installed = registry() if installed is None else installed
    context = app.create_context(home, registry=installed)
    raw = b"".join(f if isinstance(f, bytes) else
                   json.dumps(f, ensure_ascii=False).encode() + b"\n" for f in frames)
    out, err = io.StringIO(), io.StringIO()
    code = mcp.main(registry=installed, context=context, stdin=io.BytesIO(raw),
                    stdout=out, stderr=err)
    return code, [json.loads(line) for line in out.getvalue().splitlines()], err.getvalue()


def rpc(method, params=None, identity=1):
    result = {"jsonrpc": "2.0", "id": identity, "method": method}
    if params is not None:
        result["params"] = params
    return result


class JournalCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="case-", dir=HERE)
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name) / "home"
        self.path = self.home / "ledger/main/events.jsonl"
        self.enterContext(mock.patch.object(time, "sleep", _sleep_guard()))
        self.append(op_id="seed0001")

    def append(self, *, op_id="request0001", payload=None, **kwargs):
        options = dict(agent="executor-a", op_id=op_id, kind="regression.event",
                       payload={"text": "working"} if payload is None else payload,
                       validators={"regression.event": accept}, clock=lambda: TS)
        options.update(kwargs)
        return journal.transact(self.home, **options)

    def raw(self):
        return self.path.read_bytes()

    def events(self):
        # A-U01R: Inspect persisted bytes without a recursive lock in fsync probes.
        return [json.loads(line) for line in self.raw().splitlines()]

    def snapshot(self):
        return self.raw(), len(self.events()), self.events()

    def refuse(self, call, code):
        before = self.snapshot()
        with self.assertRaises(LineageError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.snapshot(), before, "refusal changed durable journal state")
        return caught.exception
