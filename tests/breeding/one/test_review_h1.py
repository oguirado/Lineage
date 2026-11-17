"""U17 pure admission regressions; these do not replace shared-owner gates."""
from copy import deepcopy
from hashlib import sha256
import ast
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lineage.core import journal
from lineage.core.errors import LineageError
from lineage.domain.breeding import _birth_payload, inherit, validate_birth
from .helpers import OracleCase, ROOT, TEST_ROOT, version
from . import test_inherit as frozen_inherit


class AdmissionRegression(OracleCase):
    def payload(self, *, op="clone", selected=None):
        return _birth_payload(
            journal.snapshot(self.home), parent_id="parent-one", child_id="child-one",
            op=op, display_name=None, selected_ids=selected,
            event_id="e-abcdef1234567890", ctx=self.ctx)

    def test_large_selection_refuses_before_brief_output_ceiling(self):
        """Gate: memory_debt before rendering; contrast: internal output overflow."""
        units = [self.unit(f"unit{i:05d}", statement="x" * 3400) for i in range(16)]
        self.seed(self.parent, units=units)
        self.refused("memory_debt", self.payload)
        self.assertFalse(any(p.name == "agent.json" for p in self.home.rglob("*")))

    def test_clone_preserves_effective_version_and_filters_source_history(self):
        """Gate: captured inputs and full audit; contrast: counter drift/private copy."""
        self.parent = self.seed(self.parent, units=[self.unit(), self.unit("unit0002", privacy="private")])
        before = self.ledger_bytes()
        payload = self.payload()
        record = payload["record"]
        self.assertEqual(self.parent["memory_gen"], 9)
        self.assertEqual(record["memory_gen"], self.parent["memory_gen"])
        self.assertEqual(record["agent_version"], self.parent["agent_version"])
        self.assertEqual([w["source_unit_id"] for w in payload["inherited_units"]], ["unit0001"])
        self.assertEqual(payload["rejected_units"], [
            {"agent_id": "parent-one", "unit_id": "unit0002", "reason": "private"}])
        self.assertEqual(self.ledger_bytes(), before)

    def test_distill_counter_uses_selected_child_units(self):
        """Gate: subset/empty counters; contrast: parent counter inheritance."""
        self.parent = self.seed(self.parent, units=[self.unit(), self.unit("unit0002", kind="negative")])
        for selected, count in ((["unit0002"], 1), ([], 0)):
            with self.subTest(selected=selected):
                payload = self.payload(op="distill", selected=selected)
                self.assertEqual(payload["record"]["memory_gen"], count)
                self.assertEqual(payload["record"]["agent_version"], version(payload["record"]))
                self.assertEqual(len(payload["inherited_units"]), count)
                self.assertEqual(len(payload["rejected_units"]), 2 - count)

    def test_invalid_reference_pin_refuses_source_integrity(self):
        """Gate: current bundled pins; contrast: well-shaped invented pin."""
        self.parent["references"][0]["sha256"] = "0" * 64
        self.seed(self.parent, units=[self.unit()])
        self.refused("hash_mismatch", self.payload)

    def test_invalid_constitution_hash_refuses_source_integrity(self):
        """Gate: committed constitution bytes; contrast: trusting its hash field."""
        self.parent["constitution_sha256"] = "0" * 64
        self.seed(self.parent, units=[self.unit()])
        self.refused("hash_mismatch", self.payload)

    def test_missing_skill_pin_refuses_source_integrity(self):
        """Gate: authoritative skill catalogue; contrast: client pin presence."""
        self.parent["skills"] = [{"skill_id": "missing-skill", "sha256": "0" * 64}]
        self.seed(self.parent, units=[self.unit()])
        self.refused("hash_mismatch", self.payload)

    def test_receipt_tamper_is_audited_with_other_unit_preserved(self):
        """Gate: fresh evidence; contrast: cached memory admission."""
        units = [self.unit(), self.unit("unit0002")]
        self.seed(self.parent, units=units)
        (self.home / units[0]["receipts"][0]["path"]).write_bytes(b"changed")
        payload = self.payload()
        self.assertEqual([w["source_unit_id"] for w in payload["inherited_units"]], ["unit0002"])
        self.assertEqual(payload["rejected_units"], [
            {"agent_id": "parent-one", "unit_id": "unit0001", "reason": "invalid_receipt"}])

    def test_pure_admission_rejects_forged_source_hash(self):
        """Gate: pure helper recomputation; shared-validator integration stays separate."""
        self.seed(self.parent, units=[self.unit()])
        payload = self.payload()
        event = {"id": payload["record"]["born"]["event_id"], "payload": deepcopy(payload)}
        validate_birth(journal.snapshot(self.home), event, ctx=self.ctx)
        event["payload"]["inherited_units"][0]["unit_sha256"] = "0" * 64
        self.refused("not_inheritable", lambda: validate_birth(
            journal.snapshot(self.home), event, ctx=self.ctx))

    def test_unequal_source_child_id_collision_is_conflict(self):
        """Gate: collision refusal; contrast: overwriting the first adopted unit."""
        selection = self.selection([self.unit(), self.unit("unit0002")])
        class Collision:
            def hexdigest(self):
                return "a" * 64
        with patch.object(inherit, "sha256", return_value=Collision()):
            self.refused("conflict", lambda: inherit._adopt(selection, "child-one"))

    def test_copied_central_filter_mutant_fails_frozen_private_oracle(self):
        """Gate: existing assertion failure; contrast: green/import-only mutant."""
        source = (ROOT / "lineage/domain/breeding/inherit.py").read_text()
        function = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name == "_rejection")
        lines = source.splitlines(keepends=True)
        lines[function.lineno - 1:function.end_lineno] = [
            "def _rejection(unit, *, workflow, language, selected, ctx):\n    return None\n"]
        mutated = "".join(lines)
        self.assertNotEqual(sha256(source.encode()).hexdigest(), sha256(mutated.encode()).hexdigest())
        ast.parse(mutated)
        with tempfile.TemporaryDirectory(prefix="filter-mutant-", dir=TEST_ROOT) as directory:
            path = Path(directory) / "inherit.py"
            path.write_text(mutated)
            name = "lineage.domain.breeding._review_filter_mutant"
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, {name: module}):
                spec.loader.exec_module(module)
                result = unittest.TestResult()
                with patch.object(inherit, "_rejection", module._rejection):
                    frozen_inherit.InheritanceOracle("test_a05_excludes_private").run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.failures), 1)
        self.assertIn("AssertionError", result.failures[0][1])
