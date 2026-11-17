import { expect, it } from 'vitest';
import { drawTree } from '../../src/screens/lineage/layout.ts';
import { assertRelations, births, broad, deep, entry, exhaust, forest, ids, isolation, mount, node, order } from './fixtures.ts';
isolation();

const hostile: [string, () => unknown][] = [
  ['null envelope', () => null], ['array envelope', () => []],
  ['extra envelope field', () => ({nodes: [], head: 0, cursor: 0})],
  ['nonarray nodes', () => ({nodes: {}, head: 0})], ['missing head', () => ({nodes: []})],
  ...[true, null, -1, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1].map(value =>
    [`invalid head ${String(value)}`, () => ({nodes: [], head: value})] as [string, () => unknown]),
  ['duplicate identity', () => ({nodes: [node('root-a'), node('root-a')], head: 2})],
  ['duplicate parent', () => ({nodes: [node('root-a'), node('child-a', ['root-a', 'root-a'], 1, 'cross')], head: 2})],
  ['self parent', () => ({nodes: [node('root-a', ['root-a'], 1)], head: 1})],
  ['cycle', () => ({nodes: [node('root-a', ['child-a'], 2), node('child-a', ['root-a'], 1)], head: 2})],
  ['missing global parent', () => ({nodes: [node('child-a', ['missing-parent'], 1)], head: 1})],
  ['extra node key', () => ({nodes: [{...node('root-a'), display_name: 'invented'}], head: 1})],
  ['nonarray parents', () => ({nodes: [{...node('root-a'), parents: {}}], head: 1})],
  ['bad op', () => ({nodes: [{...node('root-a'), op: 'breed'}], head: 1})],
  ['bad status', () => ({nodes: [{...node('root-a'), status: 'alive'}], head: 1})],
  ['boolean generation', () => ({nodes: [{...node('root-a'), generation: true}], head: 1})],
  ['fractional generation', () => ({nodes: [{...node('root-a'), generation: 0.5}], head: 1})],
  ['root generation', () => ({nodes: [node('root-a', [], 1)], head: 1})],
  ['child generation', () => ({nodes: [node('root-a'), node('child-a', ['root-a'], 7)], head: 2})],
  ['genesis arity', () => ({nodes: [node('root-a'), node('child-a', ['root-a'], 1, 'genesis')], head: 2})],
  ['cross arity', () => ({nodes: [node('root-a'), node('child-a', ['root-a'], 1, 'cross')], head: 2})],
  ...(['clone', 'distill', 'mutate', 'specialize'] as const).map(op =>
    [`${op} arity`, () => ({nodes: [node('root-a', [], 0, op)], head: 1})] as [string, () => unknown]),
  ...['operator', 'system', '__proto__', 'constructor', 'aa', 'Uppercase', 'a'.repeat(65), 'bad/id'].map(agent_id =>
    [`invalid agent ${agent_id}`, () => ({nodes: [{...node('root-a'), agent_id}], head: 1})] as [string, () => unknown]),
  ['reserved parent', () => ({nodes: [node('root-a', ['system'], 1)], head: 1})],
  ['too many parents', () => ({nodes: [node('root-a'), node('root-b'), node('root-c'), node('child-a', ['root-a', 'root-b', 'root-c'], 1, 'cross')], head: 4})],
];
it.each(hostile)('A4 refuses %s without invented links or ready success', async (_label, make) => {
  const h = mount({tree: make()});
  await expect(h.ready).rejects.toBeDefined();
  expect(h.host.textContent).toContain('Lineage unavailable. Retry to continue.');
  expect(h.host.textContent).toContain('invalid_response');
  expect(ids(h.host)).toEqual([]);
  expect(h.host.textContent).not.toContain('No lineage agents yet.');
});

it('A5 enumerates every nested parent edge/operator, independent of response order', async () => {
  const nodes = forest(); const h = mount({nodes: [...nodes].reverse()}); await h.ready; await exhaust(h);
  assertRelations(h.host, nodes);
  const initial = ids(h.host); await h.update(); expect(ids(h.host)).toEqual(initial);
  expect(entry(h.host, 'root-b').textContent).toContain('retired');
});
it('A6 has one canonical shared child under the first persisted in-scope parent', async () => {
  const h = mount(); await h.ready; await exhaust(h);
  const child = entry(h.host, 'cross-e');
  expect(child.parentElement?.closest('[data-lin-entity="agent"]')?.getAttribute('data-lin-id')).toBe('root-b');
  assertRelations(h.host, h.nodes);
  // A-U24: Nested canonical entries own separate controls; scope dispatch to the nearest entity as U21 does.
  expect([...child.querySelectorAll('[data-lin-action="select-lineage-agent"]')]
    .filter(control => control.closest('[data-lin-entity="agent"]') === child)).toHaveLength(1);
  expect([...h.host.querySelectorAll('[data-lin-action="select-lineage-agent"]')]
    .filter(control => control.textContent === 'Select lineage cross-e')).toHaveLength(1);
});
it('A13 initial global budget uses generation then full identity across a wide forest', async () => {
  const nodes = broad(); const h = mount({nodes: [...nodes].reverse()}); await h.ready;
  expect(ids(h.host)).toHaveLength(50);
  expect(new Set(ids(h.host))).toEqual(new Set([...nodes].sort(order).slice(0, 50).map(n => n.agent_id)));
  expect(h.host.textContent).toMatch(/150\s+(?:agents?\s+)?(?:remaining|more)|remaining[^\d]*150/iu);
  await exhaust(h); assertRelations(h.host, nodes);
});
it('A14 deep ancestry is bounded initially and eventually exposes every relationship', async () => {
  const nodes = deep(); const h = mount({nodes}); await h.ready;
  expect(ids(h.host)).toEqual(['chain-000', 'chain-001']);
  await exhaust(h); assertRelations(h.host, nodes);
  for (const n of nodes) {
    const heading = entry(h.host, n.agent_id).querySelector('h2,h3,h4,h5,h6,[role="heading"]');
    expect(heading).not.toBeNull();
    const level = Number(heading!.getAttribute('aria-level') ?? heading!.tagName.slice(1));
    expect(Number.isSafeInteger(level) && level >= 2).toBe(true);
    if (heading!.getAttribute('role') !== 'heading') expect(level).toBeLessThanOrEqual(6);
  }
});
it('A14 refuses a cyclic deep hostile variant as data failure, not drawing fallback', async () => {
  const nodes = deep(); nodes[0].parents = [nodes.at(-1)!.agent_id]; nodes[0].op = 'clone';
  const h = mount({nodes}); await expect(h.ready).rejects.toBeDefined();
  expect(h.host.textContent).toContain('invalid_response');
  expect(h.host.textContent).not.toContain('Tree drawing unavailable.');
});

it('A25 drawing seam returns deterministic decorative geometry from coherent visible projection', () => {
  const nodes = forest(), tree = {nodes, head: births(nodes).length}; const visible = new Set(['root-a', 'root-b', 'clone-c']);
  const before = JSON.stringify(tree), first = drawTree(tree, visible, 'clone-c');
  const second = drawTree({...tree, nodes: [...nodes].reverse()}, visible, 'clone-c');
  expect(first).toBeInstanceOf(SVGSVGElement); expect(first.getAttribute('aria-hidden')).toBe('true');
  expect(first.outerHTML).toBe(second.outerHTML); expect(JSON.stringify(tree)).toBe(before);
  expect(first.querySelector('[data-lin-id],[data-lin-entity],[data-lin-action],a,button,[tabindex],foreignObject')).toBeNull();
  for (const el of [first, ...first.querySelectorAll('*')]) {
    for (const attr of el.attributes) {expect(attr.name).not.toMatch(/^on/iu); expect(attr.value).not.toMatch(/NaN|Infinity/u);}
  }
});
it('A7 decorative layout accepts an empty coherent topology', () => {
  const svg = drawTree({nodes: [], head: 0}, new Set(), null);
  expect(svg).toBeInstanceOf(SVGSVGElement); expect(svg.getAttribute('aria-hidden')).toBe('true');
});
