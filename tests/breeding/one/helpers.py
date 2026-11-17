"""Independent expected values and explicitly nominal journal fixtures.

Fixture validators ONLY construct hostile/pure histories. They are never evidence
of live U12 admission. Integration tests require the actual registry owners.
All disposable writes stay beneath this test package.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
from lineage.core import journal
from lineage.core.app import CallContext, ToolError, dispatch
from lineage.core.errors import LineageError
from lineage.core.registry import load
from lineage.core.schema import SchemaError, validate
from lineage.domain.breeding import inherit
# A-U17: integrated reference verification requires bundled pins, not placeholders.
from lineage.domain.references import REFERENCE_PINS
from lineage.domain import agents, brief
from lineage.domain.memory import fold as memory_fold
from lineage.domain.breeding.clone import clone
from lineage.domain.breeding.distill import distill, retire

ROOT = Path(__file__).resolve().parents[3]
TEST_ROOT = Path(__file__).resolve().parent
SEAT = {"model": "fixture-model", "effort": "medium", "mode": "headless"}
TEXT = "Fixture constitution.\n"
REASONS = (
    "episode", "level_one", "level_three", "private", "inactive",
    "kind_not_inheritable", "scope_mismatch", "missing_receipt",
    "invalid_receipt", "not_promoted", "not_selected",
)
SURFACE = frozenset({
    "lineage/domain/breeding/__init__.py", "lineage/domain/breeding/inherit.py",
    "lineage/domain/breeding/clone.py", "lineage/domain/breeding/distill.py",
    "lineage/domain/tree.py", "lineage/ext/lineage_ops.py",
})


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def version(record):
    return sha({"constitution_sha256": record["constitution_sha256"],
                "skills": sorted(record["skills"], key=lambda s: (s["skill_id"], s["sha256"])),
                "memory_gen": record["memory_gen"]})


def adopted_id(child_id, source_agent_id, source_unit_id):
    return "inh-" + sha({"child_id": child_id, "source_agent_id": source_agent_id,
                         "source_unit_id": source_unit_id})[:44]


def agent(agent_id="parent-one", *, parents=(), op="genesis", generation=0,
          status="draft", memory_gen=9):
    record = {
        "schema": "lineage.agent/v1", "agent_id": agent_id,
        "display_name": "Fixture parent", "workflow": "develop", "language": "python",
        "allowed_seats": [deepcopy(SEAT)],
        "references": [{"id": name, "sha256": digest}
                       for name, digest in sorted(REFERENCE_PINS.items())],
        "constitution_sha256": hashlib.sha256(TEXT.encode()).hexdigest(),
        "skills": [], "memory_gen": memory_gen, "brief_head_sha256": "3" * 64,
        "agent_version": "0" * 64, "generation": generation,
        "parents": list(parents), "born": {"op": op, "event_id": "e-0000000000000001"},
        "status": status,
    }
    record["agent_version"] = version(record)
    return record


@dataclass(frozen=True)
class FixtureCommand:
    """Nominal command value, never misrepresented as an installed core type."""
    tool: str
    args: dict
    agent: str
    op_id: str
    expected_head: int | None = None


def inner(value):
    return deepcopy(value.value if hasattr(value, "value") else value)


def check_schema(value, schema, *, base=None):
    """Test-side evaluator for bundled schema assertions missing from U02.

    Structural leaves use installed validate(value, schema). This helper is an
    independent result oracle, not an alternate production admission service.
    """
    if schema is True:
        return
    if schema is False:
        raise AssertionError("False schema")
    if "$ref" in schema:
        reference = schema["$ref"]
        name, _, pointer = reference.partition("#")
        document = json.loads((ROOT / "schemas" / name).read_text()) if name else base
        target = document
        for key in pointer.lstrip("/").split("/") if pointer else ():
            target = target[key.replace("~1", "/").replace("~0", "~")]
        check_schema(value, target, base=document)
    basic_keys = {"type", "required", "minItems", "maxItems", "uniqueItems",
                  "minLength", "maxLength", "pattern", "minimum", "maximum",
                  "enum", "const"}
    basic = {k: v for k, v in schema.items() if k in basic_keys}
    validate(value, basic)
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        if "maxProperties" in schema:
            assert len(value) <= schema["maxProperties"]
        for key, item in value.items():
            if "propertyNames" in schema:
                check_schema(key, schema["propertyNames"], base=base)
            if key in properties:
                check_schema(item, properties[key], base=base)
            elif extra is False:
                raise AssertionError("Unexpected shaped property: " + key)
            elif isinstance(extra, dict):
                check_schema(item, extra, base=base)
    if isinstance(value, list) and "items" in schema:
        for item in value:
            check_schema(item, schema["items"], base=base)
    for branch in schema.get("allOf", ()):
        check_schema(value, branch, base=base)
    def matches(branch):
        try:
            check_schema(value, branch, base=base)
            return True
        except (AssertionError, SchemaError):
            return False
    if "anyOf" in schema:
        assert any(matches(branch) for branch in schema["anyOf"]), "No anyOf branch"
    if "oneOf" in schema:
        assert sum(matches(branch) for branch in schema["oneOf"]) == 1
    if "not" in schema:
        assert not matches(schema["not"]), "Forbidden schema branch"
    if "if" in schema:
        branch = "then" if matches(schema["if"]) else "else"
        if branch in schema:
            check_schema(value, schema[branch], base=base)


def record_schema(value, name):
    document = json.loads((ROOT / "schemas" / name).read_text())
    check_schema(value, document, base=document)


class OracleCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="u17-", dir=TEST_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.registry = load()
        self.ctx = CallContext(self.home, self.registry.validators,
                               self.registry.folds, "creator-one", "operation-0001")
        self.parent = agent()
        self.sequence = 0

    def receipt(self, name="evidence.txt", content=b"verified fixture\n"):
        path = self.home / "receipts" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return {"path": path.relative_to(self.home).as_posix(),
                "sha256": hashlib.sha256(content).hexdigest()}

    def unit(self, unit_id="unit0001", *, kind="lesson", level=None, **changes):
        bodies = {
            "ruling": {"quote_sha256": "4" * 64, "how_to_apply": "Fixture quote"},
            "lesson": {"tempting_use": "Trust stale facts", "failure_mode": "Stale facts",
                       "safer_action": "Recheck evidence", "blocked_use": []},
            "negative": {"gate_id": "fixture-gate", "verdict": "HOLD", "cause": "Fixture cause",
                         "coordinate": "tests/breeding/one", "safer_action": "Check first"},
            "workflow": {"trigger_sig": "fixture-trigger", "steps": ["Check evidence"],
                         "stats": {"runs": 1, "successes": 1, "mean_reward": None}, "status": "promoted"},
            "episode": {"run_id": "run00001", "task_id": "task0001", "seat": deepcopy(SEAT),
                        "outcome": {"verdict": "green", "repair_loops": 0,
                                    "findings": {"confirmed": 0, "refuted": 0}},
                        "cost": dict.fromkeys(("tokens_in", "tokens_out", "tokens_cache",
                                               "duration_ms", "cost_micro_usd")), "parents_context": []},
            "decision": {"reason": "Fixture decision"},
            "open_item": {"class": "fixture", "order": 0},
        }
        provenance = {"origin": "fixture", "actor": "parent-one"}
        if kind == "episode":
            provenance["run_id"] = "run00001"
        unit = {"schema": "lineage.mem.unit/v1", "id": unit_id, "kind": kind,
                "level": (1 if kind == "ruling" else 2) if level is None else level,
                "statement": "Fixture statement " + unit_id, "status": "active",
                "privacy": "public", "scope": {"workflow": "develop", "language": "python"},
                "provenance": provenance, "receipts": [self.receipt(unit_id + ".txt")],
                "supersedes": [], "body": bodies[kind]}
        unit.update(deepcopy(changes))
        return unit

    def selection(self, units, *, parents=None, selected_ids=None,
                  workflow="develop", language="python"):
        parents = [self.parent] if parents is None else parents
        mapping = units if isinstance(units, Mapping) else {self.parent["agent_id"]: units}
        return inherit.select(parents, mapping, workflow=workflow, language=language,
                              selected_ids=selected_ids, ctx=self.ctx)

    def assert_excluded(self, unit, reason, **kwargs):
        chosen = self.selection([unit], **kwargs)
        self.assertEqual(chosen.inherited, ())
        self.assertEqual(chosen.rejected, ({"agent_id": "parent-one", "unit_id": unit["id"],
                                           "reason": reason},))
        self.assertNotIn(unit["statement"], canonical(list(chosen.rejected)).decode())

    def ledger_bytes(self):
        try:
            return (self.home / "ledger" / "main" / "events.jsonl").read_bytes()
        except FileNotFoundError:
            return b""

    def refused(self, code, operation):
        before = self.ledger_bytes()
        try:
            operation()
        except (LineageError, ToolError) as exc:
            self.assertEqual(exc.code, code)
            if exc.detail:
                self.assertIsInstance(exc.detail, str)
                self.assertLessEqual(len(exc.detail), 2048)
                self.assertNotIn(str(self.base), exc.detail)
                self.assertNotIn("Traceback", exc.detail)
        else:
            self.fail("Expected domain refusal " + code)
        finally:
            self.assertEqual(self.ledger_bytes(), before, "Refusal appended journal bytes")

    def seed(self, record, *, units=()):
        """Pure fixture history through the real journal, NOT live admission proof."""
        def append(kind, payload, actor):
            self.sequence += 1
            index = self.sequence
            return journal.transact(
                self.home, agent=actor, op_id=f"fixture-{index:08d}", kind=kind,
                payload=payload, validators={kind: lambda history, event: None},
                clock=lambda: 1700000000000 + index,
                id_factory=lambda: f"e-{index:016x}")
        # A-U17: memory.put now advances the integrated memory/agent folds. Seed
        # the captured baseline so the requested final counter stays unchanged.
        # Missing historical supersession targets need committed fixture records.
        units = [deepcopy(unit) for unit in units]
        present = {unit["id"] for unit in units}
        predecessors = []
        for unit in units:
            for unit_id in unit["supersedes"]:
                if unit_id not in present:
                    previous = deepcopy(unit)
                    previous.update(id=unit_id, status="retired", supersedes=[])
                    previous.pop("superseded_by", None)
                    predecessors.append(previous)
                    present.add(unit_id)
        units = predecessors + units
        record = deepcopy(record)
        projected = {}
        memory_fold.apply(projected, {"kind": "agent.born", "payload": {
            "record": dict(record, memory_gen=0), "inherited_units": []}})
        for unit in units:
            memory_fold.apply(projected, {"kind": "memory.put", "payload": {
                "agent_id": record["agent_id"], "unit": unit}})
        growth = projected["memory"][record["agent_id"]]["memory_gen"]
        record["memory_gen"] = max(0, record["memory_gen"] - growth)
        record["agent_version"] = version(record)
        record["brief_head_sha256"] = hashlib.sha256(
            brief.build(record, (), rule_ids=[], memory_arm="own")).hexdigest()
        record["born"]["event_id"] = f"e-{self.sequence + 1:016x}"
        append("agent.born", {"record": record, "inherited_units": [], "rejected_units": [],
                              "constitution": {"text": TEXT, "overlays": [], "rule_ids": []}}, "creator-one")
        if len(units) <= 8:
            for unit in units:
                append("memory.put", {"agent_id": record["agent_id"], "unit": deepcopy(unit)}, record["agent_id"])
        else:
            # Large PURE fixtures are built in one write to avoid quadratic
            # transaction setup. This is not a memory-admission bypass test.
            # The real journal snapshot immediately verifies the complete chain.
            path = self.home / "ledger" / "main" / "events.jsonl"
            raw = path.read_bytes()
            previous = raw.splitlines(keepends=True)[-1]
            additions = []
            head = len(raw.splitlines())
            for offset, unit in enumerate(units, 1):
                self.sequence += 1
                index = self.sequence
                request = {"ledger": "main", "agent": record["agent_id"],
                           "op_id": f"fixture-{index:08d}", "kind": "memory.put",
                           "payload": {"agent_id": record["agent_id"], "unit": deepcopy(unit)},
                           "evidence": []}
                event = {"schema": "lineage.event/v1", "id": f"e-{index:016x}",
                         "lamport": head + offset, "ts": 1700000000000 + index,
                         **request, "request_sha256": sha(request),
                         "prev_sha256": hashlib.sha256(previous).hexdigest()}
                event["sha256"] = sha(event)
                previous = canonical(event) + b"\n"
                additions.append(previous)
            path.write_bytes(raw + b"".join(additions))
            self.assertEqual(len(journal.snapshot(self.home)), head + len(units))
        # A-U17: expose the integrated effective record after memory fold updates.
        return agents._record(agents._state(journal.snapshot(self.home), self.ctx),
                              record["agent_id"])

    def command(self, tool="agent_clone", *, op_id="operation-0001", actor="creator-one", **args):
        return FixtureCommand(tool, {**args, "agent": actor, "op_id": op_id}, actor,
                              op_id, args.get("expected_head"))

    def breed(self, *, op="clone", parent_id="parent-one", child_id="child-one",
              op_id="operation-0001", actor="creator-one", display_name=None,
              unit_ids=None, expected_head=None):
        args = {"parent_id": parent_id, "child_id": child_id}
        if display_name is not None:
            args["display_name"] = display_name
        if unit_ids is not None:
            args["unit_ids"] = list(unit_ids)
        if expected_head is not None:
            args["expected_head"] = expected_head
        command = self.command("agent_" + op, op_id=op_id, actor=actor, **args)
        call = clone if op == "clone" else distill
        kwargs = {"display_name": display_name, "command": command, "ctx": self.ctx}
        if op == "distill":
            kwargs["unit_ids"] = unit_ids
        return inner(call(parent_id, child_id, **kwargs))

    def retire_agent(self, agent_id="parent-one", reason="Fixture retirement", *,
                     op_id="retirement-0001", actor="creator-one"):
        command = self.command("agent_retire", op_id=op_id, actor=actor,
                               agent_id=agent_id, reason=reason)
        return inner(retire(agent_id, reason, command=command, ctx=self.ctx))

    def assert_commit(self, result, *, birth=True):
        expected = {"record", "commit", "inherited_units", "rejected_units"} if birth else {"record", "commit"}
        self.assertEqual(set(result), expected)
        record_schema(result["record"], "agent.schema.json")
        commit = result["commit"]
        self.assertEqual(set(commit), {"event_ids", "head", "sha256"})
        history = journal.snapshot(self.home)
        prefix = history[:commit["head"]]
        self.assertEqual(len(commit["event_ids"]), 1)
        self.assertEqual(prefix[-1]["id"], commit["event_ids"][0])
        self.assertEqual(prefix[-1]["sha256"], commit["sha256"])
        if birth:
            self.assertEqual(set(prefix[-1]["payload"]),
                             {"record", "constitution", "inherited_units", "rejected_units"})
            self.assertEqual(result["record"]["born"]["event_id"], prefix[-1]["id"])
            for wrapper in result["inherited_units"]:
                self.assertEqual(set(wrapper), {"unit", "source_agent_id", "source_unit_id", "unit_sha256"})
                record_schema(wrapper["unit"], "mem_unit.schema.json")
        return prefix[-1]

    def require_owners(self):
        self.assertIn("agent.born", self.registry.validators,
                      "HOLD: U12 agent.born owner/delegation AUSENTE")
        self.assertIn("agent.status", self.registry.validators,
                      "HOLD: U12 agent.status owner/delegation AUSENTE")
        self.assertIn("memory", self.registry.folds, "HOLD: U10 memory fold AUSENTE")
        self.assertIn("agents", self.registry.folds, "HOLD: U12 agents fold AUSENTE")

    def admission_validators(self):
        # A-U17: bind the installed U12 validators' runtime ctx argument through
        # the production adapter; the genuine registered owners remain intact.
        from lineage.domain.breeding import _validators
        return _validators(self.ctx)

    def public_call(self, tool, args):
        return dispatch(tool, args, context=self.ctx, registry=self.registry).payload


def breed_process(home, ready, start, output, parent_id, child_id, op_id):
    """Owned child; Event synchronization, no sleep or process-group operation."""
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    registry = load()
    context = CallContext(Path(home), registry.validators, registry.folds,
                          "creator-one", op_id)
    args = {"parent_id": parent_id, "child_id": child_id,
            "agent": "creator-one", "op_id": op_id}
    command = FixtureCommand("agent_clone", args, "creator-one", op_id)
    ready.set()
    if not start.wait(1):
        output.put({"code": "fixture_timeout"})
        return
    try:
        output.put({"result": inner(clone(parent_id, child_id, command=command, ctx=context))})
    except (LineageError, ToolError) as exc:
        output.put({"code": exc.code})
    except Exception as exc:
        output.put({"unexpected": type(exc).__name__})
