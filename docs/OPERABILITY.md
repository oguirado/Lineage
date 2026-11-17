# Lineage operability contract

Status: **K0 implementation target**. Runtime CDP, AT-SPI, capsule and persona receipts: **AUSENTE — no inventar**. This document defines acceptance criteria; it does not certify an implementation.

Normative inputs are `NORTH_STAR.md` (NS3, NS4, NS5, NS6, P1–P8), `STRATEGY.md` §2.4 (O1–O14), `docs/CONTRACT.md`, `docs/INTERFACES.md` and the schemas listed below. Numeric limits, viewport sizes, fixture quantities and probe exit codes in this document are **[TARGET]**. `[K0 decision]` identifies choices where the strategy is silent. A disagreement with a wire schema blocks the affected operation until the contract is amended; UI code must not create another API.

## Acceptance requirements

The verification methods C, A, P and V are specified under “Independent verification”. Each gate requires its positive witness and rejecting contrast. An unavailable observer never passes a gate.

| ID | Required behavior | Headless verification gate | Rejecting contrast |
|---|---|---|---|
| O1 | No interactive element has an `article` ancestor. Agent cards use `li` or a heading-labelled `section`. | C checks DOM ancestry, including dialogs; P compares required controls before and after pruning; A and V activate a card action. | A button hidden inside an `article` must fail even if a coordinate click works. |
| O2 | Use only the selector vocabulary below. Identity comes from persisted IDs, never array position, DOM allocation or rendering order. | C resolves each expected scoped selector uniquely before and after filtering, sorting, reload and refresh; A/P corroborate the identity in the accessible name; V refreshes observations before acting. | Positional CSS, sequence-generated identifiers, or a selector that activates another record fail. |
| O3 | Exposed controls have unique normalized names within the active screen and modal scope. Every name fits the UTF-8 byte ceiling below and record controls carry an identity key. Volatile state and full identifiers belong in descriptions. | C measures accessible names as UTF-8; A reads names independently; P checks uniqueness after normalization; V selects by observed role/name. | Colliding display names, a clipped identity, or an over-budget name fail. |
| O4 | Interactive DOM elements are native `button`, `a`, `input` or `select`. Every record has a heading or identity-bearing button. Links navigate; buttons perform actions. | C checks tag, role, focusability and behavior; A checks action roles; P retains identity headings/buttons; V completes the same action. | A clickable `div`, a pointer-only control, or a record with no surviving identity fails. |
| O5 | The shell has a `banner`, a navigation landmark named `Primary`, a `main`, a skip link and exactly one visible `h1`. Screen headings and subordinate record headings follow the table below. | C counts and orders headings/landmarks; A enumerates them independently; P retains headings; V locates the screen through its heading. | Duplicate `h1`, unnamed primary navigation or a skip link that misses `main` fails. |
| O6 | Observable states use `busy`, `checked`, `current`, `disabled`, `expanded`, `hidden`, `pressed`, `selected`. State is derived from the DOM; descriptions carry additional business status. | C/A compare native or ARIA state to visible text; P compares the pruned state; V observes state after the action. | A color-only verdict or an invented state token fails. |
| O7 | All workflows are keyboard-complete. Dialogs contain focus, close with Escape and restore the invoker; refresh preserves focus/expansion by identity. | C drives the keyboard journey and checks `activeElement`; A invokes focus/actions; P retains focused controls; V records entry, dismissal and return. | Background focus in a modal, lost focus after sorting, or a pointer-only operation fails. |
| O8 | One shell-owned persistent `role="status"` region announces each lifecycle/verdict transition once. It survives screen rendering. | C records node identity and message changes; A finds the region; P retains it when supported and otherwise retains the associated named state; V checks the visible postcondition. | Replacing the region, repeated announcements on polling, or announcing success after a rejected call fails. |
| O9 | `html[data-lin-ready="true"]` means the active route has completed its initial data fold. `data-lin-rev` is the corresponding ledger-head Lamport value. | C waits on attributes and checks the displayed revision; A/P see the matching ready/error text; V waits for the named ready state and then acts. | A timer setting ready before data arrives or reporting a revision newer than displayed data fails. |
| O10 | Loading, empty, no-match, stale and error states are distinct text states. Panel failures preserve usable panels and the user's draft. | C injects each fixture scenario; A/P expose the status/error headings and Retry; V follows a failure and recovery. | An empty list presented as loading forever, silent stale data, or a blank page after one failed panel fails. |
| O11 | Each UI mutation is a documented tool call through shared dispatch. Completion is verified against `ledger_events` and the relevant read tool. | C captures the request/result and checks the journal witness; A/P/V repeat the journey and use the same headless postcondition. | Changed pixels, a launch acknowledgement, or a success toast without a matching domain event fails. |
| O12 | Support the specified viewports, zoom, reduced motion, light/dark themes and computed contrast. Long statements and hashes wrap without document overflow. | C measures geometry, computed token contrast and media-query behavior; A checks reading/focus order; P preserves controls after reflow; V captures the viewport/theme matrix. | Hidden essential controls, clipped focus, horizontal document scrolling, or color-only state fails. |
| O13 | The app works through CDP pipe transport and independently through AT-SPI with Chrome renderer accessibility enabled on a private display/session bus. | C and A each execute the documented journey; P checks the transformed tree; V supplies a separate capsule witness. | CDP success cannot substitute for an empty AT-SPI tree; that observation is INCONCLUSIVE. |
| O14 | Fixtures and the presentation clock are deterministic. Capture metadata stays outside product state; no vision-engine-specific application API is introduced. | C compares repeated seeded state and pixels; A/P compare normalized role/name/state sets; V binds frames to scenario and revision. | A live cloud/model dependency, host clock, random record ordering or a fixture mutation masquerading as persistence fails. |

## Routes, headings and landmarks

`[K0 decision]` These are the complete `data-lin-screen` values. Only the active `main` carries this attribute; dialogs belong to its scope. Error, empty and loading states retain the intended screen value. A malformed route falls back to `#/agents`, clears unrelated selection and displays `Unknown page. Showing Agents.`; it must not dispatch a mutation.

| Route | `data-lin-screen` | Visible `h1` | Subordinate identity heading | Screen label used in names |
|---|---|---|---|---|
| `#/agents` | `agents` | `Agents` | `Agent {agent-key}` | `Agents` |
| `#/agents/<agent_id>` | `agent` | `Agent {agent-key}` | `Constitution`, `Skills`, `Memory`, `Scorecard`, `Runs`; records below them | `Agent` |
| `#/lineage` | `lineage` | `Lineage` | `Lineage agent {agent-key}` | `Lineage` |
| `#/arena` | `arena` | `Arena` | `Benchmark {bench-key}` | `Arena` |
| `#/arena/<bench_id>` | `bench` | `Benchmark {bench-key}` | `Declared rule`, `Task results`, `Verdict` | `Benchmark` |
| `#/ledger` | `ledger` | `Ledger` | `Event {event-key}` | `Ledger` |

The shell has a `header` banner, `nav aria-label="Primary"`, and `main id="main-content" tabindex="-1"`. The skip link targets `#main-content` through focus handling without replacing the application route. The active navigation link uses `aria-current="page"`, including nested agent and benchmark routes. A page title is `Lineage · {screen label}`; record identity remains in the heading and descriptions.

Cards and list entries have an identity heading. Static display names may collide; they are rendered as text. An agent's workflow, language, status, seat, version and score are descriptions, never substitutions for identity. A missing score or cost reads `Not measured`, preserving the wire value `null`.

`[K0 decision]` Agent detail panels use native navigation buttons with `aria-pressed`, rather than requiring a custom tab role to survive pruning. They behave as the keyboard map states. The lineage SVG is decorative (`aria-hidden="true"`, no focusable descendants); the nested list is authoritative. Shared children have one actionable canonical entry and text references from additional parents, avoiding duplicate action names.

## Selector and identity vocabulary

| Attribute | Exact values or meaning |
|---|---|
| `data-lin-screen` | `agents`, `agent`, `lineage`, `arena`, `bench`, `ledger` |
| `data-lin-entity` | `agent`, `run`, `bench`, `event`, `unit`, `skill` |
| `data-lin-id` | Full persisted identifier for the declared entity kind. For a skill pin, `skill_id@sha256` is its complete identity [K0 decision]. |
| `data-lin-action` | Exactly the literal values in the action tables below; names never contain an identifier or counter. |
| `data-lin-ready` | On `html`: literal `false` or `true`; absent is not ready. |
| `data-lin-rev` | On `html`: canonical decimal ledger-head Lamport value; absent before a first successful fold. |

`[K0 decision]` Form fields additionally use native `name` attributes from the field registry below. These are semantic selectors, not another `data-lin-*` namespace. Reference controls use `name="gold_s1"` or `name="memory_v21"`; references do not add an entity kind. Dialogs are selected by observed role/name; there are no extra screen values for dialogs.

A record selector combines screen, entity and full ID, then its action. For example: `[data-lin-screen="agents"] [data-lin-entity="agent"][data-lin-id="aurora-root"] [data-lin-action="open-agent"]`. A field selector combines the named active dialog, `[data-lin-action="edit-field"]` and its semantic `name`. Use attribute escaping when constructing selectors. Never use sibling numbers, `nth-child`, transient CDP/AX IDs or a display name as an identifier. Each expected action selector must resolve to exactly one exposed control; hidden panels and inactive dialogs are excluded from the exposed set.

### Accessible identity keys

Every exposed control name is at most **64 UTF-8 bytes [TARGET]**, after Unicode NFC normalization and whitespace collapse. Names must be unique in the active screen, including its shell and currently exposed modal. Option labels need uniqueness within their own select; repeated enumerated choices in different selects do not create action targets [K0 decision]. With a modal open, the background is inert and absent from the exposed action set.

`[K0 decision]` Full identifiers can already occupy the entire name budget. Define `key(kind, identity)` as the full identity when its UTF-8 encoding is at most **20 bytes [TARGET]**. Otherwise use the first **7 ASCII identity characters [TARGET]**, a hyphen, and the first **12 lowercase hexadecimal characters [TARGET]** of SHA-256 of UTF-8 `kind + NUL + identity`. Keys are content-derived, stable across ordering and reload, and never used for dispatch or `data-lin-id`. The categories used for keys are the entity kind, `reference`, `rule`, `seat`, `field` or `item`, as appropriate.

Display the full identifier as wrapping text adjacent to its key and include it in `aria-describedby`, alongside volatile state. If different identities produce the same key within a category, stop the affected screen before enabling ambiguous actions, show `Identity key collision. Actions unavailable.`, and keep readiness false. Do not resolve collisions by ordinal, silently truncate a name, or send a request using a key. All naming templates below fit the budget with the maximum key length; dynamically generated field/item labels must pass the same gate.

## Complete action registry

Every rendered interactive control has one `data-lin-action` from these tables. An action may be absent when its context is absent; it must not acquire a new meaning. A control has the native element shown; `input` rows specify the input type. Placeholder values in braces are substitutions, not literal selector suffixes. A button must specify its form behavior; only Confirm submits. A disabled action retains its name and a textual reason.

### Shell actions (available on every screen)

| Action | Element | Accessible name | Effect |
|---|---|---|---|
| `skip-main` | `a` | `Skip to main content` | Focus the active main. |
| `nav-agents` | `a` | `Agents navigation` | Navigate to `#/agents`. |
| `nav-lineage` | `a` | `Lineage navigation` | Navigate to `#/lineage`. |
| `nav-arena` | `a` | `Arena navigation` | Navigate to `#/arena`. |
| `nav-ledger` | `a` | `Ledger navigation` | Navigate to `#/ledger`. |
| `theme-light` | `button` | `Use light theme` | Select light tokens; expose pressed state. |
| `theme-dark` | `button` | `Use dark theme` | Select dark tokens; expose pressed state. |
| `refresh-screen` | `button` | `Refresh {screen label}` | Refresh reads; preserve identity-based focus. |
| `retry-panel` | `button` | `Retry {panel label}` | Retry only the named failed panel. |
| `dismiss-message` | `button` | `Dismiss message` | Dismiss the single non-modal notice. |
| `select-actor` | `select` | `Acting agent` | Select the asserted actor for subsequent calls. |
| `toggle-fixture-info` | `button` | `Fixture details` | Expand synthetic/read-only provenance. |

Panel labels are `Agents`, `Agent`, `Constitution`, `References`, `Skills`, `Memory`, `Scorecard`, `Runs`, `Lineage`, `Benchmarks`, `Rule`, `Task results`, `Verdict`, `Ledger` or `Verification`. A panel has at most one Retry control. Selecting actor `operator` never grants level-1 authority; the UI exposes no ruling writer.

### Agents actions

| Action | Element | Accessible name | Effect |
|---|---|---|---|
| `filter-agent-query` | `input search` | `Find agents` | Local text filter of loaded records; indicate partial results when paged. |
| `filter-agent-workflow` | `select` | `Filter agents by workflow` | Set the public workflow filter. |
| `filter-agent-language` | `select` | `Filter agents by language` | Set the public language filter. |
| `filter-agent-status` | `select` | `Filter agents by status` | Set the public status filter. |
| `include-retired` | `input checkbox` | `Include retired agents` | Opt into retired records. |
| `sort-agents` | `select` | `Sort agents` | Stable sort with full ID as the final tie-break. |
| `clear-agent-filters` | `button` | `Clear agent filters` | Restore unfiltered view and URL state. |
| `create-agent` | `button` | `Create agent` | Open Create; Confirm calls `agent_create`. |
| `open-agent` | `a` | `Open agent {agent-key}` | Navigate to the full agent ID. |
| `compare-agent` | `input checkbox` | `Compare agent {agent-key}` | Toggle comparison selection. |
| `compare-agents` | `button` | `Compare selected agents` | Open a comparison of exactly two selected agents [TARGET]. |
| `clear-comparison` | `button` | `Clear compared agents` | Clear comparison selection. |
| `page-agents` | `button` | `Load more agents` | Continue the `agent_list` cursor. |

Comparison is a labelled table grouped by agent and seat; it does not combine unlike seats or replace unknown values with zero. No second copy of an `open-agent` control is rendered in the comparison dialog.

### Agent-detail actions

| Action | Element | Accessible name | Effect |
|---|---|---|---|
| `show-constitution` | `button` | `Constitution for {agent-key}` | Select Constitution. |
| `show-skills` | `button` | `Skills for {agent-key}` | Select Skills. |
| `show-memory` | `button` | `Memory for {agent-key}` | Select Memory. |
| `show-scorecard` | `button` | `Scorecard for {agent-key}` | Select Scorecard. |
| `show-runs` | `button` | `Runs for {agent-key}` | Select Runs. |
| `view-brief` | `button` | `Read brief {agent-key}` | Inspect `agent_brief`, including its hash. |
| `get-reference` | `button` | `Read reference {reference-key}` | Inspect `reference_get` for the selected pin. |
| `verify-reference` | `button` | `Verify reference {reference-key}` | Run `reference_verify`; display a hash mismatch explicitly. |
| `open-skill` | `button` | `Open skill {skill-key}` | Inspect the pinned `skill_get` result. |
| `filter-memory-query` | `input search` | `Find memory` | Filter displayed statements locally. |
| `filter-memory-kind` | `select` | `Filter memory by kind` | Filter by schema kind. |
| `filter-memory-level` | `select` | `Filter memory by level` | Filter by level, shown in words. |
| `filter-memory-privacy` | `select` | `Filter memory by privacy` | Filter the selected agent's inspector results; retain explicit privacy labels. |
| `filter-memory-inheritable` | `input checkbox` | `Show inheritable memory` | Show eligible units, with the eligibility explanation. |
| `clear-memory-filters` | `button` | `Clear memory filters` | Restore the memory view. |
| `open-unit` | `button` | `Open unit {unit-key}` | Inspect `memory_get` content. |
| `toggle-unit-details` | `button` | `Unit details {unit-key}` | Expand receipt, hash, provenance and supersession details. |
| `memory-history` | `button` | `Memory history {agent-key}` | Inspect `memory_history`. |
| `route-memory` | `button` | `Search agent memory` | Call `memory_route` using the query field; show `NOT IN MEMORY` unchanged when returned. |
| `bootcheck-memory` | `button` | `Check agent memory` | Open Resume; validate observations with `memory_bootcheck`. |
| `write-memory` | `button` | `Write agent memory` | Open Memory; Confirm calls `memory_put`. |
| `filter-scorecard-seat` | `select` | `Scorecard seat` | Select the full model/effort/mode tuple. |
| `filter-scorecard-arm` | `select` | `Scorecard memory arm` | Select `none`, `own` or `inherited`. |
| `open-run` | `button` | `Open run {run-key}` | Inspect `run_get`, not a new-run operation. |
| `open-run-form` | `button` | `Open a run` | Open Run start; Confirm calls `run_open`. |
| `heartbeat-run` | `button` | `Record heartbeat {run-key}` | Call `run_beat` for the open run with a fresh operation identity. |
| `close-run` | `button` | `Close run {run-key}` | Open Run close; Confirm calls `run_close`. |
| `derive-agent` | `button` | `Derive agent {agent-key}` | Open Derive with the parent fixed. |
| `retire-agent` | `button` | `Retire agent {agent-key}` | Open Retire; Confirm calls `agent_retire`. |
| `promote-agent` | `button` | `Promote agent {agent-key}` | Open Promote; Confirm calls `agent_promote`. |
| `page-memory` | `button` | `Load more memory` | Continue `memory_history` or locally page the documented `memory_get` result; do not add cursor arguments to `memory_get`. |
| `page-runs` | `button` | `Load more runs` | Continue run events, then resolve run records with `run_get`. |

The memory view distinguishes `Level one — operator ruling`, `Level two — receipt-backed` and `Level three — observation`. It shows `Inheritable` or `Not inheritable: {reason}` as text. Private units never appear in an agent brief or inheritance preview. An inspector scoped to their owning agent may show private units within the documented same-user boundary; this is not an additional authentication mechanism. Only eligible receipt-backed level-two lessons/negatives and promoted workflows can be selected for inheritance; every excluded unit retains its rejection reason. Constitution citations remain resolvable and display rule IDs.

### Lineage actions

| Action | Element | Accessible name | Effect |
|---|---|---|---|
| `filter-lineage-query` | `input search` | `Find lineage agent` | Find a full ID or display name in the structured list. |
| `filter-lineage-root` | `select` | `Lineage root` | Set the root filter. |
| `select-lineage-agent` | `button` | `Select lineage {agent-key}` | Show parents, operator, inherited units and changed rules. |
| `expand-lineage-agent` | `button` | `Expand lineage {agent-key}` | Expose children and expanded state. |
| `collapse-lineage-agent` | `button` | `Collapse lineage {agent-key}` | Hide descendants and restore parent focus if needed. |
| `open-lineage-agent` | `a` | `Inspect lineage {agent-key}` | Navigate to the selected agent's detail. |
| `reset-lineage` | `button` | `Reset lineage filters` | Reset filter and selection to the root. |
| `expand-next-generation` | `button` | `Show next lineage generation` | Reveal the next bounded group. |

`[K0 decision]` Initially expand roots and their immediate children. Each expansion adds at most **50 actionable agent entries [TARGET]**; further entries remain available through the named continuation control. The **200-agent fixture [TARGET]** must remain navigable without rendering all controls at once. A lone root says `Genesis agent. No descendants yet.` A layout failure says `Tree drawing unavailable. Use the lineage list.` and preserves the complete structured relation data. Every parent-to-child edge and breeding operator is readable as text.

### Arena-list actions

| Action | Element | Accessible name | Effect |
|---|---|---|---|
| `filter-bench-query` | `input search` | `Find benchmarks` | Filter loaded benchmark identities. |
| `filter-bench-purpose` | `select` | `Filter benchmarks by purpose` | Filter `select` or `confirm`. |
| `filter-bench-state` | `select` | `Filter benchmarks by state` | Filter the public benchmark state. |
| `clear-bench-filters` | `button` | `Clear benchmark filters` | Clear filters and URL state. |
| `declare-benchmark` | `button` | `Declare benchmark` | Open Declare; Confirm calls `bench_declare`. |
| `open-benchmark` | `a` | `Open benchmark {bench-key}` | Navigate to benchmark detail. |
| `page-benches` | `button` | `Load more benchmarks` | Continue `bench_list`. |

### Benchmark-detail actions

| Action | Element | Accessible name | Effect |
|---|---|---|---|
| `show-bench-rule` | `button` | `Benchmark rule {bench-key}` | Expand the already-declared immutable rule. |
| `launch-benchmark` | `button` | `Launch benchmark {bench-key}` | Open Launch; Confirm calls `bench_run`. |
| `refresh-benchmark` | `button` | `Refresh benchmark {bench-key}` | Read `bench_status`. |
| `inspect-bench-result` | `button` | `Task result {run-key}` | Inspect the result tied to this actual run. |
| `open-bench-run` | `button` | `Inspect benchmark run {run-key}` | Inspect the run record. |
| `open-task-evidence` | `a` | `Task evidence {run-key}` | Navigate to the witnessing event in Ledger; retain the link on a failed task. |
| `evaluate-benchmark` | `button` | `Evaluate benchmark {bench-key}` | Call `bench_verdict`; verify any new verdict event. |
| `promote-candidate` | `button` | `Promote candidate {agent-key}` | Open Promote with the candidate fixed. |

Launch stays disabled until the declaration, credit rule, bank hash, purpose and memory arms have been displayed successfully. A disclosure may collapse details afterwards but cannot erase their summary. `Queued`, `Running`, `Stalled`, `Complete` and `Declared` are distinct text. Task outcomes preserve `ADMIT`, `HOLD`, `red`, `green`, `error`; benchmark decisions preserve `superior`, `not_superior`, `inconclusive`. Held-out tasks display `Held out — confirmation only`. Synthetic-bank results carry `Synthetic offline benchmark` and imply no real-seat or memory-benefit claim.

### Ledger actions

| Action | Element | Accessible name | Effect |
|---|---|---|---|
| `filter-ledger-query` | `input search` | `Find ledger events` | Filter loaded event content locally; identify incomplete search coverage. |
| `filter-ledger-agent` | `select` | `Filter ledger by agent` | Use the `agent_id` cursor filter. |
| `filter-ledger-kind` | `select` | `Filter ledger by kind` | Use the `kinds` cursor filter. |
| `clear-ledger-filters` | `button` | `Clear ledger filters` | Clear filters without losing an acknowledged revision. |
| `page-events` | `button` | `Load more events` | Read the next cursor page. |
| `toggle-event-hash` | `button` | `Event hashes {event-key}` | Expand `sha256` and `prev_sha256`. |
| `toggle-event-payload` | `button` | `Event payload {event-key}` | Expand escaped payload and evidence metadata. |
| `verify-ledger` | `button` | `Verify ledger chain` | Call `ledger_verify`; show the verified head and drift result. |
| `export-ledger` | `button` | `Export ledger` | Open Export; Confirm calls `ledger_export`. |
| `resync-ledger` | `button` | `Resync ledger` | Restart a cursor after the visible resync warning. |
| `open-event-agent` | `a` | `Agent for event {event-key}` | Navigate to the event's agent; omit for non-agent actors. |

Use **100 events per page [TARGET]** for the **10,000-event fixture [TARGET]**. Pagination, retry and resync preserve filter values. An event link carries its full event ID; resolving an event that has not been loaded must use cursor reads, not a new HTTP endpoint. Raw payloads and paths are passive text, never injected HTML, executable commands or automatic navigation targets.

### Shared dialogs, inspectors and form controls

| Action | Element | Accessible name | Effect |
|---|---|---|---|
| `submit-dialog` | `button` | `Confirm {form label}` | Validate and submit the named documented operation. |
| `cancel-dialog` | `button` | `Cancel {form label}` | Close the form without dispatch; preserve its recoverable draft. |
| `edit-field` | `input` or `select` | `{field prefix} {field label}` | Edit one named field from the registry. |
| `add-item` | `button` | `Add {collection label}` | Add a validated draft collection item locally. |
| `remove-item` | `button` | `Remove {collection label} {item-key}` | Remove a draft item locally; never retire a persisted object. |
| `select-unit` | `input checkbox` | `Inherit unit {unit-key}` | Select an eligible unit in Derive. |
| `select-skill` | `input checkbox` | `Pin skill {skill-key}` | Select a content-addressed skill pin. |
| `select-rule` | `input checkbox` | `Use rule {rule-key}` | Select a permitted overlay rule. |
| `select-parent` | `input checkbox` | `Cross parent {agent-key}` | Select the other compatible parent. |
| `select-bench-agent` | `input checkbox` | `Benchmark agent {agent-key}` | Select a declared benchmark participant. |
| `select-seat` | `input checkbox` | `Allow seat {seat-key}` | Select the complete allowed seat tuple. |
| `close-inspector` | `button` | `Close {inspector label}` | Close a read-only inspector and restore the invoker. |

`[K0 decision]` Only one modal is exposed at a time. A form uses a labelled `dialog` container with modal semantics; all its controls remain native. Form labels/prefixes are respectively: `Create agent`/`Create`, `Derive agent`/`Derive`, `Write memory`/`Memory`, `Open run`/`Run start`, `Close run`/`Run close`, `Check memory`/`Resume`, `Declare benchmark`/`Declare`, `Launch benchmark`/`Launch`, `Promote agent`/`Promote`, `Retire agent`/`Retire`, `Export ledger`/`Export`. Its dialog name appends the target entity key where a target exists. Inspector labels are `agent comparison`, `agent brief`, `reference`, `skill`, `memory unit`, `memory history`, `run`, `task result`; the dialog name also appends the selected identity key, when applicable.

The field registry is exhaustive at the semantic-name level. Dotted paths below address form models; serializers map them to the exact closed tool schema. A field's `name` is the literal listed path. Input type is text unless an enum uses `select`, a count uses `number`, or a boolean uses `checkbox`. Native validation never replaces server validation. Visible labels use the field-label column; help text explains provenance, units and constraints. No arbitrary JSON editor is required for an ordinary workflow.

| Form | Semantic names | Field labels in the same order |
|---|---|---|
| Create | `agent_id`, `display_name`, `workflow`, `language` | `Agent ID`, `Display name`, `Workflow`, `Language` |
| Create / seat draft | `seat.model`, `seat.effort`, `seat.mode` | `Seat model`, `Seat effort`, `Seat mode` |
| Derive | `operation`, `child_id`, `display_name`, `language` | `Operator`, `Child ID`, `Display name`, `Language` |
| Derive / mutation | `change.kind`, `change.skill_id`, `change.from_sha256`, `change.to.skill_id`, `change.to.sha256`, `change.rule_id`, `change.text` | `Change kind`, `Changed skill`, `Previous skill hash`, `Replacement skill`, `Replacement hash`, `Changed rule`, `Rule text` |
| Memory | `unit.id`, `unit.kind`, `unit.level`, `unit.statement`, `unit.privacy`, `unit.status`, `unit.scope.workflow`, `unit.scope.language`, `run_id` | `Unit ID`, `Kind`, `Level`, `Statement`, `Privacy`, `Unit status`, `Workflow`, `Language`, `Run ID` |
| Memory / provenance | `unit.provenance.origin` | `Origin` |
| Memory / lesson | `unit.body.tempting_use`, `unit.body.failure_mode`, `unit.body.safer_action`, `unit.body.blocked_use` | `Tempting use`, `Failure mode`, `Safer action`, `Blocked uses` |
| Memory / negative | `unit.body.gate_id`, `unit.body.verdict`, `unit.body.cause`, `unit.body.coordinate`, `unit.body.safer_action` | `Gate ID`, `Verdict`, `Cause`, `Coordinate`, `Safer action` |
| Memory / workflow | `unit.body.trigger_sig`, `unit.body.steps`, `unit.body.stats`, `unit.body.status` | `Trigger`, `Steps`, `Statistics`, `Workflow status` |
| Memory / episode | `unit.body.run_id`, `unit.body.task_id`, `unit.body.seat.model`, `unit.body.seat.effort`, `unit.body.seat.mode`, `unit.body.outcome.verdict`, `unit.body.outcome.repair_loops`, `unit.body.outcome.findings.confirmed`, `unit.body.outcome.findings.refuted`, `unit.body.cost.tokens_in`, `unit.body.cost.tokens_out`, `unit.body.cost.tokens_cache`, `unit.body.cost.duration_ms`, `unit.body.cost.cost_micro_usd` | `Episode run`, `Episode task`, `Seat model`, `Seat effort`, `Seat mode`, `Outcome`, `Repair loops`, `Confirmed findings`, `Refuted findings`, `Input tokens`, `Output tokens`, `Cached tokens`, `Duration ms`, `Cost micro USD` |
| Memory / decision | `unit.body.reason` | `Reason` |
| Memory / open item | `unit.body.class`, `unit.body.order`, `unit.body.trigger` | `Item class`, `Item order`, `Item trigger` |
| Memory / artifact draft | `receipt.path`, `receipt.sha256` | `Evidence path`, `Evidence hash` |
| Run start | `run_id`, `seat.model`, `seat.effort`, `seat.mode`, `task.id`, `task.kind`, `task.language`, `task.bank_id`, `task.bench_id`, `task.split`, `memory_arm` | `Run ID`, `Seat model`, `Seat effort`, `Seat mode`, `Task ID`, `Task kind`, `Task language`, `Bank ID`, `Benchmark ID`, `Task split`, `Memory arm` |
| Run close | `outcome.verdict`, `outcome.repair_loops`, `outcome.findings.confirmed`, `outcome.findings.refuted`, `cost.tokens_in`, `cost.tokens_out`, `cost.tokens_cache`, `cost.duration_ms`, `cost.cost_micro_usd` | `Outcome`, `Repair loops`, `Confirmed findings`, `Refuted findings`, `Input tokens`, `Output tokens`, `Cached tokens`, `Duration ms`, `Cost micro USD` |
| Run close / artifact draft | `evidence.path`, `evidence.sha256` | `Evidence path`, `Evidence hash` |
| Resume | `observed` | `Observed memory values` |
| Declare | `declaration.bench_id`, `declaration.bank_id`, `declaration.bank_sha256`, `declaration.protocol`, `declaration.purpose`, `declaration.agents`, `declaration.seats`, `declaration.memory_arms`, `declaration.credit_rule`, `declaration.sprt.p0`, `declaration.sprt.p1`, `declaration.sprt.alpha`, `declaration.sprt.beta`, `declaration.sprt.cap`, `declaration.promotion.n_shadow_runs` | `Benchmark ID`, `Bank ID`, `Bank hash`, `Protocol`, `Purpose`, `Agents`, `Seats`, `Memory arms`, `Credit rule`, `Null probability`, `Alternative probability`, `Alpha`, `Beta`, `Task cap`, `Clean shadow runs` |
| Launch | `runner` | `Runner` |
| Promote | `bench_id` | `Benchmark ID` |
| Retire | `reason` | `Reason` |
| Export | `out` | `Export directory` |

Structured fields (`observed`, statistics, steps, credit rule, runner) are compound groups: render their schema-defined leaves as native inputs/selects using the parent semantic name plus the leaf property. Leaf labels are human-readable property names; a repeated label adds its group label. If the resulting name exceeds the byte budget, use `{field prefix} Field {field-key}` with the full path and human label in its visible description. This is a deterministic naming rule, not permission to send unknown keys. Enumerations, required leaves, bounds and nullability come from `docs/CONTRACT.md` and the corresponding schema; unsupported compound shapes block submission.

Collection labels are `skills`, `seats`, `rules`, `units`, `parents`, `evidence`, `steps`, `blocked uses`, `parent context`, `supersedes`, `agents`, `memory arms`. Collection items are keyed by full natural identity (skill pin, seat tuple, rule ID, unit ID, agent ID or evidence path), not index. A collection has one uncommitted item editor using `<collection>.new`; committed editor names use `<collection>.<item-key>.<property>` [K0 decision]. A removed item's focus goes to the collection's Add button. Parent-context items expose agent ID, version and run ID. References are fixed verified pins, selected skills are pinned packages, provenance actor is the asserted actor, and derived `inherited_from` is never editable. Hidden schema constants and operation IDs are generated, not extra controls. Costs offer an explicit unknown choice that serializes as `null`.

## Tool boundary and observable postconditions

All tool names below are exactly the public names from `docs/CONTRACT.md`. Successful HTTP results unwrap only `untrusted`; failures preserve `ok:false`, `code` and optional `detail`. A semantic failure body must never be treated as success because HTTP completed.

| Public tools | UI binding |
|---|---|
| `reference_get`, `reference_verify` | Reference read/verify actions in Constitution and creation preflight. |
| `skill_list`, `skill_get` | Create/derive skill choices and pinned-skill inspector. |
| `skill_publish`, `skill_retire` | Headless catalogue administration; no dedicated v1 screen control [K0 decision]. |
| `agent_create`, `agent_get`, `agent_list`, `agent_brief` | Agents list, Create, agent detail, comparison and brief. |
| `agent_clone`, `agent_distill`, `agent_cross`, `agent_mutate`, `agent_specialize` | Derive operator choices with a read-only preview of changed/inherited/rejected context. |
| `agent_retire`, `lineage_tree` | Retire and structured Lineage. |
| `memory_put`, `memory_route`, `memory_get`, `memory_bootcheck`, `memory_history` | Write, search, inspect, resume and history. Level one is not a write choice. |
| `run_open`, `run_beat`, `run_close`, `run_get` | Run start, heartbeat, gated close and inspector. |
| `bench_list`, `bench_declare`, `bench_run`, `bench_status`, `bench_verdict`, `agent_promote` | Arena list, Declare, Launch, refresh, evaluate and Promote. |
| `scorecard_get`, `ledger_events`, `ledger_export`, `ledger_verify` | Per-seat/per-arm scorecard, cursor reads, Export and chain verification. |
| `openfresnel_probe`, `openfresnel_spawn` | Headless bridge operations; no dedicated v1 screen control [K0 decision]. A returned `launched` is never an app completion. |

`[K0 decision]` Mutation forms retain a generated `op_id` with the draft and reuse it for an unchanged retry. A user edit after submission starts a new operation. A transport failure leaves the prior result uncertain until idempotent replay or a ledger witness resolves it. The request includes the full asserted actor and, when supported, the last acknowledged `expected_head`. Keep the process session token in memory; send `X-Lineage-Session`, JSON content type and the same-origin `Origin` required by `docs/CONTRACT.md`. Never store a token in fixtures, URL state, a draft or exported content. Error detail is escaped text.

| Operation | Required postcondition | Rejection postcondition |
|---|---|---|
| Create / derive | Corresponding `agent.born` event; `agent_get` confirms full child ID, version and parents. | No born event; preserve draft and show the exact error. |
| Memory write | `memory.put` event with the selected owner/run, unit hash and valid receipts; `memory_get` agrees. | No memory event; display `forbidden_level`, `hash_mismatch`, `memory_debt` or the actual error. |
| Run start / beat / close | Matching `run.open`, `run.beat` or `run.close`; `run_get` confirms lifecycle and closing gate. | A refused close leaves the run open. `memory_required` and `memory_debt` are visible separately. |
| Declare / launch / evaluate | `bench.declared`, task runs and available `bench.result`/`bench.verdict` events agree with `bench_status`. Launching may remain running. | A missing declaration or held-out selection is rejected; do not fabricate a verdict. |
| Retire / promote | Matching `agent.status` event; `agent_get` confirms the folded status and benchmark witness when needed. | Do not optimistically change status on rejection. |
| Export / verify | Validate the documented export result or verification result and reported head. These reads/projections need not append an event. | A filesystem acknowledgement does not assert journal or projection integrity. |

If `ledger_events` reports `resync:true`, show a warning, keep the filters and offer `resync-ledger`. Do not declare an unseen mutation failed merely because its event is outside the currently loaded page. Mutation checks must read far enough to establish the operation's commit witness. There is no UI path for editing a scorecard, journal event, level-one ruling, held-out credit rule or agent status directly.

## Keyboard, focus and URL state

| Key / transition | Required behavior |
|---|---|
| Tab / Shift+Tab | Native focus order follows the visible reading order. In a modal it cycles through modal controls only. |
| Enter | Activate a focused link or button. In a form, submit only through its defined submit behavior after validation; filtering never dispatches a mutation. |
| Space | Activate a focused native button or toggle a checkbox. |
| Arrow keys / Home / End | Native select/input behavior. The lineage nested list does not claim a custom tree-widget key map. |
| Escape | Close the active form/inspector without dispatch; restore its invoker. No modal means no destructive action. |
| Skip link activation | Move focus to `main-content`, retaining the route. |
| Route change | Focus the active `h1` after its first fold; restore the stored identity when returning through history where available. |
| Refresh / sort / new cursor page | Keep focus, selection and expansion by full entity ID and action name. If the entity disappears, focus the containing panel heading and announce its removal. |
| Validation failure | Keep the draft, focus the first invalid field, associate its error text, and announce refusal once. |
| Modal open / close | Focus the first meaningful editable field, or the least consequential action in a confirmation. Make background inert. Restore the invoker; if removed, focus its panel heading. |

`[K0 decision]` No global single-letter shortcuts are required. This avoids intercepting text entry and preserves native assistive-technology shortcuts. Every pointer action has a named keyboard equivalent in the action registry.

`[K0 decision]` Hash-route query keys are: Agents `q,workflow,language,status,retired,sort,compare`; Agent `panel,kind,level,privacy,inheritable,seat,arm`; Lineage `root,q,selected`; Arena `q,purpose,state`; Benchmark `rule`; Ledger `q,agent,kind,event`. Encode full IDs with standard URL encoding; encode compound values canonically. Ignore unknown query keys with a visible notice. Invalid values reset only their own field. Back/forward and reload restore the documented filters, selected panel and entity, never an unrelated entity. Cursor offsets, session tokens and mutation payloads are not URL state. A failed Create draft may persist locally under a versioned draft key, retaining its `op_id`; do not persist memory bodies, secrets or tokens. Reload offers draft recovery before any submission.

## Status, readiness and visual rules

The shell owns one persistent status region named `Application updates`, with polite, atomic announcements. Each failure panel has an ordinary named heading and linked field descriptions; it does not create another live region. Untrusted statements, names and errors are rendered as text.

| Trigger | Exact message template |
|---|---|
| Initial load | `Loading {screen label}.` |
| First fold / route ready | `{screen label} ready.` |
| Empty list | `No agents yet.`, `No benchmarks yet.`, `No ledger events yet.`, `No memory units yet.` or `No runs yet.` |
| Filter with no matches | `No matching {record label}. Clear filters to see all loaded records.` |
| Stale reads | `Data is stale. Last confirmed revision {rev}.` |
| Panel error | `{panel label} unavailable. Retry to continue.` |
| Pending mutation | `{operation label} pending.` |
| Committed mutation | `{operation label} recorded for {entity-key}.` |
| Domain refusal | `{operation label} refused: {code}.` |
| Close without memory | `Close run refused: memory_required. Run remains open.` |
| Failure-memory debt | `Close run refused: memory_debt. Run remains open.` |
| Lifecycle transition | `Run {run-key}: {lifecycle}.` |
| Verdict transition | `Benchmark {bench-key}: {decision}.` |
| Cursor resync | `Ledger changed. Resync required; filters kept.` |
| Record removed | `{entity-key} is no longer in this view.` |
| Fixture view | `Synthetic fixtures. Changes are unavailable.` |

Record labels are `agents`, `benchmarks`, `events`, `memory units` or `runs`; operation labels are `Create agent`, `Derive agent`, `Write memory`, `Open run`, `Record heartbeat`, `Close run`, `Declare benchmark`, `Launch benchmark`, `Evaluate benchmark`, `Retire agent`, `Promote agent`, `Export ledger`. Close-refusal wording takes precedence over the generic refusal. Loading/empty/error text appears in its panel as well as any applicable announcement. Debounce identical transition messages by full entity ID plus its transition event ID or revision; unchanged polling responses produce no new announcement. Multiple genuine transitions are announced in Lamport order. Business status uses descriptions, not a volatile accessible control name.

On navigation set readiness false until that route's initial fold completes. Publish the active screen's DOM and decimal `data-lin-rev` from the same acknowledged snapshot, then set readiness true. A legitimately empty journal has revision zero; an unknown head is absent, never zero. On initial failure keep readiness false and expose the named error/Retry. A later panel failure can retain the previously folded screen, its old revision and readiness true, but must show Stale and the failed panel. `aria-busy` reflects active loading. Automation waits for readiness and its expected entity/revision/error predicate; fixed sleeps are not acceptance conditions.

The viewport matrix is **390×844, 768×1024 and 1440×900 CSS pixels [TARGET]**, plus **200% zoom [TARGET]**. Test both themes and reduced motion. Compute foreground/background contrast from the actual token pairs at **4.5:1 minimum [TARGET]**; include labels, help, errors and disabled-state explanations. Focus remains visible and unobscured. Statements and hexadecimal hashes wrap with bounded cards/panels. No document-level horizontal overflow; a data table may use a labelled keyboard-reachable scrolling container while retaining readable column headings. Layout cannot depend on animation finishing; reduced motion removes nonessential movement.

## Deterministic fixtures and clock

`fixtures/ui/README.md` is the fixture manifest contract for U21–U27. K0b defines the set; it does not create or certify fixture payloads. Fixture mode is visibly synthetic and read-only: `serve --fixtures fixtures/ui` supplies reads and rejects all journal/external mutations and exports with `fixture_readonly`. Disable mutating controls with a visible explanation; keep contract tests that submit a direct request and prove server refusal. A fixture must never mutate the real runtime home.

Successful mutation journeys use a separately seeded fresh runtime home and the real shared dispatcher, not the static fixture server. U29 supplies that seed. Public reads and journal events establish postconditions for CDP, AT-SPI and capsules alike. A simulated transition sequence is useful for rendering tests and remains explicitly labelled synthetic.

`[K0 decision]` Use fixed locale `en-GB`, timezone `UTC`, stable ordering, fixed initial theme, deterministic IDs and a presentation clock supplied by the fixture manifest. Render elapsed time from that clock; do not sample the host time or a random generator in fixture mode. Advance the virtual clock only when the harness selects a declared frame. Record viewport, device scale, theme, motion setting, scenario, frame and ledger revision in external capture metadata. Fonts use the system stack with an identical pinned capture environment; do not download assets or introduce a product-only visual testing API.

## Independent verification

These are probe contracts for `tools/qa/` and `tests/operability/`, not claims that those files already exist. `[K0 decision]` Probe exit codes are **0 PASS, 1 FAIL, 2 INCONCLUSIVE [TARGET]**. Keep raw observations and transformed observations separately. Missing or truncated evidence cannot satisfy a required action set.

| Method | Required procedure and witness | Rejecting contrast |
|---|---|---|
| C — CDP pipe | Launch an owned Chrome with `--remote-debugging-pipe`, a dedicated profile and a deterministic fixture/live seed. Read standard DOM and accessibility trees, computed geometry, console exceptions and focus. Wait on readiness predicates; resolve every expected action, exercise the keyboard journey and compare semantic postconditions with public reads. | Hostile pages must fail for an article-contained control, duplicate names, an over-budget name, clickable generic container, positional selector, stale-ready flag or missing ledger witness. |
| A — AT-SPI | Run Chrome with `--force-renderer-accessibility` on a private Xvfb display and session bus. Use `gi.repository.Atspi` to find the actual document, enumerate roles/names/states and activate the required controls independently of CDP. Save browser/process association, raw tree, truncation status and required-versus-observed action set. | No document, an empty tree, unavailable bus or incomplete traversal is INCONCLUSIVE, never PASS. An observed document missing an expected control is FAIL. |
| P — prune survival | Compare the raw accessible action set to a clean-room transform implementing the supplied opaque `article` boundary, normalized names and allowed state vocabulary. Required headings/buttons must survive. This transform is not a replacement for A. | An interactive descendant of an opaque article must disappear in the negative fixture and cause gate failure. Duplicate or clipped identity targets also fail. |
| V — vision capsule | Use an isolated capsule per tester. Observe, act through a fresh observed target, declare expected change, and check the resulting named state. Keep `vis.receipt/v1` with `pass`, `fail` or `refused`, frame SHA-256 values, run/step identity and observer reference pins. Cross-check a mutation with `ledger_events`. | A changed frame alone, expired target handle, missing frame hash, absent state check or acknowledgement without domain evidence cannot PASS. Image-only semantic judgement remains AUSENTE. |

Each screen must have a C and A action inventory and a P required-action comparison; V supplies frame evidence for a representative journey. Fixture-only screens have no pretend mutation receipt. The persona journeys use the real application and public docs (`docs/QUICKSTART.md`, `docs/UI_GUIDE.md`, `docs/HEADLESS.md`) in separate capsules. Their **8/10 score each [TARGET]** is NS6 acceptance evidence supplied later, not a K0 result.

| Screen | Minimum journey | Required semantic witness |
|---|---|---|
| Agents | Filter, clear, open an agent, compare, Create in a fresh live home. | Identity survives duplicate display names; creation has its born event. |
| Agent | Inspect constitution/reference, skill, unit and scorecard; open a run; reject close without memory; write required memory and close. | No-memory run remains open; valid closure has a gate-passed close event. |
| Lineage | Select root, expand child, inspect inheritance and operator; navigate through the list with the SVG unavailable. | Parent/child and rejection data agree with `lineage_tree` and agent reads. |
| Arena | Inspect a declaration, verify held-out purpose and launch a synthetic offline benchmark in a live home. | Rule precedes result; actual task runs pass the memory gate. |
| Benchmark | Inspect task failure/evidence, refresh verdict, attempt an ineligible promotion. | Evidence survives failure; refusal leaves status unchanged. |
| Ledger | Filter, page, expand hashes, handle resync, verify and export in a live home. | Cursor and verified head agree; export is checked independently. |

### Wire/schema dependencies

| Repository file | Operability dependency |
|---|---|
| `schemas/event.schema.json` | Event IDs, kinds, ordering, actor and evidence for postconditions. |
| `schemas/agent.schema.json` | Full identity, allowed seats, version, status, parents and pins. |
| `schemas/run.schema.json` | Task, seat, outcome, null costs, memory arm and closing gate. |
| `schemas/mem_unit.schema.json` | Kind bodies, levels, privacy, receipts and inheritance provenance. |
| `schemas/family_envelope.schema.json` | Program-to-program parity; UI does not construct a separate domain model. |
| `schemas/family_receipt.schema.json` | Success/error distinction across parity journeys. |
| `schemas/bench_declared.schema.json` | Predeclared credit, protocol, purpose and memory arms. |
| `schemas/tool_error.schema.json` | Exact visible error code; no invented success fallback. |

Before acceptance, compare the implemented action/field inventory to this document, run the negative fixtures, and record separate C/A/P/V verdicts. Runtime operability remains unproven until those witnesses exist. This mandate is scoped to the supplied Lineage North Star, strategy, K0 rules, seed conventions and public K0 contract corpus.
<!-- U27-APPENDIX:BEGIN -->

## U27 verification appendix

This appendix adds instruments, not acceptance evidence. The exact bytes before
the delimiter line are the frozen K0 input. Its SHA-256 is
`06d87b1e36a6a39f7627ed461a4078e1c3162bf3b4ce3ae9b199cc91c0a3b197`
[CITED: frozen oracle]. Copying the document or adding verification prose cannot
change the extracted registry. `load_contract` refuses an unknown frozen prefix.
The completed document has its own artifact hash, separate from this pin.

### Public commands and prerequisites

Run from the repository root. Supply an existing browser executable, disposable
loopback target, prepared inventory and positive explicit deadline; there is no
observer download, port fallback or automatic installation.

```sh
python3 -m tools.qa.cdp_probe --url '<loopback-url>' --browser '<browser-executable>' --inventory '<inventory.json>' --contract docs/OPERABILITY.md --timeout-ms '<positive-integer>'
python3 -m tools.qa.atspi_probe --url '<loopback-url>' --browser '<browser-executable>' --xvfb '<Xvfb-executable>' --session-bus '<dbus-daemon-executable>' --inventory '<inventory.json>' --contract docs/OPERABILITY.md --timeout-ms '<positive-integer>' --node-limit '<positive-integer>'
python3 -m tools.qa.prune --observation '<observation.json>' --inventory '<inventory.json>' --contract docs/OPERABILITY.md
python3 -m unittest discover -s tests/operability -t .
```

C requires a Chromium implementation of inherited debugging pipes. A requires
Xvfb with `-displayfd`, foreground `dbus-daemon` with `--print-address=1`, and the
existing Python GI/Atspi installation. GI is imported only for native work; pure
self-tests need none of these observers. A provisions its own display, bus and
profile. A new interpreter isolates the native bus connection. A never uses C to
observe or act. The session-bus argument is specifically a `dbus-daemon`
executable, not shell text or a command template.

A caller may select a disposable external artifact directory using
`LINEAGE_QA_ARTIFACT_ROOT`. C writes separate structural DOM and raw CDP AX JSON
there, using opaque digest-based relative references. The DOM snapshot excludes
session-token metadata. Raw captures can contain untrusted application text;
they require private storage and publication review. An unset directory does not
produce pretend artifacts: the evidence check is INCONCLUSIVE. Runtime profiles
are disposable; they are never evidence references or selectors. Public reports
redact local paths, network names and credential-like text and escape markup.

The test oracle's real-browser class is opt-in through `U27_BROWSER` and
`U27_SELFTEST_ORIGIN`; the latter must already serve the frozen HTML specimens.
Default discovery performs no network work and reports observer skips explicitly
as INCONCLUSIVE. A passing pure test suite does not establish W5/W6/W7/W8, live
operability, external interoperability, persona quality or inherited-memory gain.

### Closed boundaries and truthful reduction

`tools/qa/inventory.schema.json` and `tools/qa/report.schema.json` are the local
closed schemas. Report schema `$defs` also define Node, Observation, Check,
Artifact and Postcondition. Strict UTF-8 decoding rejects duplicate keys,
surrogates, nonfinite numbers, trailing values and Boolean integers. Canonical
bytes use the integrated `lineage.core.journal.canonical_bytes`; decoding uses
`lineage.core.schema.strict_loads`, whose current input limit is 65,536 bytes
[CITED: integrated source]. No process-wide decoder limit is changed.

The report envelope is `lineage.qa.report/v1`. Exit/status pairs are
`0/PASS`, `1/FAIL`, `2/INCONCLUSIVE` [CITED: K0]. Known failures dominate gaps,
and every individual diagnosis remains present. Empty checks, missing required
actions, missing observers, incomplete trees, unverified cleanup and unavailable
artifacts cannot give PASS. Methods C/A/P/V and scopes selftest/fixture/live are
independent. Scope always comes from the validated input, never from a successful
observation under another method or another scope.

Helper boundaries use the following exact shapes; no additional fields are
emitted. The closed Check and Report shapes are as defined above.

| Boundary | Shape and interpretation |
|---|---|
| `load_contract` | `{sha256,actions,fields,screens,entities,states}`. `actions` maps the literal action to `{action,element,name}`; `fields` maps a literal form label to its semantic field-name array. Registry maps are bounded by the pinned frozen document. |
| `source_inventory` | `{complete,records,checks}`; each record is `{attribute,value,path,line}` with repository-relative path. Unresolved computations leave completeness false. |
| `compare_inventory` | Check array; compares each route/dialog context and full action/entity/id/role/name/availability tuples. Missing contexts are not silently omitted. |
| `prune.transform` | Node array. Parent links point to the nearest retained ancestor, or null. Input is never modified. |
| `prune.compare` | P Report with selftest scope; required entries are full Node snapshots selected from a forest, not an independently traversable forest. Comparison ignores observer-local IDs and binds role/name/entity/entity_id/action. |
| `prune.main` | Derives required action Nodes from every non-absent Inventory action. Full required heading/route evidence must additionally be supplied by the observation campaign; action inventory alone is not full screen acceptance. |
| `check_postcondition` | Check. This is a semantic witness helper: immutable event envelopes, event/prefix hashes, operation identity, committed record and corresponding read must agree. A semantic PASS alone is not full wire-schema acceptance. |
| `verify_capsule` | V Report with selftest scope. Without a pinned external receipt schema/trust root it refuses admission; it never infers a receipt shape from a supplied success flag. |

`validate_wire` is a private adaptation layer over the integrated mini-validator.
It evaluates local references, compositions, conditional payloads, closed objects
and numeric constraints that the integrated validator does not itself support.
Network reference resolution is forbidden. Full wire validation must precede a
live witness admission. The frozen synthetic postcondition examples omit
mandatory kind-specific event fields, including the complete run-open payload
and run-close `memory_receipts`/`gate`; their semantic helper result cannot stand
in for full event-schema acceptance. Likewise static inventory validation checks
name-template syntax, while observer checks enforce the actual identity key and
computed name. The frozen good specimen contains conflicting record-control
names; it cannot establish a positive runtime name-uniqueness witness as supplied.

For UI-generated operation identities, bind an independently captured public
request by tool, actor, entity and run before calling the helper with its observed
`op_id`. A null static `op_id` remains unbound evidence, never a wildcard commit.
Refusal checks need exact error, before/after state and complete relevant history.
Projection checks need verified head and independent manifest verification.
Compound benchmark operations require actual suboperation commits; the helper
does not invent a root event. Cursor and resync integration remain separate.

### Canonical observation and process ownership

Canonical roles are `article`, `group`, `document`, `heading`, `button`, `link`,
`textbox`, `searchbox`, `combobox`, `checkbox`, `radio`, `option`, `list`,
`listitem`, `navigation`, `banner`, `main`, `status`, `dialog`, `table`, `row`,
`cell`, `columnheader`, `rowheader`, `text`, `separator`, `generic`, `spinbutton`
and `img`. CDP retains its canonical role facts; unknown roles remain observable
rather than acquiring guessed semantics. Native mappings are explicit in
`ROLE_MAP`: `push button` becomes `button`, `document web`/`document frame` become
`document`, `entry` becomes `textbox`, `check box` becomes `checkbox`,
`combo box` becomes `combobox`, `list item` becomes `listitem`, static/label/text
become `text`, and section/panel/frame/application/desktop/landmark become `group`.
Unmapped native names remain raw facts, not a certification of a general role map.

The transform removes article and its entire subtree. Group, generic, document,
text, image and separator containers are transparent; other canonical roles and
actionable controls are retained. Names are normalized before measuring their
byte budget and are never clipped or deduplicated. Unknown normalized states are
rejected; unrelated raw platform flags remain separate from K0 product states.
Native raw snapshots are retained in `RAW_OBSERVATIONS` by opaque content digest
for in-process callers; this is not a durable native artifact receipt.

The transport maps inherited descriptors 3/4 [CITED: Chromium pipe protocol]
through an exec trampoline, uses NUL JSON frames, monotonic deadlines, request
IDs and flattened session IDs. It injects `--remote-debugging-pipe` and rejects
port flags. `PipeError` carries only a QA diagnostic, with no private protocol
text. `Target.setAutoAttach` and explicit flattened page attachment associate
the owned page. Loopback origins and navigation redirects are checked; unsafe
requests are blocked before dispatch. Reload/structural changes require new
DOM/AX handles. No inventory string becomes executable browser code or shell.

Only recorded owned child processes with verified PID greater than 1 [TARGET]
are terminated and reaped. No process-group operation or broad process matching
is used. Failure to verify cleanup changes the verdict. Private native traversal
has an explicit node ceiling and deadline; cycles, unreadable children, missing
documents and empty documents remain incomplete evidence.

### Coverage register and limitations

| Requirement group | Available instrument / remaining witness |
|---|---|
| O1–O6; OC1–OC16 semantics | C structural/computed AX checks, native enumeration, pure identity and prune checks. Complete source/runtime context equality still needs the prepared route/dialog matrix. |
| O7–O8 | C keyboard skip-link check and status shape. Complete modal, focus continuity and ordered lifecycle announcement journeys remain INCONCLUSIVE. |
| O9–O11 | Readiness/revision comparisons and semantic witness checks. Real HTTP token/actor/refusal, memory close, cursor and authoritative request/read journeys need prepared live evidence. |
| O12 | Actual snapshot geometry is recorded. Full theme/motion/effective-zoom/contrast matrix remains INCONCLUSIVE. |
| O13–O14; OC21–OC27 | Distinct C/A/P observations and explicit missing evidence. Durable raw native artifacts, independent native activation, manifest clock/frame repeatability and full route coverage remain INCONCLUSIVE. |
| OC17–OC20, OC28 | Dependency/integration obligations, not added transports or external integration permission. |
| OC29–OC30 | Capsule/persona admission and public safety; no publication or fabricated scores. |

The required context set remains agents, agent, lineage, arena, bench and ledger,
plus every applicable active dialog. Missing implementations or prepared contexts
must stay listed, and no screen may be deleted from the required inventory.
Fixtures are read-only; synthetic HTML is always selftest scope. Existing fixture
selection conventions are consumed without inventing a testing endpoint.

TSX extraction is deliberately conservative: quoted literal JSX attributes and
quoted constant attribute expressions are recorded, comments are excluded and
computed expressions/spreads/DOM-builder APIs mark extraction incomplete. It is
not an AST claim and does not resolve arbitrary TypeScript. Runtime corroboration
is necessary for those declarations.

For a later complete rendered gate, use real layout viewport reflow at the
specified effective zoom, not a device-scale-only screenshot. Alpha composite
foreground and ancestor backgrounds to an opaque canvas, convert sRGB channels
to linear luminance and compare actual text/background token pairs. Labels,
help, errors and disabled explanations remain in the required element scope.
The present probe does not certify this matrix; the precise campaign zoom and
capture pins remain unavailable. No source-only or image-only PASS substitutes.

The exact external `vis.receipt/v1` schema, authenticated observer pins,
J1–J8 definitions and SC1–SC8 weights are AUSENTE — no inventar. Therefore no
positive capsule receipt, persona arithmetic or score is synthesized. Relative
artifact refs reject traversal, empty segments, backslashes and symlinks;
file-byte and canonical-JSON digests are recomputed separately. Pixel-basis
claims need a pinned decoder/capture definition and remain unsupported.

All remaining runtime, native activation, capsule and persona evidence is
AUSENTE — no inventar until independently collected. These limitations preserve
the frozen requirements; passing instrument assertions does not waive them.


## AI operability (ViewPoint)

Use MCP or the JSON lane for application operations first, the accessibility
tree second, and pixels only when semantic observation cannot resolve a task.
The browser observer consumes `prune_ax_v1`: chassis roles, NFC-normalized names
bounded to 64 serialized UTF-8 bytes [CITED: prune_ax_v1], and the states `busy`, `checked`, `current`,
`disabled`, `expanded`, `hidden`, `pressed`, `selected`. Generic containers,
tables, rows and static text are traversed without being emitted. An article is
opaque; interactive content must stay outside it. The observer never needs
`data-lin-*`, CSS selectors, console output, network traffic or JavaScript globals.

The shell has banner, Primary navigation, named main and contentinfo landmarks.
The active navigation link has `aria-current="page"`. Every action is a native
button, link or form control with a unique stable name within the screen.
Entity controls carry their identity in the name. Option names include their
owning field so independent selects cannot expose duplicate option names.
Names do not contain changing counts or timestamps. Controls use ARIA/native
states, support the keyboard, avoid hover-only menus and stay in the same window.

Readiness remains available through `data-lin-ready` and a persistent native
`output` (implicit `status` role) with the name `Screen agents ready`,
`Screen agent <id> ready`, `Screen lineage ready`, `Screen arena ready`,
`Screen arena <bench> ready`, or `Screen ledger ready`. Its name is fixed for
that screen identity. The working main has `aria-busy="true"`; a named
`progressbar` is exposed only while busy. Completion requires the ready status,
no progressbar or busy region, and quiet consecutive pruned snapshots.
Readiness proves screen rendering, including an explicit unavailable state;
it does not prove an unavailable backend capability succeeded.

A separate persistent native status names the committed field value or action
outcome. Errors have `role="alert"` and an `Error:` name. Outcomes survive quiet
reads until the next action; success is announced after the existing journal
postcondition checks. The legacy `Application updates` live region is retained.
The session token travels in the bootstrap meta element and the
`X-Lineage-Session` header, never a query or hash route. Every index response
uses the same server injection path and `Cache-Control: no-store`.

From the repository root, after building the UI with the installed local tools,
run the gates against an already served disposable home. `$URL` is its loopback
URL including the hash route; `$CHROME`, `$XVFB` and `$DBUS_DAEMON` identify
installed executables. `$ARTIFACTS` is an existing caller-owned temporary folder.
No gate downloads a browser, attaches to an existing browser, or signals a
process group.

```sh
python3 -m tools.qa.cdp_probe --viewpoint --url "$URL" --browser "$CHROME" --timeout-ms 15000 --artifacts "$ARTIFACTS"
python3 -m tools.qa.atspi_probe --viewpoint --url "$URL" --browser "$CHROME" --xvfb "$XVFB" --session-bus "$DBUS_DAEMON" --timeout-ms 15000 --node-limit 10000 --expect-button "Create agent" --artifacts "$ARTIFACTS"
python3 -m unittest tests.operability.test_viewpoint_ax -v
```

The real-browser tests seed an isolated home using public CLI reference pins and
`agent_create`, build into their temporary capsule, visit every route and retain
pruned JSON only inside that capsule. Only a missing installed Chrome permits a
browser-test skip. The AT-SPI probe launches its own Xvfb, dbus session and Chrome
with `--force-renderer-accessibility`. An empty, unowned, incomplete or unavailable
native tree is INCONCLUSIVE with a specific diagnostic, never PASS.

Measured platform limitation: some installed Chrome builds omit `aria-current`
from `Accessibility.getFullAXTree`, even when the AX-identified navigation link
has `aria-current="page"` in the DOM. The faithful pruner does not invent this
state. The CDP gate reports INCONCLUSIVE for this limitation; the regression
suite verifies the real attribute separately on that AX-identified node. Other
semantic failures still report FAIL. Native `ATSPI_ROLE_MAP` retains web
`xml-roles` and adds status/alert mapping so live regions can be checked; these
roles are absent from the upstream native mapping.

Integrated API adaptations: hosts without `lineage_tree` use paged, folded
`agent_list` records. Hosts without `bench_list`/`bench_status` expose named
unavailable alerts rather than fabricated benchmark records. The HTTP transport
accepts the integrated `/api/events` dispatch wrapper as well as the unwrapped
cursor. Browser frame decoding uses its own bounded strict JSON decoder because
the integrated ledger decoder has a smaller fixed document cap.
