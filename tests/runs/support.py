"""U13 oracle fixtures. Synthetic peers isolate policy; they are not U10/U12 receipts."""
from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import importlib
import importlib.util
import io
import itertools
import json
import multiprocessing
import os
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest import mock

from lineage.core import app, journal, registry, schema
from lineage.core.errors import LineageError
from lineage.domain import agents, brief, gate_close, runs
from lineage.domain.memory import fold as memory_fold
from lineage.ext import runs as extension

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CONTRACTS = json.loads((HERE / 'contract_schemas.json').read_text(encoding='utf-8'))
OWNER = 'agent-one'
OTHER = 'agent-two'
RUN = 'run_0001'
SEAT = {'model': 'fixture-model', 'effort': 'medium', 'mode': 'headless'}
TASK = {'id': 'task0001', 'kind': 'test', 'language': 'python'}
COST = dict.fromkeys(('tokens_in', 'tokens_out', 'tokens_cache', 'duration_ms', 'cost_micro_usd'))
OUTCOME = {'verdict': 'green', 'repair_loops': 0, 'findings': {'confirmed': 0, 'refuted': 0}}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':')).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def version(record):
    inputs = {k: deepcopy(record[k]) for k in ('constitution_sha256', 'skills', 'memory_gen')}
    inputs['skills'].sort(key=lambda pin: (pin['skill_id'], pin['sha256']))
    return sha(canonical(inputs))


def outcome(verdict='green', repairs=0):
    return {**deepcopy(OUTCOME), 'verdict': verdict, 'repair_loops': repairs}


def compatible(value):
    """Exact nullable-integer equivalent supported by the integrated mini-validator."""
    if isinstance(value, list):
        return [compatible(v) for v in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {'anyOf'} and len(value['anyOf']) == 2:
        a, b = value['anyOf']
        if a.get('type') == 'integer' and b == {'type': 'null'}:
            return {**a, 'type': ['integer', 'null']}
    return {k: compatible(v) for k, v in value.items()}


def validate_record(value, name):
    """Independent test-side bundled-ref/conditional walker; no production decoder."""
    document = json.loads((ROOT / 'schemas' / name).read_text(encoding='utf-8'))
    def walk(item, spec):
        if isinstance(spec, bool):
            if not spec:
                raise schema.SchemaError('false_schema')
            return
        if '$ref' in spec:
            target = spec['$ref']
            if target.startswith('#/'):
                sub = document
                for key in target[2:].split('/'):
                    sub = sub[key.replace('~1', '/').replace('~0', '~')]
                walk(item, sub)
            else:
                validate_record(item, target)
            return
        simple = {k: v for k, v in spec.items() if k not in
                  ('allOf', 'anyOf', 'oneOf', 'not', 'if', 'then', 'else', '$defs',
                   'properties', 'items', 'propertyNames', 'maxProperties')}
        if 'properties' in spec:
            simple['properties'] = {k: {} for k in spec['properties']}
        if 'items' in spec:
            simple['items'] = {}
        schema.validate(item, compatible(simple))
        if type(item) is dict:
            for key, sub in spec.get('properties', {}).items():
                if key in item:
                    walk(item[key], sub)
        if type(item) is list and 'items' in spec:
            for child in item:
                walk(child, spec['items'])
        for sub in spec.get('allOf', []):
            walk(item, sub)
        if 'anyOf' in spec:
            for sub in spec['anyOf']:
                try:
                    walk(item, sub)
                    break
                except schema.SchemaError:
                    pass
            else:
                raise schema.SchemaError('anyOf')
        if 'not' in spec:
            try:
                walk(item, spec['not'])
            except schema.SchemaError:
                pass
            else:
                raise schema.SchemaError('not')
        if 'if' in spec:
            try:
                walk(item, spec['if'])
                branch = 'then'
            except schema.SchemaError:
                branch = 'else'
            if branch in spec:
                walk(item, spec[branch])
    walk(value, document)


@dataclass(frozen=True)
class Command:
    tool: str
    args: dict
    agent: str
    op_id: str
    expected_head: int | None = None


@dataclass(frozen=True)
class Snapshot:
    events: tuple
    head: int
    raw_head_sha256: str | None
    state: dict


@dataclass(frozen=True)
class Context(app.CallContext):
    authority: str = 'tool'
    transport: str = 'library'
    services: object = None


def accept(history, event):
    """Test-only producer seam; invalid histories are explicitly controlled fixtures."""
    return None


def peer_agents(state, event):
    # A-U13: retain synthetic admission, using U12's source and brief projection shape.
    records = state.setdefault('agents', {})
    payload = event['payload']
    if event['kind'] == 'agent.born':
        record = deepcopy(payload['record'])
        records[record['agent_id']] = record
        records.setdefault('_sources', {})[record['agent_id']] = deepcopy(payload['constitution'])
    elif event['kind'] == 'agent.status':
        records[payload['agent_id']]['status'] = payload['to']
    elif event['kind'] in ('memory.put', 'memory.retire'):
        agent_id = payload['agent_id']
        record = records.get(agent_id)
        if record is not None:
            record['memory_gen'] = state['memory'][agent_id]['memory_gen']
            record['agent_version'] = version(record)
            source = records['_sources'][agent_id]
            raw = brief.build(record, memory_fold.units_for(state, agent_id),
                              rule_ids=source['rule_ids'])
            records.setdefault('_brief_heads', {})[agent_id] = sha(raw)


# A-U13: preserve integrated fold ordering: memory precedes the agent/version view.
peer_agents.order = 40

# A-U13: U10's installed fold owns the units/originals/memory_gen state shape.
peer_memory = memory_fold.apply


class Fixture:
    """Real journal/registry with explicitly synthetic agent/memory producer folds."""
    def __init__(self, home=None, *, seed=True):
        self.temporary = None
        if home is None:
            import tempfile
            self.temporary = tempfile.TemporaryDirectory(prefix='runtime-', dir=HERE)
            home = Path(self.temporary.name) / 'home'
        self.home = Path(home)
        self.clock_value = 1700000000000
        self.counter = itertools.count(1)
        self.ids = itertools.count(1000)
        self.registry = registry.Registry(
            {t.name: t for t in extension.TOOLS},
            {**extension.VALIDATORS, 'agent.born': accept, 'agent.status': accept,
             'memory.put': accept, 'memory.retire': accept},
            {'memory': peer_memory, 'agents': peer_agents, **extension.FOLDS})
        self.services = SimpleNamespace(home=self.home, repo_root=ROOT,
            registry=self.registry, clock=lambda: self.clock_value,
            id_factory=lambda: f'e-{next(self.ids):016x}', token_count=None)
        if seed:
            self.add_agent(OWNER)
            self.add_agent(OTHER)

    def cleanup(self):
        if self.temporary:
            self.temporary.cleanup()

    def context(self, actor=OWNER, op_id=None, authority='tool'):
        return Context(self.home, self.registry.validators, self.registry.folds,
                       actor, op_id, authority, 'library', self.services)

    def command(self, tool, args, *, actor=OWNER, op_id=None, expected_head=None):
        # A-U13: native U03 retains actor/op_id across fixture restarts; reserve fresh IDs.
        if op_id is None:
            used = {(event['agent'], event['op_id']) for event in self.events()}
            while True:
                op_id = f'op_{next(self.counter):08d}'
                if (actor, op_id) not in used:
                    break
        effective = {**deepcopy(args), 'agent': actor}
        if tool == 'run_close':
            effective.setdefault('evidence', [])
        return Command(tool, effective, actor, op_id, expected_head)

    def events(self):
        return journal.snapshot(self.home)

    def raw(self):
        path = self.home / 'ledger/main/events.jsonl'
        return path.read_bytes() if path.exists() else b''

    def append_peer(self, kind, payload, *, actor=OWNER, validators=None):
        index = len(self.events()) + 1
        return journal.transact(self.home, agent=actor, op_id=f'peer{index:08d}',
            kind=kind, payload=deepcopy(payload),
            validators=validators or {kind: accept},
            clock=lambda: self.clock_value, id_factory=lambda: f'e-{index:016x}')

    def add_agent(self, agent_id):
        record = {'schema': 'lineage.agent/v1', 'agent_id': agent_id,
            'display_name': agent_id, 'workflow': 'test', 'language': 'python',
            'allowed_seats': [deepcopy(SEAT)],
            'references': [{'id': 'gold_s1', 'sha256': sha(b'gold')},
                           {'id': 'memory_v21', 'sha256': sha(b'memory')}],
            'constitution_sha256': sha(b'constitution\n'), 'skills': [], 'memory_gen': 0,
            'brief_head_sha256': sha(b'brief\n'), 'generation': 0, 'parents': [],
            'born': {'op': 'genesis', 'event_id': f'e-{len(self.events()) + 1:016x}'},
            'status': 'draft'}
        # A-U13: seed byte-consistent U12 brief/source fixtures for real projection publication.
        record['agent_version'] = version(record)
        record['brief_head_sha256'] = sha(brief.build(record, (), rule_ids=[]))
        self.append_peer('agent.born', {'record': record,
            'constitution': {'text': 'constitution\n', 'overlays': [], 'rule_ids': []},
            'inherited_units': [], 'rejected_units': []}, actor=agent_id)
        agents.refresh_projections(agent_id, ctx=self.context(agent_id))
        return record

    def controlled_open(self, *, run_id=RUN, agent_id=OWNER, arm='own', task=None, parents=()):
        agent = self.agent(agent_id)
        return self.append_peer('run.open', {'run_id': run_id, 'agent_id': agent_id,
            'agent_version': agent['agent_version'], 'seat': deepcopy(SEAT),
            'task': deepcopy(task or TASK), 'parents_context': deepcopy(list(parents)),
            'memory_arm': arm}, actor=agent_id)

    def agent(self, agent_id=OWNER):
        # A-U13: fold U10 memory before the U12 effective agent/version view.
        state = {}
        for event in self.events():
            peer_memory(state, event)
            peer_agents(state, event)
        return deepcopy(state.get('agents', {}).get(agent_id))

    def snapshot(self, events=None):
        events = self.events() if events is None else tuple(deepcopy(events))
        state = {k: {} for k in ('references', 'skills', 'memory', 'agents', 'runs',
                                'arena', 'scorecards', 'tree', 'promotion')}
        for event in events:
            peer_memory(state, event)
            peer_agents(state, event)
            if event['kind'].startswith('run.'):
                self.registry.folds['runs'](state, deepcopy(event))
        last = events[-1] if events else None
        return Snapshot(tuple(deepcopy(events)), last['lamport'] if last else 0,
                        sha(canonical(last) + b'\n') if last else None, state)

    def unit(self, kind='episode', *, identifier='episode1', run_id=RUN, agent_id=OWNER,
             verdict=None, cost=None, level=3, privacy='public', receipts=()):
        matching = [e for e in self.events() if e['kind'] == 'run.open' and
                    e['payload']['run_id'] == run_id]
        opening = matching[-1]['payload'] if matching else {
            'seat': SEAT, 'task': TASK, 'parents_context': []}
        result = {'schema': 'lineage.mem.unit/v1', 'id': identifier, 'kind': kind,
            'level': level, 'statement': 'Record the observed result.', 'status': 'active',
            'privacy': privacy, 'scope': {'workflow': 'test', 'language': 'python'},
            'provenance': {'origin': 'oracle', 'actor': agent_id, 'run_id': run_id},
            'receipts': deepcopy(list(receipts)), 'supersedes': []}
        bodies = {
            'episode': {'run_id': run_id, 'task_id': opening['task']['id'],
                'seat': deepcopy(opening['seat']), 'parents_context': deepcopy(opening['parents_context']),
                'outcome': deepcopy(verdict if verdict is not None else OUTCOME),
                'cost': deepcopy(COST if cost is None else cost)},
            'lesson': {'tempting_use': 'Skip validation.', 'failure_mode': 'Missing proof.',
                       'safer_action': 'Validate the witness.', 'blocked_use': []},
            'negative': {'gate_id': 'memory-close', 'verdict': 'red', 'cause': 'Missing proof.',
                         'coordinate': 'tests/runs', 'safer_action': 'Write current-run memory.'},
            'workflow': {'trigger_sig': 'on close', 'steps': ['Check memory.'],
                         'stats': {'runs': 1, 'successes': 1, 'mean_reward': None}, 'status': 'candidate'},
            'decision': {'reason': 'Keep the run open.'},
            'ruling': {'quote_sha256': sha(b'rule'), 'how_to_apply': 'Preserve authority.'},
            'open_item': {'class': 'verification', 'order': 1}}
        result['body'] = bodies[kind]
        return result

    def put(self, unit, *, agent_id=OWNER, run_id=RUN):
        return self.append_peer('memory.put', {'agent_id': agent_id,
                    'run_id': run_id, 'unit': deepcopy(unit)}, actor=agent_id)

    def witness(self, verdict=None, *, cost=None, level=3):
        verdict = deepcopy(OUTCOME if verdict is None else verdict)
        units = [self.unit(verdict=verdict, cost=cost, level=level)]
        if verdict['verdict'] in ('error', 'HOLD', 'red') or verdict['repair_loops'] > 0:
            units.append(self.unit('lesson', identifier='lesson01', level=level))
        if verdict['verdict'] in ('HOLD', 'red'):
            units.append(self.unit('negative', identifier='negative', level=level))
        for unit in units:
            self.put(unit)
        return units

    def receipt(self, path='evidence/result.txt', content=b'verified\n'):
        target = self.home / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return {'path': path, 'sha256': sha(content)}

    def open(self, *, run_id=RUN, agent_id=OWNER, seat=None, task=None, parents=(),
             arm='own', actor=None, command=None):
        actor = agent_id if actor is None else actor
        args = {'run_id': run_id, 'agent_id': agent_id, 'seat': deepcopy(SEAT if seat is None else seat),
                'task': deepcopy(TASK if task is None else task),
                'parents_context': deepcopy(list(parents)), 'memory_arm': arm}
        cmd = command or self.command('run_open', args, actor=actor)
        return runs.open_run(run_id, agent_id, args['seat'], args['task'],
            parents_context=args['parents_context'], memory_arm=arm,
            command=cmd, ctx=self.context(actor, cmd.op_id))

    def beat(self, progress='Working', *, run_id=RUN, actor=OWNER, command=None):
        cmd = command or self.command('run_beat', {'run_id': run_id, 'progress': progress}, actor=actor)
        return runs.beat(run_id, progress, command=cmd, ctx=self.context(actor, cmd.op_id))

    def close(self, verdict=None, cost=None, *, run_id=RUN, actor=OWNER, evidence=(), command=None):
        verdict = deepcopy(OUTCOME if verdict is None else verdict)
        cost = deepcopy(COST if cost is None else cost)
        cmd = command or self.command('run_close', {'run_id': run_id, 'outcome': verdict,
                   'cost': cost, 'evidence': deepcopy(list(evidence))}, actor=actor)
        return runs.close(run_id, verdict, cost, evidence=evidence, command=cmd,
                          ctx=self.context(actor, cmd.op_id))

    def check(self, verdict=None, cost=None, *, events=None, actor=OWNER):
        return gate_close.check(self.snapshot(events), RUN,
            deepcopy(OUTCOME if verdict is None else verdict),
            deepcopy(COST if cost is None else cost), actor=actor, ctx=self.context(actor))

    def retire(self):
        return self.append_peer('agent.status', {'agent_id': OWNER, 'from': 'draft',
                    'to': 'retired', 'reason': 'oracle retirement'})


class RunCase(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.addCleanup(self.f.cleanup)

    def refusal(self, code, callback, detail=None):
        before = self.f.raw()
        try:
            events = self.f.events()
        except LineageError as exc:
            if code != 'hash_mismatch' or exc.code != 'hash_mismatch':
                raise
            events = None
        with self.assertRaises(LineageError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)
        if detail is not None:
            self.assertEqual(caught.exception.detail, detail)
        self.assertEqual(self.f.raw(), before)
        if events is not None:
            self.assertEqual(self.f.events(), events)

    def passed(self, report):
        self.assertEqual(set(report), {'passed', 'checks', 'memory_receipts'})
        self.assertIs(report['passed'], True)
        self.assertGreaterEqual(len(report['checks']), 1)
        self.assertLessEqual(len(report['checks']), 32)
        for check in report['checks']:
            self.assertIs(check['passed'], True)
            self.assertIsInstance(check['id'], str)
            self.assertLessEqual(set(check), {'id', 'passed', 'detail'})
        self.assertEqual(report['memory_receipts'], sorted(report['memory_receipts'],
                         key=lambda r: (r['path'], r['sha256'])))

    def closed(self, committed):
        self.assertEqual(set(committed.value), {'run', 'commit'})
        record = committed.value['run']
        validate_record(record, 'run.schema.json')
        event = committed.event
        self.assertEqual(event['kind'], 'run.close')
        self.assertEqual(record, event['payload']['record'])
        self.assertEqual(set(event['payload']), {'record', 'gate', 'memory_receipts'})
        self.assertEqual(set(event['payload']['gate']), {'passed', 'checks'})
        self.assertEqual(committed.value['commit'], {'event_ids': [event['id']],
            'head': event['lamport'], 'sha256': event['sha256']})
        self.assertEqual(record['ts_close'], event['ts'])
        self.assertLessEqual(record['ts_open'], record['ts_close'])
        self.assertTrue(record['memory']['gate_passed'])
        self.assertEqual(record['memory']['unit_ids'], sorted(set(record['memory']['unit_ids'])))
        self.assertEqual(record['memory']['levels'], sorted(set(record['memory']['levels'])))
        self.assertEqual(runs.get(record['run_id'], ctx=self.f.context())['closed'], record)
        self.assertTrue(journal.verify(self.f.home)['ok'])
        return record


class GateCase(RunCase):
    def setUp(self):
        super().setUp()
        self.f.controlled_open()


# These children never create process groups. Only their parent-owned Process is terminated.
def child_operation(home, operation, command, start, connection):
    fixture = Fixture(home, seed=False)
    fixture.services.id_factory = lambda: 'e-' + sha(command.op_id.encode())[:16]
    try:
        if not start.wait(1.0):
            raise AssertionError('start barrier expired')
        if operation == 'close':
            value = fixture.close(command=command).value
        elif operation == 'retire':
            value = fixture.retire()
        else:
            value = fixture.append_peer('memory.retire', {'agent_id': OWNER, 'unit_id': 'episode1'})
        connection.send(('ok', value))
    except BaseException as exc:
        connection.send(('error', getattr(exc, 'code', type(exc).__name__), str(exc)))
    finally:
        connection.close()


def lock_child(home, ready, release):
    import fcntl
    path = Path(home) / 'ledger/main/events.lock'
    with path.open('r+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        ready.set()
        if not release.wait(2.0):
            raise AssertionError('release barrier expired')


@contextmanager
def owned_process(target, args):
    process = multiprocessing.get_context('fork').Process(target=target, args=args)
    process.start()
    pid = process.pid
    try:
        yield process
    finally:
        process.join(0.5)
        if process.is_alive():
            if pid is None or pid <= 1 or process.pid != pid:
                raise AssertionError('unsafe child identity')
            process.terminate()
            process.join(0.5)
        if process.is_alive():
            raise AssertionError('owned child failed to stop')
