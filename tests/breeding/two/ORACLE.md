# U18 fail-first oracle

Source: `.unit/SPEC.md`, including Amendment B; frozen wire source:
`docs/CONTRACT.md`, including Amendment A-K0. All counts and limits in the
acceptance table are requirements [TARGET], not admission evidence.

The invocation is `python3 -m unittest discover -s tests/breeding/two -t .`.
Each case begins with a real missing-parent/no_agent domain control using the
operator under test. This control precedes optional dependency imports. A stub
exception is neither caught as success nor converted into a skip. This makes the
current red cause U18 itself, rather than missing dependencies. After U18 is
implemented, absent dependencies explicitly fail HOLD. The control does not
certify the scenario assertions that follow it.

The only implementation files created are `lineage/domain/breeding/cross.py`,
`lineage/domain/breeding/mutate.py`, `lineage/domain/breeding/specialize.py`, and
`lineage/ext/breeding2.py`. Domain bodies raise `NotImplementedError("U18 stub")`.
The extension's inert `TOOLS=()`, `VALIDATORS={}`, `FOLDS={}` exports preserve
registry discovery until implementation. The exact required registration and
schemas are asserted, never implemented in the oracle. No U17 package initializer
or ancestor test package is created or modified.

## Acceptance map

Every test name is relative to `tests/breeding/two/`. Rows map the numbered
acceptance obligations to executable assertions; a row is not a passing receipt.

| Acceptance | Test names |
|---|---|
| A1 | `test_extension.py:ExtensionTests.test_a01_exact_domain_signatures_and_importable_surface`<br>`test_extension.py:ExtensionTests.test_a01_selector_and_shared_validator_are_real_admission_witnesses` |
| A2 | `test_extension.py:ExtensionTests.test_a02_missing_actor_and_operation_identity_reject`<br>`test_extension.py:ExtensionTests.test_a02_null_name_boolean_head_unknown_top_level_and_claimed_gates`<br>`test_extension.py:ExtensionTests.test_a02_nested_skill_change_unknown_keys_and_mixed_branches`<br>`test_extension.py:ExtensionTests.test_a02_blank_or_control_display_names_reject`<br>`test_extension.py:ExtensionTests.test_a02_shared_strict_cli_rejects_duplicate_keys_and_bad_unicode` |
| A3 | `test_extension.py:ExtensionTests.test_a03_missing_parent_and_source_ownership`<br>`test_extension.py:ExtensionTests.test_a03_existing_child_and_self_parent_are_conflict`<br>`test_extension.py:ExtensionTests.test_a03_reserved_children_and_duplicate_parents_reject`<br>`test_extension.py:ExtensionTests.test_a03_actor_is_same_user_assertion_without_parent_membership` |
| A4 | `test_extension.py:ExtensionTests.test_a04_registry_has_exact_tools_no_duplicate_validator_or_fold`<br>`test_extension.py:ExtensionTests.test_a04_cli_and_mcp_replay_exact_inner_result_and_one_wrapper`<br>`test_extension.py:ExtensionTests.test_a04_json_lane_uses_computed_identity_and_shared_policy`<br>`test_extension.py:ExtensionTests.test_a04_real_http_handler_replays_shared_result_without_network` |
| A5 | `test_cross.py:CrossTests.test_a05_compatible_language_matrix_and_order`<br>`test_cross.py:CrossTests.test_a05_parent_reversal_changes_name_and_array_only_as_declared`<br>`test_cross.py:CrossTests.test_a05_distinct_concrete_languages_reject`<br>`test_cross.py:CrossTests.test_a05_distinct_workflows_reject`<br>`test_cross.py:CrossTests.test_a05_explicit_name_changes_only_child_name` |
| A6 | `test_cross.py:CrossTests.test_a06_seat_intersection_uses_complete_tuples_and_sorts`<br>`test_cross.py:CrossTests.test_a06_same_model_different_effort_has_empty_intersection`<br>`test_cross.py:CrossTests.test_a06_same_model_different_mode_has_empty_intersection` |
| A7 | `test_cross.py:CrossTests.test_a07_skill_union_collapses_equal_pins_and_sorts`<br>`test_cross.py:CrossTests.test_a07_competing_skill_hashes_cannot_prefer_first_parent`<br>`test_cross.py:CrossTests.test_a07_retired_pin_resolves_historically_but_unknown_hash_rejects`<br>`test_cross.py:CrossTests.test_a07_corrupt_materialized_skill_package_cannot_be_inherited` |
| A8 | `test_cross.py:CrossTests.test_a08_alias_canonical_overrides_union_and_reversion`<br>`test_cross.py:CrossTests.test_a08_opposite_overrides_reject`<br>`test_cross.py:CrossTests.test_a08_compiler_conflict_has_no_parent_preference_fallback`<br>`test_cross.py:CrossTests.test_a08_recompile_union_uses_verified_empty_overlay_sets`<br>`test_cross.py:CrossTests.test_a08_supported_source_alias_and_canonical_override_share_one_identity` |
| A9 | `test_cross.py:CrossTests.test_a09_distinct_subject_keys_coexist`<br>`test_cross.py:CrossTests.test_a09_lesson_conflict_names_both_source_identities`<br>`test_cross.py:CrossTests.test_a09_negative_conflict_general_concrete`<br>`test_cross.py:CrossTests.test_a09_workflow_steps_conflict`<br>`test_cross.py:CrossTests.test_a09_normalized_subject_key_does_not_normalize_body_equality`<br>`test_cross.py:CrossTests.test_a09_raw_body_whitespace_difference_is_conflict`<br>`test_cross.py:CrossTests.test_a09_conflicts_within_one_parent_are_not_ignored` |
| A10 | `test_cross.py:CrossTests.test_a10_identical_claims_keep_two_ids_and_source_hashes`<br>`test_cross.py:CrossTests.test_a10_workflow_statistics_do_not_conflict_or_merge`<br>`test_cross.py:CrossTests.test_a10_equal_statements_across_kinds_are_not_claim_overlap`<br>`test_cross.py:CrossTests.test_a10_normalized_statements_compare_without_rewriting_sources` |
| A11 | `test_cross.py:CrossTests.test_a11_excluded_claim_does_not_create_conflict`<br>`test_specialize.py:SpecializeTests.test_a11_private_content_never_reaches_child_or_brief`<br>`test_specialize.py:SpecializeTests.test_a11_real_selector_reports_every_exclusion_and_precedence`<br>`test_specialize.py:SpecializeTests.test_a11_valid_three_kinds_survive_each_operator`<br>`test_specialize.py:SpecializeTests.test_a11_u18_uses_real_u17_precedence_for_overlapping_exclusions` |
| A12 | `test_birth_integrity.py:BirthIntegrityTests.test_a12_direct_journal_reverifies_changed_evidence`<br>`test_specialize.py:SpecializeTests.test_a12_changed_or_missing_receipt_is_excluded_not_fatal`<br>`test_specialize.py:SpecializeTests.test_a12_internal_symlink_and_directory_receipts_are_invalid`<br>`test_specialize.py:SpecializeTests.test_a12_forbidden_normalized_receipt_paths_are_invalid`<br>`test_specialize.py:SpecializeTests.test_a12_symlink_ancestor_outside_resolved_home_is_allowed` |
| A13 | `test_mutate.py:MutateTests.test_a13_replace_one_hash_preserves_configuration_and_rules`<br>`test_mutate.py:MutateTests.test_a13_replace_with_different_noncolliding_skill_id`<br>`test_mutate.py:MutateTests.test_a13_missing_old_skill_id_is_bad_args`<br>`test_mutate.py:MutateTests.test_a13_wrong_from_hash_is_hash_mismatch`<br>`test_mutate.py:MutateTests.test_a13_missing_target_pin_is_hash_mismatch`<br>`test_mutate.py:MutateTests.test_a13_retired_target_remains_historical_and_unknown_hash_rejects` |
| A14 | `test_mutate.py:MutateTests.test_a14_identical_replacement_is_bad_args`<br>`test_mutate.py:MutateTests.test_a14_replacement_id_collision_is_conflict`<br>`test_mutate.py:MutateTests.test_a14_second_change_and_hidden_rule_or_seat_fields_reject` |
| A15 | `test_mutate.py:MutateTests.test_a15_remove_then_add_has_single_diff_and_explicit_canonical_override`<br>`test_mutate.py:MutateTests.test_a15_rule_text_is_only_literal_add_or_remove`<br>`test_mutate.py:MutateTests.test_a15_unknown_rule_and_unsupported_alias_are_bad_args`<br>`test_mutate.py:MutateTests.test_a15_noop_add_or_repeated_remove_is_bad_args` |
| A16 | `test_mutate.py:MutateTests.test_a16_all_protected_rules_aliases_actions_and_operator_actor_reject` |
| A17 | `test_specialize.py:SpecializeTests.test_a17_general_and_exact_target_only_without_relabeling`<br>`test_specialize.py:SpecializeTests.test_a17_same_language_target_is_valid`<br>`test_specialize.py:SpecializeTests.test_a17_general_target_does_not_broaden_concrete_memory`<br>`test_specialize.py:SpecializeTests.test_a17_language_comparison_is_case_sensitive`<br>`test_specialize.py:SpecializeTests.test_a17_blank_and_control_character_languages_reject`<br>`test_specialize.py:SpecializeTests.test_a17_foreign_ruling_and_wrong_workflow_are_never_relabelled` |
| A18 | `test_mutate.py:MutateTests.test_a18_empty_overrides_are_omitted_on_skill_mutation`<br>`test_specialize.py:SpecializeTests.test_a18_preserves_pins_seats_references_overlays_and_overrides`<br>`test_specialize.py:SpecializeTests.test_a18_retired_skill_can_be_resolved_by_historical_pin` |
| A19 | `test_birth_integrity.py:BirthIntegrityTests.test_a19_nonclone_generation_memory_count_and_independent_version`<br>`test_birth_integrity.py:BirthIntegrityTests.test_a19_empty_inherited_memory_starts_zero`<br>`test_birth_integrity.py:AdditionalBirthTests.test_a19_filtered_child_does_not_copy_parent_memory_gen` |
| A20 | `test_birth_integrity.py:BirthIntegrityTests.test_a20_closed_birth_matches_frozen_schema_and_actual_event_id`<br>`test_birth_integrity.py:BirthIntegrityTests.test_a20_extra_payload_diff_claims_and_born_identity_reject` |
| A21 | `test_birth_integrity.py:BirthIntegrityTests.test_a21_own_brief_hash_omits_inherited_but_capacity_service_includes_it`<br>`test_birth_integrity.py:BirthIntegrityTests.test_a21_static_entry_exact_byte_boundary_and_multibyte_overflow`<br>`test_birth_integrity.py:AdditionalBirthTests.test_a21_operator_enforces_multibyte_inherited_entry_overflow` |
| A22 | `test_birth_integrity.py:BirthIntegrityTests.test_a22_accepted_and_rejected_count_overflow_do_not_truncate`<br>`test_birth_integrity.py:AdditionalBirthTests.test_a22_empty_audit_and_complete_within_limit_source_accounting` |
| A23 | `test_birth_integrity.py:BirthIntegrityTests.test_a23_two_hop_provenance_resets_supersession_and_is_immediate`<br>`test_birth_integrity.py:BirthIntegrityTests.test_a23_returned_nested_data_does_not_alias_authority` |
| A24 | `test_transactions.py:TransactionTests.test_a24_replay_returns_original_prefix_after_unrelated_commit`<br>`test_transactions.py:TransactionTests.test_a24_omitted_and_explicit_name_are_distinct_requests`<br>`test_transactions.py:TransactionTests.test_a24_parent_order_and_tool_changes_are_bad_op`<br>`test_transactions.py:TransactionTests.test_a24_language_and_mutation_changes_bind_operation_identity`<br>`test_transactions.py:TransactionTests.test_a24_actor_namespaces_are_independent`<br>`test_transactions.py:TransactionTests.test_a24_full_k0_operation_id_is_not_renamed`<br>`test_transactions.py:TransactionTests.test_a24_replay_ignores_changed_parent_projection_metadata` |
| A25 | `test_transactions.py:TransactionTests.test_a25_new_operation_exact_head_and_stale_head`<br>`test_transactions.py:TransactionTests.test_a25_replay_precedes_retirement_and_expected_head` |
| A26 | `test_transactions.py:TransactionTests.test_a26_concurrent_distinct_operations_same_child_have_one_winner`<br>`test_transactions.py:TransactionTests.test_a26_concurrent_identical_retry_has_one_witness` |
| A27 | `test_transactions.py:TransactionTests.test_a27_retirement_before_admission_is_observed`<br>`test_transactions.py:TransactionTests.test_a27_supersession_before_admission_uses_locked_latest_source`<br>`test_transactions.py:TransactionTests.test_a27_birth_winning_before_retirement_retains_valid_source_prefix`<br>`test_transactions.py:TransactionTests.test_a27_concurrent_retire_and_birth_follow_committed_order` |
| A28 | `test_birth_integrity.py:BirthIntegrityTests.test_a28_record_forgeries_reject_before_append`<br>`test_birth_integrity.py:BirthIntegrityTests.test_a28_constitution_prose_tamper_with_matching_hash_still_rejects`<br>`test_birth_integrity.py:BirthIntegrityTests.test_a28_fake_source_hash_receipt_or_level_one_cannot_bypass`<br>`test_birth_integrity.py:BirthIntegrityTests.test_a28_extra_skill_change_in_mutation_is_rejected`<br>`test_birth_integrity.py:BirthIntegrityTests.test_a28_specialization_cannot_widen_seats_or_scope`<br>`test_birth_integrity.py:AdditionalBirthTests.test_a28_forbidden_rule_override_and_extra_citation_reject` |
| A29 | `test_transactions.py:TransactionTests.test_a29_corrupt_or_unreadable_ledger_is_never_empty_state`<br>`test_transactions.py:TransactionTests.test_a29_compiler_and_validator_failure_leave_no_birth`<br>`test_transactions.py:TransactionTests.test_a29_held_real_admission_lock_returns_busy` |
| A30 | `test_transactions.py:TransactionTests.test_a30_projection_failure_is_durable_and_retry_repairs_original_birth`<br>`test_transactions.py:TransactionTests.test_a30_deleted_child_projections_rebuild_identically`<br>`test_transactions.py:TransactionTests.test_a30_partial_projection_failure_repairs_without_parent_changes` |
| A31 | `test_cross.py:CrossTests.test_a31_reordered_source_mapping_preserves_complete_audit`<br>`test_cross.py:CrossTests.test_a31_seat_pin_and_source_order_preserve_artifacts_at_fixed_identity` |
| A32 | `test_birth_integrity.py:GuardMutationTests.test_a32_claim_conflict_guard_discriminates`<br>`test_birth_integrity.py:GuardMutationTests.test_a32_protected_rule_guard_discriminates`<br>`test_birth_integrity.py:GuardMutationTests.test_a32_language_scope_guard_discriminates` |
| A33 | `test_birth_integrity.py:BirthIntegrityTests.test_a33_public_fixtures_and_output_have_no_host_coordinates` |

## Explicit Amendment B resolutions

- Retired immutable skill pins remain resolvable historically, following K0's
  explicit retirement guarantee. Cross, mutation targets and specialization test
  this; an unavailable or changed historical package/hash is still rejected.
- The byte-budget target is exactly
  `memory.entry.build(child, inherited_units, token_count=None, max_bytes=6000)`
  [TARGET: 6000 UTF-8 bytes], using adopted units without provenance wrappers.
  It is the memory static entry, not the entire inherited-arm brief. Byte-boundary
  service tests and U18 delegation/overflow tests are separate. No byte/token
  conversion is used; the token ceiling is not measured.
- Claim statement overlap is restricted to equal kinds. Comparison keys and
  statements normalize only for comparison. Body equality is raw canonical JSON;
  a workflow body omits exactly `stats` for equality. Different statistics remain
  separate source records. Source text is never normalized on storage.
- All syntactically valid caller actors are allowed in the same-user boundary,
  including operator/system, unregistered and retired creators. They acquire no
  operator authority. Reserved identifiers remain forbidden for children.
- Rule text is the exact literal add/remove. Resolved canonical override keys
  persist explicitly on reversal, and empty maps are omitted. Positive alias
  behavior is asserted when a spelling from the verified source is supported;
  unsupported source spellings are bad_args, never presumed valid aliases.
- Blank names/languages and all ASCII control characters are bad_args. Language
  equality stays exact and case sensitive. Same-language and general targets are
  covered without broadening a concrete unit.
- Receipt paths remain home-relative. Tests include a symlink pointing back
  inside home, directories, traversal, ledger/family normalization tricks and
  an ancestor symlink outside resolved home. Two-hop provenance checks name the
  immediate source, reset supersedes and remove superseded_by. Matching hashes
  and valid citation IDs do not authorize tampered constitution prose.

## Integrated API adaptations and remaining gates

| Boundary | Observed adaptation or unresolved precondition |
|---|---|
| Core context | Use installed `app.CallContext`, not absent nominal Context/Services. The test-owned immutable Command only models the specified effective request; it is not a production service. |
| Registry | Installed ToolSpec uses mutating and a keyword-only context handler; validators accept history/event and folds are callable. No FoldSpec, effect constructor or nominal Command import is used. |
| Dispatch | Call `dispatch(..., context=..., registry=...)` and inspect `DispatchResult.payload`, preserving exactly one untrusted wrapper. |
| Journal | Use `snapshot(home)` tuples and `transact(home, ..., prepare, clock, id_factory)`; prepare reads draft["id"]. No nominal render, expected_head argument or Snapshot class is invented. Request identity and wider OpId/optimistic-head behavior remain acceptance assertions, not silently narrowed contracts. |
| Strict JSON | Use installed `schema.strict_loads`/validate and the real CLI/MCP, not absent decode/SchemaStore/canonical aliases. Frozen schema assertions are not deleted to fit the installed subset. |
| References | Existing reference_get has a reference wrapper. Pins come from its verified returned hashes and rules, not synthetic reference hashes. |
| HTTP | Exercise inspected `_Handler` and `_Services` through in-memory request/response streams. No listener, network traffic or invented HTTP API is used. |
| JSON lane | Create the required recipient-owned `family/target/config.json` and use the inspected envelope operation identity, not a hand-selected transport op_id. |
| Missing owners | U17 inherit.select; U12 agents/agent.born delegation, fold and materialization; constitution, version, brief, memory.entry and memory.store services are AUSENTE in this snapshot. The integrated memory extension still imports absent nominal registry types. These are HOLD gates, never replaced with permissive validators, fake selectors, fabricated packages or passing skips. |

The isolated count/byte-overflow tests inject only the public memory-fold read
for bounded oversized source fixtures; the real selector and shared validator
remain required. These fixtures do not certify authoritative source-history
admission. Invalid historical-unit policy fixtures call the real U17 selector;
they are not inserted using a permissive journal validator. Actual births use
real parent creation, real journal commits and independently hashed evidence.

Each rejecting operation compares authoritative journal bytes and projection
files. Lock creation is permitted; child materialization is not. Successful
operations check the original commit prefix, event ID, hash chain, parent links,
status, independently calculated version and complete source accounting.

Concurrency uses spawn, events and pipes, with owned PID witnesses. There are no
fixed sleeps or process-group operations. Cleanup kills only exact owned PIDs
that were checked greater than one. Mutant evaluation runs in temporary copied
sources, preserves frozen oracle bytes, first requires healthy positive/negative
controls and then requires the selected negative assertion to fail while the
positive still passes. Imports, missing mutation sites, timeouts and exceptions
are HOLD, not discriminating mutant evidence. No private helper name is assumed.

## Evidence status

Fail-first discovery and stub causes are verified on the host [MEASURED]. The
post-stub behavioral assertions, integrated direct-journal admission, actual guard
mutants and byte-boundary delegation remain HOLD. Nonempty compatible overlay
fixtures require the owner's verified overlay registry; that registry is AUSENTE,
so empty-union and injected compiler-conflict tests do not certify nonempty overlay
composition. Supported positive aliases likewise require the verified compiler.

Cross-family ADMIT receipt: AUSENTE. U17 host-green receipt: AUSENTE. U18 runtime
acceptance receipt: AUSENTE. Capsule/UI evidence: INCONCLUSIVE. Measured fitness
or inherited-memory benefit: AUSENTE. Syntax checks and synthetic fixtures never
claim these statuses. The external regression runner in helpers excludes the U18
suite and preserves its existing failures/skips separately from expected U18 red.

All mandates and evidence claims are scoped to the supplied campaign corpus,
amended K0 and the assigned U18 surface.

## Amendments A-U18

These are API, argument-plumbing and fixture reconciliations under A-K0-9,
A-TOK1 and A-LAY1. Existing test methods, behavioral assertions, expected errors,
closed records and guard-mutant verdicts are retained. No case is skipped.

| File / case | Reconciliation |
|---|---|
| `helpers.py:publish`; `test_cross.py:test_a07_retired_pin_resolves_historically_but_unknown_hash_rejects` | Read the hash from integrated `skill_get`'s `skill` wrapper, preserving independently calculated pin equality. |
| `helpers.py:source_snapshot`; `test_specialize.py:test_a17_general_and_exact_target_only_without_relabeling` | Current `memory_put` refuses concrete scopes on a general owner. Admit the valid general unit normally, then supply the historical mixed-language fixture at the public fold read. The real selector, safe evidence service, shared validator and journal still run. This isolated fixture does not certify historical source admission. All accepted/rejected identities, original scopes and unchanged-parent assertions remain. |
| `test_specialize.py:test_a17_language_comparison_is_case_sensitive`; `test_birth_integrity.py:test_a28_specialization_cannot_widen_seats_or_scope` | Put python memory on a python owner, as required by integrated memory admission. Keep the case-sensitive target and forged-scope assertions. |
| `test_birth_integrity.py:test_a19_filtered_child_does_not_copy_parent_memory_gen` | Seed valid general/python units on a python owner, then specialize to general. The parent count, filtered child count, independent version and next-generation assertions are unchanged. |
| `test_extension.py:test_a04_json_lane_uses_computed_identity_and_shared_policy` | Give mailbox control directories and config private permissions, independent of host umask. Keep the actual lane identity and exact result comparison. |
| `test_extension.py:test_a04_real_http_handler_replays_shared_result_without_network` | Supply `raw_requestline`, which the integrated router reads; retain HTTP success and exact replay assertions. |
| `test_birth_integrity.py:test_a20_closed_birth_matches_frozen_schema_and_actual_event_id` | Use the integrated frozen-envelope checker for full schema composition, closure and property-name checks. Resolve the integrated event schema's additional bundled run/benchmark references; no wire field or schema constraint is removed. |
| `test_birth_integrity.py:test_a21_own_brief_hash_omits_inherited_but_capacity_service_includes_it` | Pass the committed constitution's required `rule_ids` into `brief.build`; keep own-arm hash and absent production token-counter assertions. |
| `test_birth_integrity.py:test_a21_static_entry_exact_byte_boundary_and_multibyte_overflow` | Isolate the byte-boundary service test with an explicit test counter at the token ceiling. Preserve exact byte admission and multibyte overflow assertions. Production uses `token_count=None`; this counter is neither a tokenizer measurement nor a birth-capacity bypass. |
| `helpers.py:forge`, `valid_forge_template`; `test_birth_integrity.py:test_a20_extra_payload_diff_claims_and_born_identity_reject` | Bind the genuine shared validator's runtime `ctx` and pass the actual original pre-prepare request. Forgery tests now reach semantic admission instead of failing merely because the context is unavailable. The journal owns the new event identity. |
| `helpers.py:valid_forge_template`; `test_transactions.py:test_a30_deleted_child_projections_rebuild_identically` | Remove the entire disposable child's projection directory through `layout.agent_dir`; leaving empty immutable-generation directories represents corruption, not deleted projections. Retain every byte-for-byte rebuild assertion. |
| `test_transactions.py:test_a30_projection_failure_is_durable_and_retry_repairs_original_birth`, `test_a30_partial_projection_failure_repairs_without_parent_changes` | Forward materialize's installed `_preserve_unchanged` keyword, so injection occurs at the intended real publication step. Durable-event, original-prefix repair and source-immutability assertions remain. |
| `test_birth_integrity.py:GuardMutationTests._evaluate` | Trace only breeding exception events, avoiding unrelated compiler line tracing. Derive the authority predicate from its actual refusing condition; mutate literal claim-conflict origins without removing generic error propagation. Allow the integrated fixtures to finish within a bounded host deadline rather than the nominal stub deadline. Preserve healthy positive controls, exact mutant-failure assertions and exact owned-PID cleanup. |
| `helpers.py:OracleCase.setUp`, `child_call`, `parallel` | Keep runtime homes outside the repository snapshot and accommodate real integrated startup/admission with bounded event/pipe deadlines. Exact owned-PID witnesses, success/error assertions and cleanup remain; no fixed sleep or process-group control is introduced. |
| `helpers.py:runtime.deterministic`; `test_cross.py:test_a31_seat_pin_and_source_order_preserve_artifacts_at_fixed_identity` | Inject deterministic generators when integrated callers explicitly pass `None`, as well as when omitted. The fixed-identity byte-equality assertion is unchanged. |
| `test_cross.py:test_a07_retired_pin_resolves_historically_but_unknown_hash_rejects` | Give the subsequent mutation its own operation identity so the test reaches unknown-pin admission, while the separate changed-tool replay test still requires `bad_op`. |
| `test_cross.py:test_a08_recompile_union_uses_verified_empty_overlay_sets` | Observe requested overlay IDs at the real U12 compiler adapter. Its lower-level compiler instead accepts a verified overlay policy mapping. Retain the exact empty-ID-list and real recompilation assertions. |
| `test_specialize.py:test_a18_preserves_pins_seats_references_overlays_and_overrides` | Use `typescript`, supported by the integrated compiler, for the fixture requiring changed constitution bytes. Keep exact requested-language equality, unchanged configuration and different constitution hashes. Arbitrary languages remain permitted and use the owner's general policy. |
| `test_review_admission.py` | Add a context-bound direct-birth positive control, hostile original-parent-order / omitted-name controls, and a deterministic concurrent-head projection recovery control. These exercise the genuine shared owner and the journal's original request digest. |

The implementation additionally verifies the installed journal's original
pre-prepare request digest during U18 birth reconstruction. This binds parent
order, mutation, specialization and optional-name spelling to the effective
request without renaming `op_id`, adding event fields, registering another
validator, or editing a dependency owner.

Cross-family review and capsule evidence remain separate acceptance gates;
these reconciliations do not create an ADMIT receipt or a measured memory benefit.

The post-commit publisher also retries only when an independently read journal
prefix proves that another durable append advanced the head during publication.
An unchanged-head publication failure remains an error, preserving the existing
failure/replay recovery assertions. Publication still goes exclusively through
`agents.refresh_projections`; the original birth result and commit prefix remain
unchanged, and no admission callback performs I/O writes.
