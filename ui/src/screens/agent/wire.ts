/** Closed public wire validation. No domain decision is made in the browser. */
import agentSchema from '../../../../schemas/agent.schema.json';
import memorySchema from '../../../../schemas/mem_unit.schema.json';
import runSchema from '../../../../schemas/run.schema.json';
import eventSchema from '../../../../schemas/event.schema.json';
import {canonical, validateJson, validatePage} from '../../transport.ts';
export {canonical};
export type RecordData = Record<string, any>;
const schemas:Record<string,any>={'agent.schema.json':agentSchema,'mem_unit.schema.json':memorySchema,'run.schema.json':runSchema,'event.schema.json':eventSchema};
export function invalid(detail='Invalid schema or mismatched response'):never {throw new Error(detail);}
export function ensure(condition:unknown,detail?:string):asserts condition {if(!condition)invalid(detail);}
export function closed(v:any,required:string[],optional:string[]=[]):void {ensure(v!==null&&typeof v==='object'&&!Array.isArray(v));ensure(required.every(k=>Object.hasOwn(v,k))&&Object.keys(v).every(k=>required.includes(k)||optional.includes(k)));}
export function validPath(path:unknown,evidence=true):path is string {return typeof path==='string'&&path.length>0&&path.length<=512&&/^[A-Za-z0-9_./-]+$/u.test(path)&&!path.startsWith('/')&&!path.split('/').some(p=>!p||p==='.'||p==='..')&&(!evidence||! /^(ledger|family)\//u.test(path));}
export const isHash=(v:unknown):v is string=>typeof v==='string'&&/^[a-f0-9]{64}$/u.test(v);
export const isId=(v:unknown):v is string=>typeof v==='string'&&/^[A-Za-z0-9_-]{8,64}$/u.test(v);
export const isAgentId=(v:unknown):v is string=>typeof v==='string'&&/^[a-z][a-z0-9-]{2,63}$/u.test(v)&&v!=='operator'&&v!=='system';
export const integer=(v:unknown):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0;
export function validate(v:any,s:any):void {
 if(s.$ref){const [file,pointer]=s.$ref.split('#');let ref=schemas[file];ensure(ref,'Unsupported schema reference');if(pointer)for(const part of pointer.split('/').slice(1))ref=ref[part];validate(v,ref);return;}
 if(s.const!==undefined)ensure(canonical(v)===canonical(s.const));if(s.enum)ensure(s.enum.includes(v));
 if(s.anyOf)ensure(s.anyOf.some((x:any)=>{try{validate(v,x);return true;}catch{return false;}}));
 if(s.type==='object'){ensure(v!==null&&typeof v==='object'&&!Array.isArray(v));}
 if(v!==null&&typeof v==='object'&&!Array.isArray(v)){
  for(const k of s.required??[])ensure(Object.hasOwn(v,k),'Required field '+k);
  for(const k of Object.keys(v)){if(s.additionalProperties===false)ensure(Object.hasOwn(s.properties??{},k),'Invalid schema: unknown field '+k);if(s.properties?.[k])validate(v[k],s.properties[k]);else if(typeof s.additionalProperties==='object')validate(v[k],s.additionalProperties);}
 }
 if(s.type==='array')ensure(Array.isArray(v));if(Array.isArray(v)){if(s.minItems!==undefined)ensure(v.length>=s.minItems);if(s.maxItems!==undefined)ensure(v.length<=s.maxItems);if(s.uniqueItems)ensure(new Set(v.map(x=>canonical(x))).size===v.length);if(s.items)v.forEach(x=>validate(x,s.items));}
 if(s.type==='string'){ensure(typeof v==='string');if(s.minLength!==undefined)ensure([...v].length>=s.minLength);if(s.maxLength!==undefined)ensure([...v].length<=s.maxLength);if(s.pattern)ensure(new RegExp(s.pattern,'u').test(v));}
 if(s.type==='integer')ensure(Number.isSafeInteger(v));if(s.type==='number')ensure(typeof v==='number'&&Number.isFinite(v));if(s.type==='null')ensure(v===null);if(s.type==='boolean')ensure(typeof v==='boolean');
 if(s.minimum!==undefined)ensure(typeof v==='number'&&v>=s.minimum);if(s.maximum!==undefined)ensure(typeof v==='number'&&v<=s.maximum);
 for(const x of s.allOf??[]) {if(x.if){let applies=true;try{validate(v,x.if);}catch{applies=false;}if(applies&&x.then)validate(v,x.then);if(!applies&&x.else)validate(v,x.else);}else validate(v,x);}
 if(s.not){let match=true;try{validate(v,s.not);}catch{match=false;}ensure(!match);}
}
export function record(v:any,kind:'agent'|'memory'|'run'|'event'):any {validateJson(v as unknown);validate(v,{agent:agentSchema,memory:memorySchema,run:runSchema,event:eventSchema}[kind]);
 const walk=(x:any):void=>{if(!x||typeof x!=='object')return;if(Object.hasOwn(x,'path'))ensure(validPath(x.path),'Invalid evidence path');for(const child of Object.values(x))walk(child);};walk(v);
 if(kind==='agent'){ensure(new Set(v.references.map((p:any)=>p.id)).size===2);ensure(isAgentId(v.agent_id));}
 if(kind==='memory')ensure(new TextEncoder().encode(canonical(v)).length<=6000,'Memory unit exceeds byte budget');return v;
}
export function cursor(v:any,after:number):any {validatePage(v);v.events.forEach((e:any)=>record(e,'event'));ensure(v.resync||v.next_after>=after,'Invalid cursor');if(v.has_more)ensure(v.next_after>after,'Stalled cursor');return v;}
export function unitResult(v:any,owner:string,id:string):any {closed(v,['unit','head']);ensure(integer(v.head));record(v.unit,'memory');ensure(v.unit.id===id,'Memory identity mismatch');return v;}
export function runResult(v:any,owner:string,id:string):any {closed(v,['opened','closed','head']);ensure(integer(v.head));record(v.opened,'event');ensure(v.opened.kind==='run.open'&&v.opened.payload.run_id===id&&v.opened.payload.agent_id===owner,'Run owner mismatch');if(v.closed!==null){record(v.closed,'run');ensure(v.closed.run_id===id&&v.closed.agent_id===owner,'Run owner mismatch');}return v;}
export function scoreResult(v:any,owner:string):any {validateJson(v as unknown);closed(v,['agent_id','groups','head']);ensure(v.agent_id===owner&&integer(v.head)&&Array.isArray(v.groups));const seen=new Set<string>();for(const g of v.groups){closed(g,['seat','memory_arm','runs','successes','unknown_costs','mean_cost_micro_usd','mean_duration_ms']);validate(g.seat,(agentSchema as any).properties.allowed_seats.items);ensure(['none','own','inherited'].includes(g.memory_arm));for(const k of ['runs','successes','unknown_costs'])ensure(integer(g[k]));ensure(g.successes<=g.runs&&g.unknown_costs<=g.runs);for(const k of ['mean_cost_micro_usd','mean_duration_ms'])ensure(g[k]===null||typeof g[k]==='number'&&Number.isFinite(g[k])&&g[k]>=0);const key=canonical([g.seat,g.memory_arm]);ensure(!seen.has(key),'Duplicate score group');seen.add(key);}return v;}
export const memoryKinds=['ruling','lesson','negative','workflow','episode','decision','open_item'];
export const levelNames:Record<string,string>={'1':'Level one — operator ruling','2':'Level two — receipt-backed','3':'Level three — observation'};
export function eligibility(u:any,a:any):string|null {if(u.level===1)return 'level one';if(u.level===3)return 'level three';if(u.privacy==='private')return 'private';if(u.status!=='active')return 'inactive';if(!['lesson','negative','workflow'].includes(u.kind))return u.kind==='episode'?'episode':'kind not inheritable';if(!u.receipts.length)return 'missing receipt';if(u.receipts.some((r:any)=>!validPath(r.path)||!isHash(r.sha256)))return 'invalid receipt';if(u.kind==='workflow'&&u.body.status!=='promoted')return 'workflow not promoted';if(u.scope.workflow!==a.workflow||!['general',a.language].includes(u.scope.language))return 'scope mismatch';return null;}
export function bodySchema(kind:string):any {return (memorySchema as any).allOf.find((x:any)=>x.if?.properties?.kind?.const===kind)?.then.properties.body;}
export const unitSchema:any=memorySchema;

export function sha256(text:string):string {
  const bytes=new TextEncoder().encode(text);const padded=new Uint8Array(Math.ceil((bytes.length+9)/64)*64);padded.set(bytes);padded[bytes.length]=0x80;
  const view=new DataView(padded.buffer);const bits=bytes.length*8;view.setUint32(padded.length-8,Math.floor(bits/4294967296));view.setUint32(padded.length-4,bits>>>0);
  const h=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
  const k=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
  const rotate=(x:number,n:number)=>(x>>>n)|(x<<(32-n));
  const w=new Uint32Array(64);
  for(let offset=0;offset<padded.length;offset+=64) {
    for(let i=0;i<16;i++) w[i]=view.getUint32(offset+i*4);
    for(let i=16;i<64;i++) {const a=w[i-15],b=w[i-2];w[i]=(rotate(a,7)^rotate(a,18)^(a>>>3))+w[i-16]+(rotate(b,17)^rotate(b,19)^(b>>>10))+w[i-7];}
    let [a,b,c,d,e,f,g,j]=h;
    for(let i=0;i<64;i++) {const t1=(j+(rotate(e,6)^rotate(e,11)^rotate(e,25))+((e&f)^(~e&g))+k[i]+w[i])|0;const t2=((rotate(a,2)^rotate(a,13)^rotate(a,22))+((a&b)^(a&c)^(b&c)))|0;j=g;g=f;f=e;e=(d+t1)|0;d=c;c=b;b=a;a=(t1+t2)|0;}
    [a,b,c,d,e,f,g,j].forEach((v,i)=>h[i]=(h[i]+v)>>>0);
  }
  return h.map(v=>v.toString(16).padStart(8,'0')).join('');
}
/** Shapes not stored as standalone record schemas retain their closed tool envelopes. */
export function resultShape(tool:string,v:any):void {
 validateJson(v as unknown);
 const t={type:'string',minLength:1};const hash={type:'string',pattern:'^[a-f0-9]{64}$'};const count={type:'integer',minimum:0,maximum:Number.MAX_SAFE_INTEGER};
 const object=(properties:Record<string,any>,optional:string[]=[])=>({type:'object',properties,required:Object.keys(properties).filter(k=>!optional.includes(k)),additionalProperties:false});
 const array=(items:any,maxItems=10000)=>({type:'array',items,maxItems});
 const evidence=object({path:{type:'string',minLength:1,maxLength:512},sha256:hash});
 const check=object({id:t,passed:{type:'boolean'},detail:t},['detail']);
 const inherited=object({unit:{$ref:'mem_unit.schema.json'},source_agent_id:t,source_unit_id:t,unit_sha256:hash});
 const rejected=object({agent_id:t,unit_id:t,reason:{enum:['episode','level_one','level_three','private','missing_receipt','invalid_receipt','not_promoted','scope_mismatch','not_selected','inactive','kind_not_inheritable']}});
 const commit=object({event_ids:{...array(t),minItems:1,uniqueItems:true},head:{...count,minimum:1},sha256:hash});
 const shapes:Record<string,any>={
  agent_get:object({record:{$ref:'agent.schema.json'}}),
  agent_list:object({agents:array({$ref:'agent.schema.json'}),next_after:{anyOf:[t,{type:'null'}]},head:count}),
  agent_brief:object({agent_id:t,agent_version:hash,text:{type:'string'},sha256:hash,memory_gen:count}),
  reference_get:object({reference:object({id:{enum:['gold_s1','memory_v21']},sha256:hash,bytes:{...count,minimum:1},rules:array(object({id:t,section:t,text:t}))})}),
  reference_verify:object({ref_id:{enum:['gold_s1','memory_v21']},sha256:hash,bytes:{...count,minimum:1},valid:{const:true}}),
  skill_list:object({skills:array(object({skill_id:t,sha256:hash,retired:{type:'boolean'}}))}),
  skill_get:object({skill:object({skill_id:t,sha256:hash,retired:{type:'boolean'},files:{...array(object({path:t,content:{type:'string'}}),256),minItems:1}})}),
  memory_get:object({unit:{$ref:'mem_unit.schema.json'},head:count}),
  memory_route:object({units:array({$ref:'mem_unit.schema.json'},100),answer:{type:'string'},head:count}),
  memory_bootcheck:object({passed:{const:true},code:{const:'OK'},checks:{...array(check),minItems:1},head:count}),
  run_get:object({opened:{$ref:'event.schema.json'},closed:{anyOf:[{$ref:'run.schema.json'},{type:'null'}]},head:count}),
  memory_put:object({unit:{$ref:'mem_unit.schema.json'},memory_gen:count,commit}),
  run_open:object({opened:{$ref:'event.schema.json'},commit}),
  run_beat:object({event:{$ref:'event.schema.json'},commit}),
  run_close:object({run:{$ref:'run.schema.json'},commit}),
  agent_retire:object({record:{$ref:'agent.schema.json'},commit}),
  agent_promote:object({record:{$ref:'agent.schema.json'},commit}),
 };
 for(const name of ['clone','distill','cross','mutate','specialize'])shapes['agent_'+name]=object({record:{$ref:'agent.schema.json'},inherited_units:array(inherited,256),rejected_units:array(rejected),commit});
 if(shapes[tool])validate(v,shapes[tool]);
 const walk=(x:any):void=>{if(!x||typeof x!=='object')return;if(Object.hasOwn(x,'path'))ensure(validPath(x.path,tool!=='skill_get'),'Invalid evidence or package path');for(const child of Object.values(x))walk(child);};walk(v);
 // These types carry semantic uniqueness beyond JSON syntax.
 if(tool==='agent_get')record(v.record,'agent');
 if(tool==='agent_list')v.agents.forEach((a:any)=>record(a,'agent'));
 if(tool==='memory_get'||tool==='memory_put')record(v.unit,'memory');
 if(tool==='memory_route'){v.units.forEach((u:any)=>record(u,'memory'));ensure(v.units.every((u:any)=>u.privacy!=='private'),'Invalid private routing result');}
}
