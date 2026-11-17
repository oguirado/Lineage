"""Run-schema records, full seat identity and null-aware public aggregates."""
from lineage.domain import scorecard
from tests.ledger._support import LedgerCase


class ScorecardTests(LedgerCase):
    def test_no_agent_and_unused_agent(self):
        self.assertEqual(self.dispatch('scorecard_get', {'agent_id': 'agent-one'}).payload['code'], 'no_agent')
        self.assertEqual(self.cli('scorecard_get', {'agent_id': 'agent-one'}, 3)['code'], 'no_agent')
        self.birth()
        expected = {'agent_id': 'agent-one', 'groups': [], 'head': 1}
        self.assertEqual(self.data('scorecard_get', {'agent_id': 'agent-one', 'agent': 'caller'}), expected)
        self.check_result('scorecard_get', expected)

    def test_payload_record_grouping_means_and_unknowns_dispatch_and_cli(self):
        self.birth()
        self.close(cost={'cost_micro_usd': 10, 'duration_ms': 100})
        self.close(cost={'cost_micro_usd': 20}, verdict='HOLD')
        self.close()
        self.close(arm='none')
        self.close(seat={'model': 'fixture', 'effort': 'different', 'mode': 'headless'})
        result = self.data('scorecard_get', {'agent_id': 'agent-one'})
        self.check_result('scorecard_get', result)
        self.assertEqual(len(result['groups']), 3)
        group = next(g for g in result['groups'] if g['memory_arm'] == 'own'
                     and g['seat']['effort'] == 'custom_effort')
        self.assertEqual(group, {'seat': {'model': 'fixture', 'effort': 'custom_effort', 'mode': 'headless'},
                                 'memory_arm': 'own', 'runs': 3, 'successes': 2,
                                 'unknown_costs': 1, 'mean_cost_micro_usd': 15.0,
                                 'mean_duration_ms': 100.0})
        unknown = next(g for g in result['groups'] if g['memory_arm'] == 'none')
        self.assertIsNone(unknown['mean_cost_micro_usd'])
        self.assertIsNone(unknown['mean_duration_ms'])
        self.assertEqual(self.cli('scorecard_get', {'agent_id': 'agent-one', 'agent': 'caller'}), {'untrusted': result})

    def test_totals_larger_than_safe_integer_use_public_means(self):
        self.birth()
        for _ in range(3):
            self.close(cost={'cost_micro_usd': 9007199254740991,
                             'duration_ms': 9007199254740991})
        result = self.data('scorecard_get', {'agent_id': 'agent-one'})
        self.check_result('scorecard_get', result)
        self.assertEqual(result['groups'][0]['mean_cost_micro_usd'], 9007199254740991)
        self.assertEqual(self.cli('scorecard_get', {'agent_id': 'agent-one'}), {'untrusted': result})

    def test_opaque_seat_strings_are_not_normalized_or_restricted(self):
        self.assertIsNone(scorecard._seat({'model': 'fixture', 'effort': 'opaque effort', 'mode': 'opaque mode'}))

    def test_removed_filters_are_rejected(self):
        for key, value in [('seat', {}), ('memory_arm', 'own')]:
            args = {'agent_id': 'agent-one', key: value}
            self.assertEqual(self.dispatch('scorecard_get', args).payload['code'], 'bad_args')
            self.assertEqual(self.cli('scorecard_get', args, 2)['code'], 'bad_args')
