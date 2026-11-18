"""Parse generated client configs and start their exact server commands."""
import json
from pathlib import Path
import subprocess
import sys
import tomllib

from .support import CommsCase, ENV, ROOT, request


class MCPConfigTests(CommsCase):
    def test_all_clients_generate_exact_usable_configuration(self):
        configs = []
        before = self.tree()
        for client in ('generic', 'claude', 'codex'):
            text = self.cli('mcp-config', '--client', client).stdout
            value = (tomllib.loads(text)['mcp_servers']['lineage'] if client == 'codex'
                     else json.loads(text)['mcpServers']['lineage'])
            self.assertEqual(value, {'command': str(ROOT / 'bin' / 'lineage'),
                                     'args': ['--home', str(self.home), 'mcp']})
            reply = subprocess.run([value['command'], *value['args']], cwd=self.temporary.name,
                                   input=json.dumps(request('ping')) + '\n', text=True,
                                   capture_output=True, env=ENV, timeout=20)
            self.assertEqual(reply.returncode, 0, reply.stderr)
            self.assertEqual(json.loads(reply.stdout)['result'], {})
            configs.append(value)
        self.assertEqual(configs[0], configs[1])
        self.assertEqual(configs[1], configs[2])
        self.assertEqual(before, self.tree())

    def test_command_local_home_and_spaces_are_quoted_without_creation(self):
        from lineage.core import cli
        import io
        target = Path(self.temporary.name) / 'home "with quotes" and spaces'
        output = io.StringIO()
        code = cli.main(['mcp-config', '--client', 'codex', '--home', str(target)], stdout=output)
        self.assertEqual(code, 0)
        config = tomllib.loads(output.getvalue())['mcp_servers']['lineage']
        self.assertEqual(config['args'], ['--home', str(target), 'mcp'])
        self.assertFalse(target.exists())

    def test_codex_del_in_home_round_trips_through_toml(self):
        target = self.home / 'résumé\x7f'
        text = self.cli('mcp-config', '--client', 'codex', home=target).stdout
        config = tomllib.loads(text)['mcp_servers']['lineage']
        self.assertEqual(config['args'], ['--home', str(target), 'mcp'])
        self.assertFalse(target.exists())

    def test_surrogateescaped_home_is_a_bad_argument(self):
        target = self.home / 'invalid-\udcff'
        for client in ('generic', 'claude', 'codex'):
            with self.subTest(client=client):
                result = subprocess.run(
                    [sys.executable, '-m', 'lineage', '--home', str(target),
                     'mcp-config', '--client', client],
                    cwd=ROOT, env=ENV, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout), {'ok': False, 'code': 'bad_args'})
                self.assertEqual(result.stderr, b'')

    def test_invalid_options_and_duplicate_home_fail(self):
        for args in (['--client', 'unknown'], ['--client'], ['--home', str(self.home)],
                     ['--client', 'claude', '--client', 'codex'], ['--unknown', 'x']):
            result = self.cli('mcp-config', *args, expected=2)
            self.assertEqual(json.loads(result.stdout)['code'], 'bad_args')

    def test_generator_requires_no_registry_and_help_lists_verbs(self):
        from unittest import mock
        from lineage.core import mcpconfig
        with mock.patch('lineage.core.registry.load', side_effect=AssertionError('registry')):
            value = json.loads(mcpconfig.configuration(home=self.home))
        self.assertEqual(value['mcpServers']['lineage']['args'][1], str(self.home))
        help_text = self.cli('--help').stdout
        for verb in ('doctor', 'mcp-config'):
            self.assertIn(verb, help_text)
