# U17 fail-first oracle

Scope: `.unit/SPEC.md`, including Amendment B; bundled K0 schemas and installed APIs.
This is a frozen oracle map, not an ADMIT receipt. Runtime/cross-family/capsule
receipts are AUSENTE. No model, network, package installation or source-project
write is part of the oracle. All mutations are confined to the assigned surface
and disposable directories beneath `tests/breeding/one/`.

Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/breeding/one -t .
```

`NotImplementedError("U17 stub")` is the intended initial behavioral failure.
No test expects or catches that exception as success. Green discovery/strict-JSON
checks establish those installed boundaries only; they do not establish births,
inheritance, retirement, replay, projection repair or host acceptance.

## Acceptance map

Every named method below is discoverable. Each row states its verification gate
and rejecting contrast. Matrix methods enumerate their declared inputs directly;
the first exception terminates a method, so error entries count test methods.

| Spec case | Test names | Verification gate | Rejecting contrast / outstanding gate |
|---|---|---|---|
| A1 | `ExtensionOracle.test_a01_discovery_exact_tools_flags_owners_and_handler_convention`<br>`ExtensionOracle.test_a01_duplicate_fold_blocks_load`<br>`ExtensionOracle.test_a01_duplicate_tool_blocks_load`<br>`ExtensionOracle.test_a01_duplicate_validator_blocks_load`<br>`ExtensionOracle.test_a01_loaded_registry_is_immutable_and_import_has_no_registration_side_effect` | Installed discovery, immutable registry, exact flags and unique ownership. | Duplicate tool/validator/fold must refuse atomically; absent U12 delegation is HOLD. |
| A2 | `CloneOracle.test_a02_reserved_child_operator_is_bad_args`<br>`CloneOracle.test_a02_reserved_child_system_is_bad_args`<br>`ExtensionOracle.test_a02_arbitrary_creator_is_not_forced_to_equal_parent`<br>`ExtensionOracle.test_a02_discovery_schemas_are_closed_and_required_fields_exact`<br>`ExtensionOracle.test_a02_operator_argument_cannot_confer_ruling_authority`<br>`ExtensionOracle.test_a02_rejects_boolean_head`<br>`ExtensionOracle.test_a02_rejects_child_newline`<br>`ExtensionOracle.test_a02_rejects_client_gate`<br>`ExtensionOracle.test_a02_rejects_client_hash`<br>`ExtensionOracle.test_a02_rejects_client_inherited`<br>`ExtensionOracle.test_a02_rejects_client_record`<br>`ExtensionOracle.test_a02_rejects_client_status`<br>`ExtensionOracle.test_a02_rejects_duplicate_selection`<br>`ExtensionOracle.test_a02_rejects_empty_display_name`<br>`ExtensionOracle.test_a02_rejects_integer_retirement_filter`<br>`ExtensionOracle.test_a02_rejects_long_child`<br>`ExtensionOracle.test_a02_rejects_long_display_name`<br>`ExtensionOracle.test_a02_rejects_malformed_child`<br>`ExtensionOracle.test_a02_rejects_missing_actor`<br>`ExtensionOracle.test_a02_rejects_missing_op_id`<br>`ExtensionOracle.test_a02_rejects_negative_head`<br>`ExtensionOracle.test_a02_rejects_nested_selection_record`<br>`ExtensionOracle.test_a02_rejects_null_display_name`<br>`ExtensionOracle.test_a02_rejects_null_expected_head`<br>`ExtensionOracle.test_a02_rejects_null_retirement_filter`<br>`ExtensionOracle.test_a02_rejects_null_root`<br>`ExtensionOracle.test_a02_rejects_null_selection`<br>`ExtensionOracle.test_a02_rejects_oversize_selection`<br>`ExtensionOracle.test_a02_rejects_short_child`<br>`ExtensionOracle.test_a02_rejects_unsafe_integer_head`<br>`ExtensionOracle.test_a02_strict_json_duplicate_keys`<br>`ExtensionOracle.test_a02_strict_json_invalid_utf8`<br>`ExtensionOracle.test_a02_strict_json_nested_duplicate_keys`<br>`ExtensionOracle.test_a02_strict_json_nonfinite`<br>`ExtensionOracle.test_a02_strict_json_overflow_float`<br>`ExtensionOracle.test_a02_strict_json_unpaired_surrogate`<br>`ExtensionOracle.test_a02_valid_read_defaults_produce_one_untrusted_wrapper`<br>`RetirementOracle.test_a02_operator_retire_does_not_create_ruling_authority` | Closed schemas, required actor/op_id, declared defaults, strict JSON and reserved identities. | Null, unknown fields, malformed IDs, Boolean integer, spoofed authority and ambiguous JSON refuse without append. |
| A3 | `CloneOracle.test_a03_existing_child_or_same_identity_is_conflict`<br>`CloneOracle.test_a03_missing_parent_is_no_agent_without_append`<br>`CloneOracle.test_a03_retired_parent_cannot_authorize_birth` | Source existence, lifecycle and child identity checks. | Absent source no_agent; retired/existing/same identity conflict. Real damaged-pin checks remain HOLD. |
| A4 | `InheritanceOracle.test_a04_positive_matrix_receipts_hashes_and_complete_wrappers` | Active receipt-backed lesson/negative/promoted-workflow matrix, public/internal and matching/general scopes. | Reject-all, receipt presence without matching bytes, or incomplete wrappers fail. |
| A5 | `InheritanceOracle.test_a05_excludes_decision`<br>`InheritanceOracle.test_a05_excludes_draft`<br>`InheritanceOracle.test_a05_excludes_episode`<br>`InheritanceOracle.test_a05_excludes_invalid_receipt`<br>`InheritanceOracle.test_a05_excludes_level_one`<br>`InheritanceOracle.test_a05_excludes_level_three`<br>`InheritanceOracle.test_a05_excludes_missing_receipt`<br>`InheritanceOracle.test_a05_excludes_not_promoted`<br>`InheritanceOracle.test_a05_excludes_open_item`<br>`InheritanceOracle.test_a05_excludes_private`<br>`InheritanceOracle.test_a05_excludes_retired`<br>`InheritanceOracle.test_a05_excludes_superseded`<br>`InheritanceOracle.test_a05_excludes_workflow_retired`<br>`InheritanceOracle.test_a05_excludes_wrong_language`<br>`InheritanceOracle.test_a05_excludes_wrong_workflow`<br>`InheritanceOracle.test_a05_general_target_does_not_broaden_concrete_language` | Complete exclusion vocabulary with exact ID/reason-only audit. | Admit-all, private payload leakage, decision/open_item, inactive statuses or broadened language fail. |
| A6 | `InheritanceOracle.test_a06_overlapping_reasons_follow_declared_precedence`<br>`InheritanceOracle.test_a06_parent_and_unit_permutations_have_identical_audit_bytes` | First applicable safety reason and source-sorted audit independent of input order. | Selection-first, private-first for an episode, or enumeration-order audit fail. |
| A7 | `DistillOracle.test_a07_existing_excluded_selection_is_audited_and_birth_succeeds`<br>`DistillOracle.test_a07_omission_selects_all_eligible_without_paraphrase`<br>`DistillOracle.test_a07_unknown_selected_id_is_bad_args_without_birth`<br>`InheritanceOracle.test_a07_duplicate_selection_is_bad_args`<br>`InheritanceOracle.test_a07_none_empty_and_subset_are_distinct`<br>`InheritanceOracle.test_a07_selected_excluded_unit_keeps_its_safety_reason`<br>`InheritanceOracle.test_a07_unknown_or_foreign_selection_is_bad_args` | Omitted, empty and subset selection; known excluded IDs retain safety reasons. | Truthiness defaults, unknown/foreign IDs, duplicates or ignored selection fail. |
| A8 | `InheritanceOracle.test_a08_every_receipt_must_match_not_only_the_first`<br>`InheritanceOracle.test_a08_fresh_receipts_are_rechecked_after_tamper_and_deletion` | Fresh hashes for every receipt after tamper or deletion. | Cached success or checking only the first receipt fails. |
| A9 | `InheritanceOracle.test_a09_authority_subtrees_never_supply_inheritable_evidence`<br>`InheritanceOracle.test_a09_evidence_file_directory_and_symlink_components`<br>`InheritanceOracle.test_a09_symlinked_parent_of_home_is_a_positive_control`<br>`InheritanceOracle.test_a09_traversal_is_never_followed` | Home-confined evidence, forbidden subtrees, symlinks and parent-symlink positive control. | Following outside files, directory evidence, ledger/family evidence or rejecting a symlink above home fails. |
| A10 | `CloneOracle.test_a10_adopted_ids_hashes_and_closed_memory_fields`<br>`InheritanceOracle.test_a10_complete_source_hash_is_before_provenance_or_supersession_edits` | Complete source hashes before edits and deterministic child/source/unit IDs. | Hashing modified units or retaining source IDs fails; forced unequal-source collision remains HOLD. |
| A11 | `CloneOracle.test_a11_child_supersession_links_are_reset_and_source_remains_unchanged`<br>`InheritanceOracle.test_a11_reinheritance_names_immediate_source_and_does_not_alias` | Immediate source provenance, source immutability, supersession reset and defensive returns. | Older ancestor as immediate source, dangling links, aliasing or private copying fails. |
| A12 | `CloneOracle.test_a12_clone_captures_parent_version_inputs_without_increment`<br>`CloneOracle.test_a12_own_brief_hash_is_identity_bearing_and_uses_real_builder` | Clone preserves captured constitution/configuration/version inputs while filtering memory. | Incremented counter, inherited excluded units, changed version or stale child own-brief hash fails. |
| A13 | `DistillOracle.test_a13_empty_selection_birth_is_valid_with_zero_counter`<br>`DistillOracle.test_a13_subset_counter_is_accepted_brief_affecting_count` | Distill counts accepted brief-affecting units and permits an empty birth. | Parent counter preservation, paraphrase or treating empty selection as omitted fails. |
| A14 | `DistillOracle.test_a14_absent_token_counter_does_not_block_within_byte_budget`<br>`DistillOracle.test_a14_inherited_arm_capacity_is_checked_before_commit`<br>`DistillOracle.test_a14_provenance_growth_over_unit_bytes_refuses_before_birth` | Byte-only admission, inherited-arm capacity and adopted-unit growth. | Missing tokenizer refusal, own-only capacity check or implicit cuts fail. |
| A15 | `CloneOracle.test_a15_birth_payload_and_event_match_bundled_schemas`<br>`TransactionOracle.test_a15_actual_prepare_receives_assigned_id_mapping`<br>`TransactionOracle.test_a15_altered_constitution_bare_event_is_refused`<br>`TransactionOracle.test_a15_extra_birth_key_bare_event_is_refused`<br>`TransactionOracle.test_a15_inherited_promoted_seat_bare_event_is_refused`<br>`TransactionOracle.test_a15_missing_founding_pin_bare_event_is_refused`<br>`TransactionOracle.test_a15_promoted_child_bare_event_is_refused`<br>`TransactionOracle.test_a15_wrong_version_bare_event_is_refused` | Closed birth records/events, assigned draft ID and immutable constitution/version facts. | Extra keys, absent reference, promoted child/seat, wrong version or constitution tamper refuse. |
| A16 | `TransactionOracle.test_a16_retirement_committed_before_waiting_child_breeds` | An already captured prefix cannot authorize birth after synchronized retirement. | Stale lifecycle or new child after retirement fails; live memory-supersession arm remains HOLD. |
| A17 | `TransactionOracle.test_a17_episode_bare_event_is_refused`<br>`TransactionOracle.test_a17_false_provenance_bare_event_is_refused`<br>`TransactionOracle.test_a17_false_source_hash_bare_event_is_refused`<br>`TransactionOracle.test_a17_level_three_bare_event_is_refused`<br>`TransactionOracle.test_a17_operator_actor_cannot_inject_rulings`<br>`TransactionOracle.test_a17_private_child_unit_bare_event_is_refused`<br>`TransactionOracle.test_a17_unrestricted_status_bare_event_is_refused` | Bare events use actual registry validators with the pre-birth prefix restored. | False source/provenance, private/level-three/episode/ruling units or arbitrary status cannot pass; fixture validators never prove this gate. |
| A18 | `CloneOracle.test_a18_birth_retry_uses_original_prefix_after_retirement`<br>`CloneOracle.test_a18_omitted_display_name_and_explicit_parent_name_are_distinct_requests`<br>`CloneOracle.test_a18_same_identity_changed_child_name_or_tool_is_bad_op`<br>`DistillOracle.test_a18_exact_empty_selection_replay_does_not_become_omitted`<br>`DistillOracle.test_a18_same_operation_changed_selection_is_bad_op`<br>`RetirementOracle.test_a18_changed_reason_same_identity_is_bad_op` | Original logical result/commit replays despite head or lifecycle advancement. | Changed tool/child/name/selection/reason is bad_op; expected_head cannot defeat exact replay. |
| A19 | `TransactionOracle.test_a19_real_held_ledger_lock_gives_busy`<br>`TransactionOracle.test_a19_short_and_punctuation_opids_are_not_silently_remapped`<br>`TransactionOracle.test_a19_stale_expected_head_on_new_request_appends_nothing` | Real ledger lock, new-operation expected_head and full external OpId alphabet. | Busy/stale append or silent OpId remapping fails; installed native gaps are HOLD. |
| A20 | `TransactionOracle.test_a20_distinct_operations_competing_for_child_commit_once`<br>`TransactionOracle.test_a20_identical_operation_racers_converge_on_original_prefix` | Independent owned processes synchronize distinct and identical child-creation requests. | Duplicate birth, wrong loser, divergent replay prefix or changed source fails. |
| A21 | `RetirementOracle.test_a21_retirement_is_one_exact_status_event`<br>`RetirementOracle.test_a21_retirement_preserves_memory_and_live_descendants`<br>`RetirementOracle.test_a21_retires_from_draft`<br>`RetirementOracle.test_a21_retires_from_promoted`<br>`RetirementOracle.test_a21_retires_from_shadow` | Single retirement event from every permitted state and retained memory/descendants. | Missing history, read-generated status or bench/seat attachment fails; default-list owner integration is HOLD. |
| A22 | `RetirementOracle.test_a22_distinct_retirement_is_conflict_and_original_replays`<br>`RetirementOracle.test_a22_invalid_reason_empty`<br>`RetirementOracle.test_a22_invalid_reason_null`<br>`RetirementOracle.test_a22_invalid_reason_oversize`<br>`RetirementOracle.test_a22_missing_target_is_no_agent` | Missing/repeated target, invalid reason and exact retirement replay. | Restoring/promoting through retire, changed content replay or appended refusal fails. |
| A23 | `ExtensionOracle.test_a23_retire_does_not_offer_arbitrary_status_or_gate_fields`<br>`RetirementOracle.test_a23_birth_first_survives_later_parent_retirement`<br>`RetirementOracle.test_a23_retirement_first_refuses_later_breeding` | Both retire/breed serial orders and closed retirement arguments. | Birth from an effectively retired parent, deleted descendants or arbitrary status setter fails; close race stays outside U17. |
| A24 | `TreeOracle.test_a24_complete_tree_all_operators_exact_nodes_and_consistent_head`<br>`TreeOracle.test_a24_independent_root_insertion_order_cannot_change_nodes` | Exact structured nodes, all birth-op labels, parent order, consistent head and deterministic sort. | SVG-only ancestry, invented fields, container-order output or renumbering fails. |
| A25 | `TreeOracle.test_a25_known_empty_journal_has_empty_nodes_and_zero_head`<br>`TreeOracle.test_a25_root_descendant_closure_preserves_an_outside_parent`<br>`TreeOracle.test_a25_unknown_root_is_no_agent` | Root plus descendant closure and preserved outside-parent links. | Extra ancestors/unrelated nodes, fabricated empty root or unknown-root success fails. |
| A26 | `TreeOracle.test_a26_retired_intermediates_are_traversed_before_filtering`<br>`TreeOracle.test_a26_retired_leaf_as_hidden_root_is_empty_success` | Traverse through retired ancestors before removing only retired nodes. | Pruning live descendants, reparenting, renumbering or no_agent for a hidden known leaf fails. |
| A27 | `TreeOracle.test_a27_boolean_generation_is_not_an_integer`<br>`TreeOracle.test_a27_cycle_is_internal_without_synthetic_root`<br>`TreeOracle.test_a27_duplicate_parents_are_internal`<br>`TreeOracle.test_a27_hash_corruption_preserves_shared_hash_mismatch`<br>`TreeOracle.test_a27_inconsistent_generation_is_internal`<br>`TreeOracle.test_a27_missing_parent_is_internal_without_graph_repair`<br>`TreeOracle.test_a27_self_parent_is_internal`<br>`TreeOracle.test_a27_unavailable_authority_is_not_empty_success` | Missing/cyclic/self/duplicate ancestry, generation and journal availability checks. | Repaired graph, Boolean generation, corrupt-chain success or unavailable-as-empty fails. |
| A28 | `TransactionOracle.test_a28_projection_tamper_delete_and_exact_retry_rebuild`<br>`TreeOracle.test_a28_materialized_tree_tamper_has_no_authority` | Authoritative reads ignore disposable projections; retry rebuilds original bytes. | Projection truth, missing restored files, changed parent bytes or altered replay fails; real owners required. |
| A29 | `TransactionOracle.test_a29_durable_birth_then_partial_projection_failure_retry_repairs` | Real materializer fault after durable birth leaves partial files, then exact retry repairs. | Rollback of durable birth, duplicate birth, fresh commit prefix or unrepaired partial files fails; real materializer required. |
| A30 | `CloneOracle.test_a30_birth_caps_are_refusals_without_silent_truncation`<br>`CloneOracle.test_a30_character_bounds_do_not_count_utf8_bytes`<br>`CloneOracle.test_a30_rejected_birth_cap_is_conflict_without_truncation`<br>`CloneOracle.test_a30_unicode_display_name_is_preserved_as_passive_text`<br>`InheritanceOracle.test_a30_audit_never_silently_truncates_examined_candidates`<br>`InheritanceOracle.test_a30_boolean_level_is_not_an_integer`<br>`InheritanceOracle.test_a30_schema_invalid_source_is_not_repaired`<br>`InheritanceOracle.test_a30_unicode_and_instruction_shaped_text_stay_passive` | Unicode and character bounds, passive text, complete audits and explicit birth overflow. | Instruction execution, truncation, Boolean level, schema repair or wrong overflow code fails. |
| A31 | `ExtensionOracle.test_a31_handler_failures_have_sanitized_domain_text`<br>`ExtensionOracle.test_a31_real_shared_dispatch_matches_inner_handler_and_replay`<br>`TransportOracle.test_a31_cli_domain_refusal_keeps_exit_three`<br>`TransportOracle.test_a31_cli_replay_uses_real_cli_and_original_commit`<br>`TransportOracle.test_a31_mcp_domain_refusal_is_rpc_result_with_iserror_true`<br>`TransportOracle.test_a31_mcp_replay_is_single_wrapped_data_with_iserror_false` | Real dispatch, in-process installed CLI/MCP success/replay/domain error parity. | Double wrappers, fresh replay commit, wrong CLI exit or wrong MCP isError fails; JSON/HTTP runtime parity remains HOLD. |
| A32 | `InheritanceOracle.test_a32_frozen_exclusion_assertion_kills_an_admit_all_substitute` | Existing private-unit exclusion assertion rejects an all-admitting selector substitute. | Green permissive substitute or import/setup-only failure is invalid; live central-predicate mutation remains HOLD. |
| A33 | `TransactionOracle.test_a33_public_surface_has_no_private_coordinates_or_new_dependencies` | Publishable assigned surface and stdlib-only imports; external immutable-tree seal checked by the runner. | Private coordinates, new dependency, source-project edits or frozen-oracle drift fail. Existing publication checker is AUSENTE. |
| A34 | `CloneOracle.test_a34_child_inherits_neither_promotion_seat_nor_measured_fitness`<br>`TreeOracle.test_a34_read_is_observational_and_return_values_do_not_alias` | Child draft state, no promotion seat/fitness/weights, immutable observational tree reads. | Inherited measurements or a read that changes history fails; automatic-retirement owner integration remains HOLD. |

## Source-of-truth and fixture boundaries

`helpers.py` uses the installed `lineage/core/journal.py` for authority reads and
ordinary fixture transactions. Its explicitly nominal fixture validator only
constructs pure histories. It is never used by bare-event, projection or competing
birth admission assertions. Large source matrices are assembled as canonical
hash-chained pure histories, then verified by the real journal snapshot before
the operation; this avoids quadratic setup. No invalid pure fixture is claimed
as a successfully admitted live event.

The source `Agent` records use synthetic reference pins and a fixture constitution.
They permit contract work while U10/U12 are absent. They cannot prove real pinned
artifact admission; host suites must use verified dependency-created agents and
reconcile nominal fixtures against those installed owners. U10/U12 source shape,
registry delegation, safe evidence-service binding, memory entry, brief, version
and projection services are integration preconditions, not facts inferred from
these fixtures. No test replaces the actual registry validators for an A17 attempt.
`forged_birth` restores the genuine pre-birth prefix so duplicate-child refusal
cannot hide a missing inheritance policy.

The test-side `check_schema` evaluates bundled record schemas independently. It
uses installed structural validation for supported leaves and handles the bundled
conditionals/references itself. This is an expected-result oracle, never a shared
production validator, and does not prove that the production boundary supports
all K0 assertions.

## A-K0-9 deviations measured in this copy

| Relevant source | Installed interface / gap | Oracle adaptation |
|---|---|---|
| `lineage/core/registry.py` | `ToolSpec(name, description, input_schema, handler, mutating)`; `load(*, package=...)`; callable `Validator(history,event)` and `Fold(state,event)`; no nominal `Command`, `Context`, `Snapshot`, `Committed`, `Services` or `FoldSpec`. | Actual ToolSpec and immutable Registry; keyword-only handlers; local `FixtureCommand` for nominal domain calls. No imports of absent core classes or duplicate validator registration. |
| `lineage/core/app.py` | `CallContext(home,validators,folds,actor,op_id)`; `dispatch(...,context=...,registry=...)` returns `DispatchResult.payload`; no shared default insertion/actor rebinding; schema-error detail can be an object. | Actual context and dispatch result; defaults/identity/error-text integration remains HOLD. |
| `lineage/core/journal.py` | `transact(home,agent=...,op_id=...,kind=...,payload=...,validators=...,prepare=...)` returns an Event; no expected_head/render parameter. | Real journal and original event-prefix checks; full K0 observable transaction semantics stay mandatory. |
| `lineage/core/journal.py` | `EventDraft` is a mapping; ID is assigned before prepare as `draft["id"]`, not an `event_id` attribute. | Direct deterministic preparation test proves the available binding. |
| `lineage/core/journal.py` | Native operation identity uses Id bounds/alphabet; native request digest binds journal request fields, unlike tool/effective-args K0 hashing. | Short, punctuation-bearing and maximum K0 OpIds plus changed-tool/content/replay tests; no remapping or schema narrowing. Native integration is HOLD. |
| `lineage/core/schema.py` | `strict_loads(raw)` and `validate(value,schema)`; no `SchemaStore`, decode/canonical/digest/load_record API, bundled refs/conditionals or full nominal assertion set. Decoder has a 65,536-byte limit [MEASURED: source constant]. | Actual structural API, independent expected canonical bytes and test-only bundled-record evaluator. Full K0 production schema/size integration is HOLD. |
| `lineage/core/cli.py`, `lineage/core/mcp.py` | Injectable streams, registry/context keyword arguments; CLI tools output has a `tools` wrapper. | Exercise installed CLI `main` and MCP `main` in process; no replacement transport and no assumed subprocess protocol. |
| `lineage/domain/agents.py`, `lineage/domain/brief.py`, `lineage/domain/version.py`, `lineage/domain/references.py`, `lineage/domain/memory/`, `lineage/ext/agents.py`, `lineage/ext/memory.py` | AUSENTE in this copy. | Nominal source fixtures only. Actual owner/delegation, safe evidence, real pin integrity, brief/version, entry, list, lifecycle and projection gates are HOLD. |
| `lineage/core/jsonlane.py` | AUSENTE; CLI names it as the JSON hook. | JSON parity is HOLD. HTTP/capsule runtime evidence is also AUSENTE; the oracle creates no network server. |

## Binding clarifications

- Amendment B1: `brief_head_sha256` uses `memory_arm="own"`; birth capacity
  includes inherited units via the inherited arm. Missing token counting never
  rejects within-byte-budget admission; the token ceiling is not measured.
- Amendment B2 is resolved against `schemas/mem_unit.schema.json`: this closed
  record has no top-level `agent_id`, `run_id`, `lamport` or `created_at`. Introduce
  none of them. Preserve existing provenance origin/actor/run_id and all other
  source fields, except the prescribed child ID, supersession reset and immediate
  `provenance.inherited_from`. No child identity is hidden in the selector context.
- Amendment B3: omitted `display_name` remains omitted for request hashing; static
  defaults alone normalize before request identity. Explicit parent-name text is
  a different request from omission. None versus an empty selected list remains
  distinct.
- Amendment B4: birth overflow is `memory_debt` beyond 256 inherited wrappers and
  `conflict` beyond 10,000 rejected records [CITED: Amendment B4]; never truncate.
  Caps are asserted at birth; pure select does not acquire an invented signature.
- Amendment B5: actual `agent.born`/`agent.status` ownership and runtime-home-aware
  receipt validation must be demonstrated on bare transactions. The installed
  two-argument validator provides no runtime home. That binding is HOLD, not a
  fabricated closure or another U17 registration.
- Amendment B6: the measured mapping key `draft["id"]` supplies birth event identity.
- Amendment B7: reserved child `operator`/`system` gives `bad_args`; an operator
  actor spelling grants no level-one memory authority through clone or retire.
- Amendment B8: symlink checks start beneath resolved home. A symlink above home
  is a positive control. Safe evidence fixtures are real bytes plus SHA-256; the
  valid relative paths in the fixture receipts begin with `receipts/`.
- A9's explicit unsafe-path classification is used for traversal:
  `invalid_receipt`, with no outside access. The general shape-first statement
  otherwise implies `bad_args` for a traversal string rejected by RelativePath.
  This is a residual specification conflict; host acceptance is HOLD until the
  orchestrator ratifies A9 precedence. Ordinary malformed unit bodies remain
  `bad_args`; empty receipt arrays retain the explicit `missing_receipt` exception.
- Amendment B9: foreign selected IDs, hidden retired leaves, self/duplicate parents
  and partial postcommit projection files have explicit assertions.

## Bounded processes and writes

Only A16/A20 create processes, through owned multiprocessing Process objects.
Event/Queue synchronization establishes ordering; there is no sleep-based oracle,
process-group operation, broad kill or signal to a non-owned process. Cleanup
checks the exact child's PID is greater than one before terminate and uses bounded
joins. Pure tree fixtures include unsupported-yet-valid future birth labels;
they do not implement U18.

## Deferred evidence, never a green surrogate

Host acceptance is HOLD until actual dependencies prove pin/evidence ownership,
locked validator delegation, full K0 operation identity and error shape, real
source-memory supersession races, default-list/effective automatic retirement,
projection rebuilding/fault repair, JSON/HTTP parity and forced unequal-source
ID collision. A29 specifies a real materializer seam; its eventual installed API
must be inspected before any host receipt is issued. No cross-family ADMIT,
capsule pass, memory-benefit claim or measured-fitness inheritance is asserted.

A32's admit-all substitute is a non-vacuity control of an existing negative
assertion. A live implementation/common-predicate mutant is AUSENTE because the
assigned implementation consists of stubs; removing a raise is not that mutant.
A green mutant or an import-only failure remains HOLD.

No existing publication checker was found in the supplied copy: AUSENTE. The
surface/stdlib/private-coordinate assertion and the runner's immutable-tree hash
comparison are local evidence only, not a replacement campaign checker receipt.
All requirements and conclusions are scoped to the supplied U17 corpus and this
assigned oracle surface.


## Amendments A-U17

- `helpers.py`: replace placeholder founding-reference hashes with the installed
  reference service's bundled pins. Seed memory counters and own-brief hashes
  through the installed memory/agent fold semantics, and supply missing historical
  supersession predecessors. Return the effective source record after fixture
  memory events. Fixtures remain explicitly nominal; no shared admission is
  replaced, mocked, skipped or treated as integrated proof.
- `test_clone.py`: pass the required explicit `rule_ids=[]` for the fixture
  constitution to `brief.build`; the expected digest assertion is unchanged.
- `test_extension.py`: assert the installed direct handler's `no_agent` exception
  before checking the shared dispatch error envelope. All diagnostic, no-append
  and transport assertions remain in force.
- `test_transactions.py`: construct the forbidden publication token from string
  fragments so scanning the test itself does not match its own fixture literal.
  The searched string, file set and negative assertion are unchanged.

The current U12 owner rejects non-genesis births and every status transition.
`lineage/domain/layout.py` and `agents.refresh_projections` are AUSENTE in this
integrated copy. Shared validator delegation and projection layout acceptance
remain HOLD; U17 neither replaces those owners nor fabricates successful events.

- `test_review_h1.py`: add pure admission regressions for captured clone inputs,
  distill selection, current evidence, reference/constitution/skill integrity,
  source-hash recomputation, unequal-source child-ID collisions and capacity
  refusal before the brief renderer ceiling. These pure probes do not claim
  shared U12 admission or postcommit projection proof.
- `test_review_h1.py`: compile a disposable copy of the current selector with its
  common rejection predicate removed. Run the existing frozen private-exclusion
  assertion against that predicate and require an assertion failure with no
  import/runtime errors. No frozen behavioral assertion is changed.


### h2: integrated owner context and projection refresh

- `lineage/domain/breeding/__init__.py`: bind the installed U12
  `agents._validate_born(history, event, ctx=None)` and
  `agents._validate_status(history, event, ctx=None)` through the production
  `_validators(ctx)` adapter. The registered owners remain unchanged and delegate
  to U17's pure admission helpers. Runtime home is supplied by the caller's
  trusted context, never by event fields. The extension still exports an empty
  `VALIDATORS` mapping; no registry is replaced or mutated.
- `helpers.py` and `test_transactions.py`: adapt direct journal argument plumbing
  to that same production binding. Bare events still pass through the genuine
  registered U12 owners, with every original refusal, error-code and no-append
  assertion preserved. No fixture validator replaces an admission owner.
- `lineage/domain/breeding/__init__.py`: use the integrated
  `agents.refresh_projections(agent_id, ctx=...)` service after durable commit
  and exact replay. The service chooses the current prefix and canonical layout.
- `test_review_h2.py`: add isolated projection/replay regressions for partial
  artifact repair, current memory projection with the original birth result,
  and publication failure followed by repair without another event. These use
  explicitly pure fixture prefixes; they do not substitute for live shared-owner
  birth/retirement acceptance or establish A17/A29 by themselves.

The earlier absence notes describe an older dependency snapshot. This workspace
now provides `lineage/domain/layout.py`, `agents.refresh_projections`, and U12's
context-aware inheritance/retirement delegation. The native journal continues
accepting two-argument callbacks, so direct callers bind the real registered U12
owners with `_validators(ctx)` before passing them to `journal.transact`.

- `test_clone.py`: keep the inherited-array overflow at its original exact
  cardinality and refusal assertion, but mark those pure fixture source units as
  already inherited. They remain active, public, receipt-backed level-two lessons.
  This keeps the installed parent own-brief renderer from failing during fixture
  setup before the independent breeding capacity assertion can execute.
- `test_review_h2.py`: use real context-bound U12 admission for child births and
  add a valid bare-birth positive control. The source setup remains nominal;
  neither its fixture validator nor a refusal-only callback proves admission.

- The production binding composes U17's pure birth/retirement admission with the
  genuine context-bound registered owner. It is a breeding capability, not an
  alternate general status setter: bare promoted/shadow transitions are refused
  by the retirement policy before any unrelated promotion service is consulted.
  Valid operations still require the U12 owner and its independent recomputation.


### h2 remaining integration gate

A28 remains HOLD. The integrated `lineage/domain/memory/store.py` service
`rebuild(agent_id, snapshot=..., ctx=...)` treats existing generation directories
as immutable: any missing or changed file causes refusal before reconstruction.
The frozen projection test deliberately damages and then deletes projection
files while leaving their directories. `agents.refresh_projections` reaches that
refusal on exact retry. U17 has no sanctioned repair argument on this service;
its adapter does not delete generation directories, rewrite their bytes, bypass
the owning service, or weaken the frozen A28 assertion. Dependency reconciliation
is required before host acceptance. Root agent/brief file repair and current
record publication are covered separately by `test_review_h2.py`.
