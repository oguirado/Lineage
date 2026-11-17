"""A7–A9: all evidence is confined, opened and checked at admission."""
import copy
import os
import threading
from unittest import mock
from ._support import IntegrationCase, OWNER, unit, sha


class ReceiptTests(IntegrationCase):
    def test_a07_level_two_receipt_and_level_three_observation(self):
        self.runtime()
        self.assertEqual(self.write(self.shaped()).value["unit"]["level"], 2)
        self.assertEqual(self.write(unit(uid="unit_002")).value["unit"]["receipts"], [])
        for absent in (False, True):
            value = unit("lesson", 2, uid="unit_003")
            if absent:
                del value["receipts"]
            self.reject("bad_args", lambda: self.write(value))

    def test_a07_wrong_missing_and_optional_receipts(self):
        self.runtime()
        self.write(self.shaped())
        for level in (2, 3):
            for path, digest in (("evidence/check.txt", "0" * 64),
                                 ("evidence/missing.txt", sha(b"missing"))):
                value = unit(level=level, uid="unit_002", receipt={"path": path, "sha256": digest})
                self.reject("hash_mismatch", lambda: self.write(value))
        value = unit(uid="unit_002", receipt=self.evidence())
        self.assertEqual(self.write(value).value["unit"], value)

    def test_a08_malformed_coordinates(self):
        self.runtime()
        self.write(self.shaped())
        for path in ("/outside.txt", "../outside.txt", "evidence/../check.txt", "./check.txt",
                     "evidence/./check.txt", "evidence//check.txt", "evidence/", "", "evidence\\check.txt"):
            value = unit("lesson", 2, uid="unit_002", receipt={"path": path, "sha256": sha(b"fixture")})
            with self.subTest(path=path):
                self.reject("bad_args", lambda: self.write(value))

    def test_a08_symlink_file_and_ancestor(self):
        self.runtime()
        receipt = self.evidence()
        self.write(unit("lesson", 2, receipt=receipt))
        os.symlink("check.txt", self.home / "evidence/link.txt")
        os.symlink("evidence", self.home / "linked")
        for path in ("evidence/link.txt", "linked/check.txt"):
            value = unit("lesson", 2, uid="unit_002", receipt={**receipt, "path": path})
            self.reject("hash_mismatch", lambda: self.write(value))

    def test_a09_changed_after_inspection_before_lock(self):
        self.runtime()
        self.write()
        value = self.shaped(uid="unit_002")
        self.validate(value)
        before = self.fingerprint()
        reached, changed = threading.Event(), threading.Event()
        original = self.journal.transact
        def held(command, prepare, render, *, ctx):
            reached.set()
            if not changed.wait(1):
                raise AssertionError("evidence barrier did not release")
            return original(command, prepare, render, ctx=ctx)
        outcome = []
        def writer():
            try:
                self.write(value)
            except Exception as exc:
                outcome.append(exc)
        with self.patch_seam(self.journal, "transact", held):
            worker = threading.Thread(target=writer, daemon=True)
            worker.start()
            try:
                self.assertTrue(reached.wait(1), "write never entered transaction seam")
                (self.home / value["receipts"][0]["path"]).write_bytes(b"changed at barrier")
            finally:
                changed.set()
                worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(outcome), 1)
        self.assertEqual(getattr(outcome[0], "code", None), "hash_mismatch")
        self.assertEqual(self.fingerprint(), before)

    def test_a09_unreadable_source_is_failure(self):
        self.runtime()
        value = self.shaped()
        self.write(value)
        # A directory at a schema-valid file coordinate is unreadable as evidence
        # even under a privileged test user; chmod-only probes are unreliable.
        directory = self.home / "evidence/unreadable.txt"
        directory.mkdir()
        value = unit("lesson", 2, uid="unit_002", receipt={"path": "evidence/unreadable.txt", "sha256": sha(b"")})
        self.reject("hash_mismatch", lambda: self.write(value))
