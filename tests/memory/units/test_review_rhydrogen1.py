"""Review regressions using real journal transactions and test-only U11 admission."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from lineage.core import app
from lineage.core.errors import LineageError
from lineage.domain import memory
from lineage.domain.memory import units
from ._support import IntegrationCase, OWNER, unit


class ReviewRegressions(IntegrationCase):
    def test_review_1_ledger_probe_errors_are_internal(self):
        self.runtime()
        self.write()
        before = self.fingerprint()
        original_stat = Path.stat
        ledger = self.home / "ledger"
        for error in (PermissionError, NotADirectoryError, OSError):
            def failing_stat(path, *args, **kwargs):
                if path == ledger:
                    raise error("fixture inaccessible authority")
                return original_stat(path, *args, **kwargs)
            with self.subTest(error=error.__name__):
                with mock.patch.object(memory, "_native_snapshot", side_effect=LineageError("internal")), \
                        mock.patch.object(Path, "stat", failing_stat), \
                        mock.patch.object(Path, "exists", return_value=False):
                    for read in (lambda: units.get(OWNER, "unit_001", ctx=self.ctx),
                                 lambda: units.history(OWNER, ctx=self.ctx)):
                        caught = self.error("internal", read)
                        self.assertEqual(caught.detail, "authoritative journal unavailable")
                self.assertEqual(self.fingerprint(), before)
        self.assertEqual(units.get(OWNER, "unit_001", ctx=self.ctx)["unit"]["id"], "unit_001")

    def test_review_1_empty_requires_existing_directory_home(self):
        self.runtime()
        before = self.fingerprint()
        fresh = self.home / "fresh-runtime"
        fresh.mkdir()
        context = replace(self.ctx, services=replace(self.ctx.services, home=fresh))
        self.assertEqual(self.journal.snapshot(ctx=context).head, 0)
        self.error("no_agent", lambda: units.history(OWNER, ctx=context))
        missing = self.home / "absent-runtime"
        regular = self.home / "regular-file"
        regular.write_bytes(b"not a directory")
        for home in (missing, regular):
            context = replace(self.ctx, services=replace(self.ctx.services, home=home))
            with self.subTest(home=home.name):
                self.error("internal", lambda: units.get(OWNER, "unit_001", ctx=context))
                self.error("internal", lambda: units.history(OWNER, ctx=context))
        self.assertEqual(self.fingerprint(), before)

    def test_review_2_transport_context_preserves_runtime_services(self):
        self.runtime()
        counter = mock.Mock(return_value=1)
        clock = mock.Mock(return_value=2345)
        ids = mock.Mock(return_value="e-1111111111111111")
        context = SimpleNamespace(home=self.home, token_count=counter, clock=clock, id_factory=ids)
        args = {"agent_id": OWNER, "unit": unit(), "agent": OWNER, "op_id": "transport-services"}
        result = app.dispatch("memory_put", args, context=context, registry=self.registry)
        self.assertIsNone(result.failure)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.payload["untrusted"]["unit"], args["unit"])
        counter.assert_called()
        clock.assert_called_once_with()
        ids.assert_called_once_with()
        committed = self.snapshot().events[-1]
        self.assertEqual((committed["ts"], committed["id"]), (2345, "e-1111111111111111"))

    def test_review_2_missing_counter_still_fails_closed(self):
        self.runtime()
        before = self.fingerprint()
        args = {"agent_id": OWNER, "unit": unit(), "agent": OWNER, "op_id": "no-counter"}
        context = app.create_context(self.home, registry=self.registry)
        result = app.dispatch("memory_put", args, context=context, registry=self.registry)
        self.assertEqual(result.payload["code"], "memory_debt")
        self.assertEqual(result.exit_code, 3)
        self.assertEqual(self.fingerprint(), before)

    def test_review_3_episode_requires_provenance_run(self):
        self.runtime()
        self.open_run()
        candidate = self.shaped("episode")
        candidate["provenance"].pop("run_id")
        self.reject("bad_args", lambda: self.write(candidate))
        candidate["provenance"]["run_id"] = candidate["body"]["run_id"]
        self.assertEqual(self.write(candidate).value["unit"], candidate)

    def test_review_4_operator_retry_after_retirement(self):
        self.runtime()
        first = self.ruling()
        self.raw_append("agent.status", {"agent_id": OWNER, "from": "draft", "to": "retired"})
        before = self.fingerprint()
        replay = self.ruling(op="different-caller-operation")
        self.assertEqual(replay.value, first.value)
        self.assertEqual(replay.event, first.event)
        self.assertEqual(self.fingerprint(), before)
        self.reject("conflict", lambda: self.ruling(quote=b"a new ruling"))

    def test_review_5_nul_receipt_is_bad_args(self):
        self.runtime()
        candidate = unit(receipt={"path": "evidence/a\x00b", "sha256": "0" * 64})
        self.error("bad_args", lambda: self.validate(candidate))
        self.reject("bad_args", lambda: self.write(candidate))
        candidate["receipts"] = [self.evidence()]
        self.assertEqual(self.write(candidate).value["unit"], candidate)
