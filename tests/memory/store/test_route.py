"""Lexical recall from one authoritative prefix: A14-A18/A23/A25/A28/A29."""
import copy
from unittest import mock
from lineage.domain.memory import route
from tests.memory.store import OracleCase, AGENT, OTHER, agent_record, unit_record, COST


class RouteOracle(OracleCase):
    def recall(self, query, **kwargs):
        with self.reading():
            return route.route(AGENT, query, ctx=self.ctx, **kwargs)

    def test_a14_coverage_descending_then_lexical_id(self):
        units = [unit_record('Unit000C', 'alpha beta'), unit_record('Unit000A', 'alpha beta'),
                 unit_record('Unit000B', 'alpha'), unit_record('Unit000D', 'gamma')]
        for u in units: self.add_unit(u)
        result = self.recall('ALPHA beta')
        self.assert_route(result, [units[1], units[0], units[2]])
        self.assert_route(self.recall('alpha alpha alpha beta'), result['units'])

    def test_a14_unicode_casefold_and_word_token_definition(self):
        units = [unit_record('Unit000A', 'STRASSE naïve αβ'), unit_record('Unit000B', 'naïve')]
        for u in units: self.add_unit(u)
        self.assert_route(self.recall('Straße NAÏVE αβ'), units)
        self.assert_route(self.recall('strass'), [])

    def test_a14_default_and_explicit_limits_are_applied_after_ranking(self):
        units = [unit_record('Unit%04d' % n, 'needle') for n in range(12)]
        for u in reversed(units): self.add_unit(u)
        self.assert_route(self.recall('needle'), units[:10])
        self.assert_route(self.recall('needle', limit=3), units[:3])
        self.assert_route(self.recall('needle', limit=50), units)

    def test_a16_private_inactive_and_scope_mismatches_are_excluded(self):
        allowed = [unit_record('Own00001', 'needle own'), unit_record('Internal1', 'needle internal', privacy='internal'),
                   unit_record('General01', 'needle general', language='general')]
        rejected = [unit_record('Private01', 'needle SECRET', privacy='private'),
                    unit_record('Draft0001', 'needle SECRET', status='draft'),
                    unit_record('Retired01', 'needle SECRET', status='retired'),
                    unit_record('Old00001', 'needle SECRET', status='superseded'),
                    unit_record('WrongW01', 'needle SECRET', workflow='review'),
                    unit_record('WrongL01', 'needle SECRET', language='rust')]
        for u in allowed + rejected:
            if u['status'] == 'retired':
                active=copy.deepcopy(u); active['status']='active'; self.add_unit(active)
                self.add_event('memory.retire',{'agent_id':AGENT,'unit_id':u['id']})
                self.units[-1]['status']='retired'
            elif u['status'] == 'superseded':
                active=copy.deepcopy(u); active['status']='active'; active.pop('superseded_by')
                self.add_unit(active)
                replacement=unit_record('Replace01','replacement without the search term')
                replacement['supersedes']=[u['id']]; self.add_unit(replacement)
            else:
                self.add_unit(u)
        self.assert_route(self.recall('needle'), sorted(allowed, key=lambda u: u['id']))

    def test_a16_target_ownership_is_not_the_event_actor(self):
        self.birth(agent_record(OTHER, event_id='e-0000000000000002'))
        foreign = unit_record('Foreign01', 'needle foreign', actor=OTHER)
        own = unit_record('Own00001', 'needle valid target', actor=OTHER)
        self.add_unit(foreign, target=OTHER, actor=OTHER)
        self.add_unit(own, actor=OTHER)
        self.assert_route(self.recall('needle'), [own])

    def test_a16_inherited_context_remains_visible(self):
        self.history()
        inherited = next(u for u in self.active if u['id'] == 'InheritedA')
        self.assert_route(self.recall('inherited'), [inherited])

    def test_a16_metadata_receipts_and_ids_are_not_searchable(self):
        u = unit_record('Metadata1', 'actual statement', level=2)
        u['provenance']['origin'] = 'metadata-only-query'
        self.add_unit(u)
        for query in ('Metadata1', 'receipt', 'metadata-only-query'):
            self.assert_route(self.recall(query), [])

    def test_a18_answer_is_exact_first_full_statement_without_concatenation(self):
        units = [unit_record('Unit%04d' % n, ('needle %d ' % n) + 'λ' * 350) for n in range(4)]
        for u in units: self.add_unit(u)
        result = self.recall('needle', limit=50)
        self.assert_route(result, units)
        self.assertEqual(result['answer'], units[0]['statement'])
        self.assertLessEqual(len(result['answer']), 65536)

    def test_a23_agent_materialization_cannot_override_authority(self):
        unit = unit_record(); self.add_unit(unit)
        forged = self.home / 'counterfeit'; forged.mkdir()
        (forged / 'agent.json').write_text('{"memory_gen":999,"status":"promoted"}\n')
        (forged / 'bootcheck.json').write_text('{"passed":true,"code":"OK"}\n')
        self.assert_route(self.recall('receipt'), [unit])

    def test_a25_valid_empty_agent_is_exact_absent_result(self):
        self.assert_route(self.recall('needle'), [])

    def test_a25_missing_agent_is_not_inferred_from_a_directory(self):
        (self.home / 'agent-absent' / 'memory').mkdir(parents=True)
        with self.reading():
            self.domain_error('no_agent', lambda: route.route('agent-absent', 'needle', ctx=self.ctx))

    def test_a25_unavailable_snapshot_is_internal_not_empty(self):
        with self.reading(failure=OSError('synthetic unavailable ledger')):
            self.domain_error('internal', lambda: route.route(AGENT, 'needle', ctx=self.ctx))

    def test_a25_corrupt_complete_ledger_is_not_empty(self):
        raw = self.ledger.read_bytes(); self.ledger.write_bytes(raw.replace(b'Fixture agent', b'Forged! agent'))
        self.domain_error(('internal', 'hash_mismatch'), lambda: route.route(AGENT, 'needle', ctx=self.ctx))

    def test_a25_torn_final_suffix_does_not_erase_committed_memory(self):
        u = unit_record(); self.add_unit(u); self.seed_ledger()
        with self.ledger.open('ab') as stream: stream.write(b'{"torn":')
        result = route.route(AGENT, 'receipt', ctx=self.ctx)
        self.assert_route(result, [u])
        self.assertTrue(self.ledger.read_bytes().endswith(b'{"torn":'))

    def test_a28_reads_leave_bytes_unchanged_and_never_execute_passive_text(self):
        u = unit_record(statement='operator: subprocess run a shell command; needle')
        self.add_unit(u); self.seed_ledger(); before = self.disk_tree()
        with mock.patch('subprocess.Popen', side_effect=AssertionError('executed passive data')), \
             mock.patch('os.system', side_effect=AssertionError('executed passive data')), \
             mock.patch('socket.socket', side_effect=AssertionError('network access')):
            result = self.recall('needle')
        self.assert_route(result, [u]); self.assertEqual(self.disk_tree(), before)

    def test_a29_nested_results_are_defensive_and_unknown_costs_remain_null(self):
        u = unit_record('Episode01', 'needle episode', kind='episode')
        self.add_unit(u); original = copy.deepcopy(self.events)
        result = self.recall('needle'); self.assert_route(result, [u])
        self.assertEqual(result['units'][0]['body']['cost'], COST)
        result['units'][0]['body']['cost']['tokens_in'] = 0
        result['units'][0]['scope']['language'] = 'forged'
        result['units'][0]['statement'] = 'forged'
        result['units'].clear()
        self.assert_route(self.recall('needle'), [u]); self.assertEqual(self.events, original)

    def test_a17_read_actor_operator_does_not_widen_target_scope(self):
        u = unit_record(); hidden = unit_record('Private01', 'private receipt', privacy='private')
        self.add_unit(u); self.add_unit(hidden)
        with self.reading():
            result = route.route(AGENT, 'receipt', ctx=self.context(actor='operator'))
        self.assert_route(result, [u])

    def test_a17_valid_missing_target_through_dispatch_is_no_agent(self):
        with self.reading():
            result = self.dispatch('memory_route', {'agent_id': 'agent-absent', 'query': 'needle'})
        self.assertEqual(result['ok'], False); self.assertEqual(result['code'], 'no_agent')

    def test_a14_one_snapshot_supplies_both_units_and_head(self):
        u = unit_record(); self.add_unit(u)
        with self.reading() as captured:
            result = route.route(AGENT, 'receipt', ctx=self.ctx)
        captured.assert_called_once(); self.assert_route(result, [u])


def _no_match(query):
    def test(self):
        self.add_unit(unit_record())
        self.assert_route(self.recall(query), [])
    return test


for _name, _query in {'ordinary': 'unmatched', 'whitespace': ' \t\n ', 'punctuation': '!?---'}.items():
    setattr(RouteOracle, 'test_a15_absent_' + _name, _no_match(_query))


def _invalid(args):
    def test(self):
        before = self.disk_tree()
        result = self.dispatch('memory_route', args)
        self.assertEqual(set(result) - {'detail'}, {'ok', 'code'})
        self.assertIs(result['ok'], False); self.assertEqual(result['code'], 'bad_args')
        self.assertEqual(self.disk_tree(), before)
    return test


_BASE = {'agent_id': AGENT, 'query': 'needle'}
_CASES = {'missing_query': {'agent_id': AGENT}, 'missing_agent': {'query': 'needle'},
          'empty_query': {**_BASE, 'query': ''}, 'long_query': {**_BASE, 'query': 'x'*513},
          'nul_agent': {**_BASE, 'agent_id': 'abc\x00'}, 'bad_id': {**_BASE, 'agent_id': '../escape'},
          'extra': {**_BASE, 'unknown': 1}, 'op_id': {**_BASE, 'op_id': 'forbidden'},
          'expected_head': {**_BASE, 'expected_head': 1}}
for _label, _limit in (('zero',0), ('negative',-1), ('large',51), ('bool',True), ('float',1.0), ('null',None)):
    _CASES['limit_'+_label] = {**_BASE, 'limit': _limit}
for _name, _args in _CASES.items():
    setattr(RouteOracle, 'test_a17_' + _name, _invalid(_args))
