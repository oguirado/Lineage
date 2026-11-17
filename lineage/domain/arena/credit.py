"""Directional scalar credit qualified by measured sample dispersion."""
import statistics

from . import ArenaStatsError, _array, _bad, _enum, _finite, _integer, _object, _real


def evaluate_credit(
    candidate: int | float | None,
    baseline: list[int | float | None], *,
    rule: dict[str, object] | None,
) -> dict[str, object]:
    """Apply the caller's declared rule without dropping missing evidence."""
    if rule is None:
        raise ArenaStatsError("rule_not_declared", "rule: a declaration is required")
    _object(rule, ("metric", "direction", "dispersion", "min_baseline"), "rule")
    _enum(rule["metric"], ("correctness", "duration_ms", "cost_micro_usd"), "rule.metric")
    direction = "higher" if rule["metric"] == "correctness" else "lower"
    _enum(rule["direction"], (direction,), "rule.direction")
    _enum(rule["dispersion"], ("sample_stddev",), "rule.dispersion")
    _integer(rule["min_baseline"], "rule.min_baseline", 2)
    _array(baseline, "baseline")
    for field, value in [("candidate", candidate)] + [
            (f"baseline[{index}]", value) for index, value in enumerate(baseline)]:
        if value is None:
            continue
        _real(value, field)
        if value < 0 or (rule["metric"] == "correctness" and value > 1):
            _bad(field, "measurement outside declared metric range")
    unknown = sum(value is None for value in baseline)
    measured = len(baseline) - unknown
    result = {"schema": "lineage.arena.credit/v1", "metric": rule["metric"],
              "eligible": False, "credited": False, "reason": "not_measured",
              "gain": None, "baseline_mean": None, "baseline_dispersion": None,
              "n_baseline": measured, "n_unknown": unknown}
    if candidate is None or unknown:
        return result
    if measured < rule["min_baseline"]:
        result["reason"] = "insufficient_baseline"
        return result
    # statistics uses exact rational intermediates for the sum and variance,
    # avoiding overflow from squaring otherwise representable measurements.
    try:
        mean = _finite(statistics.mean(baseline), "baseline_mean")
        dispersion = _finite(statistics.stdev(baseline), "baseline_dispersion")
        gain = _finite(candidate - mean if direction == "higher" else mean - candidate, "gain")
    except (OverflowError, ValueError, ArithmeticError) as exc:
        if isinstance(exc, ArenaStatsError):
            raise
        _bad("baseline/candidate", "arithmetic is not representable")
    credited = gain > dispersion
    result.update(eligible=True, credited=credited,
                  reason="credited" if credited else "within_dispersion",
                  gain=gain, baseline_mean=mean, baseline_dispersion=dispersion)
    return result
