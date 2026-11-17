"""Frozen-contract gaps are measured refusals, never successful promotion."""
import inspect
from dataclasses import replace  # A-U19: detach the actual CallContext for missing-owner fixtures.
import json
import tempfile
import unittest

from lineage.core import app, journal, schema as boundary  # A-U19: current boundary exception identity.
from lineage.core.errors import LineageError
from lineage.core.registry import load
from lineage.core.schema import validate
from lineage.domain import promotion
from lineage.ext import promotion as extension
from tests.promotion.test_dispatch import ARGS
from tests.promotion.test_evaluate import (CHILD, SELECT, SEAT, Fixture,
    PolicyCase, REPO_ROOT, TEST_ROOT)


class ContractGapTests(PolicyCase):
    def test_a25_frozen_status_payload_cannot_record_complete_seat(self):
        # A-U19: A-K0-10 adds the closed seat; retain the legacy negative contrast explicitly.
        schema = json.loads((REPO_ROOT / "schemas/event.schema.json").read_text())
        payload_schema = next(rule["then"]["properties"]["payload"] for rule in schema["allOf"]
            if rule.get("if", {}).get("properties", {}).get("kind", {}).get("const") == "agent.status")
        payload = {"agent_id": CHILD, "from": "draft", "to": "shadow",
                   "reason": "synthetic qualification", "bench_id": SELECT}
        validate(payload, payload_schema)
        self.assertIn("seat", payload_schema["properties"])
        self.assertIs(payload_schema["additionalProperties"], False)
        validate(dict(payload, seat=SEAT), payload_schema)
        legacy = {**payload_schema, "properties": {key: value for key, value
                  in payload_schema["properties"].items() if key != "seat"}}
        with self.assertRaises(boundary.SchemaError):
            validate(dict(payload, seat=SEAT), legacy)
        with self.assertRaises(boundary.SchemaError):
            validate(dict(payload, seat=dict(SEAT, authority=True)), payload_schema)

    def test_a25_actual_public_opid_is_broader_than_integrated_journal(self):
        # Assert the PUBLIC boundary; do not depend on private journal constants.
        for op in ("x", "promotion:child/selection.1", "p" * 128):
            with self.subTest(op=op):
                validate(dict(ARGS, op_id=op), extension.TOOLS[0].input_schema)

    def test_amendment_b2_optional_internal_seat_signature(self):
        signature = inspect.signature(promotion.promote)
        self.assertIsNone(signature.parameters["seat"].default)
        self.assertEqual(signature.parameters["seat"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(inspect.signature(promotion.evaluate).parameters["seat"].kind,
                         inspect.Parameter.KEYWORD_ONLY)

    def test_a25_missing_owner_seams_are_explicit_internal_and_no_append(self):
        # A-U19: installed owners now exist; explicitly remove the owner from this negative fixture.
        registry = load()
        with tempfile.TemporaryDirectory(prefix="runtime-", dir=TEST_ROOT) as home:
            context = app.create_context(home, registry=registry, actor=ARGS["agent"], op_id=ARGS["op_id"])
            context = replace(context, validators={key: value for key, value in context.validators.items()
                                                   if key != "agent.status"})
            before = journal.snapshot(home)
            with self.assertRaises(LineageError) as caught:
                self.invoke(promotion.promote, CHILD, SELECT,
                            command={"tool": "agent_promote", "args": dict(ARGS),
                                     "agent": ARGS["agent"], "op_id": ARGS["op_id"]}, ctx=context)
            self.assertEqual(caught.exception.code, "internal")
            self.assertEqual(journal.snapshot(home), before)
            # A-U19: native journal locking may create an empty ledger; refusal must append no bytes.
            ledger = context.home / "ledger/main/events.jsonl"
            self.assertFalse(ledger.read_bytes() if ledger.exists() else b"")

    def test_a25_seat_gate_preserves_missing_verdict_error_in_pure_policy(self):
        self.rejects(Fixture(), "no_benchmark")

    def test_a25_opid_gate_precedes_missing_agent_and_expected_head(self):
        # A-U19: A-JL1 removed the narrow OpId gate; a legal short id reaches locked expected_head.
        registry = load()
        with tempfile.TemporaryDirectory(prefix="runtime-", dir=TEST_ROOT) as home:
            context = app.create_context(home, registry=registry)
            args = dict(ARGS, op_id="x", expected_head=999)
            with self.assertRaises(LineageError) as caught:
                self.invoke(extension.agent_promote, args, context=context)
            self.assertEqual(caught.exception.code, "stale_rev")
            # A-U19: native journal locking may create an empty ledger; refusal must append no bytes.
            ledger = context.home / "ledger/main/events.jsonl"
            self.assertFalse(ledger.read_bytes() if ledger.exists() else b"")
            self.assertNotIn(home, str(caught.exception.detail))

    def test_a27_oracle_lists_every_numbered_acceptance(self):
        text = (TEST_ROOT / "ORACLE.md").read_text()
        for n in range(1, 29):
            self.assertRegex(text, rf"(?m)^\| A{n} \|")
        self.assertIn("BLOCKED/HOLD", text)
        self.assertIn("AUSENTE", text)
        self.assertNotIn("skipTest", text)
