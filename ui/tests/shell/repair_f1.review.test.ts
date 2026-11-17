// @vitest-environment jsdom
import { expect, it, vi } from 'vitest';
import { app, fakeTransport, fixture, flush, isolateDom, response, source } from './helpers.ts';
import { stubScreens } from './screen-stubs.ts';
import type { ScreenContext } from '../../src/ui/contracts.ts';

isolateDom();

it('B1 Retry remounts after a rejected initial ready promise', async () => {
  let failedSignal: AbortSignal | undefined;
  const dispose = vi.fn(() => expect(failedSignal?.aborted).toBe(true));
  const mount = vi.spyOn(stubScreens.lineage, 'mount').mockImplementationOnce((host, context) => {
    failedSignal = context.signal;
    const heading = document.createElement('h1'); heading.textContent = 'Lineage';
    host.replaceChildren(heading);
    return {ready: Promise.reject(Error('Synthetic initial read failure')), update: async () => {}, dispose};
  });
  const {root, handle} = await app(fakeTransport(), '#/lineage');
  const status = root.querySelector('[role="status"]');
  expect(document.documentElement.dataset.linReady).toBe('false');
  expect(root.textContent).toContain('The screen could not be rendered.');
  (root.querySelector('[data-lin-action="retry-panel"]') as HTMLButtonElement).click();
  await flush();
  expect(mount).toHaveBeenCalledTimes(2);
  expect(dispose).toHaveBeenCalledOnce();
  expect(handle.store.getState().head).toBe(0);
  expect(document.documentElement.dataset.linReady).toBe('true');
  expect(root.textContent).not.toContain('The screen could not be rendered.');
  expect(root.querySelector('[role="status"]')).toBe(status);
});

it('B1 a synchronous mount throw releases the previous mounted screen exactly once', async () => {
  let agentContext: ScreenContext;
  const dispose = vi.fn(() => expect(agentContext.signal.aborted).toBe(true));
  vi.spyOn(stubScreens.agents, 'mount').mockImplementationOnce((host, context) => {
    agentContext = context;
    const heading = document.createElement('h1'); heading.textContent = 'Agents';
    host.replaceChildren(heading);
    return {ready: Promise.resolve(), update: async next => {agentContext = next;}, dispose};
  });
  const lineageMount = vi.spyOn(stubScreens.lineage, 'mount').mockImplementationOnce(() => {
    throw Error('Synthetic mount failure');
  });
  const {root} = await app();
  (root.querySelector('[data-lin-action="nav-lineage"]') as HTMLAnchorElement).click();
  await flush();
  expect(dispose).toHaveBeenCalledOnce();
  expect(document.documentElement.dataset.linReady).toBe('false');
  (root.querySelector('[data-lin-action="retry-panel"]') as HTMLButtonElement).click();
  await flush();
  expect(lineageMount).toHaveBeenCalledTimes(2);
  expect(dispose).toHaveBeenCalledOnce();
  expect(document.documentElement.dataset.linReady).toBe('true');
  expect(root.querySelector('h1')?.textContent).toBe('Lineage');
});

it.each(['agents', 'lineage'] as const)('B2 %s query navigation preserves typing focus and path history', async screen => {
  let context: ScreenContext;
  let input: HTMLInputElement;
  const update = vi.fn(async (next: ScreenContext) => {
    if (next.signal !== context.signal) expect(context.signal.aborted).toBe(true);
    context = next; input.value = next.route.query.q ?? '';
  });
  vi.spyOn(stubScreens[screen], 'mount').mockImplementation((host, initial) => {
    context = initial;
    const heading = document.createElement('h1'); heading.textContent = screen === 'agents' ? 'Agents' : 'Lineage';
    input = document.createElement('input');
    input.dataset.linAction = screen === 'agents' ? 'filter-agent-query' : 'filter-lineage-query';
    input.setAttribute('aria-label', screen === 'agents' ? 'Search agents' : 'Search lineage');
    input.addEventListener('input', () => context.navigate({...context.route, query: {...context.route.query, q: input.value}}));
    host.replaceChildren(heading, input);
    return {ready: Promise.resolve(), update, dispose() {expect(context.signal.aborted).toBe(true);}};
  });
  const {root, handle} = await app(fakeTransport(), `#/${screen}`);
  const status = root.querySelector('[role="status"]');
  const filter = root.querySelector('main input') as HTMLInputElement;
  update.mockClear();
  expect(document.activeElement).toBe(root.querySelector('h1'));
  filter.focus();
  for (const character of 'ab') {
    // Dispatch to the focused control so focus stolen after the first letter loses the second.
    const active = document.activeElement as HTMLInputElement;
    active.value += character; active.dispatchEvent(new Event('input', {bubbles: true}));
    await flush();
    expect(document.activeElement).toBe(filter);
  }
  expect(filter.value).toBe('ab');
  expect(handle.store.getState().route.query.q).toBe('ab');
  expect(update).toHaveBeenCalledTimes(2);
  expect(document.documentElement.dataset.linReady).toBe('true');
  expect(root.querySelector('[role="status"]')).toBe(status);
  // A changed path still focuses the new destination; returning restores the filter.
  (root.querySelector('[data-lin-action="nav-ledger"]') as HTMLAnchorElement).click();
  await flush(); expect(document.activeElement).toBe(root.querySelector('h1'));
  history.replaceState(null, '', `#/${screen}?q=ab`);
  window.dispatchEvent(new HashChangeEvent('hashchange')); await flush();
  expect(document.activeElement?.getAttribute('data-lin-action')).toBe(filter.dataset.linAction);
});

it.each([null, 'synthetic-session'] as const)('B3 read classified as mutation rejects before fetch (token %s)', async sessionToken => {
  const {createHttpTransport} = await source('transport.ts');
  const fetchImpl = vi.fn(async () => response({untrusted: {synthetic: true}}));
  const transport = createHttpTransport({fetchImpl, sessionToken, timeoutMs: 100});
  await expect(transport.call('agent_get', {}, {mutation: true})).rejects.toMatchObject({source: 'domain', code: 'bad_args'});
  expect(fetchImpl).not.toHaveBeenCalled();
  await expect(transport.call('agent_get', {}, {mutation: false})).resolves.toEqual({synthetic: true});
  expect(fetchImpl).toHaveBeenCalledOnce();
});

it('B3 A16 ledger_export is protected but requires no invented operation identity', async () => {
  const {createHttpTransport} = await source('transport.ts');
  const fetchImpl = vi.fn(async () => response({untrusted: {synthetic: true}}));
  const transport = createHttpTransport({fetchImpl, sessionToken: 'synthetic-session', timeoutMs: 100});
  const args = {format: 'json'};
  await expect(transport.call('ledger_export', args, {mutation: false})).rejects.toMatchObject({source: 'domain', code: 'bad_args'});
  expect(fetchImpl).not.toHaveBeenCalled();
  await expect(transport.call('ledger_export', args, {mutation: true})).resolves.toEqual({synthetic: true});
  expect(fetchImpl).toHaveBeenCalledOnce();
  const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
  expect(JSON.parse(init.body as string)).toEqual({tool: 'ledger_export', args});
  expect(new Headers(init.headers).get('X-Lineage-Session')).toBe('synthetic-session');
});

it.each([false, true])('B3 fixture calls preserve fixture_readonly for mutations (classification %s)', async mutation => {
  const {createFixtureTransport} = await source('transport.ts');
  const transport = createFixtureTransport(fixture());
  await expect(transport.call('ledger_export', {}, {mutation})).rejects.toMatchObject({source: 'domain', code: 'fixture_readonly'});
  await expect(transport.call('agent_list', {}, {mutation: true})).rejects.toMatchObject({source: 'domain', code: 'fixture_readonly'});
});
