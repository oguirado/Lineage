"""Every real child/signal scenario runs inside its own PID namespace."""
import os
import subprocess
import sys
import unittest

from .support import ROOT


class Processes(unittest.TestCase):
    def probe(self, case):
        # A full suite launched by unshare is already namespace init. The host
        # init is not Python; every standalone invocation creates a namespace.
        prefix = [] if os.getpid() == 1 else [
            "unshare", "--user", "--pid", "--fork", "--kill-child", "--mount-proc"]
        result = subprocess.run([*prefix, sys.executable, "-m", "tests.harness.process_probe", case], cwd=ROOT,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_green_literal_argv_heartbeats_measured_cost_and_repair(self):
        self.probe("green")

    def test_red_failure_memory_and_replay(self):
        self.probe("red")

    def test_sigterm_forward_and_error_close(self):
        self.probe("term")

    def test_sigint_forward_and_error_close(self):
        self.probe("int")

    def test_spawn_error_keeps_repairable_open_run(self):
        self.probe("spawn-error")
