# U16 fail-first oracle

Scope: `.unit/SPEC.md`, all MUST requirements and Acceptance obligations. This
suite is an implementation target, not an integrated acceptance receipt.
All counts, limits and expected arithmetic in this document are [TARGET] unless
explicitly identified as a verification observation. The mandate is scoped to
the supplied campaign corpus and the inspected frozen K0 artifacts.

Run from the repository root:

```sh
python3 -m unittest discover -s tests/arena -t .
```

Tests use standard-library unittest, temporary homes and bank roots, deterministic
clocks and event factories, and no model/network service. Controlled argv children
are created only for runner tests. Timeout/barrier synchronization uses bounded
waits, never sleeps. Cleanup targets only the exact Popen objects created by a
test, with pid greater than one; no process groups are created or signalled.
Fixtures are not operational agents, real fitness, promotion evidence or evidence
of inherited-memory benefit. The bundled bank is a Synthetic offline benchmark.

## Acceptance-to-test map

Fully qualified unittest method names below are discoverable under `tests.arena`. Matrix cases use subTest and retain their individual
rejection assertions. The map includes integration targets that cannot be
certified until their real dependencies exist; no skips replace those assertions.

| Acceptance | Test names |
|---|---|
| A1 | `tests.arena.test_extension.ExtensionTests.test_a1_discovery_exact_tools_effects_validators_fold`<br>`tests.arena.test_extension.ExtensionTests.test_a1_duplicate_tool_or_validator_blocks_discovery`<br>`tests.arena.test_extension.ExtensionTests.test_a1_mcp_and_cli_descriptor_and_sample_read_parity` |
| A2 | `tests.arena.test_bank.BankTests.test_a2_strict_raw_bank_matrix`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a2_malformed_stdout_keeps_real_open_witness`<br>`tests.arena.test_declare.DeclarationTests.test_a2_unknown_declaration_fields_are_closed`<br>`tests.arena.test_extension.ExtensionTests.test_a2_dispatch_invalid_nested_inputs_no_spawn_or_append`<br>`tests.arena.test_runner.RunnerTests.test_a2_recursive_duplicate_keys_utf8_surrogates_and_numbers`<br>`tests.arena.test_runner.RunnerTests.test_a2_invalid_runner_refuses_before_spawn`<br>`tests.arena.test_runner.RunnerTests.test_a2_execution_binding_cannot_be_rewritten` |
| A3 | `tests.arena.test_bank.BankTests.test_a3_manifest_and_canonical_hash_are_independent`<br>`tests.arena.test_bank.BankTests.test_a3_load_and_selection_are_defensive`<br>`tests.arena.test_bank.BankTests.test_a3_changed_raw_byte_is_hash_mismatch`<br>`tests.arena.test_bank.BankTests.test_a3_missing_manifest_has_no_fallback`<br>`tests.arena.test_bank.BankTests.test_a3_identity_mismatch_is_hash_mismatch`<br>`tests.arena.test_bank.BankTests.test_a3_duplicate_task_ids_and_missing_data`<br>`tests.arena.test_declare.DeclarationTests.test_a3_wrong_canonical_hash_refuses_before_run` |
| A4 | `tests.arena.test_bank.BankTests.test_a4_traversal_identifiers`<br>`tests.arena.test_bank.BankTests.test_a4_manifest_members_confined_and_unambiguous`<br>`tests.arena.test_bank.BankTests.test_a4_symlinked_bank_file_and_manifest`<br>`tests.arena.test_bank.BankTests.test_a4_symlinked_bank_directory` |
| A5 | `tests.arena.test_bank.BankTests.test_a5_split_filter_preserves_hash_pinned_order`<br>`tests.arena.test_bank.BankTests.test_a5_empty_eligible_split_is_not_zero_observations`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a5_only_eligible_tasks_execute_in_bank_order`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a5_empty_split_refuses_before_open` |
| A6 | `tests.arena.test_bench_execution.ExecutionTests.test_a6_confirm_admits_heldout_tasks`<br>`tests.arena.test_declare.DeclarationTests.test_a6_direct_heldout_selection_result_is_forbidden` |
| A7 | `tests.arena.test_declare.DeclarationTests.test_a7_run_requires_declaration_before_runner_or_journal`<br>`tests.arena.test_declare.DeclarationTests.test_a7_result_requires_declaration`<br>`tests.arena.test_declare.DeclarationTests.test_a7_unknown_status_and_verdict_are_no_benchmark`<br>`tests.arena.test_recovery.RecoveryTests.test_a7_direct_result_without_declaration_is_refused` |
| A8 | `tests.arena.test_declare.DeclarationTests.test_a8_exact_declaration_replays_original_prefix`<br>`tests.arena.test_declare.DeclarationTests.test_a8_changed_declaration_bad_op_and_distinct_redeclare_conflict` |
| A9 | `tests.arena.test_declare.DeclarationTests.test_a9_invalid_probabilities_and_boolean_cap`<br>`tests.arena.test_declare.DeclarationTests.test_a9_old_alpha_beta_constraint_does_not_reject_declaration`<br>`tests.arena.test_declare.DeclarationTests.test_a9_complete_seat_identity_is_admitted` |
| A10 | `tests.arena.test_bench_execution.ExecutionTests.test_a10_required_failure_memory_does_not_rebase_declaration`<br>`tests.arena.test_declare.DeclarationTests.test_a10_projection_edit_cannot_rebase_declared_snapshot` |
| A11 | `tests.arena.test_bench_execution.ExecutionTests.test_a11_paired_grid_and_full_seat_arm_identity`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a11_crossed_grid_and_task_order_are_complete` |
| A12 | `tests.arena.test_bench_execution.ExecutionTests.test_a12_real_lifecycle_and_actual_closed_run_witness` |
| A13 | `tests.arena.test_bench_execution.ExecutionTests.test_a13_other_actor_memory_refused`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a13_level_one_never_gains_tool_authority`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a13_operator_named_caller_still_tool_authority`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a13_run_open_actor_subject_mismatch_is_actor_mismatch` |
| A14 | `tests.arena.test_bench_execution.ExecutionTests.test_a14_missing_episode_leaves_run_open`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a14_private_episode_cannot_close_run`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a14_other_run_episode_refused`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a14_episode_only_before_open_cannot_satisfy_gate` |
| A15 | `tests.arena.test_bench_execution.ExecutionTests.test_a15_error_without_lesson_is_memory_debt`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a15_repaired_green_requires_same_run_lesson`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a15_hold_and_red_require_negative`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a15_failure_memory_preserves_failed_outcomes`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a15_red_without_negative_is_memory_debt` |
| A16 | `tests.arena.test_bench_execution.ExecutionTests.test_a16_missing_or_changed_evidence_refuses_admission`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a16_reserved_evidence_storage_is_not_a_receipt`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a16_symlink_evidence_is_confined`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a16_oversize_memory_fails_byte_budget`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a16_token_count_none_does_not_create_memory_debt`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a16_missing_receipt_file_is_not_valid_memory` |
| A17 | `tests.arena.test_bench_execution.ExecutionTests.test_a17_fresh_homes_reproduce_exact_ledger_bytes`<br>`tests.arena.test_runner.RunnerTests.test_a17_fake_runner_repeatable_with_virtual_clock` |
| A18 | `tests.arena.test_bench_execution.ExecutionTests.test_a18_command_memory_roundtrip_through_real_close`<br>`tests.arena.test_runner.RunnerTests.test_a18_command_roundtrip_exact_input_and_output`<br>`tests.arena.test_runner.RunnerTests.test_a18_zero_exit_empty_or_malformed_output_is_not_success` |
| A19 | `tests.arena.test_runner.RunnerTests.test_a19_literal_argv_and_passive_prompt` |
| A20 | `tests.arena.test_runner.RunnerTests.test_a20_stdout_over_cap_is_refused_and_reaped`<br>`tests.arena.test_runner.RunnerTests.test_a20_dual_pipe_flood_is_bounded`<br>`tests.arena.test_runner.RunnerTests.test_a20_stderr_does_not_corrupt_valid_protocol` |
| A21 | `tests.arena.test_bench_execution.ExecutionTests.test_a21_completed_timeout_returns_failed_benchmark_datum`<br>`tests.arena.test_runner.RunnerTests.test_a21_timeout_only_reaps_owned_child_sentinel_survives` |
| A22 | `tests.arena.test_bench_execution.ExecutionTests.test_a22_timeout_memory_failure_leaves_open_and_no_result`<br>`tests.arena.test_bench_execution.ExecutionTests.test_a22_allowed_memory_repair_allows_timeout_recovery` |
| A23 | `tests.arena.test_extension.ExtensionTests.test_a23_registered_validator_runs_inside_real_journal_lock`<br>`tests.arena.test_extension.ExtensionTests.test_a23_fold_does_not_mutate_other_namespaces_or_event`<br>`tests.arena.test_recovery.RecoveryTests.test_a23_runner_unlocked_while_unrelated_mutation_commits` |
| A24 | `tests.arena.test_recovery.RecoveryTests.test_a24_stale_initial_head_refuses_before_open`<br>`tests.arena.test_recovery.RecoveryTests.test_a24_seed_argv_timeout_changes_are_bad_op_before_reexecution`<br>`tests.arena.test_recovery.RecoveryTests.test_a24_child_ids_bounded_and_request_fields_not_polluted`<br>`tests.arena.test_recovery.RecoveryTests.test_a24_command_argv_and_timeout_changed_under_retained_identity` |
| A25 | `tests.arena.test_recovery.RecoveryTests.test_a25_fake_crash_after_open_resumes_without_second_run`<br>`tests.arena.test_recovery.RecoveryTests.test_a25_command_crash_after_open_is_ambiguous_not_rerun` |
| A26 | `tests.arena.test_recovery.RecoveryTests.test_a26_durable_output_recovery_never_reexecutes_completed_cell`<br>`tests.arena.test_recovery.RecoveryTests.test_a26_tampered_staging_cannot_authorize_completion` |
| A27 | `tests.arena.test_recovery.RecoveryTests.test_a27_crash_after_memory_reuses_committed_units`<br>`tests.arena.test_recovery.RecoveryTests.test_a27_crash_after_close_appends_result_without_runner` |
| A28 | `tests.arena.test_recovery.RecoveryTests.test_a28_frozen_compound_replay_and_event_digest` |
| A29 | `tests.arena.test_recovery.RecoveryTests.test_a29_identical_callers_never_start_same_cell_twice` |
| A30 | `tests.arena.test_recovery.RecoveryTests.test_a30_spoofed_result_matrix_direct_registered_admission`<br>`tests.arena.test_recovery.RecoveryTests.test_a30_open_run_cannot_be_consumed_as_closed_result` |
| A31 | `tests.arena.test_recovery.RecoveryTests.test_a31_pagination_defensive_reads_and_no_cache_authority`<br>`tests.arena.test_recovery.RecoveryTests.test_a31_unreadable_journal_is_internal_never_empty`<br>`tests.arena.test_recovery.RecoveryTests.test_a31_rebuild_after_deleting_non_authoritative_caches` |
| A32 | `tests.arena.test_recovery.RecoveryTests.test_a32_declared_running_complete_and_explicit_verdict`<br>`tests.arena.test_verdict.VerdictTests.test_a32_no_observations_cannot_produce_verdict` |
| A33 | `tests.arena.test_verdict.VerdictTests.test_a33_crossed_mean_outweighs_one_favorable_cell`<br>`tests.arena.test_verdict.VerdictTests.test_a33_distinct_repeat_changes_mean_exact_delivery_adds_nothing` |
| A34 | `tests.arena.test_verdict.VerdictTests.test_a34_population_not_sample_dispersion`<br>`tests.arena.test_verdict.VerdictTests.test_a34_gain_equal_dispersion_is_not_credited`<br>`tests.arena.test_verdict.VerdictTests.test_a34_gain_equal_minimum_is_not_credited`<br>`tests.arena.test_verdict.VerdictTests.test_a34_cost_only_advantage_cannot_create_correctness_credit`<br>`tests.arena.test_verdict.VerdictTests.test_a34_cheaper_less_correct_candidate_remains_worse`<br>`tests.arena.test_verdict.VerdictTests.test_a34_unknown_cost_does_not_win_a_correctness_tie` |
| A35 | `tests.arena.test_verdict.VerdictTests.test_a35_eight_wins_exhaust_without_upper_boundary`<br>`tests.arena.test_verdict.VerdictTests.test_a35_ninth_independent_win_is_superior`<br>`tests.arena.test_verdict.VerdictTests.test_a35_three_losses_do_not_cross_lower_boundary`<br>`tests.arena.test_verdict.VerdictTests.test_a35_fourth_independent_loss_is_not_superior` |
| A36 | `tests.arena.test_verdict.VerdictTests.test_a36_ties_consume_task_cap_without_likelihood`<br>`tests.arena.test_verdict.VerdictTests.test_a36_upper_boundary_on_cap_takes_priority` |
| A37 | `tests.arena.test_verdict.VerdictTests.test_a37_hash_pinned_task_order_determines_first_terminal_prefix`<br>`tests.arena.test_verdict.VerdictTests.test_a37_favorable_prefix_with_unfinished_crossed_mate_cannot_win`<br>`tests.arena.test_verdict.VerdictTests.test_a37_out_of_order_real_closed_cells_keep_bank_order` |
| A38 | `tests.arena.test_verdict.VerdictTests.test_a38_verdict_schema_replay_finality_and_no_status_change`<br>`tests.arena.test_verdict.VerdictTests.test_a38_false_verdict_direct_append_refused` |
| A39 | `tests.arena.test_verdict.VerdictTests.test_a39_unrepresentable_commit_plan_refused_before_open`<br>`tests.arena.test_verdict.VerdictTests.test_a39_representable_plan_commit_has_exact_shape` |
| A40 | `tests.arena.test_extension.ExtensionTests.test_a40_dispatch_wraps_once_and_errors_map_to_cli`<br>`tests.arena.test_extension.ExtensionTests.test_a40_mcp_domain_error_is_result_with_is_error` |
| A41 | `tests.arena.test_declare.DeclarationTests.test_a7_run_requires_declaration_before_runner_or_journal`<br>`tests.arena.test_recovery.RecoveryTests.test_a7_direct_result_without_declaration_is_refused`<br>`tests.arena.test_declare.DeclarationTests.test_a6_direct_heldout_selection_result_is_forbidden`<br>`tests.arena.test_recovery.RecoveryTests.test_a41_result_without_actual_close_witness_is_rejected` |
| A42 | `tests.arena.test_bank.BankTests.test_a42_bundled_bank_is_synthetic_and_closed`<br>`tests.arena.test_extension.ExtensionTests.test_a42_public_output_offline_no_promotion_and_discoverable` |


## Integrated API adaptations (A-K0-9)

- `lineage/core/registry.py`: ToolSpec has `handler` and `mutating`, rather than
  `effect`; handlers receive `(args, *, context)`. Validators receive
  `(history, event)` rather than `(snapshot, event, ctx)`. Folds are callables,
  not FoldSpec records. Registry methods `descriptors` and `names` are absent;
  use its immutable maps and `app.list_tools(registry=...)`. Discovery uses
  `load(*, package=...)`. FoldSpec.order and the numerical arena order are
  unobservable here; this is an unverified core integration obligation.
- `lineage/core/app.py`: CallContext, create_context and DispatchResult replace
  the proposed Context/Services dispatch interface. Tests use actual
  `dispatch(..., context=..., registry=...)`, payload and exit_code. A test-local
  OracleContext extends CallContext to carry deterministic services for U16's
  specified domain ctx. Test-local Command is a data fixture because registry
  Command/Services/Committed and JSON record aliases are absent; no production
  substitute or shared-core edit is installed.
- `lineage/core/schema.py`: strict_loads/validate and SchemaError are the actual
  APIs; decode/canonical/digest/SchemaStore/load_record are absent. Canonical test
  bytes use independent standard-library JSON. The integrated subset does not
  support $ref, oneOf or exclusive bounds. Stub descriptors inline local refs,
  express the closed runner property union and inclusive probability bounds;
  exact alternative requirements and strict probability boundaries remain
  mandatory domain assertions. Full K0 discovery schema expressiveness remains
  an unverified core integration obligation; it is not claimed equivalent.
- `lineage/core/journal.py`: snapshot(home) returns a detached event tuple;
  transact(home, agent, op_id, kind, payload, validators, evidence, prepare,
  clock, id_factory, lock_timeout_s) returns Event. There is no append,
  Snapshot/Render transaction API, registry fold integration or expected_head
  argument. Direct append obligations use this actual locked transact path.
  Its replay digest binds kind/payload/evidence rather than tool/effective args;
  U16 must preserve root request identity and expected_head behavior itself.
  An observed explicit stub exception inside a validator is identified as a
  stub failure even though the journal sanitizes it to internal; validation still
  runs inside the real transaction. Other internal failures are not reclassified.
- `lineage/core/errors.py`: LineageError.detail can be a JSON value and defaults
  to None; no error_payload helper is present. Tests use code and the actual
  shared dispatch wrapper, never import the absent helper.
- `lineage/core/cli.py` and `lineage/core/mcp.py`: actual main functions accept
  injectable streams and registry; MCP also takes context. Tests invoke those
  APIs in memory instead of assuming the proposed no-argument signatures.
- U15 exports evaluate_sprt, evaluate_credit and aggregate_score instead of
  thresholds/update/decide, credit and correctness/compare. The installed policy
  also uses sample dispersion, first-seed retention and alpha+beta<1. Tests call
  U16's public verdict boundary and retain K0 population/cell-mean requirements;
  no replacement production statistics implementation is supplied.

## Decisions and honest integration limits

- A35's eight wins and three losses are below their respective thresholds.
  Public verdicts cannot store continue. When such a complete bank is exhausted,
  the expected recorded decision is inconclusive. Nine wins and four losses
  exercise the boundary through real engine-created task cells.
- Repetitions use distinct bench_run operations; exact operation retries do not
  count again. No particular digest spelling, staging filename or serialization
  strategy is asserted. Tamper tests locate only recovery artifacts in their
  temporary runtime home and never use a file as application completion authority.
- Runner unit fixtures seed valid immutable born/declaration/open event shapes
  with the actual journal. They do not simulate run.close or claim U13 behavior.
  End-to-end tests require actual U13 run and memory APIs and actual gate_passed
  journal witnesses. U13 run/memory/gate modules are absent in this workspace;
  tests reach U16's explicit stubs before importing those absent dependencies.
  Integrated U13 and U15 acceptance is AUSENTE — no inventar.
- CLI/MCP use the integrated boundary. JSON lane is absent. HTTP source imports
  K0 core names that the integrated core does not export, so HTTP parity is
  unavailable against this snapshot. Neither unavailable adapter counts as a
  transport pass. Completed-timeout domain success is tested; end-to-end
  timeout CLI success awaits real lifecycle integration.
- A41's declaration, split and close-witness rejecting tests are frozen mutant
  killers. Their present red-on-stub run is not a real-implementation mutation
  receipt. Removing an implemented central check in an isolated verification
  copy must later make its unchanged relevant negative assertion fail.
  A real-implementation mutant receipt, cross-family review, host acceptance
  gates, UI capsules, CDP and AT-SPI evidence remain AUSENTE — no inventar.
- No assertions, shared modules or other unit sources are weakened. The only
  persistent implementation artifacts are permitted U16 raising stubs and the
  synthetic bank/manifest. All runtime homes/evidence/children remain temporary.

## Baseline observations

Before U16 artifacts, the existing suite reported `Ran 643 tests in 20.983s`
[MEASURED], `FAILED (failures=2, skipped=3)` [MEASURED]. Those failures were
`tests.core.journal.test_concurrency.ConcurrencyTests.test_a6_eight_independent_writers_sixteen_operations_each`
(busy) and `tests.core.regression` (failed legacy family cursor import).
No baseline failure is represented as a new U16 acceptance witness.


## Verification observations

Required discovery command, exit status 1 [MEASURED]:

```text
Ran 121 tests in 2.958s

FAILED (failures=158)
```

121 test methods were red, none green [MEASURED]. There were 158 assertion
failure records because hostile-input subtests retain separate failures
[MEASURED], no errors and no skips [MEASURED]. A result audit checked that every
failure contains the explicit U16 stub marker, every method has a stub failure,
and each current stub-backed test completed below the five-second target
[MEASURED]. This timing is not a receipt for the future implemented engine.

The unchanged non-arena suite subsequently reported `Ran 643 tests in 21.080s`
and `FAILED (failures=1, skipped=3)` [MEASURED]. The remaining failure is the same
legacy regression family cursor import; the earlier busy race passed on rerun.
No additional existing-suite failure was observed. Stub function bodies,
manifest bytes and publishability were checked independently [MEASURED].


## Amendments A-U16

- `tests/arena/test_extension.py`, A1 discovery fixture: remove the temporary
  replacement module's cached bytecode before reimporting it. Equal-size fixture
  sources written within one timestamp tick can otherwise reuse the tool-only
  module while testing duplicate validators. Both exact rejection assertions
  remain unchanged; no application module or discovery API is patched.
- `tests/arena/test_extension.py`, A1 descriptor parity: compare CLI output with
  its integrated `{tools: descriptors}` envelope. The full descriptor list and
  successful exit assertion remain exact. MCP assertions are unchanged.
- `tests/arena/test_verdict.py`, A37 out-of-order closed-cell fixture: construct
  the direct `memory_put` Command using `agent_id`, `unit`, and `run_id`, matching
  the integrated `memory.units.put` API. Actual run, memory, close, result, order,
  and verdict assertions remain unchanged. No lifecycle witness is fabricated.

No frozen-input hash rows existed to update. Required behavior remains binding: a
missing token counter must permit entries within the byte-only allowance; absent
or incompatible dependency behavior remains a failing integration obligation.

- `tests/arena/helpers.py`, subject birth fixture: derive `brief_head_sha256`
  with the integrated `brief.build` API instead of an arbitrary digest. Agent
  publication continues through `agents.refresh_projections` and the integrated
  layout; immutable brief verification and all lifecycle assertions are retained.

- `tests/arena/helpers.py`, interruption helper: recognize the memory transaction
  kind on the integrated prepare callback as well as the native keyword.
  Before/after interruption assertions and durable journal checks are unchanged.
- `tests/arena/test_bench_execution.py`, A12: read the real `run_get.closed`
  record instead of the former `run` key, and additionally assert it exists.
  The required `memory.gate_passed` assertion is unchanged.
- `tests/arena/test_declare.py`, A10: use a success-only projection-tampering
  fixture so unrelated required failure-memory version advances do not change
  the asserted birth version. The dedicated A10 failure-memory test retains
  that separate version-advancement obligation. Resolve the tampered projection
  through `layout.agent_dir`, exercising the actual integrated projection path.
  Declaration, snapshot, and actual run-version assertions remain exact.

- `tests/arena/test_review_h1.py` adds h1 regression coverage without replacing
  frozen tests: bounded synthetic summary supersession with retained real run
  history; native sample-to-population credit adaptation and strict thresholds;
  K0-valid overlapping SPRT boundaries with actual closed cells; and unchanged
  caller OpIds that resemble private child identities, including frozen replay.

The h1 implementation adapts U15's installed `evaluate_credit` API, converting
its measured sample variance to population variance and enforcing the declared
minimum gain. Singleton dispersion is zero without invented duplicate samples.
It also uses native SPRT likelihood/count reports for the K0 parameter range
excluded by U15's additional alpha/beta restriction. These are private U16
adapters; no U15 source or frozen behavioral assertion is changed.

- `tests/arena/helpers.py` and `tests/arena/test_verdict.py`, custom crossed,
  repeated, and manually closed fixtures: explicitly declare supersession of
  prior closed-run summaries before real memory admission. Integrated memory
  enforces bounded active entries with no token counter; immutable episodes,
  lessons, negatives, and gated run history remain in the journal. No task, cell,
  outcome, ordering, credit, or verdict assertion is removed or widened. Child
  command fixtures keep their closed stdout schema and default no-supersession
  behavior; production never rewrites supplied command memory.
