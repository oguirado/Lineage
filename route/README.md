# Lineage code router

The router finds Lineage source files and symbols for a question. It runs locally with Python 3.12 and the vendored PapersFast engine. Run the commands below from the repository root.

## Build

```sh
python3 -I route/build.py
python3 -I route/build.py --status
python3 -I route/build.py --check
```

The build verifies the four engine files against `route/VENDOR.json` before loading the builder. Vendor drift exits with code 4. Rebuild after an indexed file or card changes and include the generated `route/nodes/` and `route/index/` with the change. For release verification, `--check` rebuilds in scratch, compares both output trees byte for byte, and exits with code 5 on a mismatch. `--status` compares current source paths and SHA-256 hashes against the last build. It reports `fresh` or `stale` with counts of modified, added, and removed source files. Both statuses exit with code 0.

A Git checkout uses tracked paths that still name regular source files in the working tree. A source export without Git metadata uses the same allowlist over the exported files. The allowlist covers Python under `lineage/`, `tools/` and `tests/`, TypeScript under `ui/src/` and `ui/tests/`, CSS directly under `ui/styles/`, Markdown directly under `docs/`, and direct files under `schemas/`. It excludes fixture data directories, caches, dependencies and generated UI output. Git is needed for path discovery in a checkout.

Node IDs are `ln-` plus the first 16 hexadecimal digits of SHA-256 of the UTF-8 repository-relative path. Each node indexes its path, Python module docstring, symbol names and statically visible tool names. Markdown headings also provide search terms and anchors. Optional cards add claims, question phrasing and debugging vocabulary. The build and the byte check report `STALE_CARD` with the path and both hashes when the card describes different source bytes. The file then uses its source-derived terms. To inspect the compiled nodes, run `python3 -I route/compile_nodes.py`. [Card format](cards/PROMPT.md)

## Query

```sh
python3 -I route/route.py --q "Where does transact reject reuse of an op_id?" --k 5
python3 -I route/route.py --q "Where is the run closure memory gate applied?" --k 3 --json
```

Each row includes the node ID, integer score, repository-relative path, best matching `path:line symbol` address, and best card question if available. The address opens line 1 when the query matches no symbol or section name. On a stale index, the query prints one warning to stderr and still ranks the indexed sources. It drops paths that no longer point to source files, resolves moved anchors by name, and emits `path:? symbol` when an anchor cannot be resolved. JSON includes the index ID and the engine's abstention flag. Use a `--k` from 1 through 20.

## Evaluate

```sh
python3 -I route/eval.py --dev
python3 -I route/eval.py
```

DEV uses questions from the indexed cards. Its scores measure retrieval on indexed phrasing. TEST reads `route/eval/test_questions.jsonl` and reports `ABSENT` with exit code 4 when the file is missing. Supply one object per line with a question `q` and an `answer` containing a node ID, a repository-relative path, or a list of either. Keep TEST questions independent of the cards. Evaluation emits JSON with mean reciprocal rank over the top 20, recall at 1 and 5, and per-question matches.

## Limits

Ranking uses lexical evidence. Paraphrases with unrelated vocabulary can miss and weak matches can rank because abstention thresholds are uncalibrated. TypeScript symbols come from a regex over exported declarations and tool discovery is static. Card edges are retained as metadata. New sources and changed ranking terms become searchable after rebuilding.
