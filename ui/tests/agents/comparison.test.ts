import { it, expect } from 'vitest';
import type { JsonObject } from '../../src/ui/contracts.ts';
import { agent, group, longIds } from './fixtures.ts';
import { Service, action, boot, card, deferred, dialog, failure, flush, isolate, name } from './helpers.ts';
isolate();
async function select(h: Awaited<ReturnType<typeof boot>>,id: string): Promise<void> {action<HTMLInputElement>(card(h,id),'compare-agent').click();await flush();}
async function compare(h: Awaited<ReturnType<typeof boot>>): Promise<HTMLDialogElement> {action(h.host,'compare-agents','Compare selected agents').click();await flush();return dialog();}

it('A11 exactly two full identities enable comparison; excess selection is blocked with text', async () => {
  const h=await boot();expect(action<HTMLButtonElement>(h.host,'compare-agents').disabled).toBe(true);await select(h,'alpha-root');expect(action<HTMLButtonElement>(h.host,'compare-agents').disabled).toBe(true);
  await select(h,'beta-root');expect(action<HTMLButtonElement>(h.host,'compare-agents').disabled).toBe(false);await select(h,'gamma-root');
  expect(action<HTMLInputElement>(card(h,'gamma-root'),'compare-agent').checked).toBe(false);expect(h.host.textContent).toMatch(/two|2/iu);
  expect(h.navigate).toHaveBeenLastCalledWith({screen:'agents',query:{compare:'["alpha-root","beta-root"]'}});
});
it('A11 selected full identities survive sorting, filtering and reload with duplicate display names', async () => {
  const service=new Service();service.records=longIds.map(id => agent(id));const h=await boot({service});for(const id of longIds) await select(h,id);
  const compareQuery=JSON.stringify(longIds);await h.update({q:'invisible',sort:'id-desc',compare:compareQuery});expect(action<HTMLButtonElement>(h.host,'compare-agents').disabled).toBe(false);
  const d=await compare(h);expect(name(d)).toBe('agent comparison');for(const id of longIds) expect(d.textContent).toContain(id);
  expect(d.querySelector('[data-lin-action="open-agent"]')).toBeNull();action(d,'close-inspector','Close agent comparison').click();
  h.dispose();h.root.remove();const restored=await boot({service,query:{compare:compareQuery}});for(const id of longIds) expect(action<HTMLInputElement>(card(restored,id),'compare-agent').checked).toBe(true);
});
it('A11 measured comparison uses a labelled native table and separate seat/arm rows with missing values intact', async () => {
  const service=new Service();service.scorecards.set('alpha-root',[group({runs:19,successes:13}),group({seat:{model:'synthetic-model',effort:'high',mode:'headless'},memory_arm:'inherited',runs:5,successes:3})]);
  service.scorecards.set('beta-root',[group({seat:{model:'synthetic-model',effort:'medium',mode:'interactive'},memory_arm:'none',runs:7,successes:0,mean_cost_micro_usd:null})]);
  const h=await boot({service,query:{compare:'["alpha-root","beta-root"]'}}),d=await compare(h),table=d.querySelector('table');expect(table).not.toBeNull();
  expect(table!.querySelector('caption')?.textContent||table!.getAttribute('aria-label')||table!.getAttribute('aria-labelledby')).toBeTruthy();
  expect(table!.querySelectorAll('th').length).toBeGreaterThan(0);const rows=Array.from(table!.querySelectorAll('tbody tr')).map(r => r.textContent??'');
  for(const tuple of [['headless','medium','own','19','13'],['headless','high','inherited','5','3'],['interactive','medium','none','7','0']]) expect(rows.some(row => tuple.every(part => row.includes(part)))).toBe(true);
  expect(table!.textContent).toContain('Not measured');expect(table!.textContent).not.toMatch(/overall fitness|measured version/iu);expect(service.mutations()).toHaveLength(0);
});
it('A11 an unmeasured selected agent remains visible instead of being omitted or replaced by zero', async () => {
  const h=await boot({query:{compare:'["alpha-root","beta-root"]'}}),d=await compare(h);expect(d.textContent).toContain('alpha-root');expect(d.textContent).toContain('beta-root');expect(d.textContent).toContain('Not measured');
  expect(h.service.mutations()).toHaveLength(0);
});
it('A11 Amendment B no_agent remains explicit without substituting a visible agent', async () => {
  const h=await boot({query:{compare:'["alpha-root","missing-root"]'}});action(h.host,'compare-agents').click();await flush();expect(h.root.textContent).toContain('no_agent');
  const modal=document.querySelector('dialog[open]');if(modal) expect(modal.textContent).not.toContain('beta-root');
  expect(h.service.for('agent_get').some(c => c.args.agent_id==='missing-root')).toBe(true);expect(h.service.mutations()).toHaveLength(0);
});
it('A11 Amendment B transient comparison agent_get failure has a registered isolated retry', async () => {
  const h=await boot({query:{compare:'["alpha-root","unloaded-root"]'}});h.service.records.push(agent('unloaded-root'));
  let unavailable=true;h.service.overrides.set('agent_get',a => {if(unavailable) throw failure();return h.service.reply('agent_get',a);});
  action(h.host,'compare-agents').click();await flush();const scope=document.querySelector('dialog[open]')??h.host;
  const retries=Array.from(scope.querySelectorAll<HTMLButtonElement>('[data-lin-action="retry-panel"]')).filter(el => /Retry (?:Agent|Verification)/u.test(name(el)));
  expect(retries,'Comparison agent_get failure needs its own registered Retry').toHaveLength(1);unavailable=false;retries[0].click();await flush();
  expect(h.root.textContent).toContain('unloaded-root');expect(h.service.mutations()).toHaveLength(0);
});
it('A11 clearing comparison changes only the route selection and never domain state', async () => {
  const h=await boot({query:{compare:'["alpha-root","beta-root"]'}});action(h.host,'clear-comparison').click();await flush();
  expect(h.navigate).toHaveBeenLastCalledWith({screen:'agents',query:{}});expect(action<HTMLButtonElement>(h.host,'compare-agents').disabled).toBe(true);expect(h.service.mutations()).toHaveLength(0);
});
it('A12 comparison traps Tab in the helper modal, Escape closes and focus returns to the trigger', async () => {
  const h=await boot({query:{compare:'["alpha-root","beta-root"]'}}),trigger=action(h.host,'compare-agents');trigger.focus();const d=await compare(h);
  expect(d.contains(document.activeElement)).toBe(true);const close=action(d,'close-inspector');close.focus();d.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));
  expect(d.contains(document.activeElement)).toBe(true);d.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));await flush();expect(d.isConnected).toBe(false);expect(document.activeElement).toBe(trigger);
});
it('A22 A25 scorecard failure in comparison retains both identities and one modal Retry Scorecard', async () => {
  const h=await boot({query:{compare:'["alpha-root","beta-root"]'}});h.service.overrides.set('scorecard_get',() => {throw failure();});const d=await compare(h);
  expect(d.textContent).toContain('alpha-root');expect(d.textContent).toContain('beta-root');expect(action(d,'retry-panel','Retry Scorecard')).toBeDefined();
  h.service.overrides.delete('scorecard_get');action(d,'retry-panel','Retry Scorecard').click();await flush();expect(h.service.mutations()).toHaveLength(0);
});
it('A26 closed comparison ignores a late agent_get response and does not reopen', async () => {
  const h=await boot({query:{compare:'["alpha-root","unloaded-root"]'}});const response=deferred();h.service.overrides.set('agent_get',() => response.promise);
  action(h.host,'compare-agents').click();await flush();const d=dialog();action(d,'close-inspector').click();const before=h.announcements.length;
  response.resolve({record:agent('unloaded-root')});await flush();expect(document.querySelector('dialog[open]')).toBeNull();expect(h.announcements).toHaveLength(before);
});
it.each([
  {agent_id:'../escape'}, {agent_id:'javascript:attack'}, {agent_version:'invalid'}, {unexpected:true},
])('A28 comparison rejects hostile agent_get record %j before enabling unsafe actions', async changes => {
  const h=await boot({query:{compare:'["alpha-root","unloaded-root"]'}});h.service.overrides.set('agent_get',() => ({record:agent('unloaded-root',changes as unknown as JsonObject)}));
  action(h.host,'compare-agents').click();await flush();expect(h.root.textContent).toContain('invalid_response');expect(h.root.querySelector('a[href^="javascript:"]')).toBeNull();expect(h.service.mutations()).toHaveLength(0);
});
