"""Closed discovery, shared dispatch and hostile caller assertions."""
from copy import deepcopy
import json
import re
import tempfile
import unittest

from lineage.core import app, schema as boundary  # A-U19: resolve exceptions after integrated boundary reloads.
from lineage.core.registry import Registry, load
from lineage.core.schema import strict_loads, validate
from lineage.ext import promotion as extension
from tests.promotion.test_evaluate import (CHILD, SELECT, PolicyCase,
                                         REPO_ROOT, TEST_ROOT)

ARGS = {"agent_id": CHILD, "bench_id": SELECT, "agent": "creator-agent", "op_id": "promote_001"}


def contract_schema():
    text = (REPO_ROOT / "docs/CONTRACT.md").read_text(encoding="utf-8")
    section = text.split("### `agent_promote`", 1)[1]
    return json.loads(re.search(r"```json\s*(.*?)\s*```", section, re.S).group(1))


class DispatchTests(PolicyCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="runtime-", dir=TEST_ROOT)
        self.addCleanup(self.temp.cleanup)
        # No replacement validators: use only the real installed registry.
        self.registry = load()
        self.context = app.create_context(self.temp.name, registry=self.registry)

    def dispatch(self, args):
        return app.dispatch("agent_promote", args, context=self.context, registry=self.registry)

    def test_a1_exact_discovery_descriptor(self):
        self.assertEqual(len(extension.TOOLS), 1)
        spec = extension.TOOLS[0]
        self.assertEqual(spec.name, "agent_promote")
        self.assertIs(spec.mutating, True)
        self.assertEqual(spec.input_schema, contract_schema())
        self.assertEqual(extension.VALIDATORS, {})
        self.assertEqual(set(extension.FOLDS), {"promotion"})
        self.assertNotIn("set_status", self.registry.tools)

    def test_a1_creator_actor_does_not_need_to_equal_child(self):
        validate(ARGS, extension.TOOLS[0].input_schema)
        # Actual extension entry point must exist and process valid arguments.
        # A-U19: installed owners now exist; the creator reaches policy and its missing target diagnostic.
        from lineage.core.errors import LineageError
        with self.assertRaises(LineageError) as caught:
            self.invoke(extension.agent_promote, deepcopy(ARGS), context=self.context)
        self.assertEqual(caught.exception.code, "no_agent")

    def test_a1_success_is_not_a_successful_noop(self):
        result = self.dispatch(ARGS)
        self.assertEqual(result.payload.get("ok"), False)
        self.assertEqual(result.failure, "execution")
        self.assertEqual(result.exit_code, 3)
        self.assertNotIn("untrusted", result.payload)

    def test_a1_descriptor_copies_are_defensive(self):
        values = app.list_tools(registry=self.registry)
        next(x for x in values if x["name"] == "agent_promote")["inputSchema"]["required"].clear()
        again = app.list_tools(registry=self.registry)
        self.assertEqual(next(x for x in again if x["name"] == "agent_promote")["inputSchema"], contract_schema())

    def test_a1_strict_duplicate_json_keys(self):
        # A-U19: the integrated suite reloads schema; assert its current exact exception class.
        with self.assertRaises(boundary.SchemaError):
            strict_loads(b'{"agent_id":"candidate-agent","agent_id":"another-agent"}')

    def test_a1_invalid_utf8_and_unpaired_surrogate(self):
        # A-U19: the integrated suite reloads schema; assert its current exact exception class.
        for raw in (b'{"agent_id":"\xff"}', b'{"agent_id":"\\ud800"}'):
            with self.subTest(raw=raw), self.assertRaises(boundary.SchemaError):
                strict_loads(raw)

    def test_a1_tool_json_cap(self):
        # A-U19: the integrated suite reloads schema; assert its current exact exception class.
        with self.assertRaises(boundary.SchemaError):
            strict_loads(b'"' + b'x' * 1048576 + b'"')


def _bad_arguments(args):
    def test(self):
        before = tuple(self.context.home.rglob("events.jsonl"))
        result = self.dispatch(deepcopy(args))
        self.assertEqual(result.payload["code"], "bad_args")
        self.assertEqual(result.failure, "request")
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(tuple(self.context.home.rglob("events.jsonl")), before)
    return test


for _key in ARGS:
    _args = deepcopy(ARGS); _args.pop(_key)
    setattr(DispatchTests, "test_a1_missing_" + _key, _bad_arguments(_args))
for _key, _value in {
    "status": "promoted", "from": "draft", "to": "promoted", "seat": {},
    "gate": {"passed": True}, "authority": "operator", "agent_version": "a" * 64,
    "reward": 1, "clean_runs": 999, "verdict": "superior", "unknown": None,
}.items():
    setattr(DispatchTests, "test_a1_rejects_injected_" + _key, _bad_arguments(dict(ARGS, **{_key: _value})))
for _label, _field, _value in [
    ("bad_agent_id", "agent_id", "A"), ("short_bench_id", "bench_id", "short"),
    ("bad_actor", "agent", "../actor"), ("bad_op_id", "op_id", "space op"),
    ("boolean_expected_head", "expected_head", True),
    ("negative_expected_head", "expected_head", -1),
    ("unsafe_expected_head", "expected_head", 9007199254740992),
    ("null_expected_head", "expected_head", None),
]:
    setattr(DispatchTests, "test_a1_" + _label, _bad_arguments(dict(ARGS, **{_field: _value})))
for _actor in ("operator", "system"):
    setattr(DispatchTests, "test_a1_" + _actor + "_cannot_inject_authority",
            _bad_arguments(dict(ARGS, agent=_actor, authority="operator")))
