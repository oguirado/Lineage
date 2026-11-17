"""A9/A14/A21/A23: result publication observed through public APIs and OS calls."""

import json
import os
import stat
from unittest.mock import patch

from lineage.core import family
from tests.core.family import RuntimeCase, request, wire


class PublicationTests(RuntimeCase):
    def result_path(self, identity="request01"):
        paths = list(self.endpoint.rglob(identity + ".result.json"))
        self.assertEqual(len(paths), 1)
        return paths[0]

    def test_a23_publish_canonical_receipt(self):
        box = self.mailbox()
        result = {"untrusted": {"skills": []}}
        box.publish("request01", result, request(correlation_id="corr0001"))
        path = self.result_path()
        value = json.loads(path.read_bytes())
        self.assertEqual(value, {"schema": "lineage.family/1", "id": "request01",
                                 "result": result, "correlation_id": "corr0001"})
        self.assert_receipt(value)
        self.assertEqual(path.read_bytes(), wire(value) + b"\n")

    def test_a23_no_envelope_does_not_synthesize_correlation(self):
        box = self.mailbox()
        box.publish("request01", {"untrusted": {"skills": []}})
        value = json.loads(self.result_path().read_bytes())
        self.assertNotIn("correlation_id", value)
        self.assertEqual(value["id"], "request01")
        self.assert_receipt(value)

    def test_a23_file_fsync_rename_directory_fsync(self):
        box = self.mailbox()
        events = []
        original_fsync, original_rename, original_replace = os.fsync, os.rename, os.replace
        def observe():
            for path in self.endpoint.rglob("request01.result.json"):
                raw = path.read_bytes()
                value = json.loads(raw)
                self.assertEqual(raw, wire(value) + b"\n")
                self.assert_receipt(value)
        def sync(fd):
            mode = os.fstat(fd).st_mode
            events.append("directory_fsync" if stat.S_ISDIR(mode) else "file_fsync")
            observe()
            return original_fsync(fd)
        def rename(src, dst, *args, **kwargs):
            events.append("rename")
            observe()
            answer = original_rename(src, dst, *args, **kwargs)
            observe()
            return answer
        def replace(src, dst, *args, **kwargs):
            events.append("rename")
            observe()
            answer = original_replace(src, dst, *args, **kwargs)
            observe()
            return answer
        with patch.object(os, "fsync", side_effect=sync), \
             patch.object(os, "rename", side_effect=rename), \
             patch.object(os, "replace", side_effect=replace):
            box.publish("request01", {"untrusted": {"skills": []}})
        self.assertIn("file_fsync", events)
        self.assertIn("rename", events)
        self.assertIn("directory_fsync", events)
        self.assertLess(events.index("file_fsync"), events.index("rename"))
        self.assertIn("directory_fsync", events[events.index("rename") + 1:])

    def test_a14_replaced_result_destination_is_not_followed(self):
        box = self.mailbox()
        box.publish("request01", {"untrusted": {"skills": []}})
        path = self.result_path()
        outside = self.home / "outside.txt"
        outside.write_bytes(b"must survive")
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaises((family.UnsafeEntry, family.RecoveryError, family.Refusal, OSError)):
            box.publish("request01", {"untrusted": {"skills": []}})
        self.assertTrue(path.is_symlink())
        self.assertEqual(outside.read_bytes(), b"must survive")

    def test_a21_file_fsync_failure_allows_publication_retry(self):
        box = self.mailbox()
        original = os.fsync
        def fail_file(fd):
            if stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError("injected fsync failure")
            return original(fd)
        with patch.object(os, "fsync", side_effect=fail_file):
            with self.assertRaises((OSError, family.RecoveryError)):
                box.publish("request01", {"untrusted": {"skills": []}})
        self.assertEqual(list(self.endpoint.rglob("request01.result.json")), [])
        box.publish("request01", {"untrusted": {"skills": []}})
        self.assert_receipt(json.loads(self.result_path().read_bytes()))

    def test_a21_rename_failure_allows_publication_retry(self):
        box = self.mailbox()
        with patch.object(os, "rename", side_effect=OSError("injected rename failure")), \
             patch.object(os, "replace", side_effect=OSError("injected rename failure")):
            with self.assertRaises((OSError, family.RecoveryError)):
                box.publish("request01", {"untrusted": {"skills": []}})
        self.assertEqual(list(self.endpoint.rglob("request01.result.json")), [])
        box.publish("request01", {"untrusted": {"skills": []}})
        self.assert_receipt(json.loads(self.result_path().read_bytes()))

    def test_a14_destination_swap_at_file_fsync(self):
        box = self.mailbox()
        result = {"untrusted": {"skills": []}}
        box.publish("request01", result)
        path = self.result_path()
        outside = self.home / "protected.txt"
        outside.write_bytes(b"protected")
        swapped = False
        original = os.fsync
        def swap(fd):
            nonlocal swapped
            if not swapped and stat.S_ISREG(os.fstat(fd).st_mode):
                path.unlink()
                path.symlink_to(outside)
                swapped = True
            return original(fd)
        with patch.object(os, "fsync", side_effect=swap):
            try:
                box.publish("request01", result)
            except (family.UnsafeEntry, family.RecoveryError, family.Refusal, OSError):
                pass
        self.assertTrue(swapped, "publication never reached the file-fsync barrier")
        self.assertTrue(path.is_symlink(), "a replaced unsafe destination was overwritten")
        self.assertEqual(outside.read_bytes(), b"protected")

    def test_a9_invalid_backend_result_cannot_be_published(self):
        box = self.mailbox()
        try:
            box.publish("request01", {"untrusted": {"arbitrary": "invalid"}})
        except (family.RecoveryError, family.UnsafeEntry, ValueError):
            self.assertEqual(list(self.endpoint.rglob("request01.result.json")), [])
        else:
            value = json.loads(self.result_path().read_bytes())
            self.assert_receipt(value)
            self.assert_error(value["result"], "internal")
