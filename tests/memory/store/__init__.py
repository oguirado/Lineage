"""Independent U11 oracle fixtures; no replacement domain fold or tokenizer.

Contract-shaped doubles permit pure-surface fail-first calls. State is always
obtained from the real K0 journal.fold and registry when a consumer requests it.
Their absence is an integration failure, never an empty memory or a skip.
"""
from __future__ import annotations
import copy
import hashlib
import importlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from collections.abc import Mapping
from contextlib import contextmanager, ExitStack
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
AGENT = 'agent-one'
OTHER = 'agent-other'
SEAT = {'model': 'fixture-model', 'effort': 'medium', 'mode': 'headless'}
COST = dict.fromkeys(('tokens_in', 'tokens_out', 'tokens_cache', 'duration_ms', 'cost_micro_usd'))
CONSTITUTION = 'Synthetic test constitution.\n'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def version(agent):
    return sha(canonical({k: agent[k] for k in ('constitution_sha256', 'skills', 'memory_gen')}))


def agent_record(agent_id=AGENT, *, memory_gen=0, event_id='e-0000000000000001'):
    a = {'schema': 'lineage.agent/v1', 'agent_id': agent_id,
         'display_name': 'Fixture agent', 'workflow': 'develop', 'language': 'python',
         'allowed_seats': [copy.deepcopy(SEAT)],
         'references': [{'id': 'gold_s1', 'sha256': sha(b'fixture gold')},
                        {'id': 'memory_v21', 'sha256': sha(b'fixture memory')}],
         'constitution_sha256': sha(CONSTITUTION.encode()), 'skills': [],
         'memory_gen': memory_gen, 'brief_head_sha256': sha(b'fixture brief'),
         'generation': 0, 'parents': [], 'born': {'op': 'genesis', 'event_id': event_id},
         'status': 'draft'}
    a['agent_version'] = version(a)
    return a


def unit_record(unit_id='Lesson001', statement='Retry only after verifying the receipt.',
                *, kind='lesson', level=3, actor=AGENT, privacy='public',
                status='active', language='python', workflow='develop'):
    bodies = {
        'lesson': {'tempting_use': 'Retry blindly', 'failure_mode': 'Duplicate work',
                   'safer_action': 'Verify first', 'blocked_use': []},
        'negative': {'gate_id': 'fixture-gate', 'verdict': 'HOLD', 'cause': 'Missing evidence',
                     'coordinate': 'evidence/receipt.txt', 'safer_action': 'Verify first'},
        'workflow': {'trigger_sig': 'retry', 'steps': ['Verify first'],
                     'stats': {'runs': 0, 'successes': 0, 'mean_reward': None}, 'status': 'promoted'},
        'episode': {'run_id': 'Run00001', 'task_id': 'Task0001', 'seat': copy.deepcopy(SEAT),
                    'outcome': {'verdict': 'green', 'repair_loops': 0,
                                'findings': {'confirmed': 0, 'refuted': 0}},
                    'cost': copy.deepcopy(COST), 'parents_context': []},
        'decision': {'reason': 'Evidence determines the action'},
        'open_item': {'class': 'followup', 'order': 0},
        'ruling': {'quote_sha256': sha(b'fixture ruling'), 'how_to_apply': 'Preserve the quote'},
    }
    u = {'schema': 'lineage.mem.unit/v1', 'id': unit_id, 'kind': kind, 'level': level,
         'statement': statement, 'status': status, 'privacy': privacy,
         'scope': {'workflow': workflow, 'language': language},
         'provenance': {'origin': 'synthetic oracle fixture', 'actor': actor},
         'receipts': [], 'supersedes': [], 'body': bodies[kind]}
    if level == 2:
        u['receipts'] = [{'path': 'evidence/receipt.txt', 'sha256': sha(b'fixture receipt\n')}]
    if kind == 'episode':
        u['provenance']['run_id'] = 'Run00001'
    if status == 'superseded':
        u['superseded_by'] = 'Replace01'
    return u


class Counter:
    """Trusted-construction test double; does not certify real tokenization."""
    def __init__(self, value=1):
        self.value, self.inputs = value, []

    def __call__(self, text):
        self.inputs.append(text)
        return self.value


class LazyRegistry:
    def __getattr__(self, name):
        reg = importlib.import_module('lineage.core.registry')
        if not hasattr(reg, 'Registry'):
            raise AssertionError('AUSENTE: frozen K0 Registry; integrated acceptance is blocked')
        return getattr(reg.load(), name)


class CommittedPrefix:
    """Read-only fixture prefix; its state is never synthesized by this oracle."""
    def __init__(self, events, registry):
        self.events = tuple(copy.deepcopy(events))
        self.head = events[-1]['lamport'] if events else 0
        self.raw_head_sha256 = sha(canonical(events[-1]) + b'\n') if events else None
        self._registry = registry

    @property
    def state(self):
        journal = importlib.import_module('lineage.core.journal')
        if not hasattr(journal, 'fold'):
            raise AssertionError('AUSENTE: K0 journal.fold and U10 memory fold; not an empty state')
        return journal.fold(copy.deepcopy(self.events), registry=self._registry)


def validate_record(value, filename):
    """Small independent assertion evaluator for the bundled fixture schemas."""
    def check(v, s):
        if s is True:
            return
        if s is False:
            raise AssertionError('false schema')
        if '$ref' in s:
            target = s['$ref']
            if '#' in target:
                raise AssertionError('fixture schema reference requires an explicit local resolver')
            check(v, json.loads((ROOT / 'schemas' / target).read_text()))
        def matches(x, y):
            return type(x) is type(y) and x == y
        if 'const' in s:
            assert matches(v, s['const']), 'const'
        if 'enum' in s:
            assert any(matches(v, x) for x in s['enum']), 'enum'
        if 'type' in s:
            types = {'object': lambda x: type(x) is dict, 'array': lambda x: type(x) is list,
                     'string': lambda x: type(x) is str, 'integer': lambda x: type(x) is int,
                     'number': lambda x: type(x) in (int, float), 'boolean': lambda x: type(x) is bool,
                     'null': lambda x: x is None}
            assert types[s['type']](v), 'type'
        def passes(schema):
            try:
                check(v, schema)
                return True
            except AssertionError:
                return False
        for part in s.get('allOf', []):
            check(v, part)
        if 'anyOf' in s:
            assert any(passes(part) for part in s['anyOf']), 'anyOf'
        if 'oneOf' in s:
            assert sum(passes(part) for part in s['oneOf']) == 1, 'oneOf'
        if 'not' in s:
            assert not passes(s['not']), 'not'
        if 'if' in s:
            branch = s.get('then' if passes(s['if']) else 'else', True)
            check(v, branch)
        if isinstance(v, dict):
            assert all(k in v for k in s.get('required', [])), 'required'
            props = s.get('properties', {})
            if s.get('additionalProperties') is False:
                assert not (set(v) - set(props)), 'extra property'
            for k in set(v) & set(props):
                check(v[k], props[k])
        if isinstance(v, (list, str)):
            assert len(v) >= s.get('minItems' if isinstance(v, list) else 'minLength', 0), 'minimum length'
            assert len(v) <= s.get('maxItems' if isinstance(v, list) else 'maxLength', len(v)), 'maximum length'
        if isinstance(v, list):
            if s.get('uniqueItems'):
                assert len({canonical(x) for x in v}) == len(v), 'uniqueItems'
            for x in v:
                check(x, s.get('items', True))
        if isinstance(v, str) and 'pattern' in s:
            assert re.search(s['pattern'], v), 'pattern'
        if type(v) in (int, float):
            assert v >= s.get('minimum', v) and v <= s.get('maximum', v), 'numeric bounds'
    schema = json.loads((ROOT / 'schemas' / filename).read_text()) if isinstance(filename, str) else filename
    check(value, schema)


def tool_schemas(name):
    text = (ROOT / 'docs' / 'CONTRACT.md').read_text()
    section = text.split('### `' + name + '`', 1)[1].split('\n### ', 1)[0]
    blocks = re.findall(r'```json\s*\n(.*?)\n```', section, re.S)
    return json.loads(blocks[0]), json.loads(blocks[1])


class OracleCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.runtime-', dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home, self.repo = self.base / 'home', self.base / 'repo'
        # A-U11: integrated family admission requires owner-controlled runtime directories.
        self.home.mkdir(mode=0o700); self.repo.mkdir(mode=0o700)
        for root in (self.home, self.repo):
            (root / 'evidence').mkdir()
            (root / 'evidence' / 'receipt.txt').write_bytes(b'fixture receipt\n')
        shutil.copytree(ROOT / 'schemas', self.repo / 'schemas')
        self.counter = Counter()
        self.ctx = self.context()
        self.agent = agent_record()
        self.units, self.events = [], []
        self.birth(self.agent)
        self.seed_ledger()

    def context(self, *, token_count='default', actor='system'):
        count = self.counter if token_count == 'default' else token_count
        fields = dict(home=self.home, repo_root=self.repo, registry=LazyRegistry(),
                      clock=mock.Mock(side_effect=AssertionError('projection consulted clock')),
                      id_factory=mock.Mock(side_effect=AssertionError('projection consulted id factory')),
                      token_count=count)
        registry = importlib.import_module('lineage.core.registry')
        services = registry.Services(**fields) if hasattr(registry, 'Services') else SimpleNamespace(**fields)
        values = dict(services=services, actor=actor, authority='tool', transport='library')
        return registry.Context(**values) if hasattr(registry, 'Context') else SimpleNamespace(**values)

    def add_event(self, kind, payload, actor=AGENT, evidence=()):
        n = len(self.events) + 1
        event = {'schema': 'lineage.event/v1', 'id': 'e-%016x' % n, 'lamport': n,
                 'ts': n, 'ledger': 'main', 'agent': actor, 'kind': kind,
                 'payload': copy.deepcopy(payload), 'op_id': 'fixture-%d' % n,
                 'request_sha256': sha(canonical({'kind': kind, 'payload': payload})),
                 'evidence': copy.deepcopy(list(evidence)),
                 'prev_sha256': sha(canonical(self.events[-1]) + b'\n') if self.events else '0' * 64}
        event['sha256'] = sha(canonical(event))
        self.events.append(event)
        return event

    def birth(self, agent, inherited=(), actor='system'):
        return self.add_event('agent.born', {'record': agent, 'inherited_units': list(inherited),
            'rejected_units': [], 'constitution': {'text': CONSTITUTION, 'overlays': [], 'rule_ids': []}}, actor)

    def add_unit(self, unit, *, target=AGENT, actor=AGENT):
        self.add_event('memory.put', {'agent_id': target, 'unit': unit}, actor)
        if target != AGENT:
            return
        for old in self.units:
            if old['id'] in unit['supersedes']:
                old['status'], old['superseded_by'] = 'superseded', unit['id']
        self.units.append(copy.deepcopy(unit))
        if unit['status'] == 'active' and unit['kind'] in ('ruling', 'lesson', 'negative', 'workflow') and unit['privacy'] != 'private' and unit['scope']['workflow'] == self.agent['workflow'] and unit['scope']['language'] in (self.agent['language'], 'general'):
            self.agent['memory_gen'] += 1
            self.agent['agent_version'] = version(self.agent)

    def history(self):
        self.units, self.events = [], []
        parent = agent_record('parent-one')
        self.birth(parent)
        source = unit_record('Source001', 'inherited retry policy', level=2, actor='parent-one')
        self.add_unit(source, target='parent-one', actor='parent-one')
        inherited = copy.deepcopy(source); inherited['id'] = 'InheritedA'
        inherited['provenance']['inherited_from'] = {'agent_id': 'parent-one', 'unit_id': source['id'], 'unit_sha256': sha(canonical(source))}
        self.agent = agent_record(memory_gen=1, event_id='e-0000000000000003')
        self.agent['generation'], self.agent['parents'], self.agent['born']['op'] = 1, ['parent-one'], 'clone'
        self.birth(self.agent, [{'unit': inherited, 'source_agent_id': 'parent-one', 'source_unit_id': source['id'], 'unit_sha256': sha(canonical(source))}], actor='parent-one')
        self.units.append(inherited)
        self.add_event('run.open', {'run_id': 'Run00001', 'agent_id': AGENT,
            'agent_version': self.agent['agent_version'], 'seat': SEAT,
            'task': {'id': 'Task0001', 'kind': 'fixture', 'language': 'python'},
            'parents_context': [], 'memory_arm': 'inherited'}, actor='system')
        self.add_unit(unit_record('Episode01', 'episode with unknown costs', kind='episode'))
        self.add_unit(unit_record('Lesson001', 'original retry rule', level=2), actor='parent-one')
        self.add_unit(unit_record('Retire001', 'temporary retry rule', level=2))
        replacement = unit_record('Replace01', 'replacement retry rule', level=2)
        replacement['supersedes'] = ['Lesson001']
        self.add_unit(replacement)
        self.add_event('memory.retire', {'agent_id': AGENT, 'unit_id': 'Retire001'})
        next(u for u in self.units if u['id'] == 'Retire001')['status'] = 'retired'
        self.agent['memory_gen'] += 1; self.agent['agent_version'] = version(self.agent)
        self.seed_ledger()

    @property
    def active(self):
        return tuple(copy.deepcopy(u) for u in self.units if u['status'] == 'active')

    @property
    def snapshot(self):
        return CommittedPrefix(self.events, self.ctx.services.registry)

    def seed_ledger(self):
        self.ledger = self.home / 'ledger' / 'main' / 'events.jsonl'
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        # A-U11: integrated journal requires a stable events.lock beside seeded ledger bytes.
        (self.ledger.parent / 'events.lock').touch(exist_ok=True)
        self.ledger.write_bytes(b''.join(canonical(e) + b'\n' for e in self.events))

    @contextmanager
    def reading(self, *, snapshot=None, failure=None):
        journal = importlib.import_module('lineage.core.journal')
        options = {'side_effect': failure} if failure is not None else {'return_value': snapshot or self.snapshot}
        with mock.patch.object(journal, 'snapshot', create=True, **options) as call:
            yield call

    def generated(self):
        from lineage.domain.memory import store
        return store.generation_files(copy.deepcopy(self.agent), self.active, copy.deepcopy(self.events), token_count=self.counter)

    def publish(self, *, snapshot=None):
        from lineage.domain.memory import store
        paths = store.rebuild(AGENT, snapshot=snapshot or self.snapshot, ctx=self.ctx)
        self.assertIsInstance(paths, tuple)
        normalized = tuple(p if p.is_absolute() else self.home / p for p in paths)
        self.assertTrue(normalized)
        self.assertEqual([p.relative_to(self.home).as_posix() for p in normalized], sorted(p.relative_to(self.home).as_posix() for p in normalized))
        pointers = [p for p in normalized if p.name == 'CURRENT']
        self.assertEqual(len(pointers), 1)
        self.memory = pointers[0].parent
        self.assertEqual(self.memory.name, 'memory')
        return normalized

    def disk_tree(self, root=None):
        root = root or self.home
        result = {}
        for p in sorted(root.rglob('*')):
            if p.is_symlink():
                result[p.relative_to(root).as_posix()] = ('symlink', str(p.readlink()))
            elif p.is_file():
                result[p.relative_to(root).as_posix()] = p.read_bytes()
        return result

    def observed(self):
        """Independent actual bytes + fixture ledger; deliberately not expected()."""
        selected = (self.memory / 'CURRENT').read_text().rstrip('\n')
        entry = (self.memory / selected / 'MEMORY_ENTRY.static.md').read_bytes()
        return {'agent_version': self.agent['agent_version'], 'memory_gen': self.agent['memory_gen'],
                'head': self.events[-1]['lamport'], 'entry_sha256': sha(entry)}

    def domain_error(self, code, call, *, boot=False):
        try:
            call()
        except NotImplementedError:
            raise
        except Exception as exc:
            self.assertEqual(type(exc).__name__, 'LineageError', 'Expected the frozen K0 error, not an incidental exception')
            self.assertIn(exc.code, (code,) if isinstance(code, str) else code)
            self.assertIsInstance(exc.detail, str)
            self.assertLessEqual(len(exc.detail), 2048)
            self.assertNotIn(str(self.base), exc.detail)
            self.assertNotIn(str(ROOT), exc.detail)
            if boot:
                self.assertTrue(exc.detail.startswith('E_BOOTCHECK'), exc.detail)
            return exc
        self.fail('Required fail-closed error was not raised')

    def assert_issues(self, issues):
        self.assertIsInstance(issues, tuple)
        self.assertTrue(issues)
        for issue in issues:
            self.assertEqual(set(issue), {'path', 'code', 'detail'})
            self.assertIn(issue['code'], {'hash_mismatch', 'bad_args', 'internal'})
            path = PurePosixPath(issue['path'])
            self.assertFalse(path.is_absolute())
            self.assertNotIn('..', path.parts)
            self.assertLessEqual(len(issue['detail']), 2048)
            self.assertNotIn(str(self.base), issue['detail'])
            self.assertNotIn(str(ROOT), issue['detail'])

    def assert_route(self, data, units, *, head=None):
        self.assertEqual(set(data), {'units', 'answer', 'head'})
        self.assertEqual(data, {'units': units, 'answer': units[0]['statement'] if units else 'NOT IN MEMORY',
                                'head': self.snapshot.head if head is None else head})
        validate_record(data, tool_schemas('memory_route')[1])

    def assert_boot(self, data, *, head=None):
        self.assertEqual(set(data), {'passed', 'code', 'checks', 'head'})
        self.assertIs(data['passed'], True); self.assertEqual(data['code'], 'OK')
        self.assertEqual(data['head'], self.snapshot.head if head is None else head)
        self.assertTrue(data['checks'])
        self.assertTrue(all(c['passed'] is True for c in data['checks']))
        validate_record(data, tool_schemas('memory_bootcheck')[1])

    def require_k0(self):
        registry = importlib.import_module('lineage.core.registry')
        journal = importlib.import_module('lineage.core.journal')
        app = importlib.import_module('lineage.core.app')
        for obj, members in ((registry, ('Command', 'Registry', 'Snapshot', 'Services', 'Context')),
                             (journal, ('snapshot', 'transact', 'fold')), (app, ('dispatch',))):
            for name in members:
                self.assertTrue(hasattr(obj, name), 'AUSENTE: frozen K0 ' + name + '; integration remains pending')
        return registry, journal, app

    def dispatch(self, name, args):
        extension = importlib.import_module('lineage.ext.memory_resume')
        # Discovery is part of the real dispatch prerequisite, not a fake registry.
        self.assertEqual({t.name for t in extension.TOOLS}, {'memory_route', 'memory_bootcheck'})
        _, _, app = self.require_k0()
        return app.dispatch(name, copy.deepcopy(args), ctx=self.ctx)


@contextmanager
def alias_patch(module, name, replacement):
    """Patch one public seam through existing import aliases as well.

    Import style is not part of the contract. No private helper name is frozen.
    """
    original=getattr(module,name)
    with ExitStack() as patches:
        modules=[module]+[m for key,m in tuple(sys.modules.items())
                          if key.startswith('lineage.') and m is not None and m is not module]
        for candidate in modules:
            for key,value in tuple(vars(candidate).items()):
                if value is original:
                    patches.enter_context(mock.patch.object(candidate,key,replacement))
        yield replacement
