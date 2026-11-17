"""A1, A26, A27: public API, isolation, purity and rejecting controls."""
import ast
from contextlib import ExitStack, contextmanager
import copy
import datetime
from fractions import Fraction
import importlib
import importlib.abc
import importlib.util
import inspect
import io
import os
from pathlib import Path
import random
import socket
import subprocess
import sys
import time
import unittest
from unittest import mock

from tests.arena_stats import APICase, PARAMS, SEAT, card, identity, outcomes, row, rule

PACKAGE = "lineage.domain.arena"
MODULES = ("sprt", "credit", "score", "rating")


class SourceModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Execute actual implementation source from memory, without import file I/O."""
    def __init__(self, codes):
        self.codes = codes

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.codes:
            return importlib.util.spec_from_loader(fullname, self, is_package=fullname == PACKAGE)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        exec(self.codes[module.__name__], module.__dict__)


@contextmanager
def pure_entrypoints():
    attempted = []

    def denied(label):
        def fail(*args, **kwargs):
            attempted.append(label)
            raise AssertionError("Pure U15 operation attempted " + label)
        return fail

    class NoDateTime(datetime.datetime):
        now = classmethod(denied("datetime.now"))
        utcnow = classmethod(denied("datetime.utcnow"))
        today = classmethod(denied("datetime.today"))

    class NoDate(datetime.date):
        today = classmethod(denied("date.today"))

    targets = {
        "builtins": ("open",),
        "io": ("open",),
        "os": ("open", "read", "write", "listdir", "scandir", "stat", "lstat", "access",
               "readlink", "getcwd", "system", "popen", "fork", "posix_spawn", "urandom", "kill", "killpg"),
        "pathlib.Path": ("open", "read_text", "read_bytes", "write_text", "write_bytes", "iterdir", "stat"),
        "socket": ("socket", "create_connection", "socketpair", "getaddrinfo"),
        "subprocess": ("Popen", "run", "call", "check_call", "check_output"),
        "time": ("time", "time_ns", "monotonic", "monotonic_ns", "perf_counter", "perf_counter_ns",
                 "process_time", "clock_gettime", "sleep"),
        "random": ("random", "randint", "randrange", "getrandbits", "choice", "choices", "shuffle",
                   "sample", "uniform", "seed", "Random", "SystemRandom"),
    }
    with ExitStack() as stack:
        for prefix, names in targets.items():
            for name in names:
                stack.enter_context(mock.patch(prefix + "." + name, denied(prefix + "." + name), create=False))
        stack.enter_context(mock.patch("datetime.datetime", NoDateTime))
        stack.enter_context(mock.patch("datetime.date", NoDate))
        yield attempted


class ContractTests(APICase):
    def functions(self):
        return (self.api("sprt", "evaluate_sprt"), self.api("credit", "evaluate_credit"),
                self.api("score", "aggregate_score"), self.api("rating", "rank_pairs"))

    def test_a01_public_signatures_and_exception(self):
        functions = self.functions()
        layouts = (("observations", ("p0", "p1", "alpha", "beta", "cap")),
                   ("candidate", ("rule",)), ("rows", ("agent_id", "seat", "memory_arm")),
                   ("scorecards", ("cost_metric",)))
        for fn, (first, keywords) in zip(functions, layouts):
            params = inspect.signature(fn).parameters
            positional = (first, "baseline") if first == "candidate" else (first,)
            self.assertEqual(tuple(params), positional + keywords)
            self.assertEqual(fn.__module__, PACKAGE + "." + MODULES[functions.index(fn)])
            for name in positional:
                self.assertEqual(params[name].kind, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            for name in keywords:
                self.assertEqual(params[name].kind, inspect.Parameter.KEYWORD_ONLY)
            for value in params.values():
                self.assertIs(value.default, inspect.Parameter.empty)
        exc = self.api("", "ArenaStatsError")("bad_args", "candidate must be finite")
        self.assertIsInstance(exc, ValueError)
        self.assertEqual((exc.code, exc.detail), ("bad_args", "candidate must be finite"))
        with self.assertRaises(TypeError):
            functions[0]([])
        with self.assertRaises(TypeError):
            functions[1](0, [])

    def test_a01_closed_outputs_and_cross_module_smoke(self):
        sprt, credit, score, rank = self.functions()
        self.sprt_shape(sprt(outcomes(["win"]), **PARAMS))
        self.credit_shape(credit(1, [2, 4, 6], rule=rule()))
        scored = score([row()], agent_id="agent-one", seat=SEAT, memory_arm="none")
        self.score_shape(scored)
        self.ranked_shape(rank([scored], cost_metric="duration_ms"))

    def sources(self):
        self.functions()
        root = Path(__file__).resolve().parents[2]
        result = {}
        for suffix in ("__init__",) + MODULES:
            relative = "lineage/domain/arena/" + suffix + ".py"
            path = root / relative
            self.assertTrue(path.is_file(), "Required implementation source missing: " + relative)
            result[PACKAGE if suffix == "__init__" else PACKAGE + "." + suffix] = path.read_text(encoding="utf-8")
        return result

    def test_a01_only_stdlib_and_owned_modules_are_imported(self):
        for name, source in self.sources().items():
            for node in ast.walk(ast.parse(source)):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        package = PACKAGE if name == PACKAGE else name.rpartition(".")[0]
                        resolved = importlib.util.resolve_name("." * node.level + (node.module or ""), package)
                        self.assertTrue(resolved == PACKAGE or resolved.startswith(PACKAGE + "."), resolved)
                    else:
                        names = [node.module]
                for imported in names:
                    self.assertTrue(imported.split(".")[0] in sys.stdlib_module_names or
                                    imported == PACKAGE or imported.startswith(PACKAGE + "."),
                                    "External implementation dependency: " + imported)

    def test_a26_inputs_unchanged_and_nested_outputs_detached(self):
        sprt, credit, score, rank = self.functions()
        observations = outcomes(["win", "tie", "loss"])
        baseline, declared = [2, 4, 6], rule()
        rows, seat = [row()], copy.deepcopy(SEAT)
        cards = [card()]
        inputs = (observations, baseline, declared, rows, seat, cards)
        before = copy.deepcopy(inputs)
        result_sprt = sprt(observations, **PARAMS)
        result_credit = credit(1, baseline, rule=declared)
        result_score = score(rows, agent_id="agent-one", seat=seat, memory_arm="none")
        result_rank = rank(cards, cost_metric="duration_ms")
        self.assertEqual(inputs, before)
        expected_score, expected_rank = copy.deepcopy(result_score), copy.deepcopy(result_rank)
        result_sprt["decision"] = "tampered"
        result_credit["credited"] = False
        result_score["seat"]["model"] = "tampered"
        result_score["task_ids"].append("tampered")
        result_score["cost"]["duration_ms"]["unknown"] = 99
        result_rank[0]["score"]["seat"]["model"] = "tampered"
        result_rank[0]["score"]["cost"]["duration_ms"]["mean"] = 99.0
        self.assertEqual(inputs, before)
        self.assertEqual(sprt(observations, **PARAMS)["decision"], "continue")
        self.assertTrue(credit(1, baseline, rule=declared)["credited"])
        self.assertEqual(score(rows, agent_id="agent-one", seat=seat, memory_arm="none"), expected_score)
        self.assertEqual(rank(cards, cost_metric="duration_ms"), expected_rank)
        self.assertEqual(score(rows, agent_id="agent-one", seat=seat, memory_arm="none")["seat"], SEAT)
        self.assertEqual(rank(cards, cost_metric="duration_ms")[0]["score"], cards[0])

    def test_a26_repeat_calls_ignore_unrelated_calls_clock_and_random_state(self):
        sprt, credit, score, rank = self.functions()

        def snapshot():
            return (sprt(outcomes(["win", "tie", "loss"]), **PARAMS),
                    credit(1, [2, 4, 6], rule=rule()),
                    score([row()], agent_id="agent-one", seat=SEAT, memory_arm="none"),
                    rank([card()], cost_metric="duration_ms"))

        with mock.patch("time.time", return_value=1.0), mock.patch("random.random", return_value=.1):
            first = snapshot()
        sprt(outcomes(["loss"] * 4), **PARAMS)
        credit(11, [10, 10, 10], rule=rule())
        score([], agent_id="agent-two", seat=SEAT, memory_arm="inherited")
        rank([], cost_metric="cost_micro_usd")
        with mock.patch("time.time", return_value=1000.0), mock.patch("random.random", return_value=.9):
            self.assertEqual(snapshot(), first)

    def test_a26_import_and_computation_have_no_external_effects(self):
        sources = self.sources()
        # Warm stdlib imports only; the owned package is executed fresh below.
        for source in sources.values():
            for node in ast.walk(ast.parse(source)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
                if isinstance(node, ast.ImportFrom) and not node.level:
                    names = [node.module]
                for name in names:
                    if name.split(".")[0] in sys.stdlib_module_names:
                        importlib.import_module(name)
        codes = {name: compile(source, name.replace(".", "/") + ".py", "exec") for name, source in sources.items()}
        finder = SourceModules(codes)
        with mock.patch.dict(sys.modules):
            for name in list(sys.modules):
                if name == PACKAGE or name.startswith(PACKAGE + "."):
                    del sys.modules[name]
            sys.meta_path.insert(0, finder)
            try:
                with pure_entrypoints() as attempted:
                    package = importlib.import_module(PACKAGE)
                    self.assertFalse(any(PACKAGE + "." + name in sys.modules for name in MODULES),
                                     "Package initializer must not eagerly import statistical submodules")
                    self.assertTrue(issubclass(package.ArenaStatsError, ValueError))
                    sprt, credit, score, rating = [importlib.import_module(PACKAGE + "." + name) for name in MODULES]
                    self.sprt_shape(sprt.evaluate_sprt(outcomes(["tie"]), **PARAMS))
                    self.credit_shape(credit.evaluate_credit(1, [2, 4, 6], rule=rule()))
                    self.score_shape(score.aggregate_score([row()], agent_id="agent-one", seat=SEAT, memory_arm="none"))
                    self.ranked_shape(rating.rank_pairs([card()], cost_metric="duration_ms"))
                    with self.assertRaises(package.ArenaStatsError):
                        sprt.evaluate_sprt([], **dict(PARAMS, cap=True))
                    with self.assertRaises(package.ArenaStatsError):
                        credit.evaluate_credit(0, [], rule=None)
                    with self.assertRaises(package.ArenaStatsError):
                        score.aggregate_score([row(correct=None)], agent_id="agent-one", seat=SEAT, memory_arm="none")
                    with self.assertRaises(package.ArenaStatsError):
                        rating.rank_pairs([], cost_metric="invalid")
                    self.assertEqual(attempted, [], "Side effects must not be swallowed")
            finally:
                sys.meta_path.remove(finder)


class MutationControls(APICase):
    def rejecting_control(self, module, function, case, method, mutant):
        original = self.api(module, function)
        baseline = unittest.TestResult()
        case(method).run(baseline)
        self.assertEqual(baseline.testsRun, 1)
        self.assertTrue(baseline.wasSuccessful(), "Nominal acceptance must pass before a mutant is meaningful: " + repr(baseline.failures + baseline.errors))
        self.assertEqual(baseline.skipped, [])
        target = importlib.import_module(PACKAGE + "." + module)
        with mock.patch.object(target, function, mutant(original)):
            result = unittest.TestResult()
            case(method).run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(result.errors, [], "A mutant must be rejected by assertion, not an incidental exception")
        self.assertEqual(result.skipped, [])
        self.assertGreaterEqual(len(result.failures), 1, "The acceptance oracle admitted a semantic mutant")
        for _, trace in result.failures:
            self.assertIn("AssertionError", trace)
            self.assertNotIn("Missing independently importable", trace)

    def test_a27_tie_filter_mutant_is_rejected(self):
        from tests.arena_stats.test_sprt import SPRTTests

        def mutate(original):
            def changed(observations, **params):
                return original([dict(value, outcome="win") if value["outcome"] == "tie" else copy.deepcopy(value)
                                 for value in observations], **params)
            return changed
        self.rejecting_control("sprt", "evaluate_sprt", SPRTTests, "test_a03_unique_ties_add_no_evidence", mutate)

    def test_a27_task_deduplication_mutant_is_rejected(self):
        from tests.arena_stats.test_sprt import SPRTTests

        def mutate(original):
            def changed(observations, **params):
                return original([dict(value, task_id=f"independent-{i:04d}")
                                 for i, value in enumerate(observations)], **params)
            return changed
        self.rejecting_control("sprt", "evaluate_sprt", SPRTTests, "test_a08_repeated_seeds_are_one_task", mutate)

    def test_a27_strict_credit_mutant_is_rejected(self):
        from tests.arena_stats.test_credit import CreditTests

        def mutate(original):
            def changed(candidate, baseline, *, rule):
                result = original(candidate, baseline, rule=rule)
                if result["eligible"] and result["gain"] == result["baseline_dispersion"]:
                    result.update(credited=True, reason="credited")
                return result
            return changed
        self.rejecting_control("credit", "evaluate_credit", CreditTests, "test_a12_sample_dispersion_and_strict_credit", mutate)

    def test_a27_correctness_priority_mutant_is_rejected(self):
        from tests.arena_stats.test_rating import RatingTests

        def mutate(original):
            def changed(scorecards, *, cost_metric):
                result = original(scorecards, cost_metric=cost_metric)

                def cost_first(item):
                    summary = item["score"]["cost"][cost_metric]
                    return (summary["unknown"] != 0,
                            Fraction(summary["total"], summary["known"]) if summary["known"] else Fraction(0),
                            identity(item["score"]))
                result.sort(key=cost_first)
                return [{"rank": i + 1, "score": item["score"]} for i, item in enumerate(result)]
            return changed
        self.rejecting_control("rating", "rank_pairs", RatingTests, "test_a21_correctness_precedes_extreme_cost", mutate)
