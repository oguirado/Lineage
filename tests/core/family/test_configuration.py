"""A4: explicit closed endpoint configurations, without inferred grants."""

import copy
from lineage.core import envelope
from tests.core.family import WireCase, config, wire


class ConfigurationTests(WireCase):
    def valid_config(self, value):
        try:
            return envelope.configuration(wire(value), value["endpoint"])
        except (envelope.InvalidEnvelope, NotImplementedError) as exc:
            self.fail("valid K0 configuration rejected: " + str(exc))

    def test_a4_configuration_matches(self):
        value = config()
        self.assertEqual(self.valid_config(value), value)

    def test_a4_configuration_defensive(self):
        raw = wire(config())
        first = self.valid_config(config())
        first["tools"].clear()
        self.assertEqual(self.valid_config(config()), config())


for label, updates in {
    "empty_sources": {"sources": []}, "empty_tools": {"tools": []},
    "uppercase_endpoint": {"endpoint": "UPPER"}, "digit_endpoint": {"endpoint": "7"},
}.items():
    def test(self, updates=updates):
        value = config(**updates)
        self.assertEqual(self.valid_config(value), value)
    setattr(ConfigurationTests, "test_a4_valid_" + label, test)

for label, updates in {
    "extra": {"extra": 1}, "legacy_rooms": {"rooms": ["main"]},
    "legacy_slice": {"slice": 1}, "source_string": {"sources": "Sender_1"},
    "source_null": {"sources": None}, "tool_string": {"tools": "skill_list"},
    "tool_null": {"tools": None}, "source_integer": {"sources": [1]},
    "tool_integer": {"tools": [1]}, "traversal": {"endpoint": "../bad"},
    "source_traversal": {"sources": ["../bad"]}, "unknown_tool": {"tools": ["unknown_tool"]},
}.items():
    def test(self, updates=updates):
        value = config(**updates)
        with self.assertRaises(envelope.InvalidEnvelope):
            envelope.configuration(wire(value), "Endpoint_1")
    setattr(ConfigurationTests, "test_a4_invalid_" + label, test)

for field in ("endpoint", "sources", "tools"):
    def test(self, field=field):
        value = config()
        del value[field]
        with self.assertRaises(envelope.InvalidEnvelope):
            envelope.configuration(wire(value), "Endpoint_1")
    setattr(ConfigurationTests, "test_a4_missing_" + field, test)

def mismatch(self):
    with self.assertRaises(envelope.InvalidEnvelope):
        envelope.configuration(wire(config()), "Other_1")
ConfigurationTests.test_a4_wrong_recipient = mismatch
