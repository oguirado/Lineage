import { expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
// A-U24: Vitest serves import.meta.url over HTTP; resolve source fixtures from its ui working directory.
import { resolve } from 'node:path';
import { startApp } from '../../src/main.ts';
import { parseRoute } from '../../src/router.ts';
import { actions } from '../../src/ui/contracts.ts';
import * as primitives from '../../src/ui/primitives.ts';
import '../../styles/lineage.css';
import { action, assertReadOnly, assertRelations, birth, births, canonical, click, controls, entry, exhaust,
  forest, ids, inherited, isolation, key, mount, name, node, search, seal, selected } from './fixtures.ts';
isolation();

const templates: Record<string, [string, string]> = {
  'filter-lineage-query': ['INPUT', 'Find lineage agent'], 'filter-lineage-root': ['SELECT', 'Lineage root'],
  'select-lineage-agent': ['BUTTON', 'Select lineage '], 'expand-lineage-agent': ['BUTTON', 'Expand lineage '],
  'collapse-lineage-agent': ['BUTTON', 'Collapse lineage '], 'open-lineage-agent': ['A', 'Inspect lineage '],
  'reset-lineage': ['BUTTON', 'Reset lineage filters'], 'expand-next-generation': ['BUTTON', 'Show next lineage generation'],
  'retry-panel': ['BUTTON', 'Retry Lineage'],
};
function assertActions(host: HTMLElement) {
  const exposed = controls(host), names = exposed.map(name);
  expect(exposed.length).toBeGreaterThan(0); expect(new Set(names).size).toBe(names.length);
  for (const control of exposed) {
    expect(control.closest('article,h1,h2,h3,h4,h5,h6,[role="heading"]')).toBeNull();
    const actionName = control.dataset.linAction!;
    expect(actions.has(actionName)).toBe(true); expect(templates[actionName]).toBeDefined();
    const [tag, template] = templates[actionName]; expect(control.tagName).toBe(tag);
    const identity = control.closest('[data-lin-entity="agent"]')?.getAttribute('data-lin-id');
    const recordAction = ['select-lineage-agent', 'expand-lineage-agent', 'collapse-lineage-agent', 'open-lineage-agent'].includes(actionName);
    expect(name(control)).toBe(recordAction ? template + key(identity!) : template);
    expect(new TextEncoder().encode(name(control)).length).toBeLessThanOrEqual(64);
    if (tag === 'BUTTON') expect((control as HTMLButtonElement).type).toBe('button');
    expect(Number(control.getAttribute('tabindex') ?? 0)).toBeLessThanOrEqual(0);
    expect(control.getAttribute('role') ?? '').not.toMatch(/tree|treeitem/u);
    if (actionName === 'select-lineage-agent') expect(['true', 'false']).toContain(control.getAttribute('aria-pressed'));
    if (actionName === 'expand-lineage-agent') expect(control.getAttribute('aria-expanded')).toBe('false');
    if (actionName === 'collapse-lineage-agent') expect(control.getAttribute('aria-expanded')).toBe('true');
  }
  for (const select of host.querySelectorAll('select')) {
    const labels = [...select.options].map(option => primitives.normalizeName(option.label));
    expect(new Set(labels).size).toBe(labels.length);
  }
  expect(host.querySelector('[role="tree"],[role="treeitem"]')).toBeNull();
  expect(host.querySelector('[onclick],[onkeydown],[role="button"]:not(button),[role="link"]:not(a)')).toBeNull();
}
it('A21 native action inventory retains unique bounded names for maximal IDs and duplicate display names', async () => {
  const a = 'agent-' + 'a'.repeat(58), b = 'agent-' + 'b'.repeat(58);
  const nodes = [node(a), node(b, [a], 1)], events = births(nodes);
  for (const e of events) (e.payload.record as any).display_name = 'Same duplicated name'; seal(events);
  const h = mount({nodes, events}); await h.ready; assertActions(h.host);
  for (const id of [a, b]) {
    const container = entry(h.host, id); expect(container.tagName).not.toBe('ARTICLE');
    expect(container.querySelector('h2,h3,h4,h5,h6,[role="heading"]')?.textContent).toBe(`Lineage agent ${key(id)}`);
    expect(container.textContent).toContain(id);
    for (const control of controls(container).filter(el => el.closest('[data-lin-entity="agent"]') === container)) {
      const descriptions = (control.getAttribute('aria-describedby') ?? '').split(/\s+/u)
        .map(ref => document.getElementById(ref)?.textContent ?? '').join(' ');
      expect(descriptions).toContain(id);
    }
  }
  expect((action(h.host, 'filter-lineage-query') as HTMLInputElement).type).toBe('search');
});
it('A21 key collision blocks ambiguous actions and readiness without ordinal fallback', async () => {
  vi.spyOn(primitives, 'identityKey').mockReturnValue('colliding-key');
  const h = mount(); await expect(h.ready).rejects.toBeDefined();
  expect(h.host.textContent).toContain('Identity key collision. Actions unavailable.');
  expect(controls(h.host).filter(el => el.dataset.linAction === 'select-lineage-agent' && !(el as HTMLButtonElement).disabled)).toHaveLength(0);
  expect(h.host.textContent).not.toMatch(/colliding-key-\d/u);
});
it('A21 action/prune assertions reject article-contained controls and duplicated names', async () => {
  const h = mount(); await h.ready; assertActions(h.host);
  const copy = h.host.cloneNode(true) as HTMLElement;
  const select = action(copy, 'select-lineage-agent', 'root-a'), article = document.createElement('article');
  select.replaceWith(article); article.append(select); expect(() => assertActions(copy)).toThrow();
  const other = h.host.cloneNode(true) as HTMLElement, first = action(other, 'select-lineage-agent', 'root-a');
  first.parentElement!.append(first.cloneNode(true)); expect(() => assertActions(other)).toThrow();
});
it('A5 A6 the edge oracle rejects an omitted secondary reference even if SVG survives', async () => {
  const h = mount(); await h.ready; await exhaust(h); assertRelations(h.host, h.nodes);
  const copy = h.host.cloneNode(true) as HTMLElement, secondary = entry(copy, 'clone-c');
  const walker = document.createTreeWalker(secondary, NodeFilter.SHOW_TEXT);
  for (let text = walker.nextNode(); text; text = walker.nextNode()) if (text.textContent?.includes('cross-e')) text.textContent = '';
  expect(() => assertRelations(copy, h.nodes)).toThrow();
});
it('A20 A21 SVG is decorative, unfocusable and carries no dispatch selectors', async () => {
  const h = mount(); await h.ready;
  const svg = h.host.querySelector('svg');
  // A genuinely unavailable drawing may fall back; it must leave actionable ancestry.
  if (svg) {
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(svg.querySelector('[data-lin-id],[data-lin-action],[data-lin-entity],a,button,input,select,[tabindex]')).toBeNull();
    for (const el of [svg, ...svg.querySelectorAll('*')]) expect([...el.attributes].some(a => /^on/iu.test(a.name))).toBe(false);
  } else expect(h.host.textContent).toContain('Tree drawing unavailable. Use the lineage list.');
  expect(ids(h.host)).toContain('clone-c'); assertActions(h.host);
});
it('A22 hostile text and receipt paths stay literal and never create executable nodes or external links', async () => {
  const nodes = forest(), events = births(nodes), child = birth(events, 'clone-c'), unit = inherited();
  const hostile = '<img src=x onerror="globalThis.compromised=true">';
  child.record.display_name = hostile; unit.unit.statement = '<script>globalThis.compromised=true</script>';
  // Path syntax is invalid evidence: it must be marked unavailable, never made a URL.
  unit.unit.receipts[0].path = 'javascript:globalThis.compromised=true'; child.inherited_units = [unit];
  child.constitution.text += '<iframe src="data:text/plain,passive"></iframe>\n';
  child.record.constitution_sha256 = 'c'.repeat(64); seal(events);
  const h = mount({nodes, events}); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  expect(h.host.textContent).toContain(hostile); expect(h.host.querySelector('img,script,iframe,object,embed')).toBeNull();
  for (const anchor of h.host.querySelectorAll('a')) expect(anchor.getAttribute('href')).toMatch(/^#\/agents\/[a-z][a-z0-9-]{2,63}(?:\?|$)/u);
  expect((globalThis as any).compromised).toBeUndefined(); expect(fetch).not.toHaveBeenCalled(); assertReadOnly(h);
});
it.each(['__proto__', 'constructor'] as const)('A22 prototype-shaped %s root and selected values reset safely and independently', async bad => {
  const prototype = Object.getOwnPropertyDescriptors(Object.prototype);
  const h = mount({query: {root: bad, selected: 'clone-c', q: 'clone'}}); await h.ready;
  selected(h, 'clone-c'); expect(h.host.textContent).toMatch(/invalid|ignored|reset/iu);
  await h.update({selected: bad, root: 'root-a', q: 'clone'});
  expect((action(h.host, 'filter-lineage-root') as HTMLSelectElement).value).toBe('root-a');
  expect(Object.getOwnPropertyDescriptors(Object.prototype)).toEqual(prototype);
});
it.each(['__proto__', 'constructor'] as const)('A22 U21 safely refuses the actual URL query key %s', async bad => {
  const resolution = parseRoute(`#/lineage?${bad}=passive&q=clone`);
  // Integrated U21 routes forbidden keys to its safe Agents fallback, rather than treating them as unknown fields.
  expect(resolution.route).toEqual({screen: 'agents', query: {}});
  expect(resolution.notice).toBe('Unknown page. Showing Agents.');
  const h = mount({query: {q: 'clone'}}); await h.ready; expect(ids(h.host)).toContain('clone-c'); assertReadOnly(h);
});
it.each(['__proto__', 'constructor'] as const)('A22 hostile rule_overrides key %s cannot alter prototypes or domain state', async bad => {
  const nodes = forest(), events = births(nodes), prototype = Object.getOwnPropertyDescriptors(Object.prototype);
  birth(events, 'clone-c').record.rule_overrides = JSON.parse(`{"${bad}":"add"}`); seal(events);
  const before = canonical(events), h = mount({nodes, events}); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  expect(Object.getOwnPropertyDescriptors(Object.prototype)).toEqual(prototype); expect(canonical(events)).toBe(before);
  expect(h.host.textContent).toMatch(/invalid|unavailable|ignored|__proto__|constructor/iu); assertReadOnly(h);
});
it('A10 unknown query fields use U21 visible notice without extending the URL schema', async () => {
  const resolution = parseRoute('#/lineage?q=clone&unknown=passive');
  expect(resolution.route.query).toEqual({q: 'clone'});
  const h = mount({query: {...resolution.route.query}, state: {notice: resolution.notice}}); await h.ready;
  expect(h.host.textContent).toContain('clone'); expect(resolution.notice).toBe('Unknown query fields ignored.');
  expect(h.transport.call).toHaveBeenCalled(); assertReadOnly(h); h.dispose(); document.body.replaceChildren();
  const root = document.createElement('div'); document.body.append(root);
  const app = startApp({root, transport: h.transport, storage: null, initialHash: '#/lineage?q=clone&unknown=passive'});
  try {await app.store.refresh(); expect(root.textContent).toContain('Unknown query fields ignored.');}
  finally {app.dispose();}
});
it('A20 A24 one persistent shell status survives lineage selection refresh and drawing fallback', async () => {
  const h = mount(); h.dispose(); document.body.replaceChildren();
  const root = document.createElement('div'); document.body.append(root);
  const app = startApp({root, transport: h.transport, storage: null, initialHash: '#/lineage'});
  try {
    await app.store.refresh();
    // The public ready predicate is the mounted screen fold, never a sleep.
    for (let turn = 0; turn < 48 && document.documentElement.dataset.linReady !== 'true'; turn++) await Promise.resolve();
    const main = root.querySelector('main')!, status = root.querySelector('[role="status"]');
    expect(status).not.toBeNull(); expect(name(status!)).toBe('Application updates');
    expect(document.documentElement.dataset.linRev).toBe(String(h.events.length));
    action(main, 'select-lineage-agent', 'clone-c').click(); await Promise.resolve();
    action(root, 'refresh-screen').click(); await app.store.refresh();
    expect(root.querySelector('[role="status"]')).toBe(status); expect(root.querySelectorAll('[role="status"]')).toHaveLength(1);
    expect(main.querySelector('[aria-live],[role="status"]')).toBeNull();
    expect(root.textContent).toContain('Synthetic fixtures. Changes are unavailable.');
  } finally {app.dispose();}
});
it('A24 unchanged reads do not flood announcements or move identity focus', async () => {
  const h = mount(); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  action(h.host, 'select-lineage-agent', 'clone-c').focus(); h.announce.mockClear();
  await h.update(); const count = h.announce.mock.calls.length; await h.update();
  expect(h.announce.mock.calls.length).toBe(count);
  expect(document.activeElement?.closest('[data-lin-entity="agent"]')?.getAttribute('data-lin-id')).toBe('clone-c');
});
it('A25 seeded reads and normalized identities ignore host clock and random sampling', async () => {
  vi.useFakeTimers(); vi.setSystemTime(0);
  const nodes = forest(), first = mount({nodes}); await first.ready; await exhaust(first);
  const before = ids(first.host); assertRelations(first.host, nodes); first.dispose(); first.host.remove();
  vi.setSystemTime(4102444800000); const random = vi.spyOn(Math, 'random'); random.mockClear();
  const second = mount({nodes: [...nodes].reverse()}); await second.ready; await exhaust(second);
  expect(ids(second.host)).toEqual(before); assertRelations(second.host, nodes); expect(random).not.toHaveBeenCalled();
  assertReadOnly(second);
});
it('A1 A26 stylesheet is owned and imported without claiming jsdom pixel acceptance', async () => {
  const h = mount(); await h.ready; expect(ids(h.host).length).toBeGreaterThan(0);
  // A-U24: Preserve both source assertions while using filesystem paths rather than HTTP module URLs.
  const entrySource = readFileSync(resolve('src/screens/lineage/index.ts'), 'utf8');
  expect(entrySource).toMatch(/import\s*['"][^'"]*styles\/lineage\.css['"]/u);
  const css = readFileSync(resolve('styles/lineage.css'), 'utf8');
  expect(css).toMatch(/lineage/u); // Geometry and computed contrast require the separate A26 gate.
});
it.todo('A26 external Chrome CDP pipe viewport contrast zoom themes and reduced-motion journey');
it.todo('A27 external AT-SPI prune-survival and independent junior/Big-Tech capsule journeys');
