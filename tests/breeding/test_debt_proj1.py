"""Child projections recover missing bytes and preserve corrupt generations."""
import os
import stat
from copy import deepcopy
from unittest import mock

from lineage.core.errors import LineageError
from lineage.core.app import ToolError
from lineage.domain import agents, layout
from tests.breeding.one.helpers import OracleCase, canonical


class ProjectionDebtTests(OracleCase):
    def setUp(self):
        super().setUp()
        self.seed(self.parent, units=[self.unit()])
        self.parent_files = agents.refresh_projections('parent-one', ctx=self.ctx)
        self.parent_bytes = {p: p.read_bytes() for p in self.parent_files}
        self.first = self.breed()
        record = self.first['record']
        scope = dict(workflow=record['workflow'], language=record['language'], agent_id='child-one')
        self.directory = layout.agent_dir(self.home, **scope)
        self.memory = layout.memory_dir(self.home, **scope)
        self.paths = agents.refresh_projections('child-one', ctx=self.ctx)
        self.generation_files = tuple(p for p in self.paths if p.is_relative_to(self.memory / 'gen'))
        self.original = {p: p.read_bytes() for p in self.paths}
        self.raw = self.ledger_bytes()

    def assert_restored(self):
        # Gate: identical retained result, bytes and ledger; contrast: a new birth.
        replay = self.breed()
        self.assertEqual(canonical(replay), canonical(self.first))
        self.assertEqual(self.ledger_bytes(), self.raw)
        self.assertEqual({p: p.read_bytes() for p in self.paths}, self.original)
        self.assertEqual({p: p.read_bytes() for p in self.parent_files}, self.parent_bytes)
        report = self.public_call('ledger_verify', {})
        self.assertIn('untrusted', report, report)
        self.assertIs(report['untrusted']['valid'], True)

    def assert_unsafe(self, path):
        # Gate: exact relative coordinate; contrast: following or replacing it.
        with self.assertRaises(LineageError) as caught:
            agents.refresh_projections('child-one', ctx=self.ctx)
        self.assertIn(path.relative_to(self.home).as_posix(), caught.exception.detail)
        self.assertNotIn(str(self.home), caught.exception.detail)
        # The integrated breeding facade intentionally sanitizes error details.
        with self.assertRaises((LineageError, ToolError)):
            self.breed()
        self.assertEqual(self.ledger_bytes(), self.raw)

    def assert_corruption_refused(self, path):
        def disk_bytes():
            return {p: p.read_bytes() for p in self.directory.rglob('*') if p.is_file()}

        before = disk_bytes()
        with self.assertRaises(LineageError) as caught:
            agents.refresh_projections('child-one', ctx=self.ctx)
        self.assertEqual(caught.exception.code, 'hash_mismatch')
        self.assertIn(path.relative_to(self.home).as_posix(), caught.exception.detail)
        self.assertEqual(disk_bytes(), before)
        with self.assertRaises(LineageError) as caught:
            self.breed()
        self.assertEqual(caught.exception.code, 'hash_mismatch')
        self.assertEqual(disk_bytes(), before)
        self.assertEqual(self.ledger_bytes(), self.raw)

    def test_empty_generation_directories_rebuilt_byte_exactly(self):
        generations = sorted((self.memory / 'gen').iterdir())
        self.assertTrue(generations)
        for path in self.directory.rglob('*'):
            if path.is_file():
                path.unlink()
        for directory in generations:
            self.assertTrue(directory.is_dir())
            self.assertFalse(any(p.is_file() for p in directory.rglob('*')))
        self.assert_restored()
        self.assert_restored()

    def test_tampered_disposable_files_repaired_byte_exactly(self):
        for path in set(self.paths) - set(self.generation_files):
            path.write_bytes(b'tampered disposable projection\n')
        self.assertEqual(self.public_call('agent_get', {'agent_id': 'child-one'})
                         ['untrusted']['record'], self.first['record'])
        self.assert_restored()
        self.assert_restored()

    def test_bootcheck_passes_after_deleted_projection_recovery(self):
        from lineage.domain.memory import _snapshot_of, bootcheck
        from lineage.core import journal

        context = agents._memory_context(self.ctx)
        snapshot = _snapshot_of(journal.snapshot(self.home), context)
        observed = bootcheck.expected('child-one', snapshot=snapshot, ctx=context)
        for path in self.paths:
            path.unlink()
        self.assert_restored()
        report = bootcheck.check('child-one', observed, ctx=context)
        self.assertIs(report['passed'], True)
        self.assertEqual(report['code'], 'OK')
        self.assertEqual(self.ledger_bytes(), self.raw)

    def test_hardlinked_projection_files_refused_without_changing_target(self):
        sentinel = self.base / 'hardlink-target.txt'
        sentinel.write_bytes(b'protected shared inode\n')
        for path in self.paths:
            with self.subTest(path=path.relative_to(self.home).as_posix()):
                path.unlink()
                os.link(sentinel, path)
                try:
                    self.assert_unsafe(path)
                    self.assertTrue(path.samefile(sentinel))
                    self.assertEqual(sentinel.read_bytes(), b'protected shared inode\n')
                finally:
                    path.unlink()
                    path.write_bytes(self.original[path])
        self.assert_restored()

    def test_tampered_and_truncated_generation_files_refuse_without_writes(self):
        self.assertTrue(self.generation_files)
        for changed in (b'tampered generation\n', b''):
            for path in self.generation_files:
                with self.subTest(path=path.relative_to(self.home).as_posix(), changed=changed):
                    path.write_bytes(changed)
                    self.assert_corruption_refused(path)
                    path.unlink()
                    self.assert_restored()

    def test_corruption_blocks_recovery_of_other_missing_generation_file(self):
        missing = next(p for p in self.generation_files if p.name == 'MEMORY_ENTRY.static.md')
        corrupt = missing.with_name('manifest.json')
        missing.unlink()
        corrupt.write_bytes(b'changed\n')
        self.assert_corruption_refused(corrupt)
        corrupt.unlink()
        self.assert_restored()
        self.assert_restored()

    def test_symlink_files_refused_with_exact_coordinate(self):
        sentinel = self.base / 'sentinel.txt'
        sentinel.write_bytes(b'protected outside projection\n')
        for path in self.paths:
            with self.subTest(path=path.relative_to(self.home).as_posix()):
                path.unlink()
                path.symlink_to(sentinel)
                try:
                    self.assert_unsafe(path)
                    self.assertTrue(path.is_symlink())
                    self.assertEqual(sentinel.read_bytes(), b'protected outside projection\n')
                finally:
                    path.unlink()
                    path.write_bytes(self.original[path])
        self.assert_restored()

    def test_symlink_directories_refused_with_exact_coordinate(self):
        memory = self.memory
        generation = next(p for p in (memory / 'gen').iterdir() if p.is_dir())
        units = next(p.parent for p in self.paths if p.parent.name == 'units')
        sentinel = self.base / 'outside'
        sentinel.mkdir()
        for path in (self.directory, memory, memory / 'gen', generation, units):
            with self.subTest(path=path.relative_to(self.home).as_posix()):
                backup = path.with_name(path.name + '-saved')
                path.rename(backup)
                path.symlink_to(sentinel, target_is_directory=True)
                try:
                    self.assert_unsafe(path)
                    self.assertEqual(list(sentinel.iterdir()), [])
                finally:
                    path.unlink()
                    backup.rename(path)
        self.assert_restored()

    def test_nonregular_projection_files_refused(self):
        memory = self.memory
        generation = next(p for p in (memory / 'gen').iterdir() if p.is_dir())
        for path in (self.directory / 'agent.json', memory / 'CURRENT',
                     generation / 'manifest.json'):
            for kind in ('directory', 'fifo'):
                with self.subTest(path=path.relative_to(self.home).as_posix(), kind=kind):
                    path.unlink()
                    if kind == 'directory':
                        path.mkdir()
                    else:
                        os.mkfifo(path)
                    try:
                        self.assert_unsafe(path)
                    finally:
                        if kind == 'directory':
                            path.rmdir()
                        else:
                            path.unlink()
                        path.write_bytes(self.original[path])
        self.assert_restored()

    def test_distill_retry_repairs_deleted_projection_files(self):
        first = self.breed(op='distill', child_id='distilled-one', op_id='distill-projection')
        paths = agents.refresh_projections('distilled-one', ctx=self.ctx)
        original = {p: p.read_bytes() for p in paths}
        raw = self.ledger_bytes()
        for path in paths:
            path.unlink()
        replay = self.breed(op='distill', child_id='distilled-one', op_id='distill-projection')
        self.assertEqual(canonical(replay), canonical(first))
        self.assertEqual(self.ledger_bytes(), raw)
        self.assertEqual({p: p.read_bytes() for p in paths}, original)
        self.assertIs(self.public_call('ledger_verify', {})['untrusted']['valid'], True)

    def test_directory_fsync_failure_retains_internal_error_and_retry_recovers(self):
        missing = self.memory / 'gen'
        saved = missing.with_name('saved-gen')
        missing.rename(saved)
        real_fsync = os.fsync
        fired = []

        def fail_once(fd):
            if not fired and stat.S_ISDIR(os.fstat(fd).st_mode):
                fired.append(True)
                raise OSError('synthetic directory durability fault')
            return real_fsync(fd)

        try:
            with mock.patch.object(os, 'fsync', side_effect=fail_once):
                with self.assertRaises(LineageError) as caught:
                    agents.refresh_projections('child-one', ctx=self.ctx)
            self.assertEqual(caught.exception.code, 'internal')
            self.assertTrue(fired)
            self.assertEqual(self.ledger_bytes(), self.raw)
        finally:
            if missing.exists():
                missing.rmdir()
            saved.rename(missing)
        self.assert_restored()

    def test_forged_snapshot_refused_without_projection_writes(self):
        from lineage.domain.memory import _snapshot_of, store
        from lineage.core import journal
        history = deepcopy(list(journal.snapshot(self.home)))
        history[-1]['payload']['record']['display_name'] = 'Uncommitted identity'
        context = agents._memory_context(self.ctx)
        snapshot = _snapshot_of(history, context)
        with self.assertRaises(LineageError) as caught:
            store.rebuild('child-one', snapshot=snapshot, ctx=context)
        self.assertEqual(caught.exception.code, 'bad_op')
        self.assertEqual({p: p.read_bytes() for p in self.paths}, self.original)
        self.assert_restored()
