"""Build the code router, check shipped bytes, or report source freshness."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import compile_nodes as CN

OUTPUTS = ("nodes", "index")
VENDOR_ORIGIN = "PapersFast route engine (corpus-router kit)"
VENDOR_FILES = {f"engine/{name}.py" for name in
                ("route_v2", "build_index_v2", "blocks", "extract_nodes")}


def verify_vendor(directory):
    manifest = C.load(directory / "VENDOR.json")
    if (not isinstance(manifest, dict) or manifest.get("origin") != VENDOR_ORIGIN
            or not isinstance(manifest.get("files"), dict)
            or manifest["files"].keys() != VENDOR_FILES):
        raise ValueError("invalid VENDOR.json")
    for name, entry in sorted(manifest["files"].items()):
        path = directory / name
        if (not isinstance(entry, dict) or path.resolve() != path
                or C.sha256(path.read_bytes()) != entry.get("sha256")):
            raise ValueError(f"engine drift: {name}")


def build_into(directory):
    sys.path.insert(0, str(C.ENGINE))
    import build_index_v2

    nodes, routes, stale = CN.compile_corpus()
    for card in stale:
        print(f"STALE_CARD {C.dumps(card)}", file=sys.stderr)
    node_dir = directory / "nodes"
    node_dir.mkdir()
    node_path = node_dir / "nodes.jsonl"
    node_path.write_bytes("".join(C.dumps(node) + "\n" for node in nodes).encode("utf-8"))
    (node_dir / "routes.json").write_bytes((C.dumps(routes) + "\n").encode("utf-8"))
    index = build_index_v2.build(
        None, str(directory / "index"), None, nodes=str(node_path), corpus=C.CORPUS
    )
    return {"nodes": len(nodes), "index_sha256": index, "stale_cards": stale}


def tree(directory):
    if directory.is_symlink() or not directory.is_dir():
        return None
    result = {}
    for path in directory.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"unexpected output entry: {path.relative_to(directory)}")
        result[path.relative_to(directory)] = None if path.is_dir() else path.read_bytes()
    return result


def publish(staging):
    previous, published = [], []
    try:
        for name in OUTPUTS:
            path = C.HERE / name
            if path.exists() or path.is_symlink():
                path.rename(staging / (name + ".previous"))
                previous.append(name)
            (staging / name).rename(path)
            published.append(name)
    except OSError:
        for name in reversed(published):
            (C.HERE / name).rename(staging / name)
        for name in reversed(previous):
            (staging / (name + ".previous")).rename(C.HERE / name)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="compare a scratch rebuild byte for byte")
    modes.add_argument("--status", action="store_true", help="report source changes since the shipped build")
    args = parser.parse_args()
    if not args.status:
        try:
            verify_vendor(C.HERE)
        except (OSError, ValueError) as exc:
            print(f"E_VENDOR: {exc}", file=sys.stderr)
            return 4

    try:
        if args.status:
            with C.output_lock():
                routes = C.load(C.HERE / "nodes" / "routes.json")
                indexed = CN.indexed_source_hashes(routes)
            modified, added, removed = CN.source_changes(indexed)
            total = modified + added + removed
            status = "stale" if total else "fresh"
            print(f"{status}: {total} files changed ({modified} modified, {added} added, {removed} removed)")
            return 0
        with tempfile.TemporaryDirectory(prefix=".build-", dir=C.HERE) as temporary:
            staging = Path(temporary)
            summary = build_into(staging)
            with C.output_lock(exclusive=not args.check):
                if not args.check:
                    publish(staging)
                else:
                    mismatches = [name for name in OUTPUTS
                                  if tree(staging / name) != tree(C.HERE / name)]
                    if mismatches:
                        print(f"MISMATCH {' '.join(mismatches)}")
                        return 5
    except (OSError, SyntaxError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"E_BUILD: {exc}", file=sys.stderr)
        return 3
    print(f"byte-identical {summary['index_sha256']}" if args.check else C.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
