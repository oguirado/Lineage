"""Hook identities, replay, strict input, privacy and real closing gates."""
from copy import deepcopy
import hashlib
import json
from unittest import mock

from lineage.core import hook, schema
from .support import AGENT, SEAT, HarnessCase, put_memory


class Hooks(HarnessCase):
    def setUp(self):
        super().setUp()
        self.map = self.home / "hook-map.json"
        self.mapping = {"session": {"agent_id": AGENT, "seat": SEAT},
            "agent_types": {"reviewer": {"agent_id": AGENT, "seat": SEAT}}}
        self.map.write_text(json.dumps(self.mapping))

    def payload(self, event="SubagentStart", **extra):
        result = {"session_id": "session-one", "transcript_path": "never-read.jsonl",
                  "cwd": "work", "hook_event_name": event}
        if event.startswith("Subagent"):
            result.update(agent_id="worker-one", agent_type="reviewer")
        return {**result, **extra}

    def deliver(self, payload, *args):
        raw = json.dumps(payload).encode() if not isinstance(payload, bytes) else payload
        return self.cli("hook", "--map", str(self.map), *args, raw=raw)

    def test_start_duplicate_and_stop_refusal_leave_exact_open_witness(self):
        start = self.payload()
        self.assertEqual(self.deliver(start), (0, "", ""))
        before = self.events()
        self.assertEqual(self.deliver(start), (0, "", ""))
        self.assertEqual(self.events(), before)
        opening = before[-1]
        run_id = opening["payload"]["run_id"]
        self.assertEqual(opening["op_id"], run_id + "/open")
        self.assertEqual(opening["agent"], AGENT)
        code, out, err = self.deliver(self.payload("SubagentStop"))
        self.assertEqual((code, out), (3, ""))
        self.assertEqual(json.loads(err)["code"], "memory_required")
        self.assertEqual(json.loads(err)["run_id"], run_id)
        self.assertIsNone(self.call("run_get", {"run_id": run_id}).payload["untrusted"]["closed"])

    def test_hash_only_and_successful_stop_replay_after_memory(self):
        self.deliver(self.payload())
        run_id = self.events()[-1]["payload"]["run_id"]
        put_memory(self.home, run_id)
        secret = "Do not persist this free text or its instructions."
        stop = self.payload("SubagentStop", last_assistant_message=secret)
        self.assertEqual(self.deliver(stop), (0, "", ""))
        before = self.events()
        self.assertEqual(self.deliver(stop), (0, "", ""))
        self.assertEqual(self.events(), before)
        encoded = json.dumps(before)
        self.assertNotIn(secret, encoded)
        self.assertNotIn("never-read.jsonl", encoded)
        self.assertIn(hashlib.sha256(secret.encode()).hexdigest(), encoded)
        closed = self.call("run_get", {"run_id": run_id}).payload["untrusted"]["closed"]
        self.assertEqual(closed["outcome"]["verdict"], "green")
        self.assertTrue(all(v is None for v in closed["cost"].values()))
        changed = {**stop, "last_assistant_message": "changed"}
        self.assertEqual(json.loads(self.deliver(changed)[2])["code"], "bad_op")

    def test_stop_failure_needs_lesson_and_preserves_error(self):
        self.deliver(self.payload("SessionStart"))
        run_id = self.events()[-1]["payload"]["run_id"]
        put_memory(self.home, run_id, verdict="error")
        result = self.deliver(self.payload("StopFailure"))
        self.assertEqual(json.loads(result[2])["code"], "memory_debt")
        put_memory(self.home, run_id, kind="lesson")
        self.assertEqual(self.deliver(self.payload("StopFailure")), (0, "", ""))
        self.assertEqual(self.events()[-1]["payload"]["record"]["outcome"]["verdict"], "error")

    def test_session_stop_and_session_end_share_identity(self):
        self.deliver(self.payload("SessionStart"))
        run_id = self.events()[-1]["payload"]["run_id"]
        put_memory(self.home, run_id)
        self.assertEqual(self.deliver(self.payload("Stop")), (0, "", ""))
        before = self.events()
        self.assertEqual(self.deliver(self.payload("SessionEnd")), (0, "", ""))
        self.assertEqual(self.events(), before)

    def test_subagents_and_sessions_never_collapse(self):
        self.deliver(self.payload())
        self.deliver(self.payload(agent_id="worker-two"))
        self.deliver(self.payload(session_id="session-two"))
        self.deliver(self.payload("SessionStart"))
        ids = [e["payload"]["run_id"] for e in self.events() if e["kind"] == "run.open"]
        self.assertEqual(len(set(ids)), 4)

    def test_unmapped_events_and_types_are_silent_unless_verbose(self):
        before = self.events()
        self.assertEqual(self.deliver(self.payload(agent_type="unknown")), (0, "", ""))
        code, out, err = self.deliver(self.payload(agent_type="unknown"), "--verbose")
        self.assertEqual((code, out), (0, ""))
        self.assertTrue(err)
        self.assertEqual(self.deliver(self.payload("Notification")), (0, "", ""))
        self.assertEqual(self.events(), before)

    def test_exact_session_binding_precedes_default_and_no_transcript_read(self):
        self.mapping["sessions"] = {"session-one": {"agent_id": "missing-agent", "seat": SEAT}}
        self.map.write_text(json.dumps(self.mapping))
        result = self.deliver(self.payload("SessionStart"))
        self.assertEqual(json.loads(result[2])["code"], "no_agent")
        with mock.patch.object(hook, "_map", return_value={}):
            self.assertEqual(self.deliver(self.payload()), (0, "", ""))

    def test_malformed_inputs_maps_and_options_fail_two(self):
        before = self.events()
        payloads = [b"[]", b"{", b'{"session_id":"a","session_id":"b"}', b"{}",
                    b"\xff", b"{\"value\":NaN}", b"x" * (schema.MAX_JSON_BYTES + 1),
                    self.payload(agent_id=1), self.payload(last_assistant_message=[])]
        for payload in payloads:
            with self.subTest(payload=str(payload)[:40]):
                code, out, err = self.deliver(payload)
                self.assertEqual((code, out), (2, ""))
                self.assertEqual(json.loads(err)["code"], "bad_args")
        for mapping in ([], {"extra": {}}, {"agent_types": []}, {"session": {"agent_id": AGENT}}):
            self.map.write_text(json.dumps(mapping))
            self.assertEqual(self.deliver(self.payload())[0], 2)
        self.assertEqual(self.events(), before)
        self.assertEqual(self.cli("hook", "--unknown", raw=b"{}")[0], 2)
