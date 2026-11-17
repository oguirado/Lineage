// @vitest-environment jsdom
import { it, expect, vi } from 'vitest';
import { resolve } from 'node:path';
// A-U21R: Mount preloaded shell modules without loader task turns during the clock guard.
import { source, text, root as repoRoot, json, fixture, event, page, app, isolateDom, flush, host, own } from './helpers.ts';
isolateDom();
const load = () => source('transport.ts', ['createFixtureTransport']);
const writes = ['agent_create','agent_clone','agent_distill','agent_cross','agent_mutate','agent_specialize',
  'agent_retire','agent_promote','skill_publish','skill_retire','memory_put','run_open','run_beat','run_close',
  'bench_declare','bench_run','bench_verdict','ledger_export','openfresnel_probe','openfresnel_spawn'];
it.each(['demo','empty','hostile'])('A22 validates assigned %s fixture and closed schema', async id => {
  const schema = json('fixtures/ui/schema.json'); const value = json(`fixtures/ui/${id}.json`);
  expect(schema.additionalProperties).toBe(false);
  expect(new Set(schema.required)).toEqual(new Set(['schema','id','clock_ms','tools','page','results','panels']));
  expect(Object.keys(value).sort()).toEqual(['clock_ms','id','page','panels','results','schema','tools']);
  expect(value.schema).toBe('lineage.ui.fixture/v1'); expect(value.id).toBe(id);
  expect(Number.isSafeInteger(value.clock_ms) && value.clock_ms >= 0).toBe(true);
  const {createFixtureTransport} = await load(); const t = createFixtureTransport(value);
  expect(t.mode).toBe('fixture'); expect(t.fixtureId).toBe(id);
  expect(await t.tools()).toEqual(value.tools); expect(await t.events(0)).toEqual(value.page);
  expect(fetch).not.toHaveBeenCalled();
});
it('A22 demo covers every panel state, duplicate names, unknown costs and separate seats', async () => {
  const value = json('fixtures/ui/demo.json');
  expect(new Set(value.panels.map((p: any) => p.state))).toEqual(new Set(
    ['loading','empty','no-match','ready','busy','queued','running','stalled','stale','error','completed','not-built']));
  const all = JSON.stringify(value); expect(all).toMatch(/synthetic/i); expect(all).toContain('null');
  // Search result records by their public fields, independent of fixture layout/grouping.
  const records: any[] = []; function walk(x: any) {if (x && typeof x === 'object') {records.push(x); Object.values(x).forEach(walk);}} walk(value);
  const named = records.filter(x => typeof x.display_name === 'string' && typeof (x.id ?? x.agent_id) === 'string');
  expect(named.some(a => named.some(b => a !== b && a.display_name === b.display_name && (a.id ?? a.agent_id) !== (b.id ?? b.agent_id)))).toBe(true);
  expect(records.some(x => typeof x.model === 'string' && typeof x.effort === 'string' && ['headless','interactive'].includes(x.mode))).toBe(true);
});
it('A22 empty fixture has a measured empty cursor and distinct empty/no-match examples', async () => {
  const value = json('fixtures/ui/empty.json'); expect(value.page).toEqual(page());
  expect(value.panels.some((p: any) => p.state === 'empty')).toBe(true);
  expect(value.panels.some((p: any) => p.state === 'no-match')).toBe(true);
});
it('A9 A28 hostile fixture remains literal multilingual data with long text and digest', async () => {
  const value = json('fixtures/ui/hostile.json'); const serialized = JSON.stringify(value);
  expect(serialized).toMatch(/<[^>]+>/u); expect(serialized).toMatch(/[^\u0000-\u007f]/u);
  expect(serialized).toMatch(/[a-f0-9]{64}/u); expect(serialized).toMatch(/[^\s"\\]{256}/u);
  const {root} = await app((await load()).createFixtureTransport(value)); expect(root.querySelector('img,script,iframe')).toBeNull();
});
it.each(['schema','id','clock_ms','tools','page','results','panels'])('A22 refuses absent required fixture field %s', async key => {
  const {createFixtureTransport} = await load(); const value = fixture(); delete value[key];
  expect(() => createFixtureTransport(value)).toThrow();
});
it('A22 rejects unknown root fields, unsafe keys and disallowed declared read results', async () => {
  const {createFixtureTransport} = await load();
  for (const value of [{...fixture(), extra: true}, {...fixture(), clock_ms: -1},
    {...fixture(), panels: [{id: 'bad', state: 'made-up', title: 'Synthetic'}]},
    {...fixture(), results: [{tool: 'agent_create', args: {}, reply: {untrusted: {}}}]},
    {...fixture(), results: [{tool: 'agent_list', args: {constructor: 'x'}, reply: {untrusted: {}}}]}]) {
    expect(() => createFixtureTransport(value)).toThrow();
  }
});
it('A22 serves declared reads only and filters the fixed event page by cursor', async () => {
  const {createFixtureTransport} = await load(); const value = fixture(); value.page = page([event(1), event(2)]);
  const t = createFixtureTransport(value);
  expect(await t.call('agent_list', {}, {mutation: false})).toEqual({agents: [], synthetic: true});
  await expect(t.call('agent_list', {limit: 1}, {mutation: false})).rejects.toMatchObject({source: 'domain', code: 'bad_args'});
  const filtered = await t.events(1); expect(filtered.events.map((e: any) => e.lamport)).toEqual([2]);
  expect(filtered.head).toBe(2); expect(filtered.next_after).toBe(2); expect(fetch).not.toHaveBeenCalled();
});
it.each(writes)('A23 refuses fixture tool %s even dishonestly classified as read', async tool => {
  const {createFixtureTransport} = await load(); const t = createFixtureTransport(fixture());
  for (const mutation of [false, true]) await expect(t.call(tool, {agent: 'aurora-root', op_id: 'synthetic-one'}, {mutation}))
    .rejects.toMatchObject({source: 'domain', code: 'fixture_readonly'});
  expect(fetch).not.toHaveBeenCalled();
});
it.each(['demo','empty','hostile'])('A23 explicit %s fixture stays visibly read-only without network or domain storage', async id => {
  const {createFixtureTransport} = await load(); const storage = {getItem: () => null, setItem: vi.fn()} as unknown as Storage;
  const {root, handle} = await app(createFixtureTransport(fixture(id)), '#/lineage', storage);
  expect(handle.store.getState()).toMatchObject({mode: 'fixture', fixtureId: id});
  expect(root.textContent).toContain(`Fixture: ${id} — read-only`); expect(root.textContent).toContain('Synthetic fixtures. Changes are unavailable.');
  expect(root.querySelector('main')!.dataset.linScreen).toBe('lineage'); expect(fetch).not.toHaveBeenCalled();
  expect((storage.setItem as any).mock.calls.every(([key]: any[]) => /theme/u.test(key))).toBe(true);
});
it('A22 fixed fixture produces repeatable state and semantic DOM without clock or randomness', async () => {
  const {createFixtureTransport} = await load(); const value = fixture();
  // A-U21R: Keep both throwing guards active across both renders, but exclude jsdom's queued event timestamps.
  const {startApp} = await source('main.ts', ['startApp']);
  const mountFixture = async () => {
    const root = host(); const handle = own(startApp({root, storage: null, initialHash: '#/agents',
      transport: createFixtureTransport(structuredClone(value))}));
    await flush(); return {root, handle};
  };
  const random = vi.spyOn(Math, 'random').mockImplementation(() => {throw Error('No random fixture state');});
  const clock = vi.spyOn(Date, 'now').mockImplementation(() => {throw Error('No wall-clock fixture state');});
  try {
    const one = await mountFixture();
    const state = JSON.stringify(one.handle.store.getState()); const content = one.root.textContent;
    one.handle.dispose(); one.root.remove();
    const two = await mountFixture();
    expect(JSON.stringify(two.handle.store.getState())).toBe(state); expect(two.root.textContent).toBe(content);
    expect(fetch).not.toHaveBeenCalled();
  } finally {clock.mockRestore(); random.mockRestore();}
});

async function bootEntry(search: string, check: (root: HTMLElement, error: any) => void) {
  text('ui/src/main.ts');
  const disposables: any[] = []; const mockIds: string[] = [];
  vi.resetModules();
  for (const [file, factory] of [['store.ts','createStore'], ['router.ts','createRouter'], ['ui/shell.ts','mountShell']]) {
    const id = resolve(repoRoot,'ui/src',file); mockIds.push(id);
    vi.doMock(id, async () => {
      const actual: any = await vi.importActual(id);
      return {...actual, [factory]: (...args: any[]) => {const value=actual[factory](...args);disposables.push(value);return value;}};
    });
  }
  const root=document.createElement('div');root.id='app';document.body.append(root);
  history.replaceState(null,'',`/${search}#/ledger`); let error: any;
  try {
    try {await source('main.ts',['startApp']);await flush();} catch(e) {error=e;}
    check(root,error);
  } finally {
    for(const d of disposables.reverse()) d.dispose();
    for(const id of mockIds) vi.doUnmock(id);
    vi.resetModules(); root.remove();
  }
}
it.each(['demo','empty','hostile'])('A23 browser entry explicitly selects %s without changing its route', async id => {
  await bootEntry(`?fixture=${id}`, (root,error)=>{
    expect(error).toBeUndefined(); expect(root.textContent).toContain(`Fixture: ${id} — read-only`);
    expect(root.querySelector('main')?.dataset.linScreen).toBe('ledger'); expect(location.hash).toBe('#/ledger');
    expect(fetch).not.toHaveBeenCalled();
  });
});
it.each(['?fixture=unknown','?fixture=','?fixture=demo&fixture=empty','?fixture=demo&fixture=demo'])
  ('A23 browser entry rejects invalid selector %s instead of using live data', async search => {
    await bootEntry(search,(root,error)=>{
      expect(error?.code==='invalid_config' || root.textContent?.includes('invalid_config')).toBe(true);
      expect(document.documentElement.dataset.linReady).not.toBe('true'); expect(fetch).not.toHaveBeenCalled();
    });
  });
