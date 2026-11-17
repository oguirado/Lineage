# U14 fail-first oracle: partial and blocked

This directory is an incomplete oracle, not an acceptance receipt for U14.
The independent discovery assertions run against the existing MCP stdio entry
point. No production stub, alternate journal, substitute validator, payload
alias or replacement domain implementation is supplied.

## Binding sources and gate

The complete `.unit/SPEC.md`, including Amendment B, was read. The on-disk
`docs/CONTRACT.md` and `docs/INTERFACES.md` are K0 targets, not runtime receipts.
M1, M25 and A31 prohibit treating absent dependencies as a failing domain
behavior oracle. Domain integration is therefore **BLOCKED**, not passed.

The existing `lineage/core/journal.py` lacks `snapshot` and `verify`;
`lineage/core/errors.py` lacks `LineageError`; and
`lineage/core/registry.py` lacks `Context`, `Services`, `ToolSpec` and `Registry`.
`lineage/core/app.py` exposes `dispatch(name, args)` without K0's `ctx`.
These observations explain the skipped prerequisite gate. No dependency file
was changed. `CallContext` from the pre-K0 U14 proposal is not an alias for K0
`Context`; selecting an alias would conceal the contract mismatch.

The four independent discovery tests require `ledger_events`, `ledger_export`,
`ledger_verify` and `scorecard_get` in a successful `tools/list` response.
A missing name is an assertion failure about the actual runtime response,
not an import failure. The protocol witness and no-initialization test
independently verify that these probes reach a functioning runtime. CLI
assertions are gated on U04 admission rather than counting its old wrapper
as a U14 behavior failure.

## Amendment disposition

| Binding amendment | Disposition |
|---|---|
| B1, B2, B3, B4 | Unresolved: scorecard shape, cursor filters/bounds/resync, verification shape/witness, export result/effect require an admitted single contract. No conflicting wire expectation was frozen here. |
| B5 | Unresolved: `payload.agent` and `payload.run` conflict with K0 `payload.record`; U12/U13 admission is unavailable. No speculative domain fixture was written. |
| B6 | Unresolved: shared `agent` handling needs admitted U04; caller-asserted identity is not operator authority. |
| B7 | Normalization and descriptor-safe creation of `exports/` are required; hostile path tests remain blocked. |
| B8 | Safe-integer ceiling and aggregate overflow need reconciliation before arithmetic fixtures are admitted. |
| B9 | Duplicate JSON keys, `NaN`, missing LF, doubled slash, symlinked export root and unchanged torn-tail replay remain required, unexecuted controls. |
| B10 | Any later barriers/fault injection must use `unittest.mock` around stdlib I/O, never production hooks. This partial suite introduces no production hooks. |

K0 explicitly defines CLI `tools` as a descriptor array. Its assertion is
retained behind the U04 gate. No ruling was inferred for the unresolved
amendments. In particular, no domain test may turn green through a fallback
payload layout or by replacing null cost with zero.

## Acceptance map

All names below belong to
`tests.ledger.test_interfaces.LedgerDiscoveryOracle`.
`test_a31_admitted_dependencies_gate` is a prerequisite test only. Mapping an
acceptance case to that gate records why its behavioral oracle is **AUSENTE**;
it does not claim that its positive, negative or hostile behavior was tested.

| Acceptance | Test names | Actual coverage / outstanding requirement |
|---|---|---|
| A1 | `test_a1_package_initializers_exist` | Parent/test initializers checked; external read-only file-hash comparison checks write confinement. No implementation diff exists in this copy. |
| A2 | `test_a2_a28_ledger_events_is_discoverable`, `test_a2_a28_ledger_export_is_discoverable`, `test_a2_a28_ledger_verify_is_discoverable`, `test_a2_a28_scorecard_get_is_discoverable` | Discovery assertion-red; full schemas, effects and pre-I/O rejection BLOCKED by U04 and B1-B6. |
| A3 | `test_a31_admitted_dependencies_gate` | BLOCKED: verified journal paging and detached events. |
| A4 | `test_a31_admitted_dependencies_gate` | BLOCKED: empty/missing journal, resync, permission/corruption contrasts; B2-B3 unresolved. |
| A5 | `test_a31_admitted_dependencies_gate` | BLOCKED: filter holes and actor/subject distinction; B2/B6 unresolved. |
| A6 | `test_a31_admitted_dependencies_gate` | BLOCKED: arrival, deadline and backward wall-clock controls. |
| A7 | `test_a31_admitted_dependencies_gate` | BLOCKED: admitted journal lock and independent writer unavailable. |
| A8 | `test_a31_admitted_dependencies_gate` | BLOCKED: strict chain verification and relative diagnostic controls. |
| A9 | `test_a31_admitted_dependencies_gate` | BLOCKED: torn tail and raw-line witness; B3 unresolved. |
| A10 | `test_a31_admitted_dependencies_gate` | BLOCKED: scorecard drift, missing/invalid JSON, duplicate keys, NaN and missing LF. |
| A11 | `test_a31_admitted_dependencies_gate` | BLOCKED: scorecard-only verification scope and unreadable caches. |
| A12 | `test_a31_admitted_dependencies_gate` | BLOCKED: full identity dimensions, versions and retired history; B1/B5 unresolved. |
| A13 | `test_a31_admitted_dependencies_gate` | BLOCKED: close-only telemetry, contradictory closes, no_agent and malformed data; B5 unresolved. |
| A14 | `test_a31_admitted_dependencies_gate` | BLOCKED: independent known/unknown arithmetic; B1/B8 unresolved. |
| A15 | `test_a31_admitted_dependencies_gate` | BLOCKED: numeric hostility, exact totals and finite means; B8 unresolved. |
| A16 | `test_a31_admitted_dependencies_gate` | BLOCKED: telemetry/correctness separation and repeated tasks. |
| A17 | `test_a31_admitted_dependencies_gate` | BLOCKED: canonical detached projection bytes; B1/B5 unresolved. |
| A18 | `test_a31_admitted_dependencies_gate` | BLOCKED: complete export, independent manifest/hash enumeration; B4 unresolved. |
| A19 | `test_a31_admitted_dependencies_gate` | BLOCKED: empty/torn export, missing/corrupt authority. |
| A20 | `test_a31_admitted_dependencies_gate` | BLOCKED: path attacks including doubled/trailing slash and working-directory independence. |
| A21 | `test_a31_admitted_dependencies_gate` | BLOCKED: source/destination symlinks, export-root symlink, special files. |
| A22 | `test_a31_admitted_dependencies_gate` | BLOCKED: deterministic component substitution and cleanup ownership. |
| A23 | `test_a31_admitted_dependencies_gate` | BLOCKED: identical replay, changed source and unchanged torn-tail replay. |
| A24 | `test_a31_admitted_dependencies_gate` | BLOCKED: incomplete/extra content conflicts and no takeover. |
| A25 | `test_a31_admitted_dependencies_gate` | BLOCKED: creation/write/sync/close/publication fault controls. |
| A26 | `test_a31_admitted_dependencies_gate` | BLOCKED: concurrent capture and single-head publication. |
| A27 | `test_a31_admitted_dependencies_gate` | BLOCKED: admitted lock timeout and separate-process contention. |
| A28 | Four `test_a2_a28_*_is_discoverable` tests; `test_a28_discovery_protocol_witness`; `test_a28_a29_cli_tools_is_the_public_descriptor_array` | MCP discovery checked; full dispatch parity, metadata and CLI integration BLOCKED. |
| A29 | `test_a28_a29_cli_tools_is_the_public_descriptor_array` | BLOCKED on U04; delegate success/error grammar and installed entry point are not tested. |
| A30 | `test_a30_discovery_does_not_initialize_runtime_state` | Discovery leaves a fresh temporary home empty; source mutation checks during domain operations BLOCKED. |
| A31 | `test_a31_admitted_dependencies_gate` | Explicit BLOCKED skip for missing admitted U03/U04; payload reconciliation remains unavailable. |
| A32 | `test_a31_admitted_dependencies_gate` | External authored-file review and unchanged-source hash comparison only; campaign publishability gate AUSENTE. Domain diagnostic review remains BLOCKED. |

## Reproduction and evidence limits

Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/ledger -t .
```

Temporary runtime homes are independent of repository fixtures. Tests use
stdlib `unittest`, in-memory protocol streams and temporary directories.
They perform no network requests, real sleeps, process-group operations,
signals, dependency installation or production writes.

The intended fail-first witnesses are missing U14 names in real MCP
`tools/list` responses. Import failures and skipped gates are not counted as
behavior-red evidence. Full A1-A32 coverage and the requested hostile domain
controls remain **AUSENTE** pending prerequisites and the Amendment B ruling.
No host integration, UI capsule, benchmark correctness, reference receipt or
live service receipt is claimed.

## Measured fail-first result

The requested discovery command ran the authored tests: nine tests,
four assertion failures, three passes and two BLOCKED skips [MEASURED].
There were no import errors or other test errors [MEASURED].
The exact unittest summary line was:

```text
FAILED (failures=4, skipped=2)
```

The failures name the missing `ledger_events`, `ledger_export`,
`ledger_verify` and `scorecard_get` descriptors. Neither skipped test is
counted as a behavior failure or acceptance pass.

## Existing-suite and source-integrity checks

The equivalent repository-relative core regression command is:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests/core -t .
```

Its exact final output was [MEASURED]:

```text
Ran 1604 tests in 246.436s

OK
```

A before/after SHA-256 and symlink-target inventory compared every captured
non-oracle file: 346 files unchanged; no additions, removals or content
changes outside `tests/ledger/` [MEASURED]. Dependency sources, `.unit/SPEC.md`,
K0 documents, schemas and pre-existing test/seed bytes were unchanged.
The scan excluded dependency directories and bytecode caches; no assertion
about an unscanned dependency tree is implied. `tests/ledger/__init__.py`
was already present and was not edited.

The final rerun after strengthening prerequisite signature checks still
reported [MEASURED]:

```text
Ran 9 tests in 0.005s

FAILED (failures=4, skipped=2)
```


## Amendments A-U14

A-K0-9 admits the integrated modules as the authority for their own APIs.
The historical results and blocked dispositions above remain historical;
the prerequisite gate now checks the integrated APIs rather than skipping.

1. `_support.py`: run the real public `python -m lineage --home HOME mcp`
   and `tools` entrypoints with binary input and captured output. The installed
   MCP delegate supplies its required integrated `context` and `registry`.
   Each probe uses a fresh interpreter because the earlier strict-JSON suite
   reloads the schema module, otherwise leaving stale exception-class imports
   in already-loaded transport modules during combined execution. This is
   fixture isolation, with no production replacement or import manipulation.
   The subprocess deadline is ten seconds [TARGET]. All protocol, descriptor,
   uniqueness, stream, status and no-source-write assertions remain.
2. `_support.py`: validate the integrated CLI's exact single-key `tools`
   envelope and list value, then return its descriptor array to the existing
   array and discovery assertions. No accepted descriptor values are widened.
3. `test_interfaces.py`: reconcile the prerequisite checks with U03
   `snapshot(home, *, lock_timeout_s)` and
   `verify(home, *, expected_head, lock_timeout_s)`, U04
   `dispatch(name, args, *, context, registry)`, `ToolSpec` fields
   `name, description, input_schema, handler, mutating`, and `app.CallContext`
   fields `home, validators, folds, actor, op_id`. K0 `Context`, `Services`,
   `ctx`, `projections` and `effect` are replaced only in API assertions.
   Required attributes and exact signatures/fields are asserted directly;
   the obsolete missing-K0 skip is removed. No test or behavioral assertion
   was deleted, skipped or relaxed. Domain acceptance coverage remains
   limited to what the recorded executions actually exercise.


### Repair h1 verification

The initial reproduction reached the reported signature errors:
`Ran 9 tests`, `FAILED (errors=6, skipped=2)` [MEASURED]. After the
API and fixture reconciliation above, the requested ledger command
`python3 -m unittest discover -s tests/ledger -t .` and the operator-supplied
full-suite command with `REGRESSION=0` both completed successfully.

The ledger result was `Ran 9 tests`, `OK`, with no skipped cases [MEASURED].
The full-suite result was `Ran 651 tests`, `OK (skipped=3)` [MEASURED].
No production source change was necessary for the reviewed discovery failure.

Eight negative controls were exercised separately [MEASURED]: removing each
required ledger descriptor independently, supplying an array instead of the
CLI envelope, adding an unexpected envelope key, supplying a non-list tools
value, and substituting an incompatible snapshot signature. Every control
triggered an assertion failure; the nominal real CLI/MCP probes passed and
the temporary runtime home stayed empty [MEASURED]. These controls validate
the reconciled assertions; they do not establish the unimplemented portions
of the historical domain acceptance map as tested.
