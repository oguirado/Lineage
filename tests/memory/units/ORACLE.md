# U10 fail-first oracle

All test bounds and acceptance assertions are [TARGET]. Source digests and discovered test counts are [MEASURED].

Run from the repository root:

    python3 -m unittest discover -s tests/memory/units -t .

## Scope and current evidence

The suite contains 110 discovered tests [MEASURED] and maps every acceptance case in the supplied SPEC_U10, including Amendment B. The source specification digest is `1446fab9473e46f85bb5d3874e8838093cc49b6f2a7a9b4455fc597ee57f8a7c` [MEASURED].

The initial valid level-three lesson in OracleCase.setUp is a required positive control. Against the supplied stubs it raises NotImplementedError("U10 stub") before integration setup. No test expects that exception as success. After implementation, every test must pass its actual positive and rejecting assertions; no required case is skipped.

Production U10 acceptance, bypass rejection after implementation, hereditary benefit and cross-family ADMIT receipts are AUSENTE. A red stub run is a construction receipt only.

## Prerequisite ledger

| Prerequisite | Observed availability | Oracle treatment |
|---|---|---|
| lineage/core/schema.py: SchemaStore, decode, canonical, validate | AUSENTE | Require the production bundled machinery; no alternate schema validator or decoder. |
| lineage/core/registry.py: Command, EventDraft, Snapshot, Committed, Services, Context, ToolSpec, FoldSpec, Registry | Frozen exports AUSENTE; seed registry is present | Attribute-only probe context for the initial pure positive control; integration requires the frozen exports. |
| lineage/core/errors.py: LineageError | AUSENTE; seed RoomError is present | An explicit prerequisite assertion after the initial positive control. |
| lineage/core/journal.py: snapshot, transact, append, fold, verify | Frozen API AUSENTE; seed room journal is present | Always require real U03 transactions; never synthesize an authoritative journal. |
| lineage/core/app.py: dispatch(name, args, *, ctx) | Frozen signature AUSENTE; seed dispatch is present | Always require U04; no transport policy emulation. |
| lineage/domain/memory/entry.py: build | AUSENTE | Test-only builder, injected at the documented seam, with exact UTF-8 byte checks and controlled token-counter results. No production rendering or U11 integration claim. |
| lineage/domain/agents.py and lineage/domain/runs.py | AUSENTE | Schema-conforming agent/run event fixtures and isolated folds only; no U12/U13 admission claim. |

Unavailable integration prerequisites cause explicit failed assertions once reached, never green fallbacks, skips, empty-journal defaults or imported fixture schema copies. Production lineage/core, schemas and docs remain untouched.

## Binding interpretations

| Issue | Resolution encoded by the oracle |
|---|---|
| Amendment B authority and supersession | Tool authority cannot replace or retire a ruling. New well-shaped superseded units fail conflict. Only active predecessors may be replaced. |
| Retired targets and repeated retirement | memory_put/operator_ruling on a retired agent fail conflict. Retirement of an already retired or superseded unit fails conflict. This amended refusal takes precedence over the base reciprocal-retirement positive example, whose target would already be superseded. No extra lifecycle is invented. |
| Brief membership | The exact active/nonprivate ruling, lesson, negative and workflow predicate applies. Workflow candidate, promoted and retired body states all participate while the root stays active. Root and body status are distinct. |
| Committed and dedicated quote identity | Domain mutations return the shared Committed dataclass; its value contains unit, memory_gen and commit. The dedicated path canonicalizes caller operation identity from target and quote, so varying caller op_id preserves exact replay. No encoding or artifact layout is prescribed by this oracle. |
| Quote errors | Empty and invalid UTF-8 quotes fail bad_args; oversized canonical units fail memory_debt. Failed evidence publication must refuse without append; hash_mismatch or internal is accepted because publication-failure code is unspecified. |
| Original source identity | inherited_from hashes the originally committed source bytes, including when later folding adds superseded_by. Current breeding selection remains U17-owned. The explicit Amendment B source-level/kind/privacy/lifecycle fences and specified missing-source/digest codes are tested. |
| Cursor precedence and absent targets | Validate cursor bounds; no_agent precedes after>head resync. A truly empty journal has no existing target and therefore no_agent, while an existing target with no memory has a verified empty matching history and the global head. |
| Token counting | Missing counting, counter exceptions and non-int/bool/negative returns fail memory_debt. The deterministic injected counters are test controls, never a production tokenization or U11 verification receipt. |
| Fold representation | Pure tests inspect public units_for results, namespace isolation and deterministic bytes; they do not impose a memory-namespace layout. Fixture agent/run namespaces contain schema-shaped records keyed by identifier solely for pending dependency substitutes. |

## Verification and isolation

Every journal rejection helper checks its fixed error code and identical authoritative ledger/main/events.jsonl bytes, global head and folded state. Direct-append controls retain the production memory validators. Positive controls accompany rejecting controls.

Only documented seams are instrumented. Evidence replacement uses events/barriers rather than timing. Competing replacements use forked processes, a bounded barrier/pipe/joins, and terminate only their own verified child PIDs if cleanup is needed. No process-group operation, sleep, model, network call, dependency installation or external source edit is used.

Runtime temporary directories are children of this test directory and are cleaned. The U11 substitute emits selected statements with LF and enforces independent byte and injected-token ceilings; it publishes no projection. Its content is a fixture format, never an asserted production rendering.

The A36 mutant check copies code, schemas, docs and oracle Python files into an isolated test-home project, then runs the authority, receipt and graph rejecting oracles under deliberate public-seam bypasses. It requires assertion failures for missing rejection, not import errors. Production sources are never mutated. These checks remain pending until the real prerequisites and implementation exist.

## Acceptance-to-test map

Names below are relative to the tests.memory.units package. All named methods are discovered by stdlib unittest. Related matrix assertions may substantiate more than their leading case identifier.

| Acceptance | Test names |
|---|---|
| A1 | `test_schema.SchemaTests.test_a01_collection_text_and_alias_bounds`<br>`test_schema.SchemaTests.test_a01_decision_level_2`<br>`test_schema.SchemaTests.test_a01_episode_level_2`<br>`test_schema.SchemaTests.test_a01_episode_level_3`<br>`test_schema.SchemaTests.test_a01_lesson_level_2`<br>`test_schema.SchemaTests.test_a01_lesson_level_3`<br>`test_schema.SchemaTests.test_a01_negative_level_2`<br>`test_schema.SchemaTests.test_a01_negative_level_3`<br>`test_schema.SchemaTests.test_a01_open_item_level_2`<br>`test_schema.SchemaTests.test_a01_open_item_level_3`<br>`test_schema.SchemaTests.test_a01_ruling_level_1`<br>`test_schema.SchemaTests.test_a01_workflow_level_2` |
| A2 | `test_admission.AdmissionTests.test_a02_direct_domain_closed_nested_objects`<br>`test_registry.RegistryTests.test_a02_cli_hostile_decoding_never_appends`<br>`test_schema.SchemaTests.test_a02_closed_body`<br>`test_schema.SchemaTests.test_a02_closed_body_cost`<br>`test_schema.SchemaTests.test_a02_closed_body_outcome`<br>`test_schema.SchemaTests.test_a02_closed_body_outcome_findings`<br>`test_schema.SchemaTests.test_a02_closed_body_seat`<br>`test_schema.SchemaTests.test_a02_closed_cost`<br>`test_schema.SchemaTests.test_a02_closed_findings`<br>`test_schema.SchemaTests.test_a02_closed_outcome`<br>`test_schema.SchemaTests.test_a02_closed_provenance`<br>`test_schema.SchemaTests.test_a02_closed_receipt`<br>`test_schema.SchemaTests.test_a02_closed_receipts_0`<br>`test_schema.SchemaTests.test_a02_closed_root`<br>`test_schema.SchemaTests.test_a02_closed_scope`<br>`test_schema.SchemaTests.test_a02_closed_seat`<br>`test_schema.SchemaTests.test_a02_closed_stats`<br>`test_schema.SchemaTests.test_a02_hostile_decode`<br>`test_schema.SchemaTests.test_a02_integer_findings`<br>`test_schema.SchemaTests.test_a02_integer_order`<br>`test_schema.SchemaTests.test_a02_integer_repair`<br>`test_schema.SchemaTests.test_a02_integer_runs`<br>`test_schema.SchemaTests.test_a02_integer_successes`<br>`test_schema.SchemaTests.test_a02_integer_tokens`<br>`test_schema.SchemaTests.test_a02_nonfinite_surrogate_and_closed_context_fields` |
| A3 | `test_schema.SchemaTests.test_a03_missing_body_members`<br>`test_schema.SchemaTests.test_a03_semantic_bounds` |
| A4 | `test_schema.SchemaTests.test_a04_exact_canonical_utf8_boundary` |
| A5 | `test_authority.AuthorityTests.test_a05_direct_validator_tool_ruling_fence`<br>`test_authority.AuthorityTests.test_a05_dispatch_drops_outer_operator_authority`<br>`test_authority.AuthorityTests.test_a05_tool_cannot_supersede_ruling`<br>`test_registry.RegistryTests.test_a05_cli_and_mcp_ruling_domain_errors` |
| A6 | `test_authority.AuthorityTests.test_a06_no_caller_authority_or_gate_fields`<br>`test_authority.AuthorityTests.test_a06_passive_claims_are_stored_literally` |
| A7 | `test_admission.AdmissionTests.test_a07_callbacks_use_snapshot_without_artifact_or_nested_actions`<br>`test_receipts.ReceiptTests.test_a07_level_two_receipt_and_level_three_observation`<br>`test_receipts.ReceiptTests.test_a07_wrong_missing_and_optional_receipts` |
| A8 | `test_receipts.ReceiptTests.test_a08_malformed_coordinates`<br>`test_receipts.ReceiptTests.test_a08_symlink_file_and_ancestor` |
| A9 | `test_receipts.ReceiptTests.test_a09_changed_after_inspection_before_lock`<br>`test_receipts.ReceiptTests.test_a09_unreadable_source_is_failure` |
| A10 | `test_admission.AdmissionTests.test_a10_owner_scope_and_target`<br>`test_admission.AdmissionTests.test_a10_retired_agent_cannot_receive_memory_or_ruling` |
| A11 | `test_runs.RunTests.test_a11_conflicting_ids_and_foreign_run`<br>`test_runs.RunTests.test_a11_explicit_and_implicit_episode_binding`<br>`test_runs.RunTests.test_a11_non_episode_binding_has_no_latest_run_inference` |
| A12 | `test_runs.RunTests.test_a12_all_frozen_episode_fields`<br>`test_runs.RunTests.test_a12_nonempty_parent_context_is_preserved` |
| A13 | `test_runs.RunTests.test_a13_closure_refuses_new_write_but_not_replay` |
| A14 | `test_admission.AdmissionTests.test_a14_real_append_cannot_bypass_validators` |
| A15 | `test_supersession.SupersessionTests.test_a15_process_barrier_competing_replacements` |
| A16 | `test_admission.AdmissionTests.test_a16_prepare_evidence_capacity_and_render_fail_atomically` |
| A17 | `test_replay.ReplayTests.test_a17_changed_content_tool_and_binding_are_bad_op`<br>`test_replay.ReplayTests.test_a17_original_result_after_later_write_and_stale_expected_head` |
| A18 | `test_replay.ReplayTests.test_a18_distinct_operation_cannot_overwrite_equal_or_changed_unit`<br>`test_replay.ReplayTests.test_a18_identity_is_scoped_to_owner` |
| A19 | `test_supersession.SupersessionTests.test_a19_atomic_multi_predecessor_graph_and_single_generation`<br>`test_supersession.SupersessionTests.test_a19_missing_self_cross_owner_and_competing_edges`<br>`test_supersession.SupersessionTests.test_a19_only_active_predecessors` |
| A20 | `test_schema.SchemaTests.test_a20_schema_backlink_iff`<br>`test_supersession.SupersessionTests.test_a20_shaped_incoming_backlink_is_conflict` |
| A21 | `test_supersession.SupersessionTests.test_a21_retirement_no_successor_and_repeat_refusal`<br>`test_supersession.SupersessionTests.test_a21_retirement_owner_and_level_authority` |
| A22 | `test_fold.FoldTests.test_a22_deterministic_prefix_and_reciprocal_fold`<br>`test_fold.FoldTests.test_a22_fresh_empty_and_namespace_ownership` |
| A23 | `test_fold.FoldTests.test_a23_inherited_birth_preserves_parent_and_source_provenance`<br>`test_fold.GenerationTests.test_a23_clone_captured_generation_is_not_inherited_count` |
| A24 | `test_fold.GenerationTests.test_a24_brief_membership_matrix`<br>`test_fold.GenerationTests.test_a24_nonbrief_and_inactive_changes_do_not_increment` |
| A25 | `test_fold.FoldTests.test_a25_private_inactive_flags_independent_order_and_copies` |
| A26 | `test_reads.ReadTests.test_a26_explicit_private_inactive_and_defensive_reads` |
| A27 | `test_reads.ReadTests.test_a27_original_events_filter_owner_and_supersession` |
| A28 | `test_reads.ReadTests.test_a28_boundaries_defaults_precedence_and_empty_prefix`<br>`test_reads.ReadTests.test_a28_page_matches_and_nonmatches_without_loss` |
| A29 | `test_runs.RunTests.test_a29_null_costs_in_get_history_fold_and_replay`<br>`test_schema.SchemaTests.test_a29_null_and_zero_are_distinct` |
| A30 | `test_admission.AdmissionTests.test_a30_candidate_selection_excludes_private_units`<br>`test_admission.AdmissionTests.test_a30_entry_byte_ceiling_is_independent`<br>`test_admission.AdmissionTests.test_a30_missing_entry_and_unexpected_dependency_failure`<br>`test_admission.AdmissionTests.test_a30_token_gate_and_invalid_counters` |
| A31 | `test_authority.AuthorityTests.test_a31_changed_artifact_is_not_repaired_into_success`<br>`test_authority.AuthorityTests.test_a31_changed_preserved_quote_refuses_retry`<br>`test_authority.AuthorityTests.test_a31_invalid_utf8_empty_and_oversize_quote`<br>`test_authority.AuthorityTests.test_a31_missing_operator_authority_or_actor`<br>`test_authority.AuthorityTests.test_a31_quote_bytes_scope_identity_and_replay` |
| A32 | `test_registry.RegistryTests.test_a32_exact_registry_discovery_and_callback_signatures`<br>`test_registry.RegistryTests.test_a32_library_dispatch_cli_mcp_read_parity`<br>`test_registry.RegistryTests.test_a32_put_exact_replay_across_all_available_surfaces`<br>`test_registry.RegistryTests.test_a32_registry_load_is_atomic_on_duplicate_ownership` |
| A33 | `test_reads.ReadTests.test_a33_projection_tamper_delete_does_not_change_reads` |
| A34 | `test_admission.AdmissionTests.test_a34_original_source_hash_survives_supersession`<br>`test_admission.AdmissionTests.test_a34_source_eligibility_fences`<br>`test_admission.AdmissionTests.test_a34_source_existence_and_digest_codes`<br>`test_admission.AdmissionTests.test_a34_source_receipts_are_reverified` |
| A35 | `test_admission.AdmissionTests.test_a35_missing_committed_state_never_uses_projection`<br>`test_reads.ReadTests.test_a35_unreadable_journal_is_internal_not_empty` |
| A36 | `test_registry.RegistryTests.test_a36_frozen_inputs_and_oracle_bytes`<br>`test_registry.RegistryTests.test_a36_rejecting_oracles_fail_in_isolated_mutant_copy` |

Additional cross-case coverage: A4 uses test_admission.AdmissionTests.test_a30_entry_byte_ceiling_is_independent; A14 uses test_admission.AdmissionTests.test_a07_callbacks_use_snapshot_without_artifact_or_nested_actions; A24 replay uses the A17 tests; A29 history/replay is exercised by the A29 run test; A35 also uses A7, A9 and A30 rejection controls.

## Frozen inputs and oracle sources

These hashes seal the read-only contract/schemas, prior tests/fixtures and new oracle Python files. Stub production files are intentionally excluded because they will be implemented. ORACLE.md is excluded from its own recursive hash; the orchestrator must seal this report externally. No successful post-implementation or mutant receipt is asserted here.

| Repository-relative file | SHA-256 [MEASURED] |
|---|---|
| `docs/CONTRACT.md` | `bb644019ed08073ef0f465eab5a4a094d108fdc655eda1d44c7388095b6de81e` |
| `docs/INTERFACES.md` | `6b7d4ce6d5a982a151fa14818f49757da9b1e686097cb1645d02e57f8f7bd694` |
| `docs/OPERABILITY.md` | `a29275a7711b23b2b104fe42fb8ac5e1225b5dc17b8ee87c1903b8fac8d78f60` |
| `schemas/agent.schema.json` | `5f6042b7367a4e7d3f8107c8ad4702fd809af54b23a52ff16bd4dfbea6fb3405` |
| `schemas/bench_declared.schema.json` | `34d88549e262cd34158366cd089b32b6dec8d2883939f5f7dc0fe0af041341fd` |
| `schemas/event.schema.json` | `20091b0905c1307ddf79e7c8918e8c0a2468bbedc6cfa2fa5be42407298c41af` |
| `schemas/family_envelope.schema.json` | `32ae99afcc151c5c5b60f7484a4b36e1adde027274cd680c1f0dcf21c10f4cd2` |
| `schemas/family_receipt.schema.json` | `7b928e608e3e1b3fcd316daabc4483e503df3b799360e0e012cfc5547f3f851c` |
| `schemas/mem_unit.schema.json` | `3ed62dbb08d75af0bacce44fe7dfb4dddbab93c4a99aa8d6dcde2d4ac7079d15` |
| `schemas/run.schema.json` | `47102a9b2c06ed9bd06f26241878d8b52b02817b090b7eca1bb45fe0c1b2e588` |
| `schemas/tool_error.schema.json` | `11f47c9c3c935a74ee843088b58ba114fbe37c2eb44c75b676d4c0e0fc343125` |
| `tests/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/agents/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/arena/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/arena_stats/__init__.py` | `35cab74e41c9d9ede8db5c2d5f9547130f3c00fc89fed51aa210fdfea2125388` |
| `tests/breeding/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/bridge/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/constitution/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/core/DROPPED.md` | `3eac5bcd5954bb7eeed04ac6d8861ba508090297305c50306994d8f063ab8339` |
| `tests/core/REGRESSION_FROZEN.sha256` | `84bdd69c7788578e3a88787f79c530e68dcf703e98f6db715709a97b3ce9a7c7` |
| `tests/core/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/core/regression/__init__.py` | `fe069e1cb18ca51073cc109b2f29d3044fde6f79f9e25f8525f2823b7593a0b9` |
| `tests/core/regression/family/__init__.py` | `4016261e73796d355e3a516a0f04fe3a814a7e21a6c745454b9465ad9b739944` |
| `tests/core/regression/family/support.py` | `1d48bb4cfcb1d8322dc28c59120d7758319fa41f3034ec408896edf2d2423fe9` |
| `tests/core/regression/family/test_cursors.py` | `a169409d2e93a764a0bc3ee02a96a61ed8b786edabead3bddaf51f85aaa945b6` |
| `tests/core/regression/family/test_envelope.py` | `17c7a29ed868deab52a2f32f112e793c75461d92b1dc3fa1ccfe6c252c217dd6` |
| `tests/core/regression/family/test_hardening.py` | `8b53e348ae69dc951a3b85f4e9113e7044874259b1c0c27d113343dce78bd2ae` |
| `tests/core/regression/family/test_mailbox.py` | `4b8106a5ba45c6f5b302a23b3ab6add1436416ccd4b584469048821ed03de249` |
| `tests/core/regression/family/test_recovery.py` | `9d90bcd56d95c6fdf119df1156b8e6858615753d135c6616a76bc22cb1a37ad1` |
| `tests/core/regression/family/test_routing.py` | `4f315b13b80f2ac9c93aa3560680cf1f97eb757ad632e9e571b934cf5aa52f20` |
| `tests/core/regression/fixtures/extraction_evidence.json` | `5216eac21d06e7da1a111443afd44dd5c4d46e5d7a8485530fdfe42215a6d56a` |
| `tests/core/regression/fixtures/measure.py` | `fec4aad0a4634217f0cfaf78b7144b1e86ac214e3edeb12e9462a1b1793279a7` |
| `tests/core/regression/fixtures/plan/bad-input.json` | `a6fb08fda1acb957b6116bd37811a1fe41a01611c0631edbf786d6889a27a55c` |
| `tests/core/regression/fixtures/plan/capsule_c2b.events.jsonl` | `03c851760136b0fd0c7942976eb5e6e8b64f1b5cfdd3c18c9c3af07c1cb2615d` |
| `tests/core/regression/fixtures/plan/load-input.json` | `851fe032bb4b5ec292ccff8217282034d392ce44cda7f8a37b53459b0135b6f2` |
| `tests/core/regression/fixtures/plan/persona_junior.events.jsonl` | `67da661581e3bf04297be6fe94840e0a4edaa92d752977a395ba13ebe88e13c2` |
| `tests/core/regression/fixtures/plan/templates.v1.json` | `75949c0535b2f0f854c1d6cdd4cd4fc7f2014e079bba64d4b8890016c17d8cde` |
| `tests/core/regression/fixtures/plan/vectors.v1.json` | `9386b2c4d7a19b9b96951dfe597e0bfaac511d6dd6be8df0f9eb90165bf3baff` |
| `tests/core/regression/fixtures/renamed_results.json` | `eb7c2ec4884d4d55469020f98d91b34b61d4edbf418cb1ebe2b7b8c32a484524` |
| `tests/core/regression/fixtures/room/u87/expected.json` | `3d06c6de278d6a27f406fe2b5ca88920bd0a91bd0444344b25d5474a5e1a5227` |
| `tests/core/regression/fixtures/room/u94/legacy_tools.json` | `e5d9707e533cf4697ee6d584fba2befb3eb89bd754f29f3adf9aa744e2cc3691` |
| `tests/core/regression/fixtures/seed_results.json` | `6a592c509075603f8b7f35f2778bb7799d174edf55df3123017e6e87824f8e3e` |
| `tests/core/regression/fixtures/selection.json` | `c7d244d189d571ebb6d72585bebb609934ac67a847af8f568b96a0cda1345659` |
| `tests/core/regression/plan/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/core/regression/plan/support.py` | `50a87b2f7d2c72cb111db056b9fd994454d09594ef6baf06506c60b0221d5bf6` |
| `tests/core/regression/plan/test_u55_conformance_md.py` | `44b9f763c755a2d0a5d2cafc4ec8f5556206f55f9f14baf6d409afdca17113ad` |
| `tests/core/regression/plan/test_u55_ops_fold.py` | `b98b261b6e3adb71f0a3e82f928316317f7f7894838fce33cc07b07dbfe6412c` |
| `tests/core/regression/plan/test_u55_repair1.py` | `3e41dd2b76f269f981865b86f7e7edff17091294a56ff1bdd88422a49e74dcfb` |
| `tests/core/regression/plan/test_u55_repair2.py` | `8a6bedb7f1631b575ba48750bf18e75c9becb2ce494da8cc064436d787d76daa` |
| `tests/core/regression/plan/test_u55_template.py` | `a18cb45cbe815270360d8048397d662e4be936ab9c9ca6776909b0463baf736b` |
| `tests/core/regression/plan/test_u55_vectors.py` | `5c77ec3a5803dc64f81bf781a109f06e540a92b769c6be99a24f10c37d514ebf` |
| `tests/core/regression/room/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/core/regression/room/s0/__init__.py` | `8c1969bf6f6a87603f3a2696749765e405c4f70cadf9272e727a56c670ec0f5f` |
| `tests/core/regression/room/s0/test_seam.py` | `8c93ea74485db0bacf7696f1fb6722a7000a88438188478a29b78988141b6ed8` |
| `tests/core/regression/room/support.py` | `8e7bcc9cee46da7927ab003b99f7260c262c5a96e2a2d619f40aa5c96d97a83d` |
| `tests/core/regression/room/test_cli.py` | `39addfef04e3ff622c2127bd1fc1301ccb2a6186d3368d3d1f9e29d7fd39ba77` |
| `tests/core/regression/room/test_mcp.py` | `23826227446b97c997d6c2c5e064a914cc6ff474c2a8c268a724bdb58756cfb6` |
| `tests/core/regression/room/test_post.py` | `92a6a81c68cf071bcd7e7ed084c1881b152b773581c35938cbe21504c3343bbe` |
| `tests/core/regression/room/test_read.py` | `4b3456496fee330eec42f7356fe48cb3beae88b02dfb8a5b4f55019fdd61577c` |
| `tests/core/regression/room/test_review1.py` | `5d14c6aef3011a9ae9e3c0da68803dd1c666e23bb1a31dff36b74a97ed6e42b4` |
| `tests/core/regression/room/test_review2.py` | `9914cb498bbb6681086e04e07c6ac18d09430ed748b6bb6cae83cc612bf5563c` |
| `tests/core/regression/room/u109/__init__.py` | `877b3b9e47f6a9a9bb4cb12014fb320d746e0d420d8cd77eb3e5c0a4f6624478` |
| `tests/core/regression/room/u109/cli_probe.py` | `2abf60b4505073bda1ab8a2668f645b935014d668d5bf2cbacc7820c6ae7d04b` |
| `tests/core/regression/room/u109/fold_probe.py` | `57f8da911584f346a90d3b8c30980e5750ca513b28782673bd5f128f2783c6ce` |
| `tests/core/regression/room/u109/protocol_support.py` | `90a52401a2f13e4362260a6d46ea73534423746888fc0916f2213b361e5d7e72` |
| `tests/core/regression/room/u109/test_protocol.py` | `330d8174278072fb4c52be346f72b85c8c842fb870a80c92cef6f17cdbb144ab` |
| `tests/core/regression/room/u110/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/core/regression/room/u110/support.py` | `b31d4a675b7a2591258f3a967b8461b1f980927b2b57882b5c5745d277231c3e` |
| `tests/core/regression/room/u110/test_durability.py` | `9ae36f53798dc06c6907fe6e13d97860b7464512c47d042adc489c8befe67008` |
| `tests/core/regression/room/u110/test_protocol.py` | `bef2275fb33928abe845b6d7300189a66bbc61d8c97ded1328070666c0680092` |
| `tests/core/regression/room/u110/test_references.py` | `c3c16fc2adff3996c4f45eac8c6207280f305759b61f1266971bbc927335aebc` |
| `tests/core/regression/room/u110/test_validation.py` | `10924e81514f89aa37d3246d253a2d1985127674c4a60c7b58b3b5af4f49825f` |
| `tests/core/regression/room/u119/__init__.py` | `9ebd5499707def3838360b8053b2358fbb0131821d97fc79e29f272bf6769448` |
| `tests/core/regression/room/u119/restart_probe.py` | `4bf3b2db8072453f6540cb2c21346c72fadd70dddb60ceec17f13a6cf3292c3f` |
| `tests/core/regression/room/u119/support.py` | `9c007d77392b807b45230f39f60bd85de03208e1ec1a37bd596b94063de9b48e` |
| `tests/core/regression/room/u119/test_acquire.py` | `552f9b24199fa669ca14ce2bfdc4f2be84fa0665047f669497aca6e54d5c0c4b` |
| `tests/core/regression/room/u119/test_atomicity.py` | `16fa15bfdb1375f8e9418c98623ca3f9410681ea7b71431db506d66f099576a4` |
| `tests/core/regression/room/u119/test_replay_protocol.py` | `965c3f026711ab0c95ec91ca982ef9a62dbfe61cd38a7ae083aef1719cf22fe8` |
| `tests/core/regression/room/u119/test_report.py` | `3fc531ff10450bbf2cb285d669d7ba9911f87a7a988d94ca4fe26e1d6d9ccaac` |
| `tests/core/regression/room/u119/test_validation.py` | `96e0d93a33c7e0746213736a7724f75bf0d65e1121e3dd3b21e2977f5a29a593` |
| `tests/core/regression/room/u121/__init__.py` | `1310e4d9911f43b025d98d7d036d5e2e19774b7dc59b000e845c7235bc3acf45` |
| `tests/core/regression/room/u121/support.py` | `f47e3ad9fab19a468146ee597faef05b55614e2e6c5914b926960c1392896b23` |
| `tests/core/regression/room/u121/test_batch.py` | `884c3236909702ccb716143768c4ae3ad55b3a307b070e65bbe70e69947d51d8` |
| `tests/core/regression/room/u121/test_controls.py` | `492134550b07c03c36c675e0717f4f40e27cfef4c2fc7ae7fcfac5ef7a5de808` |
| `tests/core/regression/room/u121/test_durability.py` | `6317d3601a227b9f40c9bd2e057521ba7656e487deb06b9857d4a5ce282f1f05` |
| `tests/core/regression/room/u121/test_lock.py` | `75e5eba601164f55dcac3483b04b400074cc9883299780255dfbccf306da8a8b` |
| `tests/core/regression/room/u121/test_replay.py` | `5ac47d8dc5888b5aadce64119fd3d8203367ffab4536b214364e57c6204be2a2` |
| `tests/core/regression/room/u121/test_reserve.py` | `ee2c7a3bf08c3a0a04b74ca69266b6769202fddd52b7f395127829afe1e8a24c` |
| `tests/core/regression/room/u69/__init__.py` | `222a64d00681531b9cb9c206a30683f92fedcdc13c0cdd36d8314b49dfa0683b` |
| `tests/core/regression/room/u69/test_contract.py` | `019cff417ab761c67bb1aa4dffee5fec2c4e97cfd41b75562074566269049579` |
| `tests/core/regression/room/u69/test_repair1.py` | `ff296fe1460a481aeee5cc818f49636ffcddec271132eb7a261aa94829cd77a6` |
| `tests/core/regression/room/u71/__init__.py` | `db39b03985358e5a883058661e07512de93c6d94c1d78148d26c29e0ffa55b34` |
| `tests/core/regression/room/u71/test_lock.py` | `27ead36df68ca8564438143446cb399e335bde5c50c5bc281dbc62725775eb2c` |
| `tests/core/regression/room/u76/__init__.py` | `c545722298cc16ba4119c838884d744db0a522f9ef0b3b39e6fe962c6933437b` |
| `tests/core/regression/room/u76/test_repair1.py` | `3c0bc6bd3168c15f0d008aaeec4017560e4bf95d65a04656389512d358ce30f5` |
| `tests/core/regression/room/u87/__init__.py` | `eb825b4eaa39c80837bce528cbfb5c6de39993ae1aba6fc335a2925b9e78c693` |
| `tests/core/regression/room/u87/probe.py` | `7430699b0e48349ace2dfd1bda32afe85600053f7f836e409a04f9b22197d1f7` |
| `tests/core/regression/room/u87/support.py` | `48055127761a33c9c5af0025e806733c0a27955606b459953e5e2a9b41e4a034` |
| `tests/core/regression/room/u87/test_contract.py` | `d54df939d92c58c1c07da67504f6425f4787410a42e2b5a70a06b4b893a57f6a` |
| `tests/core/regression/room/u87/test_repair1.py` | `5301b867dbde3765e3c4ff25e2c30a18e5765c13a2aa65ed0382622448b1e595` |
| `tests/core/regression/room/u89/__init__.py` | `0077d6d560cc8952fcfd3e5675497a896d6251defddc24072b59b24ad3dcde98` |
| `tests/core/regression/room/u89/support.py` | `3842369b1aa8a30a793500bb9bc4028cfbcb1112f5c6cbed0ec8363026cda6c1` |
| `tests/core/regression/room/u89/test_events.py` | `be3074c6f351bdbad22863970fa5d8baff93caa970d8f4518b24e296df9f0f93` |
| `tests/core/regression/room/u89/test_repair1.py` | `337f820e8e3b50a21f32c47dd2628436d3ce0cb954fd2bf221a170d2acadb374` |
| `tests/core/regression/room/u94/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/core/regression/room/u94/support.py` | `2f3c50e8af9c6bee37d7e42afb21c5b936abbc0512b6f6b20dc4aa5435d7d0d5` |
| `tests/core/regression/room/u94/test_contract.py` | `24f0243e08fa8368a24493342d5db5caa427a6e17b3a4f8cae2954e0d61a7567` |
| `tests/core/regression/room/u94/test_files.py` | `c051afcaa61f30cd37c900738744b5f962c0341b7f3ff677b46e99999e1560bc` |
| `tests/core/regression/room/u94/test_repair1.py` | `a64f9c75a3a07704e9c3994f156c1ffc9a361a10ea06cddfa16d7786c1248762` |
| `tests/core/regression/room/u94c/__init__.py` | `3d06f7d5ccd296d6f59ac1f53893fccce8a3b81c464e60f134c769eb14ac7dde` |
| `tests/core/regression/room/u94c/test_cli_export.py` | `fe778c2f2dac8a2eb15ef4b39f09d6c6d871251aee14b160c9db7038981346c7` |
| `tests/core/regression/room/u95/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/core/regression/room/u95/test_headless_resource.py` | `bb677f866701b182e1c09fe673494508aea8c2399426ccf1c2ae556f833f8c15` |
| `tests/docs/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/e2e/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/importers/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/ledger/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/memory/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/memory/units/__init__.py` | `7c6121f7502cf234703eb520d2a9f03f1b29188ab2fa0a3d95def79b34349275` |
| `tests/memory/units/_support.py` | `39456ae90f8211bb4b8b070dc95d85c23238df7b52761ce2cadf63e927f374a5` |
| `tests/memory/units/test_admission.py` | `7d179f2af3d0aa2df5b0b6cd190c7f877cc1d06bc4135c520aeee7828a7405b9` |
| `tests/memory/units/test_authority.py` | `30fee66fe440902c16485a1d3ba1e159f9669d4455d0003542d81fc5e0129c1e` |
| `tests/memory/units/test_fold.py` | `296a45ab69e1889d64511b0729e9fdd36d0ce9198a0d0ea37a62afad3242196e` |
| `tests/memory/units/test_reads.py` | `7e06d6575348c105402558bb0f85330c3b19cc194d0d17ee1e5772ca4d00522d` |
| `tests/memory/units/test_receipts.py` | `2f31c4c80dc44b5d2b34e333d8a6df5094ab5cb615019b7bb976309f233f865f` |
| `tests/memory/units/test_registry.py` | `d3d21d0fd03ff7024e98894d4eb4a5f80acd1cbd0a7d17e6aa8e0c4f9bc2f00e` |
| `tests/memory/units/test_replay.py` | `d194283e1db40c838a7df5860f963d6ef103ff1f97f5a4c548178dbfcf3f3a50` |
| `tests/memory/units/test_runs.py` | `7900268ff414a3ab0aae203a7c350eac9f80fc18af5e9ac9223d354543a6c8db` |
| `tests/memory/units/test_schema.py` | `d2829ff2218d5b0851e33de7922d2acd18e2efed78e477440282b1197ce1599d` |
| `tests/memory/units/test_supersession.py` | `677d5fbc4d9c9080c2e33840da8c6abe9bd53e1ccfefab2b813a5972ded290c5` |
| `tests/operability/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/promotion/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/references/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/runs/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/serve/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/skills/__init__.py` | `17f68f141978e5ef422192ad60a5406aee0b6f331f79696b8d39e058deb9af29` |


## Amendments A-U10 (orchestrator)
- Frozen input hashes of docs/CONTRACT.md, docs/INTERFACES.md, schemas/agent.schema.json and tests/arena_stats/__init__.py updated: those inputs changed after the oracle froze (K0 amendments A-K0 1-9 and the U15 integration). No test or assertion changed.


## Amendment A-INT1 (orchestrator integration repair)

The existing seal was stale for `docs/CONTRACT.md`, `docs/OPERABILITY.md` and
`tests/skills/__init__.py` after integrated K0 and U09 amendments. Those inputs
were read-only during INT1; their current authoritative bytes are repinned above.
No frozen oracle Python file or assertion was changed.

A-U10-2 preserved native journal introspection, and A-U03-2 supplied the public
`error_payload` helper. Those implementation files had no rows in the original
stub-era manifest. The following pins now seal those integrated inputs, including
A-INT1's non-destructive dual-call facade repair.

| Repository-relative file | SHA-256 [MEASURED] |
|---|---|
| `lineage/domain/memory/__init__.py` | `6a9a41c1cedc8c3d112085649eaa57d6e751908239cd5973eca334d31be571fc` |
| `lineage/core/errors.py` | `3506b2fd2b1e9e2631763bc076a182403ec8cc3f49aa97b7d8670252d86254d1` |
