"""Pure arena statistics and shared, strict value validation.

These helpers calculate evidence only; benchmark policy and promotion belong
at the integration boundary. Importing this package loads no submodules.
"""
import math
import re


class ArenaStatsError(ValueError):
    """A supplied value violates the statistical helper contract."""

    code: str
    detail: str

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail)


_COST_FIELDS = ("tokens_in", "tokens_out", "tokens_cache", "duration_ms", "cost_micro_usd")


def _bad(field, requirement):
    raise ArenaStatsError("bad_args", f"{field}: {requirement}")


def _text(value, field):
    if type(value) is not str or not value:
        _bad(field, "expected a nonempty native string")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        _bad(field, "surrogates are not Unicode scalar values")
    return value


def _object(value, fields, field):
    if type(value) is not dict:
        _bad(field, "expected a native dict")
    for key in value:
        _text(key, field + " key")
    if set(value) != set(fields):
        _bad(field, "expected exactly fields " + ", ".join(fields))


def _array(value, field):
    if type(value) is not list:
        _bad(field, "expected a native list")


def _integer(value, field, minimum=0):
    if type(value) is not int or value < minimum:
        _bad(field, f"expected a native integer >= {minimum}")
    return value


def _finite(value, field):
    try:
        result = float(value)
    except (OverflowError, ValueError, TypeError):
        _bad(field, "arithmetic is not representable as a finite float")
    if not math.isfinite(result):
        _bad(field, "expected finite arithmetic")
    return result


def _real(value, field):
    if type(value) not in (int, float):
        _bad(field, "expected a native real number")
    _finite(value, field)
    return value


def _enum(value, choices, field):
    _text(value, field)
    if value not in choices:
        _bad(field, "unsupported value")


def _identity(agent_id, seat, memory_arm):
    _text(agent_id, "agent_id")
    if re.fullmatch(r"[a-z][a-z0-9-]{2,63}", agent_id) is None:
        _bad("agent_id", "invalid agent identifier")
    _object(seat, ("model", "effort", "mode"), "seat")
    for field in ("model", "effort", "mode"):
        _text(seat[field], "seat." + field)
    _enum(memory_arm, ("none", "own", "inherited"), "memory_arm")
    return (agent_id, seat["model"], seat["effort"], seat["mode"], memory_arm)


def _task(row, field):
    _text(row["task_id"], field + ".task_id")
    _integer(row["seed"], field + ".seed")


def _redeliveries(rows):
    """Validate every delivery key, including keys after a possible stop."""
    seen = {}
    for row in rows:
        key = (row["task_id"], row["seed"])
        if key in seen and seen[key] != row:
            _bad("task " + row["task_id"], "conflicting same-seed redelivery")
        seen[key] = row


def _ratio(total, known, field):
    try:
        result = total / known
    except (OverflowError, ZeroDivisionError):
        _bad(field, "division is not representable")
    return _finite(result, field)
