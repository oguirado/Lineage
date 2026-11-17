# Excluded regression candidates

Measured discovery: 1817 distinct outcomes, of which 1604 selected IDs are green [MEASURED]. Every measured exclusion appears below. An import failure is a module placeholder, not a passing or absent test.

| Reason class | Measured IDs excluded |
|---|---:|
| `hook_observer_excluded` | 23 [MEASURED] |
| `in_flight_unit` | 81 [MEASURED] |
| `out_of_scope_module` | 42 [MEASURED] |
| `red_in_seed` | 67 [MEASURED] |

`red_in_seed`: existing assertion failures, errors, or missing-fixture import errors. `in_flight_unit`: hook hardening unit, excluded before extraction. `out_of_scope_module`: external installer, client-configuration and docs/adapter setup. `hook_observer_excluded`: optional hooks and wall observer.

Excluded source modules: `bridge/room/hook.py`, `bridge/room/hook_claude.py`, `bridge/room/observer.py`. They are not copied.

| Seed test ID | Seed outcome | Reason class |
|---|---|---|
| `bridge.tests.room.test_hook.Hook.test_default_agent_and_room_from_cwd` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_hook.Hook.test_errors_go_to_log_never_stdout` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_hook.Hook.test_garbage_stdin_exits_zero_silently` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_hook.Hook.test_items_and_text_key_for_other_tools` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_hook.Hook.test_log_is_capped_at_256_kib` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_hook.Hook.test_new_session_posts_new_plan` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_hook.Hook.test_non_plan_tool_ignored` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_hook.Hook.test_plan_then_steps` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_observer.Observer.test_called_with_keywords_only_compatible` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_observer.Observer.test_cursor_does_not_advance_on_falsy` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_observer.Observer.test_cursor_per_room` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_observer.Observer.test_emits_each_event_once_with_expected_kwargs` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_observer.Observer.test_failure_midway_keeps_order_and_earlier_cursor` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_observer.Observer.test_glob_limits_rooms` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_observer.Observer.test_malformed_and_torn_lines_skipped_once` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_observer.Observer.test_new_room_appearing_later_is_picked_up` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_observer.Observer.test_real_emit_signature_is_compatible` | `error` | `hook_observer_excluded` |
| `bridge.tests.room.u119.test_replay_protocol.ReplayOracle.test_a6_acquire_replay_survives_foreign_reclaim_without_renewal` | `failure` | `red_in_seed` |
| `bridge.tests.room.u119.test_replay_protocol.ReplayOracle.test_a6_acquire_replay_uses_committed_prefix_after_plan_close` | `failure` | `red_in_seed` |
| `bridge.tests.room.u119.test_replay_protocol.ReplayOracle.test_a6_acquire_restart_lost_reply_after_progress_returns_original` | `failure` | `red_in_seed` |
| `bridge.tests.room.u119.test_replay_protocol.ReplayOracle.test_a6_historical_acquire_replay_does_not_renew_authority` | `failure` | `red_in_seed` |
| `bridge.tests.room.u119.test_replay_protocol.ReplayOracle.test_a6_report_replay_survives_release_and_foreign_reclaim` | `failure` | `red_in_seed` |
| `bridge.tests.room.u119.test_replay_protocol.ReplayOracle.test_a6_report_replay_uses_committed_prefix_after_plan_close` | `failure` | `red_in_seed` |
| `bridge.tests.room.u119.test_replay_protocol.ReplayOracle.test_a6_report_restart_after_progress_and_evidence_deletion` | `failure` | `red_in_seed` |
| `bridge.tests.room.u133.test_boundaries.BoundaryOracle.test_amendment_c_exact_exported_signature` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_boundaries.BoundaryOracle.test_m6_documents_wait_only_deadline_and_non_posix_limit` | `failure` | `in_flight_unit` |
| `bridge.tests.room.u133.test_boundaries.BoundaryOracle.test_m8_documented_json_fixtures_cover_all_four_states` | `failure` | `in_flight_unit` |
| `bridge.tests.room.u133.test_boundaries.BoundaryOracle.test_m8_documents_commands_home_replay_cleanup_and_identity_trust` | `failure` | `in_flight_unit` |
| `bridge.tests.room.u133.test_boundaries.BoundaryOracle.test_m8_public_documentation_excludes_local_identity_and_paths` | `failure` | `in_flight_unit` |
| `bridge.tests.room.u133.test_boundaries.BoundaryOracle.test_m8_transitive_import_graph_has_no_provider_clients` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_a2_failed_releases_owned_unfinished_work_and_preserves_payloads` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_a2_finished_releases_without_completing_or_cancelling` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_a3_delayed_replay_does_not_release_reclaimed_work` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_a3_interrupted_after_commit_replays_cleanup_once` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_a3_interrupted_after_one_release_resumes_remaining_only` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_a3_reopened_plan_reusing_task_ids_is_not_released` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_a3_successor_run_skips_old_cleanup` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_amendment_b_both_terminal_states_exclude_done_cancelled` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_amendment_b_no_stale_retry_at_or_below_remaining_budget` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_amendment_b_stale_revision_has_at_most_three_retries` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_amendment_c_claim_at_or_after_terminal_blocks_that_task` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_amendment_c_opened_at_or_after_terminal_blocks_cleanup` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_m4_current_projection_omits_since_rev_and_uses_subject_slug` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_m4_deployed_alive_do_not_attempt_cleanup` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_m4_no_plan_does_not_turn_persisted_terminal_into_failure` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_m5_claimed_by_other_is_not_retried` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_m5_missing_claim_or_revision_never_substitutes_default` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_m5_missing_generation_or_lifecycle_evidence_blocks_cleanup` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_m5_null_bool_or_invalid_fence_evidence_never_passes` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_m5_race_after_projection_read_is_protected_by_claim_fence` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_m5_release_id_contains_captured_generation_and_claim` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_m5_reopened_plan_after_read_cannot_release_reused_task` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_m5_revalidate_generation_owner_claim_and_run_before_release` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_m5_same_run_wrong_lifecycle_skips_cleanup` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_m5_stale_revision_retries_with_current_rev_and_same_claim` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_cleanup.CleanupOracle.test_m6_expired_budget_stops_before_next_mutation` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_controls.ControlOracle.test_a6_claim_fence_omission_mutant_is_detected_after_read_race` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_controls.ControlOracle.test_a6_cleanup_omission_mutant_is_detected` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_controls.ControlOracle.test_a6_infrastructure_failure_is_never_mutant_detection` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_controls.ControlOracle.test_a6_unstable_id_mutant_is_detected_after_throttle_window` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_controls.ControlOracle.test_hardening_200_events_fixed_clock_growth_and_cleanup` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_a1_claude_lifecycle_delegates_equivalent_fixture` | `failure` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_a1_neutral_without_claude_environment_and_cross_process_replay` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_a4_events_lock_deadline_is_baseexception_and_no_late_mutation` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_a4_incomplete_stdin_deadline_has_no_surviving_worker` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_a4_missing_room_is_silent_and_is_not_created` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_a5_denied_network_and_process_creation_still_allows_metadata` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_amendment_b_claude_lifecycle_bypasses_hook_state_lock` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_m3_distinct_processes_have_identical_utf8_ids` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_m6_deadline_never_interrupts_dispatch_write` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_m6_import_budget_exhaustion_blocks_dispatch` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_m6_malformed_and_oversized_input_are_silent` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_m6_parse_exhaustion_blocks_dispatch` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_m6_silence_for_capacity_contention_and_internal_failures` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_m7_default_todo_mirroring_preserves_plan_then_step` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_entries.EntryOracle.test_m7_todo_data_cannot_fabricate_lifecycle_identity` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_integration.IntegratedOracle.test_a1_real_journal_deploy_and_cross_process_adapter_replay` | `skip` | `in_flight_unit` |
| `bridge.tests.room.u133.test_integration.IntegratedOracle.test_a2_real_journal_failed_cleanup_matches_plan_get` | `skip` | `in_flight_unit` |
| `bridge.tests.room.u133.test_integration.IntegratedOracle.test_a2_real_undeployed_failure_never_appends_or_releases` | `skip` | `in_flight_unit` |
| `bridge.tests.room.u133.test_integration.IntegratedOracle.test_a5_real_hostile_metadata_persists_with_sockets_denied` | `skip` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_a1_exact_dispatch_and_receipt_without_plan` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_a5_conflicting_event_id_state_and_content_reuse_is_rejected` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_a5_hostile_reason_is_passive_and_not_prompted` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_a5_invalid_utf8_and_unencodable_surrogates_never_dispatch` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_a5_one_object_only_and_strict_json` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_a5_rejects_duplicate_keys_at_every_depth_before_dispatch` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_a5_unknown_keys_and_payload_paths_never_dispatch` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_amendment_c_optional_character_limits_and_literal_values` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_amendment_c_optional_fields_are_nonempty_strings` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m1_byte_limit_plus_one_never_dispatches` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m1_event_identity_is_validated_before_it_is_removed` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m1_exact_byte_limit_is_accepted` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m1_explicit_identity_wins_over_harness_environment` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m1_no_identity_from_environment_or_working_directory` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m1_required_values_must_be_nonempty_strings` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m2_dispatch_errors_preserve_codes_and_details` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m2_invalid_lifecycle_retains_bad_op` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m2_invalid_slugs_keep_shared_error_codes` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m2_undeployed_termination_retains_detail_and_never_cleans` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m2_unexpected_exception_uses_existing_internal_code` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m3_alive_replay_after_window_is_not_a_new_identity` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m3_alive_throttling_is_delegated_not_cached_by_hook` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m3_identical_retry_preserves_original_lamport` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m3_utf8_canonical_id_and_no_input_mutation` | `green` | `in_flight_unit` |
| `bridge.tests.room.u133.test_protocol.ProtocolOracle.test_m8_socket_denial_permits_local_dispatch` | `green` | `in_flight_unit` |
| `bridge.tests.room.u137.test_contract.CoordinationTemplates.test_a2_beats_retired_runs_and_takeover_rule` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.CoordinationTemplates.test_a2_coordinator_reads_plans_assigns_routes_and_reconciles` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.CoordinationTemplates.test_a2_discover_prompts_before_get_and_version_fallback_copies` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.CoordinationTemplates.test_a2_executor_claims_before_editing_and_keeps_identity` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.CoordinationTemplates.test_a2_manual_activation_and_unknown_native_triggers` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.CoordinationTemplates.test_a5_interpolated_text_and_untrusted_results_are_passive` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.LifecycleFallback.test_a4_bookkeeping_tokens_and_limited_c1_coverage` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.LifecycleFallback.test_a4_explicit_enablement_and_r39_exception` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.LifecycleFallback.test_a4_fallback_provenance_is_agent_reported` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.LifecycleFallback.test_a4_graceful_release_and_abrupt_kill_limit` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.LifecycleFallback.test_a5_hook_fallback_same_run_collision_stop_rule` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.LifecycleFallback.test_a6_missing_template_is_not_a_detected_mutant` | `green` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.LifecycleFallback.test_a6_provenance_mutant_is_rejected_after_positive_control` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.NativeGateAndScope.test_a3_conditional_contract_covers_persistence_without_model_calls` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.NativeGateAndScope.test_a3_guide_declares_native_contract_and_automatic_lifecycle_ausente` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.NativeGateAndScope.test_a3_native_replay_failure_release_bound_and_op_id_mutant` | `skip` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.NativeGateAndScope.test_a3_no_adapter_without_public_native_contract` | `green` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.NativeGateAndScope.test_a5_caller_asserted_identity_and_same_user_boundary` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.NativeGateAndScope.test_a5_public_artifacts_contain_no_operator_or_secret_leaks` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.RegistrationDocumentation.test_a1_live_compatibility_receipts_cannot_be_inferred` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.RegistrationDocumentation.test_a1_raw_config_navigation_and_manual_preservation` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.RegistrationDocumentation.test_a1_tasklight_registration_is_separate_from_firebase` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_contract.RegistrationDocumentation.test_a1_unknown_client_capabilities_are_ausente` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_protocol.FallbackMcpIntegration.test_a1_required_lifecycle_capability_is_discovered_before_use` | `green` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_protocol.FallbackMcpIntegration.test_a4_deploy_alive_and_truthful_finish_without_plan` | `green` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_protocol.FallbackMcpIntegration.test_a4_observed_failure_carries_agent_reported_origin` | `green` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_protocol.FallbackMcpIntegration.test_a4_retry_identity_does_not_duplicate_mutations` | `green` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_protocol.FallbackMcpIntegration.test_a5_invalid_lifecycle_state_and_room_append_nothing` | `green` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_protocol.FallbackMcpIntegration.test_a5_valid_reason_is_data_and_does_not_execute` | `green` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_protocol.IndependentLifecycleStop.test_a4_abrupt_kill_expires_to_unknown_without_fabricated_failed` | `skip` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_protocol.LegacyMcpBoundaries.test_a1_initialize_and_discover_coordination_prompts` | `green` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_protocol.LegacyMcpBoundaries.test_a2_versioned_templates_retain_discovered_u111_prompt_text` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_protocol.LegacyMcpBoundaries.test_a5_hostile_prompt_brief_stays_passive_without_mutation` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_protocol.LegacyMcpBoundaries.test_a5_malformed_json_is_rejected_without_append_and_stream_recovers` | `green` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_protocol.LegacyMcpBoundaries.test_a5_traversal_room_is_rejected_without_storage_escape` | `green` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_protocol.LegacyMcpBoundaries.test_a5_unknown_tool_is_not_a_lifecycle_transition` | `green` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_registration.LauncherExamples.test_a1_documented_launcher_initializes_and_discovers_offline` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_registration.LauncherExamples.test_a1_launcher_preserves_unrelated_and_malformed_configurations` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_registration.LauncherExamples.test_a1_registration_json_has_only_public_command_and_args` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_registration.LauncherExamples.test_a5_launcher_never_interpolates_event_text_into_shell` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_registration.LauncherExamples.test_a5_launcher_quotes_hostile_configured_paths` | `failure` | `out_of_scope_module` |
| `bridge.tests.room.u137.test_registration.LauncherExamples.test_a5_quoting_probe_keeps_unsafe_expansions_visible` | `green` | `out_of_scope_module` |
| `bridge.tests.room.u69.test_contract.Contract.test_a2_ascii_locale_roundtrips_memory` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_a4_phase_to_design_single_op_and_envelope` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_a4_stale_phase_rejected_without_write` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_a4_unknown_phase_rejected_without_write` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_a4_zero_phase_revision_is_stale` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_a5_close_with_passive_unicode_outcome` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_a5_close_without_optional_outcome` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_a6_other_agent_claim_is_never_returned` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_a6_own_claim_precedes_lower_id_unassigned_task` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_a7_demo_accepts_both_identity_literals` | `error` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_m3_close_empty_outcome_is_valid` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_m3_close_replay_does_not_duplicate_archive` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_m3_close_stale_revision` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_m3_hostile_arguments_are_rejected_atomically` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_m3_missing_base_revision_cannot_write` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_m3_phase_op_id_replay_is_single_write` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_m4_filter_ownership_before_limit` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_m4_invalid_limits_remain_rejected` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_m4_readiness_and_terminal_states_preserved` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_contract.Contract.test_m6_first_phase_injection_preserved` | `failure` | `red_in_seed` |
| `bridge.tests.room.u69.test_repair1.Repair1.test_dense_dependencies_complete_with_reference_result` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_a2_plan_create_starts_in_brief` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_a2_runtime_lists_autonomous_software` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_a3_missing_not_listed_and_not_found` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_a3_resource_exact_shipped_text` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_a3_resource_list_shape_and_uniqueness` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_a4_bad_room_rejected` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_a4_prompt_list_exact_order_and_schema` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_a4_room_agent_final_line` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_a4_shipped_prompt_exact_fenced_text` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_a5_shipped_prompt_at_most_250_words` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m3_empty_utf8_file_is_available` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m3_invalid_utf8_not_found` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m3_listing_rechecks_after_removal` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m3_one_byte_over_limit_not_found` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m3_reads_latest_bytes_each_call` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m3_size_limit_inclusive_utf8_bytes` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m4_agent_injection_rejected` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m4_bad_agent_rejected` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m4_extraction_uses_only_marked_fence` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m4_legacy_prompt_descriptors_unchanged` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m4_missing_end_marker_contract_unavailable` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m4_missing_file_contract_unavailable` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m4_missing_start_marker_contract_unavailable` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m4_nonstring_agent_rejected` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m4_nonstring_room_rejected` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m4_omitted_arguments_are_optional` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m4_room_injection_rejected` | `error` | `red_in_seed` |
| `bridge.tests.room.u76.test_contract.ContractOracle.test_m5_plan_from_template_text_unchanged` | `error` | `red_in_seed` |
| `bridge.tests.room.u87.test_contract.ParityOracle.test_a2_list_templates` | `failure` | `red_in_seed` |
| `bridge.tests.room.u87.test_contract.ParityOracle.test_a2_same_dispatcher_for_every_tool` | `failure` | `red_in_seed` |
| `bridge.tests.room.u94.test_contract.Discovery.test_m6_first_import_and_discovery_have_no_filesystem_side_effects` | `failure` | `red_in_seed` |
| `bridge.tests.room.u94.test_contract.ExportContract.test_a1_frozen_cli_call_matches_mcp_when_u87_is_integrated` | `failure` | `red_in_seed` |
| `unittest.loader._FailedTest.bridge.tests.plan.u88.test_dependencies` | `error` | `red_in_seed` |
| `unittest.loader._FailedTest.bridge.tests.plan.u88.test_next_work` | `error` | `red_in_seed` |
| `unittest.loader._FailedTest.bridge.tests.room.u109.test_fold` | `error` | `red_in_seed` |
| `unittest.loader._FailedTest.bridge.tests.room.u132.test_lifecycle` | `error` | `red_in_seed` |
| `unittest.loader._FailedTest.bridge.tests.room.u90.test_activity` | `error` | `red_in_seed` |
| `unittest.loader._FailedTest.bridge.tests.room.u90.test_repair1` | `error` | `red_in_seed` |
| `unittest.loader._FailedTest.bridge.tests.room.u90.test_repair2` | `error` | `red_in_seed` |

| `bridge.tests.room.test_review1.R6HookRaces.test_concurrent_hooks_one_plan_per_session` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_review2.F6HookPermissions.test_existing_logless_room_log_created_private` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_review2.F6HookPermissions.test_invalid_stdin_leaves_only_private_artifacts` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_review2.F6HookPermissions.test_normal_run_private_modes_and_no_temp_files` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_review2.F6HookPermissions.test_refused_post_failure_path_private` | `green` | `hook_observer_excluded` |
| `bridge.tests.room.test_review2.F6HookPermissions.test_umask_zero_run_also_private` | `green` | `hook_observer_excluded` |

## Declarations not individually executable in the seed

222 explicitly declared methods below were outside default discovery or behind a failed import [MEASURED]. They are additional source declarations, not additional measured test results. Dynamic expansion behind unavailable fixture data is AUSENTE — no inventar.

| Declared seed method | Reason class | Evidence limit |
|---|---|---|
| `bridge.tests.plan.u88.test_dependencies.DependencyOracle.test_A2_incremental_cancellation_recomputes_immediately` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.plan.u88.test_dependencies.DependencyOracle.test_A2_clear_override_recomputes_from_pending_with_latest_revision` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.plan.u88.test_dependencies.DependencyOracle.test_A2_op_id_replay_preserves_cancellation_without_extra_revision` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.plan.u88.test_dependencies.DependencyOracle.test_A4_cancellation_preserves_microdata_ownership_revisions_and_progress` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.plan.u88.test_dependencies.DependencyOracle.test_A4_unlocking_never_activates_or_manufactures_liveness` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.plan.u88.test_dependencies.DependencyOracle.test_A4_terminal_dependants_and_empty_dependencies` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.plan.u88.test_next_work.NextWorkOracle.test_A5_cancellation_exposes_exactly_the_dependant_microtask` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.plan.u88.test_next_work.NextWorkOracle.test_A5_blocked_dependant_is_excluded_after_cancellation` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.plan.u88.test_next_work.NextWorkOracle.test_M3_cancellation_exposes_active_dependant_microtasks` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.plan.u88.test_next_work.NextWorkOracle.test_A5_other_owned_dependant_is_excluded_after_cancellation` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.plan.u88.test_next_work.NextWorkOracle.test_A4_cancellation_appends_only_the_requested_event` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.plan.u88.test_next_work.NextWorkOracle.test_M3_owned_before_free_order_limits_and_active_microtasks` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.plan.u88.test_next_work.NextWorkOracle.test_M3_dependency_depth_precedes_task_id_order` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u109.test_fold.FoldOracle.test_m1_conformance_remains_pure_and_does_not_enforce_authority` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u109.test_fold.FoldOracle.test_a6_python_integral_float_is_bad_op` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u109.test_fold.FoldOracle.test_a4_retired_run_cannot_reappear_after_release_and_reclaim` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a1_direct_no_plan_commit` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a1_shared_dispatch` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a1_mcp_tools_call` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a1_cli_call` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a1_discovery_and_extension_loader` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a1_generated_identifier` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a2_orphans_all_transports` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a2_fold_rejects_orphans` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a3_restart_replay_before_after_supersession` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a3_concurrent_duplicate_deliveries` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a3_payload_conflicts_are_not_replays` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a3_room_agent_identity_scope` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a4_activity_fencing_and_assignee_release` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a4_identical_deployed_and_terminal_noops` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a4_retired_run_rejections_and_alive_noop` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a4_unregistered_activity_compatibility` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a4_takeover_predicate_unchanged` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a5_throttle_restart_equality_and_backward_clock` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a5_concurrent_boundary_appends_once` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a5_new_run_resets_alive_evidence` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a5_committed_replay_precedes_current_throttle` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a6_closed_plan_reopen_and_json_continuation` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a6_retirement_order_deduplication_and_churn` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a6_empty_and_older_projection_defaults` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a7_bad_args_shapes_missing_and_unknown` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a7_room_agent_error_codes` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a7_null_wrong_type_and_state_values` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a7_identifiers_full_match_and_boundaries` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a7_reason_scalars_and_label_bounds` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a7_c0_c1_and_surrogate_rejection` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a7_json_safety_and_prototype_keys` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a7_operation_byte_limit_precedence` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a7_literal_metadata_never_executes` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a8_frozen_shared_histories` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a8_disabling_python_fold_fails_frozen_a1_and_a6` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_a8_rejected_transition_preserves_input_and_semantics` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_m7_capacity_noops_and_fsync_failure_keep_journal_contract` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_m8_rejected_identity_is_not_committed` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_m1_unknown_kind_remains_rejected` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u132.test_lifecycle.LifecycleOracle.test_hardening_bounded_burst_correctness_and_ack_recovery` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u5657_repair_test.StoreRepair.test_a_deep_nesting_post_and_post_ops` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u5657_repair_test.StoreRepair.test_b_short_write_post_ops_truncates` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u5657_repair_test.StoreRepair.test_c_batch_replay_different_payload_and_length` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u5657_repair_test.StoreRepair.test_d_individually_posted_not_a_batch` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u5657_repair_test.McpRepair.test_e_template_traversal_rejected` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u5657_repair_test.McpRepair.test_f_evidence_dict_bypass_rejected` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u5657_repair_test.McpRepair.test_g_creation_race_heartbeat_before_lock` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u5657_repair_test.McpRepair.test_h_nullable_schemas` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u5657_repair_test.McpRepair.test_i_deps_nonstring_is_bad_op` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u5657_repair_test.McpRepair.test_j_batch_replay_replacement_keys` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_legacy_compat_test.LegacyCompat.test_all_legacy_acts_golden_bytes_and_read_models` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_legacy_compat_test.LegacyCompat.test_legacy_event_with_op_is_invalid` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_legacy_compat_test.LegacyCompat.test_legacy_plan_rejects_op_before_directories_or_lock` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_legacy_compat_test.LegacyCompat.test_op_rejects_legacy_plan` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_legacy_compat_test.LegacyCompat.test_op_rejects_legacy_step` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_legacy_compat_test.LegacyCompat.test_legacy_explicit_op_none_preserves_wire_bytes` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_concurrency_test.OpConcurrency.test_two_process_revision_race` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_concurrency_test.OpConcurrency.test_claim_guard_and_strict_silence_boundary` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_concurrency_test.OpConcurrency.test_latest_legacy_activity_including_out_of_order_timestamps` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_concurrency_test.OpConcurrency.test_invalid_room_activity_does_not_extend_claim` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_concurrency_test.OpConcurrency.test_already_owned_claim_release_and_unassigned_micro` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_concurrency_test.OpConcurrency.test_micro_updates_parent_task_revision` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_concurrency_test.OpConcurrency.test_task_and_memory_changes_do_not_advance_plan_revision` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_constants` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_all_ten_kinds_persist_canonical_and_fsync` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_no_plan` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_plan_exists` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_unknown_template` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_missing_task` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_missing_dependency` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_task_add_self_cycle` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_transitive_cycle` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_task_limit_and_cancelled_ids_consumed` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_micro_limit` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_replay_after_plan_revision_advanced` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_changed_payload_replays_first_accepted_event` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_cross_agent_id_is_independent_and_omitted_id_never_replays` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_memory_before_plan_and_closed_plan_rules` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_markdown_is_never_authoritative` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_exact_utf8_byte_cap_and_one_over` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_unicode_codepoint_limit_and_ordinary_text` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_reader_valid_op_corrupt_lines_and_torn_tail` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_reader_rejects_contamination_and_hostile_integers` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_room_cap_preserves_file_and_releases_lock` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_batch_success_and_retry_do_not_duplicate_members` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_batch_forward_dependency_resolves_before_commit` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_batch_cycle_is_atomic` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_batch_late_invalid_op_is_atomic` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_batch_strict_conformance_failure_is_atomic` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_batch_strict_conformant_creation_succeeds` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_nested_and_legacy_evidence_remain_independent` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_op_store_test.OpStore.test_batch_capacity_failure_is_atomic` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair1_test.Repair1.test_item1_task_set_forward_dep_persisted_eq_validated` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair1_test.Repair1.test_item2_batch_retry_returns_all_members_and_member_alone_never_replays` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair1_test.Repair1.test_item3_unsafe_integer_writer_and_reader` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair1_test.Repair1.test_item4_surrogate_text_rejected_as_bad_op_and_invalid_event` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair1_test.Repair1.test_item5_strict_via_templates_injection` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair1_test.Repair1.test_item5_runtime_templates_no_fixture_coupling` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair3_test.Repair3.test_1_reordered_batch_retry_identity` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair3_test.Repair3.test_2_stale_base_rev_not_healed` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair3_test.Repair3.test_3_reopen_batch_task_ids_reset` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair3_test.Repair3.test_4_fsync_failure_not_acknowledged` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair4_test.Repair4.test_a_single_then_batch_conflicts` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair4_test.Repair4.test_b_duplicate_member_conflicts` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair4_test.Repair4.test_b_nonfirst_stored_member_conflicts` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair4_test.Repair4.test_c_reordered_batch_cannot_replay_as_single` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair4_test.Repair4.test_batch_member_identity_replays_batch` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair4_test.Repair4.test_agent_identity_is_independent` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair4_test.Repair4.test_non_strict_missing_archived_template_uses_fallback` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair4_test.Repair4.test_strict_missing_template_fails_closed` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair4_test.Repair4.test_strict_missing_conformance_fails_closed` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair4_test.Repair4.test_strict_missing_archived_template_fails_closed` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair4_test.Repair4.test_strict_merges_runtime_and_injected_templates` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair4_test.Repair4.test_strict_runs_conformance` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair4_test.Repair4.test_strict_nonconformance_is_not_appended` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u56_repair4_test.Repair4.test_surrogate_text_is_room_error_before_directory_creation` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.IdentityOracle.test_01_initialize` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.IdentityOracle.test_01_golden_legacy_schemas` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.IdentityOracle.test_01_twenty_tools_and_amended_schemas` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HappyOracle.test_02_templates_and_hash` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HappyOracle.test_02_all_edit_tools_and_entity_revisions` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HappyOracle.test_02_next_work_dependencies` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HappyOracle.test_02_evidence_hash_and_persisted_mapping` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HappyOracle.test_02_memory_before_plan_and_entity_revision` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ResourceOracle.test_03_resources_and_discovery_are_read_only` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ResourceOracle.test_03_missing_resources_and_invalid_uris` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ResourceOracle.test_03_prompts_and_fences` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ResourceOracle.test_08_canaries_only_inside_complete_envelopes` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_04_no_plan` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_04_plan_exists` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_04_unknown_template` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_04_bad_template` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_04_bad_op` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_04_not_found` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_04_stale_rev` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_04_dep_cycle` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_04_claimed_by_other` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_04_limit_exceeded` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_04_not_conformant` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_07_advisory_and_deterministic_findings` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_07_strict_conforming_creation` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_04_missing_and_duplicate_dependencies` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ErrorOracle.test_04_required_revisions_and_forbidden_keys` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ReplayOracle.test_05_task_add_replay_and_agent_scope` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ReplayOracle.test_05_memory_replay_ignores_changed_payload` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ReplayOracle.test_05_batch_retry_and_no_op_id_runs_normally` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.ReplayOracle.test_06_takeover_strict_boundary_and_legacy_activity` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HostileOracle.test_09_malformed_and_torn_stdio_survives` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HostileOracle.test_09_invalid_identifiers_before_disk` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HostileOracle.test_09_string_caps_unicode_and_micro_limits` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HostileOracle.test_09_evidence_rejections` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HostileOracle.test_09_oversize_canonical_operation` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HostileOracle.test_09_capacity_and_atomic_rejection` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HostileOracle.test_09_required_argument_types_before_disk` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HostileOracle.test_09_nonfinite_values_over_real_stdio` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HostileOracle.test_09_optional_revisions_are_checked_when_supplied` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HostileOracle.test_09_non_json_cyclic_input_fails_without_disk` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_mcp_v2_test.HostileOracle.test_12_no_network_and_stdlib_imports` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_race_test.RaceOracle.test_11_two_process_task_update` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_race_test.RaceOracle.test_11_two_process_memory_set` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u57_race_test.RaceOracle.test_11_two_process_task_claim` | `out_of_scope_module` | Outside the frozen test*.py candidate discovery; unmeasured. |
| `bridge.tests.room.u90.test_activity.SeamTests.test_import_registers_exact_descriptor_without_executing_handler` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.SeamTests.test_extension_imports_only_allowed_dependencies` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.SeamTests.test_unknown_kind_stays_rejected` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.SeamTests.test_a7_calibration_ownership_assertion_fails_on_bypassed_fold` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_a1_real_store_admission_and_unknown_stop` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_a1_real_store_preserves_high_entropy_run_identity` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_a2_exact_response_and_replay_original_committed_clock` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_a2_generated_op_id_and_replay_is_scoped_to_agent` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_a2_altered_replay_returns_original_receipt_and_live` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_a3_non_assignee_no_append` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_a3_unassigned_no_append` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_a3_unknown_task_no_append` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_a3_missing_micro_no_append` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_a3_mismatched_micro_no_append` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_a3_no_plan_no_append` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_a3_closed_plan_no_append` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_a4_tool_exact_arguments_hostile_inputs_no_append` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_m4_unicode_note_boundary_persists_through_real_store` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_a4_passive_note_preserves_semantics` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_m6_real_store_accepts_no_applicable_micro_without_semantic_change` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ToolTests.test_m4_dispatcher_wraps_result_as_untrusted` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ValidatorTests.test_m2_exact_shape_valid_boundaries_unicode_codepoints` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ValidatorTests.test_a4_shape_missing_null_wrong_unknown_dangerous_and_patterns` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.ValidatorTests.test_m2_byte_cap_precedence_and_json_safety` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.FoldTests.test_a2_full_incremental_json_roundtrip_and_replay` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.FoldTests.test_a3_authority_is_enforced_inside_fold` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.FoldTests.test_a5_opaque_runs_retire_after_json_roundtrip` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.FoldTests.test_a5_task_guards_retire_all_active_runs_and_preserve_other_task` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.FoldTests.test_a5_leave_active_completion_block_cancel_release_reassignment` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.FoldTests.test_a5_omitted_micro_only_currently_active_children` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.FoldTests.test_m6_no_applicable_micro_is_success_without_semantic_change` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.FoldTests.test_m5_microtask_set_keeps_existing_unassigned_authority` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_activity.FoldTests.test_a7_ownership_negative_control_is_rejected_by_oracle` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_repair1.RepairActivityTests.test_superseded_run_cannot_poison_new_sibling` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_repair1.RepairActivityTests.test_supersession_retires_live_on_untargeted_sibling` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_repair1.RepairActivityTests.test_task_lifecycle_retires_runs_for_future_siblings` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_repair1.RepairActivityTests.test_close_retires_at_task_scope` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_repair1.RepairActivityTests.test_release_retires_run_even_after_microtask_left_active` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_repair1.RepairActivityTests.test_retirement_is_bounded_without_readmitting_evicted_runs` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_repair1.RepairActivityTests.test_malformed_receipt_times_do_not_crash_takeover` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_repair1.RepairActivityTests.test_authority_precedes_microtask_lookup` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_repair1.RepairActivityTests.test_notes_reject_c0_del_and_c1_controls` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_repair2.RepairTwoTests.test_saturation_is_reset_only_by_successful_plan_open` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_repair2.RepairTwoTests.test_unsaturated_retired_run_can_be_reused_in_new_plan` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |
| `bridge.tests.room.u90.test_repair2.RepairTwoTests.test_rejection_of_each_kind_preserves_the_input_projection` | `red_in_seed` | Module import failed in seed; individual outcomes AUSENTE — no inventar. |

The dossier also names `tests/unit/u111/test_mcp.py`; that path is absent from the supplied seed (AUSENTE — no inventar). Fixture-dependent imports for the lifecycle, fold and activity units remain blocked; no substitute fixture is invented.

Missing seed prerequisites (AUSENTE — no inventar):

| Blocked surface | Missing seed path or module |
|---|---|
| Dependency/work fixtures | `tests/unit/u88/cases.json` |
| Fold oracle | `tests/unit/u109/cases.json` |
| Lifecycle oracle | `tests/unit/u132/fixtures.json` |
| Activity oracle | `tests/unit/u90/fixture.json` |
| Template/resource setup | `templates/planning/` |
| Observer integration | `bridge.wall.emit` |

The green subset excludes these failed imports rather than creating replacement
fixtures. The declared methods in failed modules are listed separately above;
their individual pass/fail outcomes cannot be inferred from an import error.

Hook exclusions include the hook-only classes `R6HookRaces` and `F6HookPermissions` within mixed review modules. Their store/transport sibling classes are carried unchanged apart from the rename map.

## Retired by U01R

U01R reconciles the frozen extraction candidates with the integrated journal, dispatch, MCP, CLI and inert package initializer. The historical selection and extraction measurements remain unchanged; they are not a claim that the original subset still passes. Every original module has an explicit decision in `tests/core/regression/fixtures/reconciliation.json`.

| Retired module | Selected tests | Reason class | Replacement directory | Reason |
|---|---:|---|---|---|
| `tests/core/regression/family/test_cursors.py` | 6 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room-scoped family/lifecycle/plan delivery is removed; this is not a Lineage mailbox parity claim. |
| `tests/core/regression/family/test_envelope.py` | 88 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room-scoped family/lifecycle/plan delivery is removed; this is not a Lineage mailbox parity claim. |
| `tests/core/regression/family/test_hardening.py` | 1 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room-scoped family/lifecycle/plan delivery is removed; this is not a Lineage mailbox parity claim. |
| `tests/core/regression/family/test_mailbox.py` | 52 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room-scoped family/lifecycle/plan delivery is removed; this is not a Lineage mailbox parity claim. |
| `tests/core/regression/family/test_recovery.py` | 23 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room-scoped family/lifecycle/plan delivery is removed; this is not a Lineage mailbox parity claim. |
| `tests/core/regression/family/test_routing.py` | 27 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room-scoped family/lifecycle/plan delivery is removed; this is not a Lineage mailbox parity claim. |
| `tests/core/regression/room/s0/test_seam.py` | 3 [MEASURED] | `superseded-by-redesign` | `tests/core/dispatch` | Explicit immutable Registry and ToolSpec replace the global extension dispatcher. |
| `tests/core/regression/room/test_cli.py` | 11 [MEASURED] | `superseded-by-redesign` | `tests/core/dispatch` | The call CLI and exits 0/2/3 replace the room verb parser and legacy exits. |
| `tests/core/regression/room/test_mcp.py` | 18 [MEASURED] | `superseded-by-redesign` | `tests/core/dispatch` | Explicit MCP registry/context and shared dispatch replace the legacy fixed room tools. |
| `tests/core/regression/room/test_post.py` | 31 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/test_read.py` | 17 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/test_review1.py` | 8 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/test_review2.py` | 22 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u109/test_protocol.py` | 69 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u110/test_durability.py` | 12 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u110/test_protocol.py` | 10 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u110/test_references.py` | 13 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u110/test_validation.py` | 13 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u119/test_acquire.py` | 27 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u119/test_atomicity.py` | 13 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u119/test_replay_protocol.py` | 13 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u119/test_report.py` | 32 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u119/test_validation.py` | 83 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u121/test_batch.py` | 31 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u121/test_controls.py` | 4 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u121/test_lock.py` | 15 [MEASURED] | `superseded-by-redesign` | `tests/core/journal` | The new deadline lock returns busy/internal LineageError; legacy Windows and batch APIs are absent. |
| `tests/core/regression/room/u121/test_replay.py` | 32 [MEASURED] | `superseded-by-redesign` | `tests/core/journal` | Content-bound journal transactions replace room/activity/send identity namespaces; room-specific calls are removed. |
| `tests/core/regression/room/u121/test_reserve.py` | 28 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u69/test_contract.py` | 6 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u69/test_repair1.py` | 2 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u71/test_lock.py` | 15 [MEASURED] | `superseded-by-redesign` | `tests/core/journal` | The fcntl-only lock and structured errors replace the optional Windows backend and raw OS errors. |
| `tests/core/regression/room/u76/test_repair1.py` | 5 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u87/test_contract.py` | 139 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u87/test_repair1.py` | 8 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u89/test_events.py` | 119 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u89/test_repair1.py` | 6 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u94/test_contract.py` | 26 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u94/test_files.py` | 15 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u94/test_repair1.py` | 9 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u94c/test_cli_export.py` | 3 [MEASURED] | `legacy-feature-removed` | AUSENTE: feature removed | Room/chat/plan-room operations, projections, and fixed planning prompts are outside the redesigned Lineage core. |
| `tests/core/regression/room/u95/test_headless_resource.py` | 7 [MEASURED] | `superseded-by-redesign` | `tests/core/dispatch` | Lineage resources and explicit MCP streams replace the legacy headless resource adapter. |

### Ported and retained modules

| Module | Selected tests | Adaptation |
|---|---:|---|
| `tests/core/regression/plan/test_u55_conformance_md.py` | 21 [MEASURED] | Pure planning assertions retain their integrated module APIs. |
| `tests/core/regression/plan/test_u55_ops_fold.py` | 239 [MEASURED] | Pure planning assertions retain their integrated module APIs. |
| `tests/core/regression/plan/test_u55_repair1.py` | 5 [MEASURED] | Pure planning assertions retain their integrated module APIs. |
| `tests/core/regression/plan/test_u55_repair2.py` | 2 [MEASURED] | Pure planning assertions retain their integrated module APIs. |
| `tests/core/regression/plan/test_u55_template.py` | 223 [MEASURED] | Pure planning assertions retain their integrated module APIs. |
| `tests/core/regression/plan/test_u55_vectors.py` | 36 [MEASURED] | Pure planning assertions retain their integrated module APIs. |
| `tests/core/regression/room/u121/test_durability.py` | 16 [MEASURED] | Fault-injection assertions use the single-event journal transaction; grouped payload is not a legacy multi-event batch API. |

### API reconciliation and coverage limits

- `journal.transact`, `snapshot`, `verify` and `LineageError` replace `post`, `read` and `RoomError`. The durability fixture now writes generic journal events; grouped payloads are one atomic event, not the removed multi-event `post_ops` API. Plan-projection validity becomes hash-chain validity, and error causes are inspected in structured `detail`.
- `locking` replaces `_lock`; the integrated implementation uses `fcntl`, with `busy` or `internal` errors. Legacy Windows-backend assertions are retired, not silently relaxed.
- Explicit `Registry`, `ToolSpec`, `CallContext`, `DispatchResult`, `mcp.main` streams and `cli.main` replace `EXT_DISPATCH`, implicit package exports, the private MCP handler and the legacy room CLI.
- Strict decoding uses the installed `schema.strict_loads` and `envelope.decode` APIs. The installed `envelope.operation_id` still returns `fam-`; the proposed `lin-` envelope and complete mailbox delivery are not certified by this reconciliation. Legacy room envelope configuration depends on removed identity helpers, so those delivery tests are retired.
- The copied pure planning modules still exist. Their selected assertions are retained byte-for-byte apart from an amendment comment; no room integration is recreated.
- Removed support/probe modules belonged exclusively to retired tests. The retained support shares the A-FLK1 immediate-caller sleep guard: only actual stdlib `subprocess`, `threading` and `selectors` globals may sleep; product calls still fail, including callbacks reached through a stdlib frame.
- New regression tests exercise the integrated journal, dispatch transports, strict decoding, and the guard. An injected product-handler sleep must raise through dispatch and produce an execution error; it must never become a successful tool result.
- Historical seed equality is retained as historical evidence. U01R discovery verifies complete module classification, retained IDs, and discovery of all newly added tests. No missing or failed import is converted into a passing test.

### Reconciliation totals

| Decision | Modules | Original selected tests |
|---|---:|---:|
| `PORT` | 7 [MEASURED] | 542 [MEASURED] |
| `superseded-by-redesign` | 7 [MEASURED] | 101 [MEASURED] |
| `legacy-feature-removed` | 34 [MEASURED] | 961 [MEASURED] |

The reconciled suite retains 542 original selected tests and adds 54 regression controls, for 596 tests [MEASURED]. `journal.snapshot` returns a tuple; the durability plumbing converts it to a list for the unchanged persisted-event equality assertion. The manifest seals all retained regression files and this retirement register.
