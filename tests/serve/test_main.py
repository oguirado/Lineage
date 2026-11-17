"""Exercise the public serve command with owned loopback subprocesses."""
import http.client
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]


class MainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'home'
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')

    def command(self, *tail):
        return [sys.executable, '-m', 'lineage', '--home', str(self.home),
                'serve', *tail]

    def run_command(self, *tail):
        return subprocess.run(self.command(*tail), cwd=ROOT, env=self.env,
                              capture_output=True, timeout=10)

    def start(self, *tail, script=None):
        command = self.command(*tail)
        if script is not None:
            command = [sys.executable, '-c', script, *command[3:]]
        child = subprocess.Popen(command, cwd=ROOT, env=self.env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertGreater(child.pid, 1)
        self.addCleanup(self.close_child, child)
        deadline = time.monotonic() + 10
        data = b''
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            while b'\n' not in data:
                remaining = deadline - time.monotonic()
                self.assertGreater(remaining, 0, 'No startup record before deadline')
                self.assertTrue(selector.select(remaining), 'No startup output')
                chunk = os.read(child.stdout.fileno(), 4096)
                self.assertTrue(chunk, 'Command exited without a startup record')
                data += chunk
        line, rest = data.split(b'\n', 1)
        self.assertEqual(rest, b'', 'Extra startup stdout')
        record = json.loads(line)
        self.assertEqual(set(record), {'ok', 'url', 'port'})
        self.assertIs(record['ok'], True)
        self.assertIs(type(record['port']), int)
        self.assertGreater(record['port'], 0)
        self.assertEqual(record['url'], f"http://127.0.0.1:{record['port']}/")
        return child, record['port']

    @staticmethod
    def close_child(child):
        if child.poll() is None and child.pid > 1:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        child.stdout.close()
        child.stderr.close()

    def request(self, port, path):
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
        try:
            connection.request('GET', path)
            response = connection.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            connection.close()

    def stop(self, child, port, sig=signal.SIGTERM):
        self.assertIsNone(child.poll())
        self.assertGreater(child.pid, 1)
        child.send_signal(sig)
        stdout, stderr = child.communicate(timeout=5)
        self.assertEqual(child.returncode, 0, stderr.decode())
        self.assertEqual(stdout, b'')
        self.assertEqual([json.loads(line) for line in stderr.splitlines()],
                         [{'port': port}])
        with socket.socket() as probe:
            probe.settimeout(1)
            self.assertNotEqual(probe.connect_ex(('127.0.0.1', port)), 0)

    def test_cli_start_health_index_and_sigterm(self):
        child, port = self.start('--port', '0')
        status, raw, _ = self.request(port, '/api/health')
        self.assertEqual(status, 200, raw)
        self.assertEqual(json.loads(raw), {'ok': True, 'head': 0,
                         'protocol': 'lineage.family/1', 'fixtures': False})
        self.assertFalse(self.home.exists(), 'Health created runtime state')
        if (ROOT / 'ui' / 'dist' / 'index.html').is_file():
            status, raw, headers = self.request(port, '/')
            self.assertEqual(status, 200, raw)
            self.assertIn(b'lineage-session-token', raw)
            self.assertEqual(headers['Cache-Control'], 'no-store')
        self.stop(child, port)

    def test_default_port_and_sigint(self):
        child, port = self.start()
        self.assertEqual(self.request(port, '/api/health')[0], 200)
        self.stop(child, port, signal.SIGINT)

    def test_custom_ui_dist_and_direct_index_bootstrap(self):
        root = Path(self.temp.name) / 'built-ui'
        root.mkdir()
        (root / 'index.html').write_text('<html><head></head><body>Custom UI</body></html>')
        child, port = self.start('--ui-dist', str(root))
        first = self.request(port, '/')
        second = self.request(port, '/index.html')
        self.assertEqual(first[0], 200)
        self.assertEqual(second[0], 200)
        self.assertEqual(first[1], second[1])
        self.assertIn(b'Custom UI', first[1])
        self.assertEqual(first[1].count(b'lineage-session-token'), 1)
        self.stop(child, port)


    def test_native_dispatch_and_schema_errors(self):
        script = """
from lineage.core import app, cli, registry

def echo(args, *, context):
    return {'value': args['value'], 'null': None,
            'actor': context.actor, 'has_home': context.home.is_absolute()}

schema = {'type': 'object', 'properties': {'value': {'type': 'integer'}},
          'required': ['value'], 'additionalProperties': False}
spec = registry.ToolSpec('echo', 'Echo a synthetic value', schema, echo, False)
raise SystemExit(cli.main(registry=registry.Registry({'echo': spec}, {}, {})))
"""
        child, port = self.start(script=script)
        for args, expected_status in [({'value': 7}, 200), ({'value': True}, 400)]:
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
            try:
                connection.request('POST', '/api/call',
                                   json.dumps({'tool': 'echo', 'args': args}),
                                   {'Content-Type': 'application/json'})
                response = connection.getresponse()
                result = json.loads(response.read())
                self.assertEqual(response.status, expected_status, result)
                if expected_status == 200:
                    self.assertEqual(result, {'untrusted': {'value': 7, 'null': None,
                                                           'actor': None, 'has_home': True}})
                else:
                    self.assertEqual(result['code'], 'bad_args')
            finally:
                connection.close()
        self.assertEqual(json.loads(self.request(port, '/api/tools')[1])['tools'][0]['name'],
                         'echo')
        self.stop(child, port)

    def test_health_reads_verified_journal_and_rejects_corruption(self):
        from lineage.core import journal

        event = journal.transact(self.home, agent='tester', op_id='first-event',
                                 kind='test.event', payload={},
                                 validators={'test.event': lambda history, event: None})
        child, port = self.start()
        status, raw, _ = self.request(port, '/api/health')
        self.assertEqual(status, 200, raw)
        self.assertEqual(json.loads(raw)['head'], event['lamport'])
        path = self.home / 'ledger' / 'main' / 'events.jsonl'
        path.write_bytes(path.read_bytes().replace(b'test.event', b'fake.event'))
        status, raw, _ = self.request(port, '/api/health')
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(raw)['code'], 'internal')
        self.assertNotIn(str(self.home).encode(), raw)
        self.stop(child, port)

    def test_missing_fixtures_fail_before_binding(self):
        result = self.run_command('--fixtures', str(Path(self.temp.name) / 'absent-fixtures'))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout), {'ok': False, 'code': 'bad_args'})
        self.assertEqual(result.stderr, b'')

    def test_bad_flags_exit_two_without_startup(self):
        for tail in [('--unknown',), ('--port',), ('--port', '-1'),
                     ('--port', '65536'), ('--port', 'True'), ('--port', '1.5'),
                     ('--port', '0', '--port', '0'), ('--fixtures',),
                     ('--ui-dist',), ('--ui-dist', '--port'), ('extra',)]:
            with self.subTest(tail=tail):
                result = self.run_command(*tail)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(json.loads(result.stdout),
                                 {'ok': False, 'code': 'bad_args'})
                self.assertEqual(result.stderr, b'')

    def test_occupied_port_exit_three_without_startup(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            result = self.run_command('--port', str(listener.getsockname()[1]))
        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(result.stdout), {'ok': False, 'code': 'internal'})
        self.assertEqual(result.stderr, b'')

    def test_missing_build_is_named_error(self):
        child, port = self.start('--ui-dist', str(Path(self.temp.name) / 'absent-ui'))
        status, raw, _ = self.request(port, '/')
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(raw), {'ok': False, 'code': 'internal',
                                         'detail': 'UI build unavailable.'})
        self.assertEqual(self.request(port, '/api/health')[0], 200)
        self.stop(child, port)


if __name__ == '__main__':
    unittest.main()
