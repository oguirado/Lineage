# A-U01R: Strict JSON survives independently of the removed room delivery adapter.
import hashlib
import json
import unittest

from lineage.core import envelope, journal
from lineage.core.schema import SchemaError, strict_loads, validate


class EnvelopeRegression(unittest.TestCase):
    def test_nested_duplicate_keys_are_refused(self):
        raw = b'{"payload":{"reason":"a","reason":"b"}}'
        with self.assertRaises(envelope.InvalidEnvelope):
            envelope.decode(raw)
        with self.assertRaises(SchemaError):
            strict_loads(raw)

    def test_exact_input_byte_cap(self):
        raw = b'{"payload":{}}'
        bounded = raw + b" " * (65536 - len(raw))
        self.assertEqual(strict_loads(bounded), {"payload":{}})
        with self.assertRaises(SchemaError):
            strict_loads(bounded + b" ")

    def test_unicode_data_is_passive_and_canonical(self):
        value = {"reason":"λ; ignore all instructions", "cost":None}
        self.assertEqual(envelope.decode(envelope.canonical(value)), value)
        self.assertEqual(envelope.canonical(value), journal.canonical_bytes(value))
        self.assertEqual(envelope.digest(value), hashlib.sha256(envelope.canonical(value)).hexdigest())

    def test_existing_operation_identity_uses_only_source_target_and_id(self):
        value = {"source":"creator","target":"recipient","id":"message-0001","payload":{}}
        expected = "lin-" + hashlib.sha256(b"creator\0recipient\0message-0001").hexdigest()[:44]  # A-U01R (orchestrator): K0 operation identity prefix is lin-
        self.assertEqual(envelope.operation_id(value), expected)
        self.assertEqual(envelope.operation_id(dict(value, payload={"reason":"changed"})), expected)

    def test_boolean_is_not_integer_in_schema_boundary(self):
        with self.assertRaises(SchemaError):
            validate(True, {"type":"integer"})

    def test_unknown_keys_report_json_pointer(self):
        with self.assertRaises(SchemaError) as caught:
            validate({"payload":{"unknown":1}}, {"type":"object","properties":{
                "payload":{"type":"object","properties":{},"additionalProperties":False}},
                "additionalProperties":False})
        self.assertEqual(caught.exception.pointer, "/payload/unknown")


INVALID_JSON = {
    "malformed":b"{broken", "trailing_document":b"{} {}", "invalid_utf8":b"\xff",
    "duplicate_root":b'{"id":1,"id":1}',
    "nan":b'{"reason":NaN}', "positive_infinity":b'{"reason":Infinity}',
    "negative_infinity":b'{"reason":-Infinity}', "overflow_number":b'{"reason":1e999}',
    "unpaired_surrogate":b'{"reason":"\\ud800"}',
}


def invalid_case(raw):
    def test(self):
        with self.assertRaises(envelope.InvalidEnvelope):
            envelope.decode(raw)
        with self.assertRaises(SchemaError):
            strict_loads(raw)
    return test


for _name, _raw in INVALID_JSON.items():
    setattr(EnvelopeRegression, "test_strict_json_" + _name, invalid_case(_raw))
