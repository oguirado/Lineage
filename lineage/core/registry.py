"""Deterministic, atomic discovery of installed Lineage extensions."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
import importlib
from functools import wraps
import pkgutil
import re
from types import MappingProxyType
from typing import Any, Protocol, TYPE_CHECKING

from .schema import SchemaError, validate

if TYPE_CHECKING:
    from .app import CallContext

Validator = Callable[[tuple[dict[str, Any], ...], dict[str, Any]], None]
Fold = Callable[[Any, dict[str, Any]], Any]


class Handler(Protocol):
    def __call__(self, args: dict[str, Any], *, context: CallContext) -> Any: ...


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Handler
    mutating: bool
    @property
    def risk(self) -> str:
        risk = {"skill_retire": "irreversible", "agent_retire": "irreversible",
                "openfresnel_spawn": "send", "openfresnel_probe": "send",
                "ledger_export": "prepare"}.get(self.name)
        return risk or ("publish" if self.mutating else "read")


def _operable_handler(spec):
    original = getattr(spec.handler, '_operable_original', spec.handler)

    @wraps(original)
    def invoke(args, *positional, **keywords):
        from . import app
        context = positional[0] if positional else keywords.get('context', keywords.get('ctx'))
        return app._invoke_operable(spec, original, args, positional, keywords, context)

    invoke._operable_original = original
    return invoke


@dataclass(frozen=True)
class Registry:
    tools: Mapping[str, ToolSpec]
    validators: Mapping[str, Validator]
    folds: Mapping[str, Fold]

    def __post_init__(self) -> None:
        # Detach schemas from the importing modules, as well as all maps.
        tools = {name: ToolSpec(spec.name, spec.description,
                               deepcopy(spec.input_schema), spec.handler,
                               spec.mutating)
                 for name, spec in self.tools.items()}
        object.__setattr__(self, "tools", MappingProxyType(tools))
        object.__setattr__(self, "validators", MappingProxyType(dict(self.validators)))
        object.__setattr__(self, "folds", MappingProxyType(dict(self.folds)))


class RegistryError(Exception):
    code = "bad_args"

    def __init__(self, reason: str, *, name: str | None = None) -> None:
        self.detail: dict[str, Any] = {"reason": reason}
        if name is not None:
            self.detail["name"] = name
        super().__init__("bad_args")


def _descriptor(spec: Any) -> None:
    if (not isinstance(spec, ToolSpec)
            or type(spec.name) is not str
            or re.fullmatch(r"[a-z][a-z0-9_]*", spec.name) is None
            or type(spec.description) is not str or not spec.description
            or type(spec.mutating) is not bool or not callable(spec.handler)):
        raise RegistryError("bad_descriptor")
    try:
        validate(spec.description, {})
    except SchemaError:
        raise RegistryError("bad_descriptor", name=spec.name) from None
    if type(spec.input_schema) is not dict or spec.input_schema.get("type") != "object":
        raise RegistryError("bad_schema", name=spec.name)
    try:
        # U02 preflights the entire schema before checking the instance. Its
        # schema_pointer distinguishes definition failures from instance errors.
        validate({}, spec.input_schema)
    except SchemaError as exc:
        if exc.schema_pointer is not None:
            raise RegistryError("bad_schema", name=spec.name) from None


def load(*, package: str = "lineage.ext") -> Registry:
    try:
        root = importlib.import_module(package)
    except Exception:
        raise RegistryError("import_failed") from None
    if not hasattr(root, "__path__"):
        raise RegistryError("bad_extension")
    try:
        modules = sorted(pkgutil.iter_modules(root.__path__, root.__name__ + "."),
                         key=lambda item: item.name)
    except Exception:
        raise RegistryError("import_failed") from None
    tools: dict[str, ToolSpec] = {}
    validators: dict[str, Validator] = {}
    folds: dict[str, Fold] = {}
    for item in modules:
        if item.ispkg:
            raise RegistryError("bad_extension", name=item.name)
        try:
            module = importlib.import_module(item.name)
        except Exception:
            raise RegistryError("import_failed", name=item.name) from None
        if (not hasattr(module, "TOOLS") or type(module.TOOLS) is not tuple
                or not isinstance(getattr(module, "VALIDATORS", None), Mapping)
                or not isinstance(getattr(module, "FOLDS", None), Mapping)):
            raise RegistryError("bad_extension", name=item.name)
        for spec in module.TOOLS:
            _descriptor(spec)
            if spec.name in tools:
                raise RegistryError("duplicate_tool", name=spec.name)
            tools[spec.name] = spec
        for exported, target, duplicate in (
                (module.VALIDATORS, validators, "duplicate_validator"),
                (module.FOLDS, folds, "duplicate_fold")):
            for name, callback in exported.items():
                if type(name) is not str or not name or not callable(callback):
                    raise RegistryError("bad_extension", name=item.name)
                try:
                    validate(name, {})
                except SchemaError:
                    raise RegistryError("bad_extension", name=item.name) from None
                if name in target:
                    raise RegistryError(duplicate, name=name)
                target[name] = callback
    return Registry(tools, validators, folds)
