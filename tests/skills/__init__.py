"""Frozen U09 oracle support, using only public K0 seams and stdlib unittest."""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace
import hashlib
import importlib
import itertools
import json
import multiprocessing
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from lineage.domain import skills

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    {"path": "docs/note.txt", "content": "café\r\n"},
    {"path": "SKILL.md", "content": "Root\n"},
]
VECTOR = b'[{"content":"Root\\n","path":"SKILL.md"},{"content":"caf\xc3\xa9\\r\\n","path":"docs/note.txt"}]'
PIN = "9b01d7b309c3ef0b71174eae2d35e730457b73dd6bc3f73c4e7a6b23346b3904"
LIMIT = 1048576


def independent_bytes(files):
    return json.dumps(sorted(copy.deepcopy(files), key=lambda f: f["path"]),
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def independent_pin(files):
    return hashlib.sha256(independent_bytes(files)).hexdigest()


def one(content="value"):
    return [{"path": "SKILL.md", "content": content}]


def boundary_files(byte_count=LIMIT, escaped=False):
    # Keep every file within its character bound; overhead is computed separately.
    content = ("\n" if escaped else "é") * 30000
    files = [{"path": "SKILL.md", "content": ""}]
    while len(independent_bytes(files)) + 60050 < byte_count:
        files.append({"path": "data/f%03d.txt" % len(files), "content": content})
    files.append({"path": "data/tail.txt", "content": ""})
    remaining = byte_count - len(independent_bytes(files))
    assert 0 <= remaining <= 65536
    files[-1]["content"] = "x" * remaining
    assert len(independent_bytes(files)) == byte_count
    return files


def disk_image(root):
    """Capture bytes, entry types and symlink targets, never dereference a link."""
    result = {}
    if not root.exists():
        return result
    for base, dirs, names in os.walk(root, followlinks=False):
        for name in sorted(dirs + names):
            p = Path(base, name)
            key = p.relative_to(root).as_posix()
            info = p.lstat()
            if stat.S_ISLNK(info.st_mode):
                result[key] = ("link", os.readlink(p))
            elif stat.S_ISREG(info.st_mode):
                result[key] = ("file", p.read_bytes())
            else:
                result[key] = ("directory",)
    return result


def contract_schema(tool, result=False):
    text = (ROOT / "docs/CONTRACT.md").read_text(encoding="utf-8")
    marker = "### `" + tool + "`"
    section = text.split(marker, 1)[1].split("\n### ", 1)[0]
    blocks = re.findall(r"```json\s*\n(.*?)\n```", section, re.S)
    return json.loads(blocks[1 if result else 0])


class PureCase(unittest.TestCase):
    def setUp(self):
        # A real positive package witness precedes every test's negative contrast.
        # This also makes absent K0 prerequisites distinct from initial stub reds.
        self.assertEqual(skills.package(copy.deepcopy(FILES)), (VECTOR, PIN))

    def require(self, module, *names):
        try:
            value = importlib.import_module(module)
        except ImportError:
            self.fail("HOLD: required K0 module is unavailable: " + module)
        missing = [name for name in names if not hasattr(value, name)]
        self.assertEqual(missing, [], "HOLD: missing K0 exports in " + module)
        return value

    def error_type(self):
        return self.require("lineage.core.errors", "LineageError").LineageError

    def bad_package(self, files):
        with self.assertRaises(self.error_type()) as caught:
            skills.package(files)
        self.assertEqual(caught.exception.code, "bad_args")


@dataclass(frozen=True)
class Command:
    # A-U09: independent request fixture; integrated registry has no Command type.
    tool: str
    args: dict
    agent: str
    op_id: str
    expected_head: int | None = None


class RuntimeCase(PureCase):
    def setUp(self):
        super().setUp()
        # A-U09: require actual integrated registry, journal, application and schema exports.
        self.regmod = self.require("lineage.core.registry", "load")
        self.journal = self.require("lineage.core.journal", "snapshot", "transact", "verify")
        self.app = self.require("lineage.core.app", "dispatch", "create_context")
        self.schema = self.require("lineage.core.schema", "strict_loads", "validate", "SchemaError")
        self.LineageError = self.error_type()
        # A-U09: restore consistent imports after shared-schema reloads in other suites.
        # Refresh real consumers and their descriptors, without replacing any API or validator.
        if self.regmod.SchemaError is not self.schema.SchemaError:
            importlib.reload(self.regmod)
            importlib.reload(self.app)
            importlib.reload(importlib.import_module("lineage.ext.skills"))
        self.registry = self.regmod.load()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self._serial = itertools.count(1)
        self.ctx = self.context(self.home)

    def context(self, home, actor="tester", tag="main"):
        # A-U09: CallContext owns home/validators/folds; journal supplies clock and IDs.
        return self.app.create_context(home, registry=self.registry, actor=actor)

    def command(self, tool, args, *, ctx=None):
        ctx = ctx or self.ctx
        effective = copy.deepcopy(args)
        effective.setdefault("agent", ctx.actor)
        effective.setdefault("op_id", "op-" + str(next(self._serial)))
        # A-U09: use the independent effective-command fixture.
        return Command(tool=tool, args=effective,
                                   agent=effective["agent"], op_id=effective["op_id"],
                                   expected_head=effective.get("expected_head"))

    def publish(self, files=None, skill_id="sample", *, op=None, actor=None,
                expected=None, ctx=None):
        ctx = ctx or self.ctx
        if actor is not None:
            # A-U09: actor is a CallContext field, without a Services container.
            ctx = replace(ctx, actor=actor)
        args = {"skill_id": skill_id, "files": copy.deepcopy(FILES if files is None else files)}
        if op is not None:
            args["op_id"] = op
        if expected is not None:
            args["expected_head"] = expected
        command = self.command("skill_publish", args, ctx=ctx)
        return skills.publish(skill_id, args["files"], command=command, ctx=ctx)

    def retire(self, pin, *, skill_id="sample", reason="obsolete", op=None,
               expected=None, ctx=None):
        ctx = ctx or self.ctx
        args = {"skill_id": skill_id, "sha256": pin, "reason": reason}
        if op is not None:
            args["op_id"] = op
        if expected is not None:
            args["expected_head"] = expected
        return skills.retire(skill_id, pin, reason,
                             command=self.command("skill_retire", args, ctx=ctx), ctx=ctx)

    def raw(self):
        path = self.home / "ledger/main/events.jsonl"
        return path.read_bytes() if path.exists() else b""

    def events(self):
        return [json.loads(line) for line in self.raw().splitlines()]

    def projection(self, pin=PIN, skill_id="sample"):
        return self.home / "skills" / skill_id / pin

    def assert_code(self, code, operation, *, unchanged=True):
        before = self.raw() if unchanged else None
        with self.assertRaises(self.LineageError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)
        if unchanged:
            self.assertEqual(self.raw(), before)
        return caught.exception

    def assert_receipt(self, committed):
        event = committed.event
        value = committed.value
        self.assertEqual(value["commit"], {"event_ids": [event["id"]],
                                          "head": event["lamport"], "sha256": event["sha256"]})
        self.assertEqual(committed.head, event["lamport"])
        self.assertEqual(committed.sha256, event["sha256"])
        self.assertEqual(self.events()[event["lamport"] - 1], event)
        self.assert_chain()
        return value

    def assert_chain(self):
        prev = "0" * 64
        seen = set()
        for number, raw in enumerate(self.raw().splitlines(keepends=True), 1):
            event = json.loads(raw)
            self.assertEqual(raw, json.dumps(event, sort_keys=True, separators=(",", ":"),
                                             ensure_ascii=False).encode() + b"\n")
            self.assertEqual(event["lamport"], number)
            self.assertEqual(event["prev_sha256"], prev)
            self.assertNotIn(event["id"], seen)
            seen.add(event["id"])
            body = {k: v for k, v in event.items() if k != "sha256"}
            expected = hashlib.sha256(json.dumps(body, sort_keys=True,
                separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            self.assertEqual(event["sha256"], expected)
            prev = hashlib.sha256(raw).hexdigest()
        # A-U09: verify takes home and reports ok/errors in the integrated journal.
        report = self.journal.verify(self.ctx.home)
        self.assertTrue(report["ok"], report.get("errors"))

    def assert_projection(self, pin=PIN, skill_id="sample", files=None):
        expected = FILES if files is None else files
        image = disk_image(self.projection(pin, skill_id))
        actual = {path: item[1] for path, item in image.items() if item[0] == "file"}
        self.assertEqual(actual, {f["path"]: f["content"].encode() for f in expected})
        self.assertFalse(any(item[0] == "link" for item in image.values()))

    def dispatch(self, tool, args):
        # A-U09: dispatch requires registry/context and returns DispatchResult.
        return self.app.dispatch(tool, args, context=self.ctx, registry=self.registry).payload

    def assert_error_wire(self, data, code, *, schema=False):
        # A-U09: integrated schema diagnostics are closed objects; domain detail stays text.
        self.assertIs(data["ok"], False)
        self.assertEqual(data["code"], code)
        self.assertLessEqual(set(data), {"ok", "code", "detail"})
        if "detail" in data:
            if schema:
                self.assertEqual(set(data["detail"]), {"reason", "pointer", "schema_pointer"})
                self.assertIsInstance(data["detail"]["reason"], str)
                self.assertIsInstance(data["detail"]["pointer"], str)
                self.assertIsNone(data["detail"]["schema_pointer"])
                detail = json.dumps(data["detail"])
            else:
                self.assertIsInstance(data["detail"], str)
                detail = data["detail"]
            self.assertTrue(1 <= len(detail) <= 2048)
            self.assertNotIn(str(self.base), detail)
            self.assertNotIn("Traceback", detail)

    def cli(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", LINEAGE_HOME=str(self.home))
        return subprocess.run([sys.executable, "-B", "-m", "lineage", "--home",
                               str(self.home), *args], cwd=ROOT, env=env,
                              capture_output=True, timeout=1.2, check=False)

    def mcp(self, method, params):
        # A-U09: MCP remains the real integrated stdio entry point.
        self.require("lineage.core.mcp", "main")
        request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        proc = subprocess.run([sys.executable, "-B", "-m", "lineage", "--home",
                               str(self.home), "mcp"], input=json.dumps(request).encode()+b"\n",
                              cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                              capture_output=True, timeout=1.2, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode(errors="replace"))
        lines = proc.stdout.splitlines()
        self.assertEqual(len(lines), 1)
        response = json.loads(lines[0])
        self.assertEqual(response["id"], 1)
        return response



def refusal_witness(case, error_type, operation, read_history, code):
    before = read_history()
    with case.assertRaises(error_type) as caught:
        operation()
    case.assertEqual(caught.exception.code, code)
    case.assertEqual(read_history(), before)


def retirement_witness(case, lookup, expected_files):
    historical = lookup()
    case.assertTrue(historical["skill"]["retired"])
    case.assertEqual(historical["skill"]["files"], expected_files)
