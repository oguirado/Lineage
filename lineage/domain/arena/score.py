"""Per-agent, per-seat, per-memory-arm task-level score aggregation."""
from . import (_COST_FIELDS, _array, _bad, _identity, _integer, _object,
               _ratio, _redeliveries, _task)


def aggregate_score(
    rows: list[dict[str, object]], *, agent_id: str,
    seat: dict[str, str], memory_arm: str,
) -> dict[str, object]:
    """Retain the first seed per task and count unknown costs independently."""
    _identity(agent_id, seat, memory_arm)
    _array(rows, "rows")
    for index, row in enumerate(rows):
        field = f"rows[{index}]"
        _object(row, ("task_id", "seed", "correct", "cost"), field)
        _task(row, field)
        if type(row["correct"]) is not bool:
            _bad(field + ".correct", "expected an explicitly adjudicated native boolean")
        _object(row["cost"], _COST_FIELDS, field + ".cost")
        for metric in _COST_FIELDS:
            if row["cost"][metric] is not None:
                _integer(row["cost"][metric], field + ".cost." + metric)
    _redeliveries(rows)
    retained = {}
    for row in rows:
        if row["task_id"] not in retained:
            retained[row["task_id"]] = row
    n_tasks = len(retained)
    n_correct = sum(row["correct"] for row in retained.values())
    summaries = {}
    for metric in _COST_FIELDS:
        values = [row["cost"][metric] for row in retained.values()
                  if row["cost"][metric] is not None]
        known = len(values)
        total = sum(values) if known else None
        summaries[metric] = {"known": known, "unknown": n_tasks - known,
                             "total": total,
                             "mean": _ratio(total, known, metric + ".mean") if known else None}
    return {"schema": "lineage.arena.score/v1", "agent_id": agent_id,
            "seat": dict(seat), "memory_arm": memory_arm,
            "task_ids": sorted(retained), "n_tasks": n_tasks,
            "n_correct": n_correct, "n_incorrect": n_tasks - n_correct,
            "correctness": _ratio(n_correct, n_tasks, "correctness") if n_tasks else None,
            "cost": summaries, "ignored_repeats": len(rows) - n_tasks}
