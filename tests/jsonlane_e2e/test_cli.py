"""Exercise documented requests against a private home and the real registry."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
GUIDE = (ROOT / "docs/JSON_LANE.md").read_text(encoding="utf-8")
EXAMPLES = [json.loads(block) for block in
            re.findall(r"```json\s*\n(.*?)\n```", GUIDE, re.S)]


class JSONLaneCLI(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name) / "home"
        self.endpoint = self.home / "family/Endpoint_1"
        self.endpoint.mkdir(parents=True, mode=0o700)
        for path in (self.home, self.home / "family", self.endpoint):
            path.chmod(0o700)
        self.config = self.endpoint / "config.json"
        configuration = next(item for item in EXAMPLES if "endpoint" in item)
        self.config.write_text(json.dumps(configuration), encoding="utf-8")
        self.config.chmod(0o600)

    def example(self, identity, *, changed=False):
        values = [item for item in EXAMPLES if item.get("id") == identity]
        return deepcopy(values[-1 if changed else 0])

    def cli(self, *arguments, request=None):
        completed = subprocess.run(
            [sys.executable, "-m", "lineage", "--home", str(self.home), *arguments],
            input=None if request is None else json.dumps(request).encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, timeout=15,
            check=False,
        )
        value = json.loads(completed.stdout)
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False).encode() + b"\n"
        self.assertEqual(completed.stdout, canonical)
        self.assertNotIn(b"Traceback", completed.stderr)
        return completed, value

    def lane(self, value):
        return self.cli("json", request=value)

    def ledger(self):
        path = self.home / "ledger/main/events.jsonl"
        return path.read_bytes() if path.exists() else b""

    def assert_refusal(self, path, reason):
        completed, receipt = self.lane(self.example("discover01"))
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(receipt["result"], {"ok": False, "code": "bad_args"})
        diagnostic = completed.stderr.decode("utf-8")
        self.assertEqual(len(diagnostic.splitlines()), 1)
        self.assertIn("lineage json: refused " + path + ": ", diagnostic)
        self.assertIn(reason, diagnostic)
        self.assertNotIn(str(self.home), diagnostic)
        self.assertNotIn("Sender_1", diagnostic)
        self.assertEqual(self.ledger(), b"")

    def test_documented_capabilities(self):
        completed, receipt = self.lane(self.example("discover01"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b"")
        data = receipt["result"]["untrusted"]
        self.assertEqual(data["health"], "ready")
        self.assertEqual(data["protocol"], "lineage.family/1")
        self.assertEqual([tool["name"] for tool in data["tools"]],
                         ["ledger_events", "skill_list", "skill_publish"])

    def test_documented_cursor_empty_kinds(self):
        completed, receipt = self.lane(self.example("cursor001"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(receipt["result"]["untrusted"]["events"], [])
        self.assertEqual(receipt["result"]["untrusted"]["head"], 0)

    def test_documented_cursor_omitted_kinds(self):
        value = self.example("cursor001")
        del value["payload"]["kinds"]
        completed, receipt = self.lane(value)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(receipt["result"]["untrusted"]["events"], [])

    def test_documented_publish_exact_retry_and_changed_payload(self):
        value = self.example("publish01")
        first, receipt = self.lane(value)
        self.assertEqual(first.returncode, 0, first.stderr)
        data = receipt["result"]["untrusted"]
        self.assertEqual(receipt["correlation_id"], "example01")
        self.assertEqual(data["skill"]["skill_id"], "example-skill")
        events = [json.loads(line) for line in self.ledger().splitlines()]
        self.assertEqual(len(events), 1)
        event = events[0]
        operation = "lin-" + hashlib.sha256(b"Sender_1\0Endpoint_1\0publish01").hexdigest()[:44]
        self.assertEqual(event["op_id"], operation)
        self.assertEqual(event["kind"], "skill.published")
        self.assertEqual(data["commit"], {"event_ids": [event["id"]],
                         "head": event["lamport"], "sha256": event["sha256"]})
        before = self.ledger()
        retry, repeated = self.lane(value)
        self.assertEqual(retry.returncode, 0, retry.stderr)
        self.assertEqual(repeated, receipt)
        self.assertEqual(retry.stdout, first.stdout)
        self.assertEqual(self.ledger(), before)
        refused, collision = self.lane(self.example("publish01", changed=True))
        self.assertEqual(refused.returncode, 3)
        self.assertEqual(collision["result"], {"ok": False, "code": "bad_op"})
        self.assertEqual(self.ledger(), before)
        final, _ = self.lane(value)
        self.assertEqual(final.stdout, first.stdout)

    def test_cli_call_then_cursor_observes_publication(self):
        args = self.example("publish01")["payload"]["args"]
        operation = "publish.cli:/example-1"
        completed, result = self.cli("call", "skill_publish", "--json",
                                    json.dumps({**args, "agent": "alice", "op_id": operation}))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        before = self.ledger()
        replay, repeated = self.cli("call", "skill_publish", "--json",
                                   json.dumps({**args, "agent": "alice", "op_id": operation}))
        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertEqual(repeated, result)
        self.assertEqual(self.ledger(), before)
        for index, kinds in enumerate(([], None)):
            value = self.example("cursor001")
            value["id"] = "observe0" + str(index)
            if kinds is None:
                del value["payload"]["kinds"]
            completed, receipt = self.lane(value)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            events = receipt["result"]["untrusted"]["events"]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["kind"], "skill.published")
            self.assertEqual(events[0]["op_id"], operation)
            self.assertEqual(result["untrusted"]["commit"]["event_ids"], [events[0]["id"]])

    def test_group_writable_config_diagnostic(self):
        self.config.chmod(0o620)
        self.assert_refusal("family/Endpoint_1/config.json", "group/world writable (chmod 600)")

    def test_world_writable_config_diagnostic(self):
        self.config.chmod(0o602)
        self.assert_refusal("family/Endpoint_1/config.json", "group/world writable")

    def test_missing_config_diagnostic(self):
        self.config.unlink()
        self.assert_refusal("family/Endpoint_1/config.json", "missing")

    def test_symlink_config_diagnostic(self):
        target = self.home / "saved-config.json"
        self.config.rename(target)
        self.config.symlink_to("../../saved-config.json")
        self.assert_refusal("family/Endpoint_1/config.json", "symlink")

    def test_writable_control_directories_diagnostic(self):
        for relative in (".", "family", "family/Endpoint_1"):
            with self.subTest(path=relative):
                path = self.home / relative
                path.chmod(0o720)
                try:
                    self.assert_refusal(relative, "group/world writable (chmod 700)")
                finally:
                    path.chmod(0o700)

    def test_missing_control_directory_diagnostic(self):
        self.config.unlink()
        self.endpoint.rmdir()
        self.assert_refusal("family/Endpoint_1", "missing")

    def test_symlink_control_directory_diagnostic(self):
        target = self.endpoint.with_name("saved-endpoint")
        self.endpoint.rename(target)
        self.endpoint.symlink_to(target.name, target_is_directory=True)
        self.assert_refusal("family/Endpoint_1", "symlink")
