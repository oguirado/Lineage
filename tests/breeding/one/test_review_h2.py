"""Real U17 admission, journal replay and projection repair regressions.

Source histories use the explicitly nominal fixtures in helpers. Child births
and retirements pass through the genuine context-bound U12 validators.
"""
from copy import deepcopy
import json
from unittest.mock import patch

from lineage.core import journal
from lineage.core.errors import LineageError
from lineage.domain import agents, layout
from lineage.domain.breeding import _birth_payload
from .helpers import OracleCase, canonical

# A-U17: use the integrated replay, layout and projection APIs; preserve all
# frozen admission assertions and keep fixture authority distinct from admission.


class ProjectionReplayRegression(OracleCase):
    def stage_birth(self):
        # A-U17: child births now use the actual context-bound U12 owner.
        self.seed(self.parent, units=[self.unit()])
        self.breed()
        return journal.snapshot(self.home)[-1]

    def child_directory(self):
        return layout.agent_dir(self.home, workflow=self.parent['workflow'],
                                language=self.parent['language'], agent_id='child-one')

    def test_replay_refresh_repairs_partial_projections_without_append(self):
        """Gate: canonical artifacts restored; contrast: stale or duplicate birth."""
        event = self.stage_birth()
        before = self.ledger_bytes()
        with patch.object(agents, 'refresh_projections', wraps=agents.refresh_projections) as refresh:
            first = self.breed()
            refresh.assert_called_once_with('child-one', ctx=self.ctx)
        directory = self.child_directory()
        originals = {name: (directory / name).read_bytes() for name in layout.PROJECTION_FILES}
        (directory / 'agent.json').write_bytes(b'partial fixture')
        (directory / 'BRIEF_HEAD.md').unlink()
        again = self.breed()
        self.assertEqual(canonical(again), canonical(first))
        self.assertEqual(again['commit'], {'event_ids': [event['id']],
                                         'head': event['lamport'], 'sha256': event['sha256']})
        self.assertEqual({name: (directory / name).read_bytes() for name in originals}, originals)
        self.assertEqual(self.ledger_bytes(), before)

    def test_retry_publishes_current_memory_but_returns_original_birth(self):
        """Gate: current projection/original Commit; contrast: projection regression."""
        self.stage_birth()
        first = self.breed()
        unit = self.unit('later001', statement='A later own-memory lesson')
        journal.transact(
            self.home, agent='child-one', op_id='later-memory-0001', kind='memory.put',
            payload={'agent_id': 'child-one', 'unit': deepcopy(unit)},
            validators={'memory.put': lambda history, event: None})
        before = self.ledger_bytes()
        again = self.breed(expected_head=0)
        self.assertEqual(canonical(again), canonical(first))
        state = agents._state(journal.snapshot(self.home), self.ctx)
        current = agents._record(state, 'child-one')
        self.assertGreater(current['memory_gen'], first['record']['memory_gen'])
        self.assertEqual(json.loads((self.child_directory() / 'agent.json').read_bytes()), current)
        self.assertEqual(self.ledger_bytes(), before)

    def test_failed_replay_publication_leaves_history_and_retry_repairs(self):
        """Gate: durable prefix and repair; contrast: duplicate event or partial success."""
        event = self.stage_birth()
        original = agents.refresh_projections
        damaged = []

        def fail_after_publication(*args, **kwargs):
            paths = original(*args, **kwargs)
            target = next(path for path in paths if path.name == 'agent.json')
            damaged.append((target, target.read_bytes()))
            target.unlink()
            raise OSError('Fixture publication failure')

        before = self.ledger_bytes()
        with patch.object(agents, 'refresh_projections', side_effect=fail_after_publication):
            with self.assertRaises(LineageError) as caught:
                self.breed()
        self.assertEqual(caught.exception.code, 'internal')
        self.assertEqual(self.ledger_bytes(), before)
        self.assertEqual(len(damaged), 1)
        self.assertFalse(damaged[0][0].exists())
        again = self.breed()
        self.assertEqual(damaged[0][0].read_bytes(), damaged[0][1])
        self.assertEqual(again['commit']['event_ids'], [event['id']])
        self.assertEqual(self.ledger_bytes(), before)


    def test_valid_bare_birth_uses_registered_owner_with_runtime_context(self):
        """Gate: valid direct admission; contrast: a refusal-only callback."""
        self.seed(self.parent, units=[self.unit()])
        event = journal.transact(
            self.home, agent='creator-one', op_id='bare-live-birth-0001',
            kind='agent.born', payload={}, validators=self.admission_validators(),
            prepare=lambda history, draft: _birth_payload(
                history, parent_id='parent-one', child_id='child-one', op='clone',
                display_name=None, selected_ids=None, event_id=draft['id'], ctx=self.ctx))
        self.assertEqual(event['payload']['record']['born']['event_id'], event['id'])
        self.assertEqual(journal.snapshot(self.home)[-1], event)
        self.assertEqual(event['payload']['inherited_units'][0]['source_agent_id'], 'parent-one')
        self.assertEqual(event['payload']['inherited_units'][0]['source_unit_id'], 'unit0001')
