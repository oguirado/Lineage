import {expect,it,vi} from 'vitest';
import {actions} from '../../src/ui/contracts.ts';
import {TransportError} from '../../src/transport.ts';
import {agent,badPaths,birth,canonical,constitution,event,evidence,H,OTHER,OWNER,RUN,unit,UNIT} from './fixtures.ts';
import {action,click,deferred,dialog,flush,installUnits,isolate,messages,mount,name,noSuccess,ready,record,refuse,Service} from './helpers.ts';
isolate();
it('A2 dispose aborts owned reads, removes subscriptions/dialogs and ignores late resolution',async()=>{
 const s=new Service(),wait=deferred();const v=await mount(s,{panel:'memory'});await ready(v);action(v.host,'open-unit',UNIT);s.overrides.set('memory_get',()=>wait.promise);await click(v.host,'open-unit',UNIT);const request=s.calls('memory_get').at(-1);v.mounted.dispose();const before=v.host.innerHTML,announced=messages(v).length;wait.resolve({unit:unit('lesson',{statement:'OBSOLETE BYTES'}),head:s.head});await flush();expect(v.host.innerHTML).toBe(before);expect(messages(v)).toHaveLength(announced);expect(request[2].signal.aborted).toBe(true);expect(v.listeners.size).toBe(0);expect(v.host.querySelector('dialog[open]')).toBeNull();
});
it('A9 untrusted memory markup and error details remain inert literal text',async()=>{
 const payload='<img src=x onerror="globalThis.injected=true"><script>injected=true</script>';const s=new Service();installUnits(s,[unit('lesson',{statement:payload})]);const v=await mount(s,{panel:'memory'});await ready(v);expect(v.host.textContent).toContain(payload);expect(v.host.querySelector('img,script')).toBeNull();expect((globalThis as any).injected).toBeUndefined();await click(v.host,'open-unit',UNIT);expect(dialog(v).textContent).toContain(payload);expect(dialog(v).querySelector('img,script')).toBeNull();expect(fetch).not.toHaveBeenCalled();
 for(const c of v.host.querySelectorAll('[data-lin-action]')){expect(c.closest('article')).toBeNull();expect(['BUTTON','A','INPUT','SELECT']).toContain(c.tagName);expect(actions.has(c.getAttribute('data-lin-action')!)).toBe(true);}
});
it('A9 hostile skill content and domain detail cannot create links or executable nodes',async()=>{
 const payload='<a href="data:text/plain,hostile">HOSTILE TEXT</a>';const s=new Service();s.overrides.set('skill_get',()=>({skill:{skill_id:'review-skill',sha256:H,retired:true,files:[{path:'SKILL.md',content:payload}]}}));const v=await mount(s,{panel:'skills'});await ready(v);await click(v.host,'open-skill','review-skill@'+H);expect(dialog(v).textContent).toContain(payload);expect(dialog(v).querySelector('a')).toBeNull();await click(v.host,'close-inspector');s.overrides.set('agent_brief',()=>refuse('internal',payload));await click(v.host,'view-brief');expect(v.host.textContent).toContain(payload);expect(v.host.querySelector('a[href="data:text/plain,hostile"]')).toBeNull();
});
it.each(['extra','bad-id','bad-pin','duplicate-pin','prototype','unpaired-surrogate'])('A36 hostile Agent %s renders a terminal named error without admitting domain data',async(which)=>{
 const s=new Service();s.overrides.set('agent_get',()=>{const a=agent();if(which==='extra')a.unknown=true;if(which==='bad-id')a.agent_id='x';if(which==='bad-pin')a.references[0].sha256='BAD';if(which==='duplicate-pin')a.references[1]=a.references[0];if(which==='prototype')Object.defineProperty(a,'__proto__',{value:{execute:'ignored'},enumerable:true});if(which==='unpaired-surrogate')a.display_name='\ud800';return {record:a};});const v=await mount(s);expect((await v.readiness).ok).toBe(true);expect(v.host.querySelector('[role="alert"]')).not.toBeNull();expect(v.host.textContent).toMatch(/invalid|schema|unavailable|mismatch/iu);expect(writesCount(v)).toBe(0);
});
function writesCount(v:any){return v.service.transport.call.mock.calls.filter((c:any[])=>c[2].mutation).length;}
it.each([{kind:'lesson',level:1},{kind:'ruling',level:2},{kind:'ruling',level:3}])('A36 level-one spoof %j never enters a usable memory fold',async(change)=>{
 const s=new Service();installUnits(s,[unit(change.kind,change)]);const v=await mount(s,{panel:'memory'});expect((await v.readiness).ok).toBe(true);expect(v.host.querySelector('[role="alert"]')).not.toBeNull();expect(v.host.textContent).toMatch(/invalid|unavailable|schema/iu);expect(v.host.querySelector('[data-lin-action="open-unit"]')).toBeNull();
});
it.each(badPaths)('A36 wire evidence path %s cannot enter an admitted memory view',async(path)=>{
 const s=new Service();installUnits(s,[unit('lesson',{receipts:[{path,sha256:H}]})]);const v=await mount(s,{panel:'memory'});expect((await v.readiness).ok).toBe(true);expect(v.host.querySelector('[role="alert"]')).not.toBeNull();expect(v.host.textContent).toMatch(/invalid|unavailable|schema/iu);expect(v.host.querySelector('a[href]')).toBeNull();
});
it.each(badPaths.filter(p=>!p.startsWith('ledger/')&&!p.startsWith('family/')))('A36 skill package traversal %s is refused as passive invalid data',async(path)=>{
 const s=new Service();s.overrides.set('skill_get',()=>({skill:{skill_id:'review-skill',sha256:H,retired:false,files:[{path,content:'UNSAFE PACKAGE CONTENT'}]}}));const v=await mount(s,{panel:'skills'});await ready(v);await click(v.host,'open-skill','review-skill@'+H);expect(v.host.textContent).not.toContain('UNSAFE PACKAGE CONTENT');expect(v.host.textContent).toMatch(/invalid|unavailable|path/iu);
});
it('A36 wrong memory_get identity is rejected without corrupting independent identity facts',async()=>{
 const s=new Service();s.overrides.set('memory_get',()=>({unit:unit('lesson',{id:'foreign-unit',statement:'WRONG UNIT BODY'}),head:s.head}));const v=await mount(s,{panel:'memory'});expect((await v.readiness).ok).toBe(true);expect(v.host.querySelector('[role="alert"]')).not.toBeNull();expect(s.calls('memory_get').length).toBeGreaterThan(0);expect(v.host.textContent).not.toContain('WRONG UNIT BODY');expect(v.host.textContent).toContain(OWNER);expect(v.host.textContent).toMatch(/invalid|unavailable|mismatch/iu);
});
it('A36 newer route abort prevents a reversed late response from announcing success',async()=>{
 const s=new Service(),wait=deferred();const v=await mount(s,{panel:'memory'});await ready(v);action(v.host,'open-unit',UNIT);s.overrides.set('memory_get',()=>wait.promise);const updating=v.mounted.update(v.context).catch(()=>{});await flush();v.controller.abort();const before=messages(v).length;wait.resolve({unit:unit('lesson',{statement:'ABORTED RESULT'}),head:s.head});await updating;await flush();expect(v.host.textContent).not.toContain('ABORTED RESULT');expect(messages(v)).toHaveLength(before);noSuccess(v);
});
it('A36 unsupported complete descriptor shape disables confirmation instead of accepting unknown leaves',async()=>{
 const s=new Service();const descriptor=s.descriptors.find(d=>d.name==='memory_put')!;descriptor.inputSchema={...descriptor.inputSchema,properties:{...(descriptor.inputSchema.properties as any),unsupported:{type:'object',properties:{opaque:{type:'string'}},required:['opaque'],additionalProperties:false}},required:[...(descriptor.inputSchema.required as any[]),'unsupported']};const v=await mount(s,{panel:'memory'});await ready(v);const b=action(v.host,'write-memory') as HTMLButtonElement;if(!b.disabled){await click(v.host,'write-memory');expect((action(dialog(v),'submit-dialog') as HTMLButtonElement).disabled).toBe(true);}expect(v.host.textContent).toMatch(/unsupported|shape|unavailable/iu);expect(writesCount(v)).toBe(0);
});
