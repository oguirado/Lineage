"""A5-A11: context isolation, validation, error provenance and passive data."""
import copy
import importlib
import json
import math
import os
from pathlib import Path
from unittest import mock

from .support import BoundaryCase, GOOD, SCHEMA, request, rpc_error

class AppTests(BoundaryCase):
    def test_a5_home_precedence_and_carrier_metadata(self):
        registry = self.registry()
        cwd, environment = Path.cwd(), dict(os.environ)
        user = self.tmp / "user"
        with mock.patch.dict(os.environ, {"HOME": str(user), "LINEAGE_HOME": str(self.tmp / "environment")}, clear=True):
            explicit = self.app.create_context(self.home, registry=registry, actor="demo", op_id="operation-1")
            self.assertEqual(explicit.home, self.home.resolve())
            self.assertEqual((explicit.actor, explicit.op_id), ("demo", "operation-1"))
            self.assertEqual(explicit.validators, registry.validators)
            self.assertEqual(explicit.folds, registry.folds)
            self.assertEqual(self.app.create_context(registry=registry).home, (self.tmp / "environment").resolve())
            del os.environ["LINEAGE_HOME"]
            default = self.app.create_context(registry=registry)
            self.assertEqual(default.home, user / ".lineage")
            self.assertEqual((default.actor, default.op_id), (None, None))
            expanded = self.app.create_context("~/chosen", registry=registry)
            self.assertEqual(expanded.home, user / "chosen")
        self.assertEqual(Path.cwd(), cwd)
        self.assertEqual(dict(os.environ), environment)
        self.assertEqual(list(self.tmp.iterdir()), [])


    def test_a5_separate_homes_do_not_leak_context(self):
        registry = self.registry()
        contexts = [self.app.create_context(self.tmp / name, registry=registry, actor=name, op_id="op-" + name) for name in ("first", "second")]
        cwd, environment = Path.cwd(), dict(os.environ)
        for context in contexts:
            result = self.app.dispatch("oracle_echo", GOOD, context=context, registry=registry)
            self.assertEqual(result.payload, {"untrusted": GOOD})
        self.assertEqual([ctx for _, ctx in self.calls], contexts)
        self.assertEqual(Path.cwd(), cwd)
        self.assertEqual(dict(os.environ), environment)
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_a5_explicit_and_environment_empty_are_configuration_errors(self):
        registry = self.registry()
        for home, value in (("", "otherwise-valid"), (None, "")):
            with self.subTest(home=home), mock.patch.dict(os.environ, {"LINEAGE_HOME": value}):
                with self.assertRaises(self.app.ToolError) as caught:
                    self.app.create_context(home, registry=registry)
                self.assertEqual(caught.exception.code, "bad_args")
        self.assertEqual(self.calls, [])
        self.assert_no_home()

    def test_a6_direct_and_adapters_share_one_dispatch(self):
        registry = self.registry()
        context = self.context(registry, actor="demo", op_id="operation-1")
        args = copy.deepcopy(GOOD)
        result = self.app.dispatch("oracle_echo", args, context=context, registry=registry)
        self.assertEqual((result.payload, result.failure, result.exit_code), ({"untrusted": GOOD}, None, 0))
        self.assertIs(self.calls[0][1], context)
        self.assertEqual(args, GOOD)
        # Reload under the spy to support either qualified or imported dispatch.
        self.addCleanup(importlib.reload, self.cli)
        self.addCleanup(importlib.reload, self.mcp)
        with mock.patch.object(self.app, "dispatch", wraps=self.app.dispatch) as shared:
            importlib.reload(self.cli)
            importlib.reload(self.mcp)
            try:
                self.assertEqual(self.cli_json(["call", "oracle_echo", "--json", json.dumps(GOOD)], registry), result.payload)
                response = self.rpc("tools/call", {"name": "oracle_echo", "arguments": GOOD}, registry)
                self.assert_tool_result(response, result.payload)
                self.assertEqual(shared.call_count, 2)
            finally:
                pass
        importlib.reload(self.cli)
        importlib.reload(self.mcp)
        self.assertEqual(len(self.calls), 3)
        self.assert_no_home()

    def test_a6_handler_receives_detached_arguments_and_result_is_detached(self):
        returned = {"nested": ["original"]}
        def mutate(args, *, context):
            args["nested"]["message"] = "changed"
            return returned
        registry = self.registry(mutate)
        args = copy.deepcopy(GOOD)
        result = self.app.dispatch("oracle_echo", args, context=self.context(registry), registry=registry)
        self.assertEqual(args, GOOD)
        returned["nested"].append("later")
        self.assertEqual(result.payload, {"untrusted": {"nested": ["original"]}})
        self.assertEqual(len(self.calls), 1)

    def test_a7_arguments_reject_before_handler_and_keep_diagnostics(self):
        registry = self.registry()
        context = self.context(registry)
        malformed = [None, [], "text", {}, {**GOOD, "n": True}, {**GOOD, "n": "7"}, {**GOOD, "extra": 1}, {**GOOD, "nested": {**GOOD["nested"], "extra": 1}}]
        for args in malformed:
            with self.subTest(args=args):
                result = self.app.dispatch("oracle_echo", args, context=context, registry=registry)
                self.assertEqual((result.failure, result.exit_code), ("request", 2))
                self.assertEqual(result.payload["code"], "bad_args")
                self.assertIs(result.payload["ok"], False)
                if isinstance(args, dict):
                    self.assertEqual(set(result.payload["detail"]), {"reason", "pointer", "schema_pointer"})
                    cli = self.cli_json(["call", "oracle_echo", "--json", json.dumps(args)], registry, expected=2)
                    self.assertEqual(cli, result.payload)
                self.assertEqual(self.calls, [])
        absent = self.app.dispatch("not_registered", GOOD, context=context, registry=registry)
        self.assertEqual((absent.failure, absent.exit_code, absent.payload["code"]), ("request", 2, "bad_args"))
        self.assertEqual(self.calls, [])
        self.assert_no_home()

    def test_a7_non_json_direct_arguments(self):
        cycle = {}
        cycle["self"] = cycle
        registry = self.registry(schema={"type": "object"})
        for args in ({"x": math.nan}, {"x": math.inf}, cycle, {"x": {1}}, {"x": "\ud800"}, {1: "invalid key"}, {"x": object()}):
            with self.subTest(kind=type(next(iter(args.values()))).__name__):
                result = self.app.dispatch("oracle_echo", args, context=self.context(registry), registry=registry)
                self.assertEqual((result.failure, result.exit_code, result.payload["code"]), ("request", 2, "bad_args"))
        self.assertEqual(self.calls, [])

    def test_a8_request_and_handler_bad_args_are_different_failures(self):
        def reject(args, *, context):
            raise self.app.ToolError("bad_args", {"reason": "domain rejection"})
        registry = self.registry(reject)
        self.assertEqual(self.cli_json(["call", "oracle_echo", "--json", "{}"], registry, expected=2)["code"], "bad_args")
        self.assertEqual(self.calls, [])
        expected = {"ok": False, "code": "bad_args", "detail": {"reason": "domain rejection"}}
        self.assertEqual(self.cli_json(["call", "oracle_echo", "--json", json.dumps(GOOD)], registry, expected=3), expected)
        self.assertEqual(self.rpc("tools/call", {"name": "oracle_echo", "arguments": {}}, registry), rpc_error(-32602, 1))
        self.assert_tool_result(self.rpc("tools/call", {"name": "oracle_echo", "arguments": GOOD}, registry), expected, True)
        self.assertEqual(len(self.calls), 2)
        self.assert_no_home()

    def test_a8_forged_error_attributes_are_untrusted(self):
        class Forged(Exception):
            code = "memory_required"
            detail = "SECRET_ORACLE"
            def as_dict(self):
                return {"ok": False, "code": self.code, "detail": self.detail}
        def reject(args, *, context):
            raise Forged("SECRET_ORACLE")
        registry = self.registry(reject)
        result = self.app.dispatch("oracle_echo", GOOD, context=self.context(registry), registry=registry)
        self.assertEqual((result.payload, result.failure, result.exit_code), ({"ok": False, "code": "internal"}, "execution", 3))
        self.assertEqual(len(self.calls), 1)

    def test_a8_concrete_u03_error_when_installed(self):
        try:
            errors = importlib.import_module("lineage.core.errors")
        except ModuleNotFoundError as exc:
            if exc.name == "lineage.core.errors":
                self.skipTest("PENDING U03 concrete LineageError integration")
            raise
        def reject(args, *, context):
            raise errors.LineageError("memory_required", "receipt missing")
        registry = self.registry(reject)
        expected = {"ok": False, "code": "memory_required", "detail": "receipt missing"}
        self.assertEqual(self.cli_json(["call", "oracle_echo", "--json", json.dumps(GOOD)], registry, expected=3), expected)
        self.assert_tool_result(self.rpc("tools/call", {"name": "oracle_echo", "arguments": GOOD}, registry), expected, True)
        self.assertEqual(len(self.calls), 2)

    def test_a9_false_and_nested_wrapper_are_passive_success(self):
        for value in ({"ok": False, "code": "memory_required"}, {"untrusted": {"action": "do nothing"}}, None, False, [1, None, "雪"]):
            with self.subTest(value=value):
                registry = self.registry(lambda args, context: value)
                payload = {"untrusted": value}
                self.assertEqual(self.cli_json(["call", "oracle_echo", "--json", json.dumps(GOOD)], registry), payload)
                self.assert_tool_result(self.rpc("tools/call", {"name": "oracle_echo", "arguments": GOOD}, registry), payload)
        self.assertEqual(len(self.calls), 10)
        self.assert_no_home()

    def test_a10_invalid_results_and_invalid_error_details(self):
        cycle = []
        cycle.append(cycle)
        values = [math.nan, math.inf, cycle, {1}, "\ud800", {1: "invalid"}, object()]
        for value in values:
            with self.subTest(kind=type(value).__name__):
                registry = self.registry(lambda args, context: value)
                self.assertEqual(self.cli_json(["call", "oracle_echo", "--json", json.dumps(GOOD)], registry, expected=3), {"ok": False, "code": "internal"})
                self.assert_tool_result(self.rpc("tools/call", {"name": "oracle_echo", "arguments": GOOD}, registry), {"ok": False, "code": "internal"}, True)
        for code, detail in (("unknown_code", None), ("busy", {"cost": math.nan}), ("busy", {1}), ("busy", "\ud800")):
            def reject(args, *, context):
                raise self.app.ToolError(code, detail)
            registry = self.registry(reject)
            result = self.app.dispatch("oracle_echo", GOOD, context=self.context(registry), registry=registry)
            self.assertEqual(result.payload, {"ok": False, "code": "internal"})
            self.assertEqual(result.exit_code, 3)
        self.assertEqual(len(self.calls), 18)

    def test_a10_incidental_output_and_secret_exception_sanitized(self):
        def reject(args, *, context):
            print("INCIDENTAL_ORACLE")
            raise OSError("SECRET_ORACLE at private/example.txt")
        registry = self.registry(reject)
        code, out, err = self.call_cli(["--home", str(self.home), "call", "oracle_echo", "--json", json.dumps(GOOD)], registry)
        self.assertEqual((code, json.loads(out)), (3, {"ok": False, "code": "internal"}))
        replies, mcp_err = self.exchange([request("tools/call", {"name": "oracle_echo", "arguments": GOOD})], registry)
        self.assert_tool_result(replies[0], {"ok": False, "code": "internal"}, True)
        self.assertIn("INCIDENTAL_ORACLE", err)
        self.assertIn("INCIDENTAL_ORACLE", mcp_err)
        for output in (out, json.dumps(replies)):
            self.assertNotIn("INCIDENTAL_ORACLE", output)
            self.assertNotIn("SECRET_ORACLE", output)
            self.assertNotIn("private/example.txt", output)
        self.assertEqual(len(self.calls), 2)
        self.assert_no_home()

    def test_a11_rejecting_mutation_gets_exact_context_once_without_witness(self):
        observed = []
        def reject(args, *, context):
            observed.append((args, context))
            raise self.app.ToolError("memory_required")
        registry = self.registry(reject, mutating=True)
        context = self.context(registry, actor="demo", op_id="operation-1")
        result = self.app.dispatch("oracle_echo", GOOD, context=context, registry=registry)
        self.assertEqual((result.failure, result.exit_code), ("execution", 3))
        self.assertIs(observed[0][1], context)
        self.assertEqual(observed[0][0], GOOD)
        self.cli_json(["call", "oracle_echo", "--json", json.dumps(GOOD)], registry, expected=3)
        self.assert_tool_result(self.rpc("tools/call", {"name": "oracle_echo", "arguments": GOOD}, registry), {"ok": False, "code": "memory_required"}, True)
        self.assertEqual(len(observed), 3)
        self.assertEqual([(ctx.actor, ctx.op_id) for _, ctx in observed[1:]], [(None, None), (None, None)])
        self.assert_no_home()

    def test_a11_real_journal_replay_integration(self):
        self.skipTest("PENDING: U03/domain-owned replay witness and carrier contract; not a U04-only pass")

ERROR_CODES = "bad_args bad_op stale_rev busy internal conflict no_agent no_run run_closed memory_required memory_debt forbidden_level not_inheritable hash_mismatch rule_not_declared no_benchmark heldout_forbidden seat_not_allowed fixture_readonly timeout".split()

def domain_error_test(code):
    def test(self):
        def reject(args, *, context):
            raise self.app.ToolError(code)
        registry = self.registry(reject)
        expected = {"ok": False, "code": code}
        result = self.app.dispatch("oracle_echo", GOOD, context=self.context(registry), registry=registry)
        self.assertEqual((result.payload, result.failure, result.exit_code), (expected, "execution", 3))
        self.assertEqual(self.cli_json(["call", "oracle_echo", "--json", json.dumps(GOOD)], registry, expected=3), expected)
        self.assert_tool_result(self.rpc("tools/call", {"name": "oracle_echo", "arguments": GOOD}, registry), expected, True)
        self.assertEqual(len(self.calls), 3)
        self.assert_no_home()
    return test

for code in ERROR_CODES:
    setattr(AppTests, "test_a9_domain_" + code, domain_error_test(code))
