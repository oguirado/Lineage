"""Deterministic, read-only publication gate with pinned fingerprint policy.

An unavailable production inventory is an admission failure. Synthetic detector
coverage does not replace that independently supplied production trust root.
"""
from __future__ import annotations

import argparse
import codecs
import errno
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import unicodedata

POLICY_SHA256 = "24283ad471680d1f256b263cbc40447a8c3865c41a43aae39ea0a367999307ff"
INVENTORY_SHA256 = "4956fd5dca7409e7e173a7c5e5f3abd2d466c0a9c3da1eedbfdaba2da1f13d97"
_BOUNDARIES = (".git", "_seed", "node_modules")
_CHUNK = 65536
_HEX = re.compile(r"[0-9a-f]{64}\Z")
# Rooted local paths, rather than documented HTTP routes or relative filenames.
_LOCAL = re.compile(
    r"(?<![\w:/])/(?:home|Users|root|tmp|private|mnt|media|dev|proc|sys)(?:/[^\s\x00<>\"'`;,(){}\[\]\\]+)+"
    r"|(?<![\w\\])[A-Za-z]:[\\/][^\s\x00<>\"'`;,(){}\[\]]+"
    r"|(?<!\\)\\\\[A-Za-z0-9_.-]+\\[A-Za-z0-9_$.-][^\s\x00<>\"'`;,(){}\[\]]*"
)
_HOST = re.compile(
    r"(?i)(?:[a-z][a-z0-9+.-]{0,31}://)(?:[^\s/@]+@)?"
    r"(?P<authority>(?:[a-z0-9][a-z0-9.-]*\.(?:local|lan|internal|localhost))|localhost)(?=[:/\s\"'<>]|$)"
    r"|\b(?:hostname|host|endpoint)\s*[:=]\s*[\"']?"
    r"(?P<config>[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9_-]+)+)(?=[:/\s\"',;}\]]|$)"
)
_SECRET = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)\s*[:=]\s*[\"']?"
    r"(?:sk-[a-z0-9_-]{20,}|[a-z0-9_+/-]{32,}={0,2})(?![a-z0-9_+/-])"
    r"|\b(?:sk-[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{30,})\b"
)
_TOKEN = re.compile(r"[^\s\x00<>\"'`;,(){}\[\]=]+")
_ESCAPE = re.compile(r"\\(?:u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|x[0-9a-fA-F]{2}|[\\/\"'bfnrt])")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError("duplicate_key")
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError("nonfinite")


def _valid_text(value):
    if isinstance(value, str):
        value.encode("utf-8", errors="strict")
    elif isinstance(value, dict):
        for key, item in value.items():
            _valid_text(key)
            _valid_text(item)
    elif isinstance(value, list):
        for item in value:
            _valid_text(item)


def _json(raw):
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_reject_constant)
    _valid_text(value)
    return value


def _keys(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError("shape")


def _portable(path):
    return (type(path) is str and re.fullmatch(r"[A-Za-z0-9_./-]+", path) is not None
            and all(s not in ("", ".", "..") for s in path.split("/")))


def _flags(directory=False):
    return (os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            | (os.O_DIRECTORY if directory else 0))


def _policy():
    """Only this installed checker determines the policy location and trust root."""
    root = Path(__file__).resolve().parents[1]
    directories = []
    fd = None
    try:
        directories.append(os.open(root, _flags(True)))
        info = os.stat("references", dir_fd=directories[-1], follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("policy_directory")
        directories.append(os.open("references", _flags(True), dir_fd=directories[-1]))
        info = os.stat("publication_policy.json", dir_fd=directories[-1], follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("policy_file")
        fd = os.open("publication_policy.json", _flags(), dir_fd=directories[-1])
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("policy_descriptor")
        data = bytearray()
        while True:
            chunk = os.read(fd, _CHUNK)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > 1048576:
                raise ValueError("policy_size")
        raw = bytes(data)
        if _sha(raw) != POLICY_SHA256:
            raise ValueError("policy_digest")
        policy = _json(raw)
        _keys(policy, ("schema", "inventory_sha256", "fingerprints", "public_path_exceptions"))
        if policy["schema"] != "lineage.publication-policy/v1":
            raise ValueError("policy_schema")
        if type(policy["fingerprints"]) is not list or type(policy["public_path_exceptions"]) is not list:
            raise ValueError("policy_arrays")
        seen = set()
        for fp in policy["fingerprints"]:
            _keys(fp, ("id", "mode", "segments", "leading_star", "trailing_star"))
            if (type(fp["id"]) is not str or not re.fullmatch(r"[a-z0-9-]+", fp["id"])
                    or fp["id"] in seen or fp["mode"] not in ("literal", "glob")
                    or type(fp["leading_star"]) is not bool or type(fp["trailing_star"]) is not bool
                    or type(fp["segments"]) is not list or not fp["segments"]):
                raise ValueError("fingerprint_shape")
            seen.add(fp["id"])
            for segment in fp["segments"]:
                _keys(segment, ("sha256", "chars"))
                if (type(segment["sha256"]) is not str or not _HEX.fullmatch(segment["sha256"])
                        or type(segment["chars"]) is not int or segment["chars"] <= 0):
                    raise ValueError("fingerprint_segment")
            if fp["mode"] == "literal" and (len(fp["segments"]) != 1 or fp["leading_star"] or fp["trailing_star"]):
                raise ValueError("literal_anchors")
        production = sorted((f for f in policy["fingerprints"] if f["id"] != "test-sentinel"), key=lambda f: f["id"])
        digest = _sha(_canonical(production))
        if policy["inventory_sha256"] != digest or digest != INVENTORY_SHA256:
            raise ValueError("inventory_digest")
        for item in policy["public_path_exceptions"]:
            _keys(item, ("fingerprint_id", "path", "reason"))
            if (item["fingerprint_id"] not in {f["id"] for f in production}
                    or not _portable(item["path"]) or type(item["reason"]) is not str
                    or not re.search(r"STRATEGY\.md.*(?:2\.1|2\.4)", item["reason"])):
                raise ValueError("path_exception")
        # Absence is not proof of a complete production inventory.
        return policy, not bool(production)
    finally:
        if fd is not None:
            os.close(fd)
        for parent in reversed(directories):
            os.close(parent)


def _normal(text, offsets):
    """NFC/casefold while retaining each normalized character's raw coordinate."""
    output, positions = [], []
    start = 0
    while start < len(text):
        end = start + 1
        while end < len(text) and unicodedata.combining(text[end]):
            end += 1
        normalized = unicodedata.normalize("NFC", text[start:end]).casefold()
        output.append(normalized)
        positions.extend([offsets[start]] * len(normalized))
        start = end
    return "".join(output), positions


def _unescape(text, offsets):
    out, mapping, last = [], [], 0
    for match in _ESCAPE.finditer(text):
        out.append(text[last:match.start()])
        mapping.extend(offsets[last:match.start()])
        token = match[0]
        if token[1] in "uUx":
            codepoint = int(token[2:], 16)
            replacement = chr(codepoint) if codepoint <= 0x10ffff else "\ufffd"
        else:
            replacement = {"b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}.get(token[1], token[1])
        out.append(replacement)
        mapping.append(offsets[match.start()])
        last = match.end()
    out.append(text[last:])
    mapping.extend(offsets[last:])
    return "".join(out), mapping


def _hits(text, fingerprints):
    """Hash literal windows; glob patterns bind complete lexical path tokens."""
    # Repeated byte windows in large/binary files need only one digest per page.
    window_sha = lru_cache(maxsize=8192)(_sha)
    lengths = {}
    for fp in fingerprints:
        if fp["mode"] == "literal":
            segment = fp["segments"][0]
            lengths.setdefault(segment["chars"], {}).setdefault(segment["sha256"], []).append(fp["id"])
    for length, targets in lengths.items():
        for index in range(max(0, len(text) - length + 1)):
            ids = targets.get(window_sha(text[index:index+length].encode("utf-8", errors="surrogatepass")))
            for identifier in ids or ():
                yield index, identifier
    for fp in fingerprints:
        if fp["mode"] != "glob":
            continue
        for token in _TOKEN.finditer(text):
            value, cursor = token[0], 0
            valid = True
            for number, segment in enumerate(fp["segments"]):
                length = segment["chars"]
                candidates = range(cursor, len(value) - length + 1)
                if number == 0 and not fp["leading_star"]:
                    candidates = (0,) if len(value) >= length else ()
                found = None
                for pos in candidates:
                    if window_sha(value[pos:pos+length].encode("utf-8", errors="surrogatepass")) == segment["sha256"]:
                        if number == len(fp["segments"])-1 and not fp["trailing_star"] and pos+length != len(value):
                            continue
                        found = pos
                        break
                if found is None:
                    valid = False
                    break
                cursor = found + length
            if valid and (fp["trailing_star"] or cursor == len(value)):
                yield token.start(), fp["id"]


def _text_hits(text, offsets, fingerprints):
    variants = [(text, offsets)]
    if "\\" in text:
        variants.append(_unescape(text, offsets))
    for value, mapping in variants:
        for code, pattern in (("local_path", _LOCAL), ("hostname", _HOST), ("secret_literal", _SECRET)):
            for match in pattern.finditer(value):
                yield code, mapping[match.start()], code
        normalized, positions = _normal(value, mapping)
        for position, rule in _hits(normalized, fingerprints):
            yield "scrub_token", positions[position], rule


def scan_tree(root):
    report = {"schema": "lineage.publish-check/v1", "ok": False, "files_checked": 0,
              "exclusions": [], "findings": []}
    fingerprints, exceptions = [], set()
    findings = set()

    def add(code, path=None, offset=None, line=None, rule=None):
        findings.add((code, path, line, offset, rule or code))

    try:
        policy, incomplete = _policy()
        fingerprints = policy["fingerprints"]
        exceptions = {(item["fingerprint_id"], item["path"]) for item in policy["public_path_exceptions"]}
        if incomplete:
            add("invalid_policy", "references/publication_policy.json", rule="policy_inventory_missing")
    except Exception:
        add("invalid_policy", "references/publication_policy.json", rule="policy_unavailable_or_invalid")
        policy = None
    # Even incomplete policy reports retain measured traversal evidence and any
    # known detector findings; they can never become a clean publication result.
    max_segment = max((s["chars"] for f in fingerprints for s in f["segments"]), default=1)
    overlap = max(16384, max_segment * 12 + 32)

    def safe_name(relative, directory=False):
        raw = relative.encode("utf-8", errors="surrogateescape")
        offsets, cursor = [], 0
        for character in relative:
            offsets.append(cursor)
            cursor += len(character.encode("utf-8", errors="surrogateescape"))
        bad = [(code, pos, rule) for code, pos, rule in _text_hits(relative, offsets, fingerprints)
               if not (code == "scrub_token" and ((rule, relative) in exceptions
                       or directory and any(r == rule and p.startswith(relative + "/")
                                            for r, p in exceptions)))]
        if bad or any(0xD800 <= ord(c) <= 0xDFFF for c in relative):
            digest = _sha(raw)
            display = "/".join("[redacted]" for _ in relative.split("/"))
            for code, _, rule in bad:
                add(code, display, rule=rule + ":path:" + digest)
            if not bad:
                add("unreadable", display, rule="filename_encoding:path:" + digest)
            return display
        return relative

    def scan_file(parent, name, relative, display):
        fd = None
        # Exact, independently pinned policy metadata may declare admitted paths.
        # This admits only those JSON path fields, never arbitrary file prose.
        policy_raw = _canonical(policy) + b"\n" if policy is not None else b""
        metadata_offsets = set()
        if _sha(policy_raw) == POLICY_SHA256:
            for identifier, path in exceptions:
                needle = b'"path":' + json.dumps(path).encode("utf-8")
                start = policy_raw.find(needle)
                if start >= 0:
                    metadata_offsets.add((start + len(b'"path":"'), identifier))
        deferred = []
        digest = hashlib.sha256()
        try:
            fd = os.open(name, _flags(), dir_fd=parent)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                add("unsafe_link", display, rule="nonregular_descriptor")
                return
            decoder = codecs.getincrementaldecoder("utf-8")("surrogateescape")
            text_tail, tail_start, absolute, line_base = "", 0, 0, 1
            while True:
                raw = os.read(fd, _CHUNK)
                final = not raw
                digest.update(raw)
                text = decoder.decode(raw, final=final)
                combined = text_tail + text
                offsets, cursor = [], tail_start
                for char in combined:
                    offsets.append(cursor)
                    cursor += len(char.encode("utf-8", errors="surrogateescape"))
                # No data is discarded until its overlapping match window was inspected.
                for code, offset, rule in _text_hits(combined, offsets, fingerprints):
                    prefix_length = 0
                    # Byte offsets are raw, file-relative, including escaped-string findings.
                    import bisect
                    prefix_length = bisect.bisect_left(offsets, offset)
                    line = line_base + combined.count("\n", 0, prefix_length)
                    if code == "scrub_token" and (offset, rule) in metadata_offsets:
                        deferred.append((code, display, offset, line, rule))
                    else:
                        add(code, display, offset, line, rule)
                if final:
                    break
                cut = max(0, len(combined) - overlap)
                line_base += combined.count("\n", 0, cut)
                text_tail = combined[cut:]
                tail_start = offsets[cut] if cut < len(offsets) else cursor
                absolute += len(raw)
            if digest.hexdigest() != POLICY_SHA256:
                for item in deferred:
                    add(*item)
            report["files_checked"] += 1
        except OSError as exc:
            add("unsafe_link" if exc.errno in (errno.ELOOP, errno.ENOTDIR) else "unreadable", display)
        except Exception:
            add("unreadable", display)
        finally:
            if fd is not None:
                os.close(fd)

    def traverse(parent, prefix=""):
        try:
            with os.scandir(parent) as entries:
                names = sorted(entry.name for entry in entries)
        except OSError:
            add("unreadable", prefix or None)
            return
        for name in names:
            relative = prefix + "/" + name if prefix else name
            display = None
            child = None
            try:
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                display = safe_name(relative, directory=stat.S_ISDIR(info.st_mode))
                # The dependency link is an explicit boundary. No target lookup.
                excluded = not prefix and name in _BOUNDARIES and (
                    stat.S_ISDIR(info.st_mode) or (name == "node_modules" and stat.S_ISLNK(info.st_mode)))
                if excluded:
                    report["exclusions"].append(name + "/")
                    continue
                if stat.S_ISDIR(info.st_mode):
                    child = os.open(name, _flags(True), dir_fd=parent)
                    traverse(child, relative)
                elif stat.S_ISREG(info.st_mode):
                    scan_file(parent, name, relative, display)
                else:
                    add("unsafe_link", display, rule="nonregular_entry")
            except OSError as exc:
                if display is None:
                    display = safe_name(relative)
                add("unsafe_link" if exc.errno in (errno.ELOOP, errno.ENOTDIR) else "unreadable", display)
            finally:
                if child is not None:
                    os.close(child)

    root_fd = None
    try:
        path = Path(root)
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            add("unsafe_link" if stat.S_ISLNK(info.st_mode) else "unreadable", rule="invalid_root")
        else:
            root_fd = os.open(path, _flags(True))
            traverse(root_fd)
    except (OSError, ValueError, TypeError):
        add("unreadable", rule="root_unavailable")
    finally:
        if root_fd is not None:
            os.close(root_fd)
    report["exclusions"].sort()
    report["findings"] = [{"code": c, "path": p, "line": l, "byte_offset": o, "rule_id": r}
        for c, p, l, o, r in sorted(findings, key=lambda f: (f[1] or "", -1 if f[3] is None else f[3], f[4], f[0]))]
    report["ok"] = not report["findings"]
    return report


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("bad_args")


def main(argv=None):
    parser = _Parser(add_help=False, allow_abbrev=False)
    parser.add_argument("--root", required=True)
    try:
        args = parser.parse_args(argv)
        if not args.root:
            raise ValueError("bad_args")
    except (ValueError, SystemExit):
        print('{"ok":false,"code":"bad_args"}')
        return 2
    report = scan_tree(args.root)
    print(_canonical(report).decode("utf-8"))
    return 0 if report["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
