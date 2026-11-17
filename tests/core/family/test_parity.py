"""A9/A31: equality at the shared seam and public example validation.

Subprocess carrier parity and mutants require the prerequisites in ORACLE.md.
"""

import json
import hashlib
from pathlib import Path
import re

from lineage.core import envelope
from tests.core.family import ROOT, RuntimeCase, WireCase, request, op_id, wire


class SharedParityTests(RuntimeCase):
    def test_a9_read_shared_dispatch_equality(self):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        value = request("call")
        expected = self.app.dispatch("skill_list", {"agent": "alice"}, context=self.ctx.context, registry=self.registry).payload
        self.assertEqual(wire(self.lane(value)), wire(expected))

    def test_a9_journal_shared_dispatch_equality(self):
        # A-U05: Adapt dependency calls and fixture plumbing to integrated APIs.
        value = self.mutation()
        args = {**value["payload"]["args"], "agent": "alice", "op_id": op_id(value)}
        expected = self.app.dispatch("skill_publish", args, context=self.ctx.context, registry=self.registry).payload
        before = self.journal.snapshot(self.home)
        actual = self.lane(value)
        self.assertEqual(wire(actual), wire(expected))
        self.assertEqual(self.journal.snapshot(self.home), before)
        self.assert_witness(actual, value)


class PublicGuideTests(WireCase):
    def guide(self):
        path = ROOT / "docs" / "JSON_LANE.md"
        self.assertTrue(path.is_file(), "public guide is missing")
        return path.read_text(encoding="utf-8")

    def test_a31_executable_wire_and_config_examples(self):
        text = self.guide()
        examples = []
        for block in re.findall(r"```json\s*\n(.*?)\n```", text, re.S):
            examples.append(json.loads(block))
        configs = [v for v in examples if isinstance(v, dict) and set(v) == {"endpoint", "sources", "tools"}]
        envelopes = [v for v in examples if isinstance(v, dict) and v.get("schema") == "lineage.family/1" and "kind" in v]
        self.assertTrue(configs, "guide needs a complete endpoint config example")
        self.assertGreaterEqual(len(envelopes), 3, "guide needs capabilities, cursor, and call examples")
        self.assertEqual({v["kind"] for v in envelopes}, {"capabilities", "events.read", "call"})
        for cfg in configs:
            self.assertEqual(envelope.configuration(wire(cfg), cfg["endpoint"]), cfg)
        for value in envelopes:
            self.assertEqual(self.validate_request(value), value)

    def test_a31_public_carrier_commands(self):
        text = self.guide()
        self.assertIn("python3 -m lineage", text)
        self.assertRegex(text, r"--home\s+\S+\s+json")
        self.assertRegex(text, r"--home\s+\S+\s+drain\s+--endpoint")

    def test_a31_no_host_coordinates(self):
        text = self.guide()
        self.assertNotIn(str(Path.home()), text)
        self.assertNotIn(str(ROOT), text)


class OracleIntegrityTests(WireCase):
    def test_a32_frozen_python_oracle_hashes(self):
        directory = ROOT / "tests" / "core" / "family"
        document = (directory / "ORACLE.md").read_text(encoding="utf-8")
        rows = dict(re.findall(r"\| `([^`]+\.py)` \| `([0-9a-f]{64})` \|", document))
        actual = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in directory.glob("*.py")}
        self.assertTrue(rows, "frozen oracle manifest is absent")
        self.assertEqual(actual, rows, "frozen oracle file set or bytes changed")


for term in ("config.json", "consumer.lock", "spool", "state", "dedup",
             "capabilities", "events.read", "call", "inputSchema", "65536",
             "op_id", "agent", "retry", "bad_op", "pending", "complete",
             "fsync", "launched"):
    def test(self, term=term):
        self.assertIn(term, self.guide(), "required public guide topic: " + term)
    setattr(PublicGuideTests, "test_a31_topic_" + term.replace(".", "_").replace("-", "_"), test)
