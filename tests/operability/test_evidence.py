"""Fail-closed capsule boundaries, without fabricating external receipts."""
import copy

from tools.qa import evidence, report
from tests.operability.test_contract import OracleCase, walk, check
from tests.operability.test_report import capture_context


class EvidenceTests(OracleCase):
    def absent_or_invalid(self,records):
        try:
            value=evidence.verify_capsule(records,artifact_root=self.scratch(),expected={})
        except NotImplementedError:
            raise
        except (ValueError,TypeError):
            return  # The amendment has not frozen the error representation.
        self.assertIsInstance(value,dict)
        self.assertNotIn('PASS',[v.get('status') for v in walk(value) if isinstance(v,dict)])
        self.assertTrue(any(isinstance(v,dict) and
                            (v.get('status') in ('FAIL','INCONCLUSIVE') or 'code' in v)
                            for v in walk(value)))

    def test_a31_missing_capsule_records_are_not_visual_acceptance(self):
        self.absent_or_invalid([])

    def test_a31_unrecognized_receipt_cannot_be_credited_as_pass(self):
        # Deliberately NOT a claimed vis.receipt/v1 specimen: that schema is
        # absent. This tests configuration refusal, not valid capsule semantics.
        self.absent_or_invalid([{'status':'pass'}])

    def test_a31_unsupported_external_schema_is_not_synthesized(self):
        self.absent_or_invalid([{'schema':'unsupported','verdict':'pass'}])

    def test_a24_artifact_hash_basis_is_closed(self):
        artifact=dict(ref='frames/before.png',sha256='a'*64,kind='frame',hash_basis='invented')
        self.reject(report.make_report,method='V',scope='selftest',checks=[check()],
                    artifacts=[artifact],context=capture_context())

    def test_a24_raw_and_pruned_kinds_remain_distinct(self):
        artifacts=[dict(ref='trees/raw.json',sha256='a'*64,kind='atspi_raw',hash_basis='file_bytes'),
                   dict(ref='trees/pruned.json',sha256='b'*64,kind='pruned',hash_basis='canonical_json')]
        value=report.make_report(method='P',scope='selftest',checks=[check('INCONCLUSIVE','evidence_missing')],artifacts=artifacts,context=capture_context())
        self.assertEqual(value['artifacts'],artifacts)
        self.assertNotEqual(value['artifacts'][0]['ref'],value['artifacts'][1]['ref'])

    def test_a24_no_unknown_artifact_fields(self):
        artifact=dict(ref='trees/raw.json',sha256='a'*64,kind='atspi_raw',hash_basis='file_bytes',extra=True)
        self.reject(report.make_report,method='A',scope='selftest',checks=[check()],
                    artifacts=[artifact],context=capture_context())

    def test_a31_valid_external_capsule_receipt(self):
        self.skipTest('INCONCLUSIVE: pinned vis.receipt/v1 schema and authentic frame/observer records AUSENTE')

    def test_a24_a31_frame_bytes_pixels_and_symlink_resolution(self):
        self.skipTest('INCONCLUSIVE: closed capsule record/artifact resolver shape unpinned; no invented positive receipt')

    def test_a32_persona_independence_and_unrounded_weighted_scores(self):
        self.skipTest('INCONCLUSIVE: frozen J1-J8 definitions, SC1-SC8 weights and independent persona stores AUSENTE')


def unsafe_artifact_test(ref):
    def test(self):
        artifact=dict(ref=ref,sha256='a'*64,kind='frame',hash_basis='file_bytes')
        self.reject(report.make_report,method='V',scope='selftest',checks=[check()],
                    artifacts=[artifact],context=capture_context())
    return test


for label,value in (('parent','../frame.png'),('nested_parent','frames/../frame.png'),
                    ('leading_separator',chr(47)+'frame.png'),('dot','./frame.png'),
                    ('backslash','frames'+chr(92)+'frame.png'),('empty_segment','frames//frame.png')):
    setattr(EvidenceTests,'test_a24_a31_confine_artifact_ref_'+label,unsafe_artifact_test(value))
