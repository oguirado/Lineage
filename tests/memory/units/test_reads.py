"""A26–A28, A33, A35: explicit inspection, owner cursors and journal authority."""
import copy
from dataclasses import replace
from ._support import IntegrationCase, OWNER, unit, canonical, sha
from lineage.domain.memory import units


class ReadTests(IntegrationCase):
    def test_a26_explicit_private_inactive_and_defensive_reads(self):
        self.runtime()
        for index, (status, privacy) in enumerate((("active", "private"), ("draft", "internal"), ("retired", "public"))):
            value = self.shaped(uid="unit_%03d" % index)
            value.update(status=status, privacy=privacy)
            self.write(value)
            observed = units.get(OWNER, value["id"], ctx=self.ctx)
            self.assertEqual(set(observed), {"unit", "head"})
            self.assertEqual(observed["unit"], value)
            self.assertEqual(observed["head"], self.snapshot().head)
            observed["unit"]["body"]["blocked_use"].append("external mutation")
            observed["unit"]["receipts"][0]["sha256"] = "0" * 64
            self.assertEqual(units.get(OWNER, value["id"], ctx=self.ctx)["unit"], value)
        active = unit(uid="unit_010")
        self.write(active)
        successor = unit(uid="unit_011")
        successor["supersedes"] = [active["id"]]
        self.write(successor)
        self.assertEqual(units.get(OWNER, active["id"], ctx=self.ctx)["unit"]["status"], "superseded")
        self.reject("no_agent", lambda: units.get("missing-agent", "unit_000", ctx=self.ctx))
        self.reject("bad_args", lambda: units.get(OWNER, "unknown1", ctx=self.ctx))
        self.assertEqual(units.get(OWNER, "unit_000", ctx=replace(self.ctx, actor="system"))["unit"]["privacy"], "private")

    def history_fixture(self):
        self.runtime()
        self.write(self.shaped(uid="source01"))
        self.ruling()
        self.born("other-agent")
        self.write(unit(uid="foreign1", actor="other-agent"), owner="other-agent", actor="other-agent")
        successor = self.shaped(uid="source02")
        successor["supersedes"] = ["source01"]
        self.write(successor)
        self.raw_append("memory.retire", {"agent_id": OWNER, "unit_id": "source02"})
        original = self.snapshot().events[1]["payload"]["unit"]
        inherited = copy.deepcopy(original)
        inherited["id"] = "child001"
        inherited["provenance"]["inherited_from"] = {"agent_id": OWNER, "unit_id": "source01", "unit_sha256": sha(canonical(original))}
        self.born("child-agent", inherited=[{"unit": inherited, "source_agent_id": OWNER,
                    "source_unit_id": "source01", "unit_sha256": sha(canonical(original))}],
                  memory_gen=7, parent=OWNER)

    def test_a27_original_events_filter_owner_and_supersession(self):
        self.history_fixture()
        snapshot = self.snapshot()
        expected = [e for e in snapshot.events if e["kind"] in {"memory.put", "memory.retire"} and e["payload"]["agent_id"] == OWNER]
        cursor = units.history(OWNER, ctx=self.ctx)
        self.assertEqual(cursor["events"], expected)
        self.assertIn("operator", [e["agent"] for e in cursor["events"]])
        self.assertEqual(cursor["head"], snapshot.head)
        self.assertEqual(cursor["events"][0]["payload"]["unit"]["status"], "active")
        filtered = units.history(OWNER, unit_id="source01", ctx=self.ctx)["events"]
        self.assertEqual([e["kind"] for e in filtered], ["memory.put", "memory.put"])
        self.assertEqual(filtered[1]["payload"]["unit"]["supersedes"], ["source01"])
        child_events = units.history("child-agent", unit_id="child001", ctx=self.ctx)["events"]
        self.assertEqual(len(child_events), 1)
        self.assertEqual(child_events[0], snapshot.events[-1])
        cursor["events"][0]["payload"]["unit"]["receipts"][0]["sha256"] = "0" * 64
        self.assertEqual(units.history(OWNER, ctx=self.ctx)["events"], expected)

    def test_a28_page_matches_and_nonmatches_without_loss(self):
        self.history_fixture()
        complete = units.history(OWNER, ctx=self.ctx)
        collected, after = [], 0
        for _ in range(self.snapshot().head + 1):
            cursor = units.history(OWNER, after=after, limit=1, ctx=self.ctx)
            self.assertEqual(set(cursor), {"events", "next_after", "head", "has_more", "resync"})
            self.assertLessEqual(len(cursor["events"]), 1)
            self.assertFalse(cursor["resync"])
            collected.extend(cursor["events"])
            if not cursor["has_more"]:
                break
            self.assertGreater(cursor["next_after"], after)
            after = cursor["next_after"]
        else:
            self.fail("cursor did not terminate within the committed prefix")
        self.assertEqual(collected, complete["events"])
        self.assertEqual(cursor["next_after"], complete["head"])
        self.assertEqual(len({e["id"] for e in collected}), len(collected))
        empty = units.history(OWNER, unit_id="unmatch1", ctx=self.ctx)
        self.assertEqual(empty["events"], [])
        self.assertEqual(empty["next_after"], complete["head"])
        self.assertFalse(empty["has_more"])

    def test_a28_boundaries_defaults_precedence_and_empty_prefix(self):
        self.runtime()
        cursor = units.history(OWNER, ctx=self.ctx)
        self.assertEqual(cursor, {"events": [], "next_after": self.snapshot().head,
                                  "head": self.snapshot().head, "has_more": False, "resync": False})
        self.assertEqual(cursor, units.history(OWNER, after=0, limit=100, ctx=self.ctx))
        self.write()
        head = self.snapshot().head
        self.assertEqual(units.history(OWNER, after=head, ctx=self.ctx),
                         {"events": [], "next_after": head, "head": head, "has_more": False, "resync": False})
        self.assertEqual(units.history(OWNER, after=head + 1, ctx=self.ctx),
                         {"events": [], "next_after": 0, "head": head, "has_more": False, "resync": True})
        self.reject("no_agent", lambda: units.history("missing-agent", after=head + 1, ctx=self.ctx))
        for after, limit in ((-1, 100), (True, 100), (9007199254740992, 100), (0, 0), (0, 1001), (0, True)):
            self.reject("bad_args", lambda: units.history(OWNER, after=after, limit=limit, ctx=self.ctx))
        empty_home = self.home / "empty-runtime"
        empty_home.mkdir()
        empty_ctx = replace(self.ctx, services=replace(self.ctx.services, home=empty_home))
        self.assertEqual(self.journal.snapshot(ctx=empty_ctx).head, 0)
        self.error("no_agent", lambda: units.history(OWNER, ctx=empty_ctx))

    def test_a33_projection_tamper_delete_does_not_change_reads(self):
        self.runtime()
        self.write()
        original_get = units.get(OWNER, "unit_001", ctx=self.ctx)
        original_history = units.history(OWNER, ctx=self.ctx)
        # Disposable contradictory projection bait, not a U11 layout assertion.
        projection = self.home / "agents" / OWNER / "agent.json"
        projection.parent.mkdir(parents=True, exist_ok=True)
        projection.write_bytes(canonical({"agent_id": OWNER, "status": "retired", "memory": []}))
        self.assertEqual(units.get(OWNER, "unit_001", ctx=self.ctx), original_get)
        self.assertEqual(units.history(OWNER, ctx=self.ctx), original_history)
        projection.unlink()
        self.assertEqual(units.get(OWNER, "unit_001", ctx=self.ctx), original_get)
        self.assertEqual(units.history(OWNER, ctx=self.ctx), original_history)
        self.assertFalse(projection.exists())

    def test_a35_unreadable_journal_is_internal_not_empty(self):
        self.runtime()
        self.write()
        path = self.home / "ledger/main/events.jsonl"
        original = path.read_bytes()
        backup = path.with_suffix(".saved")
        path.rename(backup)
        path.mkdir()
        try:
            self.error("internal", lambda: units.get(OWNER, "unit_001", ctx=self.ctx))
            self.error("internal", lambda: units.history(OWNER, ctx=self.ctx))
        finally:
            path.rmdir()
            backup.rename(path)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(units.get(OWNER, "unit_001", ctx=self.ctx)["unit"]["id"], "unit_001")
