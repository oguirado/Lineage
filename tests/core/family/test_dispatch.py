"""A5/A8/A10/A24/A25: shared registry, actor injection, and domain refusal."""

import copy

from tests.core.family import RuntimeCase, config, op_id, request, wire, ERRORS


class DispatchTests(RuntimeCase):
    def test_a5_capabilities_intersection(self):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        cfg = config(tools=["skill_list", "ledger_events"])
        expected = [d for d in self.app.list_tools(registry=self.registry) if d["name"] in cfg["tools"]]
        expected.sort(key=lambda d: d["name"])
        value = self.lane(request(), cfg)
        self.assertEqual(value, {"untrusted": {"protocol": "lineage.family/1",
            "kinds": ["capabilities", "events.read", "call"], "tools": expected, "health": "ready"}})
        self.assertEqual(self.extension.SEEN, [])

    def test_a5_empty_tool_intersection(self):
        result = self.lane(request(), config(tools=[]))
        self.assertEqual(result["untrusted"]["tools"], [])
        self.assertEqual(self.extension.SEEN, [])

    def test_a5_source_membership(self):
        self.assert_error(self.lane(request(), config(sources=[])), "bad_args")
        self.assertEqual(self.extension.SEEN, [])

    def test_a5_events_read_needs_grant(self):
        self.assert_error(self.lane(request("events.read"), config(tools=[])), "bad_args")
        self.assertEqual(self.extension.SEEN, [])

    def test_a5_call_ledger_needs_same_grant(self):
        value = request("call", payload={"tool": "ledger_events", "args": {}})
        self.assert_error(self.lane(value, config(tools=[])), "bad_args")
        self.assertEqual(self.extension.SEEN, [])

    def test_a5_unregistered_frozen_tool_does_not_execute(self):
        value = request("call", payload={"tool": "agent_list", "args": {}})
        self.assert_error(self.lane(value, config(tools=["agent_list"])), "bad_args")
        self.assertEqual(self.extension.SEEN, [])

    def test_a8_read_actor_defaults_authority_and_transport(self):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        value = request("call", agent="operator")
        self.assertEqual(self.lane(value), {"untrusted": {"skills": []}})
        args, ctx = self.extension.SEEN[-1]
        self.assertEqual(args, {"agent": "operator", "include_retired": False})
        self.assertEqual(ctx.actor, "operator")
        self.assertEqual(ctx.authority, "tool")
        self.assertEqual(ctx.transport, "json")
        self.assertIs(ctx.home, self.ctx.context.home)
        self.assertIs(ctx.validators, self.ctx.context.validators)
        self.assertIs(ctx.folds, self.ctx.context.folds)

    def test_a8_mutation_identity_and_expected_head(self):
        value = self.mutation()
        value["payload"]["args"]["expected_head"] = 0
        result = self.lane(value)
        args, ctx = self.extension.SEEN[-1]
        self.assertEqual(args, {**value["payload"]["args"], "agent": "alice", "op_id": op_id(value)})
        self.assertEqual((ctx.authority, ctx.transport, ctx.actor), ("tool", "json", "alice"))
        self.assert_witness(result, value)

    def test_a8_noncall_run_is_only_correlation(self):
        self.lane(request("events.read", run_id="run00001"))
        self.assertNotIn("run_id", self.extension.SEEN[-1][0])

    def test_a8_does_not_modify_callers_envelope(self):
        value = request("call")
        before = copy.deepcopy(value)
        self.lane(value)
        self.assertEqual(value, before)

    def test_a10_empty_cursor(self):
        self.assertEqual(self.lane(request("events.read")), {"untrusted": {
            "events": [], "next_after": 0, "head": 0, "has_more": False, "resync": False}})

    def test_a10_after_head_resync(self):
        self.assertEqual(self.lane(request("events.read", after=9007199254740991)), {"untrusted": {
            "events": [], "next_after": 0, "head": 0, "has_more": False, "resync": True}})

    def test_a10_filtered_cursor_parity(self):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        self.lane(self.mutation())
        args = {"after": 0, "limit": 1, "wait_ms": 0,
                "agent_id": "bobby", "kinds": ["skill.published"], "agent": "alice"}
        direct = self.app.dispatch("ledger_events", args, context=self.ctx.context, registry=self.registry).payload
        value = request("events.read", id="cursor001", payload={k: v for k, v in args.items() if k not in {"after", "agent"}})
        result = self.lane(value)
        self.assertEqual(wire(result), wire(direct))
        self.assertEqual(result["untrusted"]["next_after"], 1)
        self.assertEqual(result["untrusted"]["events"], [])

    def test_a10_wait_is_not_silently_zeroed(self):
        # The spy resolves immediately without a wall-clock wait.
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        from unittest.mock import patch
        cursor = {"events": [], "next_after": 0, "head": 0, "has_more": False, "resync": False}
        with patch.object(self.extension, "cursor", return_value=cursor) as read:
            self.lane(request("events.read", payload={"wait_ms": 30000}))
        self.assertEqual(read.call_args.kwargs["wait_ms"], 30000)

    def test_a10_page_boundaries(self):
        self.lane(self.mutation())
        value = self.mutation(id="request02")
        value["payload"]["args"]["skill_id"] = "other-skill"
        self.lane(value)
        first = self.lane(request("events.read", id="cursor001", payload={"limit": 1}))["untrusted"]
        second = self.lane(request("events.read", id="cursor002", after=first["next_after"],
                                   payload={"limit": 1}))["untrusted"]
        self.assertEqual((first["next_after"], first["head"], first["has_more"]), (1, 2, True))
        self.assertEqual((second["next_after"], second["head"], second["has_more"]), (2, 2, False))
        self.assertEqual([e["lamport"] for e in first["events"] + second["events"]], [1, 2])

    def test_a26_external_timeout_reuses_identity_without_journal(self):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        value = request("call", payload={"tool": "openfresnel_spawn", "args": {
            "mode": "drain", "endpoint": "Endpoint_1"}})
        cfg = config(tools=["openfresnel_spawn"])
        self.extension.FAIL = self.err.LineageError("timeout", "uncertain acknowledgement")
        self.assert_error(self.lane(value, cfg), "timeout")
        self.extension.FAIL = None
        result = self.lane(value, cfg)
        self.assertEqual(result["untrusted"]["state"], "launched")
        self.assertIsNone(result["untrusted"]["pane_id"])
        self.assertIsNone(result["untrusted"]["screen_id"])
        self.assertNotIn("commit", result["untrusted"])
        self.assertEqual(self.journal.snapshot(self.home), ())
        self.assertEqual([args["op_id"] for args, _ in self.extension.SEEN], [op_id(value)] * 2)
        self.assertTrue(all(ctx.transport == "json" and ctx.authority == "tool"
                            for _, ctx in self.extension.SEEN))

    def test_a24_validator_refusal_is_transactional(self):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        self.extension.REJECT = self.err.LineageError("hash_mismatch", "rejected by validator")
        result = self.lane(self.mutation())
        self.assert_error(result, "hash_mismatch")
        self.assertEqual(self.journal.snapshot(self.home), ())

    def test_a25_unexpected_exception_is_sanitized(self):
        self.extension.FAIL = RuntimeError("secret-value " + str(self.home) + " hostile-payload")
        result = self.lane(request("call"))
        self.assert_error(result, "internal")
        encoded = wire(result).decode()
        for sensitive in (str(self.home), "secret-value", "hostile-payload", "Traceback"):
            self.assertNotIn(sensitive, encoded)


for supplied in ("agent", "op_id"):
    def test(self, supplied=supplied):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        value = self.mutation()
        value["payload"]["args"][supplied] = "alice" if supplied == "agent" else op_id(value)
        self.assert_error(self.lane(value), "bad_args")
        self.assertEqual(self.extension.SEEN, [])
        self.assertEqual(self.journal.snapshot(self.home), ())
    setattr(DispatchTests, "test_a8_reject_explicit_" + supplied, test)

for code in sorted(ERRORS):
    def test(self, code=code):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        self.extension.FAIL = self.err.LineageError(code, "safe refusal")
        self.assert_error(self.lane(request("call")), code)
    setattr(DispatchTests, "test_a25_error_" + code, test)

for label, malformed in {
    "arbitrary_data": {"unrecognized": "value"},
    "nested_wrapper": {"untrusted": {"skills": []}},
    "wrong_array_type": {"skills": "invalid"},
    "extra_key": {"skills": [], "extra": True},
    "invalid_error_shape": {"ok": False, "code": "unknown_code"},
    "missing_result": {},
}.items():
    def test(self, malformed=malformed):
        self.extension.HAS_RESULT = True
        self.extension.RESULT = copy.deepcopy(malformed)
        self.assert_error(self.lane(request("call")), "internal")
    setattr(DispatchTests, "test_a25_malformed_backend_" + label, test)
