"""Deterministic telemetry from committed birth and run-close records.

Full seat identities and memory arms remain separate. Declared outcomes are
counts, without any inference of correctness, credit or promotion eligibility.
"""
from collections.abc import Sequence
from copy import deepcopy
import math
import re

from lineage.core import journal
from lineage.core.errors import LineageError

METRICS = ("tokens_in", "tokens_out", "tokens_cache", "duration_ms", "cost_micro_usd")
VERDICTS = ("ADMIT", "HOLD", "red", "green", "error")
WORKFLOWS = frozenset(("develop", "test", "review", "harden", "research", "orchestrate"))
_AGENT = re.compile(r"[a-z][a-z0-9-]{2,63}")
_HASH = re.compile(r"[0-9a-f]{64}")


def _require(ok):
    if not ok:
        raise LineageError("internal", "invalid consumed ledger record")


def _matches(pattern, value):
    return type(value) is str and pattern.fullmatch(value) is not None


def _integer(value):
    _require(type(value) is int and value >= 0)
    return value


def _add(left, right):
    return _integer(left + right)


def _text(value):
    _require(type(value) is str and bool(value))
    try:
        value.encode("utf-8", "strict")
    except UnicodeError:
        _require(False)
    return value


def _record(event):
    _require(type(event) is dict and type(event.get("payload")) is dict)
    record = event["payload"].get("record")
    _require(type(record) is dict)
    return record


def _birth(record):
    identifier = record.get("agent_id")
    _require(_matches(_AGENT, identifier) and identifier not in ("operator", "system"))
    _require(type(record.get("workflow")) is str and record["workflow"] in WORKFLOWS)
    language = _text(record.get("language"))
    _require(language not in (".", "..") and not any(c in language for c in ("/", "\\", "\x00"))
             and re.match(r"[A-Za-z]:", language) is None)
    return identifier


def agent_records(events):
    """Return detached, validated birth records; no payload aliases are accepted."""
    result = {}
    for event in events:
        _require(type(event) is dict)
        if event.get("kind") == "agent.born":
            record = _record(event)
            identifier = _birth(record)
            _require(identifier not in result)
            result[identifier] = deepcopy(record)
    return result


def _seat(value):
    _require(type(value) is dict and set(value) == {"model", "effort", "mode"})
    for name in ("model", "effort", "mode"):
        _text(value[name])


def fold_scorecards(events: Sequence[dict], *, agent_id=None) -> list[dict]:
    """Validate every consumed close and return sorted, fully detached series."""
    if agent_id is not None and not _matches(_AGENT, agent_id):
        raise LineageError("bad_args", "invalid agent id")
    born, closed, series = {}, set(), {}
    for event in events:
        _require(type(event) is dict)
        kind = event.get("kind")
        if kind == "agent.born":
            record = _record(event)
            identifier = _birth(record)
            _require(identifier not in born)
            born[identifier] = record
        elif kind == "run.close":
            run = _record(event)
            identifier, run_id = run.get("agent_id"), run.get("run_id")
            _require(_matches(_AGENT, identifier) and identifier in born)
            _text(run_id)
            _require(run_id not in closed)
            closed.add(run_id)
            version = run.get("agent_version")
            _require(_matches(_HASH, version))
            seat, arm = run.get("seat"), run.get("memory_arm")
            _seat(seat)
            _require(arm in ("none", "own", "inherited"))
            outcome, cost = run.get("outcome"), run.get("cost")
            _require(type(outcome) is dict and {"verdict", "repair_loops", "findings"} <= set(outcome))
            verdict = outcome["verdict"]
            _require(type(verdict) is str and verdict in VERDICTS)
            _integer(outcome["repair_loops"])
            findings = outcome["findings"]
            _require(type(findings) is dict and set(findings) == {"confirmed", "refuted"})
            for value in findings.values():
                _integer(value)
            _require(type(cost) is dict and set(cost) == set(METRICS))
            for value in cost.values():
                if value is not None:
                    _integer(value)
            key = (identifier, seat["model"], seat["effort"], seat["mode"], arm)
            if key not in series:
                series[key] = {
                    "schema": "lineage.scorecard.row/v1", "agent_id": identifier,
                    "seat": deepcopy(seat), "memory_arm": arm, "run_ids": [],
                    "agent_versions": [], "n_runs": 0,
                    "outcomes": dict.fromkeys(VERDICTS, 0), "repair_loops": 0,
                    "findings": {"confirmed": 0, "refuted": 0},
                    "cost": {name: {"known": 0, "unknown": 0, "total": None, "mean": None}
                             for name in METRICS},
                }
            row = series[key]
            row["run_ids"].append(run_id)
            row["agent_versions"].append(version)
            row["n_runs"] = _add(row["n_runs"], 1)
            row["outcomes"][verdict] = _add(row["outcomes"][verdict], 1)
            row["repair_loops"] = _add(row["repair_loops"], outcome["repair_loops"])
            for name, value in findings.items():
                row["findings"][name] = _add(row["findings"][name], value)
            for name, value in cost.items():
                metric = row["cost"][name]
                if value is None:
                    metric["unknown"] = _add(metric["unknown"], 1)
                else:
                    metric["known"] = _add(metric["known"], 1)
                    metric["total"] = _add(0 if metric["total"] is None else metric["total"], value)
    if agent_id is not None and agent_id not in born:
        raise LineageError("no_agent", "agent absent from authoritative births")
    result = []
    for key in sorted(series):
        row = series[key]
        row["run_ids"].sort()
        row["agent_versions"] = sorted(set(row["agent_versions"]))
        for metric in row["cost"].values():
            if metric["known"]:
                try:
                    mean = metric["total"] / metric["known"]
                    _require(math.isfinite(mean))
                except (OverflowError, ValueError):
                    raise LineageError("internal", "metric mean is not finite") from None
                metric["mean"] = mean
        if agent_id is None or key[0] == agent_id:
            result.append(row)
    return result


def _groups(rows):
    """Expose counts and means, keeping unbounded totals private to the fold."""
    return [{"seat": deepcopy(row["seat"]), "memory_arm": row["memory_arm"],
             "runs": row["n_runs"],
             "successes": row["outcomes"]["ADMIT"] + row["outcomes"]["green"],
             "unknown_costs": row["cost"]["cost_micro_usd"]["unknown"],
             "mean_cost_micro_usd": row["cost"]["cost_micro_usd"]["mean"],
             "mean_duration_ms": row["cost"]["duration_ms"]["mean"]}
            for row in rows]


def projection_bytes(events, *, agent_id):
    return journal.canonical_bytes({"schema": "lineage.scorecard/v1", "agent_id": agent_id,
                                    "groups": _groups(fold_scorecards(events, agent_id=agent_id))}) + b"\n"


def fold(events):
    """Index the public telemetry groups by born agent, including empty agents."""
    groups = {identifier: [] for identifier in sorted(agent_records(events))}
    for row in fold_scorecards(events):
        groups[row["agent_id"]].extend(_groups([row]))
    return groups


def get(agent_id, *, context, seat=None, memory_arm=None):
    if not _matches(_AGENT, agent_id):
        raise LineageError("bad_args", "invalid agent id")
    if seat is not None:
        try:
            _seat(seat)
        except LineageError:
            raise LineageError("bad_args", "invalid seat filter") from None
    if memory_arm is not None and memory_arm not in ("none", "own", "inherited"):
        raise LineageError("bad_args", "invalid memory arm filter")
    history = journal.snapshot(context.home)
    rows = fold_scorecards(history, agent_id=agent_id)
    rows = [row for row in rows if (seat is None or row["seat"] == seat)
            and (memory_arm is None or row["memory_arm"] == memory_arm)]
    return {"agent_id": agent_id, "head": history[-1]["lamport"] if history else 0,
            "groups": _groups(rows)}
