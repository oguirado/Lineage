"""Independent raw-byte hashes, package pins and corrupted stored records."""
import copy
import json
import re
from unittest import mock

from . import (OracleCase, PUBLIC_IDS, OWNED, REFERENCE_FILES, SOURCE_PIN, canonical, sha)


class ArtifactOracle(OracleCase):
    def test_a08_memory_derivative_honesty_and_citations(self):
        text = self.required("references/memory_v21/REFERENCE.md").read_text(encoding="utf-8")
        for token in ("Memory v2.1", "3.7", "6.1.1", "0.718", "0.738", "CITED",
                      "NORTH_STAR.md", "P2", "P4", "P8", "STRATEGY.md", "2.2"):
            self.assertIn(token, text)
        self.assertTrue("P3" in text or re.search(r"P2\s*[–-]\s*P4", text), "Cite P3 directly or through P2–P4")
        lower = text.casefold()
        for concept in (r"derivative", r"mandatory", r"operator", r"level.?one|level.?1",
                        r"level.?two|level.?2", r"receipt", r"context", r"weight",
                        r"adaptation", r"unfulfilled|unenforced|target", r"storage|latency",
                        r"measur", r"not.*(prove|benefit|beat)|unproven|unestablished|unknown|did not beat|must.*measur|require.*measur"):
            self.assertRegex(lower, concept)

    def test_a08_source_provenance_and_unavailable_fields(self):
        catalog = self.read_json("references/catalog.json")
        by_id = {r["ref_id"]: r for r in catalog["references"]}
        source = by_id["gold_s1"]["source"]
        self.assertEqual(source, {"document_id": "GOLD-S1", "version": "PM-1001.1",
                                 "sha256": SOURCE_PIN, "status": "ACTIVE",
                                 "generation": "ASSEMBLED", "publication": "DRAFT"})
        self.assertEqual(by_id["memory_v21"]["source"],
                         {"document_id": "Memory v2.1", "version": "2.1", "sha256": None,
                          "status": None, "generation": None, "publication": None})

    def test_a09_lf_final_newline_no_timestamp_or_environment_fields(self):
        for relative in REFERENCE_FILES:
            raw = self.required(relative).read_bytes()
            self.assertTrue(raw.endswith(b"\n"), relative)
            self.assertNotIn(b"\r", raw, relative)
            raw.decode("utf-8", errors="strict")
            self.assertNotRegex(raw.decode(), r'"(?:generated_at|hostname|repo_root|source_path)"\s*:')
            self.assertNotRegex(raw.decode(), r"\b20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d")

    def test_a09_two_isolated_packages_produce_equal_bytes_and_results(self):
        module = self.domain()
        with self.reference_copy() as left, self.reference_copy() as right:
            for relative in REFERENCE_FILES:
                self.assertEqual((left / relative).read_bytes(), (right / relative).read_bytes())
            for ref_id in PUBLIC_IDS:
                self.assertEqual(self.get(module, ref_id, left), self.get(module, ref_id, right))
                self.assertEqual(self.verify(module, ref_id, left), self.verify(module, ref_id, right))

    def test_a10_independent_package_and_file_hashes_match_code_pins(self):
        module = self.domain()
        catalog = self.read_json("references/catalog.json")
        self.assertEqual(set(catalog), {"schema", "references"})
        self.assertEqual(catalog["schema"], "lineage.references/v1")
        self.assertEqual([r["ref_id"] for r in catalog["references"]], list(PUBLIC_IDS))
        self.assertEqual(getattr(module, "PUBLIC_REFERENCE_IDS", None), PUBLIC_IDS)
        self.assertEqual(set(getattr(module, "REFERENCE_PINS", {})), set(PUBLIC_IDS))
        for descriptor in catalog["references"]:
            self.assertEqual(set(descriptor), {"ref_id", "title", "source", "files", "sha256"})
            self.assertTrue(descriptor["title"])
            ref_id = descriptor["ref_id"]
            self.assertEqual([f["path"] for f in descriptor["files"]], OWNED[ref_id])
            for item in descriptor["files"]:
                self.assertEqual(set(item), {"path", "sha256", "bytes"})
                raw = self.required(item["path"]).read_bytes()
                self.assertIs(type(item["bytes"]), int)
                self.assertEqual(item["bytes"], len(raw))
                self.assertEqual(item["sha256"], sha(raw))
            independent = sha(canonical({k: v for k, v in descriptor.items() if k != "sha256"}))
            self.assertEqual(descriptor["sha256"], independent)
            self.assertEqual(module.REFERENCE_PINS[ref_id], independent)
            self.assertNotEqual(independent, SOURCE_PIN)

    def test_a11_complete_canonical_manifest(self):
        manifest = self.required("references/MANIFEST.sha256").read_bytes()
        lines = manifest.decode().splitlines(keepends=True)
        entries = []
        for line in lines:
            self.assertRegex(line, r"\A[0-9a-f]{64}  [A-Za-z0-9_./-]+\n\Z")
            digest, relative = line[:-1].split("  ", 1)
            self.assertNotIn("..", relative.split("/"))
            self.assertFalse(relative.startswith("/"))
            self.assertEqual(sha(self.required(relative).read_bytes()), digest)
            entries.append(relative)
        self.assertEqual(entries, sorted(set(entries)))
        actual = sorted(p.relative_to(self.required("references/catalog.json").parents[1]).as_posix()
                        for p in self.required("references/catalog.json").parent.rglob("*")
                        if p.is_file() and p.name != "MANIFEST.sha256")
        self.assertEqual(entries, actual)

    def test_a12_optional_pin_verifies_only_public_package(self):
        module = self.domain()
        for ref_id in PUBLIC_IDS:
            self.assertTrue(hasattr(module, "REFERENCE_PINS"))
            pin = module.REFERENCE_PINS[ref_id]
            result = self.verify(module, ref_id, expected_sha256=pin)
            self.assertEqual(set(result), {"schema", "ref_id", "verified", "sha256", "files_checked",
                                           "source_sha256", "source_verified"})
            self.assertEqual(result["schema"], "lineage.reference-verification/v1")
            self.assertEqual(result["ref_id"], ref_id)
            self.assertIs(result["verified"], True)
            self.assertIs(result["source_verified"], False)
            self.assertEqual(result["sha256"], pin)
            self.assertEqual(result["source_sha256"], SOURCE_PIN if ref_id == "gold_s1" else None)
            descriptor = next(d for d in self.read_json("references/catalog.json")["references"]
                              if d["ref_id"] == ref_id)
            self.assertEqual(result["files_checked"], descriptor["files"])

    def test_a12_wrong_expected_pin_and_source_pin_are_rejected(self):
        module = self.domain()
        function = self.function(module, "reference_verify")
        for value in (SOURCE_PIN, "0" * 64):
            self.reject(function, "hash_mismatch", "gold_s1", expected_sha256=value)

    def test_a15_get_returns_complete_exact_detached_data(self):
        module = self.domain()
        for ref_id in PUBLIC_IDS:
            original = self.get(module, ref_id)
            self.assertEqual(set(original), {"schema", "ref_id", "title", "sha256", "source", "files",
                                             "rules", "contract"})
            self.assertEqual(original["schema"], "lineage.reference/v1")
            self.assertEqual(original["ref_id"], ref_id)
            descriptor = next(d for d in self.read_json("references/catalog.json")["references"]
                              if d["ref_id"] == ref_id)
            for key, value in descriptor.items():
                self.assertEqual(original[key], value)
            if ref_id == "gold_s1":
                self.assertEqual(original["rules"], self.read_json("references/gold_s1/gold_rules.json")["rules"])
                self.assertIsNone(original["contract"])
            else:
                self.assertIsNone(original["rules"])
                self.assertEqual(original["contract"], self.required("references/memory_v21/REFERENCE.md").read_text())
            expected = copy.deepcopy(original)
            changed = original
            changed["source"]["document_id"] = "changed"
            changed["files"][0]["bytes"] = 0
            if changed["rules"]:
                changed["rules"][0]["roles"].append("changed")
            self.assertEqual(self.get(module, ref_id), expected)
            returned = self.get(module, ref_id)
            returned.clear()
            self.assertEqual(self.get(module, ref_id), expected)

    def attack(self, kind):
        module = self.domain()
        with self.reference_copy() as root:
            registry = root / "references/gold_s1/gold_rules.json"
            catalog = root / "references/catalog.json"
            manifest = root / "references/MANIFEST.sha256"
            if kind == "registry_byte":
                registry.write_bytes(registry.read_bytes() + b" ")
            elif kind == "index_byte":
                path = root / "references/gold_s1/gold_rules.md"
                path.write_bytes(path.read_bytes() + b" ")
            elif kind == "memory_byte":
                path = root / "references/memory_v21/REFERENCE.md"
                path.write_bytes(path.read_bytes() + b" ")
                self.rejected_package(module, root, ref_id="memory_v21")
                return
            elif kind == "missing_file":
                registry.unlink()
            elif kind == "duplicate_manifest":
                manifest.write_bytes(manifest.read_bytes() + manifest.read_bytes().splitlines(keepends=True)[0])
            elif kind == "manifest_corrupt":
                manifest.write_bytes(b"not a checksum\n")
            elif kind == "unexpected_file":
                (registry.parent / "unexpected.json").write_bytes(b"{}\n")
            elif kind in {"wrong_length", "unknown_catalog_field", "catalog_path_escape", "catalog_absolute_path"}:
                data = json.loads(catalog.read_bytes())
                gold = next(d for d in data["references"] if d["ref_id"] == "gold_s1")
                if kind == "wrong_length":
                    gold["files"][0]["bytes"] += 1
                elif kind == "unknown_catalog_field":
                    data["unknown"] = True
                elif kind == "catalog_path_escape":
                    gold["files"][0]["path"] = "../outside.txt"
                else:
                    gold["files"][0]["path"] = str(root / "outside.txt")
                catalog.write_bytes(canonical(data) + b"\n")
            elif kind == "recomputed_tamper":
                registry.write_bytes(registry.read_bytes() + b" ")
                self.repack(root)
            self.rejected_package(module, root)

    def strict_attack(self, kind):
        module = self.domain()
        with self.reference_copy() as root:
            path = root / "references/gold_s1/gold_rules.json"
            data = json.loads(path.read_bytes())
            if kind == "duplicate_nested_key":
                data["source"]["title"] = "duplicate marker"
                raw = canonical(data).replace(b'"title":"duplicate marker"', b'"title":"one","title":"two"')
            elif kind == "nonfinite":
                raw = canonical(data).replace(b'"rules":[', b'"rules":[NaN,', 1)
            elif kind == "float_overflow":
                raw = canonical(data).replace(b'"rules":[', b'"rules":[1e999,', 1)
            elif kind == "invalid_utf8":
                raw = b'"' + bytes([255]) + b'"'
            elif kind == "surrogate":
                raw = canonical(data).replace(b'"rules":[', b'"rules":["\\ud800",', 1)
            elif kind == "bad_digest":
                data["source"]["sha256"] = SOURCE_PIN.upper()
                raw = canonical(data)
            elif kind == "oversize":
                raw = canonical(data) + b" " * 1048577
            elif kind == "trailing_json":
                raw = canonical(data) + b"{}"
            path.write_bytes(raw + b"\n")
            pins = self.repack(root)
            self.assertTrue(hasattr(module, "REFERENCE_PINS"))
            with mock.patch.object(module, "REFERENCE_PINS", pins):
                self.rejected_package(module, root)


def _attack(kind, strict=False):
    def test(self):
        (self.strict_attack if strict else self.attack)(kind)
    return test


for _kind in ("registry_byte", "index_byte", "memory_byte", "recomputed_tamper", "missing_file",
              "duplicate_manifest", "manifest_corrupt", "unexpected_file", "wrong_length",
              "unknown_catalog_field", "catalog_path_escape", "catalog_absolute_path"):
    setattr(ArtifactOracle, "test_a10_a11_reject_" + _kind, _attack(_kind))
for _kind in ("duplicate_nested_key", "nonfinite", "float_overflow", "invalid_utf8", "surrogate",
              "bad_digest", "oversize", "trailing_json"):
    setattr(ArtifactOracle, "test_a14_reject_" + _kind, _attack(_kind, True))
