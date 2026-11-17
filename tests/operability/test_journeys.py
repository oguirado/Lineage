"""Domain-witness boundaries use K0 wire records, never pixel completion."""
import copy
import hashlib

from tools.qa import journeys
from tests.operability.test_contract import OracleCase, canonical, walk

RUN='run_0001'
ACTOR='alpha-root'


def expected(**changes):
    value=dict(operation='Close run',tool='run_close',actor=ACTOR,op_id='close-1',
               kind='run.close',entity_id=None,run_id=RUN,expect='commit',code=None)
    value.update(changes)
    return value


def closed_run(verdict='green'):
    return dict(schema='lineage.run/v1',run_id=RUN,ts_open=0,ts_close=2,
                agent_id=ACTOR,agent_version='a'*64,
                seat=dict(model='offline-specimen',effort='medium',mode='headless'),
                task=dict(id='task_001',kind='selftest',language='python'),
                outcome=dict(verdict=verdict,repair_loops=0,findings=dict(confirmed=0,refuted=0)),
                cost=dict.fromkeys(('tokens_in','tokens_out','tokens_cache','duration_ms','cost_micro_usd')),
                memory=dict(unit_ids=['episode1'],levels=[3],gate_passed=True),
                evidence=[],parents_context=[],memory_arm='own')


def event(kind='run.close',lamport=2,payload=None,op_id='close-1',prev='0'*64):
    value=dict(schema='lineage.event/v1',id='e-'+format(lamport,'016x'),
               lamport=lamport,ts=lamport,ledger='main',agent=ACTOR,kind=kind,
               payload=payload if payload is not None else {'record':closed_run()},
               op_id=op_id,request_sha256='b'*64,evidence=[],prev_sha256=prev)
    value['sha256']=hashlib.sha256(canonical(value)).hexdigest()
    return value


def witness():
    run=closed_run()
    opened=event('run.open',1,{'run_id':RUN},'open-1')
    closed=event(prev=hashlib.sha256(canonical(opened)+b'\n').hexdigest())
    commit=dict(event_ids=[closed['id']],head=closed['lamport'],sha256=closed['sha256'])
    result={'untrusted':{'run':run,'commit':commit}}
    observed={'untrusted':{'opened':opened,'closed':copy.deepcopy(run),'head':2}}
    return result,[opened,closed],observed


class JourneyTests(OracleCase):
    def test_a26_valid_commit_and_corresponding_read_agree(self):
        result,events,observed=witness()
        value=journeys.check_postcondition(expected=expected(),result=result,events=events,observed=observed)
        self.verdict(value,'PASS')

    def test_a26_pixels_and_http_completion_are_not_witnesses(self):
        result,_,observed=witness()
        value=journeys.check_postcondition(expected=expected(),result=result,events=[],observed=observed)
        self.verdict(value,'FAIL','missing_witness')

    def test_a26_launch_acknowledgement_cannot_complete_a_run(self):
        value=journeys.check_postcondition(expected=expected(),
            result={'untrusted':{'state':'launched'}},events=[],observed={})
        self.assertNotIn('PASS',[x.get('status') for x in walk(value) if isinstance(x,dict)])

    def test_a26_semantic_error_is_not_successful_dispatch(self):
        result,events,observed=witness()
        result={'ok':False,'code':'memory_required'}
        value=journeys.check_postcondition(expected=expected(),result=result,events=events,observed=observed)
        self.verdict(value,'FAIL','semantic_mismatch')

    def test_a26_closed_read_without_matching_event_cannot_pass(self):
        result,events,observed=witness()
        events[-1]['op_id']='another-operation'
        value=journeys.check_postcondition(expected=expected(),result=result,events=events,observed=observed)
        self.verdict(value,'FAIL')

    def test_a28_refusal_with_no_prior_state_is_not_acceptance(self):
        value=journeys.check_postcondition(expected=expected(expect='refusal',code='memory_required'),
            result={'ok':False,'code':'memory_required'},events=[],observed={})
        self.assertNotIn('PASS',[x.get('status') for x in walk(value) if isinstance(x,dict)])

    def test_a28_distinct_memory_errors_are_not_interchangeable(self):
        value=journeys.check_postcondition(expected=expected(expect='refusal',code='memory_required'),
            result={'ok':False,'code':'memory_debt'},events=[],observed={})
        self.verdict(value,'FAIL','semantic_mismatch')

    def test_a29_operator_name_does_not_prove_level_one_authority(self):
        value=journeys.check_postcondition(
            expected=dict(operation='Write memory',tool='memory_put',actor='operator',
                          op_id='write-1',kind='memory.put',entity_id=ACTOR,
                          run_id=None,expect='refusal',code='forbidden_level'),
            result={'untrusted':{}},events=[],observed={})
        self.assertNotIn('PASS',[x.get('status') for x in walk(value) if isinstance(x,dict)])

    def test_a27_unknown_history_is_not_an_empty_commit_prefix(self):
        result,_,observed=witness()
        observed['untrusted']['head']=None
        value=journeys.check_postcondition(expected=expected(),result=result,events=[],observed=observed)
        self.assertNotIn('PASS',[x.get('status') for x in walk(value) if isinstance(x,dict)])

    def test_a27_export_acknowledgement_without_manifest_is_insufficient(self):
        value=journeys.check_postcondition(
            expected=dict(operation='Export ledger',tool='ledger_export',actor=ACTOR,
                          op_id=None,kind=None,entity_id=None,run_id=None,
                          expect='projection',code=None),
            result={'untrusted':{}},events=[],observed={})
        self.assertNotIn('PASS',[x.get('status') for x in walk(value) if isinstance(x,dict)])

    def test_a27_verify_false_is_never_success(self):
        value=journeys.check_postcondition(
            expected=dict(operation='Verify ledger',tool='ledger_verify',actor=ACTOR,
                          op_id=None,kind=None,entity_id=None,run_id=None,
                          expect='projection',code=None),
            result={'ok':False,'code':'hash_mismatch'},events=[],observed={})
        self.assertNotIn('PASS',[x.get('status') for x in walk(value) if isinstance(x,dict)])

    def test_a25_fixture_refusal_with_mutation_event_fails(self):
        result,events,observed=witness()
        value=journeys.check_postcondition(expected=expected(expect='refusal',code='fixture_readonly'),
            result={'ok':False,'code':'fixture_readonly'},events=events,observed=observed)
        self.verdict(value,'FAIL')


def mismatch_test(mutate):
    def test(self):
        result,events,observed=witness()
        mutate(result,events,observed)
        value=journeys.check_postcondition(expected=expected(),result=result,events=events,observed=observed)
        self.verdict(value,'FAIL')
    return test


for label,mutate in {
    'wrong_actor':lambda r,e,o:e[-1].update(agent='beta-root'),
    'wrong_run':lambda r,e,o:r['untrusted']['run'].update(run_id='other001'),
    'wrong_entity':lambda r,e,o:r['untrusted']['run'].update(agent_id='beta-root'),
    'commit_hash':lambda r,e,o:r['untrusted']['commit'].update(sha256='f'*64),
    'commit_event_id':lambda r,e,o:r['untrusted']['commit'].update(event_ids=['e-00000000000000ff']),
    'commit_head':lambda r,e,o:r['untrusted']['commit'].update(head=3),
    'event_digest':lambda r,e,o:e[-1].update(sha256='e'*64),
    'read_still_open':lambda r,e,o:o['untrusted'].update(closed=None),
    'failed_gate':lambda r,e,o:r['untrusted']['run']['memory'].update(gate_passed=False),
}.items():
    setattr(JourneyTests,'test_a26_mismatch_'+label,mismatch_test(mutate))
