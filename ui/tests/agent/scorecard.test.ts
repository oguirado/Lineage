import {expect,it} from 'vitest';
import {group,OTHER,seat} from './fixtures.ts';
import {action,flush,isolate,mount,ready,Service} from './helpers.ts';
isolate();
it('A21 full seat effort/mode and every arm remain separate labelled rows',async()=>{
 const s=new Service();s.groups=[group({seat,memory_arm:'none',runs:5,successes:3,mean_cost_micro_usd:0,mean_duration_ms:0,unknown_costs:0}),group(),group({memory_arm:'inherited'}),group({seat:{...seat,effort:'high'}}),group({seat:{...seat,mode:'interactive'}})];
 const v=await mount(s,{panel:'scorecard'});await ready(v);const table=v.host.querySelector('table');expect(table,'Scorecard labelled table').not.toBeNull();expect(table!.getAttribute('aria-label')||table!.getAttribute('aria-labelledby')||table!.querySelector('caption')?.textContent).toBeTruthy();
 const rows=table!.querySelectorAll('tbody tr');expect(rows).toHaveLength(5);expect(table!.textContent).toMatch(/not measured/iu);const zeroRow=Array.from(rows).find(r=>r.textContent?.includes('none'));expect(zeroRow).toBeDefined();expect(Array.from(zeroRow!.querySelectorAll('td')).filter(c=>c.textContent?.trim()==='0').length).toBeGreaterThanOrEqual(2);for(const value of ['medium','high','headless','interactive','none','own','inherited'])expect(table!.textContent).toContain(value);
 expect(v.host.textContent).toContain(s.record.agent_version);expect(table!.textContent).not.toContain('current version only');
});
it('A21 full tuple and arm filters restore exactly without fabricated groups',async()=>{
 const s=new Service();s.groups=[group(),group({seat:{...seat,effort:'high'},memory_arm:'inherited'})];const selected=JSON.stringify({effort:'high',mode:'headless',model:seat.model});const v=await mount(s,{panel:'scorecard',seat:selected,arm:'inherited'});await ready(v);
 const f=action(v.host,'filter-scorecard-seat') as HTMLSelectElement;expect(JSON.parse(f.value)).toEqual({...seat,effort:'high'});expect((action(v.host,'filter-scorecard-arm') as HTMLSelectElement).value).toBe('inherited');expect(v.host.querySelectorAll('tbody tr')).toHaveLength(1);
});
it.each(['missing','NaN','unsafe','negative','wrong-owner','extra'])('A21 A36 %s score data is a named local error, never an unknown zero',async(which)=>{
 const s=new Service();s.overrides.set('scorecard_get',()=>{const g=group();if(which==='missing')delete (g as any).mean_cost_micro_usd;if(which==='NaN')g.mean_duration_ms=NaN;if(which==='unsafe')g.runs=Number.MAX_SAFE_INTEGER+1;if(which==='negative')g.unknown_costs=-1;if(which==='extra')(g as any).agent_version=OTHER;return {agent_id:which==='wrong-owner'?'foreign-agent':s.record.agent_id,groups:[g],head:s.head};});
 const v=await mount(s,{panel:'scorecard'});expect((await v.readiness).ok).toBe(true);expect(v.host.querySelector('[role="alert"]')).not.toBeNull();expect(v.host.textContent).toMatch(/Scorecard unavailable|invalid|schema|mismatch/iu);expect(v.host.querySelectorAll('tbody tr')).toHaveLength(0);
});
