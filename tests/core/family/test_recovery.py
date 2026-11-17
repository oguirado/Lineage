"""A17/A18/A24: real-journal shared-dispatch replay and admission.

These tests establish the shared dispatch seam, not mailbox phase recovery.
The missing transport layout decision is recorded in ORACLE.md.
"""

import copy
from tests.core.family import RuntimeCase, op_id, request, wire


class JournalDispatchTests(RuntimeCase):
    def test_a17_mutation_requires_real_journal_witness(self):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        value = self.mutation()
        result = self.lane(value)
        self.assert_witness(result, value)
        self.assertEqual(self.journal.snapshot(self.home)[-1]["lamport"], 1)

    def test_a18_original_expected_head_replays_after_head_advances(self):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        value = self.mutation()
        value["payload"]["args"]["expected_head"] = 0
        original = self.lane(value)
        self.assert_witness(original, value)
        later = self.mutation(id="request02")
        later["payload"]["args"]["skill_id"] = "other-skill"
        self.lane(later)
        before = self.journal.snapshot(self.home)
        replay = self.lane(copy.deepcopy(value))
        self.assertEqual(wire(replay), wire(original))
        self.assertEqual(self.journal.snapshot(self.home), before)

    def test_a24_stale_revision_appends_nothing(self):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        value = self.mutation()
        value["payload"]["args"]["expected_head"] = 1
        self.assert_error(self.lane(value), "stale_rev")
        self.assertEqual(self.journal.snapshot(self.home), ())

    def test_a24_validator_memory_required_appends_nothing(self):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        from tests.core.family import config
        value = request("call", payload={"tool": "run_close", "args": {
            "run_id": "run00001", "outcome": {"verdict": "green", "repair_loops": 0,
            "findings": {"confirmed": 0, "refuted": 0}}, "cost": {
                "tokens_in": None, "tokens_out": None, "tokens_cache": None,
                "duration_ms": None, "cost_micro_usd": None}}})
        self.assert_error(self.lane(value, config(tools=["run_close"])), "memory_required")
        self.assertEqual(self.journal.snapshot(self.home), ())

    def test_a10_unreadable_journal_never_becomes_empty(self):
        # A directory at the authoritative file is deterministic even as root;
        # chmod-based permission tests would not be discriminating as root.
        path = self.home / "ledger" / "main" / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.mkdir()
        self.assert_error(self.lane(request("events.read")), "internal")

    def test_a22_corrupt_journal_blocks_success(self):
        self.lane(self.mutation())
        path = self.home / "ledger" / "main" / "events.jsonl"
        path.write_bytes(path.read_bytes().replace(b'"alice"', b'"bobby"', 1))
        result = self.lane(self.mutation(id="request02"))
        self.assertIn(result.get("code"), {"internal", "hash_mismatch"})
        self.assert_error(result, result["code"])
