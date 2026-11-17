"""Regression witnesses for context-bound admission and original request identity."""
from copy import deepcopy
from functools import partial
from unittest import mock

from lineage.core import journal
from lineage.domain import agents

from .helpers import ACTOR, OracleCase, seam


class ReviewAdmissionTests(OracleCase):
    def test_real_context_bound_validator_accepts_valid_direct_birth(self):
        # A-U18: a positive control proves forged births reach semantic admission,
        # rather than passing rejection assertions on an unavailable context.
        self.parents()
        self.put(self.unit())
        payload = self.valid_forge_template()
        owner = mock.Mock(wraps=self.reg.validators['agent.born'])
        validators = dict(self.reg.validators)
        validators['agent.born'] = partial(owner, ctx=self.context)

        def prepare(history, draft):
            candidate = deepcopy(payload)
            candidate['record']['born']['event_id'] = draft['id']
            return candidate

        event = journal.transact(self.home, agent=ACTOR, op_id='review-valid-direct',
                                 kind='agent.born', payload=self.forge_request,
                                 validators=validators, prepare=prepare)
        self.assertEqual(owner.call_count, 1)
        self.assertIs(owner.call_args.kwargs['ctx'], self.context)
        agents.refresh_projections('child-agent', ctx=self.context)
        data = {key: deepcopy(event['payload'][key]) for key in
                ('record', 'inherited_units', 'rejected_units')}
        data['commit'] = {'event_ids': [event['id']], 'head': event['lamport'],
                          'sha256': event['sha256']}
        self.witness(data)

    def test_direct_birth_cannot_change_original_parent_order(self):
        # A-U18: caller order is meaningful even when composition is symmetric.
        self.parents()
        payload = self.valid_forge_template()
        payload['record']['parents'].reverse()
        self.forge(payload, 'not_inheritable')

    def test_omitted_display_name_is_resolved_from_locked_parent(self):
        # A-U18: an unnamed request cannot authorize an arbitrary prepared name.
        self.parents()
        payload = self.valid_forge_template()
        payload['record']['display_name'] = 'Injected child name'
        self.forge(payload, 'not_inheritable')

    def test_projection_retries_after_proven_concurrent_head_advance(self):
        # A-U18: reproduce a durable birth racing another append between the
        # projection snapshot and publication, without sleeps or process groups.
        self.parents()
        original = agents.materialize
        advanced = []

        def racing(agent_id, *, snapshot, ctx, _preserve_unchanged=False):
            if agent_id == 'child-agent' and not advanced:
                advanced.append(True)
                self.parent('projection-racer')
            return original(agent_id, snapshot=snapshot, ctx=ctx,
                            _preserve_unchanged=_preserve_unchanged)

        with seam(agents, 'materialize', racing):
            data = self.op()
        self.assertEqual(advanced, [True])
        self.witness(data)
        births = [event for event in self.history() if event['kind'] == 'agent.born'
                  and event['payload']['record']['agent_id'] == 'child-agent']
        self.assertEqual(len(births), 1)
        self.assertLess(data['commit']['head'], len(self.history()))
        self.assertEqual(self.op(), data)
