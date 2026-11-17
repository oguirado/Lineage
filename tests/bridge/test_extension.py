"""A1-A4/A21/A22/A29-A36: public adapters and passive registration."""
from contextlib import ExitStack
from copy import deepcopy
import importlib
import inspect
import io
import json
import os
from pathlib import Path
from unittest import mock

from lineage.bridge import openfresnel as bridge
from lineage.core import app, cli, mcp
from lineage.core.registry import Registry, ToolSpec
from tests.bridge._support import (AGENT, OP_ID, RID, ROOT, BridgeCase, canonical,
                                  client_double, contract_schema, family, image, install_cases)

PROBE = {'rid': RID, 'available': True, 'verbs': [], 'receipt_family': 'deck'}
SPAWN = {'rid': RID, 'state': 'launched', 'terminal_id': 'terminal-fixture',
         'pane_id': None, 'screen_id': None, 'receipt_family': 'deck'}


class AdapterOracle(BridgeCase):
    def test_a01_public_signatures_and_importable_packages(self):
        """Positive exact exported keyword boundaries; unknown API is not guessed."""
        expected = {
            'commands_dir': [('commands_dir', 'KEYWORD_ONLY', None), ('contract_file', 'KEYWORD_ONLY', None)],
            'parse_receipt': [('value', 'POSITIONAL_OR_KEYWORD', inspect.Parameter.empty),
                              ('rid', 'KEYWORD_ONLY', inspect.Parameter.empty), ('op', 'KEYWORD_ONLY', inspect.Parameter.empty)],
            'probe': [('commands_dir', 'KEYWORD_ONLY', None), ('contract_file', 'KEYWORD_ONLY', None),
                      ('timeout_ms', 'KEYWORD_ONLY', 20000), ('command', 'KEYWORD_ONLY', inspect.Parameter.empty),
                      ('ctx', 'KEYWORD_ONLY', inspect.Parameter.empty)],
            'spawn': [('mode', 'POSITIONAL_OR_KEYWORD', inspect.Parameter.empty),
                      ('endpoint', 'KEYWORD_ONLY', None), ('envelope', 'KEYWORD_ONLY', None),
                      ('commands_dir', 'KEYWORD_ONLY', None), ('contract_file', 'KEYWORD_ONLY', None),
                      ('timeout_ms', 'KEYWORD_ONLY', 20000), ('command', 'KEYWORD_ONLY', inspect.Parameter.empty),
                      ('ctx', 'KEYWORD_ONLY', inspect.Parameter.empty)],
        }
        self.assertTrue((ROOT / 'tests/bridge/__init__.py').is_file())
        self.assertTrue((ROOT / 'lineage/bridge/__init__.py').is_file())
        for name, shape in expected.items():
            sig = inspect.signature(getattr(bridge, name))
            self.assertEqual([(p.name, p.kind.name, p.default) for p in sig.parameters.values()], shape)
            self.assertIsNot(sig.return_annotation, inspect.Signature.empty)
        for name in ('_probe', '_spawn'):
            sig = inspect.signature(getattr(self.extension(), name))
            self.assertEqual([(p.name, p.kind.name) for p in sig.parameters.values()],
                             [('args', 'POSITIONAL_OR_KEYWORD'), ('context', 'KEYWORD_ONLY')])

    def test_a02_exact_names_mutating_flags_and_empty_event_ownership(self):
        specs = self.descriptors()
        self.assertTrue(all(s.mutating is True for s in specs))
        self.assertEqual(self.extension().VALIDATORS, {})
        self.assertEqual(self.extension().FOLDS, {})
        for spec in specs:
            self.assertIsInstance(spec, ToolSpec)
            self.assertEqual(spec.input_schema, contract_schema(spec.name))

    def test_a02_reload_import_and_descriptor_listing_are_passive(self):
        """Hostile filesystem effect guards during import/reload/listing."""
        ext = self.extension()
        before = image(self.base)
        with ExitStack() as stack:
            for target in ('os.open', 'os.mkdir', 'os.makedirs', 'os.rename', 'os.replace', 'os.write'):
                stack.enter_context(mock.patch(target, side_effect=AssertionError('import-time effect')))
            ext = importlib.reload(ext)
            specs = self.descriptors()
            registry = Registry({s.name: s for s in specs}, {}, {})
            data = app.list_tools(registry=registry)
        self.assertEqual(image(self.base), before)
        self.assertEqual({d['name'] for d in data}, {'openfresnel_probe', 'openfresnel_spawn'})

    def test_a04_valid_probe_adapts_effective_identity_and_default(self):
        args = {'agent': AGENT, 'op_id': OP_ID, 'commands_dir': str(self.channel)}
        before = deepcopy(args)
        with client_double(self, 'probe', PROBE) as client:
            self.assertEqual(self.handler('openfresnel_probe', args), PROBE)
        client.assert_called_once()
        kwargs = client.call_args.kwargs
        self.assertEqual(kwargs.get('timeout_ms', 20000), 20000)
        self.assertEqual(kwargs['commands_dir'], str(self.channel))
        command = kwargs['command']
        self.assertEqual((command.tool, command.agent, command.op_id, command.expected_head),
                         ('openfresnel_probe', AGENT, OP_ID, None))
        self.assertEqual(command.args['timeout_ms'], 20000)
        self.assertEqual(kwargs['ctx'].home, self.home)
        self.assertEqual(args, before)

    def test_a04_valid_json_adapts_an_envelope_without_shell_interpolation(self):
        envelope = family()
        args = {'agent': AGENT, 'op_id': OP_ID, 'mode': 'json', 'envelope': envelope}
        with client_double(self, 'spawn', SPAWN) as client:
            self.assertEqual(self.handler('openfresnel_spawn', args), SPAWN)
        client.assert_called_once()
        self.assertEqual(client.call_args.args[0] if client.call_args.args else client.call_args.kwargs['mode'], 'json')
        self.assertEqual(client.call_args.kwargs['envelope'], envelope)
        self.assertIsNone(client.call_args.kwargs.get('endpoint'))
        self.assertEqual(client.call_args.kwargs['ctx'].home, self.home)

    def test_a04_valid_drain_preserves_endpoint_and_effective_home(self):
        args = {'agent': AGENT, 'op_id': OP_ID, 'mode': 'drain', 'endpoint': 'Receiver_1'}
        with client_double(self, 'spawn', SPAWN) as client:
            self.assertEqual(self.handler('openfresnel_spawn', args), SPAWN)
        self.assertEqual(client.call_args.args[0] if client.call_args.args else client.call_args.kwargs['mode'], 'drain')
        self.assertEqual(client.call_args.kwargs['endpoint'], 'Receiver_1')
        self.assertIsNone(client.call_args.kwargs.get('envelope'))
        self.assertEqual(client.call_args.kwargs['ctx'].home, self.home)

    def test_a04_reserved_operator_actor_never_constructs_operator_authority(self):
        """K0 admits this caller-asserted actor; it grants no level-one power."""
        before = image(self.home)
        with client_double(self, 'probe', PROBE) as client:
            self.handler('openfresnel_probe', {'agent': 'operator', 'op_id': OP_ID})
        command = client.call_args.kwargs['command']
        context = client.call_args.kwargs['ctx']
        self.assertEqual(command.agent, 'operator')
        self.assertEqual(getattr(context, 'authority', 'tool'), 'tool')
        self.assertEqual(image(self.home), before)

    def test_a04_reserved_system_actor_is_an_ordinary_tool_actor(self):
        with client_double(self, 'probe', PROBE) as client:
            self.handler('openfresnel_probe', {'agent': 'system', 'op_id': OP_ID})
        self.assertEqual(client.call_args.kwargs['command'].agent, 'system')
        self.assertEqual(getattr(client.call_args.kwargs['ctx'], 'authority', 'tool'), 'tool')

    def test_a22_a32_probe_dispatch_wraps_inner_data_exactly_once(self):
        specs = self.descriptors()
        registry = Registry({s.name: s for s in specs}, {}, {})
        context = app.CallContext(self.home, registry.validators, registry.folds)
        with client_double(self, 'probe', PROBE):
            result = app.dispatch('openfresnel_probe', {'agent': AGENT, 'op_id': OP_ID}, context=context, registry=registry)
        self.assertEqual(result.payload, {'untrusted': PROBE})
        self.assertEqual(result.exit_code, 0)
        self.assertIsNone(result.failure)

    def test_a29_adaptation_alone_never_changes_run_memory_or_ledger(self):
        """This verifies adapter effects only; remote launch is a separate gate."""
        before = image(self.home)
        with client_double(self, 'probe', PROBE):
            self.assertEqual(self.handler('openfresnel_probe', {'agent': AGENT, 'op_id': OP_ID}), PROBE)
        self.assertEqual(image(self.home), before)

    def test_a35_public_guide_describes_required_behaviors_and_limits(self):
        text = (ROOT / 'docs/OPENFRESNEL.md').read_text(encoding='utf-8')
        required = ('LINEAGE_OPENFRESNEL_COMMANDS_DIR', 'commands_dir', 'contract_file',
                    'compiler', 'deck', 'timeout', 'retry', 'json', 'drain', '--home',
                    'launched', 'bad_args', 'bad_op', 'conflict', 'internal',
                    'fake', 'AUSENTE', 'U05', 'stdin', 'memory', 'ledger',
                    'python3 -m unittest discover -s tests/bridge -t .')
        missing = [word for word in required if word.casefold() not in text.casefold()]
        self.assertEqual(missing, [], 'U20 stub: public guide is incomplete')


class ProbeBoundaryOracle(BridgeCase):
    def registry(self):
        specs = self.descriptors()
        return Registry({s.name: s for s in specs}, {}, {})

    def reject(self, args):
        registry = self.registry()
        context = app.CallContext(self.home, registry.validators, registry.folds)
        before = image(self.base)
        result = app.dispatch('openfresnel_probe', args, context=context, registry=registry)
        self.assertEqual(result.payload['code'], 'bad_args')
        self.assertIs(result.payload['ok'], False)
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(image(self.base), before)


def bad_probe_args(self, args):
    self.reject(args)


_valid = {'agent': AGENT, 'op_id': OP_ID}
_cases = {
    'missing_agent': {'op_id': OP_ID}, 'missing_operation': {'agent': AGENT},
    'missing_both': {}, 'array': [], 'null': None,
}
for key, value in {'rid': RID, 'argv': ['x'], 'expected_head': 0, 'gate': {},
                   'receipt_family': 'deck', 'unknown': True}.items():
    _cases['forged_' + key] = {**_valid, key: value}
for key in ('commands_dir', 'contract_file'):
    _cases[key + '_null'] = {**_valid, key: None}
    _cases[key + '_empty'] = {**_valid, key: ''}
for label, value in {'boolean': True, 'fraction': 1.5, 'zero': 0, 'negative': -1,
                     'too_large': 60001, 'null': None, 'string': '5'}.items():
    _cases['timeout_' + label] = {**_valid, 'timeout_ms': value}
for label, value in {'uppercase': 'Tester', 'short': 'ab', 'newline': 'tester\n',
                     'overlong': 'a' * 65, 'null': None, 'surrogate': '\ud800'}.items():
    _cases['agent_' + label] = {**_valid, 'agent': value}
for label, value in {'empty': '', 'newline': 'op\n', 'overlong': 'x' * 129,
                     'metacharacter': 'op;cmd', 'null': None}.items():
    _cases['operation_' + label] = {**_valid, 'op_id': value}
install_cases(ProbeBoundaryOracle, 'test_a04_closed_probe_', _cases, bad_probe_args)


class SharedTransportOracle(BridgeCase):
    def runtime(self):
        specs = self.descriptors()
        registry = Registry({s.name: s for s in specs}, {}, {})
        return registry, app.CallContext(self.home, registry.validators, registry.folds)

    def test_a31_cli_and_mcp_share_probe_adapter_and_single_wrapper(self):
        """Actual in-process transports; the public bridge seam supplies data."""
        registry, context = self.runtime()
        args = {'agent': AGENT, 'op_id': OP_ID}
        out, err = io.StringIO(), io.StringIO()
        with client_double(self, 'probe', PROBE):
            code = cli.main(['--home', str(self.home), 'call', 'openfresnel_probe', '--json', canonical(args).decode()],
                            registry=registry, stdin=io.BytesIO(), stdout=out, stderr=err)
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().encode(), canonical({'untrusted': PROBE}) + b'\n')
        self.assertEqual(err.getvalue(), '')
        rpc = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
               'params': {'name': 'openfresnel_probe', 'arguments': args}}
        out, err = io.StringIO(), io.StringIO()
        with client_double(self, 'probe', PROBE):
            mcp.main(context=context, registry=registry, stdin=io.BytesIO(canonical(rpc) + b'\n'), stdout=out, stderr=err)
        response = json.loads(out.getvalue())
        self.assertIs(response['result']['isError'], False)
        self.assertEqual(json.loads(response['result']['content'][0]['text']), {'untrusted': PROBE})
        self.assertEqual(err.getvalue(), '')

    def test_a28_json_lane_injects_external_identity_and_replays_without_journal(self):
        """U05 carrier integration at the client seam, not terminal interoperability."""
        import hashlib
        from tests.bridge._support import call_envelope, request_id
        registry, context = self.runtime()
        # A-U20: use U05's owner-only recipient fixture; keep replay assertions intact.
        self.recipient_configuration(sources=['source'],
                                     tools=['openfresnel_probe', 'openfresnel_spawn'])
        envelope = call_envelope()
        op_id = 'lin-' + hashlib.sha256(b'source\x00receiver\x00request01').hexdigest()[:44]
        expected = {**PROBE, 'rid': request_id(AGENT, op_id)}
        outputs = []
        with client_double(self, 'probe', expected) as client:
            for _ in range(2):
                out, err = io.StringIO(), io.StringIO()
                code = cli.main(['--home', str(self.home), 'json'], registry=registry,
                                stdin=io.BytesIO(canonical(envelope)), stdout=out, stderr=err)
                self.assertEqual(code, 0, 'U20 stub or blocked U05 external acknowledgement')
                self.assertEqual(err.getvalue(), '')
                outputs.append(json.loads(out.getvalue()))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], {'schema': 'lineage.family/1', 'id': 'request01', 'result': {'untrusted': expected}})
        client.assert_called_once()
        command = client.call_args.kwargs['command']
        context = client.call_args.kwargs['ctx']
        self.assertEqual(command.op_id, op_id)
        self.assertEqual(context.op_id, op_id)
        self.assertEqual(context.actor, AGENT)
        self.assertFalse((self.home / 'ledger/main/events.jsonl').exists())

    def test_a31_json_denied_source_cannot_reach_client(self):
        from tests.bridge._support import call_envelope
        registry, context = self.runtime()
        # A-U20: reach source authorization with an otherwise valid U05 fixture.
        self.recipient_configuration(sources=['authorized'], tools=['openfresnel_probe'])
        out, err = io.StringIO(), io.StringIO()
        with client_double(self, 'probe', PROBE) as client:
            code = cli.main(['--home', str(self.home), 'json'], registry=registry,
                            stdin=io.BytesIO(canonical(call_envelope())), stdout=out, stderr=err)
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())['result'], {'ok': False, 'code': 'bad_args'})
        client.assert_not_called()

    def test_a04_cli_hostile_json_never_publishes(self):
        registry, context = self.runtime()
        invalid = [b'{"agent":"tester","agent":"other","op_id":"x"}',
                   b'{"timeout_ms":NaN}', b'{"timeout_ms":Infinity}', b'{"timeout_ms":1e999}',
                   b'{"agent":"\\ud800"}', b'{"agent":"\xff"}', b'{}{}']
        with client_double(self, 'probe', PROBE) as client:
            for raw in invalid:
                out, err = io.StringIO(), io.StringIO()
                # Invalid UTF-8 is rejected by strict_loads at the byte boundary;
                # argv itself consists of strings and cannot carry bad UTF-8.
                if b'\xff' in raw:
                    from lineage.core.schema import SchemaError, strict_loads
                    with self.assertRaises(SchemaError):
                        strict_loads(raw)
                    continue
                code = cli.main(['--home', str(self.home), 'call', 'openfresnel_probe', '--json', raw.decode()],
                                registry=registry, stdin=io.BytesIO(), stdout=out, stderr=err)
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(out.getvalue())['code'], 'bad_args')
                self.assertEqual(len(out.getvalue().splitlines()), 1)
        client.assert_not_called()


class HermeticOracle(BridgeCase):
    def test_a33_network_and_subprocess_guards_are_discriminating(self):
        import socket
        import subprocess
        with self.assertRaisesRegex(AssertionError, 'forbidden external effect'):
            socket.socket()
        with self.assertRaisesRegex(AssertionError, 'forbidden external effect'):
            subprocess.run(['fixture-never-executed'])
        self.assertIsInstance(os.kill, mock.Mock)
        self.assertIsInstance(os.killpg, mock.Mock)

    def test_a33_filesystem_guard_rejects_writes_outside_disposable_runtime(self):
        candidate = ROOT / 'bridge-forbidden-write.fixture'
        self.assertFalse(candidate.exists())
        with self.assertRaisesRegex(AssertionError, 'outside the disposable'):
            candidate.write_text('must never be written')
        self.assertFalse(candidate.exists())
        allowed = self.base / 'allowed.fixture'
        allowed.write_text('test-owned')
        self.assertEqual(allowed.read_text(), 'test-owned')

    def test_a33_virtual_clock_advances_without_real_sleep(self):
        import time
        with self.clock.installed():
            start = time.monotonic()
            time.sleep(0.25)
            stop = time.monotonic()
        self.assertGreaterEqual(stop - start, 0.25)
        self.assertLess(stop - start, 0.26)

    def test_a35_owned_sources_have_no_runtime_coordinates(self):
        """Local publishability contrast; campaign-level checker is a separate gate."""
        prefixes = [os.sep + part + os.sep for part in ('home', 'Users', 'tmp', 'private', 'var', 'root')]
        def clean(text):
            return not any(prefix in text for prefix in prefixes)
        self.assertTrue(clean('docs/CONTRACT.md'))
        self.assertFalse(clean(prefixes[0] + 'fixture-user/project'))
        files = [ROOT / 'lineage/bridge/__init__.py', ROOT / 'lineage/bridge/openfresnel.py',
                 ROOT / 'lineage/ext/openfresnel.py', ROOT / 'docs/OPENFRESNEL.md']
        files += list((ROOT / 'tests/bridge').glob('*.py'))
        files += list((ROOT / 'tests/bridge').glob('*.md'))
        for path in files:
            self.assertTrue(clean(path.read_text()), path.relative_to(ROOT).as_posix())
