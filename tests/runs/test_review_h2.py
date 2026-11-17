"""h2 regression coverage for postcommit projection publication and recovery."""
# A-U13: Add regressions; retain every frozen behavioral assertion.
from copy import deepcopy
from unittest import mock

from lineage.core import journal, registry, schema
from lineage.core.errors import LineageError
from lineage.domain import agents, layout, runs, scorecard
from tests.runs.support import RunCase, OWNER, RUN, OUTCOME, COST


class ReviewH2(RunCase):
    def ready(self):
        self.f.open()
        self.f.witness()
        return self.f.command('run_close',
            {'run_id': RUN, 'outcome': deepcopy(OUTCOME), 'cost': deepcopy(COST)},
            op_id='h2:/close.retained')

    def scorecard(self):
        agent = self.f.agent()
        directory = layout.agent_dir(self.f.home, workflow=agent['workflow'],
                                     language=agent['language'], agent_id=OWNER)
        return directory / 'scorecard.json'

    def test_a40_discovery_does_not_invalidate_fixture_projections(self):
        registry.load()
        report = journal.verify(self.f.home)
        self.assertTrue(report['ok'], report['errors'])
        self.assertEqual(report['head'], len(self.f.events()))

    def test_a34_close_publishes_scorecard_after_durability(self):
        registry.load()
        command = self.ready()
        previous = self.scorecard().read_bytes()
        original = agents.refresh_projections
        seen = []
        def publish(agent_id, *, ctx):
            history = journal.snapshot(self.f.home)
            self.assertEqual(history[-1]['kind'], 'run.close')
            self.assertEqual(history[-1]['op_id'], command.op_id)
            seen.append(agent_id)
            return original(agent_id, ctx=ctx)
        with mock.patch.object(agents, 'refresh_projections', side_effect=publish):
            result = self.f.close(command=command)
        self.closed(result)
        self.assertEqual(seen, [OWNER])
        current = self.scorecard().read_bytes()
        self.assertNotEqual(current, previous)
        self.assertEqual(current, scorecard.projection_bytes(self.f.events(), agent_id=OWNER))
        self.assertEqual(schema.strict_loads(current)['groups'][0]['runs'], 1)
        self.assertEqual(result.event['op_id'], command.op_id)

    def test_a34_projection_failure_retains_close_and_exact_retry_recovers(self):
        registry.load()
        command = self.ready()
        before = self.f.events()
        with mock.patch.object(agents, 'refresh_projections', side_effect=OSError('publisher fault')):
            with self.assertRaises(LineageError) as caught:
                self.f.close(command=command)
        self.assertEqual(caught.exception.code, 'internal')
        durable = self.f.events()
        self.assertEqual(len(durable), len(before) + 1)
        self.assertEqual(durable[-1]['kind'], 'run.close')
        self.assertEqual(durable[-1]['op_id'], command.op_id)
        self.assertIsNotNone(runs.get(RUN, ctx=self.f.context())['closed'])
        raw = self.f.raw()
        with mock.patch('lineage.domain.gate_close.check', side_effect=AssertionError('replayed gate')):
            result = self.f.close(command=command)
        self.closed(result)
        self.assertEqual(result.event, durable[-1])
        self.assertEqual(self.f.raw(), raw)

    def test_a25_exact_retry_repairs_projection_without_new_event(self):
        registry.load()
        command = self.ready()
        committed = self.f.close(command=command)
        raw = self.f.raw()
        self.scorecard().write_bytes(b'[]')
        self.assertFalse(journal.verify(self.f.home)['ok'])
        with mock.patch('lineage.domain.gate_close.check', side_effect=AssertionError('replayed gate')):
            recovered = self.f.close(command=command)
        self.assertEqual(recovered.value, committed.value)
        self.assertEqual(recovered.event, committed.event)
        self.assertEqual(self.f.raw(), raw)
        self.closed(recovered)
