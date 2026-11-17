"""Strict family envelopes and frozen-schema validation without dependencies."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
from typing import TypeAlias

from . import schema as boundary
from .errors import JSONValue

JSONObject: TypeAlias = dict[str, JSONValue]
SCHEMA = "lineage.family/1"
MAX_REQUEST_BYTES = 65536
MAX_DEPTH = boundary.MAX_DEPTH
MAX_INTEGER = 9007199254740991
ID_RE = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
ENDPOINT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


class InvalidEnvelope(ValueError):
    """Invalid wire data; exception messages never include client content."""


def _require(condition: bool) -> None:
    if not condition:
        raise InvalidEnvelope("invalid family data")


def _json(value: JSONValue, depth: int = 0, active: set[int] | None = None) -> None:
    active = set() if active is None else active
    kind = type(value)
    if kind is str:
        value.encode("utf-8", errors="strict")
    elif kind is int:
        _require(-MAX_INTEGER <= value <= MAX_INTEGER)
    elif kind is float:
        _require(math.isfinite(value))
    elif kind in (bool, type(None)):
        return
    elif kind in (dict, list):
        _require(depth < MAX_DEPTH and id(value) not in active)
        active.add(id(value))
        try:
            if kind is dict:
                for key, item in value.items():
                    _require(type(key) is str)
                    _json(key, depth + 1, active)
                    _json(item, depth + 1, active)
            else:
                for item in value:
                    _json(item, depth + 1, active)
        finally:
            active.remove(id(value))
    else:
        raise InvalidEnvelope("invalid JSON value")


def canonical(value: JSONValue) -> bytes:
    try:
        _json(value)
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise InvalidEnvelope("invalid JSON value") from None


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value)
        value[key] = item
    return value


def _constant(value):
    raise InvalidEnvelope("invalid JSON number")


def _parse(raw: bytes, *, bounded: bool = True) -> JSONObject:
    try:
        _require(type(raw) is bytes)
        if bounded:
            _require(len(raw) <= MAX_REQUEST_BYTES)
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=_constant)
        _require(type(value) is dict)
        _json(value)
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise InvalidEnvelope("invalid JSON object") from None


def decode(raw: bytes) -> JSONObject:
    return _parse(raw)


@lru_cache(maxsize=16)
def _schema(name: str) -> JSONObject:
    # Schema documents are trusted repository data, not bounded request records.
    _require(bool(re.fullmatch(r"[a-z_]+\.schema\.json", name)))
    path = Path(__file__).resolve().parents[2] / "schemas" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _matches(value, shape, base):
    try:
        _check(value, shape, base)
        return True
    except InvalidEnvelope:
        return False


def _check(value, shape, base):
    """Compose the frozen schemas around the integrated structural validator.

    U02 validates structural keywords. Frozen family schemas also use references,
    composition and pattern properties, which are handled here privately.
    """
    if type(shape) is bool:
        _require(shape)
        return
    _require(type(shape) is dict)
    if "$ref" in shape:
        filename, _, fragment = shape["$ref"].partition("#")
        target_base = filename or base
        target = _schema(target_base)
        if fragment:
            _require(fragment.startswith("/"))
            for name in fragment[1:].split("/"):
                target = target[name.replace("~1", "/").replace("~0", "~")]
        _check(value, target, target_base)
    structural_keywords = {"$schema", "$id", "title", "description", "type",
                           "required", "minItems", "maxItems", "uniqueItems",
                           "minLength", "maxLength", "pattern", "minimum",
                           "maximum", "enum", "const"}
    structural = {key: item for key, item in shape.items()
                  if key in structural_keywords}
    # Descendants can contain composition unsupported by the U02 preflight.
    if "properties" in shape:
        structural["properties"] = {key: {} for key in shape["properties"]}
    try:
        boundary.validate(value, structural)
    except boundary.SchemaError:
        raise InvalidEnvelope("schema mismatch") from None
    if type(value) is dict:
        props = shape.get("properties", {})
        patterns = shape.get("patternProperties", {})
        if "maxProperties" in shape:
            _require(len(value) <= shape["maxProperties"])
        for key, item in value.items():
            if "propertyNames" in shape:
                _check(key, shape["propertyNames"], base)
            covered = key in props
            if covered:
                _check(item, props[key], base)
            for pattern, subshape in patterns.items():
                if re.search(pattern, key):
                    covered = True
                    _check(item, subshape, base)
            if not covered:
                additional = shape.get("additionalProperties", True)
                _check(item, additional, base)
    if type(value) is list and "items" in shape:
        for item in value:
            _check(item, shape["items"], base)
    if type(value) in (int, float):
        if "exclusiveMinimum" in shape:
            _require(value > shape["exclusiveMinimum"])
        if "exclusiveMaximum" in shape:
            _require(value < shape["exclusiveMaximum"])
    for branch in shape.get("allOf", []):
        _check(value, branch, base)
    for keyword in ("anyOf", "oneOf"):
        if keyword in shape:
            matches = sum(_matches(value, branch, base) for branch in shape[keyword])
            _require(matches == 1 if keyword == "oneOf" else matches > 0)
    if "not" in shape:
        _require(not _matches(value, shape["not"], base))
    if "if" in shape:
        branch = "then" if _matches(value, shape["if"], base) else "else"
        if branch in shape:
            _check(value, shape[branch], base)


def _validate_schema(value, name):
    try:
        _json(value)
        _check(value, _schema(name), name)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError):
        raise InvalidEnvelope("schema mismatch") from None


def operation_id(value: JSONObject) -> str:
    identity = "\0".join(value[key] for key in ("source", "target", "id"))
    return "lin-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:44]


def digest(value: JSONObject) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _call_branches():
    return _schema("family_envelope.schema.json")["allOf"][2]["then"]["properties"]["payload"]["oneOf"]


def configuration(raw: bytes, endpoint: str) -> JSONObject:
    value = decode(raw)
    _require(set(value) == {"endpoint", "sources", "tools"})
    _require(type(endpoint) is str and ENDPOINT_RE.fullmatch(endpoint) is not None)
    _require(value["endpoint"] == endpoint)
    tools = {branch["properties"]["tool"]["const"] for branch in _call_branches()}
    for name in ("sources", "tools"):
        items = value[name]
        _require(type(items) is list)
        _require(all(type(item) is str for item in items))
        _require(len(items) == len(set(items)))
        if name == "sources":
            _require(all(ENDPOINT_RE.fullmatch(item) is not None for item in items))
        else:
            _require(set(items) <= tools)
    return deepcopy(value)


def validate(raw: bytes, endpoint: str, filename_id: str | None = None) -> JSONObject:
    value = decode(raw)
    _validate_schema(value, "family_envelope.schema.json")
    _require(value["target"] == endpoint)
    if filename_id is not None:
        _require(value["id"] == filename_id)
    if value["kind"] == "call":
        args = value["payload"]["args"]
        _require(not {"agent", "op_id"} & args.keys())
        if "run_id" in value and "run_id" in args:
            _require(value["run_id"] == args["run_id"])
    return deepcopy(value)
