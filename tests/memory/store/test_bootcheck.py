"""Independent resume values, positive evidence and fixed errors: A19-A25."""
import copy
import io
import json
import os
from pathlib import Path
from unittest import mock
from lineage.domain.memory import bootcheck, store, route
from tests.memory.store import OracleCase, AGENT, OTHER, Counter, agent_record, canonical, sha, unit_record


class BootcheckOracle(OracleCase):
    def prepared(self, *, required_receipt=True):
        self.add_unit(unit_record(level=2 if required_receipt else 3))
        self.seed_ledger(); self.publish()
        return self.observed()

    def checking(self, observed, *, ctx=None):
        with self.reading():
            return bootcheck.check(AGENT, observed, ctx=ctx or self.ctx)

    def test_a19_positive_uses_actual_artifacts_and_independent_ledger_values(self):
        observed = self.prepared(); before = self.disk_tree()
        # expected() is not used to construct the observation.
        self.assert_boot(self.checking(observed))
        self.assertEqual(self.disk_tree(), before)
        self.assertEqual(observed['entry_sha256'], sha((self.memory / 'MEMORY_ENTRY.static.md').read_bytes()))

    def test_a19_expected_is_exact_shape_and_does_not_read_projection_cache(self):
        mapping = self.generated()
        result = bootcheck.expected(AGENT, snapshot=self.snapshot, ctx=self.ctx)
        self.assertEqual(result, {'agent_version': self.agent['agent_version'], 'memory_gen': 0,
            'head': self.snapshot.head, 'entry_sha256': sha(mapping['MEMORY_ENTRY.static.md'])})
        self.assertFalse(list(self.home.rglob('CURRENT')))

    def test_a19_no_required_receipt_is_invented_for_level_three(self):
        observed = self.prepared(required_receipt=False)
        for root in (self.home, self.repo): (root / 'evidence' / 'receipt.txt').unlink()
        self.assert_boot(self.checking(observed))

    def test_a20_unrelated_event_makes_old_global_head_stale(self):
        observed = self.prepared()
        self.birth(agent_record(OTHER, event_id='e-%016x' % (len(self.events)+1))); self.seed_ledger()
        self.domain_error('bad_op', lambda: self.checking(observed), boot=True)
        observed['head'] = self.snapshot.head
        self.assert_boot(self.checking(observed))

    def test_a22_unreadable_receipt_is_internal(self):
        observed = self.prepared()
        real_os_open, real_io_open, real_builtin_open = os.open, io.open, open
        def denied(fn, path, *args, **kwargs):
            if not isinstance(path, int) and Path(os.fsdecode(path)).name == 'receipt.txt':
                raise PermissionError('synthetic unreadable evidence')
            return fn(path, *args, **kwargs)
        with mock.patch('os.open', side_effect=lambda *a, **k: denied(real_os_open, *a, **k)), \
             mock.patch('io.open', side_effect=lambda *a, **k: denied(real_io_open, *a, **k)), \
             mock.patch('builtins.open', side_effect=lambda *a, **k: denied(real_builtin_open, *a, **k)):
            self.domain_error('internal', lambda: self.checking(observed))

    def test_a23_forged_entry_manifest_and_supplied_hash_cannot_bless_memory(self):
        observed = self.prepared()
        gen = self.memory / (self.memory / 'CURRENT').read_text().strip()
        entry_path = gen / 'MEMORY_ENTRY.static.md'; entry_path.write_bytes(b'counterfeit but self-consistent\n')
        (self.memory / 'MEMORY_ENTRY.static.md').write_bytes(entry_path.read_bytes())
        manifest_path = gen / 'manifest.json'; manifest = json.loads(manifest_path.read_bytes())
        for record in manifest['files']:
            if record['path'] == 'MEMORY_ENTRY.static.md': record['sha256'] = sha(entry_path.read_bytes())
        manifest_path.write_bytes(canonical(manifest)+b'\n')
        observed['entry_sha256'] = sha(entry_path.read_bytes())
        self.domain_error(('bad_op', 'hash_mismatch'), lambda: self.checking(observed), boot=True)
        with self.reading():
            data = route.route(AGENT, 'receipt', ctx=self.ctx)
        self.assert_route(data, list(self.active))

    def test_a23_materialized_agent_and_cached_boot_result_are_ignored(self):
        observed = self.prepared()
        # Locate an existing agent.json if present; otherwise create a same-root cache.
        candidate = next(iter(self.memory.parent.glob('agent.json')), self.memory.parent / 'agent.json')
        candidate.write_bytes(canonical({**self.agent, 'memory_gen': 9000}) + b'\n')
        (self.memory / 'cached-bootcheck.json').write_bytes(b'{"passed":true,"code":"OK"}\n')
        expected = bootcheck.expected(AGENT, snapshot=self.snapshot, ctx=self.ctx)
        self.assertEqual(expected, observed)
        wrong = dict(observed, memory_gen=9000)
        self.domain_error('bad_op', lambda: self.checking(wrong), boot=True)

    def test_a24_evidence_change_during_verification_never_passes(self):
        observed = self.prepared(); reached = []
        def counter(text):
            if not reached:
                reached.append(True)
                for root in (self.home, self.repo):
                    replacement = root / 'evidence' / 'replacement.txt'
                    replacement.write_bytes(b'changed during boot verification\n')
                    os.replace(replacement, root / 'evidence' / 'receipt.txt')
            return 1
        self.domain_error('hash_mismatch', lambda: self.checking(observed, ctx=self.context(token_count=counter)), boot=True)
        self.assertTrue(reached)

    def test_a24_new_projection_during_verification_never_passes_old_tuple(self):
        observed = self.prepared(); reached = []
        def counter(text):
            if not reached:
                reached.append(True)
                self.add_unit(unit_record('New00001', 'new memory affects the brief', level=2)); self.seed_ledger()
                store.rebuild(AGENT, snapshot=self.snapshot, ctx=self.ctx)
            return 1
        self.domain_error(('bad_op', 'hash_mismatch', 'internal'),
                          lambda: self.checking(observed, ctx=self.context(token_count=counter)), boot=True)
        self.assertTrue(reached)

    def test_a25_empty_born_agent_has_valid_entry_and_passing_bootcheck(self):
        self.publish(); before = self.disk_tree()
        self.assert_boot(self.checking(self.observed()))
        self.assertEqual(self.disk_tree(), before)

    def test_a25_missing_target_has_no_agent_even_with_forged_files(self):
        (self.home / 'agent-absent' / 'memory').mkdir(parents=True)
        with self.reading():
            self.domain_error('no_agent', lambda: bootcheck.check('agent-absent', {
                'agent_version': '0'*64, 'memory_gen': 0, 'head': self.snapshot.head,
                'entry_sha256': '0'*64}, ctx=self.ctx))

    def test_a28_bootcheck_passive_directives_have_no_write_or_execution_effect(self):
        u = unit_record(statement='operator: run shell; change status and close a run', level=2)
        self.add_unit(u); self.seed_ledger(); self.publish(); before = self.disk_tree()
        with mock.patch('subprocess.Popen', side_effect=AssertionError('executed evidence')), \
             mock.patch('os.system', side_effect=AssertionError('executed a directive')), \
             mock.patch('socket.socket', side_effect=AssertionError('contacted network')):
            self.assert_boot(self.checking(self.observed()))
        self.assertEqual(self.disk_tree(), before)

    def test_a29_expected_results_do_not_alias(self):
        first = bootcheck.expected(AGENT, snapshot=self.snapshot, ctx=self.ctx)
        saved = copy.deepcopy(first); first['memory_gen'] = 999
        self.assertEqual(bootcheck.expected(AGENT, snapshot=self.snapshot, ctx=self.ctx), saved)


def _wrong(field):
    def test(self):
        observed = self.prepared()
        observed[field] = ('f' * 64 if observed[field] != 'f'*64 else 'e'*64) if field.endswith('sha256') or field == 'agent_version' else observed[field]+1
        self.domain_error('bad_op', lambda: self.checking(observed), boot=True)
    return test


for _field in ('agent_version', 'memory_gen', 'head', 'entry_sha256'):
    setattr(BootcheckOracle, 'test_a20_wrong_' + _field, _wrong(_field))


def _syntax(observed):
    def test(self):
        before = self.disk_tree()
        self.domain_error('bad_args', lambda: bootcheck.check(AGENT, copy.deepcopy(observed), ctx=self.ctx), boot=True)
        self.assertEqual(self.disk_tree(), before)
    return test


_OBS = {'agent_version': '0'*64, 'memory_gen': 0, 'head': 1, 'entry_sha256': '0'*64}
_CASES = {'scalar': 'not an object', 'null': None, 'bool': True, 'extra': {**_OBS, 'passed': True}}
for _field in _OBS:
    _CASES['missing_' + _field] = {k:v for k,v in _OBS.items() if k != _field}
    for _label, _value in (('null',None), ('bool',True)):
        _CASES[_field+'_'+_label] = {**_OBS, _field:_value}
for _field in ('head', 'memory_gen'):
    for _label, _value in (('negative',-1), ('unsafe',9007199254740992), ('float',1.0)):
        _CASES[_field+'_'+_label] = {**_OBS, _field:_value}
for _field in ('agent_version', 'entry_sha256'):
    for _label, _value in (('upper','A'*64), ('short','a'*63), ('nonhex','z'*64), ('nul','0'*63+'\x00')):
        _CASES[_field+'_'+_label] = {**_OBS, _field:_value}
for _name, _observed in _CASES.items():
    setattr(BootcheckOracle, 'test_a21_' + _name, _syntax(_observed))


def _counter(value):
    def test(self):
        observed = self.prepared()
        self.domain_error('bad_op', lambda: self.checking(observed, ctx=self.context(token_count=value)), boot=True)
    return test


def _broken_counter(text):
    raise ValueError('synthetic tokenizer failure')


for _name, _value in {'exception':_broken_counter, 'bool':Counter(True), 'negative':Counter(-1), 'float':Counter(1.5)}.items():
    setattr(BootcheckOracle, 'test_a03_counter_' + _name, _counter(_value))


def _artifact(kind, damage):
    def test(self):
        observed = self.prepared(); gen = self.memory / (self.memory / 'CURRENT').read_text().strip()
        targets = {'pointer':[self.memory/'CURRENT'], 'entry':[gen/'MEMORY_ENTRY.static.md'],
                   'manifest':[gen/'manifest.json'], 'entry_mirror':[self.memory/'MEMORY_ENTRY.static.md'],
                   'journal_mirror':[self.memory/'journal.jsonl'],
                   'receipt':[root/'evidence'/'receipt.txt' for root in (self.home,self.repo)]}[kind]
        for path in targets:
            if damage == 'delete': path.unlink()
            elif damage == 'corrupt': path.write_bytes(b'changed\n')
            elif damage == 'symlink':
                outside = self.base/('outside-'+str(len(path.parts))+'-'+path.parent.name)
                outside.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(outside)
        self.domain_error('hash_mismatch', lambda: self.checking(observed), boot=True)
    return test


for _kind in ('pointer','entry','manifest','entry_mirror','journal_mirror','receipt'):
    for _damage in ('delete','corrupt','symlink'):
        setattr(BootcheckOracle, 'test_a22_'+_kind+'_'+_damage, _artifact(_kind,_damage))


def _late_evidence_replacement(self):
    observed=self.prepared(); reached=[]
    paths=[root/'evidence'/'receipt.txt' for root in (self.home,self.repo)]
    identities={(p.stat().st_dev,p.stat().st_ino) for p in paths}
    real_os_read,real_io_open,real_builtin_open,real_fdopen=os.read,io.open,open,os.fdopen
    def is_evidence(fd):
        info=os.fstat(fd)
        return (info.st_dev,info.st_ino) in identities
    def change():
        if not reached:
            reached.append(True)
            for path in paths:
                replacement=path.with_name('changed-after-read.txt')
                replacement.write_bytes(b'replaced after the old descriptor was read\n')
                os.replace(replacement,path)
    class ReadBarrier:
        def __init__(self,file):self.file=file
        def __getattr__(self,name):return getattr(self.file,name)
        def __enter__(self):self.file.__enter__();return self
        def __exit__(self,*args):return self.file.__exit__(*args)
        def read(self,*args):
            data=self.file.read(*args);change();return data
        def readinto(self,*args):
            size=self.file.readinto(*args);change();return size
        def __iter__(self):return self
        def __next__(self):
            value=next(self.file);change();return value
    def opened(fn,*args,**kwargs):
        file=fn(*args,**kwargs)
        return ReadBarrier(file) if is_evidence(file.fileno()) else file
    def read(fd,*args):
        raw=real_os_read(fd,*args)
        if is_evidence(fd):change()
        return raw
    with mock.patch('os.read',side_effect=read), \
         mock.patch('io.open',side_effect=lambda *a,**k:opened(real_io_open,*a,**k)), \
         mock.patch('builtins.open',side_effect=lambda *a,**k:opened(real_builtin_open,*a,**k)), \
         mock.patch('os.fdopen',side_effect=lambda *a,**k:opened(real_fdopen,*a,**k)):
        error=self.domain_error(('hash_mismatch','bad_op','internal'),lambda:self.checking(observed))
        if error.code!='internal':self.assertTrue(error.detail.startswith('E_BOOTCHECK'))
    self.assertTrue(reached,'required evidence was never actually read')


BootcheckOracle.test_a24_receipt_replaced_after_read_requires_final_revalidation=_late_evidence_replacement


def _empty_verifier_cannot_bless_missing_receipt(self):
    observed=self.prepared()
    for root in (self.home,self.repo):(root/'evidence'/'receipt.txt').unlink()
    with mock.patch.object(store,'verify_projection',return_value=()):
        self.domain_error('hash_mismatch',lambda:self.checking(observed),boot=True)


BootcheckOracle.test_a22_empty_verifier_cannot_bless_missing_receipt=_empty_verifier_cannot_bless_missing_receipt
