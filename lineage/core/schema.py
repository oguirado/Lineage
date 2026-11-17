"""Strict JSON decoding and a dependency-free structural schema boundary.

Schema definitions are preflighted before a complete instance value-model check.
Assertions then run in this order: type; object required/additional/properties;
array bounds/uniqueness/items; string bounds/pattern; numeric bounds; enum/const.
Schema keyword order is fixed below, with child schemas visited last. Objects
are always traversed lexically and arrays by index. No caller data is changed.
"""

import json
import math
import re
from typing import Any

MAX_JSON_BYTES: int = 65_536  # [CITED: STRATEGY.md section 2.3]
MAX_DEPTH: int = 64  # [TARGET: defensive container-depth bound]


class SchemaError(ValueError):
    """Sanitized boundary failure with independent instance/schema coordinates."""

    code: str
    reason: str
    pointer: str
    schema_pointer: str | None

    def __init__(self, reason: str, *, pointer: str = "",
                 schema_pointer: str | None = None) -> None:
        self.code = "bad_args"
        self.reason = reason
        self.pointer = pointer
        self.schema_pointer = schema_pointer
        super().__init__("bad_args:" + reason)


_TYPES = {
    "object": (dict,), "array": (list,), "string": (str,),
    "integer": (int,), "number": (int, float), "boolean": (bool,),
    "null": (type(None),),
}
_KEYWORDS = (
    "$schema", "$id", "title", "description", "type", "properties",
    "required", "additionalProperties", "items", "minItems", "maxItems",
    "uniqueItems", "minLength", "maxLength", "pattern", "minimum", "maximum",
    "enum", "const",
)
_COUNTS = ("minItems", "maxItems", "minLength", "maxLength")
_BOUND_PAIRS = (("minItems", "maxItems"), ("minLength", "maxLength"),
                ("minimum", "maximum"))


def _child(pointer: str, name: str | int) -> str:
    return pointer + "/" + str(name).replace("~", "~0").replace("/", "~1")


def _problem(reason: str, pointer: str, definition: bool) -> None:
    if definition:
        raise SchemaError("invalid_schema", schema_pointer=pointer)
    raise SchemaError(reason, pointer=pointer)


def _text(value: str, pointer: str, definition: bool) -> None:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        _problem("invalid_unicode", pointer, definition)


def _keys(value: dict, pointer: str, definition: bool) -> None:
    # Check key types before sorting, so mixed keys cannot leak a TypeError.
    if any(type(name) is not str for name in value):
        _problem("not_json", pointer, definition)
    for name in sorted(value):
        # An invalid key is diagnosed at its containing object.
        _text(name, pointer, definition)


def _enter(value: dict | list, pointer: str, depth: int,
           active: set[int], definition: bool) -> int:
    depth += 1
    if depth > MAX_DEPTH:
        _problem("depth_limit", pointer, definition)
    if id(value) in active:
        _problem("cycle", pointer, definition)
    active.add(id(value))
    return depth


def _check_json(value: Any, pointer: str, depth: int,
                active: set[int], definition: bool) -> None:
    concrete = type(value)
    if concrete is str:
        _text(value, pointer, definition)
    elif concrete is float:
        if not math.isfinite(value):
            _problem("non_finite", pointer, definition)
    elif concrete in (int, bool, type(None)):
        return
    elif concrete in (dict, list):
        depth = _enter(value, pointer, depth, active, definition)
        try:
            if concrete is dict:
                _keys(value, pointer, definition)
                for name in sorted(value):
                    _check_json(value[name], _child(pointer, name), depth,
                                active, definition)
            else:
                for index, item in enumerate(value):
                    _check_json(item, _child(pointer, index), depth,
                                active, definition)
        finally:
            active.remove(id(value))
    else:
        _problem("not_json", pointer, definition)


def _equal(left: Any, right: Any) -> bool:
    """JSON equality; native mixed int/float comparisons preserve precision."""
    left_type, right_type = type(left), type(right)
    if left_type in (int, float) and right_type in (int, float):
        return left == right
    if left_type is not right_type:
        return False
    if left_type is list:
        return len(left) == len(right) and all(
            _equal(a, b) for a, b in zip(left, right))
    if left_type is dict:
        return left.keys() == right.keys() and all(
            _equal(left[name], right[name]) for name in sorted(left))
    return left == right


def _later_duplicate(values: list) -> int | None:
    for index, value in enumerate(values):
        if any(_equal(value, prior) for prior in values[:index]):
            return index
    return None


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for name, value in pairs:
        if name in result:
            raise SchemaError("duplicate_key")
        result[name] = value
    return result


def _constant(token: str) -> Any:
    raise SchemaError("non_finite")


def _float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise SchemaError("non_finite")
    return value


def _integer(token: str) -> int:
    # Parse short chunks to avoid the interpreter's configurable digit limit,
    # without modifying process-wide settings or rounding through a float.
    negative = token.startswith("-")
    digits = token[1:] if negative else token
    value = 0
    for start in range(0, len(digits), 9):
        chunk = digits[start:start + 9]
        value = value * (10 ** len(chunk)) + int(chunk)
    return -value if negative else value


def strict_loads(raw: str | bytes) -> Any:
    """Decode one strict UTF-8 JSON value within the fixed document byte cap."""
    if type(raw) not in (str, bytes):
        raise SchemaError("input_type")
    if type(raw) is str:
        try:
            encoded = raw.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            raise SchemaError("invalid_unicode") from None
    else:
        encoded = raw
    if len(encoded) > MAX_JSON_BYTES:
        raise SchemaError("too_large")
    try:
        text = encoded.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise SchemaError("invalid_utf8") from None
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_float=_float,
                           parse_int=_integer, parse_constant=_constant)
    except SchemaError:
        raise
    except RecursionError:
        raise SchemaError("depth_limit") from None
    except (ValueError, OverflowError):
        raise SchemaError("invalid_json") from None
    try:
        _check_json(value, "", 0, set(), False)
    except SchemaError as error:
        # Decoding diagnostics deliberately expose only the root coordinate.
        raise SchemaError(error.reason) from None
    except RecursionError:
        raise SchemaError("depth_limit") from None
    return value


def _schema_node(schema: Any, pointer: str, depth: int,
                 active: set[int], patterns: dict[int, re.Pattern]) -> None:
    if type(schema) is not dict:
        _problem("invalid_schema", pointer, True)
    depth = _enter(schema, pointer, depth, active, True)
    try:
        _keys(schema, pointer, True)
        for keyword in sorted(schema):
            if keyword not in _KEYWORDS:
                raise SchemaError("unsupported_keyword",
                                  schema_pointer=_child(pointer, keyword))
        for keyword in _KEYWORDS:
            if keyword not in schema:
                continue
            operand = schema[keyword]
            location = _child(pointer, keyword)
            if keyword == "properties":
                if type(operand) is not dict:
                    _problem("invalid_schema", location, True)
                _enter(operand, location, depth, active, True)
                try:
                    _keys(operand, location, True)
                finally:
                    active.remove(id(operand))
                # Child schema contents are checked after local assertions.
                continue
            if keyword == "items":
                if type(operand) is not dict:
                    _problem("invalid_schema", location, True)
                continue
            _check_json(operand, location, depth, active, True)
            valid = True
            if keyword in ("$schema", "$id", "title", "description", "pattern"):
                valid = type(operand) is str
                if valid and keyword == "pattern":
                    try:
                        patterns[id(schema)] = re.compile(operand)
                    except (re.error, OverflowError, RecursionError):
                        valid = False
            elif keyword == "type":
                if type(operand) is str:
                    valid = operand in _TYPES
                elif type(operand) is list:
                    valid = bool(operand) and all(
                        type(name) is str and name in _TYPES for name in operand)
                    if valid:
                        valid = len(set(operand)) == len(operand)
                else:
                    valid = False
            elif keyword == "required":
                valid = type(operand) is list and all(
                    type(name) is str for name in operand)
                if valid:
                    valid = len(set(operand)) == len(operand)
            elif keyword in ("additionalProperties", "uniqueItems"):
                # Subschema-valued additionalProperties is an invalid operand,
                # diagnosed at the keyword, rather than silently interpreted.
                valid = type(operand) is bool
            elif keyword in _COUNTS:
                valid = type(operand) is int and operand >= 0
            elif keyword in ("minimum", "maximum"):
                valid = type(operand) in (int, float)
            elif keyword == "enum":
                valid = type(operand) is list and bool(operand)
                if valid:
                    duplicate = _later_duplicate(operand)
                    if duplicate is not None:
                        _problem("invalid_schema", _child(location, duplicate), True)
            if not valid:
                _problem("invalid_schema", location, True)
        for lower, upper in _BOUND_PAIRS:
            if lower in schema and upper in schema and schema[lower] > schema[upper]:
                _problem("invalid_schema", _child(pointer, upper), True)
        if "properties" in schema:
            properties = schema["properties"]
            location = _child(pointer, "properties")
            child_depth = _enter(properties, location, depth, active, True)
            try:
                for name in sorted(properties):
                    _schema_node(properties[name], _child(location, name),
                                 child_depth, active, patterns)
            finally:
                active.remove(id(properties))
        if "items" in schema:
            _schema_node(schema["items"], _child(pointer, "items"),
                         depth, active, patterns)
    finally:
        active.remove(id(schema))


def _assertions(value: Any, schema: dict[str, Any], pointer: str,
                patterns: dict[int, re.Pattern]) -> None:
    concrete = type(value)
    if "type" in schema:
        names = schema["type"]
        names = [names] if type(names) is str else names
        if not any(concrete in _TYPES[name] for name in names):
            raise SchemaError("type", pointer=pointer)
    if concrete is dict:
        properties = schema.get("properties", {})
        for name in sorted(schema.get("required", [])):
            if name not in value:
                raise SchemaError("required", pointer=_child(pointer, name))
        if schema.get("additionalProperties", True) is False:
            for name in sorted(value):
                if name not in properties:
                    raise SchemaError("additionalProperties", pointer=_child(pointer, name))
        for name in sorted(value):
            if name in properties:
                _assertions(value[name], properties[name], _child(pointer, name), patterns)
    elif concrete is list:
        for keyword, fails in (("minItems", lambda bound: len(value) < bound),
                               ("maxItems", lambda bound: len(value) > bound)):
            if keyword in schema and fails(schema[keyword]):
                raise SchemaError(keyword, pointer=pointer)
        if schema.get("uniqueItems", False):
            duplicate = _later_duplicate(value)
            if duplicate is not None:
                raise SchemaError("uniqueItems", pointer=_child(pointer, duplicate))
        if "items" in schema:
            for index, item in enumerate(value):
                _assertions(item, schema["items"], _child(pointer, index), patterns)
    elif concrete is str:
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise SchemaError("minLength", pointer=pointer)
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise SchemaError("maxLength", pointer=pointer)
        if "pattern" in schema and patterns[id(schema)].search(value) is None:
            raise SchemaError("pattern", pointer=pointer)
    elif concrete in (int, float):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaError("minimum", pointer=pointer)
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaError("maximum", pointer=pointer)
    if "enum" in schema and not any(_equal(value, item) for item in schema["enum"]):
        raise SchemaError("enum", pointer=pointer)
    if "const" in schema and not _equal(value, schema["const"]):
        raise SchemaError("const", pointer=pointer)


def validate(value: Any, schema: dict[str, Any]) -> None:
    """Check a complete schema and JSON value, then apply conjunctive assertions."""
    patterns: dict[int, re.Pattern] = {}
    _schema_node(schema, "", 0, set(), patterns)
    _check_json(value, "", 0, set(), False)
    _assertions(value, schema, "", patterns)
