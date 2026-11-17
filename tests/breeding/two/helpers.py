"""Public-boundary fixtures; absent owners are HOLD, never emulated services.

The initial no_agent control is a real domain assertion. It deliberately precedes
optional dependency loading so a missing peer cannot camouflage the U18 stub.
No test accepts NotImplementedError, patches a validator to pass, or skips HOLD.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import importlib
import io
import itertools
import json
import multiprocessing
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from lineage.core import app, journal, registry, schema
from lineage.core.errors import LineageError
from lineage.domain.breeding import cross, mutate, specialize

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
ACTOR = "creator-agent"
SEAT = {"model": "fixture-model", "effort": "medium", "mode": "headless"}
TOOLS = ("agent_cross", "agent_mutate", "agent_specialize")
SAFE = 9007199254740991


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Command:
    """Test-owned effective request, matching the spec without a missing import."""
    tool: str
    args: dict
    agent: str
    op_id: str
    expected_head: int | None = None


def arguments(tool, **overrides):
    data = {"agent": ACTOR, "op_id": "breed-op", "child_id": "child-agent"}
    if tool == "agent_cross":
        data["parent_ids"] = ["parent-one", "parent-two"]
    else:
        data["parent_id"] = "parent-one"
    if tool == "agent_mutate":
        data["change"] = {"kind": "skill", "skill_id": "source-skill",
                          "from_sha256": "1" * 64,
                          "to": {"skill_id": "target-skill", "sha256": "2" * 64}}
    if tool == "agent_specialize":
        data["language"] = "python"
    data.update(deepcopy(overrides))
    return data


def invoke(tool, args, context):
    copied = deepcopy(args)
    command = Command(tool, copied, args["agent"], args["op_id"], args.get("expected_head"))
    common = {"command": command, "ctx": context}
    if "display_name" in args:
        common["display_name"] = args["display_name"]
    if tool == "agent_cross":
        return cross.cross(args["parent_ids"], args["child_id"], **common)
    if tool == "agent_mutate":
        return mutate.mutate(args["parent_id"], args["child_id"], args["change"], **common)
    return specialize.specialize(args["parent_id"], args["child_id"], args["language"], **common)


def frozen_schema(name):
    text = (ROOT / "docs/CONTRACT.md").read_text(encoding="utf-8")
    section = text.split("### `" + name + "`", 1)[1].split("\n### ", 1)[0]
    return json.loads(re.search(r"```json\s*(.*?)```", section, re.S).group(1))


def tree_bytes(path):
    if not path.exists():
        return {}
    return {p.relative_to(path).as_posix(): p.read_bytes()
            for p in sorted(path.rglob("*")) if p.is_file() and not p.is_symlink()}


@contextmanager
def seam(module, name, replacement):
    """Instrument a public service and existing imported aliases by identity."""
    original = getattr(module, name)
    locations = [(module, name)]
    for loaded in tuple(sys.modules.values()):
        if loaded is None or not getattr(loaded, "__name__", "").startswith("lineage."):
            continue
        for key, value in tuple(vars(loaded).items()):
            if value is original and (loaded, key) not in locations:
                locations.append((loaded, key))
    with ExitStack() as stack:
        for owner, key in locations:
            stack.enter_context(mock.patch.object(owner, key, replacement))
        yield


def child_call(home, tool, args, ready, release, connection):
    """Spawn target; no process groups, signals, sleeps, or imported test instance."""
    try:
        r = registry.load()
        context = app.create_context(home, registry=r)
        ready.set()
        # A-U18: bounded synchronization accommodates integrated registry startup.
        if not release.wait(20):
            connection.send({"pid": os.getpid(), "timeout": True})
            return
        result = app.dispatch(tool, args, context=context, registry=r).payload
        connection.send({"pid": os.getpid(), "result": result})
    except Exception as exc:
        connection.send({"pid": os.getpid(), "exception": type(exc).__name__})
    finally:
        connection.close()


class OracleCase(unittest.TestCase):
    OP = "agent_cross"

    def setUp(self):
        # A-U18: runtime homes must not mutate the repository snapshot that other
        # integrated tests verify read-only. No fixture depends on a host path.
        temp = tempfile.TemporaryDirectory(prefix="lineage-u18-")
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.sequence = itertools.count(1)
        # No dependency or optional import runs ahead of this public negative
        # control. A successful empty child, wrong error, or no-op shim fails it.
        probe = arguments(self.OP)
        context = app.CallContext(self.home, {}, {}, ACTOR, probe["op_id"])
        with self.assertRaises(LineageError) as caught:
            invoke(self.OP, probe, context)
        self.assertEqual(caught.exception.code, "no_agent")
        self.assertEqual(self.ledger_bytes(), b"", "missing parent must append nothing")
        self.assertFalse(any(not p.startswith("ledger/") for p in tree_bytes(self.home)))

    def runtime(self):
        if not hasattr(self, "reg"):
            try:
                self.reg = registry.load()
            except Exception as exc:
                self.fail("HOLD: integrated registry unavailable (" + type(exc).__name__ + ")")
            self.context = app.create_context(self.home, registry=self.reg)
            actual = journal.transact

            def deterministic(*args, **kwargs):
                # A-U18: integrated callers explicitly pass None for generators;
                # deterministic fixture injection must cover omission and None.
                if kwargs.get("clock") is None:
                    kwargs["clock"] = lambda: 1234567890000
                if kwargs.get("id_factory") is None:
                    kwargs["id_factory"] = lambda: "e-%016x" % next(self.sequence)
                return actual(*args, **kwargs)

            self.enterContext(seam(journal, "transact", deterministic))
        return self.reg

    def module(self, name):
        try:
            return importlib.import_module(name)
        except ImportError:
            self.fail("HOLD: required integrated service " + name + " is AUSENTE")

    def call(self, name, args):
        r = self.runtime()
        self.assertIn(name, r.tools, "HOLD: missing integrated tool " + name)
        return app.dispatch(name, deepcopy(args), context=self.context, registry=r).payload

    def success(self, name, args):
        result = self.call(name, args)
        self.assertEqual(set(result), {"untrusted"}, result)
        self.assertNotIn("untrusted", result["untrusted"])
        return result["untrusted"]

    def op(self, name=None, **kwargs):
        return self.success(name or self.OP, arguments(name or self.OP, **kwargs))

    def reject(self, code, name=None, args=None, **kwargs):
        name = name or self.OP
        args = deepcopy(args) if args is not None else arguments(name, **kwargs)
        before = self.ledger_bytes()
        files = tree_bytes(self.home)
        result = self.call(name, args)
        self.assertEqual(result.get("code"), code, result)
        self.assertIs(result.get("ok"), False)
        self.assertLessEqual(set(result), {"ok", "code", "detail"})
        if "detail" in result:
            self.assertIsInstance(result["detail"], str)
            self.assertLessEqual(len(result["detail"]), 2048)
            self.assertNotIn(str(self.home), result["detail"])
            self.assertNotIn("Traceback", result["detail"])
        self.assertEqual(self.ledger_bytes(), before)
        # Lock-file creation is permitted; no child projection is.
        after = tree_bytes(self.home)
        self.assertEqual({k:v for k,v in after.items() if not k.endswith(".lock")},
                         {k:v for k,v in files.items() if not k.endswith(".lock")})
        return result

    def ledger_bytes(self):
        path = self.home / "ledger/main/events.jsonl"
        return path.read_bytes() if path.exists() else b""

    def history(self):
        return journal.snapshot(self.home)

    def pins(self):
        return [{"id": ref, "sha256": self.success("reference_get", {"ref_id": ref})
                 ["reference"]["sha256"]} for ref in ("gold_s1", "memory_v21")]

    def parent(self, agent_id="parent-one", **kwargs):
        args = {"agent_id": agent_id, "display_name": agent_id, "workflow": "develop",
                "language": "python", "allowed_seats": [deepcopy(SEAT)],
                "references": self.pins(), "skills": [], "agent": ACTOR,
                "op_id": "create-" + agent_id}
        args.update(deepcopy(kwargs))
        data = self.success("agent_create", args)
        return data["record"]

    def parents(self, one=None, two=None):
        return self.parent(**(one or {})), self.parent("parent-two", **(two or {}))

    def publish(self, skill_id="source-skill", text="# Fixture\nPassive context.\n"):
        files = [{"path": "SKILL.md", "content": text}]
        result = self.success("skill_publish", {"skill_id": skill_id, "files": files,
                              "agent": ACTOR, "op_id": "publish-" + sha(canonical(files))[:16] + skill_id})
        expected = {"skill_id": skill_id, "sha256": sha(canonical(files))}
        # A-U18: skill_get returns the immutable package inside its skill wrapper.
        self.assertEqual(self.success("skill_get", expected)["skill"]["sha256"], expected["sha256"])
        return expected

    def get_agent(self, agent_id):
        return self.success("agent_get", {"agent_id": agent_id})["record"]

    def receipt(self, name="proof.txt", raw=b"independently verified fixture\n"):
        p = self.home / "evidence" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
        return {"path": p.relative_to(self.home).as_posix(), "sha256": sha(raw)}

    def unit(self, uid="unit_0001", kind="lesson", *, owner="parent-one", **overrides):
        bodies = {
            "lesson": {"tempting_use": "reuse " + uid, "failure_mode": "stale input",
                       "safer_action": "verify input", "blocked_use": []},
            "negative": {"gate_id": "fixture-gate", "verdict": "HOLD", "cause": "stale input",
                         "coordinate": "evidence/" + uid, "safer_action": "verify input"},
            "workflow": {"trigger_sig": "trigger " + uid, "steps": ["verify input"],
                         "stats": {"runs": 1, "successes": 1, "mean_reward": None}, "status": "promoted"},
            "decision": {"reason": "fixture decision"},
            "open_item": {"class": "followup", "order": 0},
            "ruling": {"quote_sha256": sha(b"fixture ruling"), "how_to_apply": "fixture ruling"},
            "episode": {"run_id": "run_0001", "task_id": "task_001", "seat": deepcopy(SEAT),
                        "outcome": {"verdict": "green", "repair_loops": 0,
                                    "findings": {"confirmed": 0, "refuted": 0}},
                        "cost": dict.fromkeys(("tokens_in", "tokens_out", "tokens_cache", "duration_ms", "cost_micro_usd")),
                        "parents_context": []},
        }
        value = {"schema": "lineage.mem.unit/v1", "id": uid, "kind": kind,
                 "level": 1 if kind == "ruling" else 2, "statement": "statement " + uid,
                 "status": "active", "privacy": "internal", "scope": {"workflow": "develop", "language": "python"},
                 "provenance": {"origin": "oracle-fixture", "actor": owner},
                 "receipts": [self.receipt()], "supersedes": [], "body": bodies[kind]}
        if kind == "episode":
            value["provenance"]["run_id"] = "run_0001"
        value.update(deepcopy(overrides))
        return value

    def put(self, unit, owner="parent-one"):
        self.success("memory_put", {"agent_id": owner, "unit": unit, "agent": owner,
                                   "op_id": "put-" + unit["id"] + "-" + owner})
        return unit

    def source_snapshot(self, units, owner="parent-one"):
        # A-U18: model historical mixed-language source fixtures at the fold read;
        # current memory_put forbids them. Selector, evidence, and admission stay
        # real. This fixture does not certify source-history admission.
        memory = self.module("lineage.domain.memory.fold")
        actual = memory.units_for
        def fixture(state, agent_id, **kwargs):
            return deepcopy(tuple(units)) if agent_id == owner else actual(state, agent_id, **kwargs)
        self.enterContext(seam(memory, "units_for", fixture))

    def retire(self, agent_id="parent-one"):
        return self.success("agent_retire", {"agent_id": agent_id, "reason": "fixture retirement",
                                            "agent": ACTOR, "op_id": "retire-" + agent_id})

    def witness(self, data, op=None):
        self.assertEqual(set(data), {"record", "inherited_units", "rejected_units", "commit"})
        history = self.history()
        commit = data["commit"]
        self.assertEqual(set(commit), {"event_ids", "head", "sha256"})
        self.assertEqual(len(commit["event_ids"]), 1)
        event = history[commit["head"] - 1]
        self.assertEqual(commit["sha256"], event["sha256"])
        self.assertEqual(commit["event_ids"], [event["id"]])
        self.assertEqual(event["kind"], "agent.born")
        self.assertEqual(set(event["payload"]), {"record", "inherited_units", "rejected_units", "constitution"})
        for key in ("record", "inherited_units", "rejected_units"):
            self.assertEqual(data[key], event["payload"][key])
        record = data["record"]
        self.assertEqual(record["born"]["event_id"], event["id"])
        self.assertEqual(record["born"]["op"], (op or self.OP).removeprefix("agent_"))
        self.assertEqual(record["status"], "draft")
        self.assertNotIn("promoted_seat", record)
        self.assertEqual(record["memory_gen"], len(data["inherited_units"]))
        self.assertEqual(record["agent_version"], sha(canonical({
            "constitution_sha256": record["constitution_sha256"],
            "skills": sorted(record["skills"], key=lambda p:(p["skill_id"], p["sha256"])),
            "memory_gen": record["memory_gen"]})))
        constitution = event["payload"]["constitution"]
        self.assertEqual(set(constitution), {"text", "overlays", "rule_ids"})
        self.assertTrue(constitution["text"].endswith("\n"))
        self.assertNotIn("\r", constitution["text"])
        self.assertEqual(record["constitution_sha256"], sha(constitution["text"].encode("utf-8")))
        for field, key in (("inherited_units", lambda x:(x["source_agent_id"],x["source_unit_id"])),
                           ("rejected_units", lambda x:(x["agent_id"],x["unit_id"]))):
            self.assertEqual(data[field], sorted(data[field], key=key))
        self.assertEqual(self.get_agent(record["agent_id"]), record)
        self.verify_chain()
        return event

    def verify_chain(self):
        previous = "0" * 64
        lines = self.ledger_bytes().splitlines(keepends=True)
        for n, line in enumerate(lines, 1):
            event = json.loads(line)
            self.assertEqual(event["lamport"], n)
            self.assertEqual(event["prev_sha256"], previous)
            self.assertEqual(event["sha256"], sha(canonical({k:v for k,v in event.items() if k != "sha256"})))
            self.assertEqual(line, canonical(event) + b"\n")
            previous = sha(line)

    def selection(self, parents, units, language="python"):
        module = self.module("lineage.domain.breeding.inherit")
        return module.select(parents, units, workflow="develop", language=language,
                             selected_ids=None, ctx=self.context)

    def forge(self, payload, code=None):
        self.runtime()
        self.assertIn("agent.born", self.reg.validators, "HOLD: U12 admission is AUSENTE")
        before = self.ledger_bytes()
        files = tree_bytes(self.home)
        copied = deepcopy(payload)
        # A-U18: the installed owner requires an explicit runtime context. Bind
        # the real validator and retain the original pre-prepare request witness.
        from functools import partial
        validators = dict(self.reg.validators)
        validators["agent.born"] = partial(validators["agent.born"], ctx=self.context)

        def prepare(history, draft):
            copied["record"]["born"]["event_id"] = draft["id"]
            return copied

        with self.assertRaises(LineageError) as caught:
            journal.transact(self.home, agent=ACTOR, op_id="forged-" + str(next(self.sequence)),
                             kind="agent.born", payload=deepcopy(self.forge_request), validators=validators,
                             prepare=prepare, clock=lambda:1234567890000,
                             id_factory=lambda:"e-%016x" % next(self.sequence))
        if code is not None:
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.ledger_bytes(), before)
        self.assertEqual(tree_bytes(self.home), files)

    def valid_forge_template(self, tool=None, **kwargs):
        tool = tool or self.OP
        args = arguments(tool, **kwargs)
        # A-U18: prepare changes persisted payload, not the journal request digest.
        self.forge_request = {"tool":tool,"args":{k:deepcopy(v) for k,v in args.items()
                                                if k not in ("op_id","expected_head")}}
        before_files = tree_bytes(self.home)
        data = self.success(tool, args)
        event = self.witness(data, tool)
        # Restore the exact pre-birth authoritative prefix in a disposable home;
        # this is fixture cloning, never editing the production ledger.
        sandbox = self.home / "prebirth"
        shutil.copytree(self.home, sandbox, ignore=shutil.ignore_patterns("prebirth"))
        lines = self.ledger_bytes().splitlines(keepends=True)
        (sandbox / "ledger/main/events.jsonl").write_bytes(b"".join(lines[:data["commit"]["head"]-1]))
        for name in tree_bytes(sandbox):
            if name not in before_files and not name.startswith("ledger/"):
                (sandbox / name).unlink()
        # A-U18: restoring a prebirth fixture removes the entire derived child
        # home, not just files inside immutable generation directories.
        from lineage.domain import layout
        child = data["record"]
        shutil.rmtree(layout.agent_dir(sandbox, workflow=child["workflow"],
                                      language=child["language"], agent_id=child["agent_id"]))
        self.home = sandbox
        self.context = app.create_context(self.home, registry=self.reg)
        return deepcopy(event["payload"])

    def parallel(self, calls):
        mp = multiprocessing.get_context("spawn")
        release = mp.Event()
        processes, receivers, readiness = [], [], []
        for tool, args in calls:
            parent, child = mp.Pipe(duplex=False)
            ready = mp.Event()
            process = mp.Process(target=child_call, args=(str(self.home), tool, args, ready, release, child))
            process.start()
            self.assertGreater(process.pid, 1)
            processes.append(process);receivers.append(parent);readiness.append(ready)
            child.close()
        try:
            for ready in readiness:
                # A-U18: integrated compiler/evidence work exceeds the nominal stub deadline.
                self.assertTrue(ready.wait(10), "child readiness deadline")
            release.set()
            output = []
            for process, pipe in zip(processes, receivers):
                self.assertTrue(pipe.poll(20), "child result deadline")
                result = pipe.recv()
                self.assertEqual(result["pid"], process.pid)
                self.assertIn("result", result, result)
                output.append(result["result"])
                process.join(2)
                self.assertFalse(process.is_alive())
            return output
        finally:
            release.set()
            for process, pipe in zip(processes, receivers):
                if process.is_alive():
                    self.assertGreater(process.pid, 1)
                    process.kill()  # Only this exact owned multiprocessing PID.
                process.join(0.2)
                pipe.close()


def hold_admission(home, ready, release, connection):
    """Hold a real prepare callback; abort the fixture without appending."""
    try:
        r=registry.load()
        def prepare(history,draft):
            connection.send(os.getpid());ready.set()
            if not release.wait(3):
                raise LineageError("internal","fixture release deadline")
            raise LineageError("conflict","fixture transaction aborted")
        try:
            journal.transact(home,agent=ACTOR,op_id="fixture-held-lock",kind="agent.born",payload={},
                             validators=r.validators,prepare=prepare)
        except LineageError as exc:
            if exc.code!="conflict":raise
    finally:
        connection.close()


def _run_existing():
    """Read-only regression runner with a spawn-importable main module."""
    suite=unittest.defaultTestLoader.discover(str(ROOT/"tests"),top_level_dir=str(ROOT))
    def leaves(node):
        for item in node:
            if isinstance(item,unittest.TestSuite):yield from leaves(item)
            elif not item.id().startswith("tests.breeding.two."):yield item
    filtered=unittest.TestSuite(leaves(suite))
    output=io.StringIO()
    result=unittest.TextTestRunner(stream=output,verbosity=0).run(filtered)
    print(json.dumps({"tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
                      "skipped":len(result.skipped),"failed_ids":[t.id() for t,_ in result.failures+result.errors]},sort_keys=True))
    print(output.getvalue()[-220:])


if __name__=="__main__":
    _run_existing()
