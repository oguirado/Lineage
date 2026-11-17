"""Real subprocess carriers and temporary filesystem fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')


class CommsCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='lineage-comms-')
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name) / 'home'
        self.home.mkdir(mode=0o700)

    def cli(self, *args, data=None, expected=0, home=None):
        command = [sys.executable, '-m', 'lineage', '--home', str(home or self.home), *args]
        result = subprocess.run(command, input=data, text=True, capture_output=True,
                                cwd=ROOT, env=ENV, timeout=30)
        self.assertEqual(result.returncode, expected, (args, result.stdout, result.stderr))
        self.assertNotIn('Traceback', result.stderr)
        return result

    def call(self, tool, args, expected=0):
        return json.loads(self.cli('call', tool, '--json', json.dumps(args), expected=expected).stdout)

    def rpc(self, requests):
        result = self.cli('mcp', data=''.join(json.dumps(item) + '\n' for item in requests))
        return [json.loads(line) for line in result.stdout.splitlines()]

    def birth(self):
        pins = [self.call('reference_get', {'ref_id': name})['untrusted']['reference']
                for name in ('gold_s1', 'memory_v21')]
        return self.call('agent_create', {
            'agent_id': 'guide-agent', 'display_name': 'Guide agent',
            'workflow': 'develop', 'language': 'python',
            'allowed_seats': [{'model': 'test-model', 'effort': 'medium', 'mode': 'headless'}],
            'references': [{'id': pin['id'], 'sha256': pin['sha256']} for pin in pins],
            'skills': [], 'agent': 'guide-agent', 'op_id': 'comms/create:1'})

    def tree(self):
        return {str(path.relative_to(self.home)):
                ('symlink' if path.is_symlink() else
                 (path.stat().st_mode, path.read_bytes() if path.is_file() else None))
                for path in self.home.rglob('*')}


def request(method, params=None, ident=1):
    return {'jsonrpc': '2.0', 'id': ident, 'method': method, 'params': params or {}}
