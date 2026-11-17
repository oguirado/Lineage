"""Real registry, journal and memory fixtures; no model or network."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from lineage.core import app, cli, journal, registry

ROOT = Path(__file__).resolve().parents[2]
SEAT = {"model": "test-model", "effort": "medium", "mode": "headless"}
AGENT = "test-agent"


def make_runtime(home):
    # Core schema oracles reload their provider. Use the installed integration
    # seam to synchronize exception identities and bundled-schema support.
    from lineage.domain.memory import schema as memory_schema
    memory_schema._sync_boundary()
    reg = registry.load()
    ctx = app.create_context(home, registry=reg)
    pins = []
    for name in ("gold_s1", "memory_v21"):
        result = app.dispatch("reference_get", {"ref_id": name}, context=ctx, registry=reg)
        assert result.exit_code == 0, result.payload
        pin = result.payload["untrusted"]["reference"]
        pins.append({"id": name, "sha256": pin["sha256"]})
    result = app.dispatch("agent_create", {"agent_id": AGENT, "display_name": "Test agent",
        "workflow": "test", "language": "python", "allowed_seats": [SEAT], "references": pins,
        "skills": [], "agent": AGENT, "op_id": "harness/create"}, context=ctx, registry=reg)
    assert result.exit_code == 0, result.payload
    return reg, ctx


def put_memory(home, run_id, *, verdict="green", kind="episode", suffix="0001", cost=None):
    reg = registry.load()
    ctx = app.create_context(home, registry=reg)
    opened = app.dispatch("run_get", {"run_id": run_id}, context=ctx, registry=reg)
    assert opened.exit_code == 0, opened.payload
    record = opened.payload["untrusted"]["opened"]["payload"]
    unit = {"schema": "lineage.mem.unit/v1", "id": kind + suffix, "kind": kind,
        "level": 3, "statement": "Observed test result.", "status": "active", "privacy": "public",
        "scope": {"workflow": "test", "language": "python"},
        "provenance": {"origin": "harness-test", "actor": AGENT, "run_id": run_id},
        "receipts": [], "supersedes": []}
    if kind == "episode":
        unit["body"] = {"run_id": run_id, "task_id": record["task"]["id"],
            "seat": record["seat"], "parents_context": record["parents_context"],
            "outcome": {"verdict": verdict, "repair_loops": 0, "findings": {"confirmed": 0, "refuted": 0}},
            "cost": deepcopy(cost) if cost is not None else dict.fromkeys(("tokens_in", "tokens_out", "tokens_cache", "duration_ms", "cost_micro_usd"))}
    elif kind == "lesson":
        unit["body"] = {"tempting_use": "Skip verification.", "failure_mode": "Missing proof.",
                        "safer_action": "Check the result.", "blocked_use": []}
    else:
        unit["body"] = {"gate_id": "memory-close", "verdict": "red", "cause": "Failed test.",
                        "coordinate": "tests/harness", "safer_action": "Check before closing."}
    result = app.dispatch("memory_put", {"agent_id": AGENT, "unit": unit, "run_id": run_id,
        "agent": AGENT, "op_id": run_id + "/memory/" + kind + suffix}, context=ctx, registry=reg)
    assert result.exit_code == 0, result.payload
    return unit


class HarnessCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lineage-harness-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir(mode=0o700)
        self.reg, self.ctx = make_runtime(self.home)

    def cli(self, *args, raw=b""):
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(["--home", str(self.home), *args], registry=self.reg,
                        stdin=io.BytesIO(raw), stdout=out, stderr=err)
        return code, out.getvalue(), err.getvalue()

    def call(self, name, args):
        return app.dispatch(name, args, context=self.ctx, registry=self.reg)

    def events(self):
        return journal.snapshot(self.home)
