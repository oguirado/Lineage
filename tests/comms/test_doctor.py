"""Healthy and fail-closed preflight, with no writes, network or subprocesses."""
from dataclasses import replace
import json
from pathlib import Path
from unittest import mock

from .support import CommsCase

CHECKS = {'home_permissions', 'registry', 'ledger', 'contract_conformance',
          'references', 'ui_bundle', 'json_endpoints'}


class DoctorTests(CommsCase):
    def doctor(self, expected=0):
        result = json.loads(self.cli('doctor', '--json', expected=expected).stdout)
        self.assertEqual(set(result) - {'unverified'}, {'ok', 'checks'})  # A-OPC1: declared non-verification (R4)
        self.assertEqual({item['id'] for item in result['checks']}, CHECKS)
        for item in result['checks']:
            self.assertEqual(set(item), {'id', 'ok', 'detail'})
            self.assertIs(type(item['ok']), bool)
            self.assertIsInstance(item['detail'], str)
        return {item['id']: item for item in result['checks']}

    def endpoint(self, config=None):
        endpoint = self.home / 'family' / 'receiver'
        endpoint.mkdir(parents=True, mode=0o700)
        (self.home / 'family').chmod(0o700)
        path = endpoint / 'config.json'
        path.write_text(json.dumps(config or {'endpoint': 'receiver', 'sources': ['sender'],
                                              'tools': ['agent_list']}))
        path.chmod(0o600)
        return path

    def test_healthy_private_home_is_read_only(self):
        self.birth()
        before = self.tree()
        checks = self.doctor()
        self.assertTrue(all(item['ok'] for item in checks.values()))
        self.assertIn('registered tools', checks['registry']['detail'])
        self.assertEqual(before, self.tree())
        self.assertIn('OK home_permissions', self.cli('doctor').stdout)

    def test_missing_ledger_is_a_failed_check_without_creation(self):
        before = self.tree()
        self.assertFalse(self.doctor(3)['ledger']['ok'])
        self.assertEqual(before, self.tree())

    def test_valid_config_and_committed_home_are_read_only(self):
        self.birth()
        self.endpoint()
        before = self.tree()
        self.assertTrue(self.doctor()['json_endpoints']['ok'])
        self.assertEqual(before, self.tree())

    def test_nonprivate_home_and_symlinked_home_fail(self):
        self.home.chmod(0o755)
        self.assertFalse(self.doctor(3)['home_permissions']['ok'])
        self.home.chmod(0o700)
        link = Path(self.temporary.name) / 'linked'
        link.symlink_to(self.home, target_is_directory=True)
        result = json.loads(self.cli('doctor', '--json', home=link, expected=3).stdout)
        self.assertFalse(next(c for c in result['checks'] if c['id'] == 'home_permissions')['ok'])

    def test_missing_home_is_reported_without_creation(self):
        missing = self.home / 'missing'
        result = json.loads(self.cli('doctor', '--json', home=missing, expected=3).stdout)
        self.assertFalse(result['ok'])
        self.assertFalse(missing.exists())

    def test_malformed_and_unsafe_endpoint_configs_fail_without_touching_files(self):
        path = self.endpoint()
        for content in ('{}', '{"endpoint":"receiver","sources":[],"tools":["unknown_tool"]}',
                        '{"endpoint":"receiver","sources":[],"tools":[],"extra":1}'):
            with self.subTest(content=content):
                path.write_text(content)
                before = self.tree()
                self.assertFalse(self.doctor(3)['json_endpoints']['ok'])
                self.assertEqual(before, self.tree())
        path.write_text('{"endpoint":"receiver","sources":[],"tools":[]}')
        path.chmod(0o666)
        self.assertFalse(self.doctor(3)['json_endpoints']['ok'])
        path.chmod(0o600)
        target = self.home / 'external-config.json'
        path.replace(target)
        path.symlink_to(target)
        self.assertFalse(self.doctor(3)['json_endpoints']['ok'])

    def test_empty_grants_are_valid_but_authorize_nothing(self):
        self.birth()
        self.endpoint({'endpoint': 'receiver', 'sources': [], 'tools': []})
        self.assertTrue(self.doctor()['json_endpoints']['ok'])

    def test_tampered_ledger_is_reported(self):
        self.birth()
        path = self.home / 'ledger/main/events.jsonl'
        path.write_bytes(path.read_bytes().replace(b'Guide agent', b'Other agent'))
        before = self.tree()
        self.assertFalse(self.doctor(3)['ledger']['ok'])
        self.assertEqual(before, self.tree())

    def test_registry_failure_and_schema_drift_are_health_failures(self):
        from lineage.core import doctor, registry
        reg = registry.load()
        with mock.patch.object(doctor.extensions, 'load', side_effect=RuntimeError('private')):
            result = doctor.report(self.home)
        self.assertFalse(result['ok'])
        self.assertEqual({item['id'] for item in result['checks']}, CHECKS)
        tools = dict(reg.tools)
        tools['agent_get'] = replace(tools['agent_get'], input_schema={'type': 'object'})
        drift = registry.Registry(tools, reg.validators, reg.folds)
        result = doctor.report(self.home, registry=drift)
        check = next(item for item in result['checks'] if item['id'] == 'contract_conformance')
        self.assertFalse(check['ok'])
        self.assertIn('agent_get', check['detail'])

    def test_missing_ui_and_references_are_not_green(self):
        from lineage.core import app, doctor, registry
        reg = registry.load()
        real_dispatch = app.dispatch
        def dispatch(name, args, **kwargs):
            if name == 'reference_verify':
                return app.DispatchResult({'ok': False, 'code': 'hash_mismatch'}, 'execution')
            return real_dispatch(name, args, **kwargs)
        with mock.patch.object(app, 'dispatch', side_effect=dispatch):
            result = doctor.report(self.home, registry=reg, root=self.home)
        checks = {item['id']: item for item in result['checks']}
        self.assertFalse(checks['ui_bundle']['ok'])
        self.assertFalse(checks['references']['ok'])

    def test_doctor_does_not_open_network_or_spawn_commands(self):
        from lineage.core import doctor, registry
        reg = registry.load()
        self.birth()
        before = self.tree()
        with mock.patch('socket.socket', side_effect=AssertionError('network')), \
                mock.patch('subprocess.Popen', side_effect=AssertionError('subprocess')):
            self.assertTrue(doctor.report(self.home, registry=reg)['ok'])
        self.assertEqual(before, self.tree())

    def test_invalid_options_are_argument_errors(self):
        for args in (('doctor', '--extra'), ('doctor', '--json', '--json')):
            self.assertEqual(json.loads(self.cli(*args, expected=2).stdout)['code'], 'bad_args')
