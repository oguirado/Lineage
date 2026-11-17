# A-U01R: Guard complete retirement accounting, discovery, and the frozen files.
import hashlib
import json
from pathlib import Path
import unittest
from unittest import mock

from . import load_tests as _load_reconciled
from ._support import HERE, ROOT


class ReconciliationRegression(unittest.TestCase):
    def test_all_historical_modules_have_one_decision(self):
        selection = json.loads((HERE / "fixtures/selection.json").read_text())
        record = json.loads((HERE / "fixtures/reconciliation.json").read_text())
        rows = record["decisions"]
        self.assertEqual(len(rows), len(selection["modules"]))
        self.assertEqual({r["module"] for r in rows}, set(selection["modules"]))
        self.assertEqual(sum(r["selected_tests"] for r in rows), selection["green_before"])
        for row in rows:
            with self.subTest(module=row["module"]):
                self.assertEqual(row["selected_tests"], sum(t.startswith(row["module"] + ".") for t in selection["green_ids"]))
                if row["decision"] == "PORT":
                    self.assertTrue((ROOT / row["path"]).is_file())
                else:
                    self.assertEqual(row["decision"], "RETIRE")
                    self.assertFalse((ROOT / row["path"]).exists())
                    self.assertIn(row["reason_class"], {"superseded-by-redesign", "legacy-feature-removed"})
                    if row["replacement"]:
                        self.assertTrue(any((ROOT / row["replacement"]).rglob("test*.py")))

    def test_historical_selection_remains_byte_identical(self):
        record = json.loads((HERE / "fixtures/reconciliation.json").read_text())
        self.assertEqual(hashlib.sha256((HERE / "fixtures/selection.json").read_bytes()).hexdigest(), record["selection_sha256"])

    def test_missing_module_decision_fails_discovery(self):
        original = Path.read_text
        def altered(path, *args, **kwargs):
            text = original(path, *args, **kwargs)
            if path == HERE / "fixtures/reconciliation.json":
                value = json.loads(text)
                value["decisions"].pop()
                return json.dumps(value)
            return text
        with mock.patch.object(Path, "read_text", altered):
            with self.assertRaisesRegex(AssertionError, "every historical module"):
                _load_reconciled(unittest.TestLoader(), unittest.TestSuite(), None)

    def test_failed_import_is_not_silently_filtered(self):
        loader = unittest.TestLoader()
        failed = unittest.loader._FailedTest("broken_import", ImportError("injected import failure"))
        with mock.patch.object(loader, "loadTestsFromName", return_value=unittest.TestSuite([failed])):
            with self.assertRaisesRegex(AssertionError, "failed to import"):
                _load_reconciled(loader, unittest.TestSuite(), None)

    def test_frozen_manifest_is_exact_and_complete(self):
        actual = {}
        for line in (ROOT / "tests/core/REGRESSION_FROZEN.sha256").read_text().splitlines():
            digest, relative = line.split("  ", 1)
            self.assertNotIn(relative, actual)
            self.assertFalse(Path(relative).is_absolute())
            actual[relative] = digest
        paths = [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        paths.append(ROOT / "tests/core/DROPPED.md")
        expected = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        self.assertEqual(actual, expected)
