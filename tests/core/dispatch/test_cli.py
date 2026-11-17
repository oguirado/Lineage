"""A7, A10, A12-A14: strict CLI grammar and lazy ownership seams."""
import importlib
from importlib.machinery import ModuleSpec
import io
import json
import sys
from types import ModuleType
from unittest import mock

from .support import BoundaryCase, GOOD, HOOKS, request

class FailingOutput:
    def write(self, text):
        raise OSError("SECRET_ORACLE")
    def flush(self):
        raise OSError("SECRET_ORACLE")

class CliTests(BoundaryCase):
    def test_a12_successful_machine_verbs_and_repeated_main_calls(self):
        registry = self.registry()
        for _ in range(2):
            self.assertEqual(self.cli_json(["tools"], registry), {"tools": self.app.list_tools(registry=registry)})
            self.assertEqual(self.cli_json(["call", "oracle_echo", "--json", json.dumps(GOOD)], registry), {"untrusted": GOOD})
            code, out, err = self.call_cli(["--home", str(self.home), "mcp"], registry, raw=json.dumps(request("ping")).encode() + b"\n")
            self.assertEqual((code, json.loads(out)), (0, {"jsonrpc": "2.0", "id": 1, "result": {}}))
        self.assertEqual(len(self.calls), 2)
        self.assert_no_home()

    def test_a12_usage_errors_are_structured_and_do_not_invoke_handler(self):
        registry = self.registry()
        cases = [
            ["call"], ["call", "oracle_echo"], ["call", "oracle_echo", "--json"],
            ["call", "oracle_echo", "--json", "{}", "--json", "{}"],
            ["call", "oracle_echo", "--json", "{}", "extra"],
            ["call", "oracle_echo", "--unknown", "{}"],
            ["tools", "extra"], ["tools", "--unknown"], ["mcp", "extra"],
            ["unknown"], ["read"], ["operator"], ["operator", "unknown"],
            ["--home", "one", "--home", "two", "tools"],
            ["--home"], ["--unknown", "tools"], ["tools", "--home", "later"],
        ]
        for argv in cases:
            with self.subTest(argv=argv):
                code, out, err = self.call_cli(argv, registry)
                self.assertEqual(code, 2)
                populated = [text for text in (out, err) if text]
                self.assertEqual(len(populated), 1, "usage emits exactly one structured error")
                self.assertTrue(populated[0].endswith("\n"))
                payload = json.loads(populated[0])
                self.assertEqual(payload["code"], "bad_args")
                self.assertIs(payload["ok"], False)
                self.assertLessEqual(set(payload), {"ok", "code", "detail"})
                self.assertNotIn("Traceback", populated[0])
        self.assertEqual(self.calls, [])
        self.assert_no_home()

    def test_a7_strict_json_rejections_before_handler(self):
        registry = self.registry()
        bad = ['[]', 'null', 'true', '1', '"text"', '{', '{}{}',
               '{"n":1,"n":2}', '{"n":1,"\\u006e":2}',
               '{"nested":{"message":"x","message":"y","cost":null},"n":1}',
               '{"nested":{"message":"\\ud800","cost":null},"n":1}',
               '{"nested":{"message":"x","cost":null},"n":NaN}',
               '{"nested":{"message":"x","cost":null},"n":Infinity}',
               '{"nested":{"message":"x","cost":null},"n":1e9999}']
        for raw in bad:
            with self.subTest(raw=raw):
                payload = self.cli_json(["call", "oracle_echo", "--json", raw], registry, expected=2)
                self.assertEqual((payload["ok"], payload["code"]), (False, "bad_args"))
        self.assertEqual(self.calls, [])
        self.assert_no_home()

    def test_a12_help_is_human_readable_and_does_not_import_delegates(self):
        registry = self.registry()
        original = importlib.import_module
        attempted = []
        def importer(name, package=None):
            if name in {row[1] for row in HOOKS}:
                attempted.append(name)
                raise AssertionError("help imported a later unit")
            return original(name, package)
        with mock.patch("importlib.import_module", side_effect=importer):
            for argv in (["--help"], ["-h"], ["tools", "--help"], ["call", "--help"], ["mcp", "--help"], *[[*row[0], "--help"] for row in HOOKS]):
                with self.subTest(argv=argv):
                    code, out, err = self.call_cli(argv, registry)
                    self.assertEqual(code, 0)
                    self.assertTrue(out.strip())
                    self.assertEqual(err, "")
                    self.assert_clean_identity(out)
        self.assertEqual(attempted, [])
        self.assertEqual(self.calls, [])
        self.assert_no_home()

    def test_a10_registry_chatter_is_confined_to_stderr(self):
        registry = self.registry()
        def noisy_load(*args, **kwargs):
            print("REGISTRY_CHATTER")
            return registry
        self.addCleanup(importlib.reload, self.cli)
        with mock.patch.object(self.reg, "load", side_effect=noisy_load):
            importlib.reload(self.cli)
            try:
                out, err = io.StringIO(), io.StringIO()
                code = self.cli.main(["--home", str(self.home), "tools"], stdout=out, stderr=err, stdin=io.BytesIO())
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(out.getvalue()), {"tools": self.app.list_tools(registry=registry)})
                self.assertIn("REGISTRY_CHATTER", err.getvalue())
                self.assertNotIn("REGISTRY_CHATTER", out.getvalue())
            finally:
                pass
        importlib.reload(self.cli)

    def test_a14_hooks_receive_unchanged_tail_context_registry_and_streams(self):
        registry = self.registry()
        for prefix, module_name, hook_name, tail in HOOKS:
            with self.subTest(command=prefix):
                module = ModuleType(module_name)
                module.__spec__ = ModuleSpec(module_name, loader=None)
                calls = []
                def delegate(argv, **kwargs):
                    calls.append((argv, kwargs))
                    kwargs["stdout"].write('{"delegate":true}\n')
                    return 0
                setattr(module, hook_name, delegate)
                original_import, original_find = importlib.import_module, importlib.util.find_spec
                def importer(name, package=None):
                    return module if name == module_name else original_import(name, package)
                def finder(name, package=None):
                    return module.__spec__ if name == module_name else original_find(name, package)
                stdin, out, err = io.BytesIO(b"passive"), io.StringIO(), io.StringIO()
                with mock.patch("importlib.import_module", side_effect=importer), mock.patch("importlib.util.find_spec", side_effect=finder):
                    code = self.cli.main(["--home", str(self.home), *prefix, *tail], stdin=stdin, stdout=out, stderr=err, registry=registry)
                self.assertEqual(code, 0)
                self.assertEqual(len(calls), 1)
                argv, kwargs = calls[0]
                self.assertEqual(list(argv), list(tail))
                self.assertEqual(set(kwargs), {"context", "registry", "stdin", "stdout", "stderr"})
                self.assertIs(kwargs["registry"], registry)
                self.assertIs(kwargs["stdin"], stdin)
                self.assertIs(kwargs["stdout"], out)
                self.assertIs(kwargs["stderr"], err)
                self.assertEqual(kwargs["context"].home, self.home.resolve())
                self.assertEqual(json.loads(out.getvalue()), {"delegate": True})
        self.assertEqual(self.calls, [])
        self.assert_no_home()

    def test_a14_missing_hooks_and_installed_broken_hooks_have_distinct_exits(self):
        registry = self.registry()
        for prefix, module_name, hook_name, tail in HOOKS:
            for mode in ("missing_module", "missing_hook", "broken_dependency", "raises", "bad_exit"):
                with self.subTest(command=prefix, mode=mode):
                    module = ModuleType(module_name)
                    module.__spec__ = ModuleSpec(module_name, loader=None)
                    def delegate(argv, **kwargs):
                        if mode == "raises":
                            raise OSError("SECRET_ORACLE")
                        return 4
                    if mode != "missing_hook":
                        setattr(module, hook_name, delegate)
                    original_import, original_find = importlib.import_module, importlib.util.find_spec
                    def importer(name, package=None):
                        if name == module_name:
                            if mode in ("missing_module", "broken_dependency"):
                                raise ModuleNotFoundError("SECRET_ORACLE", name=module_name if mode == "missing_module" else "missing_dependency")
                            return module
                        return original_import(name, package)
                    def finder(name, package=None):
                        if name == module_name:
                            return None if mode == "missing_module" else module.__spec__
                        return original_find(name, package)
                    expected = 2 if mode.startswith("missing_") else 3
                    with mock.patch("importlib.import_module", side_effect=importer), mock.patch("importlib.util.find_spec", side_effect=finder) as probe:
                        payload = self.cli_json([*prefix, *tail], registry, expected=expected)
                    self.assertEqual((payload["ok"], payload["code"]), (False, "bad_args" if expected == 2 else "internal"))
                    self.assertNotIn("SECRET_ORACLE", json.dumps(payload))
                    self.assertTrue(any(call.args and call.args[0] == module_name for call in probe.call_args_list), "Amendment B requires find_spec for missing-module detection")
        self.assert_no_home()

    def test_a14_builtin_verbs_never_import_lazy_hooks(self):
        registry = self.registry()
        original = importlib.import_module
        def importer(name, package=None):
            self.assertNotIn(name, {row[1] for row in HOOKS}, "builtin verb imported lazy hook")
            return original(name, package)
        with mock.patch("importlib.import_module", side_effect=importer):
            self.cli_json(["tools"], registry)
            self.cli_json(["call", "oracle_echo", "--json", json.dumps(GOOD)], registry)
            self.assertEqual(self.call_cli(["mcp"], registry)[0], 0)
        self.assertEqual(len(self.calls), 1)
        self.assert_no_home()


    def test_a5_empty_home_configuration_is_structured(self):
        registry = self.registry()
        code, out, err = self.call_cli(["--home", "", "tools"], registry)
        self.assertEqual(code, 2)
        populated = [text for text in (out, err) if text]
        self.assertEqual(len(populated), 1)
        self.assertEqual(json.loads(populated[0])["code"], "bad_args")
        self.assertEqual(self.calls, [])
        self.assert_no_home()

    def test_a14_registry_configuration_failure_is_not_success(self):
        registry = self.registry()
        self.addCleanup(importlib.reload, self.cli)
        with mock.patch.object(self.reg, "load", side_effect=self.reg.RegistryError("import_failed")):
            importlib.reload(self.cli)
            out, err = io.StringIO(), io.StringIO()
            code = self.cli.main(["--home", str(self.home), "tools"], stdin=io.BytesIO(), stdout=out, stderr=err)
        self.assertEqual(code, 2)
        text = out.getvalue() or err.getvalue()
        self.assertEqual(json.loads(text)["code"], "bad_args")
        self.assertEqual(self.calls, [])
        self.assert_no_home()

    def test_a19_broken_cli_output_is_execution_failure(self):
        registry = self.registry()
        self.assertEqual(self.cli.main(["tools"], stdin=io.BytesIO(), stdout=FailingOutput(), stderr=io.StringIO(), registry=registry), 3)
