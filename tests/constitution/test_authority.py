"""Capability ceilings, composition, and immutable authority invariants."""
from copy import deepcopy
from tests.constitution.support import (
    BASE_RULE, ConstitutionCase, LANGUAGES, MAX_CAPABILITIES, PROTECTED, ROLES, WRITE_CAPS,
    add_overlay, change_claim, effective, exclusion, policy_row, registry, repin,
    replacement,
)


class AuthorityTests(ConstitutionCase):
    def test_reviewers_keep_own_memory_without_repository_authority(self):
        self.api()
        for role in ("cross_reviewer", "privacy_verifier", "researcher", "performance_auditor"):
            with self.subTest(role=role):
                args = self.fixture(roles=(role,))
                result = self.compile(args)
                self.assertEqual(set(result.capabilities), MAX_CAPABILITIES[role])
                self.assertIn("memory_write", result.capabilities)
                self.assertFalse(WRITE_CAPS & set(result.capabilities))

    def test_matrix_cannot_expand_any_reviewer_ceiling(self):
        for role in ("cross_reviewer", "privacy_verifier", "researcher", "performance_auditor"):
            for capability in WRITE_CAPS:
                args = self.fixture(roles=(role,))
                row = next(row for row in args["role_matrix"]["roles"] if row["id"] == role)
                row["capabilities"].append(capability)
                self.rejection(args, "conflict", "authority_escalation")

    def test_overlay_write_claim_cannot_expand_reviewer_authority(self):
        args = self.fixture(roles=("cross_reviewer",))
        entry = replacement(args)
        change_claim(entry, "repository_access", "scoped_write")
        add_overlay(args, entry)
        self.rejection(args, "conflict", "authority_escalation")

    def test_author_plus_reviewer_uses_intersection_in_both_orders(self):
        args = self.fixture(roles=("author", "cross_reviewer"))
        result = self.compile(args)
        self.assertEqual(set(result.capabilities), {"read", "memory_write"})
        self.assertFalse(WRITE_CAPS & set(result.capabilities))
        args["role_ids"].reverse()
        self.assertEqual(self.compile(args), result)
        args["role_ids"].append("author")
        self.assertEqual(self.compile(args), result)

    def test_writers_have_exact_distinct_ceiling_and_no_privileged_capability(self):
        for role in ("author", "oracle_writer", "repairer"):
            args = self.fixture(roles=(role,))
            result = self.compile(args)
            self.assertEqual(set(result.capabilities), MAX_CAPABILITIES[role])
            self.assertFalse(set(result.capabilities) & {"commit", "push", "deploy", "install",
                                                       "create_accounts", "operator_rulings", "publication"})
        args = self.fixture()
        row = next(row for row in args["role_matrix"]["roles"] if row["id"] == "author")
        row["capabilities"].append("publication")
        self.rejection(args, "bad_args", "invalid_input")

    def test_matrix_may_restrict_but_never_union_capabilities(self):
        args = self.fixture(roles=("author", "repairer"))
        for row in args["role_matrix"]["roles"]:
            if row["id"] == "repairer":
                row["capabilities"] = ["read"]
        # Protected entry claims must match their declared, now restricted role.
        args["overlays"]["entries"] = []
        # Test only a black-box restriction if the protected source form is admitted;
        # use reviewed read-only protected entries from an independent read-only fixture.
        read_only = self.fixture(roles=("cross_reviewer",))
        for entry in read_only["overlays"]["entries"]:
            if "cross_reviewer" in entry["role_ids"]:
                adapted = deepcopy(entry)
                adapted["role_ids"] = ["repairer"]
                args["overlays"]["entries"].append(adapted)
        result = self.compile(args)
        self.assertEqual(result.capabilities, ("read",))

    def test_empty_capability_set_is_valid_and_never_defaults_to_maximum(self):
        args = self.fixture(roles=("cross_reviewer",))
        row = next(row for row in args["role_matrix"]["roles"] if row["id"] == "cross_reviewer")
        row["capabilities"] = []
        result = self.compile(args)
        self.assertEqual(result.capabilities, ())
        self.assertLessEqual(set(PROTECTED), {item.rule_id for item in result.dispositions
                                             if item.decision == "included"})

    def test_protected_rules_appear_for_every_role_and_language(self):
        for role in ROLES:
            for language in LANGUAGES:
                args = self.fixture(roles=(role,), language=language)
                result = self.compile(args)
                self.assertLessEqual(set(PROTECTED), {row.rule_id for row in result.dispositions
                                                     if row.decision == "included"})
                self.citation_audit(result, args)

    def test_protected_rules_cannot_be_excluded_or_reworded(self):
        for rule_id in PROTECTED:
            for action in ("exclude", "replace"):
                args = self.fixture()
                args["overlays"]["entries"] = [entry for entry in args["overlays"]["entries"]
                                                 if entry["rule_id"] != rule_id]
                entry = exclusion(args, rule_id=rule_id) if action == "exclude" else replacement(
                    args, rule_id=rule_id, text="A caller supplied alternate authority sentence.")
                add_overlay(args, entry)
                self.rejection(args, "conflict", "protected_rule_change")

    def test_protected_rules_cannot_be_role_or_language_filtered(self):
        for rule_id in PROTECTED:
            args = self.fixture()
            policy_row(args, rule_id)["languages"] = ["python"]
            self.rejection(args, "conflict", "protected_rule_change")
            args = self.fixture()
            value = registry(args)
            next(row for row in value["rules"] if row["id"] == rule_id)["roles"].remove("author")
            repin(args, value)
            self.rejection(args, "conflict", "protected_rule_change")

    def test_protected_rules_cannot_acquire_write_prerequisites(self):
        for rule_id in PROTECTED:
            args = self.fixture()
            policy_row(args, rule_id)["requires"] = ["repository_code_write"]
            self.rejection(args, "conflict", "protected_rule_change")

    def test_protected_claim_changes_reject_with_stable_conflict(self):
        for rule_id in PROTECTED:
            args = self.fixture()
            args["overlays"]["entries"] = [entry for entry in args["overlays"]["entries"]
                                             if entry["rule_id"] != rule_id]
            entry = replacement(args, rule_id=rule_id)
            change_claim(entry, "ruling_writer", "agent")
            add_overlay(args, entry)
            first = self.rejection(args, "conflict", {"protected_rule_change", "authority_escalation"})
            args["overlays"]["entries"].reverse()
            second = self.rejection(args, "conflict", {"protected_rule_change", "authority_escalation"})
            self.assertEqual((first.code, first.detail), (second.code, second.detail))

    def test_checked_in_writer_prose_preserves_scope_and_oracle_boundaries(self):
        for role in ("author", "oracle_writer", "repairer"):
            args = self.actual(role)
            text = self.compile(args).markdown.decode("utf-8").casefold()
            self.assertIn("scope", text, "Reviewed writer prose must state its separately assigned scope")
            self.assertIn("oracle", text)
            self.assertTrue("frozen" in text or "immutable" in text)
            self.assertIn("operator", text)
