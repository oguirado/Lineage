// @vitest-environment jsdom
import { it, expect, vi } from 'vitest';
import { source, text, host, route, fakeTransport, isolateDom } from './helpers.ts';
// A-U21R: Exercise the real fixed registry against deterministic screen doubles, not installed domain screens.
import { stubScreens } from './screen-stubs.ts';
isolateDom();
const cases = [
  ['agents', 'Agents', 'Agents: not built yet.', route()],
  ['agent', 'Agent', 'Agent detail: not built yet.', route('agent', {agentId: 'aurora-root'})],
  ['lineage', 'Lineage', 'Lineage: not built yet.', route('lineage')],
  // A-U21R: Benchmark detail uses the K0 bench route through the arena module.
  ['arena', 'Arena', 'Arena: not built yet.', route('bench', {benchId: 'bench_01'})],
  ['ledger', 'Ledger', 'Ledger: not built yet.', route('ledger')],
] as const;
it.each(cases)('A2 A28 fixed %s screen exposes an honest independent lifecycle', async (id, title, copy, selected) => {
  const module = await source(`screens/${id}/index.ts`, ['screen']); const screen = module.screen;
  // A-U21R: Verify that placeholder assertions target the injected double, never U22–U26 content.
  expect(screen).toBe(stubScreens[id]);
  expect(screen.id).toBe(id); expect(screen.title).toBe(title); expect(screen.mount).toBeTypeOf('function');
  const main = host('main'); const controller = new AbortController();
  const context = {route: selected, signal: controller.signal, transport: fakeTransport(),
    store: {getState: () => ({route: selected, tools: [], events: [], head: 0}), subscribe: () => () => {}},
    navigate: vi.fn(), announce: vi.fn()};
  const mounted = screen.mount(main, context);
  try {
    // A-U21R: Honor the screen render acknowledgement before checking its mounted DOM.
    await mounted.ready;
    expect(main.querySelectorAll('h1')).toHaveLength(1); expect(main.textContent).toContain(copy);
    expect(main.querySelector('main,header,nav,[role="status"]')).toBeNull();
    expect(main.querySelector('[data-lin-entity]')).toBeNull();
    expect(main.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled)')).toHaveLength(0);
    if ('agentId' in selected) expect(main.textContent).toContain(selected.agentId);
    if ('benchId' in selected) expect(main.textContent).toContain(selected.benchId);
    expect(mounted.update).toBeTypeOf('function'); expect(mounted.dispose).toBeTypeOf('function');
    // A-U21R: Await the shared update lifecycle while preserving all passive-data assertions.
    await mounted.update({...context, route: {...selected, query: {q: '<img src=x>'}}});
    expect(main.querySelector('img,script')).toBeNull(); expect(main.querySelectorAll('h1')).toHaveLength(1);
  } finally { mounted.dispose(); }
});
it('A2 registry contains every literal module and resolves through the shared route seam', async () => {
  const module = await source('screens/index.ts', ['screens', 'getScreen']);
  expect(Object.keys(module.screens).sort()).toEqual(['agent','agents','arena','ledger','lineage']);
  const registry = text('ui/src/screens/index.ts');
  for (const [id, , , selected] of cases) {
    expect(registry).toMatch(new RegExp(`['"]\\./${id}/index\\.ts['"]`));
    expect(module.getScreen(selected)).toBe(module.screens[id]);
  }
  expect(registry).not.toMatch(/import\.meta\.glob/);
});
