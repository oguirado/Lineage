"""Find the Lineage source locations most relevant to a question."""

import argparse
import os
import re
import subprocess
import sys
import warnings

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import compile_nodes as CN

sys.path.insert(0, str(C.ENGINE))
import route_v2 as engine


def best_anchor(query, anchors):
    positions = {}
    for position, word in enumerate(re.findall(r"[\w$]+", query.casefold())):
        positions.setdefault(word, position)
    terms = set(engine.toks(C.CAMEL.sub(" ", query)))

    def match(anchor):
        _, symbol = anchor.split(":", 1)
        position = positions.get(symbol.casefold())
        words = set(engine.toks(C.CAMEL.sub(" ", symbol)))
        return position is not None, -position if position is not None else 0, len(terms & words), -len(words)

    # An exact symbol takes precedence over partial terms. Ties use source order.
    best = max(anchors, key=match)
    exact, _, overlap, _ = match(best)
    return best if exact or overlap else None


def resolve_line(path, raw, line, symbol):
    try:
        with warnings.catch_warnings(action="ignore"):
            _, symbols, _ = CN.source_metadata(path, raw, set())
    except (SyntaxError, ValueError):
        return "?"
    matches = {str(number) for number, name in symbols if name == symbol}
    if line in matches:
        return line
    return matches.pop() if len(matches) == 1 else "?"


def best_question(query, questions):
    tokens = set(engine.toks(query))
    return max(questions, key=lambda q: len(tokens.intersection(engine.toks(q))), default=None)


def rank(index, query, k):
    return engine.route(index, query, k=k, budget=C.BUDGET)


def route_one(query, k):
    with C.output_lock():
        index = engine.Index(os.fspath(C.HERE / "index"))
        routes = C.load(C.HERE / "nodes" / "routes.json")
        indexed = CN.indexed_source_hashes(routes)
        result = rank(index, query, k)
    changed = sum(CN.source_changes(indexed))
    rows = []
    for ident, _, score, *_ in result["r"]:
        route = routes[ident]
        path = route["path"]
        raw = CN.read_source(C.ROOT, path)
        if raw is None:
            continue
        anchor = best_anchor(query, route["anchors"])
        line, symbol = "1", "file"
        if anchor is not None:
            line, symbol = anchor[1:].split(":", 1)
            if C.sha256(raw) != indexed[path]:
                line = resolve_line(path, raw, line, symbol)
        rows.append({"id": ident, "score": score, "path": path,
                     "anchor": f"{path}:{line} {symbol}",
                     "q": best_question(query, route["questions"])})
    return {"index": index.ixid, "abstain": result["abstain"]["flag"], "rows": rows}, changed


def render(result):
    lines = [f"# index {result['index']}"]
    for row in result["rows"]:
        lines.append(f"{row['id']} [{row['score']}] {row['anchor']}")
        if row["q"] is not None:
            lines.append(f"  Q: {row['q']}")
    if not result["rows"]:
        lines.append("(no candidate)")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--q", required=True)
    parser.add_argument("--k", type=int, choices=range(1, C.K_MAX + 1), default=5, metavar="1..20")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result, changed = route_one(args.q, args.k)
    except (engine.IndexError_, OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"E_INDEX: {exc} (build with route/build.py)", file=sys.stderr)
        return 3
    if changed:
        print(f"# index stale: {changed} files changed; run python3 -I route/build.py", file=sys.stderr)
    print(C.dumps(result) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
