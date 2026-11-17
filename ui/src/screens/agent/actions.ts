import {identityKey} from '../../ui/primitives.ts';
import type {Runtime} from './panels.ts';
import {errorText} from './panels.ts';
import {canonical,closed,ensure,integer,isHash,record,unitResult,runResult} from './wire.ts';
export interface Submission {tool:string;args:any;fingerprint:string;phase:'pending'|'uncertain'|'refused'|'confirmed'}
export interface OperationDraft {submission?:Submission}
export interface MutationResult {data:any;record?:any;events:any[]}
export function operationId():string {const bytes=new Uint8Array(20);crypto.getRandomValues(bytes);return 'ui-'+Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');}
export async function witness(r:Runtime,tool:string,args:any,data:any):Promise<MutationResult> {
 ensure(data&&typeof data==='object','Unconfirmed mutation result');const commit=data.commit;closed(commit,['event_ids','head','sha256']);ensure(Array.isArray(commit.event_ids)&&commit.event_ids.length>0&&new Set(commit.event_ids).size===commit.event_ids.length&&integer(commit.head)&&commit.head>0&&isHash(commit.sha256),'Invalid commit witness');
 const kinds:Record<string,string>={memory_put:'memory.put',run_open:'run.open',run_beat:'run.beat',run_close:'run.close',agent_retire:'agent.status',agent_promote:'agent.status'};
 const kind=kinds[tool]??'agent.born';let after=0,seenHead:number|null=null;const found=new Map<string,any>();
 for(let page=0;page<1000;page++){
  const p=await r.call('ledger_events',{after,limit:100});ensure(!p.resync,'Unconfirmed witness: resync');ensure(p.head>=commit.head,'Unconfirmed commit prefix');if(seenHead!==null)ensure(p.head===seenHead,'Unconfirmed changing witness prefix');seenHead=p.head;
  for(const e of p.events)if(commit.event_ids.includes(e.id))found.set(e.id,e);
  if(p.next_after>=commit.head)break;ensure(p.has_more&&p.next_after>after,'Unconfirmed missing or stalled witness');after=p.next_after;
 }
 ensure(found.size===commit.event_ids.length,'Unconfirmed missing witness');const events=commit.event_ids.map((id:string)=>found.get(id));ensure(events.some((e:any)=>e.lamport===commit.head&&e.sha256===commit.sha256),'Unconfirmed commit hash pin');
 for(const e of events){ensure(e.lamport<=commit.head&&e.kind===kind&&e.agent===args.agent&&e.op_id===args.op_id,'Unconfirmed witness identity mismatch');const p=e.payload;
  if(tool==='memory_put'){ensure(p.agent_id===args.agent_id&&p.unit.id===args.unit.id&&canonical(p.unit)===canonical(args.unit)&&p.run_id===args.run_id,'Unconfirmed memory witness');}
  else if(tool.startsWith('run_')){if(tool==='run_close'){ensure(p.record.run_id===args.run_id&&p.record.agent_id===args.agent&&canonical(p.record.outcome)===canonical(args.outcome)&&canonical(p.record.cost)===canonical(args.cost),'Unconfirmed close owner or outcome');ensure(p.gate?.passed===true&&Array.isArray(p.gate.checks)&&p.gate.checks.length>0&&p.gate.checks.every((x:any)=>x.passed===true)&&p.memory_receipts?.length>0&&p.record.memory.gate_passed===true,'Unconfirmed closing gate witness');}else{ensure(p.run_id===args.run_id&&p.agent_id===(args.agent_id??args.agent),'Unconfirmed run owner');if(tool==='run_open')for(const k of ['seat','task','parents_context','memory_arm'])ensure(canonical(p[k])===canonical(args[k]),'Run start witness mismatch');if(tool==='run_beat')ensure(p.progress===args.progress,'Heartbeat witness mismatch');}}
  else if(kind==='agent.status'){ensure(p.agent_id===args.agent_id,'Status owner mismatch');if(tool==='agent_promote')ensure(p.bench_id===args.bench_id,'Benchmark witness mismatch');}
  else{ensure(p.record.agent_id===args.child_id&&p.record.born.op===tool.slice(6),'Child birth mismatch');const parents=args.parent_ids??[args.parent_id];ensure(canonical(p.record.parents)===canonical(parents),'Child parents mismatch');}
 }
 let current:any;
 if(tool==='memory_put'){const d=unitResult(await r.call('memory_get',{agent_id:args.agent_id,unit_id:args.unit.id}),args.agent_id,args.unit.id);ensure(d.head===seenHead&&canonical(d.unit)===canonical(data.unit)&&canonical(d.unit)===canonical(args.unit),'Unconfirmed memory read mismatch');}
 else if(tool.startsWith('run_')){const d=runResult(await r.call('run_get',{run_id:args.run_id}),args.agent_id??args.agent,args.run_id);ensure(d.head===seenHead,'Unconfirmed run prefix');if(tool==='run_close')ensure(d.closed!==null&&canonical(d.closed)===canonical(data.run)&&canonical(d.closed)===canonical(events[0].payload.record),'Unconfirmed close read mismatch');if(tool==='run_open')ensure(d.opened.id===events[0].id&&data.opened.id===events[0].id,'Open read mismatch');if(tool==='run_beat')ensure(data.event.id===events[0].id,'Heartbeat read mismatch');}
 else{const target=args.child_id??args.agent_id;const before=await r.call('ledger_events',{after:0,limit:1});ensure(before.head===seenHead,'Unconfirmed agent prefix');const d=await r.call('agent_get',{agent_id:target});closed(d,['record']);record(d.record,'agent');const afterPage=await r.call('ledger_events',{after:0,limit:1});ensure(afterPage.head===before.head,'Unconfirmed agent changed');current=d.record;ensure(current.agent_id===target&&canonical(current)===canonical(data.record),'Unconfirmed agent read mismatch');if(kind==='agent.born')ensure(canonical(current.parents)===canonical(args.parent_ids??[args.parent_id]),'Child parents read mismatch');else ensure(current.status===events[0].payload.to,'Status read mismatch');}
 return {data,record:current,events};
}
export async function execute(r:Runtime,draft:OperationDraft,tool:string,payload:any,label:string,entity:string,onState:(state:'pending'|'settled',message:string)=>void):Promise<MutationResult|null> {
 if(draft.submission?.phase==='pending')return null;const fingerprint=canonical({tool,payload});let submission=draft.submission;
 if(submission?.phase==='confirmed'){if(submission.fingerprint===fingerprint)return null;submission=undefined;}
 if(submission?.phase!=='uncertain'&&(!submission||submission.fingerprint!==fingerprint)){
  const reason=r.available(tool,['memory_put','run_open','run_beat','run_close'].includes(tool));if(reason){onState('settled',reason);return null;}
  const actor=document.querySelector<HTMLSelectElement>('[data-lin-action="select-actor"]')!.value;ensure(r.head!==null,'Unknown acknowledged ledger head');submission={tool,args:{...payload,agent:actor,op_id:operationId(),expected_head:r.context.store.getState().head},fingerprint,phase:'pending'};draft.submission=submission;
 }
 ensure(submission,'Missing submitted draft');const saved=submission;saved.phase='pending';onState('pending',label+' pending.');r.announce('pending:'+saved.args.op_id,label+' pending.');
 try{const data=await r.call(saved.tool,saved.args,true);saved.phase='uncertain';const result=await witness(r,saved.tool,saved.args,data);saved.phase='confirmed';await r.context.store.refresh();if(result.record&&result.record.agent_id===r.a.agent_id)r.a=result.record;const message=label+' recorded for '+identityKey(entity.startsWith('run')||tool.startsWith('run_')?'run':tool==='memory_put'?'unit':'agent',entity)+'.';onState('settled',message);r.announce('committed:'+saved.args.agent+':'+saved.args.op_id,message);return result;}
 catch(e){if(r.signal.aborted)return null;const source=(e as any)?.source;let message:string;
  if(source==='domain'){saved.phase='refused';const code=(e as any).code;if(tool==='run_close'&&['memory_required','memory_debt'].includes(code)){try{const d=runResult(await r.call('run_get',{run_id:saved.args.run_id}),saved.args.agent,saved.args.run_id);ensure(d.closed===null,'Close refusal disagrees with run read');message='Close run refused: '+code+'. Run remains open.';}catch(readError){message='Unconfirmed close refusal: '+errorText(readError);}}else message=label+' refused: '+code+'. '+(e as Error).message;}
  else{saved.phase='uncertain';message=(source==='transport'?'Transport uncertainty. Retry replays the original operation. ':'Unconfirmed witness. ')+errorText(e);}
  onState('settled',message);r.announce('refusal:'+saved.args.op_id+':'+message,message);return null;
 }
}
