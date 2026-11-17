"""Cross composition and conservative claims: A5 through A12, A31."""
from copy import deepcopy
from unittest import mock

from .helpers import OracleCase, SEAT, arguments, canonical, seam, sha, tree_bytes


class CrossTests(OracleCase):
    def test_a05_compatible_language_matrix_and_order(self):
        for n, (left, right, target) in enumerate((
                ("python", "python", "python"), ("general", "python", "python"),
                ("python", "general", "python"), ("general", "general", "general"))):
            with self.subTest(left=left, right=right):
                ids = ["left-" + str(n), "right-" + str(n)]
                self.parent(ids[0], language=left, display_name="First parent")
                self.parent(ids[1], language=right, display_name="Second parent")
                data = self.op(parent_ids=ids, child_id="child-" + str(n), op_id="cross-" + str(n))
                self.witness(data)
                self.assertEqual(data["record"]["parents"], ids)
                self.assertEqual(data["record"]["language"], target)
                self.assertEqual(data["record"]["display_name"], "First parent")
                self.assertEqual(data["record"]["generation"], 1)

    def test_a05_parent_reversal_changes_name_and_array_only_as_declared(self):
        self.parents(one={"display_name": "Left"}, two={"display_name": "Right"})
        one = self.op(child_id="child-one", op_id="cross-one")
        two = self.op(parent_ids=["parent-two", "parent-one"], child_id="child-two", op_id="cross-two")
        self.assertEqual(one["record"]["display_name"], "Left")
        self.assertEqual(two["record"]["display_name"], "Right")
        self.assertEqual(two["record"]["parents"], list(reversed(one["record"]["parents"])))
        for key in ("skills", "allowed_seats", "references", "constitution_sha256"):
            self.assertEqual(one["record"][key], two["record"][key])

    def test_a05_distinct_concrete_languages_reject(self):
        self.parents(two={"language": "javascript"})
        self.reject("bad_args")

    def test_a05_distinct_workflows_reject(self):
        self.parents(two={"workflow": "test"})
        self.reject("bad_args")

    def test_a05_explicit_name_changes_only_child_name(self):
        self.parents()
        before = tree_bytes(self.home)
        data = self.op(display_name="Explicit child")
        self.witness(data)
        self.assertEqual(data["record"]["display_name"], "Explicit child")
        for path, raw in before.items():
            if "parent-one" in path or "parent-two" in path:
                self.assertEqual(tree_bytes(self.home)[path], raw)

    def test_a06_seat_intersection_uses_complete_tuples_and_sorts(self):
        shared = [dict(SEAT, model="model-z"), dict(SEAT, model="model-a")]
        self.parents(one={"allowed_seats": shared + [dict(SEAT, effort="high")]},
                     two={"allowed_seats": list(reversed(shared)) + [dict(SEAT, mode="interactive")]})
        data = self.op()
        self.witness(data)
        self.assertEqual(data["record"]["allowed_seats"], list(reversed(shared)))
        self.assertNotIn("promoted_seat", data["record"])

    def test_a06_same_model_different_effort_has_empty_intersection(self):
        self.parents(two={"allowed_seats": [dict(SEAT, effort="high")]})
        self.reject("bad_args")

    def test_a06_same_model_different_mode_has_empty_intersection(self):
        self.parents(two={"allowed_seats": [dict(SEAT, mode="interactive")]})
        self.reject("bad_args")

    def test_a07_skill_union_collapses_equal_pins_and_sorts(self):
        first, second = self.publish("skill-zzz"), self.publish("skill-aaa")
        self.parents(one={"skills": [first]}, two={"skills": [second, first]})
        data = self.op()
        self.witness(data)
        self.assertEqual(data["record"]["skills"], [second, first])

    def test_a07_competing_skill_hashes_cannot_prefer_first_parent(self):
        one, two = self.publish(), self.publish(text="# Alternative\nPassive alternative.\n")
        self.parents(one={"skills": [one]}, two={"skills": [two]})
        for ids in (["parent-one", "parent-two"], ["parent-two", "parent-one"]):
            with self.subTest(parents=ids):
                self.reject("conflict", parent_ids=ids)

    def test_a07_retired_pin_resolves_historically_but_unknown_hash_rejects(self):
        pin = self.publish()
        self.parents(one={"skills": [pin]}, two={"skills": [pin]})
        self.success("skill_retire", dict(pin, reason="fixture retirement", agent="creator-agent", op_id="retire-skill"))
        data = self.op()
        self.witness(data)
        self.assertEqual(data["record"]["skills"], [pin])
        # A-U18: preserve historical-pin assertion through the integrated skill wrapper.
        self.assertNotEqual(self.success("skill_get", pin)["skill"]["sha256"], "0" * 64)
        # A-U18: this is a new mutation request, not reuse of the cross op_id.
        self.reject("hash_mismatch", "agent_mutate", args=arguments("agent_mutate", child_id="next-child",op_id="unknown-historical-pin",
                    change={"kind":"skill", "skill_id":pin["skill_id"], "from_sha256":pin["sha256"],
                            "to":dict(pin, sha256="0"*64)}))

    def _claims(self, kind, same_id=False, **changes):
        self.parents(one={"language": "general"})
        left = self.unit("unit_same" if same_id else "unit_left", kind,
                         scope={"workflow":"develop", "language":"general"})
        right = deepcopy(left)
        right["id"] = left["id"] if same_id else "unit_right"
        right["provenance"]["actor"] = "parent-two"
        right["scope"]["language"] = "python"
        right["body"].update(changes)
        self.put(left);self.put(right, "parent-two")
        return left, right

    def test_a09_distinct_subject_keys_coexist(self):
        self.parents()
        self.put(self.unit("unit_left"))
        self.put(self.unit("unit_right", owner="parent-two"), "parent-two")
        data = self.op()
        self.witness(data)
        self.assertEqual(len(data["inherited_units"]), 2)

    def test_a09_lesson_conflict_names_both_source_identities(self):
        left, right = self._claims("lesson", safer_action="incompatible action")
        result = self.reject("conflict")
        for value in ("parent-one", "parent-two", left["id"], right["id"]):
            self.assertIn(value, result["detail"])
        self.assertNotIn("incompatible action", result["detail"])
        reverse = self.reject("conflict", parent_ids=["parent-two", "parent-one"])
        self.assertEqual(reverse["detail"], result["detail"])

    def test_a09_negative_conflict_general_concrete(self):
        self._claims("negative", verdict="red", safer_action="different action")
        self.reject("conflict")

    def test_a09_workflow_steps_conflict(self):
        self._claims("workflow", steps=["incompatible step"])
        self.reject("conflict")

    def test_a09_normalized_subject_key_does_not_normalize_body_equality(self):
        self.parents()
        one = self.unit("unit_left")
        two = self.unit("unit_right", owner="parent-two")
        one["body"]["tempting_use"] = "  Shared\tTRIGGER "
        two["body"]["tempting_use"] = "shared trigger"
        two["body"]["safer_action"] = "different"
        self.put(one);self.put(two, "parent-two")
        self.reject("conflict")

    def test_a10_identical_claims_keep_two_ids_and_source_hashes(self):
        left, right = self._claims("lesson", same_id=True)
        data = self.op()
        self.witness(data)
        inherited = data["inherited_units"]
        self.assertEqual(len(inherited), 2)
        self.assertEqual(len({x["unit"]["id"] for x in inherited}), 2)
        for wrapper, source, owner in zip(inherited, (left,right), ("parent-one","parent-two")):
            self.assertEqual(wrapper["source_agent_id"], owner)
            self.assertEqual(wrapper["source_unit_id"], source["id"])
            self.assertEqual(wrapper["unit_sha256"], sha(canonical(source)))
            self.assertEqual(wrapper["unit"]["provenance"]["inherited_from"],
                {"agent_id":owner,"unit_id":source["id"],"unit_sha256":sha(canonical(source))})
        self.assertEqual(data["rejected_units"], [])

    def test_a10_workflow_statistics_do_not_conflict_or_merge(self):
        self._claims("workflow", stats={"runs":4,"successes":3,"mean_reward":0.5})
        data = self.op()
        self.assertEqual([x["unit"]["body"]["stats"]["runs"] for x in data["inherited_units"]], [1,4])
        self.witness(data)

    def test_a10_equal_statements_across_kinds_are_not_claim_overlap(self):
        self.parents()
        a,b = self.unit("unit_left"),self.unit("unit_right", "negative", owner="parent-two")
        a["statement"]=b["statement"]="Same statement"
        self.put(a);self.put(b,"parent-two")
        self.assertEqual(len(self.op()["inherited_units"]), 2)

    def test_a08_alias_canonical_overrides_union_and_reversion(self):
        self.parents()
        # Rule identity comes from the verified bundled source, never substring matching.
        source = self.success("reference_get", {"ref_id":"gold_s1"})["reference"]["rules"]
        current = self.op(child_id="configuration-parent", op_id="configuration-parent")
        active = set(self.witness(current)["payload"]["constitution"]["rule_ids"])
        candidates = [r for r in source if r["id"] in active and not any(r["text"].startswith(p+" ") for p in ("I20","I21","I22"))]
        self.assertTrue(candidates, "HOLD: no verified mutable active rule")
        rule = candidates[0]["id"]
        child = self.op("agent_mutate", parent_id="configuration-parent", child_id="override-parent",
                        op_id="override-parent", change={"kind":"rule","rule_id":rule,"text":"remove"})
        self.assertEqual(child["record"]["rule_overrides"], {rule:"remove"})
        result = self.op(parent_ids=["override-parent","parent-two"], child_id="override-child", op_id="override-child")
        self.assertEqual(result["record"]["rule_overrides"], {rule:"remove"})
        restored = self.op("agent_mutate", parent_id="override-child", child_id="restored-child", op_id="restore",
                           change={"kind":"rule","rule_id":rule,"text":"add"})
        self.assertEqual(restored["record"]["rule_overrides"], {rule:"add"})

    def test_a08_opposite_overrides_reject(self):
        self.parents()
        baseline = self.op(child_id="base-child", op_id="base")
        rule = next(r for r in self.witness(baseline)["payload"]["constitution"]["rule_ids"]
                    if r not in {"I20","I21","I22","GS-4.1-20","GS-4.1-21","GS-4.1-22"})
        self.op("agent_mutate", parent_id="parent-one", child_id="remove-child", op_id="remove",
                change={"kind":"rule","rule_id":rule,"text":"remove"})
        self.op("agent_mutate", parent_id="remove-child", child_id="add-child", op_id="add",
                change={"kind":"rule","rule_id":rule,"text":"add"})
        self.reject("conflict", parent_ids=["remove-child","add-child"])

    def test_a31_reordered_source_mapping_preserves_complete_audit(self):
        p,q = self.parents()
        a,b = self.unit("unit_left"),self.unit("unit_right",owner="parent-two")
        self.put(a);self.put(b,"parent-two")
        first=self.selection([p,q],{"parent-one":[a],"parent-two":[b]})
        second=self.selection([p,q],{"parent-two":[b],"parent-one":[a]})
        self.assertEqual(canonical(first.inherited),canonical(second.inherited))
        self.assertEqual(canonical(first.rejected),canonical(second.rejected))

    def test_a08_compiler_conflict_has_no_parent_preference_fallback(self):
        self.parents()
        compiler=self.module("lineage.domain.constitution")
        from lineage.core.errors import LineageError
        refusal=mock.Mock(side_effect=LineageError("conflict","contradictory verified overlay composition"))
        with seam(compiler,"compile_constitution",refusal):
            self.reject("conflict")
        self.assertGreaterEqual(refusal.call_count,1)

    def test_a08_recompile_union_uses_verified_empty_overlay_sets(self):
        self.parents()
        # A-U18: the U12 compiler adapter receives overlay IDs; the lower-level
        # compiler receives verified policy mappings, not the requested ID list.
        compiler=self.module("lineage.domain.agents")
        seen=mock.Mock(wraps=compiler._compile)
        with seam(compiler,"_compile",seen):
            data=self.op()
        event=self.witness(data)
        self.assertEqual(event["payload"]["constitution"]["overlays"],[])
        self.assertTrue(seen.call_args_list)
        self.assertTrue(all(list(c.args[1])==[] for c in seen.call_args_list))

    def test_a07_corrupt_materialized_skill_package_cannot_be_inherited(self):
        text="# Integrity fixture\nOnly this immutable package has these bytes.\n"
        pin=self.publish(text=text)
        self.parents(one={"skills":[pin]})
        candidates=[p for p in self.home.rglob("SKILL.md") if p.is_file() and p.read_text()==text]
        self.assertTrue(candidates,"HOLD: skill materialization is AUSENTE")
        for p in candidates:p.write_text("tampered package\n")
        self.reject("hash_mismatch")

    def test_a09_raw_body_whitespace_difference_is_conflict(self):
        self.parents()
        a=self.unit("unit_left")
        b=deepcopy(a);b["id"]="unit_right";b["provenance"]["actor"]="parent-two"
        b["body"]["safer_action"]=" verify   INPUT "
        self.put(a);self.put(b,"parent-two")
        self.reject("conflict")

    def test_a09_conflicts_within_one_parent_are_not_ignored(self):
        self.parents()
        a=self.unit("unit_left");b=deepcopy(a);b["id"]="unit_right"
        b["body"]["safer_action"]="incompatible advice"
        self.put(a);self.put(b)
        result=self.reject("conflict")
        self.assertIn("unit_left",result["detail"]);self.assertIn("unit_right",result["detail"])

    def test_a10_normalized_statements_compare_without_rewriting_sources(self):
        self.parents()
        a=self.unit("unit_left");b=deepcopy(a)
        b["id"]="unit_right";b["provenance"]["actor"]="parent-two"
        a["statement"]="  SAME\tstatement ";b["statement"]="same STATEMENT"
        self.put(a);self.put(b,"parent-two")
        data=self.op()
        self.assertEqual([w["unit"]["statement"] for w in data["inherited_units"]],[a["statement"],b["statement"]])
        self.witness(data)

    def test_a11_excluded_claim_does_not_create_conflict(self):
        self.parents()
        a=self.unit("unit_left");b=deepcopy(a)
        b["id"]="unit_priv";b["provenance"]["actor"]="parent-two"
        b["privacy"]="private";b["body"]["safer_action"]="PRIVATE_CONFLICT_SENTINEL"
        self.put(a);self.put(b,"parent-two")
        data=self.op();self.witness(data)
        self.assertEqual(len(data["inherited_units"]),1)
        self.assertEqual(data["rejected_units"],[{"agent_id":"parent-two","unit_id":"unit_priv","reason":"private"}])
        self.assertNotIn("PRIVATE_CONFLICT_SENTINEL",canonical(data).decode())

    def test_a08_supported_source_alias_and_canonical_override_share_one_identity(self):
        self.parents()
        baseline=self.op(child_id="baseline-child",op_id="baseline-op")
        active=set(self.witness(baseline)["payload"]["constitution"]["rule_ids"])
        rules=self.success("reference_get",{"ref_id":"gold_s1"})["reference"]["rules"]
        source=next(r for r in rules if r["id"] in active and not any(r["text"].startswith(p+" ") for p in ("I20","I21","I22")))
        canonical_id=source["id"];alias=source["text"].split()[0]
        before=self.ledger_bytes()
        request=arguments("agent_mutate",parent_id="parent-one",child_id="alias-parent",op_id="alias-request",
                          change={"kind":"rule","rule_id":alias,"text":"remove"})
        result=self.call("agent_mutate",request)
        if result.get("ok") is False:
            # An alias unsupported by the verified registry is bad_args. No
            # invented spelling is assumed to be a supported positive alias.
            self.assertEqual(result["code"],"bad_args")
            self.assertEqual(self.ledger_bytes(),before)
            request["change"]["rule_id"]=canonical_id
            result=self.call("agent_mutate",request)
        self.assertEqual(set(result),{"untrusted"})
        self.assertEqual(result["untrusted"]["record"]["rule_overrides"],{canonical_id:"remove"})
        self.op("agent_mutate",parent_id="parent-two",child_id="canonical-parent",op_id="canonical-request",
                change={"kind":"rule","rule_id":canonical_id,"text":"remove"})
        child=self.op(parent_ids=["alias-parent","canonical-parent"],child_id="alias-cross",op_id="alias-cross")
        self.assertEqual(child["record"]["rule_overrides"],{canonical_id:"remove"})
        self.witness(child)

    def test_a31_seat_pin_and_source_order_preserve_artifacts_at_fixed_identity(self):
        import itertools
        from lineage.core import app
        primary=self.home
        def scenario(reverse):
            a,b=self.publish("skill-aaa"),self.publish("skill-zzz")
            pins=[a,b]
            seats=[dict(SEAT,model="model-a"),dict(SEAT,model="model-z")]
            sources=[self.unit("unit_left"),self.unit("unit_right")]
            if reverse:pins.reverse();seats.reverse();sources.reverse()
            self.parents(one={"skills":pins,"allowed_seats":seats},two={"skills":pins,"allowed_seats":seats})
            for source in sources:self.put(source)
            data=self.op()
            event=self.witness(data)
            return {"record":data["record"],"inherited_units":data["inherited_units"],
                    "rejected_units":data["rejected_units"],"constitution":event["payload"]["constitution"]}
        first=scenario(False)
        self.home=primary/"permuted-home";self.home.mkdir()
        self.sequence=itertools.count(1)
        self.context=app.create_context(self.home,registry=self.reg)
        second=scenario(True)
        self.assertEqual(canonical(first),canonical(second))
