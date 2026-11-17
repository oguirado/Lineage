import {expect,it,vi} from 'vitest';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {agent,birth,constitution,descriptors,eid,event,H,OTHER,OWNER,repoRoot,schema,unit,UNIT} from './fixtures.ts';
import {action,click,deferred,flush,identityKey,isolate,messages,mount,name,ready,refuse,schemaCheck,Service} from './helpers.ts';
isolate();
it('A2 importing the public screen performs no DOM, network, storage or timer work',async()=>{
 vi.resetModules();const append=vi.spyOn(Node.prototype,'appendChild'),replace=vi.spyOn(Element.prototype,'replaceChildren'),storage=vi.spyOn(Storage.prototype,'setItem'),timer=vi.spyOn(globalThis,'setTimeout');
 const {screen}=await import('../../src/screens/agent/index.ts');expect(screen.id).toBe('agent');expect(screen.title).toBe('Agent');
 expect(append).not.toHaveBeenCalled();expect(replace).not.toHaveBeenCalled();expect(storage).not.toHaveBeenCalled();expect(timer).not.toHaveBeenCalled();expect(fetch).not.toHaveBeenCalled();
});
it('A3 persisted agent facts precede measurements and distinguish identical display names',async()=>{
 const s=new Service(),v=await mount(s);await ready(v);expect(s.calls('agent_get').length,'detail must read persisted identity').toBeGreaterThan(0);
 expect(v.host.querySelectorAll('h1')).toHaveLength(1);expect(v.host.querySelector('h1')?.textContent).toBe('Agent '+identityKey('agent',OWNER));
 for(const x of [OWNER,s.record.display_name,s.record.workflow,s.record.language,s.record.agent_version,s.record.status,H,OTHER])expect(v.host.textContent).toContain(x);
 s.record=agent({agent_id:'second-agent',agent_version:OTHER,display_name:s.record.display_name});s.ledger=[birth(s.record),event(2,'memory.put',{agent_id:'second-agent',unit:s.units[0]})];await v.update();
 expect(v.host.querySelector('h1')?.textContent).toBe('Agent second-agent');expect(v.host.textContent).toContain(OTHER);expect(v.host.querySelector('h1')?.textContent).not.toContain(OWNER);
});
it('A3 no_agent is an explicit fatal read, never a successful empty detail',async()=>{
 const s=new Service();s.overrides.set('agent_get',()=>refuse('no_agent'));const v=await mount(s);expect((await v.readiness).ok).toBe(true);expect(v.host.querySelector('[role="alert"]')).not.toBeNull();expect(v.host.textContent).toContain('no_agent');expect(v.context.route).toMatchObject({agentId:OWNER});
});
it('A4 ready remains pending until its coherent identity and active panel fold is rendered',async()=>{
 const gate=deferred(),s=new Service();s.overrides.set('agent_get',()=>gate.promise);const v=await mount(s);let settled=false;void v.readiness.then(()=>{settled=true;});await flush();expect(settled).toBe(false);expect(document.documentElement.dataset.linReady).toBe('false');
 gate.resolve({record:s.record});await flush();await ready(v);expect(v.host.textContent).toContain(constitution.trim());
});
it('A4 active initial panel failure renders a terminal alert and its named Retry',async()=>{
 const s=new Service();s.overrides.set('memory_history',()=>refuse('internal','Synthetic history unavailable'));const v=await mount(s,{panel:'memory'});expect((await v.readiness).ok).toBe(true);expect(v.host.querySelector('[role="alert"]')).not.toBeNull();expect(v.host.textContent).toContain('Memory unavailable. Retry to continue.');expect(name(action(v.host,'retry-panel'))).toBe('Retry Memory');
});
it('A4 late old-route identity cannot replace the new route fold',async()=>{
 const slow=deferred(),s=new Service();s.overrides.set('agent_get',args=>args.agent_id===OWNER?slow.promise:{record:s.record});const v=await mount(s);expect(s.calls('agent_get').length).toBeGreaterThan(0);s.record=agent({agent_id:'next-agent'});s.ledger=[birth(s.record)];
 const updating=v.update();await flush();slow.resolve({record:agent()});await updating;expect(v.host.querySelector('h1')?.textContent).toBe('Agent next-agent');expect(v.host.textContent).not.toContain('Agent '+OWNER);
});
it('A5 head brackets surround headless agent_get and agree with store head',async()=>{
 const s=new Service(),v=await mount(s);await ready(v);const calls=s.transport.call.mock.calls.map((x:any[])=>x[0]);const i=calls.indexOf('agent_get');expect(i).toBeGreaterThan(0);expect(calls.slice(0,i)).toContain('ledger_events');expect(calls.slice(i+1)).toContain('ledger_events');expect(v.host.textContent).toContain(constitution.trim());expect(document.documentElement.hasAttribute('data-lin-rev')).toBe(false);
});
it.each(['server','store'])('A5 %s advance preserves the previous fold as stale without spinning',async(which)=>{
 const s=new Service(),v=await mount(s,{panel:'scorecard'});await ready(v);action(v.host,'show-scorecard');const old=v.host.textContent;s.groups=[{...s.groups[0],runs:713}];
 if(which==='server')s.head+=1;else v.emit({head:s.head+1});await v.mounted.update(v.context).catch(()=>{});await flush();
 expect(v.host.textContent).toMatch(/stale|Resync/iu);expect(v.host.textContent).not.toContain('713');expect(vi.mocked(v.store.refresh).mock.calls.length).toBeLessThanOrEqual(1);expect(old).not.toBe('');
});
it('A5 initial head race permits at most one refresh then rejects unresolved readiness',async()=>{
 const s=new Service();s.overrides.set('ledger_events',args=>({...s.page(s.ledger,args),head:s.head+1}));const v=await mount(s);expect((await v.readiness).ok).toBe(false);expect(vi.mocked(v.store.refresh).mock.calls.length).toBeLessThanOrEqual(1);expect(s.calls('agent_get').length).toBeLessThanOrEqual(2);
});
it('A6 failed Memory refresh retains identity, old units and filters; Retry is panel-local',async()=>{
 const s=new Service(),v=await mount(s,{panel:'memory',kind:'lesson'});await ready(v);action(v.host,'filter-memory-kind');s.overrides.set('memory_history',()=>refuse('internal'));await v.mounted.update(v.context).catch(()=>{});await flush();
 expect(v.host.textContent).toContain(OWNER);expect(v.host.textContent).toContain(s.units[0].statement);expect(v.host.textContent).toContain('Memory unavailable. Retry to continue.');expect(v.host.textContent).toMatch(/stale/iu);
 expect(name(action(v.host,'retry-panel'))).toBe('Retry Memory');const before=s.calls('scorecard_get').length;s.overrides.delete('memory_history');await click(v.host,'retry-panel');expect(s.calls('scorecard_get')).toHaveLength(before);expect((action(v.host,'filter-memory-kind') as HTMLSelectElement).value).toBe('lesson');
});
it('A12 finds exact owner birth beyond first page with unfiltered ascending kind scan',async()=>{
 const s=new Service();s.record=agent({born:{op:'genesis',event_id:eid(102)}});s.head=102;s.ledger=[birth(agent({agent_id:'foreign-agent'})),birth(s.record,102)];const v=await mount(s);await ready(v);
 expect(v.host.textContent).toContain(constitution.trim());const scans=s.calls('ledger_events').filter((x:any[])=>x[1].kinds?.includes('agent.born'));expect(scans.length).toBeGreaterThanOrEqual(2);expect(scans[0][1].after??0).toBe(0);expect(scans.some((x:any[])=>x[1].after>=100)).toBe(true);for(const x of scans)expect(x[1]).not.toHaveProperty('agent_id');
 for(const pin of s.record.references)expect(v.host.textContent).toContain(pin.sha256);expect(v.host.textContent).toContain('I1');
});
it.each(['owner','digest','rule'])('A12 rejects %s provenance mismatch instead of displaying verified constitution',async(which)=>{
 const s=new Service();if(which==='owner')s.ledger[0]=birth(agent({agent_id:'foreign-agent'}));if(which==='digest')s.record.constitution_sha256=OTHER;if(which==='rule')s.overrides.set('reference_get',args=>({reference:{id:args.ref_id,sha256:args.ref_id==='gold_s1'?H:OTHER,bytes:100,rules:[]}}));
 const v=await mount(s);expect((await v.readiness).ok).toBe(true);expect(v.host.querySelector('[role="alert"]')).not.toBeNull();expect(v.host.textContent).toMatch(/mismatch|unavailable|missing|invalid/iu);expect(v.host.textContent).not.toMatch(/verified constitution/iu);
});
it('A12 separate reference verify preserves hash_mismatch as text',async()=>{
 const s=new Service();s.overrides.set('reference_verify',()=>refuse('hash_mismatch','Synthetic pin mismatch'));const v=await mount(s);await ready(v);
 const controls=Array.from(v.host.querySelectorAll<HTMLElement>('[data-lin-action="verify-reference"]'));expect(controls).toHaveLength(1);controls[0].click();await flush();expect(v.host.textContent).toContain('hash_mismatch');expect(s.calls('reference_verify')).toHaveLength(1);
});
it('A13 historical skill uses exact displayed pin and own brief preserves server bytes',async()=>{
 const s=new Service(),v=await mount(s,{panel:'skills'});await ready(v);await click(v.host,'open-skill','review-skill@'+H);expect(s.calls('skill_get').at(-1)[1]).toMatchObject({skill_id:'review-skill',sha256:H});expect(v.host.textContent).toContain('Synthetic skill content');await click(v.host,'close-inspector');await click(v.host,'view-brief');expect(s.calls('agent_brief').at(-1)[1]).toMatchObject({agent_id:OWNER,memory_arm:'own'});expect(v.host.textContent).toContain('SERVER BRIEF');expect(v.host.textContent).toContain(s.record.agent_version);
});
it('A13 wrong returned skill pin is rejected without blanking identity',async()=>{
 const s=new Service();s.overrides.set('skill_get',()=>({skill:{skill_id:'review-skill',sha256:OTHER,retired:false,files:[{path:'SKILL.md',content:'WRONG PIN CONTENT'}]}}));const v=await mount(s,{panel:'skills'});await ready(v);await click(v.host,'open-skill','review-skill@'+H);expect(v.host.textContent).not.toContain('WRONG PIN CONTENT');expect(v.host.textContent).toContain(OWNER);expect(v.host.textContent).toMatch(/mismatch|invalid|unavailable/iu);
});
it('A37 fixture records satisfy frozen closed schemas before feature assertions',()=>{
 schemaCheck(agent(),schema('agent.schema.json'));for(const kind of ['ruling','lesson','negative','workflow','episode','decision','open_item'])schemaCheck(unit(kind),schema('mem_unit.schema.json'));schemaCheck(birth(),schema('event.schema.json'));expect(descriptors).toHaveLength(25);expect(descriptors.every(d=>d.inputSchema.additionalProperties===false)).toBe(true);
});

it('A1 exact public entry exports screen and imports the local scoped stylesheet',async()=>{
 const module=await import('../../src/screens/agent/index.ts');expect(Object.keys(module)).toEqual(['screen']);expect(readFileSync(resolve(repoRoot,'ui/src/screens/agent/index.ts'),'utf8')).toMatch(/import\s+['"]\.\.\/\.\.\/\.\.\/styles\/agent\.css['"]/u);
});
it.each(['gold_s1','memory_v21'])('A12 reference %s read is independent of verification and preserves its displayed pin',async(refId)=>{
 const s=new Service(),v=await mount(s);await ready(v);const choice=action(v.host,'edit-field') as HTMLSelectElement;choice.value=refId;choice.dispatchEvent(new Event('change',{bubbles:true}));const button=Array.from(v.host.querySelectorAll<HTMLButtonElement>('[data-lin-action="get-reference"]')).find(e=>e.name===refId);expect(button,'read reference '+refId).toBeDefined();button!.click();await flush();expect(s.calls('reference_get').at(-1)[1]).toMatchObject({ref_id:refId});expect(v.host.textContent).toContain(refId==='gold_s1'?H:OTHER);expect(s.calls('reference_verify')).toHaveLength(0);
});
