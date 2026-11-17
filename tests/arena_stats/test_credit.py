"""A11-A15: predeclared, directional, dispersion-qualified evidence."""
import math

from tests.arena_stats import (APICase, DictSubclass, IntegerSubclass,
                               ListSubclass, NumericEnum, StringSubclass, rule)


class CreditTests(APICase):
    def setUp(self):
        self.evaluate = self.api("credit", "evaluate_credit")

    def test_a11_complete_rule_and_declaration_precedence(self):
        result = self.evaluate(1, [2, 4, 6], rule=rule())
        self.credit_shape(result)
        self.assertTrue(result["credited"])
        self.error(self.evaluate, 1, [2, 4, 6], rule=None, code="rule_not_declared")
        self.error(self.evaluate, object(), "malformed", rule=None, code="rule_not_declared")
        self.error(self.evaluate, object(), "malformed", rule={}, field="rule")

    def test_a11_closed_rule_validation(self):
        good = rule()
        invalid = [{}, [], "rule", DictSubclass(good), {**good, "unknown": 0}]
        invalid += [{k: v for k, v in good.items() if k != field} for field in good]
        for metric in ("latency", "\ud800", None, True, StringSubclass("duration_ms")):
            invalid.append(dict(good, metric=metric))
        for estimator in ("population_stddev", "stddev", None, False):
            invalid.append(dict(good, dispersion=estimator))
        for minimum in (0, 1, -1, True, 2.0, "2", None, NumericEnum.ONE, IntegerSubclass(3)):
            invalid.append(dict(good, min_baseline=minimum))
        invalid.extend([dict(good, direction="higher"), dict(rule("correctness"), direction="lower"),
                        dict(rule("cost_micro_usd"), direction="higher"), dict(good, direction="up")])
        for value in invalid:
            with self.subTest(value=repr(value)):
                self.error(self.evaluate, 1, [2, 4, 6], rule=value)

    def test_a12_sample_dispersion_and_strict_credit(self):
        for candidate, credited in ((2, False), (1, True), (3, False)):
            with self.subTest(candidate=candidate):
                result = self.evaluate(candidate, [2, 4, 6], rule=rule())
                self.credit_shape(result)
                self.assertEqual(result["metric"], "duration_ms")
                self.assertTrue(result["eligible"])
                self.assertIs(result["credited"], credited)
                self.assertEqual(result["reason"], "credited" if credited else "within_dispersion")
                self.close(result["baseline_mean"], 4)
                self.close(result["baseline_dispersion"], 2)
                self.close(result["gain"], 4 - candidate)
                self.assertEqual((result["n_baseline"], result["n_unknown"]), (3, 0))

    def test_a13_correctness_gain_is_directional(self):
        for candidate, credited in ((1.0, True), (.4, False), (.3, False), (0.0, False)):
            with self.subTest(candidate=candidate):
                result = self.evaluate(candidate, [.2, .4, .6], rule=rule("correctness"))
                self.assertIs(result["credited"], credited)
                self.close(result["gain"], candidate - .4)
                self.close(result["baseline_dispersion"], .2)

    def test_a13_lower_cost_and_constant_baseline(self):
        for metric in ("duration_ms", "cost_micro_usd"):
            for candidate, credited in ((9, True), (10, False), (11, False)):
                with self.subTest(metric=metric, candidate=candidate):
                    result = self.evaluate(candidate, [10, 10, 10], rule=rule(metric))
                    self.assertTrue(result["eligible"])
                    self.assertIs(result["credited"], credited)
                    self.close(result["baseline_dispersion"], 0)
                    self.close(result["gain"], 10 - candidate)
        zero = self.evaluate(.1, [0, 0], rule=rule("correctness", minimum=2))
        self.assertTrue(zero["credited"])
        self.close(zero["baseline_dispersion"], 0)

    def test_a14_missing_and_insufficient_evidence(self):
        cases = [(None, [2, 4, 6], "not_measured", 3, 0),
                 (1, [], "insufficient_baseline", 0, 0),
                 (1, [2], "insufficient_baseline", 1, 0),
                 (1, [2, 4], "insufficient_baseline", 2, 0),
                 (1, [2, 4, 6, None], "not_measured", 3, 1),
                 (1, [None, None], "not_measured", 0, 2),
                 (None, [], "not_measured", 0, 0)]
        for candidate, baseline, reason, measured, unknown in cases:
            with self.subTest(candidate=candidate, baseline=baseline):
                result = self.evaluate(candidate, baseline, rule=rule())
                self.credit_shape(result)
                self.assertIs(result["eligible"], False)
                self.assertIs(result["credited"], False)
                self.assertEqual(result["reason"], reason)
                self.assertEqual((result["n_baseline"], result["n_unknown"]), (measured, unknown))
                for field in ("gain", "baseline_mean", "baseline_dispersion"):
                    self.assertIsNone(result[field])

    def test_a14_validate_every_value_before_null_gate(self):
        for candidate, baseline in ((None, [None, -1]), (1, [None, -1]),
                                    (None, [2, "4"]), (True, [None]),
                                    (None, [float("nan")]), (None, [float("inf")])):
            with self.subTest(candidate=candidate, baseline=repr(baseline)):
                self.error(self.evaluate, candidate, baseline, rule=rule())

    def test_a15_invalid_measurements(self):
        for metric in ("duration_ms", "cost_micro_usd", "correctness"):
            invalid = [-1, True, False, "0.5", "\ud800", float("nan"), float("inf"),
                       float("-inf"), [], {}, NumericEnum.ONE, IntegerSubclass(1)]
            if metric == "correctness":
                invalid += [1.01, 2]
            for value in invalid:
                with self.subTest(metric=metric, value=repr(value), position="candidate"):
                    self.error(self.evaluate, value, [0, 0, 0], rule=rule(metric))
                with self.subTest(metric=metric, value=repr(value), position="baseline"):
                    self.error(self.evaluate, 0, [0, value, 0], rule=rule(metric))
        for baseline in ((), (2, 4, 6), ListSubclass([2, 4, 6]), None, "246", {}):
            with self.subTest(container=type(baseline).__name__):
                self.error(self.evaluate, 1, baseline, rule=rule())

    def test_a15_resilient_large_finite_dispersion(self):
        # Squaring an unscaled deviation overflows, although every result is finite.
        result = self.evaluate(0.0, [0.0, 1e308, 1e308], rule=rule())
        self.credit_shape(result)
        self.assertTrue(result["eligible"])
        self.assertTrue(result["credited"])
        self.close(result["baseline_mean"], (2.0 / 3.0) * 1e308)
        self.close(result["baseline_dispersion"], math.sqrt(1.0 / 3.0) * 1e308)
        self.close(result["gain"], result["baseline_mean"])

    def test_a15_unrepresentable_arithmetic_is_domain_error(self):
        huge = 10 ** 400
        self.error(self.evaluate, huge, [1, 2, 3], rule=rule())
        self.error(self.evaluate, 1, [huge, huge, huge], rule=rule())
