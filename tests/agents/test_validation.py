"""Strict direct arguments, hostile wire data and reference/skill admission."""
from copy import deepcopy
from unittest import mock
from lineage.core import app, schema
from lineage.core.errors import LineageError
from . import HASH, PINS, REFS, SEAT, OracleCase, agents, extension


class ValidationTests(OracleCase):
    def reject_create(self, code="bad_args", **changes):
        args = self.arguments(**changes)
        return self.reject(code, agents.create, **args, command=self.command(args), ctx=self.ctx)

    def test_a03_reference_membership_is_exact_by_id(self):
        for references in ([], [REFS[0]], [REFS[1]],
                           [REFS[0], {"id": "gold_s1", "sha256": HASH}],
                           [*REFS, {"id": "unknown", "sha256": HASH}],
                           [REFS[0], {"id": "unknown", "sha256": HASH}]):
            self.reject_create(references=references)

    def test_a04_stale_foundation_pin_is_hash_mismatch(self):
        pins = deepcopy(REFS)
        pins[0]["sha256"] = "0" * 64
        self.reject_create("hash_mismatch", references=pins)

    def test_a04_reference_verification_cannot_be_cached(self):
        self.create()
        references = self.require_peer("lineage.domain.references")
        args = self.arguments(agent_id="agent-two")
        with mock.patch.object(references, "require_pins", side_effect=LineageError("hash_mismatch", "bundled artifact changed")) as checked:
            self.reject("hash_mismatch", agents.create, **args, command=self.command(args), ctx=self.ctx)
        self.assertTrue(checked.called, "genesis bypassed required byte re-verification")

    def test_a06_unknown_skill_is_bad_args(self):
        self.reject_create("bad_args", skills=[{"skill_id": "missing-skill", "sha256": HASH}])

    def test_a06_explicit_skill_hash_mismatch_is_preserved(self):
        self.create()
        skills = self.require_peer("lineage.domain.skills")
        args = self.arguments(agent_id="agent-two", skills=[PINS[0]])
        with mock.patch.object(skills, "get", side_effect=LineageError("hash_mismatch", "immutable package changed")) as called:
            self.reject("hash_mismatch", agents.create, **args, command=self.command(args), ctx=self.ctx)
        self.assertTrue(called.called)
        self.assertTrue(all(call.kwargs.get("sha256") == PINS[0]["sha256"] for call in called.call_args_list))

    def test_a08_reserved_path_unicode_and_non_full_match_ids(self):
        for identifier in ("operator", "system", "../agent-one", "a/b", "agent-one\n", "ab", "Agent-one", "bad\ud800"):
            self.reject_create(agent_id=identifier)

    def test_a08_closed_complete_unique_seats(self):
        for seats in ([], [SEAT, SEAT], [{**SEAT, "extra": True}],
                      [{"model": "x", "effort": "Medium", "mode": "headless"}],
                      [{**SEAT, "mode": "unknown"}], [{**SEAT, "model": ""}],
                      [{**SEAT, "effort": "medium\n"}], [SEAT] * 17):
            self.reject_create(allowed_seats=seats)

    def test_a08_unknown_authority_and_record_fields_are_closed(self):
        # A-U12: a missing-agent handler raises the documented no_agent domain error.
        self.reject("no_agent", self.handler, "agent_get", {"agent_id": "missing-one"})
        for key, value in (("status", "promoted"), ("constitution", "forged"),
                           ("parents", ["parent-one"]), ("inherited_units", []),
                           ("agent_version", HASH), ("rule_overrides", {}),
                           ("authority", "operator")):
            args = {**self.arguments(), "agent": "system", "op_id": "operation0001", key: value}
            result = app.dispatch("agent_create", args, context=self.ctx, registry=self.reg)
            self.assertEqual(result.payload["code"], "bad_args")
            self.assertEqual(self.ledger(), b"")

    def test_a08_duplicate_keys_invalid_utf8_and_nonfinite_wire(self):
        self.handler("agent_list", {})
        from lineage.core import cli
        import io, json
        for raw in ('{"agent_id":"one","agent_id":"two"}',
                    '{"agent_id":"bad\\ud800"}', '{"limit":NaN}', '{"limit":Infinity}'):
            out, err = io.StringIO(), io.StringIO()
            code = cli.main(["--home", str(self.home), "call", "agent_list", "--json", raw],
                            registry=self.reg, stdout=out, stderr=err, stdin=io.BytesIO())
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(out.getvalue())["code"], "bad_args")
        with self.assertRaises(schema.SchemaError):
            schema.strict_loads(b'{"agent_id":"\xff"}')
        self.assertEqual(self.ledger(), b"")

    def test_a09_unknown_conflicting_and_expanding_overlays(self):
        self.reject_create("bad_args", workflow="review", overlays=["unknown-overlay"])
        compiler = self.require_peer("lineage.domain.constitution")
        for code in ("bad_args", "conflict"):
            with mock.patch.object(compiler, "compile_constitution", side_effect=LineageError(code, "overlay policy refusal")):
                self.reject_create(code, workflow="review", overlays=[])

    def test_a09_missing_compiler_is_internal_and_atomic(self):
        # No compiler is integrated in this workspace. An absent module is not
        # an empty constitution, a synthesized policy, or a passed acceptance.
        import sys
        with mock.patch.dict(sys.modules, {"lineage.domain.constitution": None}):
            self.reject_create("internal")

    def test_a26_invalid_read_actors_and_malformed_after(self):
        self.handler("agent_list", {})
        for tool in ("agent_get", "agent_list", "agent_brief"):
            for actor in ("bad/name", "agent-one\n", True, None, "ab"):
                args = {"agent": actor}
                if tool != "agent_list":
                    args["agent_id"] = "agent-one"
                result = app.dispatch(tool, args, context=self.ctx, registry=self.reg)
                self.assertEqual(result.payload["code"], "bad_args")
        self.assertEqual(self.ledger(), b"")

    def test_a26_operator_actor_grants_no_domain_authority(self):
        args = self.arguments(agent_id="operator")
        command = self.command(args, actor="operator")
        context = app.create_context(self.home, registry=self.reg, actor="operator")
        self.reject("bad_args", agents.create, **args, command=command, ctx=context)

    def test_a40_control_and_blank_text_is_rejected(self):
        for text in ("\n", "name\rforged", "bad\x00text", "   ", "\t"):
            for field in ("display_name", "language", "overlays"):
                self.reject_create(**{field: [text] if field == "overlays" else text})

    def test_a08_text_and_collection_bounds_and_closed_pins(self):
        for change in ({"display_name": ""}, {"display_name": "x" * 129},
                       {"language": ""}, {"language": "x" * 65},
                       {"overlays": ["x" * 65]}, {"overlays": ["same", "same"]},
                       {"skills": [{"skill_id": "skill-one", "sha256": HASH, "extra": 0}]},
                       {"skills": [{"skill_id": "skill-one", "sha256": "A" * 64}]},
                       {"references": [{**REFS[0], "extra": True}, REFS[1]]}):
            self.reject_create(**change)

    def test_seat_models_reject_blank_and_all_c0_c1_controls(self):
        models = [' ', '\u2003', ' \n\x00']
        models.extend('model' + chr(code) + 'name' for code in (*range(32), *range(127, 160)))
        for model in models:
            with self.subTest(model=repr(model)):
                self.reject_create(allowed_seats=[{**SEAT, 'model': model}])
