"""Structural validator oracle; no transport or domain dependencies."""

import copy
import json
import unittest
from unittest.mock import patch

from lineage.core import schema as boundary
from tests.core.schema import (
    OracleMixin, container_ids, nested_array, no_application_io,
)


class DictSubclass(dict):
    pass


class ListSubclass(list):
    pass


class IntSubclass(int):
    pass


class FloatSubclass(float):
    pass


class StrSubclass(str):
    pass


class ValidationTests(OracleMixin, unittest.TestCase):
    def test_a02_valid_nested_values_and_return_none(self):
        value = {"items": [{"name": "ok", "values": [1, 2.5]}], "enabled": True}
        schema = {"type": "object", "required": ["items"],
                  "additionalProperties": False, "properties": {
                      "enabled": {"type": "boolean"},
                      "items": {"type": "array", "items": {
                          "type": "object", "required": ["name", "values"],
                          "additionalProperties": False, "properties": {
                              "name": {"type": "string"},
                              "values": {"type": "array", "items": {"type": "number"}},
                          }}}}}
        self.accept(value, schema)

    def test_a09_direct_value_depth_boundaries(self):
        for kind in ("list", "dict"):
            value = 0
            for _ in range(boundary.MAX_DEPTH):
                value = [value] if kind == "list" else {"x": value}
            self.accept(value, {})
            too_deep = [value] if kind == "list" else {"x": value}
            pointer = ("/0" if kind == "list" else "/x") * boundary.MAX_DEPTH
            self.value_error(too_deep, {}, "depth_limit", pointer)

    def test_a09_direct_cycles_and_shared_noncycles(self):
        array = []
        array.append(array)
        self.value_error(array, {}, "cycle", "/0")
        mapping = {}
        mapping["self"] = mapping
        self.value_error(mapping, {}, "cycle", "/self")
        left, right = [], {}
        left.append(right)
        right["left"] = left
        self.value_error({"outer": left}, {}, "cycle", "/outer/0/left")
        shared = {"items": [1, 2]}
        self.accept({"a": shared, "b": shared}, {})

    def test_a09_schema_depth_counts_containers_including_literal_values(self):
        schema = {}
        for _ in range(boundary.MAX_DEPTH - 1):
            schema = {"items": schema}
        self.accept(0, schema)
        self.schema_error({"items": schema}, "/items" * boundary.MAX_DEPTH)
        literal = nested_array(boundary.MAX_DEPTH - 1)
        self.accept(literal, {"const": literal})
        self.schema_error({"const": nested_array(boundary.MAX_DEPTH)},
                          "/const" + "/0" * (boundary.MAX_DEPTH - 1))

    def test_a09_schema_cycles_point_to_back_edge(self):
        schema = {}
        schema["items"] = schema
        self.schema_error(schema, "/items")
        literal = []
        literal.append(literal)
        self.schema_error({"const": literal}, "/const/0")

    def test_a09_schema_shared_containers_are_allowed(self):
        child = {"type": "integer"}
        self.accept({"a": 1, "b": 2},
                    {"properties": {"a": child, "b": child}})

    def test_a10_schema_must_be_native_object(self):
        for schema in (None, True, False, [], "object", 1, DictSubclass()):
            with self.subTest(schema_type=type(schema).__name__):
                self.schema_error(schema, "")

    def test_a10_malformed_scalar_operands(self):
        fixtures = [
            ({"type": "bogus"}, "/type"), ({"type": True}, "/type"),
            ({"type": []}, "/type"), ({"properties": []}, "/properties"),
            ({"properties": None}, "/properties"),
            ({"items": []}, "/items"), ({"items": True}, "/items"),
            ({"required": "a"}, "/required"),
            ({"additionalProperties": 1}, "/additionalProperties"),
            ({"additionalProperties": None}, "/additionalProperties"),
            ({"uniqueItems": 1}, "/uniqueItems"),
            ({"uniqueItems": "true"}, "/uniqueItems"),
            ({"enum": []}, "/enum"), ({"enum": "x"}, "/enum"),
            ({"enum": None}, "/enum"), ({"pattern": "["}, "/pattern"),
            ({"pattern": 1}, "/pattern"),
            ({"minimum": "1"}, "/minimum"), ({"maximum": True}, "/maximum"),
        ]
        for schema, pointer in fixtures:
            with self.subTest(schema=schema):
                self.schema_error(schema, pointer)

    def test_a10_invalid_union_required_and_enum_entries(self):
        fixtures = [
            ("type", ["string", "string"], 1),
            ("type", ["string", "bogus"], 1),
            ("type", ["string", 0], 1),
            ("required", ["x", "x"], 1),
            ("required", [0], 0),
            ("required", [True], 0),
            ("enum", [1, 1.0], 1),
            ("enum", [{"a": [1], "b": None}, {"b": None, "a": [1.0]}], 1),
            ("enum", [True, True], 1),
        ]
        for keyword, operand, index in fixtures:
            with self.subTest(keyword=keyword, operand=operand):
                self.one_of_errors(boundary.validate, None, {keyword: operand},
                                   reasons=("invalid_schema",),
                                   schema_pointers=("/" + keyword,
                                                    "/" + keyword + "/" + str(index)))

    def test_a10_child_schemas_and_schema_native_types(self):
        self.schema_error({"properties": {"a/b~c": False}},
                          "/properties/a~1b~0c")
        self.schema_error({"properties": {"x": DictSubclass()}}, "/properties/x")
        for schema, locations in (
            ({"type": StrSubclass("string")}, ("/type",)),
            ({"required": ListSubclass()}, ("/required",)),
            ({"minLength": IntSubclass(0)}, ("/minLength",)),
            ({"maximum": FloatSubclass(1)}, ("/maximum",)),
            ({1: {}}, ("",)),
            ({"const": (1,)}, ("/const",)),
            ({"properties": {1: {}}}, ("/properties",)),
        ):
            with self.subTest(schema=schema):
                self.one_of_errors(boundary.validate, None, schema,
                                   reasons=("invalid_schema",),
                                   schema_pointers=locations)

    def test_a11_unreachable_malformed_children_preflight_first(self):
        for keyword, operand, reason in (("minLength", -1, "invalid_schema"),
                                         ("typo", True, "unsupported_keyword")):
            with self.subTest(keyword=keyword):
                self.schema_error({"properties": {"absent": {keyword: operand}}},
                                  "/properties/absent/" + keyword, reason, value={})
                self.schema_error({"items": {keyword: operand}},
                                  "/items/" + keyword, reason, value=[])
                self.schema_error({"type": "integer", "properties": {
                    "absent": {keyword: operand}}},
                    "/properties/absent/" + keyword, reason, value=object())

    def test_a11_non_json_values_in_schema_literals(self):
        for bad in (float("nan"), float("inf"), float("-inf"), "\ud800", b"x"):
            for schema, pointer in (({"const": bad}, "/const"),
                                    ({"enum": [bad]}, "/enum/0"),
                                    ({"const": {"x": bad}}, "/const/x")):
                with self.subTest(pointer=pointer, bad_type=type(bad).__name__):
                    self.schema_error(schema, pointer)

    def test_a12_unsupported_keywords_at_root_and_child(self):
        for keyword, operand in (("minLenght", 1), ("$ref", "other.schema.json"),
                                 ("anyOf", [{}]), ("allOf", [{}]),
                                 ("default", 1), ("format", "email"),
                                 ("patternProperties", {})):
            for schema, pointer in (
                ({keyword: operand}, "/" + keyword),
                ({"properties": {"a/b~c": {keyword: operand}}},
                 "/properties/a~1b~0c/" + keyword),
                ({"items": {keyword: operand}}, "/items/" + keyword),
            ):
                with self.subTest(pointer=pointer):
                    self.schema_error(schema, pointer, "unsupported_keyword")

    def test_a12_subschema_additional_properties_is_never_ignored(self):
        for schema, pointer in (
            ({"additionalProperties": {}}, "/additionalProperties"),
            ({"properties": {"x": {"additionalProperties": {}}}},
             "/properties/x/additionalProperties"),
            ({"items": {"additionalProperties": {}}}, "/items/additionalProperties"),
        ):
            with self.subTest(pointer=pointer):
                self.one_of_errors(boundary.validate, {}, schema,
                                   reasons=("invalid_schema", "unsupported_keyword"),
                                   schema_pointers=(pointer,))

    def test_a12_annotations_are_passive_and_string_only(self):
        annotations = {"$schema": "urn:lineage:passive-schema",
                       "$id": "unresolved.schema.json", "title": "schema title",
                       "description": "passive text"}
        with no_application_io() as (output, errors):
            self.accept({"schema": "ordinary data"}, annotations)
        self.assertEqual((output.getvalue(), errors.getvalue()), ("", ""))
        for name in annotations:
            for bad in (None, 1, False, []):
                with self.subTest(name=name, bad=bad):
                    self.schema_error({name: bad}, "/" + name)

    def test_a26_boolean_is_not_integer(self):
        self.value_error(True, {"type": "integer"}, "type")

    def test_a13_all_native_types_no_coercion(self):
        cases = [({}, "object"), ([], "array"), ("1", "string"),
                 (1, "integer"), (1.0, "number"), (False, "boolean"),
                 (None, "null")]
        for value, expected_type in cases:
            for name in ("object", "array", "string", "integer", "number",
                         "boolean", "null"):
                with self.subTest(value=value, name=name):
                    if name == expected_type or (expected_type == "integer" and name == "number"):
                        self.accept(value, {"type": name})
                    else:
                        self.value_error(value, {"type": name}, "type")
        for boolean in (True, False):
            for name in ("integer", "number"):
                self.value_error(boolean, {"type": name}, "type")

    def test_a13_union_null_and_absent_are_distinct(self):
        union = {"type": ["string", "null"]}
        for value in (None, "", "ok"):
            self.accept(value, union)
        self.value_error([], union, "type")
        schema = {"properties": {"x": union}, "required": ["x"]}
        self.accept({"x": None}, schema)
        self.value_error({}, schema, "required", "/x")
        self.value_error({"x": None}, {"properties": {"x": {"type": "string"}},
                                       "required": ["x"]}, "type", "/x")

    def test_a14_non_json_python_inputs_everywhere(self):
        bad_values = [(), set(), b"x", bytearray(b"x"), memoryview(b"x"),
                      object(), DictSubclass(), ListSubclass(), IntSubclass(1),
                      FloatSubclass(1), StrSubclass("x")]
        for bad in bad_values:
            for schema in ({}, {"properties": {"x": {}}},
                           {"additionalProperties": True}):
                with self.subTest(bad_type=type(bad).__name__, schema=schema):
                    self.value_error({"x": bad}, schema, "not_json", "/x")
            with self.subTest(root_type=type(bad).__name__):
                self.value_error(bad, {}, "not_json")
            with self.subTest(array_type=type(bad).__name__):
                self.value_error([0, bad], {}, "not_json", "/1")

    def test_a14_non_string_keys_report_containing_object(self):
        for key in (1, None, False, (1,), StrSubclass("x")):
            for schema in ({}, {"properties": {"x": {}}},
                           {"additionalProperties": True}):
                with self.subTest(key_type=type(key).__name__, schema=schema):
                    self.value_error({"x": {key: 0}}, schema, "not_json", "/x")

    def test_a14_non_finite_and_unicode_direct_values(self):
        for bad, reason in ((float("nan"), "non_finite"),
                            (float("inf"), "non_finite"),
                            (float("-inf"), "non_finite"),
                            ("\ud800", "invalid_unicode"),
                            ("\udfff", "invalid_unicode")):
            for schema in ({}, {"properties": {"x": {}}},
                           {"additionalProperties": True}):
                with self.subTest(reason=reason, schema=schema):
                    self.value_error({"x": bad}, schema, reason, "/x")
            self.value_error(bad, {}, reason)

    def test_a14_surrogate_key_reports_key_or_containing_object(self):
        for key in ("\ud800", "\udfff"):
            self.one_of_errors(boundary.validate, {"x": {key: 0}}, {},
                               reasons=("invalid_unicode",),
                               pointers=("/x", "/x/" + key))

    def test_a15_required_closed_objects_and_optional_preservation(self):
        schema = {"type": "object", "required": ["name", "nullable"],
                  "additionalProperties": False, "properties": {
                      "name": {"type": "string"},
                      "nullable": {"type": ["number", "null"]},
                      "optional": {"type": "integer"}}}
        value = {"name": "agent", "nullable": None}
        self.accept(value, schema)
        self.assertEqual(value, {"name": "agent", "nullable": None})
        self.assertNotIn("optional", value)
        self.value_error({"nullable": None}, schema, "required", "/name")
        self.value_error({"name": "agent"}, schema, "required", "/nullable")

    def test_a15_empty_required_and_undeclared_required_name(self):
        self.accept({}, {"required": []})
        self.accept({"": None}, {"required": [""]})
        self.value_error({}, {"required": [""]}, "required", "/")
        self.accept({"undeclared": None}, {"required": ["undeclared"]})
        self.value_error({}, {"required": ["undeclared"]}, "required", "/undeclared")

    def test_a26_unknown_key_escaped_pointer(self):
        self.value_error({"a/b~c": 1}, {"type": "object", "additionalProperties": False},
                         "additionalProperties", "/a~1b~0c")

    def test_a16_recursive_closed_objects_and_full_pointers(self):
        closed = {"type": "object", "additionalProperties": False,
                  "properties": {"ok": {"type": "integer"}}}
        fixtures = [({"extra": 0}, closed, "/extra"),
                    ({"outer": {"a/b~c": 1}}, {"properties": {"outer": closed}},
                     "/outer/a~1b~0c"),
                    ({"outer": [{"a/b~c": 1}]},
                     {"properties": {"outer": {"items": closed}}},
                     "/outer/0/a~1b~0c"),
                    ([{"": 0}], {"items": closed}, "/0/"),
                    ({"/": {"~": 0}}, {"properties": {"/": closed}}, "/~1/~0")]
        for value, schema, pointer in fixtures:
            with self.subTest(pointer=pointer):
                before = copy.deepcopy(value)
                identities = container_ids(value)
                self.value_error(value, schema, "additionalProperties", pointer)
                self.assertEqual(value, before)
                self.assertEqual(container_ids(value), identities)

    def test_a17_permissive_defaults_and_type_specific_applicability(self):
        for schema in ({}, {"properties": {}}, {"additionalProperties": True}):
            value = {"undeclared": [1, None, {"x": True}]}
            self.accept(value, schema)
            self.assertIn("undeclared", value)
        self.value_error({"outer": {"extra": 1}}, {"properties": {
            "outer": {"additionalProperties": False}}},
            "additionalProperties", "/outer/extra")
        for value in (None, True, 0, 1.5, "ok", [], {}):
            self.accept(value, {})
        # No keyword implicitly requires the instance to have a given type.
        for value, schema in ((0, {"required": ["x"], "additionalProperties": False}),
                              ({}, {"minItems": 10, "items": {"type": "integer"}}),
                              ([], {"minLength": 10, "pattern": "^x$"}),
                              (None, {"minimum": 10}), (False, {"minimum": 1}),
                              ("0", {"minimum": 10})):
            self.accept(value, schema)

    def test_a18_array_bounds_inclusive_and_empty_arrays(self):
        schema = {"type": "array", "minItems": 1, "maxItems": 2}
        self.accept([0], schema)
        self.accept([0, 1], schema)
        self.value_error([], schema, "minItems")
        self.value_error([0, 1, 2], schema, "maxItems")
        self.accept([], {"minItems": 0, "maxItems": 0})
        self.value_error([0], {"maxItems": 0}, "maxItems")

    def test_a18_array_items_after_valid_prefix_and_nested_pointers(self):
        self.value_error([1, 2, "3"], {"items": {"type": "integer"}}, "type", "/2")
        self.value_error([{"x": 0}, {"x": "bad"}], {"items": {
            "properties": {"x": {"type": "integer"}}}}, "type", "/1/x")

    def test_a19_uniqueness_deep_containers_and_numeric_equality(self):
        schema = {"uniqueItems": True}
        self.accept([[1], [2], {"x": [1]}, {"x": [2]}], schema)
        self.accept([True, 1, False, 0, None, "1"], schema)
        for value, pointer in (([{"a": 1, "b": [2]}, {"b": [2.0], "a": 1.0}], "/1"),
                               ([[1, {"x": 2}], [1.0, {"x": 2.0}]], "/1"),
                               ([1, 2, 1.0], "/2"), ([None, None], "/1")):
            with self.subTest(pointer=pointer, value=value):
                self.value_error(value, schema, "uniqueItems", pointer)
        self.accept([{}, {}], {})
        self.accept([[], []], {"uniqueItems": False})

    def test_a20_string_length_counts_unicode_codepoints(self):
        for text in ("", "a", "日本", "😀", "e\u0301"):
            length = len(text)
            with self.subTest(text=text):
                self.accept(text, {"minLength": length, "maxLength": length})
                self.value_error(text, {"minLength": length + 1}, "minLength")
                if length:
                    self.value_error(text, {"maxLength": length - 1}, "maxLength")

    def test_a20_pattern_search_no_implicit_flags_or_anchors(self):
        self.accept("prefix cat suffix", {"pattern": "cat"})
        self.accept("cat", {"pattern": "^cat$"})
        self.value_error("prefix cat suffix", {"pattern": "^cat$"}, "pattern")
        self.value_error("CAT", {"pattern": "cat"}, "pattern")
        self.value_error("a\nb", {"pattern": "a.b"}, "pattern")
        self.accept("[", {"pattern": "."})
        self.value_error("", {"pattern": "."}, "pattern")
        self.schema_error({"pattern": "("}, "/pattern")

    def test_a21_numeric_bounds_are_inclusive_without_null_coercion(self):
        schema = {"type": ["number", "null"], "minimum": -1.5, "maximum": 2.25}
        for value in (-1.5, -1, 0, 2.25, None):
            self.accept(value, schema)
        self.value_error(-1.5001, schema, "minimum")
        self.value_error(2.2501, schema, "maximum")
        self.accept(None, {"type": ["number", "null"], "minimum": 10})
        self.accept(True, {"minimum": 2, "maximum": 3})
        self.accept("0", {"minimum": 2})

    def test_a21_invalid_count_length_and_numeric_operands(self):
        for keyword in ("minItems", "maxItems", "minLength", "maxLength"):
            for operand in (-1, True, False, 1.5, "1", None):
                with self.subTest(keyword=keyword, operand=operand):
                    self.schema_error({keyword: operand}, "/" + keyword)
        for keyword in ("minimum", "maximum"):
            for operand in (True, False, float("nan"), float("inf"), float("-inf"),
                            "1", None):
                with self.subTest(keyword=keyword, operand=operand):
                    self.schema_error({keyword: operand}, "/" + keyword)

    def test_a21_reversed_matching_bounds_are_schema_errors(self):
        for lower, upper in (("minItems", "maxItems"), ("minLength", "maxLength"),
                             ("minimum", "maximum")):
            with self.subTest(lower=lower):
                self.one_of_errors(boundary.validate, None, {lower: 2, upper: 1},
                                   reasons=("invalid_schema",),
                                   schema_pointers=("/" + lower, "/" + upper))

    def test_a22_enum_and_const_scalars_containers_and_null(self):
        for value in (None, True, "x", 1, [1, {"x": None}], {"b": [2], "a": 1}):
            for keyword, operand in (("const", value), ("enum", [value])):
                with self.subTest(keyword=keyword, value=value):
                    self.accept(copy.deepcopy(value), {keyword: copy.deepcopy(operand)})
        self.accept({"a": 1.0, "b": [2.0]}, {"const": {"b": [2], "a": 1}})
        self.accept([1.0, {"x": 2}], {"enum": [[1, {"x": 2.0}]]})
        self.accept(1.0, {"const": 1})
        self.accept(1, {"enum": [1.0]})
        for value, schema, reason in ((True, {"const": 1}, "const"),
                                       (False, {"enum": [0]}, "enum"),
                                       (1, {"const": True}, "const"),
                                       (None, {"const": 0}, "const"),
                                       ("b", {"enum": ["a"]}, "enum"),
                                       ([2, 1], {"const": [1, 2]}, "const")):
            with self.subTest(schema=schema):
                self.value_error(value, schema, reason)

    def test_a22_enum_distinguishes_bool_and_number_and_is_conjunctive(self):
        self.accept(True, {"enum": [True, 1, False, 0]})
        self.accept(1, {"enum": [True, 1, False, 0]})
        self.accept(2, {"enum": [1, 2], "const": 2})
        self.value_error(1, {"enum": [1, 2], "const": 2}, "const")
        self.value_error(2, {"enum": [1], "const": 2}, "enum")
        self.value_error(1, {"type": "string", "const": 1}, "type")

    def test_a22_huge_int_float_equality_never_overflows(self):
        huge = 10 ** 400
        self.accept(huge, {"const": huge})
        self.accept(huge, {"enum": [huge, 1e308]})
        self.accept([huge, 1e308], {"uniqueItems": True})
        self.value_error(huge, {"const": 1e308}, "const")
        self.value_error(huge, {"enum": [1e308]}, "enum")
        self.value_error([huge, huge], {"uniqueItems": True}, "uniqueItems", "/1")
        self.accept([9_007_199_254_740_993, 9_007_199_254_740_992.0],
                    {"uniqueItems": True})
        self.value_error(9_007_199_254_740_993,
                         {"const": 9_007_199_254_740_992.0}, "const")

    def test_a23_schemaerror_constructor_and_sanitized_string(self):
        error = boundary.SchemaError("type", pointer="/a~1b~0c/0")
        self.assertEqual((error.code, error.reason, error.pointer, error.schema_pointer,
                          str(error)),
                         ("bad_args", "type", "/a~1b~0c/0", None, "bad_args:type"))
        error = boundary.SchemaError("invalid_schema", schema_pointer="/items/type")
        self.assertEqual((error.code, error.reason, error.pointer, error.schema_pointer,
                          str(error)), ("bad_args", "invalid_schema", "", "/items/type",
                                       "bad_args:invalid_schema"))

    def test_a23_sensitive_scalar_never_leaks_in_diagnostics(self):
        secret = "SENSITIVE_U02_VALUE_7e9f"
        error = self.value_error({"": [{"/a~": secret}]}, {"properties": {"": {
            "items": {"properties": {"/a~": {"type": "integer"}}}}}},
            "type", "//0/~1a~0")
        for field in (error.code, error.reason, error.pointer,
                      error.schema_pointer, str(error)):
            self.assertNotIn(secret, str(field))

    def test_a24_deterministic_required_properties_arrays_and_type_order(self):
        for names in (["z", "a"], ["a", "z"]):
            self.value_error({}, {"required": names}, "required", "/a")
        for names in (("z", "a"), ("a", "z")):
            schema = {"properties": {name: {"type": "integer"} for name in names}}
            value = {name: "bad" for name in names}
            self.value_error(value, schema, "type", "/a")
            self.value_error([value, {"a": "bad"}], {"items": schema}, "type", "/0/a")
            closed = {"additionalProperties": False}
            self.value_error(value, closed, "additionalProperties", "/a")
        self.value_error([], {"type": "object", "minItems": 3}, "type")
        for _ in range(2):
            self.schema_error({"items": True}, "/items")
            self.value_error({"z": "bad", "a": "bad"}, {"properties": {
                "z": {"type": "integer"}, "a": {"type": "integer"}}}, "type", "/a")

    def test_a24_schema_preflight_unsupported_lexical_and_unreachable_order(self):
        for names in (("z_bad", "a_bad"), ("a_bad", "z_bad")):
            self.schema_error({name: True for name in names}, "/a_bad", "unsupported_keyword")
        for names in (("z", "a"), ("a", "z")):
            self.schema_error({"properties": {name: {"type": "bogus"} for name in names}},
                              "/properties/a/type")
        self.schema_error({"type": "bogus", "z_bad": True}, "/z_bad", "unsupported_keyword")

    def test_a24_unresolved_error_precedence_is_still_repeatable(self):
        def diagnostic(value, schema):
            with self.assertRaises(boundary.SchemaError) as caught:
                boundary.validate(value, schema)
            error = caught.exception
            self.assertEqual(error.code, "bad_args")
            self.assertEqual(str(error), "bad_args:" + error.reason)
            self.assertIsNone(error.schema_pointer)
            return error.reason, error.pointer

        # Amendment B leaves full JSON preflight versus lazy traversal open.
        first = diagnostic({"a": "bad", "b": ()}, {"properties": {
            "a": {"type": "integer"}}})
        self.assertIn(first, (("type", "/a"), ("not_json", "/b")))
        second = diagnostic({"b": (), "a": "bad"}, {"properties": {
            "a": {"type": "integer"}}})
        self.assertEqual(first, second)

        # Check deterministic node keyword precedence without inventing its order.
        expected = diagnostic({}, {"required": ["z"], "enum": [1]})
        self.assertIn(expected, (("required", "/z"), ("enum", "")))
        self.assertEqual(expected, diagnostic({}, {"enum": [1], "required": ["z"]}))

    def test_a24_ambiguous_schema_keyword_order_is_stable(self):
        results = []
        for names in (("type", "pattern"), ("pattern", "type")):
            operands = {"type": "bogus", "pattern": "["}
            error = self.one_of_errors(boundary.validate, None,
                                       {name: operands[name] for name in names},
                                       reasons=("invalid_schema",),
                                       schema_pointers=("/type", "/pattern"))
            results.append((error.reason, error.schema_pointer))
        self.assertEqual(results[0], results[1])

    def test_a25_success_failure_and_reused_pattern_schema_are_pure(self):
        schema = {"type": "object", "additionalProperties": False,
                  "properties": {"text": {"type": "string", "pattern": "ok"},
                                 "literal": {"const": {"a": [1, 2]}}},
                  "required": ["text", "literal"]}
        before_schema = copy.deepcopy(schema)
        schema_ids = container_ids(schema)
        for text, succeeds in (("ok", True), ("bad", False), ("ok again", True)):
            value = {"text": text, "literal": {"a": [1, 2]}}
            before = copy.deepcopy(value)
            value_ids = container_ids(value)
            with no_application_io() as (output, errors):
                if succeeds:
                    self.accept(value, schema)
                else:
                    self.value_error(value, schema, "pattern", "/text")
            self.assertEqual((output.getvalue(), errors.getvalue()), ("", ""))
            self.assertEqual(value, before)
            self.assertEqual(container_ids(value), value_ids)
            self.assertEqual(schema, before_schema)
            self.assertEqual(container_ids(schema), schema_ids)

    def test_a25_failed_schema_preflight_does_not_mutate_inputs(self):
        value = {"retained": [1, {"x": 2}]}
        schema = {"properties": {"unused": {"pattern": "["}}}
        before_value, before_schema = copy.deepcopy(value), copy.deepcopy(schema)
        value_ids, schema_ids = container_ids(value), container_ids(schema)
        self.schema_error(schema, "/properties/unused/pattern", value=value)
        self.assertEqual(value, before_value)
        self.assertEqual(schema, before_schema)
        self.assertEqual(container_ids(value), value_ids)
        self.assertEqual(container_ids(schema), schema_ids)

    def test_a26_permissive_doubles_fail_five_assertion_oracles(self):
        from tests.core.schema.test_strict_json import StrictJSONTests

        suite = unittest.TestSuite([
            StrictJSONTests("test_a26_byte_cap_rejection"),
            StrictJSONTests("test_a26_nested_duplicate_rejection"),
            StrictJSONTests("test_a26_non_finite_rejection"),
            ValidationTests("test_a26_boolean_is_not_integer"),
            ValidationTests("test_a26_unknown_key_escaped_pointer"),
        ])
        result = unittest.TestResult()
        with patch.object(boundary, "strict_loads", side_effect=json.loads), \
             patch.object(boundary, "validate", return_value=None):
            suite.run(result)
        self.assertEqual(result.testsRun, 5)
        self.assertEqual(len(result.failures), 5)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.skipped, [])
        for _, traceback in result.failures:
            self.assertIn("AssertionError", traceback)
            self.assertNotIn("NotImplementedError", traceback)
        # This oracle itself remains red until the real boundary is implemented.
        self.accept({}, {})


if __name__ == "__main__":
    unittest.main()
