"""Journal-authoritative defensive queries and complete pagination semantics."""
from copy import deepcopy
from unittest import mock
from lineage.core import journal
from lineage.core.errors import LineageError
from . import OracleCase, SEAT, agents, brief, canonical


class QueryTests(OracleCase):
    def test_a24_verified_empty_ledger_exact_page(self):
        self.assertEqual(self.invoke(agents.list_agents, ctx=self.ctx),
                         {"agents": [], "next_after": None, "head": 0})
        self.assertFalse(self.home.exists())

    def test_a24_missing_get_and_brief_are_no_agent(self):
        self.reject("no_agent", agents.get, "missing-one", ctx=self.ctx)
        self.reject("no_agent", brief.get, "missing-one", ctx=self.ctx)
        self.assertFalse(self.home.exists())

    def test_a24_corrupt_journal_is_not_empty(self):
        target = self.home / "ledger/main/events.jsonl"
        target.parent.mkdir(parents=True)
        target.write_bytes(b'{"not":"an event"}\n')
        with self.assertRaises(LineageError) as raised:
            self.invoke(agents.list_agents, ctx=self.ctx)
        self.assertIn(raised.exception.code, ("hash_mismatch", "internal"))
        self.assertEqual(target.read_bytes(), b'{"not":"an event"}\n')

    def test_a24_unreadable_journal_is_not_empty(self):
        with mock.patch.object(journal, "snapshot", side_effect=LineageError("internal", "fixture read refusal")):
            self.reject("internal", agents.list_agents, ctx=self.ctx)

    def seed_mixed(self):
        for name, workflow, language, status in (
                ("zeta-one", "develop", "python", "draft"),
                ("beta-one", "review", "general", "retired"),
                ("alpha-one", "develop", "python", "draft"),
                ("theta-one", "develop", "python", "retired"),
                ("delta-one", "develop", "general", "shadow")):
            self.seed(name, workflow=workflow, language=language, status=status)

    def test_a25_lexical_pages_and_snapshot_head(self):
        self.seed_mixed()
        seen, after = [], None
        while True:
            page = self.invoke(agents.list_agents, include_retired=True, after=after, limit=2, ctx=self.ctx)
            self.assertEqual(set(page), {"agents", "next_after", "head"})
            self.assertEqual(page["head"], 5)
            self.assertLessEqual(len(page["agents"]), 2)
            ids = [item["agent_id"] for item in page["agents"]]
            self.assertEqual(ids, sorted(ids))
            self.assertFalse(set(ids) & set(seen))
            seen += ids
            if page["next_after"] is None:
                break
            self.assertEqual(page["next_after"], ids[-1])
            after = page["next_after"]
            self.assertLessEqual(len(seen), 5)
        self.assertEqual(seen, ["alpha-one", "beta-one", "delta-one", "theta-one", "zeta-one"])

    def test_a25_conjunctive_filters_absent_cursor_and_empty_final_page(self):
        self.seed_mixed()
        page = self.invoke(agents.list_agents, workflow="develop", language="python", status="draft",
                           after="middle-one", limit=1, ctx=self.ctx)
        self.assertEqual([a["agent_id"] for a in page["agents"]], ["zeta-one"])
        self.assertIsNone(page["next_after"])
        page = self.invoke(agents.list_agents, after="zzzz-one", ctx=self.ctx)
        self.assertEqual(page, {"agents": [], "next_after": None, "head": 5})

    def test_a26_retirement_default_include_and_explicit_override(self):
        self.seed_mixed()
        normal = self.invoke(agents.list_agents, ctx=self.ctx)
        self.assertEqual([a["agent_id"] for a in normal["agents"]], ["alpha-one", "delta-one", "zeta-one"])
        all_agents = self.invoke(agents.list_agents, include_retired=True, ctx=self.ctx)
        self.assertEqual(len(all_agents["agents"]), 5)
        retired = self.invoke(agents.list_agents, status="retired", workflow="develop", language="python", ctx=self.ctx)
        self.assertEqual([a["agent_id"] for a in retired["agents"]], ["theta-one"])
        self.assertEqual(self.invoke(agents.get, "theta-one", ctx=self.ctx)["record"]["status"], "retired")

    def test_a26_invalid_limits_filters_and_cursor(self):
        for args in ({"limit": True}, {"limit": False}, {"limit": 0}, {"limit": 1001},
                     {"limit": 2.0}, {"workflow": "unknown"}, {"status": "unknown"},
                     {"include_retired": 1}, {"after": "a/b"}, {"after": "agent-one\n"},
                     {"after": "ab"}, {"after": 3}):
            self.reject("bad_args", agents.list_agents, **args, ctx=self.ctx)

    def test_a26_unknown_filter_is_closed_at_tool_boundary(self):
        # Invoke the real handler before the schema assertions so the fail-first
        # witness is behavioral even though an unknown property is U04-owned.
        self.handler("agent_list", {})
        from lineage.core import app
        result = app.dispatch("agent_list", {"unknown_filter": True}, context=self.ctx, registry=self.reg)
        self.assertEqual(result.payload["code"], "bad_args")
        self.assertNotIn("untrusted", result.payload)

    def test_a27_get_list_and_create_nested_results_are_detached(self):
        seats = [deepcopy(SEAT), {**SEAT, "effort": "high"}]
        self.seed(allowed_seats=seats)
        pristine = deepcopy(journal.snapshot(self.home))
        first = self.invoke(agents.get, "agent-one", ctx=self.ctx)
        first["record"]["allowed_seats"][0]["model"] = "forged"
        first["record"]["references"][0]["sha256"] = "f" * 64
        listed = self.invoke(agents.list_agents, ctx=self.ctx)
        listed["agents"][0]["allowed_seats"].clear()
        again = self.invoke(agents.get, "agent-one", ctx=self.ctx)
        self.assertEqual(again["record"], pristine[0]["payload"]["record"])
        self.assertEqual(journal.snapshot(self.home), pristine)

    def test_a27_create_result_nested_aliases_do_not_leak(self):
        original = self.create()
        original.value["record"]["allowed_seats"][0]["mode"] = "interactive"
        original.value["record"]["references"].clear()
        actual = self.invoke(agents.get, "agent-one", ctx=self.ctx)["record"]
        self.assertEqual(actual["allowed_seats"], [SEAT])
        self.assertEqual(len(actual["references"]), 2)

    def test_a38_tampered_agent_and_scorecard_are_not_authority(self):
        self.seed()
        expected = self.invoke(agents.get, "agent-one", ctx=self.ctx)
        directory = self.projection_dir()
        directory.mkdir(parents=True)
        (directory / "agent.json").write_bytes(canonical({"agent_id": "forged-one", "status": "promoted"}))
        (directory / "scorecard.json").write_bytes(canonical({"score": 999, "status": "promoted"}))
        self.assertEqual(self.invoke(agents.get, "agent-one", ctx=self.ctx), expected)
        page = self.invoke(agents.list_agents, ctx=self.ctx)
        self.assertEqual(page["agents"], [expected["record"]])
        self.assertNotIn("score", expected["record"])

    def test_a42_success_and_failure_reads_change_no_files(self):
        self.seed()
        before = self.inventory()
        self.invoke(agents.get, "agent-one", ctx=self.ctx)
        self.invoke(agents.list_agents, ctx=self.ctx)
        self.invoke(brief.get, "agent-one", ctx=self.ctx)
        for function in (agents.get, brief.get):
            self.reject("no_agent", function, "missing-one", ctx=self.ctx)
        self.assertEqual(self.inventory(), before)

    def test_a42_missing_home_reads_do_not_create_runtime(self):
        self.invoke(agents.list_agents, ctx=self.ctx)
        self.reject("no_agent", agents.get, "missing-one", ctx=self.ctx)
        self.reject("no_agent", brief.get, "missing-one", ctx=self.ctx)
        self.assertFalse(self.home.exists())
