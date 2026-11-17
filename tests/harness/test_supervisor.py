"""Unit checks for invalid options and supervision through actual dispatch."""
import io
import json
from types import SimpleNamespace
from unittest import mock

from lineage.core import supervisor
from .support import AGENT, HarnessCase, put_memory


class Supervisor(HarnessCase):
    def test_invalid_options_never_start_child_or_open_run(self):
        before = self.events()
        prefix = ["run", "--agent", AGENT, "--seat-model", "test-model", "--seat-effort", "medium"]
        cases = [[], ["--"], ["--beat-s", "0", "--", "cmd"],
                 ["--beat-s", "nan", "--", "cmd"], ["--beat-s", "inf", "--", "cmd"],
                 ["--seat-effort", "medium"], ["--bad", "x", "--", "cmd"], ["--", "cmd", "bad\0arg"]]
        with mock.patch.object(supervisor.subprocess, "Popen", side_effect=AssertionError("spawned")):
            for tail in cases:
                self.assertEqual(self.cli(*(prefix + tail))[0], 2)
        self.assertEqual(self.events(), before)

    def test_refused_open_prints_identity_first_and_never_launches(self):
        with mock.patch.object(supervisor.subprocess, "Popen", side_effect=AssertionError("spawned")):
            code, out, err = self.cli("run", "--agent", AGENT, "--seat-model", "unallowed",
                                      "--seat-effort", "medium", "--", "cmd")
        lines = [json.loads(line) for line in out.splitlines()]
        self.assertEqual(code, 3)
        self.assertEqual(lines[0]["op_id"], lines[0]["run_id"] + "/open")
        self.assertEqual(lines[1]["code"], "seat_not_allowed")
        self.assertEqual(len(self.events()), 1)

    def test_signal_forwarding_is_exact_child_only_and_handlers_restore(self):
        handlers = {}
        restored = []
        child = SimpleNamespace(pid=18, returncode=-15)
        state = {"alive": True}
        child.poll = lambda: None if state["alive"] else -15
        child.wait = lambda **kw: state.update(alive=False)
        child.send_signal = mock.Mock()
        def install(signum, function):
            if callable(function):
                handlers[signum] = function
            else:
                restored.append((signum, function))
            return "previous"
        def launch(*args, **kwargs):
            # Interruption during creation is recorded before assignment.
            handlers[supervisor.signal.SIGTERM](supervisor.signal.SIGTERM, None)
            return child
        with mock.patch.object(supervisor.signal, "signal", side_effect=install), \
             mock.patch.object(supervisor.subprocess, "Popen", side_effect=launch):
            code, out, err = self.cli("run", "--agent", AGENT, "--seat-model", "test-model",
                "--seat-effort", "medium", "--", "literal", "--home", "child-value")
        self.assertEqual(code, 3)
        child.send_signal.assert_called_once_with(supervisor.signal.SIGTERM)
        self.assertEqual(len(restored), 2)
        value = json.loads(out.splitlines()[-1])
        self.assertEqual(value["close_args"]["outcome"]["verdict"], "error")
        self.assertEqual(value["code"], "memory_required")

    def test_never_signal_reserved_child_pid(self):
        for pid in (1, 0, -1):
            handlers = {}
            child = SimpleNamespace(pid=pid, returncode=0, send_signal=mock.Mock())
            child.poll = lambda: 0
            def install(signum, function):
                if callable(function):
                    handlers[signum] = function
                return "previous"
            def launch(*args, **kwargs):
                handlers[supervisor.signal.SIGINT](supervisor.signal.SIGINT, None)
                return child
            with mock.patch.object(supervisor.signal, "signal", side_effect=install), \
                 mock.patch.object(supervisor.subprocess, "Popen", side_effect=launch):
                self.cli("run", "--agent", AGENT, "--seat-model", "test-model",
                         "--seat-effort", "medium", "--", "literal")
            child.send_signal.assert_not_called()

    def test_successful_close_uses_measured_duration_and_null_unknown_costs(self):
        state = {"alive": True}
        child = SimpleNamespace(pid=18, returncode=0)
        child.poll = lambda: None if state["alive"] else 0
        def wait(**kwargs):
            opening = [e for e in self.events() if e["kind"] == "run.open"][-1]
            cost = dict.fromkeys(("tokens_in", "tokens_out", "tokens_cache", "duration_ms", "cost_micro_usd"))
            cost["duration_ms"] = 125
            put_memory(self.home, opening["payload"]["run_id"], cost=cost)
            state["alive"] = False
        child.wait = wait
        with mock.patch.object(supervisor.subprocess, "Popen", return_value=child) as launch, \
             mock.patch.object(supervisor.time, "monotonic_ns", side_effect=[0, 125_000_000]):
            code, out, err = self.cli("run", "--agent", AGENT, "--seat-model", "test-model",
                "--seat-effort", "medium", "--", "literal", "a;b", "")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(launch.call_args.args[0], ["literal", "a;b", ""])
        self.assertIs(launch.call_args.kwargs["shell"], False)
        result = json.loads(out.splitlines()[-1])
        self.assertEqual(result["untrusted"]["run"]["cost"]["duration_ms"], 125)
        self.assertEqual(result["untrusted"]["run"]["outcome"]["verdict"], "green")

    def test_interrupt_during_open_is_captured_before_child_exists(self):
        original = supervisor._call
        def interrupted_open(tool, args, **kwargs):
            if tool == "run_open":
                handler = supervisor.signal.getsignal(supervisor.signal.SIGTERM)
                self.assertTrue(callable(handler))
                handler(supervisor.signal.SIGTERM, None)
            return original(tool, args, **kwargs)
        with mock.patch.object(supervisor, "_call", side_effect=interrupted_open), \
             mock.patch.object(supervisor.subprocess, "Popen", side_effect=AssertionError("spawned")):
            code, out, err = self.cli("run", "--agent", AGENT, "--seat-model", "test-model",
                "--seat-effort", "medium", "--", "literal")
        self.assertEqual(code, 3)
        result = json.loads(out.splitlines()[-1])
        self.assertEqual(result["code"], "memory_required")
        self.assertEqual(result["close_args"]["outcome"]["verdict"], "error")

    def test_child_signal_exit_is_error_without_supervisor_signal(self):
        child = SimpleNamespace(pid=18, returncode=-15, poll=lambda: -15)
        with mock.patch.object(supervisor.subprocess, "Popen", return_value=child):
            code, out, err = self.cli("run", "--agent", AGENT, "--seat-model", "test-model",
                "--seat-effort", "medium", "--", "literal")
        self.assertEqual(code, 3)
        result = json.loads(out.splitlines()[-1])
        self.assertEqual(result["child_exit_code"], -15)
        self.assertEqual(result["close_args"]["outcome"]["verdict"], "error")
