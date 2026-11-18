// @vitest-environment jsdom
import { expect, it, vi } from 'vitest';
import { accessibleName, app, event, fakeTransport, fixture, flush, isolateDom, page, response, source } from './helpers.ts';
import { stubScreens } from './screen-stubs.ts';
import { descriptors as ledgerTools } from '../ledger/fixtures.ts';
import type { ScreenContext, ScreenModule } from '../../src/ui/contracts.ts';

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


it('R49 the real Find agents input publishes an ordinary named status', async () => {
  const {screen} = await vi.importActual<{screen: ScreenModule}>('../../src/screens/agents/index.ts');
  vi.spyOn(stubScreens.agents, 'mount').mockImplementation(screen.mount);
  const transport = fakeTransport({
    call: vi.fn(async () => ({agents: [], next_after: null, head: 0})),
  });
  const {root, handle} = await app(transport);
  const field = root.querySelector<HTMLInputElement>('[data-lin-action="filter-agent-query"]')!;
  field.focus();
  field.value = 'error-handler';
  field.dispatchEvent(new Event('input', {bubbles: true}));
  await flush();

  expect(handle.store.getState().route.query.q).toBe('error-handler');
  expect(document.activeElement).toBe(field);
  const outcome = root.querySelector<HTMLOutputElement>('output.action-outcome')!;
  expect(outcome.hidden).toBe(false);
  expect(outcome.getAttribute('role')).toBeNull(); // Native output has the status role.
  expect(accessibleName(outcome)).toBe('Find agents: error-handler');
});

it('R49 Ledger export validation publishes a named alert and returns focus to the field', async () => {
  const {screen} = await vi.importActual<{screen: ScreenModule}>('../../src/screens/ledger/index.ts');
  vi.spyOn(stubScreens.ledger, 'mount').mockImplementation(screen.mount);
  const transport = fakeTransport({
    tools: vi.fn(async () => ledgerTools),
    call: vi.fn(async (tool: string) => {
      if (tool !== 'ledger_events') throw Error('Unexpected tool: ' + tool);
      return page();
    }),
  });
  const {root} = await app(transport, '#/ledger');
  await flush();
  root.querySelector<HTMLButtonElement>('[data-lin-action="export-ledger"]')!.click();
  const dialog = root.querySelector<HTMLDialogElement>('dialog[open]')!;
  const field = dialog.querySelector<HTMLInputElement>('input[name="out"]')!;
  const confirm = dialog.querySelector<HTMLButtonElement>('[data-lin-action="submit-dialog"]')!;
  field.value = 'outside';
  field.dispatchEvent(new Event('input', {bubbles: true}));
  confirm.focus();
  confirm.click();

  expect(field.getAttribute('aria-invalid')).toBe('true');
  expect(document.activeElement).toBe(field);
  expect(transport.call.mock.calls.map(([tool]: [string]) => tool)).not.toContain('ledger_export');
  const outcome = root.querySelector<HTMLOutputElement>('output.action-outcome')!;
  expect(outcome.hidden).toBe(false);
  expect(outcome.getAttribute('role')).toBe('alert');
  expect(accessibleName(outcome)).toBe('Error: Export ledger refused: bad_args.');
});

it('R49 refresh announces a removed focused identity while preserving the confirmed outcome', async () => {
  const confirmed = 'Create agent recorded for aurora-born.';
  vi.spyOn(stubScreens.agents, 'mount').mockImplementation((host, context) => {
    const heading = document.createElement('h1');
    heading.textContent = 'Agents';
    const record = document.createElement('a');
    record.href = '#/agents/error-handler';
    record.textContent = 'Open agent error-handler';
    record.dataset.linEntity = 'agent';
    record.dataset.linId = 'error-handler';
    record.dataset.linAction = 'open-agent';
    const create = document.createElement('button');
    create.textContent = 'Create agent';
    create.dataset.linAction = 'create-agent';
    create.addEventListener('click', () => context.announce('created:aurora-born:confirmed', confirmed));
    host.replaceChildren(heading, record, create);
    return {
      ready: Promise.resolve(),
      async update(next) {
        // Screen reads complete asynchronously before replacing the focused record.
        await Promise.resolve();
        if (next.store.getState().events.some(entry => entry.kind === 'agent.status')) record.remove();
      },
      dispose() {},
    };
  });
  const transport = fakeTransport({
    events: vi.fn().mockResolvedValueOnce(page())
      .mockResolvedValueOnce(page([event(1, {kind: 'agent.status'})]))
      .mockResolvedValue(page([], {head: 1, next_after: 1})),
  });
  const {root, handle} = await app(transport);
  const main = root.querySelector('main')!;
  const updates = root.querySelector<HTMLElement>('[role="status"][aria-label="Application updates"]')!;
  const outcome = root.querySelector<HTMLOutputElement>('output.action-outcome')!;
  root.querySelector<HTMLButtonElement>('[data-lin-action="create-agent"]')!.click();
  expect(outcome.hidden).toBe(false);
  expect(accessibleName(outcome)).toBe(confirmed);
  expect(outcome.getAttribute('role')).toBeNull();
  const record = root.querySelector<HTMLAnchorElement>('[data-lin-action="open-agent"]')!;
  record.focus();
  expect(document.activeElement).toBe(record);

  const outcomeWrites: MutationRecord[] = [];
  const writes = new MutationObserver(records => outcomeWrites.push(...records));
  writes.observe(outcome, {attributes: true, childList: true});
  try {
    await handle.store.refresh();
    await flush();
    expect(record.isConnected).toBe(false);
    expect(document.activeElement).toBe(main);
    expect(accessibleName(outcome)).toBe(confirmed);
    expect(outcome.getAttribute('role')).toBeNull();
    expect(updates.textContent).toBe('error-handler is no longer in this view.');
    await handle.store.refresh();
    await flush();
    expect(document.activeElement).toBe(main);
    expect(outcome.hidden).toBe(false);
    expect(accessibleName(outcome)).toBe(confirmed);
    expect(root.querySelector('.application-status')).toBe(updates);
    expect(root.querySelector('.action-outcome')).toBe(outcome);
    expect([...outcomeWrites, ...writes.takeRecords()]).toEqual([]);

    root.querySelector<HTMLButtonElement>('[data-lin-action="theme-dark"]')!.click();
    expect(outcome.hidden).toBe(true);
    expect(outcome.hasAttribute('aria-label')).toBe(false);
  } finally {
    writes.disconnect();
  }
});
