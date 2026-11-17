"""Explicitly failing prerequisites, excluded from default fake-client discovery.

Run separately: python3 -m unittest tests.bridge.upstream_gates
No expectedFailure, skip, guessed receiver field, or fabricated green receipt.
"""
from contextlib import redirect_stderr, redirect_stdout
import io
import json

from lineage.core import app, cli, registry as extensions, schema
from lineage.core.errors import LineageError
from lineage.core.registry import Registry, ToolSpec
from tests.bridge._support import AGENT, OP_ID, BridgeCase, canonical, contract_schema


class UpstreamSchemaAndCLI(BridgeCase):
    def test_a03_exact_k0_spawn_schema_is_accepted_without_weakening(self):
        expected = contract_schema('openfresnel_spawn')
        self.assertEqual(expected['properties']['envelope'], {'$ref': 'family_envelope.schema.json'})
        try:
            schema.validate({}, expected)
        except schema.SchemaError as exc:
            if exc.schema_pointer is not None:
                self.fail('BLOCKED A3: shared schema owner rejects the exact K0 descriptor at ' + exc.schema_pointer)
            # Missing instance fields are expected; schema definition must load.
        specs = self.descriptors()
        self.assertEqual({s.name: s.input_schema for s in specs},
                         {name: contract_schema(name) for name in ('openfresnel_probe', 'openfresnel_spawn')})
        loaded = extensions.load()
        self.assertEqual(loaded.tools['openfresnel_spawn'].input_schema, expected)

    def test_a30_handler_configuration_bad_args_is_cli_usage_exit_two(self):
        """Actual CLI/dispatch prerequisite, independent of the U20 stub."""
        def missing_configuration(args, *, context):
            raise LineageError('bad_args', 'Bridge configuration is required')
        spec = ToolSpec('openfresnel_probe', 'Configuration prerequisite fixture',
                        contract_schema('openfresnel_probe'), missing_configuration, True)
        registry = Registry({spec.name: spec}, {}, {})
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(['--home', str(self.home), 'call', spec.name, '--json',
                         canonical({'agent': AGENT, 'op_id': OP_ID}).decode()],
                        registry=registry, stdin=io.BytesIO(), stdout=out, stderr=err)
        self.assertEqual(json.loads(out.getvalue())['code'], 'bad_args')
        self.assertEqual(code, 2, 'BLOCKED A30: shared dispatcher classifies handler configuration errors as execution')


class ReceiverContractGates(BridgeCase):
    """Acceptance assertions that M27 prevents us from guessing.

    These fail explicitly before interpreting any unbacked success fixture.
    A source amendment must supply an authoritative command/receipt grammar,
    child stdin+EOF binding and receiver dedupe evidence before activation.
    """


def _blocked(self, value):
    acceptance, missing = value
    self.fail('BLOCKED ' + acceptance + ': AUSENTE — no inventar: ' + missing)


from tests.bridge._support import install_cases
install_cases(ReceiverContractGates, 'test_', {
    'a01_integration_surface_receipt': ('A1', 'integration diff/receipt and admitted U05 prerequisite'),
    'a09_restart_rid_publication': ('A9', 'authoritative outgoing command schema for a retained publication'),
    'a10_late_result_same_rid_and_no_second_action': ('A10', 'successful correlated receipt grammar and receiver action fixture'),
    'a11_same_target_intent_and_cross_target_u05': ('A11', 'command content grammar; cross-target identity is U05-only'),
    'a12_concurrent_identical_and_different_publishers': ('A12', 'canonical command grammar for valid retained-intent comparison'),
    'a13_atomic_canonical_publication_and_fsync_order': ('A13', 'normative client command schema; no invented command keys'),
    'a14_short_write_file_fsync_rename_directory_fsync': ('A14', 'command grammar enabling observable publication and retry after rename'),
    'a15_result_inode_replacement': ('A15', 'valid source-backed result receipt preceding the replacement fault'),
    'a16_absence_deadline_versus_present_io_failure': ('A16', 'valid publication binding before timed observation'),
    'a17_hostile_result_bytes_and_client_size_cap': ('A17', 'publication binding reaching bounded result decoding'),
    'a18_positive_correlated_receipt_and_purity': ('A18', 'complete affirmative receipt nesting/correlation grammar'),
    'a19_compiler_ok_accepted_and_error_forms': ('A19', 'compiler correlation, data nesting and documented error payloads'),
    'a20_deck_affirmative_and_documented_error_forms': ('A20', 'complete operation data nesting and Deck error payload grammar'),
    'a22_documented_remote_failure_mapping': ('A22', 'authoritative remote bad_args/conflict/internal payload forms'),
    'a23_verbs_empty_present_missing_bounds': ('A23', 'authoritative location of capability data in each receipt family'),
    'a24_json_argv_stdin_exact_bytes_and_eof': ('A24', 'source-backed argv carrier and JSON stdin+EOF binding'),
    'a25_drain_argv_home_endpoint_and_no_input': ('A25', 'source-backed argv carrier for sys.executable -m lineage --home HOME drain --endpoint ENDPOINT'),
    'a26_successful_publication_both_modes': ('A26', 'valid command grammar and affirmative acknowledgement forms'),
    'a27_closed_nullable_terminal_results': ('A27', 'source-backed terminal/pane/screen data locations in both families'),
    'a28_crash_pending_mailbox_bridge_recovery': ('A28', 'bridge publication/retention fixture and receiver dedupe evidence'),
    'a29_real_ack_cannot_close_run_or_memory': ('A29', 'acknowledgement fixture; application receipt and verified ledger witness remain separate'),
    'a31_both_tools_all_surfaces_and_http_refusals': ('A31', 'spawn schema prerequisite and full transport acceptance without a live server'),
    'a32_success_and_error_frozen_wire_alternatives': ('A32', 'source-backed bridge results and upstream schema admission'),
    'a34_identity_retry_atomic_mutants': ('A34', 'valid control publication/receipt from which to remove each individual check'),
    'a35_campaign_publishability_checker': ('A35', 'source-identified campaign checker and rejecting seeded fixture'),
    'a36_live_interoperability_and_terminal_parity': ('A36', 'authorized measured live interoperability, headless parity and durable receiver dedupe'),
}, _blocked)
