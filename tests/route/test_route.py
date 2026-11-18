"""Acceptance tests for the offline, reproducible source router."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CARDS = {
    "lineage/core/journal.py": (
        "ln-0dc04b50a33b3a34", "Why does transact return the original event on a repeated op_id?", "transact",
    ),
    "lineage/core/registry.py": (
        "ln-4bc2d3ea662c5a53", "Where does load reject duplicate ToolSpec names in extension discovery?", "load",
    ),
    "lineage/domain/runs.py": (
        "ln-a048d5b35996c34c", "Where does open_run freeze the agent version and seat before the journal append?", "open_run",
    ),
}
ABSOLUTE_PATH = re.compile(
    r"(?<![\w/])/(?:home|Users|root|tmp|var|opt|etc|run|private|mnt|media|dev|proc|sys|srv|workspace)/[^\s\"'`]+"
    r"|\b[A-Za-z]:[\\/][\w.]|\\\\[\w.-]+\\[\w.$-]+"
)
HOSTNAME = re.compile(
    r"(?i)[a-z][a-z0-9+.-]*://(?:[^\s/@]+@)?[a-z0-9.-]+"
    r"|\b(?:localhost|[a-z0-9-]+\.(?:local|lan|internal|localhost))\b"
    r"|\b(?:hostname|host|endpoint)\s*[:=]\s*[\"']?[a-z0-9_-]+(?:\.[a-z0-9_-]+)+\b"
)


def run_router(script, *args, root=ROOT):
    return subprocess.run([sys.executable, "-I", f"route/{script}.py", *args],
                          cwd=root, capture_output=True, text=True, timeout=30)


def router_copy(root):
    (root / "route").mkdir()
    for name in ("common.py", "compile_nodes.py", "build.py", "route.py", "eval.py", "VENDOR.json"):
        shutil.copyfile(ROOT / "route" / name, root / "route" / name)
    shutil.copytree(ROOT / "route" / "engine", root / "route" / "engine",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (root / "route" / "cards").mkdir()
    (root / "docs").mkdir()
    (root / "docs" / "CONTRACT.md").write_text("### `run_open`\n", encoding="utf-8")
    (root / "lineage").mkdir()


class RouterTests(unittest.TestCase):
    def temporary_root(self):
        directory = tempfile.TemporaryDirectory(prefix=".build-case-", dir=ROOT / "route")
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        router_copy(root)
        return root

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_scratch_rebuilds_are_byte_identical(self):
        build = """\
from pathlib import Path
import runpy
import sys

build = runpy.run_path("route/build.py")
build["verify_vendor"](Path("route").resolve())
build["build_into"](Path(sys.argv[1]))
"""
        with tempfile.TemporaryDirectory(prefix=".build-determinism-", dir=ROOT / "route") as scratch:
            outputs = []
            for name in ("first", "second"):
                destination = Path(scratch) / name
                destination.mkdir()
                result = subprocess.run([sys.executable, "-I", "-c", build, str(destination)],
                                        cwd=ROOT, capture_output=True, text=True, timeout=30)
                self.assert_success(result)
                outputs.append(destination)
            for name in ("nodes", "index"):
                with self.subTest(output=name):
                    trees = []
                    for output in outputs:
                        folder = output / name
                        trees.append({path.relative_to(folder): path.read_bytes() if path.is_file() else None
                                      for path in folder.rglob("*")})
                    self.assertTrue(trees[0])
                    self.assertEqual(*trees)

    def test_source_status_counts_edits_additions_and_deletions_until_rebuilt(self):
        root = self.temporary_root()
        edited = root / "lineage/edited.py"
        removed = root / "lineage/removed.py"
        edited.write_text("value = 1\n", encoding="utf-8")
        removed.touch()
        subprocess.run(["git", "init", "-q", "--template="], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "add", "-f", "--", "docs", "lineage"],
                       cwd=root, check=True, capture_output=True)
        self.assert_success(run_router("build", root=root))

        def assert_status(expected):
            status = run_router("build", "--status", root=root)
            self.assert_success(status)
            self.assertEqual(status.stdout, expected + "\n")
            self.assertEqual(status.stderr, "")

        fresh = "fresh: 0 files changed (0 modified, 0 added, 0 removed)"
        assert_status(fresh)
        edited.write_text("value = 2\n", encoding="utf-8")
        assert_status("stale: 1 files changed (1 modified, 0 added, 0 removed)")
        removed.unlink()
        (root / "lineage/added.py").touch()
        subprocess.run(["git", "add", "-f", "--", "lineage/added.py"],
                       cwd=root, check=True, capture_output=True)
        assert_status("stale: 3 files changed (1 modified, 1 added, 1 removed)")
        self.assert_success(run_router("build", root=root))
        assert_status(fresh)

    def test_stale_query_drops_deleted_paths_and_resolves_anchors(self):
        root = self.temporary_root()
        moved = root / "lineage/moved.py"
        removed = root / "lineage/deleted.py"
        renamed = root / "lineage/renamed.py"
        linked = root / "lineage/linked.py"
        for path in (moved, removed, renamed, linked):
            path.write_text("def lookup():\n    pass\n", encoding="utf-8")
        self.assert_success(run_router("build", root=root))

        def query(expected_warning):
            result = run_router("route", "--q", "lookup", "--json", root=root)
            self.assert_success(result)
            self.assertEqual(result.stderr, expected_warning)
            return {row["path"]: row["anchor"] for row in json.loads(result.stdout)["rows"]}

        self.assertEqual(query(""), {f"lineage/{path.name}": f"lineage/{path.name}:1 lookup"
                                      for path in (moved, removed, renamed, linked)})
        moved.write_text('# lookup moved\npattern = "\\d"\ndef lookup():\n    pass\n', encoding="utf-8")
        removed.unlink()
        renamed.write_text("def other():\n    pass\n", encoding="utf-8")
        linked.unlink()
        linked.symlink_to(moved.name)
        self.assertEqual(
            query("# index stale: 4 files changed; run python3 -I route/build.py\n"),
            {"lineage/moved.py": "lineage/moved.py:3 lookup",
             "lineage/renamed.py": "lineage/renamed.py:? lookup"},
        )

    def test_hand_cards_rank_and_resolve_real_symbols(self):
        for path, (ident, question, symbol) in CARDS.items():
            with self.subTest(path=path):
                card = json.loads((ROOT / f"route/cards/{ident}.card.json").read_bytes())
                raw = (ROOT / path).read_bytes()
                self.assertEqual(card["source_sha256"], hashlib.sha256(raw).hexdigest())
                result = run_router("route", "--q", question, "--k", "3", "--json")
                self.assert_success(result)
                rows = json.loads(result.stdout)["rows"]
                self.assertLessEqual(len(rows), 3)
                row = next((row for row in rows if row["path"] == path), None)
                self.assertIsNotNone(row, rows)
                self.assertEqual(row["id"], ident)
                self.assertIsInstance(row["score"], int)
                self.assertIn(row["q"], [item["q"] for item in card["questions"]])
                target, anchor = row["anchor"].split(" ", 1)
                file_part, line = target.rsplit(":", 1)
                self.assertEqual(file_part, path)
                self.assertEqual(anchor, symbol)
                self.assertRegex(raw.decode().splitlines()[int(line) - 1], rf"^def {symbol}\(")

    def test_missing_card_still_compiles_deterministic_zones(self):
        root = self.temporary_root()
        (root / "lineage/sample.py").write_text(
            '"""Sample module.\n\nMore purpose.\n"""\n'
            'DESCRIPTOR = {"name": "example_tool"}\n'
            'def lookup():\n    return call("run_open")\n'
            'register(DESCRIPTOR, lookup)\n',
            encoding="utf-8",
        )
        result = run_router("build", root=root)
        self.assert_success(result)
        rows = [json.loads(line) for line in (root / "route/nodes/nodes.jsonl").read_bytes().splitlines()]
        node = next(row for row in rows if row["title"].startswith("lineage/sample.py"))
        self.assertEqual(node["title"], "lineage/sample.py - Sample module.")
        self.assertIn("More purpose.", node["purpose"])
        self.assertTrue({"lookup", "run_open", "example_tool"}.issubset(node["search"]["keywords"]))
        self.assertEqual(node["search"]["questions"], [])
        self.assertIn({"a": "L6:lookup", "role": "symbol"}, node["anchors"])
        query = run_router("route", "--q", "example_tool lookup", "--json", root=root)
        self.assert_success(query)
        row = json.loads(query.stdout)["rows"][0]
        self.assertEqual(row["anchor"], "lineage/sample.py:6 lookup")
        self.assertIsNone(row["q"])

    def test_git_inventory_uses_tracked_paths_and_filters_exclusions(self):
        root = self.temporary_root()
        for name in ("lineage/enrolled.py", "lineage/untracked.py", "tests/fixtures/example.py",
                     "ui/dist/bundle.ts", "ui/src/widget.ts", "docs/nested/ignored.md"):
            file = root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("export async function widget() {}\n" if name.endswith(".ts") else "", encoding="utf-8")
        subprocess.run(["git", "init", "-q", "--template="], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "add", "-f", "--", "docs", "lineage/enrolled.py", "tests", "ui"],
                       cwd=root, check=True, capture_output=True)
        result = run_router("build", root=root)
        self.assert_success(result)
        routes = json.loads((root / "route/nodes/routes.json").read_bytes())
        self.assertEqual({row["path"] for row in routes.values()},
                         {"docs/CONTRACT.md", "lineage/enrolled.py", "ui/src/widget.ts"})
        widget = next(row for row in routes.values() if row["path"] == "ui/src/widget.ts")
        self.assertEqual(widget["anchors"], ["L1:widget"])

    def test_stale_cards_are_reported_without_indexing_stale_claims(self):
        root = self.temporary_root()
        path = "lineage/core/journal.py"
        ident = CARDS[path][0]
        source = root / path
        source.parent.mkdir()
        shutil.copyfile(ROOT / path, source)
        card_path = f"route/cards/{ident}.card.json"
        shutil.copyfile(ROOT / card_path, root / card_path)
        self.assert_success(run_router("build", root=root))
        source.write_bytes(source.read_bytes() + b"\n# source revision\n")
        mismatch = run_router("build", "--check", root=root)
        self.assertEqual(mismatch.returncode, 5, mismatch.stdout + mismatch.stderr)
        self.assertIn(f'"path":"{path}"', mismatch.stderr)
        self.assertIn("STALE_CARD", mismatch.stderr)
        result = run_router("build", root=root)
        self.assert_success(result)
        stale = json.loads(result.stdout)["stale_cards"]
        self.assertEqual([(row["id"], row["path"]) for row in stale], [(ident, path)])
        routes = json.loads((root / "route/nodes/routes.json").read_bytes())
        self.assertEqual(routes[ident]["questions"], [])

    def test_vendor_drift_fails_before_executing_engine(self):
        root = self.temporary_root()
        (root / "route/engine/build_index_v2.py").write_text("raise AssertionError\n", encoding="utf-8")
        result = run_router("build", root=root)
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("E_VENDOR", result.stderr)
        self.assertIn("engine/build_index_v2.py", result.stderr)
        self.assertFalse((root / "route/index").exists())

    def test_eval_reads_a_separate_test_bank(self):
        root = self.temporary_root()
        missing = run_router("eval", root=root)
        self.assertEqual(missing.returncode, 4, missing.stdout + missing.stderr)
        self.assertEqual(json.loads(missing.stdout)["status"], "ABSENT")
        self.assert_success(run_router("build", root=root))
        bank = root / "route/eval/test_questions.jsonl"
        bank.parent.mkdir()
        bank.write_text('{"q":"Where is run_open documented?","answer":"docs/CONTRACT.md"}\n', encoding="utf-8")
        result = run_router("eval", root=root)
        self.assert_success(result)
        summary = json.loads(result.stdout)["summary"]
        self.assertEqual((summary["split"], summary["n"], summary["mrr"]), ("TEST", 1, 1))

    def test_public_surface_contains_no_local_paths_or_hostnames(self):
        for path in sorted((ROOT / "route").rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or any(
                part.startswith(".build-") for part in path.relative_to(ROOT / "route").parts
            ):
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(ABSOLUTE_PATH.search(text))
                self.assertIsNone(HOSTNAME.search(text))
