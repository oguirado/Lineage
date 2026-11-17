"""U07 role projection and read-only compound-gate regression coverage."""
from tests.constitution.support import ConstitutionCase, LANGUAGES


class ReviewH1Tests(ConstitutionCase):
    def test_auditor_alone_respects_shipped_rule_projection(self):
        # A-U08: Pin the standalone auditor behavior to the integrated U07 projection.
        for language in LANGUAGES:
            with self.subTest(language=language):
                args = self.actual("performance_auditor", language)
                result = self.compile(args)
                self.citation_audit(result, args)
                audit = {row.rule_id: row for row in result.dispositions}
                self.assertEqual((audit["GS-2.4-4"].decision,
                                  audit["GS-2.4-4"].reason),
                                 ("excluded", "role_not_applicable"))
                self.assertEqual((audit["GS-2.4-7"].decision,
                                  audit["GS-2.4-7"].reason),
                                 ("included", "adapted"))
                self.assertNotIn(b"- GS-2.4-4:", result.markdown)

    def test_read_only_compound_gate_projection_is_order_independent(self):
        # A-U08: Retain compound gates through applicable read-only role arguments.
        for language in LANGUAGES:
            with self.subTest(language=language):
                args = self.actual("performance_auditor", language)
                args["role_ids"].append("orchestrator")
                result = self.compile(args)
                text = self.citation_audit(result, args)
                self.assertEqual(result.capabilities, ("memory_write", "read", "review"))
                audit = {row.rule_id: row for row in result.dispositions}
                for rule_id in ("GS-2.4-4", "GS-2.4-7"):
                    self.assertEqual((audit[rule_id].decision, audit[rule_id].reason),
                                     ("included", "adapted"))
                    line = next(line for line in text.splitlines()
                                if line.startswith("- " + rule_id + ":"))
                    self.assertNotRegex(line, r"\b(?:cargo|rustc|gofmt|go test|go vet)\b")
                self.assertIn("complete applicable", text)
                self.assertIn("empty caches", text)
                args["role_ids"].reverse()
                self.assertEqual(self.compile(args), result)
