import { it, expect, vi } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import type { JsonObject } from '../../src/ui/contracts.ts';
import { actions } from '../../src/ui/contracts.ts';
import { lintOperability } from '../../src/ui/operability.ts';
import * as primitives from '../../src/ui/primitives.ts';
import { agent, group, longIds, repositoryPath } from './fixtures.ts';
import { Service, action, boot, card, controls, dialog, enter, failure, field, fillCreate, flush, isolate, key, mount, name, openCreate } from './helpers.ts';
isolate();

it('A2 A27 rendered agents retain native registered unique controls and heading-labelled cards', async () => {
  const h=await boot();card(h,'alpha-root');expect(lintOperability(h.root)).toEqual([]);
  for(const c of controls(h.root)) {expect(c.matches('button,a,input,select')).toBe(true);expect(actions.has(c.dataset.linAction!)).toBe(true);expect(c.closest('article')).toBeNull();expect(c.tabIndex).toBeLessThanOrEqual(0);}
  for(const c of h.host.querySelectorAll('[data-lin-entity="agent"]')) {
    expect(c.matches('li,section')).toBe(true);const heading=c.querySelector('h2,h3');expect(heading?.textContent).toBe(`Agent ${key('agent',c.getAttribute('data-lin-id')!)}`);
    expect(c.getAttribute('aria-labelledby')?.split(/\s+/u)).toContain(heading?.id);
  }
  expect(h.host.querySelectorAll('h1')).toHaveLength(1);expect(h.host.querySelector('[aria-live],[role="status"]')).toBeNull();
});
it.each(['article action','generic clickable','extra heading','extra live region','unnamed control','positive tabindex'])('A2 A27 rejecting structural contrast: %s', async kind => {
  const h=await boot();card(h,'alpha-root');expect(lintOperability(h.root)).toEqual([]);
  const control=action(card(h,'alpha-root'),'open-agent');
  if(kind==='article action') {const article=document.createElement('article');control.replaceWith(article);article.append(control);}
  if(kind==='generic clickable') {const div=document.createElement('div');div.dataset.linAction='create-agent';div.setAttribute('role','button');div.textContent='Hostile action';h.host.append(div);}
  if(kind==='extra heading') h.host.append(document.createElement('h1'));
  if(kind==='extra live region') {const status=document.createElement('div');status.setAttribute('role','status');status.setAttribute('aria-label','Application updates');h.host.append(status);}
  if(kind==='unnamed control') {const button=document.createElement('button');button.dataset.linAction='create-agent';h.host.append(button);}
  if(kind==='positive tabindex') control.tabIndex=1;
  expect(lintOperability(h.root).length).toBeGreaterThan(0);
});
it('A3 A27 names fit the normalized byte ceiling while full long IDs remain descriptions', async () => {
  const service=new Service();service.records=longIds.map(id => agent(id,{display_name:'🧬'.repeat(128)}));const h=await boot({service});card(h,longIds[0]);
  const names=controls(h.root).map(el => name(el).normalize('NFC').replace(/\s+/gu,' ').trim());expect(new Set(names).size).toBe(names.length);
  for(const value of names) expect(new TextEncoder().encode(value).length).toBeLessThanOrEqual(64);
  for(const id of longIds) {const c=card(h,id);expect(c.textContent).toContain(id);const link=action(c,'open-agent');const described=link.getAttribute('aria-describedby');expect(described).toBeTruthy();
    expect(described!.split(/\s+/u).map(ref => document.getElementById(ref)?.textContent??'').join(' ')).toContain(id);}
});
it('A3 initial identityKey collision rejects readiness and disables affected actions', async () => {
  const original=primitives.identityKey;vi.spyOn(primitives,'identityKey').mockImplementation((kind,id) => kind==='agent'?'forced-collision':original(kind,id));
  const h=mount();await flush();expect(h.service.for('agent_list').length).toBeGreaterThan(0);expect(h.initial).toBe('rejected');expect(h.host.textContent).toContain('Identity key collision. Actions unavailable.');
  for(const el of h.host.querySelectorAll<HTMLElement>('[data-lin-entity="agent"] [data-lin-action]')) expect(el.matches(':disabled,[aria-disabled="true"]')||!el.hasAttribute('href')).toBe(true);
});
it('A3 Amendment B collision discovered after paging disables affected controls without pretending to unresolve ready', async () => {
  const service=new Service();service.overrides.set('agent_list',a => ({agents:a.after?[agent('beta-root')]:[agent()],next_after:a.after?null:'alpha-root',head:7}));const h=await boot({service});card(h,'alpha-root');
  const original=primitives.identityKey;vi.spyOn(primitives,'identityKey').mockImplementation((kind,id) => kind==='agent'?'forced-collision':original(kind,id));
  action(h.host,'page-agents').click();await flush();expect(h.initial).toBe('fulfilled');expect(h.host.textContent).toContain('Identity key collision. Actions unavailable.');
  expect(h.service.mutations()).toHaveLength(0);
});
it('A11 A25 comparison close and repeated reads do not repeat recorded announcements', async () => {
  const h=await boot({query:{compare:'["alpha-root","beta-root"]'}});card(h,'alpha-root');const start=h.announcements.filter(e => e.message.startsWith('Create agent recorded')).length;
  for(let i=0;i<2;i++) {action(h.host,'compare-agents').click();await flush();action(dialog(),'close-inspector').click();await h.refresh();}
  expect(h.announcements.filter(e => e.message.startsWith('Create agent recorded'))).toHaveLength(start);expect(h.root.querySelectorAll('[role="status"]')).toHaveLength(1);
});
it('A12 Create contains Tab and Shift+Tab and restores invoker with Escape and Cancel', async () => {
  const h=await boot(),trigger=action(h.host,'create-agent');trigger.focus();let d=await openCreate(h);const first=field(d,'agent_id'),last=controls(d).filter(el => !(el as HTMLButtonElement).disabled).at(-1)!;
  last.focus();d.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));expect(document.activeElement).toBe(first);
  first.focus();d.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',shiftKey:true,bubbles:true,cancelable:true}));expect(document.activeElement).toBe(last);
  d.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));await flush();expect(document.activeElement).toBe(trigger);
  d=await openCreate(h);action(d,'cancel-dialog','Cancel Create agent').click();await flush();expect(document.activeElement).toBe(trigger);expect(h.service.mutations()).toHaveLength(0);
});
it('A12 Create makes its background inert and all exposed names stay unique', async () => {
  const h=await boot(),d=await openCreate(h);expect(controls(h.root).every(el => d.contains(el))).toBe(true);expect(lintOperability(h.root).filter(i => i.code==='duplicate_name')).toEqual([]);
  expect(document.querySelectorAll('dialog[open]')).toHaveLength(1);expect(d.getAttribute('aria-modal')).toBe('true');expect(h.service.mutations()).toHaveLength(0);
});
it('A15 Enter in Find agents cannot dispatch creation', async () => {
  const h=await boot();const search=action<HTMLInputElement>(h.host,'filter-agent-query');search.focus();search.value='Shared';search.dispatchEvent(new Event('input',{bubbles:true}));
  search.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));await flush();expect(h.service.mutations()).toHaveLength(0);expect(document.querySelector('dialog[open]')).toBeNull();
});
it('A25 retry of references does not restart skills, erase fields or submit', async () => {
  const service=new Service();service.overrides.set('reference_get',() => {throw failure();});service.overrides.set('skill_list',() => {throw failure();});const h=await boot({service}),d=await openCreate(h);await fillCreate(d);
  const skills=service.for('skill_list').length;action(d,'retry-panel','Retry References').click();await flush();expect(service.for('skill_list')).toHaveLength(skills);
  expect(field(d,'display_name').value).toBe('New child');expect(action(d,'retry-panel','Retry Skills')).toBeDefined();expect(service.mutations()).toHaveLength(0);
});
it('A27 fixtures retain filtering, sorting, navigation and comparison while visibly synthetic', async () => {
  const service=new Service();service.mode='fixture';const h=await boot({service,query:{compare:'["alpha-root","beta-root"]'}});card(h,'alpha-root');
  expect(h.root.textContent).toContain('Synthetic fixtures. Changes are unavailable.');await enter(h.host,'filter-agent-query','Shared');await enter(h.host,'sort-agents','id-desc');
  action(card(h,'alpha-root'),'open-agent').click();expect(h.navigate).toHaveBeenLastCalledWith({screen:'agent',agentId:'alpha-root',query:{}});
  await h.update({compare:'["alpha-root","beta-root"]'});action(h.host,'compare-agents').click();await flush();expect(dialog().querySelector('table')).not.toBeNull();expect(service.mutations()).toHaveLength(0);
});
it('A28 hostile display names, reference rules and errors stay passive text', async () => {
  const service=new Service(),hostile='<img src=x onerror=attack()><script>attack()</script>';service.records=[agent('alpha-root',{display_name:hostile})];
  const h=await boot({service});expect(card(h,'alpha-root').textContent).toContain(hostile);expect(h.host.querySelector('img,script')).toBeNull();
  service.overrides.set('reference_get',a => {const result=service.reply('reference_get',a);(result.reference as JsonObject).rules=[{id:'hostile',section:'passive',text:hostile}];return result;});
  const d=await openCreate(h);expect(d.querySelector('img,script')).toBeNull();expect(service.mutations()).toHaveLength(0);
});
it('A28 authored screen imports stay relative and shared transport is the only public tool boundary', async () => {
  const h=await boot();card(h,'alpha-root');const base='ui/src/screens/agents/';
  for(const module of ['index.ts','types.ts','model.ts','view.ts','create.ts','comparison.ts']) {
    const url=repositoryPath(base+module);if(!existsSync(url)) continue;const source=readFileSync(url,'utf8');
    expect(source).not.toMatch(/https?:\/\/|node:child_process|\bfetch\s*\(|XMLHttpRequest|X-Lineage-Session|lineage-session-token/u);
    for(const m of source.matchAll(/\bfrom\s*['"]([^'"]+)['"]/gu)) expect(m[1].startsWith('.')).toBe(true);
  }
  expect(h.service.calls.every(c => c.options.signal instanceof AbortSignal)).toBe(true);
});
it('A29 static style precondition: entry imports owned CSS, with no remote asset or motion-dependent readiness', async () => {
  const h=await boot();card(h,'alpha-root');const entry=readFileSync(repositoryPath('ui/src/screens/agents/index.ts'),'utf8');
  expect(entry).toMatch(/['"]\.\.\/\.\.\/\.\.\/styles\/agents\.css['"]/u);
  const css=repositoryPath('ui/styles/agents.css');expect(existsSync(css),'Owned Agents styles must exist before external pixel verification').toBe(true);
  expect(readFileSync(css,'utf8')).not.toMatch(/https?:\/\//u);
  // This source assertion is not a geometry, computed contrast, Chrome or AT-SPI receipt.
});
it('A31 local prune contrast removes an article-contained action and loses the required inventory', async () => {
  const h=await boot();const link=action(card(h,'alpha-root'),'open-agent'),expected=name(link);expect(controls(h.root).some(el => name(el)===expected)).toBe(true);
  const article=document.createElement('article');link.replaceWith(article);article.append(link);const transformed=h.root.cloneNode(true) as HTMLElement;
  for(const opaque of transformed.querySelectorAll('article')) opaque.replaceChildren();expect(controls(transformed).some(el => name(el)===expected)).toBe(false);
  expect(lintOperability(h.root).some(i => i.code==='interactive_article')).toBe(true);
  // C/A/P/V observers and persona capsules remain external acceptance gates.
});
const invalidScores: [string,(v: JsonObject) => JsonObject][] = [
  ['extra result key',v => ({...v,extra:true})],['wrong agent ID',v => ({...v,agent_id:'../escape'})],['unsafe head',v => ({...v,head:Number.MAX_SAFE_INTEGER+1})],
  ['negative runs',v => ({...v,groups:[group({runs:-1})]})],['successes exceed runs',v => ({...v,groups:[group({runs:1,successes:2})]})],
  ['nonfinite mean',v => ({...v,groups:[group({mean_duration_ms:Infinity})]})],['extra seat key',v => ({...v,groups:[group({seat:{model:'synthetic',effort:'medium',mode:'headless',extra:true}})]})],
];
it.each(invalidScores)('A10 A28 malformed scorecard %s is isolated from the usable catalogue', async (_label,corrupt) => {
  const service=new Service();service.overrides.set('scorecard_get',a => corrupt(service.reply('scorecard_get',a)));const h=await boot({service});card(h,'alpha-root');
  expect(h.host.textContent).toContain('invalid_response');expect(action(h.host,'retry-panel','Retry Scorecard')).toBeDefined();expect(service.mutations()).toHaveLength(0);
});
