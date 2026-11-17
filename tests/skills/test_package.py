"""Pure package expectations authored independently of the U09 implementation."""
import copy
import hashlib

from tests.skills import (FILES, LIMIT, PIN, VECTOR, PureCase, boundary_files,
                          independent_bytes, one, skills)


class PackageOracle(PureCase):
    def test_a03_literal_canonical_vector(self):
        self.assertEqual(hashlib.sha256(VECTOR).hexdigest(), PIN)
        actual = skills.package(copy.deepcopy(FILES))
        self.assertEqual(actual, (VECTOR, PIN))
        reordered = [{"content": f["content"], "path": f["path"]} for f in reversed(FILES)]
        self.assertEqual(skills.package(reordered), actual)
        self.assertEqual(skills.package(tuple(reordered)), actual)
        self.assertFalse(actual[0].endswith(b"\n"))
        self.assertNotEqual(actual[0], repr(FILES).encode())

    def test_a04_content_codepoints_and_line_endings_are_preserved(self):
        vectors = [
            ("", b""), ("a", b"a"), ("b", b"b"),
            ("a\n", b"a\\n"), ("a\r\n", b"a\\r\\n"),
            ("\ufeffa", b"\xef\xbb\xbfa"), ("é", b"\xc3\xa9"),
            ("e\u0301", b"e\xcc\x81"), ("a\n\n", b"a\\n\\n"),
        ]
        pins = []
        for content, encoded in vectors:
            with self.subTest(content=repr(content)):
                expected = b'[{"content":"' + encoded + b'","path":"SKILL.md"}]'
                actual = skills.package(one(content))
                self.assertEqual(actual, (expected, hashlib.sha256(expected).hexdigest()))
                pins.append(actual[1])
        self.assertEqual(len(set(pins)), len(vectors))

    def test_a04_path_is_part_of_pin(self):
        first = one() + [{"path": "a.txt", "content": "same"}]
        second = one() + [{"path": "b.txt", "content": "same"}]
        for files in (first, second):
            expected = independent_bytes(files)
            self.assertEqual(skills.package(files), (expected, hashlib.sha256(expected).hexdigest()))
        self.assertNotEqual(skills.package(first)[1], skills.package(second)[1])

    def test_a05_exact_root_entrypoint_and_collisions(self):
        self.assertEqual(skills.package(one(""))[0], b'[{"content":"","path":"SKILL.md"}]')
        rejected = [
            [], [{"path": "notes.md", "content": ""}],
            [{"path": "nested/SKILL.md", "content": ""}],
            one() + [{"path": "nested/SKILL.md", "content": ""}],
            one() + one("changed"),
            one() + [{"path": "a", "content": ""}, {"path": "a/b", "content": ""}],
            one() + [{"path": "a/b", "content": ""}, {"path": "a", "content": ""}],
            one() + [{"path": "SKILL.md/child", "content": ""}],
        ]
        for files in rejected:
            with self.subTest(files=files):
                self.bad_package(files)

    def test_a06_path_attack_matrix(self):
        invalid = ["/escape", "", ".", "..", "a/./b", "a/../b", "../b", "./a",
                   "a//b", "a/b/", "a/", "a\\b", "C:drive", "%2e%2e/b", "a\x00b",
                   "a\nb", "a\tb", "naïve", "a b", "a?b", "a#b", "a\x7fb"]
        for path in invalid:
            with self.subTest(path=repr(path)):
                self.bad_package(one() + [{"path": path, "content": "passive"}])
        accepted = one() + [{"path": "a-b_C.1/note.txt", "content": "ok"}]
        self.assertEqual(skills.package(accepted)[0], independent_bytes(accepted))

    def test_a02_direct_package_wrong_types_and_extra_keys(self):
        invalid = [None, True, 1, "files", b"files", {}, [None], ["SKILL.md"],
                   [{"path": "SKILL.md"}], [{"content": "text"}],
                   [{"path": "SKILL.md", "content": None}],
                   [{"path": "SKILL.md", "content": 1}],
                   [{"path": True, "content": ""}],
                   [{"path": "SKILL.md", "content": "", "extra": True}],
                   [{"path": "SKILL.md", "content": "\ud800"}],
                   [{"path": "\udfff", "content": ""}],
                   [{"path": "SKILL.md", "content": "\ud800\udc00"}]]
        for files in invalid:
            with self.subTest(files=repr(files)):
                self.bad_package(files)

    def test_a08_file_count_bounds(self):
        accepted = one() + [{"path": "f%03d" % n, "content": ""} for n in range(255)]
        self.assertEqual(len(accepted), 256)
        self.assertEqual(skills.package(accepted)[0], independent_bytes(accepted))
        self.bad_package(accepted + [{"path": "extra", "content": ""}])
        self.bad_package([])

    def test_a08_path_character_length_bounds(self):
        accepted = one() + [{"path": "a" * 512, "content": ""}]
        self.assertEqual(skills.package(accepted)[0], independent_bytes(accepted))
        self.bad_package(one() + [{"path": "a" * 513, "content": ""}])

    def test_a08_content_character_length_bounds(self):
        for char in ("a", "é", "😀", "\n"):
            with self.subTest(char=repr(char)):
                accepted = one(char * 65536)
                self.assertEqual(skills.package(accepted)[0], independent_bytes(accepted))
                self.bad_package(one(char * 65537))

    def test_a08_exact_canonical_utf8_byte_bound(self):
        files = boundary_files()
        raw = independent_bytes(files)
        self.assertEqual(len(raw), LIMIT)
        self.assertEqual(skills.package(files), (raw, hashlib.sha256(raw).hexdigest()))
        over = copy.deepcopy(files)
        over[-1]["content"] += "x"
        self.assertEqual(len(independent_bytes(over)), LIMIT + 1)
        self.bad_package(over)

    def test_a08_json_escaping_counts_toward_byte_bound(self):
        files = boundary_files(escaped=True)
        self.assertEqual(len(independent_bytes(files)), LIMIT)
        self.assertEqual(skills.package(files)[0], independent_bytes(files))
        over = copy.deepcopy(files)
        over[-1]["content"] += "\n"
        self.assertEqual(len(independent_bytes(over)), LIMIT + 2)
        self.bad_package(over)

    def test_a22_package_inputs_are_defensively_copied(self):
        original = copy.deepcopy(FILES)
        frozen = skills.package(original)
        original[0]["content"] = "changed"
        original.append({"path": "extra", "content": "extra"})
        self.assertEqual(frozen, (VECTOR, PIN))
        self.assertEqual(skills.package(FILES), frozen)
