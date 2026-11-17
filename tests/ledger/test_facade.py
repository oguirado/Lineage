"""A-INT1: native and K0 seams coexist in fresh interpreter import orders."""
from pathlib import Path
import os
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]

_SCRIPT = r"""
import importlib
import inspect
import json
from pathlib import Path
import tempfile
from dataclasses import fields
from lineage.core import app, journal, registry

native_tool = registry.ToolSpec
native_init = inspect.signature(native_tool)
native_load = registry.load
native_signatures = {name: inspect.signature(getattr(journal, name))
                     for name in ('snapshot', 'transact', 'verify')}
dispatch_signature = inspect.signature(app.dispatch)
modules = json.loads(__import__('sys').argv[1])
for name in modules:
    importlib.import_module(name)
if not modules:
    native_load()
from lineage.domain import memory
memory._install()
installed = (registry.ToolSpec, registry.load, app.dispatch, journal.snapshot,
             journal.transact, journal.verify)
memory._install()
assert installed == (registry.ToolSpec, registry.load, app.dispatch, journal.snapshot,
                     journal.transact, journal.verify)
assert registry.ToolSpec is native_tool
assert inspect.signature(registry.ToolSpec) == native_init
assert tuple(field.name for field in fields(registry.ToolSpec)) == (
    'name', 'description', 'input_schema', 'handler', 'mutating')
assert inspect.signature(app.dispatch) == dispatch_signature
for name, signature in native_signatures.items():
    assert inspect.signature(getattr(journal, name)) == signature
loaded = native_load()
assert {'memory_put', 'memory_get', 'memory_history', 'ledger_events',
        'ledger_export', 'ledger_verify', 'scorecard_get', 'skill_publish'} <= set(loaded.tools)
assert all(type(spec) is native_tool for spec in loaded.tools.values())
assert registry.load().tools.keys() == loaded.tools.keys()

with tempfile.TemporaryDirectory() as temporary:
    home = Path(temporary)
    event = journal.transact(home, agent='tester', op_id='native-event',
        kind='fixture.event', payload={'unchanged': None},
        validators={'fixture.event': lambda history, event: None})
    assert type(event) is dict and event['payload'] == {'unchanged': None}
    assert journal.snapshot(home) == journal.snapshot(home=home) == (event,)
    report = journal.verify(home)
    assert report['ok'] is True and 'valid' not in report
    ctx = registry.Context(registry.Services(home, Path.cwd(), loaded), 'tester')
    snapshot = journal.snapshot(ctx=ctx)
    assert isinstance(snapshot, registry.Snapshot) and snapshot.events == (event,)
    assert journal.verify(ctx=ctx)['valid'] is True
    context = app.create_context(home, registry=loaded)
    native_result = app.dispatch('ledger_events', {}, context=context, registry=loaded)
    assert isinstance(native_result, app.DispatchResult) and native_result.exit_code == 0
    k0_result = app.dispatch('ledger_events', {}, ctx=ctx)
    assert type(k0_result) is dict and k0_result == native_result.payload
    assert set(k0_result) == {'untrusted'}
    assert k0_result['untrusted']['events'] == [event]
    # Native handler policy and schemas still run for ctx-style calls.
    invalid = app.dispatch('ledger_events', {'after': True}, ctx=ctx)
    assert invalid['ok'] is False and invalid['code'] == 'bad_args'
    assert 'untrusted' not in invalid
    assert app.dispatch('skill_list', {}, ctx=ctx) == {'untrusted': {'skills': []}}
    assert app.dispatch('absent', {}, ctx=ctx) == {'ok': False, 'code': 'bad_args'}
    from lineage.core.errors import LineageError
    try:
        journal.transact(home, agent='tester', op_id='native-event',
            kind='fixture.event', payload={'changed': True},
            validators={'fixture.event': lambda history, event: None})
    except LineageError as exc:
        assert exc.code == 'bad_op'
    else:
        raise AssertionError('native replay conflict bypassed')
    assert journal.snapshot(home) == (event,)
print('native/K0 assertions passed')
"""


class FacadeTests(unittest.TestCase):
    def check_order(self, modules):
        import json
        completed = subprocess.run(
            [sys.executable, '-B', '-c', _SCRIPT, json.dumps(modules)],
            cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
            capture_output=True, text=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, 'native/K0 assertions passed\n')
        self.assertEqual(completed.stderr, '')

    def test_memory_first_keeps_native_apis(self):
        self.check_order(['lineage.ext.memory', 'lineage.ext.ledger',
                          'lineage.serve.http', 'lineage.ext.skills'])

    def test_ledger_first_keeps_native_apis(self):
        self.check_order(['lineage.ext.ledger', 'lineage.ext.skills',
                          'lineage.ext.memory', 'lineage.serve.http'])

    def test_http_first_keeps_native_apis(self):
        self.check_order(['lineage.serve.http', 'lineage.ext.skills',
                          'lineage.ext.memory', 'lineage.ext.ledger'])

    def test_native_discovery_triggers_idempotent_install(self):
        # Discovery's original function must finish even if peers install K0
        # while it is iterating extensions, without pre-importing memory.
        self.check_order([])
