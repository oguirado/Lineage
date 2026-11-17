"""Citation coordinates, exact provenance suffixes, and normative layout."""
from dataclasses import replace
from tests.constitution.support import ConstitutionCase, BASE_RULE, registry, repin, replacement, add_overlay


class CitationTests(ConstitutionCase):
    def test_every_bullet_resolves_and_original_names_survive(self):
        args = self.fixture()
        result = self.compile(args)
        text = self.citation_audit(result, args)
        self.assertIn("D1: Preserve a safe [label]", text)
        self.assertIn("I20", text)
        self.assertIn("I21", text)
        self.assertIn("I22", text)
        self.assertNotIn("/D1;", text)

    def test_mismatched_section_endpoint_and_extra_citation_reject(self):
        for transform in (
            lambda text: text.replace("§1:L10-L12", "§2:L10-L12"),
            lambda text: text.replace("L10-L12", "L10-L13"),
            lambda text: text + " [GOLD-S1/PM-1001.1/GS-1-1; §1:L10-L12]",
            lambda text: text.replace(" [CITED;", " [CITED; §9:L1-L2]. [CITED;"),
        ):
            args = self.fixture()
            value = registry(args)
            value["rules"][0]["text"] = transform(value["rules"][0]["text"])
            repin(args, value)
            self.rejection(args, "bad_args", {"invalid_citation", "unsafe_public_text"})

    def test_identifier_numeric_section_must_match_section(self):
        args = self.fixture()
        value = registry(args)
        value["rules"][0]["section"] = "§3.1"
        value["rules"][0]["text"] = value["rules"][0]["text"].replace("§1:", "§3.1:")
        repin(args, value)
        self.rejection(args, "bad_args", {"invalid_citation", "invalid_input"})

    def test_unknown_citation_identity_is_not_accepted_as_a_rule(self):
        args = self.fixture()
        entry = replacement(args, rule_id="GS-9-999")
        add_overlay(args, entry)
        self.rejection(args, "bad_args", "unknown_rule")

    def test_replacement_cannot_supply_a_counterfeit_source_citation(self):
        for suffix in (" [GOLD-S1/PM-1001.1/GS-1-1; §1:L10-L12]",
                       " [CITED; §1:L10-L12]."):
            args = self.fixture()
            add_overlay(args, replacement(args, text="Public adaptation." + suffix))
            self.rejection(args, "bad_args", {"invalid_citation", "invalid_overlay", "unsafe_public_text"})

    def test_citation_audit_rejects_forged_missing_or_wrong_coordinate_lines(self):
        args = self.fixture()
        result = self.compile(args)
        self.citation_audit(result, args)
        for old, new in (("GS-1-1;", "GS-9-999;"), ("L10-L12]", "L10-L13]"),
                         ("§1:L10-L12]", "§§1:L10-L12]")):
            damaged = replace(result, markdown=result.markdown.replace(old.encode(), new.encode()))
            with self.assertRaises(AssertionError):
                self.citation_audit(damaged, args)

    def test_coordinate_pair_stays_ordered(self):
        args = self.fixture()
        value = registry(args)
        value["rules"][0]["lines"] = [12, 10]
        repin(args, value)
        self.rejection(args, "bad_args", {"invalid_input", "invalid_citation"})
