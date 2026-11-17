"""Real-process assertions. Invoke only inside an isolated PID namespace."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from lineage.core import app, journal
from .support import AGENT, ROOT, make_runtime, put_memory


def check(case):
    # This driver may be namespace init. Only its verified child is signalled.
    with tempfile.TemporaryDirectory(prefix="lineage-process-") as temporary:
        home = Path(temporary) / "home"
        home.mkdir(mode=0o700)
        reg, ctx = make_runtime(home)
        literal = ["a;b", "$(false)", "*", "two words", "--home", "child-value", ""]
        child_source = """import json, os, signal, sys, time
from pathlib import Path
home = Path(os.environ['LINEAGE_HOME'])
(home / 'literal.json').write_text(json.dumps(sys.argv[1:]))
def stopped(signum, frame):
    (home / 'received.json').write_text(json.dumps({'signal':signum,'pid':os.getpid()}))
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stopped)
signal.signal(signal.SIGINT, stopped)
(home / 'ready').write_text(str(os.getpid()))
time.sleep(0.25 if os.environ['PROBE_CASE'] not in ('term','int') else 20)
raise SystemExit(7 if os.environ['PROBE_CASE']=='red' else 0)
"""
        command = [sys.executable, "-m", "lineage", "--home", str(home), "run", "--agent", AGENT,
                   "--seat-model", "test-model", "--seat-effort", "medium", "--beat-s", "0.04", "--"]
        command += (["missing-executable-for-harness-test"] if case == "spawn-error" else
                    [sys.executable, "-c", child_source, *literal])
        process = subprocess.Popen(command, cwd=ROOT, env=dict(os.environ, PROBE_CASE=case,
            PYTHONDONTWRITEBYTECODE="1"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert process.pid > 1
        try:
            first = json.loads(process.stdout.readline())
            run_id = first["run_id"]
            assert first["op_id"] == run_id + "/open"
            if case in ("term", "int"):
                deadline = time.monotonic() + 10
                while not (home / "ready").exists():
                    assert time.monotonic() < deadline
                    assert process.poll() is None
                    time.sleep(0.01)
                child_pid = int((home / "ready").read_text())
                assert child_pid > 1 and child_pid != process.pid
                signum = signal.SIGTERM if case == "term" else signal.SIGINT
                # Exact verified live process created by this test. No groups.
                if process.poll() is None and process.pid > 1:
                    process.send_signal(signum)
            out, err = process.communicate(timeout=15)
            assert process.returncode == 3, (out, err)
            report = json.loads(out.splitlines()[-1])
            assert report["run_id"] == run_id
            assert report["code"] == "memory_required", report
            close = report["close_args"]
            verdict = "red" if case == "red" else "error" if case in ("term", "int", "spawn-error") else "green"
            assert close["outcome"]["verdict"] == verdict
            assert type(close["cost"]["duration_ms"]) is int and close["cost"]["duration_ms"] >= 0
            assert all(value is None for key, value in close["cost"].items() if key != "duration_ms")
            result = app.dispatch("run_get", {"run_id": run_id}, context=ctx, registry=reg)
            assert result.payload["untrusted"]["closed"] is None
            events = journal.snapshot(home)
            opening = next(e for e in events if e["kind"] == "run.open")
            assert opening["op_id"] == first["op_id"]
            if case != "spawn-error":
                assert json.loads((home / "literal.json").read_text()) == literal
            if case in ("green", "red"):
                assert any(e["kind"] == "run.beat" for e in events)
                assert report["child_exit_code"] == (0 if case == "green" else 7)
            if case in ("term", "int"):
                received = json.loads((home / "received.json").read_text())
                assert received == {"signal": signum, "pid": child_pid}
            # Repair uses the measured close args unchanged, including duration.
            put_memory(home, run_id, verdict=verdict, cost=close["cost"])
            if verdict in ("red", "error"):
                put_memory(home, run_id, kind="lesson")
            if verdict == "red":
                put_memory(home, run_id, kind="negative")
            repaired = app.dispatch("run_close", close, context=ctx, registry=reg)
            assert repaired.exit_code == 0, repaired.payload
            before = journal.snapshot(home)
            assert app.dispatch("run_close", close, context=ctx, registry=reg).payload == repaired.payload
            assert journal.snapshot(home) == before
        finally:
            if process.poll() is None and process.pid > 1:
                process.kill()
            process.wait(timeout=5)
            for stream in (process.stdout, process.stderr):
                stream.close()


if __name__ == "__main__":
    check(sys.argv[1])
    print("process_probe: " + sys.argv[1] + " OK")
