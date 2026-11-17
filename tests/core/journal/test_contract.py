"""A2-A4, A28, A36-A37: public envelope, byte encoding and arguments."""
import contextlib
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from ._support import (CoreCase, FIELDS, REPORT_FIELDS, ZERO, canonical,
                       event, independent_verify, line, sha)


class ContractTests(CoreCase):
    def test_a2_missing_and_explicitly_empty_authority(self):
        self.assertEqual(self.journal.snapshot(self.home), ())
        report = self.journal.verify(self.home)
        self.assertEqual(set(report), REPORT_FIELDS)
        self.assertIs(report["ok"], False)
        self.assertIs(report["exists"], False)
        self.assertEqual(report["events"], 0)
        self.assertEqual(report["head"], 0)
        self.assertEqual(report["head_sha256"], ZERO)
        self.assertEqual(report["errors"][0]["code"], "internal")
        self.assertFalse(self.home.exists(), "Missing-home reads must not create authority")
        self.install()
        report = self.journal.verify(self.home)
        self.assertIs(report["ok"], True)
        self.assertIs(report["exists"], True)
        self.assertEqual(report["errors"], [])

    def test_a2_explicit_home_precedes_environment(self):
        other = self.home.parent / "environment"
        with patch.dict(os.environ, {"LINEAGE_HOME": str(other)}):
            self.tx()
        self.assertTrue(self.path.is_file())
        self.assertFalse(other.exists())
        self.assertEqual({str(p.relative_to(self.home)) for p in self.home.rglob("*")},
                         {"ledger", "ledger/main", "ledger/main/events.jsonl", "ledger/main/events.lock"})

    def test_a2_environment_then_user_home_and_empty_environment(self):
        other = self.home.parent / "environment"
        with patch.dict(os.environ, {"LINEAGE_HOME": str(other)}):
            self.tx(home=None)
        self.assertTrue((other / "ledger/main/events.jsonl").is_file())
        for value in (None, ""):
            user = self.home.parent / ("unset-user" if value is None else "empty-user")
            with patch.dict(os.environ, {"HOME": str(user)}):
                if value is None:
                    with patch.dict(os.environ):
                        os.environ.pop("LINEAGE_HOME", None)
                        self.tx(home=None)
                else:
                    with patch.dict(os.environ, {"LINEAGE_HOME": value}):
                        self.tx(home=None)
            self.assertTrue((user / ".lineage/ledger/main/events.jsonl").is_file())

    def test_a2_empty_explicit_home_is_bad_args(self):
        self.rejects("bad_args", self.tx, home="")

    def test_a3_independent_unicode_encoding_vector(self):
        payload = {"z": [1, True, None, {"雪": "é"}], "a": "é"}
        expected = event(payload=payload)
        result = self.tx(payload=payload)
        self.assertEqual(set(result), FIELDS)
        self.assertEqual(result, expected)
        self.assertEqual(self.bytes(), line(expected))
        self.assertEqual(independent_verify(self.bytes()), (expected,))
        self.assertEqual(self.journal.canonical_bytes(payload), canonical(payload))
        replay = self.tx(op_id="request0001", payload={"a": "é", "z": payload["z"]},
                         validators={}, clock=lambda: self.fail("Replay called clock"))
        self.assertEqual(replay, expected)
        self.rejects("bad_op", self.tx, op_id="request0001",
                     payload={"z": list(reversed(payload["z"])), "a": "é"})

    def test_a3_canonical_types_and_unicode_are_not_normalized(self):
        for a, b in ((1, True), (0, 0.0), (0.0, -0.0), ("é", "é"), ([1, 2], [2, 1])):
            self.assertNotEqual(self.journal.canonical_bytes(a), self.journal.canonical_bytes(b))
        self.assertEqual(self.journal.canonical_bytes({"b": 1, "a": None}), b'{"a":null,"b":1}')

    def test_a4_hostile_input_values_preserve_authority(self):
        self.tx()
        class IntegerSubclass(int):
            pass
        class StringSubclass(str):
            pass
        class ObjectSubclass(dict):
            pass
        cycle = []
        cycle.append(cycle)
        for value in (float("nan"), float("inf"), -float("inf"), "\ud800",
                      {1: "non-string"}, cycle, (1, 2), {1, 2}, b"bytes",
                      IntegerSubclass(1), StringSubclass("text"), ObjectSubclass(a=1)):
            with self.subTest(type=type(value).__name__):
                self.rejects("bad_args", self.tx, payload={"bad": value})
        for payload in (None, [], "text", 1, True):
            with self.subTest(payload=payload):
                self.rejects("bad_args", self.tx, payload=payload)
        independent_verify(self.bytes())

    def test_a4_agent_kind_and_operation_arguments(self):
        for agent in (None, True, "", "a", "Uppercase", "a/b", "a" * 65):
            self.rejects("bad_args", self.tx, agent=agent)
        for kind in (None, True, "", "\ud800"):
            self.rejects("bad_args", self.tx, kind=kind)
        for op_id in (None, True, "", "bad id", "x" * 129):
            self.rejects("bad_op", self.tx, op_id=op_id)

    def test_amendment_b_argument_validation_precedes_corrupt_history(self):
        self.install(b"broken\n")
        for options, code in (({"home": ""}, "bad_args"), ({"lock_timeout_s": True}, "bad_args"),
                              ({"agent": "!"}, "bad_args"), ({"op_id": None}, "bad_op"),
                              ({"payload": []}, "bad_args"),
                              ({"evidence": [{"path": "../escape", "sha256": ZERO}]}, "bad_args")):
            self.rejects(code, self.tx, **options)
        self.rejects("bad_args", self.journal.verify, self.home,
                     expected_head={"lamport": True, "sha256": ZERO})

    def test_a28_evidence_is_structural_and_ordered(self):
        evidence = [{"path": "receipts/a.json", "sha256": "a" * 64},
                    {"path": "receipts/b.json", "sha256": "b" * 64}]
        result = self.tx(evidence=evidence)
        self.assertEqual(result["evidence"], evidence)
        self.assertFalse((self.home / "receipts").exists())
        self.assertEqual(result["request_sha256"], event(evidence=evidence)["request_sha256"])
        self.rejects("bad_op", self.tx, op_id="request0001", evidence=list(reversed(evidence)))

    def test_a28_hostile_evidence_paths_and_closed_shape(self):
        paths = ("", "/rooted", "../escape", "a/../b", "./file", "a/./b", "a//b",
                 "a/", "C:/drive", "a\\b", "nul\x00file")
        for path in paths:
            self.rejects("bad_args", self.tx, evidence=[{"path": path, "sha256": ZERO}])
        for item in ({"path": "a", "sha256": "G" * 64}, {"path": "a", "sha256": "0" * 63},
                     {"path": "a"}, {"path": "a", "sha256": ZERO, "extra": True}):
            self.rejects("bad_args", self.tx, evidence=[item])

    def test_a36_error_serialization_detaches_structured_detail(self):
        self.assertEqual(self.error("bad_op").as_dict(), {"ok": False, "code": "bad_op"})
        detail = {"missing": ["episode"], "unknown": None}
        exc = self.error("memory_required", detail)
        result = exc.as_dict()
        self.assertEqual(result, {"ok": False, "code": "memory_required", "detail": detail})
        result["detail"]["missing"].append("tamper")
        self.assertEqual(exc.as_dict()["detail"]["missing"], ["episode"])
        self.assertEqual(exc.code, "memory_required")

    def test_a36_unexpected_callback_error_is_sanitized_and_silent(self):
        sensitive = str(self.home / "private-token")
        def crash(history, candidate):
            raise RuntimeError(sensitive)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exc = self.rejects("internal", self.tx, validators={"claim": crash})
        self.assertNotIn(sensitive, json.dumps(exc.as_dict()))
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(set(exc.as_dict()) - {"ok", "code", "detail"}, set())


class OraclePackageTests(unittest.TestCase):
    def test_a37_package_initializers_are_present(self):
        root = Path(__file__).resolve().parents[2]
        for path in (root / "__init__.py", root / "core/__init__.py",
                     Path(__file__).parent / "__init__.py"):
            self.assertTrue(path.is_file(), str(path.name))

    def test_a37_independent_oracle_accepts_valid_and_rejects_bad_chain(self):
        first = line(event())
        second = line(event(2, previous=sha(first)))
        self.assertEqual(len(independent_verify(first + second)), 2)
        with self.assertRaises(AssertionError):
            independent_verify(first + line(event(2, previous=event()["sha256"])))
