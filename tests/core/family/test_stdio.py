"""A11: one-shot entry point, canonical framing, and strict identity recovery."""

import io
import json
import sys
import subprocess
from unittest.mock import patch

from lineage.core import jsonlane
from tests.core.family import ROOT, WireCase, request, wire


class StdioTests(WireCase):
    def test_a11_subprocess_eof_and_single_receipt(self):
        completed = subprocess.run([sys.executable, "-B", "-c",
            "from lineage.core.jsonlane import main; raise SystemExit(main([]))"],
            input=b'{"id":"request01","extra":1}', stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=ROOT, timeout=2, check=False)
        if b"NotImplementedError: U05 stub" in completed.stderr:
            self.fail("U05 stub")
        self.assertEqual(completed.returncode, 2)
        value = json.loads(completed.stdout)
        self.assertEqual(completed.stdout, wire(value) + b"\n")
        self.assertEqual(value["id"], "request01")
        self.assert_error(value["result"], "bad_args")

    def invoke(self, raw):
        stdin = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8")
        output = io.BytesIO()
        stdout = io.TextIOWrapper(output, encoding="utf-8", write_through=True)
        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout), \
                patch.object(sys, "stderr", io.StringIO()):
            try:
                status = jsonlane.main([])
            except NotImplementedError as exc:
                self.fail(str(exc))
        stdout.flush()
        raw_result = output.getvalue()
        value = json.loads(raw_result.decode("utf-8"))
        self.assertEqual(raw_result, wire(value) + b"\n")
        self.assertEqual(set(value), {"schema", "id", "result"})
        self.assertEqual(value["schema"], "lineage.family/1")
        self.assertNotIn(b"Traceback", raw_result)
        return status, value

    def test_a11_schema_invalid_recovers_strict_id(self):
        value = request()
        value["extra"] = 1
        status, result = self.invoke(wire(value))
        self.assertEqual(status, 2)
        self.assertEqual(result["id"], "request01")
        self.assert_error(result["result"], "bad_args")

    def test_a11_reserved_request_not_dispatched(self):
        status, result = self.invoke(wire(request(id="invalid0")))
        self.assertEqual(status, 2)
        self.assertEqual(result["id"], "invalid0")
        self.assert_error(result["result"], "bad_args")


for label, raw in {
    "broken": b'{"id":"request01",',
    "duplicate_id": b'{"id":"request01","id":"request02"}',
    "duplicate_nested": b'{"id":"request01","payload":{"a":1,"a":2}}',
    "invalid_encoding": b'{"id":"request01","a":"\xff"}',
    "surrogate": b'{"id":"request01","a":"\\ud800"}',
    "multiple": wire(request()) + b"\n" + wire(request(id="request02")),
    "array": b'[]', "scalar": b'1', "empty": b'',
    "invalid_id": b'{"id":"bad"}', "no_id": b'{}',
}.items():
    def test(self, raw=raw):
        status, result = self.invoke(raw)
        self.assertEqual(status, 2)
        self.assertEqual(result["id"], "invalid0")
        self.assert_error(result["result"], "bad_args")
    setattr(StdioTests, "test_a11_" + label, test)
