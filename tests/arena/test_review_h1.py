"""Regression witnesses for h1 repairs; public lifecycle assertions remain real."""
# A-U16: h1 regressions retain native statistics and real journal lifecycle witnesses.
import math
from unittest import mock

from lineage.domain import gate_close
from lineage.domain.arena import sprt
from .helpers import ArenaCase, bank_data, bench, declaration, task


class ReviewH1Tests(ArenaCase):
    def configure(self, pairs):
        self.bank = bank_data([task(index + 1, baseline=baseline, candidate=candidate)
                               for index, (baseline, candidate) in enumerate(pairs)])
        self.write_bank(self.bank)
        self.decl = declaration(self.bank)

    def test_closed_synthetic_summaries_supersede_without_losing_run_history(self):
        self.configure([("red", "green")] * 3)
        self.declare()
        result = self.execute()
        self.assertEqual(len(result["bench"]["results"]), 6)
        self.assertEqual(result["bench"]["state"], "complete")
        self.assert_lifecycle()
        state = gate_close._snapshot(self.events(), self.ctx).state
        baseline = state["memory"]["baseline-one"]["units"]
        self.assertEqual(len(baseline), 9)
        self.assertEqual(sum(unit["status"] == "active" for unit in baseline.values()), 3)
        self.assertEqual(sum(unit["status"] == "superseded" for unit in baseline.values()), 6)
        for event in self.events("memory.put"):
            self.assertEqual(event["payload"]["unit"]["status"], "active")
        self.assertEqual(len(self.events("run.close")), 6)

    def test_population_adapter_uses_real_native_samples_and_strict_boundaries(self):
        rows = lambda values: [{"correctness": value} for value in values]
        from lineage.domain.arena import credit
        with mock.patch.object(credit, "evaluate_credit", wraps=credit.evaluate_credit) as native:
            value = bench._credit(rows([1, 1]), rows([0, 1]), rule={"minimum_gain": 0})
        self.assertEqual(native.call_args.args[1], [0, 1])
        self.assertEqual(value, {"gain": 0.5, "baseline_dispersion": 0.5,
                                 "minimum_reward": 0, "credited": False})
        value = bench._credit(rows([1]), rows([0]), rule={"minimum_gain": 1})
        self.assertEqual(value, {"gain": 1, "baseline_dispersion": 0.0,
                                 "minimum_reward": 1, "credited": False})
        value = bench._credit(rows([1, 1, 1, 0]), rows([0, 0, 0, 1]), rule={"minimum_gain": 0})
        self.assertAlmostEqual(value["baseline_dispersion"], math.sqrt(3 / 16))
        self.assertIs(value["credited"], True)

    def test_k0_probability_policy_uses_native_likelihood_and_actual_closed_cells(self):
        parameters = {"p0": 0.5, "p1": 0.7, "alpha": 0.99, "beta": 0.02, "cap": 10}
        observations = [{"task_id": "task00000001", "seed": 0, "outcome": "loss"}]
        with mock.patch.object(sprt, "evaluate_sprt", wraps=sprt.evaluate_sprt) as native:
            report = bench._sprt(observations, parameters)
        self.assertTrue(native.called)
        self.assertEqual(report["decision"], "not_superior")
        self.assertAlmostEqual(report["llr"], math.log(0.3 / 0.5))
        self.configure([("green", "green")])
        self.decl["sprt"].update(alpha=0.8, beta=0.8)
        self.declare()
        self.execute()
        verdict = self.verdict().value["verdict"]
        self.assertEqual(verdict["decision"], "superior")
        self.assertEqual(verdict["llr"], 0.0)
        self.assertEqual(verdict["n_discordant"], 0)
        self.assertIs(verdict["credit"]["credited"], False)
        self.assert_lifecycle()

    def test_caller_op_id_matching_private_prefix_is_unchanged_complete_and_replayable(self):
        self.configure([("green", "green")])
        self.declare()
        config = {"kind": "fake", "seed": 9}
        op_id = "ar-" + "a" * 40 + "/result/" + "b" * 40
        command = self.command("bench_run", {"bench_id": "bench0001", "runner": config}, op=op_id)
        result = self.execute(config, command)
        self.assertEqual(result["bench"]["state"], "complete")
        self.assertEqual(self.events("bench.result")[-1]["op_id"], op_id)
        self.tx("unrelated", {"passive": True})
        previous = self.raw()
        self.assertEqual(self.execute(config, command), result)
        self.assertEqual(self.raw(), previous)
        self.assert_lifecycle()
