"""Installed registry/dispatch boundary; no replacement transport or validator."""
from copy import deepcopy
import inspect
import json

from lineage.core.app import dispatch
from lineage.core.registry import ToolSpec, load
from lineage.core.schema import SchemaError, strict_loads, validate
from lineage.ext import lineage_ops
from .helpers import OracleCase, canonical


ARGS = {
    "agent_clone": {"parent_id": "parent-one", "child_id": "child-one", "agent": "creator-one", "op_id": "operation-0001"},
    "agent_distill": {"parent_id": "parent-one", "child_id": "child-one", "agent": "creator-one", "op_id": "operation-0001"},
    "agent_retire": {"agent_id": "parent-one", "reason": "Fixture retirement", "agent": "creator-one", "op_id": "operation-0001"},
    "lineage_tree": {},
}


class ExtensionOracle(OracleCase):
    def test_a01_discovery_exact_tools_flags_owners_and_handler_convention(self):
        names = [tool.name for tool in lineage_ops.TOOLS]
        self.assertEqual(sorted(names), sorted(ARGS))
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(dict(lineage_ops.VALIDATORS), {})
        self.assertEqual(set(lineage_ops.FOLDS), {"tree"})
        for spec in lineage_ops.TOOLS:
            self.assertIsInstance(spec, ToolSpec)
            self.assertIs(spec.mutating, spec.name != "lineage_tree")
            self.assertEqual(inspect.signature(spec.handler).parameters["context"].kind,
                             inspect.Parameter.KEYWORD_ONLY)
            self.assertIs(self.registry.tools[spec.name].handler, spec.handler)
        self.registry.tools["lineage_tree"].handler({}, context=self.ctx)
        self.require_owners()

    def test_a01_loaded_registry_is_immutable_and_import_has_no_registration_side_effect(self):
        self.registry.tools["lineage_tree"].handler({}, context=self.ctx)
        before = set(self.registry.tools)
        with self.assertRaises(TypeError):
            self.registry.tools["invented_tool"] = self.registry.tools["lineage_tree"]
        self.assertEqual(set(load().tools), before)

    def test_a02_discovery_schemas_are_closed_and_required_fields_exact(self):
        expected_required = {"agent_clone": {"parent_id", "child_id", "agent", "op_id"},
                             "agent_distill": {"parent_id", "child_id", "agent", "op_id"},
                             "agent_retire": {"agent_id", "reason", "agent", "op_id"}, "lineage_tree": set()}
        allowed = {"agent_clone": {"parent_id", "child_id", "display_name", "agent", "op_id", "expected_head"},
                   "agent_distill": {"parent_id", "child_id", "display_name", "unit_ids", "agent", "op_id", "expected_head"},
                   "agent_retire": {"agent_id", "reason", "agent", "op_id", "expected_head"},
                   "lineage_tree": {"root_id", "include_retired", "agent"}}
        for name, args in ARGS.items():
            schema = self.registry.tools[name].input_schema
            self.assertIs(schema["additionalProperties"], False)
            self.assertEqual(set(schema["required"]), expected_required[name])
            self.assertEqual(set(schema["properties"]), allowed[name])
            validate(args, schema)

    def test_a02_valid_read_defaults_produce_one_untrusted_wrapper(self):
        self.registry.tools["lineage_tree"].handler({}, context=self.ctx)
        result = self.public_call("lineage_tree", {})
        explicit = self.public_call("lineage_tree", {"agent": "system", "include_retired": True})
        self.assertEqual(result, {"untrusted": {"nodes": [], "head": 0}})
        self.assertEqual(result, explicit)

    def test_a02_operator_argument_cannot_confer_ruling_authority(self):
        self.seed(self.parent, units=[self.unit(kind="ruling"), self.unit("unit0002")])
        args = dict(ARGS["agent_clone"], agent="operator")
        data = self.registry.tools["agent_clone"].handler(args, context=self.ctx)
        result = self.public_call("agent_clone", args)
        self.assertEqual(set(result), {"untrusted"})
        self.assertEqual(result["untrusted"], data)
        self.assertEqual(result["untrusted"]["rejected_units"][0]["reason"], "level_one")
        for wrapper in result["untrusted"]["inherited_units"]:
            self.assertEqual(wrapper["unit"]["level"], 2)

    def test_a02_arbitrary_creator_is_not_forced_to_equal_parent(self):
        self.seed(self.parent, units=[self.unit()])
        args = dict(ARGS["agent_clone"], agent="other-creator")
        self.registry.tools["agent_clone"].handler(args, context=self.ctx)
        result = self.public_call("agent_clone", args)
        self.assertEqual(set(result), {"untrusted"})
        self.assertEqual(result["untrusted"]["record"]["agent_id"], "child-one")

    def test_a23_retire_does_not_offer_arbitrary_status_or_gate_fields(self):
        before = self.ledger_bytes()
        for field in ("to", "status", "record", "gate", "bench_id", "promoted_seat"):
            result = self.public_call("agent_retire", {**ARGS["agent_retire"], field: "promoted"})
            self.assertEqual(result["code"], "bad_args")
            self.assertEqual(self.ledger_bytes(), before)

    def test_a31_real_shared_dispatch_matches_inner_handler_and_replay(self):
        self.seed(self.parent, units=[self.unit()])
        args = deepcopy(ARGS["agent_clone"])
        inner = self.registry.tools["agent_clone"].handler(args, context=self.ctx)
        result = dispatch("agent_clone", args, context=self.ctx, registry=self.registry)
        self.assertEqual(result.payload, {"untrusted": inner})
        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("untrusted", inner)
        self.assertEqual(self.public_call("agent_clone", args), result.payload)

    def test_a31_handler_failures_have_sanitized_domain_text(self):
        # A-U17: installed domain handlers raise; dispatch returns the error envelope.
        self.refused("no_agent", lambda: self.registry.tools["agent_clone"].handler(
            ARGS["agent_clone"], context=self.ctx))
        result = self.public_call("agent_clone", ARGS["agent_clone"])
        self.assertIs(result["ok"], False)
        self.assertEqual(result["code"], "no_agent")
        self.assertLessEqual(set(result), {"ok", "code", "detail"})
        if "detail" in result:
            self.assertIsInstance(result["detail"], str)
            self.assertLessEqual(len(result["detail"]), 2048)
            self.assertNotIn(str(self.base), result["detail"])


def _invalid_case(tool, changes, missing=None):
    def test(self):
        args = deepcopy(ARGS[tool])
        args.update(changes)
        if missing is not None:
            args.pop(missing)
        before = self.ledger_bytes()
        result = self.public_call(tool, args)
        self.assertIs(result["ok"], False)
        self.assertEqual(result["code"], "bad_args")
        self.assertEqual(self.ledger_bytes(), before)
    test.__doc__ = "Gate: strict shared argument refusal with no append; contrast: ignored/normalized input."
    return test


for label, tool, changes, missing in (
    ("missing_actor", "agent_clone", {}, "agent"),
    ("missing_op_id", "agent_clone", {}, "op_id"),
    ("null_display_name", "agent_clone", {"display_name": None}, None),
    ("null_selection", "agent_distill", {"unit_ids": None}, None),
    ("null_expected_head", "agent_clone", {"expected_head": None}, None),
    ("boolean_head", "agent_clone", {"expected_head": True}, None),
    ("unsafe_integer_head", "agent_clone", {"expected_head": 9007199254740992}, None),
    ("negative_head", "agent_clone", {"expected_head": -1}, None),
    ("malformed_child", "agent_clone", {"child_id": "../child"}, None),
    ("child_newline", "agent_clone", {"child_id": "child-one\n"}, None),
    ("short_child", "agent_clone", {"child_id": "ab"}, None),
    ("long_child", "agent_clone", {"child_id": "a" * 65}, None),
    ("empty_display_name", "agent_clone", {"display_name": ""}, None),
    ("long_display_name", "agent_clone", {"display_name": "é" * 129}, None),
    ("null_root", "lineage_tree", {"root_id": None}, None),
    ("null_retirement_filter", "lineage_tree", {"include_retired": None}, None),
    ("integer_retirement_filter", "lineage_tree", {"include_retired": 1}, None),
    ("duplicate_selection", "agent_distill", {"unit_ids": ["unit0001", "unit0001"]}, None),
    ("oversize_selection", "agent_distill", {"unit_ids": [f"unit{i:05d}" for i in range(257)]}, None),
    ("nested_selection_record", "agent_distill", {"unit_ids": [{"id": "unit0001"}]}, None),
    ("client_record", "agent_clone", {"record": {"status": "promoted"}}, None),
    ("client_inherited", "agent_clone", {"inherited_units": []}, None),
    ("client_hash", "agent_clone", {"sha256": "0" * 64}, None),
    ("client_status", "agent_clone", {"status": "promoted"}, None),
    ("client_gate", "agent_clone", {"gate": {"passed": True}}, None),
):
    setattr(ExtensionOracle, "test_a02_rejects_" + label, _invalid_case(tool, changes, missing))


def _raw_case(raw):
    def test(self):
        before = self.ledger_bytes()
        with self.assertRaises(SchemaError):
            strict_loads(raw)
        self.assertEqual(self.ledger_bytes(), before)
    test.__doc__ = "Gate: installed strict decoder; contrast: ambiguous/non-JSON input."
    return test
for label, raw in (("duplicate_keys", b'{"child_id":"one","child_id":"two"}'),
                   ("nested_duplicate_keys", b'{"x":{"a":1,"a":2}}'),
                   ("nonfinite", b'{"x":NaN}'), ("overflow_float", b'{"x":1e999}'),
                   ("invalid_utf8", b'"\xff"'), ("unpaired_surrogate", b'"\\ud800"')):
    setattr(ExtensionOracle, "test_a02_strict_json_" + label, _raw_case(raw))


class TransportOracle(OracleCase):
    def test_a31_cli_replay_uses_real_cli_and_original_commit(self):
        """Gate: installed CLI exit/JSON lane; contrast: transport-local birth."""
        import io
        from lineage.core import cli
        self.seed(self.parent, units=[self.unit()])
        expected = self.breed()
        stdout, stderr = io.StringIO(), io.StringIO()
        status = cli.main(["--home", str(self.home), "call", "agent_clone", "--json",
                           canonical(ARGS["agent_clone"]).decode()],
                          stdin=io.BytesIO(), stdout=stdout, stderr=stderr,
                          registry=self.registry)
        self.assertEqual(status, 0)
        self.assertEqual(strict_loads(stdout.getvalue()), {"untrusted": expected})
        self.assertEqual(stderr.getvalue(), "")

    def test_a31_mcp_replay_is_single_wrapped_data_with_iserror_false(self):
        import io
        from lineage.core import mcp
        self.seed(self.parent, units=[self.unit()])
        expected = self.breed()
        request = {"jsonrpc": "2.0", "id": "fixture-request", "method": "tools/call",
                   "params": {"name": "agent_clone", "arguments": ARGS["agent_clone"]}}
        stdout, stderr = io.StringIO(), io.StringIO()
        status = mcp.main(context=self.ctx, registry=self.registry,
                          stdin=io.BytesIO(canonical(request) + b"\n"),
                          stdout=stdout, stderr=stderr)
        self.assertEqual(status, 0)
        result = strict_loads(stdout.getvalue())["result"]
        self.assertIs(result["isError"], False)
        self.assertEqual(len(result["content"]), 1)
        self.assertEqual(strict_loads(result["content"][0]["text"]), {"untrusted": expected})

    def test_a31_mcp_domain_refusal_is_rpc_result_with_iserror_true(self):
        import io
        from lineage.core import mcp
        self.refused("no_agent", lambda: self.breed())
        request = {"jsonrpc": "2.0", "id": "fixture-request", "method": "tools/call",
                   "params": {"name": "agent_clone", "arguments": ARGS["agent_clone"]}}
        stdout = io.StringIO()
        mcp.main(context=self.ctx, registry=self.registry,
                 stdin=io.BytesIO(canonical(request) + b"\n"),
                 stdout=stdout, stderr=io.StringIO())
        response = strict_loads(stdout.getvalue())
        self.assertNotIn("error", response)
        self.assertIs(response["result"]["isError"], True)
        self.assertEqual(strict_loads(response["result"]["content"][0]["text"])["code"], "no_agent")

    def test_a31_cli_domain_refusal_keeps_exit_three(self):
        import io
        from lineage.core import cli
        self.refused("no_agent", lambda: self.breed())
        stdout = io.StringIO()
        status = cli.main(["--home", str(self.home), "call", "agent_clone", "--json",
                           canonical(ARGS["agent_clone"]).decode()], stdin=io.BytesIO(),
                          stdout=stdout, stderr=io.StringIO(), registry=self.registry)
        self.assertEqual(status, 3)
        self.assertEqual(strict_loads(stdout.getvalue())["code"], "no_agent")


def _duplicate_registry_case(kind):
    def test(self):
        """Gate: real atomic registry duplicate refusal; contrast: last-owner-wins."""
        import types
        from unittest.mock import patch
        from lineage.core import registry as registry_module
        package = types.ModuleType("fixture_extensions")
        package.__path__ = []
        modules = []
        for name in ("fixture_extensions.first", "fixture_extensions.second"):
            module = types.ModuleType(name)
            module.TOOLS = lineage_ops.TOOLS if kind == "tool" else ()
            module.VALIDATORS = {"agent.born": lambda history, event: None} if kind == "validator" else {}
            module.FOLDS = dict(lineage_ops.FOLDS) if kind == "fold" else {}
            modules.append(module)
        values = {package.__name__: package, **{m.__name__: m for m in modules}}
        entries = [types.SimpleNamespace(name=m.__name__, ispkg=False) for m in modules]
        original_import = registry_module.importlib.import_module
        def resolve(name):
            return values[name] if name in values else original_import(name)
        with patch.object(registry_module.importlib, "import_module", side_effect=resolve), \
             patch.object(registry_module.pkgutil, "iter_modules", return_value=entries):
            with self.assertRaises(registry_module.RegistryError) as caught:
                registry_module.load(package=package.__name__)
        self.assertEqual(caught.exception.detail["reason"], "duplicate_" + kind)
    return test
for _kind in ("tool", "validator", "fold"):
    setattr(ExtensionOracle, "test_a01_duplicate_" + _kind + "_blocks_load", _duplicate_registry_case(_kind))
