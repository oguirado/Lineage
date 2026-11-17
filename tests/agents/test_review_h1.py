"""Review h1 regressions for unchanged operation identity and U11 admission."""
from copy import deepcopy
from hashlib import sha256
from unittest import mock

from lineage.core import app, jsonlane
from lineage.core.errors import LineageError
from lineage.domain.memory import entry

from . import OracleCase, agents, canonical, unit


class ReviewH1Tests(OracleCase):
    def test_caller_operation_id_is_journaled_unchanged(self):
        for index, identity in enumerate(("A", "root:child/path.v1_2-3", "Z" * 128)):
            with self.subTest(op_id=identity):
                args = self.arguments(agent_id=f"review-{index}")
                command = self.command(args, op_id=identity)
                created = self.create(command=command, agent_id=args["agent_id"])
                event = self.assert_chain()[-1]
                self.assertEqual(event["op_id"], identity)
                self.assertEqual(event["agent"], command.agent)
                self.assertEqual(created.value["commit"]["event_ids"], [event["id"]])
                before = self.ledger()
                retried = self.create(command=command, agent_id=args["agent_id"])
                self.assertEqual(canonical(retried.value), canonical(created.value))
                self.assertEqual(self.ledger(), before)

    def test_json_lane_creation_and_dispatch_replay_share_commit(self):
        config = {"endpoint": "review-target", "sources": ["review-source"],
                  "tools": ["agent_create"]}
        args = self.arguments()
        envelope = {"schema": "lineage.family/1", "id": "review0001",
                    "source": "review-source", "target": "review-target",
                    "kind": "call", "agent": "system",
                    "payload": {"tool": "agent_create", "args": deepcopy(args)}}
        self.assertEqual(jsonlane.dispatch(envelope, config, ctx=self.ctx),
                         {"ok": False, "code": "bad_args"})
        self.assertEqual(self.ledger(), b"")
        self.configure_lane(config)
        result = jsonlane.dispatch(envelope, config, ctx=self.ctx)
        self.assertEqual(set(result), {"untrusted"}, result)
        created = result["untrusted"]
        event = self.assert_chain()[0]
        identity = "lin-" + sha256("\0".join(envelope[key] for key in
                                  ("source", "target", "id")).encode()).hexdigest()[:44]
        self.assertEqual(event["op_id"], identity)
        self.assertEqual(created["record"], event["payload"]["record"])
        self.assertEqual(created["commit"], {"event_ids": [event["id"]],
                         "head": event["lamport"], "sha256": event["sha256"]})
        self.append_fixture("memory.put", {"agent_id": "agent-one", "unit": unit()})
        before = self.ledger()
        dispatched = app.dispatch("agent_create", {**args, "agent": "system", "op_id": identity},
                                  context=self.ctx, registry=self.reg)
        self.assertEqual(dispatched.exit_code, 0, dispatched.payload)
        self.assertEqual(dispatched.payload, result)
        self.assertEqual(jsonlane.dispatch(envelope, config, ctx=self.ctx), result)
        self.assertEqual(self.ledger(), before)
        self.assertEqual(len(self.assert_chain()), 2)

    def test_u11_counter_refusal_is_not_bypassed_before_birth(self):
        args = self.arguments()
        refusal = LineageError("memory_debt", "token counter unavailable or invalid; cuts unavailable")
        with mock.patch.object(entry, "build", side_effect=refusal) as checked:
            self.reject("memory_debt", agents.create, **args, command=self.command(args), ctx=self.ctx)
        self.assertTrue(checked.called)
        self.assertIsNone(checked.call_args.kwargs["token_count"])
        self.assertEqual(self.ledger(), b"")
        self.assertFalse(self.projection_dir().exists())
