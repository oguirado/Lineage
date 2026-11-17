"""A5, A7-A9: generated fields, final-payload validation and callback isolation."""
import copy
from unittest.mock import Mock
from ._support import CoreCase, accept, canonical, independent_verify, sha


class TransactionTests(CoreCase):
    def test_a5_generated_values_and_regressing_wall_clock(self):
        a = self.tx(clock=lambda: 20)
        b = self.tx(clock=lambda: 10)
        self.assertEqual((a["lamport"], b["lamport"]), (1, 2))
        self.assertEqual((a["ts"], b["ts"]), (20, 10))
        self.assertEqual([a["id"], b["id"]], ["e-0000000000000001", "e-0000000000000002"])
        independent_verify(self.bytes())

    def test_a5_invalid_generators_and_collision_do_not_consume_lamport(self):
        first = self.tx()
        for value in (True, -1, 1.5, None, "100"):
            self.rejects("internal", self.tx, clock=lambda value=value: value)
        for value in (None, 12, "bad", "e-ABCDEF0123456789"):
            self.rejects("internal", self.tx, id_factory=lambda value=value: value)
        def crash():
            raise RuntimeError("generator failed")
        self.rejects("internal", self.tx, clock=crash)
        self.rejects("internal", self.tx, id_factory=crash)
        self.rejects("conflict", self.tx, id_factory=lambda: first["id"])
        self.assertEqual(self.tx()["lamport"], 2)

    def test_a7_prepare_and_validate_share_latest_history_and_final_digest(self):
        first = self.tx()
        observed = []
        def prepare(history, draft):
            self.assertEqual(history, (first,))
            self.assertNotIn("sha256", draft)
            observed.append(canonical(list(history)))
            return {"derived": len(history), "source": draft["payload"]["source"]}
        def validate(history, candidate):
            self.assertEqual(canonical(list(history)), observed[0])
            self.assertEqual(candidate["payload"], {"derived": 1, "source": "original"})
            without = {k: v for k, v in candidate.items() if k != "sha256"}
            self.assertEqual(candidate["sha256"], sha(canonical(without)))
            observed.append("validated")
        result = self.tx(payload={"source": "original"}, prepare=prepare,
                         validators={"claim": validate})
        self.assertEqual(result["payload"]["derived"], 1)
        self.assertEqual(observed[-1], "validated")

    def test_a7_invalid_prepared_payload_cannot_use_original_approval(self):
        def validate(history, candidate):
            if candidate["payload"].get("allowed") is not True:
                raise self.error("forbidden_level", {"source": "prepared"})
        self.rejects("forbidden_level", self.tx, payload={"allowed": True},
                     prepare=lambda h, d: {"allowed": False}, validators={"claim": validate})

    def test_a8_missing_validator_rejects(self):
        self.rejects("bad_args", self.tx, validators={})

    def test_a8_validator_non_none_return_rejects(self):
        for result in (False, True, 0, {}, []):
            self.rejects("internal", self.tx, validators={"claim": lambda h, e, r=result: r})

    def test_a8_domain_error_preserves_code_and_detail(self):
        detail = {"required": ["episode"], "cost": None}
        def reject(history, candidate):
            raise self.error("memory_required", detail)
        exc = self.rejects("memory_required", self.tx, validators={"claim": reject})
        self.assertEqual(exc.detail, detail)

    def test_a8_preparation_contract_and_exception(self):
        for value in (None, [], True, 1, "payload", {"bad": float("nan")}):
            self.rejects("internal", self.tx, prepare=lambda h, d, v=value: v)
        def crash(history, candidate):
            raise RuntimeError("unexpected preparation error")
        self.rejects("internal", self.tx, prepare=crash)

    def test_a9_input_and_return_values_are_detached(self):
        payload = {"nested": {"value": 1}}
        evidence = [{"path": "receipts/one", "sha256": "a" * 64}]
        def validate(history, candidate):
            payload["nested"]["value"] = 99
            evidence[0]["sha256"] = "b" * 64
        result = self.tx(payload=payload, evidence=evidence, validators={"claim": validate})
        self.assertEqual(result["payload"]["nested"]["value"], 1)
        self.assertEqual(result["evidence"][0]["sha256"], "a" * 64)
        before = self.bytes()
        result["payload"]["nested"]["value"] = 7
        self.assertEqual(self.bytes(), before)
        self.assertEqual(self.journal.snapshot(self.home)[0]["payload"]["nested"]["value"], 1)

    def test_a9_validator_cannot_repair_its_argument(self):
        def validate(history, candidate):
            candidate["payload"]["allowed"] = True
            self.assertIs(candidate["payload"]["allowed"], True)
        self.rejects("internal", self.tx, payload={"allowed": False}, validators={"claim": validate})

    def test_a9_equal_python_values_still_detect_json_type_mutation(self):
        self.tx(payload={"value": 0})
        for old, new in ((1, True), (0, 0.0), (0.0, -0.0)):
            def validate(history, candidate, value=new):
                candidate["payload"]["value"] = value
            self.rejects("internal", self.tx, payload={"value": old}, validators={"claim": validate})
        def mutate_history(history, candidate):
            history[0]["payload"]["value"] = False
        self.rejects("internal", self.tx, validators={"claim": mutate_history})
        independent_verify(self.bytes())

    def test_a9_preparation_cannot_mutate_draft_or_history(self):
        self.tx()
        def draft_mutation(history, draft):
            draft["agent"] = "system"
            return {"value": 1}
        def history_mutation(history, draft):
            history[0]["payload"]["value"] = True
            return {"value": 1}
        self.rejects("internal", self.tx, prepare=draft_mutation)
        self.rejects("internal", self.tx, prepare=history_mutation)

    def test_m9_validator_mapping_is_snapshotted(self):
        chosen = Mock(return_value=None)
        replacement = Mock(side_effect=AssertionError("Mapping was not snapshotted"))
        validators = {"claim": chosen}
        def prepare(history, draft):
            validators["claim"] = replacement
            return dict(draft["payload"])
        self.tx(validators=validators, prepare=prepare)
        chosen.assert_called_once()
        replacement.assert_not_called()
