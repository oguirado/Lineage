"""A15, A19–A21 and Amendment B: graph admission and internal retirement."""
import copy
import multiprocessing
from ._support import IntegrationCase, OWNER, unit
from lineage.domain.memory import units


class SupersessionTests(IntegrationCase):
    def test_a19_atomic_multi_predecessor_graph_and_single_generation(self):
        self.runtime()
        first = self.write(unit(uid="unit_001"))
        second = self.write(unit(uid="unit_002"))
        before = self.fingerprint()[0]
        replacement = unit(uid="unit_003")
        replacement["supersedes"] = ["unit_001", "unit_002"]
        committed = self.write(replacement)
        self.assertEqual(committed.value["memory_gen"], second.value["memory_gen"] + 1)
        self.assertTrue(self.fingerprint()[0].startswith(before))
        for uid in replacement["supersedes"]:
            effective = units.get(OWNER, uid, ctx=self.ctx)["unit"]
            self.assertEqual((effective["status"], effective["superseded_by"]), ("superseded", replacement["id"]))
        self.assertEqual(units.get(OWNER, replacement["id"], ctx=self.ctx)["unit"], replacement)
        self.assertNotIn("superseded_by", first.event["payload"]["unit"])
        self.assertTrue(self.journal.verify(projections=False, ctx=self.ctx)["valid"])

    def test_a19_missing_self_cross_owner_and_competing_edges(self):
        self.runtime()
        self.write()
        self.born("other-agent")
        self.write(unit(uid="foreign1", actor="other-agent"), owner="other-agent", actor="other-agent")
        for edges in (["unknown1"], ["unit_002"], ["foreign1"]):
            value = unit(uid="unit_002")
            value["supersedes"] = edges
            self.reject("conflict", lambda: self.write(value))
        successor = unit(uid="unit_002")
        successor["supersedes"] = ["unit_001"]
        self.write(successor)
        competing = unit(uid="unit_003")
        competing["supersedes"] = ["unit_001"]
        self.reject("conflict", lambda: self.write(competing))
        # Closing a cycle would require overwriting the immutable predecessor id.
        cycle = unit(uid="unit_001")
        cycle["supersedes"] = ["unit_002"]
        self.reject("conflict", lambda: self.write(cycle))

    def test_a19_only_active_predecessors(self):
        self.runtime()
        for n, status in enumerate(("draft", "retired"), 1):
            predecessor = unit(uid="unit_%03d" % n)
            predecessor["status"] = status
            self.write(predecessor)
            replacement = unit(uid="unit_003")
            replacement["supersedes"] = [predecessor["id"]]
            self.reject("conflict", lambda: self.write(replacement))
        active = unit(uid="unit_003")
        self.write(active)
        replacement = unit(uid="unit_004")
        replacement["supersedes"] = [active["id"]]
        self.write(replacement)

    def test_a20_shaped_incoming_backlink_is_conflict(self):
        self.runtime()
        self.write()
        incoming = unit(uid="unit_002")
        incoming.update(status="superseded", superseded_by="unit_001")
        self.validate(incoming)
        self.reject("conflict", lambda: self.write(incoming))
        incoming.pop("superseded_by")
        self.reject("bad_args", lambda: self.write(incoming))

    def test_a21_retirement_no_successor_and_repeat_refusal(self):
        self.runtime()
        self.write()
        self.raw_append("memory.retire", {"agent_id": OWNER, "unit_id": "unit_001"})
        self.assertEqual(units.get(OWNER, "unit_001", ctx=self.ctx)["unit"]["status"], "retired")
        self.reject("conflict", lambda: self.raw_append("memory.retire", {"agent_id": OWNER, "unit_id": "unit_001"}))
        self.write(unit(uid="unit_002"))
        self.reject("conflict", lambda: self.raw_append("memory.retire", {"agent_id": OWNER, "unit_id": "unit_002", "superseded_by": "unknown1"}))
        successor = unit(uid="unit_003")
        successor["supersedes"] = ["unit_002"]
        self.write(successor)
        self.reject("conflict", lambda: self.raw_append("memory.retire", {"agent_id": OWNER, "unit_id": "unit_002", "superseded_by": "unit_003"}))

    def test_a21_retirement_owner_and_level_authority(self):
        self.runtime()
        self.write()
        self.reject("conflict", lambda: self.raw_append("memory.retire", {"agent_id": OWNER, "unit_id": "unit_001"}, actor="other-agent"))
        ruling = self.ruling().value["unit"]
        self.reject("forbidden_level", lambda: self.raw_append("memory.retire", {"agent_id": OWNER, "unit_id": ruling["id"]}))
        self.raw_append("memory.retire", {"agent_id": OWNER, "unit_id": ruling["id"]}, actor="operator", authority="operator")
        self.assertEqual(units.get(OWNER, ruling["id"], ctx=self.ctx)["unit"]["status"], "retired")

    def test_a15_process_barrier_competing_replacements(self):
        self.runtime()
        self.write()
        mp = multiprocessing.get_context("fork")
        barrier = mp.Barrier(3, timeout=1)
        receiver, sender = mp.Pipe(duplex=False)
        def replace_predecessor(uid):
            try:
                barrier.wait()
                value = unit(uid=uid)
                value["supersedes"] = ["unit_001"]
                result = self.write(value, op="replace-" + uid)
                sender.send(("ok", result.value["unit"]["id"]))
            except Exception as exc:
                sender.send((getattr(exc, "code", type(exc).__name__), uid))
            finally:
                sender.close()
        workers = [mp.Process(target=replace_predecessor, args=(uid,)) for uid in ("unit_002", "unit_003")]
        try:
            for worker in workers:
                worker.start()
            barrier.wait()
            answers = []
            for _ in workers:
                self.assertTrue(receiver.poll(1), "replacement process did not return")
                answers.append(receiver.recv())
            for worker in workers:
                worker.join(timeout=0.5)
                self.assertFalse(worker.is_alive())
                self.assertEqual(worker.exitcode, 0)
        finally:
            sender.close()
            receiver.close()
            for worker in workers:
                if worker.is_alive():
                    self.assertGreater(worker.pid, 1)
                    worker.terminate()  # Exact verified child started by this test; no groups.
                    worker.join(timeout=0.5)
        self.assertEqual(sorted(code for code, _ in answers), ["conflict", "ok"])
        winner = next(uid for code, uid in answers if code == "ok")
        self.assertEqual(units.get(OWNER, "unit_001", ctx=self.ctx)["unit"]["superseded_by"], winner)
        self.assertTrue(self.journal.verify(projections=False, ctx=self.ctx)["valid"])
