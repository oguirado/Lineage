# U09 fail-first oracle

Status: **HOLD** for dependency-backed acceptance. This deliverable freezes tests and importable U09 stubs, not an implementation or ADMIT receipt.

## Scope and execution

Run from the repository root:

```sh
python3 -m unittest discover -s tests/skills -t .
```

The specification is SPEC_U09, including Amendment B. Its SHA-256 is `5d6adec08cce80bcf132f47bce907b3408f0c02408a5781a53d6a2d2c95f3418` [MEASURED]. All fixture bounds and expected domain behavior are [TARGET] until executed against real dependencies. Canonical expectations include a literal UTF-8 vector and a separately computed, frozen SHA-256, rather than the production canonicalizer.

Every test first requires the same positive canonical-package witness. In this snapshot that call raises `NotImplementedError("U09 stub")`; integration prerequisites are deliberately imported only after that witness. This makes the initial red distinguishable from a missing import. No test catches a stub exception as success, skips a missing prerequisite, installs a replacement core, or changes production behavior to pass.

The runtime fixture requires the public K0 objects and real registry/journal/dispatch. The supplied extracted core lacks `Command`, `Context`, `Services`, `Snapshot`, `EventDraft`, `LineageError`, `SchemaStore`, and the K0 transaction API. `lineage/core/schema.py` and the public `lineage` module entry point are AUSENTE in this snapshot. Missing prerequisites become explicit HOLD assertion failures once the package witness succeeds. No compatibility API is invented.

Python tests use only stdlib unittest. Runtime state lives in isolated temporary homes; clocks and identifiers are injected. Concurrency uses independent processes and barriers/events, never fixed sleeps. Cleanup can signal only exact owned child PIDs greater than one [TARGET]; no process groups are created or signalled. Child waits and transport timeouts are bounded; each test targets less than five seconds [TARGET].

## Frozen interpretation choices

- `Command.args` requires exactly `{skill_id,files,agent,op_id}` for `skill_publish` and `{skill_id,sha256,reason,agent,op_id}` for `skill_retire`, plus optional `expected_head`. Arguments, actor, op_id, tool and command revision must agree with the call and Context. File-array order remains request identity. An omitted revision corresponds to `Command.expected_head=None`; explicit null is invalid in arguments.
- `system` and `operator` are admitted as ordinary caller-asserted skill mutation actors under tool authority. They confer no operator authority and create no agent. This follows the K0 shared actor contract; reserving names from agent creation does not reserve them from skill requests.
- The domain Sequence signature admits a tuple for pure `package`; JSON transports retain their frozen array schemas.
- Schema objects are extracted verbatim from `docs/CONTRACT.md` for equality. The permissive frozen path regex is preserved: `a//b` and `a/b/` pass schema validation and fail domain admission with `bad_args`, CLI exit three [CITED: Amendment B].
- Runtime symlink checks begin at `skills/`; a symlink above that boundary is valid. A linked projection component is `bad_args`; a completed non-directory or modified package is `hash_mismatch`; a corrupt/unreadable `skill_list` history is `internal`.
- No seed population, private fold representation, staging filename or ledger-lock filename is prescribed. The lock fixture obtains the real lock through a blocked public `transact` prepare callback. Capacity builds synthetic state through the registered public fold and substitutes only the public snapshot seam.
- The I/O-fault fixture permits an initial package-entry write, then faults the next write after a journal event exists, discriminating staged publication from a partial final directory. Placement fixtures simulate a concurrent complete destination through descriptor-safe copies, then raise `EEXIST` or `ENOTEMPTY`; corrupted destination bytes must remain untouched.
- A repository publication checker is AUSENTE from the supplied corpus. The independent local public-string screen and its clean/forbidden fixtures do not claim that absent external checker receipt. A28 remains subject to that campaign verification gap.
- JSON/HTTP parity, cross-family review, persona QA and live external interoperability receipts are AUSENTE and are not asserted by this U09 oracle.

## Acceptance mapping

Every acceptance identifier below maps to concrete test methods. The final column states the admission witness and its rejecting contrast; these are [TARGET] expectations, not runtime acceptance results.

| Acceptance | Test names | Witness and rejecting contrast |
|---|---|---|
| A1 | `tests/skills/test_extension.py::SignatureOracle.test_a01_exact_public_domain_signatures`<br>`tests/skills/test_extension.py::ExtensionOracle.test_a01_exact_registry_schema_effect_and_ownership`<br>`tests/skills/test_extension.py::ExtensionOracle.test_a01_shared_dispatch_has_one_wrapper_and_real_witness`<br>`tests/skills/test_extension.py::ExtensionOracle.test_a01_lexical_loader_refuses_duplicate_registration_atomically` | Exact signatures, schema objects, ownership/effects, duplicate-load refusal, and one shared wrapper. |
| A2 | `tests/skills/test_extension.py::ExtensionOracle.test_a02_closed_dispatch_hostile_arguments`<br>`tests/skills/test_extension.py::ExtensionOracle.test_a02_strict_decode_duplicate_nonfinite_and_invalid_unicode`<br>`tests/skills/test_package.py::PackageOracle.test_a02_direct_package_wrong_types_and_extra_keys`<br>`tests/skills/test_replay.py::ReplayOracle.test_a02_publish_function_command_context_must_agree`<br>`tests/skills/test_replay.py::ReplayOracle.test_a02_retire_function_command_context_must_agree`<br>`tests/skills/test_replay.py::ReplayOracle.test_a02_direct_api_wrong_types_ids_reason_and_revision`<br>`tests/skills/test_replay.py::ReplayOracle.test_a02_reserved_actors_are_ordinary_tool_actors`<br>`tests/skills/test_replay.py::ReplayOracle.test_a02_direct_publish_rejects_invalid_files_and_commands`<br>`tests/skills/test_replay.py::ReplayOracle.test_a02_direct_retirement_hashes_and_reason_bound` | Closed and strict arguments, direct-call type/text validation, full Command agreement, and ordinary reserved actors. |
| A3 | `tests/skills/test_catalogue.py::CatalogueOracle.test_a03_package_pin_is_independent_of_skill_id`<br>`tests/skills/test_package.py::PackageOracle.test_a03_literal_canonical_vector` | Literal canonical UTF-8 bytes and precomputed digest; order and skill identity cannot alter the pin. |
| A4 | `tests/skills/test_package.py::PackageOracle.test_a04_content_codepoints_and_line_endings_are_preserved`<br>`tests/skills/test_package.py::PackageOracle.test_a04_path_is_part_of_pin` | Independent vectors distinguish every path/content/codepoint/line-ending/newline change. |
| A5 | `tests/skills/test_integrity.py::IntegrityOracle.test_a05_a06_rejected_packages_append_nothing`<br>`tests/skills/test_package.py::PackageOracle.test_a05_exact_root_entrypoint_and_collisions` | Only the root entry point is admitted; duplicates and file/directory collisions reject without append. |
| A6 | `tests/skills/test_integrity.py::IntegrityOracle.test_a05_a06_rejected_packages_append_nothing`<br>`tests/skills/test_package.py::PackageOracle.test_a06_path_attack_matrix` | Hostile paths are refused rather than normalized; empty and trailing segments remain domain errors. |
| A7 | `tests/skills/test_integrity.py::IntegrityOracle.test_a07_new_publish_refuses_each_symlink_before_transaction`<br>`tests/skills/test_integrity.py::IntegrityOracle.test_a07_existing_lookup_refuses_each_symlink`<br>`tests/skills/test_integrity.py::IntegrityOracle.test_a07_symlink_above_runtime_skills_is_allowed` | Every symlink component below runtime skills rejects; ancestor symlinks remain permitted. |
| A8 | `tests/skills/test_extension.py::ExtensionOracle.test_a08_transport_envelope_cap_is_separate`<br>`tests/skills/test_integrity.py::IntegrityOracle.test_a08_rejected_publication_bounds_have_no_event`<br>`tests/skills/test_package.py::PackageOracle.test_a08_file_count_bounds`<br>`tests/skills/test_package.py::PackageOracle.test_a08_path_character_length_bounds`<br>`tests/skills/test_package.py::PackageOracle.test_a08_content_character_length_bounds`<br>`tests/skills/test_package.py::PackageOracle.test_a08_exact_canonical_utf8_byte_bound`<br>`tests/skills/test_package.py::PackageOracle.test_a08_json_escaping_counts_toward_byte_bound` | Character/count/path/UTF-8/escaping bounds and the separate full-input cap. |
| A9 | `tests/skills/test_catalogue.py::CatalogueOracle.test_a09_committed_publication_and_independent_chain` | Publication payload, receipt prefix, independent raw chain, lookup and exact projection bytes. |
| A10 | `tests/skills/test_catalogue.py::CatalogueOracle.test_a10_multiple_versions_and_nonlexical_latest` | Old and new pins coexist; greatest publication Lamport wins rather than hash order. |
| A11 | `tests/skills/test_replay.py::ReplayOracle.test_a11_original_publication_replays_after_retirement_and_new_head`<br>`tests/skills/test_replay.py::ReplayOracle.test_a11_retirement_replay_retains_original_commit` | Exact replay preserves original result/receipt after intervening commits and ignores obsolete revision. |
| A12 | `tests/skills/test_replay.py::ReplayOracle.test_a12_changed_files_paths_order_and_skill_id_refused`<br>`tests/skills/test_replay.py::ReplayOracle.test_a12_same_identity_changed_tool_is_bad_op`<br>`tests/skills/test_replay.py::ReplayOracle.test_a12_distinct_request_can_share_package_pin` | Changed content/path/order/id/tool refuses; distinct operations may share a pin. |
| A13 | `tests/skills/test_replay.py::ReplayOracle.test_a13_new_operation_checks_revision_under_lock`<br>`tests/skills/test_replay.py::ReplayOracle.test_a13_operation_identity_is_scoped_by_actor` | Locked expected_head and actor-scoped identities; replay precedes current revision admission. |
| A14 | `tests/skills/test_catalogue.py::CatalogueOracle.test_a14_retirement_is_exact_pin_and_schema_closed` | Exact retirement payload, version-local filtering and immutable historical resolution. |
| A15 | `tests/skills/test_catalogue.py::CatalogueOracle.test_a15_retirement_is_monotonic_across_distinct_operations`<br>`tests/skills/test_replay.py::ReplayOracle.test_a15_retirement_reason_participates_in_request_identity` | Reason identity, exact replay, distinct retire/republish events, one row, monotonic retirement. |
| A16 | `tests/skills/test_catalogue.py::CatalogueOracle.test_a16_empty_catalogue_and_no_seed_discovery`<br>`tests/skills/test_catalogue.py::CatalogueOracle.test_a16_complete_deterministic_sorted_listing`<br>`tests/skills/test_catalogue.py::CatalogueOracle.test_a16_capacity_is_internal_without_truncation`<br>`tests/skills/test_extension.py::ExtensionOracle.test_a16_registry_reload_and_reads_do_not_bootstrap_or_write`<br>`tests/skills/test_integrity.py::IntegrityOracle.test_a16_corrupt_or_unreadable_ledger_never_lists_as_empty` | Verified empty catalogue, deterministic complete listing, corrupt/unreadable refusal and overflow refusal. |
| A17 | `tests/skills/test_catalogue.py::CatalogueOracle.test_a17_unpinned_fallback_and_all_retired`<br>`tests/skills/test_catalogue.py::CatalogueOracle.test_a17_republishing_active_pin_advances_publication_order` | Latest-active fallback, all-retired refusal and republishing an active pin advances its Lamport. |
| A18 | `tests/skills/test_catalogue.py::CatalogueOracle.test_a18_missing_pin_and_invalid_syntax` | Absent skill/version and invalid syntax differ from tampered immutable representation; wire errors close and sanitize. |
| A19 | `tests/skills/test_integrity.py::IntegrityOracle.test_a19_direct_append_cannot_bypass_publication_checks`<br>`tests/skills/test_integrity.py::IntegrityOracle.test_a19_direct_append_retirement_schema_and_existence`<br>`tests/skills/test_integrity.py::IntegrityOracle.test_a19_registered_validator_is_pure_and_cannot_dispatch_or_write` | Real direct append cannot bypass validation, including Amendment B bounds; validators are pure. |
| A20 | `tests/skills/test_integrity.py::IntegrityOracle.test_a20_tampered_projection_is_not_repaired_by_get_or_replay`<br>`tests/skills/test_integrity.py::IntegrityOracle.test_a20_new_operation_does_not_overwrite_existing_corrupt_pin` | Changed/missing/extra/non-directory completed projections fail without read/replay/new-operation overwrite. |
| A21 | `tests/skills/test_integrity.py::IntegrityOracle.test_a21_absent_projection_reads_are_pure_retry_rebuilds_original` | Wholly deleted projections do not affect pure reads; exact retry rebuilds original bytes and receipt. |
| A22 | `tests/skills/test_catalogue.py::CatalogueOracle.test_a22_returns_and_publication_inputs_are_isolated`<br>`tests/skills/test_catalogue.py::CatalogueOracle.test_a22_runtime_homes_have_independent_catalogues`<br>`tests/skills/test_extension.py::ExtensionOracle.test_a22_fold_owns_only_skills_and_does_not_alias_event`<br>`tests/skills/test_package.py::PackageOracle.test_a22_package_inputs_are_defensively_copied` | Caller/result/event defensive copies, isolated runtime homes, and exclusive fold namespace ownership. |
| A23 | `tests/skills/test_concurrency.py::ConcurrencyOracle.test_a23_same_identity_identical_requests_have_one_event`<br>`tests/skills/test_concurrency.py::ConcurrencyOracle.test_a23_same_identity_changed_request_admits_exactly_one`<br>`tests/skills/test_concurrency.py::ConcurrencyOracle.test_a23_distinct_operations_same_pin_keep_both_commits`<br>`tests/skills/test_concurrency.py::ConcurrencyOracle.test_a23_publication_retirement_race_preserves_all_pins`<br>`tests/skills/test_integrity.py::IntegrityOracle.test_a23_atomic_placement_eexist_verifies_identical_destination`<br>`tests/skills/test_integrity.py::IntegrityOracle.test_a23_atomic_placement_enotempty_verifies_identical_destination`<br>`tests/skills/test_integrity.py::IntegrityOracle.test_a23_collision_with_changed_destination_refuses_without_overwrite` | Barrier-coordinated processes, identity races, monotonic retirement and deterministic placement-collision branches. |
| A24 | `tests/skills/test_concurrency.py::ConcurrencyOracle.test_a24_real_lock_contention_is_busy_then_release_succeeds`<br>`tests/skills/test_integrity.py::IntegrityOracle.test_a24_corrupt_history_blocks_mutation_without_projection` | Real locked prepare callback proves contention; corruption refuses mutation and projection publication. |
| A25 | `tests/skills/test_integrity.py::IntegrityOracle.test_a25_postcommit_io_failure_has_no_partial_final_and_exact_recovery` | Post-commit projection I/O fault leaves a durable event and no partial final directory; retry repairs once. |
| A26 | `tests/skills/test_extension.py::ExtensionOracle.test_a26_cli_and_mcp_discovery_match_frozen_descriptors`<br>`tests/skills/test_extension.py::ExtensionOracle.test_a26_cli_mutation_mcp_read_and_original_replay`<br>`tests/skills/test_extension.py::ExtensionOracle.test_a26_cli_usage_and_mcp_schema_errors`<br>`tests/skills/test_extension.py::ExtensionOracle.test_a26_cli_domain_and_mcp_domain_errors`<br>`tests/skills/test_extension.py::ExtensionOracle.test_a26_cli_duplicate_json_and_nonfinite_refusals`<br>`tests/skills/test_extension.py::ExtensionOracle.test_a26_empty_segments_remain_domain_errors_cli_exit_three` | Real shared CLI/MCP discovery, success/replay, strict usage failures, domain failures and empty-segment exit mapping. |
| A27 | `tests/skills/test_extension.py::ExtensionOracle.test_a27_hostile_packages_are_passive_data` | Hostile prose and companion Python round-trip with execution/network guards and no authority change. |
| A28 | `tests/skills/test_extension.py::PortableOracle.test_a28_surface_markers_and_passive_stdlib_source`<br>`tests/skills/test_extension.py::PortableOracle.test_a28_public_string_screen_discriminates_forbidden_fixture`<br>`tests/skills/test_extension.py::DiscriminationOracle.test_a28_shared_repository_files_stay_readonly` | Public surface/import checks, discriminating public-string fixtures, runtime repository immutability and external write audit. |
| A29 | `tests/skills/test_extension.py::DiscriminationOracle.test_a29_same_witnesses_reject_in_memory_gate_mutants` | The same refusal/history witnesses reject isolated in-memory omitted-gate mutants; no production mutation. |

## Source surfaces and freeze seals

New stubs: `lineage/domain/skills.py`, `lineage/ext/skills.py`. Only the named domain functions have bodies; every body raises `NotImplementedError("U09 stub")`. The extension exports typed empty `TOOLS`, `VALIDATORS`, and `FOLDS` placeholders without registration, transport imports or I/O. No unspecified handler name or seed is fabricated.

The existing `tests/skills/__init__.py` package marker now also holds test-only fixtures. New test files are `tests/skills/test_package.py`, `tests/skills/test_catalogue.py`, `tests/skills/test_replay.py`, `tests/skills/test_integrity.py`, `tests/skills/test_concurrency.py`, and `tests/skills/test_extension.py`. This report is `tests/skills/ORACLE.md`. No seed package is required or created under `skills/`.

Read-only contract dependencies are `lineage/core/registry.py`, `lineage/core/journal.py`, `lineage/core/errors.py`, `lineage/core/app.py`, `lineage/core/schema.py` when supplied, `docs/CONTRACT.md`, `docs/INTERFACES.md`, `schemas/event.schema.json`, `schemas/agent.schema.json`, and `schemas/tool_error.schema.json`. The tests use `ledger/main/events.jsonl` and `skills/<skill_id>/<sha256>/` only within temporary runtime homes.

SHA-256 seals below are [MEASURED] before final verification; they identify frozen oracle bytes and stubs, not an implementation receipt.

| Path | SHA-256 |
|---|---|
| `lineage/domain/skills.py` | `8cb44facd18e910a926bc48036bf808002f97ad133e500830bced238640b711d` |
| `lineage/ext/skills.py` | `b537728d7db5cf852119557b0ae79796b39b727213a2145427723bf95e709a8b` |
| `tests/skills/__init__.py` | `3fa22574efb9815817ebf206f865d677d02b93d2b032f323813e9242cde294a4` |
| `tests/skills/test_catalogue.py` | `d2cdd9a57f5cd1a051e940f2a68289f1f4324846b0c17191b32790861aa79111` |
| `tests/skills/test_concurrency.py` | `9f454820cca9700e51ecde8af685033b0cd9da4821010789979659015afa3917` |
| `tests/skills/test_extension.py` | `4245ab56a747ae8929dd560a32fe7dcf14306512aa0853276aeea82175087aa4` |
| `tests/skills/test_integrity.py` | `6b629bd3dcda3a1f5fe997f6614142162b6ddc403686ffee28eff292a2f8baaa` |
| `tests/skills/test_package.py` | `7947c7b6c682ec45a2d6956d1c69ebf47a37b04d3b0d39f40f528dd76c26a63d` |
| `tests/skills/test_replay.py` | `ba38d571cf186281dcb899ac7f4fa284ced8eebb1ad24f6d180db1f8cf6db821` |

## Initial host verification

The named command completed with 81 red tests, zero green tests, zero skips and zero import errors [MEASURED]. Every error is exactly `NotImplementedError: U09 stub` from the positive canonical-package witness. The process exit was one [MEASURED]. No dependency-backed runtime or mutant-discrimination pass is claimed.

Exact unittest summary [MEASURED]:

```text
----------------------------------------------------------------------
Ran 81 tests in 0.004s

FAILED (errors=81)
```

Full discovery regression comparison [MEASURED]:

```text
----------------------------------------------------------------------
Ran 1685 tests in 286.050s

FAILED (errors=81)
```

The complete run contained 1685 tests: exactly 81 expected U09 stub errors and 1604 green legacy tests, with no failures or additional errors [MEASURED]. The pre-edit baseline was `Ran 1604 tests in 282.447s` / `OK` [MEASURED]. Filtered runner attempts changed multiprocessing or module selection and are not used as regression evidence.

Final named-command verification [MEASURED]:

```text
----------------------------------------------------------------------
Ran 81 tests in 0.004s

FAILED (errors=81)
```

The final boundary audit matches all 346 protected original files byte-for-byte [MEASURED]; the aggregate SHA-256 is `38dfcb0b66b0a35b3994e295e28c963c2824c84370be3762ce5e9367f21bae21` [MEASURED]. All oracle/stub freeze seals match. The named command has exactly 81 red tests, zero green tests, zero skips and zero import errors [MEASURED], each red caused by the explicit U09 stub. The existing tests remain green in the full discovery comparison above.


## Amendments A-U09

The orchestrator's A-U09 reconciliation and A-K0-9 integrated-API ruling supersede the historical missing-prerequisite HOLD above. Only oracle plumbing and fixtures are reconciled here. The literal package vector, package ceilings, test identities, positive/negative cases and domain behaviour remain frozen. Production sources and shared dependencies are unchanged.

| Changed surface | Exact reconciliation and preserved witness |
|---|---|
| `tests/skills/__init__.py`: `Command`, `RuntimeCase.setUp` | Define an independent immutable effective-request fixture because integrated `registry` has no `Command`. Require actual `load`, `snapshot`, `transact`, `verify`, `dispatch`, `create_context`, `strict_loads`, `validate`, `SchemaError`. Refresh real registry/application consumers and skill descriptors if another suite reloads the schema exception class; never replace validation or suppress an exception. |
| `tests/skills/__init__.py`: `context`, `command`, `publish` | Construct real `app.CallContext` through `create_context(home, registry=..., actor=...)`; there is no `Services` container, injected service clock, identifier factory or context authority field. Build independent command arguments and use dataclass actor replacement. The real journal supplies timestamps/identifiers; receipt uniqueness and chain assertions remain. |
| `tests/skills/__init__.py`: `assert_chain`, `dispatch` | `journal.verify(home)` reports `ok/errors`; `app.dispatch(..., context=..., registry=...)` returns `DispatchResult.payload`. Preserve independent record hashing, commit prefix checks, unchanged-ledger refusal and exactly one `untrusted` wrapper. |
| `tests/skills/__init__.py`: `assert_error_wire`, `mcp` | Explicit schema-error call sites require the integrated closed diagnostic object with exactly `reason`, `pointer`, `schema_pointer`; domain details still require strings. Bounds, host-coordinate exclusion and traceback exclusion remain. MCP continues to execute the real stdio entry point. |
| `tests/skills/test_catalogue.py`: `test_a16_capacity_is_internal_without_truncation` | Integrated snapshots are detached event tuples, without `Snapshot` or public `fold`. Substitute the complete synthetic event tuple at the real snapshot seam; retain the over-capacity `internal` assertion and reject truncation. |
| `tests/skills/test_concurrency.py`: `child_context`, `worker`, `lock_owner` | Use real CallContext plus independent Command fixture. Integrated `transact(home, agent=..., op_id=..., kind=..., payload=..., validators=..., prepare=...)` is the public append seam. Its locked prepare callback receives `(history, draft)` and returns payload. Preserve actual lock contention, barriers, exact owned-child cleanup, serial-history and receipt assertions. |
| `tests/skills/test_integrity.py`: `direct_append` | Invoke the integrated public `journal.transact` directly, with registered validators and no domain publication helper. The absent `append/EventDraft/render` API is replaced only in fixture plumbing; wrap the returned real event for existing receipt assertions. All forged payload, bounds, path and retirement rejection cases remain. |
| `tests/skills/test_integrity.py`: `test_a19_registered_validator_is_pure_and_cannot_dispatch_or_write` | Use `snapshot(home)` and validator `(history, event)`, preserve the complete original history tuple, and guard the actual `transact` mutation entry point. Keep all write/dispatch/execution guards and digest-refusal, nonaliasing and unchanged-filesystem assertions. |
| `tests/skills/test_extension.py`: `test_a01_exact_registry_schema_effect_and_ownership` | Integrated ToolSpec uses boolean `mutating` rather than string `effect`; handlers take `(args, *, context)`. Discovery is `app.list_tools(registry=...)`. Preserve exact tool ownership, frozen schema equality, fold order/kinds and descriptor closure. |
| `tests/skills/test_extension.py`: `test_a01_lexical_loader_refuses_duplicate_registration_atomically` | Read registry names from the immutable `Registry.tools` map; retain duplicate rejection and unchanged inventory assertions. |
| `tests/skills/test_extension.py`: `test_a02_closed_dispatch_hostile_arguments`, `test_a02_strict_decode_duplicate_nonfinite_and_invalid_unicode` | Use real `strict_loads` and its `SchemaError` with `bad_args`, plus integrated closed schema diagnostics. Every hostile request, invalid encoding, duplicate key, nonfinite value and no-event witness remains. |
| `tests/skills/test_extension.py`: `test_a08_transport_envelope_cap_is_separate` | The integrated decoder's `MAX_JSON_BYTES` is asserted equal to 65,536 [MEASURED from source]. Build exact-bound and immediately-over-bound transport fixtures against that authority instead of the documented 1,048,576 [CITED] transport cap. Keep the independent 1,048,576-byte [CITED] pure-package witness and rejection of its oversized envelope. No accepted limit is widened. |
| `tests/skills/test_extension.py`: `test_a22_fold_owns_only_skills_and_does_not_alias_event` | Call the integrated reducer directly instead of `FoldSpec.apply`; retain unrelated namespaces and defensive-copy assertions. |
| `tests/skills/test_extension.py`: `test_a26_cli_and_mcp_discovery_match_frozen_descriptors` | Extract CLI descriptors from its `tools` envelope before comparing to MCP and exact frozen schemas. |
| `tests/skills/test_extension.py`: `test_a26_cli_usage_and_mcp_schema_errors`, `test_a26_cli_duplicate_json_and_nonfinite_refusals`, `test_a26_empty_segments_remain_domain_errors_cli_exit_three` | Assert the actual closed CLI schema diagnostic. Integrated inline `validate` has no `SchemaStore`, `store` or `base` arguments. Preserve CLI exit codes, RPC mappings, domain path refusals and unchanged ledger. |
| `tests/skills/test_extension.py`: `test_a27_hostile_packages_are_passive_data`; `tests/skills/test_replay.py`: `test_a02_reserved_actors_are_ordinary_tool_actors` | Integrated contexts have no authority field. Compare independently constructed complete CallContext values before/after instead; preserve actor identity, hostile-content guards, immutable content, event kind and no-side-effect witnesses. |

Every edited test/helper carries an `A-U09` comment. `tests/skills/test_package.py` is unchanged. Test inventory and assertion-count checks retain all original test methods without reducing any method's explicit assertion count; no skips or accepted-value alternatives were introduced. The integrated journal's narrower operation identifier syntax remains adapted by the existing private domain digest mapping. It returns an event rather than `Committed`; the existing domain adapter renders receipts from the original event prefix and enforces `expected_head` in locked preparation. These are API deviations, not alternative journal authorities.
