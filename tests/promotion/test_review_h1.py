"""Regression checks against installed owners; synthetic evidence is not fitness."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import itertools
import tempfile
import unittest
from unittest.mock import patch

from lineage.core import app, journal
from lineage.core.errors import LineageError
from lineage.core.registry import load, Context, Services
from lineage.domain import promotion
from tests.promotion.test_dispatch import ARGS
from tests.promotion.test_evaluate import BASE, CHILD, SELECT, SEAT, Fixture, canonical


class ReviewH1Tests(unittest.TestCase):
    def setUp(self):
        # A-U19: isolate regression homes with the installed registry and explicit fixture services.
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = load()
        self.context = app.create_context(self.temp.name, registry=self.registry)
        # A-U19: the integrated fake arena runner requires an explicitly injected virtual clock.
        self.sequence = itertools.count(1)
        self.virtual_ticks = itertools.count(2000)

    def public(self, tool, args):
        # A-U19: retain real shared-dispatch assertions for promotion and agent reads.
        result = app.dispatch(tool, args, context=self.context, registry=self.registry)
        self.assertIsNone(result.failure, result.payload)
        self.assertEqual(set(result.payload), {'untrusted'})
        return result.payload['untrusted']

    def mutation(self, tool, args, *, op_id=None):
        # A-U19: the installed arena handler validates fixture commands using its actual schema store.
        effective = dict(args, agent=ARGS['agent'], op_id=op_id or f'review_{next(self.sequence):08d}')
        if tool in {'bench_declare', 'bench_run', 'bench_verdict'}:
            ctx = Context(Services(self.context.home, self.context.home, self.registry,
                                   clock=lambda: next(self.virtual_ticks)), actor=ARGS['agent'])
            return self.registry.tools[tool].handler(effective, context=ctx)
        return self.public(tool, effective)

    def seed_agents(self, *, first_op=None):
        # A-U19: seed identities through the real agent owner rather than projection files.
        pins = [{'id': ref, 'sha256': self.public('reference_verify', {'ref_id': ref})['sha256']}
                for ref in ('gold_s1', 'memory_v21')]
        for agent in (BASE, CHILD):
            self.mutation('agent_create', {'agent_id': agent, 'display_name': agent,
                'workflow': 'test', 'language': 'python', 'allowed_seats': [dict(SEAT)],
                'references': pins, 'skills': [], 'overlays': []},
                op_id=first_op if agent == BASE else None)

    def seed_selection(self):
        # A-U19: admit a synthetic pinned bank through the integrated arena owners.
        self.seed_agents()
        tasks = []
        for split, prefix in (('select', 'select'), ('heldout', 'holdout')):
            for i in range(3):
                def outcome(verdict):
                    return {'verdict': verdict, 'repair_loops': 0,
                            'findings': {'confirmed': 0, 'refuted': 0}}
                tasks.append({'id': f'{prefix}_{i:04d}', 'split': split, 'kind': 'unit',
                    'language': 'python', 'prompt': 'Synthetic lifecycle fixture.',
                    'expected': {'baseline': outcome('green' if i == 0 else 'error'),
                                 'candidate': outcome('green')}})
        bank = {'schema': 'lineage.bank/v1', 'bank_id': 'demo-offline', 'tasks': tasks}
        raw = canonical(bank)
        parent = self.context.home / 'arena/banks/demo-offline'
        parent.mkdir(parents=True)
        (parent / 'bank.json').write_bytes(raw + b'\n')
        (parent / 'MANIFEST.sha256').write_text(
            hashlib.sha256(raw + b'\n').hexdigest() + '  bank.json\n', encoding='ascii')
        declaration = deepcopy(Fixture().bench().payload('bench.declared'))
        declaration['bank_sha256'] = hashlib.sha256(raw).hexdigest()
        self.mutation('bench_declare', {'declaration': declaration})
        self.mutation('bench_run', {'bench_id': SELECT, 'runner': {'kind': 'fake', 'seed': 0}})
        self.mutation('bench_verdict', {'bench_id': SELECT})

    def test_a25_real_evidence_commits_complete_seat_under_amended_schema(self):
        # A-U19: keep a positive complete-seat assertion against A-K0-10 and real dispatch.
        self.seed_selection()
        prefix = journal.snapshot(self.context.home)
        transition = promotion.evaluate(prefix, CHILD, SELECT, seat=dict(SEAT))
        self.assertEqual(transition['from'], 'draft')
        self.assertEqual(transition['to'], 'shadow')
        ledger = self.context.home / 'ledger/main/events.jsonl'
        before = ledger.read_bytes()
        result = app.dispatch('agent_promote', dict(ARGS), context=self.context, registry=self.registry)
        self.assertIsNone(result.failure, result.payload)
        self.assertEqual(set(result.payload), {'untrusted'})
        after = journal.snapshot(self.context.home)
        self.assertEqual(len(after), len(prefix) + 1)
        self.assertEqual(after[-1]['kind'], 'agent.status')
        self.assertEqual(after[-1]['payload']['seat'], SEAT)
        self.assertEqual(ledger.read_bytes(), before + journal.canonical_bytes(after[-1]) + b'\n')
        record = self.public('agent_get', {'agent_id': CHILD})['record']
        self.assertEqual(record['status'], 'shadow')
        self.assertEqual(record['promoted_seat'], SEAT)

    def test_a18_broad_public_opid_is_journalled_unchanged(self):
        # A-U19: exercise A-JL1 legal identities without remapping.
        for op in ('x', 'promotion:child/selection.1', 'p' * 128):
            with self.subTest(op=op), tempfile.TemporaryDirectory() as home:
                self.context = app.create_context(home, registry=self.registry)
                self.seed_agents(first_op=op)
                prefix = journal.snapshot(home)
                self.assertEqual(prefix[0]['op_id'], op)
                self.assertEqual(prefix[0]['agent'], ARGS['agent'])

    def test_a17_missing_runtime_is_sanitized_internal(self):
        # A-U19: assert the bounded missing-service diagnostic.
        @dataclass(frozen=True)
        class IncompleteContext:
            actor: str = 'creator-agent'
        command = {'tool': 'agent_promote', 'args': dict(ARGS),
                   'agent': ARGS['agent'], 'op_id': ARGS['op_id']}
        with self.assertRaises(LineageError) as caught:
            promotion.promote(CHILD, SELECT, command=command, ctx=IncompleteContext())
        self.assertEqual(caught.exception.code, 'internal')
        self.assertNotIn(self.temp.name, str(caught.exception.detail))
        self.assertFalse((self.context.home / 'ledger/main/events.jsonl').exists())

    def test_a22_unavailable_policy_evidence_is_sanitized_internal(self):
        # A-U19: assert sanitized evidence-failure refusal without mutating the prefix.
        fixture = Fixture().bench()
        before = fixture.history()
        with patch.object(promotion, '_identities', side_effect=OSError('private evidence diagnostic')):
            with self.assertRaises(LineageError) as caught:
                promotion.evaluate(before, CHILD, SELECT, seat=dict(SEAT))
        self.assertEqual(caught.exception.code, 'internal')
        self.assertNotIn('private evidence diagnostic', str(caught.exception.detail))
        self.assertEqual(fixture.history(), before)

    def test_a15_foreign_actor_close_cannot_trigger_retirement(self):
        # A-U19: exclude a close whose actor does not own the run.
        fixture = Fixture()
        fixture.run(verdict='error')
        fixture.run(verdict='HOLD')
        fixture.run(verdict='red')
        fixture.events[-1]['agent'] = BASE
        state = {}
        for event in fixture.history():
            promotion.apply(state, event)
        self.assertEqual(state['promotion'][CHILD]['failure_streak'], 2)
        self.assertEqual(state['promotion'][CHILD]['status'], 'draft')

    def test_a15_mismatched_parent_witness_cannot_trigger_retirement(self):
        # A-U19: exclude a close with contradictory parent-context evidence.
        fixture = Fixture()
        fixture.run(verdict='error')
        fixture.run(verdict='HOLD')
        fixture.run(verdict='red')
        fixture.events[-1]['payload']['record']['parents_context'] = ['different-context']
        state = {}
        for event in fixture.history():
            promotion.apply(state, event)
        self.assertEqual(state['promotion'][CHILD]['failure_streak'], 2)
        self.assertEqual(state['promotion'][CHILD]['status'], 'draft')

    def test_a7_unrelated_memory_cannot_bridge_benchmark_run_versions(self):
        # A-U19: reject unrelated memory as a bridge between declared and run versions.
        fixture = Fixture()
        unrelated = fixture.run(agent=BASE)
        fixture.bench()
        fixture.unit(unrelated, 'lesson')
        extra = fixture.events.pop()
        declaration_index = next(i for i, event in enumerate(fixture.events)
                                 if event['kind'] == 'bench.declared')
        fixture.events.insert(declaration_index + 1, extra)
        for lamport, event in enumerate(fixture.events, 1):
            event['lamport'] = lamport
        opening = [event for event in fixture.events if event['kind'] == 'run.open'
                   and event['payload']['agent_id'] == BASE][-1]
        prior = tuple(event for event in fixture.events if event['lamport'] < opening['lamport'])
        version = promotion._identities(prior)[BASE]['agent_version']
        opening['payload']['agent_version'] = version
        closing = next(event for event in fixture.events if event['kind'] == 'run.close'
                       and event['payload']['record']['run_id'] == opening['payload']['run_id'])
        closing['payload']['record']['agent_version'] = version
        before = fixture.history()
        with self.assertRaises(LineageError) as caught:
            promotion.evaluate(before, CHILD, SELECT, seat=dict(SEAT))
        self.assertEqual(caught.exception.code, 'conflict')
        self.assertEqual(fixture.history(), before)
