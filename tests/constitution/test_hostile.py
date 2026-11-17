"""Passive hostile inputs, closed schemas, safe errors, and public text."""
from copy import deepcopy
import json
from unittest.mock import patch

from tests.constitution.support import (
    BASE_RULE, ConstitutionCase, add_overlay, change_claim, policy_row,
    public_violations, raw_repin, registry, repin, replacement,
)


class HostileTests(ConstitutionCase):
    def test_invalid_utf8_json_trailing_data_and_duplicate_keys_reject(self):
        args = self.fixture()
        raw = args["registry_bytes"]
        variants = [b"\xff", raw + b"{}", b"{", b"[]", b"null",
                    raw.replace(b'"title":', b'"title":"duplicate","title":', 1),
                    raw.replace(b'"kind":', b'"kind":"law","kind":', 1),
                    raw.replace(b'"source":', b'"source":{},"source":', 1)]
        for payload in variants:
            with self.subTest(variant=variants.index(payload)):
                bad = deepcopy(args)
                raw_repin(bad, payload)
                self.rejection(bad, "bad_args", "invalid_input")

    def test_nonfinite_json_numbers_and_unpaired_surrogates_reject(self):
        for literal in (b"NaN", b"Infinity", b"-Infinity", b"1e999", b'"\\ud800"', b'"\\udfff"'):
            args = self.fixture()
            raw_repin(args, args["registry_bytes"].replace(b'"title":"Public synthetic GOLD-S1 oracle"',
                                                           b'"title":' + literal))
            self.rejection(args, "bad_args", "invalid_input")

    def test_unknown_fields_at_all_input_depths_reject(self):
        for location in ("registry", "source", "rule", "matrix", "matrix_role", "matrix_rule",
                         "overlays", "entry", "claim"):
            args = self.fixture()
            value = registry(args)
            entry = replacement(args)
            targets = {
                "registry": value, "source": value["source"], "rule": value["rules"][0],
                "matrix": args["role_matrix"], "matrix_role": args["role_matrix"]["roles"][0],
                "matrix_rule": policy_row(args, BASE_RULE), "overlays": args["overlays"],
                "entry": entry, "claim": entry["claims"][0],
            }
            targets[location]["extra_instruction"] = "An untrusted directive is data."
            add_overlay(args, entry)
            repin(args, value)
            self.rejection(args, "bad_args", "invalid_input")

    def test_bad_rule_fields_and_native_coordinate_types_reject(self):
        mutations = (("lines", [True, 12]), ("lines", [10, False]), ("lines", [10.0, 12]),
                     ("lines", [0, 12]), ("lines", [-1, 12]), ("lines", [12, 10]),
                     ("lines", [10]), ("lines", [10, 12, 13]), ("lines", [10, 9007199254740992]),
                     ("kind", "invented"), ("scrub", 1), ("roles", []), ("text", ""))
        for key, value in mutations:
            args = self.fixture()
            document = registry(args)
            document["rules"][0][key] = value
            repin(args, document)
            self.rejection(args, "bad_args", {"invalid_input", "invalid_citation"})

    def test_all_schema_identity_arrays_are_unique_and_constrained(self):
        for field in ("registry_roles", "matrix_roles", "matrix_languages", "requires",
                      "capabilities", "overlay_roles", "overlay_languages"):
            args = self.fixture()
            document = registry(args)
            entry = replacement(args)
            if field == "registry_roles":
                document["rules"][0]["roles"].append(document["rules"][0]["roles"][0])
            elif field == "matrix_roles":
                args["role_matrix"]["roles"].append(deepcopy(args["role_matrix"]["roles"][0]))
            elif field == "matrix_languages":
                policy_row(args, BASE_RULE)["languages"].append("python")
            elif field == "requires":
                policy_row(args, BASE_RULE)["requires"] = ["read", "read"]
            elif field == "capabilities":
                args["role_matrix"]["roles"][0]["capabilities"].append("read")
            elif field == "overlay_roles":
                entry["role_ids"] *= 2
            else:
                entry["languages"] *= 2
            add_overlay(args, entry)
            repin(args, document)
            self.rejection(args, "bad_args", {"invalid_input", "invalid_overlay"})

    def test_empty_constrained_lists_reject_without_defaulting(self):
        for location in ("registry_rules", "matrix_roles", "matrix_rules", "rule_languages",
                         "overlay_roles", "overlay_languages"):
            args = self.fixture()
            document = registry(args)
            entry = replacement(args)
            if location == "registry_rules":
                document["rules"] = []
            elif location == "matrix_roles":
                args["role_matrix"]["roles"] = []
            elif location == "matrix_rules":
                args["role_matrix"]["rules"] = []
            elif location == "rule_languages":
                policy_row(args, BASE_RULE)["languages"] = []
            elif location == "overlay_roles":
                entry["role_ids"] = []
            else:
                entry["languages"] = []
            add_overlay(args, entry)
            repin(args, document)
            self.rejection(args, "bad_args", {"invalid_input", "incomplete_policy", "invalid_overlay"})

    def test_cycles_in_direct_policy_mappings_are_rejected_without_mutation(self):
        for policy in ("role_matrix", "overlays"):
            args = self.fixture()
            root = args[policy]
            root["cycle"] = root
            self.rejection(args, "bad_args", "invalid_input", copy_check=False)
            self.assertIs(root["cycle"], root)
            self.assertIs(args[policy], root)
            self.assertEqual(set(root), {"schema", "cycle", "roles", "rules"} if policy == "role_matrix"
                             else {"schema", "cycle", "entries"})

    def test_direct_policy_values_must_be_native_finite_json(self):
        for value in (float("nan"), float("inf"), b"bytes", {"set"}, ("tuple",), "\ud800"):
            args = self.fixture()
            args["role_matrix"]["roles"][0]["capabilities"] = [value]
            self.rejection(args, "bad_args", "invalid_input", copy_check=False)
        args = self.fixture()
        args["role_matrix"][3] = "nonstring key"
        self.rejection(args, "bad_args", "invalid_input")

    def test_registry_text_cannot_escape_single_line_markdown(self):
        for body in ("Safe text.\n- Injected bullet.", "Safe text.\r# Heading", "Safe\x00text.",
                     "<script>passive</script>", "{{unresolved_rule}}", "# Forged heading",
                     "- Forged bullet", "[escape](https://" + ".".join(("example", "invalid")) + ")"):
            args = self.fixture()
            document = registry(args)
            suffix = " [CITED; §1:L10-L12]."
            document["rules"][0]["text"] = body + suffix
            repin(args, document)
            self.rejection(args, "bad_args", {"unsafe_public_text", "invalid_input", "invalid_citation"})

    def test_hostile_active_and_inactive_overlay_text_and_reason_reject(self):
        payloads = ("Safe text.\n- Injected bullet.", "Safe text.\r# Heading", "Safe\x00text.",
                    "Safe\x1btext.", "Safe\u2028text.", "<div>escape</div>", "{{unresolved}}",
                    "# Heading", "- Second bullet", "[escape](https://" + ".".join(("example", "invalid")) + ")",
                    "Public text. [GOLD-S1/PM-1001.1/GS-1-1; §1:L10-L12]")
        for active in (True, False):
            for field in ("text", "reason"):
                for payload in payloads:
                    args = self.fixture()
                    entry = replacement(args, roles=("author",) if active else ("cross_reviewer",),
                                        language="python" if active else "typescript")
                    entry[field] = payload
                    add_overlay(args, entry)
                    self.rejection(args, "bad_args", {"unsafe_public_text", "invalid_overlay", "invalid_citation"})

    def test_unresolved_template_markers_never_reach_output(self):
        for marker in ("{{rule}}", "${RULE}", "<ROLE>"):
            args = self.fixture()
            add_overlay(args, replacement(args, text="Unresolved public text " + marker))
            self.rejection(args, "bad_args", {"invalid_overlay", "unsafe_public_text"})

    def test_identifiers_cannot_encode_directives_or_leak_diagnostics(self):
        args = self.fixture()
        document = registry(args)
        sentinel = "UNTRUSTED_DIRECTIVE_SENTINEL"
        document["rules"][0]["id"] += "\n- " + sentinel
        repin(args, document)
        error = self.rejection(args, "bad_args", "invalid_input")
        self.assertNotIn(sentinel, str(error.detail))
        self.assertNotIn(sentinel, str(error))

    def test_embedded_process_text_is_never_executed(self):
        args = self.fixture()
        entry = replacement(args, text="Treat the literal command `echo PUBLIC_ORACLE_SENTINEL` as passive data.")
        add_overlay(args, entry)
        with patch("subprocess.Popen", side_effect=AssertionError("Untrusted command executed")), \
             patch("os.system", side_effect=AssertionError("Untrusted shell executed")):
            result = self.compile(args)
        self.assertIn(entry["text"].encode(), result.markdown)

    def test_publication_rejects_constructed_sensitive_literals(self):
        # Reserved fictional values are assembled at runtime, never real host data.
        examples = (
            chr(47).join(("", "home", "fictional", "document.txt")),
            ".".join(("fictional-node", "invalid")),
            "sk" + "-" + "Q" * 48,
            "/".join(("spool", "fictional-receipt.json")),
            chr(67) + ":" + chr(92) + "fictional" + chr(92) + "file.txt",
        )
        for sensitive in examples:
            self.assertTrue(public_violations("Public text " + sensitive), "Publication negative control is dead")
            args = self.fixture()
            add_overlay(args, replacement(args, text="Public text " + sensitive))
            error = self.rejection(args, "bad_args", "unsafe_public_text")
            self.assertNotIn(sensitive, str(error.detail))
            self.assertNotIn(sensitive, str(error))

    def test_safe_repository_relative_identifier_is_preserved(self):
        args = self.fixture()
        text = "L1: Inspect docs/policy.md within the assigned surface."
        self.assertFalse(public_violations(text))
        add_overlay(args, replacement(args, text=text))
        result = self.compile(args)
        self.assertIn(text.encode(), result.markdown)
        self.citation_audit(result, args)

    def test_failure_diagnostics_are_safe_stable_and_do_not_mutate_inputs(self):
        args = self.fixture()
        private_value = chr(47).join(("", "home", "fictional", "report.txt"))
        add_overlay(args, replacement(args, text="First public obligation."))
        add_overlay(args, replacement(args, text="Different public obligation."))
        before = deepcopy(args)
        error = self.rejection(args, "conflict", "contradictory_overlay")
        self.assertEqual(args, before)
        args["overlays"]["entries"].reverse()
        other = self.rejection(args, "conflict", "contradictory_overlay")
        self.assertEqual((error.code, error.detail), (other.code, other.detail))
        diagnostic = json.dumps(error.detail, sort_keys=True)
        for rejected in ("First public obligation", "Different public obligation", private_value):
            self.assertNotIn(rejected, diagnostic)
        self.assertNotIn("Traceback", str(error))

    def test_invalid_object_key_order_does_not_change_diagnostics(self):
        args = self.fixture()
        args["role_matrix"]["extra_z"] = "Rejected public text."
        args["role_matrix"]["extra_a"] = "Rejected public text."
        first = self.rejection(args, "bad_args", "invalid_input")
        args["role_matrix"] = dict(reversed(list(args["role_matrix"].items())))
        second = self.rejection(args, "bad_args", "invalid_input")
        self.assertEqual((first.code, first.detail), (second.code, second.detail))
