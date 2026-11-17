"""A1–A4, A20, A29: bundled shapes, hostile values and exact bytes."""
import copy
from ._support import OracleCase, canonical, unit


class SchemaTests(OracleCase):
    def test_a02_hostile_decode(self):
        api, _ = self.schema_store()
        for raw in (b'{"a":{"x":1,"x":2}}', b'{"x":"\xff"}', b'{"x":"\\ud800"}',
                    b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}', b'{} {}'):
            with self.subTest(raw=raw):
                self.error("bad_args", lambda: api.decode(raw))
        self.assertEqual(api.decode(b'{"x":null}'), {"x": None})

    def test_a02_nonfinite_surrogate_and_closed_context_fields(self):
        for bad in (float("nan"), float("inf"), -float("inf")):
            value = self.shaped("workflow")
            value["body"]["stats"]["mean_reward"] = bad
            self.error("bad_args", lambda: self.validate(value))
        value = unit()
        value["statement"] = "\ud800"
        self.error("bad_args", lambda: self.validate(value))
        value = self.shaped("episode")
        parent = {"agent_id": "agent-one", "agent_version": "a" * 64, "run_id": "parent01"}
        value["body"]["parents_context"] = [dict(parent, extra=True)]
        self.error("bad_args", lambda: self.validate(value))
        value["body"]["parents_context"] = [parent, parent]
        self.error("bad_args", lambda: self.validate(value))
        value = self.shaped()
        value["provenance"]["inherited_from"] = {"agent_id": "agent-one", "unit_id": "source01", "unit_sha256": "a" * 64, "extra": True}
        self.error("bad_args", lambda: self.validate(value))

    def test_a03_missing_body_members(self):
        for kind in ("lesson", "negative", "episode"):
            original = self.shaped(kind)
            self.validate(original)
            for key in original["body"]:
                candidate = copy.deepcopy(original)
                del candidate["body"][key]
                with self.subTest(kind=kind, missing=key):
                    self.error("bad_args", lambda: self.validate(candidate))
        value = self.shaped("episode")
        for key in value["body"]["cost"]:
            broken = copy.deepcopy(value)
            del broken["body"]["cost"][key]
            self.error("bad_args", lambda: self.validate(broken))

    def test_a03_semantic_bounds(self):
        value = self.shaped("workflow")
        value["body"]["stats"].update(runs=2, successes=2)
        self.validate(value)
        value["body"]["stats"]["successes"] = 3
        self.error("bad_args", lambda: self.validate(value))
        for kind, field, invalid in (("negative", "verdict", "green"),
                                     ("workflow", "status", "active")):
            candidate = self.shaped(kind)
            candidate["body"][field] = invalid
            self.error("bad_args", lambda: self.validate(candidate))
        candidate = self.shaped("decision")
        candidate["level"] = 3
        self.error("bad_args", lambda: self.validate(candidate))

    def test_a04_exact_canonical_utf8_boundary(self):
        for glyph in ("a", "é", "界", "🙂"):
            value = unit()
            value["statement"] = ""
            room = 6000 - len(canonical(value))
            count, remainder = divmod(room, len(glyph.encode("utf-8")))
            value["statement"] = glyph * count + "a" * remainder
            with self.subTest(glyph=glyph):
                self.assertEqual(len(canonical(value)), 6000)
                self.validate(value)
                value["statement"] += "a"
                self.assertEqual(len(canonical(value)), 6001)
                self.assertLessEqual(len(value["statement"]), 6000)
                self.error("memory_debt", lambda: self.validate(value))

    def test_a20_schema_backlink_iff(self):
        value = unit()
        value["status"] = "superseded"
        self.error("bad_args", lambda: self.validate(value))
        value["superseded_by"] = "unit_002"
        self.validate(value)  # Structural validity is distinct from graph admission.
        value["status"] = "active"
        self.error("bad_args", lambda: self.validate(value))

    def test_a29_null_and_zero_are_distinct(self):
        value = self.shaped("episode")
        self.validate(value)
        self.assertTrue(all(v is None for v in value["body"]["cost"].values()))
        for key in value["body"]["cost"]:
            for bad in (True, False, -1, 9007199254740992, 1.5):
                candidate = copy.deepcopy(value)
                candidate["body"]["cost"][key] = bad
                self.error("bad_args", lambda: self.validate(candidate))
            value["body"]["cost"][key] = 0
        self.validate(value)
        value = self.shaped("workflow")
        self.validate(value)
        self.assertIsNone(value["body"]["stats"]["mean_reward"])

    def test_a01_collection_text_and_alias_bounds(self):
        candidates = []
        for key, invalid in (("schema", "mem.unit.v2"), ("schema", "lineage.memory.unit/v1"),
                             ("id", "short"), ("id", "x" * 65), ("statement", ""),
                             ("statement", "x" * 16001), ("level", True), ("privacy", "secret")):
            value = unit()
            value[key] = invalid
            candidates.append(value)
        for path, invalid in ((["scope", "language"], "x" * 65),
                              (["provenance", "origin"], "x" * 129),
                              (["supersedes"], ["unit_002", "unit_002"]),
                              (["supersedes"], ["unit_%04d" % i for i in range(257)]),
                              (["body", "blocked_use"], ["x"] * 65)):
            value = unit()
            target = value
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = invalid
            candidates.append(value)
        for value in candidates:
            with self.subTest(value=value):
                self.error("bad_args", lambda: self.validate(value))


def _kind_test(kind, level):
    def test(self):
        value = self.shaped(kind, level, actor="operator" if kind == "ruling" else "agent-one")
        authority = "operator" if kind == "ruling" else "tool"
        actor = value["provenance"]["actor"]
        self.validate(value, authority=authority, actor=actor)
        self.shape_check(value, "mem_unit.schema.json")
        value["kind"] = "episode" if kind != "episode" else "lesson"
        self.error("bad_args", lambda: self.validate(value, authority=authority, actor=actor))
    return test


for _kind, _levels in {"ruling": (1,), "lesson": (2, 3), "negative": (2, 3),
                       "workflow": (2,), "episode": (2, 3), "decision": (2,),
                       "open_item": (2, 3)}.items():
    for _level in _levels:
        setattr(SchemaTests, "test_a01_%s_level_%d" % (_kind, _level), _kind_test(_kind, _level))


def _unknown_test(path):
    def test(self):
        value = self.shaped("episode")
        target = value
        for part in path:
            target = target[part]
        target["unexpected"] = "no authority"
        self.error("bad_args", lambda: self.validate(value))
    return test


for _path in ((), ("body",), ("provenance",), ("receipts", 0), ("scope",),
              ("body", "seat"), ("body", "cost"), ("body", "outcome"),
              ("body", "outcome", "findings")):
    setattr(SchemaTests, "test_a02_closed_" + "_".join(map(str, _path or ("root",))), _unknown_test(_path))


def _unknown_field_test(kind, path):
    def test(self):
        value = self.shaped(kind)
        target = value
        for key in path:
            target = target[key]
        target["unlisted"] = "forged authority"
        self.error("bad_args", lambda: self.validate(value))
    return test


for _label, _kind, _path in (
    ("root", "lesson", ()), ("body", "lesson", ("body",)),
    ("scope", "lesson", ("scope",)), ("provenance", "lesson", ("provenance",)),
    ("receipt", "lesson", ("receipts", 0)), ("seat", "episode", ("body", "seat")),
    ("outcome", "episode", ("body", "outcome")),
    ("findings", "episode", ("body", "outcome", "findings")),
    ("cost", "episode", ("body", "cost")), ("stats", "workflow", ("body", "stats"))):
    setattr(SchemaTests, "test_a02_closed_" + _label, _unknown_field_test(_kind, _path))


def _integer_test(kind, path):
    def test(self):
        for invalid in (True, False, -1, 9007199254740992, 0.5):
            value = self.shaped(kind)
            target = value
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = invalid
            self.error("bad_args", lambda: self.validate(value))
    return test


for _label, _kind, _path in (
    ("tokens", "episode", ("body", "cost", "tokens_in")),
    ("repair", "episode", ("body", "outcome", "repair_loops")),
    ("findings", "episode", ("body", "outcome", "findings", "confirmed")),
    ("runs", "workflow", ("body", "stats", "runs")),
    ("successes", "workflow", ("body", "stats", "successes")),
    ("order", "open_item", ("body", "order"))):
    setattr(SchemaTests, "test_a02_integer_" + _label, _integer_test(_kind, _path))
