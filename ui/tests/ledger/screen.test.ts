// @vitest-environment jsdom
import { it, expect, vi } from 'vitest';
import { startApp } from '../../src/main.ts';
import { parseRoute } from '../../src/router.ts';
import { screen } from '../../src/screens/ledger/index.ts';
import {
  ACTOR, action, assertRead, deferred, descriptors, event, flush, id, ids, input,
  isolate, mount, own, page, record, retry, scripted, sourceExists, sourceText, transport, visibleText,
} from './fixtures.ts';
isolate();

it('A1 exports the shared screen, replaces the placeholder and imports its owned CSS', async()=>{
  const h=await mount(transport(()=>page([event(1)])).transport);await h.ready;
  expect(screen.id).toBe('ledger');expect(screen.title).toBe('Ledger');
  expect(h.main.querySelectorAll('h1')).toHaveLength(1);expect(h.main.querySelector('h1')?.textContent).toBe('Ledger');
  expect(h.main.textContent).not.toMatch(/not built yet|placeholder/i);record(h.main,id(1));
  const source=sourceText('ui/src/screens/ledger/index.ts');
  expect(source).toMatch(/import\s*['"]\.\.\/\.\.\/\.\.\/styles\/ledger\.css['"]/);
  expect(sourceExists('ui/styles/ledger.css')).toBe(true);
  expect(h.main.querySelector('main,header,nav,[role="status"],[aria-live]')).toBeNull();
});
it('A2 keeps Loading and the initial ready promise pending until the active page is folded', async()=>{
  const first=deferred<unknown>();const t=scripted([first.promise]);const h=await mount(t.transport,{},null);
  let settled=false;void h.ready.then(()=>{settled=true;},()=>{settled=true;});await flush();
  expect(visibleText(h.main)).toContain('Loading');expect(settled).toBe(false);assertRead(t.calls[0],0);
  first.resolve(page());await h.ready;
  expect(visibleText(h.main)).toContain('No ledger events yet.');expect(settled).toBe(true);
});
it('A2 renders an established unfiltered empty journal rather than a no-match', async()=>{
  const h=await mount(transport(()=>page()).transport,{},0);await h.ready;
  expect(visibleText(h.main)).toContain('No ledger events yet.');expect(visibleText(h.main)).not.toContain('No matching events');
  expect(h.main.querySelector('[data-lin-action="page-events"]:not(:disabled)')).toBeNull();
});
it('A2 initial failure rejects readiness, preserves unknown head and offers Retry Ledger', async()=>{
  const t=scripted([new Error('Synthetic initial failure')]);const h=await mount(t.transport,{},null);
  await expect(h.ready).rejects.toBeDefined();retry(h.main);
  expect(visibleText(h.main)).not.toContain('No ledger events yet.');expect(h.store.getState().head).toBeNull();
  expect(document.documentElement.hasAttribute('data-lin-rev')).toBe(false);
});
it('A2 A18 initial failure recovers by an explicit named retry without remounting', async()=>{
  // A-U26: let AppStore.refresh acknowledge the recovered page through Transport.events at the same head.
  const t=scripted([new Error('Synthetic read failure'),page([event(1)])],1);const h=await mount(t.transport,{},null);
  await h.ready.catch(()=>{});retry(h.main).click();await flush();
  expect(ids(h.main)).toEqual([id(1)]);expect(t.calls).toHaveLength(2);assertRead(t.calls[1],0);
});
it.each(['ledger_events','ledger_verify','ledger_export'])('A3 discovery absence of %s fails its affected action visibly', async missing=>{
  const t=transport(tool=>tool==='ledger_events'?page([event(1)]):{});
  t.transport.tools=vi.fn(async()=>descriptors.filter(d=>d.name!==missing));
  const h=await mount(t.transport);await h.ready.catch(()=>{});await flush();
  if(missing!=='ledger_events') {
    const button=action<HTMLButtonElement>(h.main,missing==='ledger_verify'?'verify-ledger':'export-ledger');
    if(!button.disabled) button.click();await flush();
  }
  expect(visibleText(h.main)).not.toMatch(/not built yet|placeholder/i);
  expect(visibleText(h.main)).toMatch(/unavailable|dependency|missing|incompatible/i);
  expect(t.calls.filter(c=>c.tool===missing)).toHaveLength(0);
});
it('A2 A15 publishes a populated Ledger through the real shell with the acknowledged global revision', async()=>{
  const t=transport(()=>page([event(1)]),{events:vi.fn(async()=>page([event(1)]))});
  const root=document.createElement('div');document.body.append(root);
  const app=own(startApp({root,transport:t.transport,initialHash:'#/ledger',storage:null}));await flush();
  const main=root.querySelector('main')!;record(main,id(1));
  expect(document.documentElement.dataset.linReady).toBe('true');expect(document.documentElement.dataset.linRev).toBe('1');
  expect(app.store.getState().head).toBe(1);expect(document.title).toBe('Lineage · Ledger');
});
it('A2 refuses a newer page fold when store refresh cannot establish its head', async()=>{
  const t=transport(()=>page([event(2)]),{events:vi.fn(async()=>{throw Error('Synthetic snapshot unavailable');})});
  const h=await mount(t.transport,{},1);await h.ready.catch(()=>{});await flush();
  expect(h.store.refresh).toHaveBeenCalled();expect(h.store.getState().head).toBe(1);
  expect(ids(h.main)).not.toContain(id(2));retry(h.main);
});
it('A9 invalid query values reset only their own field and unknown fields retain the router notice', async()=>{
  const parsed=parseRoute('#/ledger?q=Checkpoint&agent=INVALID&kind=run.beat&event=e-0000000000000001&extra=ignored');
  expect(parsed.notice).toBe('Unknown query fields ignored.');
  const t=scripted([page([event(1)])]);const h=await mount(t.transport,parsed.route.query);await h.ready;
  expect(action<HTMLInputElement>(h.main,'filter-ledger-query').value).toBe('Checkpoint');
  expect(action<HTMLSelectElement>(h.main,'filter-ledger-agent').value).toBe('');
  expect(action<HTMLSelectElement>(h.main,'filter-ledger-kind').value).toBe('run.beat');
  assertRead(t.calls[0],0,{kinds:['run.beat']});record(h.main,id(1));
});
it('A9 deep link finds a later full ID only through sequential cursor reads', async()=>{
  const next=deferred<unknown>();const t=scripted([
    page([event(1)],{head:5,next_after:3,has_more:true}),next.promise]);
  const h=await mount(t.transport,{event:id(5)},5);await flush();record(h.main,id(1));
  expect(visibleText(h.main)).toMatch(/search|looking|scann|partial|unscanned/i);
  // Either explicit continuation or asynchronous continuation is valid; neither invents an endpoint.
  if(t.calls.length===1) action(h.main,'page-events').click();await flush();
  assertRead(t.calls[1],3);next.resolve(page([event(5)],{head:5}));await flush();await h.ready;
  record(h.main,id(5));expect(h.store.getState().selection.ledger??h.context.route.query.event).toBe(id(5));
  expect(t.transport.events).not.toHaveBeenCalled();expect(t.calls.every(c=>c.tool==='ledger_events')).toBe(true);
});
it.each([{}, {agent:ACTOR,kind:'run.beat'}] as Record<string,string>[])('A9 absent target under %j never broadens server filters', async filters=>{
  const t=scripted([page([event(1)])]);const h=await mount(t.transport,{...filters,event:id(2)});await h.ready;await flush();
  expect(visibleText(h.main)).toMatch(/not found|not.*(?:loaded|available|present)/i);
  if(filters.agent) expect(visibleText(h.main)).toMatch(/active filters|under.*filters/i);
  expect(t.calls).toHaveLength(1);assertRead(t.calls[0],0,filters.agent?{agent_id:ACTOR,kinds:['run.beat']}:{ });
});
it('A9 clear filters preserves a requested event so it can be resolved again', async()=>{
  const t=transport(()=>page([event(1)]));const h=await mount(t.transport,{q:'absent',agent:ACTOR,kind:'run.beat',event:id(2)});
  await h.ready;action(h.main,'clear-ledger-filters').click();await flush();
  expect(h.context.navigate).toHaveBeenLastCalledWith({screen:'ledger',query:{event:id(2)}});
});
it('A9 URL restoration uses full identities and never carries cursor, export draft or credentials', async()=>{
  const t=transport(()=>page([event(1)]));const restored={q:'Checkpoint',agent:ACTOR,kind:'run.beat',event:id(1)};
  const h=await mount(t.transport,restored);await h.ready;
  input(h.main,'filter-ledger-query','mixed [literal].*');await flush();
  const navigate=h.context.navigate as ReturnType<typeof vi.fn>;const route=navigate.mock.calls.at(-1)?.[0];
  expect(route.screen).toBe('ledger');expect(route.query).toEqual({...restored,q:'mixed [literal].*'});
  await h.update(restored);expect(action<HTMLInputElement>(h.main,'filter-ledger-query').value).toBe('Checkpoint');record(h.main,id(1));
});
it('A18 retains one shell-owned status node and deduplicates unchanged updates', async()=>{
  const h=await mount(transport(()=>page([event(1)])).transport);await h.ready;const status=h.status;
  record(h.main,id(1));await h.update();await h.update();await flush();
  expect(h.root.querySelectorAll('[role="status"],[aria-live]')).toHaveLength(1);
  expect(h.root.querySelector('[role="status"]')).toBe(status);
  const messages=h.announcements.mock.calls.map(c=>String(c[1]));
  expect(new Set(messages).size).toBe(messages.length);
});
it('A15 refresh preserves event selection, disclosure state and focus by full identity', async()=>{
  const t=transport(()=>page([event(1),event(2)]));const h=await mount(t.transport,{event:id(2)},2);await h.ready;
  const target=action(record(h.main,id(2)),'toggle-event-hash');target.click();target.focus();
  await h.update();await flush();
  const same=action(record(h.main,id(2)),'toggle-event-hash');
  expect(same.getAttribute('aria-expanded')).toBe('true');expect(document.activeElement).toBe(same);
  expect(h.context.route.query.event??h.store.getState().selection.ledger).toBe(id(2));
});
it('A15 replacement removal focuses the Ledger heading and announces removal once', async()=>{
  const t=transport(()=>page([event(1),event(2)]));const h=await mount(t.transport,{event:id(2)},2);await h.ready;
  const target=action(record(h.main,id(2)),'toggle-event-hash');target.click();target.focus();
  t.call.mockImplementation(async()=>page([event(1)]) as never);h.acknowledge(1,[event(1)]);await h.update();await flush();
  expect(ids(h.main)).not.toContain(id(2));expect(document.activeElement).toBe(h.main.querySelector('h1'));
  expect(h.announcements.mock.calls.filter(c=>String(c[1])===`${id(2)} is no longer in this view.`)).toHaveLength(1);
});
it('A5 A18 local no-match is distinct from an empty authoritative journal', async()=>{
  const t=transport(()=>page([event(1)],{head:4,next_after:2,has_more:true}));const h=await mount(t.transport,{},4);await h.ready;
  input(h.main,'filter-ledger-query','no matching literal here');await flush();
  expect(visibleText(h.main)).toContain('No matching events. Clear filters to see all loaded records.');
  expect(visibleText(h.main)).not.toContain('No ledger events yet.');expect(t.calls).toHaveLength(1);
});
it('A8 initial read from an obsolete filter cannot settle the current update fold', async()=>{
  const initial=deferred<unknown>(),replacement=deferred<unknown>();const t=scripted([initial.promise,replacement.promise]);
  const h=await mount(t.transport);await flush();const update=h.update({agent:ACTOR});let settled=false;
  void update.then(()=>{settled=true;},()=>{settled=true;});await flush();initial.resolve(page([event(1)]));await flush();
  expect(settled).toBe(false);expect(ids(h.main)).toEqual([]);replacement.resolve(page([event(2)]));h.acknowledge(2);await update;
  expect(ids(h.main)).toEqual([id(2)]);assertRead(t.calls[1],0,{agent_id:ACTOR});
});
it('A9 active deep-link scan stays cancellable while the next page is unresolved', async()=>{
  const next=deferred<unknown>();const t=scripted([page([event(1)],{head:10000,next_after:100,has_more:true}),next.promise]);
  const h=await mount(t.transport,{event:id(9999)},10000);await flush();record(h.main,id(1));
  if(t.calls.length===1) action(h.main,'page-events').click();await flush();expect(t.calls).toHaveLength(2);
  input(h.main,'filter-ledger-query','Checkpoint');await flush();h.controller.abort();h.mounted.dispose();
  const before=h.main.textContent;next.resolve(page([event(9999)],{head:10000,next_after:10000}));await flush();
  expect(h.main.textContent).toBe(before);expect(t.calls).toHaveLength(2);
});
