import { afterEach, beforeEach, expect, vi } from 'vitest';
import { createHash } from 'node:crypto';
import { getScreen } from '../../src/screens/index.ts';
import { identityKey, normalizeName } from '../../src/ui/primitives.ts';
import type { AppState, AppStore, JsonObject, JsonValue, LedgerEvent, MountedScreen,
  EntityKind, Route, ScreenContext, ScreenId, Transport } from '../../src/ui/contracts.ts';
import type { BirthOp, LineageNode, LineageTreeData } from '../../src/screens/lineage/model.ts';

vi.setConfig({testTimeout: 4000, hookTimeout: 4000});
export const CLOCK = 1700000000000;
export const HASH = 'a'.repeat(64);
export const SOURCE_HASH = 'b'.repeat(64);
export const ABSENT = /AUSENTE — no inventar|not available|unavailable|not recorded|absent/iu;
export const REASONS = ['episode', 'level_one', 'level_three', 'private', 'missing_receipt',
  'invalid_receipt', 'not_promoted', 'scope_mismatch', 'not_selected', 'inactive', 'kind_not_inheritable'] as const;
export const canonical = (value: any): string => Array.isArray(value) ? `[${value.map(canonical).join(',')}]`
  : value !== null && typeof value === 'object' ? `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${canonical(value[k])}`).join(',')}}`
    : JSON.stringify(value);
export const sha = (text: string) => createHash('sha256').update(text, 'utf8').digest('hex');
export const route = (query: Record<string, string> = {}): Route => ({screen: 'lineage', query});
export function node(agent_id: string, parents: string[] = [], generation = 0,
  op: BirthOp = parents.length ? 'clone' : 'genesis', status: LineageNode['status'] = 'draft'): LineageNode {
  return {agent_id, parents, generation, op, status};
}
export const order = (a: LineageNode, b: LineageNode) => a.generation - b.generation || (a.agent_id < b.agent_id ? -1 : a.agent_id > b.agent_id ? 1 : 0);
export const forest = () => [node('root-a'), node('root-b', [], 0, 'genesis', 'retired'),
  node('clone-c', ['root-a'], 1), node('distill-d', ['root-a'], 1, 'distill'),
  node('cross-e', ['root-b', 'clone-c'], 2, 'cross'), node('mutate-f', ['cross-e'], 3, 'mutate'),
  node('specialize-g', ['distill-d'], 2, 'specialize')];
export const broad = () => [node('wide-root'), ...Array.from({length: 199}, (_, i) => node(`child-${String(i).padStart(3, '0')}`, ['wide-root'], 1))];
export const deep = () => Array.from({length: 200}, (_, i) => node(`chain-${String(i).padStart(3, '0')}`,
  i ? [`chain-${String(i - 1).padStart(3, '0')}`] : [], i));
export const rules = (entries: [string, string][] = [['I1', 'Keep recorded evidence.']]) => ({
  text: entries.map(([id, text]) => `[GOLD-S1/PM-1001.1/${id}; §1] ${text}`).join('\n') + '\n',
  overlays: [], rule_ids: entries.map(([id]) => id),
});
export function agent(n: LineageNode, eventId: string, constitution = rules()): any {
  const record = {schema: 'lineage.agent/v1', agent_id: n.agent_id, display_name: `Recorded ${n.agent_id}`,
    workflow: 'develop', language: 'typescript', allowed_seats: [{model: 'synthetic', effort: 'medium', mode: 'headless'}],
    references: [{id: 'gold_s1', sha256: HASH}, {id: 'memory_v21', sha256: SOURCE_HASH}],
    constitution_sha256: sha(constitution.text), skills: [], memory_gen: 0, brief_head_sha256: HASH,
    agent_version: '', generation: n.generation, parents: [...n.parents], born: {op: n.op, event_id: eventId}, status: n.status};
  record.agent_version = sha(canonical({constitution_sha256: record.constitution_sha256, skills: [], memory_gen: 0}));
  return record;
}
export function inherited(source = 'root-a', kind: 'lesson' | 'negative' | 'workflow' = 'lesson'): any {
  const body = kind === 'lesson' ? {tempting_use: 'Skip evidence', failure_mode: 'Unproven claim', safer_action: 'Read evidence', blocked_use: []}
    : kind === 'negative' ? {gate_id: 'test-gate', verdict: 'red', cause: 'Missing evidence', coordinate: 'test/example', safer_action: 'Read evidence'}
      : {trigger_sig: 'Recorded trigger', steps: ['Read evidence'], stats: {runs: 1, successes: 1, mean_reward: 1}, status: 'promoted'};
  return {source_agent_id: source, source_unit_id: 'source_01', unit_sha256: SOURCE_HASH,
    unit: {schema: 'lineage.mem.unit/v1', id: 'child_001', kind, level: 2, statement: 'Recorded inherited context.',
      status: 'active', privacy: 'internal', scope: {workflow: 'develop', language: 'typescript'},
      provenance: {origin: 'inheritance', actor: source,
        inherited_from: {agent_id: source, unit_id: 'source_01', unit_sha256: SOURCE_HASH}},
      receipts: [{path: 'evidence/unit.json', sha256: HASH}], supersedes: [], body}};
}
export function births(nodes: LineageNode[]): LedgerEvent[] {
  let previousLine = '0'.repeat(64);
  return [...nodes].sort(order).map((n, i) => {
    const id = `e-${(i + 1).toString(16).padStart(16, '0')}`;
    const constitution = rules();
    const event: LedgerEvent = {schema: 'lineage.event/v1', id, lamport: i + 1, ts: CLOCK + i,
      ledger: 'main', agent: 'creator-agent', kind: 'agent.born', op_id: `birth-${n.agent_id}`,
      request_sha256: HASH, evidence: [], prev_sha256: previousLine, sha256: '',
      payload: {record: agent(n, id, constitution), inherited_units: [], rejected_units: [], constitution}};
    const {sha256: _hash, ...rest} = event; event.sha256 = sha(canonical(rest));
    previousLine = sha(canonical(event) + '\n'); return event;
  });
}
export function birth(events: LedgerEvent[], id: string): any {
  const found = events.find(e => (e.payload.record as JsonObject | undefined)?.agent_id === id);
  expect(found, `Fixture birth ${id}`).toBeDefined(); return found!.payload;
}
export function seal(events: LedgerEvent[]): void {
  let previous = '0'.repeat(64);
  for (const e of events) {
    e.prev_sha256 = previous; const {sha256: _hash, ...rest} = e;
    e.sha256 = sha(canonical(rest)); previous = sha(canonical(e) + '\n');
  }
}
export function deferred<T>() {
  let resolve!: (value: T) => void; let reject!: (error: unknown) => void;
  const promise = new Promise<T>((yes, no) => {resolve = yes; reject = no;});
  return {promise, resolve, reject};
}
// Drain queued promise reactions, without timers or a wall-clock readiness guess.
export async function drain() {for (let i = 0; i < 32; i++) await Promise.resolve();}
export function outcome(promise: Promise<void>) {
  const state = {value: 'pending' as 'pending' | 'fulfilled' | 'rejected', error: undefined as unknown};
  void promise.then(() => {state.value = 'fulfilled';}, error => {state.value = 'rejected'; state.error = error;});
  return state;
}
const cleanups: (() => void)[] = [];
export function isolation() {
  beforeEach(() => {
    document.body.replaceChildren(); document.documentElement.removeAttribute('data-lin-ready');
    document.documentElement.removeAttribute('data-lin-rev'); history.replaceState(null, '', '/#/lineage');
    vi.stubGlobal('fetch', vi.fn(() => {throw Error('Network is forbidden in this oracle');}));
    vi.stubGlobal('matchMedia', vi.fn((media: string) => ({media, matches: false, onchange: null,
      addEventListener: vi.fn(), removeEventListener: vi.fn(), addListener: vi.fn(), removeListener: vi.fn(), dispatchEvent: () => true})));
  });
  afterEach(() => {
    for (const dispose of cleanups.splice(0).reverse()) dispose();
    vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); document.body.replaceChildren();
  });
}
export interface HarnessOptions {nodes?: LineageNode[]; events?: LedgerEvent[]; head?: number | null;
  query?: Record<string, string>; tree?: unknown; call?: (tool: string, args: JsonObject) => unknown;
  state?: Partial<AppState>; expanded?: string[]}
export function mount(options: HarnessOptions = {}) {
  const nodes = options.nodes ?? forest(); const events = options.events ?? births(nodes);
  const tree = Object.hasOwn(options, 'tree') ? options.tree : {nodes, head: events.length};
  const controller = new AbortController(); const host = document.createElement('main'); host.id = 'main-content';
  host.dataset.linScreen = 'lineage'; host.tabIndex = -1; document.body.append(host);
  let currentRoute = route(options.query);
  let state: AppState = {phase: 'ready', stale: false, route: currentRoute, mode: 'fixture', fixtureId: 'u24-local',
    tools: [], events, head: options.head === undefined ? events.length : options.head, error: null,
    selection: {}, expanded: options.expanded ?? [], ...options.state};
  const listeners = new Set<(s: AppState) => void>();
  const publish = (patch: Partial<AppState>) => {state = {...state, ...patch}; for (const listener of [...listeners]) listener(state);};
  const transport: Transport = {mode: 'fixture', fixtureId: 'u24-local',
    presentation: {clockMs: CLOCK, locale: 'en-GB', timezone: 'UTC', theme: 'light'},
    tools: vi.fn(async () => []), events: vi.fn(async () => ({events: [...events], head: events.length, next_after: events.length, has_more: false, resync: false})),
    call: vi.fn(async (tool: string, args: JsonObject) => {
      if (options.call && tool === 'lineage_tree') return await options.call(tool, args) as JsonValue;
      if (tool === 'lineage_tree') return structuredClone(tree) as JsonValue;
      if (tool === 'agent_get') {const record = birth(events, String(args.agent_id)).record; return {record};}
      if (tool === 'ledger_events') return {events, head: events.length, next_after: events.length, has_more: false, resync: false} as unknown as JsonValue;
      throw Error(`Unexpected tool ${tool}`);
    }) as Transport['call']};
  const store: AppStore = {getState: () => state,
    subscribe: vi.fn(listener => {listeners.add(listener); return () => {listeners.delete(listener);};}),
    refresh: vi.fn(async () => {}),
    setRoute: vi.fn(next => {publish({route: next, selection: {}});}),
    setSelection: vi.fn((screen: ScreenId, id: string | null) => {const selection = {...state.selection}; if (id === null) delete selection[screen]; else selection[screen] = id; publish({selection});}),
    setExpanded: vi.fn((entity: EntityKind, id: string, expanded: boolean) => {const key = JSON.stringify([entity, id]);
      publish({expanded: expanded ? [...new Set([...state.expanded, key])] : state.expanded.filter(k => k !== key)});}),
    dispose: () => {listeners.clear();}};
  let mounted!: MountedScreen; const pending: Promise<void>[] = [];
  const announce = vi.fn();
  const context = (): ScreenContext => ({route: currentRoute, transport, store, signal: controller.signal, announce,
    navigate: vi.fn(next => {
      navigation.push(next); currentRoute = next; store.setRoute(next);
      if (next.screen === 'lineage') {const p = mounted.update(context()); outcome(p); pending.push(p);}
    })});
  const navigation: Route[] = [];
  mounted = getScreen(currentRoute).mount(host, context()); const readyState = outcome(mounted.ready);
  let disposed = false;
  const dispose = () => {if (disposed) return; disposed = true; controller.abort(); mounted.dispose(); store.dispose();};
  cleanups.push(dispose);
  return {host, nodes, events, tree, store, transport, announce, navigation, controller, mounted,
    ready: mounted.ready, readyState, publish, dispose, listenerCount: () => listeners.size,
    async settled() {await drain(); for (const p of pending.splice(0)) await p; await drain();},
    update(query = currentRoute.query as Record<string, string>) {
      currentRoute = route(query); publish({route: currentRoute}); const p = mounted.update(context()); outcome(p); return p;
    }};
}
export type Harness = ReturnType<typeof mount>;
export const entries = (host: ParentNode) => [...host.querySelectorAll<HTMLElement>('[data-lin-entity="agent"][data-lin-id]')];
export const ids = (host: ParentNode) => entries(host).map(el => el.dataset.linId!);
export function entry(host: ParentNode, id: string): HTMLElement {
  const found = entries(host).filter(el => el.dataset.linId === id);
  expect(found, `Exactly one actionable canonical entry for ${id}`).toHaveLength(1); return found[0];
}
export function controls(host: ParentNode) {return [...host.querySelectorAll<HTMLElement>('button,a[href],input,select')].filter(el => !el.closest('[hidden]'));}
export function name(el: Element): string {
  const labelled = el.getAttribute('aria-labelledby');
  if (labelled) return normalizeName(labelled.split(/\s+/u).map(id => document.getElementById(id)?.textContent ?? '').join(' '));
  if (el.hasAttribute('aria-label')) return normalizeName(el.getAttribute('aria-label')!);
  if (el instanceof HTMLInputElement || el instanceof HTMLSelectElement) return normalizeName([...el.labels ?? []].map(l => l.textContent).join(' '));
  return normalizeName(el.textContent ?? '');
}
export function action(host: ParentNode, value: string, id?: string): HTMLElement {
  const scope = id === undefined ? host : entry(host, id);
  const found = controls(scope).filter(el => el.dataset.linAction === value && (id === undefined || el.closest('[data-lin-entity="agent"]') === scope));
  expect(found, `One exposed ${value}${id ? ` for ${id}` : ''}`).toHaveLength(1); return found[0];
}
export async function click(h: Harness, value: string, id?: string) {action(h.host, value, id).click(); await h.settled();}
export async function search(h: Harness, value: string) {
  const input = action(h.host, 'filter-lineage-query') as HTMLInputElement;
  input.value = value; input.dispatchEvent(new Event('input', {bubbles: true})); await h.settled();
}
export function ownText(el: HTMLElement): string {
  // A-U24: Adapt relation-text support to nested canonical entries without cloning every descendant subtree.
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (node instanceof Element) return node.matches('[data-lin-entity="agent"],svg') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_SKIP;
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  const text: string[] = [];
  while (walker.nextNode()) text.push(walker.currentNode.textContent ?? '');
  return normalizeName(text.join(''));
}
export function assertRelations(host: HTMLElement, nodes: LineageNode[]) {
  expect(new Set(ids(host)).size).toBe(ids(host).length);
  const scope = new Map(nodes.map(n => [n.agent_id, n]));
  for (const n of nodes) {
    const child = entry(host, n.agent_id), text = ownText(child);
    expect(text).toContain(n.agent_id); expect(text).toContain(n.op); expect(text).toContain(n.status);
    for (const parentId of n.parents) expect(text, `Child description retains ${parentId} → ${n.agent_id} (${n.op})`).toContain(parentId);
    const canonicalParent = n.parents.find(id => scope.has(id));
    if (canonicalParent) expect(child.parentElement?.closest('[data-lin-entity="agent"]')?.getAttribute('data-lin-id')).toBe(canonicalParent);
    for (const parentId of n.parents.filter(id => scope.has(id) && id !== canonicalParent)) {
      const reference = ownText(entry(host, parentId));
      for (const token of [n.agent_id, n.op, canonicalParent!]) expect(reference, `Passive secondary edge ${parentId} → ${n.agent_id}`).toContain(token);
    }
  }
}
export async function exhaust(h: Harness, total = h.nodes.length) {
  const seen = new Set(ids(h.host));
  for (let turn = 0; turn < total + 1; turn++) {
    const continuation = controls(h.host).find(el => el.dataset.linAction === 'expand-next-generation');
    if (!continuation) break;
    const before = new Set(ids(h.host)); continuation.click(); await h.settled(); const after = ids(h.host);
    expect(after.filter(id => !before.has(id)).length).toBeLessThanOrEqual(50);
    expect(new Set(after).size).toBe(after.length);
    for (const id of after) seen.add(id);
    expect(after.length, 'Continuation must make deterministic progress').toBeGreaterThan(before.size);
  }
  expect([...seen].sort()).toEqual(h.nodes.map(n => n.agent_id).sort());
  expect(controls(h.host).filter(el => el.dataset.linAction === 'expand-next-generation')).toHaveLength(0);
}
export function assertReadOnly(h: Harness) {
  const calls = vi.mocked(h.transport.call).mock.calls;
  expect(calls.some(([tool]) => tool === 'lineage_tree')).toBe(true);
  for (const [tool, args, options] of calls) {
    expect(['lineage_tree', 'agent_get', 'ledger_events']).toContain(tool); expect(options.mutation).toBe(false);
    expect(args).not.toHaveProperty('op_id'); expect(args).not.toHaveProperty('expected_head');
    if (tool === 'lineage_tree') {expect(args.include_retired).toBe(true);
      expect(Object.keys(args).every(k => ['root_id', 'include_retired', 'agent'].includes(k))).toBe(true);}
    if (tool === 'ledger_events') expect(args.agent_id, 'Birth lookup must not filter on the child as ledger actor').toBeUndefined();
  }
}
export function selected(h: Harness, id: string) {
  expect(action(h.host, 'select-lineage-agent', id).getAttribute('aria-pressed')).toBe('true');
}
export const key = (id: string) => identityKey('agent', id);
