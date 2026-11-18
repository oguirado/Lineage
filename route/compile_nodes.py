"""Compile a routing node and display metadata per repository source file."""

import argparse
import ast
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tokenize

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

# The boolean describes recursion below the specified prefix.
SURFACES = {
    "lineage": (".py", True),
    "ui/src": (".ts", True),
    "ui/styles": (".css", False),
    "tools": (".py", True),
    "docs": (".md", False),
    "schemas": (None, False),
    "tests": (".py", True),
    "ui/tests": (".ts", True),
}
EXCLUDED = {".git", "_seed", "node_modules", "__pycache__", "fixtures", "fixture_data"}
CARD_SCHEMA = "lineage.route-card.v1"
CARD_ID = re.compile(r"ln-[a-f0-9]{16}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
TOOL = re.compile(r"[a-z][a-z0-9_]*\Z")
TOOL_HEADING = re.compile(r"^#{3} +`([a-z][a-z0-9_]*)`[ \t]*$", re.M)
TOOL_WORD = re.compile(r"\b[a-z][a-z0-9_]*\b")
TS_EXPORT = re.compile(
    r"^export[ \t]+(?:(?:default|declare|abstract|async)[ \t]+)*"
    r"(?:function\*?|class|const|interface)[ \t]+([A-Za-z_$][\w$]*)", re.M
)
MD_HEADING = re.compile(r"^ {0,3}#{1,6}[ \t]+(.+?)\s*#*\s*$")
MD_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def node_id(path):
    return "ln-" + C.sha256(path.encode("utf-8"))[:16]


def in_surface(path):
    if EXCLUDED.intersection(path.parts) or path.is_relative_to("ui/dist"):
        return False
    for prefix, (suffix, recursive) in SURFACES.items():
        if path.is_relative_to(prefix):
            tail = path.relative_to(prefix)
            return bool(tail.parts and (recursive or len(tail.parts) == 1)
                        and (suffix is None or path.suffix == suffix))
    return False


def export_files(root):
    for prefix, (_, recursive) in SURFACES.items():
        start = root / prefix
        if start.resolve() != start:
            continue
        for directory, folders, files in os.walk(start):
            folders[:] = [name for name in folders if recursive and name not in EXCLUDED]
            for filename in files:
                path = Path(directory) / filename
                if not path.is_symlink() and path.is_file():
                    yield PurePosixPath(path.relative_to(root).as_posix())


def source_paths(root):
    if (root / ".git").exists():
        listed = subprocess.check_output(["git", "ls-files", "-z", "--cached"], cwd=root)
        candidates = (PurePosixPath(os.fsdecode(path)) for path in listed.split(b"\0") if path)
    else:
        # Exported workspaces carry only the source tree, with no tracking data.
        candidates = export_files(root)
    return sorted({path.as_posix() for path in candidates if in_surface(path)})


def read_source(root, path):
    if not in_surface(PurePosixPath(path)):
        return None
    source = root / path
    if not source.is_file() or source.resolve() != source:
        return None
    try:
        return source.read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        return None


def sources(root):
    for path in source_paths(root):
        raw = read_source(root, path)
        if raw is not None:
            yield path, raw


def indexed_source_hashes(routes):
    with (C.HERE / "nodes" / "nodes.jsonl").open(encoding="utf-8") as source:
        nodes = (json.loads(line) for line in source if line.strip())
        return {routes[node["id"]]["path"]: node["source_sha256"] for node in nodes}


def source_changes(indexed):
    current = {path: C.sha256(raw) for path, raw in sources(C.ROOT)}
    modified = sum(current[path] != indexed[path] for path in current.keys() & indexed.keys())
    return modified, len(current.keys() - indexed.keys()), len(indexed.keys() - current.keys())


def assignment_names(target):
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            yield from assignment_names(item)
    elif isinstance(target, ast.Starred):
        yield from assignment_names(target.value)


def python_symbols(tree):
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield item.lineno, item.name
        else:
            targets = item.targets if isinstance(item, ast.Assign) else []
            if isinstance(item, ast.AnnAssign):
                targets = [item.target]
            elif isinstance(item, ast.TypeAlias):
                targets = [item.name]
            for target in targets:
                for name in assignment_names(target):
                    yield target.lineno, name


def registration_names(tree):
    descriptors = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    descriptors[target.id] = statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            descriptors[statement.target.id] = statement.value

    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name not in {"register", "ToolSpec"}:
            continue
        value = call.args[0] if call.args else next(
            (kw.value for kw in call.keywords if kw.arg == "name"), None
        )
        if name == "register" and isinstance(value, ast.Name):
            value = descriptors.get(value.id)
        if isinstance(value, ast.Dict):
            value = next((v for k, v in zip(value.keys, value.values)
                          if isinstance(k, ast.Constant) and k.value == "name"), None)
        if isinstance(value, ast.Constant) and isinstance(value.value, str) and TOOL.fullmatch(value.value):
            yield value.value


def headings(text):
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        match = MD_FENCE.match(line)
        if match:
            marker, rest = match.groups()
            if fence is None:
                fence = marker
            elif marker.startswith(fence) and not rest.strip():
                fence = None
        elif fence is None and (match := MD_HEADING.match(line)):
            heading = match[1].strip("` ")
            if heading:
                yield number, heading


def source_metadata(path, raw, contract):
    suffix = PurePosixPath(path).suffix
    docstring = ""
    if suffix == ".py":
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        text = raw.decode(encoding)
        tree = ast.parse(text, filename=path)
        docstring = ast.get_docstring(tree) or ""
        symbols = list(python_symbols(tree))
        tools = set(registration_names(tree))
    else:
        text = raw.decode("utf-8")
        tools = set()
        if suffix == ".ts":
            symbols = [(text.count("\n", 0, m.start()) + 1, m[1]) for m in TS_EXPORT.finditer(text)]
        elif suffix == ".md":
            symbols = list(headings(text))
        else:
            symbols = []
    tools.update(contract.intersection(TOOL_WORD.findall(text)))
    return docstring, symbols, tools


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def records(value, fields):
    return isinstance(value, list) and all(
        isinstance(row, dict) and row.keys() == set(fields)
        and all(check(row[key]) for key, check in fields.items())
        for row in value
    )


def strings(value):
    return isinstance(value, list) and all(map(nonempty, value))


def read_card(card_path):
    card = C.load(card_path)
    validators = {
        "schema": lambda value: value == CARD_SCHEMA,
        "title": nonempty,
        "claims": lambda value: records(value, dict(id=nonempty, text=nonempty, type=nonempty)),
        "triggers": strings,
        "decision": lambda value: records([value], dict(rule=nonempty, failure=nonempty)),
        "questions": lambda value: records(value, dict(q=nonempty)),
        "aliases": strings,
        "edges": lambda value: records(value, {
            "rel": lambda rel: rel in ("imports", "tests", "documents"),
            "to": lambda target: isinstance(target, str) and CARD_ID.fullmatch(target),
        }),
        "source_sha256": lambda value: isinstance(value, str) and SHA.fullmatch(value),
    }
    if not isinstance(card, dict) or card.keys() != validators.keys():
        raise ValueError(f"invalid card fields: {card_path.name}")
    for field, check in validators.items():
        if not check(card[field]):
            raise ValueError(f"invalid card {field}: {card_path.name}")
    return card


def compile_corpus(root=C.ROOT, cards_dir=C.HERE / "cards"):
    contract_raw = read_source(root, "docs/CONTRACT.md")
    contract = set(TOOL_HEADING.findall((contract_raw or b"").decode("utf-8")))
    nodes, routes, stale = [], {}, []
    for path, raw in sources(root):
        source = root / path
        digest = C.sha256(raw)
        ident = node_id(path)
        if ident in routes:
            raise ValueError(f"node id collision: {path} and {routes[ident]['path']}")
        card_path = cards_dir / f"{ident}.card.json"
        card = read_card(card_path) if card_path.exists() else {}
        if card and card["source_sha256"] != digest:
            stale.append({"id": ident, "path": path,
                          "card_sha256": card["source_sha256"], "source_sha256": digest})
            card = {}
        docstring, symbols, tools = source_metadata(path, raw, contract)
        first_line = docstring.split("\n", 1)[0]
        title = f"{path} - {first_line}" if first_line else path
        claims = [claim["text"] for claim in card.get("claims", [])]
        questions = [question["q"] for question in card.get("questions", [])]
        keywords = set(PurePosixPath(path).parts) | tools
        for _, symbol in symbols:
            keywords.update((symbol, C.CAMEL.sub(" ", symbol)))
        role = "symbol" if source.suffix in {".py", ".ts"} else "section"
        anchors = [{"a": f"L{line}:{symbol}", "role": role} for line, symbol in symbols]
        if not anchors:
            anchors = [{"a": "L1:file", "role": "section"}]
        decision = card.get("decision")
        nodes.append({
            "schema": "ctx.node.v2", "corpus": C.CORPUS, "id": ident, "family": ident,
            "kind": "code" if role == "symbol" else "document", "status": "active",
            "title": title, "purpose": " ".join(filter(None, [docstring, *claims])),
            "domains": [], "anchors": anchors, "source_sha256": digest,
            "edges": [[edge["to"], edge["rel"]] for edge in card.get("edges", [])],
            "search": {
                "triggers": card.get("triggers", []), "tasks": [decision["rule"], decision["failure"]] if decision else [],
                "questions": questions, "problem_names": card.get("aliases", []),
                "keywords": sorted(keywords),
            },
        })
        routes[ident] = {"path": path, "anchors": [anchor["a"] for anchor in anchors],
                         "questions": questions}
    return sorted(nodes, key=lambda node: node["id"]), routes, stale


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        nodes, _, stale = compile_corpus()
    except (OSError, SyntaxError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"E_COMPILE: {exc}", file=sys.stderr)
        return 3
    for card in stale:
        print(f"STALE_CARD {C.dumps(card)}", file=sys.stderr)
    for node in nodes:
        print(C.dumps(node))
    return 0


if __name__ == "__main__":
    sys.exit(main())
