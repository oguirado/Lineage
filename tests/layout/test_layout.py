"""Exercise canonical homes through the real public CLI and confined verifier."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from lineage.domain import layout

ROOT = Path(__file__).resolve().parents[2]


class LayoutTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='.runtime-', dir=Path(__file__).parent)
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name) / 'home'
        self.home.mkdir(mode=0o700)
        self.references = [{'id': ref, 'sha256': self.call('reference_get', {'ref_id': ref})['untrusted']['reference']['sha256']}
                           for ref in ('gold_s1', 'memory_v21')]

    def call(self, tool, args, code=0):
        completed = subprocess.run(
            [sys.executable, '-B', '-m', 'lineage', '--home', str(self.home),
             'call', tool, '--json', json.dumps(args, ensure_ascii=False)],
            cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
            capture_output=True, text=True, timeout=15, check=False)
        self.assertEqual(completed.returncode, code, completed.stdout + completed.stderr)
        self.assertEqual(completed.stderr, '')
        self.assertEqual(len(completed.stdout.splitlines()), 1)
        return json.loads(completed.stdout)

    def create(self, *, language='python', workflow='test'):
        args = {'agent_id': 'agent-one', 'display_name': 'Layout oracle',
                'workflow': workflow, 'language': language,
                'allowed_seats': [{'model': 'fixture', 'effort': 'medium', 'mode': 'headless'}],
                'references': self.references, 'skills': [],
                'agent': 'system', 'op_id': 'create/layout:unchanged'}
        result = self.call('agent_create', args)
        directory = layout.agent_dir(self.home, workflow=workflow, language=language, agent_id='agent-one')
        return args, result, directory

    def verify(self):
        result = self.call('ledger_verify', {})
        self.assertIs(result['untrusted']['valid'], True)
        self.assertEqual(result['untrusted']['issues'], [])

    def inventory(self):
        return {path.relative_to(self.home).as_posix():
                (path.read_bytes(), path.stat().st_ino, path.stat().st_mode,
                 path.stat().st_mtime_ns, path.stat().st_ctime_ns)
                for path in self.home.rglob('*') if path.is_file()}

    def test_exact_single_agent_tree_and_clean_verification(self):
        _, _, directory = self.create()
        prefix = 'test/python/agent-one'
        expected = {'test', 'test/python', prefix, prefix + '/memory',
                    prefix + '/memory/gen', prefix + '/memory/gen/1'}
        expected.update(prefix + '/' + name for name in layout.PROJECTION_FILES)
        expected.update(prefix + '/memory/' + name for name in
                        ('.publish.lock', 'CURRENT', 'MEMORY_ENTRY.static.md', 'journal.jsonl',
                         'gen/1/MEMORY_ENTRY.static.md', 'gen/1/journal.jsonl', 'gen/1/manifest.json'))
        self.assertEqual({p.relative_to(self.home / 'agents').as_posix()
                          for p in (self.home / 'agents').rglob('*')}, expected)
        self.assertEqual((directory / 'memory/CURRENT').read_bytes(), b'gen/1\n')
        self.verify()

    def test_each_projection_tamper_is_drift_and_verification_is_read_only(self):
        _, _, directory = self.create()
        for name in layout.PROJECTION_FILES:
            with self.subTest(name=name):
                path = directory / name
                original = path.read_bytes()
                path.write_bytes(b'{}\n' if name.endswith('.json') else b'tampered\n')
                before = self.inventory()
                error = self.call('ledger_verify', {}, 3)
                self.assertEqual(error['code'], 'hash_mismatch')
                self.assertIn('projection_drift', error['detail'])
                self.assertIn(path.relative_to(self.home).as_posix(), error['detail'])
                self.assertEqual(self.inventory(), before)
                path.write_bytes(original)
        self.verify()

    def test_missing_agent_file_is_drift(self):
        _, _, directory = self.create()
        (directory / 'agent.json').unlink()
        error = self.call('ledger_verify', {}, 3)
        self.assertEqual(error['code'], 'hash_mismatch')
        self.assertIn('agent.json: projection_drift: missing', error['detail'])
        self.assertFalse((directory / 'agent.json').exists())

    def test_missing_agent_directory_is_drift(self):
        _, _, directory = self.create()
        shutil.rmtree(directory)
        error = self.call('ledger_verify', {}, 3)
        self.assertEqual(error['code'], 'hash_mismatch')
        for name in layout.PROJECTION_FILES:
            self.assertIn(name + ': projection_drift: missing', error['detail'])
        self.assertFalse(directory.exists())

    def test_exact_create_retry_preserves_all_file_bytes_and_metadata(self):
        args, result, _ = self.create()
        before = self.inventory()
        self.assertEqual(self.call('agent_create', args), result)
        self.assertEqual(self.inventory(), before)
        events = (self.home / 'ledger/main/events.jsonl').read_text().splitlines()
        self.assertEqual(len(events), 1)
        self.assertEqual(json.loads(events[0])['op_id'], args['op_id'])
        self.verify()

    def test_unicode_language_uses_hash_and_preserves_wire_language(self):
        language = '日本語'
        _, result, directory = self.create(language=language)
        self.assertEqual(directory.parent.name, 'lang-' + sha256(language.encode()).hexdigest())
        self.assertEqual(result['untrusted']['record']['language'], language)
        self.verify()

    def test_executable_regular_skill_and_agent_files_verify(self):
        _, _, directory = self.create()
        # Deliberately opaque local skill data: no skill publication is needed.
        skills = self.home / 'skills' / 'local-skill'
        skills.mkdir(parents=True)
        script = skills / 'runner.sh'
        script.write_bytes(b'#!/bin/sh\nexit 0\n')
        script.chmod(0o755)
        (directory / 'agent.json').chmod(0o700)
        self.verify()

    def test_hardlinks_symlinks_and_nonregular_skill_files_are_refused(self):
        self.create()
        skills = self.home / 'skills'
        skills.mkdir()
        source = self.home / 'source.txt'
        source.write_bytes(b'fixture')
        target = skills / 'unsafe'
        for kind in ('hardlink', 'symlink', 'fifo'):
            with self.subTest(kind=kind):
                if kind == 'hardlink':
                    os.link(source, target)
                elif kind == 'symlink':
                    target.symlink_to(source)
                else:
                    os.mkfifo(target)
                error = self.call('ledger_verify', {}, 3)
                self.assertEqual(error['code'], 'bad_args')
                target.unlink()

    def test_export_rebuilds_four_files_in_canonical_unicode_home(self):
        _, _, directory = self.create(language='日本語')
        expected = {name: (directory / name).read_bytes() for name in layout.PROJECTION_FILES}
        (directory / 'agent.json').write_bytes(b'{}\n')
        (directory / 'scorecard.json').unlink()
        result = self.call('ledger_export', {'out': 'exports/rebuilt'})['untrusted']
        exported = self.home / result['out'] / directory.relative_to(self.home)
        for name, raw in expected.items():
            self.assertEqual((exported / name).read_bytes(), raw)
        self.assertEqual((directory / 'agent.json').read_bytes(), b'{}\n')
        self.assertFalse((directory / 'scorecard.json').exists())


class PureLayoutTests(unittest.TestCase):
    def test_paths_are_pure_and_language_mapping_is_exact(self):
        with mock.patch('os.open', side_effect=AssertionError('layout performed I/O')):
            for language in ('python', 'C++', '../escape', '日本語'):
                expected = language if language == 'python' else 'lang-' + sha256(language.encode()).hexdigest()
                self.assertEqual(layout.language_component(language), expected)
                directory = layout.agent_dir('home', workflow='review', language=language, agent_id='agent-one')
                self.assertEqual(directory, Path('home/agents/review') / expected / 'agent-one')
                self.assertEqual(layout.memory_dir('home', workflow='review', language=language,
                                                   agent_id='agent-one'), directory / 'memory')
        self.assertEqual(layout.PROJECTION_FILES, ('agent.json', 'CONSTITUTION.md', 'BRIEF_HEAD.md', 'scorecard.json'))
