"""Frozen U27 input oracles; helpers do not implement production validation."""
from __future__ import annotations

import copy
import hashlib
import inspect
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.qa import contracts, cdp_probe, inventory, report

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / 'tests/operability'
FIXTURES = TESTS / 'fixtures'
CONTRACT_PATH = ROOT / 'docs/OPERABILITY.md'
FROZEN_SHA256 = '06d87b1e36a6a39f7627ed461a4078e1c3162bf3b4ce3ae9b199cc91c0a3b197'
APPENDIX = b'<!-- U27-APPENDIX:BEGIN -->'
SAFE_INTEGER = 9007199254740991


def canonical(value):
    """Independent byte oracle, never a replacement for a QA entry point."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def context(**changes):
    result = dict.fromkeys(('contract_sha256', 'inventory_sha256', 'fixture_sha256',
                           'scenario', 'frame', 'head', 'viewport', 'theme',
                           'reduced_motion', 'zoom_percent', 'owner_ref'))
    result.update(changes)
    return result


def check(status='PASS', code='ok', **changes):
    result = dict(id='O1', requirement='O1', status=status, code=code,
                  detail='Public specimen', expected=None, observed=None)
    result.update(changes)
    return result


def node(identity='button-1', parent=None, role='button', name='Create agent',
         action='create-agent', **changes):
    result = dict(id=identity, parent=parent, role=role, name=name, states=[],
                  actionable=action is not None, entity=None, entity_id=None,
                  action=action)
    result.update(changes)
    return result


def walk(value):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from walk(item)


def loaded_inventory():
    return json.loads((FIXTURES / 'inventory-good.json').read_text('utf-8'))


class OracleCase(unittest.TestCase):
    """No test methods: discovery must not duplicate inherited tests."""
    def scratch(self):
        resource = tempfile.TemporaryDirectory(prefix='case-', dir=TESTS)
        self.addCleanup(resource.cleanup)
        return Path(resource.name)

    def reject(self, function, *args, **kwargs):
        # NotImplementedError inherits RuntimeError: explicitly let it fail red.
        try:
            function(*args, **kwargs)
        except NotImplementedError:
            raise
        except (ValueError, TypeError, OSError, RuntimeError):
            return
        self.fail('The public boundary accepted a forbidden input')

    def verdict(self, value, status, code=None):
        # Helper result schemas are unpinned; assert semantic facts without
        # prescribing a private container key or diagnostic exception class.
        self.assertIsInstance(value, dict)
        objects = [x for x in walk(value) if isinstance(x, dict)]
        self.assertTrue(any(x.get('status') == status for x in objects), value)
        if code:
            self.assertTrue(any(x.get('code') == code for x in objects), value)

    def main_report(self, raw, *, contract_path=None):
        directory = self.scratch()
        path = directory / 'inventory.json'
        path.write_bytes(raw)
        output = io.StringIO()
        args = ['--url', 'http://127.0.0.1:1/#/agents', '--browser',
                str(directory / 'missing-browser'), '--inventory', str(path),
                '--contract', str(contract_path or CONTRACT_PATH),
                '--timeout-ms', '100']
        with patch('sys.stdout', output):
            rc = cdp_probe.main(args)
        result = json.loads(output.getvalue())
        self.assertEqual(result['rc'], rc)
        return rc, result


class ContractTests(OracleCase):
    def test_a01_a35_frozen_prefix_and_package_markers(self):
        contracts.load_contract(CONTRACT_PATH)
        prefix = CONTRACT_PATH.read_bytes().split(APPENDIX, 1)[0]
        self.assertEqual(hashlib.sha256(prefix).hexdigest(), FROZEN_SHA256)
        for path in (ROOT / 'tests/__init__.py', TESTS / '__init__.py',
                     FIXTURES / '__init__.py'):
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_bytes(), b'')

    def test_a02_a35_literal_k0_registry_is_retained(self):
        value = contracts.load_contract(CONTRACT_PATH)
        literals = set(x for x in walk(value) if isinstance(x, str))
        for item in ('agents', 'agent', 'lineage', 'arena', 'bench', 'ledger',
                     'open-agent', 'write-memory', 'launch-benchmark',
                     'export-ledger', 'seat.model', 'unit.statement'):
            self.assertIn(item, literals)
        for state in ('busy', 'checked', 'current', 'disabled', 'expanded',
                      'hidden', 'pressed', 'selected'):
            self.assertIn(state, literals)

    def test_a35_appendix_does_not_change_frozen_inventory(self):
        before = contracts.load_contract(CONTRACT_PATH)
        path = self.scratch() / 'OPERABILITY.md'
        path.write_bytes(CONTRACT_PATH.read_bytes() + APPENDIX + b'\n\nPublic verification appendix.\n')
        self.assertEqual(contracts.load_contract(path), before)

    def test_a35_ambiguous_or_unsupported_contract_is_refused(self):
        path = self.scratch() / 'OPERABILITY.md'
        path.write_text('# Not a K0 contract\n', encoding='utf-8')
        self.reject(contracts.load_contract, path)

    def test_a35_appendix_documents_public_commands_and_limitations(self):
        contracts.load_contract(CONTRACT_PATH)
        raw=CONTRACT_PATH.read_bytes()
        self.assertEqual(raw.count(APPENDIX),1)
        appendix=raw.split(APPENDIX,1)[1].decode('utf-8')
        for literal in ('python3 -m tools.qa.cdp_probe',
                        'python3 -m tools.qa.atspi_probe',
                        'python3 -m tools.qa.prune', '--timeout-ms', '--node-limit',
                        'INCONCLUSIVE', 'lineage.qa.report/v1'):
            self.assertIn(literal,appendix)

    def test_a03_qa_local_schemas_close_top_level_shapes(self):
        contracts.normalize_name('QA schemas')
        for filename,identifier in (('inventory.schema.json','lineage.qa.inventory/v1'),
                                    ('report.schema.json','lineage.qa.report/v1')):
            schema=json.loads((ROOT/'tools/qa'/filename).read_text('utf-8'))
            self.assertEqual(schema['type'],'object')
            self.assertIs(schema['additionalProperties'],False)
            self.assertEqual(schema['properties']['schema']['const'],identifier)
            self.assertEqual(set(schema['required']),set(schema['properties']))

    def test_a26_ui_generated_operation_identity_is_bound_later(self):
        value=loaded_inventory()
        value['contexts'][0]['postconditions']=[dict(
            operation='Create agent',tool='agent_create',actor='alpha-root',op_id=None,
            kind='agent.born',entity_id='child-root',run_id=None,expect='commit',code=None)]
        contracts.validate_inventory(value,contract=contracts.load_contract(CONTRACT_PATH))

    def test_a03_public_export_signatures(self):
        contracts.normalize_name('Public interface')
        from tools.qa import atspi_probe, cdp_pipe, evidence, journeys, prune
        targets=[
            (contracts.load_contract,['path'],()),
            (contracts.normalize_name,['value'],()),
            (contracts.identity_key,['kind','identity'],()),
            (contracts.validate_inventory,['value','contract'],('contract',)),
            (inventory.source_inventory,['root','contract'],('contract',)),
            (inventory.compare_inventory,['documented','source','observed'],()),
            (report.make_report,['method','scope','checks','artifacts','context'],('method','scope','checks','artifacts','context')),
            (report.exit_code,['report'],()),
            (report.emit,['report','write'],('write',)),
            (cdp_pipe.PipeClient.__init__,['self','argv','timeout_ms'],('timeout_ms',)),
            (cdp_pipe.PipeClient.start,['self'],()),
            (cdp_pipe.PipeClient.call,['self','method','params','session_id'],('session_id',)),
            (cdp_pipe.PipeClient.close,['self'],()),
            (cdp_probe.probe,['url','browser','inventory','contract','timeout_ms'],('url','browser','inventory','contract','timeout_ms')),
            (atspi_probe.observe,['browser_pid','desktop','timeout_ms','node_limit'],('browser_pid','desktop','timeout_ms','node_limit')),
            (atspi_probe.probe,['url','browser','xvfb','session_bus','inventory','contract','timeout_ms','node_limit'],('url','browser','xvfb','session_bus','inventory','contract','timeout_ms','node_limit')),
            (prune.transform,['nodes'],()),
            (prune.compare,['raw','pruned','required','complete'],('required','complete')),
            (journeys.check_postcondition,['expected','result','events','observed'],('expected','result','events','observed')),
            (evidence.verify_capsule,['records','artifact_root','expected'],('artifact_root','expected'))]
        for function,names,keyword_only in targets:
            signature=inspect.signature(function)
            self.assertEqual(list(signature.parameters),names)
            for name in keyword_only:
                self.assertEqual(signature.parameters[name].kind,inspect.Parameter.KEYWORD_ONLY)
                if name!='session_id':
                    self.assertIs(signature.parameters[name].default,inspect.Parameter.empty)
        for function in (cdp_probe.main,atspi_probe.main,prune.main):
            signature=inspect.signature(function)
            self.assertEqual(list(signature.parameters),['argv'])
            self.assertIsNone(signature.parameters['argv'].default)
        self.assertIsNone(inspect.signature(cdp_pipe.PipeClient.call).parameters['session_id'].default)

    def test_a03_good_inventory_is_accepted_without_mutation(self):
        value = loaded_inventory()
        before = copy.deepcopy(value)
        self.assertIsNone(contracts.validate_inventory(
            value, contract=contracts.load_contract(CONTRACT_PATH)))
        self.assertEqual(value, before)

    def test_a03_hostile_scenario_text_remains_passive(self):
        value = loaded_inventory()
        sentinel = self.scratch() / 'sentinel'
        value['scenario'] = '$(touch ' + str(sentinel) + '); <script>never()</script>'
        contracts.validate_inventory(value, contract=contracts.load_contract(CONTRACT_PATH))
        self.assertFalse(sentinel.exists())

    def test_a03_a07_known_empty_head_zero_is_not_unknown(self):
        value = loaded_inventory()
        self.assertEqual(value['contexts'][0]['head'], 0)
        contracts.validate_inventory(value, contract=contracts.load_contract(CONTRACT_PATH))
        value['contexts'][0]['head'] = None
        contracts.validate_inventory(value, contract=contracts.load_contract(CONTRACT_PATH))

    def test_a13_identity_keys_do_not_follow_input_order(self):
        ids = ('alpha-root', 'agent-with-a-long-persisted-identity', 'beta-root')
        first = {x: contracts.identity_key('agent', x) for x in ids}
        second = {x: contracts.identity_key('agent', x) for x in reversed(ids)}
        self.assertEqual(first, second)
        self.assertEqual(ids, ('alpha-root', 'agent-with-a-long-persisted-identity', 'beta-root'))

    def test_a13_category_changes_long_identity_digest(self):
        identity = 'a' * 21
        self.assertNotEqual(contracts.identity_key('agent', identity),
                            contracts.identity_key('unit', identity))

    def test_a03_a12_nfc_whitespace_normalization(self):
        self.assertEqual(contracts.normalize_name('  Cafe\u0301\t \n action\u00a0 '),
                         'Café action')
        self.assertEqual(contracts.normalize_name('é' * 32), 'é' * 32)
        self.assertEqual(contracts.normalize_name('é' * 32 + 'x'), 'é' * 32 + 'x')


def invalid_inventory_test(mutate):
    def test(self):
        value = loaded_inventory()
        mutate(value)
        self.reject(contracts.validate_inventory, value,
                    contract=contracts.load_contract(CONTRACT_PATH))
    return test


INVALID_INVENTORIES = {
    'a03_extra_root_key': lambda v: v.update(extra=True),
    'a03_extra_nested_key': lambda v: v['contexts'][0]['actions'][0].update(extra=True),
    'a03_duplicate_context': lambda v: v['contexts'].append(copy.deepcopy(v['contexts'][0])),
    'a03_empty_contexts': lambda v: v.update(contexts=[]),
    'a03_boolean_head': lambda v: v['contexts'][0].update(head=True),
    'a03_negative_head': lambda v: v['contexts'][0].update(head=-1),
    'a03_unsafe_integer_head': lambda v: v['contexts'][0].update(head=SAFE_INTEGER + 1),
    'a03_float_head': lambda v: v['contexts'][0].update(head=1.0),
    'a03_changed_contract_hash': lambda v: v.update(contract_sha256='f' * 64),
    'a03_uppercase_hash': lambda v: v.update(contract_sha256='A' * 64),
    'a03_unknown_action': lambda v: v['contexts'][0]['actions'][0].update(action='invent-action'),
    'a03_unknown_screen': lambda v: v['contexts'][0].update(screen='debug'),
    'a03_wrong_route_screen': lambda v: v['contexts'][0].update(route='#/ledger'),
    'a03_entity_without_id': lambda v: v['contexts'][0]['actions'][0].update(entity='agent'),
    'a03_id_without_entity': lambda v: v['contexts'][0]['actions'][0].update(id='alpha-root'),
    'a03_wrong_role': lambda v: v['contexts'][0]['actions'][0].update(role='button'),
    'a03_wrong_name_template': lambda v: v['contexts'][0]['actions'][0].update(name='Invented navigation'),
    'a03_conflicting_duplicate_expectation': lambda v: v['contexts'][0]['actions'].append(
        dict(v['contexts'][0]['actions'][0], availability='disabled', reason='Conflicting')),
    'a02_legacy_selector': lambda v: v['contexts'][0]['actions'][0].update(selector='[data-testid="skip"]'),
    'a14_positional_selector': lambda v: v['contexts'][0]['actions'][0].update(selector='button:nth-child(2)'),
    'a14_transient_selector': lambda v: v['contexts'][0]['actions'][0].update(selector='[backendNodeId="42"]'),
    'a14_observer_id_selector': lambda v: v['contexts'][0]['actions'][0].update(selector='#AXNode42'),
    'a14_selector_identity_mismatch': lambda v: next(a for a in v['contexts'][0]['actions']
        if a['action'] == 'open-agent').update(selector='[data-lin-id="other-agent"] [data-lin-action="open-agent"]'),
    'a03_disabled_without_reason': lambda v: v['contexts'][0]['actions'][0].update(availability='disabled'),
    'a03_unknown_availability': lambda v: v['contexts'][0]['actions'][0].update(availability='sometimes'),
    'a03_invalid_surrogate': lambda v: v.update(scenario='\ud800'),
}
for label, mutate in INVALID_INVENTORIES.items():
    setattr(ContractTests, 'test_' + label, invalid_inventory_test(mutate))


def key_test(kind, identity):
    def test(self):
        expected = (identity if len(identity.encode('utf-8')) <= 20 else
                    identity[:7] + '-' + hashlib.sha256(
                        (kind + '\0' + identity).encode('utf-8')).hexdigest()[:12])
        self.assertEqual(contracts.identity_key(kind, identity), expected)
    return test


for label, kind, identity in (
        ('below_threshold', 'agent', 'a' * 19),
        ('at_threshold', 'agent', 'a' * 20),
        ('above_threshold', 'agent', 'a' * 21),
        ('long_agent', 'agent', 'a' * 64),
        ('long_unit', 'unit', 'U' * 64),
        ('skill_pin', 'skill', 'public-skill@' + '0' * 64)):
    setattr(ContractTests, 'test_a13_' + label, key_test(kind, identity))


class StrictInputTests(OracleCase):
    def assert_bad_json(self, raw):
        rc, value = self.main_report(raw)
        self.assertEqual(rc, 2)
        self.verdict(value, 'INCONCLUSIVE', 'bad_config')

    def test_a03_duplicate_json_key(self):
        raw = canonical(loaded_inventory())
        self.assert_bad_json(raw[:-1] + b',"schema":"lineage.qa.inventory/v1"}')

    def test_a03_nested_duplicate_json_key(self):
        raw = canonical(loaded_inventory()).replace(b'"head":0', b'"head":0,"head":0')
        self.assert_bad_json(raw)

    def test_a03_invalid_utf8(self):
        self.assert_bad_json(b'{"schema":"\xff"}')

    def test_a03_unpaired_surrogate(self):
        self.assert_bad_json(canonical(loaded_inventory()).replace(b'"good"', b'"\\ud800"'))

    def test_a03_trailing_json(self):
        self.assert_bad_json(canonical(loaded_inventory()) + b' {}')

    def test_a03_nonfinite_numbers(self):
        for token in (b'NaN', b'Infinity', b'-Infinity'):
            self.assert_bad_json(canonical(loaded_inventory()).replace(b'"head":0', b'"head":' + token))

    def test_a03_strict_utf8_bom_is_not_silent_input(self):
        self.assert_bad_json(b'\xef\xbb\xbf' + canonical(loaded_inventory()))

    def test_a14_frozen_positional_inventory_refused(self):
        self.reject(contracts.validate_inventory,
                    json.loads((FIXTURES / 'inventory-positional.json').read_text('utf-8')),
                    contract=contracts.load_contract(CONTRACT_PATH))
