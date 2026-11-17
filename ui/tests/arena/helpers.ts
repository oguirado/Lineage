import { afterEach, beforeEach, expect, vi } from 'vitest';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
export const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
import type { AppState, AppStore, CallOptions, JsonObject, JsonValue, LedgerEvent, MountedScreen, Route, ScreenContext, Transport } from '../../src/ui/contracts.ts';
import { screen } from '../../src/screens/arena/index.ts';
import { closeDialogsWithin } from '../../src/ui/dialog.ts';
import { TransportError } from '../../src/transport.ts';

// Only public contracts and rendered actions are observed. All fixture values are [TARGET].
// Bounds are [CITED: docs/CONTRACT.md and schemas/]. All scripts are synthetic.
export const BENCH = 'bench_alpha_0001';
export const OTHER = 'bench_zulu_0002';
export const ACTOR = 'arena-actor';
export const BASELINE = 'baseline-agent';
export const CANDIDATE = 'candidate-agent';
export const HASH = 'a'.repeat(64);
export const FROZEN_VERSION = 'b'.repeat(64);
export const CLOCK = 1_800_000_000_000;
export const SEAT = { model: 'test-model', effort: 'medium', mode: 'headless' };
export const SECOND_SEAT = { model: 'test-model', effort: 'high', mode: 'interactive' };
export const unknownCost = () => ({ tokens_in: null, tokens_out: null, tokens_cache: null, duration_ms: null, cost_micro_usd: null });
export const copy = <T>(value: T): T => structuredClone(value);
export const declaration = (patch: Record<string, any> = {}): any => ({
  schema: 'lineage.bench.declared/v1', bench_id: BENCH, bank_id: 'scripted-bank', bank_sha256: HASH,
  protocol: 'paired', purpose: 'select', agents: [BASELINE, CANDIDATE], seats: [copy(SEAT)], memory_arms: ['own', 'inherited'],
  credit_rule: { metric: 'correctness_first', minimum_gain: 0.125, dispersion: 'population_stddev', cost_tiebreaker: true },
  sprt: { p0: 0.3, p1: 0.7, alpha: 0.05, beta: 0.1, cap: 12 }, promotion: { n_shadow_runs: 3 }, ...patch,
});
export const status = (patch: Record<string, any> = {}): any => ({ declaration: declaration(), state: 'declared', results: [], verdict: null, head: 10, ...patch });
export const verdict = (patch: Record<string, any> = {}): any => ({ bench_id: BENCH, decision: 'not_superior', llr: -2.125, n_discordant: 3,
  credit: { gain: -0.25, baseline_dispersion: 0.375, minimum_reward: -1, credited: false }, ...patch });
export function result(runId = 'run_alpha_0001', patch: Record<string, any> = {}): any {
  return { bench_id: BENCH, task_id: 'task_alpha_0001', agent_id: CANDIDATE, seat: copy(SEAT), memory_arm: 'own', run_id: runId,
    verdict: 'error', correctness: 0, cost: unknownCost(), ...patch };
}
export function agent(id = CANDIDATE, patch: Record<string, any> = {}): any {
  return { schema: 'lineage.agent/v1', agent_id: id, display_name: 'Repeated display name', workflow: 'test', language: 'general',
    allowed_seats: [copy(SEAT), copy(SECOND_SEAT)], references: [{ id: 'gold_s1', sha256: HASH }, { id: 'memory_v21', sha256: HASH }],
    constitution_sha256: HASH, skills: [], memory_gen: 9, brief_head_sha256: HASH, agent_version: HASH, generation: 0,
    parents: [], born: { op: 'genesis', event_id: eventId(1) }, status: 'draft', ...patch };
}
export function eventId(n: number): string { return 'e-' + n.toString(16).padStart(16, '0'); }
export function event(n: number, kind: string, payload: any, patch: Record<string, any> = {}): LedgerEvent {
  return { schema: 'lineage.event/v1', id: eventId(n), lamport: n, ts: CLOCK + n, ledger: 'main', agent: ACTOR, kind,
    payload: copy(payload), op_id: `script-${n}`, request_sha256: HASH, evidence: [], prev_sha256: HASH, sha256: HASH, ...patch };
}
export function runReply(cell = result(), split = 'select', closed = true): any {
  const frozen = { run_id: cell.run_id, agent_id: cell.agent_id, agent_version: FROZEN_VERSION, seat: cell.seat,
    task: { id: cell.task_id, kind: 'scripted', language: 'general', bank_id: 'scripted-bank', bench_id: cell.bench_id, split },
    parents_context: [], memory_arm: cell.memory_arm };
  return { opened: event(3, 'run.open', frozen, { agent: cell.agent_id }), closed: closed ? {
    schema: 'lineage.run/v1', ...frozen, ts_open: CLOCK + 3, ts_close: CLOCK + 4,
    outcome: { verdict: cell.verdict, repair_loops: 1, findings: { confirmed: 1, refuted: 0 } }, cost: copy(cell.cost),
    memory: { unit_ids: ['memory_episode_0001', 'memory_lesson_0001'], levels: [2, 3], gate_passed: true },
    evidence: [{ path: 'evidence/task-result.txt', sha256: HASH }],
  } : null, head: 10 };
}
export const cursor = (events: LedgerEvent[] = [], patch: Record<string, any> = {}): any => ({ events,
  next_after: events.at(-1)?.lamport ?? 10, head: 10, has_more: false, resync: false, ...patch });
export const commit = (events: LedgerEvent[]): any => ({ event_ids: events.map(e => e.id), head: events.at(-1)!.lamport, sha256: HASH });
export const listRoute = (query: Record<string, string> = {}): Route => ({ screen: 'arena', query });
export const detailRoute = (benchId = BENCH, query: Record<string, string> = {}): Route => ({ screen: 'bench', benchId, query });
export function key(kind: string, id: string): string {
  return Buffer.byteLength(id, 'utf8') <= 20 ? id : `${id.slice(0, 7)}-${createHash('sha256').update(kind + '\0' + id).digest('hex').slice(0, 12)}`;
}
export function deferred<T = any>() {
  let resolve!: (value: T) => void; let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}
export async function flush(): Promise<void> { for (let turn = 0; turn < 100; turn++) await Promise.resolve(); }
export const refusal = (code = 'conflict', detail = 'Scripted refusal') => new TransportError('domain', code, detail, { detail });

// Discovery schemas are read verbatim; no implementation-specific field vocabulary.
const contract = readFileSync(resolve(repoRoot, 'docs/CONTRACT.md'), 'utf8');
export function toolSchema(name: string, output = false): any {
  const part = contract.split(`### \`${name}\``)[1]?.split('\n### ')[0];
  if (!part) throw Error(`Public contract is missing ${name}`);
  const blocks = [...part.matchAll(/```json\n([\s\S]*?)\n```/g)];
  return JSON.parse(blocks[output ? 1 : 0][1]);
}
const schemas = new Map<string, any>();
function resolveSchema(ref: string): any {
  if (!schemas.has(ref)) schemas.set(ref, JSON.parse(readFileSync(resolve(repoRoot, 'schemas', ref), 'utf8')));
  return schemas.get(ref);
}
// Test-data validator: deliberately independent of the product. Never certifies a backend gate.
export function conforms(value: any, schema: any): boolean {
  if (schema.$ref) return conforms(value, resolveSchema(schema.$ref));
  if (schema.const !== undefined && JSON.stringify(value) !== JSON.stringify(schema.const)) return false;
  if (schema.enum && !schema.enum.includes(value)) return false;
  if (schema.anyOf && !schema.anyOf.some((s: any) => conforms(value, s))) return false;
  if (schema.oneOf && schema.oneOf.filter((s: any) => conforms(value, s)).length !== 1) return false;
  if (schema.allOf && !schema.allOf.every((s: any) => conforms(value, s))) return false;
  if (schema.if && conforms(value, schema.if) && schema.then && !conforms(value, schema.then)) return false;
  if (schema.type === 'null' && value !== null) return false;
  if (schema.type === 'boolean' && typeof value !== 'boolean') return false;
  if (schema.type === 'string') {
    if (typeof value !== 'string') return false;
    const length = [...value].length;
    if (schema.minLength !== undefined && length < schema.minLength || schema.maxLength !== undefined && length > schema.maxLength) return false;
    if (schema.pattern && !new RegExp(schema.pattern, 'u').test(value)) return false;
  }
  if (schema.type === 'integer' || schema.type === 'number') {
    if (typeof value !== 'number' || !Number.isFinite(value) || schema.type === 'integer' && !Number.isSafeInteger(value)) return false;
    if (schema.minimum !== undefined && value < schema.minimum || schema.maximum !== undefined && value > schema.maximum ||
      schema.exclusiveMinimum !== undefined && value <= schema.exclusiveMinimum || schema.exclusiveMaximum !== undefined && value >= schema.exclusiveMaximum) return false;
  }
  if (schema.type === 'array') {
    if (!Array.isArray(value)) return false;
    if (schema.minItems !== undefined && value.length < schema.minItems || schema.maxItems !== undefined && value.length > schema.maxItems) return false;
    if (schema.uniqueItems && new Set(value.map(v => JSON.stringify(v))).size !== value.length) return false;
    if (schema.items && !value.every(v => conforms(v, schema.items))) return false;
  }
  if (schema.type === 'object' || schema.properties) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
    if ((schema.required ?? []).some((k: string) => !Object.hasOwn(value, k))) return false;
    if (schema.additionalProperties === false && Object.keys(value).some(k => !Object.hasOwn(schema.properties ?? {}, k))) return false;
    for (const [k, s] of Object.entries(schema.properties ?? {})) if (Object.hasOwn(value, k) && !conforms(value[k], s)) return false;
  }
  return true;
}
export const toolNames = ['bench_list', 'bench_status', 'bench_declare', 'bench_run', 'bench_verdict', 'agent_promote', 'agent_list', 'agent_get', 'run_get', 'ledger_events'];
export const mutations = new Set(['bench_declare', 'bench_run', 'bench_verdict', 'agent_promote']);
export const descriptors = () => toolNames.map(name => ({ name, description: `Scripted ${name}`, inputSchema: toolSchema(name) }));
type Reply = any | ((args: JsonObject, options: CallOptions) => any);
export class Script {
  benches = new Map<string, any>([[BENCH, status()]]);
  agents = new Map<string, any>([[BASELINE, agent(BASELINE)], [CANDIDATE, agent()], [ACTOR, agent(ACTOR)]]);
  runs = new Map<string, any>();
  journal: LedgerEvent[] = [];
  head = 10;
  nextAfter: string | null = null;
  queues = new Map<string, Reply[]>();
  constructor(public mode: 'live' | 'fixture' = 'live') {}
  queue(tool: string, ...replies: Reply[]): this { this.queues.set(tool, [...(this.queues.get(tool) ?? []), ...replies]); return this; }
  async dispatch(tool: string, args: JsonObject, options: CallOptions): Promise<any> {
    expect(options.mutation, `Shared classification for ${tool}`).toBe(mutations.has(tool));
    expect(conforms(args, toolSchema(tool)), `Closed public arguments for ${tool}`).toBe(true);
    const scripted = this.queues.get(tool);
    if (scripted?.length) {
      const reply = scripted.shift();
      if (reply instanceof Error) throw reply;
      return typeof reply === 'function' ? await reply(args, options) : copy(reply);
    }
    switch (tool) {
      case 'bench_list': return { benches: [...this.benches.values()].sort((a, b) => a.declaration.bench_id.localeCompare(b.declaration.bench_id)), next_after: this.nextAfter, head: this.head };
      case 'bench_status': {
        const bench = this.benches.get(String(args.bench_id));
        if (!bench) throw refusal('no_benchmark');
        return { bench: copy(bench) };
      }
      case 'agent_list': return { agents: [...this.agents.values()].map(copy), next_after: null, head: this.head };
      case 'agent_get': {
        const record = this.agents.get(String(args.agent_id)); if (!record) throw refusal('no_agent');
        return { record: copy(record) };
      }
      case 'run_get': {
        const reply = this.runs.get(String(args.run_id)); if (!reply) throw refusal('no_run'); return copy(reply);
      }
      case 'ledger_events': {
        const after = Number(args.after ?? 0), limit = Number(args.limit ?? 100);
        const relevant = this.journal.filter(e => e.lamport > after);
        const slice = relevant.slice(0, limit);
        return cursor(copy(slice), { head: this.head, next_after: relevant.length > limit ? slice.at(-1)!.lamport : this.head, has_more: relevant.length > limit });
      }
      default: throw refusal('bad_op', 'No synthetic mutation reply has been scripted');
    }
  }
  transport: Transport = {
    mode: 'live', fixtureId: null, presentation: null,
    tools: vi.fn(async () => descriptors()), events: vi.fn(async () => cursor()),
    call: vi.fn(async (tool: string, args: JsonObject, options: CallOptions) => this.dispatch(tool, copy(args), options)) as unknown as Transport['call'],
  };
  useMode(): Transport {
    return Object.assign(this.transport, { mode: this.mode, fixtureId: this.mode === 'fixture' ? 'demo' : null,
      presentation: this.mode === 'fixture' ? { clockMs: CLOCK, locale: 'en-GB', timezone: 'UTC', theme: 'light' } : null });
  }
  calls(tool: string): any[][] { return vi.mocked(this.transport.call).mock.calls.filter(call => call[0] === tool); }
  mutationCalls(): any[][] { return vi.mocked(this.transport.call).mock.calls.filter(call => mutations.has(call[0])); }
}

const owned: (() => void)[] = [];
export function isolate(): void {
  beforeEach(() => {
    vi.setConfig({ testTimeout: 1500, hookTimeout: 1500 });
    vi.useFakeTimers(); vi.setSystemTime(CLOCK); localStorage.clear();
    document.body.replaceChildren(); document.documentElement.removeAttribute('data-lin-rev');
    document.documentElement.dataset.linReady = 'false'; window.history.replaceState(null, '', '/#/arena');
    vi.stubGlobal('fetch', vi.fn(() => { throw Error('Network is forbidden in the Arena oracle'); }));
    vi.stubGlobal('matchMedia', vi.fn((media: string) => ({ matches: false, media, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  });
  afterEach(() => {
    for (const dispose of owned.splice(0).reverse()) dispose();
    closeDialogsWithin(document.body); document.body.replaceChildren(); localStorage.clear();
    vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers();
  });
}
export interface Harness {
  root: HTMLElement; host: HTMLElement; statusNode: HTMLElement; actor: HTMLSelectElement;
  script: Script; state: AppState; store: AppStore; context: ScreenContext; mounted: MountedScreen;
  announcements: [string, string][]; navigate: ReturnType<typeof vi.fn>; abort: AbortController;
  update(route?: Route, head?: number): Promise<void>; emit(patch: Partial<AppState>): void;
}
export function mount(script = new Script(), route: Route = detailRoute()): Harness {
  const root = document.createElement('div'); document.body.append(root);
  const header = document.createElement('header'); header.textContent = 'Lineage';
  const nav = document.createElement('nav'); nav.setAttribute('aria-label', 'Primary');
  const actor = document.createElement('select'); actor.dataset.linAction = 'select-actor'; actor.setAttribute('aria-label', 'Acting agent');
  const option = document.createElement('option'); option.value = ACTOR; option.textContent = ACTOR; actor.append(option); actor.value = ACTOR;
  const host = document.createElement('main'); host.id = 'main-content'; host.tabIndex = -1; host.dataset.linScreen = route.screen;
  const statusNode = document.createElement('div'); statusNode.setAttribute('role', 'status'); statusNode.setAttribute('aria-label', 'Application updates');
  root.append(header, nav, actor, host, statusNode);
  const abort = new AbortController();
  const listeners = new Set<(state: AppState) => void>();
  const state: AppState = { phase: 'ready', stale: false, route, mode: script.mode, fixtureId: script.mode === 'fixture' ? 'demo' : null,
    tools: descriptors(), events: [], head: script.head, error: null, selection: {}, expanded: [] };
  const announcements: [string, string][] = [];
  const navigate = vi.fn((next: Route) => {
    h.context = { ...h.context, route: next }; h.state = { ...h.state, route: next }; host.dataset.linScreen = next.screen;
    // U21 sends query navigation back through update; permit route-driven disclosures.
    void Promise.resolve().then(() => {
      if (!abort.signal.aborted) return h.mounted.update(h.context);
    }).catch(() => {});
  });
  const store: AppStore = {
    getState: () => h.state, subscribe: listener => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    refresh: vi.fn(async () => {
      h.emit({ phase: 'ready', stale: false, head: script.head, events: copy(script.journal), error: null });
      if (!abort.signal.aborted) await h.mounted.update(h.context);
    }),
    setRoute: next => { h.state = { ...h.state, route: next }; }, setSelection: (screen, id) => { h.state = { ...h.state, selection: { ...h.state.selection, [screen]: id ?? undefined } }; },
    setExpanded: vi.fn(), dispose: () => listeners.clear(),
  };
  const context: ScreenContext = { route, transport: script.useMode(), store, signal: abort.signal, navigate,
    announce: (k, message) => { announcements.push([k, message]); statusNode.textContent = message; } };
  const h: Harness = { root, host, actor, statusNode, script, state, store, context, mounted: undefined as unknown as MountedScreen, announcements, navigate, abort,
    async update(next = h.context.route, head = h.state.head ?? script.head) {
      h.state = { ...h.state, route: next, head }; h.context = { ...h.context, route: next }; host.dataset.linScreen = next.screen;
      await h.mounted.update(h.context); await flush();
    },
    emit(patch) { h.state = { ...h.state, ...patch }; for (const listener of listeners) listener(h.state); },
  };
  const mounted = screen.mount(host, context); h.mounted = mounted;
  // Observe rejections immediately; individual tests still assert the ready rejection.
  void mounted.ready.catch(() => {});
  owned.push(() => { abort.abort(); mounted.dispose(); store.dispose(); closeDialogsWithin(root); root.remove(); });
  return h;
}
export async function ready(h: Harness): Promise<void> { await h.mounted.ready; await flush(); }
export function text(node: ParentNode): string { return (node as Node).textContent?.replace(/\s+/gu, ' ').trim() ?? ''; }
export function nameOf(el: Element): string {
  const ids = el.getAttribute('aria-labelledby');
  if (ids) return ids.split(/\s+/u).map(id => document.getElementById(id)?.textContent ?? '').join(' ').replace(/\s+/gu, ' ').trim();
  if (el.hasAttribute('aria-label')) return el.getAttribute('aria-label')!.normalize('NFC').replace(/\s+/gu, ' ').trim();
  if (el instanceof HTMLInputElement || el instanceof HTMLSelectElement) return [...(el.labels ?? [])].map(l => l.textContent ?? '').join(' ').trim();
  return text(el);
}
export function visible(el: Element): boolean { return !el.closest('[hidden],[inert]'); }
export function allActions(root: ParentNode): HTMLElement[] { return [...root.querySelectorAll<HTMLElement>('[data-lin-action]')].filter(visible); }
export function action(root: ParentNode, literal: string, name?: string): HTMLElement {
  const found = allActions(root).filter(el => el.dataset.linAction === literal && (!name || nameOf(el) === name));
  expect(found, `Expected one exposed ${literal}${name ? ` named ${name}` : ''}`).toHaveLength(1);
  return found[0];
}
export function record(root: ParentNode, kind: string, id: string): HTMLElement {
  const found = [...root.querySelectorAll<HTMLElement>('[data-lin-entity][data-lin-id]')].filter(el => el.dataset.linEntity === kind && el.dataset.linId === id && visible(el));
  expect(found, `Full ${kind} identity ${id}`).toHaveLength(1); return found[0];
}
export async function click(root: ParentNode, literal: string, name?: string): Promise<HTMLElement> {
  const el = action(root, literal, name); el.focus(); el.click(); await flush(); return el;
}
export function dialog(root: ParentNode, prefix: string): HTMLElement {
  const found = [...root.querySelectorAll<HTMLElement>('dialog,[role="dialog"]')].filter(el => visible(el) && nameOf(el).startsWith(prefix));
  expect(found, `Named ${prefix} modal`).toHaveLength(1); return found[0];
}
export function edit(root: ParentNode, path: string, value: string | boolean): HTMLInputElement | HTMLSelectElement {
  const fields = [...root.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-lin-action="edit-field"][name]')].filter(el => el.name === path && visible(el));
  expect(fields, `Native field ${path}`).toHaveLength(1); const field = fields[0];
  if (field instanceof HTMLInputElement && field.type === 'checkbox') field.checked = Boolean(value); else field.value = String(value);
  field.dispatchEvent(new Event('input', { bubbles: true })); field.dispatchEvent(new Event('change', { bubbles: true })); return field;
}
export async function submit(root: ParentNode, label: string): Promise<void> {
  const button = action(root, 'submit-dialog', `Confirm ${label}`) as HTMLButtonElement;
  expect(button.tagName).toBe('BUTTON'); expect(button.type).toBe('submit');
  const form = button.closest('form'); expect(form, 'Confirm belongs to a native form').not.toBeNull();
  // Submit event also exercises the handler when browser validity would block a click.
  form!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await flush();
}
export async function reveal(h: Harness): Promise<void> {
  const toggle = action(h.host, 'show-bench-rule');
  if (toggle.getAttribute('aria-expanded') !== 'true') await click(h.host, 'show-bench-rule');
  expect(text(h.host)).toContain(HASH);
}
export async function launchForm(h: Harness, seed = '17'): Promise<HTMLElement> {
  await reveal(h); await click(h.host, 'launch-benchmark');
  const modal = dialog(h.root, 'Launch benchmark'); edit(modal, 'runner.kind', 'fake'); edit(modal, 'runner.seed', seed); return modal;
}
export async function promoteForm(h: Harness): Promise<HTMLElement> {
  await click(h.host, 'promote-candidate'); return dialog(h.root, 'Promote agent');
}
export function noRecorded(h: Harness): void { expect(h.announcements.map(([, m]) => m).join(' ')).not.toMatch(/recorded for/u); }
export function assertCall(h: Harness, tool: string, expected: Record<string, any>): any {
  const calls = h.script.calls(tool); expect(calls, `${tool} dispatch count`).toHaveLength(1);
  const [, args, opts] = calls[0]; expect(args).toEqual({ ...expected, op_id: expect.stringMatching(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/u) });
  expect(opts.mutation).toBe(true); expect(opts.signal).toBeInstanceOf(AbortSignal); return args;
}
export function snapshotStorage(): Record<string, string> {
  return Object.fromEntries(Array.from({ length: localStorage.length }, (_, n) => localStorage.key(n)!).map(k => [k, localStorage.getItem(k)!]));
}
export function restoreStorage(values: Record<string, string>): void { localStorage.clear(); for (const [k, v] of Object.entries(values)) localStorage.setItem(k, v); }
