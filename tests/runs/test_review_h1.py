"""Regression checks for h1 argument classification and retained operation IDs."""
# A-U13: Add carrier and restart regressions without changing frozen assertions.
from copy import deepcopy
import io

from lineage.core import app, cli, mcp, schema
from lineage.domain import runs
from tests.runs.support import (Fixture, RunCase, OWNER, RUN, SEAT, TASK,
                               OUTCOME, COST, canonical)


class ReviewH1(RunCase):
    def partial_open(self):
        return {'agent': OWNER, 'op_id': 'partial-benchmark', 'run_id': RUN,
                'agent_id': OWNER, 'seat': deepcopy(SEAT),
                'task': {**TASK, 'bank_id': 'bank-one'},
                'parents_context': [], 'memory_arm': 'own'}

    def test_partial_benchmark_dispatch_is_request_error(self):
        before = self.f.raw()
        result = app.dispatch('run_open', self.partial_open(),
                              context=self.f.context(), registry=self.f.registry)
        self.assertEqual(result.payload, {'ok': False, 'code': 'bad_args'})
        self.assertEqual(result.failure, 'request')
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(self.f.raw(), before)

    def test_partial_benchmark_cli_exits_two(self):
        before = self.f.raw()
        output, errors = io.StringIO(), io.StringIO()
        result = cli.main(['--home', str(self.f.home), 'call', 'run_open',
                           '--json', canonical(self.partial_open()).decode()],
                          registry=self.f.registry, stdout=output, stderr=errors,
                          stdin=io.BytesIO())
        self.assertEqual(result, 2)
        self.assertEqual(schema.strict_loads(output.getvalue()),
                         {'ok': False, 'code': 'bad_args'})
        self.assertEqual(errors.getvalue(), '')
        self.assertEqual(self.f.raw(), before)

    def test_partial_benchmark_mcp_uses_invalid_params(self):
        before = self.f.raw()
        request = {'jsonrpc': '2.0', 'id': 'partial-benchmark', 'method': 'tools/call',
                   'params': {'name': 'run_open', 'arguments': self.partial_open()}}
        output, errors = io.StringIO(), io.StringIO()
        result = mcp.main(context=self.f.context(), registry=self.f.registry,
                          stdin=io.BytesIO(canonical(request) + b'\n'),
                          stdout=output, stderr=errors)
        response = schema.strict_loads(output.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(response['error']['code'], -32602)
        self.assertNotIn('result', response)
        self.assertEqual(errors.getvalue(), '')
        self.assertEqual(self.f.raw(), before)

    def test_restarted_fixture_uses_fresh_close_identity(self):
        self.f.open()
        self.f.witness()
        used = {(event['agent'], event['op_id']) for event in self.f.events()}
        reopened = Fixture(self.f.home, seed=False)
        reopened.services.id_factory = lambda: 'e-bbbbbbbbbbbbbbbb'
        command = reopened.command('run_close',
                    {'run_id': RUN, 'outcome': OUTCOME, 'cost': COST})
        self.assertNotIn((command.agent, command.op_id), used)
        self.closed(reopened.close(command=command))
        self.assertEqual(self.f.events()[-1]['op_id'], command.op_id)
        self.assertIsNotNone(runs.get(RUN, ctx=reopened.context())['closed'])

    def test_caller_operation_identity_is_journaled_unchanged(self):
        self.f.open()
        self.f.witness()
        command = self.f.command('run_close',
            {'run_id': RUN, 'outcome': OUTCOME, 'cost': COST},
            op_id='caller:/retained.13-001')
        result = self.f.close(command=command)
        self.closed(result)
        event = self.f.events()[-1]
        self.assertEqual(event['op_id'], 'caller:/retained.13-001')
        before = self.f.raw()
        self.assertEqual(self.f.close(command=command).value, result.value)
        self.assertEqual(self.f.raw(), before)
