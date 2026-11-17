# U25 frozen fail-first oracle

## Scope and honest status

The authority is `.unit/SPEC.md`, including Amendment B, with the public K0 types,
`docs/CONTRACT.md`, `docs/OPERABILITY.md` and the bundled `schemas/`.
The manifest pins the specification bytes used to author this suite; public test
execution does not require the private `.unit/` directory.

Only files beneath `ui/tests/arena/` are delivered. The existing
`ui/src/screens/arena/index.ts` exports `screen` with the required U21 interface
and is retained unchanged. No implementation-only exports, replacement shell,
new dispatcher, stylesheet stub or fabricated throwing module is introduced.

The requested literal `U25 stub` failure conflicts with preserving this existing
placeholder and the existing shell tests. A27 explicitly requires missing-feature
assertions against that placeholder. These tests therefore fail on rendered
behavior, lifecycle promises or missing public dispatch, never an artificial
stub exception, unresolved import or missing configuration. Passing negative-only
checks and fixture-validation checks do not certify an implemented Arena.

## Execution and isolation

From the repository root:

```sh
cd ui && ../node_modules/.bin/vitest run tests/arena
```

TypeScript gate:

```sh
cd ui && ../node_modules/.bin/tsc --noEmit
```

Existing shell regression gate:

```sh
cd ui && ../node_modules/.bin/vitest run tests/shell
```

The existing vitest/jsdom configuration is used unchanged. Every test has a
1,500 ms ceiling [TARGET], below the assigned 5 s bound [TARGET]. The presentation
clock and synthetic identifiers are fixed [TARGET]. Deferred promises and bounded
microtask turns drive races; no real sleeps, network, model calls, child processes,
process groups or signals occur in these tests. The fake-clock setup is in the
owned helper. Fixtures and tool replies remain in this directory; shared fixtures
and dependencies remain read-only.

`Script` validates every dispatched argument against the discovery schema copied
verbatim from the public contract and checks the read/mutation classification.
The data sanity tests independently check scripted result shapes. Cursor and event
scripts establish UI workflow assertions; they do not certify backend hash-chain,
memory-write, statistical, promotion or real-agent fitness behavior. Fixture hashes
are schema-shaped synthetic values, not runtime receipts.

The enabled actor in the direct screen harness is a synthetic contract seam. The
actual U21 disabled `select-actor` remains a live integration blocker; a screen
oracle does not claim that the live shell can currently mutate.

## Amendment B decisions frozen here

| Binding issue | Oracle decision and rejecting contrast |
|---|---|
| Omitted `rule` and launch display gate | Omission means collapsed, equivalent to `rule=0` [TARGET local convention]. An explicit expansion is required once for the exact immutable declaration. A collapsed summary after that expansion retains the launch prerequisite. New identity or changed declaration bytes invalidates it. |
| Recovery controls | Opening the existing `declare-benchmark`, `launch-benchmark` or `promote-candidate` explicitly recovers that scoped draft for inspection. Only `submit-dialog` / `Confirm {form label}` retries. `cancel-dialog` / `Cancel {form label}` declines the attempted recovery/submission and preserves the draft, as K0 requires. `evaluate-benchmark` explicitly retries a recovered verdict operation. No unregistered recovery action is allowed. |
| Persistent discard gap | The exhaustive K0 registry has no action for deleting an entire stored pending operation. Cancel is not redefined as destructive deletion. A separately named destructive discard control is **AUSENTE — no inventar**; an amendment is needed to require one. Editing registered fields starts a new operation without silently replaying the uncertain prior request. |
| Stored operations | Permit only safe versioned drafts and minimal `{tool, actor, op_id, expected_head, args}` pending tuples plus route/benchmark scoping metadata. Recovery is explicit. Reject forbidden keys, reserved actors, malformed arguments, altered benchmark scope and extra arguments. No token, memory body, response or authoritative projection is persisted. |
| Launch disable predicate | Disable unless live, explicit usable nonreserved AgentId, matching tool descriptor, confirmed head, no affected identity collision, successfully displayed immutable rule and supported fake-runner form. Pending submissions block duplicates. Unsupported command input cannot submit. |
| Evaluate disable predicate | Require live mode, explicit usable nonreserved actor, descriptor, confirmed head, valid benchmark identity and no affected collision/pending operation. Do not locally decide SPRT eligibility, require completion or manufacture verdict evidence. |
| Promote disable predicate | Require live mode, explicit usable nonreserved actor, descriptor, confirmed head, valid benchmark identity and no affected collision/pending operation. Do not disable for a null verdict, multiple seats, held-out purpose or a current-version difference: server refusals must remain observable. |
| Actor spoofing | Apply the public AgentId pattern and reject `operator` and `system`, including recovered storage. Never substitute another actor. |
| Witness verification | Inspect `commit.event_ids`, benchmark/run identities and immutable payloads across cursor pages, then confirm with public reads. Require equal op_id for single-event mutations only. Compound launch child op_ids are opaque backend data. Evidence preference is `bench.result`, then `run.close`, then `run.open`. |
| Synthetic predicate | A known submitted `runner.kind === 'fake'` operation, confirmed with its public witnesses, requires `Synthetic offline benchmark` even in live mode. This does not add a runner field to BenchStatus. A snapshot without exposed runner provenance cannot invent it. No demo-bank pin constants are supplied by the fixture corpus. |
| Identity collision | Affected actions stop; `ready`/`update` settle after rendering `Identity key collision. Actions unavailable.` The module does not write shell-owned readiness attributes. |
| URI and head binding | Validate full benchmark IDs before dispatch and EventId before constructing an encoded local Ledger route. Launch and Promote retain the head from dialog open; they cannot silently adopt a newer head on submit. |
| Announcements | Suppress initial pre-existing state/verdict. Debounce by full benchmark and state/decision or actual transition event, never unrelated head changes. A poll that changes both announces state before verdict. Use the existing status node only. |
| Initial failure | Render the named panel and registered Retry inside the supplied host before rejecting `ready` or `update`; later failure retains a confirmed stale fold. |

There is no integrated Python API deviation: this unit imports no Python domain
internals. U21's existing ScreenContext, store, transport, identity and dialog
signatures are used without extension. The preserved-placeholder failure reason
and unavailable destructive-discard action are the explicit contract limitations.

## Acceptance-to-test map

Names with `%s` denote every expanded row in the corresponding `it.each` table.
`EXTERNAL` names are explicit pending tests; they cannot turn green in jsdom.
Other mapped tests are TS unit coverage or prerequisites, not substitute observer
receipts. All fixture values are [TARGET]; schema bounds and public names are
[CITED: the named K0 contract/schema sections]. Acceptance labels are identifiers.

| Acceptance | Exact test names and containing files |
|---|---|
| A01 | `lifecycle.test.ts` — `A01 list and detail use the registered screen and preserve shell ownership`<br>`lifecycle.test.ts` — `A01 A32 the screen imports its owned stylesheet without a registry edit` |
| A02 | `continuity.test.ts` — `A02 newer refresh wins when the older same-benchmark reply arrives last`<br>`continuity.test.ts` — `A02 malformed %s read renders recovery before rejecting readiness`<br>`continuity.test.ts` — `A02 A21 initial list failure shows Benchmarks recovery rather than false emptiness`<br>`lifecycle.test.ts` — `A02 ready remains unsettled until the matching initial list read folds`<br>`lifecycle.test.ts` — `A02 actual U21 readiness waits for the screen fold at the published snapshot`<br>`lifecycle.test.ts` — `A02 A21 initial failure renders Rule and Retry before rejecting ready`<br>`lifecycle.test.ts` — `A02 route changes discard an older benchmark reply delivered last`<br>`lifecycle.test.ts` — `A02 A23 abort and dispose discard callbacks and announcements` |
| A03 | `continuity.test.ts` — `A03 pending lexical page cannot be submitted twice and repeated cursor cannot loop`<br>`lifecycle.test.ts` — `A03 lexical paging deduplicates identities and filters only loaded records`<br>`lifecycle.test.ts` — `A03 an empty confirmed list is distinct from a filtered no-match`<br>`lifecycle.test.ts` — `A03 failed paging retries its cursor once and retains filters` |
| A04 | `lifecycle.test.ts` — `A04 names are bounded content keys and actions survive article pruning`<br>`lifecycle.test.ts` — `A04 a forced key collision disables affected controls but settles the visible error` |
| A05 | `evidence.test.ts` — `A05 A16 task inspector uses exact run_get frozen identity and null-safe cost`<br>`evidence.test.ts` — `A05 open run with closed null never displays a passed closing memory gate`<br>`lifecycle.test.ts` — `A05 separate task agent seat arm and actual run identities remain visible` |
| A06 | `continuity.test.ts` — `A06 an explicitly entered participant absent from loaded choices is checked with agent_get`<br>`continuity.test.ts` — `A06 repeated memory-arm entry cannot create duplicate declared arms`<br>`mutations.test.ts` — `A06 all typed declaration leaves serialize exact closed arguments and explicit roles`<br>`mutations.test.ts` — `A06 malformed %s=%s is refused before dispatch with field focus`<br>`mutations.test.ts` — `A06 natural-key agent collection rejects a duplicate without swapping roles`<br>`mutations.test.ts` — `A06 natural-key seat collection rejects repeated complete tuples` |
| A07 | `mutations.test.ts` — `A07 %s preserves explicit bank purpose and credit draft`<br>`mutations.test.ts` — `A07 existing declaration is read-only and discloses bank credit SPRT and memory meaning` |
| A08 | `lifecycle.test.ts` — `A08 omitted rule is collapsed and requires explicit display before launch`<br>`lifecycle.test.ts` — `A08 changed declaration or selected identity invalidates the display prerequisite` |
| A09 | `continuity.test.ts` — `A09 fixture list Declare cannot dispatch even through programmatic activation`<br>`mutations.test.ts` — `A09 reserved or malformed actor %s cannot mutate`<br>`mutations.test.ts` — `A09 %s precondition blocks all programmatic mutation attempts`<br>`mutations.test.ts` — `A09 the actual shell disabled actor placeholder is an integration blocker` |
| A10 | `mutations.test.ts` — `A10 A14 fake Launch uses shared transport exact args and dialog-open expected head`<br>`mutations.test.ts` — `A10 semantic refusal through actual shared HTTP transport is never success` |
| A11 | `continuity.test.ts` — `A11 a lost already-committed launch replays its exact operation without duplicate journal events`<br>`continuity.test.ts` — `A11 %s draft reload uses explicit existing controls and preserves exact pending tuple`<br>`continuity.test.ts` — `A11 recovered pending evaluate stays inert until explicit Evaluate retry`<br>`continuity.test.ts` — `A11 persisted drafts omit response projections tokens and memory bodies`<br>`evidence.test.ts` — `A11 A26 tampered stored %s cannot be recovered or automatically replayed`<br>`mutations.test.ts` — `A11 pending submission blocks duplicate calls and exact retry retains operation identity`<br>`mutations.test.ts` — `A11 editing or changing actor after uncertain submission starts a new operation`<br>`mutations.test.ts` — `A11 reload never auto-submits and explicit Launch recovery reuses the saved safe tuple`<br>`mutations.test.ts` — `A11 cancellation declines recovery without resubmission and keeps safe draft`<br>`mutations.test.ts` — `A11 denied storage is visible and does not prevent an honest uncertain state`<br>`mutations.test.ts` — `A11 A18 evaluate response loss is recoverable with its exact retained operation` |
| A12 | `continuity.test.ts` — `A12 compound commit with a changed task payload cannot certify launch`<br>`mutations.test.ts` — `A12 commit witness past the first cursor page is required before recorded completion`<br>`mutations.test.ts` — `A12 %s single-event witness cannot certify declaration`<br>`mutations.test.ts` — `A12 compound launch verifies commit event IDs and payloads without guessing child op_ids` |
| A13 | `mutations.test.ts` — `A13 A14 backend %s remains visible with no invented success`<br>`mutations.test.ts` — `A13 ledger resync makes acknowledged launch uncertain with named recovery` |
| A14 | `continuity.test.ts` — `A14 failed backend task stays inspectable with its actual failure-memory closing gate`<br>`mutations.test.ts` — `A10 A14 fake Launch uses shared transport exact args and dialog-open expected head`<br>`mutations.test.ts` — `A13 A14 backend %s remains visible with no invented success`<br>`mutations.test.ts` — `A14 invalid fake seed %s submits nothing`<br>`mutations.test.ts` — `A14 command runner is visibly unavailable and cannot submit browser shell text` |
| A15 | `lifecycle.test.ts` — `A15 actual %s lifecycle is rendered distinctly`<br>`lifecycle.test.ts` — `A15 named refresh folds delayed results and never manufactures completion` |
| A16 | `evidence.test.ts` — `A05 A16 task inspector uses exact run_get frozen identity and null-safe cost`<br>`evidence.test.ts` — `A16 exact task outcome %s is preserved`<br>`evidence.test.ts` — `A16 inspector failure retains other cells and uses Task results recovery` |
| A17 | `continuity.test.ts` — `A17 stale benchmark read retains the failed task existing witness URL`<br>`evidence.test.ts` — `A17 failed task retains its verified event link after an evidence refresh error`<br>`evidence.test.ts` — `A17 a later cursor page supplies a task witness without a guessed link`<br>`evidence.test.ts` — `A17 evidence fallback prefers %s over lower-priority witnesses`<br>`evidence.test.ts` — `A17 missing witness retains the task and exposes absence with retry`<br>`evidence.test.ts` — `A17 unrelated run and changed cell payload cannot provide an evidence URL` |
| A18 | `evidence.test.ts` — `A18 pending verdict is unmeasured rather than an invented inconclusive decision`<br>`evidence.test.ts` — `A18 repeated task cells do not change the exact server verdict or credit`<br>`mutations.test.ts` — `A18 evaluate displays server numbers exactly and verifies bench.verdict`<br>`mutations.test.ts` — `A11 A18 evaluate response loss is recoverable with its exact retained operation`<br>`mutations.test.ts` — `A18 absent verdict witness never announces recorded or synthesizes superiority` |
| A19 | `lifecycle.test.ts` — `A19 unrelated head changes and unchanged polls never repeat verdict announcements`<br>`lifecycle.test.ts` — `A19 one poll announces state before verdict once and in observed order` |
| A20 | `mutations.test.ts` — `A20 promotion %s reaches the server and preserves candidate status`<br>`mutations.test.ts` — `A20 promotion accepts server-declared snapshot despite a newer observed memory version`<br>`mutations.test.ts` — `A20 agent_get disagreement leaves acknowledged promotion uncertain` |
| A21 | `continuity.test.ts` — `A02 A21 initial list failure shows Benchmarks recovery rather than false emptiness`<br>`evidence.test.ts` — `A21 Task results panel errors preserve Rule and Verdict confirmed panels`<br>`evidence.test.ts` — `A21 Verdict refusal is isolated from usable Rule and actual task cells`<br>`lifecycle.test.ts` — `A02 A21 initial failure renders Rule and Retry before rejecting ready`<br>`lifecycle.test.ts` — `A21 later Rule failure retains the confirmed fold with stale revision and disables launch` |
| A22 | `continuity.test.ts` — `A22 %s native modal is keyboard-contained and Escape restores its invoker`<br>`mutations.test.ts` — `A22 modal focus contains keyboard traversal Escape restores invoker and controls are registered` |
| A23 | `lifecycle.test.ts` — `A02 A23 abort and dispose discard callbacks and announcements`<br>`lifecycle.test.ts` — `A23 query restoration resets only unsupported values and retains valid filters`<br>`lifecycle.test.ts` — `A23 refresh reorder preserves full run identity focus and disclosure` |
| A24 | `evidence.test.ts` — `A24 fixture provenance is visible and every mutation is disabled`<br>`evidence.test.ts` — `A24 successful live fake-runner provenance says Synthetic offline benchmark`<br>`evidence.test.ts` — `A24 heldout text comes from the frozen run split and never confirm purpose alone` |
| A25 | `observers.test.ts` — `A25 EXTERNAL browser geometry contrast focus themes reduced-motion and zoom matrix` |
| A26 | `evidence.test.ts` — `A26 hostile tool-error detail remains inert text and no evidence path is a URL`<br>`evidence.test.ts` — `A26 invalid bench route %s dispatches no read or mutation`<br>`evidence.test.ts` — `A26 invalid event identity %s never becomes a link`<br>`evidence.test.ts` — `A11 A26 tampered stored %s cannot be recovered or automatically replayed`<br>`evidence.test.ts` — `A26 schema-valid hostile seat model is displayed as passive rule text`<br>`evidence.test.ts` — `A26 hostile query is a native input value rather than executable markup` |
| A27 | `contracts.test.ts` — `A27 scripted public replies and records conform to the frozen wire schemas`<br>`contracts.test.ts` — `A27 the scripted compound launch has closed public replies and actual run wrappers`<br>`contracts.test.ts` — `A27 malformed scripted shapes are discriminated by the public schema check`<br>`lifecycle.test.ts` — `A27 the unimplemented placeholder cannot satisfy a rendered Arena oracle` |
| A28 | `observers.test.ts` — `A28 A29 A31 public observer inventory has native named bounded identity-bearing targets (unit prerequisite)`<br>`observers.test.ts` — `A28 EXTERNAL CDP pipe live seeded-home keyboard journey with journal postconditions` |
| A29 | `observers.test.ts` — `A28 A29 A31 public observer inventory has native named bounded identity-bearing targets (unit prerequisite)`<br>`observers.test.ts` — `A29 EXTERNAL independent native AT-SPI document action and raw/transformed tree witnesses` |
| A30 | `observers.test.ts` — `A30 clean-room article pruning preserves actual task controls and rejects an article-contained action`<br>`observers.test.ts` — `A30 EXTERNAL capsule frame hashes route revision prune comparison and semantic postcondition` |
| A31 | `observers.test.ts` — `A28 A29 A31 public observer inventory has native named bounded identity-bearing targets (unit prerequisite)`<br>`observers.test.ts` — `A31 EXTERNAL separate public-doc-only junior and Big Tech scored persona capsules` |
| A32 | `contracts.test.ts` — `A32 frozen oracle bytes match the published relative-path SHA-256 manifest`<br>`lifecycle.test.ts` — `A01 A32 the screen imports its owned stylesheet without a registry edit` |

## Separate integration gates

| Gate | Required witness and rejecting contrast | Present status |
|---|---|---|
| A25 / C geometry | Real browser at 390×844, 768×1024 and 1440×900 CSS pixels, 200% zoom, both themes and reduced motion [CITED: O12]. Computed foreground/background contrast at least 4.5:1 [CITED: O12], visible focus and no document overflow. jsdom geometry is insufficient. | **AUSENTE — no inventar**; pending external test. |
| A28 / C CDP | Public selectors and keyboard on a live seeded home: inspect immutable rule, fake launch, actual runs/evidence and ineligible promotion; public reads and journal witnesses establish completion. No fixed sleeps or pixel-only claim. | **AUSENTE — no inventar**; pending external test. |
| A29 / A AT-SPI | Independently find the actual browser document with renderer accessibility enabled, retain raw/transformed trees and truncation status, activate a required control and check public reads. Empty/unavailable/truncated native evidence is INCONCLUSIVE; a complete observed document missing required actions is FAIL. CDP cannot substitute. | **AUSENTE — no inventar**; pending external test. |
| A30 / P and V | The unit prune prerequisite compares surviving names/identity/state and rejects a hostile article-contained action. Integration additionally binds frame hashes to route/revision and semantic journal postconditions; no frame alone proves a mutation. | Unit prerequisite remains red against the placeholder; native/capsule witnesses **AUSENTE — no inventar**. |
| A31 / V personas | Separate junior and Big Tech capsules, public docs only, rubric J4/J6–J8, scored reports with frame and journal evidence. Target 8/10 each [CITED: NS6]. Assistance, fixture mutations or unsupported scores reject the gate. | **AUSENTE — no inventar**; pending external test. |
| A32 / integration | Compare all changed paths against the exclusive U25 surface, run campaign type/publishability checks and verify `freeze.json`. Changes outside the surface, oracle-byte edits or machine-local/private references reject delivery. | Manifest self-check is a unit gate; integration acceptance remains separate. |

## Freeze

`freeze.json` records SHA-256 for the tests, helpers and this document using only
repository-relative paths. It excludes itself to avoid a circular digest. Any
assertion change after freeze requires an explicit new oracle revision; the unit
must not weaken these assertions to fit its implementation. No backend, UI,
observer, capsule, persona, publication or interoperability receipt is fabricated.
This oracle is scoped to the supplied Lineage corpus, U25 surface and frozen K0 contracts.


## Amendments A-U25

- Added `h2.review.test.ts` under the authorized new-regression exception. Its
  A23 cases require main-heading focus to survive list and detail refreshes.
  The rejecting contrast is focus falling back to the document body.
- Its A01/A02/A09/A21 integration cases use the existing `startApp` options and
  `Transport` signatures with contract-shaped benchmark reads. They require
  published snapshot readiness and the disabled shell actor boundary. A
  placeholder-only reply must retain false readiness and named recovery text.
- No frozen test, helper, behavioural assertion, API expectation or fixture was
  edited. No integrated API deviation or oracle reconciliation was necessary.
- `freeze.json` retains all original test/helper hashes, adds the new regression
  file, and refreshes only this document's digest for this required appendix.
  The specification pin remains unchanged.

These additions are scoped to the supplied Lineage corpus and U25 surface;
external observer and persona witnesses remain AUSENTE — no inventar.
