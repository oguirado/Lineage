"""Deterministic public-boundary fixtures, never a replacement arena engine.

The integrated U03/U04 APIs take home/history and CallContext respectively.
Command/Services below are test-side values for the U16 domain signature, since
those K0 records do not exist in the integrated registry. No run or memory gate
is simulated: lifecycle assertions inspect events written by the actual engine.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import importlib
import io
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from lineage.core import app, journal, registry, schema
from lineage.core.errors import LineageError
from lineage.domain.arena import bank, bench, runner

ROOT = Path(__file__).resolve().parents[2]
NOW = 1700000000000
SEAT = {"model": "offline-fixture", "effort": "medium", "mode": "headless"}
SEAT2 = {**SEAT, "effort": "high"}
COST = dict.fromkeys(("tokens_in", "tokens_out", "tokens_cache", "duration_ms", "cost_micro_usd"))
TOOL_NAMES = {"bench_list", "bench_declare", "bench_run", "bench_status", "bench_verdict"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def outcome(verdict="green", repairs=0):
    return {"verdict": verdict, "repair_loops": repairs,
            "findings": {"confirmed": 0, "refuted": 0}}


def task(index=1, split="select", baseline="red", candidate="green"):
    return {"id": f"task{index:08d}", "split": split, "kind": "test",
            "language": "python", "prompt": "Synthetic offline benchmark",
            "expected": {"baseline": outcome(baseline), "candidate": outcome(candidate)}}


def bank_data(tasks=None):
    return {"schema": "lineage.bank/v1", "bank_id": "demo-offline",
            "tasks": deepcopy(tasks if tasks is not None else
                              [task(3), task(1, "heldout"), task(2, baseline="green", candidate="HOLD")])}


def declaration(bank_value=None, **changes):
    value = {"schema": "lineage.bench.declared/v1", "bench_id": "bench0001",
             "bank_id": "demo-offline", "bank_sha256": digest(bank_value or bank_data()),
             "protocol": "paired", "purpose": "select", "agents": ["baseline-one", "candidate-one"],
             "seats": [deepcopy(SEAT)], "memory_arms": ["none"],
             "credit_rule": {"metric": "correctness_first", "minimum_gain": 0.0,
                             "dispersion": "population_stddev", "cost_tiebreaker": True},
             "sprt": {"p0": 0.5, "p1": 0.7, "alpha": 0.05, "beta": 0.2, "cap": 100},
             "promotion": {"n_shadow_runs": 1}}
    value.update(deepcopy(changes))
    return value


@dataclass(frozen=True)
class Command:
    tool: str
    args: dict
    agent: str
    op_id: str
    expected_head: int | None = None


@dataclass(frozen=True)
class OracleContext(app.CallContext):
    services: object = None
    authority: str = "tool"
    transport: str = "library"


class Interrupted(BaseException):
    """Deliberate crash boundary, distinct from an application exception."""


class ArenaCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.home, self.repo = self.base / "home", self.base / "repo"
        self.home.mkdir()
        self.repo.mkdir()
        self.counter = itertools.count(1)
        self.operations = itertools.count(1)
        self.reg = registry.load()
        services = SimpleNamespace(home=self.home, repo_root=self.repo, registry=self.reg,
                                   clock=lambda: NOW, id_factory=lambda: f"e-{next(self.counter):016x}",
                                   token_count=None)
        self.ctx = OracleContext(self.home, self.reg.validators, self.reg.folds,
                                 "arena-caller", None, services)
        self.bank = bank_data()
        self.write_bank(self.bank)
        self.decl = declaration(self.bank)

    @property
    def ledger(self):
        return self.home / "ledger/main/events.jsonl"

    def raw(self):
        return self.ledger.read_bytes() if self.ledger.exists() else b""

    def events(self, kind=None):
        values = journal.snapshot(self.home)
        return [e for e in values if kind is None or e["kind"] == kind]

    def invoke(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except NotImplementedError as exc:
            if str(exc) != "U16 stub":
                raise
            self.fail(f"U16 stub: {function.__module__}.{function.__name__}")

    def write_bank(self, value, raw=None, manifest=None):
        self.bankdir = self.repo / "arena/banks/demo-offline"
        self.bankdir.mkdir(parents=True, exist_ok=True)
        persisted = canonical(value) + b"\n" if raw is None else raw
        (self.bankdir / "bank.json").write_bytes(persisted)
        entry = hashlib.sha256(persisted).hexdigest() + "  bank.json\n"
        (self.bankdir / "MANIFEST.sha256").write_text(entry if manifest is None else manifest)

    def command(self, tool, args, op=None, expected=None, actor="arena-caller"):
        values = deepcopy(args)
        values.update(agent=actor, op_id=op or f"operation{next(self.operations):08d}")
        if expected is not None:
            values["expected_head"] = expected
        return Command(tool, values, actor, values["op_id"], expected)

    def tx(self, kind, payload, *, actor="arena-caller", op=None, validators=None):
        return journal.transact(self.home, agent=actor,
            op_id=op or f"fixture{next(self.operations):08d}", kind=kind,
            payload=deepcopy(payload), validators=validators or {kind: lambda h, e: None},
            clock=self.ctx.services.clock, id_factory=self.ctx.services.id_factory)

    def subjects(self):
        """Seed immutable born facts only; do not fake run or memory admission."""
        for index, name in enumerate(self.decl["agents"]):
            if any(e["payload"].get("record", {}).get("agent_id") == name
                   for e in self.events("agent.born")):
                continue
            record = {"schema": "lineage.agent/v1", "agent_id": name, "display_name": name,
                "workflow": "test", "language": "python", "allowed_seats": deepcopy(getattr(self, "subject_seats", [SEAT, SEAT2])),
                "references": [{"id": "gold_s1", "sha256": "a" * 64},
                               {"id": "memory_v21", "sha256": "b" * 64}],
                "constitution_sha256": hashlib.sha256(b"Synthetic constitution\n").hexdigest(),
                "skills": [], "memory_gen": 0, "brief_head_sha256": "c" * 64,
                "generation": 0, "parents": [],
                "born": {"op": "genesis", "event_id": f"e-{index + 1:016x}"}, "status": "draft"}
            record["agent_version"] = digest({k: record[k] for k in
                                             ("constitution_sha256", "skills", "memory_gen")})
            # A-U16: integrated agent projection verifies the real deterministic birth brief digest.
            from lineage.domain import brief
            record["brief_head_sha256"] = hashlib.sha256(brief.build(record, [], rule_ids=[])).hexdigest()
            self.tx("agent.born", {"record": record, "inherited_units": [], "rejected_units": [],
                                  "constitution": {"text": "Synthetic constitution\n", "overlays": [], "rule_ids": []}}, actor=name)

    def declare(self, value=None, command=None):
        self.subjects()
        value = self.decl if value is None else value
        command = command or self.command("bench_declare", {"declaration": value})
        return self.invoke(bench.declare, value, command=command, ctx=self.ctx)

    def execute(self, config=None, command=None):
        config = config or {"kind": "fake", "seed": 7}
        command = command or self.command("bench_run", {"bench_id": self.decl["bench_id"], "runner": config})
        return self.invoke(bench.run, self.decl["bench_id"], config, command=command, ctx=self.ctx)

    def status(self, identifier=None):
        result = self.invoke(bench.status, identifier or self.decl["bench_id"], ctx=self.ctx)
        self.assertEqual(set(result), {"bench"})
        self.assertEqual(set(result["bench"]), {"declaration", "state", "results", "verdict", "head"})
        return result["bench"]

    def verdict(self, command=None):
        command = command or self.command("bench_verdict", {"bench_id": self.decl["bench_id"]})
        return self.invoke(bench.verdict, self.decl["bench_id"], command=command, ctx=self.ctx)

    def value(self, committed):
        return committed.value

    def rejects(self, code, function, *args, unchanged=True, **kwargs):
        before = self.raw()
        with self.assertRaises(LineageError) as error:
            self.invoke(function, *args, **kwargs)
        self.assertEqual(error.exception.code, code)
        if unchanged:
            self.assertEqual(self.raw(), before, "Rejected admission appended authoritative bytes")
        return error.exception

    def result(self, task_id=None):
        return {"bench_id": self.decl["bench_id"], "task_id": task_id or self.bank["tasks"][0]["id"],
                "agent_id": "baseline-one", "seat": deepcopy(SEAT), "memory_arm": "none",
                "run_id": "run00001", "verdict": "red", "correctness": 0, "cost": deepcopy(COST)}

    def direct(self, kind, value):
        # U03 sanitizes unexpected callback exceptions to internal. Observe the
        # explicit stub at its real locked boundary, without bypassing admission.
        original = self.reg.validators[kind]
        observed = []
        def validator(history, event):
            try:
                return original(history, event)
            except NotImplementedError as exc:
                if str(exc) == "U16 stub":
                    observed.append(exc)
                raise
        try:
            return self.tx(kind, value, validators={**self.reg.validators, kind: validator})
        except LineageError:
            if observed:
                self.fail("U16 stub: registered " + kind + " validator")
            raise

    def assert_open_without_result(self):
        self.assertTrue(self.events("run.open"))
        self.assertFalse(self.events("run.close"))
        self.assertFalse(self.events("bench.result"))
        self.assertEqual(self.status()["state"], "running")

    def assert_lifecycle(self):
        events = self.events()
        for result_event in self.events("bench.result"):
            cell = result_event["payload"]
            opened = next(e for e in events if e["kind"] == "run.open" and e["payload"]["run_id"] == cell["run_id"])
            closed = next(e for e in events if e["kind"] == "run.close" and e["payload"]["record"]["run_id"] == cell["run_id"])
            memories = [e for e in events if e["kind"] == "memory.put" and e["payload"].get("run_id") == cell["run_id"]]
            self.assertTrue(memories)
            self.assertLess(opened["lamport"], min(e["lamport"] for e in memories))
            self.assertLess(max(e["lamport"] for e in memories), closed["lamport"])
            self.assertLess(closed["lamport"], result_event["lamport"])
            record = closed["payload"]["record"]
            self.assertIs(record["memory"]["gate_passed"], True)
            self.assertEqual(record["agent_id"], cell["agent_id"])
            self.assertEqual(record["seat"], cell["seat"])
            self.assertEqual(record["memory_arm"], cell["memory_arm"])
            self.assertEqual(record["outcome"]["verdict"], cell["verdict"])
            self.assertEqual(record["cost"], cell["cost"])
            self.assertEqual(cell["correctness"], int(cell["verdict"] in ("ADMIT", "green")))
            self.assertIs(type(cell["correctness"]), int)
            self.assertEqual(result_event["agent"], "arena-caller")
            self.assertEqual(opened["agent"], cell["agent_id"])
            self.assertTrue(all(e["agent"] == cell["agent_id"] for e in memories))

    def execution(self):
        subject = self.events("agent.born")[0]["payload"]["record"]
        value = deepcopy(self.bank["tasks"][0])
        value.update(bank_id="demo-offline", bench_id=self.decl["bench_id"], run_id="run00001")
        return value, subject

    def child(self, source, args=(), timeout=1000):
        path = self.base / f"child{next(self.operations)}.py"
        path.write_text(source)
        return {"kind": "command", "argv": [sys.executable, "-B", str(path), *args], "timeout_ms": timeout}

    def runner_call(self, config, task_value=None):
        if not self.events("agent.born"):
            self.subjects()
        value, subject = self.execution()
        if not self.events("bench.declared"):
            self.tx("bench.declared", self.decl)
        if not self.events("run.open"):
            common = {k: value[k] for k in ("id", "kind", "language", "bank_id", "bench_id", "split")}
            self.tx("run.open", {"run_id": value["run_id"], "agent_id": subject["agent_id"],
                    "agent_version": subject["agent_version"], "seat": SEAT, "task": common,
                    "parents_context": [], "memory_arm": "none"}, actor=subject["agent_id"])
        return self.invoke(runner.run_task, task_value or value, agent=subject, seat=SEAT,
                           memory_arm="none", runner=config, ctx=self.ctx)

    def memory_predecessors(self, agent_id):
        # A-U16: explicit fixture supersession keeps closed-run summaries within real byte budgets.
        from lineage.domain.memory import fold
        events = self.events()
        state = {}
        for event in events:
            fold.apply(state, event)
        closed = {event["payload"]["record"]["run_id"] for event in events if event["kind"] == "run.close"}
        grouped = {}
        for unit in fold.units_for(state, agent_id):
            if unit["provenance"].get("run_id") in closed:
                grouped.setdefault(unit["kind"], []).append(unit["id"])
        return grouped

    def interrupted_at(self, kind, *, after=True):
        original = journal.transact
        fired = []
        def transaction(*args, **kwargs):
            # A-U16: memory transactions carry their kind on the integrated prepare callback.
            prepare = args[1] if len(args) > 1 else None
            event_kind = kwargs.get("kind") or getattr(prepare, "kind", None)
            if event_kind == kind and not fired:
                fired.append(True)
                if not after:
                    raise Interrupted(kind)
                value = original(*args, **kwargs)
                raise Interrupted(kind)
            return original(*args, **kwargs)
        return mock.patch.object(journal, "transact", side_effect=transaction)

    def child_cleanup(self, process):
        self.assertGreater(process.pid, 1)
        if process.poll() is None:
            process.kill()
        process.wait(timeout=1)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream:
                stream.close()


def output_for(task_value, agent, verdict="green", repairs=0, receipt=None, supersedes=None):
    """Independent closed command-output fixture; not a close-gate substitute."""
    chosen = outcome(verdict, repairs)
    receipt = receipt or {"path": "evidence/fixture.txt", "sha256": hashlib.sha256(b"fixture\n").hexdigest()}
    units = []
    kinds = ["episode"]
    if verdict in ("error", "HOLD", "red") or repairs:
        kinds.append("lesson")
    if verdict in ("HOLD", "red"):
        kinds.append("negative")
    for kind in kinds:
        body = {"episode": {"run_id": task_value["run_id"], "task_id": task_value["id"],
                "seat": deepcopy(SEAT), "outcome": chosen, "cost": deepcopy(COST), "parents_context": []},
            "lesson": {"tempting_use": "Assume success", "failure_mode": "Missing evidence",
                       "safer_action": "Check receipts", "blocked_use": []},
            "negative": {"gate_id": "offline", "verdict": verdict, "cause": "Synthetic failure",
                         "coordinate": "fixture:1", "safer_action": "Retain failure memory"}}[kind]
        units.append({"schema": "lineage.mem.unit/v1",
            "id": "u-" + digest([task_value["run_id"], agent["agent_id"], kind])[:32],
            "kind": kind, "level": 2, "statement": "Synthetic offline benchmark",
            "status": "active", "privacy": "internal",
            "scope": {"workflow": agent["workflow"], "language": agent["language"]},
            "provenance": {"origin": "offline", "actor": agent["agent_id"], "run_id": task_value["run_id"]},
            # A-U16: the fixture caller declares replacement edges; the engine never repairs command memory.
            "receipts": [deepcopy(receipt)], "supersedes": list((supersedes or {}).get(kind, [])), "body": body})
    return {"outcome": chosen, "cost": deepcopy(COST), "evidence": [deepcopy(receipt)], "memory_units": units}


def command_source(verdict="green", repairs=0):
    """Self-contained child program, receiving only documented runner stdin."""
    import inspect
    parts = ["import json, hashlib", "from copy import deepcopy",
             "SEAT = " + repr(SEAT), "COST = " + repr(COST)]
    for function in (canonical, digest, outcome, output_for):
        parts.append(inspect.getsource(function))
    parts.append("import sys\nx=json.load(sys.stdin)\nassert set(x)=={'task','agent','seat','memory_arm'}")
    parts.append("assert set(x['task'])=={'id','split','kind','language','prompt','expected','bank_id','bench_id','run_id'}")
    parts.append("assert 'run_id' not in x['agent']")
    parts.append("result=output_for(x['task'],x['agent']," + repr(verdict) + "," + repr(repairs) + ")")
    parts.append("print(json.dumps(result,ensure_ascii=False,allow_nan=False))")
    return "\n".join(parts)
