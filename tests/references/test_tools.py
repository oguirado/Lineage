"""K0 public wire shapes take precedence under Amendment B.1."""
import io
import importlib
import json
import os
import re
import subprocess
import sys
from unittest import mock

from . import OracleCase, PUBLIC_IDS, ROOT, canonical, tree_state


class ToolOracle(OracleCase):
    def components(self):
        extension = self.module("lineage.ext.references")
        registry = self.module("lineage.core.registry")
        app = self.module("lineage.core.app")
        # A-U07: U02's import-isolation test reloads its exception class. Reimport
        # dependent fixtures against that live module before exercising U04.
        schema = self.module("lineage.core.schema")
        if registry.SchemaError is not schema.SchemaError:
            registry = importlib.reload(registry)
            app = importlib.reload(app)
            extension = importlib.reload(extension)
        loaded = self.invoke(self.function(registry, "load"))
        return extension, registry, app, loaded

    def context(self, registry, loaded, home, authority="tool"):
        # A-U07: U04 supplies create_context/CallContext; actor is trusted context,
        # while an optional argument agent remains passive attribution data.
        app = self.module("lineage.core.app")
        self.function(app, "create_context")
        self.function(app, "CallContext")
        return app.create_context(home, registry=loaded, actor="system")

    def contract_schema(self, name):
        text = self.required("docs/CONTRACT.md").read_text(encoding="utf-8")
        section = text.split("### `" + name + "`", 1)[1].split("\n### ", 1)[0]
        blocks = re.findall(r"```json\n(.*?)\n```", section, re.S)
        self.assertEqual(len(blocks), 2)
        return json.loads(blocks[0])

    def test_a01_u02_u04_prerequisites_are_real_not_replacement_stubs(self):
        schema = self.module("lineage.core.schema")
        # A-U07: U02 names its strict decoder strict_loads in the integrated API.
        self.function(schema, "strict_loads")
        self.function(schema, "validate")
        errors = self.module("lineage.core.errors")
        self.function(errors, "LineageError")
        # A-U07: U04 exposes the immutable tools mapping instead of names().
        _, _, _, registry = self.components()
        self.assertTrue(set(("reference_get", "reference_verify")) <= set(registry.tools))

    def test_a16_extension_discovery_exact_read_tool_descriptors(self):
        # A-U07: U04 descriptors come from app.list_tools(registry=...).
        extension, _, app, loaded = self.components()
        tools = getattr(extension, "TOOLS", None)
        self.assertIsInstance(tools, tuple)
        self.assertEqual({t.name for t in tools}, {"reference_get", "reference_verify"})
        self.assertEqual(len(tools), 2)
        descriptors = self.invoke(self.function(app, "list_tools"), registry=loaded)
        for spec in tools:
            self.assertEqual(spec.mutating, False)  # A-U07: U04 read effect is mutating=False.
            self.assertTrue(callable(spec.handler))
            descriptor = next(d for d in descriptors if d["name"] == spec.name)
            self.assertEqual(set(descriptor) - {"annotations"}, {"name", "description", "inputSchema"})  # A-OPC1: optional MCP annotations
            self.assertTrue(descriptor["description"])
            self.assertEqual(descriptor["inputSchema"], self.contract_schema(spec.name))

    def test_a16_handlers_return_raw_k0_shapes(self):
        extension = self.module("lineage.ext.references")
        for ref_id in PUBLIC_IDS:
            got = self.invoke(self.function(extension, "handle_reference_get"), {"ref_id": ref_id})
            self.assertEqual(set(got), {"reference"})
            self.assertEqual(set(got["reference"]), {"id", "sha256", "bytes", "rules"})
            self.assertEqual(got["reference"]["id"], ref_id)
            self.assertIs(type(got["reference"]["bytes"]), int)
            self.assertGreater(got["reference"]["bytes"], 0)
            for rule in got["reference"]["rules"]:
                self.assertEqual(set(rule), {"id", "section", "text"})
            verified = self.invoke(self.function(extension, "handle_reference_verify"), {"ref_id": ref_id})
            self.assertEqual(set(verified), {"ref_id", "sha256", "bytes", "valid"})
            self.assertIs(verified["valid"], True)
            self.assertEqual(verified["sha256"], got["reference"]["sha256"])

    def test_a16_dispatch_wraps_success_once_and_preserves_actor_restriction(self):
        _, registry, app, loaded = self.components()
        with self.temporary() as home:
            ctx = self.context(registry, loaded, home, authority="operator")
            before = tree_state(home)
            for name in ("reference_get", "reference_verify"):
                for actor in (None, "operator", "tester-agent"):
                    args = {"ref_id": "gold_s1"}
                    if actor is not None:
                        args["agent"] = actor
                    # A-U07: U04 dispatch requires context/registry and returns DispatchResult.
                    result = self.invoke(app.dispatch, name, args, context=ctx, registry=loaded).payload
                    self.assertEqual(set(result), {"untrusted"})
                    self.assertNotIn("untrusted", result["untrusted"])
            self.assertEqual(tree_state(home), before, "Actor strings cannot authorize a journal write")

    def test_a16_k0_rejects_extended_wire_expected_digest(self):
        self.bad_arguments({"ref_id": "gold_s1", "expected_sha256": "0" * 64}, "reference_verify")

    def bad_arguments(self, args, name="reference_get"):
        _, registry, app, loaded = self.components()
        with self.temporary() as home:
            ctx = self.context(registry, loaded, home)
            before = tree_state(home)
            # A-U07: Inspect the integrated DispatchResult payload with explicit registry plumbing.
            result = self.invoke(app.dispatch, name, args, context=ctx, registry=loaded).payload
            self.assertEqual(result.get("ok"), False)
            self.assertEqual(result.get("code"), "bad_args")
            self.assertNotIn("untrusted", result)
            self.assertEqual(tree_state(home), before)
            self.assertNotIn(str(home), json.dumps(result))

    def test_a16_cli_and_mcp_share_reference_boundary(self):
        self.required("lineage/__main__.py")
        self.required("lineage/core/mcp.py")
        with self.temporary() as home:
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            command = [sys.executable, "-B", "-m", "lineage", "--home", str(home),
                       "call", "reference_get", "--json", '{"ref_id":"gold_s1"}']
            result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, timeout=3)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(set(json.loads(result.stdout)), {"untrusted"})
            self.assertEqual(result.stderr, b"")
            request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "reference_verify", "arguments": {"ref_id": "gold_s1"}}}
            result = subprocess.run([sys.executable, "-B", "-m", "lineage", "--home", str(home), "mcp"],
                                    input=canonical(request) + b"\n", cwd=ROOT, env=environment,
                                    capture_output=True, timeout=1)
            self.assertEqual(result.returncode, 0)
            reply = json.loads(result.stdout)
            self.assertNotIn("error", reply)
            self.assertIs(reply["result"]["isError"], False)
            inner = json.loads(reply["result"]["content"][0]["text"])
            self.assertEqual(set(inner), {"untrusted"})


def _bad_test(args):
    def test(self):
        self.bad_arguments(args)
    return test


for _label, _args in (
    ("unknown_id", {"ref_id": "unknown"}), ("missing_id", {}),
    ("null_id", {"ref_id": None}), ("boolean_id", {"ref_id": True}),
    ("extra_field", {"ref_id": "gold_s1", "unexpected": 1}),
    ("root_selection", {"ref_id": "gold_s1", "repo_root": "."}),
    ("authority_selection", {"ref_id": "gold_s1", "authority": "operator"}),
    ("invalid_agent", {"ref_id": "gold_s1", "agent": "INVALID"}),
    ("short_agent", {"ref_id": "gold_s1", "agent": "ab"}),
    ("null_agent", {"ref_id": "gold_s1", "agent": None}),
    ("agent_newline", {"ref_id": "gold_s1", "agent": "tester\n"}),
    ("path_agent", {"ref_id": "gold_s1", "agent": "../tester"}),
):
    setattr(ToolOracle, "test_a16_bad_args_" + _label, _bad_test(_args))
