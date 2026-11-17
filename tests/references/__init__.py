"""Independent U07 oracle support; no runtime implementation or disk stubs."""
import sys
sys.dont_write_bytecode = True

import contextlib
import copy
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import unittest
from unittest import mock
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = ROOT / "tests" / "references"
PUBLIC_IDS = ("gold_s1", "memory_v21")
INPUT_PIN = "3c4d347ed6d4011112a61f3d48da76c4b5d230d688a0fc71cbb715b4cba0af8c"
SOURCE_PIN = "f90dc84fc814fce0258a12d0e0fd17e5332021410470c469247e2b019b3511c5"
GATES = ("G-PACK", "G-SURFACE", "G-LAWS", "G-WHOLE", "G-E2E-TOUCHED",
         "G-REAL-PEER", "G-HOSTED-LIKE", "G-NOWEAKEN", "G-LINK", "G-LIVE",
         "G-HOSTED", "G-JUDGE", "G-MEM")
REJECTED = ("PREFIX_PRUNING", "HOMOGENEOUS_PROPOSERS", "DEEP_AGGREGATION", "LARGE_BATCHES")
SEATS = ("ORCHESTRATOR", "WRITER", "SWARM", "JUDGE", "EXTERNAL_TESTER",
         "LIVE_VERIFIER", "UI_PEER", "ROUTER", "ECONOMICS")
LABELS = {}
for section, labels in (("2.1", [f"D{i}" for i in range(1, 9)]),
                        ("2.2", [f"L{i}" for i in range(1, 9)]),
                        ("2.4", GATES), ("4.1", [f"I{i}" for i in range(1, 29)]),
                        ("4.2", [f"A{i}" for i in range(1, 36)] +
                         ["REJECTED." + item for item in REJECTED]),
                        ("5", ["DERIVED.SEAT." + item for item in SEATS])):
    LABELS.update({f"GS-{section}-{i}": label for i, label in enumerate(labels, 1)})
ROLES = {"agent_creator", "author", "capsule_tester", "cross_reviewer", "oracle_writer",
         "orchestrator", "performance_auditor", "persona", "privacy_verifier", "repairer", "researcher"}
REFERENCE_FILES = (
    "references/MANIFEST.sha256", "references/catalog.json", "references/publication_policy.json",
    "references/gold_s1/gold_rules.json", "references/gold_s1/gold_rules.md",
    "references/memory_v21/REFERENCE.md",
)
OWNED = {"gold_s1": ["references/gold_s1/gold_rules.json", "references/gold_s1/gold_rules.md"],
         "memory_v21": ["references/memory_v21/REFERENCE.md"]}
REPORT_KEYS = {"schema", "ok", "files_checked", "exclusions", "findings"}
FINDING_KEYS = {"code", "path", "line", "byte_offset", "rule_id"}
CODES = {"local_path", "hostname", "secret_literal", "scrub_token", "unsafe_link", "unreadable", "invalid_policy"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def sentinel():
    return "-".join(("lineage", "oracle", "s\u00e9ntinel"))


def fingerprint(label, text, mode="literal"):
    normalized = unicodedata.normalize("NFC", text).casefold()
    parts = [part for part in normalized.split("*") if part]
    return {"id": label, "mode": mode,
            "segments": [{"sha256": sha(part.encode()), "chars": len(part)} for part in parts],
            "leading_star": normalized.startswith("*"), "trailing_star": normalized.endswith("*")}


def tree_state(root):
    """Observe content and write-sensitive metadata, excluding read access times."""
    result = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        info = path.lstat()
        raw = (path.read_bytes() if stat.S_ISREG(info.st_mode) else
               os.readlink(path).encode() if stat.S_ISLNK(info.st_mode) else b"")
        result[rel] = (info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
                       info.st_ino, sha(raw))
    return result


class OracleCase(unittest.TestCase):
    def module(self, name):
        relative = name.replace(".", "/") + ".py"
        self.assertTrue((ROOT / relative).is_file(), "Missing required implementation: " + relative)
        try:
            with mock.patch.object(sys, "dont_write_bytecode", True):
                return importlib.import_module(name)
        except Exception as exc:
            self.fail("Required module is not usable: " + name + " (" + type(exc).__name__ + ")")

    def function(self, module, name):
        value = getattr(module, name, None)
        self.assertTrue(callable(value), "Missing required callable: " + name)
        return value

    def invoke(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except AssertionError:
            raise
        except Exception as exc:
            self.fail("Required operation raised " + type(exc).__name__ + " instead of returning data")

    def domain(self):
        return self.module("lineage.domain.references")

    def checker(self):
        return self.module("tools.publish_check")

    def required(self, relative):
        path = ROOT / relative
        self.assertTrue(path.is_file(), "Missing required artifact: " + relative)
        return path

    def read_json(self, relative):
        return json.loads(self.required(relative).read_bytes())

    @contextlib.contextmanager
    def temporary(self):
        with tempfile.TemporaryDirectory(prefix="case-", dir=TEST_ROOT) as location:
            yield Path(location)

    @contextlib.contextmanager
    def reference_copy(self):
        for relative in REFERENCE_FILES:
            self.required(relative)
        with self.temporary() as root:
            shutil.copytree(ROOT / "references", root / "references", symlinks=True)
            yield root

    def get(self, module, ref_id, root=None):
        kwargs = {} if root is None else {"repo_root": root}
        return self.invoke(self.function(module, "reference_get"), ref_id, **kwargs)

    def verify(self, module, ref_id, root=None, **kwargs):
        if root is not None:
            kwargs["repo_root"] = root
        return self.invoke(self.function(module, "reference_verify"), ref_id, **kwargs)

    def reject(self, function, code, *args, **kwargs):
        try:
            function(*args, **kwargs)
        except AssertionError:
            raise
        except Exception as exc:
            self.assertEqual(getattr(exc, "code", None), code,
                             "Failure must retain the specified domain code")
            diagnostic = str(exc) + " " + str(getattr(exc, "detail", ""))
            self.assertNotIn(str(ROOT), diagnostic)
            self.assertNotIn("Traceback", diagnostic)
            return exc
        self.fail("Required rejection was accepted: " + code)

    def rejected_package(self, module, root, ref_id="gold_s1"):
        before = tree_state(root)
        for name in ("reference_get", "reference_verify"):
            self.reject(self.function(module, name), "hash_mismatch", ref_id, repo_root=root)
        self.assertEqual(tree_state(root), before, "Integrity failures must not repair or cache")

    def repack(self, root):
        """Independent test builder; never borrows a runtime digest implementation."""
        catalog_path = root / "references/catalog.json"
        catalog = json.loads(catalog_path.read_bytes())
        pins = {}
        for descriptor in catalog["references"]:
            for item in descriptor["files"]:
                raw = (root / item["path"]).read_bytes()
                item.update(sha256=sha(raw), bytes=len(raw))
            descriptor["sha256"] = sha(canonical({k: v for k, v in descriptor.items() if k != "sha256"}))
            pins[descriptor["ref_id"]] = descriptor["sha256"]
        catalog_path.write_bytes(canonical(catalog) + b"\n")
        files = sorted(p for p in (root / "references").rglob("*") if p.is_file()
                       and p.name != "MANIFEST.sha256")
        manifest = "".join(sha(p.read_bytes()) + "  " + p.relative_to(root).as_posix() + "\n" for p in files)
        (root / "references/MANIFEST.sha256").write_text(manifest, encoding="utf-8", newline="\n")
        return pins

    def report(self, checker, root):
        result = self.invoke(self.function(checker, "scan_tree"), root)
        self.assertIsInstance(result, dict)
        self.assertEqual(set(result), REPORT_KEYS)
        self.assertEqual(result["schema"], "lineage.publish-check/v1")
        self.assertIs(type(result["ok"]), bool)
        self.assertIs(type(result["files_checked"]), int)
        self.assertGreaterEqual(result["files_checked"], 0)
        self.assertIsInstance(result["exclusions"], list)
        self.assertIsInstance(result["findings"], list)
        for finding in result["findings"]:
            self.assertEqual(set(finding), FINDING_KEYS)
            self.assertIn(finding["code"], CODES)
            self.assertIsInstance(finding["rule_id"], str)
            self.assertTrue(finding["rule_id"])
            for key, minimum in (("line", 1), ("byte_offset", 0)):
                value = finding[key]
                if value is not None:
                    self.assertIs(type(value), int)
                    self.assertGreaterEqual(value, minimum)
            if finding["path"] is not None:
                self.assertFalse(Path(finding["path"]).is_absolute())
                self.assertNotIn("..", Path(finding["path"]).parts)
        self.assertEqual(result["ok"], not result["findings"])
        return result

    def leak(self, checker, root, content, code="scrub_token", name="sample.txt"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode() if isinstance(content, str) else content)
        report = self.report(checker, root)
        self.assertFalse(report["ok"], "Seeded forbidden control must fail")
        self.assertIn(code, {item["code"] for item in report["findings"]})
        encoded = json.dumps(report, ensure_ascii=False)
        self.assertNotIn(str(root), encoded)
        self.assertNotIn(sentinel(), encoded)
        return report

    def prework(self):
        # A-U07: The staged pre-work fixture is now available; retain its independent byte pin.
        location = os.environ.get("LINEAGE_U07_ORACLE_GOLD_INPUT",
                                  str(ROOT / ".unit/prework/gold_rules.json"))
        self.assertTrue(location, "AUSENTE — no inventar: injected pre-work gold_rules.json")
        path = Path(location)
        self.assertTrue(path.is_file(), "Injected pre-work input is unavailable")
        raw = path.read_bytes()
        self.assertEqual(sha(raw), INPUT_PIN, "Pre-work byte identity changed")
        document = json.loads(raw)
        self.assertEqual(document["schema"], "lineage.gold-rules/v1")
        self.assertEqual(len(document["rules"]), 105)
        self.assertEqual({r["id"] for r in document["rules"]}, set(LABELS))
        self.assertEqual(sum(r["scrub"] is True for r in document["rules"]), 32)
        return raw, document
