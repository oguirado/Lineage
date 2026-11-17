"""Real shared dispatch, CLI and MCP; no replacement transport implementations."""
from copy import deepcopy
import io
import json

from lineage.core import app, cli, mcp, schema
from tests.runs.support import RunCase, OWNER, RUN, OUTCOME, COST, canonical, CONTRACTS


class Transports(RunCase):
    def args(self, **updates):
        return {'run_id': RUN, 'outcome': deepcopy(OUTCOME), 'cost': deepcopy(COST),
                'agent': OWNER, 'op_id': 'close001', **updates}

    def cli_call(self, name, args):
        output, errors = io.StringIO(), io.StringIO()
        code = cli.main(['--home', str(self.f.home), 'call', name, '--json',
                         canonical(args).decode()], registry=self.f.registry,
                        stdout=output, stderr=errors, stdin=io.BytesIO())
        self.assertEqual(errors.getvalue(), '')
        self.assertEqual(output.getvalue().count('\n'), 1)
        return code, schema.strict_loads(output.getvalue())

    def rpc(self, args):
        request = {'jsonrpc': '2.0', 'id': 'oracle', 'method': 'tools/call',
                   'params': {'name': 'run_close', 'arguments': args}}
        output, errors = io.StringIO(), io.StringIO()
        code = mcp.main(context=self.f.context(), registry=self.f.registry,
            stdin=io.BytesIO(canonical(request) + b'\n'), stdout=output, stderr=errors)
        self.assertEqual(code, 0)
        self.assertEqual(errors.getvalue(), '')
        return schema.strict_loads(output.getvalue())

    def test_a36_dispatch_missing_memory_has_one_error_and_no_append(self):
        self.f.open()
        before = self.f.raw()
        result = app.dispatch('run_close', self.args(), context=self.f.context(), registry=self.f.registry)
        self.assertEqual(result.payload.get('code'), 'memory_required')
        self.assertEqual(result.exit_code, 3)
        self.assertNotIn('untrusted', result.payload)
        self.assertEqual(self.f.raw(), before)

    def test_a36_dispatch_success_wraps_once(self):
        self.f.open()
        self.f.witness()
        result = app.dispatch('run_close', self.args(), context=self.f.context(), registry=self.f.registry)
        self.assertEqual(set(result.payload), {'untrusted'})
        self.assertEqual(set(result.payload['untrusted']), {'run', 'commit'})
        self.assertEqual(result.exit_code, 0)

    def test_a36_cli_memory_required_exits_three(self):
        self.f.open()
        before = self.f.raw()
        code, value = self.cli_call('run_close', self.args())
        self.assertEqual(code, 3)
        self.assertEqual(value['code'], 'memory_required')
        self.assertEqual(self.f.raw(), before)

    def test_a36_cli_failed_task_can_close_with_exit_zero(self):
        from tests.runs.support import outcome
        requested = outcome('red')
        self.f.open()
        self.f.witness(requested)
        code, value = self.cli_call('run_close', self.args(outcome=requested))
        self.assertEqual(code, 0)
        self.assertEqual(value['untrusted']['run']['outcome'], requested)

    def test_a36_mcp_domain_error_is_normal_rpc_result(self):
        self.f.open()
        response = self.rpc(self.args())
        self.assertNotIn('error', response)
        result = response['result']
        self.assertTrue(result['isError'])
        self.assertEqual(schema.strict_loads(result['content'][0]['text'])['code'], 'memory_required')

    def test_a36_mcp_schema_error_is_rpc_minus_32602(self):
        self.f.open()
        response = self.rpc(self.args(gate={'passed': True}))
        self.assertEqual(response['error']['code'], -32602)
        self.assertNotIn('result', response)

    def test_a36_mcp_success_and_dispatch_have_identical_replay(self):
        self.f.open()
        self.f.witness()
        expected = app.dispatch('run_close', self.args(), context=self.f.context(), registry=self.f.registry)
        before = self.f.raw()
        response = self.rpc(self.args())
        self.assertFalse(response['result']['isError'])
        inner = schema.strict_loads(response['result']['content'][0]['text'])
        self.assertEqual(inner, expected.payload)
        self.assertEqual(self.f.raw(), before)

    def test_a06_dispatch_cannot_preserve_outer_operator_authority(self):
        self.f.open()
        result = app.dispatch('run_close', self.args(agent='operator'),
                     context=self.f.context('operator', authority='operator'), registry=self.f.registry)
        self.assertEqual(result.payload.get('code'), 'bad_args')
        self.assertEqual(result.payload.get('detail'), 'actor_mismatch')

    def test_a02_cli_duplicate_keys_at_depth_refused_before_append(self):
        # Positive control prevents an absent handler being mistaken for schema enforcement.
        self.f.open()
        before = self.f.raw()
        output = io.StringIO()
        raw = '{"run_id":"run_0001","outcome":{"verdict":"green","verdict":"red"}}'
        code = cli.main(['--home', str(self.f.home), 'call', 'run_close', '--json', raw],
            registry=self.f.registry, stdout=output, stderr=io.StringIO(), stdin=io.BytesIO())
        self.assertEqual(code, 2)
        self.assertEqual(schema.strict_loads(output.getvalue())['code'], 'bad_args')
        self.assertEqual(self.f.raw(), before)

    def test_a02_mcp_invalid_utf8_refused_without_append(self):
        self.f.open()
        before = self.f.raw()
        output = io.StringIO()
        mcp.main(context=self.f.context(), registry=self.f.registry,
            stdin=io.BytesIO(b'{"jsonrpc":"2.0","id":1,"method":"\xff"}\n'),
            stdout=output, stderr=io.StringIO())
        self.assertEqual(schema.strict_loads(output.getvalue())['error']['code'], -32700)
        self.assertEqual(self.f.raw(), before)
