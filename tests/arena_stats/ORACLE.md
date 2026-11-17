# U15 fail-first statistical oracle

Scope: the pure helper APIs specified in `.unit/SPEC.md`, including Amendment B.
All mathematical fixtures, bounds and intended outcomes are [TARGET] unless a
verification result below is explicitly tagged [MEASURED]. The oracle uses only
stdlib `unittest`; no historical benchmark receipts or correctness labels.

## Test surface and execution

Files: `tests/arena_stats/__init__.py`, `tests/arena_stats/test_sprt.py`,
`tests/arena_stats/test_credit.py`, `tests/arena_stats/test_score.py`,
`tests/arena_stats/test_rating.py`, `tests/arena_stats/test_contract.py`,
`tests/arena_stats/ORACLE.md`.

Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/arena_stats -t .
```

The package initializer holds fixtures and assertion helpers, and imports no
implementation. There are no implementation stubs, skipped requirements,
installed dependencies, network calls, real sleeps or subprocess launches in
these tests. Missing implementation source fails an explicit public-behavior
assertion before importing it; present implementations are exercised through
the required module-level APIs. An import failure is never an admitted green
result. Source-presence failures do not establish mathematical correctness.

Surface confinement and frozen-oracle integrity are external prerequisites to
interpreting any suite result: compare all project file hashes with the
pre-edit snapshot, allowing changes only beneath `tests/arena_stats`.
The isolated project has no Git metadata. Baseline discovery found no existing
assertion tests [MEASURED]; this is absence of prior coverage, not a prior pass.
No change to another project or frozen contract is authorized.

## Acceptance-to-test map

Each row names executable assertions, not a documentation-only promise.
Subtests cover positive, negative and hostile variants within the named case.

| Acceptance | Tests |
|---|---|
| A1 | `test_contract.ContractTests.test_a01_public_signatures_and_exception`<br>`test_contract.ContractTests.test_a01_closed_outputs_and_cross_module_smoke`<br>`test_contract.ContractTests.test_a01_only_stdlib_and_owned_modules_are_imported` |
| A2 | `test_sprt.SPRTTests.test_a02_binding_win_prefixes`<br>`test_sprt.SPRTTests.test_a02_binding_loss_prefixes` |
| A3 | `test_sprt.SPRTTests.test_a03_natural_log_formulas`<br>`test_sprt.SPRTTests.test_a03_unique_ties_add_no_evidence` |
| A4 | `test_sprt.SPRTTests.test_a04_exact_upper_boundary_is_inclusive`<br>`test_sprt.SPRTTests.test_a04_exact_lower_boundary_is_inclusive` |
| A5 | `test_sprt.SPRTTests.test_a05_terminal_prefix_is_immutable` |
| A6 | `test_sprt.SPRTTests.test_a06_tie_cap_and_empty_input` |
| A7 | `test_sprt.SPRTTests.test_a07_boundary_precedes_cap` |
| A8 | `test_sprt.SPRTTests.test_a08_repeated_seeds_are_one_task` |
| A9 | `test_score.ScoreTests.test_a09_a16_redelivery_and_changed_same_seed`<br>`test_sprt.SPRTTests.test_a09_redelivery_and_first_seed` |
| A10 | `test_sprt.SPRTTests.test_a10_probabilities_and_error_bounds`<br>`test_sprt.SPRTTests.test_a10_cap_is_a_positive_native_integer`<br>`test_sprt.SPRTTests.test_a10_closed_outcome_schema_and_native_types` |
| A11 | `test_credit.CreditTests.test_a11_complete_rule_and_declaration_precedence`<br>`test_credit.CreditTests.test_a11_closed_rule_validation` |
| A12 | `test_credit.CreditTests.test_a12_sample_dispersion_and_strict_credit` |
| A13 | `test_credit.CreditTests.test_a13_correctness_gain_is_directional`<br>`test_credit.CreditTests.test_a13_lower_cost_and_constant_baseline` |
| A14 | `test_credit.CreditTests.test_a14_missing_and_insufficient_evidence`<br>`test_credit.CreditTests.test_a14_validate_every_value_before_null_gate` |
| A15 | `test_credit.CreditTests.test_a15_invalid_measurements`<br>`test_credit.CreditTests.test_a15_resilient_large_finite_dispersion`<br>`test_credit.CreditTests.test_a15_unrepresentable_arithmetic_is_domain_error` |
| A16 | `test_score.ScoreTests.test_a16_counts_sorted_tasks_and_first_seed`<br>`test_score.ScoreTests.test_a09_a16_redelivery_and_changed_same_seed` |
| A17 | `test_score.ScoreTests.test_a17_only_explicit_correctness_boolean`<br>`test_score.ScoreTests.test_a17_empty_score_preserves_null`<br>`test_score.ScoreTests.test_a17_empty_rows_still_validate_identity` |
| A18 | `test_score.ScoreTests.test_a18_each_cost_field_keeps_unknowns_and_zero`<br>`test_score.ScoreTests.test_a18_unknown_is_distinct_from_measured_zero`<br>`test_score.ScoreTests.test_a18_totals_use_integer_arithmetic` |
| A19 | `test_score.ScoreTests.test_a19_invalid_cost_values_identify_the_field`<br>`test_score.ScoreTests.test_a19_closed_nested_cost_objects`<br>`test_score.ScoreTests.test_a19_row_container_task_and_seed_validation` |
| A20 | `test_rating.RatingTests.test_a20_full_identity_remains_separate`<br>`test_score.ScoreTests.test_a20_preserves_all_identity_components`<br>`test_score.ScoreTests.test_a20_invalid_seat_and_memory_identity` |
| A21 | `test_rating.RatingTests.test_a21_correctness_precedes_extreme_cost` |
| A22 | `test_rating.RatingTests.test_a22_complete_chosen_cost_breaks_correctness_ties`<br>`test_rating.RatingTests.test_a22_any_incomplete_member_ties_the_entire_group`<br>`test_rating.RatingTests.test_a22_exact_ratios_override_rounded_equal_means` |
| A23 | `test_rating.RatingTests.test_a23_evidence_ties_identity_order_and_dense_ranks`<br>`test_rating.RatingTests.test_a23_empty_rating` |
| A24 | `test_rating.RatingTests.test_a24_cost_metric_validated_even_on_empty_input`<br>`test_rating.RatingTests.test_a24_duplicate_series_task_mismatch_and_empty_tasks`<br>`test_rating.RatingTests.test_a24_invalid_scorecard_shape_counts_and_task_order`<br>`test_rating.RatingTests.test_a24_correctness_requires_exact_float_fraction`<br>`test_rating.RatingTests.test_a24_cost_summary_consistency_and_closure`<br>`test_rating.RatingTests.test_a24_subclass_counts_are_not_native_integers` |
| A25 | `test_score.ScoreTests.test_a25_duplicate_task_does_not_bypass_validation`<br>`test_sprt.SPRTTests.test_a25_entire_terminal_suffix_is_validated`<br>`test_sprt.SPRTTests.test_a25_post_terminal_conflicting_redelivery` |
| A26 | `test_contract.ContractTests.test_a26_inputs_unchanged_and_nested_outputs_detached`<br>`test_contract.ContractTests.test_a26_repeat_calls_ignore_unrelated_calls_clock_and_random_state`<br>`test_contract.ContractTests.test_a26_import_and_computation_have_no_external_effects` |
| A27 | `test_contract.MutationControls.test_a27_tie_filter_mutant_is_rejected`<br>`test_contract.MutationControls.test_a27_task_deduplication_mutant_is_rejected`<br>`test_contract.MutationControls.test_a27_strict_credit_mutant_is_rejected`<br>`test_contract.MutationControls.test_a27_correctness_priority_mutant_is_rejected` |

## Amendment interpretations and limits

- Cap exhaustion is terminal: `inconclusive` names the cap task in `stopped_at`;
  only `continue` has a null stop marker. Boundary checks precede cap checks.
- Credit validation follows declaration absence, rule validity, every measurement,
  then missing/insufficient evidence. `[None, -1]` is invalid, not ineligible.
- Choose resilient sample dispersion. The concrete large finite fixture is
  candidate `0`, baseline `[0.0, 1e308, 1e308]`: finite mean and sample standard
  deviation must be returned despite overflow in naive squared deviations.
  Integers whose computed float values are unrepresentable raise `bad_args`.
- Scorecard correctness and measured means are native `float` values and must
  exactly equal the specified divisions. Adjacent representable fractions are
  invalid; diagnostic tolerance never changes decisions or input validation.
  Integer ratios determine cost order even when displayed float means coincide.
- Empty inputs still validate parameters. Repetition counts are nonnegative;
  task counts match distinct, nonempty, strictly ascending task identities.
- Native means exact built-in types: tuples, subclasses and `IntEnum` are not
  interchangeable with lists, dictionaries, strings or integers. Lone surrogates
  are invalid Unicode scalar strings. Agent identifiers reject trailing LF.
  Whitespace-only task/seat policy remains unspecified: Amendment B requests a
  clarification but does not choose one. No test invents a whitespace policy.
- Full validation includes conflicting same-seed redelivery in terminal suffixes,
  including conflicts wholly inside the suffix and behind already-ignored tasks.

## K0 integration boundary

`docs/INTERFACES.md` names `thresholds`, `update`, `decide`, `correctness`,
`compare`, `credit`, and `fold`; this oracle tests the explicitly requested U15
`evaluate_sprt`, `evaluate_credit`, `aggregate_score`, and `rank_pairs` instead.
`ArenaStatsError` is the pure statistical exception; transport errors and
`bench.verdict` emission remain outside this unit.

`docs/CONTRACT.md` specifies population dispersion plus `minimum_gain` for
benchmark correctness credit. U15 explicitly specifies a scalar `CreditRule`
with `sample_stddev`. This oracle verifies that U15 helper contract and does not
assert that it replaces K0 benchmark credit. The conflicting integration
semantics require reconciliation before integration; K0 compatibility is not
certified and neither frozen document is changed. Valid seat fixtures also
satisfy K0, without imposing additional undocumented helper constraints.

## Purity and negative controls

Purity tests pre-read and compile only the exclusive implementation sources,
then import fresh modules using an in-memory loader with file, network, process,
clock and randomness entry points patched to reject calls. Valid and invalid
computations are checked. Package initialization must not eagerly import its
statistical submodules. Returned nested records must not alias caller inputs or
become cross-call mutable state.

The A27 controls patch one public function at a time in memory in this isolated
verification copy: tie filtering, task independence, strict credit comparison,
and correctness-first ranking. They rerun the corresponding acceptance case.
The nominal case must pass first; the mutant must produce assertion failures,
with no errors or skips. An unavailable nominal implementation fails the
control and cannot be reported as a killed mutant. No patched implementation
or extra verification copy is written to disk.

This oracle's mandate is confined to the supplied U15 specification,
Amendment B, North Star and inspected K0 contract surface.
