"""Public-protocol discovery probes; no domain substitutes or source writes."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
LEDGER_TOOLS = frozenset({
    "ledger_events", "ledger_export", "ledger_verify", "scorecard_get",
})


class DiscoveryCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="lineage-ledger-oracle-")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        environment = mock.patch.dict(os.environ, {"LINEAGE_HOME": str(self.home)})
        environment.start()
        self.addCleanup(environment.stop)

    def mcp_discovery(self):
        request = {"jsonrpc": "2.0", "id": "ledger-oracle",
                   "method": "tools/list", "params": {}}
        # A-U14: use the installed MCP delegate, which supplies context/registry.
        # Fresh processes isolate fixtures from other suites' schema-class reloads.
        status, stdout, stderr = self._entrypoint(
            "mcp", (json.dumps(request) + "\n").encode("utf-8"))
        self.assertEqual(status, 0)
        self.assertEqual(stderr.getvalue(), "")
        lines = stdout.getvalue().splitlines()
        self.assertEqual(len(lines), 1, "MCP must emit one discovery response")
        response = json.loads(lines[0])
        self.assertEqual(set(response), {"jsonrpc", "id", "result"})
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], request["id"])
        self.assertEqual(set(response["result"]), {"tools"})
        descriptors = response["result"]["tools"]
        self.assertIsInstance(descriptors, list)
        for descriptor in descriptors:
            self.assertIsInstance(descriptor, dict)
            self.assertIsInstance(descriptor.get("name"), str)
        return descriptors

    def require_tool(self, name):
        descriptors = self.mcp_discovery()
        names = [descriptor["name"] for descriptor in descriptors]
        self.assertIn(name, names,
                      "Missing U14 behavior: MCP tools/list must discover " + name)
        self.assertEqual(names.count(name), 1, "Tool names must be unique")
        descriptor = next(item for item in descriptors if item["name"] == name)
        self.assertEqual(set(descriptor) - {"annotations"}, {"name", "description", "inputSchema"})  # A-OPC1: optional MCP annotations
        self.assertIsInstance(descriptor["description"], str)
        self.assertTrue(descriptor["description"])
        self.assertEqual(descriptor["inputSchema"].get("type"), "object")
        self.assertIs(descriptor["inputSchema"].get("additionalProperties"), False)
        return descriptor

    def cli_discovery(self):
        # A-U14: exercise the actual CLI with the same isolated runtime fixture.
        status, stdout, stderr = self._entrypoint("tools")
        self.assertEqual(status, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(len(stdout.getvalue().splitlines()), 1)
        # A-U14: integrated CLI tools wraps the descriptor array in {"tools": ...}.
        # Assert the exact transport shape before exposing the same array to callers.
        payload = json.loads(stdout.getvalue())
        self.assertEqual(set(payload), {"tools"})
        self.assertIsInstance(payload["tools"], list)
        return payload["tools"]

    def _entrypoint(self, verb, raw=b""):
        # A-U14: public entrypoints own U04 argument plumbing in a fresh interpreter.
        completed = subprocess.run(
            [sys.executable, "-m", "lineage", "--home", str(self.home), verb],
            input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=ROOT, timeout=10, check=False)
        return (completed.returncode, io.StringIO(completed.stdout.decode("utf-8")),
                io.StringIO(completed.stderr.decode("utf-8")))


def contract_schemas(name):
    """Read the frozen input/output oracle independently of tool descriptors."""
    import re
    section = (ROOT / 'docs/CONTRACT.md').read_text().split('### `' + name + '`', 1)[1]
    section = section.split('\n### ', 1)[0]
    return [json.loads(block) for block in re.findall(r'```json\n(.*?)```', section, re.S)]


class LedgerCase(unittest.TestCase):
    def run(self, result=None):
        # Core schema tests deliberately reload their provider. Exercise the
        # public registry/dispatch in a fresh interpreter, as discovery does,
        # without patching production schemas, callbacks or error classes.
        if os.environ.get('LINEAGE_LEDGER_TEST_PROCESS') == '1':
            return super().run(result)
        result = self.defaultTestResult() if result is None else result
        result.startTest(self)
        try:
            completed = subprocess.run(
                [sys.executable, '-B', '-m', 'unittest', self.id()], cwd=ROOT,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                         LINEAGE_LEDGER_TEST_PROCESS='1'),
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

    def setUp(self):
        from lineage.core import app, registry
        self.registry = registry.load()
        temporary = tempfile.TemporaryDirectory(prefix='.runtime-', dir=Path(__file__).parent)
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.context = app.create_context(self.home, registry=self.registry)
        self.sequence = 0
        authority = self.home / 'ledger/main/events.jsonl'
        authority.parent.mkdir(parents=True)
        authority.with_name('events.lock').write_bytes(b'')
        authority.write_bytes(b'')

    def dispatch(self, name, args):
        from lineage.core import app
        return app.dispatch(name, args, context=self.context, registry=self.registry)

    def data(self, name, args):
        result = self.dispatch(name, args)
        self.assertEqual(result.exit_code, 0, result.payload)
        self.assertEqual(set(result.payload), {'untrusted'})
        return result.payload['untrusted']

    def cli(self, name, args, code=0):
        completed = subprocess.run(
            [sys.executable, '-B', '-m', 'lineage', '--home', str(self.home),
             'call', name, '--json', json.dumps(args)], cwd=ROOT,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
            capture_output=True, text=True, timeout=10, check=False)
        self.assertEqual(completed.returncode, code, completed.stdout + completed.stderr)
        self.assertEqual(completed.stderr, '')
        self.assertEqual(len(completed.stdout.splitlines()), 1)
        return json.loads(completed.stdout)

    def check_result(self, name, value):
        from lineage.core.schema import SchemaStore, validate
        store = SchemaStore(ROOT / 'schemas')
        validate(value, contract_schemas(name)[1], store=store)

    def append(self, kind='run.beat', *, actor='agent-one', payload=None):
        from lineage.core import journal
        self.sequence += 1
        if payload is None:
            payload = {'run_id': 'run_0001', 'agent_id': actor, 'progress': 'working'}
        return journal.transact(
            self.home, agent=actor, op_id='fixture_%08d' % self.sequence,
            kind=kind, payload=payload, validators={kind: lambda history, event: None})

    def birth(self, agent_id='agent-one'):
        record = {'schema': 'lineage.agent/v1', 'agent_id': agent_id,
                  'display_name': agent_id, 'workflow': 'develop', 'language': 'python',
                  'allowed_seats': [{'model': 'fixture', 'effort': 'custom_effort', 'mode': 'headless'}],
                  'references': [{'id': ref, 'sha256': 'a' * 64}
                                 for ref in ('gold_s1', 'memory_v21')],
                  'constitution_sha256': 'b' * 64, 'skills': [], 'memory_gen': 0,
                  'brief_head_sha256': 'c' * 64, 'agent_version': 'd' * 64,
                  'generation': 0, 'parents': [],
                  'born': {'op': 'genesis', 'event_id': 'e-0000000000000001'}, 'status': 'draft'}
        return self.append('agent.born', actor='creator', payload={
            'record': record, 'inherited_units': [], 'rejected_units': [],
            'constitution': {'text': 'fixture\n', 'overlays': [], 'rule_ids': []}})

    def close(self, *, agent_id='agent-one', arm='own', seat=None,
              cost=None, verdict='green'):
        record = {'schema': 'lineage.run/v1', 'run_id': 'run_%08d' % (self.sequence + 1),
                  'ts_open': 1, 'ts_close': 2, 'agent_id': agent_id,
                  'agent_version': 'd' * 64,
                  'seat': seat or {'model': 'fixture', 'effort': 'custom_effort', 'mode': 'headless'},
                  'task': {'id': 'task_001', 'kind': 'develop', 'language': 'python'},
                  'outcome': {'verdict': verdict, 'repair_loops': 0,
                              'findings': {'confirmed': 0, 'refuted': 0}},
                  'cost': dict.fromkeys(['tokens_in', 'tokens_out', 'tokens_cache',
                                         'duration_ms', 'cost_micro_usd']),
                  'memory': {'unit_ids': ['unit_001'], 'levels': [3], 'gate_passed': True},
                  'evidence': [], 'parents_context': [], 'memory_arm': arm}
        record['cost'].update(cost or {})
        from lineage.core.schema import SchemaStore, validate
        store = SchemaStore(ROOT / 'schemas')
        validate(record, store.load('run.schema.json'), store=store)
        return self.append('run.close', actor=agent_id, payload={
            'record': record, 'memory_receipts': [],
            'gate': {'passed': True, 'checks': [{'id': 'memory', 'passed': True}]}})
