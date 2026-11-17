import { afterEach, beforeEach, expect, vi } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
// A-U21R: Mock only the five screen modules in shell suites; retain the real registry and shell.
import { stubScreens } from './screen-stubs.ts';
vi.setConfig({testTimeout: 4000, hookTimeout: 4000});

export const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
// A-U21R: Register before dynamic source imports; Vitest isolates these mocks from tests/agents.
for (const screen of Object.values(stubScreens)) {
  vi.doMock(resolve(root, `ui/src/screens/${screen.id}/index.ts`), () => ({screen}));
}
export function text(path: string): string {
  expect(existsSync(resolve(root, path)), `Required U21 deliverable ${path} is absent`).toBe(true);
  return readFileSync(resolve(root, path), 'utf8');
}
export function json(path: string): any { return JSON.parse(text(path)); }
export async function moduleAt(path: string, exports: string[] = []): Promise<any> {
  text(path); // Fail as an assertion before asking the module loader to resolve absent source.
  const result = await import(/* @vite-ignore */ resolve(root, path));
  for (const name of exports) expect(result[name], `${path} must export ${name}`).toBeDefined();
  return result;
}
export const source = (path: string, exports: string[] = []) => moduleAt(`ui/src/${path}`, exports);
export function deferred<T = any>() {
  let resolve!: (value: T) => void; let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}
// A bounded microtask turn drains promises only; it never waits on wall time.
export async function flush() { for (let i = 0; i < 24; i++) await Promise.resolve(); }
export const route = (screen = 'agents', extra: any = {}) => ({screen, query: {}, ...extra});
export const descriptor = {name: 'agent_list', description: 'Synthetic agent read', inputSchema: {type: 'object'}};
export const digest = 'f2d2e9d62c17f4f5b9f5a1d784c3a9cbd21a53d681af57e75e76f6b354ed10bc';
export function event(n: number, changes: any = {}): any {
  return {schema: 'lineage.event/v1', id: `e-${n.toString(16).padStart(16, '0')}`,
    lamport: n, ts: 1700000000000 + n, ledger: 'main', agent: 'aurora-root',
    kind: 'run.beat', payload: {synthetic: true}, op_id: `synthetic-${n}`,
    request_sha256: digest, evidence: [], prev_sha256: '0'.repeat(64), sha256: digest, ...changes};
}
export const page = (events: any[] = [], changes: any = {}) => ({events,
  next_after: events.at(-1)?.lamport ?? 0, head: events.at(-1)?.lamport ?? 0,
  has_more: false, resync: false, ...changes});
export function fakeTransport(changes: any = {}): any {
  return {mode: 'live', fixtureId: null, tools: vi.fn(async () => [structuredClone(descriptor)]),
    events: vi.fn(async () => page()), call: vi.fn(async () => ({synthetic: true})), ...changes};
}
export function response(value: any, status = 200): Response {
  return {ok: status >= 200 && status < 300, status, redirected: false,
    headers: new Headers({'content-type': 'application/json'}),
    json: async () => structuredClone(value), text: async () => JSON.stringify(value)} as Response;
}
export function fixture(id = 'demo'): any {
  return {schema: 'lineage.ui.fixture/v1', id, clock_ms: 1700000000000,
    tools: [structuredClone(descriptor)], page: page(),
    results: [{tool: 'agent_list', args: {}, reply: {untrusted: {agents: [], synthetic: true}}}],
    panels: [{id: 'empty', state: 'empty', title: 'Synthetic empty agents'}]};
}
const cleanup: (() => void)[] = [];
export function own<T extends {dispose(): void}>(handle: T): T { cleanup.push(() => handle.dispose()); return handle; }
export function isolateDom() {
  beforeEach(() => {
    document.body.replaceChildren(); document.documentElement.dataset.linReady = 'false';
    document.documentElement.removeAttribute('data-lin-rev');
    window.history.replaceState(null, '', '/#/agents');
    vi.stubGlobal('fetch', vi.fn(() => { throw new Error('Oracle forbids real network'); }));
    vi.stubGlobal('matchMedia', vi.fn((query: string) => ({matches: false, media: query,
      onchange: null, addEventListener: vi.fn(), removeEventListener: vi.fn(),
      addListener: vi.fn(), removeListener: vi.fn(), dispatchEvent: () => true})));
  });
  afterEach(() => {
    for (const dispose of cleanup.splice(0).reverse()) dispose();
    vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals();
    document.body.replaceChildren();
  });
}
export function host(tag = 'div'): HTMLElement {
  const node = document.createElement(tag); document.body.append(node); return node;
}
export function accessibleName(el: Element): string {
  const refs = el.getAttribute('aria-labelledby');
  if (refs) return refs.split(/\s+/).map(id => document.getElementById(id)?.textContent ?? '').join(' ').trim();
  if (el.hasAttribute('aria-label')) return el.getAttribute('aria-label')!;
  if (el instanceof HTMLInputElement || el instanceof HTMLSelectElement) {
    return Array.from(el.labels ?? []).map(l => l.textContent).join(' ').trim();
  }
  return el.textContent?.trim() ?? '';
}
export const normalizedName = (el: Element) => accessibleName(el).normalize('NFC').replace(/\s+/gu, ' ').trim();
export const controls = (node: ParentNode) => Array.from(node.querySelectorAll('button,a[href],input,select'));
export function goodShell(): HTMLElement {
  const root = host();
  root.innerHTML = '<header>Lineage</header><nav aria-label="Primary"><a href="#/agents" data-lin-action="nav-agents" aria-label="Agents navigation" aria-current="page">Agents</a><a href="#/lineage" data-lin-action="nav-lineage" aria-label="Lineage navigation">Lineage</a><a href="#/arena" data-lin-action="nav-arena" aria-label="Arena navigation">Arena</a><a href="#/ledger" data-lin-action="nav-ledger" aria-label="Ledger navigation">Ledger</a></nav><a href="#main-content" data-lin-action="skip-main">Skip to main content</a><main id="main-content" tabindex="-1" data-lin-screen="agents"><h1>Agents</h1></main><div role="status" aria-label="Application updates" aria-live="polite" aria-atomic="true"></div>';
  return root;
}
export async function app(transport = fakeTransport(), initialHash = '#/agents', storage: Storage | null = null) {
  const {startApp} = await source('main.ts', ['startApp']);
  const root = host(); const handle = own(startApp({root, transport, initialHash, storage}));
  await flush(); return {root, handle, transport};
}
