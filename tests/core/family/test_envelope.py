"""A1-A3/A7: independent strict-wire and identity oracles."""

import copy
import hashlib
import inspect
import json

from lineage.core import envelope
from tests.core.family import WireCase, request, wire


class EnvelopeTests(WireCase):
    def test_a1_validate_filename_is_optional(self):
        parameter = inspect.signature(envelope.validate).parameters["filename_id"]
        self.assertIs(parameter.default, None)
        value = request()
        self.assertEqual(envelope.validate(wire(value), value["target"]), value)

    def test_a2_capabilities(self):
        value = request()
        self.assertEqual(self.validate_request(value), value)

    def test_a2_call(self):
        value = request("call")
        self.assertEqual(self.validate_request(value), value)

    def test_a2_cursor_maximum(self):
        value = request("events.read", after=9007199254740991,
                        payload={"limit": 1000, "wait_ms": 30000,
                                 "agent_id": "alice", "kinds": ["run.open", "run.close"]})
        self.assertEqual(self.validate_request(value), value)

    def test_a2_exact_raw_byte_cap(self):
        value = request()
        raw = wire(value)
        padded = raw + b" " * (65536 - len(raw))
        self.assertEqual(len(padded), 65536)
        self.assertEqual(self.valid_raw(padded, value["target"], value["id"]), value)
        with self.assertRaises(envelope.InvalidEnvelope):
            envelope.validate(padded + b" ", value["target"], value["id"])

    def test_a2_decode_enforces_raw_cap(self):
        with self.assertRaises(envelope.InvalidEnvelope):
            envelope.decode(b"{}" + b" " * 65535)

    def test_a2_defensive_validation(self):
        value = request("call")
        raw = wire(value)
        first = self.valid_raw(raw, value["target"], value["id"])
        first["payload"]["args"]["include_retired"] = True
        self.assertEqual(self.valid_raw(raw, value["target"], value["id"]), value)

    def test_a3_wrong_target(self):
        with self.assertRaises(envelope.InvalidEnvelope):
            envelope.validate(wire(request()), "Other_1", "request01")

    def test_a3_filename_mismatch(self):
        with self.assertRaises(envelope.InvalidEnvelope):
            envelope.validate(wire(request()), "Endpoint_1", "request02")

    def test_a3_deep_json_has_protocol_error(self):
        # No exact depth is frozen. Never prescribe an arbitrary cutoff.
        raw = b'{"a":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}"
        try:
            value = envelope.decode(raw)
        except envelope.InvalidEnvelope:
            return
        self.assertIsInstance(value, dict)

    def test_a7_known_operation_vector(self):
        # A-U05 (orchestrator): K0 CONTRACT and SPEC_U05 fix the identity at lin- + first 44 hex; the frozen vector carried 46.
        self.assertEqual(envelope.operation_id(request()),
                         "lin-0173f5ca52e001e7cd08b6673dd0bdd66b279a42ff0c")

    def test_a7_known_digest_vector(self):
        self.assertEqual(envelope.digest(request()),
                         "ea5fa080a14bd44f256c98dfd57715cf25af1a6f681b83fb020ec3a147323f55")

    def test_a7_canonical_unicode_and_no_lf(self):
        self.assertEqual(envelope.canonical({"z": None, "a": "é"}),
                         b'{"a":"\xc3\xa9","z":null}')

    def test_a7_formatting_invariance(self):
        value = request()
        variant = json.dumps(dict(reversed(list(value.items()))), indent=2).encode() + b"\n"
        validated = self.valid_raw(variant, value["target"], value["id"])
        self.assertEqual(envelope.digest(validated), envelope.digest(value))
        self.assertEqual(envelope.operation_id(validated), envelope.operation_id(value))
        self.assertNotEqual(envelope.digest(value), hashlib.sha256(wire(value) + b"\n").hexdigest())


def add_case(name, function):
    function.__name__ = name
    setattr(EnvelopeTests, name, function)


for label, raw in {
    "duplicate_root": b'{"id":"request01","id":"request02"}',
    "duplicate_nested": b'{"a":{"b":1,"b":2}}',
    "duplicate_in_array": b'{"a":[{"b":1,"b":2}]}',
    "invalid_utf8": b'{"a":"\xff"}',
    "surrogate_high": b'{"a":"\\ud800"}',
    "surrogate_low": b'{"a":"\\udfff"}',
    "nan": b'{"a":NaN}',
    "positive_infinity": b'{"a":Infinity}',
    "negative_infinity": b'{"a":-Infinity}',
    "exponent_overflow": b'{"a":1e9999}',
    "integer_overflow": b'{"a":9007199254740992}',
    "negative_integer_overflow": b'{"a":-9007199254740992}',
    "trailing_object": b'{} {}',
    "trailing_text": b'{} trailing',
    "array": b'[]', "null": b'null', "true": b'true',
    "integer": b'123', "string": b'"text"', "empty": b'',
    "bom": b'\xef\xbb\xbf{}',
}.items():
    def test(self, raw=raw):
        with self.assertRaises(envelope.InvalidEnvelope):
            envelope.decode(raw)
    add_case("test_a3_decode_" + label, test)

for label, updates in {
    "uppercase": {"target": "X", "source": "A"},
    "digit_leading": {"target": "7", "source": "9Sender_1"},
    "endpoint_length": {"target": "A" * 64},
    "request_length": {"id": "R" * 64},
    "agent_length": {"agent": "a" * 64},
    "operator_actor": {"agent": "operator"},
    "system_actor": {"agent": "system"},
    "correlation_run": {"run_id": "run00001", "correlation_id": "corr0001"},
}.items():
    def test(self, updates=updates):
        value = request(**updates)
        self.assertEqual(self.validate_request(value), value)
    add_case("test_a2_valid_" + label, test)

for field in ("schema", "id", "source", "target", "kind", "agent", "payload"):
    def test(self, field=field):
        value = request()
        del value[field]
        with self.assertRaises(envelope.InvalidEnvelope):
            envelope.validate(wire(value), "Endpoint_1", "request01")
    add_case("test_a3_missing_" + field, test)

for label, updates in {
    "unknown_root": {"extra": 0}, "legacy_room": {"room": "main"},
    "legacy_generation": {"plan_opened": 1}, "reserved_id": {"id": "invalid0"},
    "short_id": {"id": "short"}, "long_id": {"id": "a" * 65},
    "id_newline": {"id": "request01\n"}, "wrong_schema": {"schema": "tasklight.family/1"},
    "endpoint_traversal": {"source": "../outside"}, "endpoint_space": {"source": "a b"},
    "endpoint_underscore_first": {"source": "_sender"}, "endpoint_long": {"source": "a" * 65},
    "actor_uppercase": {"agent": "Alice"}, "actor_short": {"agent": "ab"},
    "actor_underscore": {"agent": "alice_one"}, "actor_long": {"agent": "a" * 65},
    "invalid_run": {"run_id": "short"}, "null_run": {"run_id": None},
    "invalid_correlation": {"correlation_id": "bad"},
    "null_correlation": {"correlation_id": None},
    "unknown_kind": {"kind": "unknown"}, "legacy_lifecycle": {"kind": "agent.alive"},
    "legacy_plan": {"kind": "agent.plan"}, "legacy_activity": {"kind": "agent.activity"},
    "capabilities_after": {"after": 0}, "capabilities_payload": {"payload": {"extra": 1}},
    "payload_array": {"payload": []}, "payload_null": {"payload": None},
}.items():
    def test(self, updates=updates):
        value = request(**updates)
        with self.assertRaises(envelope.InvalidEnvelope):
            envelope.validate(wire(value), "Endpoint_1", value.get("id", "request01"))
    add_case("test_a3_invalid_" + label, test)

for label, payload in {
    "limit_bool": {"limit": True}, "limit_zero": {"limit": 0},
    "limit_large": {"limit": 1001}, "wait_negative": {"wait_ms": -1},
    "wait_large": {"wait_ms": 30001}, "wait_bool": {"wait_ms": False},
    "filter_extra": {"extra": 0}, "legacy_acts": {"acts": []},
    "duplicate_kind": {"kinds": ["run.open", "run.open"]},
    "unknown_kind": {"kinds": ["not.an.event"]},
    "invalid_agent": {"agent_id": "A"},
}.items():
    def test(self, payload=payload):
        with self.assertRaises(envelope.InvalidEnvelope):
            self.validate_request(request("events.read", payload=payload))
    add_case("test_a3_cursor_" + label, test)

for label, after in {"boolean": True, "negative": -1, "overflow": 9007199254740992,
                     "null": None, "float": 1.5}.items():
    def test(self, after=after):
        with self.assertRaises(envelope.InvalidEnvelope):
            self.validate_request(request("events.read", after=after))
    add_case("test_a3_after_" + label, test)

def test_missing_cursor(self):
    value = request("events.read")
    del value["after"]
    with self.assertRaises(envelope.InvalidEnvelope):
        self.validate_request(value)
add_case("test_a3_missing_cursor", test_missing_cursor)

for label, updates in {
    "after": {"after": 0},
    "unknown_payload": {"payload": {"tool": "skill_list", "args": {}, "extra": 1}},
    "unknown_tool": {"payload": {"tool": "no_such_tool", "args": {}}},
    "unknown_args": {"payload": {"tool": "skill_list", "args": {"extra": 1}}},
    "args_agent": {"payload": {"tool": "skill_list", "args": {"agent": "alice"}}},
    "args_op_id": {"payload": {"tool": "skill_list", "args": {"op_id": "op01"}}},
    "nested_extra": {"payload": {"tool": "skill_publish", "args": {"skill_id": "sample",
        "files": [{"path": "SKILL.md", "content": "text", "extra": 1}]}}},
}.items():
    def test(self, updates=updates):
        with self.assertRaises(envelope.InvalidEnvelope):
            self.validate_request(request("call", **updates))
    add_case("test_a3_call_" + label, test)

for field, value in {"source": "Sender_2", "target": "Other_1", "id": "request02"}.items():
    def test(self, field=field, value=value):
        original = request()
        changed = copy.deepcopy(original)
        changed[field] = value
        expected = "lin-" + hashlib.sha256("\0".join(changed[k] for k in
                    ("source", "target", "id")).encode()).hexdigest()[:44]
        self.assertEqual(envelope.operation_id(changed), expected)
        self.assertNotEqual(envelope.operation_id(original), expected)
    add_case("test_a7_identity_changes_" + field, test)

for field, value in {"agent": "bobby", "correlation_id": "corr0001",
                     "run_id": "run00001", "payload": {"include_retired": True}}.items():
    def test(self, field=field, value=value):
        original = request("call")
        changed = copy.deepcopy(original)
        if field == "payload":
            changed[field]["args"] = value
        else:
            changed[field] = value
        self.assertEqual(envelope.operation_id(changed), envelope.operation_id(original))
        self.assertNotEqual(envelope.digest(changed), envelope.digest(original))
        self.assertEqual(envelope.digest(changed), hashlib.sha256(wire(changed)).hexdigest())
    add_case("test_a7_digest_changes_" + field, test)
