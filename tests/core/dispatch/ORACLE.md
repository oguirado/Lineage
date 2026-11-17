# U04 fail-first oracle

Source: `.unit/SPEC.md`, including Amendment B. This oracle writes only test
sources under `tests/core/dispatch`. Runtime fixtures use disposable directories
outside the source tree. It uses standard-library `unittest` only.

## Status and gates

**BLOCKED / AUSENTE:** U01/U02 package scaffolding and the schema implementation
are missing in the supplied copy: `lineage/__init__.py`,
`lineage/core/__init__.py`, and `lineage/core/schema.py`. The prerequisite
assertion fails explicitly. Dependent tests skip with a `BLOCKED` reason before
attempting production imports. This is a failed setup gate, **not** behavioral
fail-first evidence and **not** U04 acceptance. No production placeholder is
created, and an import failure is never relabeled as a behavioral red receipt.

The production boundary is also absent: `lineage/core/registry.py`,
`lineage/core/app.py`, `lineage/core/mcp.py`, `lineage/core/cli.py`,
`lineage/__main__.py`, `lineage/ext/__init__.py`, and `bin/lineage`. Once U01/U02
land, missing U04 surface produces assertions before imports. Existing modules
that fail to import fail a separate explicit import assertion.

| Step | Verification gate | Rejecting contrast |
|---|---|---|
| Prerequisites | Required package/schema files exist | Missing dependency blocks behavioral evidence |
| Registry | Sorted, complete, immutable registrations | Duplicate, malformed schema, failed dependency import |
| Dispatch | One validated invocation, detached passive result | Non-JSON args never invoke a handler; forged errors are internal |
| Adapters | Canonical payload parity and exact error provenance | Missing descriptor, bypassed validation, false isError |
| Processes | Real entrypoints and responses before deadlines | Unflushed response, corrupted frame, broken output stream |
| Integration | Real owning-unit registrations and witnesses | Test-only registrations do not prove product completion |

A11 replay, A24 canonical domain calls, JSON/HTTP parity and journal witnesses
remain **PENDING / AUSENTE**. Their dedicated skip cases do not claim success.
The installed inventory check runs only when actual domain registrations match
the spec inventory. It proves discovery parity only, never domain correctness.

## Acceptance mapping

Every numbered Acceptance case A1–A24 [CITED: `.unit/SPEC.md`] is mapped below.
Names are relative to the `tests.core.dispatch` package. Generated registry and
error-code cases are individually discoverable unittest methods.

| Acceptance | Test names |
|---|---|
| A1 | `test_registry.PrerequisiteGate.test_a1_required_u01_u02_scaffolding`<br>`test_registry.RegistryTests.test_a1_imports_are_inert_without_domain_or_u03` |
| A2 | `test_registry.RegistryTests.test_a2_sorted_discovery_including_underscore_and_new_module` |
| A3 | `test_registry.RegistryTests.test_a3_absent_and_nonpackage_configuration_is_sanitized`<br>`test_registry.RegistryTests.test_a3_reject_bad_name`<br>`test_registry.RegistryTests.test_a3_reject_cross_module_duplicate_tool`<br>`test_registry.RegistryTests.test_a3_reject_dependency_import_failure`<br>`test_registry.RegistryTests.test_a3_reject_duplicate_fold`<br>`test_registry.RegistryTests.test_a3_reject_duplicate_validator`<br>`test_registry.RegistryTests.test_a3_reject_empty_description`<br>`test_registry.RegistryTests.test_a3_reject_empty_event_key`<br>`test_registry.RegistryTests.test_a3_reject_equal_duplicate_tool`<br>`test_registry.RegistryTests.test_a3_reject_malformed_schema`<br>`test_registry.RegistryTests.test_a3_reject_missing_export`<br>`test_registry.RegistryTests.test_a3_reject_nested_package`<br>`test_registry.RegistryTests.test_a3_reject_nonboolean_metadata`<br>`test_registry.RegistryTests.test_a3_reject_nonobject_root`<br>`test_registry.RegistryTests.test_a3_reject_nonstring_event_key`<br>`test_registry.RegistryTests.test_a3_reject_not_toolspec`<br>`test_registry.RegistryTests.test_a3_reject_uncallable_fold`<br>`test_registry.RegistryTests.test_a3_reject_uncallable_handler`<br>`test_registry.RegistryTests.test_a3_reject_uncallable_validator`<br>`test_registry.RegistryTests.test_a3_reject_unsupported_optional_assertion`<br>`test_registry.RegistryTests.test_a3_reject_wrong_mapping`<br>`test_registry.RegistryTests.test_a3_reject_wrong_tools_container`<br>`test_registry.RegistryTests.test_a3_validator_and_fold_can_share_kind` |
| A4 | `test_registry.RegistryTests.test_a4_descriptors_detached_sorted_and_read_only_snapshot`<br>`test_registry.RegistryTests.test_a4_empty_and_populated_transport_parity` |
| A5 | `test_app.AppTests.test_a5_explicit_and_environment_empty_are_configuration_errors`<br>`test_app.AppTests.test_a5_home_precedence_and_carrier_metadata`<br>`test_app.AppTests.test_a5_separate_homes_do_not_leak_context`<br>`test_cli.CliTests.test_a5_empty_home_configuration_is_structured` |
| A6 | `test_app.AppTests.test_a6_direct_and_adapters_share_one_dispatch`<br>`test_app.AppTests.test_a6_handler_receives_detached_arguments_and_result_is_detached`<br>`test_entrypoints.EntrypointTests.test_a6_real_cli_and_mcp_success_have_identical_payloads` |
| A7 | `test_app.AppTests.test_a7_arguments_reject_before_handler_and_keep_diagnostics`<br>`test_app.AppTests.test_a7_non_json_direct_arguments`<br>`test_cli.CliTests.test_a7_strict_json_rejections_before_handler` |
| A8 | `test_app.AppTests.test_a8_concrete_u03_error_when_installed`<br>`test_app.AppTests.test_a8_forged_error_attributes_are_untrusted`<br>`test_app.AppTests.test_a8_request_and_handler_bad_args_are_different_failures` |
| A9 | `test_app.AppTests.test_a9_domain_bad_args`<br>`test_app.AppTests.test_a9_domain_bad_op`<br>`test_app.AppTests.test_a9_domain_busy`<br>`test_app.AppTests.test_a9_domain_conflict`<br>`test_app.AppTests.test_a9_domain_fixture_readonly`<br>`test_app.AppTests.test_a9_domain_forbidden_level`<br>`test_app.AppTests.test_a9_domain_hash_mismatch`<br>`test_app.AppTests.test_a9_domain_heldout_forbidden`<br>`test_app.AppTests.test_a9_domain_internal`<br>`test_app.AppTests.test_a9_domain_memory_debt`<br>`test_app.AppTests.test_a9_domain_memory_required`<br>`test_app.AppTests.test_a9_domain_no_agent`<br>`test_app.AppTests.test_a9_domain_no_benchmark`<br>`test_app.AppTests.test_a9_domain_no_run`<br>`test_app.AppTests.test_a9_domain_not_inheritable`<br>`test_app.AppTests.test_a9_domain_rule_not_declared`<br>`test_app.AppTests.test_a9_domain_run_closed`<br>`test_app.AppTests.test_a9_domain_seat_not_allowed`<br>`test_app.AppTests.test_a9_domain_stale_rev`<br>`test_app.AppTests.test_a9_domain_timeout`<br>`test_app.AppTests.test_a9_false_and_nested_wrapper_are_passive_success` |
| A10 | `test_app.AppTests.test_a10_incidental_output_and_secret_exception_sanitized`<br>`test_app.AppTests.test_a10_invalid_results_and_invalid_error_details`<br>`test_cli.CliTests.test_a10_registry_chatter_is_confined_to_stderr` |
| A11 | `test_app.AppTests.test_a11_real_journal_replay_integration`<br>`test_app.AppTests.test_a11_rejecting_mutation_gets_exact_context_once_without_witness` |
| A12 | `test_cli.CliTests.test_a12_help_is_human_readable_and_does_not_import_delegates`<br>`test_cli.CliTests.test_a12_successful_machine_verbs_and_repeated_main_calls`<br>`test_cli.CliTests.test_a12_usage_errors_are_structured_and_do_not_invoke_handler` |
| A13 | `test_entrypoints.EntrypointTests.test_a13_real_original_entrypoints_discovery_and_unknown_tool` |
| A14 | `test_cli.CliTests.test_a14_builtin_verbs_never_import_lazy_hooks`<br>`test_cli.CliTests.test_a14_hooks_receive_unchanged_tail_context_registry_and_streams`<br>`test_cli.CliTests.test_a14_missing_hooks_and_installed_broken_hooks_have_distinct_exits`<br>`test_cli.CliTests.test_a14_registry_configuration_failure_is_not_success` |
| A15 | `test_entrypoints.EntrypointTests.test_a15_real_stdio_discovery_and_handshake_are_promptly_flushed`<br>`test_mcp.McpTests.test_a15_identity_capabilities_and_discovery_without_handshake` |
| A16 | `test_mcp.McpTests.test_a16_bad_params_and_unknown_names_reject_before_handler`<br>`test_mcp.McpTests.test_a16_ids_round_trip_and_methods_never_fall_through_to_tools`<br>`test_mcp.McpTests.test_a16_invalid_envelopes_have_null_error_id`<br>`test_mcp.McpTests.test_a16_server_configuration_failure_is_rpc_internal` |
| A17 | `test_mcp.McpTests.test_a17_notifications_cannot_execute_work` |
| A18 | `test_entrypoints.EntrypointTests.test_a18_real_frame_limit_recovery_and_final_eof_frame`<br>`test_mcp.McpTests.test_a18_exact_frame_limit_and_oversize_recovery`<br>`test_mcp.McpTests.test_a18_long_line_uses_bounded_reads_and_preserves_next_request`<br>`test_mcp.McpTests.test_a18_strict_parse_failures_recover_frame_boundaries`<br>`test_mcp.McpTests.test_a18_whitespace_and_final_frames_without_lf` |
| A19 | `test_cli.CliTests.test_a19_broken_cli_output_is_execution_failure`<br>`test_entrypoints.EntrypointTests.test_a19_real_stdio_error_liveness_and_eof`<br>`test_mcp.McpTests.test_a19_broken_mcp_output_is_execution_failure` |
| A20 | `test_mcp.McpTests.test_a20_exact_resource_bodies_independent_of_cwd_and_home`<br>`test_mcp.McpTests.test_a20_resource_default_root_is_installed_root`<br>`test_mcp.McpTests.test_a20_symlinked_intermediate_directory_and_escape_are_rejected`<br>`test_mcp.McpTests.test_a20_unreadable_resource_is_not_partial_success`<br>`test_mcp.McpTests.test_a20_unsupported_missing_invalid_utf8_and_symlinked_targets` |
| A21 | `test_mcp.McpTests.test_a21_prompt_arguments_closed_nonempty_strings`<br>`test_mcp.McpTests.test_a21_prompt_discovery_exact_shapes`<br>`test_mcp.McpTests.test_a21_prompt_injection_is_json_encoded_passive_and_deterministic` |
| A22 | `test_mcp.McpTests.test_a22_clean_generated_identity_and_unscrubbed_caller_data` |
| A23 | `test_entrypoints.EntrypointTests.test_a23_adapter_descriptor_omission_is_detected`<br>`test_entrypoints.EntrypointTests.test_a23_dispatch_validation_bypass_is_detected`<br>`test_entrypoints.EntrypointTests.test_a23_duplicate_bypass_is_detected_by_registry_oracle`<br>`test_entrypoints.EntrypointTests.test_a23_wrong_iserror_is_detected_by_tool_result_oracle` |
| A24 | `test_entrypoints.EntrypointTests.test_a24_domain_result_json_http_and_journal_witnesses_pending`<br>`test_entrypoints.EntrypointTests.test_a24_installed_inventory_parity_is_an_integration_gate` |

## Amendment decisions and unresolved contract conflicts

The unit spec explicitly requires an amendment before integration with a
conflicting later K0 contract. `docs/CONTRACT.md` and `docs/INTERFACES.md` contain
such conflicts. The unit-specific assertions retain the unit target; compatible
integration is **HOLD**, not silently claimed. No nonexistent schema API is
invented to bridge the two contracts.

| Surface | Unit spec target | K0 conflict / disposition |
|---|---|---|
| Tool metadata/callbacks | `ToolSpec.mutating`, keyword `context`, callable folds | `effect`, positional `Context`, `FoldSpec`; HOLD |
| Context/dispatch | `CallContext`, `DispatchResult`, explicit registry | `Context.services`, `ctx`, dict return/default insertion; HOLD |
| U02 API | `strict_loads`, `validate`, `SchemaError` | `decode`, store/base schema API; missing prerequisite and HOLD |
| CLI `tools` | `{tools: descriptors}` | Bare descriptor array; HOLD |
| MCP identity/negotiation | `0.1.0`, supported version returned on mismatch | `1.0.0`, incompatible proposal refused; HOLD |
| MCP frame bytes | 65,536 [CITED: unit spec] | 1,048,576 [TARGET: K0]; HOLD |
| Resource name | `Contract` | `Lineage contract`; HOLD |
| Prompt arguments | Required `spec` or `bench_id` only | Optional `agent_id`, breeding `parent_id`/`child_id`/`op`; HOLD |
| Error details | Strict JSON; U02 diagnostic objects preserved | Bounded strings; HOLD |

Amendment B resolutions:

- **B1:** Exercise schema validity through `registry.load()` using an unsupported
  assertion under an optional property. No schema-validation function name is
  asserted; the exact U02 schema-validation seam remains AUSENTE.
- **B2:** `TOOLS` is a tuple as explicitly declared. Registration shape/callback
  failures use `bad_extension`; malformed tool metadata uses `bad_descriptor`;
  malformed/unsupported schemas use `bad_schema`; duplicates use their named
  reasons. `detail.name` semantics were not supplied: test only the permitted
  keys, sanitization and reason. Absent/non-package injection permits either
  `import_failed` or `bad_extension` pending a normative decision.
- **B3:** No undocumented actor/op-id transport flags or MCP fields are added.
  Direct `create_context()` preserves supplied metadata. CLI defaults remain
  absent; MCP preserves the caller-provided context. Journal replay stays pending.
- **B4:** Global `--home` precedes the verb, as K0 states. Machine call responses
  use stdout. Unspecified usage/configuration stream placement accepts exactly
  one structured error on either stream. Help is human-readable and imports no
  delegates. Bare invocation, help's registry/context bypass, and `--json=...`
  remain unspecified and are not constrained.
- **B5:** Strip both `operator` and `ruling`; bare operator is rejected. Probe
  hook existence using `importlib.util.find_spec`; an installed hook's failed
  dependency is execution failure. Tests inject only temporary in-memory hooks.
- **B6:** Reject a symlinked leaf and symlinked intermediate `docs/` directory,
  including escape beyond the resource root.
- **B7:** Direct non-JSON arguments reject before invocation; incidental CLI
  registry/handler output belongs on the supplied stderr stream.
- **B8:** Missing/wrong-type `clientInfo` fields reject. Unknown clientInfo fields
  and whitespace-only prompt strings remain unresolved; the oracle adds no
  unsupported assertion for either. Empty strings are rejected.

Prompt encoding tests decode embedded JSON without requiring an undocumented
literal template or delimiter. Real permission refusal is checked where the
filesystem identity cannot bypass permission bits; otherwise that one gate
skips explicitly. Resource bodies preserve UTF-8 bytes, including CRLF.

## Bounded execution and non-vacuity

The prescribed command is:

```sh
python3 -m unittest discover -s tests/core/dispatch -t .
```

Each owned process has a deadline; live reads use selectors and observed LF
responses rather than sleeps. Tests never use process groups or broad signals;
cleanup can kill only its own still-live verified child PID. Temporary replicas
copy the actual entrypoints and add a passive test extension. The executable is
also exercised directly from an unrelated working directory, without PYTHONPATH.
No network, model invocation, dependency installation or production fixture
modification is performed.

A23 runs the same positive oracle assertions under isolated test mutants for
duplicate acceptance, adapter descriptor omission, validation bypass and an
incorrect `isError` flag. Each broken variant must make the oracle assertion
fail; a green variant is HOLD. Mutants do not edit production or oracle files.

All claims are scoped to `.unit/SPEC.md`, its supplied corpus and this isolated
test workspace; pending domain or product gates are not asserted as passed.

## Measured prerequisite receipt

Prescribed discovery exits with failure [MEASURED]: 105 tests discovered,
1 prerequisite assertion failure, 104 blocked/skipped, 0 errors, 0 green
behavioral tests [MEASURED]. Exact unittest summary:

```text
Ran 105 tests in 0.002s

FAILED (failures=1, skipped=104)
```

The failed assertion names the absent U01/U02 paths, not an ImportError.
Behavioral fail-first remains **BLOCKED / AUSENTE**. The pre-existing test tree
contained no test methods [MEASURED]; no existing behavioral green is claimed.
