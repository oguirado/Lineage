// @vitest-environment jsdom
import { it, expect, vi } from 'vitest';
import { source, own, fakeTransport, event, page, descriptor, deferred, flush, route, isolateDom } from './helpers.ts';
isolateDom();
async function make(transport: any) { const {createStore} = await source('store.ts', ['createStore']); return own(createStore(transport, route())); }
it('A17 waits for descriptors and the complete fold before publishing a cursor', async () => {
  const tools = deferred(); const final = deferred(); const t = fakeTransport({tools: vi.fn(() => tools.promise),
    events: vi.fn().mockResolvedValueOnce(page([event(1)], {head: 2, has_more: true})).mockImplementation(() => final.promise)});
  const s = await make(t); const states: any[] = []; s.subscribe((v: any) => states.push(v));
  expect(s.getState()).toMatchObject({head: null, phase: 'loading'});
  const refresh = s.refresh(); await flush(); expect(s.getState().head).toBeNull();
  tools.resolve([descriptor]); await flush(); expect(s.getState().head).toBeNull();
  expect(s.getState().events).toEqual([]);
  final.resolve(page([event(2)])); await refresh;
  expect(s.getState()).toMatchObject({phase: 'ready', head: 2, stale: false, error: null});
  expect(s.getState().events.map((e: any) => e.lamport)).toEqual([1, 2]);
  expect(states.some(state => state.head === 1)).toBe(false);
});
it('A17 commits an authoritative empty prefix as zero rather than absence', async () => {
  const s = await make(fakeTransport()); await s.refresh();
  expect(s.getState()).toMatchObject({head: 0, phase: 'ready', events: [], error: null});
});
it('A18 stages identical overlap once, follows advancing heads and detaches response objects', async () => {
  const first = event(1); const second = event(2); const third = event(3);
  const t = fakeTransport({events: vi.fn().mockResolvedValueOnce(page([first], {head: 2, has_more: true}))
    .mockResolvedValueOnce(page([structuredClone(first), second], {head: 3, has_more: true}))
    .mockResolvedValueOnce(page([third]))});
  const s = await make(t); await s.refresh();
  expect(s.getState().head).toBe(3); expect(s.getState().events.map((e: any) => e.id)).toEqual([first.id, second.id, third.id]);
  first.payload.synthetic = false; descriptor.description = 'changed outside snapshot';
  expect(s.getState().events[0].payload.synthetic).toBe(true);
  expect(s.getState().tools[0].description).not.toBe('changed outside snapshot');
  descriptor.description = 'Synthetic agent read';
  expect(t.events.mock.calls.map((c: any[]) => c[0])).toEqual([0, 1, 2]);
});
it.each([
  ['conflicting duplicate', page([event(1), event(1, {payload: {synthetic: false}})])],
  ['duplicate lamport', page([event(1), event(1, {id: 'e-other-identity'})])],
  ['out-of-order events', page([event(2), event(1)], {next_after: 2, head: 2})],
  ['event ahead of cursor', page([event(2)], {next_after: 1, head: 2, has_more: true})],
  ['cursor beyond head', page([], {next_after: 2, head: 1})],
  ['resync with events', page([event(1)], {resync: true})],
  ['non-progressing page', page([], {head: 2, next_after: 0, has_more: true})],
  ['incomplete terminal page', page([event(1)], {head: 2, next_after: 1, has_more: false})],
])('A18 rejects %s without publishing staged data', async (_name, bad) => {
  const s = await make(fakeTransport({events: vi.fn(async () => bad)}));
  await expect(s.refresh()).resolves.toBeUndefined();
  expect(s.getState()).toMatchObject({phase: 'error', head: null, events: [], error: {code: 'invalid_response'}});
});
it('A18 rejects a regressing refresh and preserves the committed revision', async () => {
  const t = fakeTransport({events: vi.fn().mockResolvedValueOnce(page([event(1), event(2)]))
    .mockResolvedValueOnce(page([], {head: 1, next_after: 1}))});
  const s = await make(t); await s.refresh(); const before = structuredClone(s.getState().events);
  await s.refresh(); expect(s.getState()).toMatchObject({head: 2, stale: true, error: {code: 'invalid_response'}});
  expect(s.getState().events).toEqual(before);
});
it('A19 late superseded responses cannot regress a newer snapshot', async () => {
  const old = deferred(); const recent = deferred(); const t = fakeTransport({events: vi.fn()
    .mockImplementationOnce(() => old.promise).mockImplementationOnce(() => recent.promise)});
  const s = await make(t); const one = s.refresh(); await flush(); const two = s.refresh(); await flush();
  recent.resolve(page([event(1), event(2)])); await two; old.resolve(page([event(1)])); await one;
  expect(s.getState()).toMatchObject({phase: 'ready', head: 2, error: null, stale: false});
});
it('A19 initial failure, stale failure and successful recovery have different truthful states', async () => {
  const failure = Object.assign(Error('Synthetic unavailable read'), {source: 'transport', code: 'network'});
  const t = fakeTransport({events: vi.fn().mockRejectedValueOnce(failure).mockResolvedValueOnce(page([event(1)]))
    .mockRejectedValueOnce(failure).mockResolvedValueOnce(page([], {head: 1, next_after: 1}))});
  const s = await make(t); await expect(s.refresh()).resolves.toBeUndefined();
  expect(s.getState()).toMatchObject({phase: 'error', head: null, error: {code: 'network'}});
  await s.refresh(); const committed = structuredClone(s.getState().events);
  await expect(s.refresh()).resolves.toBeUndefined();
  expect(s.getState()).toMatchObject({phase: 'error', head: 1, stale: true}); expect(s.getState().events).toEqual(committed);
  await s.refresh(); expect(s.getState()).toMatchObject({phase: 'ready', head: 1, stale: false, error: null});
});
it('A20 resync restarts from genesis, replaces the fold and clears unverified identity state', async () => {
  const t = fakeTransport({events: vi.fn().mockResolvedValueOnce(page([event(1), event(2)]))
    .mockResolvedValueOnce(page([], {resync: true})).mockResolvedValueOnce(page([event(1, {payload: {synthetic: 'replacement'}})]))});
  const s = await make(t); await s.refresh(); s.setSelection('agents', 'aurora-root'); s.setExpanded('agent', 'aurora-root', true);
  await s.refresh(); expect(t.events.mock.calls.map((c: any[]) => c[0])).toEqual([0, 2, 0]);
  expect(s.getState()).toMatchObject({head: 1, selection: {}, expanded: [], error: null});
  expect(s.getState().events[0].payload.synthetic).toBe('replacement');
});
it('A20 repeated resync fails once instead of spinning', async () => {
  const t = fakeTransport({events: vi.fn(async () => page([], {resync: true}))}); const s = await make(t);
  await s.refresh(); expect(t.events.mock.calls.length).toBeLessThanOrEqual(2);
  expect(s.getState()).toMatchObject({phase: 'error', head: null, error: {code: 'invalid_response'}});
});
it('A10 normal refresh preserves selected identity and tuple-based expansion', async () => {
  const s = await make(fakeTransport()); await s.refresh();
  s.setSelection('agent', 'aurora-root'); s.setExpanded('unit', 'id:[a]"b', true);
  const state = structuredClone(s.getState()); await s.refresh();
  expect(s.getState().selection).toEqual(state.selection); expect(s.getState().expanded).toEqual(state.expanded);
  s.setSelection('agent', null); s.setExpanded('unit', 'id:[a]"b', false);
  expect(s.getState().selection.agent).toBeUndefined(); expect(s.getState().expanded).toEqual([]);
});
it('A29 disposal aborts active requests and forbids late publishes or further calls', async () => {
  const pending = deferred(); const t = fakeTransport({events: vi.fn(() => pending.promise)});
  const s = await make(t); const listener = vi.fn(); const unsubscribe = s.subscribe(listener);
  const refresh = s.refresh(); await flush();
  const signal = t.events.mock.calls[0][1].signal; s.dispose(); const count = listener.mock.calls.length;
  expect(signal.aborted).toBe(true); pending.resolve(page([event(1)])); await refresh;
  expect(listener).toHaveBeenCalledTimes(count); expect(s.getState().head).toBeNull();
  const calls = t.events.mock.calls.length; await s.refresh(); expect(t.events).toHaveBeenCalledTimes(calls); unsubscribe();
});
it('A29 unsubscribe stops observations and getState snapshots do not change in place', async () => {
  const s = await make(fakeTransport()); const before = s.getState(); const observer = vi.fn(); const off = s.subscribe(observer);
  off(); const count = observer.mock.calls.length; await s.refresh();
  expect(observer).toHaveBeenCalledTimes(count); expect(before.head).toBeNull(); expect(s.getState().head).toBe(0);
});
