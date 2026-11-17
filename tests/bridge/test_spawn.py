"""A4/A9/A26: prepublication mode, actor and nested family refusals."""
from dataclasses import replace

from lineage.bridge import openfresnel as bridge
from tests.bridge._support import AGENT, OP_ID, BridgeCase, FAMILY_LIMIT, canonical, family, call_envelope, install_cases


class SpawnAdmissionOracle(BridgeCase):
    def test_a09_probe_context_actor_mismatch_is_prepublication_bad_args(self):
        command = self.command(commands_dir=str(self.channel))
        ctx = replace(self.ctx, actor='another')
        self.no_effect_error('bad_args', bridge.probe, commands_dir=str(self.channel), command=command, ctx=ctx)

    def test_a09_probe_context_operation_mismatch_is_prepublication_bad_args(self):
        command = self.command(commands_dir=str(self.channel))
        ctx = replace(self.ctx, op_id='another')
        self.no_effect_error('bad_args', bridge.probe, commands_dir=str(self.channel), command=command, ctx=ctx)

    def test_a09_spawn_context_actor_mismatch_is_prepublication_bad_args(self):
        command = self.command('openfresnel_spawn', mode='drain', endpoint='receiver', commands_dir=str(self.channel))
        ctx = replace(self.ctx, actor='another')
        self.no_effect_error('bad_args', bridge.spawn, 'drain', endpoint='receiver',
                             commands_dir=str(self.channel), command=command, ctx=ctx)

    def test_a26_nested_envelope_cap_counts_canonical_utf8_bytes(self):
        """Unicode characters cannot be counted as one byte."""
        envelope = call_envelope('skill_publish', {'skill_id': 'skill-one', 'files': [{'path': 'SKILL.md', 'content': '\u00e9' * 33000}]})
        self.assertGreater(len(canonical(envelope)), FAMILY_LIMIT)
        command = self.command('openfresnel_spawn', mode='json', envelope=envelope, commands_dir=str(self.channel))
        self.no_effect_error('bad_args', bridge.spawn, 'json', envelope=envelope,
                             commands_dir=str(self.channel), command=command, ctx=self.ctx)


def bad_mode(self, options):
    mode = options.pop('mode')
    command = self.command('openfresnel_spawn', mode=mode, commands_dir=str(self.channel), **options)
    self.no_effect_error('bad_args', bridge.spawn, mode, **options,
                         commands_dir=str(self.channel), command=command, ctx=self.ctx)


install_cases(SpawnAdmissionOracle, 'test_a26_mode_', {
    'json_missing_envelope': {'mode': 'json'},
    'json_endpoint_only': {'mode': 'json', 'endpoint': 'receiver'},
    'json_endpoint_and_envelope': {'mode': 'json', 'endpoint': 'receiver', 'envelope': family()},
    'drain_missing_endpoint': {'mode': 'drain'},
    'drain_envelope': {'mode': 'drain', 'endpoint': 'receiver', 'envelope': family()},
    'drain_empty_endpoint': {'mode': 'drain', 'endpoint': ''},
    'drain_endpoint_metacharacters': {'mode': 'drain', 'endpoint': 'x;echo'},
    'drain_endpoint_newline': {'mode': 'drain', 'endpoint': 'receiver\n'},
    'drain_endpoint_overlong': {'mode': 'drain', 'endpoint': 'x' * 65},
    'drain_endpoint_nonascii': {'mode': 'drain', 'endpoint': '\u00e9'},
    'unknown': {'mode': 'shell'},
    'null': {'mode': None},
    'boolean': {'mode': True},
}, bad_mode)


def bad_envelope(self, envelope):
    command = self.command('openfresnel_spawn', mode='json', envelope=envelope, commands_dir=str(self.channel))
    self.no_effect_error('bad_args', bridge.spawn, 'json', envelope=envelope,
                         commands_dir=str(self.channel), command=command, ctx=self.ctx)


install_cases(SpawnAdmissionOracle, 'test_a26_envelope_', {
    'reserved_id': family(id='invalid0'),
    'unknown_top_level': family(unrecognized=True),
    'unknown_capability_payload': family(payload={'unknown': True}),
    'after_on_capabilities': family(after=0),
    'wrong_schema': family(schema='lineage.family/2'),
    'missing_actor': {k: v for k, v in family().items() if k != 'agent'},
    'actor_smuggling': call_envelope(args={'agent': 'operator'}),
    'op_id_smuggling': call_envelope(args={'op_id': 'forged'}),
    'unknown_call_payload': family(kind='call', payload={'tool': 'agent_get', 'args': {}, 'extra': True}),
    'unknown_nested_argument': call_envelope('agent_get', {'agent_id': 'agent-one', 'unknown': True}),
    'array': [], 'null': None, 'surrogate': family(source='\ud800'),
}, bad_envelope)


class AdmissionMutationOracle(BridgeCase):
    def test_a34_invalid_mode_success_mutant_is_detected(self):
        """First prove real refusal, then require the same assertion to kill a mutant."""
        from unittest import mock
        command = self.command('openfresnel_spawn', mode='drain', commands_dir=str(self.channel))
        args = {'commands_dir': str(self.channel), 'command': command, 'ctx': self.ctx}
        self.no_effect_error('bad_args', bridge.spawn, 'drain', **args)
        # This isolated double bypasses mode admission only at the public seam.
        with mock.patch.object(bridge, 'spawn', return_value={'state': 'launched'}):
            with self.assertRaises(AssertionError):
                self.no_effect_error('bad_args', bridge.spawn, 'drain', **args)
