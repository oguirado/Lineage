"""Canonical public bytes and semantic, rather than serialization, hashing."""
from copy import deepcopy
from hashlib import sha256
from unittest.mock import patch

from tests.constitution.support import (
    BASE_RULE, ConstitutionCase, add_overlay, effective, exclusion,
    raw_repin, registry, repin, replacement, reverse_unordered,
)


class DeterminismTests(ConstitutionCase):
    def test_exact_complete_markdown_bytes(self):
        args = self.fixture()
        result = self.compile(args)
        self.assertEqual(result.markdown, self.exact_expected(args))
        self.assertEqual(result.markdown.decode("utf-8").encode("utf-8"), result.markdown)
        self.assertNotIn(b"\r", result.markdown)
        self.assertTrue(result.markdown.endswith(b"\n"))
        self.assertFalse(result.markdown.endswith(b"\n\n"))
        self.assertRegex(result.sha256, r"^[0-9a-f]{64}$")
        self.assertNotIn(args["expected_registry_sha256"].encode(), result.markdown)

    def test_reordered_objects_rules_roles_and_policies_are_identical(self):
        args = self.fixture(roles=("repairer", "author"))
        # Both declared roles have scoped-write baselines; no mixed-class overlay.
        add_overlay(args, replacement(args, roles=("author", "repairer")))
        before = deepcopy(args)
        result = self.compile(args)
        other = reverse_unordered(deepcopy(args))
        repin(other, reverse_unordered(registry(args)))
        self.assertNotEqual(args["registry_bytes"], other["registry_bytes"])
        self.assertEqual(self.compile(other), result)
        self.assertEqual(args, before)
        self.assertEqual(result.role_ids, ("author", "repairer"))
        self.assertEqual(result.capabilities, tuple(sorted(effective(args["role_matrix"], args["role_ids"]))))

    def test_duplicate_requested_roles_collapse(self):
        args = self.fixture(roles=("author", "cross_reviewer"))
        result = self.compile(args)
        args["role_ids"] = ["cross_reviewer", "author", "author", "cross_reviewer"]
        self.assertEqual(self.compile(args), result)

    def test_clock_and_environment_do_not_change_bytes(self):
        args = self.fixture()
        before = self.compile(args)
        with patch("time.time", return_value=123), patch.dict("os.environ", {"ORACLE_PUBLIC_CASE": "alternate"}):
            self.assertEqual(self.compile(args), before)
        with patch("time.time", return_value=987):
            self.assertEqual(self.compile(args), before)

    def test_serialization_whitespace_is_not_normative(self):
        args = self.fixture()
        result = self.compile(args)
        raw_repin(args, b" \n" + args["registry_bytes"] + b"\n ")
        self.assertEqual(self.compile(args), result)

    def test_normative_change_changes_digest_and_preserves_source_coordinates(self):
        args = self.fixture()
        before = self.compile(args)
        value = registry(args)
        value["rules"][0]["text"] = value["rules"][0]["text"].replace("agent identity", "distinct agent identity")
        repin(args, value)
        after = self.compile(args)
        self.assertNotEqual(before.markdown, after.markdown)
        self.assertNotEqual(before.sha256, after.sha256)
        self.assertEqual(after.sha256, sha256(after.markdown).hexdigest())
        self.citation_audit(after, args)

    def test_excluding_all_ordinary_rules_keeps_protected_rules_and_final_lf(self):
        args = self.fixture()
        add_overlay(args, exclusion(args))
        result = self.compile(args)
        self.assertNotIn(f"- {BASE_RULE}:".encode(), result.markdown)
        self.assertTrue(result.markdown.endswith(b"\n"))
        self.assertFalse(result.markdown.endswith(b"\n\n"))
        self.citation_audit(result, args)
