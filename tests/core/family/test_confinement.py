"""A4/A6/A13: startup safety and live configuration checks."""

import os
from unittest.mock import patch
from lineage.core import family
from tests.core.family import RuntimeCase, config, request


class ConfinementTests(RuntimeCase):
    def refused_open(self):
        box = family.Mailbox("Endpoint_1", ctx=self.ctx)
        self.addCleanup(box.release)
        with self.assertRaises(family.Refusal):
            box.open()
        self.assertEqual(self.extension.SEEN, [])

    def test_a4_missing_config_not_manufactured(self):
        (self.endpoint / "config.json").unlink()
        self.refused_open()
        self.assertFalse((self.endpoint / "config.json").exists())

    def test_a13_symlinked_config(self):
        path = self.endpoint / "config.json"
        outside = self.home / "outside.json"
        path.rename(outside)
        original = outside.read_bytes()
        path.symlink_to(outside)
        self.refused_open()
        self.assertEqual(outside.read_bytes(), original)

    def test_a13_symlinked_endpoint(self):
        outside = self.home / "outside"
        self.endpoint.rename(outside)
        original = (outside / "config.json").read_bytes()
        self.endpoint.symlink_to(outside, target_is_directory=True)
        self.refused_open()
        self.assertEqual((outside / "config.json").read_bytes(), original)
        self.assertFalse((outside / "consumer.lock").exists())

    def test_a13_hardlinked_config(self):
        path = self.endpoint / "config.json"
        original = path.read_bytes()
        os.link(path, self.home / "other.json")
        self.refused_open()
        self.assertEqual(path.read_bytes(), original)

    def test_a13_symlinked_lock(self):
        outside = self.home / "outside.lock"
        outside.write_bytes(b"unchanged")
        (self.endpoint / "consumer.lock").symlink_to(outside)
        self.refused_open()
        self.assertEqual(outside.read_bytes(), b"unchanged")

    def test_a13_fifo_config_refused_without_open(self):
        path = self.endpoint / "config.json"
        path.unlink()
        os.mkfifo(path, 0o600)
        original = os.open
        def guarded(name, flags, *args, **kwargs):
            if os.fspath(name).endswith("config.json"):
                self.fail("FIFO config must be classified before open")
            return original(name, flags, *args, **kwargs)
        with patch.object(os, "open", side_effect=guarded):
            self.refused_open()

    def test_a6_live_config_corruption(self):
        box = self.mailbox()
        self.assertIn("untrusted", box.dispatch(request("call")))
        seen = len(self.extension.SEEN)
        (self.endpoint / "config.json").write_bytes(b'{"endpoint":')
        try:
            result = box.dispatch(request("call"))
        except family.Refusal:
            pass
        else:
            self.assert_error(result, "bad_args")
        self.assertEqual(len(self.extension.SEEN), seen)

    def test_a6_live_config_symlink(self):
        box = self.mailbox()
        self.assertIn("untrusted", box.dispatch(request("call")))
        seen = len(self.extension.SEEN)
        path = self.endpoint / "config.json"
        outside = self.home / "config.other"
        path.rename(outside)
        original = outside.read_bytes()
        path.symlink_to(outside)
        try:
            result = box.dispatch(request("call"))
        except (family.Refusal, family.UnsafeEntry):
            pass
        else:
            self.assert_error(result, "bad_args")
        self.assertEqual(outside.read_bytes(), original)
        self.assertEqual(len(self.extension.SEEN), seen)


for mode in (0o770, 0o777):
    def test(self, mode=mode):
        self.endpoint.chmod(mode)
        self.addCleanup(self.endpoint.chmod, 0o700)
        self.refused_open()
    setattr(ConfinementTests, "test_a13_untrusted_writable_" + oct(mode)[2:], test)
