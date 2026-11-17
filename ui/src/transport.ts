import { forbiddenKeys, panelStates, type JsonValue, type JsonObject, type ToolDescriptor, type EventsPage, type Transport, type RequestOptions, type CallOptions, type UiFixture } from './ui/contracts.ts';
export type { Transport, UiFixture } from './ui/contracts.ts';
export interface HttpOptions {fetchImpl:typeof fetch;sessionToken:string|null;timeoutMs:number}
export class TransportError extends Error {
  readonly name='TransportError';
  readonly httpStatus?:number; readonly detail?:JsonValue;
  constructor(readonly source:'transport'|'domain',readonly code:string,message:string,options?:{httpStatus?:number;detail?:JsonValue}) {
    super(message); this.httpStatus=options?.httpStatus; this.detail=options?.detail;
  }
}
const domainCodes = new Set('bad_args bad_op stale_rev busy internal conflict no_agent no_run run_closed memory_required memory_debt forbidden_level not_inheritable hash_mismatch rule_not_declared no_benchmark heldout_forbidden seat_not_allowed fixture_readonly timeout'.split(' '));
const reads = new Set('reference_get reference_verify skill_list skill_get agent_get agent_list agent_brief lineage_tree memory_route memory_get memory_bootcheck memory_history run_get bench_list bench_status scorecard_get ledger_events ledger_verify'.split(' '));
const protectedTools = new Set('skill_publish skill_retire agent_create agent_clone agent_distill agent_cross agent_mutate agent_specialize agent_retire agent_promote memory_put run_open run_beat run_close bench_declare bench_run bench_verdict ledger_export openfresnel_probe openfresnel_spawn'.split(' '));
export const invalidResponse = () => new TransportError('transport','invalid_response','The service returned an invalid response.');
const badArgs = () => new TransportError('domain','bad_args','The request arguments are invalid.');
const aborted = () => new TransportError('transport','aborted','Request cancelled.');
export function isObject(v:unknown):v is Record<string,unknown> {return v!==null && typeof v==='object' && !Array.isArray(v);}
export function keysExactly(value:Record<string,unknown>,required:readonly string[],optional:readonly string[]=[]):boolean {
  return required.every(k=>Object.hasOwn(value,k)) && Object.keys(value).every(k=>required.includes(k)||optional.includes(k));
}
const validString = (s:string):boolean => {
  for (let i=0;i<s.length;i++) {
    const c=s.charCodeAt(i);
    if (c>=0xd800 && c<=0xdbff) {const next=s.charCodeAt(++i);if (!(next>=0xdc00 && next<=0xdfff)) return false;}
    else if (c>=0xdc00 && c<=0xdfff) return false;
  }
  return true;
};
export function validateJson(value:unknown):asserts value is JsonValue {
  const seen=new Set<object>();
  const visit=(v:unknown,depth:number):void => {
    if (depth>128) throw invalidResponse();
    if (v===null || typeof v==='boolean') return;
    if (typeof v==='string') {if (!validString(v)) throw invalidResponse();return;}
    if (typeof v==='number') {if (!Number.isFinite(v)) throw invalidResponse();return;}
    if (typeof v!=='object' || seen.has(v)) throw invalidResponse();
    seen.add(v);
    if (Array.isArray(v)) v.forEach(x=>visit(x,depth+1));
    else {
      if (![Object.prototype,null].includes(Object.getPrototypeOf(v))) throw invalidResponse();
      for(const [k,x] of Object.entries(v)) {if(forbiddenKeys.has(k)||!validString(k)) throw invalidResponse();visit(x,depth+1);}
    }
    seen.delete(v);
  };
  visit(value,0);
}
const safeInt=(v:unknown):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0;
const hash=(v:unknown)=>typeof v==='string'&&/^[a-f0-9]{64}$/u.test(v);
export function validateTools(value:unknown):asserts value is readonly ToolDescriptor[] {
  validateJson(value);
  if (!Array.isArray(value) || value.some(v=>!isObject(v)||!keysExactly(v,['name','description','inputSchema'],['annotations'])||('annotations' in v&&!isObject(v.annotations))||typeof v.name!=='string'||!v.name||typeof v.description!=='string'||!isObject(v.inputSchema))) throw invalidResponse();
  if (new Set(value.map(v=>(v as unknown as ToolDescriptor).name)).size!==value.length) throw invalidResponse();
}
export function validatePage(value:unknown):asserts value is EventsPage {
  validateJson(value);
  if (!isObject(value)||!keysExactly(value,['events','next_after','head','has_more','resync']) || !Array.isArray(value.events) || !safeInt(value.next_after)||!safeInt(value.head)||value.next_after>value.head||typeof value.has_more!=='boolean'||typeof value.resync!=='boolean') throw invalidResponse();
  if (value.resync && (value.events.length>0||value.has_more||value.next_after!==0)) throw invalidResponse();
  let previous=0; const ids=new Set<string>();
  for (const e of value.events) {
    if (!isObject(e)||!keysExactly(e,['schema','id','lamport','ts','ledger','agent','kind','payload','op_id','request_sha256','evidence','prev_sha256','sha256'])||e.schema!=='lineage.event/v1'||e.ledger!=='main'||!safeInt(e.lamport)||e.lamport<=previous||e.lamport>value.next_after||!safeInt(e.ts)||!isObject(e.payload)||!Array.isArray(e.evidence)||!hash(e.request_sha256)||!hash(e.prev_sha256)||!hash(e.sha256)) throw invalidResponse();
    for (const field of ['id','agent','kind','op_id']) if (typeof e[field]!=='string'||!e[field]) throw invalidResponse();
    if (ids.has(e.id as string)) throw invalidResponse(); ids.add(e.id as string);
    for(const ev of e.evidence) if (!isObject(ev)||!keysExactly(ev,['path','sha256'])||typeof ev.path!=='string'||!ev.path||!hash(ev.sha256)||!/^[A-Za-z0-9_.\/-]+$/u.test(ev.path)||ev.path.startsWith('/')||ev.path.split('/').some(s=>!s||s==='.'||s==='..')) throw invalidResponse();
    previous=e.lamport;
  }
}
export function canonical(value:JsonValue):string {
  if (Array.isArray(value)) return '['+value.map(canonical).join(',')+']';
  if (isObject(value)) return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k] as JsonValue)).join(',')+'}';
  return JSON.stringify(value);
}
function decodeReply(value:unknown,httpStatus?:number,secret:string|null=null):JsonValue {
  validateJson(value);
  if(!isObject(value)) throw invalidResponse();
  if (keysExactly(value,['untrusted'])) return value.untrusted as JsonValue;
  if(keysExactly(value,['ok','code'],['detail'])&&value.ok===false&&typeof value.code==='string'&&domainCodes.has(value.code)&&(!Object.hasOwn(value,'detail')||typeof value.detail==='string')) {
    // Handler detail is passive. Do not expose credentials or private implementation coordinates.
    let detail=typeof value.detail==='string'?value.detail:undefined;
    if(detail) {if(secret) detail=detail.split(secret).join('[redacted]');detail=detail.replace(/\/(?:home|Users|tmp|var)\/[^\s]+/gu,'[redacted]').replace(/\b(?:Error|Traceback):[^\n]*/gu,'[redacted]');}
    throw new TransportError('domain',value.code,`Request refused: ${value.code}.`,{httpStatus,detail});
  }
  throw invalidResponse();
}
function checkCall(tool:string,args:JsonObject,options:CallOptions,fixture:boolean):void {
  if (fixture && (options.mutation||!reads.has(tool))) throw new TransportError('domain','fixture_readonly','Synthetic fixtures. Changes are unavailable.');
  if (reads.has(tool)&&options.mutation) throw badArgs();
  if (!reads.has(tool)&&!protectedTools.has(tool)) throw badArgs();
  if(protectedTools.has(tool)&&!options.mutation) throw badArgs();
  try {validateJson(args);if(!isObject(args)) throw badArgs();} catch {throw badArgs();}
  if (tool==='memory_put' && (args.agent==='operator'||(isObject(args.unit)&&args.unit.level===1))) throw new TransportError('domain','forbidden_level','Level one is reserved for operator rulings.');
}
export function createHttpTransport({fetchImpl,sessionToken,timeoutMs}:HttpOptions):Transport {
  if(!Number.isSafeInteger(timeoutMs)||timeoutMs<=0) throw new TransportError('transport','invalid_config','A positive request timeout is required.');
  async function request(url:string,init:RequestInit,options:RequestOptions={}):Promise<unknown> {
    if(options.signal?.aborted) throw aborted();
    const controller=new AbortController(); let timer:ReturnType<typeof setTimeout>|undefined;
    let rejectAbort:(error:TransportError)=>void=()=>{};
    const cancelled=new Promise<never>((_resolve,reject)=>{rejectAbort=reject;});
    const cancel=()=>{controller.abort();rejectAbort(aborted());};
    options.signal?.addEventListener('abort',cancel,{once:true});
    timer=setTimeout(()=>{controller.abort();rejectAbort(new TransportError('transport','timeout','Request timed out.'));},timeoutMs);
    try {
      const work=(async()=>{
        let res:Response;
        try {res=await fetchImpl(url,{...init,credentials:'same-origin',redirect:'error',signal:controller.signal});}
        catch {if(controller.signal.aborted) throw aborted();throw new TransportError('transport','network','The service could not be reached.');}
        if(controller.signal.aborted) throw aborted();
        let body:unknown;
        try {body=await res.json();} catch {throw res.ok?invalidResponse():new TransportError('transport','http','The service request failed.',{httpStatus:res.status});}
        if(controller.signal.aborted) throw aborted();
        if(!res.ok) {
          if (isObject(body)&&Object.hasOwn(body,'ok')) {try {decodeReply(body,res.status,sessionToken);} catch(error) {if(error instanceof TransportError && error.source==='domain') throw error;}}
          throw new TransportError('transport','http','The service request failed.',{httpStatus:res.status});
        }
        return body;
      })();
      return await Promise.race([work,cancelled]);
    } finally {clearTimeout(timer);options.signal?.removeEventListener('abort',cancel);}
  }
  return {mode:'live',fixtureId:null,presentation:null,
    async tools(options) {const body=await request('/api/tools',{method:'GET'},options);if(!isObject(body)||!keysExactly(body,['tools'])) throw invalidResponse();validateTools(body.tools);return body.tools;},
    async events(after,options={}) {
      const wait=options.waitMs??0;if(!safeInt(after)||!safeInt(wait)||wait>30000) throw badArgs();
      const body=await request(`/api/events?after=${after}&wait_ms=${wait}`,{method:'GET'},options);
      // Integrated HTTP hosts retain the dispatch wrapper on the cursor route.
      const page=isObject(body)&&keysExactly(body,['untrusted'])?decodeReply(body,undefined,sessionToken):body;
      validatePage(page);return page;
    },
    async call<T extends JsonValue>(tool:string,args:JsonObject,options:CallOptions):Promise<T> {
      if(options.signal?.aborted) throw aborted(); checkCall(tool,args,options,false);
      if(options.mutation && !sessionToken) throw new TransportError('transport','session_required','This operation requires a session.');
      const headers:Record<string,string>={'Content-Type':'application/json'};
      if(sessionToken) headers['X-Lineage-Session']=sessionToken;
      const body=await request('/api/call',{method:'POST',headers,body:JSON.stringify({tool,args})},options);
      return decodeReply(body,undefined,sessionToken) as T;
    },
  };
}
export function createFixtureTransport(input:UiFixture):Transport {
  try {
    validateJson(input);
    if(!isObject(input)||!keysExactly(input,['schema','id','clock_ms','tools','page','results','panels'],['locale','timezone','theme'])||input.schema!=='lineage.ui.fixture/v1'||!['demo','empty','hostile'].includes(input.id)||!safeInt(input.clock_ms)) throw invalidResponse();
    if(input.locale!==undefined&&input.locale!=='en-GB'||input.timezone!==undefined&&input.timezone!=='UTC'||input.theme!==undefined&&!['light','dark'].includes(input.theme)) throw invalidResponse();
    validateTools(input.tools); validatePage(input.page);
    if(input.page.resync||input.page.has_more||input.page.next_after!==input.page.head||!Array.isArray(input.results)||!Array.isArray(input.panels)) throw invalidResponse();
    const matches=new Set<string>();
    for(const result of input.results) {
      if(!isObject(result)||!keysExactly(result,['tool','args','reply'])||!reads.has(result.tool)||!isObject(result.args)) throw invalidResponse();
      const key=result.tool+canonical(result.args);if(matches.has(key)) throw invalidResponse();matches.add(key);
      try {decodeReply(result.reply);} catch(error) {if(!(error instanceof TransportError)||error.source!=='domain') throw error;}
    }
    const ids=new Set<string>();
    for(const panel of input.panels) {
      if(!isObject(panel)||!keysExactly(panel,['id','state','title'],['detail'])||!panel.id||ids.has(panel.id)||!panelStates.includes(panel.state)||typeof panel.title!=='string'||panel.detail!==undefined&&typeof panel.detail!=='string') throw invalidResponse();ids.add(panel.id);
    }
  } catch {throw new TransportError('transport','invalid_config','The fixture configuration is invalid.');}
  const fixture=structuredClone(input);
  const presentation=Object.freeze({clockMs:fixture.clock_ms,locale:'en-GB' as const,timezone:'UTC' as const,theme:fixture.theme??'light' as const});
  const check=(options?:RequestOptions)=>{if(options?.signal?.aborted) throw aborted();};
  return {mode:'fixture',fixtureId:fixture.id,presentation,
    async tools(options) {check(options);return structuredClone(fixture.tools);},
    async events(after,options={}) {
      check(options);if(!safeInt(after)||!safeInt(options.waitMs??0)||(options.waitMs??0)>30000) throw badArgs();
      if(after>fixture.page.head) return {events:[],next_after:0,head:fixture.page.head,has_more:false,resync:true};
      return {...structuredClone(fixture.page),events:structuredClone(fixture.page.events.filter(e=>e.lamport>after))};
    },
    async call<T extends JsonValue>(tool:string,args:JsonObject,options:CallOptions):Promise<T> {
      check(options);checkCall(tool,args,options,true);
      const result=fixture.results.find(r=>r.tool===tool&&canonical(r.args)===canonical(args));if(!result) throw badArgs();
      return structuredClone(decodeReply(result.reply)) as T;
    },
  };
}
