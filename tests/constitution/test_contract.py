"""Public interface, reference pins, purity, audit, and actual U07 handoff."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass
from hashlib import sha256
import inspect
from unittest.mock import patch

from tests.constitution.support import (
    BASE_RULE, ConstitutionCase, LANGUAGES, MAX_CAPABILITIES, PROTECTED, ROLES,
    ROOT, WRITE_CAPS, add_overlay, add_rule, effective, exclusion,
    policy_row, raw_repin, registry, repin, replacement, verbatim_key, public_violations,
)


class ContractTests(ConstitutionCase):
    def test_public_api_result_and_frozen_fields(self):
        api = self.api()
        signature = inspect.signature(api.compile_constitution)
        names = {"registry_bytes", "expected_registry_sha256", "expected_source_sha256",
                 "role_ids", "language", "role_matrix", "overlays"}
        self.assertEqual(set(signature.parameters), names)
        self.assertTrue(all(p.kind is inspect.Parameter.KEYWORD_ONLY
                            for p in signature.parameters.values()))
        args = self.fixture()
        result = self.compile(args)
        self.assertIs(type(result), api.CompiledConstitution)
        self.assertTrue(is_dataclass(result))
        self.assertEqual([field.name for field in fields(result)],
                         ["markdown", "sha256", "role_ids", "capabilities", "dispositions"])
        self.assertIs(type(result.markdown), bytes)
        self.assertIs(type(result.role_ids), tuple)
        self.assertIs(type(result.capabilities), tuple)
        self.assertIs(type(result.dispositions), tuple)
        self.assertEqual(result.sha256, sha256(result.markdown).hexdigest())
        self.assertEqual(result.role_ids, ("author",))
        for item in result.dispositions:
            self.assertIs(type(item), api.RuleDisposition)
            self.assertEqual([field.name for field in fields(item)], ["rule_id", "decision", "reason"])
            with self.assertRaises(FrozenInstanceError):
                item.reason = "explicit_exclusion"
        with self.assertRaises(FrozenInstanceError):
            result.sha256 = "0" * 64

    def test_compilation_and_failure_have_no_io_or_input_mutation(self):
        args = self.fixture()
        before = deepcopy(args)
        forbidden = ("builtins.open", "io.open", "os.open", "pathlib.Path.open",
                     "os.getenv", "os.urandom", "os.system", "subprocess.Popen",
                     "socket.socket", "time.time", "time.monotonic", "time.perf_counter",
                     "time.sleep", "random.random", "random.getrandbits", "uuid.uuid4",
                     "secrets.token_bytes")
        class NoEnvironment(dict):
            def __getitem__(self, key):
                raise AssertionError("Compiler accessed the environment")
            def get(self, *args):
                raise AssertionError("Compiler accessed the environment")
            def __iter__(self):
                raise AssertionError("Compiler inspected the environment")
        api = self.api()
        with ExitStack() as stack:
            for target in forbidden:
                stack.enter_context(patch(target, side_effect=AssertionError("Forbidden compiler side effect")))
            stack.enter_context(patch("os.environ", NoEnvironment()))
            result = api.compile_constitution(**args)
            bad = deepcopy(args)
            bad["expected_registry_sha256"] = "0" * 64
            with self.assertRaises(api.ConstitutionError) as caught:
                api.compile_constitution(**bad)
            self.assertEqual(caught.exception.code, "hash_mismatch")
        self.assertEqual(args, before)
        self.assertEqual(result.markdown, self.exact_expected(args))

    def test_exact_registry_byte_pin_precedes_decode(self):
        args = self.fixture()
        args["registry_bytes"] = b"!" + args["registry_bytes"][1:]
        self.rejection(args, "hash_mismatch", "registry_hash_mismatch")

    def test_source_provenance_pin_is_independent(self):
        args = self.fixture()
        value = registry(args)
        value["source"]["sha256"] = "0" * 64
        repin(args, value)
        self.rejection(args, "hash_mismatch", "source_hash_mismatch")

    def test_source_pin_cannot_substitute_for_registry_artifact_pin(self):
        args = self.fixture()
        args["expected_registry_sha256"] = args["expected_source_sha256"]
        self.rejection(args, "hash_mismatch", "registry_hash_mismatch")

    def test_missing_and_malformed_pins_are_bad_args(self):
        self.api()
        for name in ("expected_registry_sha256", "expected_source_sha256"):
            for malformed in (None, "", "a" * 63, "A" * 64, "z" * 64, 0, True):
                with self.subTest(argument=name, kind=type(malformed).__name__):
                    args = self.fixture()
                    args[name] = malformed
                    self.rejection(args, "bad_args", "invalid_input")
            args = self.fixture()
            del args[name]
            self.rejection(args, "bad_args", "invalid_input")

    def test_argument_shapes_precede_hash_checks(self):
        args = self.fixture()
        args["role_ids"] = "author"
        args["expected_registry_sha256"] = "0" * 64
        self.rejection(args, "bad_args", "invalid_input")

    def test_missing_source_fields_reject(self):
        for field in ("source", "rules", "schema"):
            args = self.fixture()
            value = registry(args)
            del value[field]
            repin(args, value)
            self.rejection(args, "bad_args", "invalid_input")
        for field in ("title", "sha256"):
            args = self.fixture()
            value = registry(args)
            del value["source"][field]
            repin(args, value)
            self.rejection(args, "bad_args", "invalid_input")

    def test_unknown_role_and_language_have_no_coercion(self):
        for roles in ([], ["review"], ["Author"], ["invented_role"], [1], [None]):
            args = self.fixture()
            args["role_ids"] = roles
            self.rejection(args, "bad_args", "unknown_role" if roles and isinstance(roles[0], str)
                           else "invalid_input")
        for language in ("Python", "rust", "", None, True):
            args = self.fixture()
            args["language"] = language
            self.rejection(args, "bad_args", {"unsupported_language", "invalid_input"})

    def test_complete_dispositions_and_exclusion_precedence(self):
        args = self.fixture(roles=("cross_reviewer",))
        add_rule(args, "GS-1-2", "L2: A role-specific obligation.", roles=("author",),
                 languages=("typescript",), requires=("repository_code_write",))
        add_rule(args, "GS-1-3", "L3: A language-specific obligation.",
                 languages=("typescript",), requires=("repository_code_write",))
        add_rule(args, "GS-1-4", "L4: A capability-specific obligation.", requires=("repository_code_write",))
        add_rule(args, "GS-1-5", "L5: An explicitly excluded obligation.")
        add_rule(args, "GS-1-6", "L6: An adapted obligation.")
        add_overlay(args, exclusion(args, rule_id="GS-1-5"))
        add_overlay(args, replacement(args, rule_id="GS-1-6"))
        result = self.compile(args)
        audit = {item.rule_id: (item.decision, item.reason) for item in result.dispositions}
        self.assertEqual(audit["GS-1-2"], ("excluded", "role_not_applicable"))
        self.assertEqual(audit["GS-1-3"], ("excluded", "language_not_applicable"))
        self.assertEqual(audit["GS-1-4"], ("excluded", "capability_not_applicable"))
        self.assertEqual(audit["GS-1-5"], ("excluded", "explicit_exclusion"))
        self.assertEqual(audit["GS-1-6"], ("included", "adapted"))
        self.assertEqual(audit[BASE_RULE], ("included", "as_registered"))
        ids = [item.rule_id for item in result.dispositions]
        self.assertEqual(ids, sorted(row["id"] for row in registry(args)["rules"]))
        self.assertEqual(len(ids), len(set(ids)))
        self.citation_audit(result, args)

    def test_actual_u07_pins_and_tamper_rejection(self):
        args = self.actual()
        self.citation_audit(self.compile(args), args)
        bad = deepcopy(args)
        bad["registry_bytes"] += b" "
        self.rejection(bad, "hash_mismatch", "registry_hash_mismatch")
        bad = deepcopy(args)
        value = registry(bad)
        value["source"]["sha256"] = "0" * 64
        repin(bad, value)
        self.rejection(bad, "hash_mismatch", "source_hash_mismatch")
        bad = deepcopy(args)
        bad["expected_registry_sha256"] = bad["expected_source_sha256"]
        self.rejection(bad, "hash_mismatch", "registry_hash_mismatch")

    def test_no_agent_version_or_birth_side_effect_is_returned(self):
        args = self.fixture()
        result = self.compile(args)
        self.assertEqual(result.sha256, sha256(result.markdown).hexdigest())
        for field in ("agent_version", "agent_id", "event", "skill_pin", "memory_receipt"):
            self.assertFalse(hasattr(result, field))


def integrated_role_test(role):
    def test(self):
        self.api()
        for language in LANGUAGES:
            with self.subTest(language=language):
                args = self.actual(role, language)
                before = deepcopy(args)
                result = self.compile(args)
                text = self.citation_audit(result, args)
                self.assertEqual(args, before)
                self.assertEqual(result.role_ids, (role,))
                self.assertEqual(set(result.capabilities), effective(args["role_matrix"], [role]))
                self.assertLessEqual(set(result.capabilities), MAX_CAPABILITIES[role])
                self.assertEqual(result.sha256, sha256(result.markdown).hexdigest())
                self.assertFalse(public_violations(text))
                included = {item.rule_id for item in result.dispositions if item.decision == "included"}
                self.assertLessEqual(set(PROTECTED), included)
                self.assertEqual([item.rule_id for item in result.dispositions],
                                 sorted(row["id"] for row in registry(args)["rules"]))
                if role in {"cross_reviewer", "privacy_verifier", "researcher", "performance_auditor"}:
                    self.assertFalse(WRITE_CAPS & set(result.capabilities))
                self.assertNotIn("Admission: ADMIT", text)
        for relative in ("lineage/domain/data/role_matrix.json", "lineage/domain/data/overlays.json"):
            self.assertFalse(public_violations((ROOT / relative).read_text(encoding="utf-8")))
    return test


for _role in ROLES:
    setattr(ContractTests, "test_integrated_role_" + _role, integrated_role_test(_role))


def integrated_scrub_test(index):
    def test(self):
        args = self.actual()
        scrubbed = sorted((row for row in registry(args)["rules"] if row["scrub"]),
                          key=lambda row: row["id"])
        self.assertEqual(len(scrubbed), 32)
        source = scrubbed[index]
        rule_id = source["id"]
        row = policy_row(args, rule_id)
        candidates = [(role, language) for role in sorted(source["roles"])
                      for language in sorted(row["languages"])
                      if set(row["requires"]) <= effective(args["role_matrix"], [role])]
        self.assertTrue(candidates, "HOLD: a marked rule has no exercisable applicability decision")
        role, language = candidates[0]
        current = self.actual(role, language)
        result = self.compile(current)
        text = self.citation_audit(result, current)
        disposition = next(item for item in result.dispositions if item.rule_id == rule_id)
        self.assertIn(disposition.reason, {"adapted", "explicit_exclusion"})
        source_body = source["text"].rsplit(" [CITED; ", 1)[0]
        self.assertNotIn(f"- {rule_id}: {source_body} [GOLD-S1/", text)
    return test


for _index in range(32):
    setattr(ContractTests, f"test_actual_scrub_index_{_index:02d}", integrated_scrub_test(_index))
