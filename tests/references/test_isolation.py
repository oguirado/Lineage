"""Read confinement, nonblocking opens, deterministic failures and oracle controls."""
import builtins
import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import socket
import stat
import sys
from types import SimpleNamespace
from unittest import mock

from . import (OracleCase, ROOT, PUBLIC_IDS, canonical, sha, sentinel, tree_state)


class IsolationOracle(OracleCase):
    @contextlib.contextmanager
    def forbid_execution(self):
        with contextlib.ExitStack() as stack:
            for target in ("socket.socket", "socket.create_connection", "subprocess.Popen", "os.system"):
                stack.enter_context(mock.patch(target, side_effect=AssertionError("Read attempted external execution")))
            yield

    @contextlib.contextmanager
    def observe_opens(self, forbidden=None, deny_name=None, flags_required=False):
        real_os, real_builtin, real_io = os.open, builtins.open, io.open
        calls = []

        def check(path, mode):
            if isinstance(path, int):
                return
            candidate = Path(os.fsdecode(path))
            if forbidden is not None:
                self.assertNotEqual(candidate.resolve(), forbidden.resolve(), "External target was opened")
            if deny_name is not None and candidate.name == deny_name:
                raise PermissionError("Synthetic read refusal")
            if candidate.exists() and not candidate.is_dir():
                self.assertTrue(stat.S_ISREG(candidate.lstat().st_mode), "Nonregular file reached a blocking open")
            if isinstance(mode, str):
                self.assertFalse(any(c in mode for c in "wax+"), "Read operation attempted a write")

        def low_open(path, flags, *args, **kwargs):
            if forbidden is not None and not isinstance(path, int):
                candidate = Path(os.fsdecode(path))
                self.assertNotEqual(candidate.resolve(), forbidden.resolve(), "External target was opened")
            if deny_name is not None and Path(os.fsdecode(path)).name == deny_name:
                raise PermissionError("Synthetic read refusal")
            writing = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
            self.assertEqual(flags & writing, 0, "Read operation attempted a write")
            if flags_required and not flags & getattr(os, "O_DIRECTORY", 0):
                for flag in (getattr(os, "O_NOFOLLOW", 0), getattr(os, "O_NONBLOCK", 0)):
                    self.assertEqual(flags & flag, flag, "File open lacks required anti-race/nonblocking flag")
            calls.append((os.fsdecode(path), flags))
            return real_os(path, flags, *args, **kwargs)

        def high_open(original):
            def wrapped(path, mode="r", *args, **kwargs):
                check(path, mode)
                if flags_required and not isinstance(path, int) and not callable(kwargs.get("opener")):
                    # A file-object facade may safely wrap an already opened descriptor.
                    self.fail("File read bypassed descriptor-safe os.open")
                return original(path, mode, *args, **kwargs)
            return wrapped

        with mock.patch("os.open", side_effect=low_open), \
             mock.patch("builtins.open", side_effect=high_open(real_builtin)), \
             mock.patch("io.open", side_effect=high_open(real_io)):
            yield calls

    def test_a17_default_root_ignores_cwd_and_runtime_environment(self):
        module = self.domain()
        expected = {key: self.get(module, key) for key in PUBLIC_IDS}
        with self.temporary() as unrelated:
            previous = Path.cwd()
            try:
                os.chdir(unrelated)
                with mock.patch.dict(os.environ, {"LINEAGE_HOME": str(unrelated), "HOME": str(unrelated)}):
                    self.assertEqual({key: self.get(module, key) for key in PUBLIC_IDS}, expected)
            finally:
                os.chdir(previous)

    def test_a17_normal_reads_and_scans_are_silent_without_network_or_processes(self):
        module, checker = self.domain(), self.checker()
        with self.reference_copy() as root:
            before = tree_state(root)
            stdout, stderr = io.StringIO(), io.StringIO()
            with self.forbid_execution(), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                for ref_id in PUBLIC_IDS:
                    self.get(module, ref_id, root)
                    self.verify(module, ref_id, root)
                self.report(checker, root)
            self.assertEqual(tree_state(root), before)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")

    def test_a17_extension_import_is_read_only_and_silent(self):
        self.required("lineage/ext/references.py")
        stdout, stderr = io.StringIO(), io.StringIO()
        with self.temporary() as home:
            before = tree_state(home)
            with mock.patch.dict(os.environ, {"LINEAGE_HOME": str(home)}), self.forbid_execution(), \
                 self.observe_opens(), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                previous = sys.modules.pop("lineage.ext.references", None)
                try:
                    self.module("lineage.ext.references")
                finally:
                    if previous is not None:
                        sys.modules["lineage.ext.references"] = previous
            self.assertEqual(tree_state(home), before)
            self.assertEqual(stdout.getvalue() + stderr.getvalue(), "")

    def test_a13_reference_files_require_nofollow_nonblock_and_regular_descriptors(self):
        module = self.domain()
        with self.reference_copy() as root:
            with self.observe_opens(flags_required=True) as calls:
                self.get(module, "gold_s1", root)
            self.assertTrue(calls, "No descriptor-safe artifact reads were observed")

    def test_a22_scanner_requires_nofollow_nonblock_and_regular_descriptors(self):
        checker = self.checker()
        with self.temporary() as root:
            (root / "public.txt").write_text("Public content.\n")
            with self.observe_opens(flags_required=True) as calls:
                report = self.report(checker, root)
            self.assertTrue(report["ok"])
            self.assertTrue(calls)

    def reference_link(self, directory=False):
        module = self.domain()
        with self.reference_copy() as root, self.temporary() as outside:
            if directory:
                target = root / "references/gold_s1"
                saved = root / "saved"
                target.rename(saved)
                external = outside / "gold_s1"
                external.mkdir()
                (external / "gold_rules.json").write_text("External content.")
                target.symlink_to(external, target_is_directory=True)
                forbidden = external / "gold_rules.json"
            else:
                target = root / "references/gold_s1/gold_rules.json"
                target.unlink()
                forbidden = outside / "outside.json"
                forbidden.write_text("External content.")
                target.symlink_to(forbidden)
            before = tree_state(outside)
            with self.observe_opens(forbidden=forbidden):
                self.rejected_package(module, root)
            self.assertEqual(tree_state(outside), before)

    def test_a13_reference_symlink_file_never_opens_external_target(self):
        self.reference_link()

    def test_a13_reference_symlink_directory_never_opens_external_target(self):
        self.reference_link(directory=True)

    def test_a22_scanned_symlink_file_and_directory_are_not_followed(self):
        checker = self.checker()
        with self.temporary() as root, self.temporary() as outside:
            forbidden = outside / "external.txt"
            forbidden.write_text(sentinel())
            (root / "link.txt").symlink_to(forbidden)
            (root / "linked-dir").symlink_to(outside, target_is_directory=True)
            with self.observe_opens(forbidden=forbidden):
                report = self.report(checker, root)
            self.assertFalse(report["ok"])
            self.assertIn("unsafe_link", {f["code"] for f in report["findings"]})

    def test_a13_reference_fifo_is_rejected_without_a_blocking_open(self):
        module = self.domain()
        with self.reference_copy() as root:
            path = root / "references/gold_s1/gold_rules.json"
            path.unlink()
            os.mkfifo(path)
            # A-U07: Keep fixture snapshots outside the SUT-only descriptor observer.
            before = tree_state(root)
            with self.observe_opens(flags_required=True):
                for name in ("reference_get", "reference_verify"):
                    self.reject(self.function(module, name), "hash_mismatch",
                                "gold_s1", repo_root=root)
            self.assertEqual(tree_state(root), before, "Integrity failures must not repair or cache")

    def test_a22_scanned_fifo_is_rejected_without_a_blocking_open(self):
        checker = self.checker()
        with self.temporary() as root:
            os.mkfifo(root / "pipe")
            with self.observe_opens(flags_required=True):
                report = self.report(checker, root)
            self.assertFalse(report["ok"])
            self.assertIn("unsafe_link", {f["code"] for f in report["findings"]})

    def test_a13_symlink_swap_between_check_and_open_is_rejected(self):
        module = self.domain()
        with self.reference_copy() as root, self.temporary() as outside:
            path = root / "references/gold_s1/gold_rules.json"
            external = outside / "outside.json"
            external.write_text("External content.")
            real_open = os.open
            swapped = []

            def racing_open(name, flags, *args, **kwargs):
                if Path(os.fsdecode(name)).name == path.name and not swapped:
                    path.unlink()
                    path.symlink_to(external)
                    swapped.append(True)
                    self.assertTrue(flags & os.O_NOFOLLOW)
                    self.assertTrue(flags & os.O_NONBLOCK)
                return real_open(name, flags, *args, **kwargs)

            with mock.patch("os.open", side_effect=racing_open):
                self.reject(self.function(module, "reference_get"), "hash_mismatch", "gold_s1", repo_root=root)
            self.assertTrue(swapped, "Hostile swap did not reach the file-open boundary")

    def test_a27_reference_read_refusal_is_internal_and_never_repairs(self):
        module = self.domain()
        with self.reference_copy() as root:
            before = tree_state(root)
            with self.observe_opens(deny_name="gold_rules.json"):
                for name in ("reference_get", "reference_verify"):
                    self.reject(self.function(module, name), "internal", "gold_s1", repo_root=root)
            self.assertEqual(tree_state(root), before)

    def test_a23_a27_scanner_read_refusal_keeps_unknown_coordinates_null(self):
        checker = self.checker()
        with self.temporary() as root:
            (root / "unreadable.txt").write_text("Public content.\n")
            (root / "a-public.txt").write_text("Public content.\n")
            before = tree_state(root)
            with self.observe_opens(deny_name="unreadable.txt"):
                report = self.report(checker, root)
            self.assertFalse(report["ok"])
            self.assertEqual(report["files_checked"], 1, "Completed reads must survive a later refusal")
            findings = [f for f in report["findings"] if f["code"] == "unreadable"]
            self.assertTrue(findings)
            for finding in findings:
                self.assertIsNone(finding["line"])
                self.assertIsNone(finding["byte_offset"])
            self.assertEqual(tree_state(root), before)

    def test_a23_traversal_error_is_not_a_clean_empty_tree(self):
        checker = self.checker()
        with self.temporary() as root:
            def denied(*args, **kwargs):
                raise PermissionError("Synthetic traversal refusal")

            with mock.patch("os.scandir", side_effect=denied), mock.patch("os.listdir", side_effect=denied):
                report = self.report(checker, root)
            self.assertFalse(report["ok"])
            self.assertIn("unreadable", {f["code"] for f in report["findings"]})

    def test_a27_argument_errors_remain_distinct_from_integrity_failures(self):
        module = self.domain()
        for name in ("reference_get", "reference_verify"):
            self.reject(self.function(module, name), "bad_args", "unknown")
        for invalid in (True, 1, "A" * 64, "f" * 63):
            self.reject(self.function(module, "reference_verify"), "bad_args", "gold_s1", expected_sha256=invalid)

    def test_a28_wrong_data_and_always_clean_in_memory_controls_fail_assertions(self):
        checker = self.checker()
        with self.temporary() as root:
            wrong = SimpleNamespace(scan_tree=lambda unused: {
                "schema": "lineage.publish-check/v1", "ok": True, "files_checked": 1,
                "exclusions": [], "findings": []})
            with self.assertRaises(AssertionError):
                self.leak(wrong, root, sentinel())
            # The unchanged real oracle then demands that the actual detector rejects it.
            self.assertFalse(self.report(checker, root)["ok"])

    def test_a17_reads_do_not_open_the_unselected_reference(self):
        module = self.domain()
        with self.reference_copy() as root:
            with self.observe_opens(deny_name="REFERENCE.md"):
                self.get(module, "gold_s1", root)
                self.verify(module, "gold_s1", root)
            with self.observe_opens(deny_name="gold_rules.json"):
                self.get(module, "memory_v21", root)
                self.verify(module, "memory_v21", root)

    def test_a17_reads_do_not_create_even_transient_files_or_journal_events(self):
        module, checker = self.domain(), self.checker()
        with self.reference_copy() as root:
            before = tree_state(root)
            with contextlib.ExitStack() as stack:
                for name in ("mkdir", "makedirs", "rename", "replace", "unlink", "remove", "symlink"):
                    stack.enter_context(mock.patch("os." + name,
                                                   side_effect=AssertionError("Read attempted filesystem mutation")))
                stack.enter_context(self.observe_opens())
                self.get(module, "gold_s1", root)
                self.verify(module, "gold_s1", root)
                self.report(checker, root)
            self.assertEqual(tree_state(root), before)

    def test_a13_fstat_nonregular_descriptor_is_rejected_before_data_use(self):
        module = self.domain()
        with self.reference_copy() as root:
            real_fstat = os.fstat
            observed = []

            def nonregular(fd):
                value = real_fstat(fd)
                if stat.S_ISREG(value.st_mode):
                    changed = list(value)
                    changed[0] = stat.S_IFIFO | stat.S_IMODE(value.st_mode)
                    observed.append(fd)
                    return os.stat_result(changed)
                return value

            with mock.patch("os.fstat", side_effect=nonregular):
                self.reject(self.function(module, "reference_get"), "hash_mismatch", "gold_s1", repo_root=root)
            self.assertTrue(observed, "Regularity must be checked on the actual open descriptor")

    def test_a22_scanner_fstat_nonregular_descriptor_cannot_pass(self):
        checker = self.checker()
        with self.temporary() as root:
            (root / "public.txt").write_text("Public content.\n")
            real_fstat = os.fstat
            observed = []

            def nonregular(fd):
                value = real_fstat(fd)
                if stat.S_ISREG(value.st_mode):
                    changed = list(value)
                    changed[0] = stat.S_IFIFO | stat.S_IMODE(value.st_mode)
                    observed.append(fd)
                    return os.stat_result(changed)
                return value

            with mock.patch("os.fstat", side_effect=nonregular):
                report = self.report(checker, root)
            self.assertFalse(report["ok"])
            self.assertTrue(observed, "Regularity must be checked on the actual open descriptor")

    def catalog_escape(self, absolute):
        module = self.domain()
        with self.reference_copy() as root, self.temporary() as outside:
            external = outside / "external.json"
            external.write_bytes((root / "references/gold_s1/gold_rules.json").read_bytes())
            path = root / "references/catalog.json"
            catalog = json.loads(path.read_bytes())
            gold = next(item for item in catalog["references"] if item["ref_id"] == "gold_s1")
            gold["files"][0]["path"] = str(external) if absolute else os.path.relpath(external, root)
            gold["sha256"] = sha(canonical({key: value for key, value in gold.items() if key != "sha256"}))
            path.write_bytes(canonical(catalog) + b"\n")
            admitted = sorted(p for p in (root / "references").rglob("*")
                              if p.is_file() and p.name != "MANIFEST.sha256")
            manifest = "".join(sha(p.read_bytes()) + "  " + p.relative_to(root).as_posix() + "\n"
                               for p in admitted)
            (root / "references/MANIFEST.sha256").write_text(manifest)
            self.assertTrue(hasattr(module, "REFERENCE_PINS"))
            pins = dict(module.REFERENCE_PINS, gold_s1=gold["sha256"])
            with mock.patch.object(module, "REFERENCE_PINS", pins), self.observe_opens(forbidden=external):
                self.rejected_package(module, root)

    def test_a13_trusted_fixture_pin_cannot_admit_relative_path_escape(self):
        self.catalog_escape(absolute=False)

    def test_a13_trusted_fixture_pin_cannot_admit_absolute_path_escape(self):
        self.catalog_escape(absolute=True)

    def test_a22_symlinked_scan_root_is_not_followed(self):
        checker = self.checker()
        with self.temporary() as root, self.temporary() as outside:
            external = outside / "external.txt"
            external.write_text(sentinel())
            linked = root / "linked"
            linked.symlink_to(outside, target_is_directory=True)
            with self.observe_opens(forbidden=external):
                report = self.report(checker, linked)
            self.assertFalse(report["ok"])
            self.assertIn("unsafe_link", {item["code"] for item in report["findings"]})
