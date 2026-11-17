"""A1-A2, A28-A29: import isolation, read-only paths and hostile authority nodes."""
import builtins
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch
from ._support import CoreCase, EVENT_PATH, LOCK_PATH


class IsolationTests(CoreCase):
    def test_a1_fresh_process_poisoned_planning_and_source_imports(self):
        script = """
import builtins, json, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'bridge', 'tasklight', '_seed'} or 'plan' in name.split('.'):
        raise ImportError('Forbidden planning or source import')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from lineage.core import journal, locking, errors
value = journal.transact(sys.argv[1], agent='agent-one', op_id='isolated-request',
    kind='claim', payload={'value': 1}, validators={'claim': lambda h, e: None},
    clock=lambda: 1234, id_factory=lambda: 'e-0123456789abcdef')
assert value['lamport'] == 1
assert not any(name == 'bridge' or name.startswith('bridge.') for name in sys.modules)
"""
        root = Path(__file__).resolve().parents[3]
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(root))
        result = subprocess.run([sys.executable, "-B", "-c", script, str(self.home)],
                                cwd=root, env=environment, capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertEqual(result.stdout, b"")

    def test_a2_existing_events_without_lock_is_internal(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"")
        for operation in (self.journal.snapshot, self.journal.verify):
            self.rejects("internal", operation, self.home)
        self.assertFalse((self.home / LOCK_PATH).exists())

    def test_a2_lock_only_directory_is_missing_not_empty_success(self):
        lock = self.home / LOCK_PATH
        lock.parent.mkdir(parents=True)
        lock.touch()
        before = set(self.home.rglob("*"))
        self.assertEqual(self.journal.snapshot(self.home), ())
        report = self.journal.verify(self.home)
        self.assertIs(report["ok"], False)
        self.assertIs(report["exists"], False)
        self.assertEqual(report["errors"][0]["code"], "internal")
        self.assertEqual(set(self.home.rglob("*")), before)
        self.assertFalse(self.path.exists())

    def test_a2_authority_directory_and_permission_errors_are_not_empty(self):
        self.install()
        self.path.unlink()
        self.path.mkdir()
        for operation in (self.journal.snapshot, self.journal.verify):
            with self.assertRaises(self.error):
                operation(self.home)
        self.path.rmdir()
        self.path.touch()
        real_open = os.open
        sensitive = str(self.home / "sensitive")
        def opened(path, flags, *args, **kwargs):
            if Path(os.fsdecode(path)).name == "events.jsonl":
                raise PermissionError(sensitive)
            return real_open(path, flags, *args, **kwargs)
        with patch.object(os, "open", opened):
            for operation in (self.journal.snapshot, self.journal.verify):
                with self.assertRaises(self.error) as caught:
                    operation(self.home)
                self.assertEqual(caught.exception.code, "internal")
                self.assertNotIn(sensitive, json.dumps(caught.exception.as_dict()))

    def test_a28_evidence_content_is_only_read_by_injected_domain_validator(self):
        sentinel = self.home.parent / "sentinel"
        sentinel.write_text("unchanged", encoding="utf-8")
        original_open, original_os_open = builtins.open, os.open
        observed = []
        def forbidden_read(path, *args, **kwargs):
            if not isinstance(path, int) and Path(path).name == "sentinel":
                observed.append(True)
                raise AssertionError("Generic journal opened evidence content")
            return original_open(path, *args, **kwargs)
        def forbidden_os_read(path, *args, **kwargs):
            if Path(os.fsdecode(path)).name == "sentinel":
                observed.append(True)
                raise AssertionError("Generic journal opened evidence content")
            return original_os_open(path, *args, **kwargs)
        evidence = [{"path": "receipts/sentinel", "sha256": "a" * 64}]
        called = []
        def validator(history, value):
            called.append(value["evidence"])
        with patch.object(builtins, "open", forbidden_read), patch.object(os, "open", forbidden_os_read):
            self.tx(evidence=evidence, validators={"claim": validator})
        self.assertEqual(observed, [])
        self.assertEqual(called, [evidence])
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged")

    def test_a28_injected_validator_alone_certifies_receipt_content(self):
        from ._support import sha
        receipt = self.home / "receipts/receipt.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_bytes(b"synthetic receipt")
        def validator(history, candidate):
            for item in candidate["evidence"]:
                if sha((self.home / item["path"]).read_bytes()) != item["sha256"]:
                    raise self.error("hash_mismatch", "receipt content mismatch")
        evidence = [{"path": "receipts/receipt.json", "sha256": sha(receipt.read_bytes())}]
        self.tx(evidence=evidence, validators={"claim": validator})
        self.rejects("hash_mismatch", self.tx,
                     evidence=[{"path": "receipts/receipt.json", "sha256": "a" * 64}],
                     validators={"claim": validator})

    def test_a29_symlink_controlled_directories_and_files_never_touch_targets(self):
        original_home = self.home
        for index, node in enumerate(("ledger", "ledger/main", EVENT_PATH, LOCK_PATH)):
            self.home = original_home.parent / f"symlink-home-{index}"
            self.install()
            controlled = self.home / node
            external = original_home.parent / f"external-{index}"
            if controlled.is_dir():
                external.mkdir()
                sentinel = external / "sentinel"
                sentinel.write_bytes(b"do not change")
                shutil.rmtree(controlled)
                controlled.symlink_to(external, target_is_directory=True)
            else:
                sentinel = external
                sentinel.write_bytes(b"do not change")
                controlled.unlink()
                controlled.symlink_to(external)
            for action in ("snapshot", "verify", "call"):
                process, pipe = self.child(action)
                status, code = self.receive(pipe)
                self.assertEqual(status, "error", (status, code))
                self.assertIn(code, {"bad_args", "internal"})
                self.finished(process)
            self.assertEqual(sentinel.read_bytes(), b"do not change")
            self.assertTrue(controlled.is_symlink())

    def test_a29_fifo_and_directory_authority_are_rejected_without_hanging(self):
        original_home = self.home
        for index, node in enumerate((EVENT_PATH, LOCK_PATH)):
            for node_type in ("fifo", "directory"):
                self.home = original_home.parent / f"nonregular-{index}-{node_type}"
                self.install()
                controlled = self.home / node
                controlled.unlink()
                if node_type == "fifo":
                    os.mkfifo(controlled)
                else:
                    controlled.mkdir()
                for action in ("snapshot", "verify", "call"):
                    process, pipe = self.child(action)
                    status, code = self.receive(pipe, 0.7)
                    self.assertEqual(status, "error", (status, code))
                    self.assertIn(code, {"bad_args", "internal"})
                    self.finished(process, 0.1)

    def test_a29_node_swap_during_open_is_refused(self):
        self.install()
        sentinel = self.home.parent / "external-sentinel"
        sentinel.write_bytes(b"unchanged")
        real_open = os.open
        swapped = []
        def opened(path, flags, *args, **kwargs):
            if Path(os.fsdecode(path)).name == "events.jsonl" and not swapped:
                swapped.append(True)
                self.path.unlink()
                self.path.symlink_to(sentinel)
            return real_open(path, flags, *args, **kwargs)
        with patch.object(os, "open", opened):
            with self.assertRaises(self.error) as caught:
                self.tx()
        self.assertTrue(swapped, "Safe-open race fixture was not exercised")
        self.assertIn(caught.exception.code, {"bad_args", "internal"})
        self.assertEqual(sentinel.read_bytes(), b"unchanged")
