# U08 fail-first constitution oracle

The normative target is SPEC_U08, including Amendment B. Tests use stdlib
`unittest` and exercise the documented public callable without installing a stub,
changing implementation code, or reading another project checkout. Existing
`tests/constitution/__init__.py` remains unchanged.

## Surface and execution

| File | Purpose |
|---|---|
| `tests/constitution/support.py` | Public synthetic inputs, strict fixture reads, black-box assertions, independent citation/publication checks |
| `tests/constitution/test_contract.py` | API, pins, purity, complete audits, actual reference handoff |
| `tests/constitution/test_determinism.py` | Complete byte layout, normalization, hashes, clock/environment independence |
| `tests/constitution/test_citations.py` | Citation identity, source coordinates, suffix integrity, negative controls |
| `tests/constitution/test_authority.py` | Capability ceilings/intersection, protected invariants, writer boundaries |
| `tests/constitution/test_overlays.py` | Policy coverage, explicit applicability, scrub handling, language gates, claims/conflicts |
| `tests/constitution/test_hostile.py` | Hostile syntax/prose, inactive entries, safe diagnostics, publication examples |
| `tests/constitution/ORACLE.md` | Acceptance map and explicitly unresolved contracts |

Run from the project root with bytecode writing disabled:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/constitution -t .
```

All compiler invocations receive byte strings and in-memory mappings. Public
policy fixtures are read before compilation and before side-effect instrumentation.
They provide the otherwise unspecified protected prose/applicability-field name;
there is no guessed fallback policy. Synthetic registries contain no source-paper
extracts. Tests do not create files, download dependencies, access the network,
sleep, create process groups, or send signals. Process APIs occur only as mocks.
Each actual scrub-record check is a separate test to bound its work.

## Acceptance map

Aliases below refer to modules under `tests.constitution`:

| Alias | Test class |
|---|---|
| C | `test_contract.ContractTests` |
| D | `test_determinism.DeterminismTests` |
| Q | `test_citations.CitationTests` |
| A | `test_authority.AuthorityTests` |
| O | `test_overlays.OverlayTests` |
| H | `test_hostile.HostileTests` |

Every test name below is an assertion-bearing test. Expected rejection tests
require `ConstitutionError`, a permitted exact code/reason pair, closed diagnostic
keys, sorted unique identifiers, rooted pointers, and unchanged inputs where
structural equality is defined. No exception/skip counts as implemented behavior.

| Acceptance | Test names | Scope / admission limit |
|---|---|---|
| A1 | C.test_public_api_result_and_frozen_fields; C.test_compilation_and_failure_have_no_io_or_input_mutation | Exact result fields, frozen objects, pins, input snapshots, forbidden entry points |
| A2 | C.test_actual_u07_pins_and_tamper_rejection; C.test_exact_registry_byte_pin_precedes_decode; C.test_source_provenance_pin_is_independent; C.test_source_pin_cannot_substitute_for_registry_artifact_pin | Actual artifact needs its independent manifest pin; synthetic pin tests are additional coverage |
| A3 | C.test_missing_and_malformed_pins_are_bad_args; C.test_missing_source_fields_reject; C.test_unknown_role_and_language_have_no_coercion | Omitting a pin keyword is tested as well as malformed/null values; actual absence is HOLD |
| A4 | H.test_invalid_utf8_json_trailing_data_and_duplicate_keys_reject; H.test_nonfinite_json_numbers_and_unpaired_surrogates_reject; H.test_unknown_fields_at_all_input_depths_reject; H.test_bad_rule_fields_and_native_coordinate_types_reject; H.test_cycles_in_direct_policy_mappings_are_rejected_without_mutation; H.test_direct_policy_values_must_be_native_finite_json | Repinned payloads reach syntax/shape checks rather than failing the artifact pin |
| A5 | O.test_matrix_requires_exact_rule_coverage; O.test_matrix_requires_exact_real_role_identifiers; O.test_duplicate_and_unknown_registry_rules_reject; C.test_complete_dispositions_and_exclusion_precedence; C.test_integrated_role_author | Actual inventory and identity coverage; no padded or truncated policy |
| A6 | D.test_reordered_objects_rules_roles_and_policies_are_identical; D.test_serialization_whitespace_is_not_normative; D.test_normative_change_changes_digest_and_preserves_source_coordinates | Raw bytes are independently repinned; ordered coordinate pairs are preserved |
| A7 | D.test_exact_complete_markdown_bytes; D.test_clock_and_environment_do_not_change_bytes; D.test_excluding_all_ordinary_rules_keeps_protected_rules_and_final_lf | Entire fixture bytes, LF/final newline, no raw artifact pin; empty-included ambiguity is recorded below |
| A8 | Q.test_every_bullet_resolves_and_original_names_survive; Q.test_mismatched_section_endpoint_and_extra_citation_reject; Q.test_identifier_numeric_section_must_match_section; Q.test_unknown_citation_identity_is_not_accepted_as_a_rule; Q.test_replacement_cannot_supply_a_counterfeit_source_citation; Q.test_citation_audit_rejects_forged_missing_or_wrong_coordinate_lines | Canonical source suffix and citation identity checked independently; missing-suffix contract remains unresolved |
| A9 | C.test_unknown_role_and_language_have_no_coercion; H.test_all_schema_identity_arrays_are_unique_and_constrained; H.test_empty_constrained_lists_reject_without_defaulting; all C.test_integrated_role_* below | Exact real role/language identifiers, no nearest-role conversion |
| A10 | A.test_reviewers_keep_own_memory_without_repository_authority; A.test_matrix_cannot_expand_any_reviewer_ceiling; A.test_overlay_write_claim_cannot_expand_reviewer_authority | Repository writing remains distinct from own-memory writing |
| A11 | A.test_author_plus_reviewer_uses_intersection_in_both_orders; D.test_duplicate_requested_roles_collapse; A.test_matrix_may_restrict_but_never_union_capabilities; A.test_empty_capability_set_is_valid_and_never_defaults_to_maximum | Set intersection, duplicate argument collapse, absence versus valid empty capabilities |
| A12 | A.test_writers_have_exact_distinct_ceiling_and_no_privileged_capability; A.test_checked_in_writer_prose_preserves_scope_and_oracle_boundaries | Checked-in prose inspection supplements structural capabilities; source-grounded prose review remains external |
| A13 | A.test_protected_rules_appear_for_every_role_and_language; A.test_protected_rules_cannot_be_excluded_or_reworded; A.test_protected_rules_cannot_be_role_or_language_filtered; A.test_protected_rules_cannot_acquire_write_prerequisites; A.test_protected_claim_changes_reject_with_stable_conflict | Protects GS-4.1-20 / GS-4.1-21 / GS-4.1-22; fixed prose comes from public policy, never private constants |
| A14 | All C.test_actual_scrub_index_* below; O.test_selected_scrub_requires_replacement_or_explicit_exclusion; O.test_inapplicable_scrub_is_a_filter_not_a_successful_adaptation | Each actual scrub record gets an applicable role/language; no raw-source fallback |
| A15 | O.test_non_scrubbed_denied_verbatim_requires_overlay; O.test_applicability_boolean_is_required_and_native; O.test_python_mixed_gate_adaptations_keep_obligations_without_foreign_legs; O.test_actual_python_compound_gates_are_retained_and_adapted | GS-2.4-4 and non-scrubbed GS-2.4-7 retain applicable obligations |
| A16 | O.test_typescript_and_general_select_only_explicit_language_legs; Q.test_coordinate_pair_stays_ordered; all C.test_integrated_role_* below | General is a separate selected language; coordinate order is not canonicalized away |
| A17 | O.test_selected_scrub_requires_replacement_or_explicit_exclusion; O.test_overlay_references_and_exclusion_shape_are_closed; O.test_overlay_roles_must_be_within_the_rule_projection; H.test_unresolved_template_markers_never_reach_output | Missing resolution, unsupported references, and placeholders reject |
| A18 | O.test_equivalent_overlays_coalesce_despite_claim_and_reason_order; O.test_different_replacements_and_replace_versus_exclude_conflict; O.test_each_unsupported_or_wrong_baseline_claim_rejects | No first/last-match priority; claim order and public explanations do not choose a resolution |
| A19 | O.test_claim_keys_are_closed_complete_and_unique; O.test_each_unsupported_or_wrong_baseline_claim_rejects; O.test_inactive_claims_validate_against_declared_role_and_language; O.test_multilanguage_and_mixed_capability_class_entries_reject | Amendment B's declared scope, single-language entries, and homogeneous access classes |
| A20 | H.test_hostile_active_and_inactive_overlay_text_and_reason_reject; H.test_registry_text_cannot_escape_single_line_markdown; H.test_embedded_process_text_is_never_executed; H.test_identifiers_cannot_encode_directives_or_leak_diagnostics; H.test_unknown_fields_at_all_input_depths_reject | Registry strings and inactive overlays are passive, fully validated data |
| A21 | H.test_publication_rejects_constructed_sensitive_literals; H.test_safe_repository_relative_identifier_is_preserved; all C.test_integrated_role_* below | Runtime-assembled fictional sensitive examples and conservative screen; U07's external publication gate/private-binding lexicon remain AUSENTE — no inventar |
| A22 | O.test_historical_seat_values_never_become_present_defaults; all C.test_integrated_role_* below | GS-5-1 through GS-5-9 synthetic seat history stays evidence; ACTIVE/ASSEMBLED/DRAFT never become fabricated admission metadata |
| A23 | C.test_complete_dispositions_and_exclusion_precedence; O.test_inapplicable_scrub_is_a_filter_not_a_successful_adaptation | Role, then language, then capability, then explicit exclusion; full sorted audit |
| A24 | H.test_failure_diagnostics_are_safe_stable_and_do_not_mutate_inputs; H.test_invalid_object_key_order_does_not_change_diagnostics; O.test_different_replacements_and_replace_versus_exclude_conflict; A.test_protected_claim_changes_reject_with_stable_conflict | Stable safe errors across input reordering; no partial document |
| A25 | D.test_normative_change_changes_digest_and_preserves_source_coordinates; D.test_reordered_objects_rules_roles_and_policies_are_identical; C.test_no_agent_version_or_birth_side_effect_is_returned | Independently hashed exact Markdown is not an agent version or birth event |
| A26 | C.test_public_api_result_and_frozen_fields; host discovery and outside-surface byte comparison | HOLD: no compiler/callable stub exists. User forbids creating stubs, so current API-absence assertions do not establish the required deeper behavioral fail-first evidence. Oracle byte preservation requires host sealing after delivery |
| A27 | All discovered tests; the exact unit command above | Discovery reaches test assertions without import errors. Eventual green requires actual artifacts and parent packages; no recursive suite invocation is hidden inside a test |
| A28 | All C.test_integrated_role_* and C.test_actual_scrub_index_* below; C.test_actual_u07_pins_and_tamper_rejection; O.test_actual_python_compound_gates_are_retained_and_adapted | Actual reference verification, citations, dispositions, authority/language checks; unresolved K0/publication contracts keep integration HOLD |

## Explicit generated test names

The actual-role tests compile every supported language independently for that
role. Actual-scrub tests select the indexed marked record in lexicographic rule-id
order, check the declared inventory, and choose an exercisable role/language.
These names identify tests, not invented source rules.

| Group | Exact test name |
|---|---|
| Actual role | C.test_integrated_role_agent_creator |
| Actual role | C.test_integrated_role_author |
| Actual role | C.test_integrated_role_capsule_tester |
| Actual role | C.test_integrated_role_cross_reviewer |
| Actual role | C.test_integrated_role_oracle_writer |
| Actual role | C.test_integrated_role_orchestrator |
| Actual role | C.test_integrated_role_performance_auditor |
| Actual role | C.test_integrated_role_persona |
| Actual role | C.test_integrated_role_privacy_verifier |
| Actual role | C.test_integrated_role_repairer |
| Actual role | C.test_integrated_role_researcher |
| Actual scrub record | C.test_actual_scrub_index_00 |
| Actual scrub record | C.test_actual_scrub_index_01 |
| Actual scrub record | C.test_actual_scrub_index_02 |
| Actual scrub record | C.test_actual_scrub_index_03 |
| Actual scrub record | C.test_actual_scrub_index_04 |
| Actual scrub record | C.test_actual_scrub_index_05 |
| Actual scrub record | C.test_actual_scrub_index_06 |
| Actual scrub record | C.test_actual_scrub_index_07 |
| Actual scrub record | C.test_actual_scrub_index_08 |
| Actual scrub record | C.test_actual_scrub_index_09 |
| Actual scrub record | C.test_actual_scrub_index_10 |
| Actual scrub record | C.test_actual_scrub_index_11 |
| Actual scrub record | C.test_actual_scrub_index_12 |
| Actual scrub record | C.test_actual_scrub_index_13 |
| Actual scrub record | C.test_actual_scrub_index_14 |
| Actual scrub record | C.test_actual_scrub_index_15 |
| Actual scrub record | C.test_actual_scrub_index_16 |
| Actual scrub record | C.test_actual_scrub_index_17 |
| Actual scrub record | C.test_actual_scrub_index_18 |
| Actual scrub record | C.test_actual_scrub_index_19 |
| Actual scrub record | C.test_actual_scrub_index_20 |
| Actual scrub record | C.test_actual_scrub_index_21 |
| Actual scrub record | C.test_actual_scrub_index_22 |
| Actual scrub record | C.test_actual_scrub_index_23 |
| Actual scrub record | C.test_actual_scrub_index_24 |
| Actual scrub record | C.test_actual_scrub_index_25 |
| Actual scrub record | C.test_actual_scrub_index_26 |
| Actual scrub record | C.test_actual_scrub_index_27 |
| Actual scrub record | C.test_actual_scrub_index_28 |
| Actual scrub record | C.test_actual_scrub_index_29 |
| Actual scrub record | C.test_actual_scrub_index_30 |
| Actual scrub record | C.test_actual_scrub_index_31 |

## Ambiguities and limits

| Contract issue | Treatment in this oracle |
|---|---|
| K0 callable/citation shape conflicts with SPEC_U08; Amendment B requests a workflow/overlay-id mapping without defining one | Tests target the explicit U08 pure API and line-span citation. No mapping, overload, or adapter is invented. Integration remains HOLD against unamended K0 |
| Applicability boolean has no prescribed field name | Read its spelling from the shipped public matrix as the single additional native-boolean rule field. Missing/ambiguous public evidence fails HOLD; no fallback field is chosen |
| Protected prose and whether as-registered forms are permitted are not fully specified | Reuse reviewed checked-in replacement forms for the effective access class and preserve fixed protected source invariants in the synthetic input. Never invent exact required prose or require a particular adapted/as-registered disposition. Mutated protected resolutions must reject |
| Protected claim-error precedence is not fixed | Require conflict with protected_rule_change or authority_escalation and demand identical diagnostics under reordering. Do not pick an arbitrary precedence |
| All ordinary rules can be excluded, but protected rules must remain included | Test that reachable boundary and its exact final LF. A successful zero-included constitution is not assumed to exist |
| Coalescing whitespace rules are undefined | Test identical text with reordered claims and differing reasons. No trim/collapse policy is imposed on leading/trailing whitespace |
| Registry suffix absence is unresolved, unlike inconsistent/forged suffixes | Test inconsistent coordinates, forged suffixes, and exact stripping of valid suffixes. Do not choose whether a suffix-free registered text is permitted |
| Lexical unsafe-text/private-binding policy and the external U07 publication command are unspecified | Test clearly hostile line/control/markup inputs and runtime-assembled fictional public examples; use a conservative independent screen. Do not claim this proves the absent U07 gate or arbitrary prose consistency |
| Error reasons are not fixed for every malformed overlay/structural subtype | Require the narrow defined diagnostic alternatives where the spec leaves classification open; exact named reasons remain exact for hashes, unresolved overlays, coverage, reference errors, and Amendment B scope restrictions |
| Omitted required Python pin keyword versus structured bad_args | Encode A3's explicit structured-error requirement without constraining parameter defaults. A bare TypeError does not pass |
| Duplicate requested roles versus unique schema arrays | Collapse duplicates only in the function argument; reject duplicates in schema-constrained identity arrays |
| Shipped artifact pins versus inspected pre-work serialization | Obtain the artifact digest independently from references/MANIFEST.sha256. Keep source provenance pinned to the spec's supplied source hash; never treat a self-declared digest as independent verification |

Current prerequisites are AUSENTE: `lineage/domain/constitution.py`,
`lineage/domain/data/role_matrix.json`, `lineage/domain/data/overlays.json`,
`references/gold_s1/gold_rules.json`, and `references/MANIFEST.sha256`.
An assertion identifying absent compiler behavior is the current red baseline,
not proof that hash/authority/overlay behavior has been exercised. No fixture,
syntax-green result, missing dependency, skip, or discovery success can produce
ADMIT. Behavioral mutation evidence, frozen-oracle integrity at later integration,
source-grounded prose review, and the actual U07 publication gate remain HOLD.

## Observed isolated baseline

The delivered suite discovers 118 tests [MEASURED]: 118 red test cases,
0 green test cases, 0 errors, and 0 skips [MEASURED]. Every failure is the explicit
missing-compiler assertion, with no import-error traceback. The exact stable
summary line is:

```text
FAILED (failures=118)
```

The existing project test surface discovered no tests before this addition
[MEASURED]. Root discovery after the addition reports the same constitution-only
failures [MEASURED]. These observations establish discovery and a safe absent-API
red baseline; they do not establish behavioral fail-first coverage or integration
admission. The acceptance map contains all A1 through A28 identifiers [MEASURED].


## Amendments A-U08

- A-U08: Reconciled argument plumbing in
  `test_actual_python_compound_gates_are_retained_and_adapted` with integrated
  U07's `references/gold_s1/gold_rules.json`: `GS-2.4-4` includes `orchestrator`
  but excludes `performance_auditor`. The auditor case now requests both roles,
  retaining their read-only capability intersection. Every existing behavioral
  assertion and both original cases remain unchanged; no registry, policy,
  source pin, or expected outcome is altered. A standalone auditor must still
  exclude that rule under the specified role-first resolution algorithm.
- Added `test_review_h1.py` to assert standalone auditor exclusion, applicable
  `GS-2.4-7` adaptation, read-only combined-role inclusion of both gates,
  citation integrity, language applicability and role-order determinism.
