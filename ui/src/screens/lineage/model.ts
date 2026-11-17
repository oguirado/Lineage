import { invalidResponse, isObject, keysExactly, validateJson } from '../../transport.ts';
import type { AppState, LedgerEvent } from '../../ui/contracts.ts';

export type BirthOp = 'genesis'|'clone'|'distill'|'cross'|'mutate'|'specialize';
export type LineageNode = {agent_id:string;parents:string[];generation:number;op:BirthOp;status:'draft'|'shadow'|'promoted'|'retired'};
export type LineageTreeData = {nodes:LineageNode[];head:number};
export const agentId = (v:unknown):v is string => typeof v==='string' && /^[a-z][a-z0-9-]{2,63}$/u.test(v) && !['operator','system','constructor','prototype'].includes(v);
export const safeInteger = (v:unknown):v is number => typeof v==='number' && Number.isSafeInteger(v) && v>=0;
export const hash = (v:unknown):v is string => typeof v==='string' && /^[a-f0-9]{64}$/u.test(v);
export const order = (a:LineageNode,b:LineageNode) => a.generation-b.generation || (a.agent_id<b.agent_id?-1:a.agent_id>b.agent_id?1:0);
export function validateTree(value:unknown):LineageTreeData {
  if(!isObject(value)||!keysExactly(value,['nodes','head'])||!Array.isArray(value.nodes)||value.nodes.length>1000000||!safeInteger(value.head)) throw invalidResponse();
  const nodes:LineageNode[]=[];const byId=new Map<string,LineageNode>();
  for(const raw of value.nodes) {
    if(!isObject(raw)||!keysExactly(raw,['agent_id','parents','generation','op','status'])||!agentId(raw.agent_id)||!Array.isArray(raw.parents)||raw.parents.length>2||!raw.parents.every(agentId)||new Set(raw.parents).size!==raw.parents.length||raw.parents.includes(raw.agent_id)||!safeInteger(raw.generation)||!['genesis','clone','distill','cross','mutate','specialize'].includes(String(raw.op))||!['draft','shadow','promoted','retired'].includes(String(raw.status))||byId.has(raw.agent_id)) throw invalidResponse();
    const n:LineageNode={agent_id:raw.agent_id,parents:[...raw.parents],generation:raw.generation,op:raw.op as BirthOp,status:raw.status as LineageNode['status']};
    if(n.parents.length!==(n.op==='genesis'?0:n.op==='cross'?2:1)) throw invalidResponse();
    nodes.push(n);byId.set(n.agent_id,n);
  }
  // Strictly increasing generations prove acyclicity without recursive graph traversal.
  for(const n of nodes) {
    if(n.parents.some(p=>!byId.has(p))) throw invalidResponse();
    if(n.generation!==(n.parents.length?Math.max(...n.parents.map(p=>byId.get(p)!.generation))+1:0)) throw invalidResponse();
  }
  return {nodes:nodes.sort(order),head:value.head};
}
export function coherent(state:AppState,head:number):boolean {
  if(!safeInteger(state.head)||state.head!==head||state.phase!=='ready'||state.stale||state.error||/resync/iu.test(state.notice??'')||state.events.length!==head) return false;
  const ids=new Set<string>();
  return state.events.every((event,i)=>event.lamport===i+1&&!ids.has(event.id)&&Boolean(ids.add(event.id)));
}
export function birthIndex(events:readonly LedgerEvent[]):Map<string,LedgerEvent> {
  const found=new Map<string,LedgerEvent>();const duplicates=new Set<string>();
  for(const e of events) {
    if(e.kind!=='agent.born') continue;
    const record=e.payload.record;
    if(!isObject(record)||!agentId(record.agent_id)||!isObject(record.born)||record.born.event_id!==e.id) continue;
    if(found.has(record.agent_id)) duplicates.add(record.agent_id);
    found.set(record.agent_id,e);
  }
  for(const id of duplicates) found.delete(id);
  return found;
}
export type EvidenceObject = Record<string,any>;
const id = (v:unknown) => typeof v==='string'&&/^[A-Za-z0-9_-]{8,64}$/u.test(v);
const path = (v:unknown) => typeof v==='string'&&v.length<=512&&/^[A-Za-z0-9_.\/-]+$/u.test(v)&&!v.startsWith('/')&&!v.split('/').some(p=>!p||p==='.'||p==='..');
export function eligible(item:unknown,record:EvidenceObject):item is EvidenceObject {
  try {validateJson(item);} catch {return false;}
  if(!isObject(item)||!keysExactly(item,['unit','source_agent_id','source_unit_id','unit_sha256'])||!agentId(item.source_agent_id)||!Array.isArray(record.parents)||!record.parents.includes(item.source_agent_id)||!id(item.source_unit_id)||!hash(item.unit_sha256)||!isObject(item.unit)) return false;
  const u=item.unit;
  if(!keysExactly(u,['schema','id','kind','level','statement','status','privacy','scope','provenance','receipts','supersedes','body'],['superseded_by'])||u.schema!=='lineage.mem.unit/v1'||!id(u.id)||!['lesson','negative','workflow'].includes(String(u.kind))||u.level!==2||u.status!=='active'||!['public','internal'].includes(String(u.privacy))||typeof u.statement!=='string'||!u.statement||!isObject(u.scope)||!isObject(u.provenance)||!isObject(u.provenance.inherited_from)||!Array.isArray(u.receipts)||!u.receipts.length||!isObject(u.body)||!Array.isArray(u.supersedes)) return false;
  if(u.scope.workflow!==record.workflow||(u.scope.language!=='general'&&u.scope.language!==record.language)) return false;
  const from=u.provenance.inherited_from;
  if(!keysExactly(from,['agent_id','unit_id','unit_sha256'])||from.agent_id!==item.source_agent_id||from.unit_id!==item.source_unit_id||from.unit_sha256!==item.unit_sha256) return false;
  if(u.receipts.some(r=>!isObject(r)||!keysExactly(r,['path','sha256'])||!path(r.path)||!hash(r.sha256))) return false;
  if(!keysExactly(u.scope,['workflow','language'])||!keysExactly(u.provenance,['origin','actor'],['run_id','inherited_from'])||typeof u.provenance.origin!=='string'||!u.provenance.origin||u.provenance.origin.length>128||!agentId(u.provenance.actor)||u.provenance.run_id!==undefined&&!id(u.provenance.run_id)||u.supersedes.length>64||!u.supersedes.every(id)) return false;
  const text=(v:unknown,max:number)=>typeof v==='string'&&[...v].length>0&&[...v].length<=max;
  const texts=(v:unknown,min:number)=>Array.isArray(v)&&v.length>=min&&v.length<=64&&v.every(x=>text(x,2048));
  if(!text(u.statement,16000)) return false;
  const b=u.body;
  if(u.kind==='lesson'&&(!keysExactly(b,['tempting_use','failure_mode','safer_action','blocked_use'])||![b.tempting_use,b.failure_mode,b.safer_action].every(x=>text(x,8000))||!texts(b.blocked_use,0))) return false;
  if(u.kind==='negative'&&(!keysExactly(b,['gate_id','verdict','cause','coordinate','safer_action'])||!text(b.gate_id,64)||!['HOLD','red','error'].includes(String(b.verdict))||!text(b.cause,8000)||!text(b.coordinate,512)||!text(b.safer_action,8000))) return false;
  if(u.kind==='workflow') {
    if(!keysExactly(b,['trigger_sig','steps','stats','status'])||b.status!=='promoted'||!text(b.trigger_sig,512)||!texts(b.steps,1)||!isObject(b.stats)||!keysExactly(b.stats,['runs','successes','mean_reward'])||!safeInteger(b.stats.runs)||!safeInteger(b.stats.successes)||b.stats.successes>b.stats.runs||(b.stats.mean_reward!==null&&(typeof b.stats.mean_reward!=='number'||!Number.isFinite(b.stats.mean_reward)))) return false;
  }
  return true;
}
export const rejectedReasons = new Map<string,string>([
  ['episode','Raw episodes are not inherited.'],['level_one','Operator rulings are not inherited.'],['level_three','Observations lack receipt-backed admission.'],['private','Private content is excluded.'],['missing_receipt','Required receipt missing.'],['invalid_receipt','Receipt was not admitted.'],['not_promoted','Workflow was not promoted.'],['scope_mismatch','Workflow or language scope differs.'],['not_selected','Unit was not selected.'],['inactive','Unit is inactive.'],['kind_not_inheritable','This kind cannot be inherited.'],
]);
export function citedRules(value:unknown):Map<string,string>|null {
  if(!isObject(value)||typeof value.text!=='string'||!Array.isArray(value.rule_ids)||!Array.isArray(value.overlays)) return null;
  const result=new Map<string,string>();
  for(const line of value.text.split('\n')) {
    const match=/^\[GOLD-S1\/PM-1001\.1\/([A-Za-z0-9.-]+); §([^\]]+)\] (.*)$/u.exec(line);
    if(match) {if(result.has(match[1])) return null;result.set(match[1],line);}
  }
  if(value.rule_ids.length!==result.size||value.rule_ids.some(r=>typeof r!=='string'||!result.has(r))) return null;
  return result;
}
