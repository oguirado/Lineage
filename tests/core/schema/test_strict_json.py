"""Fail-first loader oracle for .unit/SPEC.md, including Amendment B."""

import importlib
import inspect
import json
import math
import unittest

from lineage.core import schema as boundary
from tests.core.schema import OracleMixin, no_application_io


class TextSubclass(str):
    pass


class BytesSubclass(bytes):
    pass


class StrictJSONTests(OracleMixin, unittest.TestCase):
    def test_a01_import_and_calls_are_silent_and_independent(self):
        with no_application_io() as (output, errors):
            module = importlib.reload(boundary)
            self.assertEqual(module.strict_loads('{"ok":[1,true,null]}'),
                             {"ok": [1, True, None]})
            self.assertIsNone(module.validate({"ok": [1, True, None]}, {}))
            self.raw_error('{"x":0,"x":0}', "duplicate_key")
            self.value_error(True, {"type": "integer"}, "type")
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(errors.getvalue(), "")

    def test_a01_exact_signatures_and_constants(self):
        self.assertEqual(boundary.MAX_JSON_BYTES, 65_536)
        self.assertEqual(boundary.MAX_DEPTH, 64)
        load = inspect.signature(boundary.strict_loads)
        self.assertEqual(list(load.parameters), ["raw"])
        validate = inspect.signature(boundary.validate)
        self.assertEqual(list(validate.parameters), ["value", "schema"])
        constructor = inspect.signature(boundary.SchemaError)
        self.assertEqual(list(constructor.parameters),
                         ["reason", "pointer", "schema_pointer"])
        for name in ("pointer", "schema_pointer"):
            self.assertEqual(constructor.parameters[name].kind,
                             inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(constructor.parameters["pointer"].default, "")
        self.assertIsNone(constructor.parameters["schema_pointer"].default)
        self.assertTrue(issubclass(boundary.SchemaError, ValueError))
        self.assertEqual(boundary.strict_loads("null"), None)

    def test_a02_all_root_types_text_and_bytes(self):
        fixtures = [({}, dict), ([], list), ({"a": [1, None]}, dict),
                    ("hello 世界 😀", str), (0, int), (-9, int),
                    (1.25, float), (True, bool), (False, bool), (None, type(None))]
        for value, concrete_type in fixtures:
            text = " \t\r\n" + json.dumps(value, ensure_ascii=False) + "\n\t "
            for raw in (text, text.encode("utf-8")):
                with self.subTest(value=value, raw_type=type(raw).__name__):
                    result = boundary.strict_loads(raw)
                    self.assertIs(type(result), concrete_type)
                    self.assertEqual(result, value)

    def test_a03_syntax_hostility_text_and_bytes(self):
        fixtures = ["", " \t\r\n", "{} []", "null null", "[0,]",
                    '{"a":0,}', "// comment\n0", "/* comment */0",
                    '"a\x01b"', r'"\x41"', r'"\uQQQQ"',
                    '"unterminated', "\ufeff{}", "+1", "01", "[.5]",
                    "[1.]", "\u00a0null", "{unquoted:0}"]
        for text in fixtures:
            for raw in (text, text.encode("utf-8")):
                with self.subTest(raw=repr(raw)):
                    self.raw_error(raw, "invalid_json")

    def test_a03_large_integer_never_leaks_interpreter_valueerror(self):
        # Amendment B explicitly permits acceptance OR sanitized invalid_json.
        for sign in ("", "-"):
            text = sign + "9" * 4_301
            results = []
            for raw in (text, text.encode("utf-8")):
                try:
                    result = boundary.strict_loads(raw)
                except boundary.SchemaError as error:
                    self.assertEqual((error.code, error.reason, error.pointer,
                                      error.schema_pointer, str(error)),
                                     ("bad_args", "invalid_json", "", None,
                                      "bad_args:invalid_json"))
                    results.append(("rejected", error.reason))
                else:
                    self.assertIs(type(result), int)
                    self.assertEqual(result, (10 ** 4_301 - 1) *
                                     (-1 if sign else 1))
                    results.append(("accepted", result))
            self.assertEqual(results[0], results[1])

    def test_a04_exact_byte_cap_accepts_valid_whitespace_padding(self):
        text = "null" + " " * (boundary.MAX_JSON_BYTES - 4)
        self.assertEqual(len(text.encode("utf-8")), boundary.MAX_JSON_BYTES)
        for raw in (text, text.encode("utf-8")):
            self.assertIsNone(boundary.strict_loads(raw))

    def test_a26_byte_cap_rejection(self):
        raw = b"null" + b" " * (boundary.MAX_JSON_BYTES - 3)
        self.raw_error(raw, "too_large")

    def test_a04_text_over_byte_cap(self):
        raw = "0" + " " * boundary.MAX_JSON_BYTES
        self.raw_error(raw, "too_large")

    def test_a04_byte_size_is_checked_before_utf8_decoding(self):
        self.raw_error(b"\xff" + b" " * boundary.MAX_JSON_BYTES, "too_large")

    def test_a05_non_ascii_utf8_accounting(self):
        # Quotes plus multi-byte characters, then one valid whitespace byte.
        text = '"' + "é" * ((boundary.MAX_JSON_BYTES - 2) // 2) + '"'
        self.assertLess(len(text), boundary.MAX_JSON_BYTES)
        self.assertEqual(len(text.encode("utf-8")), boundary.MAX_JSON_BYTES)
        for raw in (text, text.encode("utf-8")):
            with self.subTest(raw_type=type(raw).__name__):
                result = boundary.strict_loads(raw)
                self.assertEqual(result, "é" * ((boundary.MAX_JSON_BYTES - 2) // 2))
        for raw in (text + " ", (text + " ").encode("utf-8")):
            with self.subTest(over_type=type(raw).__name__):
                self.raw_error(raw, "too_large")

    def test_a05_raw_types_and_subclasses_are_rejected(self):
        for raw in ({}, bytearray(b"{}"), memoryview(b"{}"), None,
                    [], 1, True, TextSubclass("{}"), BytesSubclass(b"{}")):
            with self.subTest(concrete_type=type(raw).__name__):
                self.raw_error(raw, "input_type")

    def test_a05_oversized_surrogate_text_encodes_strictly_first(self):
        self.raw_error(" " * (boundary.MAX_JSON_BYTES + 1) + "\ud800",
                       "invalid_unicode")

    def test_a26_nested_duplicate_rejection(self):
        self.raw_error('{"outer":[{"nested":{"x":1,"x":1}}]}',
                       "duplicate_key")

    def test_a06_duplicate_names_at_every_depth_and_decoded_equivalence(self):
        for text in ('{"x":1,"x":2}', '{"x":null,"x":null}',
                     '[{"x":1,"x":1}]', '{"a":{"b":{"x":0,"x":1}}}',
                     r'{"a":1,"\u0061":2}', '{"":0,"":1}'):
            for raw in (text, text.encode("utf-8")):
                with self.subTest(raw=raw):
                    self.raw_error(raw, "duplicate_key")

    def test_a06_sibling_names_and_canonical_unicode_remain_distinct(self):
        self.assertEqual(boundary.strict_loads('[{"x":1},{"x":2}]'),
                         [{"x": 1}, {"x": 2}])
        self.assertEqual(boundary.strict_loads('{"é":1,"e\\u0301":2}'),
                         {"é": 1, "e\u0301": 2})

    def test_a26_non_finite_rejection(self):
        self.raw_error('{"outer":[1e9999]}', "non_finite")

    def test_a07_non_finite_tokens_and_overflow(self):
        for token in ("NaN", "Infinity", "-Infinity", "1e9999", "-1e9999"):
            for text in (token, '[' + token + ']', '{"x":[' + token + ']}'):
                for raw in (text, text.encode("utf-8")):
                    with self.subTest(raw=raw):
                        self.raw_error(raw, "non_finite")

    def test_a07_finite_numbers_and_quoted_spellings(self):
        for text, expected, concrete in (("-0", 0, int), ("-0.0", -0.0, float),
                ("1.5", 1.5, float), ("-2.5e+2", -250.0, float),
                ("1e308", 1e308, float), ("1e-9999", 0.0, float),
                ("null", None, type(None))):
            with self.subTest(text=text):
                actual = boundary.strict_loads(text)
                self.assertIs(type(actual), concrete)
                self.assertEqual(actual, expected)
                if type(actual) is float:
                    self.assertTrue(math.isfinite(actual))
        for word in ("NaN", "Infinity", "-Infinity", "1e9999"):
            self.assertEqual(boundary.strict_loads(json.dumps(word)), word)

    def test_a08_invalid_utf8_and_no_encoding_autodetection(self):
        fixtures = [(b'"\xff"', "invalid_utf8"),
                    (b'"\xc0\xaf"', "invalid_utf8"),
                    (b'"\xed\xa0\x80"', "invalid_utf8"),
                    (b'"\xf4\x90\x80\x80"', "invalid_utf8"),
                    (b'"\xe2\x82', "invalid_utf8")]
        for encoding in ("utf-16", "utf-32"):
            fixtures.append(('{}'.encode(encoding), "invalid_utf8"))
        for encoding in ("utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"):
            fixtures.append(('{}'.encode(encoding), "invalid_json"))
        for raw, reason in fixtures:
            with self.subTest(raw=raw):
                self.raw_error(raw, reason)

    def test_a08_escaped_and_literal_unpaired_surrogates(self):
        for escape in (r"\ud800", r"\udfff", r"\ud800x", r"\udfff\ud800"):
            for text in ('"' + escape + '"', '{"' + escape + '":0}',
                         '{"x":["' + escape + '"]}'):
                for raw in (text, text.encode("ascii")):
                    with self.subTest(raw=raw):
                        self.raw_error(raw, "invalid_unicode")
        for surrogate in ("\ud800", "\udfff"):
            for text in ('"' + surrogate + '"', '{"' + surrogate + '":0}'):
                with self.subTest(literal=repr(text)):
                    self.raw_error(text, "invalid_unicode")

    def test_a08_paired_surrogates_and_multilingual_roundtrip(self):
        self.assertEqual(boundary.strict_loads(r'"\ud83d\ude00"'), "😀")
        self.assertEqual(boundary.strict_loads(r'{"\ud83d\ude00":"\ud83d\ude00"}'),
                         {"😀": "😀"})
        value = {"日本語": "العربية", "emoji": "😀", "e\u0301": "é"}
        for raw in (json.dumps(value, ensure_ascii=False),
                    json.dumps(value, ensure_ascii=False).encode("utf-8")):
            self.assertEqual(boundary.strict_loads(raw), value)

    def test_a09_loader_depth_boundary(self):
        for opener, closer, leaf in (("[", "]", "0"), ('{"x":', "}", "0")):
            text = opener * boundary.MAX_DEPTH + leaf + closer * boundary.MAX_DEPTH
            for raw in (text, text.encode("utf-8")):
                self.assertIsNotNone(boundary.strict_loads(raw))
            too_deep = opener + text + closer
            self.assertLess(len(too_deep), boundary.MAX_JSON_BYTES)
            for raw in (too_deep, too_deep.encode("utf-8")):
                self.raw_error(raw, "depth_limit")

    def test_a09_parser_recursion_is_normalized(self):
        text = "[" * 2_000 + "0" + "]" * 2_000
        self.assertLess(len(text), boundary.MAX_JSON_BYTES)
        self.raw_error(text, "depth_limit")

    def test_a23_raw_error_never_exposes_sensitive_scalar(self):
        secret = "SENSITIVE_U02_VALUE_7e9f"
        error = self.raw_error('"' + secret + '" trailing', "invalid_json")
        for diagnostic in (str(error), error.code, error.reason, error.pointer,
                           error.schema_pointer):
            self.assertNotIn(secret, str(diagnostic))


if __name__ == "__main__":
    unittest.main()
