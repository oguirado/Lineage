"""Operation identity and original-prefix receipts through the frozen transaction API."""
import copy
from dataclasses import replace

from tests.skills import FILES, PIN, RuntimeCase, one, refusal_witness, skills


class ReplayOracle(RuntimeCase):
    def test_a11_original_publication_replays_after_retirement_and_new_head(self):
        original = self.publish(op="original", expected=0)
        captured = copy.deepcopy(original.value)
        self.publish(one("second"))
        self.retire(PIN)
        self.publish(one("advance"), skill_id="another")
        before = self.raw()
        replay = self.publish(op="original", expected=0)
        self.assertEqual(replay.value, captured)
        self.assertEqual(replay.event, original.event)
        self.assertEqual(replay.head, original.head)
        self.assertEqual(replay.sha256, original.sha256)
        self.assertFalse(replay.value["skill"]["retired"])
        self.assertEqual(self.raw(), before)
        self.assert_receipt(replay)

    def test_a11_retirement_replay_retains_original_commit(self):
        self.publish()
        original = self.retire(PIN, op="retirement", expected=1)
        self.publish(one("after"))
        before = self.raw()
        replay = self.retire(PIN, op="retirement", expected=0)
        self.assertEqual(replay.value, original.value)
        self.assertEqual(replay.event, original.event)
        self.assertEqual(self.raw(), before)

    def test_a12_changed_files_paths_order_and_skill_id_refused(self):
        self.publish(op="bound")
        changed = copy.deepcopy(FILES)
        changed[0]["content"] += "!"
        renamed = copy.deepcopy(FILES)
        renamed[0]["path"] = "docs/other.txt"
        for files, skill_id in [(changed, "sample"), (renamed, "sample"),
                               (list(reversed(FILES)), "sample"), (FILES, "another")]:
            with self.subTest(files=files, skill_id=skill_id):
                refusal_witness(self, self.LineageError, lambda: self.publish(files, skill_id, op="bound"), self.raw, "bad_op")

    def test_a12_same_identity_changed_tool_is_bad_op(self):
        self.publish(op="bound")
        self.assert_code("bad_op", lambda: self.retire(PIN, op="bound"))

    def test_a12_distinct_request_can_share_package_pin(self):
        first = self.publish(op="first")
        second = self.publish(list(reversed(FILES)), op="second")
        self.assertEqual(first.value["skill"]["sha256"], second.value["skill"]["sha256"])
        self.assertEqual(len(self.events()), 2)
        self.assertEqual(len(skills.list_skills(ctx=self.ctx)["skills"]), 1)
        self.assertNotEqual(first.value["commit"], second.value["commit"])

    def test_a13_new_operation_checks_revision_under_lock(self):
        self.assert_code("stale_rev", lambda: self.publish(expected=1))
        self.assertEqual(self.raw(), b"")
        first = self.publish(expected=0)
        self.assert_code("stale_rev", lambda: self.publish(one("next"), expected=0))
        second = self.publish(one("next"), expected=first.head)
        self.assertEqual(second.head, first.head + 1)
        self.assert_receipt(second)

    def test_a13_operation_identity_is_scoped_by_actor(self):
        first = self.publish(op="shared", actor="alpha")
        second = self.publish(one("bravo"), op="shared", actor="bravo")
        self.assertNotEqual(first.value["commit"], second.value["commit"])
        before = self.raw()
        self.assertEqual(self.publish(op="shared", actor="alpha").value, first.value)
        self.assertEqual(self.publish(one("bravo"), op="shared", actor="bravo").value, second.value)
        self.assertEqual(self.raw(), before)
        self.assertEqual(len(self.events()), 2)

    def test_a15_retirement_reason_participates_in_request_identity(self):
        self.publish()
        original = self.retire(PIN, reason="first reason", op="retire-bound")
        before = self.raw()
        self.assertEqual(self.retire(PIN, reason="first reason", op="retire-bound").value, original.value)
        self.assertEqual(self.raw(), before)
        self.assert_code("bad_op", lambda: self.retire(PIN, reason="different reason", op="retire-bound"))
        self.assertNotIn("reason", original.event["payload"])

    def test_a02_publish_function_command_context_must_agree(self):
        args = {"skill_id": "sample", "files": copy.deepcopy(FILES), "agent": "tester", "op_id": "agree"}
        valid = self.command("skill_publish", args)
        variants = [
            replace(valid, tool="skill_retire"),
            replace(valid, agent="someone"),
            replace(valid, op_id="different"),
            replace(valid, expected_head=0),
            replace(valid, args={**args, "skill_id": "another"}),
            replace(valid, args={**args, "files": one("different")}),
            replace(valid, args={**args, "sha256": PIN}),
            replace(valid, args={**args, "unexpected": True}),
            replace(valid, args={k: v for k, v in args.items() if k != "agent"}),
            replace(valid, args={k: v for k, v in args.items() if k != "op_id"}),
        ]
        for command in variants:
            with self.subTest(command=command):
                self.assert_code("bad_args", lambda: skills.publish("sample", FILES, command=command, ctx=self.ctx))
        other_ctx = replace(self.ctx, actor="someone")
        self.assert_code("bad_args", lambda: skills.publish("sample", FILES, command=valid, ctx=other_ctx))
        self.assert_receipt(skills.publish("sample", FILES, command=valid, ctx=self.ctx))

    def test_a02_retire_function_command_context_must_agree(self):
        self.publish()
        args = {"skill_id": "sample", "sha256": PIN, "reason": "reason", "agent": "tester", "op_id": "agree-retire"}
        valid = self.command("skill_retire", args)
        variants = [replace(valid, tool="skill_publish"), replace(valid, agent="someone"),
                    replace(valid, args={**args, "reason": "changed"}),
                    replace(valid, args={**args, "sha256": "0" * 64}),
                    replace(valid, args={**args, "skill_id": "another"}),
                    replace(valid, args={**args, "extra": 1}),
                    replace(valid, args={k: v for k, v in args.items() if k != "reason"})]
        for command in variants:
            with self.subTest(command=command):
                self.assert_code("bad_args", lambda: skills.retire("sample", PIN, "reason", command=command, ctx=self.ctx))
        self.assert_code("bad_args", lambda: skills.retire("sample", PIN, "reason", command=valid,
                                                          ctx=replace(self.ctx, actor="someone")))
        self.assert_receipt(skills.retire("sample", PIN, "reason", command=valid, ctx=self.ctx))

    def test_a02_direct_api_wrong_types_ids_reason_and_revision(self):
        for skill_id in (None, True, 3, [], {}, "ab", "Upper", "a" * 65, "abc\n", "\ud800"):
            with self.subTest(skill_id=repr(skill_id)):
                self.assert_code("bad_args", lambda: skills.get(skill_id, ctx=self.ctx))
                self.assert_code("bad_args", lambda: self.publish(skill_id=skill_id))
                self.assert_code("bad_args", lambda: self.retire(PIN, skill_id=skill_id))
        self.publish()
        for reason in (None, 2, False, [], "", "x" * 2049, "\udfff"):
            with self.subTest(reason=repr(reason)):
                self.assert_code("bad_args", lambda: self.retire(PIN, reason=reason))
        for revision in (True, -1, 1.5, 9007199254740992, "0"):
            with self.subTest(revision=revision):
                self.assert_code("bad_args", lambda: self.publish(expected=revision))
        for include in (None, 0, 1, "false", []):
            with self.subTest(include=include):
                self.assert_code("bad_args", lambda: skills.list_skills(include_retired=include, ctx=self.ctx))

    def test_a02_reserved_actors_are_ordinary_tool_actors(self):
        # A-U09: actor names must leave every actual CallContext capability unchanged.
        for actor in ("system", "operator"):
            with self.subTest(actor=actor):
                ctx = replace(self.ctx, actor=actor)
                original_context = replace(self.ctx, actor=actor)
                result = self.publish(skill_id="skill-" + actor, ctx=ctx)
                self.assertEqual(result.event["agent"], actor)
                self.assertEqual(ctx, original_context)
                self.assertEqual(result.event["kind"], "skill.published")


    def test_a02_direct_publish_rejects_invalid_files_and_commands(self):
        invalid = [None, True, 2, {}, "files", [None],
                   [{"path": "SKILL.md", "content": "", "extra": True}],
                   [{"path": "SKILL.md", "content": "\ud800"}],
                   [{"path": "SKILL.md", "content": None}]]
        for files in invalid:
            with self.subTest(files=repr(files)):
                command = self.command("skill_publish", {"skill_id": "sample", "files": files})
                self.assert_code("bad_args", lambda: skills.publish("sample", files, command=command, ctx=self.ctx))
        valid = self.command("skill_publish", {"skill_id": "sample", "files": FILES})
        for command in (None, {}, replace(valid, args=None), replace(valid, args=[]),
                        replace(valid, args={**valid.args, "op_id": "bad\n"}, op_id="bad\n"),
                        replace(valid, args={**valid.args, "agent": "Bad"}, agent="Bad")):
            with self.subTest(command=command):
                self.assert_code("bad_args", lambda: skills.publish("sample", FILES, command=command, ctx=self.ctx))

    def test_a02_direct_retirement_hashes_and_reason_bound(self):
        self.publish()
        for pin in (None, True, 1, [], {}, "F" * 64, "a" * 63, "a" * 64 + "\n", "\ud800"):
            with self.subTest(pin=repr(pin)):
                self.assert_code("bad_args", lambda: self.retire(pin))
        longest = self.retire(PIN, reason="é" * 2048)
        self.assert_receipt(longest)
        self.assertTrue(skills.get("sample", sha256=PIN, ctx=self.ctx)["skill"]["retired"])
