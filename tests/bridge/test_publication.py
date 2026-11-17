"""A7/A9/A12/A15: safe refusals; successful wire binding remains blocked."""
import os
from pathlib import Path
from unittest import mock

from lineage.bridge import openfresnel as bridge
from lineage.core.errors import LineageError
from tests.bridge._support import BridgeCase, RID, canonical, image, install_cases


class PublicationSafetyOracle(BridgeCase):
    def refused(self, operation, *args, **kwargs):
        """M7/M9 allow a safe conflict or an explicit uncertainty refusal."""
        try:
            self.invoke(operation, *args, **kwargs)
        except LineageError as exc:
            self.assertIn(exc.code, ('internal', 'conflict', 'bad_op'))
            return
        self.fail('unsafe existing entry was accepted as an acknowledgement')

    def test_a07_directory_swap_before_open_cannot_follow_link(self):
        real_open = os.open
        displaced = self.base / 'displaced'
        fired = []
        def swap(path, flags, *args, **kwargs):
            if not fired and Path(os.fspath(path)).name == self.channel.name:
                fired.append(True)
                self.channel.rename(displaced)
                self.channel.symlink_to(self.other, target_is_directory=True)
            return real_open(path, flags, *args, **kwargs)
        before = image(self.other)
        with mock.patch.object(os, 'open', side_effect=swap):
            self.error('bad_args', bridge.commands_dir, commands_dir=str(self.channel))
        self.assertTrue(fired, 'configuration never reached required descriptor-safe open')
        self.assertEqual(image(self.other), before)
        self.assertEqual(list(displaced.iterdir()), [])

    def test_a15_directory_swap_after_open_is_not_used_for_publication(self):
        real_open = os.open
        displaced = self.base / 'displaced'
        fired = []
        def swap(path, flags, *args, **kwargs):
            fd = real_open(path, flags, *args, **kwargs)
            if not fired and Path(os.fspath(path)).name == self.channel.name and flags & os.O_DIRECTORY:
                fired.append(True)
                self.channel.rename(displaced)
                self.channel.symlink_to(self.other, target_is_directory=True)
            return fd
        before = image(self.other)
        command = self.command(commands_dir=str(self.channel), timeout_ms=5)
        with mock.patch.object(os, 'open', side_effect=swap), self.clock.installed():
            try:
                self.invoke(bridge.probe, commands_dir=str(self.channel), timeout_ms=5, command=command, ctx=self.ctx)
            except LineageError as exc:
                self.assertIn(exc.code, ('internal', 'bad_args', 'conflict'))
            else:
                self.fail('descriptor replacement produced availability')
        self.assertTrue(fired, 'required directory descriptor was not opened')
        self.assertEqual(image(self.other), before)
        self.assertEqual(list(displaced.iterdir()), [], 'publication used a detached selected directory')

    def test_a09_identity_binding_is_checked_before_any_directory_open(self):
        from dataclasses import replace
        command = self.command(commands_dir=str(self.channel))
        with mock.patch.object(os, 'open', side_effect=AssertionError('effect before actor validation')):
            self.error('bad_args', bridge.probe, commands_dir=str(self.channel),
                       command=command, ctx=replace(self.ctx, actor='other-agent'))


def unsafe_entry(self, kind):
    suffix, entry_type = kind
    target = self.base / 'untouched'
    target.write_bytes(b'fixture-owned unrelated content')
    entry = self.channel / (RID + suffix)
    if entry_type == 'symlink':
        entry.symlink_to(target)
    elif entry_type == 'directory':
        entry.mkdir()
    elif entry_type == 'fifo':
        os.mkfifo(entry)
    else:
        entry.write_bytes(b'{"unrelated":true}')
    before = image(self.channel)
    command = self.command(commands_dir=str(self.channel), timeout_ms=5)
    real_open = os.open
    def no_blocking_fifo(path, flags, *args, **kwargs):
        if Path(os.fspath(path)).name == entry.name:
            if entry_type == 'fifo':
                self.assertTrue(flags & os.O_NONBLOCK, 'a blocking FIFO open violates the bounded refusal')
            if entry_type == 'symlink':
                self.assertTrue(flags & os.O_NOFOLLOW, 'an existing symlink was opened without O_NOFOLLOW')
        return real_open(path, flags, *args, **kwargs)
    with self.clock.installed(), mock.patch.object(os, 'open', side_effect=no_blocking_fifo):
        self.refused(bridge.probe, commands_dir=str(self.channel), timeout_ms=5,
                     command=command, ctx=self.ctx)
    self.assertEqual(target.read_bytes(), b'fixture-owned unrelated content')
    # Owned temporary cleanup is permitted; pre-existing entries are immutable.
    after = image(self.channel)
    for name, value in before.items():
        self.assertEqual(after.get(name), value, 'unrelated entry changed')
    self.assertNotIn(RID + '.tmp', set(after) - set(before))


install_cases(PublicationSafetyOracle, 'test_a12_existing_', {
    suffix_name + '_' + kind: (suffix, kind)
    for suffix_name, suffix in [('temporary', '.tmp'), ('command', '.json'), ('result', '.result.json')]
    for kind in ('symlink', 'directory', 'fifo', 'unrelated_regular')
}, unsafe_entry)


class FakeConsumerHarnessOracle(BridgeCase):
    def test_a13_a34_observer_rejects_partial_noncanonical_and_scalar_final(self):
        """Harness negative controls only; these are not receiver command fixtures."""
        import json
        from tests.bridge._support import FakeConsumer
        consumer = FakeConsumer(self.channel)
        final = self.channel / (RID + '.json')
        self.assertIsNone(consumer.observe())
        for raw in (b'{', b'{"fixture": 1}', b'[]', b'{"x":1,"x":2}'):
            final.write_bytes(raw)
            with self.assertRaises((AssertionError, json.JSONDecodeError)):
                consumer.observe()
        final.write_bytes(canonical({'fixture': 'complete'}))
        self.assertEqual(consumer.observe(), {'fixture': 'complete'})
        self.assertEqual(consumer.observe(), {'fixture': 'complete'})
        self.assertEqual(len(consumer.seen), 1)
