# U11 fail-first oracle

This oracle targets `.unit/SPEC.md`, including Amendment B, and frozen
`docs/CONTRACT.md`, `docs/INTERFACES.md`, `docs/OPERABILITY.md`,
`schemas/agent.schema.json`, `schemas/mem_unit.schema.json`,
`schemas/event.schema.json` and `schemas/tool_error.schema.json`.
Only the U11 test directory and the assigned U11 stub modules are changed.

Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/memory/store -t .
```

Behavioral cases must reach `NotImplementedError("U11 stub")` now, rather than
an import error or an assertion expecting that exception. Once implementation
exists, unavailable K0/U10 interfaces remain explicit integration failures.
No test converts an absent prerequisite into a pass or skip. The structural
coverage/package checks can pass before implementation; they certify only the
oracle inventory. Red counts are test outcomes, never runtime success receipts.

All fixture files live in automatically removed `.runtime-*` directories under
`tests/memory/store`. Inputs are synthetic, schema-checked fixtures, not evidence
of production births or memory performance. Pure tests use independently written
canonical ledger lines with original event and predecessor digests. They do not
assert that the projected subsequence is a complete global hash chain.

## Acceptance mapping

Every numbered Acceptance item is listed below. Test ids are relative to the
`tests.memory.store` package. A mapped case is an obligation, not a passing
receipt. Integration cases require the actual dependency owners; no legacy
room API, replacement fold or replacement registry is supplied.

| Acceptance | Test names | Gate / rejecting contrast |
|---|---|---|
| A1 | `test_entry.EntryOracle.test_a01_counter_sees_final_render_including_lf`<br>`test_entry.EntryOracle.test_a01_deterministic_complete_sorted_passive_bytes`<br>`test_generations.GenerationOracle.test_a05_loss_rebuild_identical_across_two_runtime_homes` | Canonical complete records, stable bytes and final LF; changed order or lossy rendering fails. |
| A2 | `test_entry.EntryOracle.test_a02_cuts_are_deterministic_and_do_not_mutate_units`<br>`test_entry.EntryOracle.test_a02_exact_configured_byte_ceiling`<br>`test_entry.EntryOracle.test_a02_exact_production_byte_ceiling`<br>`test_entry.EntryOracle.test_a02_exact_token_ceiling_and_next_token`<br>`test_entry.EntryOracle.test_a02_long_cut_diagnostic_is_bounded_and_explicit`<br>`test_entry.EntryOracle.test_a02_unicode_byte_limit_is_not_character_limit` | Independent exact/next byte and token boundaries; estimates, silent cuts or bypassed ceilings fail. |
| A3 | `test_bootcheck.BootcheckOracle.test_a03_counter_bool`<br>`test_bootcheck.BootcheckOracle.test_a03_counter_exception`<br>`test_bootcheck.BootcheckOracle.test_a03_counter_float`<br>`test_bootcheck.BootcheckOracle.test_a03_counter_missing`<br>`test_bootcheck.BootcheckOracle.test_a03_counter_negative`<br>`test_entry.EntryOracle.test_a03_counter_bool`<br>`test_entry.EntryOracle.test_a03_counter_exception`<br>`test_entry.EntryOracle.test_a03_counter_float`<br>`test_entry.EntryOracle.test_a03_counter_missing`<br>`test_entry.EntryOracle.test_a03_counter_negative`<br>`test_entry.EntryOracle.test_a03_counter_string`<br>`test_generations.GenerationOracle.test_a03_rebuild_without_counter_refuses_without_partial_files` | Unusable injected counters refuse; fallback estimates and missing capacity cannot pass. |
| A4 | `test_memory_resume.MemoryResumeOracle.test_a04_overflow_before_append_then_same_operation_can_commit`<br>`test_memory_resume.MemoryResumeOracle.test_a04_real_transaction_byte_overflow_appends_nothing` | Real U10 admission and same-op retry; changed ledger, dedup or projection on rejection fails. K0/U10 integration pending. |
| A5 | `test_generations.GenerationOracle.test_a05_full_history_mapping_is_pure_canonical_and_complete`<br>`test_generations.GenerationOracle.test_a05_loss_rebuild_identical_across_two_runtime_homes` | Full historical mapping, deletion/rebuild and another home; missing inherited/history bytes fail. |
| A6 | `test_generations.GenerationOracle.test_a06_birth_is_generation_one_and_episode_is_not_memory_gen`<br>`test_generations.GenerationOracle.test_a06_unrelated_head_does_not_rewrite_entry_or_generation` | Projection generation, brief counter and global head remain distinct; conflation fails. |
| A7 | `test_generations.GenerationOracle.test_a07_historical_versions_and_supersession_are_not_copied_backward`<br>`test_generations.GenerationOracle.test_a07_repeated_rebuild_reuses_every_published_generation` | Historical manifests/status and existing generations remain immutable; backward copying fails. |
| A8 | `test_generations.GenerationOracle.test_a08_subject_selection_preserves_original_hashes_and_gaps`<br>`test_generations.GenerationOracle.test_a08_target_actor_event_is_selected_without_a_target_payload` | Schema subjects/actors/runs select canonical subsequences; text matching or local rehashing fails. |
| A9 | `test_projection_safety.ProjectionSafetyOracle.test_a09_crash_debris_is_never_selected`<br>`test_projection_safety.ProjectionSafetyOracle.test_a09_fault_current_replace`<br>`test_projection_safety.ProjectionSafetyOracle.test_a09_fault_directory_fsync`<br>`test_projection_safety.ProjectionSafetyOracle.test_a09_fault_file_fsync`<br>`test_projection_safety.ProjectionSafetyOracle.test_a09_fault_generation_publish`<br>`test_projection_safety.ProjectionSafetyOracle.test_a09_fault_staging` | Syscall fault injection and crash debris; incomplete current generations cannot pass verification. |
| A10 | `test_memory_resume.MemoryResumeOracle.test_a10_postcommit_failure_replay_preserves_original_commit_prefix` | Real post-commit failure and exact retry retain the original prefix; append-on-retry fails. K0/U10 pending. |
| A11 | `test_generations.GenerationOracle.test_a11_corrupted_published_entry_cannot_be_repaired_in_place`<br>`test_projection_safety.ProjectionSafetyOracle.test_a11_corrupt_manifest_not_overwritten`<br>`test_projection_safety.ProjectionSafetyOracle.test_a11_corrupt_unit_not_overwritten` | Corrupted published files refuse repair; destructive overwrite fails. |
| A12 | `test_projection_safety.ProjectionSafetyOracle.test_a12_entry_mirror`<br>`test_projection_safety.ProjectionSafetyOracle.test_a12_extra_file`<br>`test_projection_safety.ProjectionSafetyOracle.test_a12_extra_generation`<br>`test_projection_safety.ProjectionSafetyOracle.test_a12_forged_manifest`<br>`test_projection_safety.ProjectionSafetyOracle.test_a12_forged_unit_and_self_consistent_manifest_are_rejected`<br>`test_projection_safety.ProjectionSafetyOracle.test_a12_issue_results_do_not_alias`<br>`test_projection_safety.ProjectionSafetyOracle.test_a12_journal_mirror`<br>`test_projection_safety.ProjectionSafetyOracle.test_a12_journal_reordering_is_not_a_new_local_chain`<br>`test_projection_safety.ProjectionSafetyOracle.test_a12_missing_entry`<br>`test_projection_safety.ProjectionSafetyOracle.test_a12_missing_old_generation`<br>`test_projection_safety.ProjectionSafetyOracle.test_a12_missing_unit`<br>`test_projection_safety.ProjectionSafetyOracle.test_a12_pristine_projection_verifies_without_writing`<br>`test_projection_safety.ProjectionSafetyOracle.test_a12_stale_pointer` | Missing/extra files, mirrors, manifests and reordered journals; self-consistent counterfeits fail. |
| A13 | `test_projection_safety.ProjectionSafetyOracle.test_a13_hostile_scope_never_forms_filesystem_components`<br>`test_projection_safety.ProjectionSafetyOracle.test_a13_staging_directory_substitution_refuses_escape`<br>`test_projection_safety.ProjectionSafetyOracle.test_a13_symlink_entry_mirror`<br>`test_projection_safety.ProjectionSafetyOracle.test_a13_symlink_generation`<br>`test_projection_safety.ProjectionSafetyOracle.test_a13_symlink_journal_mirror`<br>`test_projection_safety.ProjectionSafetyOracle.test_a13_symlink_manifest`<br>`test_projection_safety.ProjectionSafetyOracle.test_a13_symlink_pointer`<br>`test_projection_safety.ProjectionSafetyOracle.test_a13_symlink_unit`<br>`test_projection_safety.ProjectionSafetyOracle.test_a13_symlink_units_directory`<br>`test_projection_safety.ProjectionSafetyOracle.test_a13_symlinked_memory_ancestor_is_refused_without_escape` | Unsafe pointers/symlinks and scope-derived path use refuse; an escape or leak fails. Staging substitution is separately tracked below. |
| A14 | `test_route.RouteOracle.test_a14_coverage_descending_then_lexical_id`<br>`test_route.RouteOracle.test_a14_default_and_explicit_limits_are_applied_after_ranking`<br>`test_route.RouteOracle.test_a14_one_snapshot_supplies_both_units_and_head`<br>`test_route.RouteOracle.test_a14_unicode_casefold_and_word_token_definition` | Exact Unicode term coverage, repeated terms, id tie-break and limits; wrong order/head fails. |
| A15 | `test_route.RouteOracle.test_a15_absent_ordinary`<br>`test_route.RouteOracle.test_a15_absent_punctuation`<br>`test_route.RouteOracle.test_a15_absent_whitespace` | Exact NOT IN MEMORY result for valid unmatched, blank and punctuation queries; invented text fails. |
| A16 | `test_entry.EntryOracle.test_a16_entry_filters_status_privacy_workflow_and_language`<br>`test_route.RouteOracle.test_a16_inherited_context_remains_visible`<br>`test_route.RouteOracle.test_a16_metadata_receipts_and_ids_are_not_searchable`<br>`test_route.RouteOracle.test_a16_private_inactive_and_scope_mismatches_are_excluded`<br>`test_route.RouteOracle.test_a16_target_ownership_is_not_the_event_actor` | Status/privacy/scope, inherited context, target ownership and metadata-only queries; context leakage fails. |
| A17 | `test_route.RouteOracle.test_a17_bad_id`<br>`test_route.RouteOracle.test_a17_empty_query`<br>`test_route.RouteOracle.test_a17_expected_head`<br>`test_route.RouteOracle.test_a17_extra`<br>`test_route.RouteOracle.test_a17_limit_bool`<br>`test_route.RouteOracle.test_a17_limit_float`<br>`test_route.RouteOracle.test_a17_limit_large`<br>`test_route.RouteOracle.test_a17_limit_negative`<br>`test_route.RouteOracle.test_a17_limit_null`<br>`test_route.RouteOracle.test_a17_limit_zero`<br>`test_route.RouteOracle.test_a17_long_query`<br>`test_route.RouteOracle.test_a17_missing_agent`<br>`test_route.RouteOracle.test_a17_missing_query`<br>`test_route.RouteOracle.test_a17_nul_agent`<br>`test_route.RouteOracle.test_a17_op_id`<br>`test_route.RouteOracle.test_a17_read_actor_operator_does_not_widen_target_scope`<br>`test_route.RouteOracle.test_a17_valid_missing_target_through_dispatch_is_no_agent` | Closed tool validation and actor isolation; bools, unsafe ids, mutation args and invented agents fail. |
| A18 | `test_route.RouteOracle.test_a18_answer_is_exact_first_full_statement_without_concatenation` | Complete ranked units and exact bounded top statement; concatenation, truncation or schema drift fails. |
| A19 | `test_bootcheck.BootcheckOracle.test_a19_expected_is_exact_shape_and_does_not_read_projection_cache`<br>`test_bootcheck.BootcheckOracle.test_a19_no_required_receipt_is_invented_for_level_three`<br>`test_bootcheck.BootcheckOracle.test_a19_positive_uses_actual_artifacts_and_independent_ledger_values` | Independent observations from actual files and fixture ledger; echoed observations cannot certify success. |
| A20 | `test_bootcheck.BootcheckOracle.test_a20_unrelated_event_makes_old_global_head_stale`<br>`test_bootcheck.BootcheckOracle.test_a20_wrong_agent_version`<br>`test_bootcheck.BootcheckOracle.test_a20_wrong_entry_sha256`<br>`test_bootcheck.BootcheckOracle.test_a20_wrong_head`<br>`test_bootcheck.BootcheckOracle.test_a20_wrong_memory_gen` | Each schema-valid wrong observation and stale global head refuses; partial success fails. |
| A21 | `test_bootcheck.BootcheckOracle.test_a21_agent_version_bool`<br>`test_bootcheck.BootcheckOracle.test_a21_agent_version_nonhex`<br>`test_bootcheck.BootcheckOracle.test_a21_agent_version_nul`<br>`test_bootcheck.BootcheckOracle.test_a21_agent_version_null`<br>`test_bootcheck.BootcheckOracle.test_a21_agent_version_short`<br>`test_bootcheck.BootcheckOracle.test_a21_agent_version_upper`<br>`test_bootcheck.BootcheckOracle.test_a21_bool`<br>`test_bootcheck.BootcheckOracle.test_a21_entry_sha256_bool`<br>`test_bootcheck.BootcheckOracle.test_a21_entry_sha256_nonhex`<br>`test_bootcheck.BootcheckOracle.test_a21_entry_sha256_nul`<br>`test_bootcheck.BootcheckOracle.test_a21_entry_sha256_null`<br>`test_bootcheck.BootcheckOracle.test_a21_entry_sha256_short`<br>`test_bootcheck.BootcheckOracle.test_a21_entry_sha256_upper`<br>`test_bootcheck.BootcheckOracle.test_a21_extra`<br>`test_bootcheck.BootcheckOracle.test_a21_head_bool`<br>`test_bootcheck.BootcheckOracle.test_a21_head_float`<br>`test_bootcheck.BootcheckOracle.test_a21_head_negative`<br>`test_bootcheck.BootcheckOracle.test_a21_head_null`<br>`test_bootcheck.BootcheckOracle.test_a21_head_unsafe`<br>`test_bootcheck.BootcheckOracle.test_a21_memory_gen_bool`<br>`test_bootcheck.BootcheckOracle.test_a21_memory_gen_float`<br>`test_bootcheck.BootcheckOracle.test_a21_memory_gen_negative`<br>`test_bootcheck.BootcheckOracle.test_a21_memory_gen_null`<br>`test_bootcheck.BootcheckOracle.test_a21_memory_gen_unsafe`<br>`test_bootcheck.BootcheckOracle.test_a21_missing_agent_version`<br>`test_bootcheck.BootcheckOracle.test_a21_missing_entry_sha256`<br>`test_bootcheck.BootcheckOracle.test_a21_missing_head`<br>`test_bootcheck.BootcheckOracle.test_a21_missing_memory_gen`<br>`test_bootcheck.BootcheckOracle.test_a21_null`<br>`test_bootcheck.BootcheckOracle.test_a21_scalar`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_agent_version_bool`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_agent_version_nonhex`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_agent_version_nul`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_agent_version_null`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_agent_version_short`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_agent_version_upper`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_bool`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_entry_sha256_bool`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_entry_sha256_nonhex`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_entry_sha256_nul`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_entry_sha256_null`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_entry_sha256_short`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_entry_sha256_upper`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_extra`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_head_bool`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_head_float`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_head_negative`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_head_null`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_head_unsafe`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_memory_gen_bool`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_memory_gen_float`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_memory_gen_negative`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_memory_gen_null`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_memory_gen_unsafe`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_missing_agent_version`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_missing_entry_sha256`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_missing_head`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_missing_memory_gen`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_missing_observed_uses_bootcheck_prefix`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_null`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_preserves_bootcheck_diagnostic_prefix`<br>`test_memory_resume.MemoryResumeOracle.test_a21_dispatch_scalar` | Nested syntax/closure through direct and actual shared dispatch paths; missing diagnostic prefix fails. |
| A22 | `test_bootcheck.BootcheckOracle.test_a22_empty_verifier_cannot_bless_missing_receipt`<br>`test_bootcheck.BootcheckOracle.test_a22_entry_corrupt`<br>`test_bootcheck.BootcheckOracle.test_a22_entry_delete`<br>`test_bootcheck.BootcheckOracle.test_a22_entry_mirror_corrupt`<br>`test_bootcheck.BootcheckOracle.test_a22_entry_mirror_delete`<br>`test_bootcheck.BootcheckOracle.test_a22_entry_mirror_symlink`<br>`test_bootcheck.BootcheckOracle.test_a22_entry_symlink`<br>`test_bootcheck.BootcheckOracle.test_a22_journal_mirror_corrupt`<br>`test_bootcheck.BootcheckOracle.test_a22_journal_mirror_delete`<br>`test_bootcheck.BootcheckOracle.test_a22_journal_mirror_symlink`<br>`test_bootcheck.BootcheckOracle.test_a22_manifest_corrupt`<br>`test_bootcheck.BootcheckOracle.test_a22_manifest_delete`<br>`test_bootcheck.BootcheckOracle.test_a22_manifest_symlink`<br>`test_bootcheck.BootcheckOracle.test_a22_pointer_corrupt`<br>`test_bootcheck.BootcheckOracle.test_a22_pointer_delete`<br>`test_bootcheck.BootcheckOracle.test_a22_pointer_symlink`<br>`test_bootcheck.BootcheckOracle.test_a22_receipt_corrupt`<br>`test_bootcheck.BootcheckOracle.test_a22_receipt_delete`<br>`test_bootcheck.BootcheckOracle.test_a22_receipt_symlink`<br>`test_bootcheck.BootcheckOracle.test_a22_unreadable_receipt_is_internal` | Delete/corrupt/symlink required evidence and artifacts; missing evidence or inaccessible I/O cannot pass. |
| A23 | `test_bootcheck.BootcheckOracle.test_a23_forged_entry_manifest_and_supplied_hash_cannot_bless_memory`<br>`test_bootcheck.BootcheckOracle.test_a23_materialized_agent_and_cached_boot_result_are_ignored`<br>`test_route.RouteOracle.test_a23_agent_materialization_cannot_override_authority` | Forged caches and self-consistent entry/manifest pair cannot replace authority; counterfeit blessing fails. |
| A24 | `test_bootcheck.BootcheckOracle.test_a24_evidence_change_during_verification_never_passes`<br>`test_bootcheck.BootcheckOracle.test_a24_new_projection_during_verification_never_passes_old_tuple`<br>`test_bootcheck.BootcheckOracle.test_a24_receipt_replaced_after_read_requires_final_revalidation`<br>`test_generations.GenerationOracle.test_a24_old_prefix_cannot_regress_current` | Counter-boundary evidence/projection changes and older-prefix publication; mixed values or pointer regression fail. |
| A25 | `test_bootcheck.BootcheckOracle.test_a25_empty_born_agent_has_valid_entry_and_passing_bootcheck`<br>`test_bootcheck.BootcheckOracle.test_a25_missing_target_has_no_agent_even_with_forged_files`<br>`test_route.RouteOracle.test_a25_corrupt_complete_ledger_is_not_empty`<br>`test_route.RouteOracle.test_a25_missing_agent_is_not_inferred_from_a_directory`<br>`test_route.RouteOracle.test_a25_torn_final_suffix_does_not_erase_committed_memory`<br>`test_route.RouteOracle.test_a25_unavailable_snapshot_is_internal_not_empty`<br>`test_route.RouteOracle.test_a25_valid_empty_agent_is_exact_absent_result` | Known empty agent, unknown target, corrupt/unavailable ledger and torn tail remain distinct; fabricated emptiness fails. |
| A26 | `test_memory_resume.MemoryResumeOracle.test_a26_exact_extension_inventory_and_frozen_discovery_schemas`<br>`test_memory_resume.MemoryResumeOracle.test_a26_handlers_delegate_positionally_and_return_inner_data`<br>`test_memory_resume.MemoryResumeOracle.test_a26_registry_load_has_one_owner_and_read_effects` | Exact read tools, positional handlers, discovery schemas and unique registry ownership; mutation/transport imports fail. |
| A27 | `test_memory_resume.MemoryResumeOracle.test_a27_transport_agreement_without_network_or_child_processes` | Real CLI/MCP/JSON/HTTP framing with memory streams and fake HTTP sockets; data/errors/wrappers/exits must agree. Adapter integration pending. |
| A28 | `test_bootcheck.BootcheckOracle.test_a28_bootcheck_passive_directives_have_no_write_or_execution_effect`<br>`test_entry.EntryOracle.test_a28_a30_builder_is_pure_and_never_executes_directives`<br>`test_route.RouteOracle.test_a28_reads_leave_bytes_unchanged_and_never_execute_passive_text` | No execution, network, ledger or projection effects from passive directives; effects fail. |
| A29 | `test_bootcheck.BootcheckOracle.test_a29_expected_results_do_not_alias`<br>`test_entry.EntryOracle.test_a29_episode_null_cost_and_workflow_null_reward_are_preserved`<br>`test_generations.GenerationOracle.test_a29_generation_mapping_does_not_alias_future_results`<br>`test_route.RouteOracle.test_a29_nested_results_are_defensive_and_unknown_costs_remain_null` | Nested result/issue mutations and null costs cannot corrupt authority; aliasing or measured-zero fabrication fails. |
| A30 | `test_entry.EntryOracle.test_a28_a30_builder_is_pure_and_never_executes_directives`<br>`test_memory_resume.MemoryResumeOracle.test_a30_admission_is_pure_under_lock_and_publication_follows_unlock`<br>`test_memory_resume.MemoryResumeOracle.test_a30_concurrent_same_prefix_publications_are_serialized` | Locked pure admission, publication after unlock and concurrent rebuilds; nested writes or unsynchronized state fail. |
| A31 | `test_memory_resume.MemoryResumeOracle.test_a31_byte_refusal_mutant_causes_assertion_failure`<br>`test_memory_resume.MemoryResumeOracle.test_a31_manifest_only_mutant_causes_assertion_failure`<br>`test_memory_resume.MemoryResumeOracle.test_a31_missing_evidence_mutant_causes_assertion_failure`<br>`test_memory_resume.MemoryResumeOracle.test_a31_privacy_mutant_causes_assertion_failure`<br>`test_memory_resume.MemoryResumeOracle.test_a31_rank_mutant_causes_assertion_failure`<br>`test_memory_resume.MemoryResumeOracle.test_a31_token_refusal_mutant_causes_assertion_failure` | In-memory mutants must produce assertion failures, never import/stub errors. Mutation receipts remain pending until implementation. |
| A32 | `test_memory_resume.OracleStructure.test_a32_every_numbered_acceptance_has_an_explicit_mapping`<br>`test_memory_resume.OracleStructure.test_a32_imports_are_stdlib_or_project_and_package_discovery_is_closed` | Every acceptance is mapped, discovery is closed and imports are stdlib/project-only; unmapped/extra dependencies fail. Host scope comparison is a separate author gate. |

## Amendment B and unresolved specification choices

| Item | Oracle treatment |
|---|---|
| B1 exact Markdown template | AUSENTE: no exact header/fence/blank-line template is supplied. Require all header values, canonical complete unit records, id order, LF, final LF and independent hashes. Do not freeze invented bytes. Cross-implementation digest equivalence remains pending a normative template. |
| B2 exact cuts/truncation | AUSENTE: no selected ordering or truncation grammar is supplied. Require permutation-stable diagnostics, budget identification, eligible ids, the wire bound and an explicit bounded-list notice. Do not force the example ordering. |
| B3 private unit retention | AUSENTE: amendment asks to choose but does not choose. Public fixtures enforce complete active units and canonical JSON plus LF. A private fixture requires one reproducible retention policy across generations; recall excludes private units. Deterministic private-file retention policy remains pending. |
| B4 historical inputs/generation | Birth counts as `gen/1` because g counts selected committed events from birth. Require prefix-derived historical versions and supersession. Contradictory inputs may use either named `bad_args` or `bad_op` until one is frozen. |
| B5 receipt scope/root | AUSENTE: no choice of permitted root or private/historical receipt scope. Required active eligible level-two receipts are tested; identical fixtures are supplied beneath both `home` and `repo_root`, so no unchosen root is blessed. Required-receipt deletion/corruption/symlink attacks affect both. Broader scope/root distinction remains pending. |
| B6 counter provenance | Services construction owns provenance. Injected deterministic counter doubles have no invented certification attribute and do not certify production tokenizer compatibility. `None`, exceptions and invalid return values fail closed. Real verified-counter receipt: AUSENTE. |
| B7 custom limits | Either clamping or the specified argument/debt refusal is permitted when ceilings are raised; an over-ceiling result can never pass. Invalid nonpositive/bool/noninteger limits refuse with `bad_args` or `memory_debt`. Exact in-range limits remain independently tested. |
| B8 verifier issue codes | Require closed relative issues with the stated fixed vocabulary (`hash_mismatch`, `bad_args`, `internal`) and no empty success for damage. A per-class choice remains AUSENTE; the oracle does not invent it. Bootcheck itself retains its exact required codes/prefix. |
| B9 ledger integrity | Rely on verified committed Snapshot guarantees; no second reader/fold is created. Real shared reads must reject complete corruption and preserve the committed prefix across a torn final suffix. Unavailable K0 read/fold is an integration failure. |
| B10 hostile additions | Same-op retry after rejected admission, mirror divergence, NUL/duplicate-key/non-finite/invalid-UTF8 input, operator actor isolation and hostile language path components have explicit tests. Invalid workflow validation belongs to frozen schema/admission, never filesystem path construction. |

A MemoryUnit has no owner field. `provenance.actor` is not its owning target.
Routing tests establish ownership through `memory.put.payload.agent_id` and the
real U10 fold; entry tests use caller-supplied target units rather than inventing
an owner field. The memory-root location beneath home is discovered from rebuild's
returned `CURRENT` artifact; an unspecified `agents/<id>` home layout is not frozen.

## Integration and evidence limits

The extracted copy has legacy `lineage/core/registry.py`,
`lineage/core/journal.py`, `lineage/core/errors.py` and `lineage/core/app.py`.
Frozen `Registry`, `Snapshot`, `Services`, `Context`, `Command`, `LineageError`,
`journal.snapshot`, `journal.transact`, `journal.fold`, `app.dispatch`,
`lineage/core/schema.py` and U10's `lineage/domain/memory/fold.py` and
`lineage/domain/memory/units.py` are AUSENTE. The oracle never edits those paths
or adapts to legacy room APIs. Contract-shaped Context/Snapshot fixture holders
only defer prerequisite inspection until a behavioral surface is called; their
state property delegates exclusively to the real K0 fold, or raises an explicit
integration assertion. They cannot fabricate an authoritative state.

A4, A10, A27 and A30 cannot receive integrated passing receipts until their owners
are ready. A27 exercises actual adapter entry points with injected test Services,
in-memory stdio and a fake stdlib HTTP server/socket; it performs no network I/O.
MCP, CLI, JSON and HTTP runtime parity is AUSENTE until this gate really executes.
No UI files are edited. Capsule/AT-SPI/persona evidence is AUSENTE/INCONCLUSIVE;
this oracle makes no persona score or inherited-memory benefit claim.

Dedicated hostile tests substitute the staging directory at the stdlib rename
boundary and replace required receipts immediately after their bytes are read.
They require that those boundaries were actually reached. Fault hooks cover both
path and descriptor I/O without freezing private U11 helper names. These tests
still have no implementation receipt: the current stubs fail before publication.

No dependencies, external services, models, downloads, clocks, real sleeps, process
signals or process groups are used by the U11 suite. Bounded thread barriers use
explicit timeout/refusal checks. Negative controls patch functions in memory only;
frozen source tests and implementation files are never rewritten by a test.

## Amendment B test inventory

| Item | Representative test names |
|---|---|
| B1 | `test_entry.EntryOracle.test_a01_deterministic_complete_sorted_passive_bytes`; `test_bootcheck.BootcheckOracle.test_a19_positive_uses_actual_artifacts_and_independent_ledger_values` |
| B2 | `test_entry.EntryOracle.test_a02_cuts_are_deterministic_and_do_not_mutate_units`; `test_entry.EntryOracle.test_a02_long_cut_diagnostic_is_bounded_and_explicit` |
| B3 | `test_generations.GenerationOracle.test_b03_private_file_policy_is_consistent_and_reproducible` |
| B4 | `test_generations.GenerationOracle.test_a06_birth_is_generation_one_and_episode_is_not_memory_gen`; `test_generations.GenerationOracle.test_a07_historical_versions_and_supersession_are_not_copied_backward`; `test_generations.GenerationOracle.test_b04_contradictory_agent_inputs_are_refused`; `test_generations.GenerationOracle.test_b04_contradictory_unit_inputs_are_refused` |
| B5 | `test_bootcheck.BootcheckOracle.test_a22_receipt_delete`; `test_bootcheck.BootcheckOracle.test_a22_receipt_corrupt`; `test_bootcheck.BootcheckOracle.test_a22_receipt_symlink`; `test_bootcheck.BootcheckOracle.test_a19_no_required_receipt_is_invented_for_level_three` |
| B6 | `test_entry.EntryOracle.test_a03_counter_missing`; `test_entry.EntryOracle.test_a03_counter_exception`; `test_entry.EntryOracle.test_a03_counter_bool`; `test_entry.EntryOracle.test_a03_counter_negative`; `test_entry.EntryOracle.test_a03_counter_float`; `test_bootcheck.BootcheckOracle.test_a03_counter_missing` |
| B7 | `test_entry.EntryOracle.test_b07_production_ceiling_max_bytes`; `test_entry.EntryOracle.test_b07_production_ceiling_max_tokens`; `test_entry.EntryOracle.test_b07_max_bytes_zero`; `test_entry.EntryOracle.test_b07_max_bytes_negative`; `test_entry.EntryOracle.test_b07_max_bytes_bool`; `test_entry.EntryOracle.test_b07_max_tokens_zero`; `test_entry.EntryOracle.test_b07_max_tokens_negative`; `test_entry.EntryOracle.test_b07_max_tokens_bool` |
| B8 | `test_projection_safety.ProjectionSafetyOracle.test_a12_missing_entry`; `test_projection_safety.ProjectionSafetyOracle.test_a12_extra_file`; `test_projection_safety.ProjectionSafetyOracle.test_a12_entry_mirror`; `test_projection_safety.ProjectionSafetyOracle.test_a12_forged_manifest`; `test_projection_safety.ProjectionSafetyOracle.test_a13_symlink_pointer` |
| B9 | `test_route.RouteOracle.test_a25_corrupt_complete_ledger_is_not_empty`; `test_route.RouteOracle.test_a25_unavailable_snapshot_is_internal_not_empty`; `test_route.RouteOracle.test_a25_torn_final_suffix_does_not_erase_committed_memory` |
| B10 | `test_memory_resume.MemoryResumeOracle.test_a04_overflow_before_append_then_same_operation_can_commit`; `test_bootcheck.BootcheckOracle.test_a22_entry_mirror_corrupt`; `test_projection_safety.ProjectionSafetyOracle.test_b10_current_nul`; `test_projection_safety.ProjectionSafetyOracle.test_b10_current_duplicate_json`; `test_projection_safety.ProjectionSafetyOracle.test_b10_current_nan`; `test_projection_safety.ProjectionSafetyOracle.test_b10_current_infinity`; `test_memory_resume.MemoryResumeOracle.test_b10_strict_wire_decoder_rejects_duplicate_nonfinite_and_nul_inputs`; `test_memory_resume.MemoryResumeOracle.test_b10_operator_read_cannot_create_a_level_one_write`; `test_route.RouteOracle.test_a17_read_actor_operator_does_not_widen_target_scope`; `test_projection_safety.ProjectionSafetyOracle.test_a13_hostile_scope_never_forms_filesystem_components`; `test_projection_safety.ProjectionSafetyOracle.test_b10_hostile_workflow_never_forms_a_path` |

## Host execution receipt

The required discovery command ran 242 tests [MEASURED] in 0.342 seconds
[MEASURED]: 240 behavioral errors [MEASURED], all exactly
`NotImplementedError: U11 stub`; 2 structural checks passed [MEASURED].
No import/setup errors, assertion failures or skips were observed [MEASURED].
Exact unittest result: `FAILED (errors=240)`.
This is the expected fail-first receipt, not implemented U11 acceptance.

Existing regression command:
`python3 -m unittest discover -s tests/core/regression -t .`
returned `Ran 1604 tests in 281.660s` and `OK` [MEASURED].
The frozen regression manifest checks all 92 recorded files unchanged [MEASURED].
Interrupted regression runtime homes were removed; no `.runtime-*` fixture debris
remains [MEASURED]. No production counter, adapter or persona success is claimed.


## Amendments A-U11

- `tests/memory/store/__init__.py`, `OracleCase.seed_ledger`: create the
  integrated journal's stable `events.lock` next to independently seeded
  `events.jsonl`. This fixture plumbing satisfies the integrated journal API's
  locking precondition (A-K0-9); ledger/event bytes and behavioral assertions
  are unchanged.

- `tests/memory/store/test_memory_resume.py`, `transaction_context`: provide the
  pending agents-fold prerequisite through the integrated Registry/FoldSpec API,
  as U10 admission requires `state.agents`. Birth/status fixture data and the
  real U10 memory counters determine that prerequisite. U12 admission is not
  claimed. Real U10 validators, transactions, entry admission, U11 publication
  and every behavioral assertion remain in place.

- `OracleCase.setUp` and the A27 endpoint fixture use owner-controlled runtime
  directories and config-file permissions required by integrated family mailbox
  admission, independently of the host umask. Request contents and parity
  assertions are unchanged.

- `MemoryResumeOracle.command` prefixes synthetic operation IDs to satisfy the
  integrated native journal's operation-identity length. Same-operation retries
  still reuse identical IDs and all replay/admission assertions are unchanged.

- `MemoryResumeOracle.http_results`: adapt HTTP's `decode(raw, max_bytes=...)`
  call to integrated `schema.decode(raw)` in the transport fixture. The helper
  enforces the exact supplied byte cap and delegates strict parsing unchanged.
  HTTP request handling, shared dispatch, results, codes and parity assertions
  remain real and unchanged. Production HTTP decoder compatibility is owned by
  the HTTP integration unit, not certified by this fixture adapter.

- `MemoryResumeOracle.http_results` restores imported HTTP, session, static and
  fixture module/package bindings at teardown. This isolates its integrated
  API fixture from later tests that install their own adapter prerequisites;
  it changes no request, result or behavioral assertion.

- `MemoryResumeOracle.http_results` injects its fake socket server at the
  integrated `http._Server` factory rather than patching the inherited
  `HTTPServer.__new__` allocator. This prevents allocator leakage into later
  real-server tests while exercising the same real HTTP handler and assertions.

- `MemoryResumeOracle.test_a26_registry_load_has_one_owner_and_read_effects`:
  A-U11 adapts the read-effect assertion on Registry-copied ToolSpec records to
  the integrated `mutating` field (`False`). Native Registry copies omit the
  facade-only `effect` attribute. The exact inventory, handler identity and
  nonmutation requirement are unchanged.

- `MemoryResumeOracle.http_results`: A-U11 constructs integrated HTTP's own
  `Context` and `_Services` with the native `app.create_context` result, matching
  `http.main` plumbing. The real HTTP handler and shared dispatch still process
  every request; all canonical-result and error assertions remain unchanged.

- Added `tests/memory/store/review_h2/test_review_h2.py` and its package marker
  for provider-refresh regression coverage. These assert post-commit publication,
  exact replay, read defaults, missing-target errors and bootcheck diagnostics
  after the integrated U10 transport provider refreshes. The existing closed
  top-level oracle inventory and its assertion remain unchanged.
