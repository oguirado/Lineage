"""Bundled founding references: strict, pinned and descriptor-confined reads."""
from __future__ import annotations

from copy import deepcopy
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

from lineage.core.schema import MAX_JSON_BYTES, SchemaError, strict_loads, validate

PUBLIC_REFERENCE_IDS = ("gold_s1", "memory_v21")
REFERENCE_PINS = {
    "gold_s1": "2f5606ae1b0ebb547b3622bc8709ac3433c0a3e234492b7cc5f1495feceace64",
    "memory_v21": "ae5c6417e8f73fe0a4dab3e6ba352d4d4d629e6711eda37b44bb7424683789c9",
}
_POLICY_PIN = "24283ad471680d1f256b263cbc40447a8c3865c41a43aae39ea0a367999307ff"
_METADATA_PIN = "5243145ad2d99c30c40da82af0b701af51fde49afe433a9ebbfedcdd1e1896fa"
_SOURCE_PIN = "f90dc84fc814fce0258a12d0e0fd17e5332021410470c469247e2b019b3511c5"
_OWNED = {
    "gold_s1": ("references/gold_s1/gold_rules.json", "references/gold_s1/gold_rules.md"),
    "memory_v21": ("references/memory_v21/REFERENCE.md",),
}
_PATHS = frozenset(p for paths in _OWNED.values() for p in paths) | {
    "references/catalog.json", "references/publication_policy.json"}
_HASH = {"type": "string", "pattern": r"^[0-9a-f]{64}(?![\s\S])"}
_TEXT = {"type": "string", "minLength": 1}
_ROLES = ("agent_creator", "author", "capsule_tester", "cross_reviewer", "oracle_writer",
          "orchestrator", "performance_auditor", "persona", "privacy_verifier", "repairer", "researcher")
_GATES = ("G-PACK", "G-SURFACE", "G-LAWS", "G-WHOLE", "G-E2E-TOUCHED", "G-REAL-PEER",
          "G-HOSTED-LIKE", "G-NOWEAKEN", "G-LINK", "G-LIVE", "G-HOSTED", "G-JUDGE", "G-MEM")
_LABELS: dict[str, tuple[str, str]] = {}
for _section, _labels, _kind in (
    ("2.1", tuple(f"D{i}" for i in range(1, 9)), "definition"),
    ("2.2", tuple(f"L{i}" for i in range(1, 9)), "law"), ("2.4", _GATES, "gate"),
    ("4.1", tuple(f"I{i}" for i in range(1, 29)), "invariant"),
    ("4.2", tuple(f"A{i}" for i in range(1, 36)) + tuple("REJECTED." + s for s in
        ("PREFIX_PRUNING", "HOMOGENEOUS_PROPOSERS", "DEEP_AGGREGATION", "LARGE_BATCHES")), "anti_use"),
    ("5", tuple("DERIVED.SEAT." + s for s in ("ORCHESTRATOR", "WRITER", "SWARM", "JUDGE",
        "EXTERNAL_TESTER", "LIVE_VERIFIER", "UI_PEER", "ROUTER", "ECONOMICS")), "seat_contract"),
):
    _LABELS.update({f"GS-{_section}-{i}": (label, _kind) for i, label in enumerate(_labels, 1)})


class ReferenceError(ValueError):
    def __init__(self, code: str, detail: dict[str, Any] | None = None) -> None:
        self.code, self.detail = code, deepcopy(detail)
        super().__init__(code)


def _fail(reason: str, path: str | None = None, code: str = "hash_mismatch") -> None:
    detail = {"reason": reason}
    if path in _PATHS or path == "references/MANIFEST.sha256":
        detail["path"] = path
    raise ReferenceError(code, detail)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _object(properties: dict, required: tuple | None = None) -> dict:
    return {"type": "object", "properties": properties,
            "required": list(properties if required is None else required), "additionalProperties": False}


_FILE_SCHEMA = _object({"path": _TEXT, "sha256": _HASH,
                        "bytes": {"type": "integer", "minimum": 0}})
_SOURCE_SCHEMA = _object({"document_id": _TEXT, "version": _TEXT,
    **{key: {"type": ["string", "null"]} for key in ("sha256", "status", "generation", "publication")}})
_DESCRIPTOR_SCHEMA = _object({"ref_id": {"enum": list(PUBLIC_REFERENCE_IDS)}, "title": _TEXT,
    "source": _SOURCE_SCHEMA, "files": {"type": "array", "items": _FILE_SCHEMA}, "sha256": _HASH})
_CATALOG_SCHEMA = _object({"schema": {"const": "lineage.references/v1"},
    "references": {"type": "array", "minItems": 2, "maxItems": 2, "items": _DESCRIPTOR_SCHEMA}})
_RULE_SCHEMA = _object({"id": _TEXT, "section": _TEXT,
    "lines": {"type": "array", "minItems": 2, "maxItems": 2,
              "items": {"type": "integer", "minimum": 1}},
    "kind": {"enum": ["definition", "law", "gate", "invariant", "anti_use", "seat_contract"]},
    "text": _TEXT, "roles": {"type": "array", "uniqueItems": True, "items": {"enum": list(_ROLES)}},
    "scrub": {"type": "boolean"}})
_GOLD_SCHEMA = _object({"schema": {"const": "lineage.gold-rules/v1"},
    "source": _object({"title": _TEXT, "sha256": _HASH}),
    "rules": {"type": "array", "minItems": 105, "maxItems": 105, "items": _RULE_SCHEMA}})


def _decode(raw: bytes, schema: dict) -> dict:
    try:
        value = strict_loads(raw)
        validate(value, schema)
        return value
    except (SchemaError, ValueError, UnicodeError, TypeError, RecursionError):
        _fail("invalid_stored_structure")


def _safe_path(relative: str) -> bool:
    return (type(relative) is str and re.fullmatch(r"[A-Za-z0-9_./-]+", relative) is not None
            and all(p not in ("", ".", "..") for p in relative.split("/")))


def _read(root_fd: int, relative: str) -> bytes:
    """Every component is opened relative to a held, no-follow directory fd."""
    if not _safe_path(relative):
        _fail("unapproved_path")
    parent = os.dup(root_fd)
    try:
        parts = relative.split("/")
        for component in parts[:-1]:
            info = os.stat(component, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode):
                _fail("unsafe_component", relative)
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK,
                            dir_fd=parent)
            os.close(parent)
            parent = child
        info = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode):
            _fail("nonregular_file", relative)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                _fail("nonregular_descriptor", relative)
            chunks, size = [], 0
            while True:
                chunk = os.read(fd, 8192)
                if not chunk:
                    break
                size += len(chunk)
                # Each shipped document fits U02's unchanged ceiling.
                if size > MAX_JSON_BYTES:
                    _fail("document_size", relative)
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(fd)
    except ReferenceError:
        raise
    except OSError as exc:
        integrity = exc.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP)
        _fail("missing_or_unsafe" if integrity else "read_failure", relative,
              "hash_mismatch" if integrity else "internal")
    finally:
        os.close(parent)


def _inventory(fd: int, prefix: str = "references") -> set[str]:
    paths = set()
    try:
        with os.scandir(fd) as entries:
            names = sorted(entry.name for entry in entries)
        for name in names:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            rel = prefix + "/" + name
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                try:
                    paths.update(_inventory(child, rel))
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                paths.add(rel)
            else:
                _fail("nonregular_reference")
    except OSError as exc:
        _fail("reference_traversal", code="internal" if exc.errno == errno.EACCES else "hash_mismatch")
    return paths


def _gold(raw: bytes) -> dict:
    value = _decode(raw, _GOLD_SCHEMA)
    if value["source"]["sha256"] != _SOURCE_PIN:
        _fail("source_identity")
    rules = value["rules"]
    if [r["id"] for r in rules] != list(_LABELS):
        _fail("rule_coverage")
    metadata = [{k: v for k, v in r.items() if k != "text"} for r in rules]
    if _sha(_canonical(metadata)) != _METADATA_PIN:
        _fail("rule_metadata")
    for rule in rules:
        label, kind = _LABELS[rule["id"]]
        if (rule["kind"] != kind or rule["lines"][0] > rule["lines"][1]
                or not rule["text"].startswith(label)
                or rule["text"][len(label):len(label)+1].isalnum()):
            _fail("rule_identity")
        citation = f"[CITED; {rule['section']}:L{rule['lines'][0]}-L{rule['lines'][1]}]."
        if not rule["text"].endswith(citation) or len(rule["text"]) <= len(label) + len(citation) + 8:
            _fail("rule_citation")
    return value


def _package(ref_id: str, repo_root: str | os.PathLike | None, expected: str | None = None) -> tuple[dict, dict]:
    if type(ref_id) is not str or ref_id not in PUBLIC_REFERENCE_IDS:
        _fail("unknown_reference", code="bad_args")
    if expected is not None and (type(expected) is not str or re.fullmatch(r"[0-9a-f]{64}", expected) is None):
        _fail("invalid_expected_digest", code="bad_args")
    root = Path(__file__).resolve().parents[2] if repo_root is None else Path(repo_root)
    fd = None
    try:
        if not stat.S_ISDIR(root.lstat().st_mode):
            _fail("unsafe_root")
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK)
        raw_catalog = _read(fd, "references/catalog.json")
        catalog = _decode(raw_catalog, _CATALOG_SCHEMA)
        if [d["ref_id"] for d in catalog["references"]] != list(PUBLIC_REFERENCE_IDS):
            _fail("catalog_coverage")
        for descriptor in catalog["references"]:
            rid = descriptor["ref_id"]
            if tuple(f["path"] for f in descriptor["files"]) != _OWNED[rid]:
                _fail("unapproved_path")
            source = descriptor["source"]
            want = ({"document_id": "GOLD-S1", "version": "PM-1001.1", "sha256": _SOURCE_PIN,
                     "status": "ACTIVE", "generation": "ASSEMBLED", "publication": "DRAFT"}
                    if rid == "gold_s1" else {"document_id": "Memory v2.1", "version": "2.1",
                    "sha256": None, "status": None, "generation": None, "publication": None})
            if source != want:
                _fail("source_identity")
        descriptor = next(d for d in catalog["references"] if d["ref_id"] == ref_id)
        package_sha = _sha(_canonical({k: v for k, v in descriptor.items() if k != "sha256"}))
        if package_sha != descriptor["sha256"] or package_sha != REFERENCE_PINS[ref_id]:
            _fail("package_digest")
        if expected is not None and expected != package_sha:
            _fail("expected_digest")
        raw_manifest = _read(fd, "references/MANIFEST.sha256")
        try:
            lines = raw_manifest.decode("ascii").splitlines(keepends=True)
        except UnicodeError:
            _fail("manifest_encoding")
        entries = {}
        for line in lines:
            match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_./-]+)\n", line)
            if not match or not _safe_path(match[2]) or match[2] in entries:
                _fail("manifest_structure")
            entries[match[2]] = match[1]
        if list(entries) != sorted(_PATHS):
            _fail("manifest_coverage")
        refdir = os.open("references", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            if _inventory(refdir) != _PATHS | {"references/MANIFEST.sha256"}:
                _fail("unexpected_reference_file")
        finally:
            os.close(refdir)
        if entries["references/catalog.json"] != _sha(raw_catalog) or entries["references/publication_policy.json"] != _POLICY_PIN:
            _fail("manifest_digest")
        for d in catalog["references"]:
            for item in d["files"]:
                if entries[item["path"]] != item["sha256"]:
                    _fail("manifest_file_digest", item["path"])
        contents = {}
        for item in descriptor["files"]:
            raw = _read(fd, item["path"])
            if len(raw) != item["bytes"] or _sha(raw) != item["sha256"]:
                _fail("file_digest_or_length", item["path"])
            contents[item["path"]] = raw
        if ref_id == "gold_s1":
            contents["gold"] = _gold(contents[_OWNED[ref_id][0]])
        for path in _OWNED[ref_id]:
            contents[path].decode("utf-8", errors="strict")
        return descriptor, contents
    except ReferenceError:
        raise
    except UnicodeError:
        _fail("invalid_utf8")
    except OSError as exc:
        _fail("read_failure", code="hash_mismatch" if exc.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP) else "internal")
    except Exception:
        _fail("unexpected_failure", code="internal")
    finally:
        if fd is not None:
            os.close(fd)


def load_gold_rules(*, repo_root: str | os.PathLike | None = None) -> dict[str, Any]:
    _, contents = _package("gold_s1", repo_root)
    return deepcopy(contents["gold"])


def reference_get(ref_id: str, *, repo_root: str | os.PathLike | None = None) -> dict[str, Any]:
    descriptor, contents = _package(ref_id, repo_root)
    return deepcopy({"schema": "lineage.reference/v1", **descriptor,
        "rules": contents["gold"]["rules"] if ref_id == "gold_s1" else None,
        "contract": contents[_OWNED[ref_id][0]].decode("utf-8") if ref_id == "memory_v21" else None})


def reference_verify(ref_id: str, expected_sha256: str | None = None, *,
                     repo_root: str | os.PathLike | None = None) -> dict[str, Any]:
    descriptor, _ = _package(ref_id, repo_root, expected_sha256)
    return deepcopy({"schema": "lineage.reference-verification/v1", "ref_id": ref_id,
        "verified": True, "sha256": descriptor["sha256"], "files_checked": descriptor["files"],
        "source_sha256": descriptor["source"]["sha256"], "source_verified": False})


def get(ref_id: str, *, ctx: object) -> dict:
    value = reference_get(ref_id)
    return {"reference": {"id": ref_id, "sha256": value["sha256"],
        "bytes": sum(f["bytes"] for f in value["files"]),
        "rules": [{k: r[k] for k in ("id", "section", "text")} for r in value["rules"] or []]}}


def verify(ref_id: str, *, ctx: object) -> dict:
    value = reference_verify(ref_id)
    return {"ref_id": ref_id, "sha256": value["sha256"],
            "bytes": sum(f["bytes"] for f in value["files_checked"]), "valid": True}


def require_pins(pins: object, *, ctx: object) -> tuple[dict, ...]:
    if type(pins) not in (list, tuple) or len(pins) != 2:
        _fail("reference_pins", code="bad_args")
    try:
        validate(list(pins), {"type": "array", "items": _object({
            "id": {"enum": list(PUBLIC_REFERENCE_IDS)}, "sha256": _HASH})})
        if sorted(p["id"] for p in pins) != list(PUBLIC_REFERENCE_IDS):
            _fail("reference_pins", code="bad_args")
    except SchemaError:
        _fail("reference_pins", code="bad_args")
    for pin in pins:
        reference_verify(pin["id"], pin["sha256"])
    return tuple(deepcopy(sorted(pins, key=lambda p: p["id"])))
