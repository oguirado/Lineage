"""Ordered task-level sequential probability ratio testing."""
import math

from . import (_array, _enum, _finite, _integer, _object, _real,
               _redeliveries, _task, _bad)


def evaluate_sprt(
    observations: list[dict[str, object]], *,
    p0: float, p1: float, alpha: float, beta: float, cap: int,
) -> dict[str, object]:
    """Validate all deliveries, then evaluate the first terminal task prefix."""
    for name, value in (("p0", p0), ("p1", p1), ("alpha", alpha), ("beta", beta)):
        _real(value, name)
        if not 0 < value < 1:
            _bad(name, "must lie strictly between zero and one")
    if not p0 < p1:
        _bad("p0/p1", "require p0 < p1")
    if not alpha + beta < 1:
        _bad("alpha/beta", "require alpha + beta < 1")
    _integer(cap, "cap", 1)
    _array(observations, "observations")
    for index, row in enumerate(observations):
        field = f"observations[{index}]"
        _object(row, ("task_id", "seed", "outcome"), field)
        _task(row, field)
        _enum(row["outcome"], ("win", "loss", "tie"), field + ".outcome")
    _redeliveries(observations)

    win_step = math.log(p1) - math.log(p0)
    loss_step = math.log1p(-p1) - math.log1p(-p0)
    upper = _finite(math.log1p(-beta) - math.log(alpha), "upper")
    lower = _finite(math.log(beta) - math.log1p(-alpha), "lower")
    result = {"schema": "lineage.arena.sprt/v1", "decision": "continue",
              "llr": 0.0, "lower": lower, "upper": upper, "n_tasks": 0,
              "n_discordant": 0, "wins": 0, "losses": 0, "ties": 0,
              "ignored_repeats": 0, "stopped_at": None}
    tasks = set()
    for row in observations:
        task = row["task_id"]
        if task in tasks:
            result["ignored_repeats"] += 1
            continue
        tasks.add(task)
        result["n_tasks"] += 1
        outcome = row["outcome"]
        result[{"win": "wins", "loss": "losses", "tie": "ties"}[outcome]] += 1
        result["n_discordant"] = result["wins"] + result["losses"]
        result["llr"] = _finite(result["wins"] * win_step + result["losses"] * loss_step, "llr")
        if result["llr"] >= upper:
            result["decision"] = "superior"
        elif result["llr"] <= lower:
            result["decision"] = "not_superior"
        elif result["n_tasks"] >= cap:
            result["decision"] = "inconclusive"
        if result["decision"] != "continue":
            result["stopped_at"] = task
            break
    return result
