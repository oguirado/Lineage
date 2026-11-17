"""Operable-program controls: real subprocess carriers and independent evidence."""
from contextlib import contextmanager
import hashlib
import http.client
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
CANCELLED = {'ok': False, 'code': 'bad_op', 'detail': 'cancelled by order'}


class OperableTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='lineage-operable-test-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        self.base = self.endpoint('test-main')

    def endpoint(self, name):
        family = self.home / 'family'
        family.mkdir(mode=0o700, exist_ok=True)
        root = family / name
        root.mkdir(mode=0o700)
        self.publish(root / 'config.json', {'endpoint': name, 'sources': ['test-source'],
            'tools': ['skill_publish', 'skill_retire', 'agent_create', 'run_beat',
                      'ledger_events', 'ledger_verify', 'openfresnel_spawn']})
        (root / 'spool').mkdir(mode=0o700)
        return root

    def publish(self, path, value):
        path.write_bytes(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())
        path.chmod(0o600)

    def package(self, name='fixture-skill'):
        return {'skill_id': name, 'files': [{'path': 'SKILL.md', 'content': 'Passive context.\n'}]}

    def argv(self, *tail):
        return [sys.executable, '-B', '-m', 'lineage', '--home', str(self.home), *tail]

    def command(self, *tail, raw=None, expected=0):
        result = subprocess.run(self.argv(*tail), input=raw, capture_output=True,
                                cwd=ROOT, env=self.environment, timeout=15)
        self.assertEqual(result.returncode, expected, (result.stdout, result.stderr))
        self.assertNotIn(b'Traceback', result.stdout + result.stderr)
        return json.loads(result.stdout)

    def call(self, tool, args, *flags, expected=0):
        return self.command('call', tool, '--json', json.dumps(args), *flags, expected=expected)

    def envelope(self, identity, tool='skill_publish', args=None, *, target='test-main', dry_run=None):
        return {'schema': 'lineage.family/1', 'id': identity, 'source': 'test-source',
                'target': target, 'kind': 'call', 'agent': 'fixture-agent',
                'payload': {'tool': tool, 'args': self.package() if args is None else args,
                            **({} if dry_run is None else {'dry_run': dry_run})}}

    def deliver(self, value, *, expected=0):
        return self.command('json', raw=json.dumps(value).encode(), expected=expected)['result']

    def files(self, application=False):
        return {p.relative_to(self.home).as_posix(): p.read_bytes() for p in self.home.rglob('*')
                if p.is_file() and (not application or p.relative_to(self.home).parts[0] != 'family')}

    def stop(self, process):
        if process.poll() is None:
            self.assertGreater(process.pid, 1)
            process.kill()
        process.wait(timeout=5)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()

    def mcp(self, params):
        raw = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': params}).encode() + b'\n'
        return self.command('mcp', raw=raw)

    def create_agent(self):
        references = [self.call('reference_get', {'ref_id': ref})['untrusted']['reference']
                      for ref in ('gold_s1', 'memory_v21')]
        args = {'agent_id': 'fixture-agent', 'display_name': 'Fixture', 'workflow': 'develop',
                'language': 'python', 'allowed_seats': [{'model': 'fixture', 'effort': 'low', 'mode': 'headless'}],
                'references': [{'id': ref['id'], 'sha256': ref['sha256']} for ref in references],
                'skills': [], 'agent': 'fixture-agent', 'op_id': 'fixture:/birth'}
        self.call('agent_create', args)
        return args

    def test_risk_annotations_match_cli_mcp_capabilities_and_http(self):
        tools = self.command('tools')['tools']
        raw = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}).encode() + b'\n'
        self.assertEqual(tools, self.command('mcp', raw=raw)['result']['tools'])
        caps = {'schema': 'lineage.family/1', 'id': 'capstest1', 'source': 'test-source',
                'target': 'test-main', 'kind': 'capabilities', 'agent': 'fixture-agent', 'payload': {}}
        allowed = json.loads((self.base / 'config.json').read_bytes())['tools']
        self.assertEqual([row for row in tools if row['name'] in allowed],
                         self.deliver(caps)['untrusted']['tools'])
        by_name = {row['name']: row['annotations'] for row in tools}
        for name in ('agent_create', 'skill_publish'):
            self.assertEqual(by_name[name]['lineage_risk'], 'publish')
        for name in ('skill_retire', 'agent_retire'):
            self.assertEqual(by_name[name]['lineage_risk'], 'irreversible')
            self.assertTrue(by_name[name]['destructiveHint'])
        self.assertEqual(by_name['ledger_export']['lineage_risk'], 'prepare')
        self.assertTrue(by_name['openfresnel_spawn']['openWorldHint'])
        self.assertTrue(by_name['ledger_verify']['readOnlyHint'])
        process = subprocess.Popen(self.argv('serve'), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   cwd=ROOT, env=self.environment)
        self.addCleanup(self.stop, process)
        self.assertTrue(select.select([process.stderr], [], [], 5)[0])
        startup = json.loads(process.stderr.readline())
        connection = http.client.HTTPConnection('127.0.0.1', startup['port'], timeout=5)
        try:
            connection.request('GET', '/api/tools')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())['tools'], tools)
        finally:
            connection.close()

    def test_risk_is_frozen_and_schema_is_unchanged(self):
        from dataclasses import FrozenInstanceError
        from lineage.core import doctor, registry
        loaded = registry.load()
        self.assertEqual(doctor.contract_mismatches(loaded, root=ROOT), [])
        with self.assertRaises(FrozenInstanceError):
            loaded.tools['skill_publish'].risk = 'read'
        self.assertNotIn('dry_run', loaded.tools['skill_publish'].input_schema['properties'])

    def test_cli_dry_run_validates_and_leaves_every_file_unchanged(self):
        args = {**self.package(), 'agent': 'fixture-agent', 'op_id': 'literal:/operation.1'}
        before = self.files()
        result = self.call('skill_publish', args, '--dry-run')['untrusted']
        self.assertEqual(self.files(), before)
        event = result['events'][0]
        self.assertEqual((result['dry_run'], result['expected_head'], event['kind']), (True, 0, 'skill.published'))
        self.call('skill_publish', args)
        history = self.call('ledger_events', {})['untrusted']['events']
        self.assertEqual(history[0]['op_id'], args['op_id'])
        from lineage.core.journal import canonical_bytes
        self.assertEqual(event['payload_sha256'], hashlib.sha256(canonical_bytes(history[0]['payload'])).hexdigest())
        before = self.files()
        bad = {**args, 'expected_head': 0, 'files': [{'path': 'SKILL.md', 'content': 'Changed'}]}
        self.assertEqual(self.call('skill_publish', bad, '--dry-run', expected=3)['code'], 'stale_rev')
        self.assertEqual(before, self.files())

    def test_dry_run_does_not_replay_an_old_success_over_current_validation(self):
        args = {**self.package(), 'agent': 'fixture-agent', 'op_id': 'literal:/original', 'expected_head': 0}
        self.call('skill_publish', args)
        self.assertEqual(self.call('skill_publish', args, '--dry-run', expected=3)['code'], 'stale_rev')
        self.assertEqual(self.call('skill_publish', args)['untrusted']['commit']['head'], 1)

    def test_mcp_dry_run_and_invalid_control(self):
        before = self.files()
        args = {**self.package(), 'agent': 'fixture-agent', 'op_id': 'mcp:/dry'}
        reply = self.mcp({'name': 'skill_publish', 'arguments': args, '_meta': {'dry_run': True}})
        result = json.loads(reply['result']['content'][0]['text'])
        self.assertTrue(result['untrusted']['dry_run'])
        self.assertEqual(before, self.files())
        self.assertEqual(self.mcp({'name': 'skill_publish', 'arguments': args,
                                   '_meta': {'dry_run': 'true'}})['error']['code'], -32602)
        self.assertEqual(self.call('skill_publish', {**args, 'dry_run': True}, expected=2)['code'], 'bad_args')

    def test_json_dry_run_has_no_retention_and_refreshes_its_snapshot(self):
        request = self.envelope('preview01', dry_run=True)
        before = self.files(application=True)
        first = self.deliver(request)['untrusted']
        self.assertEqual(before, self.files(application=True))
        self.assertFalse((self.base / 'dedup' / 'preview01.json').exists())
        self.call('skill_publish', {**self.package('other-skill'), 'agent': 'fixture-agent', 'op_id': 'other:/write'})
        second = self.deliver(request)['untrusted']
        self.assertEqual((first['expected_head'], second['expected_head']), (0, 1))
        self.assertEqual((self.base / 'state' / 'preview01.done').read_bytes(), b'<!-- preview01_DONE -->\n')
        for invalid in ('true', None, 1):
            bad = self.envelope('badflag01', dry_run=False)
            bad['payload']['dry_run'] = invalid
            self.assertEqual(self.deliver(bad, expected=2)['code'], 'bad_args')

    def test_external_dry_run_never_publishes_or_runs_a_program(self):
        commands = self.home / 'commands'
        commands.mkdir(mode=0o700)
        args = {'agent': 'fixture-agent', 'op_id': 'external:/dry', 'mode': 'drain',
                'endpoint': 'test-main', 'commands_dir': str(commands)}
        before = self.files()
        result = self.call('openfresnel_spawn', args, '--dry-run')['untrusted']
        self.assertEqual(result['events'][0]['kind'], 'openfresnel.command')
        self.assertEqual(before, self.files())
        self.assertEqual(list(commands.iterdir()), [])
        args['endpoint'] = 'unsafe/endpoint'
        self.assertEqual(self.call('openfresnel_spawn', args, '--dry-run', expected=2)['code'], 'bad_args')

    def test_export_preview_does_not_create_a_projection(self):
        self.call('skill_publish', {**self.package(), 'agent': 'fixture-agent', 'op_id': 'export:/seed'})
        before = self.files()
        data = self.call('ledger_export', {'out': 'exports/probe'}, '--dry-run')['untrusted']
        self.assertEqual(data['events'][0]['kind'], 'ledger.export')
        self.assertEqual(before, self.files())
        self.assertFalse((self.home / 'exports').exists())
        (self.home / 'exports').symlink_to(self.base, target_is_directory=True)
        self.assertEqual(self.call('ledger_export', {'out': 'exports/probe'}, '--dry-run', expected=3)['code'], 'bad_args')
        (self.home / 'exports').unlink()
        self.assertEqual(self.call('ledger_export', {'out': '../escape'}, '--dry-run', expected=2)['code'], 'bad_args')

    def test_cancel_one_of_two_spooled_requests_without_stopping_consumer(self):
        first, second = self.envelope('cancel001'), self.envelope('survive01', args=self.package('survivor-skill'))
        for request in (first, second):
            self.publish(self.base / 'spool' / (request['id'] + '.json'), request)
        abort = self.base / 'spool' / 'cancel001.abort'
        abort.touch(mode=0o600)
        process = subprocess.Popen(self.argv('drain', '--endpoint', 'test-main', '--poll-ms', '5'),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, env=self.environment)
        self.addCleanup(self.stop, process)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and not (self.base / 'state' / 'survive01.done').exists():
            self.assertIsNone(process.poll())
            time.sleep(0.01)
        self.assertTrue((self.base / 'state' / 'survive01.done').exists())
        self.assertEqual(json.loads((self.base / 'state' / 'cancel001.result.json').read_bytes())['result'], CANCELLED)
        history = self.call('ledger_events', {})['untrusted']['events']
        self.assertEqual([event['payload']['skill_id'] for event in history], ['survivor-skill'])
        self.assertIsNone(process.poll())

    def test_cancel_after_committed_receipt_replays_the_original_commit(self):
        request = self.envelope('committed1')
        first = self.deliver(request)
        (self.base / 'spool' / 'committed1.abort').touch(mode=0o600)
        self.assertEqual(first, self.deliver(request))
        self.assertEqual(self.call('ledger_events', {})['untrusted']['head'], 1)

    def test_unsafe_abort_is_quarantined_without_following_or_dispatch(self):
        request = self.envelope('unsafe001')
        (self.base / 'spool' / 'unsafe001.abort').symlink_to(self.base / 'config.json')
        before = (self.base / 'config.json').read_bytes()
        self.assertEqual(self.deliver(request, expected=2)['code'], 'bad_args')
        self.assertEqual(before, (self.base / 'config.json').read_bytes())
        self.assertEqual(self.call('ledger_events', {})['untrusted']['head'], 0)
        self.assertTrue(any(path.is_symlink() for path in (self.base / 'state').glob('quarantine-*')))

    @contextmanager
    def paused_delivery(self, request, injection):
        notify_read, notify_write = os.pipe()
        resume_read, resume_write = os.pipe()
        script = "import os, sys\nfrom lineage.core import cli, family, journal\n" + injection + "\nraise SystemExit(cli.main(['--home', sys.argv[3], 'json']))\n"
        process = subprocess.Popen([sys.executable, '-B', '-c', script, str(notify_write), str(resume_read), str(self.home)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   pass_fds=(notify_write, resume_read), cwd=ROOT, env=self.environment)
        os.close(notify_write)
        os.close(resume_read)
        try:
            process.stdin.write(json.dumps(request).encode())
            process.stdin.close()
            process.stdin = None
            self.assertTrue(select.select([notify_read], [], [], 8)[0])
            self.assertEqual(os.read(notify_read, 16), b'ready')
            yield process, resume_write
        finally:
            os.close(notify_read)
            os.close(resume_write)
            self.stop(process)

    def test_abort_arriving_during_preparation_is_checked_under_commit_lock(self):
        injection = """
original = journal._callback
def callback(function, history, event):
    result = original(function, history, event)
    if event.get('kind') == 'skill.published' and 'sha256' in event:
        os.write(int(sys.argv[1]), b'ready')
        os.read(int(sys.argv[2]), 1)
    return result
journal._callback = callback
"""
        for identity, dry_run in [('lateabort', False), ('latedry01', True)]:
            with self.subTest(dry_run=dry_run), self.paused_delivery(
                    self.envelope(identity, dry_run=dry_run), injection) as (process, resume):
                (self.base / 'spool' / (identity + '.abort')).touch(mode=0o600)
                os.write(resume, b'x')
                stdout, stderr = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 3, stderr)
                self.assertEqual(json.loads(stdout)['result'], CANCELLED)
        self.assertEqual(self.call('ledger_events', {})['untrusted']['events'], [])

    def test_kill_after_commit_recovers_pending_identity_without_duplicate(self):
        injection = """
original = family.Mailbox._witness
def witness(self, value, result, name):
    original(self, value, result, name)
    if 'untrusted' in result:
        os.write(int(sys.argv[1]), b'ready')
        os.read(int(sys.argv[2]), 1)
family.Mailbox._witness = witness
"""
        request = self.envelope('crashreq1')
        with self.paused_delivery(request, injection) as (process, _):
            self.assertGreater(process.pid, 1)
            process.kill()
            process.wait(timeout=5)
        self.assertFalse((self.base / 'state' / 'crashreq1.done').exists())
        self.assertEqual(json.loads((self.base / 'dedup' / 'crashreq1.json').read_bytes())['phase'], 'pending')
        lock = self.base / 'consumer.lock'
        self.assertEqual(lock.read_bytes(), b'owned\n')
        lock.unlink()  # Only this test's waited-for child owned this isolated endpoint.
        (self.base / 'spool' / 'crashreq1.abort').touch(mode=0o600)
        before = self.call('ledger_events', {})['untrusted']
        first = self.deliver(request)
        self.assertEqual(first, self.deliver(request))
        after = self.call('ledger_events', {})['untrusted']
        self.assertEqual(before, after)
        self.assertEqual(after['head'], 1)
        from lineage.core.envelope import operation_id
        self.assertEqual(after['events'][0]['op_id'], operation_id(request))

    def test_cancelled_preview_does_not_create_a_retained_result(self):
        request = self.envelope('dryabort1', dry_run=True)
        (self.base / 'spool' / 'dryabort1.abort').touch(mode=0o600)
        self.assertEqual(self.deliver(request, expected=3), CANCELLED)
        self.assertFalse((self.base / 'dedup' / 'dryabort1.json').exists())
        self.assertEqual(self.files(application=True), {})

    def test_agent_preview_uses_actual_prepare_without_creating_agent_paths(self):
        args = self.create_agent()
        args = {**args, 'agent_id': 'preview-agent', 'op_id': 'preview:/agent'}
        before = self.files()
        result = self.call('agent_create', args, '--dry-run')['untrusted']
        self.assertEqual(result['events'][0]['kind'], 'agent.born')
        self.assertEqual(before, self.files())
        self.call('agent_create', args)
        self.assertEqual(self.call('agent_create', args, '--dry-run', expected=3)['code'], 'conflict')

    def test_rehearsal_blocks_unprepared_filesystem_side_effects(self):
        from lineage.core import app, registry
        destination = self.home / 'forbidden-output'
        def unsafe(args, *, context):
            destination.write_text('must never be written')
            return {}
        tool = registry.ToolSpec('unsafe_fixture', 'Attempt an unprepared effect.',
                                 {'type': 'object', 'additionalProperties': False}, unsafe, True)
        loaded = registry.Registry({'unsafe_fixture': tool}, {}, {})
        context = app.create_context(self.home, registry=loaded)
        result = app.preview('unsafe_fixture', {}, context=context, registry=loaded)
        self.assertEqual(result.payload['code'], 'bad_op')
        self.assertFalse(destination.exists())
        self.assertIs(loaded.tools['unsafe_fixture'].handler, unsafe)

    def test_done_is_last_and_receipt_alone_is_in_progress(self):
        from lineage.core import app, family, registry
        loaded = registry.load()
        context = app.create_context(self.home, registry=loaded)
        box = family.Mailbox('test-main', ctx=context)
        box.open()
        self.addCleanup(box.release)
        original = family._atomic_write
        def fail_done(directory, name, *args, **kwargs):
            if name.endswith('.done'):
                raise OSError('injected marker publication failure')
            return original(directory, name, *args, **kwargs)
        with patch.object(family, '_atomic_write', fail_done):
            with self.assertRaises(OSError):
                box.publish('sentinel1', {'ok': False, 'code': 'bad_args'})
        self.assertTrue((self.base / 'state' / 'sentinel1.result.json').is_file())
        self.assertIsNone(box.completed('sentinel1'))
        box.publish('sentinel1', {'ok': False, 'code': 'bad_args'})
        self.assertEqual(box.completed('sentinel1')['result']['code'], 'bad_args')
        original_read = family._read_regular
        def interrupted_read(directory, name, *args, **kwargs):
            result = original_read(directory, name, *args, **kwargs)
            if name == 'sentinel1.result.json':
                os.unlink('sentinel1.done', dir_fd=directory)
            return result
        with patch.object(family, '_read_regular', interrupted_read):
            self.assertIsNone(box.completed('sentinel1'))
        box.publish('sentinel1', {'ok': False, 'code': 'bad_args'})
        with patch.object(family, '_atomic_write', fail_done):
            with self.assertRaises(OSError):
                box.publish('sentinel1', {'ok': False, 'code': 'internal'})
        self.assertIsNone(box.completed('sentinel1'))

    def test_verification_and_doctor_declare_unmeasured_agent_fitness(self):
        agent = self.create_agent()
        self.call('run_open', {'run_id': 'openonly1', 'agent_id': 'fixture-agent',
            'seat': agent['allowed_seats'][0],
            'task': {'id': 'taskonly1', 'kind': 'test', 'language': 'python'},
            'parents_context': [], 'memory_arm': 'none', 'agent': 'fixture-agent', 'op_id': 'fixture:/open'})
        report = self.call('ledger_verify', {})['untrusted']
        self.assertTrue(report['valid'])
        # A-OPC1: ledger_verify keeps its frozen closed result; R4 gaps live in doctor.
        self.assertNotIn('unverified', report)
        doctor = self.command('doctor', '--json', expected=0)
        scopes = {item['scope'] for item in doctor['unverified']}
        self.assertIn('scorecard:fixture-agent', scopes)
        self.assertIn('external_openfresnel', scopes)
        self.assertEqual(report, self.deliver(self.envelope('verify001', tool='ledger_verify', args={}))['untrusted'])

    def test_doctor_operable_runs_mechanical_checks_in_a_temporary_home(self):
        before = self.files()
        report = self.command('doctor', '--operable')
        self.assertTrue(report['ok'])
        checks = {item['id']: item['ok'] for item in report['checks']}
        for name in ('risk_classes', 'dry_run_no_effects', 'cancel_one_request',
                     'kill_resume_without_duplicate', 'shared_agent_serializes',
                     'done_sentinel', 'independent_verification'):
            self.assertIs(checks[name], True)
        self.assertTrue(report['unverified'])
        self.assertEqual(before, self.files())


if __name__ == '__main__':
    unittest.main()
