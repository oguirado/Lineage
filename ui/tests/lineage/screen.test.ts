import { expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
// A-U24: Vitest serves import.meta.url over HTTP; resolve source fixtures from its ui working directory.
import { resolve } from 'node:path';
import { getScreen } from '../../src/screens/index.ts';
import { TransportError, createHttpTransport } from '../../src/transport.ts';
import { ABSENT, HASH, REASONS, SOURCE_HASH, action, assertReadOnly, assertRelations, birth, births, click,
  entry, exhaust, forest, ids, inherited, isolation, mount, node, route, rules, search, seal, selected, sha, canonical } from './fixtures.ts';
isolation();

it('A1 registered lifecycle replaces the placeholder and imports the owned stylesheet', async () => {
  const h = mount(); await h.ready;
  expect(getScreen(route()).id).toBe('lineage'); expect(getScreen(route()).title).toBe('Lineage');
  expect(h.host.textContent).not.toContain('not built yet');
  expect(h.host.querySelectorAll('h1')).toHaveLength(1); expect(h.host.querySelector('h1')!.textContent).toBe('Lineage');
  expect(h.host.querySelector('main,nav,header,[role="status"],[aria-live]')).toBeNull();
  expect(h.host.querySelector('[data-lin-screen]')).toBeNull();
  // A-U24: Preserve the source assertion while using the integrated runner's filesystem fixture API.
  const source = readFileSync(resolve('src/screens/lineage/index.ts'), 'utf8');
  expect(source).toMatch(/import\s*['"][^'"]*styles\/lineage\.css['"]/u);
  await h.update(); h.dispose(); expect(h.listenerCount()).toBe(0);
});
it('A2 uses the authoritative unwrapped read contract with no mutations or unsupported arguments', async () => {
  const h = mount(); await h.ready; assertReadOnly(h);
  expect(ids(h.host)).toContain('root-a'); expect(entry(h.host, 'root-b').textContent).toContain('retired');
});
it.each(['no_agent', 'bad_args', 'internal', 'network'] as const)('A3 preserves %s and exposes Retry rather than empty success', async code => {
  const h = mount({call: () => {throw new TransportError(code === 'network' ? 'transport' : 'domain', code, `Synthetic ${code}`);}});
  await expect(h.ready).rejects.toMatchObject({code, source: code === 'network' ? 'transport' : 'domain'});
  expect(h.host.textContent).toContain('Lineage unavailable. Retry to continue.'); expect(h.host.textContent).toContain(code);
  expect(action(h.host, 'retry-panel').getAttribute('aria-label') ?? action(h.host, 'retry-panel').textContent).toBe('Retry Lineage');
  expect(ids(h.host)).toEqual([]); expect(h.host.textContent).not.toContain('No lineage agents yet.');
});
it('A3 HTTP completion with semantic refusal never enables ancestry actions', async () => {
  const h = mount();
  const http = createHttpTransport({sessionToken: null, timeoutMs: 1000,
    fetchImpl: vi.fn(async () => new Response(JSON.stringify({ok: false, code: 'no_agent'}),
      {status: 200, headers: {'Content-Type': 'application/json'}})) as typeof fetch});
  vi.mocked(h.transport.call).mockImplementation(http.call); await expect(h.update()).rejects.toMatchObject({code: 'no_agent'});
  expect(h.host.textContent).toContain('no_agent'); expect(ids(h.host)).toEqual([]);
});
it('A7 measured empty head zero has the designated empty copy', async () => {
  const h = mount({nodes: []}); await h.ready;
  expect(h.host.textContent).toContain('No lineage agents yet.'); expect(ids(h.host)).toEqual([]);
  expect(h.host.textContent).not.toMatch(/Loading|unavailable/u); assertReadOnly(h);
});
it('A7 a lone true genesis has no fabricated descendants', async () => {
  const h = mount({nodes: [node('actual-genesis')]}); await h.ready;
  expect(ids(h.host)).toEqual(['actual-genesis']); expect(h.host.textContent).toContain('Genesis agent. No descendants yet.');
  expect(h.host.querySelector('[data-lin-action="expand-lineage-agent"]')).toBeNull();
});
it('A7 A9 a scoped descendant leaf retains boundary parents and is never called genesis', async () => {
  const h = mount({query: {root: 'mutate-f'}}); await h.ready;
  expect(ids(h.host)).toEqual(['mutate-f']); expect(entry(h.host, 'mutate-f').textContent).toContain('cross-e');
  expect(h.host.textContent).toMatch(/boundary|outside (?:the )?(?:root|scope)/iu);
  expect(h.host.textContent).not.toContain('Genesis agent.');
});
it.each(['CLONE-C', 'cafe\u0301', 'CAFÉ'])('A8 searches normalized full IDs and recorded names: %s', async query => {
  const nodes = forest(), events = births(nodes);
  birth(events, 'clone-c').record.display_name = 'Café'; birth(events, 'distill-d').record.display_name = 'Cafe\u0301'; seal(events);
  const h = mount({nodes, events}); await h.ready; await search(h, query);
  expect(ids(h.host)).toContain('clone-c'); expect(ids(h.host)).toContain('root-a');
  if (query !== 'CLONE-C') expect(ids(h.host)).toContain('distill-d');
  expect(h.host.textContent).toMatch(/context/iu);
});
it('A8 no matches uses the exact copy, while selected hidden identity is preserved', async () => {
  const h = mount(); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  await search(h, 'unfindable-record');
  expect(h.host.textContent).toContain('No matching agents. Clear filters to see all loaded records.');
  expect(h.host.textContent).toMatch(/(?:selected.*(?:hidden|filtered)|(?:hidden|filtered).*selected)/iu);
  expect(h.host.textContent).toContain('clone-c'); await search(h, ''); selected(h, 'clone-c');
});
it('A9 root scope preserves shared-child boundary ancestry and canonical identity', async () => {
  const h = mount({query: {root: 'clone-c'}}); await h.ready; await exhaust({...h, nodes: h.nodes.filter(n => ['clone-c', 'cross-e', 'mutate-f'].includes(n.agent_id))});
  expect(ids(h.host).sort()).toEqual(['clone-c', 'cross-e', 'mutate-f']);
  const child = entry(h.host, 'cross-e'); expect(child.textContent).toContain('root-b');
  expect(child.parentElement?.closest('[data-lin-entity="agent"]')?.getAttribute('data-lin-id')).toBe('clone-c');
  expect(h.host.textContent).toMatch(/boundary|outside/iu);
});
it('A9 A17 missing birth metadata declares unavailable display name and preserves topology', async () => {
  const nodes = forest(), events = births(nodes); const missing = events.find(e => e.payload.record && (e.payload.record as any).agent_id === 'clone-c')!;
  missing.kind = 'run.beat'; missing.payload = {run_id: 'run_0001', agent_id: 'creator-agent', progress: 'Synthetic missing birth'}; seal(events);
  const h = mount({nodes, events, query: {selected: 'clone-c'}}); await h.ready;
  expect(entry(h.host, 'clone-c').textContent).toMatch(ABSENT); expect(h.host.textContent).toMatch(/(?:birth|inheritance|evidence).*unavailable|unavailable.*(?:birth|inheritance|evidence)/iu);
  expect(h.host.textContent).not.toMatch(/no inherited units|0 inherited/iu);
});
it.each(['lesson', 'negative', 'workflow'] as const)('A17 A19 inspects recorded eligible %s provenance from a different birth actor', async kind => {
  const nodes = forest(), events = births(nodes), payload = birth(events, 'clone-c'), accepted = inherited('root-a', kind);
  payload.inherited_units = [accepted]; seal(events);
  const h = mount({nodes, events}); await h.ready; await click(h, 'select-lineage-agent', 'clone-c'); selected(h, 'clone-c');
  const bornEvent = events.find(e => e.payload === payload)!;
  for (const value of [bornEvent.id, bornEvent.sha256, payload.record.agent_version, 'root-a', 'source_01', SOURCE_HASH,
    'child_001', kind, accepted.unit.statement, 'evidence/unit.json', HASH]) expect(h.host.textContent).toContain(value);
  expect(h.host.textContent).toMatch(/context/iu); expect(h.host.textContent).toMatch(/weights/iu);
  expect(h.host.textContent).not.toMatch(/freshly verified|filesystem verified/iu); assertReadOnly(h);
});
it.each(REASONS)('A17 preserves rejection identity and readable reason %s', async reason => {
  const nodes = forest(), events = births(nodes);
  birth(events, 'clone-c').rejected_units = [{agent_id: 'root-a', unit_id: 'rejected_01', reason}]; seal(events);
  const h = mount({nodes, events}); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  for (const token of ['root-a', 'rejected_01', reason]) expect(h.host.textContent).toContain(token);
  expect(h.host.textContent).toMatch(/rejected|excluded/iu);
  expect(vi.mocked(h.transport.call).mock.calls.some(([tool]) => tool === 'memory_get')).toBe(false);
});
it('A17 an explicitly empty inheritance array differs from missing evidence', async () => {
  const h = mount(); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  expect(h.host.textContent).toMatch(/no (?:accepted |recorded )?inherited (?:units|context)|inherited units[^.]*\b0\b/iu);
  expect(h.host.textContent).toMatch(/no rejected|no exclusions|rejected units[^.]*\b0\b/iu);
});

function constitutionCase(kind: 'equal' | 'different' | 'hash-only' | 'missing') {
  const nodes = forest(); if (kind !== 'equal') nodes.find(n => n.agent_id === 'clone-c')!.op = 'mutate';
  const events = births(nodes);
  const parent = birth(events, 'root-a'), child = birth(events, 'clone-c');
  parent.constitution = rules([['I1', 'Old cited rule.'], ['I2', 'Removed rule.']]);
  child.constitution = kind === 'equal' ? structuredClone(parent.constitution) : kind === 'hash-only'
    ? {...structuredClone(parent.constitution), text: parent.constitution.text + 'Unattributed appendix.\n'}
    : rules([['I1', 'Changed cited rule.'], ['I3', 'Added rule.']]);
  for (const p of [parent, child]) {
    p.record.constitution_sha256 = sha(p.constitution.text);
    p.record.agent_version = sha(canonical({constitution_sha256: p.record.constitution_sha256, skills: [], memory_gen: 0}));
  }
  if (kind === 'missing') delete parent.constitution;
  seal(events); return {nodes, events, parent, child};
}
it('A18 compares equal complete immutable parent artifacts without inventing a captured version', async () => {
  const c = constitutionCase('equal'), h = mount(c); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  expect(h.host.textContent).toMatch(/No changed rules/iu); expect(h.host.textContent).toMatch(/parent.*(?:derivation|captured).*?(?:AUSENTE — no inventar|not recorded|unavailable)/iu);
});
it('A18 attributes added removed and changed cited text and reads record rule_overrides', async () => {
  const c = constitutionCase('different'); c.parent.record.rule_overrides = {I2: 'add'}; c.child.record.rule_overrides = {I2: 'remove', I3: 'add'}; seal(c.events);
  const h = mount(c); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  for (const token of ['root-a', 'I1', 'I2', 'I3', 'Old cited rule.', 'Changed cited rule.', 'Added rule.',
    '[GOLD-S1/PM-1001.1/I1; §1]', c.parent.record.constitution_sha256, c.child.record.constitution_sha256]) expect(h.host.textContent).toContain(token);
  for (const word of [/added/iu, /removed/iu, /changed/iu, /overrides/iu]) expect(h.host.textContent).toMatch(word);
});
it.each(['hash-only', 'missing'] as const)('A18 %s evidence never claims equal or invents rule changes', async kind => {
  const c = constitutionCase(kind), h = mount(c); await h.ready; await click(h, 'select-lineage-agent', 'clone-c');
  expect(h.host.textContent).not.toContain('No changed rules');
  expect(h.host.textContent).toMatch(kind === 'missing' ? ABSENT : /hash|content difference/iu);
  if (kind === 'hash-only') expect(h.host.textContent).not.toMatch(/I1\s*(?:was )?(?:added|removed|changed)/iu);
});
it('A18 cross compares each parent separately and genesis fabricates no parent artifact', async () => {
  const nodes = forest(), events = births(nodes);
  for (const [id, entries] of [
    ['root-b', [['I1', 'First parent text.'], ['I2', 'First parent removal.']]],
    ['clone-c', [['I1', 'Second parent text.'], ['I4', 'Second parent removal.']]],
    ['cross-e', [['I1', 'Child changed text.'], ['I3', 'Child addition.']]],
  ] as [string, [string, string][]][]) {
    const payload = birth(events, id); payload.constitution = rules(entries);
    payload.record.constitution_sha256 = sha(payload.constitution.text);
    payload.record.agent_version = sha(canonical({constitution_sha256: payload.record.constitution_sha256, skills: [], memory_gen: 0}));
  }
  seal(events); const h = mount({nodes, events}); await h.ready; await exhaust(h); await click(h, 'select-lineage-agent', 'cross-e');
  expect(h.host.textContent).toMatch(/comparison|compared/iu);
  for (const id of ['root-b', 'clone-c']) expect(h.host.textContent).toMatch(new RegExp(`(?:parent|compar)[^.]*${id}|${id}[^.]*compar`, 'iu'));
  for (const text of ['First parent text.', 'Second parent text.', 'Child changed text.', 'First parent removal.', 'Second parent removal.', 'Child addition.']) expect(h.host.textContent).toContain(text);
  await click(h, 'select-lineage-agent', 'root-a'); expect(h.host.textContent).toMatch(/genesis|no parent/iu);
});
