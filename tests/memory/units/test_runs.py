"""A11–A13, A29: explicit run binding, opened content and exact retry."""
import copy
from ._support import IntegrationCase, OWNER, COST, unit, canonical
from lineage.domain.memory import units


class RunTests(IntegrationCase):
    def test_a11_explicit_and_implicit_episode_binding(self):
        self.runtime()
        self.open_run()
        for uid, run_id in (("unit_001", "run_0001"), ("unit_002", None)):
            value = self.shaped("episode", uid=uid)
            self.assertEqual(self.write(value, run_id=run_id).value["unit"], value)
        lesson = self.shaped(uid="unit_003")
        self.write(lesson)
        raw = self.snapshot().events[-1]
        self.assertNotIn("run_id", raw["payload"])
        self.assertNotIn("run_id", raw["payload"]["unit"]["provenance"])

    def test_a11_conflicting_ids_and_foreign_run(self):
        self.runtime()
        self.open_run()
        good = self.shaped("episode")
        self.write(good)
        for part in ("tool", "provenance", "body"):
            value = self.shaped("episode", uid="unit_002")
            run_id = None
            if part == "tool":
                run_id = "run_0002"
            else:
                value[part]["run_id"] = "run_0002"
            self.reject("conflict", lambda: self.write(value, run_id=run_id))
        self.born("other-agent")
        self.open_run(owner="other-agent", run_id="run_0002")
        value = self.shaped("episode", uid="unit_002")
        value["body"]["run_id"] = value["provenance"]["run_id"] = "run_0002"
        self.reject("conflict", lambda: self.write(value))
        value["body"]["run_id"] = value["provenance"]["run_id"] = "unknown1"
        self.reject("no_run", lambda: self.write(value))

    def test_a11_non_episode_binding_has_no_latest_run_inference(self):
        self.runtime()
        self.open_run()
        value = self.shaped()
        value["provenance"]["run_id"] = "run_0001"
        self.reject("conflict", lambda: self.write(value, run_id="run_0002"))
        value["provenance"]["run_id"] = "unknown1"
        self.reject("no_run", lambda: self.write(value))
        value["provenance"]["run_id"] = "run_0001"
        self.write(value)

    def test_a12_all_frozen_episode_fields(self):
        self.runtime()
        self.open_run()
        value = self.shaped("episode")
        first = self.write(value)
        for path, replacement in ((("task_id",), "task_002"), (("seat", "model"), "other-model"),
                                  (("seat", "effort"), "high"), (("seat", "mode"), "interactive"),
                                  (("parents_context",), [{"agent_id": OWNER, "agent_version": "a" * 64, "run_id": "parent01"}])):
            candidate = self.shaped("episode", uid="unit_002")
            target = candidate["body"]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = replacement
            self.reject("conflict", lambda: self.write(candidate))
        self.assertNotIn("gate", first.event["payload"])
        self.assertNotIn("run.close", [e["kind"] for e in self.snapshot().events])

    def test_a13_closure_refuses_new_write_but_not_replay(self):
        self.runtime()
        self.open_run()
        value = self.shaped("episode")
        first = self.write(value, op="episode-original")
        self.close_run()
        self.reject("run_closed", lambda: self.write(self.shaped("episode", uid="unit_002")))
        before = self.fingerprint()
        replay = self.write(value, op="episode-original", expected=0)
        self.assertEqual(replay.value, first.value)
        self.assertEqual(replay.event, first.event)
        self.assertEqual(self.fingerprint(), before)
        changed = copy.deepcopy(value)
        changed["provenance"]["run_id"] = changed["body"]["run_id"] = "run_0002"
        self.reject("bad_op", lambda: self.write(changed, op="episode-original"))

    def test_a29_null_costs_in_get_history_fold_and_replay(self):
        self.runtime()
        self.open_run()
        episode = self.shaped("episode")
        first = self.write(episode, op="unknown-costs")
        for observed in (units.get(OWNER, episode["id"], ctx=self.ctx)["unit"],
                         self.write(episode, op="unknown-costs").value["unit"],
                         next(e["payload"]["unit"] for e in units.history(OWNER, ctx=self.ctx)["events"] if e["kind"] == "memory.put")):
            self.assertEqual(observed["body"]["cost"], COST)
            self.assertIn(b'"tokens_in":null', canonical(observed))
        folded = self.journal.fold(self.snapshot().events, registry=self.ctx.services.registry)
        from lineage.domain.memory.fold import units_for
        self.assertEqual(units_for(folded, OWNER)[0]["body"]["cost"], COST)
        workflow = self.shaped("workflow", uid="unit_002")
        self.write(workflow)
        self.assertIsNone(units.get(OWNER, "unit_002", ctx=self.ctx)["unit"]["body"]["stats"]["mean_reward"])
        zero = self.shaped("episode", uid="unit_003")
        zero["body"]["cost"]["tokens_in"] = 0
        self.assertEqual(self.write(zero).value["unit"]["body"]["cost"]["tokens_in"], 0)
        for bad in (True, -1):
            value = self.shaped("episode", uid="unit_004")
            value["body"]["cost"]["tokens_in"] = bad
            self.reject("bad_args", lambda: self.write(value))

    def test_a12_nonempty_parent_context_is_preserved(self):
        self.runtime()
        parents = [{"agent_id": "parent-agent", "agent_version": "a" * 64, "run_id": "parent01"}]
        self.open_run(parents=parents)
        value = self.shaped("episode")
        value["body"]["parents_context"] = copy.deepcopy(parents)
        self.assertEqual(self.write(value).value["unit"]["body"]["parents_context"], parents)
        value = self.shaped("episode", uid="unit_002")
        self.reject("conflict", lambda: self.write(value))
