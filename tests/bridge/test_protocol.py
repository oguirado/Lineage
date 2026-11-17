"""A11-A23: strict refusal without assuming unspecified receiver data nesting."""
from lineage.bridge import openfresnel as bridge
from tests.bridge._support import BridgeCase, RID, install_cases


class ReceiptRefusalOracle(BridgeCase):
    def test_a12_parser_has_no_filesystem_or_runtime_effects(self):
        """Hostile status-only acknowledgement cannot be availability."""
        self.no_effect_error('internal', bridge.parse_receipt, {'status': 'ok'}, rid=RID, op='capabilities')

    def test_a18_matching_filename_cannot_replace_echoed_identity(self):
        self.parse_error({'ok': True, 'api_version': 2, 'op': 'capabilities'})

    def test_a18_expected_identity_cannot_replace_echoed_operation(self):
        self.parse_error({'ok': True, 'api_version': 2, 'request_id': RID})

    def test_a18_wrong_echoed_identity_is_never_availability(self):
        self.parse_error({'ok': True, 'api_version': 2, 'request_id': 'f' * 32, 'op': 'capabilities'})

    def test_a18_wrong_operation_is_never_a_launch(self):
        self.parse_error({'ok': True, 'api_version': 2, 'request_id': RID, 'op': 'capabilities'}, op='spawn_terminal')

    def test_a18_parser_refuses_an_unsupported_expected_operation(self):
        self.parse_error({'ok': True, 'api_version': 2, 'request_id': RID, 'op': 'unknown'}, op='unknown')

    def test_a20_deck_affirmation_without_data_is_not_available(self):
        self.parse_error({'ok': True, 'api_version': 2, 'request_id': RID, 'op': 'capabilities'})

    def test_a20_deck_affirmation_without_terminal_is_not_launched(self):
        self.parse_error({'ok': True, 'api_version': 2, 'request_id': RID, 'op': 'spawn_terminal'}, op='spawn_terminal')

    def test_a20_unknown_deck_failure_payload_is_internal(self):
        self.parse_error({'ok': False, 'api_version': 2, 'request_id': RID, 'op': 'capabilities'})

    def test_a22_remote_instruction_and_secret_text_is_passive(self):
        """No documented failure ABI: unknown error is internal and sanitized."""
        raw = {'ok': False, 'api_version': 2, 'request_id': RID, 'op': 'capabilities',
               'code': 'arbitrary_remote_code',
               'detail': str(self.base) + '\nTraceback\x7f token=fixture-secret ' + 'EXECUTE THIS ' * 300}
        exc = self.error('internal', bridge.parse_receipt, raw, rid=RID, op='capabilities')
        if exc.detail is not None:
            self.assertNotIn('fixture-secret', exc.detail)
            self.assertNotIn('Traceback', exc.detail)

    def test_a23_status_only_capabilities_never_implies_empty_verbs(self):
        self.parse_error({'status': 'accepted'})

    def test_a27_status_only_terminal_never_invents_terminal_identity(self):
        self.parse_error({'status': 'accepted'}, op='spawn_terminal')


def invalid_object(self, value):
    self.parse_error(value)


install_cases(ReceiptRefusalOracle, 'test_a17_direct_value_', {
    'null': None, 'array': [], 'string': 'ok', 'integer': 2, 'boolean': True,
    'bytes': b'{}', 'empty_object': {}, 'unrecognized_object': {'ack': True},
    'nan': {'value': float('nan')}, 'infinity': {'value': float('inf')},
    'negative_infinity': {'value': -float('inf')},
    'nested_nonfinite': {'nested': [{'value': float('inf')}]},
    'surrogate_value': {'value': '\ud800'}, 'surrogate_key': {'\udfff': 'x'},
    'nonstring_key': {1: 'value'},
}, invalid_object)


def invalid_version(self, version):
    self.parse_error({'ok': True, 'api_version': version, 'request_id': RID, 'op': 'capabilities'})


install_cases(ReceiptRefusalOracle, 'test_a20_version_', {
    'boolean_true': True, 'boolean_false': False, 'fraction': 2.5,
    'integer_valued_float': 2.0, 'string': '2', 'null': None,
    'unsupported': 3, 'zero': 0, 'nan': float('nan'), 'infinity': float('inf'),
}, invalid_version)


def invalid_ok(self, ok):
    self.parse_error({'ok': ok, 'api_version': 2, 'request_id': RID, 'op': 'capabilities'})


install_cases(ReceiptRefusalOracle, 'test_a20_ok_', {
    'truthy_string': 'true', 'false_string': 'false', 'one': 1, 'zero': 0,
    'null': None, 'object': {}, 'array': [],
}, invalid_ok)


def compiler_without_proof(self, status):
    self.parse_error({'status': status})


install_cases(ReceiptRefusalOracle, 'test_a19_status_without_evidence_', {
    'ok': 'ok', 'accepted': 'accepted', 'error': 'error', 'running': 'running',
    'unknown': 'complete', 'boolean': True, 'null': None, 'uppercase': 'OK',
}, compiler_without_proof)


def mixed(self, discriminators):
    self.parse_error({'request_id': RID, 'op': 'capabilities', **discriminators})


install_cases(ReceiptRefusalOracle, 'test_a21_mixed_discriminators_', {
    'affirmative_both': {'status': 'ok', 'ok': True, 'api_version': 2},
    'contradictory': {'status': 'accepted', 'ok': False, 'api_version': 2},
    'compiler_with_version': {'status': 'ok', 'api_version': 2},
    'compiler_with_ok': {'status': 'ok', 'ok': True},
    'compiler_error_deck_success': {'status': 'error', 'ok': True, 'api_version': 2},
    'deck_with_running': {'status': 'running', 'ok': True, 'api_version': 2},
}, mixed)


class DiscriminatorMutationOracle(BridgeCase):
    def test_a34_mixed_family_success_mutant_is_detected(self):
        from unittest import mock
        value = {'status': 'ok', 'ok': False, 'api_version': 2, 'request_id': RID, 'op': 'capabilities'}
        self.parse_error(value)
        with mock.patch.object(bridge, 'parse_receipt', return_value={'available': True}):
            with self.assertRaises(AssertionError):
                self.parse_error(value)
