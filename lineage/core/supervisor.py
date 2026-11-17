"""Native literal-argv run capture through the shared tool dispatcher."""
from __future__ import annotations

import argparse
import json
import math
import os
import secrets
import signal
import subprocess
import time

from . import app


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid command options")


def _emit(stream, value):
    stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False,
                            sort_keys=True, separators=(",", ":")) + "\n")
    stream.flush()


def _call(tool, args, *, context, registry):
    return app.dispatch(tool, args, context=context, registry=registry)


def _opening(run_id, agent_id, seat, task):
    return {"run_id": run_id, "agent_id": agent_id, "seat": seat, "task": task,
            "parents_context": [], "memory_arm": "own", "agent": agent_id,
            "op_id": run_id + "/open"}


def _closing(run_id, agent_id, verdict, duration_ms=None):
    return {"run_id": run_id, "agent": agent_id, "op_id": run_id + "/close",
            "outcome": {"verdict": verdict, "repair_loops": 0,
                        "findings": {"confirmed": 0, "refuted": 0}},
            "cost": {"tokens_in": None, "tokens_out": None, "tokens_cache": None,
                     "duration_ms": duration_ms, "cost_micro_usd": None}}


def _episode(run_id, agent_id, seat, task, closing, workflow):
    return {"agent_id": agent_id, "run_id": run_id, "agent": agent_id,
            "op_id": run_id + "/episode",
            "unit": {"schema": "lineage.mem.unit/v1", "id": "<UnitId>", "kind": "episode",
                     "level": 3, "statement": "<what happened in this run>",
                     "status": "active", "privacy": "internal",
                     "scope": {"workflow": workflow, "language": task["language"]},
                     "provenance": {"origin": "run", "actor": agent_id, "run_id": run_id},
                     "receipts": [], "supersedes": [],
                     "body": {"run_id": run_id, "task_id": task["id"], "seat": seat,
                              "outcome": closing["outcome"], "cost": closing["cost"],
                              "parents_context": []}}}


def _options(argv):
    boundary = argv.index("--")
    parser = _Parser(add_help=False, allow_abbrev=False)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--seat-model", required=True)
    parser.add_argument("--seat-effort", required=True)
    parser.add_argument("--task-id")
    parser.add_argument("--task-kind", default="command")
    parser.add_argument("--task-language")
    parser.add_argument("--beat-s", type=float, default=30.0)
    options = parser.parse_args(argv[:boundary])
    command = argv[boundary + 1:]
    if (not command or not command[0] or any("\0" in item for item in command)
            or not math.isfinite(options.beat_s) or options.beat_s <= 0):
        raise ValueError("invalid command options")
    return options, command


def main(argv, *, context, registry, stdin, stdout, stderr):
    try:
        options, command = _options(argv)
    except (ValueError, TypeError):
        _emit(stdout, {"ok": False, "code": "bad_args"})
        return 2
    run_id = "run-" + secrets.token_hex(16)
    child = None
    interrupted = []
    previous = {}
    first_failure = None

    def send_owned(signum):
        # Popen owns this exact child and rechecks liveness before signalling.
        # No sessions/process groups are created or signalled.
        if child is not None and child.pid > 1 and child.poll() is None:
            try:
                child.send_signal(signum)
            except ProcessLookupError:
                pass

    def forward(signum, frame):
        interrupted.append(signum)
        send_owned(signum)

    started = time.monotonic_ns()
    child_code = None
    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.signal(signum, forward)
        # Flush before opening or launching, including when the opening is refused.
        _emit(stdout, {"run_id": run_id, "op_id": run_id + "/open"})
        agent = _call("agent_get", {"agent_id": options.agent}, context=context, registry=registry)
        if agent.failure is not None:
            _emit(stdout, {"run_id": run_id, **agent.payload})
            return agent.exit_code
        workflow = agent.payload["untrusted"]["record"]["workflow"]
        task = {"id": options.task_id or run_id, "kind": options.task_kind,
                "language": options.task_language or agent.payload["untrusted"]["record"]["language"]}
        seat = {"model": options.seat_model, "effort": options.seat_effort, "mode": "headless"}
        opened = _call("run_open", _opening(run_id, options.agent, seat, task),
            context=context, registry=registry)
        if opened.failure is not None:
            _emit(stdout, {"run_id": run_id, **opened.payload})
            return opened.exit_code
        env = dict(os.environ, LINEAGE_RUN_ID=run_id, LINEAGE_AGENT_ID=options.agent,
                   LINEAGE_HOME=str(context.home))
        if not interrupted:
            try:
                child = subprocess.Popen(command, env=env, shell=False)
            except (OSError, ValueError):
                first_failure = {"ok": False, "code": "internal"}
        if child is not None:
            # Deliver an interrupt that raced the Popen assignment.
            if interrupted:
                send_owned(interrupted[-1])
            next_beat = time.monotonic() + options.beat_s
            beat = 0
            while child.poll() is None:
                remaining = max(0.001, next_beat - time.monotonic())
                try:
                    child.wait(timeout=min(remaining, 0.1))
                except subprocess.TimeoutExpired:
                    pass
                if child.poll() is None and time.monotonic() >= next_beat:
                    beat += 1
                    result = _call("run_beat", {"run_id": run_id, "agent": options.agent,
                        "op_id": run_id + "/beat/" + str(beat), "progress": "running"},
                        context=context, registry=registry)
                    if result.failure is not None and first_failure is None:
                        first_failure = result.payload
                    next_beat = time.monotonic() + options.beat_s
            child_code = child.returncode
        duration = max(0, (time.monotonic_ns() - started) // 1_000_000)
        verdict = ("error" if interrupted or child_code is None or child_code < 0
                   else "green" if child_code == 0 else "red")
        closed = _call("run_close", _closing(run_id, options.agent, verdict, duration),
                       context=context, registry=registry)
        report = {"run_id": run_id, "child_exit_code": child_code,
                  "close_args": _closing(run_id, options.agent, verdict, duration),
                  **closed.payload}
        if closed.payload.get("code") == "memory_required":
            # A-HOOK1b: hand the AI the exact run-bound episode write (the gate
            # matches memory.put's top-level run_id plus the episode's outcome
            # and cost); it fills only the unit id and statement.
            report["episode_args"] = _episode(run_id, options.agent, seat, task,
                                              report["close_args"], workflow)
        _emit(stdout, report)
        if first_failure is not None:
            _emit(stderr, {"run_id": run_id, **first_failure})
        if closed.failure is not None:
            return closed.exit_code
        return 0 if child_code == 0 and not interrupted and first_failure is None else 3
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
