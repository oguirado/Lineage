import {expect,it} from 'vitest';
import {agent,birth,canonical,cost,eid,event,evidence,H,hash,levels,OTHER,OWNER,RUN,unit,UNIT} from './fixtures.ts';
import {action,click,dialog,flush,installUnits,isolate,messages,mount,noSuccess,ready,record,refuse,Service,set,submit} from './helpers.ts';
isolate();
it('A14 inherited owner introduction survives a different event actor and paged duplicate events',async()=>{
 const s=new Service(),u=unit('lesson',{provenance:{origin:'inherited',actor:'source-agent',inherited_from:{agent_id:'source-agent',unit_id:'source-unit',unit_sha256:H}}});
 s.units=[u];s.head=102;s.history=[birth(s.record,1,[{unit:u,source_agent_id:'source-agent',source_unit_id:'source-unit',unit_sha256:H}]),event(102,'memory.put',{agent_id:OWNER,unit:u})];
 const v=await mount(s,{panel:'memory'});await ready(v);expect(record(v.host,UNIT).textContent).toContain(u.statement);
 const more=v.host.querySelector<HTMLElement>('[data-lin-action="page-memory"]');if(more){more.click();await flush();}
 const gets=s.calls('memory_get');expect(gets.length).toBeGreaterThan(0);for(const x of gets){expect(Object.keys(x[1]).filter(k=>k!=='agent').sort()).toEqual(['agent_id','unit_id']);expect(x[1].agent_id).toBe(OWNER);}
 expect(v.host.querySelectorAll('[data-lin-action="open-unit"]')).toHaveLength(1);expect(v.host.textContent).toContain('source-agent');
});
it('A15 memory_get current supersession and retirement override immutable history payloads',async()=>{
 const s=new Service(),old=unit('lesson',{status:'superseded',superseded_by:'unit-00002'}),replacement=unit('lesson',{id:'unit-00002',supersedes:[UNIT],status:'retired'});s.units=[old,replacement];
 s.history=[birth(s.record),event(2,'memory.put',{agent_id:OWNER,unit:unit()}),event(3,'memory.put',{agent_id:OWNER,unit:{...replacement,status:'active'}}),event(4,'memory.retire',{agent_id:OWNER,unit_id:replacement.id})];s.ledger=[...s.history];s.head=4;
 const v=await mount(s,{panel:'memory'});await ready(v);await click(v.host,'open-unit',UNIT);expect(v.host.textContent).toContain('superseded');expect(v.host.textContent).toContain(replacement.id);await click(v.host,'close-inspector');await click(v.host,'open-unit',replacement.id);expect(v.host.textContent).toContain('retired');expect(v.host.textContent).toContain(UNIT);await click(v.host,'close-inspector');await click(v.host,'memory-history');expect(v.host.textContent).toContain(eid(2));expect(v.host.textContent).toContain(s.history[1].sha256);
});
const pairs=[['ruling',1],['lesson',2],['lesson',3],['negative',2],['negative',3],['workflow',2],['episode',2],['episode',3],['decision',2],['open_item',2],['open_item',3]] as const;
it.each(pairs)('A16 inspect %s level %s with worded level, body and evidence',async(kind,level)=>{
 const s=new Service(),u=unit(kind,{level});installUnits(s,[u]);const v=await mount(s,{panel:'memory'});await ready(v);const r=record(v.host,UNIT);expect(r.textContent).toContain(levels[level]);expect(r.textContent).toMatch(/internal/iu);await click(v.host,'open-unit',UNIT);expect(v.host.textContent).toContain(u.statement);expect(v.host.textContent).toContain(evidence.path);expect(v.host.textContent).toContain(H);expect(v.host.textContent).toContain(OWNER);
 if(kind==='episode'||kind==='workflow')expect(v.host.textContent).toMatch(/not measured/iu);expect(v.host.querySelector('a[href="'+evidence.path+'"]')).toBeNull();
});
it.each(['draft','active','superseded','retired'])('A16 status %s and private metadata remain inspectable but never inheritable',async(status)=>{
 const s=new Service(),u=unit('lesson',{status,privacy:'private',...(status==='superseded'?{superseded_by:'unit-00002'}:{})});installUnits(s,[u]);const v=await mount(s,{panel:'memory'});await ready(v);expect(record(v.host,UNIT).textContent).toMatch(/Private/u);expect(record(v.host,UNIT).textContent).toContain('Not inheritable:');await click(v.host,'open-unit',UNIT);expect(v.host.textContent).toContain(status);
});
it.each(['lesson','negative','workflow'])('A17 admitted active receipt-backed %s is provisionally inheritable',async(kind)=>{
 const s=new Service();installUnits(s,[unit(kind)]);const v=await mount(s,{panel:'memory'});await ready(v);expect(record(v.host,UNIT).textContent).toMatch(/\bInheritable\b/u);await click(v.host,'derive-agent');set(dialog(v),'operation','distill');await flush();expect(dialog(v).textContent).toMatch(/provisional/iu);const choice=action(dialog(v),'select-unit',UNIT) as HTMLInputElement;expect(choice.disabled).toBe(false);
});
const exclusions=[['ruling',{}],['lesson',{level:3}],['episode',{}],['decision',{}],['open_item',{}],['lesson',{privacy:'private'}],['lesson',{status:'retired'}],['workflow',{body:{trigger_sig:'trigger',steps:['step'],stats:{runs:0,successes:0,mean_reward:null},status:'candidate'}}],['lesson',{scope:{workflow:'develop',language:'rust'}}]] as const;
it.each(exclusions)('A17 excluded %s %j has explicit reason and cannot be selected',async(kind,changes)=>{
 const s=new Service(),u=unit(kind,changes);installUnits(s,[u]);const v=await mount(s,{panel:'memory'});await ready(v);expect(record(v.host,UNIT).textContent).toContain('Not inheritable:');await click(v.host,'derive-agent');const d=dialog(v);const options=Array.from(d.querySelectorAll<HTMLInputElement>('[data-lin-action="select-unit"]')).filter(e=>e.closest('[data-lin-id]')?.getAttribute('data-lin-id')===UNIT);expect(options.every(e=>e.disabled)).toBe(true);if(u.privacy==='private')expect(d.textContent).not.toContain(u.statement);
});
it.each([{receipts:[]},{receipts:[{path:'evidence/synthetic.txt',sha256:'invalid'}]}])('A17 missing or invalid receipt evidence cannot enable selection: %j',async({receipts})=>{
 const s=new Service();installUnits(s,[unit('lesson',{receipts})]);const v=await mount(s,{panel:'memory'});expect((await v.readiness).ok).toBe(true);expect(v.host.querySelector('[role="alert"]')).not.toBeNull();expect(v.host.textContent).toMatch(/invalid|unavailable|Not inheritable:/iu);const choices=Array.from(v.host.querySelectorAll<HTMLInputElement>('[data-lin-action="select-unit"]'));expect(choices.every(e=>e.disabled)).toBe(true);
});
it('A18 filters apply only to loaded records, preserve search and report partial continuation',async()=>{
 const s=new Service();s.head=102;s.history=[birth(s.record),event(102,'memory.put',{agent_id:OWNER,unit:s.units[0]})];const v=await mount(s,{panel:'memory',kind:'lesson',level:'2',privacy:'internal',inheritable:'1'});await ready(v);const q=action(v.host,'filter-memory-query') as HTMLInputElement;q.value='Receipt';q.dispatchEvent(new Event('input',{bubbles:true}));expect(v.host.textContent).toMatch(/partial|loaded|more/iu);expect(v.host.textContent).not.toContain('No memory units yet.');const more=action(v.host,'page-memory');more.focus();await click(v.host,'page-memory');expect(q.value).toBe('Receipt');expect((action(v.host,'filter-memory-kind') as HTMLSelectElement).value).toBe('lesson');expect(s.calls('memory_history').some((x:any[])=>x[1].after>=100)).toBe(true);expect(v.host.textContent).toContain(s.units[0].statement);
});
it('A18 successful exhausted empty and local no-match use different messages',async()=>{
 const s=new Service();installUnits(s,[]);const v=await mount(s,{panel:'memory'});await ready(v);expect(v.host.textContent).toContain('No memory units yet.');installUnits(s,[unit()]);await v.update();const query=action(v.host,'filter-memory-query') as HTMLInputElement;query.value='absent term';query.dispatchEvent(new Event('input',{bubbles:true}));await flush();expect(v.host.textContent).toContain('No matching memory units. Clear filters to see all loaded records.');expect(v.host.textContent).not.toContain('No memory units yet.');
});
it('A18 resync is not empty memory and keeps public filters',async()=>{
 const s=new Service();s.overrides.set('memory_history',()=>({events:[],next_after:0,head:s.head,has_more:false,resync:true}));const v=await mount(s,{panel:'memory',kind:'lesson'});await v.readiness;expect(v.host.textContent).toContain('Ledger changed. Resync required; filters kept.');expect(v.host.textContent).not.toContain('No memory units yet.');expect((action(v.host,'filter-memory-kind') as HTMLSelectElement).value).toBe('lesson');
});
it('A19 local query routes exact server answer without private inspector text or URL query',async()=>{
 const s=new Service();installUnits(s,[unit('lesson',{privacy:'private',statement:'PRIVATE BODY SENTINEL'})]);const v=await mount(s,{panel:'memory'});await ready(v);await click(v.host,'open-unit',UNIT);expect(dialog(v).textContent).toContain('PRIVATE BODY SENTINEL');await click(v.host,'close-inspector');
 const q=action(v.host,'filter-memory-query') as HTMLInputElement;q.value='needle';q.dispatchEvent(new Event('input',{bubbles:true}));await click(v.host,'route-memory');const args=s.calls('memory_route').at(-1)[1];expect(args).toMatchObject({agent_id:OWNER,query:'needle'});expect(v.host.textContent).toContain('NOT IN MEMORY');const ds=v.host.querySelector('dialog[open]');if(ds)expect(ds.textContent).not.toContain('PRIVATE BODY SENTINEL');for(const [route] of v.navigate.mock.calls)expect(route.query).not.toHaveProperty('q');
});
it.each(['OK','bad_args','bad_op','hash_mismatch'])('A20 exact observed leaves survive authoritative bootcheck %s',async(result)=>{
 const s=new Service();if(result!=='OK')s.overrides.set('memory_bootcheck',()=>refuse(result,'E_BOOTCHECK synthetic observation mismatch'));const v=await mount(s,{panel:'memory'});await ready(v);await click(v.host,'bootcheck-memory');const d=dialog(v);
 const observed={agent_version:s.record.agent_version,memory_gen:1,head:s.head,entry_sha256:H};for(const [k,val] of Object.entries(observed))set(d,'observed.'+k,val);await submit(v);expect(s.calls('memory_bootcheck').at(-1)[1]).toMatchObject({agent_id:OWNER,observed});if(result==='OK')expect(v.host.textContent).toContain('OK');else{expect(v.host.textContent).toContain(result);expect(v.host.textContent).toContain('E_BOOTCHECK');expect((d.querySelector('[name="observed.entry_sha256"]') as HTMLInputElement).value).toBe(H);expect(v.host.textContent).not.toMatch(/passed.*OK/u);}expect(v.host.textContent).not.toContain('SKIP');
});
it('A20 incomplete observations never produce a fabricated successful bootcheck',async()=>{
 const v=await mount(new Service(),{panel:'memory'});await ready(v);await click(v.host,'bootcheck-memory');await submit(v);expect(v.service.calls('memory_bootcheck')).toHaveLength(0);expect(dialog(v).textContent).toMatch(/required|invalid|observation/iu);expect(dialog(v).querySelector('[role="alert"]')?.getAttribute('aria-label')).toMatch(/^Error:/);expect(v.host.textContent).not.toContain('SKIP');
});
