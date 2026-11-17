"""Immutable predeclaration and subject/seat admission."""
from copy import deepcopy
from dataclasses import replace
from unittest import mock

from .helpers import ArenaCase, bench, declaration, digest, runner, SEAT, SEAT2
from .helpers import bank_data, task  # A-U16: success-only projection fixture uses the shared bank builders.


class DeclarationTests(ArenaCase):
    def test_a7_run_requires_declaration_before_runner_or_journal(self):
        config = {"kind": "fake", "seed": 1}
        command = self.command("bench_run", {"bench_id": "bench0001", "runner": config})
        with mock.patch.object(runner, "run_task", side_effect=AssertionError("undeclared execution")) as spy:
            self.rejects("rule_not_declared", bench.run, "bench0001", config, command=command, ctx=self.ctx)
        spy.assert_not_called()
        self.assertFalse(self.events())

    def test_a7_result_requires_declaration(self):
        result = self.result()
        self.rejects("rule_not_declared", bench.record_result, result,
                     command=self.command("bench_run", {"bench_id": "bench0001", "runner": {"kind": "fake", "seed": 1}}), ctx=self.ctx)

    def test_a7_unknown_status_and_verdict_are_no_benchmark(self):
        self.rejects("no_benchmark", bench.status, "bench0001", ctx=self.ctx)
        self.rejects("no_benchmark", bench.verdict, "bench0001",
                     command=self.command("bench_verdict", {"bench_id": "bench0001"}), ctx=self.ctx)

    def test_a8_exact_declaration_replays_original_prefix(self):
        command = self.command("bench_declare", {"declaration": self.decl})
        first = self.declare(command=command)
        self.tx("unrelated", {"passive": True})
        before = self.raw()
        second = self.invoke(bench.declare, self.decl, command=replace(command, expected_head=0), ctx=self.ctx)
        self.assertEqual(first.value, second.value)
        self.assertEqual(first.head, second.head)
        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual(self.raw(), before)
        self.assertEqual(len(self.events("bench.declared")), 1)
        self.assertEqual(self.events("bench.declared")[0]["payload"], self.decl)

    def test_a8_changed_declaration_bad_op_and_distinct_redeclare_conflict(self):
        command = self.command("bench_declare", {"declaration": self.decl})
        self.declare(command=command)
        variants = []
        for field, value in (("bank_sha256", "0" * 64), ("purpose", "confirm"),
                             ("agents", list(reversed(self.decl["agents"]))), ("seats", [SEAT2]),
                             ("credit_rule", {**self.decl["credit_rule"], "minimum_gain": 0.5})):
            variants.append({**deepcopy(self.decl), field: value})
        for changed in variants:
            changed_command = replace(command, args={**command.args, "declaration": changed})
            self.rejects("bad_op", bench.declare, changed, command=changed_command, ctx=self.ctx)
        self.rejects("conflict", bench.declare, self.decl,
                     command=self.command("bench_declare", {"declaration": self.decl}), ctx=self.ctx)
        self.execute()
        self.rejects("bad_op", bench.declare, variants[-1],
                     command=replace(command, args={**command.args, "declaration": variants[-1]}), ctx=self.ctx)

    def test_a9_invalid_probabilities_and_boolean_cap(self):
        self.subjects()
        for field, value in (("p0", 0), ("p1", 1), ("p0", 0.7), ("p0", 0.9),
                             ("alpha", float("nan")), ("beta", float("inf")),
                             ("cap", True), ("cap", 0), ("cap", 9007199254740992)):
            changed = deepcopy(self.decl)
            changed["sprt"][field] = value
            self.rejects("bad_args", bench.declare, changed,
                         command=self.command("bench_declare", {"declaration": changed}), ctx=self.ctx)

    def test_a9_old_alpha_beta_constraint_does_not_reject_declaration(self):
        self.decl["sprt"].update(alpha=0.7, beta=0.4)
        self.declare()
        self.assertEqual(self.status()["declaration"]["sprt"], self.decl["sprt"])

    def test_a9_complete_seat_identity_is_admitted(self):
        self.subjects()
        for seat in ({**SEAT, "effort": "unadmitted"}, {**SEAT, "mode": "interactive"}):
            changed = {**self.decl, "seats": [seat]}
            self.rejects("seat_not_allowed", bench.declare, changed,
                         command=self.command("bench_declare", {"declaration": changed}), ctx=self.ctx)
        self.decl["seats"] = [SEAT, SEAT2]
        self.declare()
        self.assertEqual(self.status()["declaration"]["seats"], [SEAT, SEAT2])

    def test_a2_unknown_declaration_fields_are_closed(self):
        self.subjects()
        for field in ("seed", "snapshot", "record"):
            changed = {**self.decl, field: {}}
            self.rejects("bad_args", bench.declare, changed,
                         command=self.command("bench_declare", {"declaration": changed}), ctx=self.ctx)

    def test_a3_wrong_canonical_hash_refuses_before_run(self):
        self.subjects()
        changed = {**self.decl, "bank_sha256": "0" * 64}
        self.rejects("hash_mismatch", bench.declare, changed,
                     command=self.command("bench_declare", {"declaration": changed}), ctx=self.ctx)
        self.assertFalse(self.events("run.open"))

    def test_a6_direct_heldout_selection_result_is_forbidden(self):
        self.declare()
        result = self.result("task00000001")
        self.rejects("heldout_forbidden", self.direct, "bench.result", result)
        self.rejects("heldout_forbidden", bench.record_result, result,
                     command=self.command("bench_run", {"bench_id": "bench0001", "runner": {"kind": "fake", "seed": 0}}), ctx=self.ctx)
        self.assertFalse(self.events("run.open"))

    def test_a10_projection_edit_cannot_rebase_declared_snapshot(self):
        # A-U16: isolate projection tampering from legitimate failure-memory version advancement.
        self.bank = bank_data([task(1, baseline="green", candidate="green")])
        self.write_bank(self.bank)
        self.decl = declaration(self.bank)
        self.declare()
        original = deepcopy(self.events("bench.declared")[0])
        # A-U16: target the integrated language/workflow layout rather than a legacy flat path.
        from lineage.domain import layout
        projections = layout.agent_dir(self.home, workflow="test", language="python", agent_id="candidate-one")
        projections.mkdir(parents=True, exist_ok=True)
        (projections / "agent.json").write_text('{"memory_gen":999,"constitution_sha256":"spoof"}')
        self.tx("unrelated", {"passive": True})
        self.execute()
        self.assertEqual(self.events("bench.declared")[0], original)
        self.assertEqual(self.status()["declaration"], self.decl)
        versions = {e["payload"]["record"]["agent_id"]: e["payload"]["record"]["agent_version"]
                    for e in self.events("agent.born")}
        for e in self.events("run.open"):
            self.assertEqual(e["payload"]["agent_version"], versions[e["payload"]["agent_id"]])
