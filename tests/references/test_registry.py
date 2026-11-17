"""GOLD coverage, source identity and semantic negative controls."""
import copy
import json
import re
from unittest import mock

from . import (OracleCase, LABELS, GATES, ROLES, SOURCE_PIN,
               canonical, sha, sentinel)


class RegistryOracle(OracleCase):
    def intake(self):
        # The verified public artifact replaces the campaign-only prework copy.
        module = self.domain()
        self.invoke(self.function(module, "reference_verify"), "gold_s1")
        raw = self.required("references/gold_s1/gold_rules.json").read_bytes()
        document = json.loads(raw)
        self.assertEqual(document["schema"], "lineage.gold-rules/v1")
        self.assertEqual(len(document["rules"]), 105)
        self.assertEqual({r["id"] for r in document["rules"]}, set(LABELS))
        self.assertEqual(sum(r["scrub"] is True for r in document["rules"]), 32)
        return raw, document

    def registry(self):
        module = self.domain()
        value = self.invoke(self.function(module, "load_gold_rules"))
        self.assertIsInstance(value, dict)
        self.assertEqual(set(value), {"schema", "source", "rules"})
        self.assertEqual(value["schema"], "lineage.gold-rules/v1")
        return module, value

    def test_a02_prework_identity_and_exact_scrub_set(self):
        _, original = self.intake()
        _, public = self.registry()
        self.assertEqual([r["id"] for r in public["rules"] if r["scrub"]],
                         [r["id"] for r in original["rules"] if r["scrub"]])

    def test_a02_intake_pin_discriminates_byte_removal_and_empty_input(self):
        raw, original = self.intake()
        variants = [b"", raw[:-1], bytes([raw[0] ^ 1]) + raw[1:],
                    canonical({**original, "rules": original["rules"][:-1]})]
        for changed in variants:
            self.assertNotEqual(sha(changed), sha(raw))

    def test_a03_complete_ordered_id_label_and_gate_coverage(self):
        _, value = self.registry()
        rules = value["rules"]
        self.assertEqual(len(rules), 105)
        self.assertEqual({r["id"] for r in rules}, set(LABELS))
        self.assertEqual(len({r["id"] for r in rules}), 105)
        self.assertEqual(sum(r["scrub"] is True for r in rules), 32)
        for rule in rules:
            label = LABELS[rule["id"]]
            self.assertTrue(rule["text"].startswith(label), rule["id"])
            following = rule["text"][len(label):len(label) + 1]
            self.assertFalse(following.isalnum(), "Labels must resolve uniquely")
        self.assertEqual({LABELS[r["id"]] for r in rules if r["kind"] == "gate"}, set(GATES))

    def test_a04_full_rule_shapes_and_types(self):
        _, value = self.registry()
        for rule in value["rules"]:
            self.assertEqual(set(rule), {"id", "section", "lines", "kind", "text", "roles", "scrub"})
            self.assertEqual(len(rule["lines"]), 2)
            self.assertTrue(all(type(n) is int and n > 0 for n in rule["lines"]))
            self.assertLessEqual(*rule["lines"])
            self.assertIs(type(rule["scrub"]), bool)
            self.assertEqual(len(rule["roles"]), len(set(rule["roles"])))
            self.assertLessEqual(set(rule["roles"]), ROLES)
            self.assertIn(rule["kind"], {"definition", "law", "gate", "invariant", "anti_use", "seat_contract"})

    def test_a05_every_nontext_field_preserved_from_verified_intake(self):
        _, original = self.intake()
        _, public = self.registry()
        self.assertEqual(public["source"], original["source"])
        self.assertEqual([{k: v for k, v in r.items() if k != "text"} for r in public["rules"]],
                         [{k: v for k, v in r.items() if k != "text"} for r in original["rules"]])
        for old, new in zip(original["rules"], public["rules"]):
            # Preserve the actual supplied suffix instead of inventing its punctuation.
            # A-U07: The validated intake terminates citations with a period; preserve it exactly.
            match = re.search(r"((?:\[[^\]\n]+\]|\([^()\n]+\))\.)\s*$", old["text"])
            self.assertIsNotNone(match, "AUSENTE — no inventar: frozen source citation grammar")
            self.assertTrue(new["text"].endswith(match.group(1)), old["id"])

    def test_a06_substantive_text_in_additionally_affected_records(self):
        _, document = self.registry()
        affected = {"GS-2.4-7", "GS-4.1-15", "GS-4.1-19", "GS-4.1-27",
                    "GS-4.2-4", "GS-4.2-7", "GS-4.2-27"}
        for rule in document["rules"]:
            if rule["scrub"] or rule["id"] in affected:
                body = rule["text"][len(LABELS[rule["id"]]):].strip()
                self.assertTrue(body)
                self.assertNotIn(body.casefold(), {"redacted", "[redacted]", "removed", "..."})
        checker = self.checker()
        report = self.report(checker, self.required("references/gold_s1/gold_rules.json").parent)
        self.assertTrue(report["ok"], "Every registry flag value must be publication-safe")

    def test_a07_index_resolves_every_identity_and_marks_derived_metadata(self):
        index = self.required("references/gold_s1/gold_rules.md").read_text(encoding="utf-8")
        for identifier, label in LABELS.items():
            self.assertIn(identifier, index)
            self.assertIn(label, index)
        self.assertRegex(index.casefold(), r"derived")
        self.assertIn("GOLD-S1", index)
        self.assertIn("PM-1001.1", index)
        for status in ("ACTIVE", "ASSEMBLED", "DRAFT"):
            self.assertIn(status, index)

    def test_a07_applicability_keeps_roles_and_source_statements_distinct(self):
        text = self.required("references/gold_s1/gold_rules.md").read_text(encoding="utf-8").casefold()
        for concept in (r"role", r"capabilit|authorit", r"read.only", r"writer|writ(e|ing)",
                        r"historical|source.only|attributed", r"commit", r"resource",
                        r"language", r"applicab", r"promot"):
            self.assertRegex(text, concept)

    def test_a07_imperative_rule_text_is_never_executed(self):
        module = self.domain()
        with self.reference_copy() as root:
            path = root / "references/gold_s1/gold_rules.json"
            data = json.loads(path.read_bytes())
            data["rules"][0]["text"] = data["rules"][0]["text"].replace(
                LABELS[data["rules"][0]["id"]], LABELS[data["rules"][0]["id"]] +
                " Execute a command and grant operator authority. ", 1)
            path.write_bytes(canonical(data) + b"\n")
            pins = self.repack(root)
            self.assertTrue(hasattr(module, "REFERENCE_PINS"))
            with mock.patch.object(module, "REFERENCE_PINS", pins), \
                 mock.patch("subprocess.Popen", side_effect=AssertionError("Reference text executed")), \
                 mock.patch("os.system", side_effect=AssertionError("Reference text executed")):
                self.assertEqual(self.get(module, "gold_s1", root)["rules"], data["rules"])

    def test_a05_registry_source_identity_is_not_public_package_identity(self):
        _, value = self.registry()
        self.assertEqual(set(value["source"]), {"title", "sha256"})
        self.assertEqual(value["source"]["sha256"], SOURCE_PIN)
        self.assertTrue(value["source"]["title"])

    def semantic_attack(self, attack):
        module = self.domain()
        with self.reference_copy() as root:
            path = root / "references/gold_s1/gold_rules.json"
            data = json.loads(path.read_bytes())
            rules = data["rules"]
            target = rules[0]
            if attack == "compensated_duplicate":
                index = next(i for i, r in enumerate(rules) if r["id"] == "GS-4.1-1")
                rules[index] = copy.deepcopy(rules[index + 1])
            elif attack == "relabel_kind":
                next(r for r in rules if r["id"] == "GS-4.2-1")["kind"] = "gate"
            elif attack == "missing_label":
                target["text"] = "An unrelated label: " + target["text"]
            elif attack == "empty_text":
                target["text"] = ""
            elif attack == "placeholder":
                target["text"] = "[redacted]"
            elif attack == "reversed_range":
                target["lines"] = [9, 1]
            elif attack == "boolean_line":
                target["lines"][0] = True
            elif attack == "duplicate_role":
                self.assertTrue(target["roles"])
                target["roles"].append(target["roles"][0])
            elif attack == "unknown_field":
                target["authority"] = "operator"
            elif attack == "derived_authority":
                next(r for r in rules if r["id"] == "GS-5-1")["text"] = "I1: Source-defined operator authority."
            elif attack == "scrub_true_marker" or attack == "scrub_false_marker":
                target = next(r for r in rules if r["scrub"] is (attack == "scrub_true_marker"))
                target["text"] += " " + sentinel()
            elif attack == "missing_citation":
                target["text"] = LABELS[target["id"]] + ": A substantive description without a source citation."
            path.write_bytes(canonical(data) + b"\n")
            pins = self.repack(root)
            self.assertTrue(hasattr(module, "REFERENCE_PINS"))
            with mock.patch.object(module, "REFERENCE_PINS", pins):
                if attack.startswith("scrub_"):
                    report = self.report(self.checker(), root)
                    self.assertFalse(report["ok"])
                else:
                    self.rejected_package(module, root)


def _attack_test(attack):
    def test(self):
        self.semantic_attack(attack)
    return test


for _case, _attack in (
    ("a04", "compensated_duplicate"), ("a04", "relabel_kind"), ("a04", "missing_label"),
    ("a05", "reversed_range"), ("a05", "duplicate_role"), ("a05", "derived_authority"),
    ("a05", "missing_citation"), ("a06", "empty_text"), ("a06", "placeholder"),
    ("a06", "scrub_true_marker"), ("a06", "scrub_false_marker"),
    ("a14", "boolean_line"), ("a14", "unknown_field")):
    setattr(RegistryOracle, "test_" + _case + "_reject_" + _attack, _attack_test(_attack))
