// @vitest-environment jsdom
import { it, expect, vi } from 'vitest';
import { TransportError } from '../../src/transport.ts';
import {
  ACTOR, HASH, action, click, deferred, domainError, event, exportResult, flush,
  httpTransport, id, ids, isolate, mount, nameOf, networkError, openExport, page,
  record, retry, submitExport, transport, verifyResult, visibleText,
} from './fixtures.ts';
isolate();
const ledgerThen=(result:unknown)=>transport(tool=>tool==='ledger_events'?page([event(1)]):result);

it('A11 begins Not verified and reports only the validated verification head and digest', async()=>{
  const t=ledgerThen(verifyResult());const h=await mount(t.transport,{agent:ACTOR});await h.ready;
  expect(visibleText(h.main)).toContain('Not verified');await click(h.main,'verify-ledger');
  const call=t.calls.find(c=>c.tool==='ledger_verify')!;expect(call).toBeDefined();
  expect(call.args===undefined?null:Object.keys(call.args).filter(k=>k!=='agent')).toEqual([]);
  if(call.args.agent!==undefined) expect(call.args.agent).toBe('system');expect(call.options.mutation).toBe(false);
  expect(call.options.signal).toBeInstanceOf(AbortSignal);expect(visibleText(h.main)).toContain(HASH);
  expect(visibleText(h.main)).toMatch(/verif[\s\S]*head\D*1\b/i);
});
it('A11 verification warnings preserve torn tail, projection drift and unknown line', async()=>{
  const t=ledgerThen(verifyResult({torn_tail_bytes:17,issues:[
    {path:'ledger/main/events.jsonl',line:null,code:'torn_tail',detail:'Uncommitted suffix ignored'},
    {path:'agents/aurora-root.json',line:null,code:'projection_drift',detail:'Projection diagnostic'},
  ]}));const h=await mount(t.transport);await h.ready;await click(h.main,'verify-ledger');
  const text=visibleText(h.main);expect(text).toContain('17');expect(text).toContain('torn_tail');
  expect(text).toContain('projection_drift');expect(text).toContain('Uncommitted suffix ignored');
  expect(text).not.toMatch(/line\s*[:=]?\s*0\b/i);expect(text).toContain(HASH);
});
it('A11 null verification digest is unknown and never fabricated', async()=>{
  // A-U26: use empty history at head zero so the cursor and integrated AppStore snapshot agree.
  const t=transport(tool=>tool==='ledger_events'?page():verifyResult({head:0,sha256:null}));
  const h=await mount(t.transport,{},0);await h.ready;
  await click(h.main,'verify-ledger');expect(visibleText(h.main)).toMatch(/head\D*0\b/i);
  expect(visibleText(h.main)).not.toContain('0'.repeat(64));
});
it('A11 newer page data retains an older verified head without certifying the new one', async()=>{
  let read=0;const t=transport(tool=>tool==='ledger_verify'?verifyResult({head:2}):
    read++===0?page([event(1)],{head:2,has_more:true}):page([event(2),event(3)]),
    {events:vi.fn(async()=>page([event(1),event(2),event(3)]))});
  const h=await mount(t.transport,{},2);await h.ready;await click(h.main,'verify-ledger');await click(h.main,'page-events');
  expect(ids(h.main)).toEqual([id(1),id(2),id(3)]);expect(visibleText(h.main)).toMatch(/verif[\s\S]*head\D*2\b/i);
  expect(visibleText(h.main)).not.toMatch(/verified\s+(?:at\s+)?head\D*3\b/i);
});
it.each(['hash_mismatch','internal','busy','bad_args'])('A11 verification refusal %s remains failure and has a named retry', async code=>{
  const t=transport(tool=>{if(tool==='ledger_events') return page([event(1)]);throw domainError(code);});
  const h=await mount(t.transport);await h.ready;await click(h.main,'verify-ledger');
  expect(visibleText(h.main)).toContain(code);retry(h.main,'Verification');record(h.main,id(1));
  expect(h.announcements.mock.calls.some(c=>/verif.*success|chain.*valid/i.test(String(c[1])))).toBe(false);
});
it.each([
  ['valid false',verifyResult({valid:false})],['extra key',verifyResult({extra:true})],
  ['unsafe head',verifyResult({head:Number.MAX_SAFE_INTEGER+1})],['null head',verifyResult({head:null})],
  ['bad digest',verifyResult({sha256:'ABC'})],['boolean torn bytes',verifyResult({torn_tail_bytes:true})],
  ['extra issue key',verifyResult({issues:[{path:'ledger/main/events.jsonl',line:1,code:'torn_tail',detail:'Warning',extra:true}]})],
  ['unknown issue code',verifyResult({issues:[{path:'ledger/main/events.jsonl',line:1,code:'invented',detail:'Warning'}]})],
  ['unsafe issue path',verifyResult({issues:[{path:'../outside',line:1,code:'bad_args',detail:'Warning'}]})],
])('A11 rejects malformed verification %s without producing certification', async(_label,result)=>{
  const h=await mount(ledgerThen(result).transport);await h.ready;await click(h.main,'verify-ledger');retry(h.main,'Verification');
  expect(visibleText(h.main)).toMatch(/invalid_response|invalid response|unavailable/i);
});
it('A8 A11 double verify dispatches once, is visibly pending and ignores late disposal', async()=>{
  const pending=deferred<unknown>();const t=ledgerThen(pending.promise);const h=await mount(t.transport);await h.ready;
  const verify=action<HTMLButtonElement>(h.main,'verify-ledger');verify.click();verify.click();await flush();
  expect(t.calls.filter(c=>c.tool==='ledger_verify')).toHaveLength(1);expect(verify.disabled).toBe(true);
  expect(visibleText(h.main)).toMatch(/verification.*(?:pending|busy)|verifying/i);
  h.dispose();const text=h.main.textContent;const count=h.announcements.mock.calls.length;
  pending.resolve(verifyResult());await flush();expect(h.main.textContent).toBe(text);expect(h.announcements.mock.calls).toHaveLength(count);
  expect(t.calls.find(c=>c.tool==='ledger_verify')!.options.signal?.aborted).toBe(true);
});
it('A11 Retry Verification retries only its panel and leaves the cursor untouched', async()=>{
  let attempts=0;const t=transport(tool=>{
    if(tool==='ledger_events') return page([event(1)]);
    if(attempts++===0) throw domainError('internal');return verifyResult();
  });const h=await mount(t.transport);await h.ready;await click(h.main,'verify-ledger');
  retry(h.main,'Verification').click();await flush();expect(t.calls.map(c=>c.tool)).toEqual(['ledger_events','ledger_verify','ledger_verify']);
  expect(visibleText(h.main)).toContain(HASH);
});
it('A12 protected export collects only out and displays the full-history result and manifest', async()=>{
  const t=ledgerThen(exportResult({head:41}));const h=await mount(t.transport,{q:'Checkpoint',agent:ACTOR,kind:'run.beat'});await h.ready;
  const {dialog,field}=await openExport(h.main);expect(nameOf(field)).toBe('Export Export directory');
  expect(visibleText(dialog)).toMatch(/relative.*(?:runtime )?home/i);expect(visibleText(dialog)).toContain('exports/');
  await submitExport(dialog,field);const call=t.calls.find(c=>c.tool==='ledger_export')!;expect(call).toBeDefined();
  const args={...call.args};if(args.agent==='system') delete args.agent;
  expect(args).toEqual({out:'exports/snapshot'});expect(call.options.mutation).toBe(true);expect(call.options.signal).toBeInstanceOf(AbortSignal);
  const text=visibleText(h.main);expect(text).toContain('exports/snapshot');expect(text).toContain('ledger/main/events.jsonl');
  expect(text).toContain(HASH);expect(text).toMatch(/head\D*41\b/i);
  expect(t.calls.filter(c=>c.tool==='ledger_events')).toHaveLength(1);
  expect(text).not.toMatch(/independently.*(?:audited|verified)|on.disk.*audited/i);
});
it.each(['cancel','escape'])('A12 export dismissal by %s dispatches nothing and restores its invoker', async how=>{
  const t=ledgerThen(exportResult());const h=await mount(t.transport);await h.ready;
  const {trigger,dialog}=await openExport(h.main);
  if(how==='cancel') action(dialog,'cancel-dialog').click();
  else dialog.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));
  await flush();expect(t.calls.some(c=>c.tool==='ledger_export')).toBe(false);
  expect(h.main.querySelector('dialog[open]')).toBeNull();expect(document.activeElement).toBe(trigger);
});
it.each(['exports','foo/bar','exports/','/exports/escape','exports/../escape','exports/./escape','exports//empty','exports\\escape','exports/a/','exports/a b'])
  ('A13 locally rejects destination %s without a protected dispatch', async destination=>{
    const t=ledgerThen(exportResult());const h=await mount(t.transport);await h.ready;
    const {dialog,field}=await openExport(h.main);await submitExport(dialog,field,destination);
    expect(t.calls.filter(c=>c.tool==='ledger_export')).toHaveLength(0);expect(field.value).toBe(destination);
    expect(document.activeElement).toBe(field);expect(field.getAttribute('aria-invalid')==='true'||!field.validity.valid).toBe(true);
    expect(visibleText(dialog)).toMatch(/exports\/|relative|directory|invalid/i);
  });
it.each([
  ['empty manifest',exportResult({manifest:[]})],['unsafe destination',exportResult({out:'../escape'})],
  ['bare exports destination',exportResult({out:'exports'})],['wrong root',exportResult({out:'foo/bar'})],
  ['trailing slash',exportResult({out:'exports/a/'})],['unsafe manifest path',exportResult({manifest:[{path:'../escape',sha256:HASH}]})],
  ['bad manifest hash',exportResult({manifest:[{path:'ledger/main/events.jsonl',sha256:'ABC'}]})],
  ['extra result key',exportResult({extra:true})],['boolean head',exportResult({head:true})],
  ['unsafe head',exportResult({head:Number.MAX_SAFE_INTEGER+1})],
  ['extra manifest key',exportResult({manifest:[{path:'ledger/main/events.jsonl',sha256:HASH,extra:true}]})],
])('A13 rejects malformed export %s and preserves the draft without claiming success', async(_label,result)=>{
  const t=ledgerThen(result);const h=await mount(t.transport);await h.ready;
  const {dialog,field}=await openExport(h.main);await submitExport(dialog,field);await flush();
  expect(visibleText(h.main)).toMatch(/invalid_response|invalid response|unavailable|refused/i);
  const liveField=h.main.querySelector<HTMLInputElement>('[name="out"]');
  if(liveField) expect(liveField.value).toBe('exports/snapshot');else expect((await openExport(h.main)).field.value).toBe('exports/snapshot');
  expect(t.calls.filter(c=>c.tool==='ledger_export')).toHaveLength(1);
});
it.each([
  ['bad_args','Symlink component refused','domain'],['internal','Projection I/O failed','domain'],
  ['hash_mismatch','Journal changed','domain'],['session_required','Session unavailable','transport'],
  ['network','Response lost after submission','transport'],
])('A13 export %s refusal or uncertainty keeps draft and never automatically replays', async(code,detail,source)=>{
  const t=transport(tool=>{
    if(tool==='ledger_events') return page([event(1)]);
    if(source==='domain') throw domainError(code,detail);throw new TransportError('transport',code,detail);
  });const h=await mount(t.transport);await h.ready;
  const {dialog,field}=await openExport(h.main);await submitExport(dialog,field);await flush();await flush();
  expect(visibleText(h.main)).toContain(code);expect(t.calls.filter(c=>c.tool==='ledger_export')).toHaveLength(1);
  expect(h.main.querySelector<HTMLInputElement>('[name="out"]')?.value).toBe('exports/snapshot');
  expect(visibleText(h.main)).not.toMatch(/export\s+(?:completed|successful|recorded)/i);
  expect(h.announcements.mock.calls.some(c=>/export.*(?:success|recorded)/i.test(String(c[1])))).toBe(false);
});
it('A13 backend confinement refusal detail is escaped and retained verbatim', async()=>{
  const detail='Symlink refused <img src=x onerror=alert(1)> & <script>ignored</script>';
  const t=transport(tool=>{if(tool==='ledger_events') return page([event(1)]);throw domainError('bad_args',detail);});
  const h=await mount(t.transport);await h.ready;const {dialog,field}=await openExport(h.main);await submitExport(dialog,field);
  expect(visibleText(h.main)).toContain(detail);expect(h.main.querySelector('img,script')).toBeNull();expect(field.value).toBe('exports/snapshot');
});
it('A12 A13 duplicate export confirmation serializes one protected dispatch', async()=>{
  const pending=deferred<unknown>();const t=ledgerThen(pending.promise);const h=await mount(t.transport);await h.ready;
  const {dialog,field}=await openExport(h.main);field.value='exports/snapshot';field.dispatchEvent(new Event('input',{bubbles:true}));
  const submit=action<HTMLButtonElement>(dialog,'submit-dialog');submit.click();submit.click();await flush();
  expect(t.calls.filter(c=>c.tool==='ledger_export')).toHaveLength(1);expect(submit.disabled).toBe(true);
  expect(visibleText(h.main)).toContain('Export ledger pending.');pending.resolve(exportResult());await flush();
});
it.each(['ledger_verify','ledger_export'])('A14 actual transport preserves HTTP-success domain refusal for %s', async tool=>{
  const wire=httpTransport(name=>name==='ledger_events'?{untrusted:page([event(1)])}:{ok:false,code:'hash_mismatch',detail:'Synthetic hash refusal'});
  const h=await mount(wire.transport);await h.ready;
  if(tool==='ledger_verify') await click(h.main,'verify-ledger');else {const {dialog,field}=await openExport(h.main);await submitExport(dialog,field);}
  expect(visibleText(h.main)).toContain('hash_mismatch');record(h.main,id(1));
  expect(visibleText(h.main)).not.toContain('No ledger events yet.');
  const posts=wire.fetchImpl.mock.calls.filter(c=>String(c[0])==='/api/call');
  expect(posts.some(c=>JSON.parse(String(c[1]?.body)).tool===tool)).toBe(true);
});
it.each([
  ['nested untrusted',{untrusted:{untrusted:verifyResult()}}],
  ['ambiguous wrapper',{untrusted:verifyResult(),ok:false,code:'hash_mismatch'}],
  ['no wrapper',verifyResult()],
])('A14 actual transport/screen rejects %s without false verification', async(_label,wireReply)=>{
  const wire=httpTransport(tool=>tool==='ledger_events'?{untrusted:page([event(1)])}:wireReply);
  const h=await mount(wire.transport);await h.ready;await click(h.main,'verify-ledger');retry(h.main,'Verification');record(h.main,id(1));
});
it('A3 shared transport removes exactly the outer wrapper and leaves inner passive keys alone', async()=>{
  const inner={untrusted:'passive domain data'};const wire=httpTransport(()=>({untrusted:inner}));
  expect(await wire.transport.call('ledger_verify',{}, {mutation:false})).toEqual(inner);
});
it('A14 shared transport negative control preserves semantic failure source and code', async()=>{
  const wire=httpTransport(()=>({ok:false,code:'internal',detail:'Synthetic refusal'}));
  await expect(wire.transport.call('ledger_export',{out:'exports/snapshot'},{mutation:true})).rejects.toMatchObject({source:'domain',code:'internal',detail:'Synthetic refusal'});
});
it('A8 newer query invalidates an old verification result without publishing its digest', async()=>{
  const pending=deferred<unknown>();const t=transport(tool=>tool==='ledger_events'?page([event(1)]):pending.promise);
  const h=await mount(t.transport);await h.ready;await click(h.main,'verify-ledger');await h.update({agent:ACTOR});
  const count=h.announcements.mock.calls.length;pending.resolve(verifyResult({sha256:'d'.repeat(64)}));await flush();
  expect(visibleText(h.main)).not.toContain('d'.repeat(64));expect(h.announcements.mock.calls).toHaveLength(count);
});
it('A8 uncertain export result from an obsolete query cannot certify the replacement view', async()=>{
  const pending=deferred<unknown>();const t=transport(tool=>tool==='ledger_events'?page([event(1)]):pending.promise);
  const h=await mount(t.transport);await h.ready;const {dialog,field}=await openExport(h.main);await submitExport(dialog,field);
  await h.update({kind:'run.beat'});const count=h.announcements.mock.calls.length;
  pending.resolve(exportResult({out:'exports/obsolete-result'}));await flush();
  expect(visibleText(h.main)).not.toContain('exports/obsolete-result');expect(h.announcements.mock.calls).toHaveLength(count);
  expect(t.calls.filter(c=>c.tool==='ledger_export')).toHaveLength(1);
});
it('A12 shared HTTP export uses the protected session lane without fabricating journal identity', async()=>{
  const wire=httpTransport(tool=>({untrusted:tool==='ledger_events'?page([event(1)]):exportResult()}));
  const h=await mount(wire.transport);await h.ready;const {dialog,field}=await openExport(h.main);await submitExport(dialog,field);
  const posts=wire.fetchImpl.mock.calls.filter(c=>String(c[0])==='/api/call');
  const request=posts.find(c=>JSON.parse(String(c[1]?.body)).tool==='ledger_export');expect(request).toBeDefined();
  const headers=new Headers(request![1]?.headers);expect(headers.get('X-Lineage-Session')).toBe('synthetic-session');
  expect(headers.get('Content-Type')).toBe('application/json');
  const args=JSON.parse(String(request![1]?.body)).args;expect(args.out).toBe('exports/snapshot');
  expect(args).not.toHaveProperty('op_id');expect(args).not.toHaveProperty('expected_head');
});
