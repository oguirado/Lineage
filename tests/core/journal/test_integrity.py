"""A4, A21-A27, A35: hostile byte fixtures are independent of production helpers."""
import copy
import json
from ._support import (CoreCase, EVENT_PATH, ZERO, canonical, chain, event,
                       independent_verify, line, rehash, sha)


class IntegrityTests(CoreCase):
    def test_a4_missing_or_extra_envelope_fields_and_integer_booleans(self):
        for key in event():
            candidate = event()
            del candidate[key]
            self.bad_record(line(candidate if key == "sha256" else rehash(candidate)))
        for changes in ({"extra": None}, {"lamport": True}, {"ts": True},
                        {"schema": "wrong"}, {"ledger": "other"}, {"payload": []},
                        {"id": "wrong"}, {"op_id": "has space"}, {"agent": "!"},
                        {"kind": ""}, {"evidence": [{"path": "../x", "sha256": ZERO}]},
                        {"request_sha256": "G" * 64}, {"ts": -1}):
            with self.subTest(changes=changes):
                self.bad_record(line(rehash({**event(), **changes})))

    def test_a4_duplicate_keys_utf8_surrogates_and_nonfinite_stored_values(self):
        base = line(event(payload={"nested": {"x": 1}}))
        variants = (base.replace(b'"x":1', b'"x":1,"x":1'),
                    base.replace(b'"x":1', b'"x":NaN'),
                    base.replace(b'"x":1', b'"x":Infinity'),
                    base.replace(b'"x":1', b'"x":1e999'),
                    base.replace(b'"x":1', b'"x":"\\ud800"'),
                    base.replace(b'"x":1', b'"x":"' + bytes([255]) + b'"'))
        for raw in variants:
            self.bad_record(raw)

    def test_a21_unterminated_suffixes_are_read_only_and_json_safe(self):
        prefix = chain(1)[0]
        tails = (bytes([226, 130]), b'{"partial":',
                 canonical(event(999, previous=sha(prefix))))
        for suffix in tails:
            with self.subTest(suffix=suffix.hex()):
                raw = prefix + suffix
                self.install(raw)
                snapshot = self.journal.snapshot(self.home)
                self.assertEqual(snapshot, (json.loads(prefix),))
                report = self.journal.verify(self.home)
                self.assertIs(report["ok"], True)
                self.assertEqual(report["errors"], [])
                self.assertEqual((report["events"], report["head"], report["head_sha256"]),
                                 (1, 1, sha(prefix)))
                tail = report["torn_tail"]
                self.assertEqual(tail["line"], 2)
                self.assertEqual(tail["byte_offset"], len(prefix))
                self.assertNotIn("bytes", tail)
                self.assertTrue("byte_length" in tail or "bytes_hex" in tail)
                self.assertLessEqual(set(tail), {"line", "byte_offset", "byte_length", "bytes_hex"})
                if "byte_length" in tail:
                    self.assertIs(type(tail["byte_length"]), int)
                    self.assertEqual(tail["byte_length"], len(suffix))
                if "bytes_hex" in tail:
                    self.assertEqual(tail["bytes_hex"], suffix.hex())
                json.dumps(report, allow_nan=False)
                self.assertEqual(self.bytes(), raw)

    def test_a22_successful_continuation_preserves_prefix_and_ignores_tail_ids(self):
        prefix = chain(1)[0]
        suffixes = (bytes([226, 130]), b'{"partial":', canonical(event(999)))
        for suffix in suffixes:
            self.install(prefix + suffix)
            result = self.tx(op_id="tail-continue", id_factory=lambda: "e-00000000000003e7")
            self.assertEqual(result["lamport"], 2)
            self.assertEqual(result["prev_sha256"], sha(prefix))
            self.assertEqual(self.bytes(), prefix + line(result))
            independent_verify(self.bytes())

    def test_a22_replay_and_rejection_do_not_repair_torn_tail(self):
        first = self.tx()
        raw = self.bytes() + b'{"uncommitted":'
        self.path.write_bytes(raw)
        self.assertEqual(self.tx(op_id="request0001", validators={}), first)
        def reject(history, candidate):
            raise self.error("memory_required", "test rejection")
        self.rejects("memory_required", self.tx, validators={"claim": reject})
        self.assertEqual(self.bytes(), raw)

    def test_a23_lf_terminated_corruption_is_never_a_tail(self):
        prefix, second, third = chain(3)
        for middle in (b"\n", b"broken\n", bytes([226, 130]) + b"\n", b'{"partial":\n'):
            self.bad_record(prefix + middle, count=1, number=2, offset=len(prefix))
            self.bad_record(prefix + middle + second + third, count=1, number=2, offset=len(prefix))

    def test_a24_byte_tamper_reports_raw_utf8_coordinate(self):
        first, second, third = chain(3)
        damaged = second.replace(b'"value":2', b'"value":9')
        self.assertNotEqual(second, damaged)
        report = self.bad_record(first + damaged + third, count=1, number=2, offset=len(first))
        self.assertEqual(report["head"], 1)
        self.assertEqual(report["head_sha256"], sha(first))
        self.assertNotEqual(len(first), len(first.decode("utf-8")))

    def test_a25_deleted_reordered_and_duplicated_complete_lines(self):
        first, second, third = chain(3)
        for raw, count, number, offset in (
                (second + third, 0, 1, 0), (first + third, 1, 2, len(first)),
                (second + first + third, 0, 1, 0),
                (first + third + second, 1, 2, len(first)),
                (first + first + second, 1, 2, len(first))):
            self.bad_record(raw, count=count, number=number, offset=offset)

    def test_a25_rehashed_duplicates_and_lamport_gaps_are_rejected(self):
        first = chain(1)[0]
        original = json.loads(first)
        for options in ({"id": original["id"]},
                        {"op_id": original["op_id"], "agent": original["agent"]},
                        {"lamport": 3}):
            second = event(2, previous=sha(first))
            second.update(options)
            self.bad_record(first + line(rehash(second)), count=1, number=2, offset=len(first))

    def test_a26_correct_independent_chain_passes(self):
        raw = b"".join(chain(3))
        self.install(raw)
        self.assertEqual(self.journal.snapshot(self.home), independent_verify(raw))
        report = self.journal.verify(self.home)
        self.assertIs(report["ok"], True)
        self.assertEqual(report["head_sha256"], sha(chain(3)[-1]))

    def test_a26_embedded_digest_is_not_raw_line_digest(self):
        first = chain(1)[0]
        wrong = event(2, previous=json.loads(first)["sha256"])
        self.assertNotEqual(wrong["prev_sha256"], sha(first))
        self.bad_record(first + line(wrong), count=1, number=2, offset=len(first))

    def test_a26_each_digest_is_independently_enforced(self):
        for field in ("sha256", "prev_sha256"):
            value = event()
            value[field] = "a" * 64
            if field != "sha256":
                value = rehash(value)
            self.bad_record(line(value))
        first = chain(1)[0]
        second = event(2, previous="b" * 64)
        self.bad_record(first + line(second), count=1, number=2, offset=len(first))

    def test_a26_noncanonical_whitespace_bom_crlf_and_unicode_escape(self):
        original = line(event(payload={"text": "雪", "number": 100.0}))
        variants = (b" " + original, bytes([239, 187, 191]) + original,
                    original[:-1] + b"\r\n", original.replace("雪".encode(), b"\\u96ea"),
                    original.replace(b'"number":100.0', b'"number":1e2'))
        for raw in variants:
            self.assertNotEqual(raw, original)
            self.bad_record(raw)

    def test_a27_pinned_head_detects_complete_suffix_loss_at_eof(self):
        records = chain(3)
        self.install(b"".join(records))
        witness = {"lamport": 3, "sha256": sha(records[-1])}
        self.assertIs(self.journal.verify(self.home, expected_head=witness)["ok"], True)
        shortened = b"".join(records[:2])
        self.path.write_bytes(shortened)
        self.assertIs(self.journal.verify(self.home)["ok"], True)
        report = self.journal.verify(self.home, expected_head=witness)
        self.assertIs(report["ok"], False)
        issue = report["errors"][0]
        self.assertEqual((issue["code"], issue["path"], issue["line"], issue["byte_offset"]),
                         ("hash_mismatch", EVENT_PATH, 3, len(shortened)))
        self.assertEqual(report["events"], 2)
        self.assertEqual(self.bytes(), shortened)

    def test_a27_malformed_witness_precedes_integrity_check(self):
        self.install(b"broken\n")
        variants = ({}, {"lamport": True, "sha256": ZERO},
                    {"lamport": -1, "sha256": ZERO}, {"lamport": 0, "sha256": "bad"},
                    {"lamport": 0, "sha256": ZERO, "extra": 0})
        for witness in variants:
            self.rejects("bad_args", self.journal.verify, self.home, expected_head=witness)

    def test_a27_torn_tail_witness_mismatch_uses_physical_eof(self):
        first = chain(1)[0]
        suffix = b'{"partial":'
        self.install(first + suffix)
        report = self.journal.verify(self.home, expected_head={"lamport": 2, "sha256": "a" * 64})
        self.assertIs(report["ok"], False)
        issue = report["errors"][0]
        self.assertEqual((issue["line"], issue["byte_offset"]), (3, len(first + suffix)))
