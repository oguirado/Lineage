"""A11-A15, A35: content-bound replay survives new processes and later state."""
from unittest.mock import patch
from ._support import CoreCase, accept, chain, forbidden, independent_verify, line


class ReplayTests(CoreCase):
    def test_a11_replay_ignores_changed_state_and_all_hooks(self):
        first = self.tx(payload={"nested": {"b": 2, "a": 1}})
        self.tx(payload={"value": "later"})
        before = self.bytes()
        with patch("os.fsync", side_effect=AssertionError("Replay fsync")):
            replay = self.tx(op_id="request0001", payload={"nested": {"a": 1, "b": 2}},
                             validators={}, prepare=forbidden, clock=forbidden, id_factory=forbidden)
        self.assertEqual(replay, first)
        self.assertEqual(self.bytes(), before)
        self.assertEqual(len(self.journal.snapshot(self.home)), 2)

    def test_a11_original_request_digest_survives_preparation(self):
        first = self.tx(payload={"requested": 1}, prepare=lambda h, d: {"stored": 2})
        self.assertEqual(self.journal.snapshot(self.home), (first,))
        replay = self.tx(op_id="request0001", payload={"requested": 1}, validators={},
                         prepare=forbidden, clock=forbidden, id_factory=forbidden)
        self.assertEqual(replay, first)
        self.rejects("bad_op", self.tx, op_id="request0001", payload={"stored": 2})

    def test_a11_replay_from_new_process(self):
        first = self.tx(op_id="shared-request")
        self.tx()
        before = self.bytes()
        process, pipe = self.child("replay")
        self.assertEqual(self.receive(pipe), ("ok", first))
        self.finished(process)
        self.assertEqual(self.bytes(), before)

    def test_a12_every_changed_request_component_conflicts(self):
        evidence = [{"path": "receipts/a", "sha256": "a" * 64},
                    {"path": "receipts/b", "sha256": "b" * 64}]
        self.tx(op_id="bound-request", payload={"nested": {"v": 1}}, evidence=evidence)
        variants = ({"kind": "other"}, {"payload": {"nested": {"v": 2}}},
                    {"evidence": [{"path": "receipts/c", "sha256": "a" * 64}, evidence[1]]},
                    {"evidence": [{"path": "receipts/a", "sha256": "c" * 64}, evidence[1]]},
                    {"evidence": list(reversed(evidence))})
        for changed in variants:
            options = dict(op_id="bound-request", payload={"nested": {"v": 1}}, evidence=evidence)
            options.update(changed)
            self.rejects("bad_op", self.tx, **options)

    def test_a13_same_operation_id_is_actor_scoped(self):
        a = self.tx(agent="agent-one", op_id="same-request", payload={"v": 1})
        b = self.tx(agent="agent-two", op_id="same-request", payload={"v": 2})
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(self.tx(agent="agent-one", op_id="same-request", payload={"v": 1}), a)
        self.assertEqual(self.tx(agent="agent-two", op_id="same-request", payload={"v": 2}), b)
        self.assertEqual(len(independent_verify(self.bytes())), 2)

    def test_a15_lost_return_retry_recovers_original_from_disk(self):
        process, pipe = self.child("lost_return")
        self.assertEqual(self.receive(pipe), ("committed", None))
        self.finished(process)
        before = self.bytes()
        original = independent_verify(before)[0]
        process, pipe = self.child("replay")
        self.assertEqual(self.receive(pipe), ("ok", original))
        self.finished(process)
        self.assertEqual(self.bytes(), before)

    def test_a35_unknown_historical_kind_and_corrupt_prefix_replay(self):
        first = self.tx()
        self.assertEqual(self.journal.snapshot(self.home), (first,))
        self.path.write_bytes(self.bytes() + b"broken\n")
        self.rejects("hash_mismatch", self.tx, op_id="request0001", validators={})

    def test_a35_read_results_are_detached(self):
        self.tx()
        before = self.bytes()
        snapshot = self.journal.snapshot(self.home)
        snapshot[0]["payload"]["value"] = 999
        report = self.journal.verify(self.home)
        report["errors"].append({"code": "fabricated"})
        report["head"] = 999
        self.assertEqual(self.bytes(), before)
        self.assertEqual(self.journal.snapshot(self.home)[0]["payload"]["value"], 1)
        self.assertEqual(self.journal.verify(self.home)["head"], 1)
