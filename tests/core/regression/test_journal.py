# A-U01R: Preserve durable replay, ordering, rejection and corruption regressions.
"""Integration probes against the actual single-journal transaction boundary."""
import copy
import hashlib
import json
import subprocess
import sys
from unittest import mock

from lineage.core import journal
from lineage.core.errors import LineageError
from ._support import JournalCase, ROOT


class JournalRegression(JournalCase):
    def test_retry_returns_original_without_second_append(self):
        first = self.append(payload={"text": "é雪", "cost": None})
        before = self.raw()
        second = self.append(payload={"cost": None, "text": "é雪"})
        self.assertEqual(second, first)
        self.assertEqual(self.raw(), before)
        self.assertIsNone(second["payload"]["cost"])

    def test_retry_does_not_revalidate_or_regenerate(self):
        first = self.append()
        before = self.snapshot()
        forbidden = mock.Mock(side_effect=AssertionError("retry executed a hook"))
        result = self.append(validators={}, prepare=forbidden, clock=forbidden, id_factory=forbidden)
        self.assertEqual(result, first)
        self.assertEqual(self.snapshot(), before)
        forbidden.assert_not_called()

    def test_changed_identity_content_is_refused_without_append(self):
        self.append(payload={"text": "first"})
        self.refuse(lambda: self.append(payload={"text": "changed"}), "bad_op")

    def test_operation_identity_is_scoped_to_actor(self):
        first = self.append()
        second = self.append(agent="other-agent")
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["op_id"], second["op_id"])
        self.assertEqual(second["lamport"], first["lamport"] + 1)

    def test_validation_rejection_has_no_journal_effect(self):
        def reject(history, event):
            raise LineageError("conflict", "regression rejection")
        self.refuse(lambda: self.append(validators={"regression.event": reject}), "conflict")

    def test_snapshot_is_detached(self):
        before = self.raw()
        snapshot = journal.snapshot(self.home)
        snapshot[0]["payload"]["text"] = "modified detached data"
        self.assertEqual(self.raw(), before)
        self.assertEqual(journal.snapshot(self.home)[0]["payload"]["text"], "working")

    def test_raw_line_chain_is_independently_hashed(self):
        self.append()
        previous = "0" * 64
        for number, line in enumerate(self.raw().splitlines(keepends=True), 1):
            value = json.loads(line)
            self.assertEqual(value["lamport"], number)
            self.assertEqual(value["prev_sha256"], previous)
            claimed = value.pop("sha256")
            encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
            self.assertEqual(claimed, hashlib.sha256(encoded).hexdigest())
            previous = hashlib.sha256(line).hexdigest()
        self.assertTrue(journal.verify(self.home)["ok"])

    def test_one_byte_tamper_is_reported_with_coordinate(self):
        original = self.raw()
        self.assertIn(b"working", original)
        self.path.write_bytes(original.replace(b"working", b"Working", 1))
        report = journal.verify(self.home)
        self.assertFalse(report["ok"])
        self.assertTrue(report["errors"])
        self.assertEqual(report["errors"][0]["line"], 1)
        with self.assertRaises(LineageError):
            journal.snapshot(self.home)

    def test_torn_final_line_is_not_a_committed_event(self):
        self.path.write_bytes(self.raw() + b'{"incomplete":')
        self.assertEqual(len(journal.snapshot(self.home)), 1)
        report = journal.verify(self.home)
        self.assertTrue(report["ok"])
        self.assertIsNotNone(report["torn_tail"])
        self.append()
        self.assertEqual(len(journal.snapshot(self.home)), 2)
        self.assertIsNone(journal.verify(self.home)["torn_tail"])

    def test_clean_interpreter_replays_durable_event(self):
        first = self.append()
        before = self.raw()
        code = """import json,sys
from lineage.core import journal
value=journal.transact(sys.argv[1],agent='executor-a',op_id='request0001',
kind='regression.event',payload={'text':'working'},validators={})
print(json.dumps(value,sort_keys=True))
"""
        child = subprocess.run([sys.executable, "-B", "-c", code, str(self.home)],
                               cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(json.loads(child.stdout), first)
        self.assertEqual(self.raw(), before)

    def test_two_process_writers_keep_all_events_in_order(self):
        code = """import sys
from lineage.core import journal
sys.stdin.buffer.read(1)
for n in range(12):
 journal.transact(sys.argv[1],agent=sys.argv[2],op_id=f'parallel{n:04d}',
 kind='regression.event',payload={'n':n},validators={'regression.event':lambda h,e:None})
"""
        children = []
        try:
            for actor in ("writer-one", "writer-two"):
                child = subprocess.Popen([sys.executable, "-B", "-c", code, str(self.home), actor],
                                         cwd=ROOT, stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                children.append(child)
            for child in children:
                child.stdin.write(b"x")
                child.stdin.flush()
            for child in children:
                out, err = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 0, (out + err).decode())
        finally:
            for child in children:
                if child.poll() is None:
                    self.assertGreater(child.pid, 1)
                    child.kill()
                child.communicate(timeout=5)
        events = journal.snapshot(self.home)
        self.assertEqual(len(events), 25)
        self.assertEqual([e["lamport"] for e in events], list(range(1, 26)))
        self.assertEqual(len({e["id"] for e in events}), 25)
        self.assertEqual({actor:sum(e["agent"] == actor for e in events)
                          for actor in ("writer-one", "writer-two")},
                         {"writer-one":12, "writer-two":12})
        self.assertTrue(journal.verify(self.home)["ok"])
