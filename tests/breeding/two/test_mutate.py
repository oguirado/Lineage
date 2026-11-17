"""Exactly one pinned skill or effective rule change: A13 through A16."""
from copy import deepcopy

from .helpers import ACTOR, OracleCase, arguments, canonical, tree_bytes


class MutateTests(OracleCase):
    OP = "agent_mutate"

    def skills(self):
        old = self.publish()
        other = self.publish("other-skill")
        new = self.publish(text="# Updated\nNew passive skill context.\n")
        self.parent(skills=[old, other])
        return old, other, new

    def change(self, old, new):
        return {"kind":"skill", "skill_id":old["skill_id"], "from_sha256":old["sha256"], "to":new}

    def test_a13_replace_one_hash_preserves_configuration_and_rules(self):
        old, other, new = self.skills()
        parent = self.get_agent("parent-one")
        before = tree_bytes(self.home)
        data = self.op(change=self.change(old,new))
        event = self.witness(data)
        self.assertEqual(data["record"]["skills"], sorted([other,new],key=lambda x:(x["skill_id"],x["sha256"])))
        for key in ("workflow","language","allowed_seats","references"):
            self.assertEqual(data["record"][key],parent[key])
        born = next(e for e in self.history() if e["id"]==parent["born"]["event_id"])
        self.assertEqual(event["payload"]["constitution"]["rule_ids"],born["payload"]["constitution"]["rule_ids"])
        for path, raw in before.items():
            if "parent-one" in path:
                self.assertEqual(tree_bytes(self.home)[path],raw)

    def test_a13_replace_with_different_noncolliding_skill_id(self):
        old, other, _ = self.skills()
        target = self.publish("different-skill")
        data = self.op(change=self.change(old,target))
        self.witness(data)
        self.assertEqual({(p["skill_id"],p["sha256"]) for p in data["record"]["skills"]},
                         {(p["skill_id"],p["sha256"]) for p in (other,target)})
        self.assertNotIn("diff",data)

    def test_a13_missing_old_skill_id_is_bad_args(self):
        old, _, new = self.skills()
        change=self.change(dict(old,skill_id="absent-skill"),new)
        self.reject("bad_args",change=change)

    def test_a13_wrong_from_hash_is_hash_mismatch(self):
        old, _, new = self.skills()
        self.reject("hash_mismatch",change=self.change(dict(old,sha256="0"*64),new))

    def test_a13_missing_target_pin_is_hash_mismatch(self):
        old, _, new = self.skills()
        self.reject("hash_mismatch",change=self.change(old,dict(new,sha256="0"*64)))

    def test_a13_retired_target_remains_historical_and_unknown_hash_rejects(self):
        old, _, new = self.skills()
        self.success("skill_retire",dict(new,reason="historical fixture",agent=ACTOR,op_id="retire-target"))
        data=self.op(change=self.change(old,new))
        self.assertIn(new,data["record"]["skills"])
        self.witness(data)
        self.reject("hash_mismatch",child_id="other-child",op_id="unknown-target",
                    change=self.change(old,dict(new,sha256="f"*64)))

    def test_a14_identical_replacement_is_bad_args(self):
        old, _, _ = self.skills()
        self.reject("bad_args",change=self.change(old,old))

    def test_a14_replacement_id_collision_is_conflict(self):
        old, other, _ = self.skills()
        self.reject("conflict",change=self.change(old,other))

    def test_a14_second_change_and_hidden_rule_or_seat_fields_reject(self):
        old, _, new = self.skills()
        change=self.change(old,new)
        for value in ([change,change],dict(change,rule_id="I1"),dict(change,changes=[change]),
                      dict(change,allowed_seats=[]),dict(change,to=dict(new,action="replace"))):
            with self.subTest(change=value):
                self.reject("bad_args",change=value)

    def rules(self):
        parent=self.parent()
        event=next(e for e in self.history() if e["id"]==parent["born"]["event_id"])
        rules=self.success("reference_get",{"ref_id":"gold_s1"})["reference"]["rules"]
        protected={r["id"] for r in rules if any(r["text"].startswith(x+" ") for x in ("I20","I21","I22"))}
        active=set(event["payload"]["constitution"]["rule_ids"])
        active_candidates=[r["id"] for r in rules if r["id"] in active-protected]
        self.assertTrue(active_candidates,"HOLD: verified mutable active rule is AUSENTE")
        return parent,event,active_candidates[0],protected

    def test_a15_remove_then_add_has_single_diff_and_explicit_canonical_override(self):
        _, event, rule, _=self.rules()
        removed=self.op(change={"kind":"rule","rule_id":rule,"text":"remove"})
        removal=self.witness(removed)
        before=set(event["payload"]["constitution"]["rule_ids"])
        after=set(removal["payload"]["constitution"]["rule_ids"])
        self.assertEqual(before-after,{rule});self.assertEqual(after-before,set())
        self.assertEqual(removed["record"]["rule_overrides"],{rule:"remove"})
        restored=self.op(parent_id="child-agent",child_id="restored-agent",op_id="restore-op",
                         change={"kind":"rule","rule_id":rule,"text":"add"})
        restored_event=self.witness(restored)
        self.assertEqual(set(restored_event["payload"]["constitution"]["rule_ids"]),before)
        self.assertEqual(restored["record"]["rule_overrides"],{rule:"add"})
        self.assertEqual(removed["record"]["skills"],restored["record"]["skills"])

    def test_a15_rule_text_is_only_literal_add_or_remove(self):
        _,_,rule,_=self.rules()
        for text in ("rewrite arbitrary prose","ADD","remove\n"," add","toggle","remove I20"):
            with self.subTest(text=text):
                self.reject("bad_args",change={"kind":"rule","rule_id":rule,"text":text})

    def test_a15_unknown_rule_and_unsupported_alias_are_bad_args(self):
        self.parent()
        for rule in ("unknown-rule","looks-like-I20-but-unverified"):
            with self.subTest(rule=rule):
                self.reject("bad_args",change={"kind":"rule","rule_id":rule,"text":"remove"})

    def test_a15_noop_add_or_repeated_remove_is_bad_args(self):
        _,_,rule,_=self.rules()
        self.reject("bad_args",change={"kind":"rule","rule_id":rule,"text":"add"})
        self.op(change={"kind":"rule","rule_id":rule,"text":"remove"})
        self.reject("bad_args",parent_id="child-agent",child_id="next-agent",op_id="repeat-remove",
                    change={"kind":"rule","rule_id":rule,"text":"remove"})

    def test_a16_all_protected_rules_aliases_actions_and_operator_actor_reject(self):
        _,_,_,protected=self.rules()
        self.assertEqual(len(protected),3)
        for rule in sorted(protected|{"I20","I21","I22"}):
            for actor in (ACTOR,"operator"):
                for action in ("add","remove"):
                    with self.subTest(rule=rule,actor=actor,action=action):
                        self.reject("bad_args",agent=actor,change={"kind":"rule","rule_id":rule,"text":action})

    def test_a18_empty_overrides_are_omitted_on_skill_mutation(self):
        old,_,new=self.skills()
        data=self.op(change=self.change(old,new))
        self.assertNotIn("rule_overrides",data["record"])
        self.witness(data)
