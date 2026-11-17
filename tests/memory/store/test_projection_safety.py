"""Read-only verifier, durable publication and hostile paths: A9-A13/A24."""
import json
import os
import shutil
import stat
from pathlib import Path
from unittest import mock
from lineage.domain.memory import store
from tests.memory.store import OracleCase, AGENT, canonical, sha, unit_record, alias_patch


class ProjectionSafetyOracle(OracleCase):
    def prepared(self):
        self.history(); self.publish()
        self.selected = (self.memory / 'CURRENT').read_text().strip()
        return self.memory / self.selected

    def verify(self):
        return store.verify_projection(AGENT, snapshot=self.snapshot, ctx=self.ctx)

    def test_a12_pristine_projection_verifies_without_writing(self):
        self.prepared(); before = self.disk_tree()
        self.assertEqual(self.verify(), ())
        self.assertEqual(self.disk_tree(), before)

    def test_a12_forged_unit_and_self_consistent_manifest_are_rejected(self):
        gen = self.prepared(); unit = gen / 'units' / 'Replace01.json'
        changed = json.loads(unit.read_bytes()); changed['statement'] = 'forged statement'
        unit.write_bytes(canonical(changed) + b'\n')
        manifest = gen / 'manifest.json'; record = json.loads(manifest.read_bytes())
        for f in record['files']:
            if f['path'] == 'units/Replace01.json':
                f['sha256'] = sha(unit.read_bytes())
        manifest.write_bytes(canonical(record) + b'\n')
        before = self.disk_tree(); self.assert_issues(self.verify())
        self.assertEqual(self.disk_tree(), before)

    def test_a12_journal_reordering_is_not_a_new_local_chain(self):
        gen = self.prepared(); victim = gen / 'journal.jsonl'
        lines = victim.read_bytes().splitlines(keepends=True); lines[0], lines[1] = lines[1], lines[0]
        victim.write_bytes(b''.join(lines)); before = self.disk_tree()
        self.assert_issues(self.verify()); self.assertEqual(self.disk_tree(), before)

    def test_a12_issue_results_do_not_alias(self):
        gen = self.prepared(); (gen / 'manifest.json').unlink()
        first = self.verify(); self.assert_issues(first)
        saved = [dict(x) for x in first]; first[0]['detail'] = 'caller mutation'
        second = self.verify(); self.assertEqual(list(second), saved)

    def test_a13_symlinked_memory_ancestor_is_refused_without_escape(self):
        self.prepared(); original = self.memory
        outside = self.base / 'outside'; shutil.move(str(original), outside)
        original.symlink_to(outside, target_is_directory=True)
        before = self.disk_tree(outside)
        self.domain_error(('hash_mismatch', 'bad_args'), lambda: store.rebuild(AGENT, snapshot=self.snapshot, ctx=self.ctx))
        self.assertEqual(self.disk_tree(outside), before)

    def test_a13_hostile_scope_never_forms_filesystem_components(self):
        # Language is arbitrary bounded schema text, not a permitted path component.
        self.agent['language'] = '../outside'
        self.events[0]['payload']['record'] = dict(self.agent)
        self.events[0].pop('sha256'); self.events[0]['sha256'] = sha(canonical(self.events[0]))
        before = self.disk_tree()
        try:
            paths = store.rebuild(AGENT, snapshot=self.snapshot, ctx=self.ctx)
        except NotImplementedError:
            raise
        except Exception as exc:
            self.assertIn(getattr(exc, 'code', None), {'bad_args', 'bad_op', 'hash_mismatch'})
        else:
            self.assertTrue(paths)
            for p in paths:
                candidate = p if p.is_absolute() else self.home / p
                self.assertTrue(candidate.is_relative_to(self.home))
                self.assertNotIn('outside', candidate.relative_to(self.home).parts)
        self.assertFalse((self.base / 'outside').exists())
        self.assertEqual(self.ledger.read_bytes(), before['ledger/main/events.jsonl'])

    def test_a09_crash_debris_is_never_selected(self):
        self.prepared()
        debris = self.memory / 'gen' / '.unfinished'; debris.mkdir(); (debris / 'partial').write_bytes(b'partial')
        self.publish()
        pointer = (self.memory / 'CURRENT').read_text()
        self.assertEqual(pointer, 'gen/7\n'); self.assertNotIn('unfinished', pointer)
        # Staging/coordination files are excluded from the deterministic mapping.
        self.assertFalse(any('unfinished' in k for k in self.generated()))


def _damage(kind):
    def test(self):
        gen = self.prepared()
        if kind == 'missing_entry': (gen / 'MEMORY_ENTRY.static.md').unlink()
        elif kind == 'missing_unit': (gen / 'units' / 'Replace01.json').unlink()
        elif kind == 'missing_old_generation': shutil.rmtree(self.memory / 'gen' / '1')
        elif kind == 'extra_file': (gen / 'extra.json').write_bytes(b'{}\n')
        elif kind == 'extra_generation': (self.memory / 'gen' / '999').mkdir()
        elif kind == 'stale_pointer': (self.memory / 'CURRENT').write_bytes(b'gen/1\n')
        elif kind == 'entry_mirror': (self.memory / 'MEMORY_ENTRY.static.md').write_bytes(b'changed\n')
        elif kind == 'journal_mirror': (self.memory / 'journal.jsonl').write_bytes(b'changed\n')
        elif kind == 'forged_manifest': (gen / 'manifest.json').write_bytes(b'{}\n')
        before = self.disk_tree()
        self.assert_issues(self.verify()); self.assertEqual(self.disk_tree(), before)
    return test


for _kind in ('missing_entry', 'missing_unit', 'missing_old_generation', 'extra_file', 'extra_generation',
              'stale_pointer', 'entry_mirror', 'journal_mirror', 'forged_manifest'):
    setattr(ProjectionSafetyOracle, 'test_a12_' + _kind, _damage(_kind))


def _unsafe_pointer(raw):
    def test(self):
        self.prepared(); (self.memory / 'CURRENT').write_bytes(raw)
        before = self.disk_tree(); self.assert_issues(self.verify())
        self.assertEqual(self.disk_tree(), before)
    return test


for _name, _raw in {'traversal': b'../outside\n', 'absolute': b'/outside\n', 'nul': b'gen/7\x00\n',
                   'noncanonical': b'gen/007\n', 'duplicate_json': b'{"g":7,"g":8}\n',
                   'nan': b'NaN\n', 'infinity': b'Infinity\n', 'invalid_utf8': b'gen/\xff\n'}.items():
    setattr(ProjectionSafetyOracle, 'test_b10_current_' + _name, _unsafe_pointer(_raw))


def _symlink(kind):
    def test(self):
        gen = self.prepared()
        target = {'generation': gen, 'units_directory': gen / 'units', 'unit': gen / 'units' / 'Replace01.json',
                  'manifest': gen / 'manifest.json', 'pointer': self.memory / 'CURRENT',
                  'entry_mirror': self.memory / 'MEMORY_ENTRY.static.md',
                  'journal_mirror': self.memory / 'journal.jsonl'}[kind]
        outside = self.base / 'sentinel'
        if target.is_dir(): shutil.copytree(target, outside); shutil.rmtree(target)
        else: outside.write_bytes(target.read_bytes()); target.unlink()
        target.symlink_to(outside, target_is_directory=outside.is_dir())
        before = self.disk_tree(outside) if outside.is_dir() else outside.read_bytes()
        self.assert_issues(self.verify())
        self.assertEqual(self.disk_tree(outside) if outside.is_dir() else outside.read_bytes(), before)
    return test


for _kind in ('generation', 'units_directory', 'unit', 'manifest', 'pointer', 'entry_mirror', 'journal_mirror'):
    setattr(ProjectionSafetyOracle, 'test_a13_symlink_' + _kind, _symlink(_kind))


def _corrupt(kind):
    def test(self):
        gen = self.prepared()
        target = gen / ('units/Replace01.json' if kind == 'unit' else 'manifest.json')
        target.write_bytes(b'corrupted\n'); before = self.disk_tree()
        self.domain_error('hash_mismatch', lambda: store.rebuild(AGENT, snapshot=self.snapshot, ctx=self.ctx))
        self.assertEqual(self.disk_tree(), before)
    return test


for _kind in ('unit', 'manifest'):
    setattr(ProjectionSafetyOracle, 'test_a11_corrupt_' + _kind + '_not_overwritten', _corrupt(_kind))


def _crash(phase):
    def test(self):
        expected = self.generated()
        before = self.ledger.read_bytes(); fired = []
        real_fsync, real_replace, real_rename, real_mkdir = os.fsync, os.replace, os.rename, os.mkdir
        def fail_once():
            if not fired:
                fired.append(True); raise OSError('synthetic durable-publication fault')
        def sync(fd):
            mode = os.fstat(fd).st_mode
            if phase == 'file_fsync' and stat.S_ISREG(mode): fail_once()
            if phase == 'directory_fsync' and stat.S_ISDIR(mode): fail_once()
            return real_fsync(fd)
        def rename(fn, src, dst, *args, **kwargs):
            name = Path(os.fsdecode(dst)).name
            if phase == 'current_replace' and name == 'CURRENT': fail_once()
            if phase == 'generation_publish' and name.isdecimal(): fail_once()
            return fn(src, dst, *args, **kwargs)
        def mkdir(path, *args, **kwargs):
            if phase == 'staging' and 'memory' in os.fsdecode(path): fail_once()
            return real_mkdir(path, *args, **kwargs)
        with alias_patch(os,'fsync',sync), \
             alias_patch(os,'replace',lambda *a,**k:rename(real_replace,*a,**k)), \
             alias_patch(os,'rename',lambda *a,**k:rename(real_rename,*a,**k)), \
             alias_patch(os,'mkdir',mkdir):
            self.domain_error('internal', lambda: store.rebuild(AGENT, snapshot=self.snapshot, ctx=self.ctx))
        self.assertTrue(fired, 'The requested durability fault was not reached')
        self.assertEqual(self.ledger.read_bytes(), before)
        # A complete selection may survive; no incomplete selection may verify.
        issues = store.verify_projection(AGENT, snapshot=self.snapshot, ctx=self.ctx)
        if not issues:
            pointers = list(self.home.rglob('CURRENT')); self.assertEqual(len(pointers), 1)
            memory = pointers[0].parent
            self.assertEqual({k: (memory / k).read_bytes() for k in expected}, dict(expected))
        self.publish()
        self.assertEqual({k: (self.memory / k).read_bytes() for k in expected}, dict(expected))
    return test


for _phase in ('staging', 'file_fsync', 'directory_fsync', 'generation_publish', 'current_replace'):
    setattr(ProjectionSafetyOracle, 'test_a09_fault_' + _phase, _crash(_phase))


def _staging_substitution(self):
    self.prepared()
    self.add_unit(unit_record('Next00001','new generation after a stable selection',level=2)); self.seed_ledger()
    outside=self.base/'outside-stage'; outside.mkdir(); (outside/'sentinel').write_bytes(b'untouched\n')
    original=self.disk_tree(outside); forbidden={(p.stat().st_dev,p.stat().st_ino) for p in (outside,outside/'sentinel')}
    opened={}; fired=[]; real_open,real_rename,real_replace=os.open,os.rename,os.replace
    def anchor(path,fd=None):
        p=Path(os.fsdecode(path))
        return p if p.is_absolute() else opened.get(fd,Path.cwd())/p
    def tracked_open(path,flags,*a,**k):
        p=anchor(path,k.get('dir_fd')); fd=real_open(path,flags,*a,**k)
        info=os.fstat(fd)
        if (info.st_dev,info.st_ino) in forbidden:
            os.close(fd); self.fail('publisher followed the substituted staging symlink')
        opened[fd]=p
        return fd
    def publish(fn,src,dst,*a,**k):
        source=anchor(src,k.get('src_dir_fd')); destination=anchor(dst,k.get('dst_dir_fd'))
        if not fired and destination.name.isdecimal() and destination.parent.name=='gen' and source.is_dir() and not source.is_symlink():
            fired.append(True)
            saved=source.with_name(source.name+'.saved')
            real_rename(source,saved)
            source.symlink_to(outside,target_is_directory=True)
        return fn(src,dst,*a,**k)
    with alias_patch(os,'open',tracked_open), \
         alias_patch(os,'rename',lambda *a,**k:publish(real_rename,*a,**k)), \
         alias_patch(os,'replace',lambda *a,**k:publish(real_replace,*a,**k)):
        self.domain_error(('hash_mismatch','bad_args','internal'),lambda:store.rebuild(AGENT,snapshot=self.snapshot,ctx=self.ctx))
    self.assertTrue(fired,'staging-directory publication boundary was not reached')
    self.assertEqual(self.disk_tree(outside),original)
    self.assert_issues(self.verify())


ProjectionSafetyOracle.test_a13_staging_directory_substitution_refuses_escape=_staging_substitution


def _hostile_workflow(self):
    self.agent['workflow']='../outside'
    self.events[0]['payload']['record']=dict(self.agent)
    self.events[0].pop('sha256');self.events[0]['sha256']=sha(canonical(self.events[0]))
    before=self.ledger.read_bytes()
    try:
        paths=store.rebuild(AGENT,snapshot=self.snapshot,ctx=self.ctx)
    except NotImplementedError:
        raise
    except Exception as exc:
        self.assertIn(getattr(exc,'code',None),{'bad_args','bad_op','hash_mismatch'})
        self.assertNotIn(str(self.base),getattr(exc,'detail',''))
    else:
        self.assertTrue(paths)
        for path in paths:
            actual=path if path.is_absolute() else self.home/path
            self.assertTrue(actual.is_relative_to(self.home))
            self.assertNotIn('outside',actual.relative_to(self.home).parts)
    self.assertEqual(self.ledger.read_bytes(),before)
    self.assertFalse((self.base/'outside').exists())


ProjectionSafetyOracle.test_b10_hostile_workflow_never_forms_a_path=_hostile_workflow
