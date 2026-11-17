"""A10, A14, A16, A30, A34, A35: locked admission and dependency refusals."""
import copy
import sys
from dataclasses import replace
from unittest import mock
from ._support import IntegrationCase, OWNER, canonical, sha, unit
from lineage.domain.memory import units


class AdmissionTests(IntegrationCase):
    def test_a02_direct_domain_closed_nested_objects(self):
        self.runtime()
        self.open_run()
        self.write(self.shaped("episode"))
        for path in ((), ("body",), ("provenance",), ("receipts", 0),
                     ("body", "seat"), ("body", "cost"), ("body", "outcome")):
            value = self.shaped("episode", uid="unit_002")
            target = value
            for key in path:
                target = target[key]
            target["authority"] = "operator"
            self.reject("bad_args", lambda: self.write(value))

    def test_a10_owner_scope_and_target(self):
        self.runtime()
        for n, language in enumerate(("python", "general")):
            value = unit(uid="unit_%03d" % (n + 1))
            value["scope"]["language"] = language
            self.write(value)
        self.reject("no_agent", lambda: self.write(unit(actor="missing-agent"), owner="missing-agent", actor="missing-agent"))
        self.born("other-agent")
        self.reject("conflict", lambda: self.write(unit(uid="unit_003"), actor="other-agent"))
        value = unit(uid="unit_003", actor="other-agent")
        self.reject("conflict", lambda: self.write(value))
        for field, invalid in (("workflow", "review"), ("language", "typescript")):
            value = unit(uid="unit_003")
            value["scope"][field] = invalid
            self.reject("conflict", lambda: self.write(value))
        context = replace(self.ctx, actor="other-agent")
        self.assertEqual(units.get(OWNER, "unit_001", ctx=context)["unit"]["id"], "unit_001")

    def test_a10_retired_agent_cannot_receive_memory_or_ruling(self):
        self.runtime()
        self.write()
        self.raw_append("agent.status", {"agent_id": OWNER, "from": "draft", "to": "retired", "reason": "fixture"})
        self.reject("conflict", lambda: self.write(unit(uid="unit_002")))
        self.reject("conflict", lambda: self.ruling())

    def test_a14_real_append_cannot_bypass_validators(self):
        self.runtime()
        good = self.shaped()
        self.raw_append("memory.put", {"agent_id": OWNER, "unit": good})
        for value, code in ((unit("ruling", 1, uid="unit_002", actor="operator"), "forbidden_level"),
                            (unit("lesson", 2, uid="unit_002", receipt={"path": "evidence/check.txt", "sha256": "0" * 64}), "hash_mismatch")):
            self.reject(code, lambda: self.raw_append("memory.put", {"agent_id": OWNER, "unit": value}, actor=value["provenance"]["actor"]))
        value = unit(uid="unit_002")
        value["supersedes"] = ["unknown1"]
        self.reject("conflict", lambda: self.raw_append("memory.put", {"agent_id": OWNER, "unit": value}))

    def test_a16_prepare_evidence_capacity_and_render_fail_atomically(self):
        self.runtime()
        self.write()
        semantic = self.shaped("workflow", uid="unit_002")
        semantic["body"]["stats"].update(runs=1, successes=2)
        self.reject("bad_args", lambda: self.write(semantic))
        evidence = unit("lesson", 2, uid="unit_002", receipt={"path": "evidence/absent.txt", "sha256": sha(b"absent")})
        self.reject("hash_mismatch", lambda: self.write(evidence))
        error = self.require("lineage.core.errors", "LineageError").LineageError
        with self.patch_seam(self.entry_module, "build", mock.Mock(side_effect=error("memory_debt", "cuts: fixture capacity"))):
            self.reject("memory_debt", lambda: self.write(unit(uid="unit_002")))
        candidate = unit(uid="unit_002")
        original = copy.deepcopy(candidate)
        def broken_render(snapshot, current):
            raise error("internal", "fixture render refusal")
        self.reject("internal", lambda: self.raw_append("memory.put", {"agent_id": OWNER, "unit": candidate}, render=broken_render))
        self.assertEqual(candidate, original)
        self.assertEqual(self.write(candidate).value["unit"], candidate)

    def test_a30_entry_byte_ceiling_is_independent(self):
        self.runtime()
        for n in range(2):
            value = unit(uid="unit_%03d" % (n + 1))
            value["statement"] = "x" * 2200
            self.assertLess(len(canonical(value)), 6000)
            self.write(value)
        value = unit(uid="unit_003")
        value["statement"] = "x" * 2200
        self.validate(value)
        caught = self.reject("memory_debt", lambda: self.write(value))
        self.assertIn("cut", caught.detail.casefold())
        self.assertLessEqual(len(caught.detail), 2048)
        self.assertNotIn(str(self.home), caught.detail)
        self.assertNotIn("x" * 128, caught.detail)

    def test_a30_token_gate_and_invalid_counters(self):
        self.runtime()
        def broken(text):
            raise ValueError("fixture token counter unavailable")
        for counter in (None, lambda text: 4001, lambda text: True, lambda text: -1,
                        lambda text: 1.5, lambda text: None, lambda text: "2", broken):
            context = replace(self.ctx, services=replace(self.ctx.services, token_count=counter))
            command = self.command({"agent_id": OWNER, "unit": unit()})
            self.reject("memory_debt", lambda: units.put(OWNER, unit(), command=command, ctx=context))
        for count, uid in ((4000, "unit_001"), (0, "unit_002")):
            context = replace(self.ctx, services=replace(self.ctx.services, token_count=lambda text, n=count: n))
            value = unit(uid=uid)
            command = self.command({"agent_id": OWNER, "unit": value})
            self.assertEqual(units.put(OWNER, value, command=command, ctx=context).value["unit"], value)

    def test_a30_missing_entry_and_unexpected_dependency_failure(self):
        self.runtime()
        self.write()
        with self.patch_seam(self.entry_module, "build", None):
            self.reject("memory_debt", lambda: self.write(unit(uid="unit_002")))
        with self.patch_seam(self.entry_module, "build", mock.Mock(side_effect=RuntimeError("fixture unexpected dependency"))):
            self.reject("internal", lambda: self.write(unit(uid="unit_002")))
        self.write(unit(uid="unit_002"))

    def test_a30_candidate_selection_excludes_private_units(self):
        self.runtime()
        self.write()
        private = unit(uid="unit_002")
        private.update(privacy="private", statement="private-fixture-marker")
        self.write(private)
        self.assertTrue(self.entry_calls)
        for _, selected in self.entry_calls:
            self.assertTrue(all(u["privacy"] != "private" for u in selected))
        successor = unit(uid="unit_003")
        successor["supersedes"] = ["unit_001"]
        self.write(successor)
        selected = self.entry_calls[-1][1]
        self.assertEqual([u["id"] for u in selected], ["unit_003"])

    def test_a34_original_source_hash_survives_supersession(self):
        self.runtime()
        source = self.shaped(uid="source01")
        self.write(source)
        successor = self.shaped(uid="source02")
        successor["supersedes"] = [source["id"]]
        self.write(successor)
        child = self.shaped(uid="child001")
        child["provenance"]["inherited_from"] = {"agent_id": OWNER, "unit_id": source["id"], "unit_sha256": sha(canonical(source))}
        # B5 binds provenance identity to original bytes; U17 owns current selection.
        self.assertEqual(self.write(child).value["unit"]["provenance"]["inherited_from"]["unit_sha256"], sha(canonical(source)))
        folded_source = units.get(OWNER, source["id"], ctx=self.ctx)["unit"]
        wrong_hash = copy.deepcopy(child)
        wrong_hash["id"] = "child002"
        wrong_hash["provenance"]["inherited_from"]["unit_sha256"] = sha(canonical(folded_source))
        self.reject("hash_mismatch", lambda: self.write(wrong_hash))

    def test_a34_source_existence_and_digest_codes(self):
        self.runtime()
        source = self.shaped(uid="source01")
        self.write(source)
        child = self.shaped(uid="child001")
        claim = {"agent_id": OWNER, "unit_id": source["id"], "unit_sha256": sha(canonical(source))}
        child["provenance"]["inherited_from"] = claim
        for field, invalid, code in (("agent_id", "missing-agent", "no_agent"),
                                     ("unit_id", "missing1", "conflict"),
                                     ("unit_sha256", "0" * 64, "hash_mismatch")):
            value = copy.deepcopy(child)
            value["provenance"]["inherited_from"][field] = invalid
            self.reject(code, lambda: self.write(value))
        self.write(child)

    def test_a34_source_eligibility_fences(self):
        self.runtime()
        self.open_run()
        sources = []
        sources.append(self.ruling().value["unit"])
        for n, (kind, level, privacy, lifecycle) in enumerate((
            ("lesson", 3, "internal", None), ("lesson", 2, "private", None),
            ("episode", 2, "internal", None), ("decision", 2, "internal", None),
            ("open_item", 2, "internal", None), ("workflow", 2, "internal", "candidate"),
            ("workflow", 2, "internal", "retired"))):
            source = self.shaped(kind, level, uid="source%02d" % n)
            source["privacy"] = privacy
            if lifecycle:
                source["body"]["status"] = lifecycle
            self.write(source)
            sources.append(source)
            self.assertNotIn("inheritable", source)
        for source in sources:
            child = self.shaped(uid="child001")
            child["provenance"]["inherited_from"] = {
                "agent_id": OWNER, "unit_id": source["id"], "unit_sha256": sha(canonical(source))}
            self.reject("conflict", lambda: self.write(child))
        for n, kind in enumerate(("lesson", "negative", "workflow")):
            source = self.shaped(kind, uid="admit_%02d" % n)
            if kind == "workflow":
                source["body"]["status"] = "promoted"
            self.write(source)
            child = self.shaped(uid="child_%02d" % n)
            child["provenance"]["inherited_from"] = {
                "agent_id": OWNER, "unit_id": source["id"], "unit_sha256": sha(canonical(source))}
            self.write(child)

    def test_a35_missing_committed_state_never_uses_projection(self):
        self.runtime()
        (self.home / "agents/ghost-agent").mkdir(parents=True)
        (self.home / "agents/ghost-agent/agent.json").write_bytes(canonical({"agent_id": "ghost-agent"}))
        self.reject("no_agent", lambda: self.write(unit(actor="ghost-agent"), owner="ghost-agent", actor="ghost-agent"))
        episode = self.shaped("episode")
        self.reject("no_run", lambda: self.write(episode))
        self.open_run()
        self.assertEqual(self.write(episode).value["unit"], episode)

    def test_a07_callbacks_use_snapshot_without_artifact_or_nested_actions(self):
        self.runtime()
        from contextlib import ExitStack
        original_transact = self.journal.transact
        app = self.require("lineage.core.app", "dispatch")
        def guarded(callback):
            def call(*args):
                with ExitStack() as stack:
                    for name in ("write_text", "write_bytes", "mkdir", "rename", "replace", "unlink"):
                        stack.enter_context(mock.patch("pathlib.Path." + name, side_effect=AssertionError("artifact write inside callback")))
                    stack.enter_context(mock.patch.object(app, "dispatch", side_effect=AssertionError("nested dispatch")))
                    stack.enter_context(mock.patch.object(self.journal, "transact", side_effect=AssertionError("nested transaction")))
                    stack.enter_context(mock.patch.object(self.journal, "snapshot", side_effect=AssertionError("snapshot re-read inside callback")))
                    stack.enter_context(mock.patch("subprocess.run", side_effect=AssertionError("subprocess inside callback")))
                    return callback(*args)
            return call
        validator = self.ctx.services.registry.validators["memory.put"]
        from types import MappingProxyType, SimpleNamespace
        registry = self.ctx.services.registry
        replacement_registry = SimpleNamespace(**{**vars(registry), "validators": MappingProxyType({**registry.validators, "memory.put": guarded(validator)})})
        self.ctx = replace(self.ctx, services=replace(self.ctx.services, registry=replacement_registry))
        def transact(command, prepare, render, *, ctx):
            return original_transact(command, guarded(prepare), guarded(render), ctx=ctx)
        with self.patch_seam(self.journal, "transact", transact):
            self.assertEqual(self.write(self.shaped()).value["unit"]["id"], "unit_001")

    def test_a34_source_receipts_are_reverified(self):
        self.runtime()
        source = self.shaped(uid="source01")
        self.write(source)
        child = self.shaped(uid="child001")
        child["receipts"] = [self.evidence(b"child evidence", "evidence/child.txt")]
        child["provenance"]["inherited_from"] = {"agent_id": OWNER, "unit_id": source["id"], "unit_sha256": sha(canonical(source))}
        (self.home / source["receipts"][0]["path"]).write_bytes(b"changed source evidence")
        self.reject("hash_mismatch", lambda: self.write(child))
