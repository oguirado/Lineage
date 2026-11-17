"""Registered validator coverage and deterministic namespace-owned folds."""
from copy import deepcopy
from hashlib import sha256
import time
from unittest import mock
from lineage.core import app, journal
from lineage.core.errors import LineageError
from . import (HASH, OracleCase, agents, brief, canonical, digest, extension,
               expected_version, expected_brief, record, unit)


class FoldTests(OracleCase):
    def tearDown(self):
        if self._testMethodName == "test_a22_effective_retirement_requires_real_promotion_peer":
            # This case now performs real receipt-backed lifecycles, not fixture appends.
            self.assertLess(time.monotonic() - self.started, 60,
                            "public retirement lifecycle exceeded its deadline")
        else:
            super().tearDown()

    def direct_rejection(self, payload, code=None):
        before = self.ledger()
        stub_seen = []
        actual_validator = extension.VALIDATORS["agent.born"]
        def checked(history, event):
            try:
                return actual_validator(history, event)
            except NotImplementedError as exc:
                stub_seen.append(str(exc))
                raise
        try:
            journal.transact(self.home, agent="system", op_id=f"directop{next(self.numbers):04d}",
                             kind="agent.born", payload=payload,
                             validators={"agent.born": checked})
        except NotImplementedError as exc:
            self.assertEqual(str(exc), "U12 stub")
            self.fail("U12 stub: registered birth admission is not implemented")
        except LineageError as exc:
            if stub_seen:
                self.fail("U12 stub: registered birth admission is not implemented")
            if code is not None:
                self.assertEqual(exc.code, code)
        else:
            self.fail("invalid direct birth was committed")
        self.assertEqual(self.ledger(), before)

    def test_a12_direct_append_forged_birth_fields(self):
        valid = self.seed("fixture-one")["payload"]
        # These fixtures test admission independently of transport validation.
        for field, forged in (("constitution_sha256", "0" * 64),
                              ("agent_version", "0" * 64), ("brief_head_sha256", "0" * 64),
                              ("parents", ["parent-one"]),
                              ("born", {"op": "genesis", "event_id": "e-ffffffffffffffff"})):
            candidate = deepcopy(valid)
            candidate["record"]["agent_id"] = "new-agent"
            candidate["record"][field] = forged
            self.direct_rejection(candidate)

    def test_a12_wrong_rule_ids_injected_inheritance_and_source_bytes(self):
        valid = self.seed("fixture-one")["payload"]
        candidates = []
        for key, value in (("rule_ids", ["I999"]), ("text", "# Forged constitution\n")):
            candidate = deepcopy(valid)
            candidate["record"]["agent_id"] = "new-agent"
            candidate["constitution"][key] = value
            candidates.append(candidate)
        candidate = deepcopy(valid)
        candidate["record"]["agent_id"] = "new-agent"
        candidate["inherited_units"] = [{"unit": unit(), "source_agent_id": "parent-one",
                                          "source_unit_id": "source01", "unit_sha256": HASH}]
        candidates.append(candidate)
        for payload in candidates:
            self.direct_rejection(payload)

    def test_a20_agents_fold_owns_only_agents_and_never_mutates_event(self):
        event = self.seed()
        original = deepcopy(event)
        others = {key: {"sentinel": [key]} for key in ("memory", "promotion", "skills", "references", "runs", "scorecards")}
        state = deepcopy(others)
        self.invoke(extension.FOLDS["agents"], state, event)
        self.assertIn("agents", state)
        for key in others:
            self.assertEqual(state[key], others[key])
        self.assertEqual(event, original)

    def test_a20_memory_generation_refresh_and_replay(self):
        self.seed()
        before = self.invoke(agents.get, "agent-one", ctx=self.ctx)["record"]
        memory = self.require_peer("lineage.domain.memory.units")
        # A-U12: U10 requires an actor-bound Context and a callable budget witness.
        # A-TOK1's UTF-8 byte bound is conservative, not a model token measurement.
        memory_ctx = self.memory_context("agent-one", token_count=lambda text: len(text.encode("utf-8")))
        item = unit()
        evidence = self.home / "receipts/fixture.txt"
        evidence.parent.mkdir(parents=True)
        evidence.write_bytes(b"oracle receipt\n")
        item["receipts"][0]["sha256"] = sha256(evidence.read_bytes()).hexdigest()
        command = self.command({"agent_id": "agent-one", "unit": item}, tool="memory_put", actor="agent-one")
        memory.put("agent-one", item, command=command, ctx=memory_ctx)
        after = self.invoke(agents.get, "agent-one", ctx=self.ctx)["record"]
        self.assertEqual(after["memory_gen"], before["memory_gen"] + 1)
        self.assertEqual(after["agent_version"], expected_version(after["constitution_sha256"], after["skills"], after["memory_gen"]))
        self.assertNotEqual(after["brief_head_sha256"], before["brief_head_sha256"])
        count = len(journal.snapshot(self.home))
        memory.put("agent-one", item, command=command, ctx=memory_ctx)
        self.assertEqual(len(journal.snapshot(self.home)), count)
        self.assertEqual(self.invoke(agents.get, "agent-one", ctx=self.ctx)["record"], after)
        replacement = unit("lesson02", supersedes=[item["id"]])
        replacement["receipts"] = deepcopy(item["receipts"])
        memory.put("agent-one", replacement, command=self.command({"agent_id": "agent-one", "unit": replacement}, tool="memory_put", actor="agent-one"), ctx=memory_ctx)
        self.assertEqual(self.invoke(agents.get, "agent-one", ctx=self.ctx)["record"]["memory_gen"], after["memory_gen"] + 1)

    def test_a21_non_brief_changes_do_not_change_version_or_bytes(self):
        self.seed()
        original = self.invoke(agents.get, "agent-one", ctx=self.ctx)["record"]
        original_brief = self.invoke(brief.get, "agent-one", ctx=self.ctx)
        # Committed-prefix fixtures isolate folding from U10 admission.
        for item in (unit("episode1", "episode"), unit("private1", privacy="private"),
                     unit("inactive", status="retired"), unit("decision", "decision"), unit("openitem", "open_item")):
            self.append_fixture("memory.put", {"agent_id": "agent-one", "unit": item})
            current = self.invoke(agents.get, "agent-one", ctx=self.ctx)["record"]
            self.assertEqual(current["agent_version"], original["agent_version"])
            self.assertEqual(current["memory_gen"], original["memory_gen"])
            self.assertEqual(self.invoke(brief.get, "agent-one", ctx=self.ctx), original_brief)

    def test_a22_effective_retirement_requires_real_promotion_peer(self):
        self.require_peer("lineage.domain.promotion")
        self.assertIn("promotion", self.reg.folds,
                      "BLOCKED/HOLD: promotion namespace contract AUSENTE")
        self.assertIn("agent_promote", self.reg.tools)

        def call(name, arguments, actor="agent-one"):
            effective = dict(arguments, agent=actor)
            if self.reg.tools[name].mutating:
                effective = self.command(arguments, tool=name, actor=actor).args
            result = app.dispatch(name, effective, context=self.ctx, registry=self.reg)
            self.assertEqual(result.exit_code, 0, result.payload)
            return result.payload["untrusted"]

        source = call("agent_create", self.arguments(), actor="system")["record"]
        evidence = self.home / "receipts/fixture.txt"
        evidence.parent.mkdir(parents=True)
        evidence.write_bytes(b"oracle receipt\n")
        receipt = {"path": "receipts/fixture.txt", "sha256": sha256(evidence.read_bytes()).hexdigest()}
        cost = dict.fromkeys(("tokens_in", "tokens_out", "tokens_cache", "duration_ms", "cost_micro_usd"))
        predecessors = {}
        for number, verdict in enumerate(("error", "HOLD", "red"), 1):
            run_id = f"run{number:05d}"
            task = {"id": f"task{number:04d}", "kind": "fixture", "language": "python"}
            outcome = {"verdict": verdict, "repair_loops": 0,
                       "findings": {"confirmed": 0, "refuted": 0}}
            call("run_open", {"run_id": run_id, "agent_id": "agent-one",
                 "seat": source["allowed_seats"][0], "task": task,
                 "parents_context": [], "memory_arm": "own"})
            kinds = ("episode", "lesson") + (("negative",) if verdict in ("HOLD", "red") else ())
            for kind in kinds:
                item = unit(f"{kind}{number:02d}", kind, receipts=[deepcopy(receipt)])
                item["provenance"]["run_id"] = run_id
                if kind == "episode":
                    item["body"].update(run_id=run_id, task_id=task["id"],
                                        outcome=deepcopy(outcome), cost=deepcopy(cost))
                elif kind == "negative":
                    item["body"]["verdict"] = verdict
                if kind in predecessors:
                    item["supersedes"] = [predecessors[kind]]
                call("memory_put", {"agent_id": "agent-one", "run_id": run_id, "unit": item})
                if kind != "episode":
                    predecessors[kind] = item["id"]
            closed = call("run_close", {"run_id": run_id, "outcome": outcome, "cost": cost})
            self.assertTrue(closed["run"]["memory"]["gate_passed"])
            self.assertEqual(call("agent_get", {"agent_id": "agent-one"})["record"]["status"],
                             "retired" if number == 3 else "draft")
        before = self.ledger()
        self.assertEqual(self.invoke(agents.get, "agent-one", ctx=self.ctx)["record"]["status"], "retired")
        self.assertEqual(self.invoke(agents.list_agents, ctx=self.ctx)["agents"], [])
        self.assertEqual(self.ledger(), before)

    def test_a23_unproven_status_is_refused(self):
        event = self.seed()
        invalid = {**deepcopy(event), "kind": "agent.status",
                   "payload": {"agent_id": "agent-one", "from": "draft", "to": "promoted", "reason": "unproven"}}
        with self.assertRaises(LineageError) as raised:
            self.invoke(extension.VALIDATORS["agent.status"], journal.snapshot(self.home), invalid)
        self.assertIn(raised.exception.code, ("internal", "bad_args", "conflict"))
        self.assertEqual(len(self.assert_chain()), 1)

    def test_a23_non_genesis_and_fabricated_parent_are_refused(self):
        candidate = self.seed("parent-one")["payload"]
        candidate = deepcopy(candidate)
        candidate["record"].update(agent_id="child-one", parents=["parent-one"], generation=1,
                                    born={"op": "clone", "event_id": "e-ffffffffffffffff"})
        self.direct_rejection(candidate, "internal")

    def test_a11_selected_seat_integration_has_no_invented_u12_entrypoint(self):
        self.seed()
        self.invoke(agents.get, "agent-one", ctx=self.ctx)
        runs = self.require_peer("lineage.domain.runs")
        task = {"id": "task0001", "kind": "fixture", "language": "python"}
        for index, seat in enumerate(({"model": "other", "effort": "medium", "mode": "headless"},
                                      {"model": "fixture-model", "effort": "high", "mode": "headless"},
                                      {"model": "fixture-model", "effort": "medium", "mode": "interactive"})):
            args = {"run_id": f"run{index:05d}", "agent_id": "agent-one", "seat": seat,
                    "task": task, "parents_context": [], "memory_arm": "own"}
            self.reject("seat_not_allowed", runs.open_run, args["run_id"], "agent-one", seat, task,
                        parents_context=[], memory_arm="own", command=self.command(args, tool="run_open", actor="agent-one"), ctx=self.ctx)

    def test_a44_negative_oracle_rejects_removed_admission_validator(self):
        event = self.seed("fixture-one")
        for field in ("references", "agent_version", "agent_id"):
            payload = deepcopy(event["payload"])
            payload["record"][field] = [] if field == "references" else ("0" * 64 if field == "agent_version" else "fixture-one")
            # First prove the real validator rejects. Stub failure must escape.
            self.direct_rejection(payload)
            with mock.patch.dict(extension.VALIDATORS, {"agent.born": lambda history, event: None}):
                with self.assertRaises(AssertionError):
                    self.direct_rejection(payload)

    def test_a12_self_consistent_but_uncompiled_constitution_is_rejected(self):
        payload = deepcopy(self.seed("fixture-one")["payload"])
        payload["record"]["agent_id"] = "new-agent"
        # The citation and all client-computed hashes are self-consistent.
        # Extra uncompiled source must still fail exact compiler-byte admission.
        payload["constitution"]["text"] += "Injected constitution rule.\n"
        value = payload["record"]
        value["constitution_sha256"] = sha256(payload["constitution"]["text"].encode()).hexdigest()
        value["agent_version"] = expected_version(value["constitution_sha256"], value["skills"], value["memory_gen"])
        value["brief_head_sha256"] = sha256(expected_brief(value)).hexdigest()
        self.direct_rejection(payload)
