"""Status reduction, closed report boundaries and public-safe emission."""
import copy
import json

from tools.qa import report
from tests.operability.test_contract import (OracleCase, FROZEN_SHA256,
                                            canonical, context, check)


def capture_context():
    return context(contract_sha256=FROZEN_SHA256, inventory_sha256='1' * 64,
                   fixture_sha256='2' * 64, scenario='good', frame='initial',
                   head=0, viewport={'width':390, 'height':844}, theme='light',
                   reduced_motion=True, zoom_percent=100, owner_ref='owner-good')


def ready_report(**changes):
    value = dict(schema='lineage.qa.report/v1', method='C', scope='selftest',
                 status='PASS', rc=0, checks=[check()], artifacts=[],
                 context=capture_context())
    value.update(changes)
    return value


class ReportTests(OracleCase):
    def reduce(self, checks, method='C', scope='selftest'):
        return report.make_report(method=method, scope=scope, checks=checks,
                                  artifacts=[], context=capture_context())

    def test_a04_all_required_success(self):
        value = self.reduce([check(), check(id='O2', requirement='O2')])
        self.assertEqual((value['status'],value['rc']), ('PASS',0))
        self.assertEqual(set(value), set(ready_report()))
        self.assertEqual(report.exit_code(value),0)

    def test_a04_empty_checks_are_inconclusive(self):
        value = self.reduce([])
        self.assertEqual((value['status'],value['rc']), ('INCONCLUSIVE',2))

    def test_a04_known_failure_dominates_observer_gap(self):
        checks = [check('FAIL','missing_control'),
                  check('INCONCLUSIVE','observer_unavailable',id='A',requirement='O13')]
        for ordered in (checks, list(reversed(checks))):
            value = self.reduce(ordered)
            self.assertEqual((value['status'],value['rc']), ('FAIL',1))
            self.assertEqual(value['checks'], ordered)

    def test_a02_methods_and_scopes_remain_distinct(self):
        for method in ('C','A','P','V'):
            for scope in ('selftest','fixture','live'):
                value=self.reduce([check('INCONCLUSIVE','evidence_missing')],method,scope)
                self.assertEqual((value['method'],value['scope']), (method,scope))
                self.assertEqual((value['status'],value['rc']), ('INCONCLUSIVE',2))

    def test_a03_a04_null_head_is_preserved(self):
        value=report.make_report(method='C',scope='selftest',checks=[check('INCONCLUSIVE','evidence_missing')],artifacts=[],context=context())
        self.assertIsNone(value['context']['head'])
        self.assertIsNone(value['context']['viewport'])

    def test_a03_a34_emit_one_canonical_json_envelope(self):
        value=ready_report()
        chunks=[]
        rc=report.emit(value,write=chunks.append)
        self.assertTrue(all(isinstance(chunk,bytes) for chunk in chunks))
        self.assertIn(b''.join(chunks),(canonical(value),canonical(value)+b'\n'))
        self.assertEqual(rc,0)

    def test_a03_report_input_is_not_mutated(self):
        checks=[check()]; settings=capture_context(); before=copy.deepcopy((checks,settings))
        report.make_report(method='P',scope='selftest',checks=checks,artifacts=[],context=settings)
        self.assertEqual((checks,settings),before)

    def test_a36_emit_redacts_private_paths_hosts_and_credentials(self):
        private_path=chr(47)+'private'+chr(47)+'case'+chr(47)+'trace.txt'
        private_host='node'+'.'+'invalid'
        private_token='sk'+'-'+'never-a-real-credential-1234567890'
        value=ready_report(status='FAIL',rc=1,checks=[check('FAIL','unsafe_content',detail=' '.join((private_path,private_host,private_token,'<script>never()</script>')))])
        chunks=[]
        rc=report.emit(value,write=chunks.append)
        payload=b''.join(chunks).decode('utf-8')
        self.assertNotEqual(rc,0)
        for private in (private_path,private_host,private_token,'<script>'):
            self.assertNotIn(private,payload)
        json.loads(payload)

    def test_a36_clean_relative_refs_are_retained(self):
        artifact=dict(ref='evidence/tree.json',sha256='a'*64,kind='pruned',hash_basis='canonical_json')
        value=report.make_report(method='P',scope='selftest',checks=[check()],artifacts=[artifact],context=capture_context())
        chunks=[];report.emit(value,write=chunks.append)
        self.assertIn('evidence/tree.json',b''.join(chunks).decode())


def reduction_test(status,code,rc):
    def test(self):
        value=self.reduce([check(status,code)])
        self.assertEqual((value['status'],value['rc']), (status,rc))
        self.assertEqual(value['checks'][0]['code'],code)
    return test


for diagnostic in ('article_control','duplicate_name','name_too_long',
                   'identity_key_mismatch','identity_collision','non_native_control',
                   'invalid_selector','inventory_mismatch','missing_control',
                   'invalid_state','focus_mismatch','announcement_mismatch','stale_ready',
                   'unexpected_console','layout_mismatch','contrast_mismatch',
                   'missing_witness','semantic_mismatch','evidence_mismatch','unsafe_content'):
    setattr(ReportTests,'test_a04_fail_'+diagnostic,reduction_test('FAIL',diagnostic,1))
for diagnostic in ('bad_config','observer_unavailable','wrong_target','no_document',
                   'empty_tree','incomplete_tree','deadline','dependency_missing',
                   'evidence_missing','cleanup_incomplete','probe_internal'):
    setattr(ReportTests,'test_a04_inconclusive_'+diagnostic,reduction_test('INCONCLUSIVE',diagnostic,2))


def invalid_report_test(mutate):
    def test(self):
        value=ready_report();mutate(value)
        self.reject(report.exit_code,value)
    return test


for label,mutate in {
    'root_extra':lambda v:v.update(extra=True),
    'check_extra':lambda v:v['checks'][0].update(extra=True),
    'context_extra':lambda v:v['context'].update(extra=True),
    'viewport_extra':lambda v:v['context']['viewport'].update(extra=True),
    'boolean_rc':lambda v:v.update(rc=False),
    'boolean_head':lambda v:v['context'].update(head=True),
    'zero_viewport':lambda v:v['context']['viewport'].update(width=0),
    'zero_zoom':lambda v:v['context'].update(zoom_percent=0),
    'invalid_hash':lambda v:v['context'].update(contract_sha256='A'*64),
    'invalid_state':lambda v:v.update(status='SKIP'),
    'unknown_method':lambda v:v.update(method='DOM'),
    'unknown_scope':lambda v:v.update(scope='production'),
    'false_green':lambda v:v.update(checks=[check('FAIL','missing_control')]),
    'pass_empty':lambda v:v.update(checks=[]),
    'pass_truncated':lambda v:v.update(checks=[check('INCONCLUSIVE','incomplete_tree')]),
    'pass_cleanup':lambda v:v.update(checks=[check('INCONCLUSIVE','cleanup_incomplete')]),
    'fail_with_ok':lambda v:v.update(status='FAIL',rc=1),
    'nonfinite_head':lambda v:v['context'].update(head=float('nan')),
}.items():
    setattr(ReportTests,'test_a03_reject_'+label,invalid_report_test(mutate))
