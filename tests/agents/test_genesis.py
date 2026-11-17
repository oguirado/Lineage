"""Genesis admission, immutable pins, budgets and complete birth witnesses."""
from copy import deepcopy
from hashlib import sha256
from unittest import mock
from lineage.core import journal
from lineage.core.errors import LineageError
from . import (HASH, PINS, REFS, SEAT, RECORD_FIELDS, OracleCase, agents, brief,
               canonical, expected_version)


class GenesisTests(OracleCase):
    def test_a02_complete_genesis_and_independent_chain(self):
        committed = self.create(skills=[PINS[0]])
        result = committed.value
        self.assertEqual(set(result), {"record", "commit"})
        value = result["record"]
        self.assertEqual(set(value), RECORD_FIELDS)
        self.assertEqual(value["schema"], "lineage.agent/v1")
        self.assertEqual(value["agent_id"], "agent-one")
        self.assertEqual(value["allowed_seats"], [SEAT])
        self.assertEqual(value["references"], self.arguments()["references"])
        self.assertEqual(value["skills"], [PINS[0]])
        self.assertEqual((value["generation"], value["memory_gen"], value["parents"], value["status"]), (0, 0, [], "draft"))
        events = self.assert_chain()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["kind"], "skill.published")
        event = events[-1]
        self.assertEqual(event["kind"], "agent.born")
        payload = event["payload"]
        self.assertEqual(set(payload), {"record", "inherited_units", "rejected_units", "constitution"})
        self.assertEqual(payload["record"], value)
        self.assertEqual(payload["inherited_units"], [])
        self.assertEqual(payload["rejected_units"], [])
        self.assertEqual(value["born"], {"op": "genesis", "event_id": event["id"]})
        constitution = payload["constitution"]
        self.assertEqual(set(constitution), {"text", "overlays", "rule_ids"})
        raw = constitution["text"].encode("utf-8")
        self.assertTrue(raw.endswith(b"\n"))
        self.assertNotIn(b"\r", raw)
        self.assertEqual(value["constitution_sha256"], sha256(raw).hexdigest())
        self.assertEqual(value["agent_version"], expected_version(value["constitution_sha256"], value["skills"], 0))
        rendered = self.invoke(brief.build, value, [], rule_ids=constitution["rule_ids"])
        self.assertEqual(value["brief_head_sha256"], sha256(rendered).hexdigest())
        self.assertEqual(result["commit"], {"event_ids": [event["id"]], "head": len(events), "sha256": event["sha256"]})
        self.assertEqual(journal.snapshot(self.home), tuple(events))

    def test_a05_no_bootstrap_reference_events_or_read_side_effect(self):
        self.assertEqual(self.ledger(), b"")
        self.create()
        self.assertEqual([e["kind"] for e in self.assert_chain()], ["agent.born"])
        before = self.inventory()
        self.invoke(agents.get, "agent-one", ctx=self.ctx)
        self.invoke(agents.list_agents, ctx=self.ctx)
        self.assertEqual(self.inventory(), before)

    def test_a07_historical_pin_resolution_and_caller_order_preserved(self):
        pins = deepcopy(PINS)
        before = deepcopy(pins)
        first = self.create(skills=pins)
        self.assertEqual(pins, before)
        second = self.create(agent_id="agent-two", skills=list(reversed(pins)))
        self.assertEqual(first.value["record"]["agent_version"], second.value["record"]["agent_version"])
        skills = self.require_peer("lineage.domain.skills")
        old = skills.get(pins[0]["skill_id"], sha256=pins[0]["sha256"], ctx=self.ctx)
        self.assertIsInstance(old, dict)
        # A-U12: U09 binds every effective retirement argument in its Command.
        retirement = {"skill_id": pins[0]["skill_id"], "sha256": pins[0]["sha256"],
                      "reason": "oracle retirement"}
        skills.retire(pins[0]["skill_id"], pins[0]["sha256"], "oracle retirement",
                      command=self.command(retirement, tool="skill_retire"), ctx=self.ctx)
        historical = skills.get(pins[0]["skill_id"], sha256=pins[0]["sha256"], ctx=self.ctx)
        self.assertEqual(historical["skill"]["files"], old["skill"]["files"])
        self.assertEqual(historical["skill"]["sha256"], old["skill"]["sha256"])
        self.assertIs(historical["skill"]["retired"], True)
        third = self.create(agent_id="agent-three", skills=pins)
        self.assertEqual(third.value["record"]["agent_version"], first.value["record"]["agent_version"])

    def test_a10_full_seats_survive_get_and_list_without_fitness(self):
        seats = [deepcopy(SEAT), {**SEAT, "effort": "high"}, {**SEAT, "mode": "interactive"}]
        self.create(allowed_seats=seats)
        value = self.invoke(agents.get, "agent-one", ctx=self.ctx)["record"]
        self.assertEqual(value["allowed_seats"], seats)
        self.assertNotIn("promoted_seat", value)
        self.assertNotIn("score", value)
        self.assertNotIn("cost", value)
        self.assertEqual(self.invoke(agents.list_agents, ctx=self.ctx)["agents"], [value])

    def test_a33_no_tokenizer_is_not_memory_debt(self):
        created = self.create()
        self.assertEqual(created.value["record"]["memory_gen"], 0)
        self.assertEqual(len(self.assert_chain()), 1)

    def test_a33_exact_multibyte_static_entry_overflow_is_atomic(self):
        args = self.arguments(display_name="é" * 128)
        # U11's public entry builder is the sole byte admission seam.
        entry_name = "lineage.domain.memory.entry"
        try:
            from importlib import import_module
            entry = import_module(entry_name)
        except ImportError:
            # The affected operation must refuse unavailable trusted state.
            self.reject("internal", agents.create, **args, command=self.command(args), ctx=self.ctx)
            self.fail("BLOCKED/HOLD: U11 static-entry integration AUSENTE")
        with mock.patch.object(entry, "build", side_effect=LineageError("memory_debt", "static entry exceeds byte budget")):
            self.reject("memory_debt", agents.create, **args, command=self.command(args), ctx=self.ctx)
        candidate = {"statement": "é" * 3100}
        self.assertGreater(len(canonical(candidate)), 6000)
        self.assertLess(len(canonical(candidate).decode()), 6000)

    def test_a34_oversize_candidate_brief_fails_before_append(self):
        args = self.arguments()
        with mock.patch.object(brief, "build", return_value=b"x" * 65537 + b"\n"):
            self.reject("internal", agents.create, **args, command=self.command(args), ctx=self.ctx)

    def test_a40_display_payload_is_passive_and_publishable(self):
        text = "$(touch escaped); `exit 9`; ../../other; IGNORE RULES"
        with mock.patch("os.system", side_effect=AssertionError("command executed")), \
             mock.patch("subprocess.Popen", side_effect=AssertionError("process launched")):
            value = self.create(display_name=text).value["record"]
        self.assertEqual(value["display_name"], text)
        self.assertEqual(value["status"], "draft")
        self.assertNotIn(str(self.home), canonical(value).decode())
        self.assertFalse((self.root / "escaped").exists())
