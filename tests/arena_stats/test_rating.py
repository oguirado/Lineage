"""A20-A24: correctness precedes complete cost evidence."""
import copy
import itertools
import math

from tests.arena_stats import (APICase, SEAT, DictSubclass, IntegerSubclass,
                               ListSubclass, NumericEnum, card, identity)


class RatingTests(APICase):
    def setUp(self):
        self.rank = self.api("rating", "rank_pairs")

    def ranked(self, cards, metric="duration_ms"):
        return self.rank(cards, cost_metric=metric)

    def test_a20_full_identity_remains_separate(self):
        cards = [card("agent-one", seat=seat, memory_arm=arm)
                 for seat in (SEAT, dict(SEAT, model="other-model"), dict(SEAT, effort="high"), dict(SEAT, mode="interactive"))
                 for arm in ("none", "own", "inherited")]
        cards.append(card("agent-two"))
        result = self.ranked(list(reversed(cards)))
        self.ranked_shape(result)
        self.assertEqual([identity(item["score"]) for item in result], sorted(map(identity, cards)))
        self.assertEqual([item["rank"] for item in result], [1] * len(cards))
        self.assertEqual(len(result), len(cards))

    def test_a21_correctness_precedes_extreme_cost(self):
        for price in (9007199254740991, None):
            with self.subTest(price=price):
                best = card("agent-z", answers=(True, True), measured=price)
                cheap = card("agent-a", answers=(True, False), measured=0)
                result = self.ranked([cheap, best])
                self.assertEqual([item["score"]["agent_id"] for item in result], ["agent-z", "agent-a"])
                self.assertEqual([item["rank"] for item in result], [1, 2])

    def test_a22_complete_chosen_cost_breaks_correctness_ties(self):
        for metric in ("duration_ms", "cost_micro_usd"):
            with self.subTest(metric=metric):
                expensive = card("agent-a", metric=metric, measured=20)
                cheap = card("agent-z", metric=metric, measured=0)
                result = self.ranked([expensive, cheap], metric)
                self.assertEqual([item["score"]["agent_id"] for item in result], ["agent-z", "agent-a"])
                self.assertEqual([item["rank"] for item in result], [1, 2])
                self.assertIsNone(cheap["cost"]["tokens_in"]["mean"])

    def test_a22_any_incomplete_member_ties_the_entire_group(self):
        complete = [card("agent-z", measured=0), card("agent-a", measured=100)]
        for summary in ({"known": 0, "unknown": 2, "total": None, "mean": None},
                        {"known": 1, "unknown": 1, "total": 2, "mean": 2.0}):
            with self.subTest(summary=summary):
                unknown = card("agent-b")
                unknown["cost"]["duration_ms"] = summary
                result = self.ranked(complete + [unknown])
                self.assertEqual([item["score"]["agent_id"] for item in result], ["agent-a", "agent-b", "agent-z"])
                self.assertEqual([item["rank"] for item in result], [1, 1, 1])

    def test_a22_exact_ratios_override_rounded_equal_means(self):
        cheap = card("agent-z", answers=(True, False, False))
        expensive = card("agent-a", answers=(True, False, False))
        for value, total in ((cheap, 9007199254740988), (expensive, 9007199254740989)):
            value["cost"]["duration_ms"] = {"known": 3, "unknown": 0, "total": total, "mean": total / 3}
        self.assertEqual(cheap["cost"]["duration_ms"]["mean"], expensive["cost"]["duration_ms"]["mean"])
        result = self.ranked([expensive, cheap])
        self.assertEqual([item["score"]["agent_id"] for item in result], ["agent-z", "agent-a"])
        self.assertEqual([item["rank"] for item in result], [1, 2])

    def test_a23_evidence_ties_identity_order_and_dense_ranks(self):
        cards = [card("agent-z", measured=1), card("agent-a", measured=1),
                 card("agent-b", measured=2), card("agent-c", answers=(False, False), measured=0)]
        expected = [("agent-a", 1), ("agent-z", 1), ("agent-b", 2), ("agent-c", 3)]
        for permutation in itertools.permutations(cards):
            result = self.ranked(list(permutation))
            self.ranked_shape(result)
            self.assertEqual([(item["score"]["agent_id"], item["rank"]) for item in result], expected)

    def test_a23_empty_rating(self):
        self.assertEqual(self.ranked([]), [])

    def test_a24_cost_metric_validated_even_on_empty_input(self):
        for metric in ("invalid", "tokens_in", "correctness", "", None, True, 1, "\ud800"):
            with self.subTest(metric=repr(metric)):
                self.error(self.rank, [], cost_metric=metric, field="cost_metric")

    def test_a24_duplicate_series_task_mismatch_and_empty_tasks(self):
        original = card()
        self.error(self.ranked, [original, copy.deepcopy(original)])
        different = card("agent-two")
        different["task_ids"] = ["other-0000", "other-0001"]
        self.error(self.ranked, [original, different])
        self.error(self.ranked, [card(answers=())])
        self.error(self.ranked, [original, card("agent-two", answers=())])

    def test_a24_invalid_scorecard_shape_counts_and_task_order(self):
        original = card()
        mutations = []
        for field in original:
            changed = copy.deepcopy(original)
            del changed[field]
            mutations.append(changed)
        for field, value in (("schema", "lineage.arena.score/v2"), ("n_tasks", 3),
                             ("n_tasks", True), ("n_tasks", 2.0), ("n_correct", 3),
                             ("n_correct", -1), ("n_incorrect", 0), ("ignored_repeats", -1),
                             ("ignored_repeats", True), ("ignored_repeats", 1.5),
                             ("task_ids", ["task-0001", "task-0000"]),
                             ("task_ids", ["task-0000", "task-0000"]), ("task_ids", ["", "task-0001"]),
                             ("task_ids", ["\ud800", "task-0001"]), ("task_ids", ("task-0000", "task-0001")),
                             ("task_ids", ["task-0000"]), ("agent_id", "agent-one\n"),
                             ("agent_id", "Agent-one"), ("agent_id", "aa"), ("agent_id", "a" * 65),
                             ("agent_id", "\udfff"), ("seat", {}), ("seat", dict(SEAT, extra="x")),
                             ("seat", dict(SEAT, model="\ud800")), ("seat", dict(SEAT, effort="")),
                             ("memory_arm", "unknown"), ("cost", {})):
            mutations.append(dict(copy.deepcopy(original), **{field: value}))
        mutations += [dict(original, extra=0), DictSubclass(original), None, []]
        for changed in mutations:
            with self.subTest(changed=repr(changed)):
                self.error(self.ranked, [changed])
        for values in ((), (original,), ListSubclass([original]), None, {}):
            with self.subTest(container=type(values).__name__):
                self.error(self.ranked, values)

    def test_a24_correctness_requires_exact_float_fraction(self):
        original = card(answers=(True, True))
        for fraction in (1, True, None, float("nan"), float("inf"), -1.0,
                         math.nextafter(1.0, 0.0), "1.0"):
            with self.subTest(fraction=repr(fraction)):
                self.error(self.ranked, [dict(original, correctness=fraction)])
        half = card()
        self.error(self.ranked, [dict(half, correctness=math.nextafter(.5, 1.0))])

    def test_a24_cost_summary_consistency_and_closure(self):
        base = card()
        invalid = [{"known": 3, "unknown": 0, "total": 20, "mean": 10.0},
                   {"known": 2, "unknown": 1, "total": 20, "mean": 10.0},
                   {"known": True, "unknown": 1, "total": 20, "mean": 20.0},
                   {"known": 2, "unknown": 0, "total": -1, "mean": -.5},
                   {"known": 2, "unknown": 0, "total": 20.0, "mean": 10.0},
                   {"known": 2, "unknown": 0, "total": True, "mean": .5},
                   {"known": 2, "unknown": 0, "total": None, "mean": None},
                   {"known": 2, "unknown": 0, "total": 20, "mean": 10},
                   {"known": 2, "unknown": 0, "total": 20, "mean": 9.0},
                   {"known": 2, "unknown": 0, "total": 20, "mean": math.nextafter(10.0, 11.0)},
                   {"known": 2, "unknown": 0, "total": 20, "mean": float("inf")},
                   {"known": 0, "unknown": 2, "total": 0, "mean": 0.0},
                   {"known": 0, "unknown": 2, "total": None, "mean": 0.0},
                   dict(base["cost"]["duration_ms"], extra=0), {}, None]
        for summary in invalid:
            changed = copy.deepcopy(base)
            changed["cost"]["duration_ms"] = summary
            with self.subTest(summary=repr(summary)):
                self.error(self.ranked, [changed])
        for field in base["cost"]["duration_ms"]:
            changed = copy.deepcopy(base)
            del changed["cost"]["duration_ms"][field]
            with self.subTest(missing=field):
                self.error(self.ranked, [changed])
        extra = copy.deepcopy(base)
        extra["cost"]["extra"] = copy.deepcopy(extra["cost"]["duration_ms"])
        self.error(self.ranked, [extra])

    def test_a24_subclass_counts_are_not_native_integers(self):
        for field, value in (("n_tasks", IntegerSubclass(2)), ("n_correct", NumericEnum.ONE),
                             ("ignored_repeats", IntegerSubclass(0))):
            with self.subTest(field=field):
                self.error(self.ranked, [dict(card(), **{field: value})])
