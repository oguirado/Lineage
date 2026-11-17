// @vitest-environment jsdom
import { afterAll, beforeAll, describe, it, expect, vi } from 'vitest';
import type { EventsPage, JsonObject } from '../../src/ui/contracts.ts';
import {
  ACTOR, action, assertRead, bank, click, deferred, event, flush, id, ids, input, isolate,
  mount, networkError, page, reads, record, retry, scripted, transport, visibleText, type Harness,
} from './fixtures.ts';

describe('cursor, filter and recovery behavior',()=>{
  isolate();
  it('A3 A4 requests exact initial and continuation K0 arguments', async()=>{
    const t=scripted([page([event(1)],{head:9,next_after:5,has_more:true}),page([event(9)],{head:9})]);
    const h=await mount(t.transport,{agent:ACTOR,kind:'run.beat'},9);await h.ready;
    expect(t.calls).toHaveLength(1);assertRead(t.calls[0],0,{agent_id:ACTOR,kinds:['run.beat']});
    await click(h.main,'page-events');expect(t.calls).toHaveLength(2);assertRead(t.calls[1],5,{agent_id:ACTOR,kinds:['run.beat']});
    expect(ids(h.main)).toEqual([id(1),id(9)]);expect(h.main.querySelector('[data-lin-action="page-events"]:not(:disabled)')).toBeNull();
  });
  it('A4 advances across empty filtered pages and trailing nonmatches using next_after', async()=>{
    const t=scripted([page([event(1)],{head:12,next_after:4,has_more:true}),
      page([],{head:12,next_after:8,has_more:true}),page([],{head:12,next_after:12})]);
    const h=await mount(t.transport,{agent:ACTOR},12);await h.ready;await click(h.main,'page-events');
    expect(ids(h.main)).toEqual([id(1)]);expect(visibleText(h.main)).not.toContain('No ledger events yet.');
    await click(h.main,'page-events');expect(t.calls.map(c=>c.args.after)).toEqual([0,4,8]);
    expect(ids(h.main)).toEqual([id(1)]);expect(h.main.querySelector('[data-lin-action="page-events"]:not(:disabled)')).toBeNull();
  });
  const malformed:(readonly [string,unknown])[]=[
    ['extra page key',{...page([event(1)]),extra:true}],
    ['unsafe head',page([],{head:Number.MAX_SAFE_INTEGER+1})],
    ['boolean head',page([],{head:true as unknown as number})],
    ['null cursor',page([],{next_after:null as unknown as number})],
    ['cursor beyond head',page([],{head:1,next_after:2})],
    ['negative head',page([],{head:-1})],
    ['string boolean',page([],{has_more:'true' as unknown as boolean})],
    ['unknown event kind',page([event(1,{kind:'instruction.execute'})])],
    ['invalid event ID',page([event(1,{id:'truncated'})])],
    ['invalid actor',page([event(1,{agent:'<img>'})])],
    ['uppercase hash',page([event(1,{sha256:'A'.repeat(64)})])],
    ['zero Lamport',page([event(1,{lamport:0})])],
    ['fractional Lamport',page([event(1,{lamport:1.5})])],
    ['array payload',page([event(1,{payload:[] as unknown as JsonObject})])],
    ['invalid evidence path',page([event(1,{evidence:[{path:'../outside',sha256:'a'.repeat(64)}]})])],
    ['extra evidence key',page([event(1,{evidence:[{path:'evidence/x',sha256:'a'.repeat(64),extra:true} as never]})])],
    ['extra event key',page([{...event(1),extra:true} as never])],
    ['non-finite payload',page([event(1,{payload:{progress:Infinity}})])],
    ['unpaired surrogate',page([event(1,{payload:{progress:'\ud800'}})])],
    ['malformed resync',page([event(1)],{resync:true})],
  ];
  it.each(malformed)('A3 rejects malformed %s before confirming any rows', async(_label,value)=>{
    const h=await mount(scripted([value]).transport);await expect(h.ready).rejects.toBeDefined();
    expect(ids(h.main)).toEqual([]);retry(h.main);expect(visibleText(h.main)).not.toContain('No ledger events yet.');
  });
  it.each([
    ['nonadvancing nonempty',page([event(4)],{head:9,next_after:4,has_more:true})],
    ['nonadvancing empty continuation',page([],{head:9,next_after:4,has_more:true})],
    ['regressing cursor',page([],{head:9,next_after:3,has_more:true})],
    ['event at exclusive boundary',page([event(4)],{head:9,next_after:8,has_more:true})],
    ['conflicting duplicate identity',page([event(6,{id:id(1)})],{head:9,next_after:6,has_more:true})],
    ['conflicting Lamport',page([event(1,{id:id(6)})],{head:9,next_after:6,has_more:true})],
    ['regressing head',page([event(5)],{head:5,next_after:5})],
    ['unsorted events',page([event(7),event(6)],{head:9,next_after:7,has_more:true})],
  ])('A4 rejects %s while retaining the confirmed page', async(_label,bad)=>{
    const t=scripted([page([event(1)],{head:9,next_after:4,has_more:true}),bad]);
    const h=await mount(t.transport,{},9);await h.ready;await click(h.main,'page-events');
    expect(ids(h.main)).toEqual([id(1)]);retry(h.main);expect(visibleText(h.main)).toMatch(/stale/i);
  });
  it('A4 identical observations on unchanged refresh do not duplicate identities', async()=>{
    const t=transport(()=>page([event(1)]));const h=await mount(t.transport);await h.ready;await h.update();await flush();
    expect(ids(h.main)).toEqual([id(1)]);expect(h.main.querySelector('[data-lin-action="retry-panel"]')).toBeNull();
  });
  it('A4 exhausted empty cursor at the acknowledged head is valid', async()=>{
    const t=scripted([page([],{head:8,next_after:8})]);const h=await mount(t.transport,{agent:ACTOR},8);await h.ready;
    expect(visibleText(h.main)).toContain('No matching events. Clear filters to see all loaded records.');
    expect(h.main.querySelector('[data-lin-action="retry-panel"]')).toBeNull();
  });
  it('A5 server filters restart at zero and selected unobserved actor remains available', async()=>{
    const t=transport(()=>page([],{head:7,next_after:7}));const h=await mount(t.transport,{agent:'unseen-agent'},7);await h.ready;
    expect(action<HTMLSelectElement>(h.main,'filter-ledger-agent').value).toBe('unseen-agent');
    assertRead(t.calls[0],0,{agent_id:'unseen-agent'});
    input(h.main,'filter-ledger-kind','run.beat');await flush();
    assertRead(reads(t.calls).at(-1)!,0,{agent_id:'unseen-agent',kinds:['run.beat']});
  });
  it.each(['operator','system'])('A5 reserved actor %s is a filter and never an asserted operator reader', async actor=>{
    const t=scripted([page([event(1,{agent:actor})])]);const h=await mount(t.transport,{agent:actor});await h.ready;
    assertRead(t.calls[0],0,{agent_id:actor});expect(t.calls[0].args.agent).not.toBe('operator');record(h.main,id(1));
  });
  it.each(['cHeCkPoInT','[a-z]+.*','javascript:payload','Checkpoint (1)'])('A5 local query %s is literal and does not restart or advance the server cursor', async q=>{
    const t=scripted([page([event(1,{payload:{run_id:'run_0001',agent_id:ACTOR,progress:q}}),event(2)],{head:9,next_after:5,has_more:true}),page([event(9)])]);
    const h=await mount(t.transport,{},9);await h.ready;input(h.main,'filter-ledger-query',q.toUpperCase());await flush();
    expect(t.calls).toHaveLength(1);expect(ids(h.main)).toContain(id(1));
    expect(visibleText(h.main)).toMatch(/partial|loaded|unscanned|incomplete/i);await click(h.main,'page-events');assertRead(t.calls[1],5);
  });
  it('A5 clear filters preserves prior revision while replacement read is pending', async()=>{
    const next=deferred<unknown>();const t=scripted([page([event(1)]),next.promise]);
    const h=await mount(t.transport,{q:'Checkpoint',agent:ACTOR,kind:'run.beat'});await h.ready;
    action(h.main,'clear-ledger-filters').click();await flush();expect(h.store.getState().head).toBe(1);
    assertRead(t.calls[1],0);expect(action<HTMLInputElement>(h.main,'filter-ledger-query').value).toBe('');
    next.resolve(page([event(1)]));await flush();
  });
  it('A6 continuation Retry keeps cursor, filters, selected identity and confirmed rows', async()=>{
    const t=scripted([page([event(1)],{head:8,next_after:5,has_more:true}),networkError(),page([event(8)])]);
    const query={q:'Checkpoint',agent:ACTOR,kind:'run.beat',event:id(1)};
    const h=await mount(t.transport,query,8);await h.ready;
    const hash=action(record(h.main,id(1)),'toggle-event-hash');hash.click();hash.focus();await click(h.main,'page-events');
    expect(ids(h.main)).toEqual([id(1)]);expect(visibleText(h.main)).toMatch(/stale/i);retry(h.main).click();await flush();
    expect(t.calls[2].args).toEqual(t.calls[1].args);assertRead(t.calls[2],5,{agent_id:ACTOR,kinds:['run.beat']});
    expect(ids(h.main)).toEqual([id(1),id(8)]);expect(action<HTMLInputElement>(h.main,'filter-ledger-query').value).toBe(query.q);
    expect(action(record(h.main,id(1)),'toggle-event-hash').getAttribute('aria-expanded')).toBe('true');
  });
  it('A7 resync is explicit, preserves filters and replaces rather than appends history', async()=>{
    const t=scripted([page([event(5)],{head:10,next_after:7,has_more:true}),
      page([],{head:2,next_after:0,resync:true}),page([event(2)])]);
    const query={q:'Checkpoint',agent:ACTOR,kind:'run.beat',event:id(5)};const h=await mount(t.transport,query,10);await h.ready;
    await click(h.main,'page-events');expect(t.calls).toHaveLength(2);
    expect(visibleText(h.main)).toContain('Ledger changed. Resync required; filters kept.');expect(ids(h.main)).toEqual([id(5)]);
    expect(visibleText(h.main)).toMatch(/stale/i);h.acknowledge(2,[event(2)]);
    await click(h.main,'resync-ledger');assertRead(t.calls[2],0,{agent_id:ACTOR,kinds:['run.beat']});
    expect(ids(h.main)).toEqual([id(2)]);expect(h.store.getState().selection.ledger).not.toBe(id(5));
    expect(action<HTMLInputElement>(h.main,'filter-ledger-query').value).toBe(query.q);
  });
  it('A7 failed resync replacement retains stale rows, warning and a recovery action', async()=>{
    const t=scripted([page([event(5)],{head:10,next_after:7,has_more:true}),page([],{head:2,next_after:0,resync:true}),networkError()]);
    const h=await mount(t.transport,{},10);await h.ready;await click(h.main,'page-events');await click(h.main,'resync-ledger');
    expect(ids(h.main)).toEqual([id(5)]);expect(visibleText(h.main)).toContain('Ledger changed. Resync required; filters kept.');
    expect(h.main.querySelector('[data-lin-action="resync-ledger"],[data-lin-action="retry-panel"]')).not.toBeNull();expect(t.calls).toHaveLength(3);
  });
  it('A8 duplicate page activation serializes one dispatch and exposes pending reason', async()=>{
    const pending=deferred<unknown>();const t=scripted([page([event(1)],{head:2,has_more:true}),pending.promise]);
    const h=await mount(t.transport,{},2);await h.ready;const button=action<HTMLButtonElement>(h.main,'page-events');button.click();button.click();await flush();
    expect(t.calls).toHaveLength(2);expect(button.disabled).toBe(true);expect(visibleText(h.main)).toMatch(/loading|pending|busy/i);
    pending.resolve(page([event(2)]));await flush();expect(ids(h.main)).toEqual([id(1),id(2)]);
  });
  it('A8 old-filter page cannot restore another query even when it ignores cancellation', async()=>{
    const late=deferred<unknown>();const t=scripted([page([event(1)],{head:2,has_more:true}),late.promise,page([event(2)])]);
    const h=await mount(t.transport,{},2);await h.ready;await click(h.main,'page-events');
    await h.update({agent:ACTOR});await flush();expect(ids(h.main)).toEqual([id(2)]);const before=h.announcements.mock.calls.length;
    late.resolve(page([event(2,{id:id(99)})]));await flush();
    expect(ids(h.main)).toEqual([id(2)]);expect(h.announcements.mock.calls).toHaveLength(before);
    expect(t.calls[1].options.signal?.aborted).toBe(true);
  });
  it('A8 disposed lookup cannot change DOM, focus, revision or announcements', async()=>{
    const pending=deferred<unknown>();const t=scripted([page([event(1)],{head:2,has_more:true}),pending.promise]);
    const h=await mount(t.transport,{event:id(2)},2);await flush();record(h.main,id(1));
    if(t.calls.length===1) await click(h.main,'page-events');h.dispose();const text=h.main.textContent;const count=h.announcements.mock.calls.length;
    const rev=document.documentElement.getAttribute('data-lin-rev');pending.resolve(page([event(2)]));await flush();
    expect(h.main.textContent).toBe(text);expect(h.announcements.mock.calls).toHaveLength(count);
    expect(document.documentElement.getAttribute('data-lin-rev')).toBe(rev);expect(h.store.dispose).not.toHaveBeenCalled();
  });
  it('A19 pending page leaves filters and cancellation usable instead of draining the bank', async()=>{
    const pending=deferred<unknown>();const t=scripted([page([event(1)],{head:10000,next_after:100,has_more:true}),pending.promise,page([],{head:10000,next_after:10000})]);
    const h=await mount(t.transport,{},10000);await h.ready;await click(h.main,'page-events');
    input(h.main,'filter-ledger-query','literal');await flush();expect(t.calls).toHaveLength(2);
    await h.update({q:'literal',agent:ACTOR});await flush();expect(t.calls).toHaveLength(3);
    expect(t.calls[1].options.signal?.aborted).toBe(true);pending.resolve(page([event(101)],{head:10000,next_after:200,has_more:true}));await flush();
    expect(ids(h.main)).not.toContain(id(101));
  });
});

// Separate one bounded assertion per page; no test synchronously renders the entire bank.
// The ordered session is shared only within this describe, and is disposed after the final page.
describe('A19 deterministic full-bank traversal',()=>{
  const t=bank();let h:Harness;
  beforeAll(async()=>{
    document.body.replaceChildren();vi.stubGlobal('fetch',vi.fn(()=>{throw Error('Oracle forbids network');}));
    h=await mount(t.transport,{},10000);await h.ready;
  });
  afterAll(()=>{h?.dispose();vi.unstubAllGlobals();});
  it.each(Array.from({length:100},(_,n)=>n))('A19 page %i adds exactly one cursor response without loss or duplication', async n=>{
    if(n>0) await click(h.main,'page-events');
    expect(t.calls).toHaveLength(n+1);assertRead(t.calls[n],n*100);
    expect(t.generated()).toBe((n+1)*100);
    const loaded=ids(h.main);expect(loaded).toEqual(Array.from({length:(n+1)*100},(_,i)=>id(i+1)));
    if(n===99) expect(h.main.querySelector('[data-lin-action="page-events"]:not(:disabled)')).toBeNull();
  });
});
