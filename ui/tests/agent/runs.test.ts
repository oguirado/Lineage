import {expect,it} from 'vitest';
import {TransportError} from '../../src/transport.ts';
import {badPaths,closed,cost,eid,event,evidence,H,opening,outcome,OWNER,RUN,seat,task,UNIT} from './fixtures.ts';
import {action,click,closeDraft,dialog,failureMemory,flush,isolate,messages,mount,noSuccess,ready,record,refuse,Service,set,submit,writes} from './helpers.ts';
isolate();
it('A22 owner payloads discover one run across open/beat/close pages without querying foreign runs',async()=>{
 const s=new Service(),opened=s.addRun(),foreign=opening({run_id:'foreign-run',agent_id:'foreign-agent'},4),run=closed();s.head=104;
 s.ledger.push(foreign,event(102,'run.beat',{run_id:RUN,agent_id:OWNER,progress:'Real target progress'}),event(103,'run.close',{record:run,memory_receipts:[evidence],gate:{passed:true,checks:[{id:'memory',passed:true}]}}));s.runs.set(RUN,{opened,closed:run});
 const v=await mount(s,{panel:'runs'});await ready(v);const more=v.host.querySelector<HTMLElement>('[data-lin-action="page-runs"]');if(more){more.click();await flush();}
 expect(v.host.querySelectorAll('[data-lin-action="open-run"]')).toHaveLength(1);await click(v.host,'open-run',RUN);for(const text of [RUN,run.agent_version,seat.model,'HOLD',evidence.path])expect(v.host.textContent).toContain(text);expect(v.host.textContent).toMatch(/not measured/iu);
 const scans=s.calls('ledger_events').filter((x:any[])=>x[1].kinds?.some((k:string)=>k.startsWith('run.')));expect(scans.length).toBeGreaterThan(0);expect(scans[0][1].after??0).toBe(0);for(const c of scans)expect(c[1]).not.toHaveProperty('agent_id');expect(s.calls('run_get').every((c:any[])=>c[1].run_id===RUN)).toBe(true);
});
it('A22 closed null remains open, run inspection differs from run start',async()=>{
 const s=new Service();s.addRun();const v=await mount(s,{panel:'runs'});await ready(v);expect(record(v.host,RUN).textContent).toMatch(/open/iu);expect(record(v.host,RUN).textContent).not.toMatch(/completed|closed/iu);await click(v.host,'open-run',RUN);expect(writes(v)).toHaveLength(0);expect(s.calls('run_get').length).toBeGreaterThan(0);await click(v.host,'close-inspector');expect(action(v.host,'open-run-form')).toBeInstanceOf(HTMLButtonElement);
});
it('A22 page-runs scans bounded 100-event cursor pages and labels foreign-only coverage partial',async()=>{
 const s=new Service();s.head=10000;s.ledger=[s.ledger[0],...Array.from({length:99},(_,i)=>opening({agent_id:'foreign-agent',run_id:'foreign-'+String(i).padStart(8,'0')},i+2))];const v=await mount(s,{panel:'runs'});await ready(v);expect(v.host.textContent).toMatch(/partial|loaded|more/iu);expect(v.host.textContent).not.toContain('No runs yet.');const runScans=()=>s.calls('ledger_events').filter((x:any[])=>x[1].kinds?.includes('run.open'));const before=runScans().length;await click(v.host,'page-runs');expect(runScans().length-before).toBe(1);expect(runScans().at(-1)[1].limit).toBe(100);expect(s.calls('run_get')).toHaveLength(0);
});
it('A22 successful exhausted owner scan alone establishes No runs yet',async()=>{
 const v=await mount(new Service(),{panel:'runs'});await ready(v);expect(v.host.textContent).toContain('No runs yet.');expect(v.service.calls('ledger_events').length).toBeGreaterThan(0);
});
it('A25 run start sends complete allowed seat, task, parents array and memory arm',async()=>{
 const s=new Service();s.overrides.set('run_open',args=>{const opened=opening({...args,agent_version:s.record.agent_version});const clean={run_id:args.run_id,agent_id:args.agent_id,agent_version:s.record.agent_version,seat:args.seat,task:args.task,parents_context:args.parents_context,memory_arm:args.memory_arm};const c=s.commit('run_open',args,clean,'run.open');s.runs.set(args.run_id,{opened:c.event,closed:null});return {opened:c.event,commit:c.commit};});
 const v=await mount(s,{panel:'runs'});await ready(v);await click(v.host,'open-run-form');const d=dialog(v);
 for(const [k,val] of Object.entries({run_id:RUN,'seat.model':seat.model,'seat.effort':seat.effort,'seat.mode':seat.mode,'task.id':task.id,'task.kind':task.kind,'task.language':task.language,memory_arm:'inherited'}))set(d,k,val);await submit(v);
 expect(writes(v,'run_open')).toHaveLength(1);const args=writes(v,'run_open')[0][1];expect(args).toMatchObject({run_id:RUN,agent_id:OWNER,agent:OWNER,seat,task,parents_context:[],memory_arm:'inherited',expected_head:2});expect(args).not.toHaveProperty('outcome');expect(args).not.toHaveProperty('ts_open');expect(s.calls('run_get').some((x:any[])=>x[1].run_id===RUN)).toBe(true);expect(messages(v)).toContain('Open run recorded for '+RUN+'.');
});
it('A25 each new heartbeat uses fresh identity, exact progress and witnessed read',async()=>{
 const s=new Service();s.addRun();s.overrides.set('run_beat',args=>{const c=s.commit('run_beat',args,{run_id:args.run_id,agent_id:OWNER,progress:args.progress},'run.beat');return {event:c.event,commit:c.commit};});const v=await mount(s,{panel:'runs'});await ready(v);
 await click(v.host,'heartbeat-run',RUN);await click(v.host,'heartbeat-run',RUN);const calls=writes(v,'run_beat');expect(calls).toHaveLength(2);for(const c of calls)expect(c[1]).toMatchObject({agent:OWNER,run_id:RUN,progress:'Heartbeat requested from Agent detail.'});expect(calls[0][1].op_id).not.toBe(calls[1][1].op_id);expect(s.calls('run_get').length).toBeGreaterThan(0);
});
it('A25 uncertain heartbeat retries the original request after a different run confirms',async()=>{
 const s=new Service();
 s.addRun();
 const otherRun='run-00000002';
 const opened=opening({run_id:otherRun},++s.head);
 s.ledger.push(opened);
 s.runs.set(otherRun,{opened,closed:null});
 const initialHead=s.head;
 const committed=new Map<string,ReturnType<Service['commit']>>();
 s.overrides.set('run_beat',args=>{
  const previous=committed.get(args.op_id);
  if(previous)return previous;
  expect(args.expected_head).toBe(s.head);
  const result=s.commit('run_beat',args,{run_id:args.run_id,agent_id:args.agent,progress:args.progress},'run.beat');
  committed.set(args.op_id,result);
  if(committed.size===1)throw new TransportError('transport','timeout','Heartbeat response was lost.');
  return result;
 });
 const v=await mount(s,{panel:'runs'});
 await ready(v);
 const requests=()=>writes(v,'run_beat').map(([,args])=>args);

 await click(v.host,'heartbeat-run',RUN);
 expect(requests()).toHaveLength(1);
 expect(v.host.textContent).toContain('Transport uncertainty. Retry replays the original operation.');
 noSuccess(v);
 const [first]=requests();
 expect(first).toMatchObject({agent:OWNER,run_id:RUN,progress:'Heartbeat requested from Agent detail.',expected_head:initialHead});

 await v.store.refresh();
 await v.update();
 await click(v.host,'heartbeat-run',otherRun);
 expect(requests()).toHaveLength(2);
 const [,other]=requests();
 expect(other).toMatchObject({agent:OWNER,run_id:otherRun,progress:first.progress,expected_head:initialHead+1});
 expect(other.op_id).not.toBe(first.op_id);
 expect(messages(v)).toContain('Record heartbeat recorded for '+otherRun+'.');

 await click(v.host,'heartbeat-run',RUN);
 expect(requests()).toHaveLength(3);
 const [,,retry]=requests();
 expect(retry.op_id).toBe(first.op_id);
 expect(retry).toEqual(first);
 expect(committed.size).toBe(2);
 expect(messages(v)).toContain('Record heartbeat recorded for '+RUN+'.');

 await click(v.host,'heartbeat-run',RUN);
 expect(requests()).toHaveLength(4);
 const [,,,next]=requests();
 expect(next).toMatchObject({agent:OWNER,run_id:RUN,progress:first.progress,expected_head:initialHead+2});
 expect(next.op_id).not.toBe(first.op_id);
 expect(committed.size).toBe(3);
});
it.each(['memory_required','memory_debt'])('A26 real close dispatch receives %s and rereads an open run',async(code)=>{
 const s=new Service();s.addRun();s.overrides.set('run_close',()=>refuse(code));const v=await mount(s,{panel:'runs'});await ready(v);expect((action(v.host,'close-run',RUN) as HTMLButtonElement).disabled).toBe(false);const d=await closeDraft(v);const before=s.calls('run_get').length;await submit(v);
 expect(writes(v,'run_close')).toHaveLength(1);expect(writes(v,'run_close')[0][1]).toMatchObject({agent:OWNER,run_id:RUN,outcome,cost});for(const key of ['gate','memory_receipts','ts_close','record'])expect(writes(v,'run_close')[0][1]).not.toHaveProperty(key);
 expect(v.host.textContent).toContain('Close run refused: '+code+'. Run remains open.');expect(s.calls('run_get').length).toBeGreaterThan(before);expect((d.querySelector('[name="outcome.verdict"]') as HTMLSelectElement).value).toBe('HOLD');expect(s.runs.get(RUN).closed).toBeNull();noSuccess(v);
});
it.each(badPaths)('A26 evidence path %s cannot dispatch run_close',async(path)=>{
 const s=new Service();s.addRun();const v=await mount(s,{panel:'runs'});await ready(v);const d=await closeDraft(v);set(d,'evidence.path',path);set(d,'evidence.sha256',H);const add=Array.from(d.querySelectorAll<HTMLButtonElement>('[data-lin-action="add-item"]')).find(b=>b.textContent?.includes('evidence'));expect(add).toBeDefined();add!.click();await submit(v);expect(writes(v,'run_close')).toHaveLength(0);expect(d.textContent).toMatch(/invalid|path|evidence/iu);
});
it.each(['pre-open','wrong-owner','private-episode','invalid-episode','repair-without-lesson','HOLD-without-negative','red-without-negative'])('A27 authoritative %s memory debt cannot be bypassed',async(reason)=>{
 const s=new Service();s.addRun();const code=reason==='pre-open'?'memory_required':'memory_debt';s.overrides.set('run_close',()=>refuse(code,'Synthetic '+reason));const v=await mount(s,{panel:'runs'});await ready(v);await closeDraft(v);await submit(v);expect(writes(v,'run_close')).toHaveLength(1);expect(v.host.textContent).toContain('Close run refused: '+code+'. Run remains open.');expect(s.runs.get(RUN).closed).toBeNull();noSuccess(v);
});
it.each(['HOLD','red','error'])('A28 valid failure-memory close preserves %s and requires gate, exact event and read',async(verdict)=>{
 const s=new Service(),opened=s.addRun();failureMemory(s);s.overrides.set('run_close',args=>{const run=closed({outcome:{...args.outcome,verdict},cost:args.cost});const c=s.commit('run_close',args,{record:run,memory_receipts:[evidence],gate:{passed:true,checks:[{id:'synthetic-memory-check',passed:true}]}},'run.close');s.runs.set(RUN,{opened,closed:run});return {run,commit:c.commit};});const v=await mount(s,{panel:'runs'});await ready(v);const d=await closeDraft(v);set(d,'outcome.verdict',verdict);await submit(v);expect(s.calls('run_get').some((x:any[])=>x[1].run_id===RUN)).toBe(true);expect(messages(v)).toContain('Close run recorded for '+RUN+'.');expect(s.runs.get(RUN).closed.outcome.verdict).toBe(verdict);
});
it('A28 missing closing gate witness cannot announce completion',async()=>{
 const s=new Service(),opened=s.addRun();s.overrides.set('run_close',args=>{const run=closed();const c=s.commit('run_close',args,{record:run,memory_receipts:[evidence]},'run.close');s.runs.set(RUN,{opened,closed:run});return {run,commit:c.commit};});const v=await mount(s,{panel:'runs'});await ready(v);await closeDraft(v);await submit(v);expect(writes(v,'run_close')).toHaveLength(1);noSuccess(v);expect(v.host.textContent).toMatch(/unconfirmed|invalid|unavailable|witness/iu);
});
it('A34 persistent status node survives ordered lifecycle updates and unchanged polling',async()=>{
 const s=new Service();s.addRun();const v=await mount(s,{panel:'runs'});await ready(v);action(v.host,'open-run',RUN);const status=v.status;const first=messages(v).length;await v.update();await v.update();expect(messages(v).length).toBe(first);expect(document.querySelector('[role="status"][aria-label="Application updates"]')).toBe(status);
 s.overrides.set('run_close',()=>refuse('memory_required'));await closeDraft(v);await submit(v);const refusal='Close run refused: memory_required. Run remains open.';expect(messages(v).filter(x=>x===refusal)).toHaveLength(1);await v.update();expect(messages(v).filter(x=>x===refusal)).toHaveLength(1);expect(document.querySelectorAll('[role="status"][aria-label="Application updates"]')).toHaveLength(1);
});
