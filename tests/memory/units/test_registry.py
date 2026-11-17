"""A2, A5, A32, A36: exact registry, transport behavior and oracle controls."""
import contextlib
import importlib
import inspect
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from unittest import mock
from ._support import IntegrationCase, OracleCase, OWNER, ROOT, canonical, unit
from lineage.domain.memory import fold, schema, units
from lineage.ext import memory


class RegistryTests(IntegrationCase):
    def test_a32_exact_registry_discovery_and_callback_signatures(self):
        self.runtime()
        self.assertIsInstance(memory.TOOLS, tuple)
        self.assertEqual({t.name for t in memory.TOOLS}, {"memory_put", "memory_get", "memory_history"})
        self.assertEqual({t.name: t.effect for t in memory.TOOLS}, {"memory_put": "journal", "memory_get": "read", "memory_history": "read"})
        self.assertEqual(set(memory.VALIDATORS), {"memory.put", "memory.retire"})
        self.assertEqual(set(memory.FOLDS), {"memory"})
        registered = memory.FOLDS["memory"]
        self.assertEqual(registered.order, 30)
        self.assertEqual(registered.kinds, frozenset({"agent.born", "memory.put", "memory.retire"}))
        text = (ROOT / "docs/CONTRACT.md").read_text(encoding="utf-8")
        for tool in memory.TOOLS:
            match = re.search(r"### `" + re.escape(tool.name) + r"`\s+Arguments:\s+```json\s*(.*?)\s*```", text, re.S)
            self.assertIsNotNone(match, "missing normative tool schema")
            self.assertEqual(tool.input_schema, json.loads(match.group(1)))
            self.assertEqual(list(inspect.signature(tool.handler).parameters), ["args", "ctx"])
        for validator in memory.VALIDATORS.values():
            self.assertEqual(list(inspect.signature(validator).parameters), ["snapshot", "event", "ctx"])
        expected = ((schema.validate_unit, ["unit", "authority", "actor", "ctx"]),
                    (units.put, ["agent_id", "unit", "run_id", "command", "ctx"]),
                    (units.get, ["agent_id", "unit_id", "ctx"]),
                    (units.history, ["agent_id", "unit_id", "after", "limit", "ctx"]),
                    (units.operator_ruling, ["agent_id", "quote", "command", "ctx"]),
                    (fold.empty, []), (fold.apply, ["state", "event"]),
                    (fold.units_for, ["state", "agent_id", "include_inactive", "include_private"]))
        for function, names in expected:
            self.assertEqual(list(inspect.signature(function).parameters), names)
        self.assertIsNone(inspect.signature(units.put).parameters["run_id"].default)
        self.assertEqual(inspect.signature(units.history).parameters["limit"].default, 100)
        self.assertEqual(inspect.signature(units.history).parameters["after"].default, 0)
        self.assertNotIn("operator_ruling", self.registry.names())
        self.assertNotIn("memory_retire", self.registry.names())

    def test_a32_registry_load_is_atomic_on_duplicate_ownership(self):
        self.runtime()
        registry_api = self.require("lineage.core.registry", "load")
        for index, category in enumerate(("tool", "validator", "fold")):
            name = "fixture_extensions_%d" % index
            package = self.home / name
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            definitions = ('from lineage.core.registry import ToolSpec, FoldSpec\n'
                           'def handle(args, ctx): return {}\n'
                           'def validate(snapshot, event, ctx): return None\n'
                           'def apply(state, event): return None\n'
                           'TOOLS = ()\nVALIDATORS = {}\nFOLDS = {}\n')
            extras = {
                "tool": 'TOOLS = (ToolSpec("memory_get", "Fixture inspection", {"type":"object","properties":{},"additionalProperties":False}, "read", handle),)\n',
                "validator": 'VALIDATORS = {"memory.put": validate}\n',
                "fold": 'FOLDS = {"memory": FoldSpec(frozenset({"memory.put"}), 30, apply)}\n'}
            for filename in ("first.py", "second.py"):
                (package / filename).write_text(definitions + extras[category], encoding="utf-8")
            with mock.patch.object(sys, "path", [str(self.home), *sys.path]):
                self.error("bad_args", lambda: registry_api.load(package=name))
            self.assertEqual(set(self.registry.tools), {"memory_put", "memory_get", "memory_history"})

    def _cli(self, argv):
        cli = self.require("lineage.core.cli", "main")
        api = self.require("lineage.core.registry", "load")
        output, errors = io.StringIO(), io.StringIO()
        with self.patch_seam(api, "load", lambda *args, **kwargs: self.registry), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = cli.main(["--home", str(self.home), *argv])
        self.assertNotIn(str(self.home), output.getvalue())
        return status, json.loads(output.getvalue())

    def _mcp(self, name, args):
        mcp = self.require("lineage.core.mcp", "main")
        api = self.require("lineage.core.registry", "load")
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}
        raw = canonical(request) + b"\n"
        incoming = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8")
        outgoing = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with self.patch_seam(api, "load", lambda *args, **kwargs: self.registry), mock.patch.dict(os.environ, {"LINEAGE_HOME": str(self.home)}), mock.patch.object(sys, "stdin", incoming), mock.patch.object(sys, "stdout", outgoing):
            mcp.main()
            outgoing.flush()
            responses = outgoing.buffer.getvalue().splitlines()
        self.assertEqual(len(responses), 1)
        return json.loads(responses[0])

    def test_a32_library_dispatch_cli_mcp_read_parity(self):
        self.runtime()
        self.write()
        args = {"agent_id": OWNER, "unit_id": "unit_001"}
        expected = {"untrusted": units.get(OWNER, "unit_001", ctx=self.ctx)}
        self.assertEqual(self.dispatch("memory_get", args), expected)
        status, cli = self._cli(["call", "memory_get", "--json", canonical(args).decode()])
        self.assertEqual(status, 0)
        self.assertEqual(cli, expected)
        rpc = self._mcp("memory_get", args)
        self.assertNotIn("error", rpc)
        self.assertFalse(rpc["result"]["isError"])
        self.assertEqual(json.loads(rpc["result"]["content"][0]["text"]), expected)

    def test_a05_cli_and_mcp_ruling_domain_errors(self):
        self.runtime()
        self.ruling()
        args = {"agent_id": OWNER, "unit": unit("ruling", 1, actor="operator", uid="unit_002"), "agent": "operator", "op_id": "tool-ruling"}
        before = self.fingerprint()
        status, result = self._cli(["call", "memory_put", "--json", canonical(args).decode()])
        self.assertEqual(status, 3)
        self.assertEqual(result["code"], "forbidden_level")
        self.assertNotIn("untrusted", result)
        rpc = self._mcp("memory_put", args)
        self.assertNotIn("error", rpc)
        self.assertTrue(rpc["result"]["isError"])
        self.assertEqual(json.loads(rpc["result"]["content"][0]["text"])["code"], "forbidden_level")
        self.assertEqual(self.fingerprint(), before)
        malformed = dict(args, authority="operator")
        status, result = self._cli(["call", "memory_put", "--json", canonical(malformed).decode()])
        self.assertEqual((status, result["code"]), (2, "bad_args"))

    def test_a02_cli_hostile_decoding_never_appends(self):
        self.runtime()
        self.write()
        before = self.fingerprint()
        for raw in ('{"agent_id":"agent-one","unit_id":"unit_001","extra":{"x":1,"x":2}}',
                    '{"agent_id":"\\ud800","unit_id":"unit_001"}',
                    '{"agent_id":NaN}', '{} {}'):
            status, result = self._cli(["call", "memory_get", "--json", raw])
            self.assertEqual((status, result["code"]), (2, "bad_args"))
        self.assertEqual(self.fingerprint(), before)

    def test_a36_rejecting_oracles_fail_in_isolated_mutant_copy(self):
        self.runtime()
        self.write()
        clone = self.home / "mutant-project"
        clone.mkdir()
        shutil.copytree(ROOT / "lineage", clone / "lineage", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "schemas", clone / "schemas")
        shutil.copytree(ROOT / "docs", clone / "docs")
        target = clone / "tests/memory/units"
        target.mkdir(parents=True)
        for marker in ("tests/__init__.py", "tests/memory/__init__.py"):
            shutil.copy2(ROOT / marker, clone / marker)
        for source in (ROOT / "tests/memory/units").glob("*.py"):
            shutil.copy2(source, target / source.name)
        mutants = {
            "authority": ("tests.memory.units.test_authority.AuthorityTests.test_a05_direct_validator_tool_ruling_fence", 'schema.validate_unit = lambda *args, **kwargs: None'),
            "receipt": ("tests.memory.units.test_receipts.ReceiptTests.test_a07_wrong_missing_and_optional_receipts", '''original = units.put
def bypass(agent_id, value, **kwargs):
    value = copy.deepcopy(value)
    for receipt in value["receipts"]:
        path = kwargs["ctx"].services.home / receipt["path"]
        if path.is_file(): receipt["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    kwargs["command"] = replace(kwargs["command"], args={**kwargs["command"].args, "unit": value})
    return original(agent_id, value, **kwargs)
units.put = bypass'''),
            "graph": ("tests.memory.units.test_supersession.SupersessionTests.test_a20_shaped_incoming_backlink_is_conflict", '''original = units.put
def bypass(agent_id, value, **kwargs):
    value = copy.deepcopy(value)
    value.pop("superseded_by", None)
    value["status"] = "active"
    kwargs["command"] = replace(kwargs["command"], args={**kwargs["command"].args, "unit": value})
    return original(agent_id, value, **kwargs)
units.put = bypass''')}
        for label, (name, mutation) in mutants.items():
            runner = ('import unittest,copy,hashlib\nfrom dataclasses import replace\nfrom lineage.domain.memory import schema,units\n' + mutation + '\n'
                      'suite=unittest.defaultTestLoader.loadTestsFromName(' + repr(name) + ')\n'
                      'result=unittest.TextTestRunner(verbosity=1).run(suite)\n'
                      'raise SystemExit(0 if result.wasSuccessful() else 1)\n')
            result = subprocess.run([sys.executable, "-B", "-c", runner], cwd=clone,
                                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                                    capture_output=True, text=True, timeout=1.1)
            with self.subTest(mutant=label):
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("FAILED (failures=1)", result.stderr)
                self.assertIn("not raised", result.stderr)
                self.assertNotIn("ImportError", result.stderr)

    def test_a32_put_exact_replay_across_all_available_surfaces(self):
        self.runtime()
        value = unit()
        first = self.write(value, op="shared-operation")
        args = {"agent_id": OWNER, "unit": value, "agent": OWNER, "op_id": "shared-operation"}
        expected = {"untrusted": first.value}
        before = self.fingerprint()
        self.assertEqual(self.dispatch("memory_put", args), expected)
        status, cli = self._cli(["call", "memory_put", "--json", canonical(args).decode()])
        self.assertEqual((status, cli), (0, expected))
        rpc = self._mcp("memory_put", args)
        self.assertFalse(rpc["result"]["isError"])
        self.assertEqual(json.loads(rpc["result"]["content"][0]["text"]), expected)
        self.assertEqual(self.fingerprint(), before)

    def test_a36_frozen_inputs_and_oracle_bytes(self):
        import re
        manifest = (ROOT / "tests/memory/units/ORACLE.md").read_text(encoding="utf-8")
        rows = re.findall(r"^\| `([^`]+)` \| `([0-9a-f]{64})` \|$", manifest, re.M)
        self.assertTrue(rows, "missing frozen input/oracle hashes")
        for name, expected in rows:
            self.assertFalse(Path(name).is_absolute())
            # Campaign seals own byte identity, including subsequently retired inputs.
            self.assertNotIn("..", Path(name).parts)
