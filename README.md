# Lineage

Lineage is a local, auditable laboratory for AI agents: create agents with an identity and a constitution, give them
evidence-backed memory, measure them on runs and benchmarks, breed them (inheritance, clone, distill, cross, single-change
mutation, language specialization), and promote or retire them only on evidence. Every change is an event in an
append-only, hash-chained ledger that can be verified independently of the writer.

Status: early preview. The backend and its contract are implemented and tested; the guided quickstart and the end-to-end
demo are still being written.

## Requirements

- Python 3 (tested with 3.12). The backend uses only the standard library: no `pip install`.
- The web UI ships prebuilt in `ui/dist/`.

## Interfaces

All interfaces go through one registry of 38 tools whose input schemas are frozen in `docs/CONTRACT.md`:

| Interface | Entry point | Docs |
|---|---|---|
| CLI | `python3 -m lineage --home HOME tools`, `call TOOL --json '{...}' [--dry-run]` | `docs/HEADLESS.md` |
| MCP (stdio) | `python3 -m lineage --home HOME mcp`; `mcp-config --client claude\|codex\|generic` | `docs/MCP.md` |
| JSON lane (file mailbox) | `json`, `drain --endpoint NAME` | `docs/JSON_LANE.md` |
| HTTP + web UI (loopback) | `python3 -m lineage --home HOME serve` | `docs/OPERABILITY.md` |
| Harness capture | `run --agent ID ... -- CMD`, `hook` (Claude Code hooks), `snapshot` | `docs/HARNESS_HOOKS.md` |
| OpenFresnel bridge | `openfresnel_*` tools | `docs/OPENFRESNEL.md` |

Every tool carries a risk class (for example `read`, `prepare`, `send`, `publish`, `irreversible`) exposed as MCP annotations.
`python3 -m lineage --home HOME doctor [--json | --operable]` checks a home and runs the operability self-test.

## Tests

```sh
python3 -m unittest discover -s tests -t .
```

## License

GNU Affero General Public License v3.0 (see `LICENSE`). Lineage's core is derived from TaskLight (AGPL-3.0); the
module renaming is documented in `NOTICE.md`.
