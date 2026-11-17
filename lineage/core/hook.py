"""Observational Claude Code hooks; identities are caller-asserted."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .schema import MAX_JSON_BYTES, SchemaError, strict_loads, validate
from .supervisor import _Parser, _call, _closing, _emit, _opening

_EVENTS = {"SessionStart", "SessionEnd", "SubagentStart", "SubagentStop", "Stop", "StopFailure"}
_BINDING = {"type": "object", "properties": {
    "agent_id": {"type": "string", "pattern": r"^[a-z][a-z0-9-]{2,63}(?![\s\S])"},
    "seat": {"type": "object", "properties": {
        "model": {"type": "string", "minLength": 1, "maxLength": 128},
        "effort": {"type": "string", "minLength": 1, "maxLength": 32,
                   "pattern": r"^[a-z0-9_-]+(?![\s\S])"},
        "mode": {"enum": ["headless", "interactive"]}},
        "required": ["model", "effort", "mode"], "additionalProperties": False}},
    "required": ["agent_id", "seat"], "additionalProperties": False}


def _map(path):
    if path is None:
        return {}
    with Path(path).open("rb") as stream:
        mapping = strict_loads(stream.read(MAX_JSON_BYTES + 1))
    if type(mapping) is not dict or set(mapping) - {"session", "sessions", "agent_types"}:
        raise ValueError("invalid map")
    if "session" in mapping:
        validate(mapping["session"], _BINDING)
    for key in ("sessions", "agent_types"):
        entries = mapping.get(key, {})
        if type(entries) is not dict:
            raise ValueError("invalid map")
        for name, value in entries.items():
            if not name:
                raise ValueError("invalid map")
            validate(value, _BINDING)
    return mapping


def _input(stdin):
    value = strict_loads(stdin.read(MAX_JSON_BYTES + 1))
    if type(value) is not dict:
        raise ValueError("invalid hook")
    for key in ("session_id", "transcript_path", "cwd", "hook_event_name"):
        if type(value.get(key)) is not str or not value[key]:
            raise ValueError("invalid hook")
    event = value["hook_event_name"]
    for key in ("agent_id", "agent_type", "last_assistant_message"):
        if key in value and type(value[key]) is not str:
            raise ValueError("invalid hook")
    if event in {"SubagentStart", "SubagentStop"}:
        if not value.get("agent_id") or not value.get("agent_type"):
            raise ValueError("invalid subagent hook")
    return value


def main(argv, *, context, registry, stdin, stdout, stderr):
    run_id = None
    try:
        parser = _Parser(add_help=False, allow_abbrev=False)
        parser.add_argument("--map")
        parser.add_argument("--verbose", action="store_true")
        options = parser.parse_args(argv)
        payload = _input(stdin)
        mapping = _map(options.map or os.environ.get("LINEAGE_HOOK_MAP") or None)
        event = payload["hook_event_name"]
        subagent = event in {"SubagentStart", "SubagentStop"} or bool(payload.get("agent_id"))
        binding = (mapping.get("agent_types", {}).get(payload.get("agent_type")) if subagent
                   else mapping.get("sessions", {}).get(payload["session_id"], mapping.get("session")))
        if event not in _EVENTS or binding is None:
            if options.verbose:
                stderr.write("hook ignored: unmapped identity or unsupported event\n")
            return 0
        identity = [payload["session_id"], "subagent" if subagent else "session",
                    payload["agent_id"] if subagent else "session"]
        import json
        digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False,
            separators=(",", ":")).encode("utf-8")).hexdigest()
        run_id = "hook-" + digest[:48]
        agent_id = binding["agent_id"]
        if event in {"SessionStart", "SubagentStart"}:
            agent = _call("agent_get", {"agent_id": agent_id}, context=context, registry=registry)
            if agent.failure is not None:
                _emit(stderr, {"run_id": run_id, **agent.payload})
                return agent.exit_code
            result = _call("run_open", _opening(run_id, agent_id, binding["seat"],
                {"id": run_id, "kind": "harness", "language":
                 agent.payload["untrusted"]["record"]["language"]}), context=context, registry=registry)
        else:
            message = payload.get("last_assistant_message")
            if message is not None:
                message_hash = hashlib.sha256(message.encode("utf-8")).hexdigest()
                result = _call("run_beat", {"run_id": run_id, "agent": agent_id,
                    "op_id": run_id + "/message", "progress": "last_assistant_message_sha256=" + message_hash},
                    context=context, registry=registry)
                if result.failure is not None:
                    _emit(stderr, {"run_id": run_id, **result.payload})
                    return result.exit_code
            result = _call("run_close", _closing(run_id, agent_id,
                "error" if event == "StopFailure" else "green"), context=context, registry=registry)
        if result.failure is not None:
            _emit(stderr, {"run_id": run_id, **result.payload})
        return result.exit_code
    except (OSError, ValueError, TypeError, SchemaError, UnicodeError):
        _emit(stderr, {"ok": False, "code": "bad_args"})
        return 2
    except Exception:
        _emit(stderr, {"ok": False, "code": "internal", **({"run_id": run_id} if run_id else {})})
        return 3
