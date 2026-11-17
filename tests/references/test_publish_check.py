"""Publication controls use synthetic values assembled only at execution time."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import unicodedata
from unittest import mock

from . import (OracleCase, ROOT, REPORT_KEYS, canonical, sha, sentinel, fingerprint,
               tree_state)


def hostile(kind):
    slash = chr(47)
    back = chr(92)
    if kind == "posix":
        return slash.join(("", "home", "fixture-user", "private", "record.txt")), "local_path"
    if kind == "windows":
        return "C:" + back + back.join(("Users", "fixture-user", "record.txt")), "local_path"
    if kind == "unc":
        return back * 2 + back.join(("fixture-server", "private-share", "record.txt")), "local_path"
    host = "fixture-machine" + "." + "local"
    if kind == "hostname_config":
        return 'hostname = "' + host + '"', "hostname"
    if kind == "authority":
        return "https:" + slash * 2 + host + ":8443/api", "hostname"
    if kind == "secret":
        return "api_key=" + "sk" + "-" + "Ab3dE7fG9hJ2kL4mN6pQ8rS0tU1vW5xY" * 2, "secret_literal"
    raise AssertionError("Unknown synthetic leak class")


class PublicationOracle(OracleCase):
    def clean_tree(self, root):
        (root / "README.md").write_text("A portable public document.\n", encoding="utf-8")

    def test_a18_policy_schema_sentinel_and_inventory_digest(self):
        policy = self.read_json("references/publication_policy.json")
        self.assertEqual(set(policy), {"schema", "inventory_sha256", "fingerprints", "public_path_exceptions"})
        self.assertEqual(policy["schema"], "lineage.publication-policy/v1")
        entries = policy["fingerprints"]
        self.assertEqual(len(entries), len({f["id"] for f in entries}))
        production = sorted((f for f in entries if f["id"] != "test-sentinel"), key=lambda f: f["id"])
        self.assertTrue(production)
        self.assertEqual(policy["inventory_sha256"], sha(canonical(production)))
        self.assertEqual([f for f in entries if f["id"] == "test-sentinel"],
                         [fingerprint("test-sentinel", sentinel())])
        for entry in entries:
            self.assertEqual(set(entry), {"id", "mode", "segments", "leading_star", "trailing_star"})
            self.assertIn(entry["mode"], {"literal", "glob"})
            self.assertIs(type(entry["leading_star"]), bool)
            self.assertIs(type(entry["trailing_star"]), bool)
            self.assertTrue(entry["segments"])
            for part in entry["segments"]:
                self.assertEqual(set(part), {"sha256", "chars"})
                self.assertRegex(part["sha256"], r"\A[0-9a-f]{64}\Z")
                self.assertIs(type(part["chars"]), int)
                self.assertGreater(part["chars"], 0)
            if entry["mode"] == "literal":
                self.assertEqual(len(entry["segments"]), 1)
                self.assertFalse(entry["leading_star"])
                self.assertFalse(entry["trailing_star"])
        for exception in policy["public_path_exceptions"]:
            self.assertEqual(set(exception), {"fingerprint_id", "path", "reason"})
            self.assertIn(exception["fingerprint_id"], {f["id"] for f in production})
            self.assertRegex(exception["reason"], r"STRATEGY\.md.*(?:2\.1|2\.4)")
            self.assertFalse(Path(exception["path"]).is_absolute())
            self.assertNotIn("..", exception["path"].split("/"))
            self.assertTrue((ROOT / exception["path"]).is_file())

    def test_a18_independent_frozen_production_inventory(self):
        # Supplied by the oracle writer, never by the implementation being checked.
        # A-U07: Freeze supplied strategy expectations independently of the implementation policy.
        fixture = self.read_json("tests/references/policy_expectations.json")
        expected = os.environ.get("LINEAGE_U07_ORACLE_FINGERPRINTS",
                                  json.dumps(fixture["fingerprints"]))
        expected_pin = os.environ.get("LINEAGE_U07_ORACLE_INVENTORY_SHA256",
                                      fixture["inventory_sha256"])
        self.assertTrue(expected and expected_pin,
                        "AUSENTE — no inventar: independently frozen production inventory")
        records = json.loads(expected)
        self.assertIsInstance(records, list)
        records = sorted(records, key=lambda record: record["id"])
        self.assertEqual(sha(canonical(records)), expected_pin)
        policy = self.read_json("references/publication_policy.json")
        production = sorted((r for r in policy["fingerprints"] if r["id"] != "test-sentinel"),
                            key=lambda record: record["id"])
        self.assertEqual(production, records)
        self.assertEqual(policy["inventory_sha256"], expected_pin)

    def test_a18_default_policy_is_installed_not_selected_by_scan_root(self):
        checker = self.checker()
        with self.temporary() as root:
            self.clean_tree(root)
            report = self.report(checker, root)
            self.assertTrue(report["ok"])
            self.assertEqual(report["files_checked"], 1)
            self.leak(checker, root, sentinel())

    def test_a19_clean_ordinary_public_syntax_passes(self):
        checker = self.checker()
        with self.temporary() as root:
            clean = ("from lineage.domain import references\n"
                     "docs/CONTRACT.md\nGET /api/health\n#/agents\n"
                     "lineage.reference/v1\nsha256=" + "a" * 64 + "\n")
            (root / "clean.txt").write_text(clean)
            report = self.report(checker, root)
            self.assertTrue(report["ok"])
            self.assertEqual(report["files_checked"], 1)

    def leak_kind(self, kind, filename=False):
        checker = self.checker()
        value, code = hostile(kind)
        with self.temporary() as root:
            report = self.leak(checker, root, value, code)
            self.assertNotIn(value, json.dumps(report, ensure_ascii=False))

    def sentinel_variant(self, kind):
        checker = self.checker()
        value = sentinel()
        with self.temporary() as root:
            if kind == "filename":
                report = self.leak(checker, root, "A public sentence.\n", name=value + ".txt")
                self.assertNotIn(value, json.dumps(report, ensure_ascii=False))
            elif kind == "casefold":
                self.leak(checker, root, value.upper())
            elif kind == "unicode_nfd":
                self.leak(checker, root, unicodedata.normalize("NFD", value))
            elif kind in {"escaped_json", "escaped_python"}:
                escaped = "".join("\\u" + format(ord(c), "04x") for c in value)
                content = ('{"value":"' + escaped + '"}\n' if kind == "escaped_json" else
                           'value = "' + escaped + '"\n')
                self.leak(checker, root, content, name="sample.json" if kind == "escaped_json" else "sample.py")
            elif kind == "binary_prefix":
                self.leak(checker, root, bytes(range(256)) + value.encode())
            elif kind == "large_file":
                self.leak(checker, root, b"x" * (2 * 1024 * 1024 + 17) + value.encode())
            elif kind == "buffer_edges":
                # Probe both sides of common buffer boundaries without depending on one buffer size.
                raw = bytearray()
                for boundary in (256, 1024, 4096, 8192, 65536):
                    start = boundary - len(value.encode()) // 2
                    raw.extend(b"x" * max(0, start - len(raw)))
                    raw.extend(value.encode())
                report = self.leak(checker, root, bytes(raw))
                hits = [f for f in report["findings"] if f["code"] == "scrub_token"]
                self.assertGreaterEqual(len({f["byte_offset"] for f in hits}), 5)

    def test_a20_literal_sentinel_does_not_match_reordered_or_shortened_text(self):
        checker = self.checker()
        with self.temporary() as root:
            (root / "clean.txt").write_text(sentinel()[:-1] + "\n" + sentinel()[::-1])
            self.assertTrue(self.report(checker, root)["ok"])

    def test_a20_production_glob_expansions_require_injected_inventory_examples(self):
        # Raw production spellings cannot be stored in public test source.
        # A-U07: Reconstruct independently frozen concrete fixtures without private source spellings.
        fixture = self.read_json("tests/references/policy_expectations.json")
        examples = [{"token": "".join(map(chr, item["token_codepoints"])),
                     "rule_id": item["rule_id"]} for item in fixture["glob_examples"]]
        raw = os.environ.get("LINEAGE_U07_ORACLE_GLOB_EXAMPLES", json.dumps(examples))
        self.assertTrue(raw, "AUSENTE — no inventar: independent concrete inventory expansions")
        cases = json.loads(raw)
        self.assertTrue(cases)
        checker = self.checker()
        for case in cases:
            self.assertEqual(set(case), {"token", "rule_id"})
            self.assertNotIn("*", case["token"])
            with self.temporary() as root:
                report = self.leak(checker, root, case["token"])
                self.assertIn(case["rule_id"], {f["rule_id"] for f in report["findings"]})

    def test_a21_exceptions_apply_to_exact_owned_path_not_prose_or_siblings(self):
        policy = self.read_json("references/publication_policy.json")
        checker = self.checker()
        entries = {f["id"]: f for f in policy["fingerprints"]}
        self.assertIsInstance(policy["public_path_exceptions"], list)
        for exception in policy["public_path_exceptions"]:
            relative = exception["path"]
            entry = entries[exception["fingerprint_id"]]
            with self.temporary() as root:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("Public content.\n")
                self.assertTrue(self.report(checker, root)["ok"])
                path.write_text(relative + "\n")
                self.assertFalse(self.report(checker, root)["ok"], "Path exceptions cannot admit prose bindings")
            for changed in (relative + ".other", relative + "/descendant.txt"):
                with self.temporary() as root:
                    report = self.leak(checker, root, "Public content.\n", name=changed)
                    self.assertFalse(report["ok"])

    def test_a22_only_root_exclusion_boundaries_are_reported(self):
        checker = self.checker()
        with self.temporary() as root:
            self.clean_tree(root)
            for name in (".git", "_seed", "node_modules"):
                path = root / name
                path.mkdir()
                (path / "hidden.txt").write_text(sentinel())
            report = self.report(checker, root)
            self.assertTrue(report["ok"])
            self.assertEqual(report["files_checked"], 1)
            self.assertEqual(report["exclusions"], [".git/", "_seed/", "node_modules/"])

    def boundary_attack(self, name):
        checker = self.checker()
        with self.temporary() as root:
            report = self.leak(checker, root, sentinel(), name=name)
            self.assertFalse(report["ok"])

    def test_a22_root_git_file_is_scanned(self):
        self.boundary_attack(".git")

    def test_a22_root_git_symlink_is_unsafe(self):
        checker = self.checker()
        with self.temporary() as root, self.temporary() as outside:
            (root / ".git").symlink_to(outside, target_is_directory=True)
            report = self.report(checker, root)
            self.assertFalse(report["ok"])
            self.assertIn("unsafe_link", {f["code"] for f in report["findings"]})

    def test_a22_dependency_symlink_exclusion_does_not_open_target(self):
        checker = self.checker()
        with self.temporary() as root, self.temporary() as outside:
            (outside / "secret.txt").write_text(sentinel())
            (root / "node_modules").symlink_to(outside, target_is_directory=True)
            self.clean_tree(root)
            self.assertTrue(self.report(checker, root)["ok"])

    def test_a23_absent_and_nondirectory_roots_fail(self):
        checker = self.checker()
        with self.temporary() as root:
            file = root / "file.txt"
            file.write_text("Public content.")
            for invalid in (root / "missing", file):
                report = self.report(checker, invalid)
                self.assertFalse(report["ok"])
                self.assertTrue(report["findings"])

    def test_a24_raw_locations_and_safe_reproducible_sorted_diagnostics(self):
        checker = self.checker()
        with self.temporary() as root:
            content = "\u03bb\n" + sentinel() + "\n"
            self.leak(checker, root, content, name="z.txt")
            self.leak(checker, root, sentinel(), name="a.txt")
            before = tree_state(root)
            left, right = self.report(checker, root), self.report(checker, root)
            self.assertEqual(left, right)
            self.assertEqual(tree_state(root), before)
            hits = [f for f in left["findings"] if f["path"] == "z.txt" and f["code"] == "scrub_token"]
            self.assertTrue(hits)
            self.assertEqual(hits[0]["line"], 2)
            self.assertEqual(hits[0]["byte_offset"], len("\u03bb\n".encode()))
            keys = [(f["path"] or "", -1 if f["byte_offset"] is None else f["byte_offset"], f["rule_id"])
                    for f in left["findings"]]
            self.assertEqual(keys, sorted(keys))

    def test_a24_hostile_filename_redaction_keeps_a_stable_digest(self):
        checker = self.checker()
        with self.temporary() as root:
            name = sentinel() + ".txt"
            report = self.leak(checker, root, "A public sentence.\n", name=name)
            self.assertTrue(any(sha(name.encode()) in finding["rule_id"] for finding in report["findings"]))
            self.assertEqual(report, self.report(checker, root))

    def test_a25_cli_clean_and_forbidden_exit_mapping(self):
        self.required("tools/publish_check.py")
        with self.temporary() as root:
            self.clean_tree(root)
            command = [sys.executable, "-B", str(ROOT / "tools/publish_check.py"), "--root", str(root)]
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            clean = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, timeout=2)
            self.assertEqual(clean.returncode, 0)
            self.assertIs(json.loads(clean.stdout)["ok"], True)
            self.assertEqual(clean.stderr, b"")
            (root / "bad.txt").write_text(sentinel())
            bad = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, timeout=2)
            self.assertEqual(bad.returncode, 3)
            self.assertIs(json.loads(bad.stdout)["ok"], False)
            self.assertNotIn(sentinel(), bad.stdout.decode() + bad.stderr.decode())
            self.assertNotIn(str(root), bad.stdout.decode() + bad.stderr.decode())

    def cli_bad_args(self, args):
        checker = self.checker()
        with self.temporary() as root:
            stdout, stderr = io.StringIO(), io.StringIO()
            before = tree_state(root)
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    code = checker.main(args)
                except SystemExit as exc:
                    code = exc.code
            self.assertEqual(code, 2)
            streams = [stream for stream in (stdout.getvalue(), stderr.getvalue()) if stream.strip()]
            objects = []
            for stream in streams:
                try:
                    objects.append(json.loads(stream))
                except ValueError:
                    continue
            self.assertEqual(len(objects), 1, "Usage failure requires one minimal JSON error")
            self.assertEqual(objects[0].get("code"), "bad_args")
            self.assertNotIn("untrusted", objects[0])
            self.assertEqual(tree_state(root), before)

    def test_a26_complete_public_tree_scans_itself(self):
        checker = self.checker()
        # Test traversal semantics independently of other units' amended corpus bytes.
        with self.temporary() as root:
            self.clean_tree(root)
            paths = [root / directory / "nested/fixture.txt"
                     for directory in ("lineage", "tests", "docs", "references", "tools", "ui")]
            for path in paths:
                path.parent.mkdir(parents=True)
                path.write_text("Portable public fixture.\n", encoding="utf-8")
            report = self.report(checker, root)
            self.assertTrue(report["ok"], "No source or test exemption may hide a public-tree leak")
            self.assertGreater(report["files_checked"], 0)
            self.assertEqual(report["files_checked"], len(paths) + 1)
            self.assertLessEqual(set(report["exclusions"]), {".git/", "_seed/", "node_modules/"})
            for path in paths:
                with self.subTest(path=path.relative_to(root).as_posix()):
                    report = self.leak(checker, root, sentinel(),
                                       name=path.relative_to(root).as_posix())
                    self.assertIn(path.relative_to(root).as_posix(),
                                  {finding["path"] for finding in report["findings"]})
                    path.write_text("Portable public fixture.\n", encoding="utf-8")
            self.assertTrue(self.report(checker, root)["ok"])

    def policy_attack(self, kind):
        checker_source = self.required("tools/publish_check.py")
        policy_source = self.required("references/publication_policy.json")
        with self.temporary() as installed, self.temporary() as scanned:
            (installed / "tools").mkdir()
            (installed / "references").mkdir()
            copied = installed / "tools/publish_check.py"
            shutil.copyfile(checker_source, copied)
            policy_path = installed / "references/publication_policy.json"
            data = json.loads(policy_source.read_bytes())
            if kind == "missing":
                pass
            else:
                if kind == "remove_entry":
                    data["fingerprints"].pop()
                elif kind == "wrong_chars":
                    data["fingerprints"][0]["segments"][0]["chars"] += 1
                elif kind == "wrong_hash":
                    data["fingerprints"][0]["segments"][0]["sha256"] = "0" * 64
                elif kind == "broaden_exception":
                    data["public_path_exceptions"].append({"fingerprint_id": "test-sentinel", "path": ".", "reason": "all"})
                policy_path.write_bytes(canonical(data) + b"\n")
            spec = importlib.util.spec_from_file_location("_u07_checker_copy", copied)
            module = importlib.util.module_from_spec(spec)
            with mock.patch.dict(sys.modules, {spec.name: module}):
                try:
                    spec.loader.exec_module(module)
                except Exception:
                    self.fail("Policy failure must be represented by a failing scan report")
                self.clean_tree(scanned)
                report = self.report(module, scanned)
                self.assertFalse(report["ok"])
                self.assertIn("invalid_policy", {f["code"] for f in report["findings"]})


def _parameter(method, value):
    def test(self):
        getattr(self, method)(value)
    return test


for _kind in ("posix", "windows", "unc", "hostname_config", "authority", "secret"):
    setattr(PublicationOracle, "test_a19_" + _kind, _parameter("leak_kind", _kind))
for _kind in ("filename", "casefold", "unicode_nfd", "escaped_json", "escaped_python", "binary_prefix", "large_file", "buffer_edges"):
    setattr(PublicationOracle, "test_a20_a23_sentinel_" + _kind, _parameter("sentinel_variant", _kind))
for _index, _name in enumerate(("nested/node_modules/bad.txt", "nested/_seed/bad.txt", "nested/.git/bad.txt",
                              "node_modules-old/bad.txt", "_seed-old/bad.txt", ".git-old/bad.txt",
                              ".hidden", "tests/test_sample.py", "docs/guide.md", "references/sample.md")):
    setattr(PublicationOracle, "test_a22_unexcluded_boundary_" + str(_index), _parameter("boundary_attack", _name))
for _index, _args in enumerate(([], ["--unknown"], ["--root", ".", "--ignore", "tests"],
                              ["--root", ".", "--allow-missing"], ["--root", ".", "--update-pins"],
                              ["--root", ".", "--report-file", "report.json"],
                              ["--root", ".", "--policy", "other.json"], ["--root"])):
    setattr(PublicationOracle, "test_a25_reject_weakening_or_bad_invocation_" + str(_index), _parameter("cli_bad_args", _args))
for _kind in ("missing", "remove_entry", "wrong_chars", "wrong_hash", "broaden_exception"):
    setattr(PublicationOracle, "test_a18_policy_tamper_" + _kind, _parameter("policy_attack", _kind))
for _index, _path in enumerate(("README.md", "tests/sample.py", "tools/publish_check.py", "docs/guide.md",
                              ".hidden", "references/gold_s1/sample.json")):
    setattr(PublicationOracle, "test_a26_seeded_content_class_" + str(_index), _parameter("boundary_attack", _path))

# A boundary name with file type does not inherit the directory/link exclusion.
setattr(PublicationOracle, "test_a22_root_seed_file_is_scanned", _parameter("boundary_attack", "_seed"))
setattr(PublicationOracle, "test_a22_root_dependency_file_is_scanned", _parameter("boundary_attack", "node_modules"))
