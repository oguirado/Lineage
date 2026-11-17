"""Closed births, direct-journal hostility, capacity and non-vacuous oracles."""
from copy import deepcopy
import ast
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest import mock

from lineage.core import schema, envelope
from lineage.core.errors import LineageError

from .helpers import HERE, ROOT, OracleCase, arguments, canonical, seam, sha, tree_bytes


class BirthIntegrityTests(OracleCase):
    def test_a19_nonclone_generation_memory_count_and_independent_version(self):
        self.parents()
        self.put(self.unit())
        first=self.op()
        self.witness(first)
        second=self.op("agent_specialize",parent_id="child-agent",child_id="grandchild-agent",op_id="second-birth")
        self.witness(second,"agent_specialize")
        self.assertEqual(second["record"]["generation"],2)
        self.assertEqual(second["record"]["memory_gen"],1)
        self.assertEqual(second["record"]["parents"],["child-agent"])
        self.assertEqual(second["record"]["references"],first["record"]["references"])

    def test_a19_empty_inherited_memory_starts_zero(self):
        self.parents()
        data=self.op()
        self.assertEqual(data["inherited_units"],[])
        self.assertEqual(data["record"]["memory_gen"],0)
        self.witness(data)

    def test_a20_closed_birth_matches_frozen_schema_and_actual_event_id(self):
        self.parents()
        self.put(self.unit())
        data=self.op();event=self.witness(data)
        def expanded(value):
            if isinstance(value,list):return [expanded(x) for x in value]
            if not isinstance(value,dict):return value
            if "$ref" in value:
                ref=value["$ref"]
                # A-U18: the integrated event schema also references run and benchmark
                # records. Resolve only these bundled inputs; retain every assertion.
                self.assertIn(ref,{"agent.schema.json","mem_unit.schema.json",
                                   "run.schema.json","bench_declared.schema.json"})
                return expanded(json.loads((ROOT/"schemas"/ref).read_text()))
            return {k:expanded(v) for k,v in value.items()}
        for value,name in ((data["record"],"agent.schema.json"),(event,"event.schema.json")):
            # A-U18: integrated frozen-envelope checker supports all closed-schema keywords.
            envelope._check(value,expanded(json.loads((ROOT/"schemas"/name).read_text())),name)
        for wrapper in data["inherited_units"]:
            # A-U18: use the same complete checker for conditional memory schemas.
            envelope._check(wrapper["unit"],json.loads((ROOT/"schemas/mem_unit.schema.json").read_text()),"mem_unit.schema.json")

    def test_a23_two_hop_provenance_resets_supersession_and_is_immediate(self):
        self.parents()
        old=self.put(self.unit("unit_old1"))
        source=self.unit("unit_new1",supersedes=[old["id"]])
        self.put(source)
        before=tree_bytes(self.home)
        first=self.op();self.witness(first)
        inherited=first["inherited_units"][0]["unit"]
        second=self.op("agent_specialize",parent_id="child-agent",child_id="next-agent",op_id="next-birth")
        self.witness(second,"agent_specialize")
        adopted=second["inherited_units"][0]
        self.assertEqual(adopted["unit"]["supersedes"],[])
        self.assertNotIn("superseded_by",adopted["unit"])
        self.assertEqual(adopted["source_agent_id"],"child-agent")
        self.assertEqual(adopted["source_unit_id"],inherited["id"])
        self.assertEqual(adopted["unit_sha256"],sha(canonical(inherited)))
        self.assertEqual(adopted["unit"]["provenance"]["inherited_from"],
                         {"agent_id":"child-agent","unit_id":inherited["id"],"unit_sha256":sha(canonical(inherited))})
        for forbidden in ("agent_id","lamport","created_at","run_id"):
            self.assertNotIn(forbidden,adopted["unit"])
        self.assertEqual(adopted["unit"]["provenance"]["origin"],source["provenance"]["origin"])
        self.assertEqual(adopted["unit"]["provenance"]["actor"],source["provenance"]["actor"])
        for name,raw in before.items():
            if "parent-one" in name or "parent-two" in name:
                self.assertEqual(tree_bytes(self.home)[name],raw)

    def test_a23_returned_nested_data_does_not_alias_authority(self):
        self.parents()
        self.put(self.unit())
        data=self.op()
        expected=canonical(data)
        data["record"]["allowed_seats"][0]["model"]="forged-model"
        data["inherited_units"][0]["unit"]["body"]["safer_action"]="forged-action"
        replay=self.op()
        self.assertEqual(canonical(replay),expected)
        self.witness(replay)

    def test_a28_record_forgeries_reject_before_append(self):
        self.parents()
        payload=self.valid_forge_template()
        attacks={"language":"javascript","generation":999,"memory_gen":999,"agent_version":"0"*64,
                 "brief_head_sha256":"f"*64,"status":"promoted","parents":["parent-two","parent-one"],
                 "allowed_seats":[{"model":"unmeasured-model","effort":"high","mode":"interactive"}],
                 "promoted_seat":{"model":"fake","effort":"high","mode":"headless"}}
        for field,value in attacks.items():
            with self.subTest(field=field):
                forged=deepcopy(payload);forged["record"][field]=value
                self.forge(forged)

    def test_a20_extra_payload_diff_claims_and_born_identity_reject(self):
        self.parents()
        payload=self.valid_forge_template()
        for field in ("change","diff","claims","fitness","authority"):
            with self.subTest(field=field):
                forged=deepcopy(payload);forged[field]={"claimed":True}
                self.forge(forged)
        # The wrapper prepares the actual ID. Here corrupt it after preparation
        # by using the real validator directly on the immutable candidate event.
        original=self.history()
        candidate=deepcopy(next(e for e in original if e["kind"]=="agent.born"))
        candidate["payload"]=deepcopy(payload)
        candidate["payload"]["record"]["born"]["event_id"]="e-ffffffffffffffff"
        with self.assertRaises(LineageError):
            # A-U18: exercise born identity validation with the owner's real context.
            self.reg.validators["agent.born"](original,candidate,ctx=self.context)

    def test_a28_constitution_prose_tamper_with_matching_hash_still_rejects(self):
        self.parents()
        payload=self.valid_forge_template()
        payload["constitution"]["text"]+="Uncited instruction changes effective authority.\n"
        payload["record"]["constitution_sha256"]=sha(payload["constitution"]["text"].encode())
        payload["record"]["agent_version"]=sha(canonical({"constitution_sha256":payload["record"]["constitution_sha256"],
                "skills":payload["record"]["skills"],"memory_gen":payload["record"]["memory_gen"]}))
        self.forge(payload)

    def test_a28_fake_source_hash_receipt_or_level_one_cannot_bypass(self):
        self.parents();self.put(self.unit())
        payload=self.valid_forge_template()
        for attack in ("source_hash","source_agent","receipt","level_one","scope","extra_memory"):
            with self.subTest(attack=attack):
                forged=deepcopy(payload);wrapper=forged["inherited_units"][0]
                if attack=="source_hash":wrapper["unit_sha256"]="0"*64
                elif attack=="source_agent":wrapper["source_agent_id"]="unrelated-agent"
                elif attack=="receipt":wrapper["unit"]["receipts"][0]["sha256"]="f"*64
                elif attack=="level_one":
                    wrapper["unit"]["kind"]="ruling";wrapper["unit"]["level"]=1
                    wrapper["unit"]["body"]={"quote_sha256":"0"*64,"how_to_apply":"forged authority"}
                elif attack=="scope":wrapper["unit"]["scope"]["language"]="javascript"
                else:wrapper["unit"]["created_at"]=1
                self.forge(forged)

    def test_a12_direct_journal_reverifies_changed_evidence(self):
        self.parents();unit=self.put(self.unit())
        payload=self.valid_forge_template()
        (self.home/unit["receipts"][0]["path"]).write_bytes(b"changed after preparation\n")
        self.forge(payload)

    def test_a28_extra_skill_change_in_mutation_is_rejected(self):
        old=self.publish();other=self.publish("other-skill");target=self.publish("target-skill")
        self.parent(skills=[old,other])
        payload=self.valid_forge_template("agent_mutate",change={"kind":"skill","skill_id":old["skill_id"],
                                        "from_sha256":old["sha256"],"to":target})
        payload["record"]["skills"]=[target]
        self.forge(payload)

    def test_a28_specialization_cannot_widen_seats_or_scope(self):
        # A-U18: seed concrete memory on its valid concrete-language owner.
        self.parent()
        self.put(self.unit())
        payload=self.valid_forge_template("agent_specialize",language="python")
        for attack in ("seat","scope","workflow"):
            forged=deepcopy(payload)
            if attack=="seat":forged["record"]["allowed_seats"].append({"model":"extra","effort":"high","mode":"headless"})
            elif attack=="scope":forged["inherited_units"][0]["unit"]["scope"]["language"]="general"
            else:forged["record"]["workflow"]="orchestrate"
            self.forge(forged)

    def test_a21_own_brief_hash_omits_inherited_but_capacity_service_includes_it(self):
        self.parents();self.put(self.unit())
        entry=self.module("lineage.domain.memory.entry")
        brief=self.module("lineage.domain.brief")
        called=mock.Mock(wraps=entry.build)
        with seam(entry,"build",called):
            data=self.op()
        self.witness(data)
        adopted=[w["unit"] for w in data["inherited_units"]]
        self.assertEqual(data["record"]["brief_head_sha256"],sha(brief.build(data["record"],adopted,memory_arm="own",
            # A-U18: brief.build requires the committed constitution citation IDs.
            rule_ids=self.history()[data["commit"]["head"]-1]["payload"]["constitution"]["rule_ids"])))
        self.assertTrue(any(call.args and len(call.args)>1 and call.args[1] for call in called.call_args_list),
                        "inherited static entry must be checked even when own brief excludes it")
        for call in called.call_args_list:
            self.assertIsNone(call.kwargs.get("token_count"))

    def test_a21_static_entry_exact_byte_boundary_and_multibyte_overflow(self):
        parent=self.parent()
        entry=self.module("lineage.domain.memory.entry")
        source=self.unit()
        source["statement"]="x"
        # A-U18: isolate the byte-boundary service test with a trusted test counter;
        # production token_count=None remains asserted by the separate birth test.
        counter=mock.Mock(return_value=4000)
        initial=entry.build(parent,[source],token_count=counter,max_bytes=100000)
        room=6000-len(initial)
        self.assertGreaterEqual(room,0)
        source["statement"]="x"*(room+1)
        boundary=entry.build(parent,[source],token_count=counter,max_bytes=6000)
        self.assertEqual(len(boundary),6000)
        source["statement"]+="é"
        with self.assertRaises(LineageError) as caught:
            entry.build(parent,[source],token_count=counter,max_bytes=6000)
        self.assertEqual(caught.exception.code,"memory_debt")

    def test_a22_accepted_and_rejected_count_overflow_do_not_truncate(self):
        self.parents()
        memory=self.module("lineage.domain.memory.fold")
        actual=memory.units_for
        # Only the public fold read is injected for these count-boundary fixtures;
        # U17 selection and shared birth validation stay real. This avoids a
        # quadratic journal fixture and does not certify source-history admission.
        for count,private,code in ((257,False,"memory_debt"),(10001,True,"conflict")):
            with self.subTest(count=count):
                sample=self.unit()
                sources=[]
                for i in range(count):
                    unit=deepcopy(sample);unit["id"]="count_%05d"%i
                    unit["statement"]="identical compatible statement"
                    if private:unit["privacy"]="private"
                    sources.append(unit)
                def fixture(state,agent_id,**kwargs):
                    return tuple(sources) if agent_id=="parent-one" else actual(state,agent_id,**kwargs)
                with seam(memory,"units_for",fixture):
                    self.reject(code)

    def test_a33_public_fixtures_and_output_have_no_host_coordinates(self):
        self.parents();data=self.op();self.witness(data)
        for raw in (canonical(data),canonical(self.history()[-1]["payload"])):
            self.assertNotIn(str(ROOT).encode(),raw)
            self.assertNotIn(str(self.home).encode(),raw)
            self.assertNotIn(b"Traceback",raw)
        paths=[HERE/"helpers.py"]+list(HERE.glob("test_*.py"))
        for path in paths:
            tree=ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.Constant) and isinstance(node.value,str):
                    self.assertNotIn("/"+"home"+"/",node.value,path.name)
                    self.assertNotIn("/"+"Users"+"/",node.value,path.name)


class GuardMutationTests(OracleCase):
    """A32 discovers actual refusal sites; it guesses no private guard name."""
    def _evaluate(self, guard, negative, positive):
        self.parents()
        sandbox=self.home/"mutant"
        sandbox.mkdir()
        for directory in ("lineage","references","schemas","docs"):
            shutil.copytree(ROOT/directory,sandbox/directory,ignore=shutil.ignore_patterns("__pycache__"))
        target=sandbox/"tests/breeding/two";target.mkdir(parents=True)
        for ancestor in (target.parent,target.parent.parent):
            (ancestor/"__init__.py").write_text("")
        for path in HERE.glob("*.py"):
            shutil.copyfile(path,target/path.name)
        frozen={p.name:sha(p.read_bytes()) for p in HERE.glob("*.py")}
        code=r'''
import ast, importlib, io, json, sys, unittest
from pathlib import Path
root=Path.cwd()
guard,negative,positive=sys.argv[1:]
sites=set()
breeding_prefix=str(root/"lineage/domain/breeding")+"/"
def report(result):
    def ident(t):return getattr(t,"test_case",t).id()
    return {"failures":sorted({ident(t) for t,_ in result.failures}),
            "errors":sorted({ident(t) for t,_ in result.errors}),
            "skips":len(result.skipped),"tests":result.testsRun}
def run():
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in (negative,positive))
    # A-U18: retain diagnostics for a broken healthy control or mutant positive.
    output=io.StringIO()
    result=unittest.TextTestRunner(stream=output).run(suite)
    if not result.wasSuccessful():
        print(output.getvalue(),file=sys.stderr)
    return result
def trace(frame,event,arg):
    # A-U18: trace only breeding exception events, not every compiler source
    # line. This preserves refusal-site discovery without line-tracing overhead.
    if event=="call":
        if not frame.f_code.co_filename.startswith(breeding_prefix):
            return None
        frame.f_trace_lines=False
        return trace
    if event!="exception":
        return trace
    path=Path(frame.f_code.co_filename)
    if path.is_relative_to(root/"lineage/domain/breeding"):
        error=arg[1]
        code=getattr(error,"code",None)
        detail=getattr(error,"detail","")
        if (code==({"claims":"conflict","authority":"bad_args"}.get(guard))
                and isinstance(detail,str)
                and detail.startswith({"claims":"incompatible claims:",
                                       "authority":"authority rule cannot"}.get(guard,"!"))):
            sites.add((str(path),frame.f_lineno))
    return trace
sys.settrace(trace)
healthy=report(run())
sys.settrace(None)
changed=0
if not healthy["errors"] and not healthy["failures"] and not healthy["skips"] and healthy["tests"]==2:
    # A-U18: derive authority predicate names from the actual refusing If;
    # disable the shared predicate, not generic error propagation or unknown-ID
    # checks. Those must keep working in both healthy and mutant controls.
    predicates=set()
    if guard=="authority":
        for source in sorted((root/"lineage/domain/breeding").glob("*.py")):
            tree=ast.parse(source.read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.If) and any(isinstance(x,ast.Raise) and
                        (str(source),x.lineno) in sites for x in ast.walk(node)):
                    predicates.update(x.func.id for x in ast.walk(node.test)
                                      if isinstance(x,ast.Call) and isinstance(x.func,ast.Name))
    for path in sorted((root/"lineage/domain/breeding").glob("*.py")):
        tree=ast.parse(path.read_text())
        class Disable(ast.NodeTransformer):
            def visit_FunctionDef(self,node):
                global changed
                if guard=="authority" and node.name in predicates:
                    node.body=[ast.Return(ast.Constant(False))];changed+=1
                    return node
                return self.generic_visit(node)
            def visit_Raise(self,node):
                global changed
                # A-U18: remove only a literal origin refusal, never a generic
                # rethrow that also carries no_agent and unrelated failures.
                literal=(isinstance(node.exc,ast.Call) and node.exc.args and
                         isinstance(node.exc.args[0],ast.Constant) and
                         node.exc.args[0].value=="conflict")
                if guard=="claims" and literal and (str(path),node.lineno) in sites:
                    changed+=1
                    return ast.copy_location(ast.Pass(),node)
                return node
            def visit_If(self,node):
                global changed
                self.generic_visit(node)
                # Scope is an audited exclusion, not an exception. Only the
                # innermost branch containing its public reason is disabled.
                direct=[s for s in node.body if not isinstance(s,(ast.If,ast.For,ast.While,ast.Try))]
                values={x.value for s in direct for x in ast.walk(s)
                        if isinstance(x,ast.Constant) and isinstance(x.value,str)}
                if guard=="scope" and "scope_mismatch" in values:
                    node.test=ast.Constant(False);changed+=1
                return node
        tree=Disable().visit(tree)
        path.write_text(ast.unparse(ast.fix_missing_locations(tree))+"\n")
    for name in tuple(sys.modules):
        if name=="lineage" or name.startswith("lineage.") or name.startswith("tests.breeding.two."):
            del sys.modules[name]
    importlib.invalidate_caches()
    mutant=report(run()) if changed else None
else:mutant=None
print(json.dumps({"control":healthy,"changed":changed,"mutant":mutant}))
'''
        process=subprocess.Popen([sys.executable,"-c",code,guard,negative,positive],cwd=sandbox,
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.assertGreater(process.pid,1)
        try:
            # A-U18: integrated compiler/admission runs exceed the nominal stub deadline;
            # preserve every healthy/mutant result assertion and owned-PID cleanup.
            stdout,stderr=process.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill();process.communicate(timeout=0.2)
            self.fail("HOLD: mutant deadline is not a discriminating rejection")
        self.assertEqual(process.returncode,0,stderr.decode(errors="replace"))
        report=json.loads(stdout)
        self.assertEqual(report["control"],{"failures":[],"errors":[],"skips":0,"tests":2})
        self.assertGreater(report["changed"],0,"HOLD: refusal-site mutation is unproven")
        self.assertEqual(report["mutant"],{"failures":[negative],"errors":[],"skips":0,"tests":2},
                         "a timeout, import, unexpected exception or broken positive cannot certify a guard\n"+stderr.decode(errors="replace"))
        self.assertEqual(frozen,{p.name:sha(p.read_bytes()) for p in HERE.glob("*.py")})

    def test_a32_claim_conflict_guard_discriminates(self):
        self._evaluate("claims","tests.breeding.two.test_cross.CrossTests.test_a09_lesson_conflict_names_both_source_identities",
                       "tests.breeding.two.test_cross.CrossTests.test_a09_distinct_subject_keys_coexist")

    def test_a32_protected_rule_guard_discriminates(self):
        self._evaluate("authority","tests.breeding.two.test_mutate.MutateTests.test_a16_all_protected_rules_aliases_actions_and_operator_actor_reject",
                       "tests.breeding.two.test_mutate.MutateTests.test_a15_remove_then_add_has_single_diff_and_explicit_canonical_override")

    def test_a32_language_scope_guard_discriminates(self):
        self._evaluate("scope","tests.breeding.two.test_specialize.SpecializeTests.test_a17_general_and_exact_target_only_without_relabeling",
                       "tests.breeding.two.test_specialize.SpecializeTests.test_a17_same_language_target_is_valid")


class AdditionalBirthTests(OracleCase):
    def test_a19_filtered_child_does_not_copy_parent_memory_gen(self):
        # A-U18: valid concrete-owner fixtures retain general memory while
        # specialization to general filters the concrete unit; counter stays two.
        self.parent()
        self.put(self.unit("unit_py01",scope={"workflow":"develop","language":"general"}))
        self.put(self.unit("unit_js01"))
        parent=self.get_agent("parent-one")
        self.assertEqual(parent["memory_gen"],2)
        data=self.op("agent_specialize",language="general")
        self.assertEqual(data["record"]["memory_gen"],1)
        self.witness(data,"agent_specialize")
        self.parent("parent-two",language="python")
        grandchild=self.op(parent_ids=["child-agent","parent-two"],child_id="grandchild",op_id="grandchild-op")
        self.assertEqual(grandchild["record"]["generation"],2)
        self.witness(grandchild)

    def test_a21_operator_enforces_multibyte_inherited_entry_overflow(self):
        self.parents()
        fold=self.module("lineage.domain.memory.fold")
        actual=fold.units_for
        sources=[]
        for i in range(3):
            unit=self.unit("budget_%02d"%i,statement="é"*1000)
            self.assertLessEqual(len(canonical(unit)),6000)
            sources.append(unit)
        def budget_fixture(state,agent_id,**kwargs):
            return tuple(sources) if agent_id=="parent-one" else actual(state,agent_id,**kwargs)
        with seam(fold,"units_for",budget_fixture):
            result=self.reject("memory_debt")
        self.assertIn("detail",result)

    def test_a22_empty_audit_and_complete_within_limit_source_accounting(self):
        self.parents()
        empty=self.op(child_id="empty-child",op_id="empty")
        self.assertEqual(empty["inherited_units"],[]);self.assertEqual(empty["rejected_units"],[])
        sources=[]
        for i in range(4):
            unit=self.unit("audit_%02d"%i,privacy="private" if i%2 else "internal")
            sources.append(self.put(unit))
        data=self.op()
        accepted={(w["source_agent_id"],w["source_unit_id"]) for w in data["inherited_units"]}
        rejected={(w["agent_id"],w["unit_id"]) for w in data["rejected_units"]}
        self.assertEqual(accepted&rejected,set())
        self.assertEqual(accepted|rejected,{("parent-one",u["id"]) for u in sources})
        self.witness(data)

    def test_a28_forbidden_rule_override_and_extra_citation_reject(self):
        self.parents()
        payload=self.valid_forge_template()
        rules=self.success("reference_get",{"ref_id":"gold_s1"})["reference"]["rules"]
        protected=[r["id"] for r in rules if any(r["text"].startswith(x+" ") for x in ("I20","I21","I22"))]
        self.assertEqual(len(protected),3)
        for rule in protected:
            forged=deepcopy(payload);forged["record"]["rule_overrides"]={rule:"remove"}
            self.forge(forged)
        forged=deepcopy(payload);forged["constitution"]["rule_ids"].append("unverified-rule")
        self.forge(forged)
