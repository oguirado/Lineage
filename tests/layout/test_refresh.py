"""Owner publication refreshes record and telemetry after committed events."""
import json
import os
import subprocess
import sys
from lineage.core import journal
from lineage.domain import agents, scorecard
from tests.agents import OracleCase, ROOT, SEAT, unit


class RefreshTests(OracleCase):
    def run(self, result=None):
        # Other suites intentionally reload the schema provider. Like ledger
        # integration oracles, exercise the installed APIs in a fresh process.
        if os.environ.get('LINEAGE_LAYOUT_TEST_PROCESS') == '1':
            return super().run(result)
        result = self.defaultTestResult() if result is None else result
        result.startTest(self)
        try:
            completed = subprocess.run(
                [sys.executable, '-B', '-m', 'unittest', self.id()], cwd=ROOT,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', LINEAGE_LAYOUT_TEST_PROCESS='1'),
                capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        except AssertionError:
            result.addFailure(self, sys.exc_info())
        except Exception:
            result.addError(self, sys.exc_info())
        else:
            result.addSuccess(self)
        finally:
            result.stopTest(self)
        return result

    def test_refresh_updates_record_brief_memory_and_scorecard_from_current_prefix(self):
        self.seed()
        self.materialize()
        directory = self.projection_dir()
        old_record = (directory / 'agent.json').read_bytes()
        self.append_fixture('memory.put', {'agent_id': 'agent-one', 'unit': unit()})
        current = agents.get('agent-one', ctx=self.ctx)['record']
        run = {'schema': 'lineage.run/v1', 'run_id': 'run_0001', 'agent_id': 'agent-one',
               'agent_version': current['agent_version'], 'ts_open': 1, 'ts_close': 2,
               'seat': SEAT, 'task': {'id': 'task_001', 'kind': 'develop', 'language': 'python'},
               'outcome': {'verdict': 'green', 'repair_loops': 0,
                           'findings': {'confirmed': 0, 'refuted': 0}},
               'cost': dict.fromkeys(('tokens_in', 'tokens_out', 'tokens_cache',
                                     'duration_ms', 'cost_micro_usd')),
               'memory': {'unit_ids': ['episode01'], 'levels': [3], 'gate_passed': True},
               'evidence': [], 'parents_context': [], 'memory_arm': 'own'}
        # A-LAY1-T: a close needs its open (the runs fold, U13, rejects an orphan close).
        self.append_fixture('run.open', {'run_id': 'run_0001', 'agent_id': 'agent-one', 'seat': SEAT,
                                         'task': run['task'], 'agent_version': current['agent_version']})
        self.append_fixture('run.close', {'record': run, 'memory_receipts': [],
                                         'gate': {'passed': True, 'checks': [{'id': 'memory', 'passed': True}]}})
        paths = agents.refresh_projections('agent-one', ctx=self.ctx)
        self.assertTrue(paths)
        self.assertNotEqual((directory / 'agent.json').read_bytes(), old_record)
        self.assertEqual(json.loads((directory / 'agent.json').read_bytes()), current)
        self.assertEqual((directory / 'scorecard.json').read_bytes(),
                         scorecard.projection_bytes(journal.snapshot(self.home), agent_id='agent-one'))
        self.assertEqual(json.loads((directory / 'scorecard.json').read_bytes())['groups'][0]['runs'], 1)
        self.assertIn(b'lesson01', (directory / 'BRIEF_HEAD.md').read_bytes())
        self.assertTrue((directory / 'memory/CURRENT').is_file())
        self.assertTrue(journal.verify(self.home)['ok'])
        before = {p: (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns) for p in paths}
        self.assertEqual(agents.refresh_projections('agent-one', ctx=self.ctx), paths)
        self.assertEqual({p: (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns) for p in paths}, before)
