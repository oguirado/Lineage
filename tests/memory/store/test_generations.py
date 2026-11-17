"""Ledger-derived historical generations and immutable rebuilds: A5-A11."""
import copy
import json
import shutil
from pathlib import PurePosixPath
from lineage.domain.memory import store, bootcheck
from tests.memory.store import OracleCase, AGENT, OTHER, Counter, agent_record, canonical, sha, unit_record, validate_record, version


class GenerationOracle(OracleCase):
    def test_a05_full_history_mapping_is_pure_canonical_and_complete(self):
        self.history(); before = self.disk_tree()
        mapping = self.generated()
        self.assertEqual(self.disk_tree(), before)
        self.assertEqual(mapping['CURRENT'], b'gen/7\n')
        self.assertEqual(mapping['MEMORY_ENTRY.static.md'], mapping['gen/7/MEMORY_ENTRY.static.md'])
        self.assertEqual(mapping['journal.jsonl'], mapping['gen/7/journal.jsonl'])
        for name, raw in mapping.items():
            self.assertIs(type(raw), bytes)
            self.assertFalse(PurePosixPath(name).is_absolute())
            self.assertNotIn('..', PurePosixPath(name).parts)
            self.assertNotIn(str(self.base).encode(), raw)
            if name.endswith('.json'):
                self.assertEqual(raw, canonical(json.loads(raw)) + b'\n')
            if '/units/' in name:
                validate_record(json.loads(raw), 'mem_unit.schema.json')
        for g in range(1, 8):
            prefix = 'gen/%d/' % g
            self.assertIn(prefix + 'MEMORY_ENTRY.static.md', mapping)
            self.assertIn(prefix + 'journal.jsonl', mapping)
            manifest = json.loads(mapping[prefix + 'manifest.json'])
            self.assertEqual(set(manifest), {'agent_id', 'generation', 'source_head', 'agent_version', 'memory_gen', 'files'})
            self.assertEqual(manifest['agent_id'], AGENT); self.assertEqual(manifest['generation'], g)
            self.assertEqual(manifest['source_head'], g + 2)
            expected_files = sorted(k[len(prefix):] for k in mapping if k.startswith(prefix) and k != prefix + 'manifest.json')
            self.assertEqual(manifest['files'], [{'path': k, 'sha256': sha(mapping[prefix + k])} for k in expected_files])
            self.assertEqual(mapping[prefix + 'journal.jsonl'], b''.join(canonical(e) + b'\n' for e in self.events[2:g+2]))
        current_units = {k.split('/')[-1] for k in mapping if k.startswith('gen/7/units/')}
        self.assertEqual(current_units, {'InheritedA.json', 'Episode01.json', 'Replace01.json'})

    def test_a05_loss_rebuild_identical_across_two_runtime_homes(self):
        self.history(); expected = self.generated(); self.publish()
        ledger = self.ledger.read_bytes()
        first = {k: (self.memory / k).read_bytes() for k in expected}
        shutil.rmtree(self.memory)
        self.publish()
        self.assertEqual({k: (self.memory / k).read_bytes() for k in expected}, first)
        self.assertEqual(self.ledger.read_bytes(), ledger)
        other_home = self.base / 'second-home'; other_home.mkdir()
        old_home = self.home
        try:
            self.home = other_home; self.ctx = self.context(); self.seed_ledger(); self.publish()
            self.assertEqual({k: (self.memory / k).read_bytes() for k in expected}, first)
        finally:
            self.home = old_home

    def test_a06_birth_is_generation_one_and_episode_is_not_memory_gen(self):
        initial = self.generated()
        self.assertEqual(initial['CURRENT'], b'gen/1\n')
        original_version, original_brief = self.agent['agent_version'], self.agent['memory_gen']
        self.add_event('run.open', {'run_id': 'Run00001', 'agent_id': AGENT, 'agent_version': original_version,
            'seat': self.agent['allowed_seats'][0], 'task': {'id': 'Task0001', 'kind': 'fixture', 'language': 'python'},
            'parents_context': [], 'memory_arm': 'own'})
        self.add_unit(unit_record('Episode01', kind='episode'))
        after = self.generated()
        self.assertEqual(after['CURRENT'], b'gen/3\n')
        self.assertEqual(self.agent['memory_gen'], original_brief)
        self.assertEqual(self.agent['agent_version'], original_version)
        manifest = json.loads(after['gen/3/manifest.json'])
        self.assertEqual(manifest['memory_gen'], original_brief)
        self.assertEqual(manifest['agent_version'], original_version)
        self.add_unit(unit_record('Lesson001', level=2))
        brief = self.generated()
        self.assertEqual(brief['CURRENT'], b'gen/4\n')
        self.assertEqual(json.loads(brief['gen/4/manifest.json'])['memory_gen'], original_brief+1)
        self.assertNotEqual(self.agent['agent_version'], original_version)

    def test_a06_unrelated_head_does_not_rewrite_entry_or_generation(self):
        self.history(); one = self.generated()
        self.birth(agent_record(OTHER, event_id='e-%016x' % (len(self.events)+1)))
        two = self.generated()
        self.assertEqual(one, two)
        expect = bootcheck.expected(AGENT, snapshot=self.snapshot, ctx=self.ctx)
        self.assertEqual(expect['head'], len(self.events))
        self.assertEqual(expect['memory_gen'], self.agent['memory_gen'])
        self.assertEqual(expect['entry_sha256'], sha(two['MEMORY_ENTRY.static.md']))

    def test_a07_historical_versions_and_supersession_are_not_copied_backward(self):
        self.history(); mapping = self.generated()
        for g, memory_gen in enumerate((1, 1, 1, 2, 3, 4, 5), 1):
            manifest = json.loads(mapping['gen/%d/manifest.json' % g])
            a = copy.deepcopy(self.agent); a['memory_gen'] = memory_gen
            self.assertEqual(manifest['memory_gen'], memory_gen)
            self.assertEqual(manifest['agent_version'], version(a))
        old = json.loads(mapping['gen/4/units/Lesson001.json'])
        self.assertEqual(old['status'], 'active'); self.assertNotIn('superseded_by', old)
        self.assertNotIn('gen/6/units/Lesson001.json', mapping)
        self.assertIn('gen/5/units/Retire001.json', mapping)
        self.assertNotIn('gen/7/units/Retire001.json', mapping)
        self.assertIn('gen/1/units/InheritedA.json', mapping)

    def test_a07_repeated_rebuild_reuses_every_published_generation(self):
        self.history(); self.publish(); before = self.disk_tree(self.memory)
        self.publish(); self.assertEqual(self.disk_tree(self.memory), before)
        self.assertEqual(store.verify_projection(AGENT, snapshot=self.snapshot, ctx=self.ctx), ())

    def test_a08_subject_selection_preserves_original_hashes_and_gaps(self):
        self.history()
        self.birth(agent_record(OTHER, event_id='e-000000000000000a'))
        unrelated = unit_record('Other001', 'agent-one only appears as passive text', actor=OTHER)
        self.add_unit(unrelated, target=OTHER, actor=OTHER)
        self.add_event('run.beat', {'run_id': 'Run00001', 'agent_id': AGENT, 'progress': 'fixture'}, actor='system')
        mapping = self.generated(); selected = self.events[2:9] + [self.events[-1]]
        self.assertEqual(mapping['CURRENT'], b'gen/8\n')
        self.assertEqual(mapping['journal.jsonl'], b''.join(canonical(e) + b'\n' for e in selected))
        lines = [json.loads(x) for x in mapping['journal.jsonl'].splitlines()]
        self.assertEqual([x['lamport'] for x in lines], [3,4,5,6,7,8,9,12])
        self.assertEqual(lines[0]['agent'], 'parent-one')
        self.assertEqual(lines[3]['agent'], 'parent-one')
        self.assertEqual(lines[-1]['prev_sha256'], self.events[-1]['prev_sha256'])

    def test_b04_contradictory_agent_inputs_are_refused(self):
        bad = copy.deepcopy(self.agent); bad['memory_gen'] += 1; bad['agent_version'] = version(bad)
        self.domain_error(('bad_args', 'bad_op'), lambda: store.generation_files(bad, (), self.events, token_count=Counter()))

    def test_b04_contradictory_unit_inputs_are_refused(self):
        self.add_unit(unit_record())
        bad = list(self.active); bad[0]['statement'] = 'Not present in the committed event'
        self.domain_error(('bad_args', 'bad_op'), lambda: store.generation_files(self.agent, bad, self.events, token_count=Counter()))

    def test_a03_rebuild_without_counter_refuses_without_partial_files(self):
        # A-TOK1: an absent counter is admissible for provably small entries; an
        # unusable counter must still refuse without partial files.
        def broken(text): raise ValueError('synthetic tokenizer failure')
        self.ctx = self.context(token_count=broken); before = self.disk_tree()
        self.domain_error('memory_debt', lambda: store.rebuild(AGENT, snapshot=self.snapshot, ctx=self.ctx))
        self.assertEqual(self.disk_tree(), before)

    def test_a11_corrupted_published_entry_cannot_be_repaired_in_place(self):
        self.history(); self.publish()
        selected = (self.memory / 'CURRENT').read_text().strip()
        victim = self.memory / selected / 'MEMORY_ENTRY.static.md'; victim.write_bytes(b'tampered\n')
        before = self.disk_tree()
        self.domain_error('hash_mismatch', lambda: store.rebuild(AGENT, snapshot=self.snapshot, ctx=self.ctx))
        self.assertEqual(self.disk_tree(), before)

    def test_a24_old_prefix_cannot_regress_current(self):
        old = self.snapshot; self.publish()
        self.add_unit(unit_record(level=2)); self.seed_ledger(); self.publish()
        newest = (self.memory / 'CURRENT').read_bytes()
        try:
            store.rebuild(AGENT, snapshot=old, ctx=self.ctx)
        except NotImplementedError:
            raise
        except Exception as exc:
            self.assertIn(getattr(exc, 'code', None), {'stale_rev', 'busy'})
        self.assertEqual((self.memory / 'CURRENT').read_bytes(), newest)


def _private_retention(self):
    private=unit_record('Private01','private context must never be recalled',privacy='private')
    self.add_unit(private); first=self.generated()
    retained='gen/2/units/Private01.json' in first
    self.add_unit(unit_record('Public001','public context')); second=self.generated()
    self.assertEqual('gen/3/units/Private01.json' in second,retained)
    for k,v in first.items():
        if k.startswith('gen/'):
            self.assertEqual(second[k],v)
    for g in (2,3):
        self.assertNotIn(private['statement'].encode(),second['gen/%d/MEMORY_ENTRY.static.md'%g])
        if retained:self.assertEqual(second['gen/%d/units/Private01.json'%g],canonical(private)+b'\n')
    self.assertEqual(second,self.generated())


GenerationOracle.test_b03_private_file_policy_is_consistent_and_reproducible=_private_retention


def _mapping_defensive(self):
    first=self.generated(); saved=dict(first)
    if isinstance(first,dict):first['CURRENT']=b'gen/999\n'
    self.assertEqual(dict(self.generated()),saved)


GenerationOracle.test_a29_generation_mapping_does_not_alias_future_results=_mapping_defensive


def _actor_selection(self):
    self.add_event('skill.retired',{'skill_id':'fixture-skill','sha256':'0'*64},actor=AGENT)
    mapping=self.generated()
    self.assertEqual(mapping['CURRENT'],b'gen/2\n')
    self.assertEqual(mapping['gen/1/MEMORY_ENTRY.static.md'],mapping['gen/2/MEMORY_ENTRY.static.md'])
    self.assertEqual(mapping['journal.jsonl'],b''.join(canonical(e)+b'\n' for e in self.events))


GenerationOracle.test_a08_target_actor_event_is_selected_without_a_target_payload=_actor_selection
