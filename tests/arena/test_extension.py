"""Actual integrated discovery/dispatch API and available headless adapters."""
from copy import deepcopy
import importlib
import importlib.util  # A-U16: locate bytecode for the temporary discovery fixture explicitly.
import io
import json
from pathlib import Path
import sys
from unittest import mock

from lineage.core import app, cli, mcp, registry, schema
from .helpers import ArenaCase, TOOL_NAMES, bench, canonical, command_source


class ExtensionTests(ArenaCase):
    def ready_read(self):
        # The same positive behavior is required before metadata can count as
        # acceptance. A descriptor-only stub must not appear green.
        return self.invoke(self.reg.tools["bench_list"].handler, {}, context=self.ctx)

    def test_a1_discovery_exact_tools_effects_validators_fold(self):
        self.assertEqual(self.ready_read(), {"benches": [], "next_after": None, "head": 0})
        extension = importlib.import_module("lineage.ext.arena")
        self.assertEqual({t.name for t in extension.TOOLS}, TOOL_NAMES)
        self.assertEqual(set(extension.VALIDATORS), {"bench.declared", "bench.result", "bench.verdict"})
        self.assertEqual(set(extension.FOLDS), {"arena"})
        self.assertTrue(callable(extension.FOLDS["arena"]))
        for tool in extension.TOOLS:
            self.assertEqual(tool.mutating, tool.name not in {"bench_list", "bench_status"})
        self.assertEqual(set(self.reg.tools) & TOOL_NAMES, TOOL_NAMES)
        self.assertNotIn("record_result", self.reg.tools)

    def test_a1_duplicate_tool_or_validator_blocks_discovery(self):
        self.ready_read()
        package = self.base / "oracle_extensions"
        package.mkdir()
        (package / "__init__.py").write_text("")
        (package / "first.py").write_text("from lineage.ext.arena import TOOLS, VALIDATORS, FOLDS\n")
        (package / "second.py").write_text("from lineage.ext.arena import TOOLS\nVALIDATORS={}\nFOLDS={}\n")
        with mock.patch.object(sys, "path", [str(self.base), *sys.path]):
            importlib.invalidate_caches()
            with self.assertRaises(registry.RegistryError) as error:
                registry.load(package="oracle_extensions")
            self.assertEqual(error.exception.detail["reason"], "duplicate_tool")
            sys.modules.pop("oracle_extensions.second", None)
            # A-U16: discard same-size, same-tick bytecode before replacing the discovery fixture.
            Path(importlib.util.cache_from_source(str(package / "second.py"))).unlink(missing_ok=True)
            (package / "second.py").write_text("from lineage.ext.arena import VALIDATORS\nTOOLS=()\nFOLDS={}\n")
            importlib.invalidate_caches()
            with self.assertRaises(registry.RegistryError) as error:
                registry.load(package="oracle_extensions")
            self.assertEqual(error.exception.detail["reason"], "duplicate_validator")
        for name in list(sys.modules):
            if name == "oracle_extensions" or name.startswith("oracle_extensions."):
                sys.modules.pop(name)

    def test_a1_mcp_and_cli_descriptor_and_sample_read_parity(self):
        expected = self.ready_read()
        descriptors = app.list_tools(registry=self.reg)
        requests = b'\n'.join(canonical(value) for value in [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "bench_list", "arguments": {}}}]) + b'\n'
        output = io.StringIO()
        mcp.main(context=self.ctx, registry=self.reg, stdin=io.BytesIO(requests), stdout=output, stderr=io.StringIO())
        replies = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(replies[0]["result"]["tools"], descriptors)
        called = replies[1]["result"]
        self.assertIs(called["isError"], False)
        self.assertEqual(json.loads(called["content"][0]["text"]), {"untrusted": expected})
        output = io.StringIO()
        code = cli.main(["--home", str(self.home), "tools"], registry=self.reg,
                        stdout=output, stderr=io.StringIO())
        self.assertEqual(code, 0)
        # A-U16: the integrated CLI wraps its unchanged descriptor list in a tools object.
        self.assertEqual(json.loads(output.getvalue()), {"tools": descriptors})

    def test_a2_dispatch_invalid_nested_inputs_no_spawn_or_append(self):
        self.ready_read()
        invalid = [{"bench_id": "bench0001", "runner": value, "agent": "arena-caller", "op_id": "strict-input"}
                   for value in ({"kind": "fake", "seed": True}, {"kind": "fake", "seed": 1, "extra": {}},
                                 {"kind": "command", "argv": ["program"], "timeout_ms": False},
                                 {"kind": "fake", "seed": float("inf")})]
        before = self.raw()
        with mock.patch("subprocess.Popen") as spawn:
            for args in invalid:
                result = app.dispatch("bench_run", args, context=self.ctx, registry=self.reg)
                self.assertEqual(result.payload["code"], "bad_args")
                self.assertEqual(result.exit_code, 2)
            spawn.assert_not_called()
        self.assertEqual(self.raw(), before)

    def test_a40_dispatch_wraps_once_and_errors_map_to_cli(self):
        expected = self.ready_read()
        success = app.dispatch("bench_list", {}, context=self.ctx, registry=self.reg)
        self.assertEqual(success.payload, {"untrusted": expected})
        self.assertEqual(success.exit_code, 0)
        failure = app.dispatch("bench_status", {"bench_id": "bench0001"}, context=self.ctx, registry=self.reg)
        self.assertEqual(failure.payload["code"], "no_benchmark")
        self.assertEqual(failure.exit_code, 3)
        for args, expected_code in ((["call", "bench_run", "--json", "{}"], 2),
                                     (["call", "bench_status", "--json", '{"bench_id":"bench0001"}'], 3),
                                     (["call", "bench_list", "--json", "{}"], 0)):
            output = io.StringIO()
            code = cli.main(["--home", str(self.home), *args], registry=self.reg,
                            stdout=output, stderr=io.StringIO())
            self.assertEqual(code, expected_code)
            self.assertNotIn("Traceback", output.getvalue())
            json.loads(output.getvalue())

    def test_a40_mcp_domain_error_is_result_with_is_error(self):
        self.ready_read()
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": "bench_status", "arguments": {"bench_id": "bench0001"}}}
        output = io.StringIO()
        mcp.main(context=self.ctx, registry=self.reg, stdin=io.BytesIO(canonical(request) + b"\n"),
                 stdout=output, stderr=io.StringIO())
        value = json.loads(output.getvalue())
        self.assertNotIn("error", value)
        self.assertIs(value["result"]["isError"], True)
        result = json.loads(value["result"]["content"][0]["text"])
        self.assertEqual(result["code"], "no_benchmark")
        self.assertIs(result["ok"], False)

    def test_a42_public_output_offline_no_promotion_and_discoverable(self):
        self.declare()
        with mock.patch("socket.create_connection", side_effect=AssertionError("network")), \
             mock.patch("subprocess.Popen", side_effect=AssertionError("external execution")):
            result = self.execute()
        public = canonical(result).decode()
        self.assertNotIn(str(self.base), public)
        self.assertNotIn(str(Path.home()), public)
        self.assertFalse(self.events("agent.status"))
        self.assertFalse(any("promotion" in e["kind"] for e in self.events()))
        self.assertTrue((Path(__file__).parent / "__init__.py").is_file())
        self.assertEqual(self.status()["declaration"]["bank_id"], "demo-offline")

    def test_a23_registered_validator_runs_inside_real_journal_lock(self):
        self.ready_read()
        from lineage.core import locking
        locked = []
        extension = importlib.import_module("lineage.ext.arena")
        original = extension.VALIDATORS["bench.declared"]
        # U03 guards nested journal entry from a validator. This must remain
        # true independently of whether a second OS thread would race.
        def validator(history, event):
            from lineage.core.errors import LineageError
            with self.assertRaises(LineageError) as error:
                journal_snapshot = __import__("lineage.core.journal", fromlist=["snapshot"])
                journal_snapshot.snapshot(self.home)
            self.assertEqual(error.exception.code, "internal")
            locked.append(event["id"])
            return original(history, event)
        validators = {**self.reg.validators, "bench.declared": validator}
        from lineage.core import journal
        self.subjects()
        self.invoke(journal.transact, self.home, agent="arena-caller", op_id="lock-witness",
                    kind="bench.declared", payload=self.decl, validators=validators,
                    clock=self.ctx.services.clock, id_factory=self.ctx.services.id_factory)
        self.assertEqual(len(locked), 1)

    def test_a23_fold_does_not_mutate_other_namespaces_or_event(self):
        self.declare()
        event = self.events("bench.declared")[0]
        pristine = deepcopy(event)
        foreign = {"agents": {"sentinel": "preserved"}, "memory": {"sentinel": "preserved"}, "runs": {}}
        state = deepcopy(foreign)
        state["arena"] = {}
        fold = self.reg.folds["arena"]
        result = self.invoke(fold, state, event)
        resulting = state if result is None else result
        for namespace, value in foreign.items():
            self.assertEqual(resulting[namespace], value)
        self.assertEqual(event, pristine)
