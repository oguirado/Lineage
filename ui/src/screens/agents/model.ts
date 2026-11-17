import type { JsonObject, JsonValue, Query, EventsPage } from '../../ui/contracts.ts';
import { canonical, invalidResponse, isObject, keysExactly, validateJson, validatePage } from '../../transport.ts';
import agentSchema from '../../../../schemas/agent.schema.json';
import eventSchema from '../../../../schemas/event.schema.json';
import memorySchema from '../../../../schemas/mem_unit.schema.json';
import runSchema from '../../../../schemas/run.schema.json';
import benchSchema from '../../../../schemas/bench_declared.schema.json';
import type { Agent, Filters, ScoreGroup, Seat, SkillPin, Pin, CreateArgs, Draft } from './types.ts';
export const workflows=['develop','test','review','harden','research','orchestrate'];
export const statuses=['draft','shadow','promoted','retired'];
export const DRAFT_KEY='lineage.u22.create-draft.v1';
export const fieldsKeys=['agent_id','display_name','workflow','language','allowed_seats','references','skills'];
export const safeInt=(v:unknown):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0;
export const id=(v:unknown):v is string=>typeof v==='string'&&/^[a-z][a-z0-9-]{2,63}$/u.test(v);
export const hash=(v:unknown):v is string=>typeof v==='string'&&/^[a-f0-9]{64}$/u.test(v);
export const opId=(v:unknown):v is string=>typeof v==='string'&&/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/u.test(v);
export const text=(v:unknown,max:number,min=1):v is string=>typeof v==='string'&&[...v].length>=min&&[...v].length<=max;
export const equal=(a:unknown,b:unknown)=>canonical(a as JsonValue)===canonical(b as JsonValue);
export const normalized=(s:string)=>s.normalize('NFC').toLocaleLowerCase('en-GB');
export const lexical=(a:string,b:string)=>a<b?-1:a>b?1:0;
export const seatIdentity=(s:Seat)=>JSON.stringify([s.model,s.effort,s.mode]);
export function demand(ok:unknown):asserts ok {if(!ok) throw invalidResponse();}
export function closed(v:unknown,required:string[],optional:string[]=[]):asserts v is JsonObject {validateJson(v);demand(isObject(v)&&keysExactly(v,required,optional));}
// Only bundled schema references are admitted. This deliberately implements the
// K0 subset, including conditional record constraints and Unicode character counts.
type Schema=Record<string,any>;
const schemas:Record<string,Schema>={'agent.schema.json':agentSchema,'event.schema.json':eventSchema,'mem_unit.schema.json':memorySchema,'run.schema.json':runSchema,'bench_declared.schema.json':benchSchema};
function matches(value:unknown,s:Schema):boolean {
  if(s.$ref) {const target=schemas[s.$ref];return !!target&&matches(value,target);}
  if('const' in s&&!equal(value,s.const)) return false;
  if(s.enum&&!s.enum.some((x:unknown)=>equal(x,value))) return false;
  if(s.anyOf&&!s.anyOf.some((x:Schema)=>matches(value,x))) return false;
  if(s.oneOf&&s.oneOf.filter((x:Schema)=>matches(value,x)).length!==1) return false;
  if(s.allOf&&!s.allOf.every((x:Schema)=>matches(value,x))) return false;
  if(s.if&&!matches(value,matches(value,s.if)?s.then??{}:s.else??{})) return false;
  if(s.type==='null'&&value!==null||s.type==='boolean'&&typeof value!=='boolean'||s.type==='string'&&typeof value!=='string'||s.type==='array'&&!Array.isArray(value)||s.type==='object'&&!isObject(value)) return false;
  if(s.type==='integer'&&!safeInt(value)||s.type==='number'&&(typeof value!=='number'||!Number.isFinite(value))) return false;
  if(typeof value==='number'&&(s.minimum!==undefined&&value<s.minimum||s.maximum!==undefined&&value>s.maximum)) return false;
  if(typeof value==='string'&&(s.minLength!==undefined&&[...value].length<s.minLength||s.maxLength!==undefined&&[...value].length>s.maxLength||s.pattern&&!new RegExp(s.pattern,'u').test(value))) return false;
  if(Array.isArray(value)) {
    if(s.minItems!==undefined&&value.length<s.minItems||s.maxItems!==undefined&&value.length>s.maxItems||s.uniqueItems&&new Set(value.map(v=>canonical(v as JsonValue))).size!==value.length) return false;
    if(s.items&&!value.every(v=>matches(v,s.items))) return false;
  }
  if(isObject(value)) {
    if(s.required&&!s.required.every((k:string)=>Object.hasOwn(value,k))) return false;
    if(s.maxProperties!==undefined&&Object.keys(value).length>s.maxProperties) return false;
    for(const [k,v] of Object.entries(value)) {
      if(s.propertyNames&&!matches(k,s.propertyNames)) return false;
      if(s.properties?.[k]) {if(!matches(v,s.properties[k])) return false;}
      else if(s.additionalProperties===false) return false;
      else if(isObject(s.additionalProperties)&&!matches(v,s.additionalProperties)) return false;
    }
  }
  return true;
}
export function agentRecord(v:unknown):Agent {validateJson(v);demand(matches(v,agentSchema));const r=v as Agent;demand(new Set(r.references.map(p=>p.id)).size===2);if(r.promoted_seat) demand(validSeat(r.promoted_seat));return r;}
export function validSeat(v:unknown):v is Seat {return isObject(v)&&keysExactly(v,['model','effort','mode'])&&text(v.model,128)&&text(v.effort,32)&&/^[a-z0-9_-]+$/u.test(v.effort)&&['headless','interactive'].includes(String(v.mode));}
export function validSkill(v:unknown):v is SkillPin {return isObject(v)&&keysExactly(v,['skill_id','sha256'])&&id(v.skill_id)&&hash(v.sha256);}
export function validPin(v:unknown):v is Pin {return isObject(v)&&keysExactly(v,['id','sha256'])&&['gold_s1','memory_v21'].includes(String(v.id))&&hash(v.sha256);}
export function listResult(v:unknown):{agents:Agent[];next_after:string|null;head:number} {
  closed(v,['agents','next_after','head']);demand(Array.isArray(v.agents)&&v.agents.length<=100&&safeInt(v.head)&&(v.next_after===null||id(v.next_after)));
  return {agents:v.agents.map(agentRecord),next_after:v.next_after as string|null,head:v.head};
}
export function getResult(v:unknown,expected:string):Agent {closed(v,['record']);const r=agentRecord(v.record);demand(r.agent_id===expected);return r;}
export function scoreResult(v:unknown,expected:string):ScoreGroup[] {
  closed(v,['agent_id','groups','head']);demand(id(v.agent_id)&&v.agent_id===expected&&safeInt(v.head)&&Array.isArray(v.groups));
  for(const g of v.groups) {closed(g,['seat','memory_arm','runs','successes','unknown_costs','mean_cost_micro_usd','mean_duration_ms']);demand(validSeat(g.seat)&&['none','own','inherited'].includes(String(g.memory_arm))&&safeInt(g.runs)&&safeInt(g.successes)&&g.successes<=g.runs&&safeInt(g.unknown_costs)&&g.unknown_costs<=g.runs);for(const k of ['mean_cost_micro_usd','mean_duration_ms']) demand(g[k]===null||typeof g[k]==='number'&&Number.isFinite(g[k])&&(g[k] as number)>=0&&(g[k] as number)<=Number.MAX_SAFE_INTEGER);}
  demand(new Set(v.groups.map(g=>canonical((g as JsonObject).seat)+':'+(g as JsonObject).memory_arm)).size===v.groups.length);return v.groups as ScoreGroup[];
}
export function skillsResult(v:unknown):(SkillPin & {retired:boolean})[] {
  closed(v,['skills']);demand(Array.isArray(v.skills));for(const p of v.skills) {closed(p,['skill_id','sha256','retired']);demand(id(p.skill_id)&&hash(p.sha256)&&typeof p.retired==='boolean');}
  demand(new Set(v.skills.map(p=>canonical(p))).size===v.skills.length);return v.skills as (SkillPin & {retired:boolean})[];
}
export function referenceResult(v:unknown,verified:unknown,refId:string):{pin:Pin;description:string} {
  closed(v,['reference']);closed(v.reference,['id','sha256','bytes','rules']);const r=v.reference;
  closed(verified,['ref_id','sha256','bytes','valid']);demand(r.id===refId&&verified.ref_id===refId&&hash(r.sha256)&&r.sha256===verified.sha256&&safeInt(r.bytes)&&r.bytes>0&&r.bytes===verified.bytes&&verified.valid===true&&Array.isArray(r.rules));
  for(const rule of r.rules) {closed(rule,['id','section','text']);demand(text(rule.id,64)&&text(rule.section,256)&&text(rule.text,65536));}
  return {pin:{id:refId,sha256:r.sha256},description:`Verified ${refId} · ${r.bytes} bytes. `+r.rules.map(rule=>(rule as JsonObject).text).join(' ')};
}
export function eventsResult(v:unknown):EventsPage {validatePage(v);demand(v.events.length<=1000);for(const e of v.events) demand(matches(e,eventSchema));return v;}
export function creationResult(v:unknown,a:CreateArgs):{record:Agent;commit:{event_ids:string[];head:number;sha256:string}} {
  closed(v,['record','commit']);const record=agentRecord(v.record);agrees(record,a);closed(v.commit,['event_ids','head','sha256']);const c=v.commit;
  demand(Array.isArray(c.event_ids)&&c.event_ids.length>0&&c.event_ids.length<=10000&&c.event_ids.every(x=>typeof x==='string'&&/^e-[0-9a-f]{16}$/u.test(x))&&new Set(c.event_ids).size===c.event_ids.length&&safeInt(c.head)&&c.head>0&&hash(c.sha256));
  demand((c.event_ids as string[]).includes(record.born.event_id));return {record,commit:c as {event_ids:string[];head:number;sha256:string}};
}
export function agrees(r:Agent,a:CreateArgs):void {demand(r.born.op==='genesis'&&r.parents.length===0&&r.generation===0);for(const key of fieldsKeys) demand(equal(r[key],a[key]));}
function arrayValid(v:unknown,max:number,check:(v:unknown)=>boolean,min=0):boolean {return Array.isArray(v)&&v.length>=min&&v.length<=max&&v.every(check)&&new Set(v.map(x=>canonical(x as JsonValue))).size===v.length;}
export function validFields(v:unknown,complete:boolean):boolean {
  if(!isObject(v)||!keysExactly(v,fieldsKeys)||!['agent_id','display_name','workflow','language'].every(k=>typeof v[k]==='string')) return false;
  if(!arrayValid(v.allowed_seats,16,validSeat,complete?1:0)||!arrayValid(v.skills,256,validSkill)||!arrayValid(v.references,2,validPin,complete?2:0)) return false;
  if(Array.isArray(v.references)&&new Set(v.references.map(x=>(x as JsonObject).id)).size!==v.references.length) return false;
  return !complete||id(v.agent_id)&&!['operator','system'].includes(v.agent_id)&&text(v.display_name,128)&&text(v.language,64)&&workflows.includes(String(v.workflow));
}
export function validArgs(v:unknown):v is CreateArgs {if(!isObject(v)||!keysExactly(v,[...fieldsKeys,'agent','op_id','expected_head'])) return false;const f=Object.fromEntries(fieldsKeys.map(k=>[k,v[k]]));return validFields(f,true)&&id(v.agent)&&opId(v.op_id)&&safeInt(v.expected_head);}
export function admitDraft(raw:string):Draft {
  demand(new TextEncoder().encode(raw).length<=1048576);const v:unknown=JSON.parse(raw);closed(v,['schema','fields','seat_draft','actor','op_id','phase','submitted','unresolved']);
  demand(v.schema==='lineage.ui.create-draft/v1'&&validFields(v.fields,false)&&isObject(v.seat_draft)&&keysExactly(v.seat_draft,['model','effort','mode'])&&Object.values(v.seat_draft).every(x=>typeof x==='string')&&(v.actor===null||id(v.actor))&&opId(v.op_id)&&['editing','pending','uncertain','verifying','refused'].includes(String(v.phase))&&(v.submitted===null||validArgs(v.submitted))&&(v.unresolved===null||validArgs(v.unresolved)));
  const d=v as unknown as Draft;demand(!['pending','uncertain','verifying'].includes(d.phase)||d.unresolved!==null);
  if(d.phase==='pending'||d.phase==='verifying') d.phase='uncertain';return d;
}
export function parseQuery(q:Query):{filters:Filters;notice:string} {
  const f:Filters={q:'',workflow:'',language:'',status:'',retired:false,sort:'id-asc',compare:[]},notices:string[]=[];
  for(const [k,v] of Object.entries(q)) {
    let ok=typeof v==='string';
    if(k==='q') {if(ok) f.q=v;}
    else if(k==='workflow') {ok=ok&&workflows.includes(v);if(ok) f.workflow=v;}
    else if(k==='language') {ok=ok&&text(v,64);if(ok) f.language=v;}
    else if(k==='status') {ok=ok&&statuses.includes(v);if(ok) f.status=v;}
    else if(k==='retired') {ok=v==='true'||v==='false';if(ok) f.retired=v==='true';}
    else if(k==='sort') {ok=['id-asc','id-desc','name-asc'].includes(v);if(ok) f.sort=v;}
    else if(k==='compare') {try {const ids:unknown=JSON.parse(v);ok=Array.isArray(ids)&&ids.length<=2&&ids.every(id)&&new Set(ids).size===ids.length&&equal(ids,[...ids].sort(lexical));if(ok) f.compare=ids as string[];}catch{ok=false;}}
    else {notices.push(`Unknown query field ${k} ignored.`);continue;}
    if(!ok) notices.push(`Invalid ${k}; field reset.`);
  }
  return {filters:f,notice:notices.join(' ')};
}
export function queryOf(f:Filters):Record<string,string> {const q:Record<string,string>={};for(const k of ['q','workflow','language','status'] as const) if(f[k]) q[k]=f[k];if(f.retired) q.retired='true';if(f.sort!=='id-asc') q.sort=f.sort;if(f.compare.length) q.compare=JSON.stringify([...f.compare].sort(lexical));return q;}
export function serverArgs(f:Filters):JsonObject {const a:JsonObject={};for(const k of ['workflow','language','status'] as const) if(f[k]) a[k]=f[k];if(f.retired) a.include_retired=true;return a;}
export function visible(records:Agent[],f:Filters):Agent[] {const q=normalized(f.q);return records.filter(r=>!q||normalized(r.agent_id).includes(q)||normalized(r.display_name).includes(q)).sort((a,b)=>f.sort==='name-asc'?lexical(normalized(a.display_name),normalized(b.display_name))||lexical(a.agent_id,b.agent_id):lexical(a.agent_id,b.agent_id)*(f.sort==='id-desc'?-1:1));}
export function errorText(error:unknown):string {const e=error as {code?:string;message?:string;detail?:unknown};return [e?.code??'invalid_response',e?.detail??e?.message??'Read unavailable.'].join(': ');}
