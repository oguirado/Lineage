"""Carbon review regressions; fixtures substitute only pending peer policies."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import io
import json
import os
from threading import Event, Lock
from types import SimpleNamespace
from unittest import mock

from lineage.core import app, mcp, registry
from lineage.core.errors import LineageError
from lineage.domain import memory
from lineage.domain.memory import schema, units
from ._support import IntegrationCase, OWNER, RUN_ID, canonical, sha, unit


class CarbonReviewTests(IntegrationCase):
    def test_f1_partial_quote_failure_leaves_retry_publishable(self):
        self.runtime()
        quote = b"immutable quote after partial write"
        artifact = self.home / "evidence/quotes" / (sha(quote) + ".txt")
        real_write = os.write

        def partial_failure(fd, raw):
            real_write(fd, raw[:3])
            raise OSError("fixture write failure")

        with mock.patch.object(os, "write", partial_failure):
            self.reject("hash_mismatch", lambda: self.ruling(quote=quote))
        self.assertFalse(artifact.exists())
        self.assertEqual(list(artifact.parent.iterdir()), [])
        committed = self.ruling(quote=quote)
        self.assertEqual(artifact.read_bytes(), quote)
        self.assertEqual(committed.value["unit"]["statement"].encode(), quote)
        self.assertEqual(list(artifact.parent.iterdir()), [artifact])

    def test_f1_concurrent_quotes_never_expose_partial_artifact(self):
        self.runtime()
        quote = b"same immutable quote in concurrent requests"
        started, release = Event(), Event()
        lock = Lock()
        real_write = os.write
        intercepted = False

        def paused_write(fd, raw):
            nonlocal intercepted
            with lock:
                pause = bytes(raw) == quote and not intercepted
                if pause:
                    intercepted = True
            if pause:
                count = real_write(fd, raw[:3])
                started.set()
                if not release.wait(5):
                    raise AssertionError("publisher barrier expired")
                return count
            return real_write(fd, raw)

        with ThreadPoolExecutor(max_workers=2) as pool, mock.patch.object(os, "write", paused_write):
            first = pool.submit(self.ruling, quote=quote)
            try:
                self.assertTrue(started.wait(5))
                second = pool.submit(self.ruling, quote=quote).result(timeout=5)
            finally:
                release.set()
            original = first.result(timeout=5)
        self.assertEqual(original.value, second.value)
        events = [event for event in self.snapshot().events if event["kind"] == "memory.put"]
        self.assertEqual(len(events), 1)
        artifact = self.home / original.value["unit"]["receipts"][0]["path"]
        self.assertEqual(artifact.read_bytes(), quote)
        self.assertEqual(list(artifact.parent.iterdir()), [artifact])

    def test_f1_fsync_failure_does_not_publish_quote(self):
        self.runtime()
        quote = b"quote requiring durable temporary bytes"
        receipt = self.evidence(b"existing", "evidence/quotes/existing.txt")
        artifact = self.home / "evidence/quotes" / (sha(quote) + ".txt")
        real_fsync = os.fsync

        def refused_file_sync(fd):
            import stat
            if stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError("fixture sync failure")
            return real_fsync(fd)

        with mock.patch.object(os, "fsync", refused_file_sync):
            self.reject("hash_mismatch", lambda: self.ruling(quote=quote))
        self.assertFalse(artifact.exists())
        self.assertEqual([p.name for p in artifact.parent.iterdir()], ["existing.txt"])
        self.ruling(quote=quote)
        schema._evidence(receipt, self.ctx)
        self.assertEqual(artifact.read_bytes(), quote)

    def test_f2_episode_run_resolver_requires_provenance(self):
        self.runtime()
        self.open_run()
        candidate = unit("episode")
        candidate["provenance"].pop("run_id")
        for supplied in (None, RUN_ID):
            with self.subTest(supplied=supplied):
                self.reject("conflict", lambda: units._run(self.snapshot(), candidate, OWNER, supplied))
        candidate["provenance"]["run_id"] = RUN_ID
        self.assertEqual(self.write(candidate).value["unit"], candidate)

    def test_f3_append_replay_checks_draft_payload(self):
        self.runtime()
        self.write(unit(uid="unit_001"))
        self.write(unit(uid="unit_002"))
        payload = {"agent_id": OWNER, "unit_id": "unit_001"}
        command = self.api.Command("retire", {}, OWNER, "carbon-retire")
        render = lambda snapshot, event: {"payload": event["payload"], "head": snapshot.head}
        first = self.journal.append(self.api.EventDraft("memory.retire", payload),
                                    command=command, render=render, ctx=self.ctx)
        replay = self.journal.append(self.api.EventDraft("memory.retire", deepcopy(payload)),
                                     command=replace(command, expected_head=0), render=render, ctx=self.ctx)
        self.assertEqual(first.value, replay.value)
        changed = dict(payload, unit_id="unit_002")
        self.reject("bad_op", lambda: self.journal.append(self.api.EventDraft("memory.retire", changed),
                    command=command, render=render, ctx=self.ctx))
        self.assertEqual(units.get(OWNER, "unit_002", ctx=self.ctx)["unit"]["status"], "active")

    def test_f3_transact_accepts_plain_prepare_callback(self):
        self.runtime()
        for index, tool in enumerate(("retire", "memory.retire"), 1):
            value = unit(uid="unit_%03d" % index)
            self.write(value)
            payload = {"agent_id": OWNER, "unit_id": value["id"]}
            command = self.api.Command(tool, payload, OWNER, "plain-prepare-%d" % index)
            prepare = lambda snapshot: self.api.EventDraft("memory.retire", deepcopy(payload))
            render = lambda snapshot, event: {"head": snapshot.head, "event": event}
            first = self.journal.transact(command, prepare, render, ctx=self.ctx)
            self.assertEqual(first.event["kind"], "memory.retire")
            self.assertEqual(units.get(OWNER, value["id"], ctx=self.ctx)["unit"]["status"], "retired")
            before = self.fingerprint()
            self.assertEqual(self.journal.transact(command, prepare, render, ctx=self.ctx).value, first.value)
            self.assertEqual(self.fingerprint(), before)

    def test_f4_dispatch_resolves_context_registry(self):
        self.runtime()
        self.write()
        context = SimpleNamespace(home=self.home, registry=self.registry)
        result = app.dispatch("memory_get", {"agent_id": OWNER, "unit_id": "unit_001"}, context=context)
        self.assertEqual(result.payload, {"untrusted": units.get(OWNER, "unit_001", ctx=self.ctx)})

    def test_f4_dispatch_constructs_missing_context(self):
        self.runtime()
        self.write()
        with mock.patch.dict(os.environ, {"LINEAGE_HOME": str(self.home)}):
            result = app.dispatch("memory_get", {"agent_id": OWNER, "unit_id": "unit_001"}, registry=self.registry)
        self.assertIsNone(result.failure)
        self.assertEqual(result.payload["untrusted"]["unit"]["id"], "unit_001")

    def test_f4_native_context_without_explicit_registry(self):
        self.runtime()
        self.write()
        with mock.patch.object(registry, "load", return_value=self.registry):
            context = app.create_context(self.home, registry=self.registry)
            result = app.dispatch("memory_get", {"agent_id": OWNER, "unit_id": "unit_001"}, context=context)
        self.assertIsNone(result.failure)
        self.assertEqual(result.payload["untrusted"]["unit"]["id"], "unit_001")

    def test_f4_sibling_read_defaults_actor_without_escalation(self):
        self.runtime()
        observed = []

        def read(args, ctx):
            observed.append((deepcopy(args), ctx.actor, ctx.authority))
            return {"actor": ctx.actor}

        read._memory_contract = True
        definition = {"type": "object", "properties": {"agent": {"type": "string"}},
                      "additionalProperties": False}
        spec = self.api.ToolSpec("other_read", "Inspect a sibling domain.", definition, "read", read)
        chosen = SimpleNamespace(tools={"other_read": spec}, validators=self.registry.validators,
                                 folds=self.registry.folds)
        context = replace(self.ctx, services=replace(self.ctx.services, registry=chosen),
                          actor="operator", authority="operator")
        self.assertEqual(app.dispatch("other_read", {}, ctx=context), {"untrusted": {"actor": "system"}})
        self.assertEqual(observed, [({"agent": "system"}, "system", "tool")])

    def test_f4_mcp_accepts_positional_streams(self):
        self.runtime()
        self.write()
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "memory_get", "arguments": {"agent_id": OWNER, "unit_id": "unit_001"}}}
        incoming, outgoing = io.BytesIO(canonical(request) + b"\n"), io.StringIO()
        with mock.patch.object(registry, "load", return_value=self.registry), \
                mock.patch.dict(os.environ, {"LINEAGE_HOME": str(self.home)}):
            self.assertEqual(mcp.main(incoming, outgoing), 0)
        response = json.loads(outgoing.getvalue())
        self.assertFalse(response["result"]["isError"])
        self.assertEqual(json.loads(response["result"]["content"][0]["text"])["untrusted"]["unit"]["id"], "unit_001")

    def test_f5_capacity_preserves_bounded_cut_diagnostics(self):
        self.runtime()
        detail = "byte capacity exceeded; cuts candidates: unit_001"
        with mock.patch.object(self.entry_module, "build", side_effect=LineageError("memory_debt", detail)):
            caught = self.reject("memory_debt", lambda: self.write())
        self.assertEqual(caught.detail, detail)
        self.write()

    def test_f5_draft_source_is_not_inheritable(self):
        self.runtime()
        source = self.shaped()
        source["status"] = "draft"
        self.write(source)
        candidate = unit(uid="unit_002")
        candidate["provenance"]["inherited_from"] = {
            "agent_id": OWNER, "unit_id": source["id"], "unit_sha256": sha(canonical(source))}
        self.reject("conflict", lambda: self.write(candidate))
        active = self.shaped(uid="unit_003")
        self.write(active)
        candidate["provenance"]["inherited_from"].update(unit_id=active["id"], unit_sha256=sha(canonical(active)))
        self.write(candidate)

    def test_f5_schema_load_returns_defensive_copy(self):
        self.runtime()
        store = schema._SchemaStore(self.ctx.services.repo_root / "schemas")
        loaded = store.load("mem_unit.schema.json")
        expected = deepcopy(loaded)
        loaded["properties"]["kind"].clear()
        loaded.clear()
        self.assertEqual(store.load("mem_unit.schema.json"), expected)
