"""Actual U04 descriptors, carriers, single wrapping and safe diagnostics."""
from copy import deepcopy
import inspect
import io
import json
import re
import sys
from unittest import mock
from lineage.core import app, cli, journal, mcp, registry
from lineage.core.errors import LineageError
from . import (ROOT, OracleCase, agents, brief, canonical, extension, record, version)


class ExtensionTests(OracleCase):
    def test_a01_registry_inventory_exact_schemas_and_callback_ownership(self):
        self.handler("agent_list", {})
        loaded = registry.load()
        self.assertEqual(set(t.name for t in extension.TOOLS), {"agent_create", "agent_get", "agent_list", "agent_brief"})
        self.assertEqual(set(extension.VALIDATORS), {"agent.born", "agent.status"})
        self.assertEqual(set(extension.FOLDS), {"agents"})
        self.assertEqual(len(extension.TOOLS), 4)
        contract = (ROOT / "docs/CONTRACT.md").read_text()
        for spec in extension.TOOLS:
            section = contract.split("### `" + spec.name + "`", 1)[1].split("### ", 1)[0]
            expected = json.loads(re.search(r"```json\s*(.*?)```", section, re.S).group(1))
            self.assertEqual(spec.input_schema, expected)
            self.assertEqual(spec.mutating, spec.name == "agent_create")
            self.assertIs(loaded.tools[spec.name].handler, spec.handler)
        self.assertNotIn("set_status", loaded.tools)

    def test_a01_exact_domain_signatures_and_amended_rule_ids(self):
        self.invoke(version.agent_version, "a" * 64, [], 0)
        self.assertEqual(tuple(inspect.signature(agents.create).parameters),
                         ("agent_id", "display_name", "workflow", "language", "allowed_seats",
                          "references", "skills", "overlays", "command", "ctx"))
        for function in (agents.get, agents.list_agents, agents.materialize, brief.get):
            self.assertEqual(inspect.signature(function).parameters["ctx"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(tuple(inspect.signature(brief.build).parameters), ("agent", "units", "rule_ids", "memory_arm"))
        self.assertEqual(inspect.signature(brief.build).parameters["rule_ids"].kind, inspect.Parameter.KEYWORD_ONLY)

    def test_a41_dispatch_cli_and_mcp_query_data_match(self):
        expected = self.handler("agent_list", {})
        result = app.dispatch("agent_list", {}, context=self.ctx, registry=self.reg)
        self.assertEqual(result.payload, {"untrusted": expected})
        self.assertEqual(result.exit_code, 0)
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(["--home", str(self.home), "call", "agent_list", "--json", "{}"],
                        registry=self.reg, stdin=io.BytesIO(), stdout=out, stderr=err)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue()), result.payload)
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "agent_list", "arguments": {}}}
        rpc_out, rpc_err = io.StringIO(), io.StringIO()
        self.assertEqual(mcp.main(context=self.ctx, registry=self.reg,
                         stdin=io.BytesIO(canonical(request) + b"\n"), stdout=rpc_out, stderr=rpc_err), 0)
        reply = json.loads(rpc_out.getvalue())
        self.assertIs(reply["result"]["isError"], False)
        self.assertEqual(json.loads(reply["result"]["content"][0]["text"]), result.payload)

    def test_a41_descriptor_discovery_matches_actual_cli_and_mcp(self):
        self.handler("agent_list", {})
        expected = app.list_tools(registry=self.reg)
        out = io.StringIO()
        code = cli.main(["--home", str(self.home), "tools"], registry=self.reg,
                        stdout=out, stderr=io.StringIO(), stdin=io.BytesIO())
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue()), {"tools": expected})
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        out = io.StringIO()
        mcp.main(context=self.ctx, registry=self.reg, stdin=io.BytesIO(canonical(request) + b"\n"),
                 stdout=out, stderr=io.StringIO())
        self.assertEqual(json.loads(out.getvalue())["result"], {"tools": expected})

    def test_a41_json_lane_parity_requires_real_adapter(self):
        self.handler("agent_list", {})
        lane = self.require_peer("lineage.core.jsonlane")
        config = {"endpoint": "fixture-target", "sources": ["fixture-source"], "tools": ["agent_list"]}
        # A-U12: lane.dispatch checks the explicit private disk configuration.
        self.configure_lane(config)
        envelope = {"schema": "lineage.family/1", "id": "request1", "source": "fixture-source",
                    "target": "fixture-target", "kind": "call", "agent": "system",
                    "payload": {"tool": "agent_list", "args": {}}}
        expected = app.dispatch("agent_list", {}, context=self.ctx, registry=self.reg).payload
        self.assertEqual(lane.dispatch(envelope, config, ctx=self.ctx), expected)
        # HTTP is a separate integrated acceptance gate: no network is opened by
        # this oracle and this test does not assert an HTTP parity receipt.

    def test_a43_dependency_error_is_fixed_bounded_and_sanitized(self):
        self.handler("agent_list", {})
        private = str(self.root / "sensitive" / "secret.txt")
        with mock.patch.object(journal, "snapshot", side_effect=OSError(private + "x" * 4000)):
            result = app.dispatch("agent_list", {}, context=self.ctx, registry=self.reg)
        payload = result.payload
        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["code"], "internal")
        self.assertTrue(set(payload) <= {"ok", "code", "detail"})
        self.assertNotIn(str(self.root), canonical(payload).decode())
        self.assertNotIn("Traceback", canonical(payload).decode())
        if "detail" in payload:
            self.assertIs(type(payload["detail"]), str)
            self.assertGreater(len(payload["detail"]), 0)
            self.assertLessEqual(len(payload["detail"]), 2048)
        self.assertEqual(result.exit_code, 3)

    def test_a44_missing_compiler_refuses_without_birth(self):
        args = self.arguments()
        with mock.patch.dict(sys.modules, {"lineage.domain.constitution": None}):
            self.reject("internal", agents.create, **args, command=self.command(args), ctx=self.ctx)

    def test_a44_journal_owned_binding_uses_allocated_id(self):
        committed = self.create()
        event = self.assert_chain()[0]
        self.assertEqual(committed.value["record"]["born"]["event_id"], event["id"])
        self.assertEqual(event["payload"]["record"]["born"]["event_id"], event["id"])

    def test_a44_missing_journal_id_binding_fails_before_append(self):
        real_transact = journal.transact
        exercised = []
        def without_id(*args, **kwargs):
            callback = kwargs.get("prepare")
            if callback is not None:
                def prepare(history, draft):
                    exercised.append(True)
                    missing = deepcopy(draft)
                    missing.pop("id", None)
                    return callback(history, missing)
                kwargs["prepare"] = prepare
            return real_transact(*args, **kwargs)
        args = self.arguments()
        with mock.patch.object(journal, "transact", side_effect=without_id):
            self.reject("internal", agents.create, **args, command=self.command(args), ctx=self.ctx)
        self.assertTrue(exercised, "missing-binding negative control did not exercise preparation")

    def test_a26_operator_read_actor_does_not_mutate_or_gain_authority(self):
        expected = self.handler("agent_list", {})
        before = self.inventory()
        actual = app.dispatch("agent_list", {"agent": "operator"}, context=self.ctx, registry=self.reg)
        self.assertEqual(actual.payload, {"untrusted": expected})
        self.assertEqual(self.inventory(), before)
