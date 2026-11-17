/** Synthetic K0 data. These hashes identify test bytes, not runtime receipts. */
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
export const repoRoot=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
import type {ToolDescriptor} from '../../src/ui/contracts.ts';
export const canonical = (value:any):string => JSON.stringify(value, (_key, v) =>
  v && typeof v === 'object' && !Array.isArray(v) ? Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])) : v);
export const hash = (text:string) => createHash('sha256').update(text,'utf8').digest('hex');
export const H=hash('synthetic evidence'), OTHER=hash('other synthetic bytes');
export const OWNER='aurora-root', CHILD='aurora-child', RUN='run-00001', UNIT='unit-00001';
export const CLOCK=1794873600000;
export const seat={model:'synthetic-model',effort:'medium',mode:'headless'};
export const task={id:'task-00001',kind:'review',language:'python'};
export const cost={tokens_in:null,tokens_out:null,tokens_cache:null,duration_ms:null,cost_micro_usd:null};
export const outcome={verdict:'HOLD',repair_loops:1,findings:{confirmed:1,refuted:0}};
export const constitution='Synthetic constitution\n[GOLD-S1/PM-1001.1/I1; §1:L1-L2]\n';
export const evidence={path:'evidence/synthetic.txt',sha256:H};
export const eid=(n:number)=>'e-'+n.toString(16).padStart(16,'0');
export function agent(changes:any={}) {
  const a:any={schema:'lineage.agent/v1',agent_id:OWNER,display_name:'Same display name',workflow:'review',language:'python',
    allowed_seats:[seat,{...seat,effort:'high'},{...seat,mode:'interactive'}],
    references:[{id:'gold_s1',sha256:H},{id:'memory_v21',sha256:OTHER}],
    constitution_sha256:hash(constitution),skills:[{skill_id:'review-skill',sha256:H}],memory_gen:1,
    brief_head_sha256:H,agent_version:H,generation:0,parents:[],born:{op:'genesis',event_id:eid(1)},status:'draft',...changes};
  if(!('agent_version' in changes)) a.agent_version=hash(canonical({constitution_sha256:a.constitution_sha256,skills:a.skills,memory_gen:a.memory_gen}));
  return a;
}
export const levels:Record<number,string>={1:'Level one — operator ruling',2:'Level two — receipt-backed',3:'Level three — observation'};
export function unit(kind='lesson',changes:any={}) {
  const bodies:Record<string,any>={
    ruling:{quote_sha256:H,how_to_apply:'Operator ruling text'},
    lesson:{tempting_use:'Guess an unseen result',failure_mode:'Missing evidence',safer_action:'Read the witness',blocked_use:[]},
    negative:{gate_id:'synthetic-gate',verdict:'HOLD',cause:'No witness',coordinate:'src/example.ts:1',safer_action:'Read the witness'},
    workflow:{trigger_sig:'Review',steps:['Read the witness'],stats:{runs:0,successes:0,mean_reward:null},status:'promoted'},
    episode:{run_id:RUN,task_id:task.id,seat,outcome,cost,parents_context:[]},
    decision:{reason:'Wait for evidence'},open_item:{class:'followup',order:0,trigger:'After review'},
  };
  const level=kind==='ruling'?1:2;
  return {schema:'lineage.mem.unit/v1',id:UNIT,kind,level,statement:'Receipt-backed synthetic lesson',status:'active',privacy:'internal',
    scope:{workflow:'review',language:'python'},provenance:{origin:'synthetic fixture',actor:OWNER,...(kind==='episode'?{run_id:RUN}:{})},
    receipts:[evidence],supersedes:[],body:bodies[kind],...changes};
}
export function event(n:number,kind:string,payload:any,changes:any={}) {
  const e:any={schema:'lineage.event/v1',id:eid(n),lamport:n,ts:CLOCK+n,ledger:'main',agent:OWNER,kind,payload,
    op_id:'synthetic-'+n,request_sha256:H,evidence:[],prev_sha256:'0'.repeat(64),...changes};
  e.sha256=hash(canonical(e)); return e;
}
export function birth(a=agent(),n=1,inherited:any[]=[]) {
  return event(n,'agent.born',{record:a,inherited_units:inherited,rejected_units:[],constitution:{text:constitution,overlays:[],rule_ids:['I1']}},{agent:'system'});
}
export function opening(changes:any={},n=3) {
  return event(n,'run.open',{run_id:RUN,agent_id:OWNER,agent_version:agent().agent_version,seat,task,parents_context:[],memory_arm:'own',...changes});
}
export function closed(changes:any={}) {
  return {schema:'lineage.run/v1',run_id:RUN,agent_id:OWNER,agent_version:agent().agent_version,ts_open:CLOCK+3,ts_close:CLOCK+5,
    seat,task,parents_context:[],memory_arm:'own',outcome,cost,memory:{unit_ids:[UNIT],levels:[2],gate_passed:true},evidence:[evidence],...changes};
}
export function group(changes:any={}) {return {seat,memory_arm:'own',runs:2,successes:1,unknown_costs:2,mean_cost_micro_usd:null,mean_duration_ms:null,...changes};}
const names=['agent_get','agent_brief','agent_list','reference_get','reference_verify','skill_get','skill_list','memory_get','memory_history','memory_route','memory_bootcheck','scorecard_get','run_get','ledger_events',
 'memory_put','run_open','run_beat','run_close','agent_clone','agent_distill','agent_cross','agent_mutate','agent_specialize','agent_retire','agent_promote'];
const contract=readFileSync(resolve(repoRoot,'docs/CONTRACT.md'),'utf8');
/** Read exact discovery schemas; never weaken them to an open object double. */
export const descriptors:ToolDescriptor[]=names.map(name=>{
  const section=contract.split('### `'+name+'`')[1];
  const block=section?.match(/Arguments:\s*```json\s*([\s\S]*?)```/u);
  if(!block) throw Error('Frozen descriptor absent: '+name);
  return {name,description:'Synthetic '+name,inputSchema:JSON.parse(block[1])};
});
export const schema=(name:string)=>JSON.parse(readFileSync(resolve(repoRoot,'schemas',name),'utf8'));
export const badPaths=['/escape.txt','../escape.txt','safe/../escape','safe/./file','safe//file','safe\\file','ledger/file','family/file','évidence/file'];
