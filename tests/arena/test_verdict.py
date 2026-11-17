"""Task-balanced repeated cells, credit, canonical boundaries and finality.

Expected arithmetic is independent oracle data. Tests feed actual benchmark
runs, never result-shaped dictionaries as statistical evidence.
"""
from copy import deepcopy
from dataclasses import replace
import math
from unittest import mock

from .helpers import (ArenaCase, COST, SEAT, SEAT2, bank_data, bench, declaration,
                      digest, outcome, runner, task)


class VerdictTests(ArenaCase):
    def configure(self, pairs, **changes):
        self.bank = bank_data([task(i + 1, baseline="green" if b else "red",
                                    candidate="green" if c else "red") for i, (b, c) in enumerate(pairs)])
        self.write_bank(self.bank)
        self.decl = declaration(self.bank, **changes)

    def measured(self, pairs, **changes):
        self.configure(pairs, **changes)
        self.declare()
        self.execute()
        value = self.value(self.verdict())["verdict"]
        self.assertEqual(set(value), {"bench_id", "decision", "llr", "n_discordant", "credit"})
        self.assertEqual(set(value["credit"]), {"gain", "baseline_dispersion", "minimum_reward", "credited"})
        self.assert_lifecycle()
        return value

    def test_a32_no_observations_cannot_produce_verdict(self):
        self.declare()
        self.rejects("conflict", bench.verdict, "bench0001",
                     command=self.command("bench_verdict", {"bench_id": "bench0001"}), ctx=self.ctx)
        self.assertFalse(self.events("bench.verdict"))

    def test_a35_eight_wins_exhaust_without_upper_boundary(self):
        value = self.measured([(0, 1)] * 8)
        self.assertEqual(value["decision"], "inconclusive")
        self.assertEqual(value["n_discordant"], 8)
        self.assertAlmostEqual(value["llr"], 8 * math.log(0.7 / 0.5))
        self.assertLess(value["llr"], math.log(0.8 / 0.05))

    def test_a35_ninth_independent_win_is_superior(self):
        value = self.measured([(0, 1)] * 9)
        self.assertEqual(value["decision"], "superior")
        self.assertEqual(value["n_discordant"], 9)
        self.assertAlmostEqual(value["llr"], 9 * math.log(0.7 / 0.5))

    def test_a35_three_losses_do_not_cross_lower_boundary(self):
        value = self.measured([(1, 0)] * 3)
        self.assertEqual(value["decision"], "inconclusive")
        self.assertAlmostEqual(value["llr"], 3 * math.log(0.3 / 0.5))
        self.assertGreater(value["llr"], math.log(0.2 / 0.95))

    def test_a35_fourth_independent_loss_is_not_superior(self):
        value = self.measured([(1, 0)] * 4)
        self.assertEqual(value["decision"], "not_superior")
        self.assertEqual(value["n_discordant"], 4)
        self.assertAlmostEqual(value["llr"], 4 * math.log(0.3 / 0.5))

    def test_a36_ties_consume_task_cap_without_likelihood(self):
        self.configure([(1, 1)] * 3)
        self.decl["sprt"]["cap"] = 2
        self.declare()
        self.execute()
        value = self.value(self.verdict())["verdict"]
        self.assertEqual(value["decision"], "inconclusive")
        self.assertEqual(value["llr"], 0.0)
        self.assertEqual(value["n_discordant"], 0)
        self.assertFalse(value["credit"]["credited"])

    def test_a36_upper_boundary_on_cap_takes_priority(self):
        self.configure([(0, 1)] * 9)
        self.decl["sprt"]["cap"] = 9
        self.declare()
        self.execute()
        self.assertEqual(self.value(self.verdict())["verdict"]["decision"], "superior")

    def test_a34_population_not_sample_dispersion(self):
        value = self.measured([(0, 1), (0, 1), (0, 1), (1, 0)])
        credit = value["credit"]
        self.assertAlmostEqual(credit["gain"], 0.5)
        self.assertAlmostEqual(credit["baseline_dispersion"], math.sqrt(3 / 16))
        self.assertEqual(credit["minimum_reward"], -1)
        self.assertIs(credit["credited"], True)

    def test_a34_gain_equal_dispersion_is_not_credited(self):
        value = self.measured([(0, 1), (1, 1)])
        self.assertEqual(value["credit"]["gain"], 0.5)
        self.assertEqual(value["credit"]["baseline_dispersion"], 0.5)
        self.assertIs(value["credit"]["credited"], False)

    def test_a34_gain_equal_minimum_is_not_credited(self):
        self.configure([(0, 1)])
        self.decl["credit_rule"]["minimum_gain"] = 1
        self.declare()
        self.execute()
        self.assertIs(self.value(self.verdict())["verdict"]["credit"]["credited"], False)

    def test_a34_cost_only_advantage_cannot_create_correctness_credit(self):
        self.configure([(1, 1)])
        self.declare()
        original = runner.run_task
        def cheap(task_value, **kwargs):
            value = original(task_value, **kwargs)
            amount = 0 if kwargs["agent"]["agent_id"] == "candidate-one" else 100
            value["cost"] = {**COST, "cost_micro_usd": amount}
            for unit in value["memory_units"]:
                if unit["kind"] == "episode":
                    unit["body"]["cost"] = deepcopy(value["cost"])
            return value
        with mock.patch.object(runner, "run_task", side_effect=cheap):
            self.execute()
        value = self.value(self.verdict())["verdict"]
        self.assertEqual(value["llr"], 0.0)
        self.assertEqual(value["n_discordant"], 0)
        self.assertIs(value["credit"]["credited"], False)

    def test_a33_crossed_mean_outweighs_one_favorable_cell(self):
        self.configure([(0, 1)], protocol="crossed", seats=[SEAT, SEAT2],
                       memory_arms=["none", "own", "inherited"])
        self.declare()
        original = runner.run_task
        def mixed(task_value, **kwargs):
            value = original(task_value, **kwargs)
            candidate = kwargs["agent"]["agent_id"] == "candidate-one"
            favorable = kwargs["seat"] == SEAT and kwargs["memory_arm"] == "none"
            desired = "green" if not candidate or favorable else "red"
            # Generate all same-run failure units independently of fake policy.
            from .helpers import output_for
            # A-U16: custom multi-cell memory fixtures explicitly supersede their closed summaries.
            result = output_for(task_value, kwargs["agent"], desired,
                                receipt=value["evidence"][0],
                                supersedes=self.memory_predecessors(kwargs["agent"]["agent_id"]))
            for unit in result["memory_units"]:
                if unit["kind"] == "episode":
                    unit["body"]["seat"] = deepcopy(kwargs["seat"])
            return result
        with mock.patch.object(runner, "run_task", side_effect=mixed):
            self.execute()
        value = self.value(self.verdict())["verdict"]
        self.assertAlmostEqual(value["credit"]["gain"], -5 / 6)
        self.assertAlmostEqual(value["credit"]["minimum_reward"], -5 / 6)
        self.assertEqual(value["n_discordant"], 1)
        self.assertAlmostEqual(value["llr"], math.log(0.3 / 0.5))

    def test_a33_distinct_repeat_changes_mean_exact_delivery_adds_nothing(self):
        self.configure([(0, 1)])
        self.declare()
        first_config = {"kind": "fake", "seed": 1}
        command = self.command("bench_run", {"bench_id": "bench0001", "runner": first_config}, op="attempt-one")
        self.execute(first_config, command)
        before = self.raw()
        self.execute(first_config, command)
        self.assertEqual(self.raw(), before)
        original = runner.run_task
        def reverse(task_value, **kwargs):
            from .helpers import output_for
            value = original(task_value, **kwargs)
            desired = "red" if kwargs["agent"]["agent_id"] == "candidate-one" else "green"
            # A-U16: repeated fixture attempts retain history through explicit memory replacement edges.
            return output_for(task_value, kwargs["agent"], desired, receipt=value["evidence"][0],
                              supersedes=self.memory_predecessors(kwargs["agent"]["agent_id"]))
        with mock.patch.object(runner, "run_task", side_effect=reverse):
            self.execute({"kind": "fake", "seed": 2})
        self.assertEqual(len(self.events("bench.result")), 4)
        value = self.value(self.verdict())["verdict"]
        self.assertEqual(value["credit"]["gain"], 0.0)
        self.assertEqual(value["llr"], 0.0)
        self.assertEqual(value["n_discordant"], 0)

    def test_a37_hash_pinned_task_order_determines_first_terminal_prefix(self):
        self.configure([(1, 0)] * 4 + [(0, 1)] * 9)
        # Reverse lexical ids while preserving bank order; names cannot select a prefix.
        for i, item in enumerate(self.bank["tasks"]):
            item["id"] = f"task{100 - i:08d}"
        self.write_bank(self.bank)
        self.decl["bank_sha256"] = digest(self.bank)
        self.declare()
        self.execute()
        value = self.value(self.verdict())["verdict"]
        self.assertEqual(value["decision"], "not_superior")
        self.assertEqual(value["n_discordant"], 4)
        self.assertEqual(value["credit"]["minimum_reward"], -1)

    def test_a38_verdict_schema_replay_finality_and_no_status_change(self):
        self.configure([(0, 1)])
        self.declare()
        self.execute()
        command = self.command("bench_verdict", {"bench_id": "bench0001"})
        first = self.verdict(command)
        value = first.value["verdict"]
        self.assertEqual(self.events("bench.verdict")[0]["payload"], value)
        self.tx("unrelated", {"passive": True})
        before = self.raw()
        self.assertEqual(self.verdict(command).value, first.value)
        self.assertEqual(self.raw(), before)
        self.rejects("conflict", bench.verdict, "bench0001",
                     command=self.command("bench_verdict", {"bench_id": "bench0001"}), ctx=self.ctx)
        self.rejects("conflict", self.execute)
        self.assertFalse(self.events("agent.status"))
        self.assertEqual(len(self.events("bench.verdict")), 1)

    def test_a38_false_verdict_direct_append_refused(self):
        self.configure([(0, 1)])
        self.declare()
        self.execute()
        expected = {"bench_id": "bench0001", "decision": "inconclusive",
                    "llr": math.log(0.7 / 0.5), "n_discordant": 1,
                    "credit": {"gain": 1.0, "baseline_dispersion": 0.0,
                               "minimum_reward": 1.0, "credited": True}}
        for field, changed in (("decision", "superior"), ("llr", 99),
                               ("n_discordant", 99), ("credit", {**expected["credit"], "credited": False})):
            self.rejects("conflict", self.direct, "bench.verdict", {**expected, field: changed})
        self.assertFalse(self.events("bench.verdict"))
        self.verdict()

    def test_a39_unrepresentable_commit_plan_refused_before_open(self):
        self.configure([(0, 1)] * 200, memory_arms=["none", "own", "inherited"])
        self.decl["seats"] = [{**SEAT, "effort": f"e{i}"} for i in range(16)]
        self.subject_seats = self.decl["seats"]
        self.decl["sprt"]["cap"] = 200
        self.declare()
        self.rejects("bad_args", self.execute)
        self.assertFalse(self.events("run.open"))
        self.assertFalse(self.events("bench.result"))

    def test_a39_representable_plan_commit_has_exact_shape(self):
        self.configure([(0, 1)])
        self.declare()
        result = self.execute()
        self.assertEqual(set(result["commit"]), {"event_ids", "head", "sha256"})
        self.assertEqual(len(result["commit"]["event_ids"]), 2)
        self.assert_lifecycle()

    def test_a34_cheaper_less_correct_candidate_remains_worse(self):
        self.configure([(1, 0)])
        self.declare()
        original = runner.run_task
        def cheap(task_value, **kwargs):
            value = original(task_value, **kwargs)
            amount = 0 if kwargs["agent"]["agent_id"] == "candidate-one" else 100
            value["cost"] = {**COST, "cost_micro_usd": amount}
            for unit in value["memory_units"]:
                if unit["kind"] == "episode":
                    unit["body"]["cost"] = deepcopy(value["cost"])
            return value
        with mock.patch.object(runner, "run_task", side_effect=cheap):
            self.execute()
        verdict = self.value(self.verdict())["verdict"]
        self.assertAlmostEqual(verdict["llr"], math.log(0.3 / 0.5))
        self.assertEqual(verdict["credit"]["gain"], -1)
        self.assertFalse(verdict["credit"]["credited"])

    def test_a34_unknown_cost_does_not_win_a_correctness_tie(self):
        self.configure([(1, 1)])
        self.declare()
        original = runner.run_task
        def unknown(task_value, **kwargs):
            value = original(task_value, **kwargs)
            value["cost"] = deepcopy(COST)
            for unit in value["memory_units"]:
                if unit["kind"] == "episode":
                    unit["body"]["cost"] = deepcopy(COST)
            return value
        with mock.patch.object(runner, "run_task", side_effect=unknown):
            self.execute()
        value = self.value(self.verdict())["verdict"]
        self.assertEqual(value["llr"], 0)
        self.assertEqual(value["n_discordant"], 0)
        self.assertFalse(value["credit"]["credited"])
        self.assertTrue(all(r["cost"] == COST for r in self.status()["results"]))

    def test_a37_favorable_prefix_with_unfinished_crossed_mate_cannot_win(self):
        from .helpers import Interrupted
        from lineage.core import journal
        self.configure([(0, 1)] * 9, protocol="crossed", seats=[SEAT, SEAT2])
        self.declare()
        original = journal.transact
        def before_last_result(*args, **kwargs):
            if kwargs.get("kind") == "bench.result":
                value = kwargs["payload"]
                if value["task_id"] == self.bank["tasks"][-1]["id"] and value["agent_id"] == "candidate-one" and value["seat"] == SEAT2:
                    raise Interrupted("missing mate")
            return original(*args, **kwargs)
        with mock.patch.object(journal, "transact", side_effect=before_last_result), self.assertRaises(Interrupted):
            self.execute()
        self.assertTrue(self.events("bench.result"))
        self.rejects("conflict", bench.verdict, "bench0001",
                     command=self.command("bench_verdict", {"bench_id": "bench0001"}), ctx=self.ctx)
        self.assertFalse(self.events("bench.verdict"))

    def test_a37_out_of_order_real_closed_cells_keep_bank_order(self):
        import importlib
        self.configure([(1, 0)] * 4 + [(0, 1)] * 9)
        self.declare()
        runs = importlib.import_module("lineage.domain.runs")
        units = importlib.import_module("lineage.domain.memory.units")
        from .helpers import output_for
        cells = []
        subjects = {e["payload"]["record"]["agent_id"]: e["payload"]["record"]
                    for e in self.events("agent.born")}
        for index, item in enumerate(self.bank["tasks"]):
            for role, agent_id in enumerate(self.decl["agents"]):
                run_id = f"manual{index:08d}{role}"
                subject = subjects[agent_id]
                context = replace(self.ctx, actor=agent_id)
                common = {k: item[k] for k in ("id", "kind", "language", "split")}
                common.update(bank_id="demo-offline", bench_id="bench0001")
                root_args = {"bench_id": "bench0001", "runner": {"kind": "fake", "seed": 1}}
                self.invoke(runs.open_run, run_id, agent_id, SEAT, common,
                            parents_context=[], memory_arm="none",
                            command=self.command("bench_run", root_args, actor=agent_id), ctx=context)
                execution = {**item, "bank_id": "demo-offline", "bench_id": "bench0001", "run_id": run_id}
                label = item["expected"]["baseline" if role == 0 else "candidate"]["verdict"]
                # A-U16: direct-run fixtures use the integrated bounded active-memory lifecycle.
                output = output_for(execution, subject, label, supersedes=self.memory_predecessors(agent_id))
                receipt = self.home / output["evidence"][0]["path"]
                receipt.parent.mkdir(parents=True, exist_ok=True)
                receipt.write_bytes(b"fixture\n")
                for unit in output["memory_units"]:
                    # A-U16: integrated memory admission binds Command.args to its own payload.
                    memory_args = {"agent_id": agent_id, "unit": unit, "run_id": run_id}
                    self.invoke(units.put, agent_id, unit, run_id=run_id,
                                command=self.command("memory_put", memory_args, actor=agent_id), ctx=context)
                self.invoke(runs.close, run_id, output["outcome"], output["cost"], evidence=output["evidence"],
                            command=self.command("bench_run", root_args, actor=agent_id), ctx=context)
                cells.append({"bench_id": "bench0001", "task_id": item["id"], "agent_id": agent_id,
                              "seat": SEAT, "memory_arm": "none", "run_id": run_id,
                              "verdict": label, "correctness": int(label == "green"), "cost": output["cost"]})
        for cell in reversed(cells):
            self.invoke(bench.record_result, cell,
                        command=self.command("bench_run", {"bench_id": "bench0001", "runner": {"kind": "fake", "seed": 1}}), ctx=self.ctx)
        value = self.value(self.verdict())["verdict"]
        self.assertEqual(value["decision"], "not_superior")
        self.assertEqual(value["n_discordant"], 4)
        self.assertAlmostEqual(value["llr"], 4 * math.log(0.3 / 0.5))
        self.assert_lifecycle()
