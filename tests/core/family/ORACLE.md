# U05 fail-first oracle

Status: **BLOCKED / PARTIAL**, not ADMIT. This seed cannot establish an
integrated U05 oracle. The tests do not install, simulate, or change U03/U04.
There are no SKIP-as-pass paths or missing-import-as-oracle-red paths.

The governing specification is `.unit/SPEC.md`, including Amendment B.
The normative dependencies are `docs/CONTRACT.md`, `docs/INTERFACES.md`,
`schemas/family_envelope.schema.json`, `schemas/family_receipt.schema.json`,
`schemas/tool_error.schema.json`, and `schemas/event.schema.json`.
No specification or schema is modified.

## Dependency and stub boundary

The inspected seed lacks `lineage.core.schema`, the frozen registry dataclasses
including `Context`, `Services`, `ToolSpec`, `Command`, and `EventDraft`,
`LineageError`, and `journal.snapshot`/`journal.transact`/`journal.verify`.
The seed's `app.list_tools`, `app.tool_names`, and `app.dispatch` lack the frozen
keyword-only `ctx` seam. `require_k0` reports these as assertion failures with
`BLOCKED U03/U04 frozen K0 seam`, before constructing any runtime fixture.
This is a prerequisite failure, not evidence of a transport defect.

`lineage/core/envelope.py` and `lineage/core/family.py` already exist. Their
existing behavior and exports are preserved, as required by the assignment.
Consequently this tree contains legacy implementations, not an all-stub U05
surface. The existing operation-id prefix and required-room behavior cannot be
replaced in this oracle flight. Assertions distinguish these mismatches from
stub failures.

Only the previously absent `lineage/core/jsonlane.py` is added as Python stub
code. Its exported `dispatch(envelope, config, *, ctx)` and `main(argv=None)`
bodies raise `NotImplementedError("U05 stub")`. Type-only imports preserve the
specified annotations without fabricating missing runtime dependencies.
`docs/JSON_LANE.md` is a documentation stub. The stdio tests turn the stub
exception into an explicit failed assertion. They do not accept that exception
as successful behavior.

## Acceptance map

Names below are relative to `tests.core.family`. A **partial** row identifies
an actual executable assertion and explicitly lists the acceptance work that
it does not establish. **AUSENTE** means executable coverage is absent; another
test's prerequisite check must not be counted as coverage of that behavior.
Runtime test methods exist but cannot currently execute past the dependency
gate. No row asserts integrated runtime acceptance.

| Acceptance | Executable test names | Coverage and remaining gate |
|---|---|---|
| A1 | `test_envelope.EnvelopeTests.test_a1_validate_filename_is_optional`; `test_mailbox.APIAndDependencyTests.test_a1_mailbox_context_signature`; `test_mailbox.APIAndDependencyTests.test_a1_jsonlane_dispatch_signature` | Partial: exact parameter/default checks. Complete annotated API conformance and host changed-path collection remain required. |
| A2 | `test_envelope.EnvelopeTests.test_a2_capabilities`, `test_a2_call`, `test_a2_cursor_maximum`, `test_a2_exact_raw_byte_cap`, `test_a2_decode_enforces_raw_cap`, `test_a2_defensive_validation`, `test_a2_valid_*` | Positive kinds, raw byte boundary, optional identities, endpoint/actor boundaries and defensive return values. The integrated schema/seam gate remains blocked. |
| A3 | `test_envelope.EnvelopeTests.test_a3_decode_*`, `test_a3_missing_*`, `test_a3_invalid_*`, `test_a3_cursor_*`, `test_a3_after_*`, `test_a3_call_*`, `test_a3_wrong_target`, `test_a3_filename_mismatch`, `test_a3_deep_json_has_protocol_error`; `test_stdio.StdioTests.test_a11_*` | Partial: hostile JSON, closed fields, legacy rejection and malformed framing. Complete no-append/no-handler assertions through both carriers are not established. Exact depth cutoff is unspecified. |
| A4 | `test_configuration.ConfigurationTests.test_a4_*`; `test_confinement.ConfinementTests.test_a4_missing_config_not_manufactured` | Closed configuration, explicit empty grants, endpoint boundary forms and missing-config refusal. Runtime startup cases are dependency-blocked. |
| A5 | `test_dispatch.DispatchTests.test_a5_*` | Executable registry-intersection, empty-grant, source, read/call-grant and unregistered-tool assertions. Dependency-blocked. |
| A6 | `test_mailbox.OwnershipTests.test_a6_direct_mailbox_revocation`; `test_confinement.ConfinementTests.test_a6_live_config_corruption`, `test_a6_live_config_symlink` | Partial: live mailbox admission/configuration changes. Revocation before retained lookup, stdio replay, and restoration of byte-identical retention remain AUSENTE. |
| A7 | `test_envelope.EnvelopeTests.test_a7_known_operation_vector`, `test_a7_known_digest_vector`, `test_a7_canonical_unicode_and_no_lf`, `test_a7_formatting_invariance`, `test_a7_identity_changes_*`, `test_a7_digest_changes_*` | Independent hardcoded vectors and independent standard-library hash calculations; semantic identity/digest distinctions and final-LF exclusion. |
| A8 | `test_dispatch.DispatchTests.test_a8_read_actor_defaults_authority_and_transport`, `test_a8_mutation_identity_and_expected_head`, `test_a8_noncall_run_is_only_correlation`, `test_a8_does_not_modify_callers_envelope`, `test_a8_reject_explicit_*` | Partial: actor/operation injection, authority downgrade, transport and non-call correlation. Matching/mismatching call run-context cases and a level-one write attempt remain AUSENTE. |
| A9 | `test_parity.SharedParityTests.test_a9_read_shared_dispatch_equality`, `test_a9_journal_shared_dispatch_equality`; `test_publication.PublicationTests.test_a9_invalid_backend_result_cannot_be_published` | Partial: exact shared-dispatch equality with original Commit and invalid-result refusal. CLI/stdio/mailbox equality from equal deterministic homes remains AUSENTE. |
| A10 | `test_dispatch.DispatchTests.test_a10_empty_cursor`, `test_a10_after_head_resync`, `test_a10_filtered_cursor_parity`, `test_a10_page_boundaries`, `test_a10_wait_is_not_silently_zeroed`; `test_recovery.JournalDispatchTests.test_a10_unreadable_journal_never_becomes_empty` | Partial: defaults, filter advancement, page boundaries, unreadable journal and preservation of caller wait. A real wait-completion handshake remains AUSENTE; the wait spy is not that evidence. |
| A11 | `test_stdio.StdioTests.test_a11_*` | EOF, exact canonical LF framing, strict identity recovery, duplicate/malformed/multiple-envelope rejection, direct entry and bounded subprocess entry. Successful recipient-owned delivery and domain-failure subprocess exits remain AUSENTE. |
| A12 | `test_mailbox.OwnershipTests.test_a12_empty_sweep_ignores_publication_names` | Partial: ignored temporary/non-request entries and zero consumed count. Lexical deliveries, filename/body mismatch receipts and result-hijacking refusal remain AUSENTE pending the layout decision. |
| A13 | `test_confinement.ConfinementTests.test_a13_*` | Partial: endpoint/config/lock symlinks, hardlinked config, FIFO control-file refusal before open, and untrusted-writable endpoint directories. Request/retention/result unsafe-object matrix and foreign ownership remain AUSENTE. |
| A14 | `test_publication.PublicationTests.test_a14_replaced_result_destination_is_not_followed`, `test_a14_destination_swap_at_file_fsync` | Partial: unsafe result destination and a deterministic replacement at a real durability barrier. Checked-request and directory/config replacement races remain AUSENTE. |
| A15 | `test_mailbox.OwnershipTests.test_a15_second_owner_refused`, `test_a15_stale_looking_lock_never_taken`, `test_a15_independent_process_owner_refused`, `test_a15_abrupt_exit_requires_explicit_test_lock_recovery` | Partial: independent ownership handshake, stale contents/timestamp refusal and explicit recovery after abrupt exit. The stdio contender is not covered. |
| A16 | `test_mailbox.OwnershipTests.test_a16_normal_release_removes_owned_lock`, `test_a16_replacement_lock_survives_release`; `test_a15_independent_process_owner_refused` | Partial: normal and controlled child release, replacement-lock preservation/reporting. Startup-failure cleanup and descriptor-count verification remain AUSENTE. |
| A17 | `test_recovery.JournalDispatchTests.test_a17_mutation_requires_real_journal_witness`; `test_dispatch.DispatchTests.test_a8_mutation_identity_and_expected_head` | Partial: real U03 transaction and returned-prefix witness verification. Pending/commit/complete/result/request-removal ordering through consume remains AUSENTE. A fake dispatcher is never accepted as a mutation witness. |
| A18 | `test_recovery.JournalDispatchTests.test_a18_original_expected_head_replays_after_head_advances`; `test_envelope.EnvelopeTests.test_a7_formatting_invariance` | Partial: original Commit/result reconstruction after unrelated events and original expected_head replay. Carrier retention, deleted result publication and changed projection files remain AUSENTE. |
| A19 | `test_envelope.EnvelopeTests.test_a7_identity_changes_*`, `test_a7_digest_changes_*` | Primitives only. Executable retained-collision/refusal/unchanged-retention coverage is AUSENTE. These hash tests are not a substitute for A19. |
| A20 | `test_mailbox.OwnershipTests.test_a15_abrupt_exit_requires_explicit_test_lock_recovery` | Lock-recovery prerequisite only. Pending/commit/complete/result crash matrix and projection-callback failure are AUSENTE. |
| A21 | `test_publication.PublicationTests.test_a21_file_fsync_failure_allows_publication_retry`, `test_a21_rename_failure_allows_publication_retry` | Partial: actual OS file-fsync and atomic-rename faults with valid retry. Pending-state, temporary-write, directory-fsync, cleanup and no-duplicate-journal matrix remain AUSENTE. |
| A22 | `test_recovery.JournalDispatchTests.test_a22_corrupt_journal_blocks_success`; `test_confinement.ConfinementTests.test_a6_live_config_corruption`, `test_a6_live_config_symlink` | Partial: corrupt journal and live unsafe/corrupt config. Corrupt retention/forged completion matrix is AUSENTE; unreadable is never simulated as empty. |
| A23 | `test_publication.PublicationTests.test_a23_publish_canonical_receipt`, `test_a23_no_envelope_does_not_synthesize_correlation`, `test_a23_file_fsync_rename_directory_fsync` | Partial: real OS durability ordering and visibility inspections of final result names. Independent-reader barriers and pending/complete/request cleanup instrumentation remain AUSENTE. |
| A24 | `test_dispatch.DispatchTests.test_a24_validator_refusal_is_transactional`; `test_recovery.JournalDispatchTests.test_a24_stale_revision_appends_nothing`, `test_a24_validator_memory_required_appends_nothing` | Partial: real U03 validator/prepare refusal paths and stale revision. Both-carrier policy matrix and successful task-close null-cost result remain AUSENTE. No real U13 close gate is claimed. |
| A25 | `test_dispatch.DispatchTests.test_a25_error_*`, `test_a25_unexpected_exception_is_sanitized`, `test_a25_malformed_backend_*` | Partial: fixed vocabulary, bounded closed errors, sanitization and malformed backend success. Per-tool error-policy matrix, all process exits and successful failed-task close are not established. |
| A26 | `test_dispatch.DispatchTests.test_a26_external_timeout_reuses_identity_without_journal` | Partial: offline schema-valid launched acknowledgement, repeated deterministic identity and absent journal witness. Pending external transport recovery remains AUSENTE. No live external process is launched. |
| A27 | AUSENTE | Compound recovery requires the missing U03/U04 seam and the unresolved Amendment B child-operation witness rule. No invented root event or child-id formula is tested. |
| A28 | AUSENTE | Cross-carrier retention and simultaneous stdio/mailbox collision behavior require the layout and direct-helper ownership decisions. |
| A29 | `test_dispatch.DispatchTests.test_a26_external_timeout_reuses_identity_without_journal` | Retry identity only. Pending-state transient errors and cached deterministic refusal versus fresh-id evaluation remain AUSENTE. |
| A30 | AUSENTE | Poll default/boundaries, public CLI delegation and drain lifecycle are not covered. Existing legacy main requires a positional command and has incompatible dependency construction; no compatibility fallback is added. |
| A31 | `test_parity.PublicGuideTests.test_a31_executable_wire_and_config_examples`, `test_a31_public_carrier_commands`, `test_a31_no_host_coordinates`, `test_a31_topic_*` | Partial: public JSON/config example extraction/validation, public command spelling, guide topics and host-coordinate absence. Executing all guide journeys in an integrated runtime remains AUSENTE. |
| A32 | `test_mailbox.APIAndDependencyTests.test_a32_dependency_gate`; `RuntimeCase.setUp` | Executable fail-closed dependency diagnostic, with no skipped prerequisite or fabricated replacement. Frozen-source integrity and test outcomes are host checks. Integrated-green evidence is absent. |
| A33 | AUSENTE | Baseline is red. Neither isolated retained-digest mutant nor pre-replay-authorization mutant has a valid green baseline. No mutation receipt or cross-family ADMIT is claimed. |

Wildcard names denote the concrete methods generated at test-module load; they
are separate discovered unittest cases, not subtests. Only test discovery
attaches those methods. Package import does not create files, launch workers,
register tools, or run tests.

## Amendment B decisions and deliberately unfrozen details

| Item | Treatment |
|---|---|
| B1 layout | No subdirectory assignment is invented. Tests of `publish` find the unique public result basename below the endpoint; they do not prescribe which member contains it. Consume/recovery fixtures are blocked until the public mapping is supplied. `publish` uses the request id, and absent envelope correlation is omitted under the existing no-synthesis rule. |
| B2 helper ownership | Direct helper tests assert admission/results without prescribing whether the helper acquires retention ownership. Independent `Mailbox` ownership is tested. Stdio contention remains an untested required refusal, not an optional pass. |
| B3 read retention/transient handling | No cached-read or drain retry policy is assumed. Different cursor requests use different ids, so either permitted helper ownership design can satisfy the primitive tests. The external fixture checks deterministic identity only, not retained completion. |
| B4 filename safety | Required basename-owned refusal and non-Id quarantine remain acceptance gaps, explicitly recorded in A12. No fallback to a body id or `invalid0` filename is introduced. |
| B5 effects/children | Fixture `ToolSpec.effect` is explicitly read/journal/external. Ordinary mutations use real `journal.transact`; no guessed compound child identity, private lookup API or root event is added. |
| B6 authority | Supplied operator context is intentional: successful ordinary dispatch must expose tool authority and json transport to the handler. The fixture cannot turn actor text into authority. |
| B6 depth/integers | Strict decode tests cover both unsafe integer signs and require that deep input never leaks RecursionError. The test accepts either a valid decoded object or InvalidEnvelope at the unfrozen depth; it does not pretend that a particular cutoff was specified. |
| B6 filesystem scope | Fixtures operate beneath the temporary services.home. They do not reject OS ancestors or prescribe how those ancestors are normalized. Group/world-writable endpoint directories have explicit negative cases. |
| B7 replay/live config | Original expected_head replay after head advancement and live config corruption/symlinking have executable cases. They are dependency-blocked; they are not reported as passing. |

## Fixture and process safety

All fixtures are inline in these test modules. Runtime extension code and homes
are disposable temporary files. Input schemas for the local extension are
copied in memory from the frozen family schema and merged with the frozen
actor/operation schemas, rather than invented tool argument shapes.
The extension uses frozen public tool names and real U03 transaction/render
callbacks. Its refusal fixture does not implement production run policy.

There is no dependency installation, network access, model invocation, external
application interaction, broad signal, or process-group operation. A child
consumer is started by multiprocessing with a pipe handshake. Cleanup signals
only that exact started process after verifying its pid is greater than one.
No process-group test is present, so no unshare exception is exercised.
The abrupt-exit child exits itself; the harness proves lock refusal before
removing the exact test-owned lock. Subprocess entry tests have a bounded
timeout. Wait forwarding uses an immediate spy instead of a wall-clock wait.

All mandates and all coverage claims are confined to the supplied Lineage
corpus, frozen K0 seed and this unit's exclusive write surface.

## Frozen Python oracle bytes

These hashes freeze test source bytes before author integration. They are not
a runtime acceptance receipt. ORACLE.md is excluded from its own manifest.

| File | SHA-256 |
|---|---|
| `__init__.py` | `19586244c389d110eb7c1be52e3cc6c88498b92ab347ca058e6fbabab955cdba` |
| `test_configuration.py` | `a9f915c4d98e459a3209a2e7077fb318a62e4ada0b459cce4ab43ecd8aa4b469` |
| `test_confinement.py` | `f9e4ac3e6e65906c88f3b3e5a9de4920fca300ba02b361c68e11887c01cc6d58` |
| `test_dispatch.py` | `ffbd6ad66d73c51a8b34411834f54c8d92dd101bec45ef0db40098fa48189316` |
| `test_envelope.py` | `fde7ccdbb4e2749f800baac4dda0c75e5af0cd24f24fda15df5b49e7d0011b08` |
| `test_mailbox.py` | `b197c5644c4aa7f8d83e74446442f62372e082b2007739af11b9dd55973154c3` |
| `test_parity.py` | `edddf371c1d0aaadb265c7797d0b4229d2ed17258d46564e3c714bbc0ef54f11` |
| `test_publication.py` | `23068b6cd34a2639d0634b1ee89a10434961735979afc7f537c1f6d723bb630b` |
| `test_recovery.py` | `b99871a52bfd137b028341c99a772e30e892b0b7963912d7977b25f2ba0bc475` |
| `test_stdio.py` | `70975df2c560c2731f8682c13324fcfe1fcaee879d829e0bcbf98654a8c4b3ce` |

## Amendments A-U05

A-K0-9 makes the integrated dependency APIs authoritative. These reconciliation
changes retain every test and behavioural assertion. The original frozen hash
manifest above remains historical; the manifest below pins the reconciled source.

- `__init__.py`, `require_k0`: check `schema.validate`/`strict_loads`,
  `errors.JSONValue`, `registry.Registry`/`ToolSpec`/`load`, `app.CallContext`/
  `create_context`/`DispatchResult`/`list_tools`/`dispatch`, and the actual journal
  signatures. Absent documented aliases are no longer prerequisites.
- `RuntimeCase.setUp`: set a temporary private fixture umask so valid runtime
  controls are safe on hosts with permissive invoking masks; hostile permissions
  remain explicit negative fixtures. Use keyword `load(package=...)`, `CallContext` home,
  validator/fold services and the existing private lane runtime registry seam.
  Preserve an intentionally operator-authority input context to test downgrading.
- `RuntimeCase.assert_receipt`, `_validate_schema`: replace absent `SchemaStore`
  with an independent fixture resolver for frozen references/composition and the
  integrated structural validator. Receipt shape validation remains required.
- `RuntimeCase.assert_witness`: use verified tuple snapshots by home and
  `verify(...)["ok"]`; retain actor, operation, commit, hash and event assertions.
- Inline extension: handlers take keyword-only `context`, descriptors use
  `mutating`, and validators take history/event. Replace absent Command/EventDraft
  and render callbacks with actual keyword journal transactions and event-based
  rendering. Fixture `expected_head` and memory refusal run inside locked prepare;
  replay remains journal-owned. Deterministic ids/clock move into the fixture.
- Inline cursor fixture: absent `journal.read` is replaced by a local registered
  read handler over real verified snapshots, preserving filters, scanned cursor,
  resync, limit and wait. The wait-forwarding spy targets this fixture seam.
- `test_dispatch.py`: descriptor calls pass `registry`; direct dispatch passes
  `context`/`registry` and compares `DispatchResult.payload`; snapshot assertions
  inspect tuples. Service-identity assertions now check each actual context
  service (home, validators and folds), preserving identity checks.
- `test_parity.py`: direct application calls pass actual context/registry and
  unwrap only `DispatchResult.payload`; journal assertions inspect tuples.
- `test_recovery.py`: snapshots use home and tuple history; head comes from the
  last verified event. All rejection, replay and no-append assertions remain.

- `WireCase.validate_request`: call validation directly so negative tests receive
  the original `InvalidEnvelope` instead of the positive-only helper's assertion.
  Existing `assertRaises(InvalidEnvelope)` statements are unchanged.
- `_registry_schema` and inline handler argument plumbing: adapt U04's supported
  structural-schema subset. Nullable branches become equivalent union types;
  recursive references retain full frozen validation in the fixture handler.
  This changes descriptor representation without changing accepted input values.

The fixed operation-id vector expects a longer digest prefix than the specified
formula and the other independent identity fixture. It is left unchanged; changing
that assertion is outside import/signature/fixture API reconciliation.

### Reconciled oracle source manifest

| File | SHA-256 |
|---|---|



## Amendments A-U05 (orchestrator)
- operation_id vector corrected to lin- + 44 hex (K0 CONTRACT, SPEC_U05).
- Frozen python hash table regenerated after the reconciliation (A-U05 h1 diff) and the vector correction.
