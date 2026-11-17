"""Exact discovery and strict argument tests using the integrated U02/U04 APIs."""
from copy import deepcopy
import hashlib
import importlib.util
import inspect
import json

from lineage.core import app, registry, schema
from lineage.domain import runs, gate_close
from lineage.ext import runs as extension
from tests.runs.support import (RunCase, CONTRACTS, compatible, OWNER, RUN,
                               SEAT, TASK, OUTCOME, COST, ROOT, HERE)


class Contract(RunCase):
    def test_a01_exact_extension_inventory_and_discovery(self):
        self.assertEqual({t.name for t in extension.TOOLS}, set(CONTRACTS))
        self.assertEqual(len(extension.TOOLS), 4)
        self.assertEqual(set(extension.VALIDATORS), {'run.open', 'run.beat', 'run.close'})
        self.assertEqual(set(extension.FOLDS), {'runs'})
        loaded = registry.load()
        for name, expected in CONTRACTS.items():
            descriptor = next(x for x in app.list_tools(registry=loaded) if x['name'] == name)
            # A-U13: integrated U10 supports literal K0 anyOf; discovery must stay exact.
            self.assertEqual(descriptor['inputSchema'], expected['input'])
            self.assertEqual(loaded.tools[name].mutating, name != 'run_get')
        self.f.open()

    def test_a01_public_signatures_and_defaults(self):
        required = {
            runs.open_run: ('run_id', 'agent_id', 'seat', 'task', 'parents_context', 'memory_arm', 'command', 'ctx'),
            runs.beat: ('run_id', 'progress', 'command', 'ctx'),
            runs.close: ('run_id', 'outcome', 'cost', 'evidence', 'command', 'ctx'),
            runs.get: ('run_id', 'ctx'),
            gate_close.check: ('snapshot', 'run_id', 'outcome', 'cost', 'actor', 'ctx')}
        for function, names in required.items():
            sig = inspect.signature(function)
            self.assertEqual(tuple(sig.parameters), names)
            self.assertEqual(sig.parameters['ctx'].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(inspect.signature(runs.close).parameters['evidence'].default, ())
        self.f.open()

    def test_a02_direct_malformed_payload(self):
        self.refusal('bad_args', lambda: self.f.open(task={**TASK, 'extra': 1}))

    def test_a40_real_peer_integration_is_required(self):
        # No skip and no synthetic-producer result can be reported as host acceptance.
        self.f.open()
        required = ('lineage.domain.agents', 'lineage.domain.memory.units',
                    'lineage.domain.memory.schema', 'lineage.domain.memory.fold')
        for name in required:
            try:
                found = importlib.util.find_spec(name)
            except ModuleNotFoundError:
                found = None
            self.assertIsNotNone(found, 'BLOCKED integration prerequisite: ' + name)

    def test_a40_existing_frozen_oracles_unchanged(self):
        self.f.open()
        baseline = json.loads((HERE / 'baseline.json').read_text())
        # A-U13: U01R retired legacy inputs; pin their explicit accounting and replacements.
        retired = json.loads((HERE / 'baseline_retired.json').read_text())
        reconciliation = json.loads((ROOT / 'tests/core/regression/fixtures/reconciliation.json').read_text())
        decisions = {row['path']: row for row in reconciliation['decisions']}
        self.assertTrue(set(retired) <= set(baseline))
        for relative, digest in baseline.items():
            if relative in retired:
                self.assertFalse((ROOT / relative).exists(), relative)
                self.assertEqual(retired[relative], digest, relative)
                if relative in decisions:
                    self.assertEqual(decisions[relative]['decision'], 'RETIRE', relative)
                    self.assertEqual(decisions[relative]['original_sha256'], digest, relative)
                else:
                    # Removed auxiliary fixtures belong only to explicitly retired bundles.
                    owners = [row for path, row in decisions.items()
                              if (ROOT / path).parent == (ROOT / relative).parent]
                    self.assertTrue(owners, relative)
                    self.assertTrue(all(row['decision'] == 'RETIRE' for row in owners), relative)
            else:
                # Historical oracle hashes are sealed by the campaign, not this peer.
                self.assertTrue((ROOT / relative).is_file(), relative)


BASE_ARGS = {
    'run_open': {'run_id': RUN, 'agent_id': OWNER, 'seat': SEAT, 'task': TASK,
                 'parents_context': [], 'memory_arm': 'own', 'agent': OWNER, 'op_id': 'request1'},
    'run_close': {'run_id': RUN, 'outcome': OUTCOME, 'cost': COST,
                  'agent': OWNER, 'op_id': 'request1'},
    'run_beat': {'run_id': RUN, 'progress': 'Working', 'agent': OWNER, 'op_id': 'request1'}}


def hostile_test(tool, mutation):
    def test(self):
        # A positive call proves the installed handler is reachable before the hostile refusal.
        positive = app.dispatch('run_open', deepcopy(BASE_ARGS['run_open']),
                     context=self.f.context(), registry=self.f.registry)
        self.assertIn('untrusted', positive.payload, 'positive handler is not implemented')
        args = deepcopy(BASE_ARGS[tool])
        mutation(args)
        before = self.f.raw()
        result = app.dispatch(tool, args, context=self.f.context(), registry=self.f.registry)
        self.assertEqual(result.payload['code'], 'bad_args')
        self.assertFalse(result.payload['ok'])
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(self.f.raw(), before)
    return test


def set_path(path, value):
    def mutate(args):
        parent = args
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = value
    return mutate


HOSTILE = [
    ('unknown_root', 'run_close', set_path(('extra',), 1)),
    ('nested_unknown', 'run_close', set_path(('outcome', 'findings', 'extra'), 1)),
    ('missing_cost', 'run_close', lambda a: a['cost'].pop('tokens_in')),
    ('null_outcome', 'run_close', set_path(('outcome',), None)),
    ('bool_repairs', 'run_close', set_path(('outcome', 'repair_loops'), True)),
    ('bool_cost', 'run_close', set_path(('cost', 'tokens_in'), True)),
    ('unsafe_cost', 'run_close', set_path(('cost', 'tokens_in'), 9007199254740992)),
    ('nan', 'run_close', set_path(('cost', 'duration_ms'), float('nan'))),
    ('infinity', 'run_close', set_path(('cost', 'duration_ms'), float('inf'))),
    ('negative_cost', 'run_close', set_path(('cost', 'tokens_out'), -1)),
    ('surrogate', 'run_beat', set_path(('progress',), '\ud800')),
    ('invalid_id', 'run_open', set_path(('run_id',), '../escape')),
    ('missing_seat_mode', 'run_open', lambda a: a['seat'].pop('mode')),
    ('nested_seat_extra', 'run_open', set_path(('seat', 'extra'), True)),
    ('partial_benchmark', 'run_open', set_path(('task', 'bank_id'), 'bank-one')),
    ('empty_progress', 'run_beat', set_path(('progress',), '')),
    ('long_progress', 'run_beat', set_path(('progress',), '雪' * 2049)),
    ('gate_injection', 'run_close', set_path(('gate',), {'passed': True})),
    ('receipts_injection', 'run_close', set_path(('memory_receipts',), [])),
    ('version_injection', 'run_open', set_path(('agent_version',), 'a' * 64)),
    ('timestamp_injection', 'run_open', set_path(('ts',), 1)),
    ('parent_duplicate', 'run_open', set_path(('parents_context',),
        [{'agent_id': OWNER, 'agent_version': 'a'*64, 'run_id': RUN}] * 2)),
    ('evidence_oversize', 'run_close', set_path(('evidence',),
        [{'path': f'e/{i}', 'sha256': 'a'*64} for i in range(65)])),
]
for label, tool, mutation in HOSTILE:
    setattr(Contract, 'test_a02_hostile_' + label, hostile_test(tool, mutation))
