"""Lifecycle, frozen identity, read authority, and exact refusal precedence."""
from copy import deepcopy
from dataclasses import replace
from unittest import mock

from lineage.core import journal
from lineage.domain import runs
from tests.runs.support import (RunCase, OWNER, OTHER, RUN, SEAT, TASK, COST,
                               OUTCOME, canonical, version, validate_record)


class Lifecycle(RunCase):
    def test_a03_open_get_freezes_authoritative_identity(self):
        agent = self.f.agent()
        committed = self.f.open()
        self.assertEqual(set(committed.value), {'opened', 'commit'})
        opening = committed.event
        validate_record(opening, 'event.schema.json')
        self.assertEqual(committed.value['opened'], opening)
        self.assertEqual(opening['payload'], {'run_id': RUN, 'agent_id': OWNER,
            'agent_version': agent['agent_version'], 'seat': SEAT, 'task': TASK,
            'parents_context': [], 'memory_arm': 'own'})
        self.assertEqual(runs.get(RUN, ctx=self.f.context(OTHER)),
            {'opened': opening, 'closed': None, 'head': opening['lamport']})
        self.assertEqual(committed.value['commit'], {'event_ids': [opening['id']],
            'head': opening['lamport'], 'sha256': opening['sha256']})

    def test_a03_benchmark_task_preserved_together(self):
        task = {**TASK, 'bank_id': 'bank-one', 'bench_id': 'bench001', 'split': 'heldout'}
        opened = self.f.open(task=task)
        self.assertEqual(opened.event['payload']['task'], task)


    def test_a03_parent_context_is_shape_only_and_preserves_order(self):
        parents = [{'agent_id': OTHER, 'agent_version': 'a' * 64, 'run_id': 'parent01'},
                   {'agent_id': OWNER, 'agent_version': 'b' * 64, 'run_id': 'parent02'}]
        opening = self.f.open(parents=parents, arm='inherited').event
        self.assertEqual(opening['payload']['parents_context'], parents)
        self.assertEqual(opening['payload']['memory_arm'], 'inherited')

    def test_a04_unknown_agent(self):
        self.refusal('no_agent', lambda: self.f.open(agent_id='unknown-agent'))

    def test_a04_retired_agent_cannot_open(self):
        self.f.retire()
        self.refusal('conflict', self.f.open)

    def test_a04_complete_seat_admission(self):
        for field, value in (('model', 'other-model'), ('effort', 'high'), ('mode', 'interactive')):
            with self.subTest(field=field):
                self.refusal('seat_not_allowed', lambda: self.f.open(seat={**SEAT, field: value}))
        self.f.open()

    def test_a04_version_integrity_recomputed(self):
        # Controlled historical corruption with a valid outer chain isolates the version gate.
        record = self.f.agent()
        record['agent_version'] = 'f' * 64
        self.f.append_peer('agent.born', {'record': record, 'constitution': {
            'text': 'constitution\n', 'overlays': [], 'rule_ids': []},
            'inherited_units': [], 'rejected_units': []})
        self.refusal('hash_mismatch', self.f.open)

    def test_a05_distinct_open_cannot_reuse_global_id(self):
        original = self.f.open().event
        self.refusal('conflict', self.f.open)
        self.refusal('conflict', lambda: self.f.open(agent_id=OTHER))
        self.assertEqual(runs.get(RUN, ctx=self.f.context())['opened'], original)

    def test_a06_open_actor_spoofing(self):
        for actor in (OTHER, 'operator', 'system'):
            with self.subTest(actor=actor):
                self.refusal('bad_args', lambda: self.f.open(actor=actor), 'actor_mismatch')

    def test_a06_reserved_subject_is_not_an_agent(self):
        for actor in ('operator', 'system'):
            with self.subTest(actor=actor):
                self.refusal('no_agent', lambda: self.f.open(agent_id=actor, actor=actor))

    def test_a06_unknown_run_precedes_actor(self):
        self.refusal('no_run', lambda: self.f.beat(actor=OTHER))
        self.refusal('no_run', lambda: self.f.close(actor=OTHER))
        self.refusal('no_run', lambda: runs.get(RUN, ctx=self.f.context(OTHER)))

    def test_a06_owner_required_for_beat_and_close(self):
        self.f.open()
        for actor in (OTHER, 'operator', 'system'):
            with self.subTest(actor=actor):
                self.refusal('bad_args', lambda: self.f.beat(actor=actor), 'actor_mismatch')
                self.refusal('bad_args', lambda: self.f.close(actor=actor), 'actor_mismatch')

    def test_a06_command_context_actor_mismatch(self):
        args = {'run_id': RUN, 'agent_id': OWNER, 'seat': SEAT, 'task': TASK,
                'parents_context': [], 'memory_arm': 'own'}
        command = self.f.command('run_open', args, actor=OTHER)
        self.refusal('bad_args', lambda: runs.open_run(RUN, OWNER, SEAT, TASK,
            parents_context=[], memory_arm='own', command=command,
            ctx=self.f.context(OWNER, command.op_id)), 'actor_mismatch')

    def test_a07_owner_heartbeat_only_changes_runs(self):
        opening = self.f.open().event
        agent = self.f.agent()
        committed = self.f.beat('雪 café')
        validate_record(committed.event, 'event.schema.json')
        self.assertEqual(set(committed.value), {'event', 'commit'})
        self.assertEqual(committed.event['payload'], {'run_id': RUN, 'agent_id': OWNER,
                                                   'progress': '雪 café'})
        self.assertEqual(committed.event['lamport'], opening['lamport'] + 1)
        self.assertEqual(self.f.agent(), agent)
        self.assertEqual(runs.get(RUN, ctx=self.f.context())['opened'], opening)
        self.refusal('memory_required', self.f.close)

    def test_a07_invalid_heartbeat_progress(self):
        self.f.open()
        for progress in ('', 'x' * 2049, None, 1, True):
            with self.subTest(progress=repr(progress)[:30]):
                self.refusal('bad_args', lambda: self.f.beat(progress))
        self.f.beat('雪' * 2048)

    def test_a07_retired_open_run_accepts_heartbeat(self):
        self.f.open()
        self.f.retire()
        self.f.beat()
        self.refusal('conflict', self.f.close)

    def test_a07_closed_precedes_retired_but_not_actor_mismatch(self):
        self.f.open()
        self.f.witness()
        self.closed(self.f.close())
        self.f.retire()
        self.refusal('bad_args', lambda: self.f.beat(actor=OTHER), 'actor_mismatch')
        self.refusal('bad_args', lambda: self.f.close(actor=OTHER), 'actor_mismatch')
        self.refusal('run_closed', self.f.beat)
        self.refusal('run_closed', self.f.close)

    def test_a08_opening_version_survives_memory_generation(self):
        opening = self.f.open().event
        receipt = self.f.receipt()
        self.f.put(self.f.unit('lesson', identifier='lesson01', level=2, receipts=[receipt]))
        self.assertNotEqual(self.f.agent()['agent_version'], opening['payload']['agent_version'])
        self.f.witness()
        before = self.f.events()
        record = self.closed(self.f.close())
        for key in ('agent_id', 'agent_version', 'seat', 'task', 'parents_context', 'memory_arm'):
            self.assertEqual(record[key], opening['payload'][key])
        self.assertEqual(record['ts_open'], opening['ts'])
        self.assertEqual([e['kind'] for e in self.f.events()[len(before):]], ['run.close'])

    def test_a09_get_is_defensive_read_only_and_rebuildable(self):
        opening = self.f.open().event
        before = self.f.raw()
        first = runs.get(RUN, ctx=self.f.context(OTHER))
        first['opened']['payload']['seat']['model'] = 'forged'
        self.assertEqual(runs.get(RUN, ctx=self.f.context())['opened'], opening)
        state = self.f.snapshot().state
        state['runs'].clear()
        self.assertEqual(runs.get(RUN, ctx=self.f.context())['opened'], opening)
        projection = self.f.home / 'agents' / OWNER / 'agent.json'
        projection.parent.mkdir(parents=True, exist_ok=True)
        projection.write_bytes(b'{"status":"retired","fake":"projection"}')
        self.assertEqual(runs.get(RUN, ctx=self.f.context())['opened'], opening)
        projection.unlink()
        self.assertEqual(self.f.raw(), before)

    def test_a09_missing_read_does_not_bootstrap_home(self):
        from tests.runs.support import Fixture
        fresh = Fixture(seed=False)
        self.addCleanup(fresh.cleanup)
        with self.assertRaises(Exception) as caught:
            runs.get(RUN, ctx=fresh.context())
        if isinstance(caught.exception, NotImplementedError):
            raise caught.exception
        self.assertEqual(caught.exception.code, 'no_run')
        self.assertFalse(fresh.home.exists())

    def test_a35_heartbeat_and_close_reject_regressing_clock(self):
        opening = self.f.open().event
        self.f.witness()
        self.f.clock_value = opening['ts'] - 1
        self.refusal('conflict', self.f.beat)
        self.refusal('conflict', self.f.close)

    def test_a39_fold_owns_only_runs(self):
        self.f.open()
        from lineage.ext import runs as extension
        sentinel = {'foreign': {'nested': [1, 2, 3]}}
        state = {'runs': {}, 'agents': deepcopy(sentinel), 'memory': deepcopy(sentinel),
                 'scorecards': deepcopy(sentinel), 'tree': deepcopy(sentinel)}
        before = deepcopy(state)
        for event in self.f.events():
            extension.FOLDS['runs'](state, deepcopy(event))
        for key in before.keys() - {'runs'}:
            self.assertEqual(state[key], before[key])
