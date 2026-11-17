"""Controlled locked-prefix fixtures for unreachable/hostile memory histories."""
from copy import deepcopy
import os
import multiprocessing
from unittest import mock

from lineage.domain import gate_close
from tests.runs.support import (GateCase, RunCase, OWNER, OTHER, RUN, SEAT,
                               COST, OUTCOME, outcome, canonical, owned_process)


def assign(value, path, replacement):
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = deepcopy(replacement)


class Witnesses(GateCase):
    def test_a12_old_replay_does_not_refresh_original_lamport(self):
        self.f.put(self.f.unit())
        events = list(deepcopy(self.f.events()))
        opening = next(e for e in events if e['kind'] == 'run.open')
        memory = next(e for e in events if e['kind'] == 'memory.put')
        memory['lamport'] = opening['lamport']
        self.refusal('memory_required', lambda: self.f.check(events=events))

    def test_a12_preopen_episode_is_not_fresh(self):
        self.f.put(self.f.unit())
        events = list(deepcopy(self.f.events()))
        opening = next(e for e in events if e['kind'] == 'run.open')
        events[-1]['lamport'] = opening['lamport'] - 1
        self.refusal('memory_required', lambda: self.f.check(events=events))

    def test_a13_foreign_owner_memory_cannot_close(self):
        # Controlled foreign-owner history: keep the target run binding identical.
        unit = self.f.unit(run_id=RUN, agent_id=OTHER)
        self.f.put(unit, agent_id=OTHER, run_id=RUN)
        self.refusal('memory_required', self.f.check)

    def test_a13_foreign_run_memory_cannot_close(self):
        self.f.controlled_open(run_id='other001')
        self.f.put(self.f.unit(run_id='other001'), run_id='other001')
        self.refusal('memory_required', self.f.check)

    def test_a13_unbound_generic_memory_cannot_close(self):
        unit = self.f.unit('lesson', identifier='lesson01')
        del unit['provenance']['run_id']
        self.f.append_peer('memory.put', {'agent_id': OWNER, 'unit': unit})
        self.refusal('memory_required', self.f.check)

    def test_a20_level_two_without_receipt_is_debt(self):
        self.f.put(self.f.unit(level=2))
        self.refusal('memory_debt', self.f.check)

    def test_a20_missing_required_receipt_is_debt(self):
        receipt = {'path': 'evidence/missing.txt', 'sha256': 'a' * 64}
        self.f.put(self.f.unit(level=2, receipts=[receipt]))
        self.refusal('memory_debt', self.f.check)

    def test_a20_unreadable_receipt_is_debt(self):
        receipt = self.f.receipt('evidence/unreadable.txt')
        self.f.put(self.f.unit(receipts=[receipt]))
        snap = self.f.snapshot()
        real_os_open, real_io_open = os.open, __import__('io').open
        def deny_os(path, *args, **kwargs):
            if str(path).endswith('unreadable.txt'):
                raise PermissionError('oracle denied evidence')
            return real_os_open(path, *args, **kwargs)
        def deny_io(path, *args, **kwargs):
            if str(path).endswith('unreadable.txt'):
                raise PermissionError('oracle denied evidence')
            return real_io_open(path, *args, **kwargs)
        with mock.patch('os.open', side_effect=deny_os), mock.patch('io.open', side_effect=deny_io):
            self.refusal('memory_debt', lambda: gate_close.check(snap, RUN, OUTCOME, COST,
                         actor=OWNER, ctx=self.f.context()))

    def test_a21_symlink_receipt_is_debt(self):
        receipt = self.f.receipt('evidence/target.txt')
        link = self.f.home / 'evidence/link.txt'
        link.symlink_to('target.txt')
        self.f.put(self.f.unit(receipts=[{**receipt, 'path': 'evidence/link.txt'}]))
        self.refusal('memory_debt', self.f.check)

    def test_a21_symlink_directory_receipt_is_debt(self):
        receipt = self.f.receipt()
        (self.f.home / 'alias').symlink_to('evidence', target_is_directory=True)
        self.f.put(self.f.unit(receipts=[{**receipt, 'path': 'alias/result.txt'}]))
        self.refusal('memory_debt', self.f.check)

    def test_a21_directory_receipt_is_debt(self):
        (self.f.home / 'evidence').mkdir(exist_ok=True)
        self.f.put(self.f.unit(receipts=[{'path': 'evidence', 'sha256': 'a' * 64}]))
        self.refusal('memory_debt', self.f.check)

    def test_a21_fifo_receipt_cannot_block(self):
        target = self.f.home / 'evidence/fifo'
        target.parent.mkdir(exist_ok=True)
        os.mkfifo(target)
        self.f.put(self.f.unit(receipts=[{'path': 'evidence/fifo', 'sha256': 'a' * 64}]))
        parent, child = multiprocessing.get_context('fork').Pipe(duplex=False)
        self.addCleanup(parent.close)
        with owned_process(_fifo_check, (self.f.home, child)) as process:
            child.close()
            self.assertTrue(parent.poll(1.5), 'non-regular receipt blocked the gate')
            result = parent.recv()
            if result == 'NotImplementedError':
                raise NotImplementedError('U13 stub')
            self.assertEqual(result, 'memory_debt')
            process.join(0.5)
            self.assertEqual(process.exitcode, 0)

    def test_a23_optional_level_three_receipt_is_verified(self):
        receipt = self.f.receipt()
        self.f.put(self.f.unit(receipts=[receipt]))
        (self.f.home / receipt['path']).unlink()
        self.refusal('memory_debt', self.f.check)

    def test_a24_invalid_lexical_first_alternative_does_not_hide_valid_one(self):
        invalid = self.f.unit(identifier='00000000', privacy='private')
        self.f.put(invalid)
        receipt = self.f.receipt()
        self.f.put(self.f.unit(identifier='episode1', receipts=[receipt]))
        report = self.f.check()
        self.passed(report)
        self.assertEqual(report['memory_receipts'], [receipt])

    def test_a24_one_unit_receipt_array_cannot_exceed_64(self):
        receipts = [self.f.receipt(f'e/{i:03x}', b'x') for i in range(65)]
        self.f.put(self.f.unit(receipts=receipts))
        self.refusal('memory_debt', self.f.check)

    def test_a37_multibyte_canonical_byte_limit_is_not_character_count(self):
        unit = self.f.unit()
        unit['statement'] = '雪' * 2100
        self.assertGreater(len(canonical(unit)), 6000)
        self.f.put(unit)
        self.refusal('memory_debt', self.f.check)


def _fifo_check(home, connection):
    from tests.runs.support import Fixture
    fixture = Fixture(home, seed=False)
    try:
        fixture.check()
        connection.send('passed')
    except BaseException as exc:
        connection.send(getattr(exc, 'code', type(exc).__name__))
    finally:
        connection.close()


INVALID_UNITS = (
    ('draft', ('status',), 'draft'),
    ('private', ('privacy',), 'private'),
    ('retired', ('status',), 'retired'),
    ('superseded', ('status',), 'superseded'),
    ('illegal_level', ('level',), 1),
    ('unknown_body', ('body', 'extra'), True),
    ('wrong_body_kind', ('body',), {'reason': 'not an episode'}),
    ('scope_workflow', ('scope', 'workflow'), 'develop'),
    ('scope_language', ('scope', 'language'), 'typescript'),
    ('malformed', ('statement',), None),
)


def invalid_unit_test(path, replacement):
    def test(self):
        unit = self.f.unit()
        assign(unit, path, replacement)
        if unit['status'] == 'superseded':
            unit['superseded_by'] = 'successor'
        self.f.put(unit)
        self.refusal('memory_debt', self.f.check)
    return test


for label, path, value in INVALID_UNITS:
    setattr(Witnesses, 'test_a14_invalid_' + label, invalid_unit_test(path, value))

BINDINGS = (
    ('body_run', ('body', 'run_id'), 'other001'),
    ('provenance_run', ('provenance', 'run_id'), 'other001'),
    ('task', ('body', 'task_id'), 'other001'),
    ('model', ('body', 'seat', 'model'), 'other-model'),
    ('effort', ('body', 'seat', 'effort'), 'high'),
    ('mode', ('body', 'seat', 'mode'), 'interactive'),
    ('parents', ('body', 'parents_context'), [{'agent_id': OTHER, 'agent_version': 'a'*64, 'run_id': 'other001'}]),
    ('version_unknown_field', ('body', 'agent_version'), 'a'*64),
)

for label, path, value in BINDINGS:
    setattr(Witnesses, 'test_a15_binding_' + label, invalid_unit_test(path, value))

COST_OUTCOME = (
    ('verdict', ('body', 'outcome', 'verdict'), 'ADMIT'),
    ('repairs', ('body', 'outcome', 'repair_loops'), 1),
    ('confirmed', ('body', 'outcome', 'findings', 'confirmed'), 1),
    ('refuted', ('body', 'outcome', 'findings', 'refuted'), 1),
) + tuple((name, ('body', 'cost', name), 0) for name in COST)

for label, path, value in COST_OUTCOME:
    setattr(Witnesses, 'test_a16_mismatch_' + label, invalid_unit_test(path, value))


def companion_test(kind, defect):
    def test(self):
        requested = outcome('red')
        self.f.put(self.f.unit(verdict=requested))
        good_kind = 'negative' if kind == 'lesson' else 'lesson'
        self.f.put(self.f.unit(good_kind, identifier='validunit'))
        candidate = self.f.unit(kind, identifier='candidate')
        actor, run_id = OWNER, RUN
        if defect == 'private':
            candidate['privacy'] = 'private'
        elif defect == 'inactive':
            candidate['status'] = 'retired'
        elif defect == 'other_run':
            candidate['provenance']['run_id'] = 'other001'
            run_id = 'other001'
        elif defect == 'other_agent':
            candidate['provenance']['actor'] = OTHER
            actor = OTHER
        elif defect == 'receipt':
            candidate['receipts'] = [{'path': 'evidence/missing', 'sha256': 'a' * 64}]
        elif defect == 'wrong_kind':
            candidate = self.f.unit('open_item', identifier='candidate')
        self.f.put(candidate, agent_id=actor, run_id=run_id)
        events = list(deepcopy(self.f.events()))
        if defect == 'preopen':
            events[-1]['lamport'] = next(e['lamport'] for e in events if e['kind'] == 'run.open')
        self.refusal('memory_debt', lambda: self.f.check(requested, events=events))
    return test


for kind in ('lesson', 'negative'):
    for defect in ('private', 'inactive', 'other_run', 'other_agent', 'receipt', 'wrong_kind', 'preopen'):
        setattr(Witnesses, f'test_a18_{kind}_{defect}', companion_test(kind, defect))


UNSAFE = ('/absolute', '../escape', './dot', 'a//empty', 'a/../escape',
          'a/./dot', 'back\\slash', '', 'ledger/result', 'family/result')


def path_test(path):
    def test(self):
        self.f.put(self.f.unit(receipts=[{'path': path, 'sha256': 'a' * 64}]))
        self.refusal('memory_debt', self.f.check)
    return test


for index, path in enumerate(UNSAFE):
    setattr(Witnesses, f'test_a21_unsafe_receipt_{index:02d}', path_test(path))


class CallerEvidence(RunCase):
    def test_a21_missing_caller_evidence_precedes_missing_episode(self):
        self.f.open()
        self.refusal('hash_mismatch', lambda: self.f.close(evidence=[
            {'path': 'evidence/missing', 'sha256': 'a' * 64}]))

    def test_a21_changed_caller_evidence_precedes_memory(self):
        self.f.open()
        receipt = self.f.receipt()
        (self.f.home / receipt['path']).write_bytes(b'changed')
        self.refusal('hash_mismatch', lambda: self.f.close(evidence=[receipt]))

    def test_a21_caller_evidence_is_not_a_memory_receipt(self):
        self.f.open()
        receipt = self.f.receipt()
        self.refusal('memory_required', lambda: self.f.close(evidence=[receipt]))
        self.f.put(self.f.unit(level=2))
        self.refusal('memory_debt', lambda: self.f.close(evidence=[receipt]))

    def test_a21_caller_nonregular_is_hash_mismatch(self):
        self.f.open()
        (self.f.home / 'evidence').mkdir(exist_ok=True)
        self.refusal('hash_mismatch', lambda: self.f.close(evidence=[
            {'path': 'evidence', 'sha256': 'a' * 64}]))

    def test_a21_owner_precedes_caller_evidence(self):
        self.f.open()
        self.refusal('bad_args', lambda: self.f.close(actor=OTHER, evidence=[
            {'path': 'evidence/missing', 'sha256': 'a' * 64}]), 'actor_mismatch')


def caller_path_test(path):
    def test(self):
        self.f.open()
        self.refusal('bad_args', lambda: self.f.close(evidence=[{'path': path, 'sha256': 'a' * 64}]))
    return test


for index, path in enumerate(UNSAFE):
    setattr(CallerEvidence, f'test_a21_unsafe_caller_{index:02d}', caller_path_test(path))
