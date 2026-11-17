"""Capacity refusals must precede run-close durability and projection writes."""
from types import SimpleNamespace
from unittest import mock

from lineage.domain import agents, runs
from lineage.domain.memory import entry, fold
from lineage.ext.ledger import ledger_verify
from tests.runs.support import RunCase, OWNER, RUN, SEAT, TASK, OUTCOME, COST, canonical


class TokenDebt(RunCase):
    def ready(self, size):
        self.f.open()
        unit = self.f.unit()
        unit['statement'] = 'x'
        base = entry.build(self.f.agent(), [unit], token_count=lambda text: 1)
        padding = size - len(base)
        self.assertGreaterEqual(padding, 0)
        unit['statement'] += 'é' * (padding // 2) + 'x' * (padding % 2)
        self.assertLessEqual(len(canonical(unit)), 6000)
        if size <= 6000:
            raw = entry.build(self.f.agent(), [unit], token_count=lambda text: 1)
            self.assertEqual(len(raw), size)
        self.f.put(unit)
        return unit

    def assert_debt_before_append(self):
        with mock.patch.object(agents, 'refresh_projections') as refresh:
            self.refusal('memory_debt', self.f.close)
        refresh.assert_not_called()
        self.assertIsNone(runs.get(RUN, ctx=self.f.context())['closed'])
        report = ledger_verify({}, context=self.f.context())
        self.assertTrue(report['valid'])
        self.assertEqual(report['head'], len(self.f.events()))
        self.assertEqual(report['issues'], [])

    def test_missing_counter_refuses_above_proven_byte_bound(self):
        self.ready(4001)
        self.assertIsNone(self.f.services.token_count)
        self.assert_debt_before_append()

    def test_exact_proven_byte_bound_closes_without_counter(self):
        self.ready(4000)
        self.closed(self.f.close())
        self.assertTrue(ledger_verify({}, context=self.f.context())['valid'])

    def test_injected_counter_is_used_before_commit_and_for_refresh(self):
        self.ready(4500)
        phases = []

        def count(text):
            if len(text.encode('utf-8')) == 4500:
                phases.append(b'"kind":"run.close"' in self.f.raw())
            return 4000

        self.f.services.token_count = count
        self.closed(self.f.close())
        self.assertIn(False, phases)
        self.assertIn(True, phases)
        self.assertTrue(ledger_verify({}, context=self.f.context())['valid'])

    def test_over_limit_counter_refuses_before_append(self):
        self.ready(4500)
        self.f.services.token_count = lambda text: 4001
        self.assert_debt_before_append()

    def test_byte_overflow_refuses_even_with_counter(self):
        self.ready(6001)
        self.f.services.token_count = lambda text: 1
        self.assert_debt_before_append()

    def test_oversized_historical_generation_refuses_before_append(self):
        previous = self.ready(4500)
        replacement = self.f.unit(identifier='episode2')
        replacement['supersedes'] = [previous['id']]
        self.f.put(replacement)
        snapshot = self.f.snapshot()
        active = fold.units_for(snapshot.state, OWNER)
        self.assertLess(len(entry.build(self.f.agent(), active, token_count=None)), 4000)
        self.assert_debt_before_append()

    def test_native_context_preserves_injected_counter_and_operation_id(self):
        self.ready(4500)
        counter = mock.Mock(return_value=4000)
        command = self.f.command('run_close',
            {'run_id': RUN, 'outcome': OUTCOME, 'cost': COST},
            op_id='close:/token.debt-2')
        context = SimpleNamespace(home=self.f.home, validators=self.f.registry.validators,
            folds=self.f.registry.folds, actor=OWNER, op_id=command.op_id,
            token_count=counter)
        committed = runs.close(RUN, OUTCOME, COST, command=command, ctx=context)
        self.closed(committed)
        self.assertEqual(committed.event['op_id'], command.op_id)
        self.assertTrue(counter.called)

    def test_disallowed_seat_reports_contract_error_before_context_actor(self):
        args = {'run_id': RUN, 'agent_id': OWNER, 'seat': {**SEAT, 'effort': 'high'},
                'task': TASK, 'parents_context': [], 'memory_arm': 'own'}
        command = self.f.command('run_open', args)
        self.refusal('seat_not_allowed', lambda: runs.open_run(RUN, OWNER,
            args['seat'], TASK, parents_context=[], memory_arm='own',
            command=command, ctx=self.f.context('system')))
