# U19 fail-first promotion oracle

The authority is `.unit/SPEC.md`, including Amendment B, the frozen K0
contract and the integrated APIs. Run from the repository root:

```sh
python3 -m unittest discover -s tests/promotion -t .
```

The callable surfaces are `lineage/domain/promotion.py` (`evaluate`, `promote`,
`apply`) and `lineage/ext/promotion.py` (`agent_promote`, `TOOLS`, `VALIDATORS`,
`FOLDS`). Every callable stub raises `NotImplementedError("U19 stub")`.
Behavioral cases convert that exception into an assertion failure containing
`U19 stub`. Imports, discovery, JSON decoding and descriptor checks can pass;
a passing descriptor does not prove promotion admission. There are no skipped
U19 cases. All fixture construction is in the listed test modules.

## Acceptance map

Test paths below are relative to `tests/promotion/`. Method prefixes denote
all independently named methods with that prefix in the named class.
`POLICY` means an executable pure-policy oracle against explicit fixtures;
`BOUNDARY` means real installed registry/dispatch/schema checks;
`BLOCKED/HOLD` means the named prerequisite/refusal assertion does not
establish the corresponding positive integrated acceptance.

| Case | Test names and files | Evidence boundary |
|---|---|---|
| A1 | `test_dispatch.py::DispatchTests.test_a1_*` | BOUNDARY: exact descriptor, every required field, injected fields, IDs, safe integers, strict JSON, reserved actors and caller authority. A valid creator request reaches the real stub; no substitute handler is installed. |
| A2 | `test_evaluate.py::EvaluateTests.test_a2_zero_minimum_reward_and_strict_credited_gain_admit` | POLICY: tied task, positive gain, zero minimum. Real status append and promoted seat remain BLOCKED/HOLD. |
| A3 | `test_evaluate.py::EvaluateTests.test_a3_*`; `test_contract_gaps.py::ContractGapTests.test_a25_seat_gate_preserves_missing_verdict_error_in_pure_policy` | POLICY: no_agent, nonexistent benchmark, declaration-only and results-only no_benchmark. Policy runs with filesystem reads forbidden. |
| A4 | `test_evaluate.py::EvaluateTests.test_a4_*` | POLICY: independent verdict, credited flag, negative task reward, equal minimum gain/dispersion, cost-only contrast and restored positive boundary in A2. |
| A5 | `test_evaluate.py::EvaluateTests.test_a5_*` | POLICY: missing/duplicate cells, detached close, wrong correctness/version, failed memory gate, forged statistics, LLR and discordant count. Real evidence I/O is covered as a bounded refusal in A22; admitted U16 provenance is BLOCKED/HOLD. |
| A6 | `test_evaluate.py::EvaluateTests.test_a6_*` | POLICY: singleton, complete allowed seat, effort/mode mismatch, baseline claiming rival credit, self-benchmark. |
| A7 | `test_evaluate.py::EvaluateTests.test_a7_post_declaration_benchmark_memory_drift_is_allowed`; `test_shadow.py::ShadowTests.test_a7_changed_constitution_requires_new_selection` | POLICY: declaration identity survives later lesson; contradictory constitution snapshot is rejected. Genuine constitution/skills evolution through the U17 owner is BLOCKED/HOLD. |
| A8 | `test_shadow.py::ShadowTests.test_a8_exact_frozen_clean_run_count_admits` | POLICY: exact original count and separate successful held-out confirmation. Durable progression remains BLOCKED/HOLD. |
| A9 | `test_shadow.py::ShadowTests.test_a9_*` | POLICY: pre-shadow, spanning shadow, open, late close, repaired, wrong agent/seat/version, failed memory, benchmark task/result and duplicate receipt exclusions, plus the exact positive completion. |
| A10 | `test_shadow.py::ShadowTests.test_a10_*` | POLICY: later declaration cannot lower original threshold; original exact count passes. No projection is read. |
| A11 | `test_shadow.py::ShadowTests.test_a11_*`; `test_evaluate.py::EvaluateTests.test_a13_confirm_cannot_admit_draft` | POLICY: absent/losing/inconclusive/uncredited/negative confirm; reused selection; pre-shadow confirm; confirm used for draft admission. |
| A12 | `test_evaluate.py::EvaluateTests.test_a12_*`; `test_shadow.py::ShadowTests.test_a12_*` | POLICY: held-out selection, contributing-selection overlap, same-pin disjointness, unrelated exploration, missing split/pin and unproven cross-bank independence. No hidden disk reads. |
| A13 | `test_shadow.py::ShadowTests.test_a13_*`; `test_dispatch.py::DispatchTests.test_a1_rejects_injected_status`, `test_a1_rejects_injected_from`, `test_a1_rejects_injected_to`; `test_a1_exact_discovery_descriptor` | POLICY/BOUNDARY: promoted/retired refusals, no set_status tool, no direct state injection. Real repeated transitions remain BLOCKED/HOLD. |
| A14 | `test_retirement.py::RetirementTests.test_a14_third_failure_retires_across_seats_and_arms` | POLICY: third error/HOLD/red retires, no invented status event, qualification seat cleared. Wire Agent exposure via missing agent owner is BLOCKED/HOLD. |
| A15 | `test_retirement.py::RetirementTests.test_a15_*` | POLICY: fewer failures, both success resets, other-agent/heartbeat/open/result isolation, absent rejected close, status not resetting streak and sticky explicit retirement. |
| A16 | `test_retirement.py::RetirementTests.test_a16_*` | POLICY: deterministic replay from empty state, closed per-agent entry, provenance/threshold, namespace ownership, input preservation and extension-order independence. |
| A17 | `test_transaction.py::TransactionTests.test_a17_replay_after_retirement_integration_prerequisites` | BLOCKED/HOLD: policy probe is followed by explicit real-owner/schema readiness assertions. No original committed promotion exists; replay acceptance is not claimed. |
| A18 | `test_transaction.py::TransactionTests.test_a18_fresh_stale_head_precedes_policy_when_owners_ready`, `test_a18_changed_tool_and_request_replay_integration_prerequisites`; `test_contract_gaps.py::ContractGapTests.test_a25_opid_gate_precedes_missing_agent_and_expected_head` | BLOCKED/HOLD for committed replay/bad_op; fresh stale-head assertion is executable when prerequisites exist. Public OpId gate is separately specified and never remapped. |
| A19 | `test_transaction.py::TransactionTests.test_a19_process_barrier_probe_and_retirement_race_prerequisites` | BLOCKED/HOLD: real spawned process reaches a deterministic policy barrier. This probe is not a locked journal race. Both durable retirement/promotion schedules are encoded behind the absent owner/schema prerequisites and have no acceptance receipt yet. |
| A20 | `test_transaction.py::TransactionTests.test_a20_direct_append_owner_validator_integration_prerequisites` | BLOCKED/HOLD: missing real agent.status owner and complete-seat schema; no permissive validator or relaxed schema is substituted. |
| A21 | `test_evaluate.py::EvaluateTests.test_a21_policy_result_is_defensive`; `test_retirement.py::RetirementTests.test_a21_mutating_fold_result_does_not_change_rebuild`; `test_transaction.py::TransactionTests.test_a21_commit_prefix_and_defensive_replay_integration_prerequisites` | POLICY defensive copies; real Commit/original-prefix replay BLOCKED/HOLD. Commit.sha256 means committed-prefix digest. |
| A22 | `test_transaction.py::TransactionTests.test_a22_held_existing_lock_yields_busy_without_append`, `test_a22_dependency_read_failure_sanitized_before_append`, `test_a22_append_fsync_rollback_integration_prerequisites` | BOUNDARY for busy/internal and unchanged bytes; admitted append/fsync rollback BLOCKED/HOLD. |
| A23 | `test_transaction.py::TransactionTests.test_a23_real_transport_parity_integration_prerequisites`; `test_dispatch.py::DispatchTests.test_a1_success_is_not_a_successful_noop` | BLOCKED/HOLD for admitted MCP/CLI/JSON/HTTP parity. Dispatch errors are execution failures with no untrusted success wrapper. |
| A24 | `test_evaluate.py::EvaluateTests.test_a24_*`; `test_shadow.py::ShadowTests.test_a24_missing_threshold_provenance`; all A5/A9 cell/run exclusions | POLICY: missing/null/Boolean/nonfinite statistics, missing witnesses, unknown costs, arms and duplicate receipts. Repeated-seed runtime witness shapes remain U16-owned and BLOCKED/HOLD. |
| A25 | `test_contract_gaps.py::ContractGapTests.test_a25_*` | BOUNDARY: frozen payload rejects seat, broad public OpIds remain valid; real promotion must return internal before append at missing owner/schema seams. No gap is promoted to PASS acceptance. |
| A26 | A2/A4/A8/A9/A12/A14/A20 test names above | Fail-first behavioral assertions target the central minimum-reward, credited-win, clean-count, held-out, shared-validator and retirement obligations. Actual implementation-source mutant executions, host review and cross-family receipts: AUSENTE. Stub redness is not a mutant receipt. Shared-validator mutant remains BLOCKED/HOLD. |
| A27 | `test_contract_gaps.py::ContractGapTests.test_a27_oracle_lists_every_numbered_acceptance`; required discovery command | BOUNDARY: package collection and complete acceptance map. Outside-surface hashes are checked by the task runner, not by an unrestricted in-test repository scan. |
| A28 | `test_evaluate.py::EvaluateTests.test_a28_*`; `test_transaction.py::TransactionTests.test_a28_synthetic_lifecycle_integration_prerequisites` | POLICY rejects telemetry-only and launch-only evidence. Real demo-offline lifecycle BLOCKED/HOLD; synthetic fixtures prove no real-seat fitness or inherited-memory benefit. |

## Explicit fixture and ambiguity resolutions

- `History` is the integrated tuple of detached event dicts. Pure fixtures are
  synthetic witnesses assumed to have passed the absent owners; they are not
  committed with test validators. Negative fixtures intentionally contradict
  one witness. Pure fixtures manufacture no authoritative bank files or external receipts.
  Gated real-owner scenarios create only a hash-pinned synthetic demo-offline
  fixture bank inside a temporary home; its manifest hashes the actual bytes.
- Amendment B permits an internal threshold map in `state["promotion"]`.
  Tests close only each agent entry and do not name or constrain the auxiliary
  map. The fold must not consult another namespace to recover declarations.
- Amendment B changes `promote` to keyword-only `seat=None`, resolving the
  declaration seat under the locked prepare callback. `evaluate` retains its
  explicit prefix and required keyword-only seat.
- Pure status payloads bind `_u19_fixture_seat` solely inside test fixtures.
  This is not an amended event schema and must never be appended. Positive
  public promoted-seat exposure is deferred until the frozen shape is
  reconciled. Tests do not demand that production recognize this fixture key
  as a general admission flag.
- Contributing selection means the shadow event's `selection_bench_id` and
  linked prior qualifications, not every exploratory benchmark. Missing
  source split or bank pin gives `internal`; a known forbidden split or
  overlapping pinned task gives `heldout_forbidden`; contradictory cells give
  `conflict`. Another bank hash cannot establish equivalence and gives
  `internal` / BLOCKED/HOLD.
- Verdict consistency includes declared SPRT decisions, llr and discordant
  count. Baseline population dispersion is over per-task baseline means,
  after seat/arm/seed aggregation. Fixtures use clear mathematical boundaries;
  no arbitrary epsilon may convert a strict credit inequality into admission.
  No implementation-specific float tolerance is frozen: positive statistics
  use ordinary deterministic math and hostile changes are far from rounding
  noise. Equality fixtures use exactly representable halves.
- Error order follows Amendment B: schema bad_args, incompatible public OpId
  internal, lock/replay busy/bad_op, stale_rev, pure-policy errors, then the
  unrepresentable-seat internal gate. Missing owner seams remain a distinct
  HOLD dependency. Caller operator/system strings grant no authority.
- Policy and fold tests prohibit filesystem/process work and compare inputs
  before/after. Pure rejection has no ledger; real-boundary refusals compare
  actual journal bytes/prefix or verify that no authority file was created.
- Fixtures retain the full model/effort/mode seat and none/own/inherited arms.
  Unknown costs are null. Versions hash constitution, sorted skill pins and
  memory_gen only. Status and seat do not enter that digest.
- The race probe uses spawn, explicit Events, Queue timeouts and bounded
  joins. Cleanup may terminate only the exact live process handle it started,
  after verifying its PID is greater than one. It creates no process group,
  sends no group signal, sleeps nowhere and contacts no network service.

## Integrated API deviations used by this oracle

| Integrated source | Actual API / adaptation |
|---|---|
| `lineage/core/registry.py` | ToolSpec(name, description, input_schema, handler, mutating), callable maps; no native Command, Snapshot, FoldSpec or Committed types. Use real load/Registry and mappings; the memory facade adds K0 aliases without removing native signatures. |
| `lineage/core/app.py` | create_context(home, registry=...), dispatch(name,args,context=...,registry=...) returns DispatchResult with payload/failure/exit_code. Handler context is keyword-only CallContext; dispatch does not inject actor/op_id itself. |
| `lineage/core/journal.py` | snapshot(home) returns History; transact(home,agent,op_id,kind,payload,validators,prepare=...) owns replay and supplies History/EventDraft. Journal does not accept the frozen Command/Render API. It fingerprints the initial payload and currently narrows OpId. |
| `lineage/core/schema.py` | validate(value,schema) and strict_loads; no SchemaStore/load_record/canonical API. Descriptor comes from the contract JSON; status closure is checked on its actual local payload subschema, without inventing a ref resolver. |
| `lineage/domain/arena/credit.py`, `lineage/domain/arena/sprt.py` | Integrated helpers are evaluate_credit (scalar, sample dispersion) and evaluate_sprt (observations). They are not U16's missing benchmark/paired-task witness authority; the oracle does not substitute their different credit contract. |
| `lineage/domain/memory/__init__.py` | Installs K0 compatibility types, wrapped journal/app functions and a new ToolSpec class. The test package imports this existing facade before binding extension descriptors, preserving class identity and retaining native CallContext/History APIs. |
| `lineage/core/cli.py`, `lineage/core/mcp.py`, `lineage/core/jsonlane.py`, `lineage/serve/http.py` | CLI/MCP/JSON expose injected stream/registry entry points; HTTP expects a K0 services context. The gated parity test exercises the actual HTTP handler with in-memory byte streams and headers, without opening a socket. No transport adapter is edited. |
| Agent/run/arena/breeding owners | Agent, run, arena benchmark/bank and explicit-retirement APIs/validators required by U19 are AUSENTE in this checkout. No imports, validators or wire shapes are fabricated for them. |

Public-contract schemas, owner code and other units' tests remain untouched.
The specification's capsule/CDP/AT-SPI, cross-family, real-seat, live bridge and
inherited-memory-benefit receipts are AUSENTE. All assertions and evidence
claims here are scoped to the supplied campaign corpus and frozen K0 seed.

## Fail-first verification receipt

Required discovery collected 148 tests: 113 assertion failures and 35 passes,
with zero errors and zero skipped cases [MEASURED]. Every failure ends in an
`AssertionError` containing `U19 stub`; no import or fixture-construction
failure is counted as behavioral redness. The slowest measured case took
0.101 seconds [MEASURED], below the per-case 5-second ceiling [TARGET].
The exact runner summary is:

```text
FAILED (failures=113)
```

The passing cases check discovery, frozen schema/public-input behavior and
oracle inventory. They do not establish promotion acceptance. The real
owner/schema gates remain BLOCKED/HOLD. Actual implementation mutants and
cross-family review receipts remain AUSENTE.

The existing-suite comparison collected 1517 tests in each arm [MEASURED].
With the new exports present it reported 14 failures, zero errors and 25
skipped cases [MEASURED]; every failing test identifier was already present
in the comparison arm. No new failure identifier was introduced [MEASURED].
These existing failures are not represented as a green regression suite.


## Amendments A-U19

- `test_contract_gaps.py::test_a25_missing_owner_seams_are_explicit_internal_and_no_append`:
  detach the integrated `CallContext` with `dataclasses.replace` and remove
  `agent.status` from its validator map. Installed owners are now present, so
  this negative fixture must explicitly supply the missing seam. The exact
  `internal`, unchanged-history and no-append assertions remain intact.
- `test_contract_gaps.py::test_a25_opid_gate_precedes_missing_agent_and_expected_head`:
  A-JL1 makes `x` a journal-valid unchanged OpId. Keep that exact input and
  assert the locked `stale_rev` diagnostic for its fresh stale request rather
  than the obsolete narrow-OpId `internal` gate. No additional accepted error
  value is introduced; no operation-id remapping is permitted.
- `test_dispatch.py::test_a1_creator_actor_does_not_need_to_equal_child`:
  installed owner validators admit the request to policy; the empty home now
  produces exactly `no_agent`. This preserves the creator/child distinction
  and a single exact domain error assertion.
- The frozen complete-seat schema prerequisite in
  `test_transaction.py::require_owners` remains unchanged. Positive append,
  replay, durability and transport acceptance remain BLOCKED/HOLD until the
  upstream status schema can record the required complete seat.

- A-K0-10 reconciles `schemas/event.schema.json`: the gap test now checks
  that the current closed payload accepts the complete seat and rejects an
  extra seat authority key. Its legacy no-seat schema contrast still rejects
  the original added-seat fixture. `require_owners` retains its seat assertion.
- The two empty-home refusal fixtures inspect absence of ledger bytes rather
  than absence of the ledger inode: native journal locking creates an empty
  file before preparation. Exact domain errors and unchanged-history checks
  remain intact.
- `test_transaction.py::mutation` seeds declarations/runs/verdicts through
  installed arena descriptor handlers, which use the integrated schema store;
  the native dispatch structural validator cannot resolve the declaration
  `$ref`. Promotion, replay, refusal and transport assertions retain real
  shared dispatch. No arena validator is replaced or bypassed.
- `test_review_h1.py` adds real-owner selection/seat and unchanged broad OpId
  coverage, sanitized runtime/evidence failures, and invalid-close retirement
  exclusions. The new amended-schema lifecycle uses synthetic evidence only.

- `test_transaction.py::mutation` explicitly supplies `Context(Services(...))`
  with its temporary home as `repo_root`: the actual arena bank loader reads
  the service repository root, not the native journal home. All source pins
  are still checked by the real arena owner. `seed_selection` documents the
  fixture binding; no public bank or owner source is edited.
- `test_transaction.py::ledger_bytes` compares committed byte strings across
  native empty-ledger materialization. This retains byte-for-byte no-append
  assertions instead of treating an empty journal inode as committed data.

- `test_transaction.py::setUp` supplies a deterministic virtual clock through
  the integrated arena fixture `Services`; its fake runner requires an
  injected clock. Journal timestamps and process/race assertions retain their
  original behavior. `Services.token_count` remains `None`.

- Integrated U16 opens later benchmark cells at their current memory version.
  U19 reconciles those versions against committed memory writes belonging to
  that same benchmark; its qualification identity remains the exact original
  declaration snapshot. Unrelated writes and unmatched versions cannot bridge
  the difference. No version assertion in the frozen tests is removed.

- `test_transaction.py::test_a20_direct_append_owner_validator_integration_prerequisites`
  binds `ctx` to the real registered U12 validator with `functools.partial`.
  The installed journal calls validators with history/event only; every
  original bypass rejection and the positive live-validator control remain.
- `test_transaction.py::test_a23_real_transport_parity_integration_prerequisites`
  supplies private recipient-directory/config permissions required by the
  native family mailbox. No transport output, status, result or ledger-effect
  assertion is changed.

- Strict duplicate-key, invalid UTF-8/surrogate, byte-cap and status-schema
  negative tests resolve `schema.SchemaError` through the integrated module
  rather than a stale imported class: the full suite reloads that boundary.
  The same malformed inputs must raise the current exact schema exception;
  no exception class set or accepted response is widened.

- A-K0-10 supersedes the earlier missing-complete-seat gate in this amendment
  log. The schema prerequisite now passes. Real admitted promotion still
  encounters an upstream projection mismatch: the memory owner's historical
  agent reconstruction omits `promoted_seat`, while its rebuild compares the
  full agent record. Positive committed lifecycle acceptance remains HOLD
  until that owner seam is reconciled; no projection failure is suppressed.
- In isolated in-memory source copies, removing close-actor binding and
  removing parent-context binding each caused its new negative retirement
  oracle to fail with an assertion and no execution error [MEASURED]. These
  receipts cover the new checks only; the original full mutant matrix,
  cross-family review and host acceptance receipts remain AUSENTE.

### Repair h2: Amendments A-U19

- Added `test_review_h2.py` without changing any frozen test or assertion.
  The regression uses the installed U12/U11 readers and real transaction
  helpers to require complete-seat Agent and memory projection refresh,
  original-prefix replay, unchanged ledger bytes and detached reader state.
  Its pure reader contrast requires sticky automatic retirement and omission
  of `promoted_seat`, while preserving the input state.
- The integrated U12 reader consumes only its agent namespace; U11's
  historical memory reconstruction folds memory alone and previously lost
  the amended status seat. U19 supplies thin reader adapters for those
  actual APIs; its `apply` callback still changes only the promotion namespace.
  Projection publication continues through `agents.refresh_projections`
  and `lineage.domain.layout`, after the journal commit.
- Fail-first: the new regression module collected two assertion failures
  against the pre-repair implementation, with no import errors [MEASURED].
  No frozen-input hash row changed in this repair.

- `test_transaction.py::test_a23_real_transport_parity_integration_prerequisites`:
  adapt only the HTTP fixture plumbing to the installed provider's
  `http.Context`, `services.call_context` and parser `raw_requestline`.
  Exact success/error status, inner-result equality and ledger-byte equality
  assertions remain unchanged, as do the prefix-digest assertions in A21.
- The installed family mailbox expects a last-event digest while U19's
  frozen Commit oracle requires a full-prefix digest. A thin U19 witness
  adapter verifies that exact prefix hash, translates a defensive copy for
  the native ownership/OpId check and leaves public/retained results intact.
  No transport source, frozen wire shape or accepted evidence is weakened.

- The added reader regression also preserves a captured birth status, so
  owner fixtures and immutable records are never reset to `draft` by a
  qualification default. Public promotion domain refusals omit optional
  detail consistently with the JSON carrier while retaining exact error codes.

- The family witness regression accepts the original prefix before and after
  later retirement, rejects corrupted hashes, event-digest substitution,
  altered heads/event IDs and actor mismatches, and checks detached results.

### Repair h2 verification

- Required promotion discovery: 159 tests, OK, no failures, errors or skips
  [MEASURED]. The new regression module contributes four tests [MEASURED].
- Contract conformance: all 38 registered descriptors match their Arguments
  blocks; exit status 0 [MEASURED].
- Agent-query, clone and initial reader-regression checks: 35 tests, OK
  [MEASURED].
- The frozen transaction assertion ASTs are byte-equivalent after adapting
  only HTTP fixture plumbing; all other pre-existing Python oracle modules
  retain their pre-repair hashes [MEASURED].
- Family witness contrast independently accepted a valid original prefix
  and replay after retirement, and refused changed prefix hashes, event hash
  substitution, head, event IDs and actor identity [MEASURED].
- These receipts establish synthetic lifecycle mechanics, not real-seat
  fitness, inherited-memory benefit or independent cross-family approval.

- Isolated in-memory retirement mutant: disabling recognized failure
  outcomes makes the arena eight-win case pass, while
  `test_a14_third_failure_retires_across_seats_and_arms` fails by assertion
  [MEASURED]. This diagnostic changes no source or acceptance assertion and
  does not count as a passing suite. It demonstrates that allowing further
  arena runs after effective retirement would weaken the required policy.

- Required full suite with `REGRESSION=0`: 3142 tests in 803.970 seconds;
  no assertion failures, nine errors, 24 existing skips; exit status 1
  [MEASURED]. Every error is in `tests/arena/test_verdict.py` and reaches
  `lineage/domain/runs.py::_open_eligible` with `conflict` because the agent
  is retired. Overall integration remains BLOCKED/HOLD. Reconciliation of
  those arena scenarios belongs to their owner; neither their tests nor the
  mandatory third-failure retirement rule was weakened.
