"""One-shot family carrier using the shared application and recipient mailbox."""
from __future__ import annotations

from collections.abc import Sequence
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import dataclass
import sys

from . import app, envelope as wire, journal, registry as extensions
from .errors import LineageError
from .registry import Registry


@dataclass(frozen=True)
class _JSONContext(app.CallContext):
    authority: str = "tool"
    transport: str = "json"


@dataclass(frozen=True)
class _Runtime:
    context: app.CallContext
    registry: Registry


def _runtime(ctx=None, registry=None):
    if isinstance(ctx, _Runtime):
        return ctx
    if registry is None:
        registry = extensions.load()
    if ctx is None:
        ctx = app.create_context(registry=registry)
    if not isinstance(ctx, app.CallContext) or not isinstance(registry, Registry):
        raise LineageError("bad_args")
    if ctx.validators != registry.validators or ctx.folds != registry.folds:
        raise LineageError("bad_args")
    # Use the registry's own mapping identities, as required by app.dispatch.
    context = _JSONContext(ctx.home, registry.validators, registry.folds)
    return _Runtime(context, registry)


def _error(code):
    return {"ok": False, "code": code if code in app.ERROR_CODES else "internal"}


def _exception(exc):
    if isinstance(exc, (LineageError, app.ToolError)):
        if exc.code == 'bad_op' and getattr(exc, 'detail', None) == 'cancelled by order':
            return {'ok': False, 'code': 'bad_op', 'detail': 'cancelled by order'}
        return _error(exc.code)
    return _error("internal")


def _receipt(identity, result, envelope=None):
    value = {"schema": wire.SCHEMA, "id": identity, "result": deepcopy(result)}
    if envelope is not None and "correlation_id" in envelope:
        value["correlation_id"] = envelope["correlation_id"]
    wire._validate_schema({**value, "result": _wire_result(result)}, "family_receipt.schema.json")
    return value


def validate_request(raw, endpoint, filename_id=None):
    """Admit the transport extension without changing any tool schema."""
    value = wire.decode(raw)
    payload = value.get('payload')
    dry_run = None
    if type(payload) is dict and 'dry_run' in payload:
        if value.get('kind') != 'call' or type(payload['dry_run']) is not bool:
            raise wire.InvalidEnvelope('invalid dry-run control')
        dry_run = payload.pop('dry_run')
    value = wire.validate(wire.canonical(value), endpoint, filename_id)
    if dry_run is not None:
        value['payload']['dry_run'] = dry_run
    return value


def _wire_result(result):
    """Validate OPC1 additions separately from the immutable K0 wire schema."""
    value = deepcopy(result)
    data = value.get('untrusted') if type(value) is dict else None
    if type(data) is not dict:
        return value
    if 'dry_run' in data:
        integer = {'type': 'integer', 'minimum': 0, 'maximum': 9007199254740991}
        event = {'type': 'object', 'properties': {
            'kind': {'type': 'string', 'minLength': 1, 'maxLength': 128},
            'payload_sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
            'expected_head': integer},
            'required': ['kind', 'payload_sha256', 'expected_head'], 'additionalProperties': False}
        shape = {'type': 'object', 'properties': {
            'dry_run': {'const': True}, 'risk': {'enum': list(app._RISKS)},
            'expected_head': integer, 'events': {'type': 'array', 'items': event, 'maxItems': 1}},
            'required': ['dry_run', 'risk', 'expected_head', 'events'], 'additionalProperties': False}
        try:
            wire.boundary.validate(data, shape)
        except wire.boundary.SchemaError:
            raise wire.InvalidEnvelope('invalid preview') from None
        return {'ok': False, 'code': 'bad_op'}  # Only for validating the outer receipt.
    if 'unverified' in data:
        if not {'valid', 'head', 'sha256', 'issues', 'torn_tail_bytes'} <= data.keys():
            raise wire.InvalidEnvelope('unverified scope on an unrelated result')
        try:
            wire.boundary.validate(data.pop('unverified'), {'type': 'array', 'items': {
                'type': 'object', 'properties': {
                    'scope': {'type': 'string', 'minLength': 1, 'maxLength': 1024},
                    'reason': {'type': 'string', 'minLength': 1, 'maxLength': 2048}},
                'required': ['scope', 'reason'], 'additionalProperties': False}})
        except wire.boundary.SchemaError:
            raise wire.InvalidEnvelope('invalid unverified scope') from None
    if data.get('protocol') == wire.SCHEMA and type(data.get('tools')) is list:
        for descriptor in data['tools']:
            if type(descriptor) is not dict:
                raise wire.InvalidEnvelope('invalid descriptor')
            annotations = descriptor.pop('annotations', None)
            if annotations is not None:
                expected = {'readOnlyHint', 'destructiveHint', 'idempotentHint', 'openWorldHint', 'lineage_risk'}
                if (type(annotations) is not dict or set(annotations) != expected
                        or annotations['lineage_risk'] not in app._RISKS
                        or any(type(annotations[key]) is not bool for key in expected - {'lineage_risk'})):
                    raise wire.InvalidEnvelope('invalid annotations')
    return value


# The installed ToolSpec exposes mutating, rather than K0's effect enum. These
# two external operations are explicitly classified by the frozen contract.
_EXTERNAL = frozenset({"openfresnel_probe", "openfresnel_spawn"})
_DEFAULTS = {
    "skill_list": {"include_retired": False},
    "agent_list": {"include_retired": False, "limit": 100},
    "agent_brief": {"memory_arm": "own"},
    "lineage_tree": {"include_retired": True},
    "memory_route": {"limit": 10},
    "ledger_events": {"after": 0, "limit": 100, "wait_ms": 0},
    "memory_history": {"after": 0, "limit": 100, "wait_ms": 0},
}


def _effect(name, runtime):
    spec = runtime.registry.tools[name]
    if name in _EXTERNAL:
        if not spec.mutating:
            raise LineageError("bad_args")
        return "external"
    # ledger_export produces a projection, not a journal mutation.
    if name == "ledger_export":
        return "read"
    return "journal" if spec.mutating else "read"


def _admit(value, config, runtime):
    value = validate_request(wire.canonical(value), value.get("target"))
    config = wire.configuration(wire.canonical(config), value["target"])
    if value["source"] not in config["sources"]:
        raise LineageError("bad_args")
    if value["kind"] == "capabilities":
        return value, None, None
    if value["kind"] == "events.read":
        name = "ledger_events"
        args = {**deepcopy(value["payload"]), "after": value["after"]}
    else:
        name = value["payload"]["tool"]
        args = deepcopy(value["payload"]["args"])
    if name not in config["tools"] or name not in runtime.registry.tools:
        raise LineageError("bad_args")
    if {"agent", "op_id"} & args.keys():
        raise LineageError("bad_args")
    # Empty lane filters mean all kinds; the frozen tool schema requires a
    # nonempty list whenever the optional filter is present.
    if name == "ledger_events" and args.get("kinds") == []:
        del args["kinds"]
    args["agent"] = value["agent"]
    if _effect(name, runtime) != "read":
        args["op_id"] = wire.operation_id(value)
    properties = runtime.registry.tools[name].input_schema.get("properties", {})
    for key, item in _DEFAULTS.get(name, {}).items():
        if key in properties:
            args.setdefault(key, deepcopy(item))
    for key in ("overlays", "evidence"):
        if key in properties:
            args.setdefault(key, [])
    if "run_id" in value and "run_id" in args and value["run_id"] != args["run_id"]:
        raise LineageError("bad_args")
    try:
        wire.boundary.validate(args, runtime.registry.tools[name].input_schema)
    except wire.boundary.SchemaError:
        raise LineageError("bad_args") from None
    return value, name, args


def _result_valid(result):
    try:
        _receipt("invalid0", result)
        return True
    except (wire.InvalidEnvelope, OSError):
        return False


def _valid_for(result, name):
    if not _result_valid(result):
        return False
    if "untrusted" not in result:
        return True
    names = [b["properties"]["tool"]["const"] for b in wire._call_branches()]
    alternatives = wire._schema("family_receipt.schema.json")["properties"]["result"]["oneOf"][0]["properties"]["untrusted"]["anyOf"]
    try:
        index = len(names) if name is None else names.index(name)
        if result['untrusted'].get('dry_run') is True:
            _wire_result(result)
            return True
        wire._check(_wire_result(result)["untrusted"], alternatives[index], "family_receipt.schema.json")
        return True
    except (wire.InvalidEnvelope, ValueError, IndexError):
        return False


def _dispatch(value, config, runtime):
    value, name, args = _admit(value, config, runtime)
    if name is None:
        descriptors = [item for item in app.list_tools(registry=runtime.registry)
                       if item["name"] in config["tools"]]
        result = {"untrusted": {"protocol": wire.SCHEMA,
                  "kinds": ["capabilities", "events.read", "call"],
                  "tools": descriptors, "health": "ready"}}
    else:
        if name == "ledger_events":
            # A backend may classify unsafe journal objects as bad_args. At the
            # wire boundary this is unavailable storage, not malformed input.
            # Release the verified snapshot before entering the read handler.
            try:
                journal.snapshot(runtime.context.home)
            except LineageError as exc:
                return _error("internal" if exc.code == "bad_args" else exc.code)
        context = _JSONContext(runtime.context.home, runtime.registry.validators,
                               runtime.registry.folds, value["agent"], args.get("op_id"))
        result = (app.preview if value["payload"].get("dry_run", False) else app.dispatch)(
            name, args, context=context, registry=runtime.registry).payload
        if type(result) is dict and result.get("ok") is False:
            # Domain diagnostics are optional. Do not propagate untrusted text
            # or app's structured, non-wire schema diagnostics into this lane.
            if result.get('code') == 'bad_op' and result.get('detail') == 'cancelled by order':
                result = {'ok': False, 'code': 'bad_op', 'detail': 'cancelled by order'}
            else:
                result = _error(result.get("code"))
    if not _valid_for(result, name):
        return _error("internal")
    return deepcopy(result)


def dispatch(envelope: wire.JSONObject, config: wire.JSONObject, *, ctx) -> wire.JSONObject:
    """Serialize direct deliveries too; caller config must match disk admission."""
    from .family import Mailbox, Refusal, UnsafeEntry
    box = None
    result = _error("internal")
    owned = False
    try:
        runtime = _runtime(ctx)
        value = validate_request(wire.canonical(envelope), envelope.get("target"))
        box = Mailbox(value["target"], ctx=runtime)
        box.open()
        owned = True
        current = box._configuration()
        if wire.configuration(wire.canonical(config), value["target"]) != current:
            result = _error("bad_args")
        else:
            result = box.dispatch(value)
    except (wire.InvalidEnvelope, Refusal):
        result = _error("bad_args")
    except UnsafeEntry:
        result = _error("internal" if owned else "bad_args")
    except Exception as exc:
        result = _exception(exc)
    finally:
        if box is not None:
            try:
                box.release()
            except Exception:
                result = _error("internal")
    return result


def _status(result):
    if "untrusted" in result:
        return 0
    return 2 if result.get("code") == "bad_args" else 3


def main(argv: Sequence[str] | None = None, *, context=None, registry=None,
         stdin=None, stdout=None, stderr=None) -> int:
    """CLI delegate; malformed input requires neither registry nor runtime home."""
    from .family import Mailbox, Refusal, UnsafeEntry, _diagnostic
    stdin = getattr(sys.stdin, "buffer", sys.stdin) if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    identity, value, box = "invalid0", None, None
    owned = False
    result = _error("bad_args")
    try:
        args = list(sys.argv[1:] if argv is None else argv)
        raw = stdin.read(wire.MAX_REQUEST_BYTES + 1)
        if type(raw) is str:
            raw = raw.encode("utf-8")
        decoded = wire.decode(raw)
        candidate = decoded.get("id")
        if type(candidate) is str and wire.ID_RE.fullmatch(candidate):
            identity = candidate
        if args:
            raise wire.InvalidEnvelope("unexpected arguments")
        value = validate_request(raw, decoded.get("target"))
        with redirect_stdout(stderr):
            runtime = _runtime(context, registry)
            box = Mailbox(value["target"], ctx=runtime)
            box.open()
            owned = True
            result = box._receive(value)
    except Refusal as exc:
        stderr.write(_diagnostic("json", exc))
        result = _error("bad_args")
    except (wire.InvalidEnvelope, UnicodeError):
        result = _error("bad_args")
    except UnsafeEntry as exc:
        stderr.write(_diagnostic("json", exc))
        result = _error("internal" if owned else "bad_args")
    except Exception as exc:
        result = _exception(exc)
    finally:
        if box is not None:
            try:
                box.release()
            except Exception:
                result = _error("internal")
    try:
        receipt = _receipt(identity, result, value)
        stdout.write((wire.canonical(receipt) + b"\n").decode("utf-8"))
        stdout.flush()
    except Exception:
        return 3
    return _status(result)


if __name__ == "__main__":
    raise SystemExit(main())
