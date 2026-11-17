"""Language scope, inherited exclusions and evidence safety: A11/A12/A17/A18."""
from copy import deepcopy
from unittest import mock

from .helpers import OracleCase, arguments, canonical, seam, sha, tree_bytes


class SpecializeTests(OracleCase):
    OP="agent_specialize"

    def test_a17_general_and_exact_target_only_without_relabeling(self):
        self.parent(language="general")
        sources=[]
        for uid, language in (("unit_gen1","general"),("unit_py01","python"),("unit_js01","javascript")):
            unit=self.unit(uid,scope={"workflow":"develop","language":language})
            sources.append(unit)
        # A-U18: current writes forbid mixed concrete scopes on general parents.
        self.put(sources[0])
        self.source_snapshot(sources)
        data=self.op(language="python")
        self.witness(data)
        self.assertEqual([w["source_unit_id"] for w in data["inherited_units"]],["unit_gen1","unit_py01"])
        self.assertEqual(data["rejected_units"],[{"agent_id":"parent-one","unit_id":"unit_js01","reason":"scope_mismatch"}])
        self.assertEqual([w["unit"]["scope"]["language"] for w in data["inherited_units"]],["general","python"])
        self.assertEqual(self.get_agent("parent-one")["language"],"general")

    def test_a17_same_language_target_is_valid(self):
        self.parent()
        self.put(self.unit())
        data=self.op(language="python")
        self.witness(data)
        self.assertEqual(len(data["inherited_units"]),1)

    def test_a17_general_target_does_not_broaden_concrete_memory(self):
        self.parent()
        self.put(self.unit("unit_gen1",scope={"workflow":"develop","language":"general"}))
        self.put(self.unit("unit_py01"))
        data=self.op(language="general")
        self.assertEqual([w["source_unit_id"] for w in data["inherited_units"]],["unit_gen1"])
        self.assertEqual(data["rejected_units"][0]["reason"],"scope_mismatch")

    def test_a17_language_comparison_is_case_sensitive(self):
        # A-U18: a concrete owner admits python memory; target Python still differs.
        self.parent()
        self.put(self.unit())
        data=self.op(language="Python")
        self.assertEqual(data["inherited_units"],[])
        self.assertEqual(data["rejected_units"][0]["reason"],"scope_mismatch")

    def test_a17_blank_and_control_character_languages_reject(self):
        self.parent()
        for language in ("", " ", "\t", "python\nrole=orchestrate", "python\r", "p\x00", "p\x1f", "p\x7f"):
            with self.subTest(language=language):
                self.reject("bad_args",language=language)

    def test_a18_preserves_pins_seats_references_overlays_and_overrides(self):
        pin=self.publish()
        parent=self.parent(language="general",skills=[pin])
        # A-U18: use a compiler-supported concrete language for the changed-
        # constitution fixture; other languages compile under its general policy.
        data=self.op(language="typescript")
        event=self.witness(data)
        for key in ("workflow","allowed_seats","references","skills"):
            self.assertEqual(parent[key],data["record"][key])
        self.assertEqual(data["record"]["language"],"typescript")
        self.assertEqual(event["payload"]["constitution"]["overlays"],[])
        self.assertNotEqual(parent["constitution_sha256"],data["record"]["constitution_sha256"])

    def test_a18_retired_skill_can_be_resolved_by_historical_pin(self):
        pin=self.publish()
        self.parent(skills=[pin])
        self.success("skill_retire",dict(pin,reason="fixture retirement",agent="creator-agent",op_id="retire-pin"))
        data=self.op()
        self.assertEqual(data["record"]["skills"],[pin])
        self.witness(data)

    def test_a11_private_content_never_reaches_child_or_brief(self):
        self.parent()
        sentinel="PRIVATE_CONTEXT_SENTINEL"
        self.put(self.unit("unit_priv",privacy="private",statement=sentinel))
        data=self.op()
        self.assertEqual(data["inherited_units"],[])
        self.assertEqual(data["rejected_units"],[{"agent_id":"parent-one","unit_id":"unit_priv","reason":"private"}])
        self.assertNotIn(sentinel,canonical(data).decode())
        child_files={k:v for k,v in tree_bytes(self.home).items() if "child-agent" in k}
        self.assertTrue(child_files,"HOLD: child materialization is AUSENTE")
        for raw in child_files.values():
            self.assertNotIn(sentinel.encode(),raw)

    def test_a11_real_selector_reports_every_exclusion_and_precedence(self):
        parent=self.parent()
        fixtures=[]
        cases=(("episode",{},"episode"),("ruling",{},"level_one"),
               ("lesson",{"level":3},"level_three"),("lesson",{"privacy":"private"},"private"),
               ("lesson",{"status":"retired"},"inactive"),("lesson",{"receipts":[]},"missing_receipt"),
               ("workflow",{},"not_promoted"),("decision",{},"kind_not_inheritable"),
               ("open_item",{},"kind_not_inheritable"))
        expected={}
        for i,(kind,changes,reason) in enumerate(cases):
            unit=self.unit("exclude_%02d"%i,kind,**changes)
            if reason=="not_promoted":unit["body"]["status"]="candidate"
            fixtures.append(unit);expected[unit["id"]]=reason
        # Direct policy fixtures exercise the real U17 selector. Schema-invalid
        # historical exclusions are not inserted through a permissive validator.
        selected=self.selection([parent],{"parent-one":fixtures})
        self.assertEqual(selected.inherited,())
        self.assertEqual({r["unit_id"]:r["reason"] for r in selected.rejected},expected)
        overlap=self.unit("overlap1","episode",privacy="private",status="retired",receipts=[])
        selected=self.selection([parent],{"parent-one":[overlap]})
        self.assertEqual(len(selected.rejected),1)
        # The exact multi-disqualification winner belongs to U17. Each birth
        # must reuse it instead of installing a second precedence in U18.
        inherit=self.module("lineage.domain.breeding.inherit")
        self.assertIsNotNone(inherit.select)

    def test_a11_valid_three_kinds_survive_each_operator(self):
        for i,tool in enumerate(("agent_cross","agent_mutate","agent_specialize")):
            with self.subTest(tool=tool):
                owner="source-"+str(i)
                pin=self.publish("skill-"+str(i))
                target=self.publish("target-"+str(i))
                self.parent(owner,skills=[pin])
                for j,kind in enumerate(("lesson","negative","workflow")):
                    self.put(self.unit("valid_%d%d"%(i,j),kind,owner=owner),owner)
                changes={"child_id":"child-"+str(i),"op_id":"birth-"+str(i)}
                if tool=="agent_cross":
                    other="other-"+str(i);self.parent(other)
                    changes["parent_ids"]=[owner,other]
                else:
                    changes["parent_id"]=owner
                    if tool=="agent_mutate":
                        changes["change"]={"kind":"skill","skill_id":pin["skill_id"],"from_sha256":pin["sha256"],"to":target}
                data=self.op(tool,**changes)
                self.witness(data,tool)
                self.assertEqual({w["unit"]["kind"] for w in data["inherited_units"]},{"lesson","negative","workflow"})

    def test_a12_changed_or_missing_receipt_is_excluded_not_fatal(self):
        self.parent()
        unit=self.put(self.unit())
        path=self.home/unit["receipts"][0]["path"]
        path.write_bytes(b"changed evidence\n")
        data=self.op()
        self.assertEqual(data["inherited_units"],[])
        self.assertEqual(data["rejected_units"][0]["reason"],"invalid_receipt")
        path.unlink()
        data=self.op(child_id="next-child",op_id="next-op")
        self.assertEqual(data["rejected_units"][0]["reason"],"invalid_receipt")

    def test_a12_internal_symlink_and_directory_receipts_are_invalid(self):
        self.parent()
        unit=self.put(self.unit())
        path=self.home/unit["receipts"][0]["path"]
        saved=self.home/"evidence/saved.txt";path.rename(saved)
        path.symlink_to(saved.name)
        data=self.op()
        self.assertEqual(data["rejected_units"][0]["reason"],"invalid_receipt")
        path.unlink();path.mkdir()
        data=self.op(child_id="directory-child",op_id="directory-op")
        self.assertEqual(data["rejected_units"][0]["reason"],"invalid_receipt")

    def test_a12_forbidden_normalized_receipt_paths_are_invalid(self):
        parent=self.parent()
        for i,path in enumerate(("../escape.txt","ledger/proof.txt","family/proof.txt","./ledger/proof.txt",
                                 "a/../ledger/proof.txt","./family/proof.txt","a/../family/proof.txt")):
            with self.subTest(path=path):
                unit=self.unit("unsafe_%02d"%i)
                unit["receipts"][0]["path"]=path
                selected=self.selection([parent],{"parent-one":[unit]})
                self.assertEqual(selected.inherited,())
                self.assertEqual(selected.rejected[0]["reason"],"invalid_receipt")

    def test_a12_symlink_ancestor_outside_resolved_home_is_allowed(self):
        self.parent()
        self.put(self.unit())
        link=self.home.parent/(self.home.name+"-alias")
        link.symlink_to(self.home,target_is_directory=True)
        self.addCleanup(link.unlink)
        original=self.context
        self.context=type(original)(link.resolve(),original.validators,original.folds,original.actor,original.op_id)
        data=self.op()
        self.assertEqual(len(data["inherited_units"]),1)
        self.witness(data)

    def test_a11_u18_uses_real_u17_precedence_for_overlapping_exclusions(self):
        parent=self.parent()
        unit=self.put(self.unit("overlap1",level=3,privacy="private",receipts=[]))
        expected=self.selection([parent],{"parent-one":[unit]})
        self.assertEqual(len(expected.rejected),1)
        data=self.op()
        self.assertEqual(data["rejected_units"],list(expected.rejected))
        self.assertEqual(data["inherited_units"],[])

    def test_a17_foreign_ruling_and_wrong_workflow_are_never_relabelled(self):
        parent=self.parent(language="general")
        ruling=self.unit("foreign1","ruling",provenance={"origin":"foreign-project","actor":"operator"})
        lesson=self.unit("wrongwf1",scope={"workflow":"review","language":"python"})
        selected=self.selection([parent],{"parent-one":[ruling,lesson]})
        self.assertEqual(selected.inherited,())
        self.assertEqual({x["unit_id"]:x["reason"] for x in selected.rejected},
                         {"foreign1":"level_one","wrongwf1":"scope_mismatch"})
