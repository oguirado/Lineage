# A-U01R: Discover the reconciled subset without hiding import or classification failures.
"""Run retained extraction assertions plus all U01R regression tests."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock


class RegressionSuite(unittest.TestSuite):
    def run(self, result, debug=False):
        popen = subprocess.Popen

        def without_bytecode(args, *positional, **keywords):
            if isinstance(args, (list, tuple)) and args and Path(str(args[0])).name.startswith("python"):
                args = [args[0], "-B", *args[1:]]
            return popen(args, *positional, **keywords)

        with mock.patch.object(subprocess, "Popen", side_effect=without_bytecode):
            return super().run(result, debug)


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def load_tests(loader, standard_tests, pattern):
    root = Path(__file__).resolve().parents[3]
    allowed = set(sys.stdlib_module_names) | {"lineage", "tests", "__future__"}
    for source in (root / "lineage").rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                names = [node.module]
            else:
                continue
            if any(name and name.split(".")[0] not in allowed for name in names):
                raise AssertionError("unexpected dependency in " + str(source.relative_to(root)))
    selection = json.loads((Path(__file__).parent / "fixtures/selection.json").read_text())
    import hashlib
    base = Path(__file__).parent
    decision = json.loads((base / "fixtures/reconciliation.json").read_text())
    if hashlib.sha256((base / "fixtures/selection.json").read_bytes()).hexdigest() != decision["selection_sha256"]:
        raise AssertionError("historical extraction selection changed")
    rows = decision["decisions"]
    modules = {row["module"] for row in rows}
    if len(modules) != len(rows) or modules != set(selection["modules"]):
        raise AssertionError("every historical module needs exactly one decision")
    ported = set()
    for row in rows:
        if row["decision"] == "PORT":
            ported.add(row["module"])
        elif row["decision"] == "RETIRE":
            if row["reason_class"] not in {"superseded-by-redesign", "legacy-feature-removed"}:
                raise AssertionError("invalid retirement class")
            if (root / row["path"]).exists():
                raise AssertionError("retired module remains discoverable: " + row["path"])
            if row["reason_class"] == "superseded-by-redesign" and not (root / row["replacement"]).is_dir():
                raise AssertionError("missing replacement test directory")
        else:
            raise AssertionError("unknown reconciliation decision")
    wanted = {identity for identity in selection["green_ids"]
              if any(identity.startswith(module + ".") for module in ported)}
    if len(set(selection["green_ids"])) != selection["green_before"]:
        raise AssertionError("frozen green candidate count changed")
    loaded = {}
    for module in sorted(ported):
        for test in flatten(loader.loadTestsFromName(module)):
            if isinstance(test, unittest.loader._FailedTest):
                raise AssertionError("regression module failed to import: " + module)
            if test.id() in wanted:
                loaded.setdefault(test.id(), test)
    if set(loaded) != wanted:
        raise AssertionError("selected retained tests disappeared: " + repr(sorted(wanted - loaded.keys())))
    # A-U01R: Every new test module is discovered; no additional selection filter.
    for source in sorted(base.rglob("test*.py")):
        module = ".".join(source.relative_to(root).with_suffix("").parts)
        if module in modules:
            continue
        for test in flatten(loader.loadTestsFromName(module)):
            if isinstance(test, unittest.loader._FailedTest):
                raise AssertionError("new regression module failed to import: " + module)
            if test.id() in loaded:
                raise AssertionError("duplicate regression test: " + test.id())
            loaded[test.id()] = test
    return RegressionSuite(loaded[identity] for identity in sorted(loaded))
