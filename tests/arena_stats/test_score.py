"""A9, A16-A20, A25: independent task and cost summaries."""
import copy

from tests.arena_stats import (APICase, COST_FIELDS, SEAT, DictSubclass,
                               IntegerSubclass, ListSubclass, NumericEnum,
                               StringSubclass, cost, row)


class ScoreTests(APICase):
    def setUp(self):
        self.aggregate = self.api("score", "aggregate_score")

    def score(self, rows, **changes):
        params = {"agent_id": "agent-one", "seat": copy.deepcopy(SEAT), "memory_arm": "none"}
        params.update(changes)
        return self.aggregate(rows, **params)

    def test_a16_counts_sorted_tasks_and_first_seed(self):
        values = [row("task-z", correct=False, duration_ms=20),
                  row("task-a", correct=True, duration_ms=10),
                  row("task-z", seed=1, correct=True, duration_ms=0)]
        result = self.score(values)
        self.score_shape(result)
        self.assertEqual(result["task_ids"], ["task-a", "task-z"])
        self.assertEqual((result["n_tasks"], result["n_correct"], result["n_incorrect"], result["ignored_repeats"]), (2, 1, 1, 1))
        self.close(result["correctness"], .5)
        self.assertEqual(result["cost"]["duration_ms"], {"known": 2, "unknown": 0, "total": 30, "mean": 15.0})

    def test_a09_a16_redelivery_and_changed_same_seed(self):
        first = row(correct=False, cost_micro_usd=7)
        result = self.score([first, copy.deepcopy(first)])
        self.assertEqual((result["n_tasks"], result["n_correct"], result["ignored_repeats"]), (1, 0, 1))
        self.assertEqual(result["cost"]["cost_micro_usd"]["total"], 7)
        self.error(self.score, [first, dict(first, correct=True)])
        changed = copy.deepcopy(first)
        changed["cost"]["cost_micro_usd"] = 6
        self.error(self.score, [first, changed])
        later = dict(first, seed=1)
        self.error(self.score, [first, later, dict(later, correct=True)])

    def test_a17_only_explicit_correctness_boolean(self):
        for value in (None, "green", "ADMIT", "OK", "done", 0, 1, 0.0, 1.0, [], NumericEnum.ONE):
            with self.subTest(value=repr(value)):
                self.error(self.score, [row(correct=value)], field="correct")

    def test_a17_empty_score_preserves_null(self):
        result = self.score([])
        self.score_shape(result)
        self.assertEqual(result["task_ids"], [])
        self.assertEqual((result["n_tasks"], result["n_correct"], result["n_incorrect"], result["ignored_repeats"]), (0, 0, 0, 0))
        self.assertIsNone(result["correctness"])
        for summary in result["cost"].values():
            self.assertEqual(summary, {"known": 0, "unknown": 0, "total": None, "mean": None})

    def test_a17_empty_rows_still_validate_identity(self):
        for changes in ({"agent_id": "Aaa"}, {"agent_id": "ab"}, {"agent_id": "agent-one\n"},
                        {"agent_id": "\ud800"}, {"agent_id": True}, {"seat": {}},
                        {"seat": dict(SEAT, extra="x")}, {"seat": None},
                        {"memory_arm": "invalid"}, {"memory_arm": None}):
            with self.subTest(changes=repr(changes)):
                self.error(self.score, [], **changes)

    def test_a18_each_cost_field_keeps_unknowns_and_zero(self):
        values = [row("task-a"), row("task-b"), row("task-c")]
        expected = {}
        for i, field in enumerate(COST_FIELDS):
            measurements = [0, None, i + 2]
            measurements = measurements[i % 3:] + measurements[:i % 3]
            for value, measurement in zip(values, measurements):
                value["cost"][field] = measurement
            expected[field] = {"known": 2, "unknown": 1, "total": i + 2, "mean": (i + 2) / 2}
        result = self.score(values + [dict(values[0], seed=17)])
        self.score_shape(result)
        self.assertEqual(result["cost"], expected)
        self.assertEqual(result["ignored_repeats"], 1)

    def test_a18_unknown_is_distinct_from_measured_zero(self):
        unknown = self.score([row()])
        zero = self.score([row(**{field: 0 for field in COST_FIELDS})])
        for field in COST_FIELDS:
            self.assertEqual(unknown["cost"][field], {"known": 0, "unknown": 1, "total": None, "mean": None})
            self.assertEqual(zero["cost"][field], {"known": 1, "unknown": 0, "total": 0, "mean": 0.0})

    def test_a18_totals_use_integer_arithmetic(self):
        # All inputs and their sum remain within the common safe-integer bound.
        n = 2251799813685247
        result = self.score([row("task-a", duration_ms=n), row("task-b", duration_ms=n - 1)])
        self.assertIs(type(result["cost"]["duration_ms"]["total"]), int)
        self.assertEqual(result["cost"]["duration_ms"]["total"], 2 * n - 1)
        self.assertEqual(result["cost"]["duration_ms"]["mean"], (2 * n - 1) / 2)

    def test_a19_invalid_cost_values_identify_the_field(self):
        for field in COST_FIELDS:
            for value in (-1, True, False, 0.0, 1.5, "1", float("nan"), float("inf"), float("-inf"), NumericEnum.ONE, IntegerSubclass(1)):
                with self.subTest(field=field, value=repr(value)):
                    self.error(self.score, [row(**{field: value})], field=field)

    def test_a19_closed_nested_cost_objects(self):
        for field in COST_FIELDS:
            bad = row()
            del bad["cost"][field]
            with self.subTest(missing=field):
                self.error(self.score, [bad], field=field)
        for value in (dict(cost(), extra=0), (), None, DictSubclass(cost())):
            with self.subTest(cost=repr(value)):
                self.error(self.score, [dict(row(), cost=value)])

    def test_a19_row_container_task_and_seed_validation(self):
        good = row()
        invalid = [None, {}, dict(good, extra=1), DictSubclass(good)]
        invalid += [{k: v for k, v in good.items() if k != field} for field in good]
        invalid += [dict(good, task_id=task) for task in ("", "\ud800", "\udfff", 1, None, StringSubclass("task"))]
        invalid += [dict(good, seed=seed) for seed in (-1, True, 1.5, "1", None, NumericEnum.ONE)]
        for value in invalid:
            with self.subTest(value=repr(value)):
                self.error(self.score, [value])
        for values in ((), (good,), ListSubclass([good]), {}, None):
            with self.subTest(container=type(values).__name__):
                self.error(self.score, values)

    def test_a20_preserves_all_identity_components(self):
        seats = [SEAT, dict(SEAT, model="other-model"), dict(SEAT, effort="high"), dict(SEAT, mode="interactive")]
        for seat in seats:
            for arm in ("none", "own", "inherited"):
                for agent in ("agent-one", "agent-two"):
                    with self.subTest(seat=seat, arm=arm, agent=agent):
                        result = self.score([row()], agent_id=agent, seat=seat, memory_arm=arm)
                        self.assertEqual((result["agent_id"], result["seat"], result["memory_arm"]), (agent, seat, arm))

    def test_a20_invalid_seat_and_memory_identity(self):
        for field in SEAT:
            for value in ("", "\ud800", "\udfff", None, 1, StringSubclass("headless")):
                with self.subTest(field=field, value=repr(value)):
                    self.error(self.score, [], seat=dict(SEAT, **{field: value}))
        self.error(self.score, [], seat=DictSubclass(SEAT))
        self.error(self.score, [], agent_id=StringSubclass("agent-one"))
        self.error(self.score, [], memory_arm=StringSubclass("none"))

    def test_a25_duplicate_task_does_not_bypass_validation(self):
        first = row()
        for bad in (dict(first, seed=1, correct=None), dict(first, seed=1, cost={}),
                    dict(first, seed=1, extra=True), row(seed=1, duration_ms=float("inf"))):
            with self.subTest(bad=repr(bad)):
                self.error(self.score, [first, bad])
