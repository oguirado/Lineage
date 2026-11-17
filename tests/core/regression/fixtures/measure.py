"""Record individual unittest outcomes without retaining machine-specific output.

Usage: python measure.py ROOT OUTPUT GROUP [GROUP ...]
Every test invocation must use the process namespace wrapper documented in NOTICE.md.
"""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock


class Outcomes(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes[test.id()] = "green"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes[test.id()] = "failure"

    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes[test.id()] = "error"

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes[test.id()] = "skip"

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.outcomes[test.id()] = "expected_failure"

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.outcomes[test.id()] = "unexpected_success"

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.outcomes[test.id()] = "failure"


def main():
    root, destination, *groups = sys.argv[1:]
    root = Path(root).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root))
    groups_out = {}
    records = {}
    popen = subprocess.Popen

    def without_bytecode(args, *positional, **keywords):
        if isinstance(args, (list, tuple)) and args and Path(str(args[0])).name.startswith("python"):
            args = [args[0], "-B", *args[1:]]
        return popen(args, *positional, **keywords)

    for group in groups:
        loader = unittest.TestLoader()
        suite = loader.discover(group, top_level_dir=str(root))
        stream = io.StringIO()
        with mock.patch.object(subprocess, "Popen", side_effect=without_bytecode):
            result = unittest.TextTestRunner(stream=stream, resultclass=Outcomes).run(suite)
        if not result.wasSuccessful():
            for test, traceback in (result.failures + result.errors)[:8]:
                print("FAILED", test.id(), "\n".join(traceback.splitlines()[-8:]), flush=True)
        records.update(result.outcomes)
        groups_out[group] = {
            "executed": result.testsRun,
            "outcomes": {status: sum(v == status for v in result.outcomes.values())
                         for status in sorted(set(result.outcomes.values()))},
            "discovery_errors": len(loader.errors),
        }
        print(json.dumps({"group": group, **groups_out[group]}), flush=True)
    payload = {"groups": groups_out, "tests": dict(sorted(records.items()))}
    Path(destination).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
