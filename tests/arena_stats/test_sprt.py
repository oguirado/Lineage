"""A2-A10 and A25: prefix evidence, boundaries, hostile schemas."""
import copy
import math

from tests.arena_stats import (APICase, PARAMS, DictSubclass, IntegerSubclass,
                               ListSubclass, NumericEnum, StringSubclass, outcomes)


class SPRTTests(APICase):
    def setUp(self):
        self.evaluate = self.api("sprt", "evaluate_sprt")

    def run_sprt(self, values, **changes):
        return self.evaluate(values, **dict(PARAMS, **changes))

    def test_a02_binding_win_prefixes(self):
        for n, decision in ((8, "continue"), (9, "superior")):
            with self.subTest(n=n):
                rows = outcomes(["win"] * n)
                result = self.run_sprt(rows)
                self.sprt_shape(result)
                self.assertEqual(result["decision"], decision)
                self.assertEqual((result["n_tasks"], result["n_discordant"], result["wins"], result["losses"], result["ties"], result["ignored_repeats"]),
                                 (n, n, n, 0, 0, 0))
                self.assertEqual(result["stopped_at"], rows[-1]["task_id"] if n == 9 else None)

    def test_a02_binding_loss_prefixes(self):
        for n, decision in ((3, "continue"), (4, "not_superior")):
            with self.subTest(n=n):
                rows = outcomes(["loss"] * n)
                result = self.run_sprt(rows)
                self.sprt_shape(result)
                self.assertEqual(result["decision"], decision)
                self.assertEqual((result["n_tasks"], result["n_discordant"], result["wins"], result["losses"], result["ties"]), (n, n, 0, n, 0))
                self.assertEqual(result["stopped_at"], rows[-1]["task_id"] if n == 4 else None)

    def test_a03_natural_log_formulas(self):
        result = self.run_sprt(outcomes(["win", "loss", "win"]))
        self.sprt_shape(result)
        self.close(result["llr"], 2 * (math.log(.7) - math.log(.5)) + math.log1p(-.7) - math.log1p(-.5))
        self.close(result["upper"], math.log1p(-.2) - math.log(.05))
        self.close(result["lower"], math.log(.2) - math.log1p(-.05))
        self.assertEqual(result["decision"], "continue")

    def test_a03_unique_ties_add_no_evidence(self):
        plain = self.run_sprt(outcomes(["win", "loss", "win"]))
        ties = self.run_sprt(outcomes(["tie", "win", "tie", "loss", "win", "tie"]))
        self.assertEqual(ties["llr"], plain["llr"])
        self.assertEqual(ties["n_discordant"], plain["n_discordant"])
        self.assertEqual((ties["n_tasks"], ties["ties"], ties["wins"], ties["losses"]), (6, 3, 2, 1))
        self.assertEqual(ties["decision"], "continue")

    def test_a04_exact_upper_boundary_is_inclusive(self):
        result = self.run_sprt(outcomes(["win"]), p0=.25, p1=.5, alpha=.25, beta=.5, cap=1)
        self.assertEqual(result["llr"], result["upper"])
        self.assertEqual(result["decision"], "superior")
        self.assertEqual(result["stopped_at"], "task-0000")

    def test_a04_exact_lower_boundary_is_inclusive(self):
        result = self.run_sprt(outcomes(["loss"]), p0=.5, p1=.75, alpha=.5, beta=.25, cap=1)
        self.assertEqual(result["llr"], result["lower"])
        self.assertEqual(result["decision"], "not_superior")
        self.assertEqual(result["stopped_at"], "task-0000")

    def test_a05_terminal_prefix_is_immutable(self):
        for prefix, opposite in ((["win"] * 9, "loss"), (["loss"] * 4, "win")):
            with self.subTest(prefix=prefix):
                rows = outcomes(prefix)
                suffix = outcomes([opposite] * 40, prefix="suffix")
                suffix += [copy.deepcopy(rows[0]), dict(rows[0], seed=99)]
                self.assertEqual(self.run_sprt(rows + suffix), self.run_sprt(rows))

    def test_a06_tie_cap_and_empty_input(self):
        empty = self.run_sprt([], cap=3)
        self.sprt_shape(empty)
        self.assertEqual((empty["decision"], empty["llr"], empty["n_tasks"], empty["stopped_at"]), ("continue", 0.0, 0, None))
        self.assertEqual([empty[k] for k in ("n_discordant", "wins", "losses", "ties", "ignored_repeats")], [0] * 5)
        for n in (2, 3):
            result = self.run_sprt(outcomes(["tie"] * n), cap=3)
            self.assertEqual(result["decision"], "continue" if n == 2 else "inconclusive")
            self.assertEqual((result["llr"], result["n_discordant"], result["n_tasks"], result["ties"]), (0.0, 0, n, n))
            self.assertEqual(result["stopped_at"], None if n == 2 else "task-0002")

    def test_a07_boundary_precedes_cap(self):
        for cap, decision in ((8, "inconclusive"), (9, "superior")):
            with self.subTest(cap=cap):
                result = self.run_sprt(outcomes(["win"] * 12), cap=cap)
                self.assertEqual(result["decision"], decision)
                self.assertEqual(result["n_tasks"], cap)
                self.assertEqual(result["wins"], cap)
                self.assertEqual(result["stopped_at"], f"task-{cap - 1:04d}")

    def test_a08_repeated_seeds_are_one_task(self):
        values = [{"task_id": "same-task", "seed": seed, "outcome": "win"} for seed in range(20)]
        result = self.run_sprt(values)
        self.assertEqual((result["n_tasks"], result["wins"], result["ignored_repeats"], result["decision"]), (1, 1, 19, "continue"))
        self.assertEqual(self.run_sprt(outcomes(["win"] * 20))["decision"], "superior")
        ties = self.run_sprt([dict(value, outcome="tie") for value in values], cap=2)
        self.assertEqual((ties["decision"], ties["n_tasks"], ties["ties"], ties["ignored_repeats"]), ("continue", 1, 1, 19))

    def test_a09_redelivery_and_first_seed(self):
        first = outcomes(["loss"])[0]
        result = self.run_sprt([first, copy.deepcopy(first), dict(first, seed=1, outcome="win")])
        self.assertEqual((result["n_tasks"], result["wins"], result["losses"], result["ignored_repeats"]), (1, 0, 1, 2))
        self.error(self.run_sprt, [first, dict(first, outcome="win")], field="task")
        self.error(self.run_sprt, [first, dict(first, seed=1, outcome="win"), dict(first, seed=1, outcome="tie")])

    def test_a10_probabilities_and_error_bounds(self):
        changes = [{"p0": .7}, {"p0": .8}, {"p0": 0}, {"p1": 1}, {"p0": -.1}, {"p1": 2},
                   {"alpha": 0}, {"beta": 0}, {"alpha": 1}, {"beta": 1}, {"alpha": -.1}, {"beta": 2},
                   {"alpha": .5, "beta": .5}, {"alpha": .9, "beta": .2}]
        for field in ("p0", "p1", "alpha", "beta"):
            for value in (None, True, "0.5", float("nan"), float("inf"), float("-inf"), NumericEnum.ONE):
                changes.append({field: value})
        for change in changes:
            with self.subTest(change=change):
                self.error(self.run_sprt, [], **change)

    def test_a10_cap_is_a_positive_native_integer(self):
        for cap in (0, -1, 1.5, True, False, "10", None, float("inf"), IntegerSubclass(3), NumericEnum.ONE):
            with self.subTest(cap=repr(cap)):
                self.error(self.run_sprt, [], cap=cap, field="cap")

    def test_a10_closed_outcome_schema_and_native_types(self):
        good = outcomes(["win"])[0]
        invalid = [None, (), {}, {**good, "unknown": 1}, DictSubclass(good)]
        invalid += [{k: v for k, v in good.items() if k != field} for field in good]
        for task in ("", "\ud800", "\udfff", None, 1, StringSubclass("task")):
            invalid.append(dict(good, task_id=task))
        for seed in (-1, True, 1.5, "1", None, float("nan"), NumericEnum.ONE, IntegerSubclass(1)):
            invalid.append(dict(good, seed=seed))
        for outcome in ("WIN", "green", "", None, True, 1, StringSubclass("win")):
            invalid.append(dict(good, outcome=outcome))
        for value in invalid:
            with self.subTest(value=repr(value)):
                self.error(self.run_sprt, [value])
        for values in ((), (good,), ListSubclass([good]), {}, None, "win"):
            with self.subTest(container=type(values).__name__):
                self.error(self.run_sprt, values)

    def test_a25_entire_terminal_suffix_is_validated(self):
        prefix = outcomes(["win"] * 9)
        for bad in ({"task_id": "suffix", "seed": 0, "outcome": "unknown"},
                    {"task_id": "suffix", "seed": float("inf"), "outcome": "win"},
                    {"task_id": "\ud800", "seed": 0, "outcome": "tie"}, {}):
            with self.subTest(bad=repr(bad)):
                self.error(self.run_sprt, prefix + [bad])

    def test_a25_post_terminal_conflicting_redelivery(self):
        prefix = outcomes(["win"] * 9)
        self.error(self.run_sprt, prefix + [dict(prefix[0], outcome="loss")])
        suffix = outcomes(["loss"], prefix="suffix")[0]
        self.error(self.run_sprt, prefix + [suffix, dict(suffix, outcome="tie")])
        self.assertEqual(self.run_sprt(prefix + [suffix, copy.deepcopy(suffix)]), self.run_sprt(prefix))
