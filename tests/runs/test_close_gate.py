"""Frozen positive and negative memory-close policy cases."""
from copy import deepcopy
from unittest import mock

from lineage.core import journal
from lineage.domain import gate_close, runs
from tests.runs.support import (GateCase, RunCase, OWNER, OTHER, RUN, OUTCOME,
                               COST, outcome, canonical, validate_record)


class CloseGate(GateCase):
    def test_a10_missing_memory_is_required(self):
        self.refusal('memory_required', self.f.check)

    def test_a10_beats_and_pending_projection_are_not_memory(self):
        self.f.append_peer('run.beat', {'run_id': RUN, 'agent_id': OWNER, 'progress': 'done'})
        staged = self.f.home / 'agents' / OWNER / 'memory' / 'journal.jsonl'
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(canonical({'unit': self.f.unit()}) + b'\n')
        self.refusal('memory_required', self.f.check)

    def test_a12_fresh_episode_passes(self):
        self.f.put(self.f.unit())
        self.passed(self.f.check())

    def test_a13_conflicting_target_provenance_is_debt(self):
        unit = self.f.unit()
        unit['provenance']['actor'] = OTHER
        self.f.put(unit)
        self.refusal('memory_debt', self.f.check)

    def test_a16_null_costs_preserved_in_gate(self):
        self.f.put(self.f.unit(cost=COST))
        self.passed(self.f.check(cost=COST))

    def test_a17_episode_absence_precedes_companion_debt(self):
        self.refusal('memory_required', lambda: self.f.check(outcome('red')))

    def test_a18_companions_may_commit_after_episode(self):
        requested = outcome('red')
        self.f.put(self.f.unit(verdict=requested))
        self.refusal('memory_debt', lambda: self.f.check(requested))
        self.f.put(self.f.unit('lesson', identifier='lesson01'))
        self.refusal('memory_debt', lambda: self.f.check(requested))
        self.f.put(self.f.unit('negative', identifier='negative'))
        self.passed(self.f.check(requested))

    def test_a20_receipt_bytes_checked_with_positive_control(self):
        receipt = self.f.receipt()
        unit = self.f.unit(level=2, receipts=[receipt])
        self.f.put(unit)
        self.passed(self.f.check())
        (self.f.home / receipt['path']).write_bytes(b'changed')
        self.refusal('memory_debt', self.f.check)

    def test_a22_changed_removed_restored_receipts(self):
        receipt = self.f.receipt()
        self.f.put(self.f.unit(receipts=[receipt]))
        path = self.f.home / receipt['path']
        path.write_bytes(b'changed')
        self.refusal('memory_debt', self.f.check)
        path.unlink()
        self.refusal('memory_debt', self.f.check)
        path.write_bytes(b'verified\n')
        self.passed(self.f.check())

    def test_a23_public_internal_observations_need_no_receipt(self):
        for privacy in ('public', 'internal'):
            unit = self.f.unit(identifier='episode_' + privacy, privacy=privacy)
            self.f.put(unit)
        self.passed(self.f.check())

    def test_a24_report_order_is_independent_of_enumeration(self):
        receipt = self.f.receipt()
        self.f.put(self.f.unit(identifier='episode_z', receipts=[receipt]))
        self.f.put(self.f.unit(identifier='episode_a', receipts=[receipt]))
        events = list(self.f.events())
        first = self.f.check(events=events)
        # Same committed prefix, different folded map enumeration order.
        snap = self.f.snapshot()
        units = snap.state['memory'][OWNER]
        snap.state['memory'][OWNER] = dict(reversed(list(units.items())))
        second = gate_close.check(snap, RUN, deepcopy(OUTCOME), deepcopy(COST),
                                  actor=OWNER, ctx=self.f.context())
        self.passed(first)
        self.assertEqual(first, second)
        self.assertEqual(first['memory_receipts'], [receipt])

    def test_a37_no_tokenizer_or_detector_requirement(self):
        self.f.put(self.f.unit())
        self.assertIsNone(self.f.services.token_count)
        report = self.f.check()
        self.passed(report)
        self.assertNotIn('tokens', report)
        self.assertTrue(any('not measured' in item.get('detail', '') for item in report['checks']))


# Expected matrix is frozen explicitly, independent of any implementation helper.
MATRIX = (
    ('ADMIT', 0, False, False), ('ADMIT', 1, True, False),
    ('green', 0, False, False), ('green', 1, True, False),
    ('error', 0, True, False), ('error', 1, True, False),
    ('HOLD', 0, True, True), ('HOLD', 1, True, True),
    ('red', 0, True, True), ('red', 1, True, True))


def matrix_test(verdict, repairs, lesson, negative):
    def test(self):
        requested = outcome(verdict, repairs)
        self.f.put(self.f.unit(verdict=requested))
        if lesson:
            self.refusal('memory_debt', lambda: self.f.check(requested))
            self.f.put(self.f.unit('lesson', identifier='lesson01'))
        if negative:
            self.refusal('memory_debt', lambda: self.f.check(requested))
            self.f.put(self.f.unit('negative', identifier='negative'))
        self.passed(self.f.check(requested))
    return test


for verdict, repairs, lesson, negative in MATRIX:
    setattr(CloseGate, f'test_a17_matrix_{verdict.lower()}_repairs_{repairs}',
            matrix_test(verdict, repairs, lesson, negative))


class CloseRecords(RunCase):
    def test_a10_domain_refusal_leaves_run_open(self):
        self.f.open()
        self.refusal('memory_required', self.f.close)
        self.assertIsNone(runs.get(RUN, ctx=self.f.context())['closed'])

    def test_a16_nullable_record_and_replay(self):
        self.f.open()
        self.f.witness(cost=COST)
        command = self.f.command('run_close', {'run_id': RUN, 'outcome': OUTCOME, 'cost': COST})
        closed = self.f.close(command=command)
        self.assertEqual(self.closed(closed)['cost'], COST)
        self.assertEqual(canonical(self.f.close(command=command).value), canonical(closed.value))

    def test_a24_minimal_sorted_witnesses_and_separate_task_evidence(self):
        self.f.open()
        requested = outcome('red')
        receipt_a = self.f.receipt('evidence/a.txt', b'a')
        receipt_b = self.f.receipt('evidence/b.txt', b'b')
        task_receipt = self.f.receipt('evidence/task.txt', b'task')
        for kind, prefix in (('episode', 'episode'), ('lesson', 'lesson__'), ('negative', 'negative')):
            for suffix in ('z', 'a'):
                unit = self.f.unit(kind, identifier=prefix + suffix, verdict=requested,
                                   receipts=[receipt_b, receipt_a])
                self.f.put(unit)
        invalid = self.f.unit(identifier='00000000', verdict=requested, privacy='private')
        self.f.put(invalid)
        for number in range(20):
            self.f.put(self.f.unit('lesson', identifier=f'unrelated{number:04d}', run_id='other001'))
        committed = self.f.close(requested, evidence=[task_receipt])
        record = self.closed(committed)
        self.assertEqual(record['memory']['unit_ids'], ['episodea', 'lesson__a', 'negativea'])
        self.assertEqual(record['memory']['levels'], [3])
        self.assertEqual(record['evidence'], [task_receipt])
        self.assertEqual(committed.event['evidence'], [task_receipt])
        self.assertEqual(committed.event['payload']['memory_receipts'], [receipt_a, receipt_b])
        report = gate_close.check(self.f.snapshot(self.f.events()[:-1]), RUN, requested, COST,
                                  actor=OWNER, ctx=self.f.context())
        self.assertEqual(committed.event['payload']['gate'],
                         {k: report[k] for k in ('passed', 'checks')})

    def test_a24_large_legal_receipt_union_without_truncation(self):
        self.f.open()
        requested = outcome('red')
        receipts = []
        for number in range(120):
            # Short file names keep every individual canonical unit below the byte ceiling.
            receipts.append(self.f.receipt(f'e/{number:03x}', bytes([number])))
        for index, kind in enumerate(('episode', 'lesson', 'negative')):
            unit = self.f.unit(kind, identifier=f'witness{index}', verdict=requested,
                               receipts=receipts[index * 40:(index + 1) * 40])
            self.assertLessEqual(len(canonical(unit)), 6000)
            self.f.put(unit)
        committed = self.f.close(requested)
        self.closed(committed)
        expected = sorted({(r['path'], r['sha256']) for e in self.f.events()
                           if e['kind'] == 'memory.put' for r in e['payload']['unit']['receipts']})
        self.assertEqual(committed.event['payload']['memory_receipts'],
                         [{'path': p, 'sha256': h} for p, h in expected])
        self.assertEqual(len(expected), 120)

    def test_a28_direct_close_cannot_bypass_gate(self):
        opening = self.f.open().event
        record = {'schema': 'lineage.run/v1', 'run_id': RUN, 'ts_open': opening['ts'],
            'ts_close': opening['ts'], **{k: deepcopy(opening['payload'][k]) for k in
                ('agent_id', 'agent_version', 'seat', 'task', 'parents_context', 'memory_arm')},
            'outcome': deepcopy(OUTCOME), 'cost': deepcopy(COST), 'evidence': [],
            'memory': {'unit_ids': ['episode1'], 'levels': [3], 'gate_passed': True}}
        validate_record(record, 'run.schema.json')
        payload = {'record': record, 'memory_receipts': [],
                   'gate': {'passed': True, 'checks': [{'id': 'fabricated', 'passed': True}]}}
        self.refusal('memory_required', lambda: self.f.append_peer('run.close', payload,
                     validators=self.f.registry.validators))

    def test_a28_forged_gate_checks_rejected(self):
        opening = self.f.open().event
        self.f.witness()
        report = self.f.check()
        record = {'schema': 'lineage.run/v1', 'run_id': RUN, 'ts_open': opening['ts'],
            'ts_close': opening['ts'], **{k: deepcopy(opening['payload'][k]) for k in
                ('agent_id', 'agent_version', 'seat', 'task', 'parents_context', 'memory_arm')},
            'outcome': deepcopy(OUTCOME), 'cost': deepcopy(COST), 'evidence': [],
            'memory': {'unit_ids': ['episode1'], 'levels': [3], 'gate_passed': True}}
        payload = {'record': record, 'memory_receipts': report['memory_receipts'],
                   'gate': {'passed': True, 'checks': [{'id': 'forged', 'passed': True}]}}
        self.refusal('conflict', lambda: self.f.append_peer('run.close', payload,
                     validators=self.f.registry.validators))

    def test_a37_byte_valid_memory_closes_without_token_counter(self):
        self.f.open()
        self.f.witness()
        self.assertIsNone(self.f.services.token_count)
        self.closed(self.f.close())


def arm_test(arm):
    def test(self):
        self.f.open(arm=arm)
        self.refusal('memory_required', self.f.close)
        self.f.witness()
        self.assertEqual(self.closed(self.f.close())['memory_arm'], arm)
    return test


for arm in ('none', 'own', 'inherited'):
    setattr(CloseRecords, 'test_a11_memory_arm_' + arm, arm_test(arm))


def failure_record_test(verdict):
    def test(self):
        requested = outcome(verdict)
        self.f.open()
        self.f.witness(requested)
        record = self.closed(self.f.close(requested))
        self.assertEqual(record['outcome'], requested)
    return test


for verdict in ('error', 'HOLD', 'red'):
    setattr(CloseRecords, 'test_a19_failed_task_' + verdict.lower(), failure_record_test(verdict))


class GateMutants(RunCase):
    """Execute frozen negatives against in-memory copies; imports/errors never kill a mutant."""
    def mutant(self, kind, method):
        import ast
        from contextlib import ExitStack
        import inspect
        import io
        from types import ModuleType
        import unittest
        self.f.open()
        self.f.witness()
        positive = self.f.check()
        self.passed(positive)
        original = gate_close.check
        copied = ModuleType('lineage.domain._u13_oracle_mutant')
        copied.__package__ = 'lineage.domain'
        if kind == 'central':
            def changed(*args, **kwargs):
                return deepcopy(positive)
        else:
            tree = ast.parse(inspect.getsource(gate_close))
            edits = []
            class RemoveGuard(ast.NodeTransformer):
                def visit_Compare(self, node):
                    text = ast.unparse(node)
                    temporal = 'lamport' in text and any(isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)) for op in node.ops)
                    owner = ('actor' in text or 'agent_id' in text) and any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops)
                    if (kind == 'post_open' and temporal) or (kind == 'owner' and owner):
                        edits.append(text)
                        # Admission checks may be phrased as a rejection or an acceptance.
                        rejected = any(isinstance(op, (ast.NotEq, ast.Lt, ast.LtE)) for op in node.ops)
                        return ast.copy_location(ast.Constant(not rejected), node)
                    return self.generic_visit(node)
            tree = RemoveGuard().visit(tree)
            self.assertTrue(edits, 'HOLD: no unambiguous guard found; mutant not certified')
            ast.fix_missing_locations(tree)
            exec(compile(tree, 'tests/runs/mutant.py', 'exec'), copied.__dict__)
            changed = copied.check
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(gate_close, 'check', changed))
            # Cover either documented module use or a direct imported reference.
            for name, value in vars(runs).items():
                if value is original:
                    stack.enter_context(mock.patch.object(runs, name, changed))
            result = unittest.TextTestRunner(stream=io.StringIO()).run(
                unittest.TestSuite([method()]))
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(result.errors, [], 'HOLD: import/dependency/exception failure is not a mutant kill')
        self.assertEqual(len(result.failures), 1, 'HOLD: frozen behavioral negative stayed green')

    def test_a38_neutralized_central_gate_killed_by_missing_memory(self):
        self.mutant('central', lambda: CloseGate('test_a10_missing_memory_is_required'))

    def test_a38_postopen_guard_mutant_killed_by_stale_memory(self):
        from tests.runs.test_memory_witnesses import Witnesses
        self.mutant('post_open', lambda: Witnesses('test_a12_preopen_episode_is_not_fresh'))

    def test_a38_owner_guard_mutant_killed_by_foreign_memory(self):
        from tests.runs.test_memory_witnesses import Witnesses
        self.mutant('owner', lambda: Witnesses('test_a13_foreign_owner_memory_cannot_close'))


def forged_record_test(field):
    def test(self):
        opening = self.f.open().event
        self.f.witness()
        report = self.f.check()
        record = {'schema': 'lineage.run/v1', 'run_id': RUN, 'ts_open': opening['ts'],
            'ts_close': opening['ts'], **{k: deepcopy(opening['payload'][k]) for k in
                ('agent_id', 'agent_version', 'seat', 'task', 'parents_context', 'memory_arm')},
            'outcome': deepcopy(OUTCOME), 'cost': deepcopy(COST), 'evidence': [],
            'memory': {'unit_ids': ['episode1'], 'levels': [3], 'gate_passed': True}}
        if field == 'version':
            record['agent_version'] = 'f' * 64
        elif field == 'owner':
            record['agent_id'] = OTHER
        elif field == 'unit_ids':
            record['memory']['unit_ids'] = ['forged01']
        payload = {'record': record, 'memory_receipts': report['memory_receipts'],
                   'gate': {k: report[k] for k in ('passed', 'checks')}}
        if field == 'receipts':
            payload['memory_receipts'] = [self.f.receipt()]
        self.refusal('conflict', lambda: self.f.append_peer('run.close', payload,
                     validators=self.f.registry.validators))
    return test


for field in ('version', 'owner', 'unit_ids', 'receipts'):
    setattr(CloseRecords, 'test_a28_forged_' + field, forged_record_test(field))
