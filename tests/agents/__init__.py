"""Independent U12 oracle fixtures; production dependencies are never replaced.

Fixtures inserted with U03 are deliberately not genesis-admission receipts.
Missing later peers are explicit integration failures, never unittest skips.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import importlib
import io
import itertools
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from lineage.core import app, journal, registry
from lineage.core.errors import LineageError
from lineage.domain import agents, brief, layout, version
from lineage.ext import agents as extension

ROOT = Path(__file__).resolve().parents[2]
HASH = "a" * 64
SEAT = {"model": "fixture-model", "effort": "medium", "mode": "headless"}
REFS = [{"id": "gold_s1", "sha256": "b" * 64},
        {"id": "memory_v21", "sha256": "c" * 64}]
SKILL_FILES = {
    "zeta-skill": [{"path": "SKILL.md", "content": "# Zeta fixture skill\n"}],
    "alpha-skill": [{"path": "SKILL.md", "content": "# Alpha fixture skill\n"}],
}
PINS = [{"skill_id": name,
         "sha256": sha256(json.dumps(files, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()}
        for name, files in SKILL_FILES.items()]
RULE_IDS = ("D1",)
CONSTITUTION = b"# Constitution\n[GOLD-S1/PM-1001.1/D1; \xc2\xa71]\n"
RECORD_FIELDS = {"schema", "agent_id", "display_name", "workflow", "language",
                 "allowed_seats", "references", "constitution_sha256", "skills",
                 "memory_gen", "brief_head_sha256", "agent_version", "generation",
                 "parents", "born", "status"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return sha256(canonical(value)).hexdigest()


def expected_version(constitution_hash, pins, memory_gen):
    return digest({"constitution_sha256": constitution_hash,
                   "skills": sorted(deepcopy(pins), key=lambda p: (p["skill_id"], p["sha256"])),
                   "memory_gen": memory_gen})


def expected_brief(record, units=(), rule_ids=RULE_IDS):
    """Frozen Amendment B byte vector, independent of the implementation."""
    skills = sorted(record["skills"], key=lambda p: (p["skill_id"], p["sha256"]))
    inputs = {"constitution_sha256": record["constitution_sha256"],
              "skills": skills, "memory_gen": record["memory_gen"]}
    def text(value):
        return canonical(value).decode("utf-8")
    lines = ["# Agent brief", "## Identity",
             "agent_id: " + text(record["agent_id"]),
             "workflow: " + text(record["workflow"]),
             "language: " + text(record["language"]),
             "version_inputs: " + text(inputs), "## Constitution",
             "sha256: " + record["constitution_sha256"], "rule_ids:"]
    lines += ["- " + text(rule) for rule in sorted(set(rule_ids))] or ["(none)"]
    lines += ["## Skills"]
    lines += ["- " + text(pin) for pin in skills] or ["(none)"]
    lines += ["## Memory"]
    lines += ["- " + text(unit) for unit in sorted(units, key=lambda u: (u["kind"], u["id"]))] or ["(none)"]
    return ("\n".join(lines) + "\n").encode("utf-8")


def record(agent_id="agent-one", **changes):
    value = {"schema": "lineage.agent/v1", "agent_id": agent_id,
             "display_name": "Fixture agent", "workflow": "develop", "language": "python",
             "allowed_seats": [deepcopy(SEAT)], "references": deepcopy(REFS),
             "constitution_sha256": sha256(CONSTITUTION).hexdigest(),
             "skills": [], "memory_gen": 0, "brief_head_sha256": HASH,
             "agent_version": HASH, "generation": 0, "parents": [],
             "born": {"op": "genesis", "event_id": "e-0000000000000001"}, "status": "draft"}
    value.update(deepcopy(changes))
    value["agent_version"] = expected_version(value["constitution_sha256"], value["skills"], value["memory_gen"])
    value["brief_head_sha256"] = sha256(expected_brief(value)).hexdigest()
    return value


def unit(identifier="lesson01", kind="lesson", **changes):
    bodies = {
        "ruling": {"quote_sha256": HASH, "how_to_apply": "Preserve the operator quote."},
        "lesson": {"tempting_use": "Trust a projection", "failure_mode": "Stale data",
                   "safer_action": "Read the journal", "blocked_use": []},
        "negative": {"gate_id": "fixture-gate", "verdict": "HOLD", "cause": "Missing fact",
                     "coordinate": "fixture.py:1", "safer_action": "Verify first"},
        "workflow": {"trigger_sig": "fixture", "steps": ["Verify"],
                     "stats": {"runs": 1, "successes": 1, "mean_reward": None}, "status": "candidate"},
        "episode": {"run_id": "run00001", "task_id": "task0001", "seat": deepcopy(SEAT),
                    "outcome": {"verdict": "green", "repair_loops": 0,
                                "findings": {"confirmed": 0, "refuted": 0}},
                    "cost": {key: None for key in ("tokens_in", "tokens_out", "tokens_cache", "duration_ms", "cost_micro_usd")},
                    "parents_context": []},
        "decision": {"reason": "Fixture"}, "open_item": {"class": "fixture", "order": 0}}
    value = {"schema": "lineage.mem.unit/v1", "id": identifier, "kind": kind,
             "level": 1 if kind == "ruling" else 2, "statement": "MARKER_" + identifier,
             "status": "active", "privacy": "internal",
             "scope": {"workflow": "develop", "language": "python"},
             "provenance": {"origin": "oracle-fixture", "actor": "operator" if kind == "ruling" else "agent-one"},
             "receipts": [{"path": "receipts/fixture.txt", "sha256": HASH}],
             "supersedes": [], "body": bodies[kind]}
    if kind == "episode":
        value["provenance"]["run_id"] = "run00001"
    value.update(deepcopy(changes))
    return value


@dataclass(frozen=True)
class Command:
    """Test-owned value fixture: the documented shared class is AUSENTE."""
    tool: str
    args: dict
    agent: str
    op_id: str
    expected_head: int | None = None


class OracleCase(unittest.TestCase):
    def setUp(self):
        self.started = time.monotonic()
        self.temp = tempfile.TemporaryDirectory(prefix="runtime-", dir=ROOT / "tests/agents")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.reg = registry.load()
        self.ctx = app.create_context(self.home, registry=self.reg, actor="system")
        self.numbers = itertools.count(1)
        ids = itertools.count(1)
        patch = mock.patch.object(journal.secrets, "token_hex", side_effect=lambda n: f"{next(ids):016x}")
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(journal.time, "time_ns", return_value=1700000000000000000)
        patch.start()
        self.addCleanup(patch.stop)

    def tearDown(self):
        self.assertLess(time.monotonic() - self.started, 5, "bounded test exceeded its deadline")

    def invoke(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except NotImplementedError as exc:
            if str(exc) == "U12 stub":
                self.fail("U12 stub: required behavior has not been implemented")
            raise

    def inventory(self):
        if not self.home.exists():
            return {}
        return {p.relative_to(self.home).as_posix():
                ("symlink", str(p.readlink())) if p.is_symlink() else p.read_bytes()
                for p in self.home.rglob("*") if p.is_file() or p.is_symlink()}

    def ledger(self):
        path = self.home / "ledger/main/events.jsonl"
        return path.read_bytes() if path.exists() else b""

    def reject(self, code, function, *args, **kwargs):
        before = self.ledger()
        projections = {k: v for k, v in self.inventory().items() if not k.startswith("ledger/")}
        with self.assertRaises(LineageError) as raised:
            self.invoke(function, *args, **kwargs)
        self.assertEqual(raised.exception.code, code)
        self.assertEqual(self.ledger(), before, "refusal changed authoritative bytes")
        self.assertEqual({k: v for k, v in self.inventory().items() if not k.startswith("ledger/")}, projections)
        return raised.exception

    def command(self, arguments, *, op_id=None, expected_head=None, tool="agent_create", actor="system"):
        identity = op_id or f"operation{next(self.numbers):04d}"
        effective = {**deepcopy(arguments), "agent": actor, "op_id": identity}
        if expected_head is not None:
            effective["expected_head"] = expected_head
        return Command(tool, effective, actor, identity, expected_head)

    def arguments(self, **changes):
        pins = deepcopy(REFS)
        try:
            references = importlib.import_module("lineage.domain.references")
        except ImportError:
            references = None
        if references is not None:
            pins = []
            for name in ("gold_s1", "memory_v21"):
                verified = references.get(name, ctx=self.ctx)["reference"]
                pins.append({"id": name, "sha256": verified["sha256"]})
        value = {"agent_id": "agent-one", "display_name": "Fixture agent", "workflow": "develop",
                 "language": "python", "allowed_seats": [deepcopy(SEAT)],
                 "references": pins, "skills": [], "overlays": []}
        value.update(deepcopy(changes))
        return value

    def publish_fixture_skills(self, pins):
        # A-U12: U09 verifies immutable packages, so publish through its real tool.
        existing = journal.snapshot(self.home)
        for pin in pins:
            if (pin["skill_id"] in SKILL_FILES and pin in PINS
                    and not any(e["kind"] == "skill.published" and e["payload"].get("skill_id") == pin["skill_id"]
                                and e["payload"].get("sha256") == pin["sha256"] for e in existing)):
                args = {"skill_id": pin["skill_id"], "files": deepcopy(SKILL_FILES[pin["skill_id"]])}
                command = self.command(args, tool="skill_publish")
                result = app.dispatch("skill_publish", command.args, context=self.ctx, registry=self.reg)
                self.assertEqual(result.exit_code, 0, result.payload)
                self.assertEqual(result.payload["untrusted"]["skill"]["sha256"], pin["sha256"])

    def create(self, *, command=None, **changes):
        # A-U12: provision the exact requested immutable skill pins via integrated U09.
        args = self.arguments(**changes)
        self.publish_fixture_skills(args["skills"])
        return self.invoke(agents.create, **args, command=command or self.command(args), ctx=self.ctx)

    def memory_context(self, actor="system", *, token_count=None):
        # A-U12: U10/U11 use Services/Context rather than native CallContext.
        services = registry.Services(home=self.home, repo_root=ROOT, registry=self.reg,
                                     token_count=token_count)
        return registry.Context(services=services, actor=actor)

    def memory_snapshot(self):
        # A-U12: U11 requires the folded snapshot, not U03's native event tuple.
        return journal.snapshot(ctx=self.memory_context())

    def configure_lane(self, config):
        # A-U12: integrated JSON lane requires explicit private on-disk admission.
        directory = self.home / "family" / config["endpoint"]
        directory.mkdir(parents=True, mode=0o700)
        for path in (self.home, directory.parent, directory):
            path.chmod(0o700)
        path = directory / "config.json"
        path.write_bytes(canonical(config))
        path.chmod(0o600)

    def require_peer(self, name):
        try:
            return importlib.import_module(name)
        except ImportError:
            self.fail("BLOCKED/HOLD: required integrated peer AUSENTE: " + name)

    def append_fixture(self, kind, payload, *, op_id=None, prepare=None):
        return journal.transact(self.home, agent="system", op_id=op_id or f"fixtureop{next(self.numbers):04d}",
                                kind=kind, payload=deepcopy(payload),
                                validators={kind: lambda history, event: None}, prepare=prepare)

    def seed(self, agent_id="agent-one", **changes):
        # A-U12: committed-prefix fixtures must carry real integrated U07 pins.
        changes.setdefault("references", self.arguments()["references"])
        source = record(agent_id, **changes)
        payload = {"record": source, "constitution": {"text": CONSTITUTION.decode(),
                    "overlays": [], "rule_ids": list(RULE_IDS)}, "inherited_units": [], "rejected_units": []}
        def bind(history, draft):
            value = deepcopy(payload)
            value["record"]["born"]["event_id"] = draft["id"]
            return value
        return self.append_fixture("agent.born", payload, prepare=bind)

    def assert_chain(self):
        previous = "0" * 64
        events, ids, operations = [], set(), set()
        for number, line in enumerate(self.ledger().splitlines(keepends=True), 1):
            event = json.loads(line)
            self.assertEqual(canonical(event) + b"\n", line)
            self.assertEqual(event["lamport"], number)
            self.assertEqual(event["prev_sha256"], previous)
            self.assertEqual(event["sha256"], digest({k: v for k, v in event.items() if k != "sha256"}))
            self.assertNotIn(event["id"], ids)
            self.assertNotIn((event["agent"], event["op_id"]), operations)
            ids.add(event["id"])
            operations.add((event["agent"], event["op_id"]))
            previous = sha256(line).hexdigest()
            events.append(event)
        return events

    def handler(self, name, args):
        return self.invoke(self.reg.tools[name].handler, deepcopy(args), context=self.ctx)

    def projection_dir(self, agent_id="agent-one", language="python"):
        return layout.agent_dir(self.home, workflow="develop", language=language, agent_id=agent_id)

    def materialize(self, agent_id="agent-one"):
        return self.invoke(agents.materialize, agent_id, snapshot=journal.snapshot(self.home), ctx=self.ctx)

    def built(self, value=None, units=(), *, arm="own", rules=RULE_IDS):
        return self.invoke(brief.build, record() if value is None else value,
                           units, rule_ids=rules, memory_arm=arm)
