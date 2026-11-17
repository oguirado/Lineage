"""Complete policy coverage, explicit applicability, claims, and conflicts."""
from copy import deepcopy
from tests.constitution.support import (
    BASE_RULE, ConstitutionCase, LANGUAGES, PROTECTED, ROLES, add_overlay, add_rule,
    change_claim, exclusion, policy_row, registry, repin, replacement, verbatim_key,
)


class OverlayTests(ConstitutionCase):
    def test_matrix_requires_exact_rule_coverage(self):
        args = self.fixture()
        args["role_matrix"]["rules"] = [row for row in args["role_matrix"]["rules"]
                                          if row["rule_id"] != BASE_RULE]
        self.rejection(args, "bad_args", "incomplete_policy")
        args = self.fixture()
        args["role_matrix"]["rules"].append(deepcopy(policy_row(args, BASE_RULE)))
        self.rejection(args, "bad_args", {"duplicate_rule", "invalid_input"})
        args = self.fixture()
        unknown = deepcopy(policy_row(args, BASE_RULE))
        unknown["rule_id"] = "GS-9-999"
        args["role_matrix"]["rules"].append(unknown)
        self.rejection(args, "bad_args", "unknown_rule")

    def test_matrix_requires_exact_real_role_identifiers(self):
        args = self.fixture()
        args["role_matrix"]["roles"] = [row for row in args["role_matrix"]["roles"]
                                          if row["id"] != "cross_reviewer"]
        self.rejection(args, "bad_args", "incomplete_policy")
        for name in ("review", "invented_role"):
            args = self.fixture()
            next(row for row in args["role_matrix"]["roles"]
                 if row["id"] == "cross_reviewer")["id"] = name
            self.rejection(args, "bad_args", "unknown_role")

    def test_duplicate_and_unknown_registry_rules_reject(self):
        args = self.fixture()
        value = registry(args)
        value["rules"].append(deepcopy(value["rules"][0]))
        repin(args, value)
        self.rejection(args, "bad_args", "duplicate_rule")
        args = self.fixture()
        value = registry(args)
        value["rules"][0]["roles"] = ["invented_role"]
        repin(args, value)
        self.rejection(args, "bad_args", "unknown_role")

    def test_selected_scrub_requires_replacement_or_explicit_exclusion(self):
        for action in ("missing", "replace", "exclude"):
            args = self.fixture()
            value = registry(args)
            value["rules"][0]["scrub"] = True
            repin(args, value)
            if action == "missing":
                self.rejection(args, "bad_args", "unresolved_overlay")
                continue
            entry = replacement(args) if action == "replace" else exclusion(args)
            add_overlay(args, entry)
            result = self.compile(args)
            item = next(row for row in result.dispositions if row.rule_id == BASE_RULE)
            self.assertEqual((item.decision, item.reason),
                             ("included", "adapted") if action == "replace"
                             else ("excluded", "explicit_exclusion"))
            self.assertNotIn(b"D1: Preserve a safe", result.markdown)

    def test_inapplicable_scrub_is_a_filter_not_a_successful_adaptation(self):
        args = self.fixture(roles=("cross_reviewer",))
        add_rule(args, "GS-1-2", "L2: Public synthetic marked source.", roles=("author",), scrub=True)
        result = self.compile(args)
        item = next(row for row in result.dispositions if row.rule_id == "GS-1-2")
        self.assertEqual((item.decision, item.reason), ("excluded", "role_not_applicable"))

    def test_non_scrubbed_denied_verbatim_requires_overlay(self):
        args = self.fixture()
        key = verbatim_key(args["role_matrix"])
        policy_row(args, BASE_RULE)[key] = False
        self.rejection(args, "bad_args", "unresolved_overlay")
        add_overlay(args, replacement(args))
        result = self.compile(args)
        self.assertEqual(next(row.reason for row in result.dispositions if row.rule_id == BASE_RULE), "adapted")

    def test_applicability_boolean_is_required_and_native(self):
        for value in (None, 0, 1, "true", "missing"):
            args = self.fixture()
            key = verbatim_key(args["role_matrix"])
            if value == "missing":
                del policy_row(args, BASE_RULE)[key]
            else:
                policy_row(args, BASE_RULE)[key] = value
            self.rejection(args, "bad_args", "invalid_input")

    def test_inactive_claims_validate_against_declared_role_and_language(self):
        args = self.fixture()
        before = self.compile(args)
        entry = replacement(args, roles=("cross_reviewer",), language="typescript")
        add_overlay(args, entry)
        self.assertEqual(self.compile(args), before)
        change_claim(entry, "repository_access", "scoped_write")
        self.rejection(args, "conflict", "authority_escalation")
        args = self.fixture()
        entry = replacement(args, roles=("cross_reviewer",), language="typescript")
        change_claim(entry, "gate_language", "python")
        add_overlay(args, entry)
        self.rejection(args, "conflict", "authority_escalation")

    def test_multilanguage_and_mixed_capability_class_entries_reject(self):
        for action in ("replace", "exclude"):
            args = self.fixture()
            entry = replacement(args) if action == "replace" else exclusion(args)
            entry["languages"] = ["python", "typescript"]
            add_overlay(args, entry)
            self.rejection(args, "bad_args", "invalid_overlay")
            args = self.fixture()
            entry = replacement(args) if action == "replace" else exclusion(args)
            entry["role_ids"] = ["author", "cross_reviewer"]
            add_overlay(args, entry)
            self.rejection(args, "bad_args", "invalid_overlay")

    def test_equivalent_overlays_coalesce_despite_claim_and_reason_order(self):
        args = self.fixture()
        first = replacement(args)
        add_overlay(args, first)
        result = self.compile(args)
        second = deepcopy(first)
        second["claims"].reverse()
        second["reason"] = "Another public explanation with identical resolution."
        add_overlay(args, second)
        self.assertEqual(self.compile(args), result)
        args["overlays"]["entries"].reverse()
        self.assertEqual(self.compile(args), result)

    def test_different_replacements_and_replace_versus_exclude_conflict(self):
        for alternative in ("replace", "exclude"):
            args = self.fixture()
            add_overlay(args, replacement(args, text="L1: First public obligation."))
            second = replacement(args, text="L1: Second public obligation.") if alternative == "replace" else exclusion(args)
            add_overlay(args, second)
            error = self.rejection(args, "conflict", "contradictory_overlay")
            args["overlays"]["entries"].reverse()
            other = self.rejection(args, "conflict", "contradictory_overlay")
            self.assertEqual((error.code, error.detail), (other.code, other.detail))
            self.assertEqual(error.detail["rule_ids"], [BASE_RULE])
            self.assertNotIn("public obligation", str(error.detail))

    def test_claim_keys_are_closed_complete_and_unique(self):
        for variant in ("missing", "unknown", "duplicate"):
            args = self.fixture()
            entry = replacement(args)
            if variant == "missing":
                entry["claims"].pop()
            elif variant == "unknown":
                entry["claims"].append({"key": "invented_authority", "value": "allowed"})
            else:
                entry["claims"].append(deepcopy(entry["claims"][0]))
            add_overlay(args, entry)
            self.rejection(args, "bad_args", "invalid_overlay")

    def test_each_unsupported_or_wrong_baseline_claim_rejects(self):
        wrong = {"repository_access": "read_only", "ruling_writer": "agent",
                 "publication": "automatic", "source_parameters": "current_defaults",
                 "gate_language": "typescript"}
        for key, value in wrong.items():
            args = self.fixture()
            entry = replacement(args)
            change_claim(entry, key, value)
            add_overlay(args, entry)
            self.rejection(args, {"bad_args", "conflict"}, {"invalid_overlay", "authority_escalation"})

    def test_overlay_references_and_exclusion_shape_are_closed(self):
        for field, value, reason in (("rule_id", "GS-9-999", "unknown_rule"),
                                     ("role_ids", ["invented_role"], "unknown_role"),
                                     ("languages", ["rust"], "invalid_overlay")):
            args = self.fixture()
            entry = replacement(args)
            entry[field] = value
            add_overlay(args, entry)
            self.rejection(args, "bad_args", reason)
        for field, value in (("text", "An exclusion cannot carry text."),
                             ("claims", [{"key": "ruling_writer", "value": "operator_only"}])):
            args = self.fixture()
            entry = exclusion(args)
            entry[field] = value
            add_overlay(args, entry)
            self.rejection(args, "bad_args", "invalid_overlay")

    def test_overlay_roles_must_be_within_the_rule_projection(self):
        args = self.fixture()
        add_rule(args, "GS-1-2", "L2: Author-only obligation.", roles=("author",))
        add_overlay(args, replacement(args, rule_id="GS-1-2", roles=("cross_reviewer",)))
        self.rejection(args, "bad_args", "invalid_overlay")

    def test_python_mixed_gate_adaptations_keep_obligations_without_foreign_legs(self):
        for role in ("author", "performance_auditor"):
            args = self.fixture(roles=(role,))
            for rule_id, name, scrub in (("GS-2.4-4", "G-WHOLE", True),
                                         ("GS-2.4-7", "G-HOSTED-LIKE", False)):
                add_rule(args, rule_id, name + ": run cargo test and go test ./... in a clean environment.",
                         scrub=scrub, verbatim=False)
                add_overlay(args, replacement(args, rule_id=rule_id,
                    text=name + ": Run the complete Python suite in a clean environment for the assigned surface."))
            result = self.compile(args)
            text = self.citation_audit(result, args)
            self.assertIn("G-WHOLE: Run the complete Python suite in a clean environment", text)
            self.assertIn("G-HOSTED-LIKE: Run the complete Python suite in a clean environment", text)
            self.assertNotIn("cargo test", text)
            self.assertNotIn("go test", text)
            for rule_id in ("GS-2.4-4", "GS-2.4-7"):
                self.assertEqual(next(row.reason for row in result.dispositions if row.rule_id == rule_id), "adapted")

    def test_actual_python_compound_gates_are_retained_and_adapted(self):
        for role in ("author", "performance_auditor"):
            args = self.actual(role)
            # A-U08: U07 projects G-WHOLE to orchestrator, not performance_auditor;
            # use the read-only role intersection to exercise both applicable gates.
            if role == "performance_auditor":
                args["role_ids"].append("orchestrator")
            result = self.compile(args)
            self.citation_audit(result, args)
            for rule_id in ("GS-2.4-4", "GS-2.4-7"):
                line = next((line for line in result.markdown.decode().splitlines()
                             if line.startswith("- " + rule_id + ":")), None)
                self.assertIsNotNone(line, "Applicable compound gate was dropped")
                self.assertNotRegex(line, r"\b(?:cargo|rustc|gofmt|go test|go vet)\b")
                self.assertEqual(next(row.reason for row in result.dispositions if row.rule_id == rule_id), "adapted")

    def test_typescript_and_general_select_only_explicit_language_legs(self):
        for language in ("typescript", "general"):
            args = self.fixture(language=language)
            add_rule(args, "GS-2.4-4", "G-WHOLE: historic cargo test and go test ./... legs.", scrub=True, verbatim=False)
            text = ("G-WHOLE: Run the complete TypeScript suite in a clean environment." if language == "typescript"
                    else "G-WHOLE: Verify the complete assigned surface in a clean environment using its declared checks.")
            add_overlay(args, replacement(args, rule_id="GS-2.4-4", text=text))
            add_rule(args, "GS-1-2", "L2: Python-only obligation.", languages=("python",))
            result = self.compile(args)
            output = self.citation_audit(result, args)
            self.assertIn(text, output)
            self.assertNotIn("cargo test", output)
            self.assertNotIn("go test", output)
            self.assertNotIn("Python-only obligation", output)
            self.assertEqual(next(row.reason for row in result.dispositions if row.rule_id == "GS-1-2"),
                             "language_not_applicable")

    def test_historical_seat_values_never_become_present_defaults(self):
        args = self.fixture(roles=("orchestrator",))
        for index in range(1, 10):
            rule_id = f"GS-5-{index}"
            add_rule(args, rule_id,
                     f"DERIVED.SEAT.fixture{index}: historical model FIXTURE_MODEL and quota 777; ACTIVE ASSEMBLED DRAFT.",
                     scrub=True, verbatim=False)
            add_overlay(args, replacement(args, rule_id=rule_id,
                text="Historical seat parameters and statuses are source evidence only; they select no present model or admission default."))
        result = self.compile(args)
        text = self.citation_audit(result, args)
        self.assertNotIn("FIXTURE_MODEL", text)
        self.assertNotIn("777", text)
        self.assertNotIn("DERIVED.SEAT", text)
        self.assertEqual(set(result.capabilities), {"read", "review", "schedule", "memory_write"})
        self.assertNotIn("Admission: ADMIT", text)
