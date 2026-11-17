"""Test-only fixtures. U02/U03/U04 are never emulated or monkeypatched.

The initial valid-unit positive control reaches the U10 stub before any optional
integration setup. Missing frozen dependencies subsequently fail with an explicit
assertion, never an import error or a skipped/passing integration test.
"""
from __future__ import annotations

import copy
from contextlib import ExitStack, contextmanager
import hashlib
import importlib
import itertools
import json
import sys
import tempfile
import types
import unittest
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from unittest import mock

from lineage.domain.memory import fold, schema, units

ROOT = Path(__file__).resolve().parents[3]
TEST_ROOT = Path(__file__).resolve().parent
OWNER = "agent-one"
OTHER = "agent-two"
RUN_ID = "run_0001"
TASK_ID = "task_001"
SAFE = 9007199254740991
SEAT = {"model": "fixture-model", "effort": "medium", "mode": "headless"}
OUTCOME = {"verdict": "green", "repair_loops": 0,
           "findings": {"confirmed": 0, "refuted": 0}}
COST = dict.fromkeys(("tokens_in", "tokens_out", "tokens_cache", "duration_ms", "cost_micro_usd"))


def canonical(value):
    """Independent expected-byte calculation, never a production decoder."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unit(kind="lesson", level=3, *, uid="unit_001", actor=OWNER, receipt=None):
    bodies = {
        "ruling": {"quote_sha256": sha(b"fixture ruling"), "how_to_apply": "fixture ruling"},
        "lesson": {"tempting_use": "reuse", "failure_mode": "stale input",
                   "safer_action": "verify", "blocked_use": []},
        "negative": {"gate_id": "fixture-gate", "verdict": "HOLD", "cause": "stale input",
                     "coordinate": "evidence/check.txt", "safer_action": "verify"},
        "workflow": {"trigger_sig": "fixture", "steps": ["verify"],
                     "stats": {"runs": 0, "successes": 0, "mean_reward": None},
                     "status": "candidate"},
        "episode": {"run_id": RUN_ID, "task_id": TASK_ID, "seat": copy.deepcopy(SEAT),
                    "outcome": copy.deepcopy(OUTCOME), "cost": copy.deepcopy(COST),
                    "parents_context": []},
        "decision": {"reason": "verify input"},
        "open_item": {"class": "followup", "order": 0},
    }
    result = {"schema": "lineage.mem.unit/v1", "id": uid, "kind": kind,
              "level": level, "statement": "fixture ruling" if kind == "ruling" else "verify input",
              "status": "active", "privacy": "internal",
              "scope": {"workflow": "develop", "language": "python"},
              "provenance": {"origin": "test-only", "actor": actor},
              "receipts": [copy.deepcopy(receipt)] if receipt else [], "supersedes": [],
              "body": bodies[kind]}
    if kind == "episode":
        result["provenance"]["run_id"] = RUN_ID
    return result


def agent_record(agent_id=OWNER, *, memory_gen=0, parent=None):
    return {"schema": "lineage.agent/v1", "agent_id": agent_id, "display_name": agent_id,
            "workflow": "develop", "language": "python", "allowed_seats": [copy.deepcopy(SEAT)],
            "references": [{"id": name, "sha256": sha(name.encode())}
                           for name in ("gold_s1", "memory_v21")],
            "constitution_sha256": sha(b"fixture constitution\n"), "skills": [],
            "memory_gen": memory_gen, "brief_head_sha256": sha(b"fixture brief\n"),
            "agent_version": sha(b"fixture version"), "generation": int(parent is not None),
            "parents": [parent] if parent else [],
            "born": {"op": "clone" if parent else "genesis", "event_id": "e-0000000000000001"},
            "status": "draft"}


def birth_payload(agent_id=OWNER, *, inherited=(), memory_gen=0, parent=None):
    return {"record": agent_record(agent_id, memory_gen=memory_gen, parent=parent),
            "inherited_units": copy.deepcopy(list(inherited)), "rejected_units": [],
            "constitution": {"text": "fixture constitution\n", "overlays": [], "rule_ids": []}}


def event(kind, payload, n=1, *, actor=OWNER):
    value = {"schema": "lineage.event/v1", "id": "e-%016x" % n, "lamport": n,
             "ts": n, "ledger": "main", "agent": actor, "kind": kind,
             "payload": copy.deepcopy(payload), "op_id": "fixture-%d" % n,
             "request_sha256": sha(b"fixture request"), "evidence": [],
             "prev_sha256": "0" * 64}
    value["sha256"] = sha(canonical(value))
    return value


def put_event(value, n=1, owner=OWNER):
    return event("memory.put", {"agent_id": owner, "unit": value}, n,
                 actor=value["provenance"]["actor"])


class OracleCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".oracle-", dir=TEST_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        services = SimpleNamespace(home=self.home, repo_root=ROOT, registry=None,
                                   clock=lambda: 1, id_factory=lambda: "e-0000000000000001",
                                   token_count=lambda text: 1)
        self.ctx = SimpleNamespace(services=services, actor=OWNER, authority="tool",
                                   transport="library")
        registry = importlib.import_module("lineage.core.registry")
        if all(hasattr(registry, name) for name in ("Context", "Services")):
            services = registry.Services(self.home, ROOT, None, services.clock,
                                         services.id_factory, services.token_count)
            self.ctx = registry.Context(services, OWNER)
        # A genuine valid-input positive control, not an expected-stub assertion.
        self.assertIsNone(schema.validate_unit(unit(), authority="tool", actor=OWNER, ctx=self.ctx))

    @contextmanager
    def patch_seam(self, module, name, replacement):
        """Patch a public seam and any imported aliases, without assuming local names."""
        original = getattr(module, name)
        references = [(module, name)]
        if original is not None:
            for loaded in tuple(sys.modules.values()):
                if loaded is None or not getattr(loaded, "__name__", "").startswith("lineage."):
                    continue
                references.extend((loaded, key) for key, value in tuple(vars(loaded).items())
                                  if value is original and (loaded is not module or key != name))
        with ExitStack() as stack:
            for owner, key in references:
                stack.enter_context(mock.patch.object(owner, key, replacement))
            yield

    def require(self, module, *names):
        try:
            loaded = importlib.import_module(module)
        except ModuleNotFoundError as exc:
            if exc.name != module:
                raise
            self.fail("AUSENTE — required frozen dependency: " + module)
        missing = [name for name in names if not hasattr(loaded, name)]
        self.assertFalse(missing, "AUSENTE — required frozen exports in %s: %s" % (module, missing))
        return loaded

    def error(self, code, callback):
        errors = self.require("lineage.core.errors", "LineageError")
        with self.assertRaises(errors.LineageError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def validate(self, value, *, authority="tool", actor=OWNER):
        context = self.ctx
        if authority == "operator":
            if isinstance(context, SimpleNamespace):
                context = SimpleNamespace(**{**vars(context), "actor": actor, "authority": authority})
            else:
                from dataclasses import replace
                context = replace(context, actor=actor, authority=authority)
        return schema.validate_unit(value, authority=authority, actor=actor, ctx=context)

    def evidence(self, raw=b"fixture evidence\n", path="evidence/check.txt"):
        dest = self.home / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        return {"path": path, "sha256": sha(raw)}

    def shaped(self, kind="lesson", level=2, **kwargs):
        return unit(kind, level, receipt=self.evidence() if level == 2 else None, **kwargs)

    def schema_store(self):
        api = self.require("lineage.core.schema", "SchemaStore", "validate", "decode", "canonical")
        return api, api.SchemaStore(ROOT / "schemas")

    def shape_check(self, value, name):
        api, store = self.schema_store()
        api.validate(value, store.load(name), store=store, base=name)


class IntegrationCase(OracleCase):
    """Real journal/dispatch; only pending agent/run policies and U11 are fixtures."""
    def runtime(self):
        if hasattr(self, "journal"):
            return
        self.api = self.require("lineage.core.registry", "Command", "Context", "Services",
                                "Committed", "EventDraft", "FoldSpec", "ToolSpec", "Snapshot")
        self.journal = self.require("lineage.core.journal", "snapshot", "transact", "append", "fold", "verify")
        self.require("lineage.core.errors", "LineageError")
        self.schema_store()
        self.ext = importlib.import_module("lineage.ext.memory")
        self.assertEqual(set(self.ext.VALIDATORS), {"memory.put", "memory.retire"})
        self.assertEqual(set(self.ext.FOLDS), {"memory"})

        def fixture_validate(snapshot, current, ctx):
            # U12/U13 policy admission is deliberately not claimed here.
            return None

        def fixture_agents(state, current):
            ns = state.setdefault("agents", {})
            payload = current["payload"]
            if current["kind"] == "agent.born":
                ns[payload["record"]["agent_id"]] = copy.deepcopy(payload["record"])
            elif current["kind"] == "agent.status":
                ns[payload["agent_id"]]["status"] = payload["to"]

        def fixture_runs(state, current):
            ns = state.setdefault("runs", {})
            payload = current["payload"]
            if current["kind"] == "run.open":
                ns[payload["run_id"]] = copy.deepcopy(payload)
                ns[payload["run_id"]].update(ts_open=current["ts"], ts_close=None)
            elif current["kind"] == "run.close":
                ns[payload["record"]["run_id"]] = copy.deepcopy(payload["record"])

        tools = {tool.name: tool for tool in self.ext.TOOLS}
        validators = dict(self.ext.VALIDATORS)
        validators.update({kind: fixture_validate for kind in
                           ("agent.born", "agent.status", "run.open", "run.close", "run.beat")})
        folds = dict(self.ext.FOLDS)
        folds["agents"] = self.api.FoldSpec(frozenset({"agent.born", "agent.status"}), 40, fixture_agents)
        folds["runs"] = self.api.FoldSpec(frozenset({"run.open", "run.close", "run.beat"}), 50, fixture_runs)
        self.registry = SimpleNamespace(tools=MappingProxyType(tools),
                                        validators=MappingProxyType(validators), folds=MappingProxyType(folds),
                                        names=lambda: frozenset(tools),
                                        descriptors=lambda: [{"name": t.name, "description": t.description,
                                                              "inputSchema": copy.deepcopy(t.input_schema)}
                                                             for t in sorted(tools.values(), key=lambda t: t.name)])
        self.seq = itertools.count(1)
        services = self.api.Services(self.home, ROOT, self.registry, lambda: 1000,
                                    lambda: "e-%016x" % next(self.seq), lambda text: 1)
        self.ctx = self.api.Context(services, OWNER)
        self.entry_calls = []
        module = types.ModuleType("lineage.domain.memory.entry")
        module.build = self._entry_build
        self.entry_module = module
        self.enterContext(mock.patch.dict(sys.modules, {module.__name__: module}))
        package = importlib.import_module("lineage.domain.memory")
        self.enterContext(mock.patch.object(package, "entry", module, create=True))
        self.born(OWNER)

    def _entry_build(self, agent, selected, *, token_count, max_bytes=6000, max_tokens=4000):
        """Test-only capacity oracle; no production rendering or projection publication."""
        self.entry_calls.append((copy.deepcopy(agent), copy.deepcopy(tuple(selected))))
        error = self.require("lineage.core.errors", "LineageError").LineageError
        if token_count is None:
            raise error("memory_debt", "cuts: verified counting unavailable")
        raw = ("\n".join(value["statement"] for value in selected) + "\n").encode("utf-8")
        try:
            count = token_count(raw.decode("utf-8"))
        except Exception:
            raise error("memory_debt", "cuts: verified counting failed") from None
        if type(count) is not int or count < 0 or len(raw) > max_bytes or count > max_tokens:
            raise error("memory_debt", "cuts: entry capacity exceeded")
        return raw

    def command(self, args=None, *, actor=None, tool="memory_put", op=None, expected=None):
        actor = actor or self.ctx.actor
        op = op or "operation-%d" % next(self.seq)
        args = copy.deepcopy(args or {})
        args.update(agent=actor, op_id=op)
        if expected is not None:
            args["expected_head"] = expected
        return self.api.Command(tool, args, actor, op, expected)

    def raw_append(self, kind, payload, *, actor=None, authority="tool", op=None, render=None):
        context = replace(self.ctx, actor=actor or self.ctx.actor, authority=authority)
        command = self.command(payload, actor=context.actor, tool="fixture_internal", op=op)
        def rendered(snapshot, current):
            return {"commit": {"event_ids": [current["id"]], "head": current["lamport"],
                               "sha256": current["sha256"]}}
        return self.journal.append(self.api.EventDraft(kind, copy.deepcopy(payload)), command=command,
                                   render=render or rendered, ctx=context)

    def born(self, owner, *, inherited=(), memory_gen=0, parent=None):
        return self.raw_append("agent.born", birth_payload(owner, inherited=inherited,
                                                         memory_gen=memory_gen, parent=parent))

    def open_run(self, *, owner=OWNER, run_id=RUN_ID, parents=()):
        payload = {"run_id": run_id, "agent_id": owner, "agent_version": sha(b"fixture version"),
                   "seat": copy.deepcopy(SEAT), "task": {"id": TASK_ID, "kind": "fixture", "language": "python"},
                   "parents_context": copy.deepcopy(list(parents)), "memory_arm": "own"}
        return self.raw_append("run.open", payload, actor=owner)

    def close_run(self, run_id=RUN_ID, owner=OWNER):
        record = {"schema": "lineage.run/v1", "run_id": run_id, "agent_id": owner,
                  "agent_version": sha(b"fixture version"), "ts_open": 1000, "ts_close": 1000,
                  "seat": copy.deepcopy(SEAT), "task": {"id": TASK_ID, "kind": "fixture", "language": "python"},
                  "outcome": copy.deepcopy(OUTCOME), "cost": copy.deepcopy(COST),
                  "memory": {"unit_ids": ["unit_001"], "levels": [2], "gate_passed": True},
                  "evidence": [], "parents_context": [], "memory_arm": "own"}
        return self.raw_append("run.close", {"record": record}, actor=owner)

    def write(self, value=None, *, owner=OWNER, actor=None, run_id=None, op=None, expected=None):
        self.runtime()
        value = value if value is not None else unit()
        args = {"agent_id": owner, "unit": copy.deepcopy(value)}
        if run_id is not None:
            args["run_id"] = run_id
        command = self.command(args, actor=actor, op=op, expected=expected)
        context = replace(self.ctx, actor=command.agent)
        return units.put(owner, value, run_id=run_id, command=command, ctx=context)

    def snapshot(self):
        return self.journal.snapshot(ctx=self.ctx)

    def fingerprint(self):
        path = self.home / "ledger/main/events.jsonl"
        raw = path.read_bytes() if path.exists() else b""
        snapshot = self.snapshot()
        return raw, snapshot.head, copy.deepcopy(snapshot.state)

    def reject(self, code, callback):
        before = self.fingerprint()
        caught = self.error(code, callback)
        self.assertEqual(self.fingerprint(), before, "rejection changed authoritative bytes/head/state")
        return caught

    def dispatch(self, name, args, *, ctx=None):
        app = self.require("lineage.core.app", "dispatch")
        return app.dispatch(name, copy.deepcopy(args), ctx=ctx or self.ctx)

    def reject_dispatch(self, code, name, args, *, ctx=None):
        before = self.fingerprint()
        result = self.dispatch(name, args, ctx=ctx)
        self.assertEqual(result.get("ok"), False)
        self.assertEqual(result.get("code"), code)
        self.assertLessEqual(set(result), {"ok", "code", "detail"})
        self.assertLessEqual(len(result.get("detail", "")), 2048)
        self.assertNotIn(str(self.home), result.get("detail", ""))
        self.assertNotIn("Traceback", result.get("detail", ""))
        self.assertEqual(self.fingerprint(), before)
        return result

    def ruling(self, quote=b"fixture ruling", *, owner=OWNER, op="caller-operation", context=None):
        context = context or replace(self.ctx, actor="operator", authority="operator")
        command = self.command({"agent_id": owner}, actor=context.actor, tool="operator_ruling", op=op)
        return units.operator_ruling(owner, quote, command=command, ctx=context)
