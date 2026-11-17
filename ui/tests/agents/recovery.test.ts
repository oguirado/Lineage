import { it, expect, vi } from 'vitest';
import type { JsonObject, LedgerEvent } from '../../src/ui/contracts.ts';
import { DRAFT_KEY, agent, args, clone, creation, draft, eventId, hash, page, seat, skill } from './fixtures.ts';
import { Service, action, boot, confirm, deferred, dialog, expectNoSuccess, failure, field, fill, fillCreate, flush, isolate, key, openCreate, saved, unresolvedControl } from './helpers.ts';
isolate();

it('A17 A19 A30 response loss after commit replays the identical actor, args and op_id once', async () => {
  const service=new Service();let lost=true;
  service.overrides.set('agent_create',a => {const result=service.reply('agent_create',a);if(lost) {lost=false;throw failure();}return result;});
  const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);const original=clone(service.for('agent_create')[0].args);
  expect(saved().unresolved).toEqual(original);expectNoSuccess(h);expect(service.events).toHaveLength(1);
  await confirm(d);expect(service.for('agent_create')).toHaveLength(2);expect(service.for('agent_create')[1].args).toEqual(original);
  expect(JSON.stringify(service.for('agent_create')[1].args)).toBe(JSON.stringify(original));expect(service.events).toHaveLength(1);
  expect(h.announcements.filter(e => e.message==='Create agent recorded for new-child.')).toHaveLength(1);expect(window.localStorage.getItem(DRAFT_KEY)).toBeNull();
});
it('A18 edited fields get a fresh identity while the frozen unresolved attempt stays retryable', async () => {
  const service=new Service();service.overrides.set('agent_create',() => {throw failure();});const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  const frozen=clone(saved().unresolved),oldOp=saved().op_id;await fill(d,'display_name','Edited child');await fill(d,'agent_id','second-child');
  expect(saved().op_id).not.toBe(oldOp);expect(saved().unresolved).toEqual(frozen);expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);
  expect(service.for('agent_create')).toHaveLength(1);service.overrides.delete('agent_create');unresolvedControl(d,'retry').click();await flush();
  expect(service.for('agent_create')[1].args).toEqual(frozen);expect(service.for('agent_create')[1].args.display_name).toBe('New child');
  expect(saved().fields).toMatchObject({agent_id:'second-child',display_name:'Edited child'});expect(saved().unresolved).toBeNull();
});
it('A18 actor change cannot rewrite a frozen attempt or dispatch edited fields before reconciliation', async () => {
  const service=new Service();service.overrides.set('agent_create',() => {throw failure();});const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  const frozen=clone(saved().unresolved);h.actor!.value='other-actor';h.actor!.dispatchEvent(new Event('change',{bubbles:true}));await flush();
  expect(saved().unresolved).toEqual(frozen);expect((saved().unresolved as JsonObject).agent).toBe('acting-root');expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);
  expect(service.for('agent_create')).toHaveLength(1);expect(unresolvedControl(d,'retry')).toBeDefined();
});
it('A18 abandon waits for a fresh complete negative birth scan and never mutates', async () => {
  const snapshot=args();window.localStorage.setItem(DRAFT_KEY,JSON.stringify(draft({phase:'uncertain',submitted:snapshot,unresolved:snapshot})));
  const service=new Service(),scan=deferred();service.overrides.set('ledger_events',() => scan.promise);const h=await boot({service}),d=await openCreate(h);
  unresolvedControl(d,'abandon').click();await flush();expect(saved().unresolved).toEqual(snapshot);expect(service.for('ledger_events').length).toBeGreaterThan(0);
  scan.resolve(page([],7));await flush();expect(saved().unresolved).toBeNull();expect(service.mutations()).toHaveLength(0);expectNoSuccess(h);
});
it('A18 abandon cannot erase an attempt when its fresh witness scan fails', async () => {
  const snapshot=args();window.localStorage.setItem(DRAFT_KEY,JSON.stringify(draft({phase:'uncertain',submitted:snapshot,unresolved:snapshot})));
  const service=new Service();service.overrides.set('ledger_events',() => {throw failure();});const h=await boot({service}),d=await openCreate(h);
  unresolvedControl(d,'abandon').click();await flush();expect(saved().unresolved).toEqual(snapshot);expectNoSuccess(h);expect(service.mutations()).toHaveLength(0);
});
it('A18 stale_rev clears unresolved and requires explicit refresh and re-confirmation of the new head', async () => {
  const service=new Service();service.overrides.set('agent_create',() => {throw failure('stale_rev','domain');});const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  expect(saved().phase).toBe('refused');expect(saved().unresolved).toBeNull();expect(h.store.refresh).not.toHaveBeenCalled();expect(service.for('agent_create')).toHaveLength(1);
  action(d,'cancel-dialog','Cancel Create agent').click();service.head=8;service.overrides.delete('agent_create');await h.refresh();
  const reopened=await openCreate(h);expect(service.for('agent_create')).toHaveLength(1);await confirm(reopened);
  expect(service.for('agent_create')[1].args.expected_head).toBe(8);expect(String(service.for('agent_create')[1].args.op_id)).toMatch(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/u);
});
it('A19 reload offers the saved uncertain draft but never submits until explicit retry', async () => {
  const service=new Service();service.overrides.set('agent_create',() => {throw failure();});const first=await boot({service}),d=await openCreate(first);await fillCreate(d);await confirm(d);
  const snapshot=clone(saved());first.dispose();first.root.remove();const second=await boot({service});expect(service.for('agent_create')).toHaveLength(1);
  const recovered=await openCreate(second);expect(field(recovered,'agent_id').value).toBe('new-child');expect(saved().op_id).toBe(snapshot.op_id);
  expect(saved().unresolved).toEqual(snapshot.unresolved);service.overrides.delete('agent_create');await confirm(recovered);
  expect(service.for('agent_create')[1].args).toEqual(snapshot.unresolved);
});
it('A19 reload converts pending into uncertain and preserves the exact operation snapshot', async () => {
  const snapshot=args();window.localStorage.setItem(DRAFT_KEY,JSON.stringify(draft({phase:'pending',submitted:snapshot,unresolved:snapshot})));
  const h=await boot();expect(h.service.mutations()).toHaveLength(0);const d=await openCreate(h);
  expect(saved().phase).toBe('uncertain');expect(saved().unresolved).toEqual(snapshot);expect(d.textContent).toMatch(/uncertain|unverified/iu);expectNoSuccess(h);
});
it.each(['cancel','escape','departure'])('A19 A26 %s after send keeps recovery identity and never asserts rollback', async close => {
  const service=new Service(),pending=deferred();service.overrides.set('agent_create',() => pending.promise);const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  const snapshot=clone(saved().unresolved);
  if(close==='cancel') action(d,'cancel-dialog').click();else if(close==='escape') d.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));else h.dispose();
  await flush();expect(saved().unresolved).toEqual(snapshot);expectNoSuccess(h);expect(h.root.textContent).not.toMatch(/rolled back|creation cancelled/iu);
  pending.reject(failure('aborted'));await flush();expect(saved().unresolved).toEqual(snapshot);
});
it('A20 persisted creation draft is a closed allowlist without token, response or authoritative projection', async () => {
  const h=await boot(),d=await openCreate(h);await fillCreate(d);const value=saved();
  expect(Object.keys(value).sort()).toEqual(['schema','fields','seat_draft','actor','op_id','phase','submitted','unresolved'].sort());
  expect(Object.keys(value.fields as JsonObject).sort()).toEqual(['agent_id','display_name','workflow','language','allowed_seats','references','skills'].sort());
  // A-U22: Canonicalize the expected Seat fixture keys like the actual keys; the closed allowlist is unchanged.
  expect(Object.keys(value.seat_draft as JsonObject).sort()).toEqual(['model','effort','mode'].sort());
  expect(JSON.stringify(value)).not.toMatch(/session|token|memory_body|agent_version|constitution_sha256|stack|raw_response/iu);
  expect(new TextEncoder().encode(JSON.stringify(value)).length).toBeLessThanOrEqual(1048576);
});
const invalidDrafts: [string,() => string][] = [
  ['malformed JSON',() => '{'],['wrong schema',() => JSON.stringify(draft({schema:'unknown/v0'}))],['extra token',() => JSON.stringify(draft({session_token:'synthetic-secret'}))],
  ['missing fields',() => {const v=draft();delete v.fields;return JSON.stringify(v);}],['wrong primitive',() => JSON.stringify(draft({actor:17}))],
  ['invalid phase',() => JSON.stringify(draft({phase:'recorded'}))],['invalid op_id',() => JSON.stringify(draft({op_id:'illegal space'}))],
  ['prototype at root',() => JSON.stringify(draft()).slice(0,-1)+',"__proto__":{"poisoned":true}}'],
  ['prototype in fields',() => {const v=draft();v.fields=JSON.parse('{"constructor":{"prototype":{"poisoned":true}}}');return JSON.stringify(v);}],
  ['extra snapshot key',() => JSON.stringify(draft({submitted:{...args(),session_token:'synthetic-secret'}}))],
  ['invalid snapshot actor',() => JSON.stringify(draft({unresolved:{...args(),agent:'../escape'}}))],
  ['oversize draft',() => {const v=draft();(v.fields as JsonObject).display_name='x'.repeat(1048576);return JSON.stringify(v);}],
  ['too many seats',() => {const v=draft();(v.fields as JsonObject).allowed_seats=Array.from({length:17},(_,i) => seat({model:`synthetic-${i}`}));return JSON.stringify(v);}],
  ['too many skills',() => {const v=draft();(v.fields as JsonObject).skills=Array.from({length:257},(_,i) => ({skill_id:`skill-${i}`,sha256:hash}));return JSON.stringify(v);}],
  ['invalid seat object',() => {const v=draft();(v.fields as JsonObject).allowed_seats=[{...seat(),extra:true}];return JSON.stringify(v);}],
  ['unknown skill pin key',() => {const v=draft();(v.fields as JsonObject).skills=[{...skill(),memory_body:'private'}];return JSON.stringify(v);}],
];
it.each(invalidDrafts)('A20 hostile stored %s cannot admit a mutation or poison objects', async (_label,make) => {
  window.localStorage.setItem(DRAFT_KEY,make());const h=await boot(),d=await openCreate(h);
  expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);expect(h.root.textContent).toMatch(/draft|recover/iu);
  expect(h.root.textContent).toMatch(/unavailable|invalid|corrupt|cannot|could not|discard/iu);expect(h.service.mutations()).toHaveLength(0);expect(({} as any).poisoned).toBeUndefined();
});
it.each(['getItem','setItem'])('A20 storage %s refusal is visible but in-session creation remains usable', async method => {
  vi.spyOn(Storage.prototype,method).mockImplementation(() => {throw new DOMException('Synthetic storage refusal','SecurityError');});
  const h=await boot(),d=await openCreate(h);expect(h.root.textContent).toMatch(/storage|reload|recovery/iu);await fillCreate(d);await confirm(d);
  expect(h.announcements.filter(e => e.message==='Create agent recorded for new-child.')).toHaveLength(1);
});
it('A20 incomplete editable draft text is recoverable without being a valid tool snapshot', async () => {
  const v=draft();(v.fields as JsonObject).agent_id='a';(v.fields as JsonObject).allowed_seats=[];window.localStorage.setItem(DRAFT_KEY,JSON.stringify(v));
  const h=await boot(),d=await openCreate(h);expect(field(d,'agent_id').value).toBe('a');expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);expect(h.service.mutations()).toHaveLength(0);
});
it('A21 witness beyond the default first page is reached from zero or the original committed prefix', async () => {
  const service=new Service();service.head=204;
  service.overrides.set('ledger_events',a => {
    const after=Number(a.after??0);expect(after).toBeLessThan(205);expect(a.agent_id).toBe('new-child');expect(a.kinds).toEqual(['agent.born']);
    if(after<200) return page([],205,Math.min(200,after+100),true);
    return page(service.events,205);
  });
  const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  const scans=service.for('ledger_events');expect(scans.length).toBeGreaterThan(0);expect([0,204]).toContain(Number(scans[0].args.after??0));
  if(Number(scans[0].args.after??0)===0) expect(scans.length).toBeGreaterThan(1);
  expect(h.announcements.filter(e => e.message==='Create agent recorded for new-child.')).toHaveLength(1);
});
const mismatches: [string,(record: JsonObject) => JsonObject][] = [
  ['child ID',r => ({...r,agent_id:'wrong-child'})],['display name',r => ({...r,display_name:'Wrong child'})],['workflow',r => ({...r,workflow:'review'})],
  ['language',r => ({...r,language:'wrong'})],['seats',r => ({...r,allowed_seats:[seat({effort:'high'})]})],['skills',r => ({...r,skills:[skill()]})],
  ['reference pins',r => ({...r,references:[{id:'gold_s1',sha256:hash},{id:'memory_v21',sha256:hash}]})],['version',r => ({...r,agent_version:'0'.repeat(64)})],
  ['parents',r => ({...r,parents:['wrong-parent']})],['origin',r => ({...r,born:{op:'clone',event_id:eventId(8)},parents:['parent-root'],generation:1})],
  ['extra projection field',r => ({...r,extra:'passive'})],
];
it.each(mismatches)('A22 Amendment B agent_get mismatch in %s leaves completion unverified', async (_label,change) => {
  const service=new Service();service.overrides.set('agent_get',a => ({record:change(clone(service.reply('agent_get',a).record as JsonObject))}));
  const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);expectNoSuccess(h);expect(saved().unresolved).not.toBeNull();
  expect(d.isConnected).toBe(true);expect(d.textContent).toMatch(/uncertain|unverified|invalid_response/iu);
});
it.each(mismatches)('A22 Amendment B event payload mismatch in %s cannot certify creation', async (_label,change) => {
  const service=new Service();service.overrides.set('ledger_events',() => {
    const event=clone(service.events[0]);event.payload.record=change(event.payload.record as JsonObject);return page([event],service.head);
  });
  const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);expectNoSuccess(h);expect(saved().unresolved).not.toBeNull();expect(d.isConnected).toBe(true);
});
it.each(['missing birth','wrong actor','wrong op_id','wrong event ID','wrong kind','extra event key','invalid evidence path'])('A22 %s leaves the sent attempt recoverable without claiming noncommit', async kind => {
  const service=new Service();service.overrides.set('ledger_events',() => {
    const event=clone(service.events[0]) as LedgerEvent & {extra?: boolean};
    if(kind==='missing birth') return page([],service.head);
    if(kind==='wrong actor') event.agent='other-actor';if(kind==='wrong op_id') event.op_id='other-operation';if(kind==='wrong event ID') event.id=eventId(99);
    if(kind==='wrong kind') event.kind='agent.status';if(kind==='extra event key') event.extra=true;
    if(kind==='invalid evidence path') event.evidence=[{path:'../escape',sha256:hash}];return page([event],service.head);
  });
  const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);expectNoSuccess(h);expect(saved().unresolved).not.toBeNull();
  expect(d.textContent).not.toMatch(/never committed|not committed|rolled back/iu);
});
it.each([
  {event_ids:[],head:8,sha256:hash},{event_ids:[eventId(8)],head:null,sha256:hash},{event_ids:[eventId(8)],head:8,sha256:'bad'},
  {event_ids:[eventId(8)],head:8,sha256:hash,extra:true},{event_ids:['../escape'],head:8,sha256:hash},
])('A22 malformed commit %j cannot be treated as completion', async commit => {
  const service=new Service();service.overrides.set('agent_create',a => ({record:creation(a).record,commit}));const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  expectNoSuccess(h);expect(saved().unresolved).not.toBeNull();expect(d.textContent).toContain('invalid_response');
});
it('A22 launch-style accepted receipt is not an agent_create result', async () => {
  const service=new Service();service.overrides.set('agent_create',() => ({status:'accepted',state:'launched'}));const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  expectNoSuccess(h);expect(saved().unresolved).not.toBeNull();expect(d.textContent).toContain('invalid_response');
});
it('A23 replay uses the original old commit prefix rather than the current expected head', async () => {
  const snapshot=args();const service=new Service();service.reply('agent_create',snapshot);service.head=30;
  window.localStorage.setItem(DRAFT_KEY,JSON.stringify(draft({phase:'uncertain',submitted:snapshot,unresolved:snapshot})));
  const h=await boot({service}),d=await openCreate(h);await confirm(d);const first=service.for('ledger_events')[0];
  expect(first).toBeDefined();expect([0,7]).toContain(Number(first.args.after??0));expect(first.args.after).not.toBe(30);expect(service.events).toHaveLength(1);
  expect(h.announcements.filter(e => e.message==='Create agent recorded for new-child.')).toHaveLength(1);
});
it('A23 repeated cursor resync stops observation, retains filters and never retries the mutation', async () => {
  const service=new Service();service.overrides.set('ledger_events',() => page([],8,0,false,true));const h=await boot({service,query:{q:'Shared',sort:'name-asc'}}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  expect(d.textContent).toContain('Ledger changed. Resync required; filters kept.');expectNoSuccess(h);expect(saved().unresolved).not.toBeNull();
  expect(service.for('ledger_events').length).toBeLessThanOrEqual(2);expect(service.for('agent_create')).toHaveLength(1);expect(h.context.route.query).toEqual({q:'Shared',sort:'name-asc'});
});
it('A26 stale reference preflight cannot render into a reopened dialog', async () => {
  const service=new Service(),old=deferred();let first=true;service.overrides.set('reference_get',a => {if(first&&a.ref_id==='gold_s1') {first=false;return old.promise;}return service.reply('reference_get',a);});
  const h=await boot({service}),d=await openCreate(h);await fill(d,'display_name','New session draft');action(d,'cancel-dialog').click();const next=await openCreate(h);
  old.resolve({reference:{id:'gold_s1',sha256:'0'.repeat(64),bytes:64,rules:[]}});await flush();expect(dialog()).toBe(next);
  expect(field(next,'display_name').value).toBe('New session draft');expect(next.textContent).not.toContain('0'.repeat(64));expectNoSuccess(h);
});
it('A26 late mutation observation after disposal cannot clear recovery or announce into another route', async () => {
  const service=new Service(),observation=deferred();service.overrides.set('agent_get',() => observation.promise);const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  const frozen=clone(saved().unresolved),announcements=h.announcements.length;h.dispose();h.host.replaceChildren(document.createTextNode('Other route'));
  observation.resolve({record:service.records.find(r => r.agent_id==='new-child')!});await flush();expect(h.host.textContent).toBe('Other route');
  expect(h.announcements).toHaveLength(announcements);expect(saved().unresolved).toEqual(frozen);expectNoSuccess(h);
});
