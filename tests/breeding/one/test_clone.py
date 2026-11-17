"""Birth contract assertions over nominal fixtures; host dependency gate is HOLD."""
from copy import deepcopy
import hashlib
import importlib.util

from lineage.core import journal
from .helpers import OracleCase, TEXT, adopted_id, canonical, record_schema, sha, version


class CloneOracle(OracleCase):
    def source(self):
        units = [self.unit("unit0001"), self.unit("unit0002", kind="episode"),
                 self.unit("unit0003", privacy="private", statement="PRIVATE-FIXTURE-CONTENT")]
        self.parent = self.seed(self.parent, units=units)
        return units

    def test_a03_missing_parent_is_no_agent_without_append(self):
        self.refused("no_agent", lambda: self.breed())

    def test_a03_existing_child_or_same_identity_is_conflict(self):
        self.source()
        self.refused("conflict", lambda: self.breed(child_id="parent-one"))
        first = self.breed()
        self.refused("conflict", lambda: self.breed(op_id="operation-0002"))
        self.assert_commit(first)

    def test_a03_retired_parent_cannot_authorize_birth(self):
        self.parent["status"] = "retired"
        self.seed(self.parent)
        self.refused("conflict", lambda: self.breed())

    def test_a12_clone_captures_parent_version_inputs_without_increment(self):
        """Gate: same version despite filtered units; contrast: copied fitness/counter bump."""
        units = self.source()
        parent_before = deepcopy(self.parent)
        before = self.ledger_bytes()
        result = self.breed()
        event = self.assert_commit(result)
        child = result["record"]
        for field in ("constitution_sha256", "skills", "memory_gen", "agent_version",
                      "workflow", "language", "allowed_seats", "references"):
            self.assertEqual(child[field], self.parent[field], field)
        self.assertEqual(child["memory_gen"], 9)
        self.assertGreater(child["memory_gen"], len(result["inherited_units"]))
        self.assertEqual(child["agent_version"], version(child))
        self.assertEqual(child["display_name"], self.parent["display_name"])
        self.assertEqual(child["status"], "draft")
        self.assertEqual(child["parents"], ["parent-one"])
        self.assertEqual(child["generation"], self.parent["generation"] + 1)
        self.assertEqual(child["born"]["op"], "clone")
        self.assertEqual(event["payload"]["constitution"], {"text": TEXT, "overlays": [], "rule_ids": []})
        self.assertEqual(hashlib.sha256(TEXT.encode()).hexdigest(), child["constitution_sha256"])
        self.assertTrue(self.ledger_bytes().startswith(before))
        self.assertEqual(self.parent, parent_before)
        self.assertEqual([w["source_unit_id"] for w in result["inherited_units"]], [units[0]["id"]])
        self.assertEqual([r["reason"] for r in result["rejected_units"]], ["episode", "private"])
        self.assertNotIn("PRIVATE-FIXTURE-CONTENT", canonical(result).decode())

    def test_a10_adopted_ids_hashes_and_closed_memory_fields(self):
        units = self.source()
        first = self.breed()
        second = self.breed(child_id="child-two", op_id="operation-0002")
        for result in (first, second):
            wrapper = result["inherited_units"][0]
            unit = wrapper["unit"]
            self.assertEqual(unit["id"], adopted_id(result["record"]["agent_id"], "parent-one", units[0]["id"]))
            self.assertEqual(wrapper["unit_sha256"], sha(units[0]))
            self.assertEqual(unit["provenance"]["inherited_from"],
                             {"agent_id": "parent-one", "unit_id": units[0]["id"], "unit_sha256": sha(units[0])})
            self.assertEqual(unit["supersedes"], [])
            self.assertNotIn("superseded_by", unit)
            self.assertEqual(set(unit), set(units[0]))
            for absent in ("agent_id", "run_id", "lamport", "created_at"):
                self.assertNotIn(absent, unit)
            record_schema(unit, "mem_unit.schema.json")
        self.assertNotEqual(first["inherited_units"][0]["unit"]["id"], second["inherited_units"][0]["unit"]["id"])

    def test_a11_child_supersession_links_are_reset_and_source_remains_unchanged(self):
        unit = self.unit(supersedes=["older001"])
        self.seed(self.parent, units=[unit])
        result = self.breed()
        adopted = result["inherited_units"][0]["unit"]
        self.assertEqual(adopted["supersedes"], [])
        self.assertNotIn("superseded_by", adopted)
        self.assertEqual(unit["supersedes"], ["older001"])
        result["record"]["allowed_seats"][0]["model"] = "mutated-result"
        replay = self.breed()
        self.assertNotEqual(replay["record"]["allowed_seats"][0]["model"], "mutated-result")

    def test_a12_own_brief_hash_is_identity_bearing_and_uses_real_builder(self):
        self.source()
        result = self.breed()
        self.assertNotEqual(result["record"]["brief_head_sha256"], self.parent["brief_head_sha256"])
        self.assertIsNotNone(importlib.util.find_spec("lineage.domain.brief"), "HOLD: U12 brief builder AUSENTE")
        from lineage.domain import brief
        units = [w["unit"] for w in result["inherited_units"]]
        # A-U17: the installed brief builder requires explicit verified rule IDs.
        expected = hashlib.sha256(brief.build(result["record"], units, rule_ids=[], memory_arm="own")).hexdigest()
        self.assertEqual(result["record"]["brief_head_sha256"], expected)

    def test_a15_birth_payload_and_event_match_bundled_schemas(self):
        self.source()
        result = self.breed()
        event = self.assert_commit(result)
        record_schema(event, "event.schema.json")
        self.assertEqual(event["payload"]["record"], result["record"])
        self.assertEqual(event["payload"]["inherited_units"], result["inherited_units"])
        self.assertEqual(event["payload"]["rejected_units"], result["rejected_units"])
        self.assertEqual(result["record"]["born"]["event_id"], event["id"])

    def test_a18_birth_retry_uses_original_prefix_after_retirement(self):
        self.source()
        result = self.breed()
        original = canonical(result)
        self.retire_agent(op_id="retirement-0002")
        before = self.ledger_bytes()
        replay = self.breed(expected_head=0)
        self.assertEqual(canonical(replay), original)
        self.assertEqual(self.ledger_bytes(), before)
        self.assertLess(replay["commit"]["head"], len(journal.snapshot(self.home)))

    def test_a18_same_identity_changed_child_name_or_tool_is_bad_op(self):
        self.source()
        self.breed()
        for changes in ({"child_id": "child-two"}, {"display_name": "Changed"}, {"op": "distill"}):
            self.refused("bad_op", lambda: self.breed(**changes))

    def test_a18_omitted_display_name_and_explicit_parent_name_are_distinct_requests(self):
        self.source()
        self.breed()
        self.refused("bad_op", lambda: self.breed(display_name=self.parent["display_name"]))

    def test_a30_unicode_display_name_is_preserved_as_passive_text(self):
        self.source()
        name = '<agent>café 漢字 🧬</agent>'
        result = self.breed(display_name=name)
        self.assertEqual(result["record"]["display_name"], name)
        self.assertEqual(result["record"]["status"], "draft")

    def test_a30_birth_caps_are_refusals_without_silent_truncation(self):
        """Amendment B4: inherited overflow memory_debt, rejected overflow conflict."""
        unit = self.unit()
        many = [dict(deepcopy(unit), id=f"unit{i:05d}") for i in range(257)]
        # A-U17: already-inherited source units keep this oversized pure fixture
        # outside the installed own-brief renderer's unrelated output ceiling.
        # All 257 sources remain active, receipt-backed and eligible for adoption.
        for source in many:
            source["provenance"]["inherited_from"] = {
                "agent_id": "ancestor-one", "unit_id": source["id"], "unit_sha256": "a" * 64}
        self.seed(self.parent, units=many)
        self.refused("memory_debt", lambda: self.breed())

    def test_a30_rejected_birth_cap_is_conflict_without_truncation(self):
        unit = self.unit(privacy="private")
        units = [dict(deepcopy(unit), id=f"unit{i:05d}") for i in range(10001)]
        self.seed(self.parent, units=units)
        self.refused("conflict", lambda: self.breed())

    def test_a34_child_inherits_neither_promotion_seat_nor_measured_fitness(self):
        self.parent["status"] = "promoted"
        self.parent["promoted_seat"] = {"model": "fixture-model", "effort": "medium", "mode": "headless"}
        self.seed(self.parent, units=[self.unit()])
        result = self.breed()
        self.assertEqual(result["record"]["status"], "draft")
        for forbidden in ("promoted_seat", "scorecard", "fitness", "weights", "runs"):
            self.assertNotIn(forbidden, result["record"])


def _reserved(child):
    def test(self):
        self.refused("bad_args", lambda: self.breed(child_id=child))
    return test
for _name in ("operator", "system"):
    setattr(CloneOracle, "test_a02_reserved_child_" + _name + "_is_bad_args", _reserved(_name))


def _boundary_text(self):
    self.seed(self.parent, units=[self.unit()])
    name = "🧬" * 128
    result = self.breed(child_id="a" * 64, display_name=name)
    self.assertEqual(result["record"]["display_name"], name)
    self.assertEqual(result["record"]["agent_id"], "a" * 64)
CloneOracle.test_a30_character_bounds_do_not_count_utf8_bytes = _boundary_text
