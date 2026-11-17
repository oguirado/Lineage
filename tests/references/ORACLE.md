# U07 independent oracle

Authority: `.unit/SPEC.md`, MUST M1–M24, Acceptance A1–A30 and Amendment B;
`docs/CONTRACT.md` and `docs/INTERFACES.md` govern frozen public interfaces.
All tests use stdlib `unittest`. Test-created trees are temporary children of
`tests/references`, removed after use. No runtime implementation, disk stub,
external dependency, model, network request or process-group operation is supplied.

Run from the repository root with bytecode writes disabled in the environment:

```sh
python3 -m unittest discover -s tests/references -t .
```

The implementation publication command remains:

```sh
python3 tools/publish_check.py --root .
```

## Contract decisions and unavailable evidence

- Amendment B.1 gives K0 precedence at the shared tool boundary. `reference_get`
  returns `{reference:{id,sha256,bytes,rules}}`; `reference_verify` returns
  `{ref_id,sha256,bytes,valid}`. Both accept optional `agent`. The wire rejects
  `expected_sha256`. An `agent` of `operator` does not grant operator authority.
  The separately specified `reference_get`, `reference_verify` and
  `load_gold_rules` domain API is tested with its richer data and isolated root
  seam; this does not add a second transport or a permissive wire fallback.
- K0 defines U02's strict decoder as `decode`, whereas M11 names `strict_loads`.
  The dependency gate follows K0's published callable. No private loader is added.
- K0's extension event/fold map conflicts with M14's empty maps. The suite tests
  the exact read-tool inventory and effect, without choosing an unapproved
  event/fold contract. An orchestrator ruling is still required for that conflict.
- The manifest uses Amendment B.2's exact two-space, lowercase checksum format,
  sorted portable paths and final LF. Package hashes are independently computed
  from canonical descriptors, excluding their `sha256` field.
- Root-only exclusions and descriptor-safe nonblocking opens follow B.4–B.5.
  `.git` files and symlinks are scanned or refused; nested lookalikes are scanned.
- B.3 and B.4 request, but do not supply, exact diagnostic rule-id spellings,
  decoded-string coordinate mapping, lexical delimiters or all detector patterns.
  Tests assert frozen report keys, raw-byte coordinates, safe deterministic
  diagnostics, root exclusions, complete hostile examples and exit codes. They
  do not invent unstated punctuation or constrain unspecified parser internals.
  Until the usage-error stream is frozen, either stream may carry the sole JSON
  `bad_args` object; successful scan reports must be on stdout.
- B.6 does not provide exact citation punctuation. The metadata test preserves
  the original bracketed/parenthesized citation suffix from the injected input.
  Its grammar still needs independent confirmation from that input, rather than
  a fabricated original citation.
- The synthetic `test-sentinel` fingerprint is independently defined by the
  NFC/casefold normalization of the runtime-assembled marker in `sentinel()`.
  Its normalized literal includes an accented character to test decomposition.
  The author must ship that synthetic fingerprint. No production spelling is
  reconstructed from hashes or guessed from model knowledge.

The pre-work registry, pre-work index and complete production scrub inventory are
**AUSENTE — no inventar** in the supplied workspace. Tests never substitute the
public derivative for an independent original. The harness may inject the original
`gold_rules.json` with `LINEAGE_U07_ORACLE_GOLD_INPUT`; its bytes must match
`3c4d347ed6d4011112a61f3d48da76c4b5d230d688a0fc71cbb715b4cba0af8c`.
Original paper provenance remains
`f90dc84fc814fce0258a12d0e0fd17e5332021410470c469247e2b019b3511c5`,
with GOLD-S1 / PM-1001.1 / ACTIVE / ASSEMBLED / DRAFT retained.
The unavailable Memory v2.1 digest and documentary statuses remain null.

`LINEAGE_U07_ORACLE_FINGERPRINTS` and
`LINEAGE_U07_ORACLE_INVENTORY_SHA256` accept independently frozen production
records and their pin, supplied by the oracle writer, never derived from the
implementation's policy. `LINEAGE_U07_ORACLE_GLOB_EXAMPLES` accepts independent
concrete expansion objects with `token` and `rule_id`. These are test-only
injection seams, not product APIs. Their absence fails assertions; no test skips
or unverified default values allow admission. Independent production fingerprints
have not yet been frozen because the inventory input is absent.

No build/neutralizing-transform callable is specified. A2 tests the byte-identity
intake precondition; A9 tests portable final bytes and equal runtime results in
isolated roots. They do not claim to execute an unavailable build transform.
A complete A2/A9 build receipt requires that interface and verified original input.

## Acceptance mapping

Counts and enumerations below are specification targets or test names, not claims
of passing host verification. Generated test names are explicit below; a shared
prefix denotes each named generated method, not a skipped case.

| Acceptance | Test names and remaining admission obligations |
|---|---|
| A1 | `ToolOracle.test_a01_u02_u04_prerequisites_are_real_not_replacement_stubs`; `ToolOracle.test_a16_extension_discovery_exact_read_tool_descriptors`. The editing mandate confines this oracle to `tests/references`; shared prerequisite code is never patched. |
| A2 | `RegistryOracle.test_a02_prework_identity_and_exact_scrub_set`; `RegistryOracle.test_a02_intake_pin_discriminates_byte_removal_and_empty_input`. Original-input and build-transform proof remain blocked as stated above. |
| A3 | `RegistryOracle.test_a03_complete_ordered_id_label_and_gate_coverage`; `RegistryOracle.test_a07_index_resolves_every_identity_and_marks_derived_metadata`. |
| A4 | `RegistryOracle.test_a04_reject_compensated_duplicate`; `RegistryOracle.test_a04_reject_relabel_kind`; `RegistryOracle.test_a04_reject_missing_label`; `RegistryOracle.test_a04_full_rule_shapes_and_types`. |
| A5 | `RegistryOracle.test_a05_every_nontext_field_preserved_from_verified_intake`; `test_a05_registry_source_identity_is_not_public_package_identity`; generated `test_a05_reject_reversed_range`, `test_a05_reject_duplicate_role`, `test_a05_reject_derived_authority`, `test_a05_reject_missing_citation`. Full preservation remains input-gated. |
| A6 | `RegistryOracle.test_a06_substantive_text_in_additionally_affected_records`; generated `test_a06_reject_empty_text`, `test_a06_reject_placeholder`, `test_a06_reject_scrub_true_marker`, `test_a06_reject_scrub_false_marker`. |
| A7 | `RegistryOracle.test_a07_applicability_keeps_roles_and_source_statements_distinct`; `test_a07_index_resolves_every_identity_and_marks_derived_metadata`; `test_a07_imperative_rule_text_is_never_executed`. Human semantic review still assesses the substantive neutralizations. |
| A8 | `ArtifactOracle.test_a08_memory_derivative_honesty_and_citations`; `test_a08_source_provenance_and_unavailable_fields`; `test_a12_optional_pin_verifies_only_public_package`. |
| A9 | `ArtifactOracle.test_a09_lf_final_newline_no_timestamp_or_environment_fields`; `test_a09_two_isolated_packages_produce_equal_bytes_and_results`. The full transformation rebuild is blocked by the absent build contract/input. |
| A10 | `ArtifactOracle.test_a10_independent_package_and_file_hashes_match_code_pins`; generated `test_a10_a11_reject_registry_byte`, `test_a10_a11_reject_index_byte`, `test_a10_a11_reject_memory_byte`, `test_a10_a11_reject_recomputed_tamper`. |
| A11 | `ArtifactOracle.test_a11_complete_canonical_manifest`; generated `test_a10_a11_reject_missing_file`, `test_a10_a11_reject_duplicate_manifest`, `test_a10_a11_reject_manifest_corrupt`, `test_a10_a11_reject_unexpected_file`, `test_a10_a11_reject_wrong_length`, `test_a10_a11_reject_unknown_catalog_field`. |
| A12 | `ArtifactOracle.test_a12_optional_pin_verifies_only_public_package`; `test_a12_wrong_expected_pin_and_source_pin_are_rejected`. Expected-pin inputs are domain-only under K0. |
| A13 | `IsolationOracle.test_a13_reference_symlink_file_never_opens_external_target`; `test_a13_reference_symlink_directory_never_opens_external_target`; `test_a13_reference_fifo_is_rejected_without_a_blocking_open`; `test_a13_symlink_swap_between_check_and_open_is_rejected`; `test_a13_reference_files_require_nofollow_nonblock_and_regular_descriptors`; `test_a13_fstat_nonregular_descriptor_is_rejected_before_data_use`; `test_a13_trusted_fixture_pin_cannot_admit_relative_path_escape`; `test_a13_trusted_fixture_pin_cannot_admit_absolute_path_escape`; `ArtifactOracle.test_a10_a11_reject_catalog_path_escape`; `test_a10_a11_reject_catalog_absolute_path`. |
| A14 | Generated `ArtifactOracle.test_a14_reject_duplicate_nested_key`, `test_a14_reject_nonfinite`, `test_a14_reject_float_overflow`, `test_a14_reject_invalid_utf8`, `test_a14_reject_surrogate`, `test_a14_reject_bad_digest`, `test_a14_reject_oversize`, `test_a14_reject_trailing_json`; `RegistryOracle.test_a14_reject_boolean_line`; `test_a14_reject_unknown_field`. An exact U02 depth-ceiling test remains blocked by absent U02 code/contract details. |
| A15 | `ArtifactOracle.test_a15_get_returns_complete_exact_detached_data`; `ToolOracle.test_a16_handlers_return_raw_k0_shapes`. |
| A16 | `ToolOracle.test_a16_extension_discovery_exact_read_tool_descriptors`; `test_a16_handlers_return_raw_k0_shapes`; `test_a16_dispatch_wraps_success_once_and_preserves_actor_restriction`; `test_a16_k0_rejects_extended_wire_expected_digest`; `test_a16_cli_and_mcp_share_reference_boundary`; generated `test_a16_bad_args_unknown_id`, `missing_id`, `null_id`, `boolean_id`, `extra_field`, `root_selection`, `authority_selection`, `invalid_agent`, `short_agent`, `null_agent`, `agent_newline`, `path_agent` with the shared `test_a16_bad_args_` prefix. Prerequisite-dependent tamper propagation and the event/fold conflict still require integration evidence. |
| A17 | `IsolationOracle.test_a17_default_root_ignores_cwd_and_runtime_environment`; `test_a17_normal_reads_and_scans_are_silent_without_network_or_processes`; `test_a17_extension_import_is_read_only_and_silent`; `test_a17_reads_do_not_open_the_unselected_reference`; `test_a17_reads_do_not_create_even_transient_files_or_journal_events`. |
| A18 | `PublicationOracle.test_a18_policy_schema_sentinel_and_inventory_digest`; `test_a18_independent_frozen_production_inventory`; `test_a18_default_policy_is_installed_not_selected_by_scan_root`; generated `test_a18_policy_tamper_missing`, `remove_entry`, `wrong_chars`, `wrong_hash`, `broaden_exception` with the shared `test_a18_policy_tamper_` prefix. Production completeness is independently input-gated. |
| A19 | `PublicationOracle.test_a19_clean_ordinary_public_syntax_passes`; generated `test_a19_posix`, `test_a19_windows`, `test_a19_unc`, `test_a19_hostname_config`, `test_a19_authority`, `test_a19_secret`; `test_a25_cli_clean_and_forbidden_exit_mapping`. |
| A20 | Generated `PublicationOracle.test_a20_a23_sentinel_filename`, `casefold`, `unicode_nfd`, `escaped_json`, `escaped_python`, `binary_prefix`, `large_file`, `buffer_edges` with the shared `test_a20_a23_sentinel_` prefix; `test_a20_literal_sentinel_does_not_match_reordered_or_shortened_text`; `test_a20_production_glob_expansions_require_injected_inventory_examples`. Production expansion evidence is absent; synthetic/Unicode controls are independent. |
| A21 | `PublicationOracle.test_a21_exceptions_apply_to_exact_owned_path_not_prose_or_siblings`; `test_a19_clean_ordinary_public_syntax_passes`; `test_a18_independent_frozen_production_inventory`. Complete private-command/isolated-binding examples still depend on the missing inventory. |
| A22 | `PublicationOracle.test_a22_only_root_exclusion_boundaries_are_reported`; `test_a22_unexcluded_boundary_0` through `test_a22_unexcluded_boundary_9`; `test_a22_root_git_file_is_scanned`; `test_a22_root_seed_file_is_scanned`; `test_a22_root_dependency_file_is_scanned`; `test_a22_root_git_symlink_is_unsafe`; `test_a22_dependency_symlink_exclusion_does_not_open_target`; `IsolationOracle.test_a22_scanned_symlink_file_and_directory_are_not_followed`; `test_a22_scanned_fifo_is_rejected_without_a_blocking_open`; `test_a22_scanner_requires_nofollow_nonblock_and_regular_descriptors`; `test_a22_scanner_fstat_nonregular_descriptor_cannot_pass`. |
| A23 | `PublicationOracle.test_a23_absent_and_nondirectory_roots_fail`; large/binary/buffer tests mapped at A20; `IsolationOracle.test_a23_a27_scanner_read_refusal_keeps_unknown_coordinates_null`; `test_a23_traversal_error_is_not_a_clean_empty_tree`. |
| A24 | `PublicationOracle.test_a24_raw_locations_and_safe_reproducible_sorted_diagnostics`; `test_a24_hostile_filename_redaction_keeps_a_stable_digest`; `test_a25_cli_clean_and_forbidden_exit_mapping`; shared domain-error privacy checks. Decoded-string exact coordinate mapping awaits the requested freeze. |
| A25 | `PublicationOracle.test_a25_cli_clean_and_forbidden_exit_mapping`; `test_a25_reject_weakening_or_bad_invocation_0` through `test_a25_reject_weakening_or_bad_invocation_7`. |
| A26 | `PublicationOracle.test_a26_complete_public_tree_scans_itself`; `test_a26_seeded_content_class_0` through `test_a26_seeded_content_class_5`; no scanner/test blanket exemption. |
| A27 | `IsolationOracle.test_a27_reference_read_refusal_is_internal_and_never_repairs`; `test_a23_a27_scanner_read_refusal_keeps_unknown_coordinates_null`; `test_a27_argument_errors_remain_distinct_from_integrity_failures`; corrupted-package and strict-record tests compare pre/post content, metadata and path sets. |
| A28 | `IsolationOracle.test_a28_wrong_data_and_always_clean_in_memory_controls_fail_assertions`; all semantic fixture tests. Module/artifact preconditions fail assertions, not imports; no stub files or skips are introduced. Separate in-memory controls execute the actual registry/get/scanner test assertions against deliberate wrong-data objects. |
| A29 | `ArtifactOracle.test_a10_a11_reject_recomputed_tamper`; `PublicationOracle.test_a18_policy_tamper_broaden_exception`; `IsolationOracle.test_a28_wrong_data_and_always_clean_in_memory_controls_fail_assertions` discriminate externally wrong behavior. Actual disposable-source mutants for bypassed digest comparison, disabled detector and broadened matcher exception are **not claimed executed**: the implementation is absent. Those host runs remain an admission obligation. |
| A30 | Composite of A1, A16, A25, A26 and the exact discovery command. A successful worker statement is insufficient. Missing inputs, unresolved frozen-contract details or unexecuted mutant/integration controls block final implementation admission; receipts belong outside this public unit surface. |

## Freeze and regression discipline

The oracle is intentionally red before implementation. Required-module assertions
precede imports so discovery itself remains usable. Wrong return shapes, accepted
corruption and always-clean reports reach behavioral assertions once modules exist.
Do not weaken these assertions to admit an implementation. Completing the absent
independent source expectations or resolving contract conflicts requires an
orchestrator amendment. A full implementation admission is not claimed by this
pre-author test delivery.


## Amendments A-U07

- `test_tools.py`: use U02 `strict_loads` instead of documented `decode`;
  use U04 `Registry.tools`, `app.list_tools(registry=...)`, and
  `ToolSpec.mutating == False` for the same discovery/read-effect assertions.
- `test_tools.py`: replace unavailable `Services`/`Context` fixture construction
  with `app.create_context(home, registry=..., actor=...)`; supply `context` and
  `registry` explicitly to dispatch and inspect `DispatchResult.payload`.
  Optional argument actors remain passive data, with the same no-write checks.
- `__init__.py`: admit the now-staged `.unit/prework/gold_rules.json` as the
  default intake fixture, preserving the independent byte pin and every intake
  assertion. Explicit environment injection still overrides it.
- `test_registry.py`: adapt the citation fixture parser to the verified input's
  final period; keep the exact original citation-suffix preservation assertion.
- `test_isolation.py`: move FIFO fixture snapshots outside the SUT-only open
  observer; both operations still must reject, descriptor flags remain observed,
  and the same complete before/after tree comparison remains mandatory.
- `policy_expectations.json` and `test_publish_check.py`: supply independently
  frozen fingerprint and concrete-expansion fixtures from the supplied strategy
  inventory. Expectations are never calculated from the implementation policy.
  Concrete tokens are assembled from code points at runtime; explicit environment
  injection remains available. No production entry, failure case, or assertion
  is removed or relaxed.

- `test_tools.py`: refresh dependent import fixtures after U02's import-isolation
  oracle reloads its exception class; exercise the integrated U04 implementation
  with matching live `SchemaError`/`ToolSpec` identities, without patching shared
  source or replacing any behavior.
