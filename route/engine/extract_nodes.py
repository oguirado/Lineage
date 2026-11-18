#!/usr/bin/env python3
"""Deterministic corpus node extractor emitting ctx.node.v2 JSONL records."""

import argparse
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import sys

VALID_MOUNTS = ("sw", "os", "vg", "nl", "oc")
MAX_COMPOSITE_BYTES = 32

ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]{0,31}$")
CORPUS_RE = re.compile(r"^[a-z][a-z0-9_]{0,15}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

EN_PAPER_RE = re.compile(
    r"^EN-(\d{3})-(\d{3})-(\d{4})-\d-\d{4}-[A-Z0-9-]+-([A-Z0-9]+)-([A-Z])-(\d{3,4})_WaveMind_(.+)\.md$"
)
EN_GENERIC_RE = re.compile(r"^(EN-\d{3}-[A-Za-z0-9-]+?)_WaveMind_(.+)\.md$")
SW_HYPERBOOK_RE = re.compile(
    r"^(?:\d{2}_(?:CONTEXT|ARCHITECTURE|PRELIMINARY)_[A-Za-z0-9_]+|Catalogo_[A-Za-z0-9_]+)\.md$"
)
OS_NODE_RE = re.compile(r"^([A-Z][A-Z0-9]{0,11}\d{2}\.\d{2}|[A-Z]{2,12}\.\d{2})\.md$")
NL_CHAPTER_RE = re.compile(r"^(\d{4})_([A-Z]{3})_[a-z0-9_]+?(?:_v(\d+))?\.md$")
NL_F_RE = re.compile(r"^(F\d)_([A-Z]{3}\d{3})_(analogies|ludic|pitfalls)\.md$")
OS_HYPERBOOK_RE = re.compile(
    r"^(?:CATALOGO_[A-Za-z0-9_]+|CONSTITUCION_[A-Za-z0-9_]+|OS\d{2}_CROSS\.?|Compilado[A-Za-z0-9]+_\d+)\.md$"
)
OS_MOD_RE = re.compile(r"^(OS\d{2}_([A-Z0-9]+))$")

DEFAULT_EXCLUDES = {
    "common": (
        ".git",
        "_archive",
        "build",
        "exports",
        "staging",
        "scratch",
        "node_modules",
        "__pycache__",
    ),
    "sw": ("pilot", "tools", "standards"),
    "vg": ("pilot", "tools", "standards"),
    "os": ("SOs", "prompts", "briefs", "packs", "logs"),
    "nl": ("SOs", "prompts", "briefs", "packs", "logs"),
    "oc": ("SOs", "prompts", "briefs", "packs", "logs"),
}

STOPWORDS = frozenset({
    "the", "and", "for", "with", "from", "that", "this", "into", "over", "under",
    "when", "where", "which", "while", "must", "only", "every", "each", "file",
    "files", "routed", "repository", "src", "internal", "pkg", "cmd", "lib", "mod",
    "true", "false", "none", "null", "self", "super", "crate", "pub", "use", "let",
    "mut", "const", "static", "return", "async", "await", "def", "class", "function",
    "export", "import", "var", "type", "struct", "enum", "trait", "impl", "func",
    "package", "interface", "string", "int", "bool", "usize", "u64", "u32", "u8",
    "i64", "i32", "f64", "str", "vec", "option", "result", "err", "new", "default",
    "are", "was", "were", "been", "being", "have", "has", "had", "having", "does",
    "did", "doing", "can", "could", "should", "would", "may", "might", "will",
    "shall", "not", "nor", "but", "yet", "also", "very", "too", "just", "more",
    "most", "other", "some", "such", "no", "own", "same", "than", "then", "there",
    "these", "they", "their", "them", "those", "through", "during", "before",
    "after", "above", "below", "between", "out", "off", "down", "about", "against",
    "all", "any", "both", "few", "many", "much", "via", "per", "one", "two", "three",
    "four", "five", "first", "second", "third", "section", "node", "paper", "card",
    "chapter", "part", "table", "figure", "line", "lines", "measured", "cited",
    "target", "derived", "absent", "invent", "host", "slot", "local", "yes",
})

SUBCODE_DOMAINS = {
    "SWKRN": ("kernel_runtime", "strong"),
    "SWLAYER": ("software_architecture", "strong"),
    "SWIKG": ("information_retrieval", "strong"),
    "LC": ("programming_languages", "strong"),
    "STO": ("storage_systems", "strong"),
    "NIM": ("inference_microservices", "strong"),
    "MEM": ("memory_architecture", "strong"),
    "NET": ("networking_fabric", "strong"),
    "SEC": ("security_containment", "strong"),
    "KERN": ("kernel_substrate", "strong"),
    "GPU": ("gpu_compute", "strong"),
}

MOUNT_BASE_DOMAIN = {
    "sw": ("software_engineering", "strong"),
    "vg": ("game_engineering", "strong"),
    "os": ("gb10_uma_substrate", "moderate"),
    "nl": ("game_design_cognition", "strong"),
    "oc": ("language_toolchains", "strong"),
}


class ExtractorError(Exception):
    """Raised on fatal extraction errors (exit code 3)."""


def _ascii_alpha(ch: str) -> bool:
    return ("A" <= ch <= "Z") or ("a" <= ch <= "z")


def _clean_markdown_text(text: str) -> str:
    # Remove absolute paths inside citations or prose for strict privacy
    text = re.sub(r"/(?:home|root|usr|var|tmp|etc|opt|mnt|srv)/[^\s\]\"')>]+", "", text)
    # Remove tagging brackets
    text = re.sub(
        r"\[(?:MEASURED|CITED|TARGET|DERIVED)(?:\s+[^\]]*)?\]", "", text
    )
    # Remove markdown links [label](url) -> label
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Unescape markdown backslashes
    text = re.sub(r"\\([._*`#()+\-\[\]\\])", r"\1", text)
    # Strip bold, italics, code ticks
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"\1", text)
    # Strip trailing numeric footnote markers attached to punctuation (e.g. ".1", ".3")
    text = re.sub(r"([.;,:])\d{1,2}(?=\s|$)", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _slugify(text: str, max_len: int = 56) -> str:
    cleaned = _clean_markdown_text(text).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", cleaned).strip("-")
    if not slug:
        slug = "section"
    return slug[:max_len].rstrip("-") or "section"


def _classify_intent(heading_text: str) -> str:
    low = heading_text.lower()
    if any(
        w in low
        for w in (
            "abstract", "claim", "theorem", "proof", "oracle", "verification",
            "receipt", "contradiction", "mutant", "validation", "rebuttal",
        )
    ):
        return "check_claim"
    if any(
        w in low
        for w in (
            "bound", "floor", "limit", "ceiling", "capacity", "bottleneck",
            "watermark", "throttling", "budget", "cost", "evaluation",
            "calibration", "residual", "telemetry", "bandwidth", "performance",
        )
    ):
        return "find_bound"
    if any(
        w in low
        for w in (
            "invariant", "precondition", "constraint", "veto", "imperative",
            "source key", "identity", "prerequisite", "residency", "contract",
            "posture", "axiom",
        )
    ):
        return "find_prerequisite"
    if any(
        w in low
        for w in (
            "failure", "edge case", "anti-pattern", "disadvantage", "trap",
            "storm", "spill", "threat", "thrashing", "collapse", "instability",
            "fallacy",
        )
    ):
        return "find_limit"
    if any(
        w in low
        for w in (
            "architecture", "taxonomy", "anatomy", "model", "structure",
            "geometry", "layout", "ecosystem", "bridge", "hierarchy",
            "foundation", "decomposition", "roadmap",
        )
    ):
        return "find_structure"
    return "find_method"


def _ident_tokens(text: str) -> list[str]:
    cleaned = re.sub(r"/(?:home|root|usr|var|tmp|etc)/[^\s\]\"')>]+", " ", text)
    out: list[str] = []
    seen: set[str] = set()
    for raw_tok in re.findall(r"[A-Za-z0-9_.-]+", cleaned):
        raw_tok = raw_tok.strip("._-")
        if not raw_tok:
            continue
        # Split camelCase and snake_case
        camel_split = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw_tok)
        parts = re.split(r"[\s_.-]+", camel_split)
        for p in parts:
            low = p.lower()
            if (
                len(low) >= 2
                and not low.isdigit()
                and low not in STOPWORDS
                and low not in seen
            ):
                seen.add(low)
                out.append(low)
        whole_low = raw_tok.lower()
        if (
            len(whole_low) >= 2
            and len(whole_low) <= 48
            and not whole_low.isdigit()
            and whole_low not in STOPWORDS
            and whole_low not in seen
        ):
            seen.add(whole_low)
            out.append(whole_low)
    return out


def _truncate_utf8(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    clipped = encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()
    # Try to break at a word or sentence boundary
    last_space = clipped.rfind(" ")
    if last_space >= max_bytes // 2:
        clipped = clipped[:last_space].rstrip(" ,;:-")
    return clipped


def _parse_markdown(text: str) -> dict:
    lines = text.splitlines()
    in_fence = False
    fence_tag = ""
    fence_lines: list[str] = []
    swkg_meta: dict = {}
    h1_title: str | None = None
    headings: list[tuple[int, int, str]] = []  # (lineno, level, text)
    paragraphs: list[tuple[int, str, str]] = []  # (start_line, current_h2, text)
    inline_codes: list[str] = []

    current_h2 = ""
    cur_para: list[str] = []
    cur_para_line = 1

    def flush_para():
        nonlocal cur_para
        if cur_para:
            joined = " ".join(cur_para).strip()
            if joined:
                paragraphs.append((cur_para_line, current_h2, joined))
            cur_para = []

    for idx, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            flush_para()
            if not in_fence:
                in_fence = True
                fence_tag = stripped[3:].strip()
                fence_lines = []
            else:
                if fence_tag.startswith("json swkg.") and not swkg_meta:
                    raw_json = "\n".join(fence_lines).strip()
                    try:
                        parsed = json.loads(raw_json)
                        if isinstance(parsed, dict):
                            swkg_meta = parsed
                    except ValueError:
                        # Extract id/family/title via regex if line was truncated or malformed
                        m_id = re.search(r'"id"\s*:\s*"([^"]+)"', raw_json)
                        m_fam = re.search(r'"family"\s*:\s*"([^"]+)"', raw_json)
                        m_tit = re.search(r'"title"\s*:\s*"([^"]+)"', raw_json)
                        if m_id:
                            swkg_meta["id"] = m_id.group(1)
                        if m_fam:
                            swkg_meta["family"] = m_fam.group(1)
                        if m_tit:
                            swkg_meta["title"] = m_tit.group(1)
                in_fence = False
                fence_tag = ""
                fence_lines = []
            continue

        if in_fence:
            fence_lines.append(raw_line)
            continue

        # Collect inline code spans outside fences
        for code_match in re.findall(r"`([^`]{2,48})`", raw_line):
            if "/" not in code_match and " " not in code_match:
                inline_codes.append(code_match)

        m_heading = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if m_heading:
            flush_para()
            hashes, h_text = m_heading.group(1), m_heading.group(2).strip()
            level = len(hashes)
            clean_h = _clean_markdown_text(h_text)
            if level == 1 and h1_title is None and clean_h:
                h1_title = clean_h
            elif level in (2, 3) and clean_h:
                headings.append((idx, level, clean_h))
                if level == 2:
                    current_h2 = clean_h
            continue

        # Skip tables, images, horizontal rules, HTML comments
        if (
            not stripped
            or stripped.startswith("|")
            or stripped.startswith("![")
            or stripped.startswith("---")
            or stripped.startswith("<!--")
        ):
            flush_para()
            continue

        # Skip metadata bullet lines at top of SW papers
        if stripped.startswith("- id:") or stripped.startswith("- Lifecycle:") or stripped.startswith("- Machine contract:"):
            flush_para()
            continue

        if not cur_para:
            cur_para_line = idx
        cur_para.append(stripped)

    flush_para()
    return {
        "swkg_meta": swkg_meta,
        "h1_title": h1_title,
        "headings": headings,
        "paragraphs": paragraphs,
        "inline_codes": inline_codes,
    }


def _classify_routable(mount: str, rel_posix: str) -> tuple[str | None, str | None]:
    """Return (kind, skip_reason). If routable, skip_reason is None."""
    parts = rel_posix.split("/")
    filename = parts[-1]

    if mount in ("sw", "vg"):
        if EN_PAPER_RE.match(filename) or EN_GENERIC_RE.match(filename):
            return "paper", None
        if SW_HYPERBOOK_RE.match(filename):
            return "hyperbook", None
        return None, "non_routable_sw_vg_file"

    if mount in ("os", "nl", "oc"):
        in_research = "research" in parts[:-1]
        if in_research and OS_NODE_RE.match(filename):
            return "paper", None
        if mount == "nl" and in_research and (NL_CHAPTER_RE.match(filename) or NL_F_RE.match(filename)):
            return "paper", None
        if OS_HYPERBOOK_RE.match(filename):
            return "hyperbook", None
        low_name = filename.lower()
        if "brief" in low_name or "prompt" in low_name:
            return None, "noise_brief_or_prompt"
        if low_name in ("claude.md", "readme.md") or low_name.startswith("contexto_"):
            return None, "noise_context_or_agent_file"
        return None, "non_routable_other_file"

    return None, "unsupported_mount"


def _derive_node_id(
    mount: str, rel_posix: str, kind: str, swkg_meta: dict, max_id_bytes: int
) -> str:
    filename = rel_posix.rsplit("/", 1)[-1]
    stem = filename[:-3] if filename.endswith(".md") else filename

    # 1. Check swkg metadata id for sw/vg
    if mount in ("sw", "vg") and kind == "paper":
        meta_id = swkg_meta.get("id")
        if (
            isinstance(meta_id, str)
            and ID_RE.fullmatch(meta_id)
            and len(meta_id.encode("utf-8")) <= max_id_bytes
        ):
            return meta_id

        m_en = EN_PAPER_RE.match(filename)
        if m_en:
            corpus_code, _fam, _method, subcode, _tier, num = (
                m_en.group(1),
                m_en.group(2),
                m_en.group(3),
                m_en.group(4),
                m_en.group(5),
                m_en.group(6),
            )
            if subcode.startswith("LC"):
                cand = f"LC-{num}"
            elif corpus_code == "060" or mount == "vg":
                cand = f"VG-{num}" if subcode == "VG" else f"VG-{subcode}-{num}"
            else:
                cand = f"SW-{num}"
            if ID_RE.fullmatch(cand) and len(cand.encode("utf-8")) <= max_id_bytes:
                return cand

        m_gen = EN_GENERIC_RE.match(filename)
        if m_gen:
            coord_segs = m_gen.group(1).split("-")
            tail = "-".join(coord_segs[-2:]) if len(coord_segs) >= 2 else coord_segs[-1]
            if not _ascii_alpha(tail[0]):
                tail = "EN-" + tail
            tail = re.sub(r"[^A-Za-z0-9._:-]", "-", tail)[:max_id_bytes]
            if ID_RE.fullmatch(tail):
                return tail

    # 2a. NeuroLudus chapters (0100_FND_slug[_vN].md -> FND-0100[.vN]) and F-series companions (F2_AIA001_ludic.md -> F2-AIA001-ludic)
    if mount == "nl" and kind == "paper":
        m_ch = NL_CHAPTER_RE.match(filename)
        if m_ch:
            cand = f"{m_ch.group(2)}-{m_ch.group(1)}" + (f".v{m_ch.group(3)}" if m_ch.group(3) else "")
            if ID_RE.fullmatch(cand) and len(cand.encode("utf-8")) <= max_id_bytes:
                return cand
        m_f = NL_F_RE.match(filename)
        if m_f:
            cand = f"{m_f.group(1)}-{m_f.group(2)}-{m_f.group(3)}"
            if ID_RE.fullmatch(cand) and len(cand.encode("utf-8")) <= max_id_bytes:
                return cand

    # 2. Research nodes in os/nl/oc
    if mount in ("os", "nl", "oc") and kind == "paper":
        m_os = OS_NODE_RE.match(filename)
        if m_os:
            cand = m_os.group(1)
            if not _ascii_alpha(cand[0]):
                cand = "N" + cand
            if ID_RE.fullmatch(cand) and len(cand.encode("utf-8")) <= max_id_bytes:
                return cand

    # 3. Hyperbooks or fallback semantic stem
    clean_stem = re.sub(r"[^A-Za-z0-9._:-]", "-", stem).strip("-")
    if not clean_stem or not _ascii_alpha(clean_stem[0]):
        clean_stem = "doc-" + clean_stem
    if (
        len(clean_stem.encode("utf-8")) <= max_id_bytes
        and ID_RE.fullmatch(clean_stem)
    ):
        return clean_stem

    # 4. Stem-anchored SHA-256 digest fallback
    alpha_stem = re.sub(r"[^A-Za-z0-9]", "", stem)
    if not alpha_stem or not _ascii_alpha(alpha_stem[0]):
        alpha_stem = "doc" + alpha_stem
    digest = hashlib.sha256(rel_posix.encode("utf-8")).hexdigest()[:12]
    prefix_len = max(1, min(7, max_id_bytes - 13))
    cand = f"{alpha_stem[:prefix_len]}-{digest}"
    if len(cand.encode("utf-8")) > max_id_bytes or not ID_RE.fullmatch(cand):
        raise ExtractorError(f"Cannot derive schema-valid id for {rel_posix}")
    return cand


def _extract_purpose(parsed: dict, title: str, kind: str) -> str:
    paragraphs = parsed["paragraphs"]
    chosen = ""

    # Priority 1: look for Scope: or Abstract section paragraph
    for _line, h2, ptext in paragraphs:
        h2_low = h2.lower()
        if "abstract" in h2_low or "identity" in h2_low or "foundations" in h2_low or "posture" in h2_low:
            cleaned = _clean_markdown_text(ptext)
            if cleaned.lower().startswith("scope:"):
                chosen = cleaned
                break
            if len(cleaned) >= 40 and not cleaned.startswith("- **[MEASURED]"):
                chosen = cleaned
                break

    # Priority 2: first substantial paragraph that isn't tagging boilerplate
    if not chosen:
        for _line, h2, ptext in paragraphs:
            if "source key" in h2.lower():
                continue
            cleaned = _clean_markdown_text(ptext)
            if (
                len(cleaned) >= 35
                and not cleaned.startswith("Lineage:")
                and not cleaned.startswith("Source discipline.")
            ):
                chosen = cleaned
                break

    if not chosen:
        chosen = title

    # Take first 1-2 sentences fitting within 400 UTF-8 bytes
    sentences = re.split(r"(?<=[.!?])\s+", chosen)
    acc: list[str] = []
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        candidate = " ".join(acc + [sent])
        if len(candidate.encode("utf-8")) <= 400:
            acc.append(sent)
            if len(acc) >= 2:
                break
        else:
            if not acc:
                acc.append(_truncate_utf8(sent, 396))
            break

    purpose = " ".join(acc).strip() if acc else _truncate_utf8(chosen, 396)
    purpose = _truncate_utf8(purpose, 400)
    if not purpose:
        purpose = _truncate_utf8(title, 240) or "Corpus node."
    return purpose[:600]


def _build_anchors(parsed: dict) -> list[dict]:
    headings = parsed["headings"]
    if not headings:
        return [{"a": "L1:document-root", "role": "section", "intent": "find_structure"}]

    # Separate H2 and H3 to ensure all major H2 sections are represented when > 16 headings
    h2_list = [h for h in headings if h[1] == 2]
    h3_list = [h for h in headings if h[1] == 3]

    selected = h2_list[:16]
    remaining_slots = 16 - len(selected)
    if remaining_slots > 0:
        selected.extend(h3_list[:remaining_slots])
    selected.sort(key=lambda item: item[0])

    anchors: list[dict] = []
    seen_a: set[str] = set()
    for lineno, _level, h_text in selected:
        prefix = f"L{lineno}:"
        slug = _slugify(h_text, max_len=64 - len(prefix))
        a_val = f"{prefix}{slug}"[:64]
        if a_val in seen_a:
            continue
        seen_a.add(a_val)
        anchors.append({
            "a": a_val,
            "role": "section",
            "intent": _classify_intent(h_text),
        })

    if not anchors:
        anchors.append({"a": "L1:document-root", "role": "section", "intent": "find_structure"})
    return anchors[:16]


def _extract_family_and_domains(
    mount: str, rel_posix: str, kind: str, swkg_meta: dict
) -> tuple[str | None, list[dict]]:
    filename = rel_posix.rsplit("/", 1)[-1]
    parts = rel_posix.split("/")
    family: str | None = None
    domains: list[dict] = []
    seen_dom: set[str] = set()

    def add_dom(name: str, strength: str):
        name = name[:40]
        if name and name not in seen_dom and len(domains) < 11:
            seen_dom.add(name)
            domains.append({"domain": name, "strength": strength})

    base_dom, base_str = MOUNT_BASE_DOMAIN[mount]
    add_dom(base_dom, base_str)

    if mount in ("sw", "vg"):
        meta_fam = swkg_meta.get("family")
        if isinstance(meta_fam, str) and meta_fam.strip():
            family = meta_fam.strip()[:32]
        m_en = EN_PAPER_RE.match(filename)
        if m_en:
            if not family:
                family = f"F{int(m_en.group(2)):02d}"
            subcode = m_en.group(4)
            if subcode in SUBCODE_DOMAINS:
                d_name, d_str = SUBCODE_DOMAINS[subcode]
                add_dom(d_name, d_str)
            elif subcode.startswith("LC"):
                add_dom("programming_languages", "strong")
                add_dom(subcode[2:].lower()[:40], "strong")
        elif kind == "hyperbook":
            family = "hyperbook"
            add_dom("architecture_catalogue", "moderate")

    elif mount in ("os", "nl", "oc"):
        for seg in parts[:-1]:
            m_mod = OS_MOD_RE.match(seg)
            if m_mod:
                family = m_mod.group(1)[:32]
                mod_short = m_mod.group(2)
                if mod_short in SUBCODE_DOMAINS:
                    d_name, d_str = SUBCODE_DOMAINS[mod_short]
                    add_dom(d_name, d_str)
                else:
                    add_dom(f"module_{mod_short.lower()}", "strong")
                break
        if not family:
            if len(parts) >= 2 and parts[-2] != "research":
                family = parts[-2][:32]
            elif kind == "hyperbook":
                family = "catalogue"
                add_dom("architecture_catalogue", "moderate")
            else:
                m_prefix = re.match(r"^([A-Z]{2,10})", filename)
                if m_prefix:
                    family = m_prefix.group(1)[:32]

    return family, domains


def _build_search_zones(
    node_id: str,
    mount: str,
    rel_posix: str,
    kind: str,
    title: str,
    purpose: str,
    family: str | None,
    domains: list[dict],
    parsed: dict,
) -> dict:
    triggers: list[str] = []
    keywords: list[str] = []
    problem_names: list[str] = []
    tasks: list[str] = []
    questions: list[str] = []
    exclusions: list[str] = []

    def add_trig(val: str):
        val = val.strip()[:64]
        if val and val not in triggers and len(triggers) < 12:
            triggers.append(val)

    def add_kw(val: str):
        val = val.strip()[:64]
        if val and val not in keywords and len(keywords) < 24:
            keywords.append(val)

    def add_prob(val: str):
        val = val.strip()[:64]
        if val and val not in problem_names and len(problem_names) < 5:
            problem_names.append(val)

    def add_task(val: str):
        val = val.strip()[:200]
        if val and val not in tasks and len(tasks) < 8:
            tasks.append(val)

    def add_q(val: str):
        val = val.strip()[:200]
        if val and val not in questions and len(questions) < 12:
            questions.append(val)

    # 1. Node ID and structural identifiers
    add_trig(node_id)
    add_trig(node_id.lower())
    add_kw(node_id.lower())

    if family:
        add_trig(family.lower())
        add_kw(family.lower())

    filename = rel_posix.rsplit("/", 1)[-1]
    m_en = EN_PAPER_RE.match(filename)
    if m_en:
        subcode = m_en.group(4).lower()
        add_trig(subcode)
        add_kw(subcode)

    # 2. Title tokens and problem names
    title_tokens = _ident_tokens(title)
    for tok in title_tokens:
        if kind == "paper":
            add_trig(tok)
        add_kw(tok)

    # Problem names from colon/dash splits of title and major H2s
    for chunk in re.split(r"[:—–\-()]+", title):
        clean_chunk = _clean_markdown_text(chunk).strip()
        if 6 <= len(clean_chunk) <= 64 and clean_chunk.lower() != node_id.lower():
            add_prob(clean_chunk.lower())

    # 3. Inline codes & technical symbols
    for code_sym in parsed["inline_codes"]:
        for tok in _ident_tokens(code_sym):
            add_kw(tok)
            if len(triggers) < 12 and kind == "paper":
                add_trig(tok)

    # 4. Headings tokens & problem names
    heading_phrases: list[str] = []
    for _lineno, level, h_text in parsed["headings"]:
        clean_h = re.sub(r"^\d+(?:\.\d+)*\s*[·.]?\s*", "", h_text).strip()
        if clean_h:
            heading_phrases.append(clean_h)
            if level == 2 and 6 <= len(clean_h) <= 64:
                add_prob(clean_h.lower())
        for tok in _ident_tokens(clean_h):
            add_kw(tok)
            if len(triggers) < 12 and kind == "paper":
                add_trig(tok)

    # 5. Purpose tokens and domain tags
    for tok in _ident_tokens(purpose):
        add_kw(tok)
    for dom in domains:
        for tok in _ident_tokens(dom["domain"]):
            add_kw(tok)

    if kind == "hyperbook":
        add_kw("catalogue")
        add_kw("overview")
        exclusions.append("single_node_proof")

    # 6. Synthesize dense tasks and questions (<= 200 chars each)
    concept_stream: list[str] = []
    for tok in title_tokens + keywords:
        if tok not in concept_stream:
            concept_stream.append(tok)
    for hp in heading_phrases:
        for tok in _ident_tokens(hp):
            if tok not in concept_stream:
                concept_stream.append(tok)

    if concept_stream:
        for start in range(0, min(len(concept_stream), 96), 16):
            phrase = " ".join(concept_stream[start : start + 16])[:200]
            if phrase:
                add_task(phrase)
                add_q(phrase)

    for hp in heading_phrases[:8]:
        q_str = f"{node_id} {hp}"[:200]
        add_q(q_str)

    if not triggers:
        triggers.append(node_id[:64])
    if not keywords:
        keywords.append(mount)

    search: dict = {
        "triggers": triggers[:12],
        "keywords": keywords[:24],
    }
    if problem_names:
        search["problem_names"] = problem_names[:5]
    if tasks:
        search["tasks"] = tasks[:8]
    if questions:
        search["questions"] = questions[:12]
    if exclusions:
        search["exclusions"] = exclusions[:12]
    return search


def _validate_record(rec: dict, max_id_bytes: int) -> None:
    """Strict self-check against ctx.node.v2.schema.json invariants."""
    required = (
        "schema", "id", "corpus", "kind", "title", "purpose",
        "anchors", "search", "status", "source_sha256",
    )
    for req in required:
        if req not in rec:
            raise ExtractorError(f"Missing required field {req}")
    if rec["schema"] != "ctx.node.v2":
        raise ExtractorError("Invalid schema const")
    if not CORPUS_RE.fullmatch(rec["corpus"]):
        raise ExtractorError(f"Invalid corpus {rec['corpus']!r}")
    if not ID_RE.fullmatch(rec["id"]) or len(rec["id"].encode("utf-8")) > max_id_bytes:
        raise ExtractorError(f"Invalid or overlong id {rec['id']!r}")
    if rec["kind"] not in ("paper", "section", "symbol", "asset", "scene", "hyperbook"):
        raise ExtractorError(f"Invalid kind {rec['kind']!r}")
    if not (1 <= len(rec["title"]) <= 240):
        raise ExtractorError(f"Invalid title length on {rec['id']}")
    if not (1 <= len(rec["purpose"]) <= 600):
        raise ExtractorError(f"Invalid purpose length on {rec['id']}")
    if not (1 <= len(rec["anchors"]) <= 16):
        raise ExtractorError(f"Invalid anchors count on {rec['id']}")
    for anc in rec["anchors"]:
        if not (1 <= len(anc["a"]) <= 64):
            raise ExtractorError(f"Invalid anchor 'a' on {rec['id']}")
    if not SHA256_RE.fullmatch(rec["source_sha256"]):
        raise ExtractorError(f"Invalid source_sha256 on {rec['id']}")
    if not (1 <= len(rec["search"].get("triggers", [])) <= 12):
        raise ExtractorError(f"Invalid search.triggers on {rec['id']}")
    if not (1 <= len(rec["search"].get("keywords", [])) <= 24):
        raise ExtractorError(f"Invalid search.keywords on {rec['id']}")


def _is_excluded(rel_posix: str, exclude_prefixes: tuple[str, ...]) -> str | None:
    parts = rel_posix.split("/")
    for pref in exclude_prefixes:
        pref_clean = pref.strip("/")
        if not pref_clean:
            continue
        if rel_posix == pref_clean or rel_posix.startswith(pref_clean + "/"):
            return f"excluded_prefix:{pref_clean}"
        if pref_clean in parts[:-1]:
            return f"excluded_dir:{pref_clean}"
    return None


def _discover_md_files(root_dir: str) -> list[str]:
    rel_files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames.sort()
        filenames.sort()
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            full_path = os.path.join(dirpath, fname)
            rel_os = os.path.relpath(full_path, root_dir)
            rel_posix = PurePosixPath(rel_os).as_posix()
            rel_files.append(rel_posix)
    rel_files.sort(key=lambda item: item.encode("utf-8"))
    return rel_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="extract_nodes.py",
        description="Deterministic ctx.node.v2 extractor for Markdown corpora.",
    )
    parser.add_argument("--mount", required=True, choices=VALID_MOUNTS)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--report", default=None)

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code != 0 else 0

    mount: str = args.mount
    root_dir: str = os.path.abspath(args.root)
    if not os.path.isdir(root_dir):
        sys.stderr.write(f"Error: --root is not a directory: {args.root}\n")
        return 3

    max_id_bytes = MAX_COMPOSITE_BYTES - len(mount.encode("utf-8")) - 1
    exclude_prefixes = tuple(
        list(DEFAULT_EXCLUDES["common"])
        + list(DEFAULT_EXCLUDES.get(mount, ()))
        + [p.replace("\\", "/").strip("/") for p in args.exclude if p.strip("/")]
    )

    try:
        all_md = _discover_md_files(root_dir)
    except OSError as exc:
        sys.stderr.write(f"Error scanning root directory: {exc}\n")
        return 3

    # Pre-order so canonical shorter paths (e.g. research/OS51_NIM/NIM01.01.md)
    # are evaluated before mirror paths (docs/Proyecto_Catalogo2/research/...),
    # while emitting records sorted deterministically by (rel_posix_bytes).
    candidates: list[tuple[str, str]] = []
    skipped: list[dict[str, str]] = []

    for rel_posix in all_md:
        ex_reason = _is_excluded(rel_posix, exclude_prefixes)
        if ex_reason is not None:
            skipped.append({"path": rel_posix, "reason": ex_reason})
            continue
        kind, skip_reason = _classify_routable(mount, rel_posix)
        if kind is None:
            skipped.append({"path": rel_posix, "reason": skip_reason or "excluded"})
            continue
        candidates.append((rel_posix, kind))

    # Sort by path depth (canonical first) for mirror deduplication on os/nl/oc
    candidates_by_canon = sorted(
        candidates,
        key=lambda item: (item[0].count("/"), item[0].encode("utf-8")),
    )

    seen_ids: dict[str, str] = {}
    records_by_rel: dict[str, dict] = {}
    counts_by_kind: dict[str, int] = {}
    longest_id = ""

    try:
        for rel_posix, kind in candidates_by_canon:
            full_path = os.path.join(root_dir, *rel_posix.split("/"))
            try:
                with open(full_path, "rb") as fh:
                    raw_bytes = fh.read()
                text = raw_bytes.decode("utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise ExtractorError(f"Unreadable file {rel_posix}: {exc}") from exc

            source_sha256 = hashlib.sha256(raw_bytes).hexdigest()
            parsed = _parse_markdown(text)
            node_id = _derive_node_id(
                mount, rel_posix, kind, parsed["swkg_meta"], max_id_bytes
            )

            if node_id in seen_ids:
                prev_rel = seen_ids[node_id]
                # Check if this is a known mirror tree duplicate in os/nl/oc
                if (
                    mount in ("os", "nl", "oc")
                    and rel_posix.rsplit("/", 1)[-1] == prev_rel.rsplit("/", 1)[-1]
                ):
                    skipped.append({
                        "path": rel_posix,
                        "reason": f"duplicate_mirror_of:{prev_rel}",
                    })
                    continue
                raise ExtractorError(
                    f"Duplicate node id {node_id!r} between {prev_rel} and {rel_posix}"
                )

            seen_ids[node_id] = rel_posix
            if len(node_id.encode("utf-8")) > len(longest_id.encode("utf-8")) or (
                len(node_id.encode("utf-8")) == len(longest_id.encode("utf-8"))
                and node_id > longest_id
            ):
                longest_id = node_id

            raw_title = (
                parsed["h1_title"]
                or parsed["swkg_meta"].get("title")
                or rel_posix.rsplit("/", 1)[-1].removesuffix(".md").replace("_", " ")
            )
            title = _clean_markdown_text(str(raw_title))[:240]
            if not title:
                title = node_id

            purpose = _extract_purpose(parsed, title, kind)
            anchors = _build_anchors(parsed)
            family, domains = _extract_family_and_domains(
                mount, rel_posix, kind, parsed["swkg_meta"]
            )
            search = _build_search_zones(
                node_id, mount, rel_posix, kind, title, purpose, family, domains, parsed
            )

            record: dict = {
                "schema": "ctx.node.v2",
                "id": node_id,
                "corpus": mount,
                "kind": kind,
                "title": title,
                "purpose": purpose,
                "anchors": anchors,
                "search": search,
                "status": "active",
                "source_sha256": source_sha256,
            }
            if family:
                record["family"] = family
            if domains:
                record["domains"] = domains

            _validate_record(record, max_id_bytes)
            records_by_rel[rel_posix] = record
            counts_by_kind[kind] = counts_by_kind.get(kind, 0) + 1

        # Write canonical JSONL sorted by mount-relative path bytes
        out_parent = os.path.dirname(os.path.abspath(args.out))
        if out_parent:
            os.makedirs(out_parent, exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as out_fh:
            for rel_posix in sorted(
                records_by_rel.keys(), key=lambda item: item.encode("utf-8")
            ):
                line = json.dumps(
                    records_by_rel[rel_posix],
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                out_fh.write(line + "\n")

        if args.report:
            rep_parent = os.path.dirname(os.path.abspath(args.report))
            if rep_parent:
                os.makedirs(rep_parent, exist_ok=True)
            skipped.sort(key=lambda item: item["path"].encode("utf-8"))
            report_obj = {
                "counts_by_kind": dict(sorted(counts_by_kind.items())),
                "longest_id": longest_id,
                "longest_id_bytes": len(longest_id.encode("utf-8")),
                "mount": mount,
                "routed_total": len(records_by_rel),
                "skipped_Files": skipped,
                "skipped_total": len(skipped),
            }
            with open(args.report, "w", encoding="utf-8", newline="\n") as rep_fh:
                rep_fh.write(
                    json.dumps(
                        report_obj,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    except ExtractorError as exc:
        sys.stderr.write(f"ExtractorError: {exc}\n")
        return 3
    except OSError as exc:
        sys.stderr.write(f"OSError: {exc}\n")
        return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
