import type { JsonObject, JsonValue, LedgerEvent } from '../../ui/contracts.ts';
import { canonical, isObject, keysExactly, validateJson, invalidResponse } from '../../transport.ts';
import declarationSchema from '../../../../schemas/bench_declared.schema.json';
import runSchema from '../../../../schemas/run.schema.json';
import agentSchema from '../../../../schemas/agent.schema.json';

export type Seat = {model:string;effort:string;mode:'headless'|'interactive'};
export type Declaration = {schema:'lineage.bench.declared/v1';bench_id:string;bank_id:string;bank_sha256:string;protocol:'paired'|'crossed';purpose:'select'|'confirm';agents:string[];seats:Seat[];memory_arms:string[];credit_rule:{metric:'correctness_first';minimum_gain:number;dispersion:'population_stddev';cost_tiebreaker:boolean};sprt:{p0:number;p1:number;alpha:number;beta:number;cap:number};promotion:{n_shadow_runs:number}};
export type Cell = {bench_id:string;task_id:string;agent_id:string;seat:Seat;memory_arm:string;run_id:string;verdict:string;correctness:number;cost:Record<string,number|null>};
export type Verdict = {bench_id:string;decision:string;llr:number;n_discordant:number;credit:{gain:number;baseline_dispersion:number;minimum_reward:number;credited:boolean}};
export type Bench = {declaration:Declaration;state:string;results:Cell[];verdict:Verdict|null;head:number};
export const id = (v:unknown):v is string => typeof v==='string'&&/^[A-Za-z0-9_-]{8,64}$/u.test(v);
export const agentId = (v:unknown):v is string => typeof v==='string'&&/^[a-z][a-z0-9-]{2,63}$/u.test(v)&&v!=='operator'&&v!=='system';
export const eventId = (v:unknown):v is string => typeof v==='string'&&/^e-[0-9a-f]{16}$/u.test(v);
export const integer = (v:unknown):v is number => typeof v==='number'&&Number.isSafeInteger(v)&&v>=0;
export const states=['declared','queued','running','stalled','complete'];
export const equal=(a:unknown,b:unknown)=>canonical(a as JsonValue)===canonical(b as JsonValue);
export const seatId=(seat:Seat)=>canonical(seat);
const schemas:Record<string,unknown>={'bench_declared.schema.json':declarationSchema,'agent.schema.json':agentSchema,'run.schema.json':runSchema};
/** The closed local schema subset used by discovery and the Arena wire records. */
export function matches(value:unknown,schema:any):boolean {
  if(!schema||typeof schema!=='object') return false;
  if(schema.$ref) {const [file,fragment]=schema.$ref.split('#');let target:any=schemas[file];if(!target) return false;if(fragment) for(const part of fragment.slice(1).split('/')) target=target?.[part.replace(/~1/g,'/').replace(/~0/g,'~')];return matches(value,target);}
  if(schema.const!==undefined&&!equal(value,schema.const)) return false;
  if(schema.enum&&!schema.enum.some((v:unknown)=>equal(value,v))) return false;
  if(schema.anyOf&&!schema.anyOf.some((s:unknown)=>matches(value,s))) return false;
  if(schema.oneOf&&schema.oneOf.filter((s:unknown)=>matches(value,s)).length!==1) return false;
  if(schema.allOf&&!schema.allOf.every((s:unknown)=>matches(value,s))) return false;
  if(schema.if&&matches(value,schema.if)&&schema.then&&!matches(value,schema.then)) return false;
  if(schema.type==='null'&&value!==null||schema.type==='boolean'&&typeof value!=='boolean') return false;
  if(schema.type==='string') {
    if(typeof value!=='string') return false;const n=[...value].length;
    if(n<(schema.minLength??0)||n>(schema.maxLength??Infinity)||schema.pattern&&!new RegExp(schema.pattern,'u').test(value)) return false;
  }
  if(schema.type==='integer'||schema.type==='number') {
    if(typeof value!=='number'||!Number.isFinite(value)||schema.type==='integer'&&!Number.isSafeInteger(value)) return false;
    if(value<(schema.minimum??-Infinity)||value>(schema.maximum??Infinity)||schema.exclusiveMinimum!==undefined&&value<=schema.exclusiveMinimum||schema.exclusiveMaximum!==undefined&&value>=schema.exclusiveMaximum) return false;
  }
  if(schema.type==='array') {
    if(!Array.isArray(value)||value.length<(schema.minItems??0)||value.length>(schema.maxItems??Infinity)) return false;
    if(schema.uniqueItems&&new Set(value.map(v=>canonical(v))).size!==value.length) return false;
    if(schema.items&&!value.every(v=>matches(v,schema.items))) return false;
  }
  if(schema.type==='object'||schema.properties) {
    if(!isObject(value)) return false;
    if((schema.required??[]).some((k:string)=>!Object.hasOwn(value,k))) return false;
    if(schema.additionalProperties===false&&Object.keys(value).some(k=>!Object.hasOwn(schema.properties??{},k))) return false;
    for(const [k,s] of Object.entries(schema.properties??{})) if(Object.hasOwn(value,k)&&!matches(value[k],s)) return false;
  }
  return true;
}
export function validDeclaration(v:unknown):v is Declaration {return matches(v,declarationSchema)&&(v as Declaration).sprt.p0<(v as Declaration).sprt.p1&&(v as Declaration).agents.every(agentId);}
export function validSeat(v:unknown):v is Seat {return matches(v,declarationSchema.properties.seats.items);}
export function validVerdict(v:unknown):v is Verdict {
  if(!isObject(v)||!keysExactly(v,['bench_id','decision','llr','n_discordant','credit'])||!id(v.bench_id)||!['superior','not_superior','inconclusive'].includes(String(v.decision))||typeof v.llr!=='number'||!Number.isFinite(v.llr)||!integer(v.n_discordant)||!isObject(v.credit)||!keysExactly(v.credit,['gain','baseline_dispersion','minimum_reward','credited'])) return false;
  return ['gain','baseline_dispersion','minimum_reward'].every(k=>typeof (v.credit as JsonObject)[k]==='number'&&Number.isFinite((v.credit as JsonObject)[k]))&&typeof v.credit.credited==='boolean';
}
export function validCell(v:unknown):v is Cell {
  if(!isObject(v)||!keysExactly(v,['bench_id','task_id','agent_id','seat','memory_arm','run_id','verdict','correctness','cost'])) return false;
  return id(v.bench_id)&&id(v.task_id)&&id(v.run_id)&&agentId(v.agent_id)&&validSeat(v.seat)&&['none','own','inherited'].includes(String(v.memory_arm))&&['ADMIT','HOLD','red','green','error'].includes(String(v.verdict))&&typeof v.correctness==='number'&&Number.isFinite(v.correctness)&&v.correctness>=0&&v.correctness<=1&&isObject(v.cost)&&keysExactly(v.cost,['tokens_in','tokens_out','tokens_cache','duration_ms','cost_micro_usd'])&&Object.values(v.cost).every(x=>x===null||integer(x));
}
export function bench(value:unknown):Bench {
  validateJson(value);
  if(!isObject(value)||!keysExactly(value,['declaration','state','results','verdict','head'])||!validDeclaration(value.declaration)||!states.includes(String(value.state))||!integer(value.head)||!Array.isArray(value.results)||!value.results.every(validCell)||value.results.some(v=>v.bench_id!==(value.declaration as Declaration).bench_id)||value.verdict!==null&&(!validVerdict(value.verdict)||value.verdict.bench_id!==value.declaration.bench_id)) throw invalidResponse();
  return value as Bench;
}
export function statusReply(value:unknown,benchId:string):Bench {
  if(!isObject(value)||!keysExactly(value,['bench'])) throw invalidResponse();const b=bench(value.bench);if(b.declaration.bench_id!==benchId) throw invalidResponse();return b;
}
export function runMatches(record:any,cell:Cell):boolean {
  return isObject(record)&&record.run_id===cell.run_id&&record.agent_id===cell.agent_id&&equal(record.seat,cell.seat)&&record.memory_arm===cell.memory_arm&&isObject(record.task)&&record.task.id===cell.task_id&&record.task.bench_id===cell.bench_id;
}
export function witnessMatches(event:LedgerEvent,cell:Cell):boolean {
  if(!eventId(event.id)) return false;
  if(event.kind==='bench.result') return equal(event.payload,cell);
  if(event.kind==='run.close') {const r=event.payload.record;return runMatches(r,cell)&&isObject(r)&&isObject(r.outcome)&&r.outcome.verdict===cell.verdict&&equal(r.cost,cell.cost)&&event.agent===cell.agent_id;}
  return event.kind==='run.open'&&runMatches(event.payload,cell)&&event.agent===cell.agent_id;
}
export function validRunReply(v:any,cell:Cell):boolean {
  return isObject(v)&&keysExactly(v,['opened','closed','head'])&&integer(v.head)&&isObject(v.opened)&&v.opened.kind==='run.open'&&runMatches(v.opened.payload,cell)&&typeof (v.opened.payload as any).agent_version==='string'&&(v.closed===null||matches(v.closed,runSchema)&&runMatches(v.closed,cell));
}
export const validAgent=(v:unknown)=>matches(v,agentSchema);
export function errorText(error:unknown):string {
  if(error instanceof Error) {const e=error as Error & {code?:string;detail?:unknown};return [e.code,e.message,typeof e.detail==='string'?e.detail:null].filter(Boolean).join(' ');}
  return 'Unavailable response.';
}
