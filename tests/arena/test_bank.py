"""Bank integrity, strict decoding, split isolation and hostile filesystem data."""
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path
from unittest import mock

from .helpers import ArenaCase, bank, bank_data, canonical, digest, task


class BankTests(ArenaCase):
    def test_a3_manifest_and_canonical_hash_are_independent(self):
        loaded = self.invoke(bank.load, "demo-offline", ctx=self.ctx)
        self.assertEqual(loaded, self.bank)
        persisted = (self.bankdir / "bank.json").read_bytes()
        self.assertNotEqual(hashlib.sha256(persisted).hexdigest(), digest(loaded))
        self.assertIsNone(self.invoke(bank.verify, loaded, digest(loaded)))
        self.rejects("hash_mismatch", bank.verify, loaded, "0" * 64)
        self.assertFalse(self.events("run.open"))

    def test_a3_load_and_selection_are_defensive(self):
        loaded = self.invoke(bank.load, "demo-offline", ctx=self.ctx)
        selected = self.invoke(bank.tasks, loaded, purpose="select")
        self.assertIsInstance(selected, tuple)
        selected[0]["prompt"] = "changed"
        loaded["tasks"].clear()
        self.assertEqual(self.invoke(bank.load, "demo-offline", ctx=self.ctx), self.bank)

    def test_a3_changed_raw_byte_is_hash_mismatch(self):
        (self.bankdir / "bank.json").write_bytes(canonical(self.bank) + b" \n")
        self.rejects("hash_mismatch", bank.load, "demo-offline", ctx=self.ctx)

    def test_a3_missing_manifest_has_no_fallback(self):
        (self.bankdir / "MANIFEST.sha256").unlink()
        self.rejects("hash_mismatch", bank.load, "demo-offline", ctx=self.ctx)

    def test_a3_identity_mismatch_is_hash_mismatch(self):
        altered = deepcopy(self.bank)
        altered["bank_id"] = "other-bank"
        self.write_bank(altered)
        self.rejects("hash_mismatch", bank.load, "demo-offline", ctx=self.ctx)

    def test_a3_duplicate_task_ids_and_missing_data(self):
        for change in ("duplicate", "prompt", "expected"):
            with self.subTest(change=change):
                altered = deepcopy(self.bank)
                if change == "duplicate":
                    altered["tasks"][1]["id"] = altered["tasks"][0]["id"]
                else:
                    del altered["tasks"][0][change]
                self.write_bank(altered)
                self.rejects("bad_args", bank.load, "demo-offline", ctx=self.ctx)

    def test_a2_strict_raw_bank_matrix(self):
        base = canonical(self.bank)
        invalid = [base.replace(b'"baseline":', b'"baseline":{},"baseline":', 1),
                   base.replace(b'"repair_loops":0', b'"repair_loops":true', 1),
                   base.replace(b'"repair_loops":0', b'"repair_loops":9007199254740992', 1),
                   base.replace(b'"repair_loops":0', b'"repair_loops":NaN', 1),
                   base.replace(b'"repair_loops":0', b'"repair_loops":Infinity', 1),
                   base.replace(b'"repair_loops":0', b'"repair_loops":1e999', 1),
                   base.replace(b'Synthetic offline benchmark', b'\\ud800', 1),
                   base.replace(b'Synthetic offline benchmark', b'\xff', 1), base + b'{}',
                   base.replace(b'"split":"select"', b'"split":"select","extra":1', 1)]
        for raw in invalid:
            with self.subTest(raw=raw[:80]):
                self.write_bank(self.bank, raw=raw)
                self.rejects("bad_args", bank.load, "demo-offline", ctx=self.ctx)
        self.write_bank(self.bank)
        self.assertEqual(self.invoke(bank.load, "demo-offline", ctx=self.ctx), self.bank)

    def test_a4_traversal_identifiers(self):
        for identifier in ("../demo-offline", "demo-offline/../other", "/other", "..", "demo_offline"):
            with self.subTest(identifier=identifier):
                self.rejects("bad_args", bank.load, identifier, ctx=self.ctx)
        self.assertFalse(self.events("run.open"))

    def test_a4_manifest_members_confined_and_unambiguous(self):
        valid_hash = hashlib.sha256((self.bankdir / "bank.json").read_bytes()).hexdigest()
        for member in ("../bank.json", "/bank.json", "sub/../bank.json", "bank.json\n" + valid_hash + "  bank.json", "other.json"):
            with self.subTest(member=member):
                self.write_bank(self.bank, manifest=valid_hash + "  " + member + "\n")
                self.rejects("hash_mismatch", bank.load, "demo-offline", ctx=self.ctx)
        for manifest in ("", "not-a-manifest\n", "0  bank.json\n"):
            self.write_bank(self.bank, manifest=manifest)
            self.rejects("hash_mismatch", bank.load, "demo-offline", ctx=self.ctx)

    def test_a4_symlinked_bank_file_and_manifest(self):
        for filename in ("bank.json", "MANIFEST.sha256"):
            with self.subTest(filename=filename):
                self.write_bank(self.bank)
                target = self.base / ("outside-" + filename)
                target.write_bytes((self.bankdir / filename).read_bytes())
                (self.bankdir / filename).unlink()
                (self.bankdir / filename).symlink_to(target)
                self.rejects("hash_mismatch", bank.load, "demo-offline", ctx=self.ctx)
                (self.bankdir / filename).unlink()

    def test_a4_symlinked_bank_directory(self):
        real = self.bankdir.with_name("actual-bank")
        self.bankdir.rename(real)
        self.bankdir.symlink_to(real, target_is_directory=True)
        self.rejects("hash_mismatch", bank.load, "demo-offline", ctx=self.ctx)

    def test_a5_split_filter_preserves_hash_pinned_order(self):
        for purpose, split in (("select", "select"), ("confirm", "heldout")):
            selected = self.invoke(bank.tasks, self.bank, purpose=purpose)
            self.assertEqual(selected, tuple(t for t in self.bank["tasks"] if t["split"] == split))
        self.assertEqual([t["id"] for t in self.invoke(bank.tasks, self.bank, purpose="select")],
                         ["task00000003", "task00000002"])

    def test_a5_empty_eligible_split_is_not_zero_observations(self):
        self.rejects("bad_args", bank.tasks, bank_data([task(1, "heldout")]), purpose="select")
        self.rejects("bad_args", bank.tasks, self.bank, purpose="unknown")

    def test_a42_bundled_bank_is_synthetic_and_closed(self):
        context = replace(self.ctx, services=type(self.ctx.services)(**{
            **vars(self.ctx.services), "repo_root": Path(__file__).resolve().parents[2]}))
        value = self.invoke(bank.load, "demo-offline", ctx=context)
        self.assertEqual(set(value), {"schema", "bank_id", "tasks"})
        self.assertEqual(value["bank_id"], "demo-offline")
        self.assertEqual({t["split"] for t in value["tasks"]}, {"select", "heldout"})
        self.assertIn("Synthetic offline benchmark", str(value))
        self.assertNotIn(str(self.base), str(value))
        self.assertFalse(self.events())
