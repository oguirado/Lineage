"""Journal-backed catalogue behavior, without assumptions about private fold layout."""
import copy
from contextlib import ExitStack
import hashlib
import json
from unittest import mock

from tests.skills import FILES, PIN, RuntimeCase, independent_pin, one, retirement_witness, skills


class CatalogueOracle(RuntimeCase):
    def test_a09_committed_publication_and_independent_chain(self):
        result = self.publish()
        value = self.assert_receipt(result)
        self.assertEqual(result.event["kind"], "skill.published")
        self.assertEqual(result.event["payload"], {
            "skill_id": "sample", "sha256": PIN,
            "files": sorted(FILES, key=lambda f: f["path"]),
        })
        self.assertEqual(value["skill"], {"skill_id": "sample", "sha256": PIN,
            "retired": False, "files": sorted(FILES, key=lambda f: f["path"])})
        self.assertEqual(skills.get("sample", sha256=PIN, ctx=self.ctx), {"skill": value["skill"]})
        self.assert_projection()

    def test_a03_package_pin_is_independent_of_skill_id(self):
        first = self.publish(skill_id="alpha")
        second = self.publish(skill_id="bravo")
        self.assertEqual(first.value["skill"]["sha256"], PIN)
        self.assertEqual(second.value["skill"]["sha256"], PIN)
        self.assertNotEqual(first.event["id"], second.event["id"])

    def test_a10_multiple_versions_and_nonlexical_latest(self):
        variants = sorted([one("first"), one("second")], key=independent_pin, reverse=True)
        results = [self.publish(files) for files in variants]
        for files, result in zip(variants, results):
            self.assert_receipt(result)
            pin = independent_pin(files)
            self.assertEqual(skills.get("sample", sha256=pin, ctx=self.ctx)["skill"]["files"], files)
            self.assert_projection(pin, files=files)
        expected = sorted([{"skill_id": "sample", "sha256": independent_pin(f), "retired": False}
                           for f in variants], key=lambda item: (item["skill_id"], item["sha256"]))
        self.assertEqual(skills.list_skills(ctx=self.ctx), {"skills": expected})
        self.assertEqual(skills.get("sample", ctx=self.ctx), {"skill": results[-1].value["skill"]})

    def test_a14_retirement_is_exact_pin_and_schema_closed(self):
        first = self.publish()
        second = self.publish(one("new"))
        result = self.retire(PIN)
        self.assert_receipt(result)
        self.assertEqual(result.event["payload"], {"skill_id": "sample", "sha256": PIN})
        self.assertEqual(result.value, {"skill_id": "sample", "sha256": PIN, "retired": True,
                                       "commit": result.value["commit"]})
        retirement_witness(self, lambda: skills.get("sample", sha256=PIN, ctx=self.ctx), first.value["skill"]["files"])
        history = skills.get("sample", sha256=PIN, ctx=self.ctx)["skill"]
        self.assertTrue(history["retired"])
        self.assertEqual(history["files"], first.value["skill"]["files"])
        self.assertEqual(skills.list_skills(ctx=self.ctx), {"skills": [{
            "skill_id": "sample", "sha256": second.value["skill"]["sha256"], "retired": False}]})
        all_rows = skills.list_skills(include_retired=True, ctx=self.ctx)["skills"]
        self.assertEqual(len(all_rows), 2)
        self.assertEqual({r["sha256"]: r["retired"] for r in all_rows},
                         {PIN: True, second.value["skill"]["sha256"]: False})
        self.assert_projection()

    def test_a15_retirement_is_monotonic_across_distinct_operations(self):
        first = self.publish(op="publish-original")
        r1 = self.retire(PIN, op="retire-first")
        before = self.raw()
        self.assertEqual(self.retire(PIN, op="retire-first").value, r1.value)
        self.assertEqual(self.raw(), before)
        r2 = self.retire(PIN, op="retire-second")
        again = self.publish(op="republish-identical")
        self.assert_receipt(r2)
        self.assert_receipt(again)
        self.assertEqual(len(self.events()), 4)
        self.assertTrue(again.value["skill"]["retired"])
        self.assertEqual(skills.list_skills(ctx=self.ctx), {"skills": []})
        self.assertEqual(skills.list_skills(include_retired=True, ctx=self.ctx), {
            "skills": [{"skill_id": "sample", "sha256": PIN, "retired": True}]})
        self.assertEqual(first.value["skill"]["retired"], False)

    def test_a16_empty_catalogue_and_no_seed_discovery(self):
        (self.home / "skills/uncommitted").mkdir(parents=True)
        (self.home / "skills/uncommitted/SKILL.md").write_text("not published")
        from tests.skills import disk_image
        before = disk_image(self.home)
        self.assertEqual(skills.list_skills(ctx=self.ctx), {"skills": []})
        self.assertEqual(disk_image(self.home), before)
        self.assertEqual(self.raw(), b"")

    def test_a16_complete_deterministic_sorted_listing(self):
        expected = []
        for name, content in [("zulu", "z"), ("alpha", "a"), ("alpha", "b"), ("mike", "m")]:
            result = self.publish(one(content), skill_id=name)
            expected.append({"skill_id": name, "sha256": result.value["skill"]["sha256"], "retired": False})
        self.publish(one("a"), skill_id="alpha")
        expected.sort(key=lambda r: (r["skill_id"], r["sha256"]))
        self.assertEqual(skills.list_skills(ctx=self.ctx), {"skills": expected})
        self.retire(expected[0]["sha256"], skill_id=expected[0]["skill_id"])
        expected[0]["retired"] = True
        self.assertEqual(skills.list_skills(include_retired=True, ctx=self.ctx), {"skills": expected})
        self.assertEqual(skills.list_skills(ctx=self.ctx), {"skills": expected[1:]})

    def test_a16_capacity_is_internal_without_truncation(self):
        original = self.publish().event
        events = []
        for n in range(10001):
            event = copy.deepcopy(original)
            event["id"] = "e-" + format(n + 1, "016x")
            event["lamport"] = n + 1
            event["payload"]["skill_id"] = "skill-%05d" % n
            events.append(event)
        # A-U09: integrated snapshot returns a detached event tuple, not a Snapshot object.
        synthetic = tuple(events)
        original_snapshot = self.journal.snapshot
        with ExitStack() as stack:
            # Patch the documented seam and any bound import of that same public function.
            for name, value in list(vars(skills).items()):
                if value is original_snapshot:
                    stack.enter_context(mock.patch.object(skills, name, return_value=synthetic))
            stack.enter_context(mock.patch.object(self.journal, "snapshot", return_value=synthetic))
            self.assert_code("internal", lambda: skills.list_skills(ctx=self.ctx))

    def test_a17_unpinned_fallback_and_all_retired(self):
        variants = [one("one"), one("two"), one("three")]
        for files in variants:
            self.publish(files)
        self.retire(independent_pin(variants[-1]))
        self.assertEqual(skills.get("sample", ctx=self.ctx)["skill"]["sha256"], independent_pin(variants[1]))
        self.retire(independent_pin(variants[1]))
        self.assertEqual(skills.get("sample", ctx=self.ctx)["skill"]["sha256"], independent_pin(variants[0]))
        self.retire(independent_pin(variants[0]))
        self.assert_code("bad_args", lambda: skills.get("sample", ctx=self.ctx))
        for files in variants:
            self.assertTrue(skills.get("sample", sha256=independent_pin(files), ctx=self.ctx)["skill"]["retired"])

    def test_a17_republishing_active_pin_advances_publication_order(self):
        first = self.publish(one("older"))
        self.publish(one("newer"))
        third = self.publish(one("older"))
        self.assertEqual(skills.get("sample", ctx=self.ctx)["skill"], third.value["skill"])
        self.assertEqual(third.value["skill"]["sha256"], first.value["skill"]["sha256"])
        self.assertEqual(len(skills.list_skills(ctx=self.ctx)["skills"]), 2)
        self.assertEqual(len(self.events()), 3)

    def test_a18_missing_pin_and_invalid_syntax(self):
        self.assert_code("bad_args", lambda: skills.get("absent", ctx=self.ctx))
        self.publish()
        self.assert_code("bad_args", lambda: skills.get("sample", sha256="0" * 64, ctx=self.ctx))
        for value in ("bad", "F" * 64, "a" * 63, "a" * 64 + "\n", True, 1, [], "\ud800"):
            with self.subTest(value=repr(value)):
                self.assert_code("bad_args", lambda: skills.get("sample", sha256=value, ctx=self.ctx))
        self.assert_error_wire(self.dispatch("skill_get", {"skill_id": "absent"}), "bad_args")

    def test_a22_returns_and_publication_inputs_are_isolated(self):
        inputs = copy.deepcopy(FILES)
        command = self.command("skill_publish", {"skill_id": "sample", "files": inputs})
        published = skills.publish("sample", inputs, command=command, ctx=self.ctx)
        inputs[0]["content"] = "caller corruption"
        published.value["skill"]["files"][0]["content"] = "return corruption"
        fetched = skills.get("sample", ctx=self.ctx)
        fetched["skill"]["files"].clear()
        self.assertEqual(skills.get("sample", ctx=self.ctx)["skill"]["files"], sorted(FILES, key=lambda f: f["path"]))
        listing = skills.list_skills(ctx=self.ctx)
        listing["skills"][0]["retired"] = True
        self.assertFalse(skills.list_skills(ctx=self.ctx)["skills"][0]["retired"])

    def test_a22_runtime_homes_have_independent_catalogues(self):
        other = self.base / "other-home"
        other.mkdir()
        other_ctx = self.context(other, tag="other")
        self.publish()
        self.assertEqual(skills.list_skills(ctx=other_ctx), {"skills": []})
        foreign = self.publish(one("other"), skill_id="different", ctx=other_ctx)
        self.assertEqual(len(skills.list_skills(ctx=self.ctx)["skills"]), 1)
        self.assert_code("bad_args", lambda: skills.get("different", ctx=self.ctx))
        self.assertEqual(skills.get("different", ctx=other_ctx)["skill"], foreign.value["skill"])
