"""Harness-recorded lifecycle, serialized by the room journal's own lock."""
import json
import os
import secrets

from .registry import register
from lineage.core.plan.errors import PlanError
from lineage.core.plan.fold import apply_op_event, fold_plan
from lineage.core.plan.limits import TITLE_MAX
from lineage.core.plan.ops import LIFECYCLE_REASON_MAX, validate_op_shape
from lineage.core import locking as _lock, journal as store


def agent_lifecycle(args: dict) -> dict:
    required = {"room", "agent", "state", "run_id"}
    allowed = required | {"swarm", "harness", "reason", "op_id"}
    if not isinstance(args, dict) or set(args) - allowed or not required <= set(args):
        raise store.RoomError("bad_args", "invalid lifecycle arguments")
    room, agent = args["room"], args["agent"]
    store._check_room(room)
    store._check_agent(agent)
    op = {"kind": "agent.lifecycle"}
    op.update((key, value) for key, value in args.items() if key not in ("room", "agent"))
    if "op_id" not in op:
        op["op_id"] = secrets.token_hex(16)
    try:
        op = validate_op_shape(op)
    except PlanError as exc:
        raise store.RoomError(exc.code, str(exc)) from exc
    return _commit(room, agent, op)


def _commit(room, agent, op):
    # post() cannot suppress successful folds. Share its journal lock and I/O
    # primitives instead, keeping replay, clock, admission and append together.
    rdir = store._ensure_dirs(None, room)
    epath = os.path.join(rdir, "events.jsonl")
    lpath = os.path.join(rdir, "events.lock")
    lockfd = os.open(lpath, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            os.chmod(lpath, 0o600)
        except OSError:
            pass
        _lock.lock_exclusive(lockfd)
        try:
            try:
                with open(epath, "rb") as stream:
                    data = stream.read()
            except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
                data = b""
            parsed, _ = store._parse_events_bytes(data)
            matched = store._op_identity_index(parsed, agent).get(op["op_id"])
            if matched is not None:
                if matched.get("room") != room or matched.get("op") != op or isinstance(matched.get("batch"), dict):
                    raise store.RoomError("bad_op", "op_id conflict")
                return {"ok": True, "lamport": matched["lamport"]}
            # Resolve server time only after acquiring the shared lock. No client
            # clock or process-local liveness/retirement cache is consulted.
            ts = store._resolve_ts(None, True)
            lamport = store._max_lamport_from_bytes(data) + 1
            event = {"id": "e-" + secrets.token_hex(8), "room": room, "agent": agent,
                     "act": "op", "text": "", "op": op, "lamport": lamport, "ts": ts}
            tpl_kw = store._tpl_kw(needed=store._plan_template_ids(parsed))
            try:
                state = fold_plan(parsed, **tpl_kw)
                _, result = apply_op_event(state, event, last_by_agent=store._op_max_activity(parsed), **tpl_kw)
            except PlanError as exc:
                raise store.RoomError(exc.code, str(exc)) from exc
            if result.get("noop"):
                return {"ok": True, "lamport": result["lamport"]}
            separator = b"\n" if data and not data.endswith(b"\n") else b""
            payload = separator + (json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
            if len(data) + len(payload) > store.CAP:
                raise store.RoomError("room_full", "room file cap exceeded")
            fd = os.open(epath, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
            try:
                try:
                    os.chmod(epath, 0o600)
                except OSError:
                    pass
                store._write_all(fd, payload, len(data))
                try:
                    os.fsync(fd)
                except OSError as exc:
                    try:
                        os.ftruncate(fd, len(data))
                    except OSError:
                        pass
                    raise store.RoomError("internal", str(exc)) from exc
            finally:
                os.close(fd)
            return {"ok": True, "lamport": lamport}
        finally:
            try:
                _lock.unlock(lockfd)
            except OSError:
                pass
    except OSError as exc:
        raise store.RoomError("internal", str(exc)) from exc
    finally:
        os.close(lockfd)


register({
    "name": "agent_lifecycle",
    "description": "Record caller-asserted agent deployment, liveness or termination in a room.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "room": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{0,47}$"},
            "agent": {"type": "string", "pattern": "^[a-z0-9][a-z0-9._-]{0,47}$"},
            "state": {"type": "string", "enum": ["deployed", "alive", "finished", "failed"]},
            "run_id": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"},
            "swarm": {"type": "string", "minLength": 1, "maxLength": TITLE_MAX},
            "harness": {"type": "string", "minLength": 1, "maxLength": TITLE_MAX},
            "reason": {"type": "string", "maxLength": LIFECYCLE_REASON_MAX},
            "op_id": {"type": "string", "pattern": "^[A-Za-z0-9_-]{8,64}$"},
        },
        "required": ["room", "agent", "state", "run_id"],
        "additionalProperties": False,
    },
}, agent_lifecycle)
