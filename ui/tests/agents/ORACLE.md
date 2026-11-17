# U22 fail-first oracle

Authority: `.unit/SPEC.md`, including Amendment B; `docs/CONTRACT.md`; `docs/OPERABILITY.md`; `schemas/agent.schema.json`; `schemas/event.schema.json`. `docs/CONTRACT.md` supplies the discovery argument schemas directly, rather than a second invented schema registry. The public U22 import is `screen` from `ui/src/screens/agents/index.ts`; internal U22 helper exports are deliberately unspecified and unused.

All transport data and ledger examples are deterministic synthetic fixtures. In-memory birth events are fault-injection inputs for UI assertions, not backend persistence evidence, live creation receipts, benchmark results or memory-benefit claims. The existing U21 shell and transport are used directly in the integration tests. The smaller screen harness implements the documented `ScreenContext` seam and supplies a native acting-agent selector without editing the shared shell.

## Verification gates and rejecting contrasts

| Step | Gate | Rejecting contrast |
|---|---|---|
| Load the public entry | Integrated TypeScript source and tests typecheck; existing registry resolves `screen`. | A missing import, configuration error or replacement registry is infrastructure failure, not a valid fail-first result. |
| Observe the unimplemented domain screen | Run the new suite against the existing Agents placeholder; assertions require public reads, cards, fields and states. | A test-only unconditional throw, expected stub exception, private implementation import or negative assertion that succeeds without exercising the screen cannot establish missing behavior. |
| Preserve the dependency | Run the existing U21 suite unchanged and compare existing-file digests. | A modified shell, schema, config, backend, dependency or existing oracle invalidates this unit's receipt. |
| Complete external acceptance | Obtain independent C/A/P/V and persona evidence from the real integration. | jsdom geometry, an empty native document, a synthetic creation or a locally transformed DOM cannot pass the corresponding external gate. |

## Acceptance-to-test map

Titles below are literal test names. Parameter placeholders denote all deterministic members of the adjacent `it.each` table. This map covers the numbered acceptance list through A32 [CITED: `.unit/SPEC.md`]. It does not turn an external requirement into a passing unit assertion.

| Case | Test file and literal test names | Coverage and remaining gate |
|---|---|---|
| A1 | `screen.test.ts`: `A1 public registry mounts, reads, updates and disposes without a substitute screen` | Public seam, CSS import, registry, update/dispose; typecheck and file-scope verification run separately. |
| A2 | `screen.test.ts`: `A2 real U21 shell retains landmarks, navigation and the persistent status node`; `operability.test.ts`: `A2 A27 rendered agents retain native registered unique controls and heading-labelled cards`, `A2 A27 rejecting structural contrast: %s` | Real shell plus structural positives and hostile contrasts; browser/native corroboration remains external. |
| A3 | `screen.test.ts`: `A3 duplicate names and long identities retain unique full-ID actions after sort and reload`; `operability.test.ts`: `A3 initial identityKey collision rejects readiness and disables affected actions`, `A3 Amendment B collision discovered after paging disables affected controls without pretending to unresolve ready`, `A3 A27 names fit the normalized byte ceiling while full long IDs remain descriptions` | Identity, names, byte budgets, descriptions and initial/post-ready collision handling. |
| A4 | `screen.test.ts`: `A4 readiness waits for the list and an equal acknowledged AppState.head`, `A4 a persistent head mismatch has one reconciliation restart and a recoverable failure`, `A4 unknown fold head is never treated as a confirmed zero revision`, `A4 A28 invalid list head %s cannot establish readiness`, `A4 Amendment B initial failure rejects ready; public Retry Agents must restore real-shell readiness` | Unknown head, initial failure, bounded reconciliation and the actual shell retry dependency. |
| A5 | `filters.test.ts`: `A5 workflow %s uses only the public server filter and resets its cursor`, `A5 A6 status %s remains effective with retirement unchecked`, `A5 query matches NFC names and full IDs with fixed lowercase semantics`, `A5 language is an open Unicode string retained even when no page contains it`, `A5 A9 %s order uses full-ID tie breaks without host collation`, `A5 invalid sort resets only sort and warns while valid q and workflow survive`, `A5 Amendment B invalid compare %s resets the whole field without losing q`, `A5 invalid %s resets its own field and leaves valid query untouched`, `A5 unknown and prototype-sensitive query keys cannot alter objects or become tool arguments` | Every declared workflow/status, open language, sort, query and malformed compound state. |
| A6 | `filters.test.ts`: `A6 retirement defaults exclude retired agents and explicit include-retired opts in`, `A6 clear resets filters and sort but retains canonical comparison IDs until separate clear`, `A6 URL filter edits contain no cursor, operation identity, token or saved draft`; also the A5/A6 status table | Retirement override and independent clearing. |
| A7 | `screen.test.ts`: `A7 %s empty catalogue has its own honest state`, `A7 partial catalogue declares coverage and retains pagination even with no local match`, `A7 default catalogue page uses one hundred records and exposes coverage honestly` | Empty versus no match, default page size and partial coverage. |
| A8 | `screen.test.ts`: `A8 exclusive paging deduplicates equal overlaps and retries the failed cursor without losing focus`, `A8 %s is invalid_response and preserves the committed page`; `filters.test.ts`: `A8 server filter changes abandon the previous page cursor` | Overlap, conflicting records, cursor progress, retry identity and filter isolation. |
| A9 | `screen.test.ts`: `A9 identity focus survives reordering and removal goes to heading with one announcement`, `A9 local typing preserves search value and caret across reads and scorecard updates`; also the A5/A9 sort table and A8 focus test | Identity-based focus, removal, typing/caret and stable ties. |
| A10 | `screen.test.ts`: `A10 cards distinguish current identity and all seat/arm groups, zero and unknown means`, `A10 A25 failed scorecards are isolated under one Retry Scorecard and do not advance catalogue head`; `operability.test.ts`: `A10 A28 malformed scorecard %s is isolated from the usable catalogue` | Nullable means, real zero, tuple/arm distinctions, counts, malformed reads and isolated errors. |
| A11 | `comparison.test.ts`: `A11 exactly two full identities enable comparison; excess selection is blocked with text`, `A11 selected full identities survive sorting, filtering and reload with duplicate display names`, `A11 measured comparison uses a labelled native table and separate seat/arm rows with missing values intact`, `A11 an unmeasured selected agent remains visible instead of being omitted or replaced by zero`, `A11 Amendment B no_agent remains explicit without substituting a visible agent`, `A11 Amendment B transient comparison agent_get failure has a registered isolated retry`, `A11 clearing comparison changes only the route selection and never domain state`; `filters.test.ts`: `A11 history restores hidden comparison identities independently of visible rows` | Selection, unresolved identities, comparison semantics and transient recovery. |
| A12 | `create.test.ts`: `A12 A13 ordinary Create opens a named native modal and verifies both fixed reference pins`, `A12 invalid submission focuses the first invalid field and keeps entered text`; `comparison.test.ts`: `A12 comparison traps Tab in the helper modal, Escape closes and focus returns to the trigger`; `operability.test.ts`: `A12 Create contains Tab and Shift+Tab and restores invoker with Escape and Cancel`, `A12 Create makes its background inert and all exposed names stay unique` | Helper-modal behavior is unit evidence; native dialog and background keyboard behavior require real Chrome. |
| A13 | `create.test.ts`: `A13 A28 %s reference preflight blocks mutation and preserves a retryable draft`, `A13 missing reference exposes hash_mismatch and keeps fields during Retry References`, `A13 A14 no model, effort, seat or overlay is guessed for a blank form`; `recovery.test.ts`: `A26 stale reference preflight cannot render into a reopened dialog` | Matching pins, required discovery, hostile responses, retry and preflight races. |
| A14 | `create.test.ts`: `A14 explicit nonretired skill selection serializes a full package pin`, `A14 optional skill failure permits explicit empty skills with an explanation and isolated retry`, `A14 recovered unresolved skill pins block submission when skill discovery fails`, `A14 full seat tuples are unique; effort and mode remain separate, removal restores Add seats focus`, `A14 incomplete seat %s / %s / %s is never admitted`, `A14 seat collection rejects a seventeenth member without changing admitted tuples`, `A14 A28 malformed skill catalogue %j is isolated and never pins unvalidated content`; also A20 oversized collection drafts | Closed selected members, discovery, empty skills, tuple uniqueness and collection limits. |
| A15 | `create.test.ts`: `A15 valid Unicode character boundaries serialize exact closed arguments and no browser-only keys`, `A15 invalid or reserved new ID %s cannot dispatch or be silently trimmed`, `A15 invalid %s length or enum blocks dispatch`, `A15 field labels, workflows and modes follow the exhaustive public registry`, `A15 A28 actual HTTP creation uses exactly tool/args and shared session handling without forbidden headers`; `operability.test.ts`: `A15 Enter in Find agents cannot dispatch creation` | Exact payload, Unicode character bounds, passive edits and native form controls. |
| A16 | `create.test.ts`: `A16 %s actor blocks Confirm and supplies no default actor`, `A16 missing agent_create capability gives a textual reason and no protected dispatch`, `A16 unknown acknowledged head cannot become expected_head zero`, `A16 actor changes are explicit and operator selection never invokes a privileged writer`, `A16 missing HTTP session never sends a mutation POST and preserves the valid draft` | Synthetic actor seam and actual shared session refusal; real actor-capable integration remains blocked by U21. |
| A17 | `create.test.ts`: `A17 pending Confirm cannot submit twice and a draft is durable before the call`; `recovery.test.ts`: `A17 A19 A30 response loss after commit replays the identical actor, args and op_id once` | Pending duplicate protection, persistence-before-send and byte-identical replay. |
| A18 | `recovery.test.ts`: `A18 edited fields get a fresh identity while the frozen unresolved attempt stays retryable`, `A18 actor change cannot rewrite a frozen attempt or dispatch edited fields before reconciliation`, `A18 abandon waits for a fresh complete negative birth scan and never mutates`, `A18 abandon cannot erase an attempt when its fresh witness scan fails`, `A18 stale_rev clears unresolved and requires explicit refresh and re-confirmation of the new head` | Amendment B state transitions, explicit recovery and unresolved-attempt controls. Registry gap remains explicit below. |
| A19 | `recovery.test.ts`: `A19 reload offers the saved uncertain draft but never submits until explicit retry`, `A19 reload converts pending into uncertain and preserves the exact operation snapshot`, `A19 A26 %s after send keeps recovery identity and never asserts rollback`; also A17/A19/A30 replay | Cancel, Escape, departure, reload and exact snapshots. |
| A20 | `recovery.test.ts`: `A20 persisted creation draft is a closed allowlist without token, response or authoritative projection`, `A20 hostile stored %s cannot admit a mutation or poison objects`, `A20 storage %s refusal is visible but in-session creation remains usable`, `A20 incomplete editable draft text is recoverable without being a valid tool snapshot` | Version, closed keys, prototypes, invalid snapshots, byte/collection limits and storage failures. |
| A21 | `create.test.ts`: `A21 matching read and birth witness are required before closing, clearing and refreshing`; `recovery.test.ts`: `A21 witness beyond the default first page is reached from zero or the original committed prefix` | Delayed witness, public record agreement, paging, original commit prefix and deduplicated announcement. |
| A22 | `recovery.test.ts`: `A22 Amendment B agent_get mismatch in %s leaves completion unverified`, `A22 Amendment B event payload mismatch in %s cannot certify creation`, `A22 %s leaves the sent attempt recoverable without claiming noncommit`, `A22 malformed commit %j cannot be treated as completion`, `A22 launch-style accepted receipt is not an agent_create result`; `create.test.ts`: `A22 outer ok=false and launch acknowledgements never become a creation success`; `comparison.test.ts`: `A22 A25 scorecard failure in comparison retains both identities and one modal Retry Scorecard` | Full record and operation identity, malformed records, missing witness, acknowledgements and honest uncertainty. |
| A23 | `recovery.test.ts`: `A23 replay uses the original old commit prefix rather than the current expected head`, `A23 repeated cursor resync stops observation, retains filters and never retries the mutation` | Original replay prefix, bounded resync, retained filters and no mutation replay loop. |
| A24 | `create.test.ts`: `A24 authoritative %s is refused, escaped and clears only the unresolved attempt`, `A24 lost observation %s leaves one uncertain frozen attempt`, `A24 session_required blocks completion, preserves the draft and exposes its exact code`, `A24 HTTP 200 outer refusal is decoded by real U21 transport and remains a domain refusal` | Full documented creation refusal matrix, transport uncertainty, exact detail and real outer-wrapper decoding. |
| A25 | `screen.test.ts`: `A25 later catalogue failure retains rows, comparison and its last acknowledged revision`; `operability.test.ts`: `A11 A25 comparison close and repeated reads do not repeat recorded announcements`, `A25 retry of references does not restart skills, erase fields or submit`; also A10/A25 and A22/A25 | Stale data, status-node identity, retries, isolation and one exposed scorecard retry per active scope. |
| A26 | `screen.test.ts`: `A26 a superseded server-filter response cannot replace the current snapshot`, `A26 disposal aborts owned reads, unsubscribes and ignores later resolution`; `comparison.test.ts`: `A26 closed comparison ignores a late agent_get response and does not reopen`; `recovery.test.ts`: `A26 stale reference preflight cannot render into a reopened dialog`, `A26 late mutation observation after disposal cannot clear recovery or announce into another route` | List, comparison, preflight, observation and teardown races; retained sent identity. |
| A27 | `create.test.ts`: `A27 fixture form remains read-only with no cryptographic randomness or clock sampling`; `operability.test.ts`: `A27 fixtures retain filtering, sorting, navigation and comparison while visibly synthetic` | Deterministic read-only transport seam, forced mutation refusal and provenance. This is not a live dispatcher receipt. |
| A28 | `screen.test.ts`: `A28 Amendment B rejects %s before links or follow-up reads`, `A28 invalid server cursor %s is rejected before paging or follow-up reads`; `comparison.test.ts`: `A28 comparison rejects hostile agent_get record %j before enabling unsafe actions`; `operability.test.ts`: `A28 hostile display names, reference rules and errors stay passive text`, `A28 authored screen imports stay relative and shared transport is the only public tool boundary`; also A13/A28, A14/A28 and A10/A28 response tables | Closed read records, traversal/scheme IDs, passive text, no direct HTTP/token handling and relocation. Existing-file digest comparison is separate. |
| A29 | `operability.test.ts`: `A29 static style precondition: entry imports owned CSS, with no remote asset or motion-dependent readiness` | CSS entry precondition only. Real viewport/zoom/theme/motion geometry and computed contrast receipts: AUSENTE — no inventar. |
| A30 | `recovery.test.ts`: `A17 A19 A30 response loss after commit replays the identical actor, args and op_id once`; `screen.test.ts`: `A9 identity focus survives reordering and removal goes to heading with one announcement` | These are the replay/focus mutation-sensitivity targets. Placeholder-red run is recorded separately. Green implementation and removal-mutant runs: AUSENTE — no inventar. |
| A31 | `operability.test.ts`: `A31 local prune contrast removes an article-contained action and loses the required inventory`; also A2/A27 structural contrasts and A12 keyboard tests | Local rejecting contrast only. Independent CDP pipe, native AT-SPI document/action inventory, raw/transformed native observations and real-backend witnesses: AUSENTE — no inventar. |
| A32 | `create.test.ts`: `A21 matching read and birth witness are required before closing, clearing and refreshing`; `recovery.test.ts`: `A19 reload offers the saved uncertain draft but never submits until explicit retry`; `comparison.test.ts`: `A11 measured comparison uses a labelled native table and separate seat/arm rows with missing values intact` | Component prerequisites only. Public-doc-only junior/Big Tech capsules, fresh frames, frame SHA-256, `vis.receipt/v1` pass/fail/refused records and scored persona reports: AUSENTE — no inventar. |

## Amendment B decisions and dependency gaps

- **Preserved placeholder.** `ui/src/screens/agents/index.ts` already exports a functional U21 placeholder. The assignment requires retaining existing stub behavior. It is unchanged; no internal module or alternate public entry was invented. The suite reports meaningful assertion failures for absent U22 behavior, as M26/A30 require. A literal `throw new Error("U22 stub")` failure cannot be obtained from this existing entry without changing its behavior. No assertion was weakened to expect a stub exception.
- **Unresolved attempts.** Separate retry/verify and abandon controls are discovered by their observed native button name and must carry an existing registered K0 action. Amendment B supplies no literal action/name additions, while U22 cannot edit the shared registry. Exact new registry entries: AUSENTE — no inventar. The oracle does not silently invent selectors to conceal that integration gap. A fresh complete `ledger_events` scan is required before abandonment; scan failure retains `unresolved`.
- **State transitions.** Reloaded `pending` becomes `uncertain`; authoritative domain refusal becomes `refused` and clears `unresolved`; observation failure retains the frozen attempt; edits after submission mint a different operation identity. The unedited `stale_rev` case accepts either a retained or fresh valid `op_id`, because Amendment B explicitly leaves that decision open. It requires explicit refresh/re-confirmation and a newly captured head, and forbids automatic resubmission.
- **Witness cursor.** The permitted starts are `after:0` or `Math.max(0,commit.head-commit.event_ids.length)` [CITED: Amendment B]. The optimized start may legitimately avoid earlier default-size pages. Tests require filters and original-prefix coverage, not a particular number of otherwise unnecessary reads. No undocumented page-cap value is frozen.
- **Seats and keys.** Agents use `identityKey('agent',fullId)` and skills use `identityKey('skill',skill_id+'@'+sha256)`. Seat identity includes model/effort/mode; tuple string encoding and private helper names are not specified, so tests require stable distinct keyed controls without choosing an implementation-private encoding. No seat-catalogue tool or mandatory `select-seat` control is invented.
- **Readiness.** `AppState.head` is the actual shared property. `identityKey`/`formatMeasurement` live in `ui/src/ui/primitives.ts`; focus helpers live in `ui/src/ui/keyboard.ts`; `openDialog` lives in `ui/src/ui/dialog.ts`. Initial collisions reject `ready`; later collisions disable actions and expose the warning. The real-shell initial-failure retry test exposes the dependency on U21's settled `initialReady` promise; the oracle does not patch U21 or publish readiness itself.
- **Expected head and session.** Capture a head only when the list and acknowledged store agree, so either agreed source yields the same value. The public seam has no session-capability getter; the real U21 HTTP transport is tested with a missing token to prove that no mutation POST occurs. No token or invented transport property enters a draft.
- **Comparison recovery.** An explicit `no_agent` error may be shown in the modal or may block opening. Either is accepted without replacement. Transient reads require a registered isolated retry; malformed comparison query arrays are rejected as a whole.
- **External evidence.** The actual U21 shell acting-agent selector is a disabled placeholder. An actor-capable live integration, approved browser build, real dispatcher seed, independent C/A/P/V observers, persona runtime homes and public-doc-only capsules are external preconditions. None is supplied by these synthetic tests. No external case is skipped and relabelled as a jsdom pass.

## Commands

From the repository root:

```sh
cd ui && ../node_modules/.bin/vitest run tests/agents
cd ui && ../node_modules/.bin/tsc --noEmit
cd ui && ../node_modules/.bin/vitest run tests/shell
```

The tests use fake clocks and bounded microtask turns, no real sleeps, network calls, installations, subprocesses or process signals. Each test has a timeout of 4000 ms [TARGET], below the requested bound of 5000 ms [CITED: assignment]. Only the permitted test directory is authored; the source placeholder, other production files, frozen shared tests and configuration remain unchanged.

## Recorded verification

New oracle: RED, 255 failed and 0 passed [MEASURED]. The required command exited 1 [MEASURED], collected every test, reported only `AssertionError` failures for missing public reads/cards/controls/states, and had no collection error or unhandled error. Exact summary:

```text
 Test Files  6 failed (6)
      Tests  255 failed (255)
```

Existing U21 suite run separately: GREEN, exit 0 [MEASURED], with no unhandled error. Exact summary:

```text
 Test Files  13 passed (13)
      Tests  260 passed (260)
```

Integrated `tsc --noEmit`: PASS, exit 0 [MEASURED], no diagnostics.

The combined suite preserves all 260 existing assertion passes [MEASURED], but it also reports an unhandled rejection attributed to `ui/tests/shell/fixtures.test.ts`, `A22 fixed fixture produces repeatable state and semantic DOM without clock or randomness`: `No wall-clock fixture state`. Its stack enters jsdom's queued selection-event creation while that existing test makes `Date.now` throw. The new harness drains its queued DOM callbacks at teardown without an elapsed-time sleep; the combined rejection still reproduces. The shared test, runtime and configuration are outside this assignment's write surface and remain unchanged. A clean combined-run verdict is therefore INCONCLUSIVE; this additional error is not accepted as oracle red evidence. Exact combined summary:

```text
 Test Files  6 failed | 13 passed (19)
      Tests  255 failed | 260 passed (515)
     Errors  1 error
```

Existing-file digest comparison found no changed existing file [MEASURED]; the created set is confined to `ui/tests/agents/`. There are no skipped/todo/focused test cases [MEASURED]. The literal nonthrowing-placeholder conflict and the external acceptance gaps above remain explicit; no `U22 stub` exception or native/persona receipt is fabricated.


## Amendments A-U22

- `ui/tests/agents/recovery.test.ts`, A20: canonicalize the expected
  `seat_draft` key-list fixture with `.sort()`, matching the existing sorting of
  the actual keys and the adjacent envelope/fields fixtures. Integrated Seat
  records have exactly `model`, `effort`, and `mode`; JSON member order carries
  no authority. The exact closed allowlist and all behavioural assertions are
  retained. No case is removed, skipped, or broadened to additional keys.
- No application API substitution was necessary. The existing U21 imports and
  call signatures remain unchanged.

### Unresolved verification conflicts

- `ui/tests/agents/create.test.ts`, A27: jsdom constructs native pointer, focus,
  and input events using `Date.now()`. The test spies on that same global method
  while clicking, focusing, and entering fields. Diagnostic stacks identify
  jsdom's `EventImpl` constructor; the owned application sources contain no
  wall-clock reads. The original zero-call assertion remains unchanged. No
  platform-call exemption, clock-spy filtering, DOM-event replacement, or
  production test detection is introduced.
- The read-only U21 shell suite still requires `Agents: not built yet.`, rejects
  authorized U22 files through its U21-only file allowlist, and expects screen
  readiness with `agent_list` replies that are not valid closed K0 records.
  Changing those assertions/helpers is outside the authorized reconciliation
  surface. U22 continues to reject malformed responses and does not publish
  fabricated readiness.
