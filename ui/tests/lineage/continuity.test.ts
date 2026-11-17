import { expect, it, vi } from 'vitest';
import { formatRoute, parseRoute } from '../../src/router.ts';
import { ABSENT, action, assertReadOnly, assertRelations, birth, births, broad, click, controls, deep, drain, entry,
  exhaust, forest, ids, isolation, key, mount, node, search, selected } from './fixtures.ts';
isolation();

it('A10 reload restores full root query and selected identities through the U21 route', async () => {
  const query = {root: 'root-a', q: 'clone', selected: 'clone-c'};
  const parsed = parseRoute(formatRoute({screen: 'lineage', query}));
  const h = mount({query: {...parsed.route.query}}); await h.ready;
  expect((action(h.host, 'filter-lineage-root') as HTMLSelectElement).value).toBe('root-a');
  expect((action(h.host, 'filter-lineage-query') as HTMLInputElement).value).toBe('clone');
  selected(h, 'clone-c'); expect(h.host.textContent).toContain(birth(h.events, 'clone-c').record.agent_version);
});
it('A10 back and forward updates restore the corresponding full selected identity', async () => {
  const h = mount({query: {selected: 'clone-c'}}); await h.ready; selected(h, 'clone-c');
  await h.update({selected: 'distill-d'}); selected(h, 'distill-d');
  await h.update({selected: 'clone-c'}); selected(h, 'clone-c');
  await h.update({selected: 'distill-d'}); selected(h, 'distill-d'); assertReadOnly(h);
});
it.each(['root', 'selected'] as const)('A10 invalid %s resets only that field with a visible notice', async field => {
  const query = {root: 'root-a', q: 'clone', selected: 'clone-c', [field]: 'INVALID/ID'};
  const h = mount({query}); await h.ready;
  expect(h.host.textContent).toMatch(/invalid|ignored|reset/iu);
  expect((action(h.host, 'filter-lineage-query') as HTMLInputElement).value).toBe('clone');
  if (field === 'root') selected(h, 'clone-c');
  else expect((action(h.host, 'filter-lineage-root') as HTMLSelectElement).value).toBe('root-a');
});
it('A10 an unavailable valid root does not select a different genesis', async () => {
  const h = mount({query: {root: 'unknown-root'}});
  await drain(); expect(h.readyState.value).not.toBe('fulfilled');
  expect(h.host.textContent).toMatch(/no_agent|unavailable/iu);
  expect(ids(h.host)).not.toContain('root-a');
});
it('A10 reset selects the first actual deterministic genesis, independent of response order', async () => {
  const nodes = [node('zeta-root'), node('beta-root')];
  const h = mount({nodes, query: {root: 'zeta-root', q: 'zeta', selected: 'zeta-root'}}); await h.ready;
  await click(h, 'reset-lineage'); selected(h, 'beta-root');
  expect((action(h.host, 'filter-lineage-query') as HTMLInputElement).value).toBe('');
  expect((action(h.host, 'filter-lineage-root') as HTMLSelectElement).value).toBe('');
  const last = h.navigation.at(-1); expect(last?.query.root).toBeUndefined(); expect(last?.query.q).toBeUndefined();
});
it('A10 resetting an empty tree invents no selected identity', async () => {
  const h = mount({nodes: []}); await h.ready; await click(h, 'reset-lineage');
  expect(h.store.getState().selection.lineage).toBeUndefined(); expect(ids(h.host)).toEqual([]);
});
it('A11 refresh and reordered births preserve selected full identity focus expansion and scroll', async () => {
  const h = mount(); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  await click(h, 'expand-lineage-agent', 'distill-d');
  expect(h.store.getState().expanded).toContain(JSON.stringify(['agent', 'distill-d']));
  const focus = action(h.host, 'select-lineage-agent', 'clone-c'); focus.focus();
  h.host.scrollTop = 37; const expansion = [...h.store.getState().expanded];
  const reordered = {nodes: [...h.nodes].reverse(), head: h.events.length};
  vi.mocked(h.transport.call).mockResolvedValue(reordered);
  await h.update(); selected(h, 'clone-c');
  expect(document.activeElement?.closest('[data-lin-entity="agent"]')?.getAttribute('data-lin-id')).toBe('clone-c');
  expect((document.activeElement as HTMLElement).dataset.linAction).toBe('select-lineage-agent');
  expect(h.store.getState().expanded).toEqual(expansion); expect(h.host.scrollTop).toBe(37);
});
it('A11 typing preserves search focus and caret while changing display text cannot redirect actions', async () => {
  const h = mount(); await h.ready;
  const input = action(h.host, 'filter-lineage-query') as HTMLInputElement; input.focus(); input.value = 'clone'; input.setSelectionRange(2, 2);
  input.dispatchEvent(new Event('input', {bubbles: true})); await h.settled();
  const current = action(h.host, 'filter-lineage-query') as HTMLInputElement;
  expect(document.activeElement).toBe(current); expect(current.selectionStart).toBe(2); expect(current.selectionEnd).toBe(2);
  await click(h, 'select-lineage-agent', 'clone-c');
  const events = structuredClone(h.events); birth(events, 'clone-c').record.display_name = 'Same name as another agent';
  h.publish({events}); await h.update(); selected(h, 'clone-c');
});
it('A11 inspect and return use the full router identity and retain selection', async () => {
  const h = mount(); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  const link = action(h.host, 'open-lineage-agent', 'clone-c');
  expect(link.tagName).toBe('A'); expect(link.getAttribute('href')).toBe(formatRoute({screen: 'agent', agentId: 'clone-c', query: {}}));
  const query = h.navigation.at(-1)?.query ?? {selected: 'clone-c'};
  h.dispose(); const returned = mount({query: {...query}}); await returned.ready; selected(returned, 'clone-c');
});
it('A12 collapse restores focus to the surviving branch disclosure and explains hidden selection', async () => {
  const h = mount(); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  action(h.host, 'select-lineage-agent', 'clone-c').focus();
  await click(h, 'collapse-lineage-agent', 'root-a');
  expect(document.activeElement).toBe(action(h.host, 'expand-lineage-agent', 'root-a'));
  expect(ids(h.host)).not.toContain('clone-c'); expect(h.host.textContent).toMatch(/selected.*(?:hidden|collapsed|filtered)|(?:hidden|collapsed).*selected/iu);
  await click(h, 'expand-lineage-agent', 'root-a'); selected(h, 'clone-c');
});
it('A12 removal clears only the missing identity, focuses the panel heading and announces once', async () => {
  const h = mount(); await h.ready; await exhaust(h); await click(h, 'select-lineage-agent', 'specialize-g');
  action(h.host, 'select-lineage-agent', 'specialize-g').focus(); h.announce.mockClear();
  const nodes = h.nodes.filter(n => n.agent_id !== 'specialize-g');
  vi.mocked(h.transport.call).mockResolvedValue({nodes, head: h.events.length}); await h.update();
  expect(ids(h.host)).not.toContain('specialize-g');
  expect(h.host.querySelector('[aria-pressed="true"][data-lin-action="select-lineage-agent"]')).toBeNull();
  expect(h.host.contains(document.activeElement)).toBe(true); expect(document.activeElement?.tagName).toMatch(/^H[1-6]$/u);
  expect(h.announce.mock.calls.filter(([, message]) => message === `${key('specialize-g')} is no longer in this view.`)).toHaveLength(1);
  await h.update(); expect(h.announce.mock.calls.filter(([, m]) => m === `${key('specialize-g')} is no longer in this view.`)).toHaveLength(1);
});
it('A8 A13 filtering cannot eagerly mount a broad generation or falsely report a pending match absent', async () => {
  const h = mount({nodes: broad()}); await h.ready;
  expect(ids(h.host).length).toBeLessThanOrEqual(50);
  await search(h, 'child'); expect(ids(h.host).length).toBeLessThanOrEqual(50);
  expect(h.host.textContent).not.toContain('No matching agents.');
  await search(h, 'child-198'); expect(ids(h.host).length).toBeLessThanOrEqual(50);
  if (!ids(h.host).includes('child-198')) {
    expect(controls(h.host).filter(el => el.dataset.linAction === 'expand-next-generation')).toHaveLength(1);
    await click(h, 'expand-next-generation');
  }
  expect(ids(h.host)).toContain('child-198');
});
it('A13 expansion adds at most fifty canonical entries and continuation exhausts partially exposed branches', async () => {
  const h = mount({nodes: broad()}); await h.ready; await click(h, 'collapse-lineage-agent', 'wide-root');
  const before = new Set(ids(h.host)); await click(h, 'expand-lineage-agent', 'wide-root');
  expect(ids(h.host).filter(id => !before.has(id)).length).toBeLessThanOrEqual(50);
  expect(ids(h.host).length).toBeGreaterThan(before.size); await exhaust(h); assertRelations(h.host, h.nodes);
});
it('A8 A14 a deep search keeps its ancestor context within the same continuation gate', async () => {
  const h = mount({nodes: deep()}); await h.ready; await search(h, 'chain-199');
  expect(ids(h.host).length).toBeGreaterThan(0); expect(ids(h.host).length).toBeLessThanOrEqual(50);
  expect(h.host.textContent).not.toContain('No matching agents.'); await exhaust(h); expect(ids(h.host)).toContain('chain-199');
});
it('A6 shared-child search preserves both parent relationships without duplicate actionable identities', async () => {
  const h = mount(); await h.ready; await search(h, 'cross-e');
  const child = entry(h.host, 'cross-e'); expect(child.textContent).toContain('root-b'); expect(child.textContent).toContain('clone-c');
  expect(ids(h.host).filter(id => id === 'cross-e')).toHaveLength(1); expect(h.host.textContent).toMatch(/context/iu);
});
it('A10 choosing a root outside the selected identity clears it with an explanation', async () => {
  const h = mount(); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  const select = action(h.host, 'filter-lineage-root') as HTMLSelectElement; select.value = 'root-b';
  select.dispatchEvent(new Event('change', {bubbles: true})); await h.settled();
  expect(h.host.querySelector('[aria-pressed="true"][data-lin-action="select-lineage-agent"]')).toBeNull();
  expect(h.host.textContent).toMatch(/selection|selected/iu); expect(h.host.textContent).toMatch(/outside|cleared|scope/iu);
});
