"""One verified read/fold, truthful errors, compact bounds and MCP parity."""
from copy import deepcopy
import hashlib
import io
import json
from unittest import mock

from lineage.core import app, journal, mcp, snapshot
from lineage.core.errors import LineageError
from lineage.domain import memory
from .support import AGENT, HarnessCase, put_memory
from lineage.core.supervisor import _closing, _opening
from .support import SEAT


class Snapshots(HarnessCase):
    def read(self):
        return snapshot.build(context=self.ctx, registry=self.reg)

    def synthetic_agents(self, count):
        seed = self.events()[0]["payload"]
        for index in range(count):
            agent_id = "a%03d" % index
            def prepare(history, draft, agent_id=agent_id):
                payload = deepcopy(seed)
                payload["record"].update(agent_id=agent_id, display_name=agent_id)
                payload["record"]["born"]["event_id"] = draft["id"]
                return payload
            # Synthetic births exercise the real verified journal and installed
            # folds; dependency admission is covered by the real seed birth.
            journal.transact(self.home, agent=agent_id, op_id="synthetic/" + agent_id,
                kind="agent.born", payload={}, prepare=prepare,
                validators={"agent.born": lambda history, event: None})

    def test_one_snapshot_and_one_shared_fold_with_exact_head_hash(self):
        raw = journal.canonical_bytes(self.events()[-1]) + b"\n"
        with mock.patch.object(journal, "snapshot", wraps=journal.snapshot) as read, \
             mock.patch.object(memory, "_fold", wraps=memory._fold) as fold, \
             mock.patch.object(app, "dispatch", side_effect=AssertionError("second tool read")):
            value = self.read()
        self.assertEqual(read.call_count, 1)
        self.assertEqual(fold.call_count, 1)
        self.assertEqual(value["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(value["head"], 1)
        self.assertFalse(value["truncated"])
        self.assertEqual(value["agents"][0]["agent_id"], AGENT)
        self.assertEqual(len(value["agents"][0]["agent_version"]), 12)

    def test_open_closed_latest_close_order_and_projections(self):
        for suffix in ("0001", "0002", "0003"):
            run_id = "snapshot" + suffix
            args = _opening(run_id, AGENT, SEAT, {"id": run_id, "kind": "test", "language": "python"})
            self.assertEqual(self.call("run_open", args).exit_code, 0)
        # Deliberately close in a different order from opening.
        for suffix, verdict in (("0002", "green"), ("0001", "error")):
            run_id = "snapshot" + suffix
            put_memory(self.home, run_id, verdict=verdict, suffix=suffix)
            if verdict == "error":
                put_memory(self.home, run_id, kind="lesson", suffix=suffix)
            self.assertEqual(self.call("run_close", _closing(run_id, AGENT, verdict)).exit_code, 0)
        row = self.read()["agents"][0]
        self.assertEqual((row["open_runs"], row["runs_closed"], row["last_run_verdict"]), (1, 2, "error"))
        record = self.call("agent_get", {"agent_id": AGENT}).payload["untrusted"]["record"]
        self.assertEqual(row["agent_version"], record["agent_version"][:12])
        self.assertEqual(row["memory_gen"], record["memory_gen"])

    def test_cli_and_mcp_resource_are_identical_and_discoverable(self):
        code, out, err = self.cli("snapshot", "--json")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.cli("snapshot")[1], out)
        requests = [{"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}},
                    {"jsonrpc": "2.0", "id": 2, "method": "resources/read",
                     "params": {"uri": "lineage://snapshot"}}]
        output = io.StringIO()
        mcp.main(context=self.ctx, registry=self.reg,
            stdin=io.BytesIO(b"".join(journal.canonical_bytes(r) + b"\n" for r in requests)),
            stdout=output, stderr=io.StringIO())
        replies = [json.loads(line) for line in output.getvalue().splitlines()]
        discovered = list(replies[0]["result"]["resources"])
        page = replies[0]["result"]
        while "nextCursor" in page:
            request = {"jsonrpc": "2.0", "id": 3, "method": "resources/list",
                       "params": {"cursor": page["nextCursor"]}}
            page_out = io.StringIO()
            mcp.main(context=self.ctx, registry=self.reg,
                stdin=io.BytesIO(journal.canonical_bytes(request) + b"\n"),
                stdout=page_out, stderr=io.StringIO())
            page = json.loads(page_out.getvalue())["result"]
            discovered.extend(page["resources"])
        self.assertIn("lineage://snapshot", [r["uri"] for r in discovered])
        content = replies[1]["result"]["contents"][0]
        self.assertEqual(content["mimeType"], "application/json")
        self.assertEqual(json.loads(content["text"]), json.loads(out))

    def test_corruption_missing_home_and_fold_failure_never_become_empty_health(self):
        for failure in (LineageError("hash_mismatch"), OSError("sensitive path")):
            with mock.patch.object(journal, "snapshot", side_effect=failure):
                code, out, err = self.cli("snapshot")
            value = json.loads(out)
            self.assertEqual(code, 3)
            self.assertEqual(value["code"], getattr(failure, "code", "internal"))
            self.assertNotIn("untrusted", value)
            self.assertNotIn("sensitive path", out + err)
        with mock.patch.object(memory, "_fold", side_effect=ValueError("invalid state")):
            self.assertEqual(self.cli("snapshot")[0], 3)
        self.ctx = app.create_context(self.home / "missing", registry=self.reg)
        with self.assertRaises(LineageError):
            self.read()

    def test_fifty_agent_size_recorded_and_bounded_to_ten_kib(self):
        self.synthetic_agents(49)
        code, out, err = self.cli("snapshot", "--json")
        size = len(out.encode("utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)["untrusted"]["agents"]), 50)
        self.assertLessEqual(size, 10_000)
        # No tokenizer is injected into runtime Services. Byte size is the
        # portable acceptance metric, not an invented exact token count.
        print("snapshot_size: agents=50 bytes=%d target_bytes=10000 token_ceiling=not_measured" % size)

    def test_cap_sort_and_optional_promoted_seat(self):
        self.synthetic_agents(201)
        value = self.read()
        self.assertTrue(value["truncated"])
        self.assertEqual(len(value["agents"]), 200)
        self.assertEqual([r["agent_id"] for r in value["agents"]], sorted(r["agent_id"] for r in value["agents"]))
        for row in value["agents"]:
            self.assertNotIn("promoted_seat", row)
        # Projection copies the exact seat rather than a model-only identity.
        original = journal.snapshot
        def promoted(*args, **kwargs):
            result = original(*args, **kwargs)
            result.state["agents"]["a000"]["promoted_seat"] = deepcopy(SEAT)
            return result
        with mock.patch.object(journal, "snapshot", side_effect=promoted):
            self.assertEqual(self.read()["agents"][0]["promoted_seat"], SEAT)

    def test_real_tamper_refuses_cli_and_mcp(self):
        path = self.home / "ledger/main/events.jsonl"
        raw = path.read_bytes()
        path.write_bytes(raw.replace(b"Test agent", b"Fake agent", 1))
        self.assertEqual(self.cli("snapshot")[0], 3)
        with self.assertRaises(mcp._ResourceFailure):
            mcp._live_resource("lineage://snapshot", context=self.ctx, registry=self.reg)

    def test_no_snapshot_mutation_and_invalid_options(self):
        before = {str(p.relative_to(self.home)): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        self.read()
        after = {str(p.relative_to(self.home)): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(self.cli("snapshot", "--unknown")[0], 2)

    def test_missing_required_fold_is_an_error_even_for_empty_state(self):
        from lineage.core.registry import Registry
        reg = Registry({}, {}, {})
        ctx = app.create_context(self.home, registry=reg)
        with self.assertRaises(LineageError) as refused:
            snapshot.build(context=ctx, registry=reg)
        self.assertEqual(refused.exception.code, "internal")

    def test_established_empty_home_has_zero_head_and_null_hash(self):
        empty = self.home / "empty"
        empty.mkdir(mode=0o700)
        self.ctx = app.create_context(empty, registry=self.reg)
        self.assertEqual(self.read(), {"head": 0, "sha256": None, "agents": [], "truncated": False})

    def test_resource_pagination_refuses_invalid_cursors(self):
        for cursor in (None, 1, "foreign", "resources:1", "resources:999999"):
            with self.subTest(cursor=cursor), self.assertRaises(mcp._InvalidParams):
                mcp._method("resources/list", {"cursor": cursor}, context=self.ctx,
                            registry=self.reg, resource_root=None)
