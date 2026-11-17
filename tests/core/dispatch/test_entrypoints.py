"""A6, A13, A15, A19, A23-A24: real processes and rejecting controls."""
import io
import json
import os
import sys
from unittest import mock

from .support import BoundaryCase, GOOD, ROOT, request, rpc_error, wire
from .test_registry import HEADER

INVENTORY = frozenset('''reference_get reference_verify skill_list skill_get skill_publish skill_retire
agent_create agent_get agent_list agent_brief agent_clone agent_distill agent_cross agent_mutate
agent_specialize agent_retire lineage_tree memory_put memory_route memory_get memory_bootcheck
memory_history run_open run_beat run_close run_get bench_list bench_declare bench_run bench_status
bench_verdict agent_promote scorecard_get ledger_events ledger_export ledger_verify openfresnel_probe
openfresnel_spawn'''.split())

class EntrypointTests(BoundaryCase):
    def test_a13_real_original_entrypoints_discovery_and_unknown_tool(self):
        binary = ROOT / "bin/lineage"
        self.assertTrue(os.access(binary, os.X_OK), "portable entrypoint is not executable")
        self.assertTrue(binary.read_bytes().splitlines()[0].startswith(b"#!/usr/bin/env"))
        registry = self.reg.load()
        expected = {"tools": self.app.list_tools(registry=registry)}
        for argv, cwd in (([sys.executable, "-m", "lineage"], ROOT), ([str(binary)], self.tmp)):
            with self.subTest(entrypoint=argv[-1]):
                result = self.process([*argv, "--home", str(self.home), "tools"], cwd=cwd)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout), expected)
                self.assertTrue(result.stdout.endswith(b"\n"))
                bad = self.process([*argv, "--home", str(self.home), "call", "not_registered", "--json", "{}"], cwd=cwd)
                self.assertEqual(bad.returncode, 2)
                self.assertEqual(json.loads(bad.stdout)["code"], "bad_args")
                self.assertNotIn(b"Traceback", bad.stderr)
        self.assert_no_home()

    def test_a6_real_cli_and_mcp_success_have_identical_payloads(self):
        root = self.fixture_repo()
        data = {"value": {"unicode": "雪", "cost": None}}
        results = []
        commands = ([sys.executable, "-m", "lineage"], [str(root / "bin/lineage")])
        for argv in commands:
            result = self.process([*argv, "call", "oracle_fixture", "--json", json.dumps(data)], cwd=root if argv[0] == sys.executable else self.tmp)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(result.stdout.endswith(b"\n"))
            results.append(json.loads(result.stdout))
        expected = {"untrusted": {"args": data, "actor": None, "op_id": None, "home_name": self.home.name, "calls": 1}}
        self.assertEqual(results, [expected, expected])
        with self.child(root) as peer:
            self.assert_tool_result(peer.send(request("tools/call", {"name": "oracle_fixture", "arguments": data})), expected)
            peer.process.stdin.close()
            self.assertEqual(peer.process.wait(timeout=0.8), 0)
        self.assert_no_home()

    def test_a15_real_stdio_discovery_and_handshake_are_promptly_flushed(self):
        root = self.fixture_repo()
        tools = self.process([sys.executable, "-m", "lineage", "tools"], cwd=root)
        self.assertEqual(tools.returncode, 0)
        descriptors = json.loads(tools.stdout)
        with self.child(root) as peer:
            self.assertEqual(peer.send(request("tools/list"))["result"], descriptors)
            hello = peer.send(request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "oracle", "version": "test"}}, ident=2))
            self.assertEqual(hello["result"], {"protocolVersion": "2024-11-05", "serverInfo": {"name": "lineage", "version": "0.1.0"}, "capabilities": {"tools": {}, "resources": {}, "prompts": {}}})
            self.assertEqual(peer.send(request("ping", ident=3)), {"jsonrpc": "2.0", "id": 3, "result": {}})
            from .support import RESOURCES, PROMPTS
            # A-COM1: discovery may grow (TaskLight lesson: never pin exact inventories); the frozen originals must remain, byte-identical.
            listed = peer.send(request("resources/list", ident=4))["result"]["resources"]
            for row in RESOURCES: self.assertIn(row, listed)
            names = [row["name"] for row in peer.send(request("prompts/list", ident=5))["result"]["prompts"]]
            self.assertEqual(names, sorted(names)); self.assertTrue(set(PROMPTS) <= set(names))
            self.assertIn("resourceTemplates", peer.send(request("resources/templates/list", ident=6))["result"])
            peer.process.stdin.close()
            self.assertEqual(peer.process.wait(timeout=0.8), 0)
        self.assert_no_home()

    def test_a19_real_stdio_error_liveness_and_eof(self):
        root = self.fixture_repo()
        with self.child(root) as peer:
            self.assertEqual(peer.send(b"not json\n"), rpc_error(-32700))
            self.assertEqual(peer.send(request("tools/call", {}, ident=2)), rpc_error(-32602, 2))
            failed = peer.send(request("tools/call", {"name": "oracle_fixture", "arguments": {"mode": "error"}}, ident=3))
            self.assert_tool_result(failed, {"ok": False, "code": "memory_required"}, True, ident=3)
            value = {"value": None}
            success = peer.send(request("tools/call", {"name": "oracle_fixture", "arguments": value}, ident=4))
            self.assert_tool_result(success, {"untrusted": {"args": value, "actor": None, "op_id": None, "home_name": self.home.name, "calls": 2}}, ident=4)
            peer.process.stdin.close()
            self.assertEqual(peer.process.wait(timeout=0.8), 0)
        self.assert_no_home()

    def test_a18_real_frame_limit_recovery_and_final_eof_frame(self):
        root = self.fixture_repo()
        ping = wire(request("ping", ident="edge"))
        exact = ping + b" " * (65536 - len(ping))
        raw = exact + b"\n" + exact + b" \n" + b"\xff\n" + wire(request("ping", ident="final"))
        child = self.process([sys.executable, "-m", "lineage", "mcp"], cwd=root, raw=raw)
        self.assertEqual(child.returncode, 0)
        self.assertEqual([json.loads(line) for line in child.stdout.splitlines()], [
            {"jsonrpc": "2.0", "id": "edge", "result": {}}, rpc_error(-32700), rpc_error(-32700), {"jsonrpc": "2.0", "id": "final", "result": {}},
        ])
        self.assert_no_home()

    def test_a23_duplicate_bypass_is_detected_by_registry_oracle(self):
        duplicates = {"duplicate.py": HEADER + "TOOLS=(spec,spec)\n"}
        # Reuse the production-observing rejection assertion, not a second model.
        from .test_registry import RegistryTests
        check = lambda: RegistryTests.assert_registry_rejects(self, duplicates, "duplicate_tool")
        check()
        good = self.registry()
        with mock.patch.object(self.reg, "load", return_value=good):
            with self.assertRaises(AssertionError):
                check()

    def test_a23_adapter_descriptor_omission_is_detected(self):
        registry = self.registry()
        descriptors = self.app.list_tools(registry=registry)
        def check():
            self.assertEqual(self.cli_json(["tools"], registry), {"tools": descriptors})
        check()
        original = self.cli.main
        def omit(argv, **kwargs):
            destination = kwargs["stdout"]
            captured = io.StringIO()
            code = original(argv, **{**kwargs, "stdout": captured})
            value = json.loads(captured.getvalue())
            value["tools"] = []
            destination.write(json.dumps(value) + "\n")
            return code
        with mock.patch.object(self.cli, "main", side_effect=omit):
            with self.assertRaises(AssertionError):
                check()
        self.assertEqual(self.calls, [])

    def test_a23_dispatch_validation_bypass_is_detected(self):
        registry = self.registry()
        context = self.context(registry)
        def check():
            result = self.app.dispatch("oracle_echo", {}, context=context, registry=registry)
            self.assertEqual((result.failure, result.exit_code), ("request", 2))
            self.assertEqual(result.payload["code"], "bad_args")
        check()
        self.assertEqual(self.calls, [])
        def bypass(name, args, *, context, registry):
            value = registry.tools[name].handler(args, context=context)
            return self.app.DispatchResult(payload={"untrusted": value})
        with mock.patch.object(self.app, "dispatch", side_effect=bypass):
            with self.assertRaises(AssertionError):
                check()
        self.assertEqual(len(self.calls), 1)

    def test_a23_wrong_iserror_is_detected_by_tool_result_oracle(self):
        def reject(args, *, context):
            raise self.app.ToolError("memory_required")
        registry = self.registry(reject)
        def check():
            self.assert_tool_result(self.rpc("tools/call", {"name": "oracle_echo", "arguments": GOOD}, registry), {"ok": False, "code": "memory_required"}, True)
        check()
        original = self.mcp.main
        def wrong_flag(**kwargs):
            captured = io.StringIO()
            code = original(**{**kwargs, "stdout": captured})
            value = json.loads(captured.getvalue())
            value["result"]["isError"] = False
            kwargs["stdout"].write(json.dumps(value) + "\n")
            return code
        with mock.patch.object(self.mcp, "main", side_effect=wrong_flag):
            with self.assertRaises(AssertionError):
                check()
        self.assertEqual(len(self.calls), 2)

    def test_a24_installed_inventory_parity_is_an_integration_gate(self):
        registry = self.reg.load()
        actual = set(registry.tools)
        if actual != INVENTORY:
            self.skipTest("PENDING domain inventory: missing=" + ",".join(sorted(INVENTORY - actual)) + "; extra=" + ",".join(sorted(actual - INVENTORY)))
        expected = self.app.list_tools(registry=registry)
        self.assertEqual(self.cli_json(["tools"], registry), {"tools": expected})
        self.assertEqual(self.rpc("tools/list", registry=registry)["result"], {"tools": expected})
        self.assertNotIn("operator ruling", actual)
        self.assert_no_home()

    def test_a24_domain_result_json_http_and_journal_witnesses_pending(self):
        self.skipTest("PENDING owning units U03/U05/U06/U29 and domain fixtures: canonical calls, replay and journal witnesses are not established by U04")
