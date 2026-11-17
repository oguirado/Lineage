"""Correctness-first dense ranking of comparable scorecard series."""
from functools import cmp_to_key

from . import (_COST_FIELDS, _array, _bad, _enum, _finite, _identity,
               _integer, _object, _ratio, _text)


_FIELDS = ("schema", "agent_id", "seat", "memory_arm", "task_ids", "n_tasks",
           "n_correct", "n_incorrect", "correctness", "cost", "ignored_repeats")


def _validate(card, field):
    _object(card, _FIELDS, field)
    _enum(card["schema"], ("lineage.arena.score/v1",), field + ".schema")
    identity = _identity(card["agent_id"], card["seat"], card["memory_arm"])
    for name in ("n_tasks", "n_correct", "n_incorrect", "ignored_repeats"):
        _integer(card[name], field + "." + name)
    n = card["n_tasks"]
    if not n or card["n_correct"] + card["n_incorrect"] != n:
        _bad(field + ".n_tasks", "require a nonempty, consistent task count")
    tasks = card["task_ids"]
    _array(tasks, field + ".task_ids")
    for task in tasks:
        _text(task, field + ".task_ids")
    if len(tasks) != n or any(left >= right for left, right in zip(tasks, tasks[1:])):
        _bad(field + ".task_ids", "require distinct strictly ascending tasks matching n_tasks")
    fraction = card["correctness"]
    if type(fraction) is not float:
        _bad(field + ".correctness", "expected a native float")
    _finite(fraction, field + ".correctness")
    if fraction != _ratio(card["n_correct"], n, field + ".correctness"):
        _bad(field + ".correctness", "must equal n_correct / n_tasks exactly")
    _object(card["cost"], _COST_FIELDS, field + ".cost")
    for metric in _COST_FIELDS:
        path = field + ".cost." + metric
        summary = card["cost"][metric]
        _object(summary, ("known", "unknown", "total", "mean"), path)
        known = _integer(summary["known"], path + ".known")
        unknown = _integer(summary["unknown"], path + ".unknown")
        if known + unknown != n:
            _bad(path, "known + unknown must equal n_tasks")
        if not known:
            if summary["total"] is not None or summary["mean"] is not None:
                _bad(path, "unmeasured total and mean must be null")
        else:
            _integer(summary["total"], path + ".total")
            if type(summary["mean"]) is not float:
                _bad(path + ".mean", "expected a native float")
            _finite(summary["mean"], path + ".mean")
            if summary["mean"] != _ratio(summary["total"], known, path + ".mean"):
                _bad(path + ".mean", "must equal total / known exactly")
    return identity


def _identity_tuple(card):
    return (card["agent_id"], card["seat"]["model"], card["seat"]["effort"],
            card["seat"]["mode"], card["memory_arm"])


def _correctness_order(left, right):
    delta = left["n_correct"] * right["n_tasks"] - right["n_correct"] * left["n_tasks"]
    return (delta < 0) - (delta > 0)


def _detached(card):
    return {**card, "seat": dict(card["seat"]), "task_ids": list(card["task_ids"]),
            "cost": {key: dict(value) for key, value in card["cost"].items()}}


def rank_pairs(
    scorecards: list[dict[str, object]], *, cost_metric: str,
) -> list[dict[str, object]]:
    """Rank evidence, using identity only to display evidence ties stably."""
    _enum(cost_metric, ("cost_micro_usd", "duration_ms"), "cost_metric")
    _array(scorecards, "scorecards")
    identities = set()
    task_ids = None
    for index, card in enumerate(scorecards):
        identity = _validate(card, f"scorecards[{index}]")
        if identity in identities:
            _bad("scorecards identity", "duplicate series")
        identities.add(identity)
        if task_ids is not None and card["task_ids"] != task_ids:
            _bad("scorecards.task_ids", "comparison task sets must match")
        task_ids = card["task_ids"]
    ordered = sorted(sorted(scorecards, key=_identity_tuple), key=cmp_to_key(_correctness_order))
    ranked = []
    rank = 0
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and _correctness_order(ordered[start], ordered[end]) == 0:
            end += 1
        group = ordered[start:end]
        complete = all(card["cost"][cost_metric]["unknown"] == 0 for card in group)

        def cost_order(left, right):
            a, b = left["cost"][cost_metric], right["cost"][cost_metric]
            delta = a["total"] * b["known"] - b["total"] * a["known"]
            return (delta > 0) - (delta < 0)

        if complete:
            group.sort(key=cmp_to_key(cost_order))
        previous = None
        for card in group:
            if previous is None or (complete and cost_order(previous, card) != 0):
                rank += 1
            ranked.append({"rank": rank, "score": _detached(card)})
            previous = card
        start = end
    return ranked
