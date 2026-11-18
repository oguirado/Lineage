"""Reject empty or option-like global home values before dispatch."""
import io
import json
import unittest
from unittest import mock

from lineage.core import cli


class CLIHomeTests(unittest.TestCase):
    def test_invalid_global_home_is_a_bad_argument(self):
        cases = (
            ('--home', '', 'doctor', '--json'),
            ('--home', '', 'call', 'agent_list', '--json', '{}'),
            ('--home', '-h'),
            ('--home', '-h', 'doctor', '--json'),
        )
        for args in cases:
            with self.subTest(args=args), \
                    mock.patch.object(cli.extensions, 'load') as load_registry:
                output = io.StringIO()
                self.assertEqual(cli.main(args, stdout=output), 2)
                self.assertEqual(json.loads(output.getvalue()), {'ok': False, 'code': 'bad_args'})
                load_registry.assert_not_called()
