/** Exercise the detail screen against the installed public CLI and real journal. */
import {expect,it,vi} from 'vitest';
import {spawnSync} from 'node:child_process';
import {mkdtempSync,mkdirSync,rmSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
import {TransportError} from '../../src/transport.ts';
import {OWNER,RUN,UNIT,repoRoot,seat,task} from './fixtures.ts';
import {action,addEvidence,click,closeDraft,dialog,flush,isolate,memoryDraft,messages,mount,ready,Service,set,submit,writes} from './helpers.ts';

isolate();
it('integrated tool results support inspection and a journal-witnessed run, refusal, memory and close journey',async()=>{
 const home=mkdtempSync(join(repoRoot,'ui/tests/agent/.runtime-'));
 const invoke=(tool:string,args:any={}):any=>{
  const result=spawnSync('python3',['-m','lineage','--home',home,'call',tool,'--json',JSON.stringify(args)],{
   cwd:repoRoot,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},encoding:'utf8',timeout:15000,maxBuffer:2**20,
  });
  if(result.error)throw result.error;
  const reply=JSON.parse(result.stdout);
  if(reply.ok===false)throw new TransportError('domain',reply.code,typeof reply.detail==='string'?reply.detail:reply.code);
  expect(result.status).toBe(0);return reply.untrusted;
 };
 let view:Awaited<ReturnType<typeof mount>>|undefined;
 try {
  const references=['gold_s1','memory_v21'].map(ref_id=>{const r=invoke('reference_get',{ref_id}).reference;return {id:ref_id,sha256:r.sha256};});
  const published=invoke('skill_publish',{skill_id:'review-skill',files:[{path:'SKILL.md',content:'# Review\nInspect the evidence.'}],agent:'system',op_id:'seed-skill'});
  invoke('agent_create',{agent_id:OWNER,display_name:'Integrated agent',workflow:'review',language:'python',allowed_seats:[seat],references,skills:[{skill_id:'review-skill',sha256:published.skill.sha256}],agent:'system',op_id:'seed-agent'});
  mkdirSync(join(home,'evidence'),{recursive:true});writeFileSync(join(home,'evidence/synthetic.txt'),'synthetic evidence');
  const service=new Service();service.record=invoke('agent_get',{agent_id:OWNER}).record;
  const refresh=()=>{const page=invoke('ledger_events',{limit:1000});service.head=page.head;service.ledger=page.events;};refresh();
  service.transport.call=vi.fn(async(tool:string,args:any,options:any)=>{
   expect(options.signal.aborted).toBe(false);
   const result=invoke(tool,args);if(options.mutation)refresh();return result;
  });
  view=await mount(service);const v=view;await ready(v);
  expect(v.host.querySelector('h1')?.textContent).toBe('Agent '+OWNER);
  expect(v.host.textContent).toContain(service.ledger.find((e:any)=>e.kind==='agent.born').payload.constitution.text.trim());
  for(const id of ['gold_s1','memory_v21']){
   const selected=action(v.host,'edit-field') as HTMLSelectElement;selected.value=id;selected.dispatchEvent(new Event('change'));
   await click(v.host,'get-reference');expect(dialog(v).textContent).toContain(id);await click(v.host,'close-inspector');
   await click(v.host,'verify-reference');expect(v.host.querySelector('[role="status"].agent-feedback-global')?.textContent).toContain('verified');
  }
  await v.update({panel:'skills'});await click(v.host,'open-skill');expect(dialog(v).textContent).toContain('Inspect the evidence.');await click(v.host,'close-inspector');
  await v.update({panel:'memory'});expect(v.host.textContent).toContain('No memory units yet.');
  await v.update({panel:'scorecard'});expect(v.host.textContent).toContain('No recorded measurements.');
  await v.update({panel:'runs'});await click(v.host,'open-run-form');
  const start=dialog(v);
  for(const [key,value] of Object.entries({run_id:RUN,'seat.model':seat.model,'seat.effort':seat.effort,'seat.mode':seat.mode,'task.id':task.id,'task.kind':task.kind,'task.language':task.language,memory_arm:'own'}))set(start,key,value);
  await submit(v);expect(messages(v)).toContain('Open run recorded for '+RUN+'.');await click(start,'cancel-dialog');
  await v.update({panel:'runs'});await closeDraft(v);await submit(v);
  expect(dialog(v).querySelector('[role="alert"]')?.textContent).toContain('memory_required');
  expect(invoke('run_get',{run_id:RUN}).closed).toBeNull();await click(dialog(v),'cancel-dialog');
  await v.update({panel:'memory'});const memory=await memoryDraft(v,'episode');
  set(memory,'run_id',RUN);await flush();
  for(const [key,value] of Object.entries({'unit.body.outcome.verdict':'green','unit.body.outcome.repair_loops':0,'unit.body.outcome.findings.confirmed':0,'unit.body.outcome.findings.refuted':0}))set(memory,key,value);
  await addEvidence(memory);await submit(v);
  expect(messages(v)).toContain('Write memory recorded for '+UNIT+'.');await click(memory,'cancel-dialog');
  await v.update({panel:'memory'});expect(v.host.textContent).toContain(UNIT);
  await v.update({panel:'runs'});const close=await closeDraft(v);set(close,'outcome.verdict','green');set(close,'outcome.repair_loops',0);set(close,'outcome.findings.confirmed',0);await submit(v);
  expect(messages(v)).toContain('Close run recorded for '+RUN+'.');
  const record=invoke('run_get',{run_id:RUN}).closed;expect(record.memory.gate_passed).toBe(true);expect(record.cost.cost_micro_usd).toBeNull();
  const journal=invoke('ledger_events',{limit:1000}).events;
  for(const call of writes(v)){
   const tool=call[0],args=call[1];const kind=({run_open:'run.open',memory_put:'memory.put',run_close:'run.close'} as Record<string,string>)[tool];
   if(tool==='run_close'&&!journal.some((e:any)=>e.op_id===args.op_id))continue; // The deliberate no-memory refusal has no commit.
   expect(journal.some((e:any)=>e.kind===kind&&e.op_id===args.op_id&&e.agent===args.agent)).toBe(true);
  }
 } finally {view?.mounted.dispose();rmSync(home,{recursive:true,force:true});}
},30000);
