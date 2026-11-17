import { it, expect, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { screen } from '../../src/screens/agents/index.ts';
import { startApp } from '../../src/main.ts';
import type { JsonObject } from '../../src/ui/contracts.ts';
import { agent, clone, group, hash, longIds, repositoryPath } from './fixtures.ts';
import { Service, action, boot, card, deferred, enter, expectReads, failure, flush, ids, isolate, key, mount, name } from './helpers.ts';
isolate();

it('A1 public registry mounts, reads, updates and disposes without a substitute screen', async () => {
  const h=await boot();expect(screen.id).toBe('agents');expect(screen.title).toBe('Agents');expectReads(h);
  expect(typeof h.mounted.update).toBe('function');expect(typeof h.mounted.dispose).toBe('function');
  await h.update({q:'alpha'});expect(ids(h)).toEqual(['alpha-root']);
  h.dispose();expect(h.store.dispose).not.toHaveBeenCalled();
  expect(readFileSync(repositoryPath('ui/src/screens/agents/index.ts'),'utf8')).toMatch(/['"]\.\.\/\.\.\/\.\.\/styles\/agents\.css['"]/u);
});
it('A2 real U21 shell retains landmarks, navigation and the persistent status node', async () => {
  const service=new Service(),root=document.createElement('div');document.body.append(root);
  const app=startApp({root,transport:service.transport,storage:window.localStorage,initialHash:'#/agents'});
  try {
    const status=root.querySelector('[role="status"]');await flush();
    expect(root.querySelector('[data-lin-entity="agent"][data-lin-id="alpha-root"]'),'Agents must replace the placeholder with an authoritative card').not.toBeNull();
    expect(root.querySelectorAll('main')).toHaveLength(1);expect(root.querySelectorAll('h1')).toHaveLength(1);
    expect(root.querySelector('h1')?.textContent).toBe('Agents');expect(root.querySelector('[aria-current="page"]')?.getAttribute('data-lin-action')).toBe('nav-agents');
    expect(root.querySelector('[role="status"]')).toBe(status);expect(root.querySelectorAll('[role="status"]')).toHaveLength(1);
    expect(document.documentElement.dataset.linReady).toBe('true');expect(document.documentElement.dataset.linRev).toBe('7');
  } finally {app.dispose();}
});
it('A3 duplicate names and long identities retain unique full-ID actions after sort and reload', async () => {
  const service=new Service();service.records=longIds.map(id => agent(id));const h=await boot({service});
  for(const id of longIds) {const c=card(h,id);expect(c.matches('li,section')).toBe(true);expect(c.textContent).toContain(id);
    expect(name(action(c,'open-agent'))).toBe(`Open agent ${key('agent',id)}`);expect(name(action(c,'compare-agent'))).toBe(`Compare agent ${key('agent',id)}`);}
  await h.update({sort:'id-desc'});expect(ids(h)).toEqual([...longIds].reverse());
  for(const id of longIds) {action(card(h,id),'open-agent').click();expect(h.navigate).toHaveBeenLastCalledWith({screen:'agent',agentId:id,query:{}});}
  h.dispose();h.root.remove();const restored=await boot({service,query:{sort:'id-desc'}});expect(ids(restored)).toEqual([...longIds].reverse());
});
it('A4 readiness waits for the list and an equal acknowledged AppState.head', async () => {
  const service=new Service(),read=deferred();service.overrides.set('agent_list',() => read.promise);
  const h=mount({service});await flush();expectReads(h);expect(h.initial).toBe('pending');expect(h.host.textContent).toContain('Loading Agents.');
  read.resolve({agents:[agent()],next_after:null,head:7});await flush();await h.mounted.ready;
  expect(h.initial).toBe('fulfilled');expect(card(h,'alpha-root')).toBeDefined();expect(h.state.head).toBe(7);
});
it('A4 a persistent head mismatch has one reconciliation restart and a recoverable failure', async () => {
  const service=new Service();service.overrides.set('agent_list',() => ({agents:[agent()],next_after:null,head:8}));
  const h=mount({service});await flush();expectReads(h);
  expect(h.service.for('agent_list').length).toBeLessThanOrEqual(2);expect(vi.mocked(h.store.refresh).mock.calls.length).toBeLessThanOrEqual(1);
  expect(h.initial).toBe('rejected');expect(h.host.textContent).toMatch(/stale|unavailable|revision/iu);expect(action(h.host,'retry-panel','Retry Agents')).toBeDefined();
});
it('A4 unknown fold head is never treated as a confirmed zero revision', async () => {
  const service=new Service(),refresh=deferred<void>();const h=mount({service,head:null,refresh:() => refresh.promise});
  await flush();expectReads(h);expect(h.initial).not.toBe('fulfilled');expect(document.documentElement.hasAttribute('data-lin-rev')).toBe(false);
  h.publish({head:7});refresh.resolve();await flush();
});
it.each([
  ['unfiltered',{},'No agents yet.'],['local query',{q:'missing'},'No matching agents. Clear filters to see all loaded records.'],
  ['server filter',{workflow:'review'},'No matching agents. Clear filters to see all loaded records.'],
] as const)('A7 %s empty catalogue has its own honest state', async (_label,query,message) => {
  const service=new Service();service.records=[];const h=await boot({service,query});expect(h.host.textContent).toContain(message);expectReads(h);
  expect(h.host.textContent).not.toContain('Loading Agents.');
});
it('A7 partial catalogue declares coverage and retains pagination even with no local match', async () => {
  const service=new Service();service.overrides.set('agent_list',() => ({agents:[agent()],next_after:'alpha-root',head:7}));
  const h=await boot({service,query:{q:'missing'}});expect(h.host.textContent).toContain('Showing loaded agents. More agents are available.');
  expect(action(h.host,'page-agents','Load more agents')).toBeDefined();expect(h.host.textContent).not.toContain('No agents yet.');
});
it('A8 exclusive paging deduplicates equal overlaps and retries the failed cursor without losing focus', async () => {
  const service=new Service();let failed=false;
  service.overrides.set('agent_list',a => {
    if(!a.after) return {agents:[agent()],next_after:'alpha-root',head:7};
    if(a.after==='alpha-root') return {agents:[agent(),agent('beta-root')],next_after:'beta-root',head:7};
    if(!failed) {failed=true;throw failure();}return {agents:[agent('gamma-root')],next_after:null,head:7};
  });
  const h=await boot({service});const link=action(card(h,'alpha-root'),'open-agent');link.focus();
  action(h.host,'page-agents').click();await flush();expect(ids(h)).toEqual(['alpha-root','beta-root']);
  expect(document.activeElement?.closest<HTMLElement>('[data-lin-entity]')?.dataset.linId).toBe('alpha-root');
  action(h.host,'page-agents').click();await flush();expect(ids(h)).toEqual(['alpha-root','beta-root']);
  action(h.host,'retry-panel','Retry Agents').click();await flush();expect(ids(h)).toEqual(['alpha-root','beta-root','gamma-root']);
  expect(service.for('agent_list').slice(-2).map(c => c.args.after)).toEqual(['beta-root','beta-root']);expect(service.mutations()).toHaveLength(0);
});
it.each(['conflicting duplicate','nonprogressing cursor','backward cursor'])('A8 %s is invalid_response and preserves the committed page', async kind => {
  const service=new Service();service.overrides.set('agent_list',a => !a.after?{agents:[agent()],next_after:'beta-root',head:7}:
    {agents:[agent('alpha-root',kind==='conflicting duplicate'?{display_name:'Changed'}:{})],next_after:kind==='backward cursor'?'alpha-root':'beta-root',head:7});
  const h=await boot({service});card(h,'alpha-root');action(h.host,'page-agents').click();await flush();
  expect(h.host.textContent).toContain('invalid_response');expect(card(h,'alpha-root').textContent).toContain('Shared name');
});
it('A9 identity focus survives reordering and removal goes to heading with one announcement', async () => {
  const h=await boot();action(card(h,'alpha-root'),'open-agent').focus();await h.update({sort:'id-desc'});
  expect(document.activeElement).toBe(action(card(h,'alpha-root'),'open-agent'));
  h.service.records=h.service.records.filter(r => r.agent_id!=='alpha-root');await h.refresh();
  expect(document.activeElement).toBe(h.host.querySelector('h1'));
  expect(h.announcements.filter(e => e.message==='alpha-root is no longer in this view.')).toHaveLength(1);
});
it('A9 local typing preserves search value and caret across reads and scorecard updates', async () => {
  const h=await boot();const search=action<HTMLInputElement>(h.host,'filter-agent-query');search.focus();
  search.value='Shared';search.setSelectionRange(2,4);search.dispatchEvent(new Event('input',{bubbles:true}));await flush();await h.refresh();
  const current=action<HTMLInputElement>(h.host,'filter-agent-query');expect(current.value).toBe('Shared');expect(current.selectionStart).toBe(2);expect(current.selectionEnd).toBe(4);
  expect(document.activeElement).toBe(current);expect(h.service.mutations()).toHaveLength(0);
});
it('A10 cards distinguish current identity and all seat/arm groups, zero and unknown means', async () => {
  const service=new Service();service.scorecards.set('alpha-root',[group({runs:17,successes:11}),group({seat:{model:'synthetic-model',effort:'high',mode:'headless'},memory_arm:'inherited',runs:9,successes:7,mean_cost_micro_usd:null}),
    group({seat:{model:'synthetic-model',effort:'medium',mode:'interactive'},memory_arm:'none',runs:3,successes:0,mean_cost_micro_usd:0,mean_duration_ms:0})]);
  const h=await boot({service});const c=card(h,'alpha-root'),text=c.textContent!;
  for(const word of ['alpha-root',String(agent().agent_version),'develop','general','draft','synthetic-model','medium','high','headless','interactive','own','inherited','none','17','11','Not measured','0']) expect(text).toContain(word);
  expect(text.indexOf('alpha-root')).toBeLessThan(text.indexOf('develop'));expect(text).not.toMatch(/overall fitness|measured version/iu);
  expect(card(h,'beta-root').textContent).toContain('Not measured');
});
it('A10 A25 failed scorecards are isolated under one Retry Scorecard and do not advance catalogue head', async () => {
  const service=new Service();service.overrides.set('scorecard_get',() => {throw failure('internal','domain');});const h=await boot({service});
  card(h,'alpha-root');card(h,'beta-root');expect(action(h.host,'retry-panel','Retry Scorecard')).toBeDefined();
  const before=service.for('agent_list').length;service.overrides.set('scorecard_get',a => ({agent_id:a.agent_id,groups:[],head:99}));
  action(h.host,'retry-panel','Retry Scorecard').click();await flush();expect(service.for('agent_list')).toHaveLength(before);expect(h.state.head).toBe(7);
});
it('A25 later catalogue failure retains rows, comparison and its last acknowledged revision', async () => {
  const h=await boot({query:{compare:'["alpha-root","beta-root"]'}});card(h,'alpha-root');h.service.overrides.set('agent_list',() => {throw failure();});
  await h.refresh();expect(card(h,'alpha-root')).toBeDefined();expect(h.host.textContent).toContain('Data is stale. Last confirmed revision 7.');
  expect(action(h.host,'retry-panel','Retry Agents')).toBeDefined();expect(action<HTMLButtonElement>(h.host,'compare-agents').disabled).toBe(false);
});
it('A26 a superseded server-filter response cannot replace the current snapshot', async () => {
  const h=await boot();card(h,'alpha-root');const old=deferred();h.service.overrides.set('agent_list',a => a.workflow==='review'?old.promise:{agents:[agent('newer-root',{workflow:'test'})],next_after:null,head:7});
  const previous=h.update({workflow:'review'});await flush();await h.update({workflow:'test'});expect(ids(h)).toEqual(['newer-root']);
  old.resolve({agents:[agent('older-root',{workflow:'review'})],next_after:null,head:7});await previous;await flush();expect(ids(h)).toEqual(['newer-root']);
});
it('A26 disposal aborts owned reads, unsubscribes and ignores later resolution', async () => {
  const h=await boot();card(h,'alpha-root');const pending=deferred();h.service.overrides.set('agent_list',() => pending.promise);
  const work=h.refresh();await flush();const count=h.announcements.length;h.dispose();h.host.replaceChildren(document.createTextNode('Another route'));
  pending.resolve({agents:[agent('late-root')],next_after:null,head:7});await work;await flush();expect(h.host.textContent).toBe('Another route');
  expect(h.announcements).toHaveLength(count);expect(h.controller.signal.aborted).toBe(true);expect(h.listeners.size).toBe(0);expect(h.store.dispose).not.toHaveBeenCalled();
  expect(h.service.for('agent_list').every(c => c.options.signal instanceof AbortSignal)).toBe(true);
});
const badAgents: [string,(record: JsonObject) => JsonObject][] = [
  ['traversal ID',r => ({...r,agent_id:'../escape'})],['scheme ID',r => ({...r,agent_id:'javascript:attack'})],['invalid hash',r => ({...r,agent_version:'UPPER'})],
  ['unsafe integer',r => ({...r,memory_gen:Number.MAX_SAFE_INTEGER+1})],['boolean integer',r => ({...r,generation:false})],['unknown key',r => ({...r,extra:'passive'})],
  ['missing required field',r => {delete r.born;return r;}],['nested extra key',r => ({...r,allowed_seats:[{model:'x',effort:'medium',mode:'headless',extra:true}]})],
  ['reserved prototype key',r => JSON.parse(JSON.stringify(r).slice(0,-1)+',"__proto__":{"poisoned":true}}')],
  ['invalid genesis parents',r => ({...r,parents:['other-parent']})],['unpaired surrogate',r => ({...r,display_name:'\ud800'})],
];
it.each(badAgents)('A28 Amendment B rejects %s before links or follow-up reads', async (_label,change) => {
  const service=new Service();service.overrides.set('agent_list',() => ({agents:[change(clone(agent()))],next_after:null,head:7}));
  const h=mount({service});await flush();expectReads(h);expect(h.initial).toBe('rejected');expect(h.host.textContent).toContain('invalid_response');
  expect(h.host.querySelector('[data-lin-action="open-agent"]')).toBeNull();expect(service.for('scorecard_get')).toHaveLength(0);expect(({} as any).poisoned).toBeUndefined();
});
it.each([null,-1,true,Number.MAX_SAFE_INTEGER+1])('A4 A28 invalid list head %s cannot establish readiness', async value => {
  const service=new Service();service.overrides.set('agent_list',() => ({agents:[],next_after:null,head:value}));const h=mount({service});await flush();
  expectReads(h);expect(h.initial).toBe('rejected');expect(h.host.textContent).toContain('invalid_response');
});

it('A4 Amendment B initial failure rejects ready; public Retry Agents must restore real-shell readiness', async () => {
  const service=new Service();let unavailable=true;service.overrides.set('agent_list',a => {if(unavailable) throw failure();return service.reply('agent_list',a);});
  const root=document.createElement('div');document.body.append(root);const app=startApp({root,transport:service.transport,storage:window.localStorage,initialHash:'#/agents'});
  try {
    await flush();expect(service.for('agent_list').length,'Initial list failure must actually be observed').toBeGreaterThan(0);
    expect(document.documentElement.dataset.linReady).toBe('false');expect(root.textContent).toContain('Agents unavailable. Retry to continue.');
    unavailable=false;action(root,'retry-panel','Retry Agents').click();await flush();expect(root.querySelector('[data-lin-id="alpha-root"]')).not.toBeNull();
    expect(document.documentElement.dataset.linReady).toBe('true');expect(document.documentElement.dataset.linRev).toBe('7');
  } finally {app.dispose();}
});
it('A7 default catalogue page uses one hundred records and exposes coverage honestly', async () => {
  const service=new Service();service.records=Array.from({length:101},(_,i) => agent(`root-${String(i).padStart(3,'0')}`));const h=await boot({service});
  expectReads(h);expect(ids(h)).toHaveLength(100);expect(service.for('agent_list')[0].args.limit??100).toBe(100);
  expect(h.host.textContent).toContain('Showing loaded agents. More agents are available.');action(h.host,'page-agents').click();await flush();
  expect(ids(h)).toHaveLength(101);expect(h.host.querySelector('[data-lin-action="page-agents"]')).toBeNull();
});
it.each(['../escape','javascript:attack',17])('A28 invalid server cursor %s is rejected before paging or follow-up reads', async next_after => {
  const service=new Service();service.overrides.set('agent_list',() => ({agents:[agent()],next_after,head:7}));const h=mount({service});await flush();
  expectReads(h);expect(h.initial).toBe('rejected');expect(h.host.textContent).toContain('invalid_response');expect(service.for('scorecard_get')).toHaveLength(0);
});
