# U03 journal oracle candidate

This is a test-only candidate, not a certified behavioral fail-first receipt.
No production code, compatibility shim, import stub or dependency is supplied.

## Scope and blockers

Source: `.unit/SPEC.md`, including Amendment B, and the supplied K0 slice;
`docs/CONTRACT.md`, `docs/INTERFACES.md` and `schemas/event.schema.json`
were inspected for conflicting public contracts.

`lineage/core/journal.py`, `lineage/core/locking.py`,
`lineage/core/errors.py` and `lineage/core/schema.py` are absent in this copy.
The existing test tree contains package initializers, with no runnable baseline
cases. U01 frozen regression execution is unavailable. The seed is not a
substitute for the missing extracted core and is never imported by these tests.

Behavioral cases load production modules only when a case executes. An absent
module causes an explicit prerequisite assertion, not an import/collection error.
That assertion is deliberately identified as unavailable behavioral evidence:
it must not be counted as satisfying A37/M26. The body after the assertion
contains the intended public-contract checks; it has not run against production.
No test is skipped or replaced with a permanently false behavioral oracle.

## Contract decisions and unresolved conflicts

- **B1:** a torn tail must contain `line` and `byte_offset`, and either or both
  `byte_length` and `bytes_hex`. Raw `bytes` and other keys are rejected. Both
  permitted representations are checked exactly when present.
- **B2:** fresh missing controlled directories return empty snapshot and a
  nonpassing missing-authority report without creating files. Existing events
  without a lock raise `internal`. A lock-only directory is treated as missing
  events, not as an established empty journal. This last choice is provisional.
- **B3:** the supplied K0 symbol is
  `lineage.core.schema.decode(raw: bytes, *, max_bytes: int = 1048576)` [CITED].
  No alternate decoder or fallback is installed. Its implementation is absent.
- **B4:** the proposed strict-input interpretation accepts exact JSON builtins;
  tuples and numeric/string/object subclasses are rejected. This is a declared
  provisional choice where Amendment B requests a decision. Callback mutations
  must distinguish JSON integer, boolean, float and signed zero content.
- **B5:** malformed caller arguments take precedence over corrupt-history
  failures; new-kind registry lookup follows replay. Lock probes use real
  `fcntl.flock`, including read-only lock descriptors. Fault instrumentation
  asserts it was reached and cannot silently pass through an unused seam.
- **B6:** an empty `LINEAGE_HOME` falls back to the user's `.lineage`, following
  frozen K0. Empty explicit home is rejected. Witness mismatch uses physical
  EOF, including any torn suffix, and the next physical line. Canonicality
  fixtures include alternate Unicode escapes and exponent spelling with a
  semantically matching event digest.

The U03 proposed keyword API and frozen K0's `Command`/`Context` API conflict.
So do verification result keys, structured error details, request-identity
construction, historical-kind admission and operation-id bounds. These are
**unresolved**, not silently reconciled. Cases currently address the explicit
U03 low-level proposal and cannot be declared frozen for integration until the
orchestrator reconciles these interfaces. Operation-id rejection cases use
values malformed under both contracts; no disputed short identity is rejected.
Tests do not require domain implementations, projection writers or transports.

## Test safety and execution

Use only standard-library `unittest`. All runtime homes, authority damage and
sentinel files use temporary directories. Deterministic clocks and ids are used
for expected byte vectors. Independent-process workers communicate by pipes;
there are no fixed sleeps, network calls or process-group operations. Cleanup
uses only recorded owned `multiprocessing.Process` objects with PID greater
than one. Contention uses an immediate attempt or a bounded deadline.

The concurrency workload is the spec's eight writers and sixteen operations
each [TARGET], with a shared bounded collection deadline. Storage and backend
faults are injected at standard-library `os`/`fcntl` seams, not private journal
helpers. Implementation absence prevents exercising those instrumented bodies
or measuring their eventual execution budgets. No backend-specific mutation
site is invented in anticipation of absent source code.

Required command (set `PYTHONDONTWRITEBYTECODE=1` in the environment to avoid
creating bytecode outside this directory):

```sh
python3 -m unittest discover -s tests/core/journal -t .
```

A38's real implementation-copy mutation trials are **unavailable** while the
implementation is absent. The table identifies the rejection probes the trials
must execute. Their presence is not a mutant receipt. No production mutation
or frozen-oracle modification has been performed. Freezing, host queue receipts
and unchanged U01 execution remain orchestrator-owned and unavailable here.

## Acceptance mapping

Names below are relative to the `tests.core.journal` package. A name denotes
an actual test body, not proof that it has reached production behavior.

| Acceptance | Test names | Evidence status |
|---|---|---|
| A1 | `test_isolation.IsolationTests.test_a1_fresh_process_poisoned_planning_and_source_imports` | Behavior unexercised: prerequisite absent |
| A2 | `test_contract.ContractTests.test_a2_missing_and_explicitly_empty_authority`<br>`test_contract.ContractTests.test_a2_explicit_home_precedes_environment`<br>`test_contract.ContractTests.test_a2_environment_then_user_home_and_empty_environment`<br>`test_contract.ContractTests.test_a2_empty_explicit_home_is_bad_args`<br>`test_isolation.IsolationTests.test_a2_existing_events_without_lock_is_internal`<br>`test_isolation.IsolationTests.test_a2_lock_only_directory_is_missing_not_empty_success`<br>`test_isolation.IsolationTests.test_a2_authority_directory_and_permission_errors_are_not_empty` | Behavior unexercised: prerequisite absent |
| A3 | `test_contract.ContractTests.test_a3_independent_unicode_encoding_vector`<br>`test_contract.ContractTests.test_a3_canonical_types_and_unicode_are_not_normalized` | Behavior unexercised: prerequisite absent |
| A4 | `test_contract.ContractTests.test_a4_hostile_input_values_preserve_authority`<br>`test_contract.ContractTests.test_a4_agent_kind_and_operation_arguments`<br>`test_integrity.IntegrityTests.test_a4_missing_or_extra_envelope_fields_and_integer_booleans`<br>`test_integrity.IntegrityTests.test_a4_duplicate_keys_utf8_surrogates_and_nonfinite_stored_values` | Behavior unexercised: prerequisite absent |
| A5 | `test_transactions.TransactionTests.test_a5_generated_values_and_regressing_wall_clock`<br>`test_transactions.TransactionTests.test_a5_invalid_generators_and_collision_do_not_consume_lamport` | Behavior unexercised: prerequisite absent |
| A6 | `test_concurrency.ConcurrencyTests.test_a6_eight_independent_writers_sixteen_operations_each` | Behavior unexercised: prerequisite absent |
| A7 | `test_transactions.TransactionTests.test_a7_prepare_and_validate_share_latest_history_and_final_digest`<br>`test_transactions.TransactionTests.test_a7_invalid_prepared_payload_cannot_use_original_approval` | Behavior unexercised: prerequisite absent |
| A8 | `test_transactions.TransactionTests.test_a8_missing_validator_rejects`<br>`test_transactions.TransactionTests.test_a8_validator_non_none_return_rejects`<br>`test_transactions.TransactionTests.test_a8_domain_error_preserves_code_and_detail`<br>`test_transactions.TransactionTests.test_a8_preparation_contract_and_exception` | Behavior unexercised: prerequisite absent |
| A9 | `test_transactions.TransactionTests.test_a9_input_and_return_values_are_detached`<br>`test_transactions.TransactionTests.test_a9_validator_cannot_repair_its_argument`<br>`test_transactions.TransactionTests.test_a9_equal_python_values_still_detect_json_type_mutation`<br>`test_transactions.TransactionTests.test_a9_preparation_cannot_mutate_draft_or_history` | Behavior unexercised: prerequisite absent |
| A10 | `test_concurrency.ConcurrencyTests.test_a10_gate_stays_inside_fence_through_commit` | Behavior unexercised: prerequisite absent |
| A11 | `test_replay.ReplayTests.test_a11_replay_ignores_changed_state_and_all_hooks`<br>`test_replay.ReplayTests.test_a11_original_request_digest_survives_preparation`<br>`test_replay.ReplayTests.test_a11_replay_from_new_process` | Behavior unexercised: prerequisite absent |
| A12 | `test_replay.ReplayTests.test_a12_every_changed_request_component_conflicts` | Behavior unexercised: prerequisite absent |
| A13 | `test_replay.ReplayTests.test_a13_same_operation_id_is_actor_scoped` | Behavior unexercised: prerequisite absent |
| A14 | `test_concurrency.ConcurrencyTests.test_a14_simultaneous_identical_requests_commit_once`<br>`test_concurrency.ConcurrencyTests.test_a14_simultaneous_conflicting_requests_have_one_winner` | Behavior unexercised: prerequisite absent |
| A15 | `test_replay.ReplayTests.test_a15_lost_return_retry_recovers_original_from_disk` | Behavior unexercised: prerequisite absent |
| A16 | `test_durability.DurabilityTests.test_a16_eintr_and_short_writes_persist_exactly_one_line` | Behavior unexercised: prerequisite absent |
| A17 | `test_durability.DurabilityTests.test_a17_nonpositive_and_partial_error_restore_exact_bytes` | Behavior unexercised: prerequisite absent |
| A18 | `test_durability.DurabilityTests.test_a18_commit_fsync_failure_restores_and_syncs_before_retry` | Behavior unexercised: prerequisite absent |
| A19 | `test_durability.DurabilityTests.test_a19_failed_rollback_reports_uncertainty_and_releases_lock` | Behavior unexercised: prerequisite absent |
| A20 | `test_durability.DurabilityTests.test_a20_creation_directories_synced_and_ordinary_inodes_preserved`<br>`test_durability.DurabilityTests.test_a20_creation_directory_fsync_failure_never_succeeds` | Behavior unexercised: prerequisite absent |
| A21 | `test_integrity.IntegrityTests.test_a21_unterminated_suffixes_are_read_only_and_json_safe` | Behavior unexercised: prerequisite absent |
| A22 | `test_durability.DurabilityTests.test_a22_failed_tail_continuation_restores_suffix_and_syncs_it`<br>`test_integrity.IntegrityTests.test_a22_successful_continuation_preserves_prefix_and_ignores_tail_ids`<br>`test_integrity.IntegrityTests.test_a22_replay_and_rejection_do_not_repair_torn_tail` | Behavior unexercised: prerequisite absent |
| A23 | `test_integrity.IntegrityTests.test_a23_lf_terminated_corruption_is_never_a_tail` | Behavior unexercised: prerequisite absent |
| A24 | `test_integrity.IntegrityTests.test_a24_byte_tamper_reports_raw_utf8_coordinate` | Behavior unexercised: prerequisite absent |
| A25 | `test_integrity.IntegrityTests.test_a25_deleted_reordered_and_duplicated_complete_lines`<br>`test_integrity.IntegrityTests.test_a25_rehashed_duplicates_and_lamport_gaps_are_rejected` | Behavior unexercised: prerequisite absent |
| A26 | `test_integrity.IntegrityTests.test_a26_correct_independent_chain_passes`<br>`test_integrity.IntegrityTests.test_a26_embedded_digest_is_not_raw_line_digest`<br>`test_integrity.IntegrityTests.test_a26_each_digest_is_independently_enforced`<br>`test_integrity.IntegrityTests.test_a26_noncanonical_whitespace_bom_crlf_and_unicode_escape` | Behavior unexercised: prerequisite absent |
| A27 | `test_integrity.IntegrityTests.test_a27_pinned_head_detects_complete_suffix_loss_at_eof`<br>`test_integrity.IntegrityTests.test_a27_malformed_witness_precedes_integrity_check`<br>`test_integrity.IntegrityTests.test_a27_torn_tail_witness_mismatch_uses_physical_eof` | Behavior unexercised: prerequisite absent |
| A28 | `test_contract.ContractTests.test_a28_evidence_is_structural_and_ordered`<br>`test_contract.ContractTests.test_a28_hostile_evidence_paths_and_closed_shape`<br>`test_isolation.IsolationTests.test_a28_evidence_content_is_only_read_by_injected_domain_validator`<br>`test_isolation.IsolationTests.test_a28_injected_validator_alone_certifies_receipt_content` | Behavior unexercised: prerequisite absent |
| A29 | `test_isolation.IsolationTests.test_a29_symlink_controlled_directories_and_files_never_touch_targets`<br>`test_isolation.IsolationTests.test_a29_fifo_and_directory_authority_are_rejected_without_hanging`<br>`test_isolation.IsolationTests.test_a29_node_swap_during_open_is_refused` | Behavior unexercised: prerequisite absent |
| A30 | `test_locking.LockingTests.test_a30_held_lock_is_busy_then_same_operation_commits`<br>`test_locking.LockingTests.test_a30_monotonic_deadline_limits_wait_and_eintr` | Behavior unexercised: prerequisite absent |
| A31 | `test_locking.LockingTests.test_a31_zero_timeout_attempts_available_and_held_lock`<br>`test_locking.LockingTests.test_a31_invalid_timeouts_precede_all_storage` | Behavior unexercised: prerequisite absent |
| A32 | `test_locking.LockingTests.test_a32_noncontention_backend_error_is_internal`<br>`test_locking.LockingTests.test_a32_missing_backend_cannot_become_lockless_success`<br>`test_locking.LockingTests.test_a32_interrupted_acquisition_then_success_and_unlock` | Behavior unexercised: prerequisite absent |
| A33 | `test_locking.LockingTests.test_a33_success_replay_rejection_crash_and_corruption_release_lock`<br>`test_durability.DurabilityTests.test_a19_failed_rollback_reports_uncertainty_and_releases_lock` | Behavior unexercised: prerequisite absent |
| A34 | `test_concurrency.ConcurrencyTests.test_a34_readers_never_observe_locked_partial_append` | Behavior unexercised: prerequisite absent |
| A35 | `test_replay.ReplayTests.test_a35_unknown_historical_kind_and_corrupt_prefix_replay`<br>`test_replay.ReplayTests.test_a35_read_results_are_detached` | Behavior unexercised: prerequisite absent |
| A36 | `test_contract.ContractTests.test_a36_error_serialization_detaches_structured_detail`<br>`test_contract.ContractTests.test_a36_unexpected_callback_error_is_sanitized_and_silent`<br>`test_transactions.TransactionTests.test_a8_domain_error_preserves_code_and_detail` | Behavior unexercised: prerequisite absent |
| A37 | `test_contract.OraclePackageTests.test_a37_package_initializers_are_present`<br>`test_contract.OraclePackageTests.test_a37_independent_oracle_accepts_valid_and_rejects_bad_chain` | Package/self-checks runnable; behavioral fail-first and U01 receipts unavailable |
| A38 | `test_transactions.TransactionTests.test_a8_missing_validator_rejects`<br>`test_transactions.TransactionTests.test_a8_validator_non_none_return_rejects`<br>`test_concurrency.ConcurrencyTests.test_a10_gate_stays_inside_fence_through_commit`<br>`test_integrity.IntegrityTests.test_a24_byte_tamper_reports_raw_utf8_coordinate`<br>`test_integrity.IntegrityTests.test_a26_embedded_digest_is_not_raw_line_digest` | Probes present; mutation execution unavailable |
