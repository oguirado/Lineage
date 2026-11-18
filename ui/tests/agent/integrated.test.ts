/** Exercise the detail screen against the installed public CLI and real journal. */
import {expect,it,vi} from 'vitest';
import {spawnSync} from 'node:child_process';
import {mkdtempSync,mkdirSync,rmSync,writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {cursor,record,resultShape} from '../../src/screens/agent/wire.ts';
import {TransportError} from '../../src/transport.ts';
import {H,OWNER,RUN,UNIT,event,repoRoot,seat,task,unit} from './fixtures.ts';
import {action,addEvidence,click,closeDraft,dialog,flush,isolate,memoryDraft,messages,mount,ready,Service,set,submit,writes} from './helpers.ts';

isolate();
const packageFiles=[{path:'SKILL.md',content:'# Witness\nInspect the journal.'},{path:'family/x.py',content:'# Passive package file\n'}];

it('R49-WITNESS-1 real journal confirms run, memory and close across an unrelated skill publication',async()=>{
 const home=mkdtempSync(join(tmpdir(),'lineage-r49-'));
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
  const unrelated=invoke('skill_publish',{skill_id:'witness-skill',files:packageFiles,agent:'system',op_id:'seed-witness-skill'});
  const resolved=invoke('skill_get',{skill_id:'witness-skill',sha256:unrelated.skill.sha256});
  resultShape('skill_get',resolved);
  expect(resolved.skill.files).toEqual(packageFiles);
  mkdirSync(join(home,'evidence'),{recursive:true});writeFileSync(join(home,'evidence/synthetic.txt'),'synthetic evidence');
  const service=new Service();service.record=invoke('agent_get',{agent_id:OWNER}).record;
  const refresh=()=>{const page=invoke('ledger_events',{limit:1000});service.head=page.head;service.ledger=page.events;};refresh();
  expect(service.record.skills.map((skill:any)=>skill.skill_id)).toEqual(['review-skill']);
  const publication=service.ledger.find(e=>e.op_id==='seed-witness-skill');
  expect(publication).toMatchObject({
   kind:'skill.published',agent:'system',payload:{skill_id:'witness-skill',sha256:unrelated.skill.sha256,files:packageFiles},
  });
  const commits=new Map<string,{event_ids:string[];head:number;sha256:string}>();
  service.transport.call=vi.fn(async(tool:string,args:any,options:any)=>{
   expect(options.signal.aborted).toBe(false);
   const result=invoke(tool,args);
   if(options.mutation){commits.set(args.op_id,result.commit);refresh();}
   return result;
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
  await submit(v);expect(messages(v),messages(v).at(-1)).toContain('Open run recorded for '+RUN+'.');await click(start,'cancel-dialog');
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
  const closedRun=invoke('run_get',{run_id:RUN}).closed;
  expect(closedRun.memory.gate_passed).toBe(true);expect(closedRun.cost.cost_micro_usd).toBeNull();
  const journal=invoke('ledger_events',{limit:1000}).events;
  const attempts:[string,{op_id:string}][]=writes(v);
  expect(attempts.map(([tool])=>tool)).toEqual(['run_open','run_close','memory_put','run_close']);
  expect(commits.size).toBe(3);
  const [opened,refused,memoryPut,closed]=attempts.map(([,args])=>args.op_id);
  expect(journal.filter((e:any)=>e.op_id===refused)).toEqual([]);
  const witnesses=journal.filter((e:any)=>[opened,memoryPut,closed].includes(e.op_id));
  expect(witnesses.map((e:any)=>[e.kind,e.op_id])).toEqual([['run.open',opened],['memory.put',memoryPut],['run.close',closed]]);
  for(const witness of witnesses){
   expect(witness.agent).toBe(OWNER);
   expect(witness.lamport).toBeGreaterThan(publication.lamport);
   expect(commits.get(witness.op_id)).toEqual({event_ids:[witness.id],head:witness.lamport,sha256:witness.sha256});
  }
  expect(witnesses[0].payload).toMatchObject({run_id:RUN,agent_id:OWNER});
  expect(witnesses[1].payload).toMatchObject({run_id:RUN,agent_id:OWNER,unit:{id:UNIT,receipts:[{path:'evidence/synthetic.txt',sha256:H}]}});
  expect(witnesses[2].payload).toMatchObject({
   record:closedRun,gate:{passed:true},memory_receipts:[{path:'evidence/synthetic.txt',sha256:H}],
  });
  if(process.env.LINEAGE_TEST_WITNESS==='1'){
   const entries=[publication,...witnesses].map(({kind,id,lamport,op_id,sha256})=>({kind,id,lamport,op_id,sha256}));
   console.info(JSON.stringify({entries,refused,receipt:witnesses[2].payload.memory_receipts[0]}));
  }
 } finally {view?.mounted.dispose();rmSync(home,{recursive:true,force:true});}
},30000);

it('R49-WITNESS-2 package paths do not relax evidence, receipts or traversal checks',()=>{
 const [entry,nested]=packageFiles;
 const publication={skill_id:'witness-skill',sha256:H,files:packageFiles};
 const restricted={path:nested.path,sha256:H};
 const badEvidence=event(1,'skill.published',publication,{evidence:[restricted]});
 const badReceipt=event(1,'memory.put',{agent_id:OWNER,unit:unit('lesson',{receipts:[restricted]})});
 for(const candidate of [badEvidence,badReceipt]){
  const page={events:[candidate],head:1,next_after:1,has_more:false,resync:false};
  expect(()=>record(candidate,'event')).toThrow('Invalid evidence path');
  expect(()=>cursor(page,0)).toThrow('Invalid evidence path');
  expect(()=>resultShape('ledger_events',page)).toThrow('Invalid evidence or package path');
 }
 for(const path of ['family/../x.py','family//x.py']){
  const skill={...publication,files:[entry,{...nested,path}]};
  expect(()=>record(event(1,'skill.published',skill),'event')).toThrow();
  expect(()=>resultShape('skill_get',{skill:{...skill,retired:false}})).toThrow();
 }
});
