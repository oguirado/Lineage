// @vitest-environment jsdom
import { it, expect, vi } from 'vitest';
import { resolve } from 'node:path';
import { source, app, host, own, fakeTransport, event, page, route, deferred, flush,
  isolateDom, accessibleName, controls, root as repoRoot } from './helpers.ts';
// A-U21R: Controlled render acknowledgements verify the shell gate independently of domain reads.
import { stubScreens } from './screen-stubs.ts';
isolateDom();
const cases = [
  ['#/agents','agents','agents','Agents'], ['#/agents/aurora-root','agent','agents','Agent'],
  ['#/lineage','lineage','lineage','Lineage'], ['#/arena','arena','arena','Arena'],
  ['#/arena/bench_01','bench','arena','Benchmark'], ['#/ledger','ledger','ledger','Ledger'],
] as const;
it.each(cases)('A3 A33 K0 landmarks, active navigation and title on %s', async (hash, screen, owner, title) => {
  const {root} = await app(fakeTransport(), hash);
  expect(root.querySelectorAll('header,[role="banner"]')).toHaveLength(1);
  expect(root.querySelectorAll('nav[aria-label="Primary"]')).toHaveLength(1);
  expect(root.querySelectorAll('main')).toHaveLength(1); expect(root.querySelectorAll('h1')).toHaveLength(1);
  const main = root.querySelector('main')!; expect(main.id).toBe('main-content');
  expect(main.getAttribute('data-lin-screen')).toBe(screen);
  expect(root.querySelectorAll('[role="status"]')).toHaveLength(1);
  expect(accessibleName(root.querySelector('[role="status"]')!)).toBe('Application updates');
  expect(root.querySelectorAll('[aria-current="page"]')).toHaveLength(1);
  expect(root.querySelector('[aria-current="page"]')?.getAttribute('data-lin-action')).toBe(`nav-${owner}`);
  expect(root.querySelector('h1')!.textContent).toContain(title); expect(document.title).toBe(`Lineage · ${title}`);
  for (const name of ['agents','lineage','arena','ledger']) {
    const link = root.querySelector(`[data-lin-action="nav-${name}"]`)!;
    expect(link.tagName).toBe('A'); expect(accessibleName(link)).toBe(`${name[0].toUpperCase() + name.slice(1)} navigation`);
  }
  expect(root.querySelector('[data-lin-action="skip-main"]')?.tagName).toBe('A');
  expect(document.documentElement.dataset.linReady).toBe('true'); expect(document.documentElement.dataset.linRev).toBe('0');
});
it('A10 skip link retains the hash and focuses the persistent main', async () => {
  const {root} = await app(); const before = location.hash;
  (root.querySelector('[data-lin-action="skip-main"]') as HTMLAnchorElement).click();
  expect(location.hash).toBe(before); expect(document.activeElement).toBe(root.querySelector('main'));
  expect(controls(root).every(el => Number(el.getAttribute('tabindex') ?? '0') <= 0)).toBe(true);
});
it('A6 A29 replacement screen aborts before disposal and updates same-screen identities', async () => {
  await source('screens/index.ts', ['screens', 'getScreen']);
  const id = resolve(repoRoot, 'ui/src/screens/index.ts'); const lifecycle: string[] = []; let context: any;
  const replacement = {id: 'agent', title: 'Agent', mount: vi.fn((main: HTMLElement, c: any) => {
    context = c; lifecycle.push('mount'); const heading = document.createElement('h1'); heading.textContent = 'Agent'; main.replaceChildren(heading);
    // A-U21R: The replacement honors the shared ready/update promise contract.
    return {ready: Promise.resolve(), update: vi.fn(async (next: any) => {context = next; lifecycle.push('update');}),
      dispose: vi.fn(() => {expect(context.signal.aborted).toBe(true); lifecycle.push('dispose');})};
  })};
  vi.resetModules(); vi.doMock(id, async () => {
    const actual: any = await vi.importActual(id);
    return {...actual, screens: {...actual.screens, agent: replacement},
      getScreen: (r: any) => r.screen === 'agent' ? replacement : actual.getScreen(r)};
  });
  let handle: any;
  try {
    const result = await app(fakeTransport(), '#/agents/aurora-root'); handle = result.handle;
    const status = result.root.querySelector('[role="status"]'); const banner = result.root.querySelector('header');
    history.replaceState(null, '', '#/agents/aurora-child'); window.dispatchEvent(new HashChangeEvent('hashchange')); await flush();
    expect(replacement.mount).toHaveBeenCalledOnce(); expect(context.route.agentId).toBe('aurora-child');
    expect(lifecycle).toContain('update');
    history.replaceState(null, '', '#/ledger'); window.dispatchEvent(new HashChangeEvent('hashchange')); await flush();
    expect(lifecycle.filter(s => s === 'dispose')).toHaveLength(1);
    expect(result.root.querySelector('[role="status"]')).toBe(status); expect(result.root.querySelector('header')).toBe(banner);
  } finally {handle?.dispose(); vi.doUnmock(id); vi.resetModules();}
});
it('A12 A19 stale failure preserves content/revision, and explicit read Retry recovers', async () => {
  const failure = Object.assign(Error('Synthetic read unavailable'), {source: 'transport', code: 'network'});
  const t = fakeTransport({events: vi.fn().mockResolvedValueOnce(page([event(1)]))
    .mockRejectedValueOnce(failure).mockResolvedValueOnce(page([], {head: 1, next_after: 1}))});
  const {root, handle} = await app(t); const status = root.querySelector('[role="status"]'); const heading = root.querySelector('h1');
  await handle.store.refresh(); await flush(); expect(root.querySelector('h1')).toBe(heading);
  expect(root.textContent).toMatch(/stale/i); expect(root.textContent).toContain('network');
  expect(document.documentElement.dataset.linReady).toBe('true'); expect(document.documentElement.dataset.linRev).toBe('1');
  // K0 owns retry selectors/names; the U21 Data error region remains required.
  const panel = root.querySelector('[role="region"][aria-label="Data error"]'); expect(panel).not.toBeNull();
  const retry = Array.from(panel!.querySelectorAll('button')).find(el => /^Retry /u.test(accessibleName(el)));
  expect(retry).toBeDefined(); expect(retry!.dataset.linAction).toBe('retry-panel'); retry!.click(); await flush();
  expect(handle.store.getState().error).toBeNull(); expect(root.querySelector('[role="status"]')).toBe(status);
  expect(root.querySelector('[role="alert"]')).toBeNull(); expect(root.querySelectorAll('[role="status"]')).toHaveLength(1);
});
it('A17 readiness never precedes both held inputs; disposal removes revision', async () => {
  const tools = deferred(); const events = deferred(); const t = fakeTransport({tools: vi.fn(() => tools.promise), events: vi.fn(() => events.promise)});
  const {root, handle} = await app(t);
  expect(document.documentElement.dataset.linReady).toBe('false'); expect(document.documentElement.hasAttribute('data-lin-rev')).toBe(false);
  tools.resolve([]); await flush(); expect(document.documentElement.dataset.linReady).toBe('false');
  events.resolve(page()); await flush(); expect(document.documentElement.dataset.linReady).toBe('true');
  handle.dispose(); expect(document.documentElement.dataset.linReady).toBe('false'); expect(document.documentElement.hasAttribute('data-lin-rev')).toBe(false);
});
it('A20 visible resync warning survives until the replacement fold completes', async () => {
  const final = deferred(); const t = fakeTransport({events: vi.fn().mockResolvedValueOnce(page([event(1)]))
    .mockResolvedValueOnce(page([], {resync: true})).mockImplementationOnce(() => final.promise)});
  const {root, handle} = await app(t); const refresh = handle.store.refresh(); await flush();
  expect(root.textContent).toContain('Ledger changed.'); final.resolve(page()); await refresh;
});
it('A24 A33 K0 theme controls change tokens, survive storage denial and preserve focus', async () => {
  const storage = {getItem: vi.fn(() => {throw Error('denied');}), setItem: vi.fn(() => {throw Error('denied');})} as unknown as Storage;
  const {root, handle} = await app(fakeTransport(), '#/agents', storage);
  const dark = root.querySelector('[data-lin-action="theme-dark"]') as HTMLButtonElement;
  const light = root.querySelector('[data-lin-action="theme-light"]') as HTMLButtonElement;
  expect(dark).not.toBeNull(); expect(light).not.toBeNull(); expect(accessibleName(dark)).toBe('Use dark theme');
  dark.focus(); dark.click(); expect(document.activeElement).toBe(dark); expect(dark.getAttribute('aria-pressed')).toBe('true');
  light.click(); expect(light.getAttribute('aria-pressed')).toBe('true'); expect(dark.getAttribute('aria-pressed')).toBe('false');
  expect(handle.store.getState().error).toBeNull();
});
it('A16 A24 session secret never reaches state, DOM, URL or theme storage', async () => {
  const {createHttpTransport} = await source('transport.ts', ['createHttpTransport']); const writes: any[] = [];
  const storage = {getItem: () => null, setItem: (key: string, value: string) => writes.push([key,value])} as unknown as Storage;
  const token = 'synthetic-private-session'; const t = createHttpTransport({sessionToken: token, timeoutMs: 100,
    fetchImpl: vi.fn(async (url: any) => ({ok: true, status: 200, json: async () => String(url).includes('/tools') ? {tools: []} : page(),
      text: async () => JSON.stringify(String(url).includes('/tools') ? {tools: []} : page())}))});
  const {root, handle} = await app(t, '#/agents', storage);
  (root.querySelector('[data-lin-action="theme-dark"]') as HTMLButtonElement).click();
  expect(JSON.stringify(handle.store.getState())).not.toContain(token); expect(root.outerHTML).not.toContain(token);
  expect(location.href).not.toContain(token); expect(JSON.stringify(writes)).not.toContain(token);
  expect(writes.every(([key,value]) => !/agent|event|token|session/u.test(key) && /light|dark|system/u.test(value))).toBe(true);
});
it('A29 disposal silences hash listeners, outstanding reads and open dialogs across remounts', async () => {
  const pending = deferred(); const t = fakeTransport({events: vi.fn(() => pending.promise)});
  const {root, handle} = await app(t); const status = root.querySelector('[role="status"]');
  const {openDialog} = await source('ui/dialog.ts', ['openDialog']);
  const trigger = root.querySelector('a') as HTMLElement; const fallback = root.querySelector('main') as HTMLElement;
  openDialog({name: 'Synthetic inspector', content: document.createElement('div'), trigger, fallback, host: root});
  handle.dispose(); const before = root.innerHTML; const count = t.events.mock.calls.length;
  pending.resolve(page([event(1)])); await flush();
  history.replaceState(null, '', '#/ledger'); window.dispatchEvent(new HashChangeEvent('hashchange')); await flush();
  expect(t.events).toHaveBeenCalledTimes(count); expect(root.innerHTML).toBe(before);
  expect(root.querySelector('dialog[open]')).toBeNull(); expect(document.documentElement.dataset.linReady).toBe('false');
  const mounted = await app(); expect(mounted.root.querySelectorAll('[role="status"]')).toHaveLength(1);
});

// A-U21R: A committed empty fold alone must not bypass the screen's initial render gate.
it('A17 committed data waits for the screen render acknowledgement', async () => {
  const ready = deferred<void>(); const mount = stubScreens.agents.mount;
  vi.spyOn(stubScreens.agents, 'mount').mockImplementationOnce((host, context) => ({
    ...mount(host, context), ready: ready.promise,
  }));
  const {root, handle, transport} = await app();
  expect(handle.store.getState().head).toBe(0);
  expect(root.querySelectorAll('h1')).toHaveLength(1);
  expect(document.documentElement.dataset.linReady).toBe('false');
  expect(transport.call).not.toHaveBeenCalled();
  ready.resolve(); await flush();
  expect(document.documentElement.dataset.linReady).toBe('true');
  expect(document.documentElement.dataset.linRev).toBe('0');
});

// A-U21R: An obsolete acknowledgement cannot ready a newer identity before its update completes.
it('A6 A17 A29 same-module navigation waits for the matching render acknowledgement', async () => {
  const ready = deferred<void>(); const updated = deferred<void>();
  const mount = stubScreens.agent.mount; let signal!: AbortSignal;
  vi.spyOn(stubScreens.agent, 'mount').mockImplementationOnce((host, context) => {
    signal = context.signal; const mounted = mount(host, context);
    return {...mounted, ready: ready.promise, async update(next) {
      await mounted.update(next);
      if (next.route.screen === 'agent' && next.route.agentId === 'aurora-child') {
        expect(signal.aborted).toBe(true); await updated.promise;
      }
    }};
  });
  const {root} = await app(fakeTransport(), '#/agents/aurora-root');
  const status = root.querySelector('[role="status"]'); const banner = root.querySelector('header');
  history.replaceState(null, '', '#/agents/aurora-child');
  window.dispatchEvent(new HashChangeEvent('hashchange')); await flush();
  expect(signal.aborted).toBe(true);
  ready.resolve(); await flush();
  expect(document.documentElement.dataset.linReady).toBe('false');
  updated.resolve(); await flush();
  expect(document.documentElement.dataset.linReady).toBe('true');
  expect(root.querySelector('h1')?.textContent).toBe('Agent aurora-child');
  expect(root.querySelector('[role="status"]')).toBe(status); expect(root.querySelector('header')).toBe(banner);
});
