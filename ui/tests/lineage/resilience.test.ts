import { beforeEach, expect, it, vi } from 'vitest';
import type { JsonValue, LedgerEvent } from '../../src/ui/contracts.ts';
import { TransportError } from '../../src/transport.ts';
import { ABSENT, action, assertReadOnly, assertRelations, birth, births, canonical, click, controls, deferred, drain,
  entry, exhaust, forest, ids, inherited, isolation, mount, outcome, search, seal, selected } from './fixtures.ts';

const drawing = vi.hoisted(() => ({mode: 'valid' as 'valid' | 'throw' | 'unusable'}));
vi.mock('../../src/screens/lineage/layout.ts', () => ({
  drawTree: vi.fn((_tree, visible: ReadonlySet<string>, _selected: string | null) => {
    if (drawing.mode === 'throw') throw Error('Synthetic layout failure');
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('aria-hidden', 'true'); svg.setAttribute('focusable', 'false');
    svg.setAttribute('viewBox', drawing.mode === 'unusable' ? '0 0 NaN Infinity' : '0 0 400 240');
    svg.setAttribute('width', '400'); svg.setAttribute('height', '240');
    for (const [i] of [...visible].sort().entries()) {
      const rect = document.createElementNS(svg.namespaceURI, 'rect'); rect.setAttribute('x', String(i * 8));
      rect.setAttribute('y', '8'); rect.setAttribute('width', '6'); rect.setAttribute('height', '6'); svg.append(rect);
    }
    return svg;
  }),
}));
isolation(); beforeEach(() => {drawing.mode = 'valid';});

it('A15 A23 deferred initial read exposes Loading and cannot resolve readiness early', async () => {
  const pending = deferred<JsonValue>(), h = mount({call: () => pending.promise});
  await drain(); expect(h.readyState.value).toBe('pending'); expect(h.host.textContent).toContain('Loading Lineage.');
  expect(ids(h.host)).toEqual([]); expect(h.host.getAttribute('aria-busy') === 'true' || h.host.querySelector('[aria-busy="true"]')).toBeTruthy();
  pending.resolve({nodes: h.nodes, head: h.events.length}); await h.ready; expect(ids(h.host)).toContain('root-a');
});
it('A15 late route response cannot replace newer selection DOM or announcements', async () => {
  const old = deferred<JsonValue>(), latest = deferred<JsonValue>(); let n = 0;
  const h = mount({query: {root: 'root-a'}, call: () => ++n === 1 ? old.promise : latest.promise});
  const update = h.update({root: 'root-b', selected: 'root-b'});
  latest.resolve({nodes: h.nodes, head: h.events.length}); await update;
  selected(h, 'root-b'); const html = h.host.innerHTML, notices = h.announce.mock.calls.length;
  old.resolve({nodes: h.nodes, head: h.events.length}); await drain();
  expect(h.host.innerHTML).toBe(html); expect(h.announce.mock.calls.length).toBe(notices); selected(h, 'root-b');
});
it('A15 dispose invalidates pending reads, subscriptions and owned listeners', async () => {
  const pending = deferred<JsonValue>(), h = mount({call: () => pending.promise});
  h.dispose(); const html = h.host.innerHTML, notices = h.announce.mock.calls.length;
  pending.resolve({nodes: h.nodes, head: h.events.length}); await drain();
  expect(h.host.innerHTML).toBe(html); expect(h.announce.mock.calls.length).toBe(notices); expect(h.listenerCount()).toBe(0);
  expect(h.readyState.value).not.toBe('fulfilled');
});
it('A15 aborted read cannot commit even if the transport ignores its signal', async () => {
  const pending = deferred<JsonValue>(), h = mount({call: () => pending.promise});
  h.controller.abort(); const before = h.host.innerHTML, notices = h.announce.mock.calls.length;
  pending.resolve({nodes: h.nodes, head: h.events.length}); await drain();
  expect(h.host.innerHTML).toBe(before); expect(h.announce.mock.calls.length).toBe(notices);
  expect(h.readyState.value).not.toBe('fulfilled');
});
it('A15 stale response cannot resolve the current update while its own read is pending', async () => {
  const old = deferred<JsonValue>(), current = deferred<JsonValue>(); let n = 0;
  const h = mount({call: () => ++n === 1 ? old.promise : current.promise});
  const p = h.update({selected: 'clone-c'}), state = outcome(p);
  old.resolve({nodes: h.nodes, head: h.events.length}); await drain(); expect(state.value).toBe('pending');
  current.resolve({nodes: h.nodes, head: h.events.length}); await p; selected(h, 'clone-c');
});
it('A16 complete contiguous prefix and matching tree head resolve the corresponding fold', async () => {
  const h = mount(); await h.ready; expect(h.readyState.value).toBe('fulfilled');
  expect(ids(h.host)).toContain('root-a'); assertReadOnly(h);
  // Only the shell may write these attributes; this direct screen mount leaves them absent.
  expect(document.documentElement.hasAttribute('data-lin-ready')).toBe(false);
  expect(document.documentElement.hasAttribute('data-lin-rev')).toBe(false);
});
it.each([-1, 1])('A16 mismatched tree revision offset %s stays unready without a refresh loop', async delta => {
  const nodes = forest(), events = births(nodes), h = mount({nodes, events, tree: {nodes, head: events.length + delta}});
  await drain(); expect(h.readyState.value).not.toBe('fulfilled');
  expect(h.store.refresh).toHaveBeenCalledTimes(Math.min(vi.mocked(h.store.refresh).mock.calls.length, 1));
  expect(vi.mocked(h.transport.call).mock.calls.length).toBeLessThanOrEqual(2);
  expect(h.host.textContent).toMatch(/stale|unavailable|revision/iu);
  expect(action(h.host, 'retry-panel')).toBeDefined();
});
it.each(['unknown-head', 'missing-event', 'duplicate-lamport', 'resync-gap'] as const)('A16 matching integers do not pass an incomplete prefix: %s', async kind => {
  const nodes = forest(), events = births(nodes), head = events.length;
  const broken = kind === 'missing-event' ? events.filter(e => e.lamport !== 2)
    : kind === 'duplicate-lamport' ? events.map((e, i) => i === 2 ? {...e, lamport: 2} : e) : events;
  const h = mount({nodes, events: broken, head: kind === 'unknown-head' ? null : head, tree: {nodes, head},
    state: kind === 'resync-gap' ? {stale: true, notice: 'Ledger changed. Resync required; filters kept.'} : {}});
  await drain(); expect(h.readyState.value).not.toBe('fulfilled');
  expect(ids(h.host)).toEqual([]); expect(h.host.textContent).toMatch(/stale|unavailable|revision|prefix|resync/iu);
});
it('A16 later mismatch retains the coherent old topology and marks its revision stale', async () => {
  const h = mount(); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  const before = ids(h.host); const changed = h.nodes.map(n => n.agent_id === 'clone-c' ? {...n, status: 'retired'} : n);
  vi.mocked(h.transport.call).mockResolvedValue({nodes: changed, head: h.events.length + 1});
  const p = h.update(), state = outcome(p); await drain();
  expect(state.value).not.toBe('fulfilled'); expect(ids(h.host)).toEqual(before); selected(h, 'clone-c');
  expect(h.host.textContent).toContain(`Data is stale. Last confirmed revision ${h.events.length}.`);
  expect(entry(h.host, 'clone-c').textContent).not.toContain('retired');
});

const badInherited: [string, (item: any) => void][] = [
  ['episode', x => {x.unit.kind = 'episode';}], ['level_one', x => {x.unit.level = 1;}],
  ['level_three', x => {x.unit.level = 3;}], ['private', x => {x.unit.privacy = 'private'; x.unit.statement = 'SECRET PRIVATE BODY';}],
  ['missing_receipt', x => {x.unit.receipts = [];}], ['invalid_receipt', x => {x.unit.receipts[0].sha256 = 'bad-hash';}],
  ['not_promoted', x => {x.unit.kind = 'workflow'; x.unit.body = {trigger_sig: 'Trigger', steps: ['Step'], stats: {runs: 0, successes: 0, mean_reward: null}, status: 'candidate'};}],
  ['scope_mismatch', x => {x.unit.scope.workflow = 'research';}], ['language scope mismatch', x => {x.unit.scope.language = 'foreign-language';}],
  ['inactive', x => {x.unit.status = 'retired';}], ['decision', x => {x.unit.kind = 'decision'; x.unit.body = {reason: 'Not inherited'};}],
  ['open_item', x => {x.unit.kind = 'open_item'; x.unit.body = {class: 'todo', order: 0};}],
  ['source agent mismatch', x => {x.unit.provenance.inherited_from.agent_id = 'root-b';}],
  ['source unit mismatch', x => {x.unit.provenance.inherited_from.unit_id = 'wrong_001';}],
  ['source hash mismatch', x => {x.unit.provenance.inherited_from.unit_sha256 = 'c'.repeat(64);}],
  ['source not a parent', x => {x.source_agent_id = 'stranger-agent'; x.unit.provenance.inherited_from.agent_id = 'stranger-agent';}],
  ['missing provenance', x => {delete x.unit.provenance.inherited_from;}],
  ['missing statement', x => {delete x.unit.statement;}], ['invalid source hash', x => {x.unit_sha256 = 'x'.repeat(64);}],
];
it.each(badInherited)('A19 invalid accepted %s remains unavailable without an Inheritable badge', async (_label, mutate) => {
  const nodes = forest(), events = births(nodes), item = inherited(); mutate(item);
  birth(events, 'clone-c').inherited_units = [item]; seal(events);
  const h = mount({nodes, events}); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  expect(h.host.textContent).toMatch(/invalid|unavailable|not inheritable/iu);
  expect([...h.host.querySelectorAll('*')].filter(el => el.childElementCount === 0 && el.textContent?.trim() === 'Inheritable')).toHaveLength(0);
  expect(h.host.textContent).not.toContain('SECRET PRIVATE BODY'); expect(ids(h.host)).toContain('clone-c');
  expect(vi.mocked(h.transport.call).mock.calls.some(([tool]) => tool === 'memory_get')).toBe(false);
});
it('A19 rejected private and episode identities never cause body fetches or content exposure', async () => {
  const nodes = forest(), events = births(nodes);
  birth(events, 'clone-c').rejected_units = [{agent_id: 'root-a', unit_id: 'private_1', reason: 'private'},
    {agent_id: 'root-a', unit_id: 'episode_1', reason: 'episode'}]; seal(events);
  const h = mount({nodes, events}); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  for (const token of ['private_1', 'episode_1', 'private', 'episode']) expect(h.host.textContent).toContain(token);
  expect(vi.mocked(h.transport.call).mock.calls.some(([tool]) => /memory_(?:get|history)/u.test(tool))).toBe(false); assertReadOnly(h);
});
it.each(['throw', 'unusable'] as const)('A20 %s drawing failure leaves every structured relation and action usable', async mode => {
  const h = mount(); await h.ready; await exhaust(h); await click(h, 'select-lineage-agent', 'clone-c');
  const before = ids(h.host); action(h.host, 'select-lineage-agent', 'clone-c').focus(); drawing.mode = mode;
  await h.update(); expect(h.host.textContent).toContain('Tree drawing unavailable. Use the lineage list.');
  expect(ids(h.host)).toEqual(before); assertRelations(h.host, h.nodes); selected(h, 'clone-c');
  expect(document.activeElement?.closest('[data-lin-entity="agent"]')?.getAttribute('data-lin-id')).toBe('clone-c');
  expect(action(h.host, 'open-lineage-agent', 'clone-c').getAttribute('href')).toBe('#/agents/clone-c');
  await click(h, 'collapse-lineage-agent', 'root-a'); await click(h, 'expand-lineage-agent', 'root-a'); selected(h, 'clone-c');
});
it('A20 initial layout exception can resolve ready with the list', async () => {
  drawing.mode = 'throw'; const h = mount(); await h.ready;
  expect(h.host.textContent).toContain('Tree drawing unavailable. Use the lineage list.'); expect(ids(h.host)).toContain('root-a');
});
it('A23 initial refusal retries successfully, then a later failure preserves acknowledged filters and selection', async () => {
  let failing = true;
  const nodes = forest(), events = births(nodes);
  const h = mount({nodes, events, query: {q: 'clone', selected: 'clone-c'}, call: () => {
    if (failing) throw new TransportError('transport', 'network', 'Synthetic network refusal'); return {nodes, head: events.length};
  }});
  await expect(h.ready).rejects.toMatchObject({code: 'network'});
  expect(h.host.textContent).toContain('Lineage unavailable. Retry to continue.');
  failing = false; await click(h, 'retry-panel'); selected(h, 'clone-c'); const before = ids(h.host);
  failing = true; await expect(h.update()).rejects.toMatchObject({code: 'network'});
  expect(ids(h.host)).toEqual(before); selected(h, 'clone-c'); expect(h.host.textContent).toMatch(/stale/iu);
  expect((action(h.host, 'filter-lineage-query') as HTMLInputElement).value).toBe('clone');
});
it('A23 malformed detail evidence preserves coherent ancestry and exposes unavailable details', async () => {
  const nodes = forest(), events = births(nodes); delete birth(events, 'clone-c').inherited_units; seal(events);
  const h = mount({nodes, events}); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  expect(ids(h.host)).toContain('clone-c'); expect(h.host.textContent).toMatch(ABSENT);
  expect(h.host.textContent).not.toMatch(/no inherited units|0 inherited/iu);
});
it('A22 A24 passive error detail never executes and an unchanged refusal is announced only once', async () => {
  const detail = '<script>globalThis.compromised=true</script>';
  const h = mount({call: () => {throw new TransportError('domain', 'internal', 'Synthetic refusal', {detail});}});
  await expect(h.ready).rejects.toMatchObject({code: 'internal'});
  expect(h.host.querySelector('script')).toBeNull(); expect((globalThis as any).compromised).toBeUndefined();
  expect(h.host.textContent).toContain('internal'); const count = h.announce.mock.calls.filter(([, m]) => /internal/u.test(m)).length;
  expect(count).toBe(1); await expect(h.update()).rejects.toBeDefined();
  expect(h.announce.mock.calls.filter(([, m]) => /internal/u.test(m))).toHaveLength(count);
});
