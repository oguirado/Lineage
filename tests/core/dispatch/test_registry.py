"""A1-A4: deterministic registration, malformed plugins and detached discovery."""
import copy
import importlib
from pathlib import Path
import sys
import shutil
import unittest
from unittest import mock

from .support import BoundaryCase, GOOD, PREREQUISITES, ROOT, SCHEMA, missing_prerequisites

HEADER = '''from lineage.core.registry import ToolSpec

def handler(args, *, context):
    raise AssertionError("discovery invoked a handler")

def validator(history, event):
    raise AssertionError("discovery invoked a validator")

def fold(state, event):
    raise AssertionError("discovery invoked a fold")

spec = ToolSpec(name="alpha", description="Passive fixture.", input_schema={"type":"object","properties":{"n":{"type":"integer"}},"additionalProperties":False}, handler=handler, mutating=False)
TOOLS = (spec,)
VALIDATORS = {}
FOLDS = {}
'''

class PrerequisiteGate(unittest.TestCase):
    def test_a1_required_u01_u02_scaffolding(self):
        self.assertEqual(missing_prerequisites(), [],
                         "BLOCKED: U01/U02 prerequisites absent; behavioral fail-first evidence is not established")

class RegistryTests(BoundaryCase):
    def test_a1_imports_are_inert_without_domain_or_u03(self):
        script = '''import importlib, importlib.abc, io, json, sys
class NoDomainImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "lineage.core.errors" or fullname.startswith(("lineage.domain", "lineage.ext.")):
            raise AssertionError("transport import depends on a later domain unit")
sys.meta_path.insert(0, NoDomainImports())
from unittest import mock
class ForbiddenInput:
    def read(self, *args): raise AssertionError("import consumed stdin")
    def readline(self, *args): raise AssertionError("import consumed stdin")
    @property
    def buffer(self): return self
out, err = io.StringIO(), io.StringIO()
with mock.patch.object(sys, "stdin", ForbiddenInput()), mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
    for name in ("lineage.core.registry", "lineage.core.app", "lineage.core.mcp", "lineage.core.cli", "lineage.__main__", "lineage.ext"):
        importlib.import_module(name)
assert not out.getvalue() and not err.getvalue(), "import emitted output"
assert not any(name.startswith("_seed") for name in sys.modules)
print(json.dumps({"ok":True}))
'''
        completed = self.process([sys.executable, "-c", script])
        self.assertEqual(completed.returncode, 0, "imports must be inert and dependency-correct")
        self.assertEqual(completed.stdout, b'{"ok": true}\n')
        self.assertEqual(completed.stderr, b"")
        self.assert_no_home()

    def test_a2_sorted_discovery_including_underscore_and_new_module(self):
        modules = {}
        for module, name in (("z_last", "zeta"), ("a_first", "alpha"), ("_early", "early")):
            modules[module + ".py"] = (
                'import builtins\nbuiltins._lineage_oracle_order.append(__name__)\n'
                + HEADER.replace('name="alpha"', 'name=' + repr(name)))
        with mock.patch("builtins._lineage_oracle_order", [], create=True) as order:
            with self.package(modules) as package:
                one = self.reg.load(package=package)
                self.assertEqual(order, [package + "." + name for name in ("_early", "a_first", "z_last")])
                first = self.app.list_tools(registry=one)
                self.assertEqual([row["name"] for row in first], ["alpha", "early", "zeta"])
                two = self.reg.load(package=package)
                self.assertIsNot(one, two)
                self.assertEqual(self.app.list_tools(registry=two), first)
                (self.tmp / package / "b_added.py").write_text(HEADER.replace('name="alpha"', 'name="beta"'), encoding="utf-8")
                importlib.invalidate_caches()
                three = self.reg.load(package=package)
                self.assertEqual([row["name"] for row in self.app.list_tools(registry=three)], ["alpha", "beta", "early", "zeta"])
        self.assert_no_home()

    def test_a3_validator_and_fold_can_share_kind(self):
        with self.package({"valid.py": HEADER + 'VALIDATORS={"event.kind":validator}\nFOLDS={"event.kind":fold}\n'}) as package:
            result = self.reg.load(package=package)
            self.assertEqual(set(result.validators), {"event.kind"})
            self.assertEqual(set(result.folds), {"event.kind"})
        self.assert_no_home()


    def test_a3_absent_and_nonpackage_configuration_is_sanitized(self):
        for package in ("oracle_absent_package", "json.decoder"):
            with self.subTest(package=package):
                with self.assertRaises(self.reg.RegistryError) as caught:
                    self.reg.load(package=package)
                self.assertEqual(caught.exception.code, "bad_args")
                self.assertIn(caught.exception.detail["reason"], ("import_failed", "bad_extension"))
                self.assertNotIn(str(self.tmp), repr(caught.exception.detail))
        self.assert_no_home()

    def test_a4_descriptors_detached_sorted_and_read_only_snapshot(self):
        with self.package({"good.py": HEADER}) as package:
            registry = self.reg.load(package=package)
            expected = self.app.list_tools(registry=registry)
            rows = self.app.list_tools(registry=registry)
            self.assertEqual(set(rows[0]), {"name", "description", "inputSchema", "annotations"})
            rows[0]["inputSchema"]["properties"]["n"]["type"] = "string"
            rows.clear()
            self.assertEqual(self.app.list_tools(registry=registry), expected)
            module = importlib.import_module(package + ".good")
            module.spec.input_schema["properties"]["n"]["type"] = "string"
            self.assertEqual(self.app.list_tools(registry=registry), expected)
            for mapping in (registry.tools, registry.validators, registry.folds):
                with self.assertRaises(TypeError):
                    mapping["injected"] = object()
        self.assert_no_home()

    def test_a4_empty_and_populated_transport_parity(self):
        for modules in ({}, {"good.py": HEADER}):
            with self.subTest(empty=not modules), self.package(modules) as package:
                registry = self.reg.load(package=package)
                direct = self.app.list_tools(registry=registry)
                self.assertEqual(self.cli_json(["tools"], registry), {"tools": direct})
                self.assertEqual(self.rpc("tools/list", registry=registry)["result"], {"tools": direct})
                self.assertEqual(self.calls, [])
                self.assert_no_home()

    def assert_registry_rejects(self, modules, reason):
        with self.package(modules) as package:
            with self.assertRaises(self.reg.RegistryError) as caught:
                self.reg.load(package=package)
            error = caught.exception
            self.assertEqual(error.code, "bad_args")
            self.assertEqual(error.detail["reason"], reason)
            self.assertLessEqual(set(error.detail), {"reason", "name"})
            self.assertNotIn("SECRET_ORACLE", repr(error.detail))
            self.assertNotIn(str(self.tmp), repr(error.detail))
            # A failed build may not poison the next fresh load.
            for child in (self.tmp / package).iterdir():
                if child.name != "__init__.py":
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
            for key in list(sys.modules):
                if key.startswith(package + "."):
                    del sys.modules[key]
            importlib.invalidate_caches()
            fresh = self.reg.load(package=package)
            self.assertEqual(self.app.list_tools(registry=fresh), [])
        self.assert_no_home()

HOSTILE = {
    "equal_duplicate_tool": ({"a.py": HEADER + "TOOLS=(spec,spec)\n"}, "duplicate_tool"),
    "cross_module_duplicate_tool": ({"a.py": HEADER, "b.py": HEADER.replace("Passive fixture.", "Conflicting fixture.")}, "duplicate_tool"),
    "duplicate_validator": ({"a.py": HEADER + 'TOOLS=()\nVALIDATORS={"kind":validator}\n', "b.py": HEADER + 'TOOLS=()\nVALIDATORS={"kind":validator}\n'}, "duplicate_validator"),
    "duplicate_fold": ({"a.py": HEADER + 'TOOLS=()\nFOLDS={"kind":fold}\n', "b.py": HEADER + 'TOOLS=()\nFOLDS={"kind":fold}\n'}, "duplicate_fold"),
    "missing_export": ({"a.py": HEADER + "del VALIDATORS\n"}, "bad_extension"),
    "wrong_tools_container": ({"a.py": HEADER + "TOOLS=[spec]\n"}, "bad_extension"),
    "wrong_mapping": ({"a.py": HEADER + "FOLDS=[]\n"}, "bad_extension"),
    "not_toolspec": ({"a.py": HEADER + "TOOLS=({},)\n"}, "bad_descriptor"),
    "bad_name": ({"a.py": HEADER.replace('name="alpha"', 'name="Invalid-Name"')}, "bad_descriptor"),
    "empty_description": ({"a.py": HEADER.replace('description="Passive fixture."', 'description=""')}, "bad_descriptor"),
    "nonboolean_metadata": ({"a.py": HEADER.replace("mutating=False", "mutating=0")}, "bad_descriptor"),
    "uncallable_handler": ({"a.py": HEADER.replace("handler=handler", "handler=None")}, "bad_descriptor"),
    "uncallable_validator": ({"a.py": HEADER + 'VALIDATORS={"kind":None}\n'}, "bad_extension"),
    "uncallable_fold": ({"a.py": HEADER + 'FOLDS={"kind":None}\n'}, "bad_extension"),
    "empty_event_key": ({"a.py": HEADER + 'VALIDATORS={"":validator}\n'}, "bad_extension"),
    "nonstring_event_key": ({"a.py": HEADER + 'FOLDS={1:fold}\n'}, "bad_extension"),
    "nested_package": ({"nested/__init__.py": ""}, "bad_extension"),
    "malformed_schema": ({"a.py": HEADER.replace('"type":"integer"', '"type":"invented"')}, "bad_schema"),
    "nonobject_root": ({"a.py": HEADER.replace('"type":"object"', '"type":"array"')}, "bad_schema"),
    "unsupported_optional_assertion": ({"a.py": HEADER.replace('"type":"integer"', '"type":"integer","inventedAssertion":True')}, "bad_schema"),
    "dependency_import_failure": ({"a.py": HEADER, "z.py": 'raise ModuleNotFoundError("SECRET_ORACLE")\n'}, "import_failed"),
}


def hostile_test(modules, reason):
    def test(self):
        self.assert_registry_rejects(modules, reason)
    return test

for label, (modules, reason) in HOSTILE.items():
    setattr(RegistryTests, "test_a3_reject_" + label, hostile_test(modules, reason))
