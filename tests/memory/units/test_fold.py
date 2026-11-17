"""A22–A25: pure fold observables and committed generation matrix."""
import copy
from ._support import OracleCase, IntegrationCase, OWNER, canonical, unit, event, put_event, birth_payload, sha
from lineage.domain.memory import fold, units


class FoldTests(OracleCase):
    def fresh(self):
        return {"memory": fold.empty(), "agents": {"untouched": {"marker": ["original"]}},
                "runs": {}, "references": {}, "skills": {}, "arena": {},
                "scorecards": {}, "tree": {}, "promotion": {}}

    def test_a22_fresh_empty_and_namespace_ownership(self):
        first, second = fold.empty(), fold.empty()
        first["fixture-marker"] = {"value": []}
        self.assertNotIn("fixture-marker", second)
        state = self.fresh()
        other = copy.deepcopy({k: v for k, v in state.items() if k != "memory"})
        current = put_event(unit())
        original = copy.deepcopy(current)
        fold.apply(state, current)
        self.assertEqual(current, original)
        self.assertEqual({k: v for k, v in state.items() if k != "memory"}, other)
        before = copy.deepcopy(state)
        fold.apply(state, event("agent.status", {"agent_id": OWNER, "from": "draft", "to": "retired", "reason": "fixture"}))
        self.assertEqual(state, before)
        current["payload"]["unit"]["statement"] = "external mutation"
        self.assertEqual(fold.units_for(state, OWNER)[0]["statement"], "verify input")

    def test_a22_deterministic_prefix_and_reciprocal_fold(self):
        predecessor = unit()
        successor = unit(uid="unit_002")
        successor["supersedes"] = [predecessor["id"]]
        events = [put_event(predecessor), put_event(successor, 2)]
        snapshots = []
        for _ in range(2):
            state = self.fresh()
            for current in events:
                fold.apply(state, current)
            snapshots.append(state)
        self.assertEqual(canonical(snapshots[0]["memory"]), canonical(snapshots[1]["memory"]))
        all_units = fold.units_for(snapshots[0], OWNER, include_inactive=True)
        self.assertEqual(all_units[0]["status"], "superseded")
        self.assertEqual(all_units[0]["superseded_by"], successor["id"])
        self.assertEqual(events[0]["payload"]["unit"], predecessor)

    def test_a23_inherited_birth_preserves_parent_and_source_provenance(self):
        source = self.shaped(uid="source01")
        child = copy.deepcopy(source)
        child["id"] = "child001"
        child["provenance"]["actor"] = "child-agent"
        child["provenance"]["inherited_from"] = {"agent_id": OWNER, "unit_id": source["id"], "unit_sha256": sha(canonical(source))}
        inherited = {"unit": child, "source_agent_id": OWNER, "source_unit_id": source["id"], "unit_sha256": sha(canonical(source))}
        state = self.fresh()
        fold.apply(state, put_event(source))
        parent_before = fold.units_for(state, OWNER)
        born = event("agent.born", birth_payload("child-agent", inherited=[inherited], memory_gen=7, parent=OWNER), 2)
        self.shape_check(born, "event.schema.json")
        before = copy.deepcopy(born)
        fold.apply(state, born)
        self.assertEqual(fold.units_for(state, "child-agent"), (child,))
        self.assertEqual(fold.units_for(state, OWNER), parent_before)
        self.assertEqual(born, before)

    def test_a25_private_inactive_flags_independent_order_and_copies(self):
        state = self.fresh()
        expected = []
        for n, (status, privacy) in enumerate((s, p) for s in ("active", "draft", "retired") for p in ("public", "internal", "private")):
            value = unit(uid="unit_%03d" % n)
            value.update(status=status, privacy=privacy)
            fold.apply(state, put_event(value, n + 1))
            expected.append(value)
        fold.apply(state, put_event(unit(uid="foreign1", actor="other-agent"), 20, "other-agent"))
        for inactive in (False, True):
            for private in (False, True):
                found = fold.units_for(state, OWNER, include_inactive=inactive, include_private=private)
                wanted = [u for u in expected if (inactive or u["status"] == "active") and (private or u["privacy"] != "private")]
                self.assertIsInstance(found, tuple)
                self.assertEqual(found, tuple(sorted(wanted, key=lambda u: u["id"])))
                if found:
                    found[0]["body"]["blocked_use"].append("corruption")
                self.assertEqual(fold.units_for(state, OWNER, include_inactive=inactive, include_private=private), tuple(wanted))


class GenerationTests(IntegrationCase):
    def test_a23_clone_captured_generation_is_not_inherited_count(self):
        self.runtime()
        source = self.shaped(uid="source01")
        self.write(source)
        self.born("child-agent", memory_gen=7, parent=OWNER)
        observation = unit("open_item", 3, actor="child-agent")
        result = self.write(observation, owner="child-agent", actor="child-agent")
        self.assertEqual(result.value["memory_gen"], 7)

    def test_a24_brief_membership_matrix(self):
        self.runtime()
        generation = 0
        for index, kind in enumerate(("ruling", "lesson", "negative", "workflow")):
            if kind == "ruling":
                committed = self.ruling(quote=b"generation ruling")
            else:
                committed = self.write(self.shaped(kind, uid="brief_%02d" % index))
            generation += 1
            self.assertEqual(committed.value["memory_gen"], generation)
            self.raw_append("memory.retire", {"agent_id": OWNER, "unit_id": committed.value["unit"]["id"]},
                            actor="operator" if kind == "ruling" else OWNER,
                            authority="operator" if kind == "ruling" else "tool")
            generation += 1
            probe = self.write(unit("open_item", 3, uid="probe_%02d" % index))
            self.assertEqual(probe.value["memory_gen"], generation)
        for index, lifecycle in enumerate(("candidate", "promoted", "retired")):
            workflow = self.shaped("workflow", uid="flow_%03d" % index)
            workflow["body"]["status"] = lifecycle
            generation += 1
            self.assertEqual(self.write(workflow).value["memory_gen"], generation)

    def test_a24_nonbrief_and_inactive_changes_do_not_increment(self):
        self.runtime()
        initial = self.write().value["memory_gen"]
        self.open_run()
        for n, kind in enumerate(("episode", "decision", "open_item")):
            value = self.shaped(kind, uid="other_%02d" % n)
            self.assertEqual(self.write(value).value["memory_gen"], initial)
        for n, (status, privacy) in enumerate((("active", "private"), ("draft", "internal"), ("retired", "public"))):
            value = unit(uid="hidden%02d" % n)
            value.update(status=status, privacy=privacy)
            result = self.write(value, op="hidden-%d" % n)
            self.assertEqual(result.value["memory_gen"], initial)
            self.assertEqual(self.write(value, op="hidden-%d" % n).value, result.value)
        replacement = unit(uid="unit_002")
        replacement.update(status="draft", supersedes=["unit_001"])
        self.assertEqual(self.write(replacement).value["memory_gen"], initial + 1)
