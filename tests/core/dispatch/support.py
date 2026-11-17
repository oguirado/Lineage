"""Temporary fixtures only; no production replacements or domain stubs."""
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import copy
import importlib
import io
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
from types import MappingProxyType
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
PREREQUISITES = (
    "lineage/__init__.py", "lineage/core/__init__.py", "lineage/core/schema.py",
)
PRODUCTION = (
    "lineage/core/registry.py", "lineage/core/app.py", "lineage/core/cli.py",
    "lineage/core/mcp.py", "lineage/__main__.py", "lineage/ext/__init__.py",
    "bin/lineage",
)
SCHEMA = {
    "type": "object", "properties": {
        "nested": {"type": "object", "properties": {
            "message": {"type": "string"},
            "cost": {"type": ["integer", "null"]},
        }, "required": ["message", "cost"], "additionalProperties": False},
        "n": {"type": "integer"},
    }, "required": ["nested", "n"], "additionalProperties": False,
}
GOOD = {"nested": {"message": "雪 café 🧬", "cost": None}, "n": 7}
RESOURCES = [
    {"uri": "lineage://contract", "name": "Contract", "mimeType": "text/markdown"},
    {"uri": "lineage://guide/headless", "name": "Headless guide", "mimeType": "text/markdown"},
]
PROMPTS = {"breed_from_best": "bench_id", "create_agent_from_spec": "spec", "run_benchmark": "bench_id"}
FORBIDDEN = ("tasklight", "tasklight://", "CW_HOME", "CW_ROOM", "CW_AGENT", ".context-wall", "bridge.room")
HOOKS = (
    (("export",), "lineage.core.export", "main", ("--out", "exports/snapshot")),
    (("verify",), "lineage.core.events", "verify_main", ()),
    (("json",), "lineage.core.jsonlane", "main", ()),
    (("drain",), "lineage.core.family", "main", ("--endpoint", "demo", "--poll-ms", "5")),
    (("serve",), "lineage.serve.http", "main", ("--port", "0", "--fixtures", "fixtures")),
    (("operator", "ruling"), "lineage.ext.memory", "operator_main", ("--agent", "demo", "--quote-file", "quote.txt")),
)

def missing_prerequisites():
    return [name for name in PREREQUISITES if not (ROOT / name).is_file()]

def wire(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")

def request(method, params=None, ident=1):
    result = {"jsonrpc": "2.0", "method": method, "id": ident}
    if params is not None:
        result["params"] = params
    return result

def rpc_error(code, ident=None):
    messages = {-32700: "parse error", -32600: "invalid request", -32601: "method not found", -32602: "invalid params", -32603: "internal error"}
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": code, "message": messages[code]}}

class BoundaryCase(unittest.TestCase):
    def setUp(self):
        absent = missing_prerequisites()
        if absent:
            self.skipTest("BLOCKED U01/U02 prerequisites: " + ", ".join(absent))
        absent = [name for name in PRODUCTION if not (ROOT / name).is_file()]
        self.assertEqual(absent, [], "U04 application boundary is missing")
        try:
            self.reg = importlib.import_module("lineage.core.registry")
            self.app = importlib.import_module("lineage.core.app")
            self.cli = importlib.import_module("lineage.core.cli")
            self.mcp = importlib.import_module("lineage.core.mcp")
        except Exception as exc:
            self.fail("U04 public modules must import safely: " + type(exc).__name__)
        self.temp = tempfile.TemporaryDirectory(prefix="lineage-oracle-")
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)
        self.home = self.tmp / "home-not-created"
        self.calls = []
        self.test_deadline = time.monotonic() + 4.0

    def registry(self, handler=None, *, schema=None, mutating=False, name="oracle_echo"):
        def record(args, *, context):
            self.calls.append((copy.deepcopy(args), context))
            return handler(args, context=context) if handler else copy.deepcopy(args)
        tool = self.reg.ToolSpec(name=name, description="Echo passive test data.", input_schema=copy.deepcopy(SCHEMA if schema is None else schema), handler=record, mutating=mutating)
        callbacks = {"test.event": lambda history, event: self.fail("validator ran during discovery")}
        folds = {"test.event": lambda state, event: self.fail("fold ran during discovery")}
        return self.reg.Registry(tools=MappingProxyType({name: tool}), validators=MappingProxyType(callbacks), folds=MappingProxyType(folds))

    def context(self, registry, **metadata):
        return self.app.create_context(self.home, registry=registry, **metadata)

    def call_cli(self, argv, registry, raw=b""):
        out, err, leaked = io.StringIO(), io.StringIO(), io.StringIO()
        with redirect_stdout(leaked):
            code = self.cli.main(list(argv), registry=registry, stdin=io.BytesIO(raw), stdout=out, stderr=err)
        self.assertEqual(leaked.getvalue(), "", "incidental stdout escaped the CLI stream adapter")
        self.assertIn(code, (0, 2, 3))
        return code, out.getvalue(), err.getvalue()

    def cli_json(self, argv, registry, expected=0):
        code, out, err = self.call_cli(["--home", str(self.home), *argv], registry)
        self.assertEqual(code, expected)
        # Usage/configuration stream placement is unspecified by the unit spec.
        text = out if out else err
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(len(text.splitlines()), 1)
        return json.loads(text)

    def exchange(self, frames, registry=None, *, root=None, context=None):
        registry = registry if registry is not None else self.registry()
        context = context if context is not None else self.context(registry)
        raw = b"".join(frame if isinstance(frame, bytes) else wire(frame) + b"\n" for frame in frames)
        out, err, leaked = io.StringIO(), io.StringIO(), io.StringIO()
        with redirect_stdout(leaked):
            code = self.mcp.main(context=context, registry=registry, stdin=io.BytesIO(raw), stdout=out, stderr=err, resource_root=root)
        self.assertEqual(code, 0)
        self.assertEqual(leaked.getvalue(), "", "incidental stdout escaped MCP")
        text = out.getvalue()
        if text:
            self.assertTrue(text.endswith("\n"))
        return [json.loads(line) for line in text.splitlines()], err.getvalue()

    def rpc(self, method, params=None, registry=None, **kwargs):
        replies, _ = self.exchange([request(method, params)], registry, **kwargs)
        self.assertEqual(len(replies), 1)
        return replies[0]

    def assert_tool_result(self, reply, payload, is_error=False, ident=1):
        self.assertEqual(set(reply), {"jsonrpc", "id", "result"})
        self.assertEqual(reply["jsonrpc"], "2.0")
        self.assertEqual(reply["id"], ident)
        result = reply["result"]
        self.assertEqual(set(result), {"content", "isError"})
        self.assertIs(result["isError"], is_error)
        self.assertEqual(len(result["content"]), 1)
        block = result["content"][0]
        self.assertEqual(set(block), {"type", "text"})
        self.assertEqual(block["type"], "text")
        self.assertEqual(json.loads(block["text"]), payload)

    @contextmanager
    def package(self, modules):
        name = "oracle_extensions"
        directory = self.tmp / name
        directory.mkdir()
        (directory / "__init__.py").write_text("", encoding="utf-8")
        for relative, content in modules.items():
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        with mock.patch.object(sys, "path", [str(self.tmp), *sys.path]):
            importlib.invalidate_caches()
            try:
                yield name
            finally:
                for key in list(sys.modules):
                    if key == name or key.startswith(name + "."):
                        del sys.modules[key]
                shutil.rmtree(directory)
                importlib.invalidate_caches()

    def assert_no_home(self):
        self.assertFalse(self.home.exists(), "read/dispatch boundary created runtime home")

    def assert_clean_identity(self, text):
        for token in FORBIDDEN:
            self.assertNotIn(token.casefold(), text.casefold())

    def fixture_repo(self):
        """Copy actual production entrypoints; add only temporary test extensions."""
        root = self.tmp / "replica"
        root.mkdir()
        shutil.copytree(ROOT / "lineage", root / "lineage", ignore=shutil.ignore_patterns("__pycache__"))
        (root / "bin").mkdir()
        shutil.copy2(ROOT / "bin/lineage", root / "bin/lineage")
        (root / "lineage/ext/oracle_fixture.py").write_text(EXTENSION, encoding="utf-8")
        return root

    def process(self, argv, *, cwd=None, raw=b""):
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["LINEAGE_HOME"] = str(self.home)
        try:
            return subprocess.run(argv, cwd=cwd or ROOT, env=env, input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=max(0.05, min(1.2, self.test_deadline - time.monotonic())), check=False)
        except subprocess.TimeoutExpired:
            self.fail("owned entrypoint exceeded bounded deadline")

    @contextmanager
    def child(self, root):
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.update(PYTHONDONTWRITEBYTECODE="1", LINEAGE_HOME=str(self.home))
        process = subprocess.Popen([sys.executable, "-m", "lineage", "mcp"], cwd=root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertGreater(process.pid, 1)
        try:
            yield LivePeer(self, process)
        finally:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            try:
                process.wait(timeout=0.8)
            except subprocess.TimeoutExpired:
                # Exact owned child only. Never send a group signal.
                if process.poll() is None and process.pid > 1:
                    process.kill()
                process.wait(timeout=0.8)
            for stream in (process.stdout, process.stderr):
                stream.close()

class LivePeer:
    def __init__(self, case, process):
        self.case, self.process, self.pending = case, process, b""
        self.deadline = time.monotonic() + 2.5

    def send(self, value):
        self.process.stdin.write(value if isinstance(value, bytes) else wire(value) + b"\n")
        self.process.stdin.flush()
        return self.read()

    def read(self):
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            while b"\n" not in self.pending:
                remaining = self.deadline - time.monotonic()
                self.case.assertGreater(remaining, 0, "response was not flushed before the deadline")
                self.case.assertTrue(selector.select(max(0, remaining)), "no response arrived")
                chunk = os.read(self.process.stdout.fileno(), 8192)
                self.case.assertTrue(chunk, "child closed stdout before its response")
                self.pending += chunk
                self.case.assertLessEqual(len(self.pending), 131072)
        line, self.pending = self.pending.split(b"\n", 1)
        return json.loads(line)

EXTENSION = r'''from lineage.core.registry import ToolSpec
from lineage.core.app import ToolError

CALLS = 0

def echo(args, *, context):
    global CALLS
    CALLS += 1
    if args.get("mode") == "error":
        raise ToolError("memory_required")
    return {"args": args, "actor": context.actor, "op_id": context.op_id, "home_name": context.home.name, "calls": CALLS}

TOOLS = (ToolSpec(name="oracle_fixture", description="Temporary passive echo.", input_schema={"type":"object","properties":{"mode":{"type":"string"},"value":{}},"additionalProperties":False}, handler=echo, mutating=False),)
VALIDATORS = {}
FOLDS = {}
'''
