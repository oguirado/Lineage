"""Shared mathematical fixtures; implementation imports occur inside assertions.

All fixture sizes and limits are normative test targets from the U15 spec.
No implementation substitute is installed when a required API is absent.
"""
import copy
import importlib
import math
from pathlib import Path
import sys
import unittest
from enum import IntEnum

# Discovery must never create bytecode outside this oracle's write surface.
sys.dont_write_bytecode = True

COST_FIELDS = ("tokens_in", "tokens_out", "tokens_cache", "duration_ms", "cost_micro_usd")
SEAT = {"model": "fixture-model", "effort": "medium", "mode": "headless"}
PARAMS = {"p0": 0.5, "p1": 0.7, "alpha": 0.05, "beta": 0.20, "cap": 100}


class IntegerSubclass(int):
    pass


class NumericEnum(IntEnum):
    ONE = 1


class DictSubclass(dict):
    pass


class ListSubclass(list):
    pass


class StringSubclass(str):
    pass


def outcomes(sequence, *, prefix="task", start=0):
    return [{"task_id": f"{prefix}-{i:04d}", "seed": 0, "outcome": value}
            for i, value in enumerate(sequence, start)]


def cost(**values):
    return {field: values.get(field) for field in COST_FIELDS}


def row(task="task-0000", *, seed=0, correct=True, **values):
    return {"task_id": task, "seed": seed, "correct": correct, "cost": cost(**values)}


def rule(metric="duration_ms", *, minimum=3):
    return {"metric": metric,
            "direction": "higher" if metric == "correctness" else "lower",
            "dispersion": "sample_stddev", "min_baseline": minimum}


def card(agent="agent-one", *, answers=(True, False), measured=10,
         metric="duration_ms", seat=None, memory_arm="none"):
    """Hand-calculated scorecard, independent of aggregate_score."""
    n = len(answers)
    costs = {}
    for field in COST_FIELDS:
        values = [measured if field == metric else None for _ in answers]
        known = sum(value is not None for value in values)
        total = sum(value for value in values if value is not None) if known else None
        costs[field] = {"known": known, "unknown": n - known,
                        "total": total, "mean": total / known if known else None}
    return {"schema": "lineage.arena.score/v1", "agent_id": agent,
            "seat": copy.deepcopy(SEAT if seat is None else seat),
            "memory_arm": memory_arm,
            "task_ids": [f"task-{i:04d}" for i in range(n)],
            "n_tasks": n, "n_correct": sum(answers),
            "n_incorrect": n - sum(answers),
            "correctness": sum(answers) / n if n else None,
            "cost": costs, "ignored_repeats": 0}


def identity(score):
    return (score["agent_id"], score["seat"]["model"], score["seat"]["effort"],
            score["seat"]["mode"], score["memory_arm"])


class APICase(unittest.TestCase):
    def api(self, module, name):
        qualified = "lineage.domain.arena" + ("." + module if module else "")
        source_root = Path(__file__).resolve().parents[2] / "lineage/domain/arena"
        required = source_root / ((module if module else "__init__") + ".py")
        self.assertTrue(required.is_file(),
                        f"Missing U15 public behavior {qualified}.{name}; required source is AUSENTE")
        try:
            loaded = importlib.import_module(qualified)
        except Exception as exc:
            self.fail(f"Missing independently importable U15 public behavior "
                      f"{qualified}.{name}: {type(exc).__name__}")
        self.assertTrue(hasattr(loaded, name), f"Required U15 public API absent: {qualified}.{name}")
        value = getattr(loaded, name)
        self.assertTrue(callable(value), f"Required callable U15 API absent: {qualified}.{name}")
        return value

    def error(self, fn, *args, code="bad_args", field=None, **kwargs):
        error_type = self.api("", "ArenaStatsError")
        self.assertTrue(issubclass(error_type, ValueError))
        with self.assertRaises(error_type) as caught:
            fn(*args, **kwargs)
        exc = caught.exception
        self.assertEqual(exc.code, code)
        self.assertIs(type(exc.detail), str)
        self.assertTrue(exc.detail.strip(), "Error detail must identify the invalid field or task")
        if field is not None:
            self.assertIn(field, exc.detail)

    def close(self, actual, expected):
        self.assertIs(type(actual), float)
        self.assertTrue(math.isfinite(actual))
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12),
                        f"{actual!r} != {expected!r}")

    def exact_shape(self, value, keys):
        self.assertIs(type(value), dict)
        self.assertEqual(set(value), set(keys.split()))

    def sprt_shape(self, result):
        self.exact_shape(result, "schema decision llr lower upper n_tasks n_discordant wins losses ties ignored_repeats stopped_at")
        self.assertEqual(result["schema"], "lineage.arena.sprt/v1")
        self.assertIn(result["decision"], ("continue", "superior", "not_superior", "inconclusive"))
        for field in ("llr", "lower", "upper"):
            self.assertIs(type(result[field]), float)
            self.assertTrue(math.isfinite(result[field]))
        for field in ("n_tasks", "n_discordant", "wins", "losses", "ties", "ignored_repeats"):
            self.assertIs(type(result[field]), int)
            self.assertGreaterEqual(result[field], 0)
        self.assertEqual(result["n_discordant"], result["wins"] + result["losses"])
        self.assertEqual(result["n_tasks"], result["n_discordant"] + result["ties"])
        if result["decision"] == "continue":
            self.assertIsNone(result["stopped_at"])
        else:
            self.assertIs(type(result["stopped_at"]), str)
            self.assertTrue(result["stopped_at"])

    def credit_shape(self, result):
        self.exact_shape(result, "schema metric eligible credited reason gain baseline_mean baseline_dispersion n_baseline n_unknown")
        self.assertEqual(result["schema"], "lineage.arena.credit/v1")
        self.assertIn(result["metric"], ("correctness", "duration_ms", "cost_micro_usd"))
        for field in ("eligible", "credited"):
            self.assertIs(type(result[field]), bool)
        for field in ("n_baseline", "n_unknown"):
            self.assertIs(type(result[field]), int)
            self.assertGreaterEqual(result[field], 0)
        for field in ("gain", "baseline_mean", "baseline_dispersion"):
            if result[field] is not None:
                self.assertIs(type(result[field]), float)
                self.assertTrue(math.isfinite(result[field]))

    def score_shape(self, result):
        self.exact_shape(result, "schema agent_id seat memory_arm task_ids n_tasks n_correct n_incorrect correctness cost ignored_repeats")
        self.assertEqual(result["schema"], "lineage.arena.score/v1")
        self.exact_shape(result["seat"], "model effort mode")
        self.assertIs(type(result["task_ids"]), list)
        self.assertEqual(result["task_ids"], sorted(set(result["task_ids"])))
        self.assertEqual(len(result["task_ids"]), result["n_tasks"])
        for field in ("n_tasks", "n_correct", "n_incorrect", "ignored_repeats"):
            self.assertIs(type(result[field]), int)
            self.assertGreaterEqual(result[field], 0)
        self.assertEqual(result["n_tasks"], result["n_correct"] + result["n_incorrect"])
        if result["n_tasks"]:
            self.assertIs(type(result["correctness"]), float)
            self.assertEqual(result["correctness"], result["n_correct"] / result["n_tasks"])
        else:
            self.assertIsNone(result["correctness"])
        self.exact_shape(result["cost"], " ".join(COST_FIELDS))
        for summary in result["cost"].values():
            self.exact_shape(summary, "known unknown total mean")
            for field in ("known", "unknown"):
                self.assertIs(type(summary[field]), int)
                self.assertGreaterEqual(summary[field], 0)
            self.assertEqual(summary["known"] + summary["unknown"], result["n_tasks"])
            if summary["known"]:
                self.assertIs(type(summary["total"]), int)
                self.assertGreaterEqual(summary["total"], 0)
                self.assertIs(type(summary["mean"]), float)
                self.assertEqual(summary["mean"], summary["total"] / summary["known"])
            else:
                self.assertIsNone(summary["total"])
                self.assertIsNone(summary["mean"])

    def ranked_shape(self, ranked):
        self.assertIs(type(ranked), list)
        for record in ranked:
            self.exact_shape(record, "rank score")
            self.assertIs(type(record["rank"]), int)
            self.assertGreaterEqual(record["rank"], 1)
            self.score_shape(record["score"])
