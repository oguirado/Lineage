# U24 fail-first oracle

Authority: `.unit/SPEC.md`, including Amendment B; the integrated U21 browser contracts, store,
router, transport and registry. Test names below are literal titles or parameterized title
prefixes. Each parameterized case is an independent test. Quantities and acceptance bounds
quoted from the specification are [TARGET]. Execution results are reported separately.

Run from the repository root:

```sh
cd ui && ../node_modules/.bin/vitest run tests/lineage
```

The only runtime stub introduced is `drawTree` in `ui/src/screens/lineage/layout.ts`.
It has the specified signature and throws `new Error('U24 stub')`. The presentation types in
`ui/src/screens/lineage/model.ts` have no executable bodies. `ui/styles/lineage.css` is an empty
comment-only stylesheet imported by the operability test. The pre-existing
`ui/src/screens/lineage/index.ts` placeholder is preserved byte-for-byte: its missing behavior
must fail assertions, as required by M21. It must not be replaced with a successful fake or
an unconditional throw. Direct drawing tests fail at the new stub; screen tests fail because
the placeholder does not supply reads, controls, relationships, inspection or refusal states.

No test asserts that a stub throws as its successful behavior. Module resolution,
typechecking and the installed test runner are prerequisites, not intended failure causes.
Tests have a timeout below the per-test ceiling [TARGET], use deferred promises and bounded
microtask drains, and do not access the network, filesystem state outside the checked-in
source, processes, real runtime homes, timers for readiness, or shared fixture payloads.
The HTTP transport test uses an injected fetch double and an in-memory Response.

## Acceptance coverage

| Spec case | Test file | Exact test name or parameterized prefix | Positive witness and rejecting contrast |
|---|---|---|---|
| A1 | `screen.test.ts`; `operability.test.ts` | `A1 registered lifecycle replaces the placeholder and imports the owned stylesheet`; `A1 A26 stylesheet is owned and imported without claiming jsdom pixel acceptance` | Real registry, single heading, lifecycle and CSS import; reject unchanged placeholder, nested shell/status and absent integration. |
| A2 | `screen.test.ts` | `A2 uses the authoritative unwrapped read contract with no mutations or unsupported arguments` | Inner topology and retired status; reject missing read, extra arguments, mutation flags and double wrapper. |
| A3 | `screen.test.ts` | `A3 preserves %s and exposes Retry rather than empty success`; `A3 HTTP completion with semantic refusal never enables ancestry actions` | Domain and transport errors retain source/code; HTTP-success semantic refusal is rejected. |
| A4 | `model.test.ts` | `A4 refuses %s without invented links or ready success` | Hostile closed envelopes, IDs, enums, numeric bounds, parent arrays, cycles, generation and op arity; reject any ready/empty success. Valid empty revision is tested separately under A7. |
| A5 | `model.test.ts`; `operability.test.ts` | `A5 enumerates every nested parent edge/operator, independent of response order`; `A5 A6 the edge oracle rejects an omitted secondary reference even if SVG survives` | All source edges, operators, statuses and canonical nesting; deleting a secondary text reference must break the assertion. |
| A6 | `model.test.ts`; `continuity.test.ts`; `operability.test.ts` | `A6 has one canonical shared child under the first persisted in-scope parent`; `A6 shared-child search preserves both parent relationships without duplicate actionable identities`; `A5 A6 the edge oracle rejects an omitted secondary reference even if SVG survives` | One canonical child, persisted parent order and passive secondary edge; reject duplicated identity/action or an omitted secondary edge. |
| A7 | `screen.test.ts`; `model.test.ts` | `A7 measured empty head zero has the designated empty copy`; `A7 a lone true genesis has no fabricated descendants`; `A7 A9 a scoped descendant leaf retains boundary parents and is never called genesis`; `A7 decorative layout accepts an empty coherent topology` | Empty, true genesis and scoped leaf are distinct; drawing accepts an empty topology without inventing descendants. |
| A8 | `screen.test.ts`; `continuity.test.ts` | `A8 searches normalized full IDs and recorded names: %s`; `A8 no matches uses the exact copy, while selected hidden identity is preserved`; `A8 A13 filtering cannot eagerly mount a broad generation or falsely report a pending match absent`; `A8 A14 a deep search keeps its ancestor context within the same continuation gate` | Full IDs, NFC/case-equivalent duplicate names, context and bounded reachable matches; reject identity merging, lost hidden selection and false no-match. |
| A9 | `screen.test.ts` | `A7 A9 a scoped descendant leaf retains boundary parents and is never called genesis`; `A9 root scope preserves shared-child boundary ancestry and canonical identity`; `A9 A17 missing birth metadata declares unavailable display name and preserves topology` | Scope from full graph, boundary parents and honest absent name evidence; reject fabricated genesis/name. |
| A10 | `continuity.test.ts`; `operability.test.ts` | `A10 reload restores full root query and selected identities through the U21 route`; `A10 back and forward updates restore the corresponding full selected identity`; `A10 invalid %s resets only that field with a visible notice`; `A10 an unavailable valid root does not select a different genesis`; `A10 reset selects the first actual deterministic genesis, independent of response order`; `A10 resetting an empty tree invents no selected identity`; `A10 choosing a root outside the selected identity clears it with an explanation`; `A10 unknown query fields use U21 visible notice without extending the URL schema` | Router round trip, successive history contexts, field-local invalidation, unknown-field notice in actual shell and deterministic reset; reject fixture defaults or unrelated selection. |
| A11 | `continuity.test.ts` | `A11 refresh and reordered births preserve selected full identity focus expansion and scroll`; `A11 typing preserves search focus and caret while changing display text cannot redirect actions`; `A11 inspect and return use the full router identity and retain selection` | Identity-based selection/focus/expansion, search caret, usable scroll context, detail href and remount; reject array-position identity and focus redirection. |
| A12 | `continuity.test.ts` | `A12 collapse restores focus to the surviving branch disclosure and explains hidden selection`; `A12 removal clears only the missing identity, focuses the panel heading and announces once` | Collapsed focus returns to disclosure; true removal clears identity and announces once; reject body/sibling focus. |
| A13 | `model.test.ts`; `continuity.test.ts` | `A13 initial global budget uses generation then full identity across a wide forest`; `A8 A13 filtering cannot eagerly mount a broad generation or falsely report a pending match absent`; `A13 expansion adds at most fifty canonical entries and continuation exhausts partially exposed branches` | Global initial budget, per-action bound, unique continuation and exhaustive progress over broad data; reject eager mounting and permanent truncation. |
| A14 | `model.test.ts`; `continuity.test.ts` | `A14 deep ancestry is bounded initially and eventually exposes every relationship`; `A14 refuses a cyclic deep hostile variant as data failure, not drawing fallback`; `A8 A14 a deep search keeps its ancestor context within the same continuation gate` | Deep incremental reachability, valid headings and bounded search context; reject cycles and eager controls. Actual indentation/reflow remains A26. |
| A15 | `resilience.test.ts` | `A15 A23 deferred initial read exposes Loading and cannot resolve readiness early`; `A15 late route response cannot replace newer selection DOM or announcements`; `A15 dispose invalidates pending reads, subscriptions and owned listeners`; `A15 aborted read cannot commit even if the transport ignores its signal`; `A15 stale response cannot resolve the current update while its own read is pending` | Explicit deferred boundaries prove lifetime isolation; reject late DOM/selection/status commits and premature active readiness. |
| A16 | `resilience.test.ts` | `A16 complete contiguous prefix and matching tree head resolve the corresponding fold`; `A16 mismatched tree revision offset %s stays unready without a refresh loop`; `A16 matching integers do not pass an incomplete prefix: %s`; `A16 later mismatch retains the coherent old topology and marks its revision stale` | Matching complete prefix, bounded refresh, unknown/gapped/resync refusal and stale retained revision; reject integer-only coherence. |
| A17 | `screen.test.ts` | `A17 A19 inspects recorded eligible %s provenance from a different birth actor`; `A17 preserves rejection identity and readable reason %s`; `A17 an explicitly empty inheritance array differs from missing evidence`; `A9 A17 missing birth metadata declares unavailable display name and preserves topology` | Birth matched by record/event IDs, accepted provenance/receipts and every rejection code; reject actor-based lookup and missing-as-empty evidence. |
| A18 | `screen.test.ts` | `A18 compares equal complete immutable parent artifacts without inventing a captured version`; `A18 attributes added removed and changed cited text and reads record rule_overrides`; `A18 %s evidence never claims equal or invents rule changes`; `A18 cross compares each parent separately and genesis fabricates no parent artifact` | Equal/different/missing/hash-only immutable artifacts, explicit record overrides and separate parent evidence; reject false derivation version and invented rule changes. |
| A19 | `resilience.test.ts`; `screen.test.ts` | `A19 invalid accepted %s remains unavailable without an Inheritable badge`; `A19 rejected private and episode identities never cause body fetches or content exposure`; `A17 A19 inspects recorded eligible %s provenance from a different birth actor` | Eligible lesson/negative/promoted workflow plus hostile kind, level, privacy, active status, receipt, scope and provenance cases; reject privacy leaks and invalid inheritance badges. |
| A20 | `resilience.test.ts`; `operability.test.ts` | `A20 %s drawing failure leaves every structured relation and action usable`; `A20 initial layout exception can resolve ready with the list`; `A20 A21 SVG is decorative, unfocusable and carries no dispatch selectors`; `A20 A24 one persistent shell status survives lineage selection refresh and drawing fallback` | Throwing/unusable drawing retains relation list, selection, focus, links and disclosures; reject list destruction or SVG dispatch controls. |
| A21 | `operability.test.ts` | `A21 native action inventory retains unique bounded names for maximal IDs and duplicate display names`; `A21 key collision blocks ambiguous actions and readiness without ordinal fallback`; `A21 action/prune assertions reject article-contained controls and duplicated names`; `A20 A21 SVG is decorative, unfocusable and carries no dispatch selectors` | Native named controls, stable full selectors/descriptions and collision seam; hostile article/name mutants must fail the DOM inventory. Native prune observations remain A27. |
| A22 | `operability.test.ts`; `resilience.test.ts` | `A22 hostile text and receipt paths stay literal and never create executable nodes or external links`; `A22 prototype-shaped %s root and selected values reset safely and independently`; `A22 U21 safely refuses the actual URL query key %s`; `A22 hostile rule_overrides key %s cannot alter prototypes or domain state`; `A22 A24 passive error detail never executes and an unchanged refusal is announced only once` | Literal text, router links, safe prototype handling and passive error detail; reject executable nodes, external requests, private body fetch or prototype/domain mutation. |
| A23 | `resilience.test.ts` | `A15 A23 deferred initial read exposes Loading and cannot resolve readiness early`; `A23 initial refusal retries successfully, then a later failure preserves acknowledged filters and selection`; `A23 malformed detail evidence preserves coherent ancestry and exposes unavailable details` | Deferred loading, recoverable refusal, Retry and stale preserved panels; reject blanking relations or evidence-as-empty. |
| A24 | `operability.test.ts`; `resilience.test.ts` | `A20 A24 one persistent shell status survives lineage selection refresh and drawing fallback`; `A24 unchanged reads do not flood announcements or move identity focus`; `A22 A24 passive error detail never executes and an unchanged refusal is announced only once` | Actual shell node identity and deduplicated read/error announcements; reject extra live regions and unchanged-refresh focus movement. |
| A25 | `model.test.ts`; `operability.test.ts` | `A25 drawing seam returns deterministic decorative geometry from coherent visible projection`; `A25 seeded reads and normalized identities ignore host clock and random sampling` | Stable list/edges/drawing under shuffle and fake host times, read-only calls and synthetic shell provenance; reject clock/random ordering or domain mutation. |
| A26 | `operability.test.ts` | `A26 external Chrome CDP pipe viewport contrast zoom themes and reduced-motion journey` (TODO); `A1 A26 stylesheet is owned and imported without claiming jsdom pixel acceptance` (limited prerequisite) | Actual Chrome, keyboard, frames, geometry, computed contrast and matrix required; jsdom/source checks cannot PASS this gate. |
| A27 | `operability.test.ts` | `A27 external AT-SPI prune-survival and independent junior/Big-Tech capsule journeys` (TODO) | Independent native document/action inventory, prune comparison and separate public-guide persona frames required; missing/empty/truncated evidence is INCONCLUSIVE. |

## Ambiguities and API adaptations

- No unspecified model helper API is invented. Topology/metadata/projection behavior is
  exercised through `screen` obtained from the actual U21 `getScreen` registry. Only the
  specified `BirthOp`, `LineageNode`, `LineageTreeData` and `drawTree` exports are introduced.
- Integrated U21 `AppState.expanded` holds `JSON.stringify([entity, fullId])` strings. The
  transport/store double mirrors that representation, and supplies every actual `AppStore`
  member, rather than guessing an ID-only expansion representation.
- Integrated U21 `parseRoute` ignores ordinary unknown fields with a notice, but forbidden
  query **keys** use the safe Agents fallback. The oracle preserves that distinction.
  Prototype-shaped **values** of `root`/`selected` are field-local invalid identities on the
  Lineage screen. No router change is authorized or required by this oracle.
- Initial candidates are roots and immediate children in generation/full-ID order, subject
  to the global budget. Continuation must make deterministic cumulative progress, including
  partially exposed wide generations. Branch expansion is tested for its bounded addition
  and eventual reachability, without specifying a private counter or queue implementation.
  Filtered matches and ancestor context share the budget.
- Search may retain the canonical ancestor chain or all parent chains: assertions require
  ancestor context, all recorded parent descriptions, eventual secondary-edge access and a
  single canonical child. They do not freeze an unamended private filtering algorithm.
- Prefix zero denotes the empty ledger; nonempty events must be contiguous from Lamport one
  through head [TARGET]. Unknown head, gaps, duplicated Lamports and active resync warnings
  cannot pass merely by integer equality. A mismatch may stop with Retry or make at most one
  bounded U21 refresh per render cycle [TARGET]; neither choice authorizes a refresh loop.
- Rule-diff fixtures use isolated, unambiguous cited lines and overrides on
  `payload.record.rule_overrides`. No attribution convention is invented for ambiguous prose.
  Missing parent-at-derivation versions accept the literal mandated absence marker or an
  explicit English unavailable/not-recorded equivalent; no value may be substituted.
- Deep records may use native headings through `h6` or valid explicit heading roles. The
  oracle does not require heading depth to equal generation or dictate a list's private tags.
  Canonical entries and their controls cannot be inside `article` or headings.
- The drawing failure boundary is injected by mocking the specified `drawTree` module only.
  Its throwing and nonfinite-geometry variants must preserve the authoritative list. No
  production test API, renderer implementation detail or geometry API is added.

## External acceptance journey: A26 and A27

Status: **UNPROVEN**. CDP, AT-SPI, prune-survival, capsule and persona execution receipts:
**AUSENTE — no inventar**. The TODOs are deliberately not jsdom substitutes and award no
score. Read `docs/QUICKSTART.md`, `docs/UI_GUIDE.md` and `docs/HEADLESS.md` in each fresh,
independent capsule. All capture storage and observer infrastructure are external to the
repository and domain state.

1. Prerequisite: the actual served application has a deterministic synthetic or separately
   seeded live corpus with genesis, shared-child ancestry and recorded inherited/rejected
   context. Discover full identities using the public `lineage_tree` read with
   `include_retired:true`, and use `ledger_events` cursors to read the complete birth prefix;
   `agent_get` corroborates the selected records. Never filter birth discovery by the child
   as ledger actor. Do not fabricate fixture IDs, endpoints or captured parent versions.
2. Open `#/lineage` from `Lineage navigation`; wait for the shell's ready/revision predicate
   and compare its revision with public reads. Read `Lineage`, `Lineage agent {agent-key}`,
   full parent IDs, textual statuses and operators. Enumerate every source edge independently
   of drawing coordinates, including the shared child's secondary parent.
3. Using native keyboard actions, `Find lineage agent`, choose `Lineage root`, activate
   `Select lineage {agent-key}`, and inspect accepted/rejected context, source IDs/digests,
   birth event/hash/version, separate parent constitution comparisons and absent witnesses.
   Exercise `Show next lineage generation`, `Expand lineage {agent-key}` and
   `Collapse lineage {agent-key}` until every pending relation is reachable. Ensure each
   reveal stays within the specified batch [TARGET].
4. Activate `Inspect lineage {agent-key}`, return, use `Refresh Lineage`, then change search,
   root and viewport. Verify selection/focus/caret continuity, hidden-selection explanations,
   `Reset lineage filters` and unavailable-root recovery. Repeat with SVG unavailable in the
   observer; the authoritative list and inherited/rejected evidence must remain usable.
5. CDP pipe witness: run the specified viewport, theme, zoom and reduced-motion matrix from
   `.unit/SPEC.md` M18/A26. Record actual pixels, computed contrast, wrapping, scroll geometry,
   focus and console observations. A jsdom metric or a stylesheet regex cannot establish
   these measurements. Keep scenario/build/revision and fresh frame SHA-256 evidence external.
6. Separately, Chrome renderer accessibility must expose an actual native document on the
   private display/session bus. Enumerate roles/names/states and activate the same controls
   through AT-SPI independently of CDP. Preserve raw and transformed action sets and observer
   association/truncation status. Missing/empty/truncated native data is INCONCLUSIVE;
   an observed missing required action is FAIL. An article-contained control must disappear
   in the negative prune comparison and cause refusal, even if pointer activation works.
7. The junior follows the ancestry/inheritance/inspect-and-return journey from public docs.
   The Big Tech tester independently reconciles every shared-parent edge, recorded source
   hash/rejection reason and per-parent rule comparison against the public reads. Each uses
   its own capsule and fresh frames. No whole-product persona score follows from this screen;
   the independent campaign score target remains the specification's target [TARGET].

Freeze this oracle's bytes before author implementation. Keep broader U21 regression,
typecheck, browser, native and persona verdicts separate from the intentional red unit run.

## Host verification and frozen-regression conflict

The targeted run reports `Tests 157 failed | 2 todo (159)` [MEASURED]. Both direct drawing
cases stop at `Error: U24 stub`; screen cases fail behavior assertions against the preserved
placeholder. No module-loading, type, timeout or unhandled-error failure was observed.
The installed TypeScript `--noEmit` check passes [MEASURED].

Before adding the authorized U24 files, the existing shell suite reported
`Tests 260 passed (260)` [MEASURED]. With the oracle surface present it reports
`Tests 1 failed | 259 passed (260)` [MEASURED]. The sole regression is the frozen
`tests/shell/config.test.ts` test `A1 authored UI surface is confined and publishable without extra configuration`:
its literal U21-only file allowlist excludes `src/screens/lineage/layout.ts`,
`src/screens/lineage/model.ts` and `styles/lineage.css`. It first reports
`Unexpected authored ui/src/screens/lineage/layout.ts`.

That allowlist is outside U24 ownership. The frozen regression remains unchanged and its
failure is reported openly. A fully green broader suite requires an integration amendment
to that obsolete allowlist; the unit must not hide its newly authorized files or suppress
the assertion. All pre-existing workspace files, including the placeholder, retain their
baseline bytes [MEASURED].


## Amendments A-U24

- `screen.test.ts`, `operability.test.ts`: source fixture reads use Node path resolution
  from the prescribed `ui` working directory. Integrated Vitest supplies an HTTP
  `import.meta.url`, which cannot be passed to `readFileSync`. The CSS import and
  stylesheet assertions are unchanged.
- `model.test.ts`, A6: scope the existing single-Select assertion to controls whose
  nearest canonical entity is the child, matching U21 full-identity dispatch. Nested
  descendants retain their own controls; the single canonical identity and all-edge
  assertions remain unchanged. An additional whole-screen exact-name assertion also
  rejects duplicate Select controls for that identity.
- `fixtures.ts`, `ownText`: extract text with a pruning TreeWalker for the integrated
  nested DOM instead of repeatedly cloning whole descendant subtrees. Exclude exactly
  the same descendant canonical entities and SVGs; preserve normalization and every
  relation assertion, timeout, input, batching bound and case.

No behavioral assertions, cases or accepted values were removed, skipped or widened.
No frozen-input hash rows require updating.


## Amendments A-U24 — repair h2

- Add `lifecycle.review.test.ts` with regressions for M3/M16: topology arriving
  before U21 commits its initial event prefix; a superseding fold completing initial
  readiness; abort and disposal releasing the prefix subscription; and actual shell
  readiness with contract-shaped topology and a delayed complete ledger prefix.
  These tests fail on the previous implementation's behavior assertions.

No existing test or helper was changed, deleted, skipped or weakened. No frozen-input
hash row changed. Existing shell regressions remain untouched: the U21-only file
allowlist, placeholder expectation and non-topology transport double require separate
integration reconciliation outside the U24 write surface. The intermittent queued
jsdom selection-event failure under the shell's clock guard also remains unresolved;
no suite suppression or product-side test-environment special case was introduced.
