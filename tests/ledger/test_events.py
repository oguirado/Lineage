"""Frozen cursor contract through real dispatch, CLI and the JSON lane."""
import json
import os
import subprocess
import sys
import threading
import time
from unittest.mock import patch

from tests.ledger._support import LedgerCase, ROOT, contract_schemas


class EventTests(LedgerCase):
    def test_all_ledger_input_schemas_equal_contract(self):
        for name in ('ledger_events', 'ledger_export', 'ledger_verify', 'scorecard_get'):
            with self.subTest(tool=name):
                self.assertEqual(self.registry.tools[name].input_schema, contract_schemas(name)[0])

    def test_empty_kinds_and_actor_subject_separation_dispatch_and_cli(self):
        one = self.append(actor='agent-one')
        self.append(actor='agent-two')
        for kinds in ({}, {'kinds': []}):
            args = {'agent': 'caller', 'agent_id': 'agent-one', **kinds}
            result = self.data('ledger_events', args)
            self.assertEqual(result['events'], [one])
            self.assertEqual(result['next_after'], 2)
            self.check_result('ledger_events', result)
            self.assertEqual(self.cli('ledger_events', args), {'untrusted': result})
        self.assertEqual(len(self.data('ledger_events', {'agent': 'caller'})['events']), 2)

    def test_filtered_paging_advances_over_holes_and_exhaustion(self):
        self.append(actor='agent-two')
        one = self.append()
        self.append(actor='agent-two')
        two = self.append()
        self.append(actor='agent-two')
        args = {'agent_id': 'agent-one', 'limit': 1, 'kinds': ['run.beat']}
        first = self.data('ledger_events', args)
        self.assertEqual(first['events'], [one])
        self.assertTrue(first['has_more'])
        second = self.data('ledger_events', {**args, 'after': first['next_after']})
        self.assertEqual(second['events'], [two])
        self.assertEqual(second['next_after'], 5)
        self.assertFalse(second['has_more'])
        exhausted = self.data('ledger_events', {**args, 'after': 5})
        self.assertEqual(exhausted['next_after'], 5)
        self.assertFalse(exhausted['has_more'])
        empty = self.data('ledger_events', {'kinds': ['memory.put'], 'after': 1})
        self.assertEqual((empty['events'], empty['next_after'], empty['has_more']), ([], 5, False))

    def test_after_head_resync_is_zero_even_on_nonempty_history(self):
        self.append()
        value = self.data('ledger_events', {'after': 2})
        self.assertEqual(value, {'events': [], 'next_after': 0, 'head': 1,
                                 'has_more': False, 'resync': True})
        self.assertEqual(self.cli('ledger_events', {'after': 2}), {'untrusted': value})

    def test_wait_accepts_full_bound_and_rejects_invalid_arguments(self):
        self.append()
        self.assertEqual(len(self.data('ledger_events', {'wait_ms': 30000})['events']), 1)
        for args in ({'wait_ms': 30001}, {'after': True}, {'after': 9007199254740992},
                     {'kinds': ['unknown']}, {'kinds': ['run.beat', 'run.beat']}):
            with self.subTest(args=args):
                self.assertEqual(self.dispatch('ledger_events', args).payload['code'], 'bad_args')
                self.assertEqual(self.cli('ledger_events', args, 2)['code'], 'bad_args')

    def test_wait_ignores_nonmatching_arrival_then_returns_matching_event(self):
        from lineage.core import events
        observed = threading.Event()
        original = events.journal.snapshot
        result = []
        def snapshot(*args, **kwargs):
            history = original(*args, **kwargs)
            observed.set()
            return history
        def read():
            result.append(self.dispatch('ledger_events', {'agent_id': 'agent-one',
                                                        'kinds': ['run.beat'], 'wait_ms': 1500}))
        with patch.object(events.journal, 'snapshot', snapshot):
            reader = threading.Thread(target=read)
            reader.start()
            try:
                self.assertTrue(observed.wait(1))
                self.append(actor='agent-two')
                time.sleep(0.08)
                self.assertTrue(reader.is_alive(), 'nonmatching event ended the wait')
                matching = self.append()
            finally:
                reader.join(2)
        self.assertFalse(reader.is_alive())
        self.assertEqual(result[0].payload['untrusted']['events'], [matching])

    def test_wait_expiry_advances_past_nonmatching_history(self):
        self.append(actor='agent-two')
        started = time.monotonic()
        result = self.data('ledger_events', {'agent_id': 'agent-one', 'wait_ms': 80})
        self.assertGreaterEqual(time.monotonic() - started, 0.06)
        self.assertEqual((result['events'], result['next_after'], result['has_more']), ([], 1, False))

    def test_json_events_read_accepts_documented_empty_kinds(self):
        expected = self.append()
        endpoint = self.home / 'family/receiver'
        endpoint.parent.mkdir(mode=0o700)
        endpoint.mkdir(mode=0o700)
        (endpoint / 'config.json').write_text(json.dumps({
            'endpoint': 'receiver', 'sources': ['sender'], 'tools': ['ledger_events']}))
        (endpoint / 'config.json').chmod(0o600)
        request = {'schema': 'lineage.family/1', 'id': 'request01', 'source': 'sender',
                   'target': 'receiver', 'kind': 'events.read', 'agent': 'caller',
                   'after': 0, 'payload': {'kinds': []}}
        completed = subprocess.run([sys.executable, '-B', '-m', 'lineage', '--home',
                                    str(self.home), 'json'], cwd=ROOT,
                                   input=json.dumps(request), text=True, capture_output=True,
                                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['result']['untrusted']['events'], [expected])
