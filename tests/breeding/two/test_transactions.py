"""Original-prefix replay, locking, races and durable projection recovery."""
from copy import deepcopy
from dataclasses import replace
import io
import multiprocessing
from pathlib import Path
import shutil
from unittest import mock

from lineage.core import app, journal, registry
from lineage.core.errors import LineageError

from .helpers import ACTOR, OracleCase, arguments, canonical, seam, sha, tree_bytes


class TransactionTests(OracleCase):
    def test_a24_replay_returns_original_prefix_after_unrelated_commit(self):
        self.parents()
        first=self.op();self.witness(first)
        self.parent("unrelated-parent")
        before=self.ledger_bytes()
        repeated=self.op()
        self.assertEqual(canonical(first),canonical(repeated))
        self.assertEqual(before,self.ledger_bytes())
        self.assertLess(repeated["commit"]["head"],len(self.history()))

    def test_a24_omitted_and_explicit_name_are_distinct_requests(self):
        self.parents()
        first=self.op()
        self.reject("bad_op",display_name=first["record"]["display_name"])

    def test_a24_parent_order_and_tool_changes_are_bad_op(self):
        self.parents()
        self.op()
        self.reject("bad_op",parent_ids=["parent-two","parent-one"])
        self.reject("bad_op","agent_specialize")

    def test_a24_language_and_mutation_changes_bind_operation_identity(self):
        self.parent()
        self.op("agent_specialize",child_id="first-child")
        self.reject("bad_op","agent_specialize",child_id="first-child",language="javascript")
        old=self.publish();new=self.publish("new-skill")
        self.parent("skill-parent",skills=[old])
        change={"kind":"skill","skill_id":old["skill_id"],"from_sha256":old["sha256"],"to":new}
        self.op("agent_mutate",parent_id="skill-parent",child_id="mutant-child",op_id="mutant-op",change=change)
        self.reject("bad_op","agent_mutate",parent_id="skill-parent",child_id="mutant-child",op_id="mutant-op",
                    change=dict(change,to=old))

    def test_a24_actor_namespaces_are_independent(self):
        self.parents()
        a=self.op(agent="creator-one",child_id="actor-one")
        b=self.op(agent="creator-two",child_id="actor-two")
        self.assertNotEqual(a["commit"]["event_ids"],b["commit"]["event_ids"])
        self.witness(a);self.witness(b)

    def test_a24_full_k0_operation_id_is_not_renamed(self):
        self.parents()
        op="A:/segment.with-dots/"+"x"*100
        data=self.op(op_id=op)
        event=self.witness(data)
        self.assertEqual(event["op_id"],op)
        self.assertEqual(self.op(op_id=op),data)

    def test_a25_new_operation_exact_head_and_stale_head(self):
        self.parents()
        head=len(self.history())
        data=self.op(expected_head=head)
        self.assertEqual(data["commit"]["head"],head+1)
        self.reject("stale_rev",child_id="stale-child",op_id="stale-operation",expected_head=head)

    def test_a25_replay_precedes_retirement_and_expected_head(self):
        self.parents()
        data=self.op(expected_head=len(self.history()))
        self.retire()
        before=self.ledger_bytes()
        self.assertEqual(self.op(expected_head=0),data)
        self.assertEqual(self.ledger_bytes(),before)
        self.reject("conflict",child_id="late-child",op_id="new-after-retirement")

    def test_a26_concurrent_distinct_operations_same_child_have_one_winner(self):
        self.parents()
        before=len(self.history())
        output=self.parallel([("agent_cross",arguments("agent_cross",op_id="race-one")),
                              ("agent_cross",arguments("agent_cross",op_id="race-two"))])
        successes=[r for r in output if "untrusted" in r]
        failures=[r for r in output if r.get("ok") is False]
        self.assertEqual(len(successes),1);self.assertEqual(len(failures),1)
        self.assertEqual(failures[0]["code"],"conflict")
        self.assertEqual(len(self.history()),before+1)
        self.witness(successes[0]["untrusted"])

    def test_a26_concurrent_identical_retry_has_one_witness(self):
        self.parents()
        before=len(self.history())
        args=arguments("agent_cross")
        output=self.parallel([("agent_cross",args),("agent_cross",args)])
        self.assertEqual(output[0],output[1])
        self.assertEqual(set(output[0]),{"untrusted"})
        self.assertEqual(len(self.history()),before+1)
        self.witness(output[0]["untrusted"])

    def test_a27_retirement_before_admission_is_observed(self):
        self.parents()
        self.retire()
        self.reject("conflict")

    def test_a27_supersession_before_admission_uses_locked_latest_source(self):
        self.parents()
        old=self.put(self.unit("unit_old1"))
        new=self.unit("unit_new1",supersedes=[old["id"]])
        self.put(new)
        data=self.op()
        self.assertEqual([w["source_unit_id"] for w in data["inherited_units"]],[new["id"]])
        self.assertEqual(data["rejected_units"],[{"agent_id":"parent-one","unit_id":old["id"],"reason":"inactive"}])
        self.witness(data)

    def test_a27_birth_winning_before_retirement_retains_valid_source_prefix(self):
        self.parents()
        original=self.op()
        self.retire()
        self.witness(original)
        self.assertEqual(self.op(),original)

    def test_a29_corrupt_or_unreadable_ledger_is_never_empty_state(self):
        self.parents()
        path=self.home/"ledger/main/events.jsonl"
        raw=path.read_bytes();path.write_bytes(raw.replace(b'"lamport":1',b'"lamport":9',1))
        self.reject("hash_mismatch")
        path.write_bytes(raw)
        # A directory is an unconditionally unreadable ledger even under root.
        path.unlink();path.mkdir()
        result=self.call("agent_cross",arguments("agent_cross"))
        self.assertEqual(result.get("code"),"internal")
        self.assertTrue(path.is_dir())

    def test_a29_compiler_and_validator_failure_leave_no_birth(self):
        self.parents()
        compiler=self.module("lineage.domain.constitution")
        with seam(compiler,"compile_constitution",mock.Mock(side_effect=LineageError("conflict","injected compilation refusal"))):
            self.reject("conflict")
        validators=dict(self.reg.validators)
        def fail(history,event):
            raise LineageError("internal","injected validation failure")
        validators["agent.born"]=fail
        self.reg=registry.Registry(self.reg.tools,validators,self.reg.folds)
        self.context=app.create_context(self.home,registry=self.reg)
        self.reject("internal")

    def test_a30_projection_failure_is_durable_and_retry_repairs_original_birth(self):
        self.parents()
        owner=self.module("lineage.domain.agents")
        original=owner.materialize
        before=len(self.history())
        def fail(agent_id,*,snapshot,ctx,_preserve_unchanged=False):
            # A-U18: refresh_projections forwards its installed publication flag.
            if agent_id=="child-agent":
                raise OSError("injected child projection refusal")
            return original(agent_id,snapshot=snapshot,ctx=ctx,_preserve_unchanged=_preserve_unchanged)
        with seam(owner,"materialize",fail):
            error=self.call("agent_cross",arguments("agent_cross"))
        self.assertEqual(error.get("code"),"internal")
        committed=self.history()
        self.assertEqual(len(committed),before+1)
        event=committed[-1]
        data=self.op()
        self.assertEqual(data["commit"],{"event_ids":[event["id"]],"head":event["lamport"],"sha256":event["sha256"]})
        self.assertEqual(len(self.history()),before+1)
        self.witness(data)

    def test_a30_deleted_child_projections_rebuild_identically(self):
        self.parents()
        before=tree_bytes(self.home)
        data=self.op();self.witness(data)
        complete=tree_bytes(self.home)
        new={k:v for k,v in complete.items() if k not in before and not k.startswith("ledger/")}
        self.assertTrue(new,"HOLD: child projection files are AUSENTE")
        for name in new:(self.home/name).unlink()
        # A-U18: remove the whole deleted child projection, including immutable
        # generation directories; an empty published generation is corruption.
        from lineage.domain import layout
        child=data["record"]
        shutil.rmtree(layout.agent_dir(self.home,workflow=child["workflow"],
                                      language=child["language"],agent_id=child["agent_id"]))
        self.assertEqual(self.op(),data)
        rebuilt=tree_bytes(self.home)
        for name,raw in new.items():self.assertEqual(rebuilt[name],raw)
        for name,raw in before.items():
            if not name.startswith("ledger/"):self.assertEqual(rebuilt[name],raw)
        self.assertEqual(complete["ledger/main/events.jsonl"],rebuilt["ledger/main/events.jsonl"])

    def test_a29_held_real_admission_lock_returns_busy(self):
        from .helpers import hold_admission
        self.parents()
        mp=multiprocessing.get_context("spawn")
        ready,release=mp.Event(),mp.Event()
        receiver,sender=mp.Pipe(duplex=False)
        process=mp.Process(target=hold_admission,args=(str(self.home),ready,release,sender))
        process.start();sender.close()
        self.assertGreater(process.pid,1)
        try:
            self.assertTrue(ready.wait(0.8))
            self.assertTrue(receiver.poll(0.1))
            self.assertEqual(receiver.recv(),process.pid)
            self.reject("busy")
        finally:
            release.set();process.join(0.3)
            if process.is_alive():
                self.assertGreater(process.pid,1);process.kill();process.join(0.2)
            receiver.close()
        self.assertEqual(process.exitcode,0)
        self.witness(self.op())

    def test_a27_concurrent_retire_and_birth_follow_committed_order(self):
        self.parents()
        retirement={"agent_id":"parent-one","reason":"synchronized retirement","agent":ACTOR,"op_id":"race-retirement"}
        results=self.parallel([("agent_cross",arguments("agent_cross")),("agent_retire",retirement)])
        self.assertIn("untrusted",results[1])
        if "untrusted" in results[0]:
            birth=self.witness(results[0]["untrusted"])
            retired=next(e for e in self.history() if e["op_id"]=="race-retirement")
            self.assertLess(birth["lamport"],retired["lamport"])
        else:
            self.assertEqual(results[0].get("code"),"conflict")
            self.assertFalse(any(e["payload"].get("record",{}).get("agent_id")=="child-agent" for e in self.history()))
        self.verify_chain()

    def test_a30_partial_projection_failure_repairs_without_parent_changes(self):
        self.parents()
        owner=self.module("lineage.domain.agents")
        original=owner.materialize
        before=tree_bytes(self.home)
        def partial(agent_id,*,snapshot,ctx,_preserve_unchanged=False):
            # A-U18: inject failure after the real integrated materializer.
            paths=original(agent_id,snapshot=snapshot,ctx=ctx,_preserve_unchanged=_preserve_unchanged)
            if agent_id=="child-agent":
                self.assertTrue(paths)
                paths[0].unlink()
                raise OSError("injected partial projection failure")
            return paths
        with seam(owner,"materialize",partial):
            failure=self.call("agent_cross",arguments("agent_cross"))
        self.assertEqual(failure.get("code"),"internal")
        committed=self.ledger_bytes()
        data=self.op();self.witness(data)
        self.assertEqual(self.ledger_bytes(),committed)
        for name,raw in before.items():
            if "parent-one" in name or "parent-two" in name:self.assertEqual(tree_bytes(self.home)[name],raw)

    def test_a24_replay_ignores_changed_parent_projection_metadata(self):
        self.parents()
        data=self.op()
        changed=False
        for path in self.home.rglob("*.json"):
            if path.is_symlink():continue
            try:
                value=__import__("json").loads(path.read_bytes())
            except (ValueError,UnicodeError):continue
            if isinstance(value,dict) and value.get("agent_id")=="parent-one" and "display_name" in value:
                value["display_name"]="untrusted projection display metadata"
                path.write_bytes(canonical(value)+b"\n");changed=True
        self.assertTrue(changed,"HOLD: parent record projection is AUSENTE")
        before=self.ledger_bytes()
        self.assertEqual(self.op(),data)
        self.assertEqual(self.ledger_bytes(),before)
