"""A18/A19: independent canonical identity and strict pure validation."""
from copy import deepcopy
from itertools import permutations
from unittest import mock
from . import HASH, PINS, OracleCase, expected_version, record, version


class VersionTests(OracleCase):
    def test_a18_independent_digest_pin_permutations_and_no_mutation(self):
        expected = expected_version(HASH, PINS, 7)
        for pins in permutations(PINS):
            value = list(deepcopy(pins))
            original = deepcopy(value)
            actual = self.invoke(version.agent_version, HASH, value, 7)
            self.assertEqual(actual, expected)
            self.assertRegex(actual, r"^[0-9a-f]{64}$")
            self.assertEqual(value, original)

    def test_a18_pure_no_filesystem_or_network(self):
        with mock.patch("builtins.open", side_effect=AssertionError("file access")), \
             mock.patch("os.open", side_effect=AssertionError("descriptor access")), \
             mock.patch("socket.socket", side_effect=AssertionError("network access")):
            actual = self.invoke(version.agent_version, HASH, [], 0)
        self.assertEqual(actual, expected_version(HASH, [], 0))

    def test_a19_each_version_input_changes_identity(self):
        baseline = self.invoke(version.agent_version, HASH, PINS, 0)
        changed = deepcopy(PINS)
        changed[0]["sha256"] = "f" * 64
        renamed = deepcopy(PINS)
        renamed[0]["skill_id"] = "other-skill"
        for h, pins, gen in (("0" * 64, PINS, 0), (HASH, changed, 0),
                             (HASH, renamed, 0), (HASH, PINS, 1)):
            self.assertNotEqual(self.invoke(version.agent_version, h, pins, gen), baseline)

    def test_a19_metadata_is_excluded(self):
        value = record(skills=PINS)
        expected = self.invoke(version.agent_version, value["constitution_sha256"], value["skills"], value["memory_gen"])
        for key, replacement in (("display_name", "Other"), ("status", "retired"),
                                 ("generation", 17), ("parents", ["parent-one"]),
                                 ("brief_head_sha256", "0" * 64), ("agent_id", "other-one")):
            altered = deepcopy(value)
            altered[key] = replacement
            self.assertEqual(self.invoke(version.agent_version, altered["constitution_sha256"],
                                         altered["skills"], altered["memory_gen"]), expected)

    def test_a19_invalid_memory_generation_native_and_safe_integer(self):
        for invalid in (True, False, -1, 9007199254740992, 1.0, None, "1"):
            self.reject("bad_args", version.agent_version, HASH, [], invalid)
        self.assertEqual(self.invoke(version.agent_version, HASH, [], 9007199254740991),
                         expected_version(HASH, [], 9007199254740991))

    def test_a19_closed_hash_and_skill_pins(self):
        for h in ("A" * 64, "a" * 63, HASH + "\n", "g" * 64, None):
            self.reject("bad_args", version.agent_version, h, [], 0)
        for pins in ([{"id": "skill-one", "sha256": HASH}],
                     [{"skill_id": "skill-one", "sha256": HASH, "extra": 1}],
                     [{"skill_id": "skill-one\n", "sha256": HASH}],
                     [PINS[0], PINS[0]], "pins"):
            self.reject("bad_args", version.agent_version, HASH, pins, 0)
