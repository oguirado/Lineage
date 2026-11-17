"""Compact read of one verified prefix using the installed registry folds."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from . import journal
from .errors import LineageError
from .supervisor import _emit

LIMIT = 200


def build(*, context, registry):
    # Importing the installed memory facade supplies Services/Context and the
    # shared snapshot API. It owns all domain folding; this module only projects.
    from lineage.domain import memory
    from .registry import Context, Services
    if context.validators is not registry.validators or context.folds is not registry.folds:
        raise LineageError("bad_args", "registry context mismatch")
    if any(not callable(registry.folds.get(name)) for name in ("agents", "memory", "runs")):
        raise LineageError("internal", "required registry fold unavailable")
    ctx = Context(Services(context.home, Path(__file__).resolve().parents[2],
                           registry, token_count=None), transport="cli")
    snapshot = journal.snapshot(ctx=ctx)
    records = snapshot.state["agents"]
    identifiers = sorted(key for key in records if not key.startswith("_"))
    telemetry = {key: {"open_runs": 0, "runs_closed": 0, "last_run_verdict": None}
                 for key in identifiers[:LIMIT]}
    last = {}
    for run in snapshot.state["runs"].values():
        agent_id = run["agent_id"]
        if agent_id not in records:
            raise LineageError("internal", "run has no agent")
        if agent_id not in telemetry:
            continue
        row = telemetry[agent_id]
        closed = run["closed"]
        if closed is None:
            row["open_runs"] += 1
        else:
            row["runs_closed"] += 1
            # The run fold retains journal order. Find the latest close using
            # the committed prefix, without refolding any domain state.
            last[run["run_id"]] = agent_id
    for event in snapshot.events:
        if event["kind"] == "run.close":
            record = event["payload"]["record"]
            agent_id = last.get(record["run_id"])
            if agent_id is not None:
                telemetry[agent_id]["last_run_verdict"] = record["outcome"]["verdict"]
    agents = []
    for agent_id in identifiers[:LIMIT]:
        record = records[agent_id]
        row = {key: record[key] for key in ("agent_id", "workflow", "language", "status",
                                             "generation", "memory_gen")}
        row["agent_version"] = record["agent_version"][:12]
        row.update(telemetry[agent_id])
        if "promoted_seat" in record:
            row["promoted_seat"] = deepcopy(record["promoted_seat"])
        agents.append(row)
    return {"head": snapshot.head, "sha256": snapshot.sha256, "agents": agents,
            "truncated": len(identifiers) > LIMIT}


def main(argv, *, context, registry, stdin, stdout, stderr):
    if argv not in ([], ["--json"]):
        _emit(stdout, {"ok": False, "code": "bad_args"})
        return 2
    try:
        _emit(stdout, {"untrusted": build(context=context, registry=registry)})
        return 0
    except LineageError as exc:
        _emit(stdout, {"ok": False, "code": exc.code})
        return 3
    except Exception:
        _emit(stdout, {"ok": False, "code": "internal"})
        return 3
