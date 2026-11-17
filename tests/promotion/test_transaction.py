"""Real-boundary refusal tests and explicit unmet integration obligations.

A17/A19/A20/A21/A22/A23 positive transaction acceptance is BLOCKED/HOLD.
No synthetic History is installed using a permissive production validator.
"""
from copy import deepcopy
from functools import partial  # A-U19: bind the integrated owner validator runtime context.
import multiprocessing
import fcntl
import hashlib
import itertools
import io
import shutil
from email.message import Message
from types import SimpleNamespace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lineage.core import app, journal
from lineage.core.errors import LineageError
from lineage.core.registry import load, Context, Services  # A-U19: integrated arena fixture services.
from lineage.domain import promotion
from lineage.ext import promotion as extension
from tests.promotion.test_dispatch import ARGS
from tests.promotion.test_evaluate import (BASE, CHILD, CONFIRM, SELECT, SEAT, UNKNOWN_COST, Fixture, canonical,
                                         PolicyCase, TEST_ROOT)


# Child process target is module-level and uses only exact owned handles.
def _race_probe(history, release, arrived, replies):
    from lineage.domain.promotion import evaluate
    from tests.promotion.test_evaluate import CHILD, SELECT, SEAT
    arrived.set()
    if not release.wait(1.0):
        replies.put(("failure", "barrier_timeout"))
        return
    try:
        result = evaluate(history, CHILD, SELECT, seat=dict(SEAT))
        replies.put(("result", result))
    except NotImplementedError as exc:
        replies.put(("stub", str(exc)))
    except LineageError as exc:
        replies.put(("domain", exc.code))


def _locked_mutation(home, tool, args, release, arrived, replies):
    from lineage.core import app
    from lineage.core.registry import load
    registry = load()
    context = app.create_context(home, registry=registry)
    arrived.set()
    if not release.wait(2.0):
        replies.put({"ok": False, "code": "internal"})
        return
    replies.put(app.dispatch(tool, args, context=context, registry=registry).payload)


class TransactionTests(PolicyCase):
    def setUp(self):
        # A-U19: fixture services carry the integrated runner's deterministic clock.
        self.temp = tempfile.TemporaryDirectory(prefix="runtime-", dir=TEST_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.registry = load()
        self.context = app.create_context(self.temp.name, registry=self.registry)
        # A-U19: the integrated fake arena runner requires an explicitly injected virtual clock.
        self.sequence = itertools.count(1)
        self.virtual_ticks = itertools.count(2000)
        ticks = itertools.count(1000)
        self.clock_patch = patch("time.time_ns", side_effect=lambda: next(ticks) * 1000000)
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)
        identifiers = itertools.count(1)
        ids_patch = patch("secrets.token_hex", side_effect=lambda n: format(next(identifiers), f"0{2*n}x"))
        ids_patch.start()
        self.addCleanup(ids_patch.stop)

    def ledger_bytes(self):
        # A-U19: compare committed bytes; native locking can materialize an empty ledger on refusal.
        p = self.context.home / "ledger/main/events.jsonl"
        return p.read_bytes() if p.exists() else b""

    def command(self, args):
        cmd = {"tool": "agent_promote", "args": deepcopy(args),
               "agent": args["agent"], "op_id": args["op_id"]}
        if "expected_head" in args:
            cmd["expected_head"] = args["expected_head"]
        return cmd

    def require_owners(self):
        required_tools = {"agent_create", "agent_get", "agent_retire", "run_open", "run_close",
                          "bench_declare", "bench_run", "bench_verdict"}
        required_validators = {"agent.born", "agent.status", "run.open", "run.close",
                               "bench.declared", "bench.result", "bench.verdict"}
        missing = sorted(required_tools - set(self.registry.tools)) + sorted(required_validators - set(self.registry.validators))
        self.assertEqual(missing, [], "BLOCKED/HOLD: real owner seams absent: " + ", ".join(missing))
        schema = __import__("json").loads((TEST_ROOT.parents[1] / "schemas/event.schema.json").read_text())
        payload = next(r["then"]["properties"]["payload"] for r in schema["allOf"]
                       if r.get("if", {}).get("properties", {}).get("kind", {}).get("const") == "agent.status")
        self.assertIn("seat", payload["properties"], "BLOCKED/HOLD: frozen complete-seat shape is AUSENTE")
        # Passing these checks is a readiness witness only. Full acceptance
        # still requires a real committed lifecycle and its receipts.

    def public(self, tool, args, *, home=None):
        context = self.context if home is None else app.create_context(home, registry=self.registry)
        result = app.dispatch(tool, args, context=context, registry=self.registry)
        self.assertIsNone(result.failure, f"{tool} refused a required real fixture: {result.payload}")
        self.assertEqual(set(result.payload), {"untrusted"})
        return result.payload["untrusted"]

    def mutation(self, tool, args, *, actor="creator-agent", op_id=None):
        # A-U19: seed through the installed arena handler; native dispatch cannot resolve its declaration $ref.
        effective = dict(args, agent=actor, op_id=op_id or f"fixture_{next(self.sequence):08d}")
        if tool in {"bench_declare", "bench_run", "bench_verdict"}:
            # A-U19: bank.load reads services.repo_root, so bind the temporary bank fixture explicitly.
            ctx = Context(Services(self.context.home, self.context.home, self.registry,
                                   clock=lambda: next(self.virtual_ticks)), actor=actor)
            return self.registry.tools[tool].handler(effective, context=ctx)
        return self.public(tool, effective)

    def seed_selection(self):
        # A-U19: the fixture bank root is supplied through the integrated arena Services adapter.
        # A stub must fail before any positive integration prerequisites are
        # mistaken for completed behavior.
        self.admits(Fixture().bench())
        self.require_owners()
        pins = [{"id": ref, "sha256": self.public("reference_verify", {"ref_id": ref})["sha256"]}
                for ref in ("gold_s1", "memory_v21")]
        for agent in (BASE, CHILD):
            self.mutation("agent_create", {"agent_id": agent, "display_name": agent,
                "workflow": "test", "language": "python", "allowed_seats": [dict(SEAT)],
                "references": pins, "skills": [], "overlays": []})
        self.selection = Fixture().bench().payload("bench.declared")
        tasks = []
        for split, prefix in (("select", "select"), ("heldout", "holdout")):
            for i in range(3):
                outcome = lambda verdict: {"verdict": verdict, "repair_loops": 0,
                                           "findings": {"confirmed": 0, "refuted": 0}}
                tasks.append({"id": f"{prefix}_{i:04d}", "split": split, "kind": "unit",
                    "language": "python", "prompt": "Synthetic lifecycle fixture.",
                    "expected": {"baseline": outcome("green" if i == 0 else "error"),
                                 "candidate": outcome("green")}})
        bank = {"schema": "lineage.bank/v1", "bank_id": "demo-offline", "tasks": tasks}
        raw = canonical(bank)
        pin = hashlib.sha256(raw).hexdigest()
        parent = self.context.home / "arena/banks/demo-offline"
        parent.mkdir(parents=True)
        (parent / "bank.json").write_bytes(raw + b"\n")
        (parent / "MANIFEST.sha256").write_text(hashlib.sha256(raw + b"\n").hexdigest() + "  bank.json\n", encoding="ascii")
        self.selection["bank_sha256"] = pin
        self.mutation("bench_declare", {"declaration": self.selection})
        self.mutation("bench_run", {"bench_id": SELECT, "runner": {"kind": "fake", "seed": 0}})
        self.mutation("bench_verdict", {"bench_id": SELECT})

    def commit_promotion(self, *, op_id="promote_001", bench=SELECT):
        before = journal.snapshot(self.context.home)
        args = dict(ARGS, bench_id=bench, op_id=op_id)
        value = self.public("agent_promote", args)
        after = journal.snapshot(self.context.home)
        self.assertEqual(len(after), len(before) + 1)
        self.assertEqual(after[-1]["kind"], "agent.status")
        self.assertEqual(value["record"]["promoted_seat"], SEAT)
        self.assertEqual(value["commit"]["event_ids"], [after[-1]["id"]])
        self.assertEqual(value["commit"]["head"], after[-1]["lamport"])
        return value, args, after[-1]

    def failed_dispatch(self, args, code, tool="agent_promote"):
        before = self.ledger_bytes()
        prefix = journal.snapshot(self.context.home)
        result = app.dispatch(tool, args, context=self.context, registry=self.registry)
        self.assertEqual(result.payload.get("code"), code)
        self.assertEqual(result.payload.get("ok"), False)
        self.assertEqual(result.failure, "execution")
        self.assertEqual(self.ledger_bytes(), before)
        self.assertEqual(journal.snapshot(self.context.home), prefix)
        return result

    def test_a18_fresh_stale_head_precedes_policy_when_owners_ready(self):
        before = self.ledger_bytes()
        # The immutable-fixture probe supplies the fail-first behavior witness;
        # it is never substituted for a real production append.
        self.admits(Fixture().bench())
        self.require_owners()
        args = dict(ARGS, expected_head=999)
        with self.assertRaises(LineageError) as caught:
            self.invoke(promotion.promote, CHILD, SELECT, command=self.command(args), ctx=self.context)
        self.assertEqual(caught.exception.code, "stale_rev")
        self.assertEqual(self.ledger_bytes(), before)

    def test_a17_replay_after_retirement_integration_prerequisites(self):
        self.seed_selection()
        original, args, event = self.commit_promotion()
        self.mutation("agent_retire", {"agent_id": CHILD, "reason": "synthetic replay contrast"})
        retired = self.public("agent_get", {"agent_id": CHILD})["record"]
        self.assertEqual(retired["status"], "retired")
        before = self.ledger_bytes()
        replay = self.public("agent_promote", dict(args, expected_head=0))
        self.assertEqual(canonical(replay), canonical(original))
        self.assertEqual(self.ledger_bytes(), before)
        self.assertEqual(replay["commit"]["head"], event["lamport"])
        self.assertNotIn("replay", replay)

    def test_a18_changed_tool_and_request_replay_integration_prerequisites(self):
        self.seed_selection()
        original, args, _ = self.commit_promotion()
        for changed in (dict(args, agent_id=BASE), dict(args, bench_id="other_001")):
            self.failed_dispatch(changed, "bad_op")
        self.failed_dispatch({"agent_id": CHILD, "reason": "different tool",
                              "agent": args["agent"], "op_id": args["op_id"]}, "bad_op", "agent_retire")
        before = self.ledger_bytes()
        self.assertEqual(self.public("agent_promote", dict(args, expected_head=0)), original)
        self.assertEqual(self.ledger_bytes(), before)
        self.failed_dispatch(dict(args, op_id="fresh_001"), "conflict")

    def test_a20_direct_append_owner_validator_integration_prerequisites(self):
        # A-U19: the registered U12 status validator requires ctx; bind it without replacing its policy.
        self.seed_selection()
        validators = {"agent.status": partial(self.registry.validators["agent.status"], ctx=self.context)}
        prefix = journal.snapshot(self.context.home)
        transition = self.invoke(promotion.evaluate, prefix, CHILD, SELECT, seat=dict(SEAT))
        valid = dict(transition, agent_id=CHILD, seat=dict(SEAT))
        cases = [(dict(valid, bench_id="missing_001"), "no_benchmark"),
                 (dict(valid, **{"from": "shadow"}), "conflict"),
                 (dict(valid, agent_id=BASE), "conflict"),
                 (dict(valid, seat=dict(SEAT, effort="high")), "bad_args"),
                 (dict(valid, to="promoted"), "conflict")]
        for i, (payload, code) in enumerate(cases):
            before = self.ledger_bytes()
            with self.subTest(case=i), self.assertRaises(LineageError) as caught:
                journal.transact(self.context.home, agent="creator-agent", op_id=f"bypass_{i:08d}",
                                 kind="agent.status", payload=payload,
                                 validators=validators)
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(self.ledger_bytes(), before)
        # Positive control proves the installed owner is not always rejecting.
        event = journal.transact(self.context.home, agent="creator-agent", op_id="direct_valid_001",
                                 kind="agent.status", payload=valid, validators=validators)
        self.assertEqual(event["payload"]["to"], "shadow")
        record = self.public("agent_get", {"agent_id": CHILD})["record"]
        self.assertEqual(record["status"], "shadow")
        self.assertEqual(record["promoted_seat"], SEAT)

    def test_a21_commit_prefix_and_defensive_replay_integration_prerequisites(self):
        self.seed_selection()
        before_record = self.public("agent_get", {"agent_id": CHILD})["record"]
        original, args, event = self.commit_promotion()
        raw = self.ledger_bytes()
        committed_prefix = b"".join(raw.splitlines(keepends=True)[:event["lamport"]])
        self.assertEqual(original["commit"]["sha256"], hashlib.sha256(committed_prefix).hexdigest())
        for key in ("constitution_sha256", "skills", "memory_gen", "agent_version"):
            self.assertEqual(original["record"][key], before_record[key])
        saved = deepcopy(original)
        original["record"]["status"] = "retired"
        original["commit"]["event_ids"].clear()
        self.assertEqual(self.public("agent_promote", args), saved)
        self.assertEqual(self.ledger_bytes(), raw)

    def test_a22_append_fsync_rollback_integration_prerequisites(self):
        self.seed_selection()
        before = self.ledger_bytes()
        native_fsync = os.fsync
        failed = False
        def fail_once(fd):
            nonlocal failed
            if not failed:
                failed = True
                raise OSError("synthetic durability refusal")
            return native_fsync(fd)
        with patch("os.fsync", side_effect=fail_once):
            result = app.dispatch("agent_promote", dict(ARGS), context=self.context, registry=self.registry)
        self.assertTrue(failed, "test did not reach the durability boundary")
        self.assertEqual(result.payload.get("code"), "internal")
        self.assertEqual(self.ledger_bytes(), before)
        self.assertEqual(self.public("agent_get", {"agent_id": CHILD})["record"]["status"], "draft")

    def test_a23_real_transport_parity_integration_prerequisites(self):
        # A-U19: native family mailboxes require explicit private recipient-directory permissions.
        self.seed_selection()
        from lineage.core import cli, envelope, jsonlane, mcp, registry as registry_api
        from lineage.serve import http
        config = {"endpoint": "oracle-target", "sources": ["oracle-source"], "tools": ["agent_promote"]}
        for rejected in (False, True):
            request = {"schema": "lineage.family/1", "id": "rejected_001" if rejected else "admitted_001",
                "source": "oracle-source", "target": "oracle-target", "kind": "call", "agent": ARGS["agent"],
                "payload": {"tool": "agent_promote", "args": {"agent_id": CHILD,
                   "bench_id": "missing_001" if rejected else SELECT}}}
            args = dict(request["payload"]["args"], agent=ARGS["agent"], op_id=envelope.operation_id(request))
            results, effects = [], []
            for transport in ("cli", "mcp", "json", "http"):
                with self.subTest(rejected=rejected, transport=transport), tempfile.TemporaryDirectory(prefix="parity-", dir=TEST_ROOT) as destination:
                    home = Path(destination) / "home"
                    shutil.copytree(self.context.home, home)
                    context = app.create_context(home, registry=self.registry)
                    (home / "family").mkdir(mode=0o700)
                    endpoint = home / "family/oracle-target"
                    endpoint.mkdir(mode=0o700)
                    (endpoint / "config.json").write_bytes(canonical(config) + b"\n")
                    (endpoint / "config.json").chmod(0o600)
                    out, err = io.StringIO(), io.StringIO()
                    with patch("time.time_ns", return_value=10000000000), patch("secrets.token_hex", side_effect=lambda n: "f" * (2*n)):
                        if transport == "cli":
                            rc = cli.main(["--home", str(home), "call", "agent_promote", "--json", canonical(args).decode()],
                                          stdout=out, stderr=err, registry=self.registry)
                            self.assertEqual(rc, 3 if rejected else 0)
                            result = json.loads(out.getvalue())
                        elif transport == "mcp":
                            rpc = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                   "params": {"name": "agent_promote", "arguments": args}}
                            rc = mcp.main(context=context, registry=self.registry, stdin=io.BytesIO(canonical(rpc)+b"\n"), stdout=out, stderr=err)
                            self.assertEqual(rc, 0)
                            response = json.loads(out.getvalue())["result"]
                            self.assertIs(response["isError"], rejected)
                            result = json.loads(response["content"][0]["text"])
                        elif transport == "json":
                            rc = jsonlane.main([], context=context, registry=self.registry,
                                  stdin=io.BytesIO(canonical(request)), stdout=out, stderr=err)
                            self.assertEqual(rc, 3 if rejected else 0)
                            result = json.loads(out.getvalue())["result"]
                        else:
                            # Exercise the installed HTTP parser/auth/dispatch
                            # in memory, without a socket or network listener.
                            body = canonical({"tool": "agent_promote", "args": args})
                            handler = http._Handler.__new__(http._Handler)
                            # A-U19: the integrated HTTP provider owns a native call_context service.
                            services = SimpleNamespace(home=home, registry=self.registry, call_context=context)
                            handler.server = SimpleNamespace(ctx=http.Context(services),
                                fixture_data=None, authority="127.0.0.1:0", token="synthetic-session")
                            handler.headers = Message()
                            for key, value in {"Host": "127.0.0.1:0", "Origin": "http://127.0.0.1:0",
                                "X-Lineage-Session": "synthetic-session", "Content-Type": "application/json",
                                "Content-Length": str(len(body))}.items():
                                handler.headers[key] = value
                            handler.command = "POST"; handler.path = "/api/call"
                            # A-U19: the installed HTTP parser reads BaseHTTPRequestHandler.raw_requestline.
                            handler.raw_requestline = b"POST /api/call HTTP/1.1\r\n"
                            handler.request_version = "HTTP/1.1"; handler.requestline = "POST /api/call HTTP/1.1"
                            handler.rfile = io.BytesIO(body); handler.wfile = io.BytesIO()
                            handler._handle()
                            headers, raw = handler.wfile.getvalue().split(b"\r\n\r\n", 1)
                            self.assertIn(b"404" if rejected else b"200", headers.split(b"\r\n",1)[0])
                            result = json.loads(raw)
                    if rejected:
                        self.assertEqual(result.get("code"), "no_benchmark")
                        self.assertEqual(result.get("ok"), False)
                    else:
                        self.assertEqual(set(result), {"untrusted"})
                    results.append(canonical(result))
                    effects.append((home / "ledger/main/events.jsonl").read_bytes())
            self.assertEqual(len(set(results)), 1)
            self.assertEqual(len(set(effects)), 1)

    def test_a28_synthetic_lifecycle_integration_prerequisites(self):
        self.seed_selection()
        first, _, _ = self.commit_promotion()
        self.assertEqual(first["record"]["status"], "shadow")
        for i in range(2):
            run_id = f"clean_{i:08d}"
            task = {"id": f"clean_task_{i:04d}", "kind": "unit", "language": "python"}
            self.mutation("run_open", {"run_id": run_id, "agent_id": CHILD, "seat": dict(SEAT),
                "task": task, "parents_context": [], "memory_arm": "own"}, actor=CHILD)
            outcome = {"verdict": "green", "repair_loops": 0, "findings": {"confirmed": 0, "refuted": 0}}
            f = Fixture()
            unit_id = f.unit({"run_id": run_id, "agent_id": CHILD, "task": task,
                              "seat": SEAT, "outcome": outcome, "cost": UNKNOWN_COST})
            unit = f.events[-1]["payload"]["unit"]
            unit["id"] = f"clean_mem_{i:04d}"
            unit["receipts"] = []
            self.mutation("memory_put", {"agent_id": CHILD, "run_id": run_id, "unit": unit}, actor=CHILD)
            self.mutation("run_close", {"run_id": run_id, "outcome": outcome,
                                       "cost": dict(UNKNOWN_COST)}, actor=CHILD)
        confirm = deepcopy(self.selection)
        confirm.update(bench_id=CONFIRM, purpose="confirm")
        confirm["promotion"]["n_shadow_runs"] = 1
        self.mutation("bench_declare", {"declaration": confirm})
        self.mutation("bench_run", {"bench_id": CONFIRM, "runner": {"kind": "fake", "seed": 0}})
        self.mutation("bench_verdict", {"bench_id": CONFIRM})
        final, _, _ = self.commit_promotion(op_id="promote_confirm_001", bench=CONFIRM)
        self.assertEqual(final["record"]["status"], "promoted")
        self.assertEqual(final["record"]["promoted_seat"], SEAT)

    def test_a22_dependency_read_failure_sanitized_before_append(self):
        self.seed_selection()
        before = self.ledger_bytes()
        with patch.object(journal, "_read", side_effect=OSError("synthetic private diagnostic")) as injection:
            with self.assertRaises(LineageError) as caught:
                self.invoke(promotion.promote, CHILD, SELECT,
                            command=self.command(ARGS), ctx=self.context)
            injection.assert_called()
        self.assertEqual(caught.exception.code, "internal")
        self.assertNotIn("synthetic private diagnostic", str(caught.exception.detail))
        self.assertNotIn(str(self.context.home), str(caught.exception.detail))
        self.assertEqual(self.ledger_bytes(), before)

    def test_a19_process_barrier_probe_and_retirement_race_prerequisites(self):
        # Real process/barrier mechanics are executable; no sleep, group or
        # broad signal exists. This pure probe is NOT a journal race receipt.
        mp = multiprocessing.get_context("spawn")
        release, arrived, replies = mp.Event(), mp.Event(), mp.Queue()
        process = mp.Process(target=_race_probe,
                             args=(Fixture().bench().history(), release, arrived, replies))
        process.start()
        try:
            self.assertTrue(arrived.wait(1.0), "child did not reach explicit barrier")
            release.set()
            kind, value = replies.get(timeout=1.0)
            if kind == "stub":
                self.fail("U19 stub: process reached callable policy (" + value + ")")
            self.assertEqual(kind, "result")
            self.assertEqual(value["to"], "shadow")
        finally:
            release.set()
            process.join(0.5)
            if process.is_alive():
                self.assertIsNotNone(process.pid)
                self.assertGreater(process.pid, 1)
                process.terminate()  # exact verified child started above
                process.join(0.5)
            self.assertFalse(process.is_alive(), "owned child did not terminate")
            replies.close()
            replies.join_thread()
        self.seed_selection()
        for first in ("retire", "promote"):
            with self.subTest(first=first), tempfile.TemporaryDirectory(prefix="race-", dir=TEST_ROOT) as destination:
                home = Path(destination) / "home"
                shutil.copytree(self.context.home, home)
                releases = {key: mp.Event() for key in ("retire", "promote")}
                arrivals = {key: mp.Event() for key in releases}
                queues = {key: mp.Queue() for key in releases}
                requests = {
                    "retire": ("agent_retire", {"agent_id": CHILD, "reason": "synthetic retirement race",
                               "agent": ARGS["agent"], "op_id": "race_retire_001"}),
                    "promote": ("agent_promote", dict(ARGS, op_id="race_promote_001")),
                }
                children = {key: mp.Process(target=_locked_mutation,
                    args=(home, *requests[key], releases[key], arrivals[key], queues[key])) for key in releases}
                try:
                    for child in children.values(): child.start()
                    for ready in arrivals.values(): self.assertTrue(ready.wait(1.0))
                    second = "promote" if first == "retire" else "retire"
                    releases[first].set()
                    first_result = queues[first].get(timeout=1.0)
                    self.assertEqual(set(first_result), {"untrusted"})
                    releases[second].set()
                    second_result = queues[second].get(timeout=1.0)
                    if first == "retire":
                        self.assertEqual(second_result.get("code"), "conflict")
                    else:
                        self.assertEqual(set(second_result), {"untrusted"})
                    context = app.create_context(home, registry=self.registry)
                    record = app.dispatch("agent_get", {"agent_id": CHILD}, context=context,
                                          registry=self.registry).payload["untrusted"]["record"]
                    self.assertEqual(record["status"], "retired")
                    self.assertNotIn("promoted_seat", record)
                    statuses = [e["payload"]["to"] for e in journal.snapshot(home) if e["kind"] == "agent.status"]
                    self.assertEqual(statuses[-2:] if first == "promote" else statuses[-1:],
                                     ["shadow", "retired"] if first == "promote" else ["retired"])
                finally:
                    for release in releases.values(): release.set()
                    for child in children.values():
                        if child.pid is None: continue
                        child.join(0.3)
                        if child.is_alive():
                            self.assertGreater(child.pid, 1)
                            child.terminate()
                            child.join(0.3)
                        self.assertFalse(child.is_alive())
                    for queue in queues.values():
                        queue.close(); queue.join_thread()

    def test_a22_held_existing_lock_yields_busy_without_append(self):
        parent = self.context.home / "ledger/main"
        parent.mkdir(parents=True)
        lock_path = parent / "events.lock"
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            before = self.ledger_bytes()
            with self.assertRaises(LineageError) as caught:
                self.invoke(promotion.promote, CHILD, SELECT,
                            command=self.command(ARGS), ctx=self.context)
            self.assertEqual(caught.exception.code, "busy")
            self.assertEqual(self.ledger_bytes(), before)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
