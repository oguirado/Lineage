"""A4–A8: frozen authorization boundary, cryptographic source and safe equality."""
import hmac
import os
import random
import secrets
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from tests.serve._support import BoundedCase, LineageError, cases, load_surface


class SessionTests(BoundedCase):
    def authorize(self, **changes):
        args = dict(host='127.0.0.1:47123', origin=None, token=None,
                    expected_authority='127.0.0.1:47123',
                    expected_token='synthetic-session-value', mutation=False)
        args.update(changes)
        with load_surface() as modules:
            return modules.session.authorize(**args)

    def test_a06_read_omits_credentials(self):
        self.assertIsNone(self.authorize())

    def test_a06_protected_exact_credentials(self):
        self.assertIsNone(self.authorize(mutation=True, origin='http://127.0.0.1:47123',
                                         token='synthetic-session-value'))

    def test_a08_token_html_safe_and_per_lifecycle(self):
        with load_surface() as modules:
            first, second = modules.session.new_token(), modules.session.new_token()
        self.assertIsInstance(first, str)
        self.assertTrue(first)
        self.assertNotEqual(first, second)
        self.assertFalse(any(c in first for c in '<>\'"&\x00\r\n'))

    def test_a08_standard_crypto_source_at_least_128_bits(self):
        # Observe all documented stdlib crypto choices without prescribing one API.
        with ExitStack() as stack:
            spies = [(stack.enter_context(patch.object(owner, name, wraps=getattr(owner, name))), bits)
                     for owner, name, bits in ((secrets, 'token_bytes', 8),
                        (secrets, 'token_hex', 8), (secrets, 'token_urlsafe', 8),
                        (os, 'urandom', 8), (random, '_urandom', 8))]
            with load_surface() as modules:
                token = modules.session.new_token()
        self.assertTrue(token)
        # Count bottom-level entropy once; nested secrets wrappers reuse it.
        entropy = 0
        for spy, bits in spies[-2:]:
            for call in spy.call_args_list:
                amount = call.args[0] if call.args else call.kwargs.get('n', 0)
                if type(amount) is int:
                    entropy += amount * bits
        self.assertGreaterEqual(entropy, 128, 'No witnessed crypto entropy request')

    def test_a06_constant_time_comparison(self):
        with patch.object(hmac, 'compare_digest', wraps=hmac.compare_digest) as hmac_spy, \
             patch.object(secrets, 'compare_digest', wraps=secrets.compare_digest) as secrets_spy:
            self.assertIsNone(self.authorize(mutation=True, origin='http://127.0.0.1:47123',
                                             token='synthetic-session-value'))
        self.assertTrue(hmac_spy.called or secrets_spy.called)


def refused(self, changes):
    try:
        self.authorize(**changes)
    except LineageError as exc:
        self.assertEqual(exc.code, 'bad_args')
    else:
        self.fail('Authorization must refuse')


cases(SessionTests, 'a04_host', [
    ('missing', {'host': ''}), ('no_port', {'host': '127.0.0.1'}),
    ('foreign_port', {'host': '127.0.0.1:47124'}), ('alternate_ip', {'host': '127.0.0.2:47123'}),
    ('prefix', {'host': 'x127.0.0.1:47123'}), ('suffix', {'host': '127.0.0.1:47123.extra'}),
    ('credentials', {'host': 'user@127.0.0.1:47123'}), ('space', {'host': '127.0.0.1:47123 '}),
    ('network_path', {'host': '//127.0.0.1:47123'}),
], refused)
cases(SessionTests, 'a05_origin', [(name, {'origin': origin}) for name, origin in [
    ('opaque', 'null'), ('foreign_port', 'http://127.0.0.1:47124'),
    ('tls', 'https://127.0.0.1:47123'), ('trailing_slash', 'http://127.0.0.1:47123/'),
    ('credentials', 'http://user@127.0.0.1:47123'), ('suffix', 'http://127.0.0.1:47123.extra'),
]], refused)
cases(SessionTests, 'a06_mutation', [(name, {'mutation': True, **values}) for name, values in [
    ('no_origin', {'token': 'synthetic-session-value'}),
    ('no_token', {'origin': 'http://127.0.0.1:47123'}),
    ('wrong_token', {'origin': 'http://127.0.0.1:47123', 'token': 'wrong'}),
    ('other_instance', {'origin': 'http://127.0.0.1:47123', 'token': 'foreign-lifecycle-value'}),
]], refused)
