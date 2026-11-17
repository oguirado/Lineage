import { it, expect, vi } from 'vitest';
import type { JsonObject } from '../../src/ui/contracts.ts';
import { DRAFT_KEY, agent, args, clone, creation, draft, hash, refs, seat, skill, workflows } from './fixtures.ts';
import { Service, action, boot, confirm, deferred, dialog, expectNoSuccess, failure, field, fill, fillCreate, flush, isolate, key, mount, name, openCreate, saved, seatDraft, viaHttp } from './helpers.ts';
isolate();

it('A12 A13 ordinary Create opens a named native modal and verifies both fixed reference pins', async () => {
  const h=await boot(),trigger=action(h.host,'create-agent');trigger.focus();const d=await openCreate(h);
  expect(document.activeElement).toBe(field(d,'agent_id'));
  for(const tool of ['reference_get','reference_verify']) expect(h.service.for(tool).map(c => c.args.ref_id).sort()).toEqual(['gold_s1','memory_v21']);
  for(const pin of refs()) expect(d.textContent).toContain(String(pin.sha256));
  expect(h.service.for('skill_list')).toHaveLength(1);expect(h.service.for('skill_list')[0].args.include_retired??false).toBe(false);
  expect(d.querySelector('textarea')).toBeNull();for(const pin of d.querySelectorAll<HTMLInputElement>('input[name="gold_s1"],input[name="memory_v21"]')) expect(pin.readOnly||pin.disabled).toBe(true);
  for(const c of h.service.calls) {expect(c.options.signal).toBeInstanceOf(AbortSignal);expect(c.options.mutation).toBe(false);}
});
it('A12 invalid submission focuses the first invalid field and keeps entered text', async () => {
  const h=await boot(),d=await openCreate(h);await fill(d,'display_name','Recover this name');
  const submit=action<HTMLButtonElement>(d,'submit-dialog');
  if(submit.form) submit.form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
  else submit.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
  await flush();
  expect(document.activeElement).toBe(field(d,'agent_id'));expect(field(d,'display_name').value).toBe('Recover this name');
  expect(field(d,'agent_id').getAttribute('aria-invalid')).toBe('true');expect(field(d,'agent_id').getAttribute('aria-describedby')).toBeTruthy();
  expect(h.service.mutations()).toHaveLength(0);
});
it('A13 A14 no model, effort, seat or overlay is guessed for a blank form', async () => {
  const h=await boot(),d=await openCreate(h);expect(field(d,'seat.model').value).toBe('');expect(field(d,'seat.effort').value).toBe('');
  expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);expect(saved().fields).toMatchObject({allowed_seats:[],skills:[]});
  expect(d.querySelector('[name="overlays"]')).toBeNull();expect(h.service.mutations()).toHaveLength(0);
});
const corruptReferences: [string,string,(value: JsonObject) => JsonObject][] = [
  ['wrong hash','reference_verify',v => ({...v,sha256:'0'.repeat(64)})],['wrong bytes','reference_verify',v => ({...v,bytes:65})],
  ['wrong ID','reference_verify',v => ({...v,ref_id:'memory_v21'})],['false validity','reference_verify',v => ({...v,valid:false})],
  ['missing validity','reference_verify',v => {delete v.valid;return v;}],['extra key','reference_verify',v => ({...v,extra:true})],
  ['unsafe bytes','reference_verify',v => ({...v,bytes:Number.MAX_SAFE_INTEGER+1})],['nested extra rule','reference_get',v => {const r=v.reference as JsonObject;r.rules=[{id:'rule',section:'section',text:'text',extra:true}];return v;}],
  ['wrong returned ID','reference_get',v => {const r=v.reference as JsonObject;r.id='memory_v21';return v;}],
];
it.each(corruptReferences)('A13 A28 %s reference preflight blocks mutation and preserves a retryable draft', async (_label,tool,corrupt) => {
  const service=new Service();service.overrides.set(tool,a => a.ref_id==='gold_s1'?corrupt(clone(service.reply(tool,a))):service.reply(tool,a));
  const h=await boot({service}),d=await openCreate(h);await fillCreate(d);expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);
  expect(action(d,'retry-panel','Retry References')).toBeDefined();expect(field(d,'display_name').value).toBe('New child');expect(service.mutations()).toHaveLength(0);
  service.overrides.delete(tool);action(d,'retry-panel','Retry References').click();await flush();expect(field(d,'display_name').value).toBe('New child');
  expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(false);
});
it('A13 missing reference exposes hash_mismatch and keeps fields during Retry References', async () => {
  const service=new Service();service.overrides.set('reference_get',() => {throw failure('hash_mismatch','domain');});const h=await boot({service}),d=await openCreate(h);
  await fill(d,'display_name','Keep me');expect(d.textContent).toContain('hash_mismatch');expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);
  service.overrides.delete('reference_get');action(d,'retry-panel','Retry References').click();await flush();expect(field(d,'display_name').value).toBe('Keep me');expect(service.mutations()).toHaveLength(0);
});
it('A14 explicit nonretired skill selection serializes a full package pin', async () => {
  const h=await boot(),d=await openCreate(h);await fillCreate(d);const pin=skill(),identity=`${pin.skill_id}@${pin.sha256}`;
  const wrapper=Array.from(d.querySelectorAll<HTMLElement>('[data-lin-entity="skill"]')).find(e => e.dataset.linId===identity);expect(wrapper).toBeDefined();
  const choice=action<HTMLInputElement>(wrapper!,'select-skill',`Pin skill ${key('skill',identity)}`);choice.click();await flush();
  await confirm(d);expect(h.service.for('agent_create')[0].args.skills).toEqual([pin]);expect(h.service.for('agent_create')[0].args.overlays).toBeUndefined();
});
it('A14 optional skill failure permits explicit empty skills with an explanation and isolated retry', async () => {
  const service=new Service();service.overrides.set('skill_list',() => {throw failure();});const h=await boot({service}),d=await openCreate(h);await fillCreate(d);
  expect(action(d,'retry-panel','Retry Skills')).toBeDefined();expect(d.textContent).toMatch(/empty|without skills|no skills/iu);
  await confirm(d);expect(service.for('agent_create')[0].args.skills).toEqual([]);expect(service.for('reference_get')).toHaveLength(2);
});
it('A14 recovered unresolved skill pins block submission when skill discovery fails', async () => {
  const stored=draft();(stored.fields as JsonObject).skills=[skill()];window.localStorage.setItem(DRAFT_KEY,JSON.stringify(stored));
  const service=new Service();service.overrides.set('skill_list',() => {throw failure();});const h=await boot({service}),d=await openCreate(h);
  expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);expect(d.textContent).toMatch(/skill/iu);expect(service.mutations()).toHaveLength(0);
});
it('A14 full seat tuples are unique; effort and mode remain separate, removal restores Add seats focus', async () => {
  const h=await boot(),d=await openCreate(h);await fillCreate(d);await seatDraft(d);expect((saved().fields as JsonObject).allowed_seats).toHaveLength(1);
  await seatDraft(d,'synthetic-model','high','headless');await seatDraft(d,'synthetic-model','medium','interactive');
  expect((saved().fields as JsonObject).allowed_seats).toHaveLength(3);
  const remove=Array.from(d.querySelectorAll<HTMLButtonElement>('[data-lin-action="remove-item"]'));expect(remove).toHaveLength(3);
  expect(new Set(remove.map(name)).size).toBe(3);remove[1].focus();remove[1].click();await flush();expect(document.activeElement).toBe(action(d,'add-item','Add seats'));
  expect((saved().fields as JsonObject).allowed_seats).toHaveLength(2);expect(h.service.mutations()).toHaveLength(0);
});
it.each([['','medium','headless'],['model','','headless'],['model','INVALID','headless'],['model','medium','wrong-mode']])('A14 incomplete seat %s / %s / %s is never admitted', async (model,effort,mode) => {
  const h=await boot(),d=await openCreate(h);await seatDraft(d,model,effort,mode);expect((saved().fields as JsonObject).allowed_seats).toEqual([]);
  expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);expect(h.service.mutations()).toHaveLength(0);
});
it('A14 seat collection rejects a seventeenth member without changing admitted tuples', async () => {
  const h=await boot(),d=await openCreate(h);for(let i=0;i<17;i++) await seatDraft(d,`synthetic-${i}`);
  expect((saved().fields as JsonObject).allowed_seats).toHaveLength(16);expect(d.textContent).toMatch(/16|limit|maximum/iu);expect(h.service.mutations()).toHaveLength(0);
});
it('A15 valid Unicode character boundaries serialize exact closed arguments and no browser-only keys', async () => {
  const h=await boot(),d=await openCreate(h);const waiting=deferred();h.service.overrides.set('agent_create',() => waiting.promise);
  await fillCreate(d,{agent_id:'a'+'b'.repeat(63),display_name:'🧬'.repeat(128),language:'語'.repeat(64)});await confirm(d);
  const call=h.service.for('agent_create')[0];expect(call.args.display_name).toBe('🧬'.repeat(128));expect(call.args.language).toBe('語'.repeat(64));
  expect(Object.keys(call.args).sort()).toEqual(['agent','agent_id','allowed_seats','display_name','expected_head','language','op_id','references','skills','workflow'].sort());
  expect(call.args.agent).toBe('acting-root');expect(call.args.expected_head).toBe(7);expect(String(call.args.op_id)).toMatch(/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/u);
  expect(call.options.mutation).toBe(true);expect(call.options.signal).toBeInstanceOf(AbortSignal);expect(call.args.references).toEqual(expect.arrayContaining(refs()));
  h.dispose();waiting.reject(failure('aborted'));await flush();
});
it.each(['operator','system','ab','A-root',' root','root ','../escape','javascript:attack','a'.repeat(65)])('A15 invalid or reserved new ID %s cannot dispatch or be silently trimmed', async id => {
  const h=await boot(),d=await openCreate(h);await fillCreate(d,{agent_id:id});expect(field(d,'agent_id').value).toBe(id);expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);
  expect(h.service.mutations()).toHaveLength(0);
});
it.each([['display_name','🧬'.repeat(129)],['language','語'.repeat(65)],['display_name',''],['language',''],['workflow','train']])('A15 invalid %s length or enum blocks dispatch', async (key,value) => {
  const h=await boot(),d=await openCreate(h);await fillCreate(d,{[key]:value});expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);expect(h.service.mutations()).toHaveLength(0);
});
it('A15 field labels, workflows and modes follow the exhaustive public registry', async () => {
  const h=await boot(),d=await openCreate(h);
  for(const [path,label] of Object.entries({agent_id:'Agent ID',display_name:'Display name',workflow:'Workflow',language:'Language','seat.model':'Seat model','seat.effort':'Seat effort','seat.mode':'Seat mode'})) {
    const el=field(d,path);expect(name(el)).toBe(`Create ${label}`);expect(el.labels?.length).toBeGreaterThan(0);
  }
  expect(Array.from((field(d,'workflow') as HTMLSelectElement).options).map(o => o.value).filter(Boolean).sort()).toEqual([...workflows].sort());
  expect(Array.from((field(d,'seat.mode') as HTMLSelectElement).options).map(o => o.value).filter(Boolean).sort()).toEqual(['headless','interactive']);
  for(const button of d.querySelectorAll('button')) expect(button.type).toBe(button.dataset.linAction==='submit-dialog'?'submit':'button');
});
it.each([['absent',null,false],['empty','',false],['disabled','acting-root',true]] as const)('A16 %s actor blocks Confirm and supplies no default actor', async (_label,actor,actorDisabled) => {
  const h=await boot({actor,actorDisabled}),d=await openCreate(h);await fillCreate(d);
  expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);expect(d.textContent).toContain('Choose an acting agent before creating.');expect(h.service.mutations()).toHaveLength(0);
});
it('A16 missing agent_create capability gives a textual reason and no protected dispatch', async () => {
  const service=new Service();service.tools=service.tools.filter(t => t.name!=='agent_create');const h=await boot({service}),d=await openCreate(h);await fillCreate(d);
  expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);expect(d.textContent).toMatch(/agent_create|capability|unavailable/iu);expect(service.mutations()).toHaveLength(0);
});
it('A16 unknown acknowledged head cannot become expected_head zero', async () => {
  const h=mount({head:null});await flush();const d=await openCreate(h);await fillCreate(d);expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);
  expect(h.service.mutations()).toHaveLength(0);
});
it('A16 actor changes are explicit and operator selection never invokes a privileged writer', async () => {
  const h=await boot(),d=await openCreate(h);await fillCreate(d);h.actor!.value='operator';h.actor!.dispatchEvent(new Event('change',{bubbles:true}));await flush();
  const button=action<HTMLButtonElement>(d,'submit-dialog');
  if(!button.disabled) {await confirm(d);expect(h.service.for('agent_create')[0].args.agent).toBe('operator');}
  else expect(d.textContent).toMatch(/actor|acting agent/iu);
  expect(h.service.mutations().every(c => c.tool==='agent_create')).toBe(true);
});
it('A17 pending Confirm cannot submit twice and a draft is durable before the call', async () => {
  const service=new Service(),pending=deferred();let durable: JsonObject|undefined;
  service.overrides.set('agent_create',() => {durable=saved();return pending.promise;});const h=await boot({service}),d=await openCreate(h);await fillCreate(d);
  const button=action<HTMLButtonElement>(d,'submit-dialog');button.click();button.click();await flush();expect(service.for('agent_create')).toHaveLength(1);
  expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);expect(d.textContent).toContain('Create agent pending.');expect(durable?.phase).toBe('pending');
  expect(durable?.unresolved).toEqual(service.for('agent_create')[0].args);pending.reject(failure());await flush();expectNoSuccess(h);
});
it.each(['bad_args','busy','bad_op','stale_rev','internal','conflict','hash_mismatch','seat_not_allowed','memory_debt','fixture_readonly'])('A24 authoritative %s is refused, escaped and clears only the unresolved attempt', async code => {
  const service=new Service();service.overrides.set('agent_create',() => {throw failure(code,'domain');});const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  expect(d.textContent).toContain(`Create agent refused: ${code}.`);expect(d.textContent).toContain('<img src=x onerror=attack()>');expect(d.querySelector('img,script')).toBeNull();
  expect(field(d,'display_name').value).toBe('New child');expect(saved().phase).toBe('refused');expect(saved().unresolved).toBeNull();expectNoSuccess(h);
  expect(service.for('agent_create')).toHaveLength(1);expect(h.host.querySelector('[data-lin-id="alpha-root"]')).not.toBeNull();
});
it.each(['network','timeout','invalid_response','http'])('A24 lost observation %s leaves one uncertain frozen attempt', async code => {
  const service=new Service();service.overrides.set('agent_create',() => {throw failure(code);});const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  expect(d.textContent).toContain(code);expect(d.textContent).toMatch(/uncertain|unverified/iu);expect(saved().phase).toBe('uncertain');expect(saved().unresolved).toEqual(service.for('agent_create')[0].args);
  expectNoSuccess(h);expect(service.for('agent_create')).toHaveLength(1);
});
it('A24 session_required blocks completion, preserves the draft and exposes its exact code', async () => {
  const service=new Service();service.overrides.set('agent_create',() => {throw failure('session_required');});const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  expect(d.textContent).toContain('session_required');expect(saved().fields).toMatchObject({agent_id:'new-child'});expectNoSuccess(h);expect(service.for('agent_create')).toHaveLength(1);
});
it('A21 matching read and birth witness are required before closing, clearing and refreshing', async () => {
  const service=new Service(),witness=deferred();service.overrides.set('ledger_events',() => witness.promise);const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  expectNoSuccess(h);expect(saved().unresolved).not.toBeNull();expect(d.isConnected).toBe(true);expect(service.for('agent_get').some(c => c.args.agent_id==='new-child')).toBe(true);
  service.overrides.delete('ledger_events');witness.resolve(service.reply('ledger_events',{after:0}));await flush();
  expect(h.announcements.filter(e => e.message===`Create agent recorded for ${key('agent','new-child')}.`)).toHaveLength(1);
  expect(window.localStorage.getItem(DRAFT_KEY)).toBeNull();expect(d.isConnected).toBe(false);expect(service.events).toHaveLength(1);
  expect(h.navigate).not.toHaveBeenCalledWith(expect.objectContaining({screen:'agent'}));expect(h.host.querySelector('[data-lin-id="new-child"]')).not.toBeNull();
  await h.refresh();expect(h.announcements.filter(e => e.message.startsWith('Create agent recorded for '))).toHaveLength(1);
});
it('A22 outer ok=false and launch acknowledgements never become a creation success', async () => {
  const service=new Service();service.overrides.set('agent_create',() => ({ok:false,code:'conflict',detail:'Passive refusal'}));const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  expectNoSuccess(h);expect(window.localStorage.getItem(DRAFT_KEY)).not.toBeNull();expect(d.textContent).toMatch(/conflict|invalid_response/iu);
});
it('A27 fixture form remains read-only with no cryptographic randomness or clock sampling', async () => {
  const service=new Service();service.mode='fixture';const randomUUID=vi.mocked(window.crypto.randomUUID),randomValues=vi.mocked(window.crypto.getRandomValues);const realNow=Date.now.bind(Date),productClock:string[]=[];const clock=vi.spyOn(Date,'now').mockImplementation(() => {const stack=new Error().stack??'';if(/\/src\//u.test(stack)&&!/node_modules/u.test(stack.split('\n').slice(2,3).join('')))productClock.push(stack);return realNow();}); // A-U22 (orchestrator): jsdom/vitest internals call Date.now; the MUST is about product code sampling the clock
  const h=await boot({service}),d=await openCreate(h);await fillCreate(d);expect(action<HTMLButtonElement>(d,'submit-dialog').disabled).toBe(true);
  expect(h.root.textContent).toContain('Synthetic fixtures. Changes are unavailable.');expect(randomUUID).not.toHaveBeenCalled();expect(randomValues).not.toHaveBeenCalled();expect(productClock).toEqual([]);void clock; // A-U22: only calls whose immediate caller is product source count
  expect(service.mutations()).toHaveLength(0);await expect(service.transport.call('agent_create',args(),{mutation:true})).rejects.toMatchObject({code:'fixture_readonly'});
});

it('A24 HTTP 200 outer refusal is decoded by real U21 transport and remains a domain refusal', async () => {
  const service=new Service();service.overrides.set('agent_create',() => {throw failure('conflict','domain','Passive exact refusal.');});const wire=viaHttp(service);
  const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  expect(d.textContent).toContain('Create agent refused: conflict.');expect(d.textContent).toContain('Passive exact refusal.');expect(saved().unresolved).toBeNull();expectNoSuccess(h);
  expect(wire.requests.some(r => r.path==='/api/call'&&JSON.parse(String(r.init.body)).tool==='agent_create')).toBe(true);
});
it('A16 missing HTTP session never sends a mutation POST and preserves the valid draft', async () => {
  const service=new Service(),wire=viaHttp(service,null);const h=await boot({service}),d=await openCreate(h);await fillCreate(d);
  const button=action<HTMLButtonElement>(d,'submit-dialog');if(!button.disabled) button.click();await flush();
  expect(wire.requests.filter(r => r.path==='/api/call'&&JSON.parse(String(r.init.body)).tool==='agent_create')).toHaveLength(0);
  expect(h.root.textContent).toMatch(/session|unavailable/iu);expect(window.localStorage.getItem(DRAFT_KEY)).not.toBeNull();expectNoSuccess(h);
});
it('A15 A28 actual HTTP creation uses exactly tool/args and shared session handling without forbidden headers', async () => {
  const service=new Service(),wire=viaHttp(service);const h=await boot({service}),d=await openCreate(h);await fillCreate(d);await confirm(d);
  const mutation=wire.requests.find(r => r.path==='/api/call'&&JSON.parse(String(r.init.body)).tool==='agent_create');expect(mutation).toBeDefined();
  const body=JSON.parse(String(mutation!.init.body));expect(Object.keys(body).sort()).toEqual(['args','tool']);const headers=new Headers(mutation!.init.headers);
  expect(headers.get('Content-Type')).toBe('application/json');expect(headers.get('X-Lineage-Session')).toBe('synthetic-session-value');expect(headers.has('Origin')).toBe(false);expect(headers.has('Host')).toBe(false);
  expect(wire.requests.every(r => !String(r.init.body??'').includes('synthetic-session-value'))).toBe(true);
  expect(window.localStorage.getItem(DRAFT_KEY)??'').not.toContain('synthetic-session-value');
});
it.each([
  {skills:[{...skill(),extra:true}]},{skills:[{skill_id:'../escape',sha256:hash,retired:false}]},{skills:[{...skill(),retired:'false'}]},
  {skills:[{...skill(),retired:false}],extra:true},
])('A14 A28 malformed skill catalogue %j is isolated and never pins unvalidated content', async result => {
  const service=new Service();service.overrides.set('skill_list',() => result);const h=await boot({service}),d=await openCreate(h);await fillCreate(d);
  expect(d.textContent).toContain('invalid_response');expect(action(d,'retry-panel','Retry Skills')).toBeDefined();
  expect(d.querySelectorAll('[data-lin-action="select-skill"]:not(:disabled)')).toHaveLength(0);expect(service.mutations()).toHaveLength(0);
});
