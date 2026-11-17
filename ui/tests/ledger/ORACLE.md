# U26 fail-first Ledger oracle

Authority: `.unit/SPEC.md`, including Amendment B; the supplied North Star, K0 contract and `docs/OPERABILITY.md`; integrated U21 APIs under Amendment A-K0-9. Test inputs and bounds are targets [TARGET], not measurements of a live journal. Test data is synthetic and never establishes persistence or real hash-chain validity.

## Files and unchanged seam

| Path | Purpose |
|---|---|
| `ui/tests/ledger/screen.test.ts` | Lifecycle, readiness, URL restoration, selection, snapshot agreement and announcements. |
| `ui/tests/ledger/cursor.test.ts` | Wire/page validation, exclusive cursors, filters, retry, resync, cancellation and incremental bank traversal. |
| `ui/tests/ledger/actions.test.ts` | Verification, protected export, refusals, uncertainty and real shared HTTP transport with an injected fetch double. |
| `ui/tests/ledger/security.test.ts` | Native controls, disclosures, modal focus, action/name inventory, collision refusal, passive hostile data and deterministic fixtures. |
| `ui/tests/ledger/fixtures.ts` | Deterministic schema-valid `run.beat` data, lazy bank, deferred replies and typed public-seam doubles. |
| `ui/tests/ledger/ORACLE.md` | Acceptance mapping, decisions, observer boundaries and frozen file hashes. |

`ui/src/screens/ledger/index.ts` already exports `screen: ScreenModule`, with `id: 'ledger'`, `title: 'Ledger'` and the integrated `mount(host, context): MountedScreen` behavior. It remains unchanged, as required by the existing-stub preservation rule. No helper export or replacement stub is needed. Consequently the red evidence consists of behavioral assertion failures against `Ledger: not built yet.`, rather than a newly introduced `throw new Error("U26 stub")`. `ui/styles/ledger.css` is absent; A1 requires the implementation to provide and import it. No source, stylesheet, shared test, configuration, dependency or upstream file was edited.

## Acceptance map

Parameterized names below are the literal test-name templates; their tables enumerate positive and rejecting inputs in the named files. Every executable case checks public DOM, the screen lifecycle or the public transport boundary. An assertion concerning an external observer is not manufactured as a passing unit test.

| Case | Executable test names and witness | Rejecting contrast / remaining evidence |
|---|---|---|
| A1 | `screen.test.ts`: `A1 exports the shared screen, replaces the placeholder and imports its owned CSS` | Imports alone cannot pass: the placeholder must disappear, an event must render, and the stylesheet import and file must exist. Whole-workspace write confinement is a host audit below. |
| A2 | `screen.test.ts`: `A2 keeps Loading and the initial ready promise pending until the active page is folded`; `A2 renders an established unfiltered empty journal rather than a no-match`; `A2 initial failure rejects readiness, preserves unknown head and offers Retry Ledger`; `A2 A18 initial failure recovers by an explicit named retry without remounting`; `A2 A15 publishes a populated Ledger through the real shell with the acknowledged global revision`; `A2 refuses a newer page fold when store refresh cannot establish its head` | Deferred initial reads, genuine zero head, unknown head, failure/retry, immutable store snapshots and real shell revision agreement. |
| A3 | `cursor.test.ts`: `A3 A4 requests exact initial and continuation K0 arguments`; `A3 rejects malformed %s before confirming any rows`; `screen.test.ts`: `A3 discovery absence of %s fails its affected action visibly`; `actions.test.ts`: `A3 shared transport removes exactly the outer wrapper and leaves inner passive keys alone` | Extra keys, unsafe/null/Boolean counters, invalid IDs/kinds/actors/digests/evidence, non-finite values, invalid Unicode, malformed resync and missing discovery tools. Read filter `agent_id` never becomes reader `agent`. |
| A4 | `cursor.test.ts`: `A4 advances across empty filtered pages and trailing nonmatches using next_after`; `A4 rejects %s while retaining the confirmed page`; `A4 identical observations on unchanged refresh do not duplicate identities`; `A4 exhausted empty cursor at the acknowledged head is valid`; the A3/A4 dispatch test | Cursor holes, trailing nonmatches, conflicts under an existing identity/Lamport, regression, order, nonadvancement and legal exhausted empty history. |
| A5 | `cursor.test.ts`: `A5 server filters restart at zero and selected unobserved actor remains available`; `A5 reserved actor %s is a filter and never an asserted operator reader`; `A5 local query %s is literal and does not restart or advance the server cursor`; `A5 clear filters preserves prior revision while replacement read is pending`; `screen.test.ts`: `A5 A18 local no-match is distinct from an empty authoritative journal` | Mixed case, punctuation, regex-shaped and URL-shaped literals, partial coverage, unknown option coverage, no broadening and no false empty state. |
| A6 | `cursor.test.ts`: `A6 continuation Retry keeps cursor, filters, selected identity and confirmed rows` | Exact failed/retried argument equality, retained rows, query and expanded full-ID disclosure; no pre-acknowledged cursor advance. |
| A7 | `cursor.test.ts`: `A7 resync is explicit, preserves filters and replaces rather than appends history`; `A7 failed resync replacement retains stale rows, warning and a recovery action` | Exact warning, no automatic restart, explicit zero-cursor replacement, removal of obsolete records, and recovery after replacement failure. |
| A8 | `cursor.test.ts`: `A8 duplicate page activation serializes one dispatch and exposes pending reason`; `A8 old-filter page cannot restore another query even when it ignores cancellation`; `A8 disposed lookup cannot change DOM, focus, revision or announcements`; `screen.test.ts`: `A8 initial read from an obsolete filter cannot settle the current update fold`; `actions.test.ts`: `A8 A11 double verify dispatches once, is visibly pending and ignores late disposal`; `A8 newer query invalidates an old verification result without publishing its digest`; `A8 uncertain export result from an obsolete query cannot certify the replacement view` | Duplicate activations, abort-ignoring replies, old initial readiness, query replacement, disposal and uncertain protected completion. Shared services must survive screen disposal. |
| A9 | `screen.test.ts`: `A9 invalid query values reset only their own field and unknown fields retain the router notice`; `A9 deep link finds a later full ID only through sequential cursor reads`; `A9 absent target under %j never broadens server filters`; `A9 clear filters preserves a requested event so it can be resolved again`; `A9 URL restoration uses full identities and never carries cursor, export draft or credentials`; `A9 active deep-link scan stays cancellable while the next page is unresolved` | Valid filters survive unrelated invalid fields; full IDs persist, cursor-only lookup, explicit filtered exhaustion, no inferred cursor or hidden endpoint, observable cancellable progress. Real browser history gestures remain external. |
| A10 | `security.test.ts`: `A10 native %s hash and payload disclosures retain labelled complete evidence`; `A10 predecessor field inequality does not invent a local chain verdict` | Separate native disclosures, expanded/control references, complete current/predecessor/request digests, escaped evidence and no editable payload or adjacent-hash shortcut. Native default key activation is emulated only where jsdom lacks it. |
| A11 | `actions.test.ts`: `A11 begins Not verified and reports only the validated verification head and digest`; `A11 verification warnings preserve torn tail, projection drift and unknown line`; `A11 null verification digest is unknown and never fabricated`; `A11 newer page data retains an older verified head without certifying the new one`; `A11 verification refusal %s remains failure and has a named retry`; `A11 rejects malformed verification %s without producing certification`; `A11 Retry Verification retries only its panel and leaves the cursor untouched`; the A8/A11 duplicate-verification test | Null digest/line remain unknown; torn-tail and projection diagnostics stay visible; valid=false, extra/unsafe fields and domain failures cannot certify history. |
| A12 | `actions.test.ts`: `A12 protected export collects only out and displays the full-history result and manifest`; `A12 export dismissal by %s dispatches nothing and restores its invoker`; `A12 A13 duplicate export confirmation serializes one protected dispatch`; `A12 shared HTTP export uses the protected session lane without fabricating journal identity` | Exact allowed args, mutation protection, no operation/expected-head invention, returned full-history head/manifest and no event requirement or independent-audit claim. |
| A13 | `actions.test.ts`: `A13 locally rejects destination %s without a protected dispatch`; `A13 rejects malformed export %s and preserves the draft without claiming success`; `A13 export %s refusal or uncertainty keeps draft and never automatically replays`; `A13 backend confinement refusal detail is escaped and retained verbatim` | Bare/wrong-root/absolute/traversal/backslash/empty/trailing segments, unsafe results, empty manifest, malformed digests, backend symlink refusal, session/domain/I/O/network uncertainty. Real filesystem confinement is the backend owner's gate. |
| A14 | `actions.test.ts`: `A14 actual transport preserves HTTP-success domain refusal for %s`; `A14 actual transport/screen rejects %s without false verification`; `A14 shared transport negative control preserves semantic failure source and code` | Actual shared wrapper decoder sees injected HTTP-success semantic errors; ambiguous/nested/missing wrappers cannot grant verification/export success or reset rows to empty. |
| A15 | `screen.test.ts`: `A15 refresh preserves event selection, disclosure state and focus by full identity`; `A15 replacement removal focuses the Ledger heading and announces removal once`; the A2/A15 integrated-shell test | Full-ID focus/expansion continuity, no positional substitution, and exact removal announcement with heading fallback. Complete native refresh evidence remains external. |
| A16 | `security.test.ts`: `A16 Export traps forward/backward focus, blocks background focus and restores the invoker`; `A16 all controls use native semantics with only Confirm submitting and no positive tabindex`; `A16 dismissal after invoker removal restores the Ledger heading and submits nothing`; A12 dismissal and A13 invalid-field tests | Modal edge trapping, background focus containment, native form behavior, first-invalid focus, Escape/Cancel and fallback. Real Tab traversal and AT activation remain external. |
| A17 | `security.test.ts`: `A17 active action inventory uses exact native names and full event identity`; `A17 reserved actor %s has passive text and no agent link`; `A17 duplicate metadata and maximum actor lengths preserve distinct byte-bounded action names`; `A17 identity-key collision fails closed before ambiguous actions become ready`; `A17 integrated action inventory survives the article boundary and shared operability checks`; `A17 shared operability negative control rejects %s`; `A17 event actor navigation retains the validated full ID in its public route` | Exact names/selectors, unique normalized names, description references, collision injection through the existing helper, article/duplicate/generic/positional negatives and full-ID navigation. The local DOM transform is a prerequisite, not an independent P receipt. |
| A18 | `screen.test.ts`: `A18 retains one shell-owned status node and deduplicates unchanged updates`; A2 loading/empty/error/retry tests; A5 local/server no-match tests; A6 stale test; A7 resync tests; A8/A11 and A12/A13 pending tests | Distinct visible states, stable persistent region, no repeated transition announcement, no secondary live region or success on refusal. |
| A19 | `cursor.test.ts`: `A19 pending page leaves filters and cancellation usable instead of draining the bank`; describe `A19 deterministic full-bank traversal`, `A19 page %i adds exactly one cursor response without loss or duplication`; `security.test.ts`: `A19 payload formatting is deferred until its disclosure is expanded`; A9 pending lookup tests | The lazy 10,000-event bank uses 100-event pages [TARGET]. The serial session has one bounded assertion per page [TARGET], exact ID comparison and no fetch-all on ordinary mount. Browser latency/geometry remain unmeasured; the runner timeout is a harness bound, not a product SLA. |
| A20 | `security.test.ts`: `A20 payload text stays passive and literal: %s`; `A20 rejects own poison key %s rather than merging it`; `actions.test.ts`: escaped refusal test; A3 malformed JSON inputs | Markup, script/URL/directive strings and prototype-sensitive text remain passive; actual poison object keys are rejected. No executable nodes, evidence navigation, automatic network or changed prototypes. |
| A21 | Prerequisites: A1 stylesheet requirement; A10 long-hash/payload disclosures; A16 keyboard semantics; A17 inventory | **EXTERNAL — INCONCLUSIVE; AUSENTE — no inventar.** The specified viewport/zoom, both themes, reduced motion, overflow, computed contrast and visible focus require real rendering. jsdom provides no passing geometry/contrast claim. |
| A22 | `security.test.ts`: `A22 fixture export is disabled with the exact synthetic explanation and direct protection refuses`; `A22 identical fixture page and presentation clock produce identical text, order and names`; `A22 fixture cancellation/refusal cannot fabricate a real export result or persistence` | Actual integrated fixture transport, exact fixture_readonly refusal, fixed presentation, differing host clocks, no live network/home or persistence claim. |
| A23 | All executable cases, especially A3/A4 dispatch, A6 retention, A10 activation and A14 wrapper-refusal assertions; host verification and frozen hashes below | Behavioral red against the unchanged placeholder is measured. Cursor/filter/disclosure/wrapper mutants in an isolated implemented copy remain **HOLD — AUSENTE — no inventar** until an implementation exists. No assertion was weakened to credit the placeholder. |
| A24 | Prerequisites: A2/A15 integrated shell, A9 full-ID evidence, A11 scoped verification, A12 protected export and A17 action inventory | **EXTERNAL — INCONCLUSIVE; AUSENTE — no inventar.** No live-home export-byte inspection, independent CDP/AT-SPI/prune/capsule witness, junior/Big Tech persona frames or persona score is fabricated. |

## Amendment B decisions and integrated APIs

| Topic | Oracle interpretation |
|---|---|
| Export confinement syntax | Both submitted and returned `out` must be K0 RelativePath and match `^exports/.+`, with no trailing/empty/dot/traversal segments. Every manifest path is RelativePath. Backend symlink/root authority is independent. |
| Deep-link lifecycle | Ordinary initial readiness waits for the active initial page. Deep-link cases accept either readiness after its validated first fold with continuing search, or readiness after resolution; they require progress, usable controls, cancellation and a matching update fold. Continuation may be asynchronous or explicit through `page-events`; no private batching/timer policy is imposed. Exhausted filtered scans report absence under active filters without an unrequested bypass. |
| Clear plus event target | Clear removes `q`, `agent` and `kind`, preserving a valid full `event` so a filtered-out target can be retried. |
| Container choice | No interactive article ancestor is permitted. The exact non-article event container tag remains implementation freedom; its full-ID tuple and heading are mandatory. |
| Cursor boundary | An empty exhausted result at `after === head` may retain that cursor. Nonadvancing results containing events or claiming more history, regressions, out-of-range cursors and events at/before the exclusive boundary fail. |
| Payload validation and timestamps | Fixtures use the actual schema-valid `run.beat` variant. The oracle requires closed event/page/evidence records, recognized kinds and recursively safe JSON, but does not impose a private implementation strategy for validating every payload variant. Full coverage of all variants is not claimed. Integrated `lineage/core/journal.py` generates `ts` in milliseconds; tests use that unit and fixed UTC/en-GB presentation. |
| Actors | Reserved `operator` and `system` may be server filters. Tool reader `agent` is omitted or explicitly `system`; it never inherits the filter or becomes `operator`. |
| Export field name | The public field prefix `Export` plus field label `Export directory` yields the intentional exact accessible name `Export Export directory`. |
| Store seam | Actual `AppStore`: `getState(): AppState`; `refresh(): Promise<void>`; `subscribe(listener): () => void`; `setRoute(route): void`; `setSelection(screen, id: string | null): void`; `setExpanded(entity, id, expanded: boolean): void`; `dispose(): void`. Expansion keys follow the existing public state. No product setter, commit operation or new API is assumed. Test-only acknowledgement belongs solely to the test double. |

No integrated API signature deviation was necessary. The timestamp unit was resolved from integrated source where the spec omitted it. No backend module was imported or modified by this UI oracle.

## Independent observer handoff

| Observer | Outcome and required public postcondition |
|---|---|
| C — CDP pipe | **INCONCLUSIVE — AUSENTE — no inventar.** Observe actual ready/revision/full IDs, action inventory, filtering/paging/disclosures/resync, scoped verification and protected export against public tool results. |
| A — AT-SPI | **INCONCLUSIVE — AUSENTE — no inventar.** Observe and activate actual named controls/modal in the native document. Missing/empty/truncated document cannot pass. |
| P — independent prune | **INCONCLUSIVE — AUSENTE — no inventar.** Retain independent raw/transformed inventories and required identity/action survival. The jsdom negative controls are not this observer. |
| V — capsules/personas | **INCONCLUSIVE — AUSENTE — no inventar.** Independent junior and Big Tech journeys from public guides need fresh frame hashes and semantic witnesses. No `pass`, `fail` or `refused` capsule receipt was supplied. |

The complete Ledger action inventory is the A17 test plus conditional `resync-ledger`, named `retry-panel` for Ledger/Verification, and Export `edit-field` (`name="out"`), `submit-dialog` and `cancel-dialog`. Event controls are `toggle-event-hash`, `toggle-event-payload`, and `open-event-agent` only for non-reserved actors. Public postconditions are validated `ledger_events`, `ledger_verify` and `ledger_export` results with separately labelled heads. Read-only disclosures and export/verification need no invented journal append. Independent export manifest inspection remains external.

## Host verification

The prescribed command was run from `ui/` using the supplied local executable:

```sh
../node_modules/.bin/vitest run tests/ledger
```

Exit status 1 [MEASURED]. Exact summary [MEASURED]:

```text
 Test Files  4 failed (4)
      Tests  256 failed | 2 passed (258)
```

All failures were behavioral assertions about the existing placeholder, missing actions/records, or incorrectly settled readiness. Non-assertion errors and import/collection/unhandled-rejection markers were absent [MEASURED]. The passing cases are the actual shared transport's one-wrapper and semantic-error controls; they grant no Ledger implementation acceptance credit.

`../node_modules/.bin/tsc --noEmit` returned exit status 0 [MEASURED]. The pre-existing shell suite passed before oracle authoring: `Tests  260 passed (260)` [MEASURED]. The post-authoring shell suite also returned exit status 0 [MEASURED], with the same exact summary:

```text
 Test Files  13 passed (13)
      Tests  260 passed (260)
```

A before/after content-hash audit matched every non-surface original file: 439 files [MEASURED], aggregate SHA-256 `38eba4c96897526520ff0480ebf7306a21915b457ba5337c9cabb17f7de965a5` [MEASURED]. The audit excludes dependency symlinks and generated build/cache directories; it does not claim an audit of external repositories. All retained authored files are under `ui/tests/ledger/`. The existing screen behavior was preserved; no source stub was added.

## Frozen test artifacts

The hashes below bind the authored executable oracle before implementation. `ORACLE.md` is excluded from its own manifest. Altering a frozen assertion to admit a failed behavior requires explicit review; later mutation checks must operate in an isolated implementation copy.

| Artifact | SHA-256 [MEASURED] |
|---|---|
| `ui/tests/ledger/actions.test.ts` | `9c744ffd610e6a3480399f93dc96c7b1d65b1ef23e6495f35f412ee0a4761ea7` |
| `ui/tests/ledger/cursor.test.ts` | `4c09f7f01a4b5373e4383fc99126fff05c581011af0e7c6e31cd58eb4caea36a` |
| `ui/tests/ledger/fixtures.ts` | `41136dbee25d20324f644244974feb2268c08f1337859da14b08c9ca1388dacd` |
| `ui/tests/ledger/screen.test.ts` | `74b725d2f92f4538d91439298c57f354bcccf17e6a8292f33449329095ee87a6` |
| `ui/tests/ledger/security.test.ts` | `3962508c4291a03d32e50b84146e2982eedfdf42604350e76013869ae6325824` |

This oracle is scoped to the supplied U26 specification and amendments, Lineage campaign corpus, frozen K0 and inspected integrated U21 seam.


## Amendments A-U26

Repair h1 applies the orchestrator's A-U26 reconciliation permission and A-K0-9 integrated API authority. These are fixture plumbing changes for the existing `AppStore.refresh(): Promise<void>` / `Transport.events(after, options?)` acknowledgement seam; no function signature or production API deviation was required. Production source and styles remain unchanged. All changes are confined to `ui/tests/ledger/`.

| Artifact | Change and reason |
|---|---|
| `ui/tests/ledger/actions.test.ts` | A11 null-digest fixture now returns an empty cursor page at head zero, matching its initial store snapshot and verification result. Previously `ledgerThen` supplied an event at head one while both the store and its refresh transport reported head zero. The null-digest behavioral assertions are unchanged. |
| `ui/tests/ledger/screen.test.ts` | A2/A18 retry fixture passes head one to `scripted`, so the integrated store's refresh path can acknowledge the recovered event page. Its initial snapshot remains unknown; the original failure, retry, exact call-count, cursor and row assertions are unchanged. |
| `ui/tests/ledger/h1.review.test.ts` | Added real-store regressions: delayed shared acknowledgement blocks recovered rows; persistent head disagreement refuses recovery; empty history preserves a null verification digest. No test-only production API or head setter is used. |
| `ui/tests/ledger/ORACLE.md` | Updated the amended frozen-artifact rows above; preserved the original hashes below and recorded this amendment and host verification. |

Every edited test and the new support helper carries an inline `// A-U26:` reason. No test was deleted, skipped or widened, and no behavioral assertion was changed. Reconstructing the two original fixture statements reproduces their frozen SHA-256 hashes exactly [MEASURED]:

| Original artifact | Original SHA-256 [MEASURED] |
|---|---|
| `ui/tests/ledger/actions.test.ts` | `d405844e231f76e0a73c43f4f678eac7ba63d82bd0c0c712623c4618c9a195a2` |
| `ui/tests/ledger/screen.test.ts` | `b1613c3045e004cdd20fbd1d5ae3a6b1f4258d9560176a759b4c4b50d0e2af30` |

Host repair verification [MEASURED]:

- `cd ui && ../node_modules/.bin/vitest run tests/ledger`: exit status 0; 261 tests passed across 5 files, including the 258 original cases and 3 added regressions.
- `cd ui && ../node_modules/.bin/tsc --noEmit -p .`: exit status 0.
- The prescribed Python suite passed; the full UI run reported 518 passed, 3 failed and 1 unhandled error across 18 files. Its failure prevented the chained typecheck from running; typecheck was executed separately as recorded above.

Remaining full-suite blockers are outside U26's write surface. `ui/tests/shell/config.test.ts` rejects the specification-required `ui/styles/ledger.css`; `ui/tests/shell/screens.test.ts` requires the removed `Ledger: not built yet.` placeholder and no enabled controls; `ui/tests/shell/shell.test.ts` expects Ledger readiness from a fake transport that advertises only `agent_list`. `ui/tests/shell/fixtures.test.ts` also reports `No wall-clock fixture state` from jsdom selection event creation under its throwing `Date.now` spy. These files were not modified. They require reconciliation by the shared-shell owner; the Ledger must not hide its implementation or bypass tool discovery to satisfy them.

Ledger unit verification is PASS; integrated full-suite status remains HOLD / RED. Independent C/A/P/V and browser/capsule receipts remain AUSENTE — no inventar. This amendment is scoped to the supplied U26 specification, orchestrator rulings and integrated U21 seam.
