"""Operation identity, original-prefix results, and revision ordering."""
from copy import deepcopy
from dataclasses import replace
from unittest import mock

from lineage.core import journal
from lineage.domain import gate_close, runs
from tests.runs.support import RunCase, OWNER, RUN, SEAT, TASK, OUTCOME, COST, canonical


class Replay(RunCase):
    def test_a05_exact_open_retry_returns_original_commit(self):
        args = {'run_id': RUN, 'agent_id': OWNER, 'seat': SEAT, 'task': TASK,
                'parents_context': [], 'memory_arm': 'own'}
        command = self.f.command('run_open', args)
        original = self.f.open(command=command)
        before = self.f.raw()
        self.assertEqual(canonical(self.f.open(command=command).value), canonical(original.value))
        self.assertEqual(self.f.raw(), before)

    def test_a25_replays_precede_later_closure_retirement_and_clock(self):
        open_args = {'run_id': RUN, 'agent_id': OWNER, 'seat': SEAT, 'task': TASK,
                     'parents_context': [], 'memory_arm': 'own'}
        open_command = self.f.command('run_open', open_args)
        opened = self.f.open(command=open_command)
        beat_command = self.f.command('run_beat', {'run_id': RUN, 'progress': 'Working'})
        beat = self.f.beat(command=beat_command)
        self.f.witness()
        close_command = self.f.command('run_close', {'run_id': RUN, 'outcome': OUTCOME, 'cost': COST})
        closed = self.f.close(command=close_command)
        self.f.retire()
        self.f.clock_value = 0
        before = self.f.raw()
        with mock.patch.object(gate_close, 'check', side_effect=AssertionError('replay rechecked gate')):
            retried = (self.f.open(command=replace(open_command, expected_head=0)),
                       self.f.beat(command=replace(beat_command, expected_head=0)),
                       self.f.close(command=replace(close_command, expected_head=0)))
        for expected, actual in zip((opened, beat, closed), retried):
            self.assertEqual(canonical(actual.value), canonical(expected.value))
            self.assertEqual(actual.head, expected.head)
            self.assertEqual(actual.sha256, expected.sha256)
        self.assertEqual(self.f.raw(), before)

    def test_a26_changed_open_content_is_bad_op(self):
        args = {'run_id': RUN, 'agent_id': OWNER, 'seat': SEAT, 'task': TASK,
                'parents_context': [], 'memory_arm': 'own'}
        command = self.f.command('run_open', args)
        self.f.open(command=command)
        modified = deepcopy(command.args)
        modified['seat']['effort'] = 'high'
        self.refusal('bad_op', lambda: self.f.open(seat=modified['seat'],
                     command=replace(command, args=modified)))

    def test_a26_changed_tool_and_progress_is_bad_op(self):
        self.f.open()
        command = self.f.command('run_beat', {'run_id': RUN, 'progress': 'Working'})
        self.f.beat(command=command)
        modified = {**command.args, 'progress': 'Different'}
        self.refusal('bad_op', lambda: self.f.beat('Different', command=replace(command, args=modified)))
        other = self.f.command('run_close', {'run_id': RUN, 'outcome': OUTCOME, 'cost': COST},
                               op_id=command.op_id)
        self.refusal('bad_op', lambda: self.f.close(command=other))

    def test_a26_default_and_explicit_empty_evidence_replay(self):
        self.f.open()
        self.f.witness()
        command = self.f.command('run_close', {'run_id': RUN, 'outcome': OUTCOME, 'cost': COST})
        original = self.f.close(command=command)
        explicit = replace(command, args={**command.args, 'evidence': []})
        before = self.f.raw()
        self.assertEqual(self.f.close(evidence=[], command=explicit).value, original.value)
        self.assertEqual(self.f.raw(), before)

    def test_a27_revision_after_replay_and_under_lock(self):
        self.f.open()
        command = self.f.command('run_beat', {'run_id': RUN, 'progress': 'Working'}, expected_head=0)
        self.refusal('stale_rev', lambda: self.f.beat(command=command))
        current = replace(command, expected_head=self.f.events()[-1]['lamport'])
        original = self.f.beat(command=current)
        before = self.f.raw()
        self.assertEqual(self.f.beat(command=command).value, original.value)
        self.assertEqual(self.f.raw(), before)

    def test_a32_memory_survives_new_fixture_before_close(self):
        from tests.runs.support import Fixture
        self.f.open()
        self.f.witness()
        reopened = Fixture(self.f.home, seed=False)
        reopened.services.id_factory = lambda: 'e-aaaaaaaaaaaaaaaa'
        self.assertIsNone(runs.get(RUN, ctx=reopened.context())['closed'])
        self.closed(reopened.close())

    def test_a35_tamper_is_not_empty_history(self):
        self.f.open()
        self.f.witness()
        path = self.f.home / 'ledger/main/events.jsonl'
        original = path.read_bytes()
        path.write_bytes(original.replace(b'constitution', b'constitutioN', 1))
        self.refusal('hash_mismatch', self.f.close)

    def test_a35_torn_suffix_is_not_a_witness(self):
        self.f.open()
        path = self.f.home / 'ledger/main/events.jsonl'
        with path.open('ab') as stream:
            stream.write(b'{"kind":"memory.put"')
        self.refusal('memory_required', self.f.close)
        self.f.witness()
        self.closed(self.f.close())


def changed_close_test(field):
    def test(self):
        self.f.open()
        self.f.witness()
        command = self.f.command('run_close', {'run_id': RUN, 'outcome': OUTCOME, 'cost': COST})
        self.f.close(command=command)
        args = deepcopy(command.args)
        kwargs = {}
        if field == 'outcome':
            args['outcome']['verdict'] = 'ADMIT'
            kwargs['verdict'] = args['outcome']
        elif field == 'cost':
            args['cost']['tokens_in'] = 0
            kwargs['cost'] = args['cost']
        elif field == 'run_id':
            args['run_id'] = 'other001'
            kwargs['run_id'] = args['run_id']
        else:
            args['evidence'] = [self.f.receipt()]
            kwargs['evidence'] = args['evidence']
        self.refusal('bad_op', lambda: self.f.close(command=replace(command, args=args), **kwargs))
    return test


for field in ('outcome', 'cost', 'run_id', 'evidence'):
    setattr(Replay, 'test_a26_changed_close_' + field, changed_close_test(field))
