# U12 fail-first oracle

All paths below are repository-relative. This document is an oracle definition,
not an ADMIT receipt. No source or frozen schema is changed.

## Execution and interpretation

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/agents -t .
```

The suite contains 99 test methods [MEASURED: AST inventory]. Each invokes a
required U12 callable. `NotImplementedError("U12 stub")` is converted into an
assertion failure, including across U03 callback exception sanitization.
Unexpected import errors and missing attributes are never the intended witness.
No requirement uses unittest skip or expectedFailure. Each test has a bound
below 5 seconds [TARGET]; owned subprocess calls have explicit timeouts.
Tests use stdlib unittest, disposable homes beneath this test package, fixed
clock/id generators, no network, no sleeps and no process-group operations.
Only the byte-vector subprocess uses an owned child; no signal APIs are used.

`BLOCKED/HOLD` means integrated acceptance is unavailable, including when a
unit-level refusal assertion eventually passes. It is never an accepted empty
result or a zero measurement. Fixture append helpers deliberately use an
accepting U03 validator to establish committed-prefix data. They do not prove
reference, memory, run-close, breeding or promotion admission. Actual U12
validator tests use the registered callback under the real U03 lock. Skill
fixtures contain canonical package bytes with independently calculated hashes.
When U07 exists, creation fixtures obtain its real bundled pin descriptors;
otherwise synthetic pins exercise explicit fail-closed/stub behavior only.
Real U07-U11, U13/promotion and drift integration receipts are AUSENTE.

## Acceptance map

Each row explicitly identifies executable test methods and the remaining
integrated gate. A method passing a refusal does not admit a blocked positive.

| Case | Test names | Scope / gate |
|---|---|---|
| A1 | `test_extension.ExtensionTests.test_a01_registry_inventory_exact_schemas_and_callback_ownership`<br>`test_extension.ExtensionTests.test_a01_exact_domain_signatures_and_amended_rule_ids` | Actual U04 registry/schema/signature assertions; runtime remains red. |
| A2 | `test_genesis.GenesisTests.test_a02_complete_genesis_and_independent_chain` | Published canonical skill source fixture plus real U03 chain; integrated genesis HOLD: U07/U08/U09/U11 absent. |
| A3 | `test_validation.ValidationTests.test_a03_reference_membership_is_exact_by_id` | Exact membership by reference id and no append. |
| A4 | `test_validation.ValidationTests.test_a04_stale_foundation_pin_is_hash_mismatch`<br>`test_validation.ValidationTests.test_a04_reference_verification_cannot_be_cached` | Stale-pin case and uncached public verification-seam refusal. Real bundled-file mutation HOLD: U07 absent. |
| A5 | `test_genesis.GenesisTests.test_a05_no_bootstrap_reference_events_or_read_side_effect` | No reference.pinned bootstrap event, including read purity; integrated genesis HOLD. |
| A6 | `test_validation.ValidationTests.test_a06_unknown_skill_is_bad_args`<br>`test_validation.ValidationTests.test_a06_explicit_skill_hash_mismatch_is_preserved` | Unknown-skill distinction and exact-hash public dependency refusal; integrated package-tamper witness HOLD. |
| A7 | `test_genesis.GenesisTests.test_a07_historical_pin_resolution_and_caller_order_preserved` | Canonical package source fixtures, permutation invariance, real historical U09 resolution/retirement when available; HOLD. |
| A8 | `test_validation.ValidationTests.test_a08_reserved_path_unicode_and_non_full_match_ids`<br>`test_validation.ValidationTests.test_a08_closed_complete_unique_seats`<br>`test_validation.ValidationTests.test_a08_unknown_authority_and_record_fields_are_closed`<br>`test_validation.ValidationTests.test_a08_duplicate_keys_invalid_utf8_and_nonfinite_wire`<br>`test_validation.ValidationTests.test_a08_text_and_collection_bounds_and_closed_pins` | Direct and real carrier validation, reserved ids, closed nested data, duplicate keys/Unicode/nonfinite values. |
| A9 | `test_validation.ValidationTests.test_a09_unknown_conflicting_and_expanding_overlays`<br>`test_validation.ValidationTests.test_a09_missing_compiler_is_internal_and_atomic` | Unknown overlay, exact compiler refusal propagation, absent-compiler atomic refusal; integrated overlays HOLD. |
| A10 | `test_genesis.GenesisTests.test_a10_full_seats_survive_get_and_list_without_fitness` | Complete Seat distinctions without promoted_seat/fitness; integrated genesis HOLD. |
| A11 | `test_fold.FoldTests.test_a11_selected_seat_integration_has_no_invented_u12_entrypoint` | Reassigned to real U13 run_open integration; all three Seat fields tested. U13 absent: HOLD. |
| A12 | `test_fold.FoldTests.test_a12_direct_append_forged_birth_fields`<br>`test_fold.FoldTests.test_a12_wrong_rule_ids_injected_inheritance_and_source_bytes`<br>`test_fold.FoldTests.test_a12_self_consistent_but_uncompiled_constitution_is_rejected` | Direct registered validator through U03; tampered facts, source/citations and self-consistent uncompiled text. |
| A13 | `test_replay.ReplayTests.test_a13_exact_retry_returns_original_prefix_after_later_activity` | Original result/Commit after later committed memory fixture; integrated genesis HOLD. |
| A14 | `test_replay.ReplayTests.test_a14_changed_effective_content_is_bad_op`<br>`test_replay.ReplayTests.test_a14_tool_identity_binds_request_digest`<br>`test_replay.ReplayTests.test_a14_expected_head_change_does_not_defeat_replay` | Tool/effective-content identity, exact-replay precedence over expected_head. |
| A15 | `test_replay.ReplayTests.test_a15_duplicate_id_distinct_operations_conflict_even_retired` | Distinct operation and existing/retired identity conflicts. |
| A16 | `test_replay.ReplayTests.test_a16_real_journal_concurrent_duplicate_identity` | Two synchronized threads use real U03 locking; bounded Barrier/Queue, no sleeps. |
| A17 | `test_replay.ReplayTests.test_a17_stale_expected_head_is_atomic`<br>`test_replay.ReplayTests.test_a17_real_held_ledger_lock_is_busy` | Real held flock and stale revision; no projection effects. |
| A18 | `test_version.VersionTests.test_a18_independent_digest_pin_permutations_and_no_mutation`<br>`test_version.VersionTests.test_a18_pure_no_filesystem_or_network` | Independent json/hashlib vector, all pin permutations, pure computation. |
| A19 | `test_version.VersionTests.test_a19_each_version_input_changes_identity`<br>`test_version.VersionTests.test_a19_metadata_is_excluded`<br>`test_version.VersionTests.test_a19_invalid_memory_generation_native_and_safe_integer`<br>`test_version.VersionTests.test_a19_closed_hash_and_skill_pins` | Each version input, excluded metadata, closed pins, native safe integers. |
| A20 | `test_fold.FoldTests.test_a20_agents_fold_owns_only_agents_and_never_mutates_event`<br>`test_fold.FoldTests.test_a20_memory_generation_refresh_and_replay` | Owned namespace; real U10 admitted lesson/replay/supersession once available. U10 absent: HOLD. |
| A21 | `test_fold.FoldTests.test_a21_non_brief_changes_do_not_change_version_or_bytes` | Committed-prefix fixtures isolate brief-ineligible memory invariance; U10/U11 integrated generation witness HOLD. |
| A22 | `test_fold.FoldTests.test_a22_effective_retirement_requires_real_promotion_peer` | Real promotion extension required; closed-run fixtures probe consecutive-failure fold without assuming its namespace shape. Promotion contract absent: HOLD. |
| A23 | `test_fold.FoldTests.test_a23_unproven_status_is_refused`<br>`test_fold.FoldTests.test_a23_non_genesis_and_fabricated_parent_are_refused` | Missing pure breeding/promotion policy never authorizes direct status/birth. |
| A24 | `test_queries.QueryTests.test_a24_verified_empty_ledger_exact_page`<br>`test_queries.QueryTests.test_a24_missing_get_and_brief_are_no_agent`<br>`test_queries.QueryTests.test_a24_corrupt_journal_is_not_empty`<br>`test_queries.QueryTests.test_a24_unreadable_journal_is_not_empty` | Established empty prefix vs absent target, corruption and unreadability. |
| A25 | `test_queries.QueryTests.test_a25_lexical_pages_and_snapshot_head`<br>`test_queries.QueryTests.test_a25_conjunctive_filters_absent_cursor_and_empty_final_page` | Lexical pages, conjunction, absent valid cursor, head, terminal empty page. |
| A26 | `test_extension.ExtensionTests.test_a26_operator_read_actor_does_not_mutate_or_gain_authority`<br>`test_queries.QueryTests.test_a26_retirement_default_include_and_explicit_override`<br>`test_queries.QueryTests.test_a26_invalid_limits_filters_and_cursor`<br>`test_queries.QueryTests.test_a26_unknown_filter_is_closed_at_tool_boundary`<br>`test_validation.ValidationTests.test_a26_invalid_read_actors_and_malformed_after`<br>`test_validation.ValidationTests.test_a26_operator_actor_grants_no_domain_authority` | Retirement default/override, limits, actors/cursors/extra filters and operator non-escalation. |
| A27 | `test_queries.QueryTests.test_a27_get_list_and_create_nested_results_are_detached`<br>`test_queries.QueryTests.test_a27_create_result_nested_aliases_do_not_leak` | Deep returned seats/pins/lists and creation value never alias authority. |
| A28 | `test_brief.BriefTests.test_a28_exact_frozen_utf8_vector_and_section_order`<br>`test_brief.BriefTests.test_a28_empty_sections_and_rule_order`<br>`test_brief.BriefTests.test_a28_fresh_interpreter_matches_exact_bytes`<br>`test_brief.BriefTests.test_a28_pure_and_excludes_metadata_and_own_hash` | Frozen exact byte vector, final LF, sections/empty markers, permutation/fresh interpreter/purity. |
| A29 | `test_brief.BriefTests.test_a29_full_kind_level_status_privacy_scope_matrix`<br>`test_brief.BriefTests.test_a29_owner_candidate_workflow_is_eligible` | Complete eligibility cross-product and unpromoted owner workflow. |
| A30 | `test_brief.BriefTests.test_a30_none_own_inherited_arms_preserve_provenance`<br>`test_brief.BriefTests.test_a30_query_hash_is_requested_arm_and_projection_stays_own` | Valid child-shaped pure input; all arms and provenance. Integrated inherited birth/query/materialized arm witness HOLD. |
| A31 | `test_brief.BriefTests.test_a31_tampered_mutable_brief_is_neither_trusted_nor_repaired` | Mutable brief is neither authoritative nor repaired by reads. Separate verifier drift assertion: A38. |
| A32 | `test_brief.BriefTests.test_a32_immutable_sources_reverified_after_prior_query` | Post-success immutable verification refusal through U07/U09 public seams; real source-file mutation HOLD. |
| A33 | `test_genesis.GenesisTests.test_a33_no_tokenizer_is_not_memory_debt`<br>`test_genesis.GenesisTests.test_a33_exact_multibyte_static_entry_overflow_is_atomic` | Missing tokenizer never blocks. U11 entry error propagates atomically; multibyte byte/character contrast. Integrated budget witness HOLD. |
| A34 | `test_brief.BriefTests.test_a34_overlong_brief_refuses_without_truncation`<br>`test_brief.BriefTests.test_a34_overlong_query_is_internal_and_read_pure`<br>`test_genesis.GenesisTests.test_a34_oversize_candidate_brief_fails_before_append` | Frozen internal overflow refusal in pure build/query/precommit candidate; no truncation. |
| A35 | `test_materialization.MaterializationTests.test_a35_exact_layout_files_and_rebuild_bytes`<br>`test_materialization.MaterializationTests.test_a35_memory_projection_owned_by_u11` | Exact relative layout/content/rebuild and U11-owned generations; U11 absent: HOLD. |
| A36 | `test_materialization.MaterializationTests.test_a36_unsafe_language_hash_component_and_exact_wire_value`<br>`test_materialization.MaterializationTests.test_a36_symlinked_parent_component_is_refused`<br>`test_materialization.MaterializationTests.test_a36_symlinked_agent_and_individual_destination_are_refused`<br>`test_materialization.MaterializationTests.test_a36_destination_swap_before_publication_cannot_escape`<br>`test_materialization.MaterializationTests.test_a36_adversarial_swap_at_write_or_publication_is_refused` | Deterministic language mapping, symlink components/destinations, replacement before publication. A deterministic adversarial interleaving swaps the directory at file write/atomic publication; an unexercised interception cannot pass. |
| A37 | `test_materialization.MaterializationTests.test_a37_postcommit_publication_failure_preserves_birth_and_exact_retry`<br>`test_materialization.MaterializationTests.test_a37_replay_recovery_keeps_current_projection`<br>`test_materialization.MaterializationTests.test_a37_stale_snapshot_cannot_replace_a_newer_projection` | Durable failed publication, original logical replay, current projection and stale-snapshot guard. |
| A38 | `test_materialization.MaterializationTests.test_a38_integrated_verifier_must_report_agent_and_scorecard_drift`<br>`test_queries.QueryTests.test_a38_tampered_agent_and_scorecard_are_not_authority` | Logical authority tamper plus integrated drift assertion. Existing U03 verify has no projection wiring: HOLD. |
| A39 | `test_materialization.MaterializationTests.test_a39_missing_agent_projection_is_not_clean_verification`<br>`test_materialization.MaterializationTests.test_a39_missing_memory_projection_is_reported_by_owner` | Missing agent and owner memory files, clean-read distinction, rebuild/generation stability. U03/U11 integration HOLD. |
| A40 | `test_brief.BriefTests.test_a40_instruction_like_memory_is_passive`<br>`test_genesis.GenesisTests.test_a40_display_payload_is_passive_and_publishable`<br>`test_validation.ValidationTests.test_a40_control_and_blank_text_is_rejected` | Passive metacharacters/path-shaped text and rejected control/blank display/language/overlay text. |
| A41 | `test_extension.ExtensionTests.test_a41_dispatch_cli_and_mcp_query_data_match`<br>`test_extension.ExtensionTests.test_a41_descriptor_discovery_matches_actual_cli_and_mcp`<br>`test_extension.ExtensionTests.test_a41_json_lane_parity_requires_real_adapter` | Real U04/CLI/MCP data/discovery; real JSON lane once integrated. JSON absent; HTTP wire parity unexecuted under the no-network mandate: HOLD. |
| A42 | `test_queries.QueryTests.test_a42_success_and_failure_reads_change_no_files`<br>`test_queries.QueryTests.test_a42_missing_home_reads_do_not_create_runtime` | Exact inventory/ledger equality for successful/failed reads and missing home. |
| A43 | `test_extension.ExtensionTests.test_a43_dependency_error_is_fixed_bounded_and_sanitized` | Fixed bounded sanitized failure via real U04 and injected public I/O seam. |
| A44 | `test_brief.BriefTests.test_a44_missing_pure_rule_id_input_is_explicit`<br>`test_extension.ExtensionTests.test_a44_missing_compiler_refuses_without_birth`<br>`test_extension.ExtensionTests.test_a44_journal_owned_binding_uses_allocated_id`<br>`test_extension.ExtensionTests.test_a44_missing_journal_id_binding_fails_before_append`<br>`test_fold.FoldTests.test_a44_negative_oracle_rejects_removed_admission_validator` | Compiler, birth-id and rule-id omission controls; admission-disabled mutant must make the same rejection oracle fail. Status/verifier gate witnesses in A11/A38. Missing peers remain HOLD. |

## Binding Amendment B resolutions

The pure seam is `brief.build(agent, units, *, rule_ids: Sequence[str],
memory_arm="own")`. Rule ids are explicit verified input, never an extra Agent
wire key or a hidden lookup. The exact UTF-8/LF template is below; angle-bracket
values are substituted as specified, and every line, including the last, has LF.
No blank lines are inserted.

```text
# Agent brief
## Identity
agent_id: <canonical JSON string>
workflow: <canonical JSON string>
language: <canonical JSON string>
version_inputs: <canonical JSON object>
## Constitution
sha256: <constitution_sha256>
rule_ids:
- <canonical JSON string>
## Skills
- <canonical SkillPin JSON>
## Memory
- <canonical eligible MemoryUnit JSON>
```

`version_inputs` contains only constitution_sha256, skills and memory_gen;
canonical keys sort as K0 specifies. Rule ids sort lexically, skills by
(skill_id, sha256), and memory by (kind, id). Each empty section body is the
single literal line `(none)`; this includes rule_ids. Memory is selected before
rendering. JSON escaping preserves passive multiline memory text without
creating Markdown headings. Metadata, status, projection head and the brief's
own hash are excluded. The independent expected vector is in the package
initializer and is compared with actual exact bytes and a fresh interpreter.

The exact agent projection layout is
`agents/<language_component>/<agent_id>/{agent.json,CONSTITUTION.md,BRIEF_HEAD.md}`.
Safe ASCII language components remain exact; all other wire languages map to
`lang-` plus SHA-256 of their UTF-8 bytes. `agent.json` is compact canonical JSON
without a final LF; text files retain their specified exact LF bytes. U11 keeps
ownership of memory-generation files and U14 of scorecards. This oracle does
not invent their subpaths or a promotion namespace read structure.

Direct births require exact compiler-byte equality as well as digest,
authority and source-resolvable citation checks. Selected-seat membership is
assigned to U13/U16 integration, with no new U12 helper. Replay repair must
preserve current projection bytes even while returning the original logical
result; no particular lock implementation is mandated. Display names,
languages and overlay ids reject LF, CR, NUL and whitespace-only values with
bad_args. Brief result overflow is internal, in both create and brief queries;
a genuine U11 static-entry overflow remains memory_debt. Token counting is
not measured and no tokenizer is injected.

## A-K0-9 integrated API deviations

| Integrated owner | Actual API used by these tests |
|---|---|
| U04 registry | ToolSpec uses mutating, not effect; handler(args, *, context); validators(history, event); folds are callable mappings, not FoldSpec/order objects. Registry.load is keyword-only package discovery. |
| Shared context/types | CallContext(home, validators, folds, actor, op_id) and app.create_context replace documented Context/Services. Shared Command/Snapshot/Committed/FoldSpec classes are AUSENTE; only a test-owned immutable Command value fixture is supplied. Snapshot fixtures use the real history tuple. No new production compatibility API is invented. |
| U03 transaction | transact(home, *, agent, op_id, kind, payload, validators, prepare, ...); prepare(history, allocated_draft) returns payload after id allocation. This resolves birth-id binding without competing allocation. append/render/fold/Command parameters and native expected_head/tool-digest support are absent; U12 policy still has to satisfy their observable requirements through this existing transaction. |
| U03 reads/verification | snapshot(home) returns history; verify(home) returns ok/errors/head fields, not valid/issues/projections. Agent/scorecard drift remains BLOCKED until real integration supplies it. |
| U04 app and carriers | dispatch(..., context=..., registry=...) returns DispatchResult; list_tools(registry=...) returns descriptors. CLI tools emits {tools:[...]}; CLI/MCP accept injected streams/registry. Defaults and effective actor binding are not performed by current app.dispatch; agent handlers must bridge required behavior within their own surface. |
| U02 schema | strict_loads and validate(value, schema) are the available APIs; SchemaStore/decode/canonical/digest interfaces are absent. Tests use the real decoder and independent stdlib canonical/hash expectations, never relax or replace the integrated validator. |

U08 is absent, so no compiler adapter is guessed. The actual integrated
transaction callback is the authoritative binding seam. The status-seat
schema and promotion read contract remain absent/inconsistent and block their
integration. Existing HTTP expects a Services-style context rather than the
integrated U04 CallContext; no private server API or network witness is invented.
All mandates here are scoped to the supplied U12 corpus and allowed surface.

## Verification receipt

The required command was executed from the project root with bytecode writing
disabled. Its exact summary was:

```text
Ran 99 tests in 1.426s

FAILED (failures=99)
```

This is 99 red, 0 green, 0 errors and 0 skips [MEASURED]. Every failure contains
`AssertionError: U12 stub:` [MEASURED: captured runner output]; none is an
import/discovery failure. The suite intentionally remains fail-first.

The final full-project command was `python3 -m unittest discover -s tests -t .`.
Its exact summary was:

```text
Ran 742 tests in 17.156s

FAILED (failures=100, skipped=3)
```

Of those, 99 failures are the new designated stub assertions [MEASURED].
Existing tests account for 639 successes, 1 pre-existing failure and 3 skips
[MEASURED]. The remaining failure is
`tests.core.regression.family.test_cursors` failing the frozen regression import
loader. Initial baseline discovery also had a busy-lock concurrency failure;
that failure did not recur in the final standard-runner regression check.
A custom stdin-based regression runner was discarded because multiprocessing
cannot respawn its stdin entrypoint; only the standard-runner receipts above
are used for regression interpretation.

A complete file-content aggregate outside the allowed surface was identical
before and after edits [MEASURED]. AST inspection confirms every production
stub body consists only of `raise NotImplementedError("U12 stub")` [MEASURED].
No implementation, integrated acceptance or token-count receipt is claimed.


## Amendments A-U12

These reconciliation changes retain every original test method and behavioural
assertion. No accepted values were widened and no skip or expected failure was
added. Historical receipts and acceptance mappings above describe their original
corpus; the integrated APIs below supersede their missing-dependency assumptions.

| Changed file or helper | Integrated API reconciliation |
|---|---|
| `tests/agents/__init__.py`: `publish_fixture_skills`, `create` | Publish exact fixture packages through real `skill_publish` dispatch, which supplies U09's immutable artifacts as well as its journal witness; independently calculated pin hashes remain unchanged. |
| `tests/agents/__init__.py`: `seed` | Obtain bundled U07 reference pins through the existing `arguments` helper instead of using synthetic pins in committed-prefix fixtures. Constitution fixtures and their independent byte expectations remain unchanged. |
| `tests/agents/__init__.py`: `memory_context`, `memory_snapshot` | Build integrated `registry.Services`/`registry.Context` and obtain `journal.snapshot(ctx=...)` for U10/U11; native `snapshot(home)` returns an event tuple and native `CallContext` lacks services. |
| `tests/agents/__init__.py`: `configure_lane`; `tests/agents/test_extension.py`: A41 | Provide the JSON lane's explicit private runtime directories and configuration, as required by `docs/JSON_LANE.md`; parity assertions are unchanged. |
| `tests/agents/test_genesis.py`: A7 | Supply `skill_id`, `sha256` and `reason` in the retirement Command, matching U09's argument agreement policy. Historical-pin and retirement assertions are unchanged. |
| `tests/agents/test_fold.py`: A20 | Use an actor-bound memory Context. Integrated U10 requires a callable budget witness even after U11's A-TOK1 change; this fixture explicitly declares the proven UTF-8 byte bound. This is not a model token measurement or a production tokenizer. Generation, replay, supersession and hash assertions remain unchanged. |
| `tests/agents/test_materialization.py`: A35 and A39 | Pass a folded Snapshot and Services-backed Context to `store.rebuild` and `store.verify_projection`, preserving ownership, deterministic bytes and missing-artifact assertions. |
| `tests/agents/test_validation.py`: A8 | Assert the documented `no_agent` error for the initial missing-agent handler call, then execute all original closed-field rejection assertions. |
| `tests/agents/test_review_h1.py` | Add regressions for unchanged caller operation ids, JSON-lane creation and replay commit parity, and propagation of U11's admission refusal without a birth. |

The implementation change in `lineage/domain/agents.py` preserves caller `op_id`
unchanged now that integrated U03 accepts the K0 alphabet. Its obsolete private
entry-rendering fallback is removed: U11 owns A-TOK1 admission, and a genuine
`memory_debt` refusal must propagate before append.

A11 and A22 remain BLOCKED/HOLD because `lineage.domain.runs` and
`lineage.domain.promotion` are AUSENTE. A38 and the agent-projection part of A39
remain BLOCKED/HOLD because integrated `journal.verify` has no projection
registration or verification seam. Their tests and assertions remain unchanged;
adding skips would contradict the repair mandate. No API, module alias or public
hook is invented to convert these gates to PASS. U11's projection verification
is independently executable with its actual Snapshot/Context API.

No frozen-input hash rows were changed. Token counts remain not measured.
All changes are scoped to the supplied U12 corpus and authorized surface.

### Repair h1 verification

| Check | Current result |
|---|---|
| `python3 -m unittest discover -s tests/agents -t .` | 102 tests: 98 passed, 4 failed, 0 errors, 0 skips [MEASURED]. |
| Full suite with `REGRESSION=0` | 2241 tests: 2212 passed, 4 failed, 25 existing skips, 0 errors [MEASURED]. |
| Contract conformance | Exit 0; all assigned agent-tool descriptors match [MEASURED]. |

The remaining failures are A11, A22, A38 and the agent-projection part of A39,
all within `tests/agents` [MEASURED]. All original test methods and assertion
counts were retained in an AST audit, and the fixture diffs were inspected
[MEASURED]. No new skips were added. The review regressions pass with the repair;
restoring the former operation-id hashing or U11-refusal bypass in isolated
in-process mutants makes their regression assertions fail without import errors
[MEASURED]. No production file was changed by those mutation checks.
