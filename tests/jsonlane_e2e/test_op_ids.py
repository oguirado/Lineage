"""Contract OpId bounds and persisted legacy digest identities."""
from pathlib import Path
import tempfile
import unittest

from lineage.core import journal
from lineage.core.errors import LineageError


class JournalOpIds(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)

    def transact(self, operation, **kwargs):
        return journal.transact(self.home, agent="alice", op_id=operation,
                                kind="test.event", payload={"value": 1},
                                validators={"test.event": lambda history, event: None}, **kwargs)

    def test_contract_alphabet_and_length_replay_unchanged(self):
        for operation in ("A", "a.b:c/d_-", "a" * 128):
            with self.subTest(operation=operation):
                event = self.transact(operation)
                self.assertEqual(event["op_id"], operation)
                before = (self.home / "ledger/main/events.jsonl").read_bytes()
                self.assertEqual(self.transact(operation), event)
                self.assertEqual((self.home / "ledger/main/events.jsonl").read_bytes(), before)
        self.assertTrue(journal.verify(self.home)["ok"])

    def test_invalid_operation_ids_append_nothing(self):
        self.transact("valid")
        path = self.home / "ledger/main/events.jsonl"
        before = path.read_bytes()
        for operation in (None, True, "", "_leading", "-leading", ".leading",
                          "/leading", ":leading", "bad id", "a" * 129, "valid\n", "é"):
            with self.subTest(operation=operation):
                with self.assertRaises(LineageError) as raised:
                    self.transact(operation)
                self.assertEqual(raised.exception.code, "bad_op")
                self.assertEqual(path.read_bytes(), before)

    def test_persisted_legacy_digest_id_still_verifies_and_replays(self):
        operation = "a" * 64
        event = self.transact(operation)
        before = (self.home / "ledger/main/events.jsonl").read_bytes()
        self.assertEqual(journal.snapshot(self.home), (event,))
        self.assertTrue(journal.verify(self.home)["ok"])
        self.assertEqual(self.transact(operation), event)
        self.assertEqual((self.home / "ledger/main/events.jsonl").read_bytes(), before)
