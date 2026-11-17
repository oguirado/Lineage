# U13 fail-first oracle

Status: **PENDING**. This is an executable specification, not a host acceptance receipt.
Run `python3 -m unittest discover -s tests/runs -t .` from the repository root.
Python standard-library unittest only. Runtime directories are disposable children of this test directory.

## Authority and integration boundary

The integrated `lineage/core/registry.py`, `lineage/core/app.py`, `lineage/core/journal.py`,
`lineage/core/schema.py`, `lineage/core/cli.py` and `lineage/core/mcp.py` are used unchanged.
`support.py` supplies explicitly synthetic agent/memory producers and folds for controlled
committed-prefix predicate fixtures. They are not replacement production modules, authenticated
principals, or evidence of U10/U12 integration. `test_a40_real_peer_integration_is_required`
blocks acceptance while the real peers are absent. No core gate case is skipped.

API deviations required by A-K0-9:

| Draft interface | Integrated API used |
|---|---|
| Registry Context/Services/Command/Snapshot/Committed | CallContext exists in app; missing orchestration shapes are explicit test fixtures. Domain stub annotations are postponed. No production core exports are fabricated. |
| ToolSpec.effect; positional handler(args, ctx) | ToolSpec.mutating; handler(args, context=...) |
| FoldSpec; Validator(snapshot,event,ctx) | Callable fold(state,event); validator(history,event) |
| Registry.names/descriptors | Registry.tools; app.list_tools(registry=...) |
| dispatch returns inner wrapper directly | dispatch(name,args,context=...,registry=...) returns DispatchResult.payload/exit_code |
| journal.transact(Command,Prepare,Render,ctx=...); append | transact(home,agent,op_id,kind,payload,validators,prepare,clock,id_factory,...); no append or render hook |
| journal.snapshot(ctx=...) and verify.valid | snapshot(home) returns history tuple; verify(home) reports ok |
| SchemaStore/decode/canonical and extended schema subset | strict_loads/validate; test-side canonical bytes and bundled-record assertion walker. Nullable integer anyOf normalizes to equivalent type array for live discovery. |
| Ordinary tool byte cap | Integrated strict decoder retains its narrower cap; no permissive alternate production decoder |

## Amendment B decisions

- Non-replay ordering: no_run; tool actor mismatch; run_closed; retirement eligibility;
  caller evidence path/regular-file/hash checks; episode absence; companion debt.
- An open retired agent may heartbeat, matching M7; it cannot freshly close. A regressing
  heartbeat or close clock gives conflict. Exact replay precedes all live checks.
- Opening version hashes are recomputed from committed constitution_sha256, sorted skills and
  memory_gen. U12 remains responsible for admission of immutable constitution/skill/reference
  bytes; editable projections are not re-hashed as a new run-open prerequisite.
- ParentContext is shape-only correlation data, preserved in order, not a new existence gate.
  The inherited arm is permitted with an empty ParentContext list.
- Command/Context/event identity must agree. Subject-owner binding is mandatory under tool
  authority; caller spelling and outer operator contexts do not promote tool authority.
  Matching reserved subjects are absent agents and give no_agent.
- Passing check ids are non-normative within the frozen schema. Proposed gate and memory_receipts
  must exactly equal the central report. With token_count=None, an informational passing check
  detail states the token ceiling is "not measured"; no field is added to Run.
- The minimal set contains at most 3 witnesses [TARGET], each at most 64 receipts [TARGET],
  so its union is at most 192 [TARGET], below 256 [TARGET]. The byte cap may lower that bound.
  The proposed over-256 valid union is unreachable; no truncation or alternative selection is
  introduced. A per-unit over-cap negative and a large byte-valid union positive cover the boundary.
- Frozen caller schema failures remain argument errors. Missing/unreadable/non-regular/mismatched
  caller files give hash_mismatch; invalid required memory receipts give memory_debt.
  Fixtures use only regular files, disposable directories, symlinks and a bounded FIFO child;
  no device nodes or process groups are created.

## Acceptance map

Each test name below is relative to `tests.runs`. Synthetic-prefix successes never discharge
host integration obligations. Every listed BLOCKED item must be resolved before A40 can pass.

| Acceptance | Test names | Scope / remaining gate |
|---|---|---|
| A1 | `test_contract.Contract.test_a01_exact_extension_inventory_and_discovery`<br>`test_contract.Contract.test_a01_public_signatures_and_defaults` | U04 mutating boolean replaces effect; callable fold replaces FoldSpec. Registry and record assertions are executable. |
| A2 | `test_contract.Contract.test_a02_direct_malformed_payload`<br>`test_contract.Contract.test_a02_hostile_bool_cost`<br>`test_contract.Contract.test_a02_hostile_bool_repairs`<br>`test_contract.Contract.test_a02_hostile_empty_progress`<br>`test_contract.Contract.test_a02_hostile_evidence_oversize`<br>`test_contract.Contract.test_a02_hostile_gate_injection`<br>`test_contract.Contract.test_a02_hostile_infinity`<br>`test_contract.Contract.test_a02_hostile_invalid_id`<br>`test_contract.Contract.test_a02_hostile_long_progress`<br>`test_contract.Contract.test_a02_hostile_missing_cost`<br>`test_contract.Contract.test_a02_hostile_missing_seat_mode`<br>`test_contract.Contract.test_a02_hostile_nan`<br>`test_contract.Contract.test_a02_hostile_negative_cost`<br>`test_contract.Contract.test_a02_hostile_nested_seat_extra`<br>`test_contract.Contract.test_a02_hostile_nested_unknown`<br>`test_contract.Contract.test_a02_hostile_null_outcome`<br>`test_contract.Contract.test_a02_hostile_parent_duplicate`<br>`test_contract.Contract.test_a02_hostile_partial_benchmark`<br>`test_contract.Contract.test_a02_hostile_receipts_injection`<br>`test_contract.Contract.test_a02_hostile_surrogate`<br>`test_contract.Contract.test_a02_hostile_timestamp_injection`<br>`test_contract.Contract.test_a02_hostile_unknown_root`<br>`test_contract.Contract.test_a02_hostile_unsafe_cost`<br>`test_contract.Contract.test_a02_hostile_version_injection`<br>`test_transports.Transports.test_a02_cli_duplicate_keys_at_depth_refused_before_append`<br>`test_transports.Transports.test_a02_mcp_invalid_utf8_refused_without_append` | Hostile tools and real CLI/MCP syntax paths; U02 keeps its integrated byte cap and nullable schema form. |
| A3 | `test_lifecycle.Lifecycle.test_a03_benchmark_task_preserved_together`<br>`test_lifecycle.Lifecycle.test_a03_open_get_freezes_authoritative_identity`<br>`test_lifecycle.Lifecycle.test_a03_parent_context_is_shape_only_and_preserves_order` | Synthetic committed agent fixture; real U12 genesis integration BLOCKED. |
| A4 | `test_lifecycle.Lifecycle.test_a04_complete_seat_admission`<br>`test_lifecycle.Lifecycle.test_a04_retired_agent_cannot_open`<br>`test_lifecycle.Lifecycle.test_a04_unknown_agent`<br>`test_lifecycle.Lifecycle.test_a04_version_integrity_recomputed` | Version is recomputed from committed version inputs; producer/artifact integrity integration BLOCKED. |
| A5 | `test_lifecycle.Lifecycle.test_a05_distinct_open_cannot_reuse_global_id`<br>`test_replay.Replay.test_a05_exact_open_retry_returns_original_commit` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A6 | `test_lifecycle.Lifecycle.test_a06_command_context_actor_mismatch`<br>`test_lifecycle.Lifecycle.test_a06_open_actor_spoofing`<br>`test_lifecycle.Lifecycle.test_a06_owner_required_for_beat_and_close`<br>`test_lifecycle.Lifecycle.test_a06_reserved_subject_is_not_an_agent`<br>`test_lifecycle.Lifecycle.test_a06_unknown_run_precedes_actor`<br>`test_transports.Transports.test_a06_dispatch_cannot_preserve_outer_operator_authority` | Tool authority tested; reserved matching subject gives no_agent; forged draft coverage also belongs to A28. |
| A7 | `test_lifecycle.Lifecycle.test_a07_closed_precedes_retired_but_not_actor_mismatch`<br>`test_lifecycle.Lifecycle.test_a07_invalid_heartbeat_progress`<br>`test_lifecycle.Lifecycle.test_a07_owner_heartbeat_only_changes_runs`<br>`test_lifecycle.Lifecycle.test_a07_retired_open_run_accepts_heartbeat` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A8 | `test_lifecycle.Lifecycle.test_a08_opening_version_survives_memory_generation` | Synthetic peer memory generation; U12 version refresh integration BLOCKED. |
| A9 | `test_lifecycle.Lifecycle.test_a09_get_is_defensive_read_only_and_rebuildable`<br>`test_lifecycle.Lifecycle.test_a09_missing_read_does_not_bootstrap_home` | Ledger-authoritative reads and controlled projection damage; U11 materialization integration BLOCKED. |
| A10 | `test_close_gate.CloseGate.test_a10_beats_and_pending_projection_are_not_memory`<br>`test_close_gate.CloseGate.test_a10_missing_memory_is_required`<br>`test_close_gate.CloseRecords.test_a10_domain_refusal_leaves_run_open` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A11 | `test_close_gate.CloseRecords.test_a11_memory_arm_inherited`<br>`test_close_gate.CloseRecords.test_a11_memory_arm_none`<br>`test_close_gate.CloseRecords.test_a11_memory_arm_own` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A12 | `test_close_gate.CloseGate.test_a12_fresh_episode_passes`<br>`test_memory_witnesses.Witnesses.test_a12_old_replay_does_not_refresh_original_lamport`<br>`test_memory_witnesses.Witnesses.test_a12_preopen_episode_is_not_fresh` | Controlled temporal prefixes; real U10 before-open admission/old-memory replay integration BLOCKED. |
| A13 | `test_close_gate.CloseGate.test_a13_conflicting_target_provenance_is_debt`<br>`test_memory_witnesses.Witnesses.test_a13_foreign_owner_memory_cannot_close`<br>`test_memory_witnesses.Witnesses.test_a13_foreign_run_memory_cannot_close`<br>`test_memory_witnesses.Witnesses.test_a13_unbound_generic_memory_cannot_close` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A14 | `test_memory_witnesses.Witnesses.test_a14_invalid_draft`<br>`test_memory_witnesses.Witnesses.test_a14_invalid_illegal_level`<br>`test_memory_witnesses.Witnesses.test_a14_invalid_malformed`<br>`test_memory_witnesses.Witnesses.test_a14_invalid_private`<br>`test_memory_witnesses.Witnesses.test_a14_invalid_retired`<br>`test_memory_witnesses.Witnesses.test_a14_invalid_scope_language`<br>`test_memory_witnesses.Witnesses.test_a14_invalid_scope_workflow`<br>`test_memory_witnesses.Witnesses.test_a14_invalid_superseded`<br>`test_memory_witnesses.Witnesses.test_a14_invalid_unknown_body`<br>`test_memory_witnesses.Witnesses.test_a14_invalid_wrong_body_kind` | Controlled invalid histories exercise the gate; real U10 producer rejection integration BLOCKED. |
| A15 | `test_memory_witnesses.Witnesses.test_a15_binding_body_run`<br>`test_memory_witnesses.Witnesses.test_a15_binding_effort`<br>`test_memory_witnesses.Witnesses.test_a15_binding_mode`<br>`test_memory_witnesses.Witnesses.test_a15_binding_model`<br>`test_memory_witnesses.Witnesses.test_a15_binding_parents`<br>`test_memory_witnesses.Witnesses.test_a15_binding_provenance_run`<br>`test_memory_witnesses.Witnesses.test_a15_binding_task`<br>`test_memory_witnesses.Witnesses.test_a15_binding_version_unknown_field` | Episode attribution negative fixtures; current-version drift is A8. |
| A16 | `test_close_gate.CloseGate.test_a16_null_costs_preserved_in_gate`<br>`test_close_gate.CloseRecords.test_a16_nullable_record_and_replay`<br>`test_memory_witnesses.Witnesses.test_a16_mismatch_confirmed`<br>`test_memory_witnesses.Witnesses.test_a16_mismatch_cost_micro_usd`<br>`test_memory_witnesses.Witnesses.test_a16_mismatch_duration_ms`<br>`test_memory_witnesses.Witnesses.test_a16_mismatch_refuted`<br>`test_memory_witnesses.Witnesses.test_a16_mismatch_repairs`<br>`test_memory_witnesses.Witnesses.test_a16_mismatch_tokens_cache`<br>`test_memory_witnesses.Witnesses.test_a16_mismatch_tokens_in`<br>`test_memory_witnesses.Witnesses.test_a16_mismatch_tokens_out`<br>`test_memory_witnesses.Witnesses.test_a16_mismatch_verdict` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A17 | `test_close_gate.CloseGate.test_a17_episode_absence_precedes_companion_debt`<br>`test_close_gate.CloseGate.test_a17_matrix_admit_repairs_0`<br>`test_close_gate.CloseGate.test_a17_matrix_admit_repairs_1`<br>`test_close_gate.CloseGate.test_a17_matrix_error_repairs_0`<br>`test_close_gate.CloseGate.test_a17_matrix_error_repairs_1`<br>`test_close_gate.CloseGate.test_a17_matrix_green_repairs_0`<br>`test_close_gate.CloseGate.test_a17_matrix_green_repairs_1`<br>`test_close_gate.CloseGate.test_a17_matrix_hold_repairs_0`<br>`test_close_gate.CloseGate.test_a17_matrix_hold_repairs_1`<br>`test_close_gate.CloseGate.test_a17_matrix_red_repairs_0`<br>`test_close_gate.CloseGate.test_a17_matrix_red_repairs_1` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A18 | `test_close_gate.CloseGate.test_a18_companions_may_commit_after_episode`<br>`test_memory_witnesses.Witnesses.test_a18_lesson_inactive`<br>`test_memory_witnesses.Witnesses.test_a18_lesson_other_agent`<br>`test_memory_witnesses.Witnesses.test_a18_lesson_other_run`<br>`test_memory_witnesses.Witnesses.test_a18_lesson_preopen`<br>`test_memory_witnesses.Witnesses.test_a18_lesson_private`<br>`test_memory_witnesses.Witnesses.test_a18_lesson_receipt`<br>`test_memory_witnesses.Witnesses.test_a18_lesson_wrong_kind`<br>`test_memory_witnesses.Witnesses.test_a18_negative_inactive`<br>`test_memory_witnesses.Witnesses.test_a18_negative_other_agent`<br>`test_memory_witnesses.Witnesses.test_a18_negative_other_run`<br>`test_memory_witnesses.Witnesses.test_a18_negative_preopen`<br>`test_memory_witnesses.Witnesses.test_a18_negative_private`<br>`test_memory_witnesses.Witnesses.test_a18_negative_receipt`<br>`test_memory_witnesses.Witnesses.test_a18_negative_wrong_kind` | Required companions are checked independently; wrong kind uses open_item; full U10 kind admission integration BLOCKED. |
| A19 | `test_close_gate.CloseRecords.test_a19_failed_task_error`<br>`test_close_gate.CloseRecords.test_a19_failed_task_hold`<br>`test_close_gate.CloseRecords.test_a19_failed_task_red` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A20 | `test_close_gate.CloseGate.test_a20_receipt_bytes_checked_with_positive_control`<br>`test_memory_witnesses.Witnesses.test_a20_level_two_without_receipt_is_debt`<br>`test_memory_witnesses.Witnesses.test_a20_missing_required_receipt_is_debt`<br>`test_memory_witnesses.Witnesses.test_a20_unreadable_receipt_is_debt` | Gate receipt rechecks are executable; real U10 level-two admission integration BLOCKED. |
| A21 | `test_memory_witnesses.CallerEvidence.test_a21_caller_evidence_is_not_a_memory_receipt`<br>`test_memory_witnesses.CallerEvidence.test_a21_caller_nonregular_is_hash_mismatch`<br>`test_memory_witnesses.CallerEvidence.test_a21_changed_caller_evidence_precedes_memory`<br>`test_memory_witnesses.CallerEvidence.test_a21_missing_caller_evidence_precedes_missing_episode`<br>`test_memory_witnesses.CallerEvidence.test_a21_owner_precedes_caller_evidence`<br>`test_memory_witnesses.CallerEvidence.test_a21_unsafe_caller_00`<br>`test_memory_witnesses.CallerEvidence.test_a21_unsafe_caller_01`<br>`test_memory_witnesses.CallerEvidence.test_a21_unsafe_caller_02`<br>`test_memory_witnesses.CallerEvidence.test_a21_unsafe_caller_03`<br>`test_memory_witnesses.CallerEvidence.test_a21_unsafe_caller_04`<br>`test_memory_witnesses.CallerEvidence.test_a21_unsafe_caller_05`<br>`test_memory_witnesses.CallerEvidence.test_a21_unsafe_caller_06`<br>`test_memory_witnesses.CallerEvidence.test_a21_unsafe_caller_07`<br>`test_memory_witnesses.CallerEvidence.test_a21_unsafe_caller_08`<br>`test_memory_witnesses.CallerEvidence.test_a21_unsafe_caller_09`<br>`test_memory_witnesses.Witnesses.test_a21_directory_receipt_is_debt`<br>`test_memory_witnesses.Witnesses.test_a21_fifo_receipt_cannot_block`<br>`test_memory_witnesses.Witnesses.test_a21_symlink_directory_receipt_is_debt`<br>`test_memory_witnesses.Witnesses.test_a21_symlink_receipt_is_debt`<br>`test_memory_witnesses.Witnesses.test_a21_unsafe_receipt_00`<br>`test_memory_witnesses.Witnesses.test_a21_unsafe_receipt_01`<br>`test_memory_witnesses.Witnesses.test_a21_unsafe_receipt_02`<br>`test_memory_witnesses.Witnesses.test_a21_unsafe_receipt_03`<br>`test_memory_witnesses.Witnesses.test_a21_unsafe_receipt_04`<br>`test_memory_witnesses.Witnesses.test_a21_unsafe_receipt_05`<br>`test_memory_witnesses.Witnesses.test_a21_unsafe_receipt_06`<br>`test_memory_witnesses.Witnesses.test_a21_unsafe_receipt_07`<br>`test_memory_witnesses.Witnesses.test_a21_unsafe_receipt_08`<br>`test_memory_witnesses.Witnesses.test_a21_unsafe_receipt_09` | Unsafe paths, symlinks, directories and bounded FIFO child; caller evidence precedes memory and follows actor eligibility. |
| A22 | `test_close_gate.CloseGate.test_a22_changed_removed_restored_receipts` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A23 | `test_close_gate.CloseGate.test_a23_public_internal_observations_need_no_receipt`<br>`test_memory_witnesses.Witnesses.test_a23_optional_level_three_receipt_is_verified` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A24 | `test_close_gate.CloseGate.test_a24_report_order_is_independent_of_enumeration`<br>`test_close_gate.CloseRecords.test_a24_large_legal_receipt_union_without_truncation`<br>`test_close_gate.CloseRecords.test_a24_minimal_sorted_witnesses_and_separate_task_evidence`<br>`test_memory_witnesses.Witnesses.test_a24_invalid_lexical_first_alternative_does_not_hide_valid_one`<br>`test_memory_witnesses.Witnesses.test_a24_one_unit_receipt_array_cannot_exceed_64` | Legal receipt union is tested without truncation. More than 256 combined receipts is unreachable under the minimal selection and per-unit cap; see decisions. |
| A25 | `test_replay.Replay.test_a25_replays_precede_later_closure_retirement_and_clock` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A26 | `test_replay.Replay.test_a26_changed_close_cost`<br>`test_replay.Replay.test_a26_changed_close_evidence`<br>`test_replay.Replay.test_a26_changed_close_outcome`<br>`test_replay.Replay.test_a26_changed_close_run_id`<br>`test_replay.Replay.test_a26_changed_open_content_is_bad_op`<br>`test_replay.Replay.test_a26_changed_tool_and_progress_is_bad_op`<br>`test_replay.Replay.test_a26_default_and_explicit_empty_evidence_replay` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A27 | `test_replay.Replay.test_a27_revision_after_replay_and_under_lock` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A28 | `test_close_gate.CloseRecords.test_a28_direct_close_cannot_bypass_gate`<br>`test_close_gate.CloseRecords.test_a28_forged_gate_checks_rejected`<br>`test_close_gate.CloseRecords.test_a28_forged_owner`<br>`test_close_gate.CloseRecords.test_a28_forged_receipts`<br>`test_close_gate.CloseRecords.test_a28_forged_unit_ids`<br>`test_close_gate.CloseRecords.test_a28_forged_version` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A29 | `test_atomicity.Atomicity.test_a29_close_first_can_commit_before_retirement`<br>`test_atomicity.Atomicity.test_a29_retirement_first_refuses_close` | Real shared journal/process order, synthetic agent.status producer; real U12 retirement validator integration BLOCKED. |
| A30 | `test_atomicity.Atomicity.test_a30_close_first_preserves_historical_memory_receipt`<br>`test_atomicity.Atomicity.test_a30_replacement_must_have_its_own_run_binding`<br>`test_atomicity.Atomicity.test_a30_witness_retirement_first_refuses_close` | Real shared journal/process order, synthetic memory retirement/supersession; real U10 validators integration BLOCKED. |
| A31 | `test_atomicity.Atomicity.test_a31_distinct_concurrent_closes_have_one_winner`<br>`test_atomicity.Atomicity.test_a31_identical_concurrent_closes_replay` | Executable component oracle using the integrated core and controlled peer prefixes. |
| A32 | `test_atomicity.CrashBoundary.test_a32_owned_task_ends_after_durable_memory_before_close`<br>`test_replay.Replay.test_a32_memory_survives_new_fixture_before_close` | Exact parent-owned child terminates after durable memory, before close; staged-only contrast is A10. |
| A33 | `test_atomicity.Atomicity.test_a33_real_lock_refusal_and_release` | Explicit ready/release events and real ledger lock; no fixed sleep establishes ordering. |
| A34 | `test_atomicity.Atomicity.test_a34_commit_write_failure_rolls_back`<br>`test_atomicity.Atomicity.test_a34_fsync_failure_rolls_back`<br>`test_atomicity.Atomicity.test_a34_gate_exception_is_internal_without_append`<br>`test_atomicity.CrashBoundary.test_a34_failed_rollback_blocks_mutation_until_verified_recovery`<br>`test_atomicity.CrashBoundary.test_a34_result_validation_failure_precedes_durability` | Gate, result validation, append/fsync and rollback faults use actual integrated seams. Postcommit projection-failure/retry integration BLOCKED: U03 has no projector hook and U11/U12 are absent. |
| A35 | `test_lifecycle.Lifecycle.test_a35_heartbeat_and_close_reject_regressing_clock`<br>`test_replay.Replay.test_a35_tamper_is_not_empty_history`<br>`test_replay.Replay.test_a35_torn_suffix_is_not_a_witness` | Journal tamper/torn suffix and regressing heartbeat/close clocks. |
| A36 | `test_transports.Transports.test_a36_cli_failed_task_can_close_with_exit_zero`<br>`test_transports.Transports.test_a36_cli_memory_required_exits_three`<br>`test_transports.Transports.test_a36_dispatch_missing_memory_has_one_error_and_no_append`<br>`test_transports.Transports.test_a36_dispatch_success_wraps_once`<br>`test_transports.Transports.test_a36_mcp_domain_error_is_normal_rpc_result`<br>`test_transports.Transports.test_a36_mcp_schema_error_is_rpc_minus_32602`<br>`test_transports.Transports.test_a36_mcp_success_and_dispatch_have_identical_replay` | Real dispatch/CLI/MCP; JSON and HTTP carrier parity BLOCKED until their run adapters integrate. |
| A37 | `test_close_gate.CloseGate.test_a37_no_tokenizer_or_detector_requirement`<br>`test_close_gate.CloseRecords.test_a37_byte_valid_memory_closes_without_token_counter`<br>`test_memory_witnesses.Witnesses.test_a37_multibyte_canonical_byte_limit_is_not_character_count` | Byte-valid no-tokenizer positive, multibyte oversize negative. U10/U11 producer/static-entry admission integration BLOCKED. |
| A38 | `test_close_gate.GateMutants.test_a38_neutralized_central_gate_killed_by_missing_memory`<br>`test_close_gate.GateMutants.test_a38_owner_guard_mutant_killed_by_foreign_memory`<br>`test_close_gate.GateMutants.test_a38_postopen_guard_mutant_killed_by_stale_memory` | In-memory source copies only. Missing mutation sites, green mutants and import/dependency errors are HOLD, never kills. H8 is unverified against stubs. |
| A39 | `test_atomicity.Atomicity.test_a39_callbacks_do_not_dispatch_network_or_spawn`<br>`test_lifecycle.Lifecycle.test_a39_fold_owns_only_runs` | Actual callback boundary traps nested transaction/dispatch, network, process spawn and file writes; namespace and defensive-copy assertions. |
| A40 | `test_contract.Contract.test_a40_existing_frozen_oracles_unchanged`<br>`test_contract.Contract.test_a40_real_peer_integration_is_required` | Acceptance guard remains red; dependency availability, frozen-oracle hashes and a green suite cannot be replaced by synthetic peer receipts. H9/capsules AUSENTE — no inventar. |

## Evidence and safety

`contract_schemas.json` freezes the public run tool schemas from `docs/CONTRACT.md`.
`baseline.json` pins the pre-existing test and schema files using relative paths and hashes;
it does not contain runtime evidence locations. Process fixtures use fork, explicit
Events/Pipes, bounded polls/joins and exact verified parent-owned Process identities.
No process group is created, signalled, or cleaned up. No network or model invocation,
dependency download, foreign project access, source edit outside the assigned surface,
or assertion relaxation is performed by these tests.

The current stubs are expected to raise `NotImplementedError("U13 stub")`; dispatch maps
that failure to internal. Import-only or missing-dependency failures are not acceptable
fail-first evidence. H8, H9, live JSON/HTTP parity, UI persona/frame/capsule receipts,
and memory-behavior benefit evidence are **AUSENTE — no inventar**.


## Amendments A-U13

# A-U13: Reconcile fixtures with installed APIs without relaxing run behaviour.

- `tests/runs/test_contract.py`: compare discovery to the literal frozen Arguments
  object. Installed U10 validates `anyOf`; the former nullable-integer rewrite
  is no longer needed at this discovery assertion. Record-validation helpers
  retain their existing semantic assertions.
- `tests/runs/support.py`: allocate unused actor/op_id pairs when making a fresh
  fixture command after restart. Explicit op_ids are unchanged. The integrated
  U03 dedupe ledger is authoritative; restarting a fixture is not an exact retry.
- `tests/runs/test_contract.py`, `tests/runs/baseline.json` and
  `tests/runs/baseline_retired.json`: reconcile frozen input pins to integrated
  U07/U09/U12 fixtures and U01R regression accounting. Every original input row
  remains present. Active inputs retain exact byte-hash assertions. Retired
  inputs retain original hashes and require absence, with explicit RETIRE
  decisions for former test modules; removed auxiliary fixtures require only
  retired modules in their bundle. The new reconciliation manifest, replacement
  assertions and the retired-input fixture itself are also hash-pinned. No run
  test, behavioural assertion or case is removed or skipped.
- `tests/runs/test_review_h1.py`: new regression coverage for partial benchmark
  arguments across dispatch, CLI and MCP, restarted fixture operations, and
  unchanged caller op_id journaling. No frozen assertions are replaced.

The following exact input changes come from integrated units. RETIRED refers to
U01R's explicit legacy extraction reconciliation, not a U13 test removal.
Hashes are SHA-256 values [MEASURED].

| Input | Previous pin | Integrated pin or retirement |
|---|---|---|
| `tests/agents/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `6f2fa6f0108b1f341ec91ac98dd0cf6297ba9f162776d937cdf8e892adc7f35a` |
| `tests/core/DROPPED.md` | `3eac5bcd5954bb7eeed04ac6d8861ba508090297305c50306994d8f063ab8339` | `b2ed808f7316242b3045f61c726fb08ccdf7312776c5a291ed2db6024ddacdc1` |
| `tests/core/REGRESSION_FROZEN.sha256` | `84bdd69c7788578e3a88787f79c530e68dcf703e98f6db715709a97b3ce9a7c7` | `a6bfacc043cd7ed017ba38e6a90a0750ecb96f785f8e41b6228d7f5735b2ef17` |
| `tests/core/regression/__init__.py` | `fe069e1cb18ca51073cc109b2f29d3044fde6f79f9e25f8525f2823b7593a0b9` | `b42a86ae48d2978799cbd347fc584cf8e0d67b70364555cd121bf1055d4c1416` |
| `tests/core/regression/family/__init__.py` | `4016261e73796d355e3a516a0f04fe3a814a7e21a6c745454b9465ad9b739944` | `RETIRED (U01R)` |
| `tests/core/regression/family/support.py` | `1d48bb4cfcb1d8322dc28c59120d7758319fa41f3034ec408896edf2d2423fe9` | `RETIRED (U01R)` |
| `tests/core/regression/family/test_cursors.py` | `a169409d2e93a764a0bc3ee02a96a61ed8b786edabead3bddaf51f85aaa945b6` | `RETIRED (U01R)` |
| `tests/core/regression/family/test_envelope.py` | `17c7a29ed868deab52a2f32f112e793c75461d92b1dc3fa1ccfe6c252c217dd6` | `RETIRED (U01R)` |
| `tests/core/regression/family/test_hardening.py` | `8b53e348ae69dc951a3b85f4e9113e7044874259b1c0c27d113343dce78bd2ae` | `RETIRED (U01R)` |
| `tests/core/regression/family/test_mailbox.py` | `4b8106a5ba45c6f5b302a23b3ab6add1436416ccd4b584469048821ed03de249` | `RETIRED (U01R)` |
| `tests/core/regression/family/test_recovery.py` | `9d90bcd56d95c6fdf119df1156b8e6858615753d135c6616a76bc22cb1a37ad1` | `RETIRED (U01R)` |
| `tests/core/regression/family/test_routing.py` | `4f315b13b80f2ac9c93aa3560680cf1f97eb757ad632e9e571b934cf5aa52f20` | `RETIRED (U01R)` |
| `tests/core/regression/plan/test_u55_conformance_md.py` | `44b9f763c755a2d0a5d2cafc4ec8f5556206f55f9f14baf6d409afdca17113ad` | `474bb742c19af048c6b2d34106129ba121487dbc52ee1d6c0350db629e426348` |
| `tests/core/regression/plan/test_u55_ops_fold.py` | `b98b261b6e3adb71f0a3e82f928316317f7f7894838fce33cc07b07dbfe6412c` | `beeb2fa2666d69e5c2f3e5e8a236da9053e2222a9674d5b0a28a930237ba8404` |
| `tests/core/regression/plan/test_u55_repair1.py` | `3e41dd2b76f269f981865b86f7e7edff17091294a56ff1bdd88422a49e74dcfb` | `a39619992170a2a9287cb8ac1ded4a69f28c9db1872f6537a0add3780daa1dd8` |
| `tests/core/regression/plan/test_u55_repair2.py` | `8a6bedb7f1631b575ba48750bf18e75c9becb2ce494da8cc064436d787d76daa` | `c355dcf8b43eab58faa8f279e5151d768c7404fe12cbf945c3be0e7625ca80c6` |
| `tests/core/regression/plan/test_u55_template.py` | `a18cb45cbe815270360d8048397d662e4be936ab9c9ca6776909b0463baf736b` | `edf6439e4073c1ddd475d3dc1105dab12bf260ba5ed673aa9f1d30e07d36ad18` |
| `tests/core/regression/plan/test_u55_vectors.py` | `5c77ec3a5803dc64f81bf781a109f06e540a92b769c6be99a24f10c37d514ebf` | `826a8fdaddce5477e8e81fd7bdf54f77e7d9f367ed5ae38a2cb772b65ba0a146` |
| `tests/core/regression/room/s0/__init__.py` | `8c1969bf6f6a87603f3a2696749765e405c4f70cadf9272e727a56c670ec0f5f` | `RETIRED (U01R)` |
| `tests/core/regression/room/s0/test_seam.py` | `8c93ea74485db0bacf7696f1fb6722a7000a88438188478a29b78988141b6ed8` | `RETIRED (U01R)` |
| `tests/core/regression/room/support.py` | `8e7bcc9cee46da7927ab003b99f7260c262c5a96e2a2d619f40aa5c96d97a83d` | `RETIRED (U01R)` |
| `tests/core/regression/room/test_cli.py` | `39addfef04e3ff622c2127bd1fc1301ccb2a6186d3368d3d1f9e29d7fd39ba77` | `RETIRED (U01R)` |
| `tests/core/regression/room/test_mcp.py` | `23826227446b97c997d6c2c5e064a914cc6ff474c2a8c268a724bdb58756cfb6` | `RETIRED (U01R)` |
| `tests/core/regression/room/test_post.py` | `92a6a81c68cf071bcd7e7ed084c1881b152b773581c35938cbe21504c3343bbe` | `RETIRED (U01R)` |
| `tests/core/regression/room/test_read.py` | `4b3456496fee330eec42f7356fe48cb3beae88b02dfb8a5b4f55019fdd61577c` | `RETIRED (U01R)` |
| `tests/core/regression/room/test_review1.py` | `5d14c6aef3011a9ae9e3c0da68803dd1c666e23bb1a31dff36b74a97ed6e42b4` | `RETIRED (U01R)` |
| `tests/core/regression/room/test_review2.py` | `9914cb498bbb6681086e04e07c6ac18d09430ed748b6bb6cae83cc612bf5563c` | `RETIRED (U01R)` |
| `tests/core/regression/room/u109/__init__.py` | `877b3b9e47f6a9a9bb4cb12014fb320d746e0d420d8cd77eb3e5c0a4f6624478` | `RETIRED (U01R)` |
| `tests/core/regression/room/u109/cli_probe.py` | `2abf60b4505073bda1ab8a2668f645b935014d668d5bf2cbacc7820c6ae7d04b` | `RETIRED (U01R)` |
| `tests/core/regression/room/u109/fold_probe.py` | `57f8da911584f346a90d3b8c30980e5750ca513b28782673bd5f128f2783c6ce` | `RETIRED (U01R)` |
| `tests/core/regression/room/u109/protocol_support.py` | `90a52401a2f13e4362260a6d46ea73534423746888fc0916f2213b361e5d7e72` | `RETIRED (U01R)` |
| `tests/core/regression/room/u109/test_protocol.py` | `330d8174278072fb4c52be346f72b85c8c842fb870a80c92cef6f17cdbb144ab` | `RETIRED (U01R)` |
| `tests/core/regression/room/u110/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `RETIRED (U01R)` |
| `tests/core/regression/room/u110/support.py` | `b31d4a675b7a2591258f3a967b8461b1f980927b2b57882b5c5745d277231c3e` | `RETIRED (U01R)` |
| `tests/core/regression/room/u110/test_durability.py` | `9ae36f53798dc06c6907fe6e13d97860b7464512c47d042adc489c8befe67008` | `RETIRED (U01R)` |
| `tests/core/regression/room/u110/test_protocol.py` | `bef2275fb33928abe845b6d7300189a66bbc61d8c97ded1328070666c0680092` | `RETIRED (U01R)` |
| `tests/core/regression/room/u110/test_references.py` | `c3c16fc2adff3996c4f45eac8c6207280f305759b61f1266971bbc927335aebc` | `RETIRED (U01R)` |
| `tests/core/regression/room/u110/test_validation.py` | `10924e81514f89aa37d3246d253a2d1985127674c4a60c7b58b3b5af4f49825f` | `RETIRED (U01R)` |
| `tests/core/regression/room/u119/__init__.py` | `9ebd5499707def3838360b8053b2358fbb0131821d97fc79e29f272bf6769448` | `RETIRED (U01R)` |
| `tests/core/regression/room/u119/restart_probe.py` | `4bf3b2db8072453f6540cb2c21346c72fadd70dddb60ceec17f13a6cf3292c3f` | `RETIRED (U01R)` |
| `tests/core/regression/room/u119/support.py` | `9c007d77392b807b45230f39f60bd85de03208e1ec1a37bd596b94063de9b48e` | `RETIRED (U01R)` |
| `tests/core/regression/room/u119/test_acquire.py` | `552f9b24199fa669ca14ce2bfdc4f2be84fa0665047f669497aca6e54d5c0c4b` | `RETIRED (U01R)` |
| `tests/core/regression/room/u119/test_atomicity.py` | `16fa15bfdb1375f8e9418c98623ca3f9410681ea7b71431db506d66f099576a4` | `RETIRED (U01R)` |
| `tests/core/regression/room/u119/test_replay_protocol.py` | `965c3f026711ab0c95ec91ca982ef9a62dbfe61cd38a7ae083aef1719cf22fe8` | `RETIRED (U01R)` |
| `tests/core/regression/room/u119/test_report.py` | `3fc531ff10450bbf2cb285d669d7ba9911f87a7a988d94ca4fe26e1d6d9ccaac` | `RETIRED (U01R)` |
| `tests/core/regression/room/u119/test_validation.py` | `96e0d93a33c7e0746213736a7724f75bf0d65e1121e3dd3b21e2977f5a29a593` | `RETIRED (U01R)` |
| `tests/core/regression/room/u121/support.py` | `f47e3ad9fab19a468146ee597faef05b55614e2e6c5914b926960c1392896b23` | `9bfc3414aa05dcb68b11eef4d92a0665c5e4deb48aca8615134671ccfa969641` |
| `tests/core/regression/room/u121/test_batch.py` | `884c3236909702ccb716143768c4ae3ad55b3a307b070e65bbe70e69947d51d8` | `RETIRED (U01R)` |
| `tests/core/regression/room/u121/test_controls.py` | `492134550b07c03c36c675e0717f4f40e27cfef4c2fc7ae7fcfac5ef7a5de808` | `RETIRED (U01R)` |
| `tests/core/regression/room/u121/test_durability.py` | `6317d3601a227b9f40c9bd2e057521ba7656e487deb06b9857d4a5ce282f1f05` | `9f2a6cb6aa0953d930cac36fabefcb2ddae13e28e336a87972371d980251ff9f` |
| `tests/core/regression/room/u121/test_lock.py` | `75e5eba601164f55dcac3483b04b400074cc9883299780255dfbccf306da8a8b` | `RETIRED (U01R)` |
| `tests/core/regression/room/u121/test_replay.py` | `5ac47d8dc5888b5aadce64119fd3d8203367ffab4536b214364e57c6204be2a2` | `RETIRED (U01R)` |
| `tests/core/regression/room/u121/test_reserve.py` | `ee2c7a3bf08c3a0a04b74ca69266b6769202fddd52b7f395127829afe1e8a24c` | `RETIRED (U01R)` |
| `tests/core/regression/room/u69/__init__.py` | `222a64d00681531b9cb9c206a30683f92fedcdc13c0cdd36d8314b49dfa0683b` | `RETIRED (U01R)` |
| `tests/core/regression/room/u69/test_contract.py` | `019cff417ab761c67bb1aa4dffee5fec2c4e97cfd41b75562074566269049579` | `RETIRED (U01R)` |
| `tests/core/regression/room/u69/test_repair1.py` | `ff296fe1460a481aeee5cc818f49636ffcddec271132eb7a261aa94829cd77a6` | `RETIRED (U01R)` |
| `tests/core/regression/room/u71/__init__.py` | `db39b03985358e5a883058661e07512de93c6d94c1d78148d26c29e0ffa55b34` | `RETIRED (U01R)` |
| `tests/core/regression/room/u71/test_lock.py` | `27ead36df68ca8564438143446cb399e335bde5c50c5bc281dbc62725775eb2c` | `RETIRED (U01R)` |
| `tests/core/regression/room/u76/__init__.py` | `c545722298cc16ba4119c838884d744db0a522f9ef0b3b39e6fe962c6933437b` | `RETIRED (U01R)` |
| `tests/core/regression/room/u76/test_repair1.py` | `3c0bc6bd3168c15f0d008aaeec4017560e4bf95d65a04656389512d358ce30f5` | `RETIRED (U01R)` |
| `tests/core/regression/room/u87/__init__.py` | `eb825b4eaa39c80837bce528cbfb5c6de39993ae1aba6fc335a2925b9e78c693` | `RETIRED (U01R)` |
| `tests/core/regression/room/u87/probe.py` | `7430699b0e48349ace2dfd1bda32afe85600053f7f836e409a04f9b22197d1f7` | `RETIRED (U01R)` |
| `tests/core/regression/room/u87/support.py` | `48055127761a33c9c5af0025e806733c0a27955606b459953e5e2a9b41e4a034` | `RETIRED (U01R)` |
| `tests/core/regression/room/u87/test_contract.py` | `d54df939d92c58c1c07da67504f6425f4787410a42e2b5a70a06b4b893a57f6a` | `RETIRED (U01R)` |
| `tests/core/regression/room/u87/test_repair1.py` | `5301b867dbde3765e3c4ff25e2c30a18e5765c13a2aa65ed0382622448b1e595` | `RETIRED (U01R)` |
| `tests/core/regression/room/u89/__init__.py` | `0077d6d560cc8952fcfd3e5675497a896d6251defddc24072b59b24ad3dcde98` | `RETIRED (U01R)` |
| `tests/core/regression/room/u89/support.py` | `3842369b1aa8a30a793500bb9bc4028cfbcb1112f5c6cbed0ec8363026cda6c1` | `RETIRED (U01R)` |
| `tests/core/regression/room/u89/test_events.py` | `be3074c6f351bdbad22863970fa5d8baff93caa970d8f4518b24e296df9f0f93` | `RETIRED (U01R)` |
| `tests/core/regression/room/u89/test_repair1.py` | `337f820e8e3b50a21f32c47dd2628436d3ce0cb954fd2bf221a170d2acadb374` | `RETIRED (U01R)` |
| `tests/core/regression/room/u94/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `RETIRED (U01R)` |
| `tests/core/regression/room/u94/support.py` | `2f3c50e8af9c6bee37d7e42afb21c5b936abbc0512b6f6b20dc4aa5435d7d0d5` | `RETIRED (U01R)` |
| `tests/core/regression/room/u94/test_contract.py` | `24f0243e08fa8368a24493342d5db5caa427a6e17b3a4f8cae2954e0d61a7567` | `RETIRED (U01R)` |
| `tests/core/regression/room/u94/test_files.py` | `c051afcaa61f30cd37c900738744b5f962c0341b7f3ff677b46e99999e1560bc` | `RETIRED (U01R)` |
| `tests/core/regression/room/u94/test_repair1.py` | `a64f9c75a3a07704e9c3994f156c1ffc9a361a10ea06cddfa16d7786c1248762` | `RETIRED (U01R)` |
| `tests/core/regression/room/u94c/__init__.py` | `3d06f7d5ccd296d6f59ac1f53893fccce8a3b81c464e60f134c769eb14ac7dde` | `RETIRED (U01R)` |
| `tests/core/regression/room/u94c/test_cli_export.py` | `fe778c2f2dac8a2eb15ef4b39f09d6c6d871251aee14b160c9db7038981346c7` | `RETIRED (U01R)` |
| `tests/core/regression/room/u95/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `RETIRED (U01R)` |
| `tests/core/regression/room/u95/test_headless_resource.py` | `bb677f866701b182e1c09fe673494508aea8c2399426ccf1c2ae556f833f8c15` | `RETIRED (U01R)` |
| `tests/references/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `f6eb3b0fecdcbade5864af1c35ae61179efe86f111bdc43309ab9cdc51d69fd3` |
| `tests/skills/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `17f68f141978e5ef422192ad60a5406aee0b6f331f79696b8d39e058deb9af29` |
| `tests/core/regression/fixtures/reconciliation.json` | `new integrated U01R input` | `e548bd2bf645221696319e3e1327e812993120bad54857f3484c3edb952af89c` |
| `tests/core/regression/_support.py` | `new integrated U01R input` | `a5991f9ce3ab2c94ec86bb2e5868afd2af3d3140e2ac9189730d1aad555e266a` |
| `tests/core/regression/test_envelope.py` | `new integrated U01R input` | `6ae2cc2a4e9d37c928fbe08c8515881dd204a5f02a3584fb3e325483ee736bee` |
| `tests/core/regression/test_journal.py` | `new integrated U01R input` | `acaedf6d04b58019af6f4b7caac199e9c6a0d965f3ae70327df516e40bc2dc18` |
| `tests/core/regression/test_locking.py` | `new integrated U01R input` | `38d1cc5f02807282b91d5fa41c2f456bd5cca62494e8926c2cdc5017f0d8fea0` |
| `tests/core/regression/test_reconciliation.py` | `new integrated U01R input` | `65d6f386c9c21bfa2be6e983802933682d951a37983b04c2c62279fc7ce00ded` |
| `tests/core/regression/test_sleep_guard.py` | `new integrated U01R input` | `8d1ccf2f1954db29316df082686856cbe60cd1ea12c64f2f1a5de7e97930f24c` |
| `tests/core/regression/test_transports.py` | `new integrated U01R input` | `2bd993878ac17c74b40c0293b9c16df8da0dfca666595f3b3cd2c8c6f131cfbf` |


### Amendments A-U13: repair h2

# A-U13: integrate agent projection ownership without changing behavioral assertions.

- `tests/runs/support.py`: synthetic producer admission remains explicit. Use
  U10's installed memory fold and its units/originals/memory_gen representation;
  retain U12 constitution sources and current brief overlays in the agent fixture
  fold, with memory applied before the effective agent/version view. Seed
  byte-consistent briefs and materialize each fixture birth through
  `agents.refresh_projections`. Production close and retry can then use the real
  postcommit publisher. Journal and projection assertions remain unchanged.
- `tests/runs/baseline.json`: update only the integrated U12 fixture hash below;
  every input remains pinned and every behavioral assertion is retained.
- `tests/runs/test_review_h2.py`: add projection verification after extension
  discovery, close scorecard publication, postcommit failure/retry recovery,
  and replay repair coverage. These tests use explicitly synthetic producer
  admission with real journal, memory folds and projection publication; they
  do not claim U10 producer admission acceptance.

| Integrated input | Previous pin | Current pin |
|---|---|---|
| `tests/agents/__init__.py` | `6f2fa6f0108b1f341ec91ac98dd0cf6297ba9f162776d937cdf8e892adc7f35a` | `d745fdd88c986d3cd7d5f0b68b312e8a557c83cf01f6cdc6ab7ce1f56ed6143e` |

Hashes are SHA-256 values [MEASURED]. No frozen behavioral test was removed,
relaxed, widened or skipped.
