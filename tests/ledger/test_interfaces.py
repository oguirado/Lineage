"""Independent discovery oracles; domain integration is explicitly gated."""
from dataclasses import fields, is_dataclass
import inspect

from lineage.core import app, errors, journal, registry
from tests.ledger._support import DiscoveryCase, LEDGER_TOOLS, ROOT


class LedgerDiscoveryOracle(DiscoveryCase):
    def test_a2_a28_ledger_events_is_discoverable(self):
        self.require_tool("ledger_events")

    def test_a2_a28_ledger_export_is_discoverable(self):
        self.require_tool("ledger_export")

    def test_a2_a28_ledger_verify_is_discoverable(self):
        self.require_tool("ledger_verify")

    def test_a2_a28_scorecard_get_is_discoverable(self):
        self.require_tool("scorecard_get")

    def test_a28_a29_cli_tools_is_the_public_descriptor_array(self):
        self.require_admitted_dependencies()
        payload = self.cli_discovery()
        self.assertTrue(
            isinstance(payload, list),
            "K0 CLI tools must return the descriptor array, without a tools wrapper")
        names = {descriptor["name"] for descriptor in payload}
        self.assertTrue(LEDGER_TOOLS <= names,
                        "CLI tools must discover every U14 tool")

    def test_a28_discovery_protocol_witness(self):
        # A successful protocol exchange distinguishes absent tools from a
        # broken test harness, missing module or malformed RPC request.
        self.mcp_discovery()

    def test_a30_discovery_does_not_initialize_runtime_state(self):
        self.assertEqual(list(self.home.iterdir()), [])
        self.mcp_discovery()
        self.cli_discovery()
        self.assertEqual(list(self.home.iterdir()), [])

    def test_a1_package_initializers_exist(self):
        for relative in ("tests/__init__.py", "tests/ledger/__init__.py",
                         "lineage/__init__.py", "lineage/core/__init__.py",
                         "lineage/domain/__init__.py"):
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).is_file(), relative)

    def require_admitted_dependencies(self):
        # A-U14: A-K0-9 admits actual U03/U04 APIs; assert them without K0 skips.
        for module, names in (
            (journal, ("snapshot", "verify")),
            (errors, ("LineageError",)),
            (registry, ("ToolSpec", "Registry")),
            (app, ("CallContext", "create_context", "dispatch")),
        ):
            for name in names:
                self.assertTrue(hasattr(module, name), module.__name__ + "." + name)
        self.assertTrue(issubclass(errors.LineageError, Exception))
        # A-U14: U03 takes home plus keyword-only timeout/witness, not ctx/projections.
        self.assertEqual(tuple(inspect.signature(journal.snapshot).parameters),
                         ("home", "lock_timeout_s"))
        self.assertEqual(tuple(inspect.signature(journal.verify).parameters),
                         ("home", "expected_head", "lock_timeout_s"))
        self.assertIs(inspect.signature(journal.verify)
                      .parameters["expected_head"].default, None)
        self.assertEqual(inspect.signature(journal.snapshot)
                         .parameters["home"].kind, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        self.assertEqual(inspect.signature(journal.verify)
                         .parameters["home"].kind, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        for function in (journal.snapshot, journal.verify):
            self.assertEqual(inspect.signature(function)
                             .parameters["lock_timeout_s"].kind,
                             inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(inspect.signature(journal.verify)
                         .parameters["expected_head"].kind, inspect.Parameter.KEYWORD_ONLY)
        # A-U14: U04 dispatch explicitly receives context and registry keyword-only.
        self.assertEqual(tuple(inspect.signature(app.dispatch).parameters),
                         ("name", "args", "context", "registry"))
        self.assertEqual(inspect.signature(app.dispatch)
                         .parameters["context"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(inspect.signature(app.dispatch)
                         .parameters["registry"].kind, inspect.Parameter.KEYWORD_ONLY)
        # A-U14: ToolSpec uses mutating; CallContext replaces K0 Context/Services.
        self.assertTrue(is_dataclass(registry.ToolSpec))
        self.assertEqual(tuple(field.name for field in fields(registry.ToolSpec)),
                         ("name", "description", "input_schema", "handler", "mutating"))
        self.assertTrue(is_dataclass(app.CallContext))
        self.assertEqual(tuple(field.name for field in fields(app.CallContext)),
                         ("home", "validators", "folds", "actor", "op_id"))

    def test_a31_admitted_dependencies_gate(self):
        self.require_admitted_dependencies()
