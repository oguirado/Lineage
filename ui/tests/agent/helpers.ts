import {afterEach,beforeEach,expect,vi} from 'vitest';
import type {AppState,AppStore,ScreenContext,MountedScreen,Route,JsonValue,JsonObject,CallOptions} from '../../src/ui/contracts.ts';
import {TransportError} from '../../src/transport.ts';
import {identityKey} from '../../src/ui/primitives.ts';
import {agent,birth,canonical,closed,CLOCK,constitution,cost,descriptors,eid,event,evidence,group,H,hash,opening,OTHER,OWNER,RUN,schema,seat,task,unit,UNIT} from './fixtures.ts';
export {identityKey};
vi.setConfig({testTimeout:4000,hookTimeout:4000});
export const clone=<T>(v:T):T=>JSON.parse(JSON.stringify(v));
export function deferred<T=any>() {let resolve!:(value:T)=>void,reject!:(reason:unknown)=>void;const promise=new Promise<T>((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
export async function flush(){for(let i=0;i<100;i++) await Promise.resolve();}
export function refuse(code:string,detail=code):never {throw new TransportError('domain',code,detail);}
export function schemaCheck(value:any,s:any):void {
 if(s.$ref){schemaCheck(value,schema(s.$ref));return;}
 if(s.anyOf){expect(s.anyOf.some((x:any)=>{try{schemaCheck(value,x);return true;}catch{return false;}}),'closed union').toBe(true);return;}
 if(s.const!==undefined) expect(value).toEqual(s.const);
 if(s.enum) expect(s.enum).toContainEqual(value);
 if(s.type==='object'||((s.properties||s.required||s.additionalProperties!==undefined)&&value!==null&&typeof value==='object'&&!Array.isArray(value))) {expect(value).not.toBeNull();expect(Array.isArray(value)).toBe(false);expect(typeof value).toBe('object');
  for(const k of s.required??[]) expect(Object.hasOwn(value,k),'required '+k).toBe(true);
  for(const k of Object.keys(value)){if(s.additionalProperties===false) expect(Object.keys(s.properties??{}),'closed field '+k).toContain(k);if(s.properties?.[k])schemaCheck(value[k],s.properties[k]);}}
 if(s.type==='array'||(Array.isArray(value)&&(s.items||s.minItems!==undefined||s.maxItems!==undefined||s.uniqueItems))){expect(Array.isArray(value)).toBe(true);if(s.minItems!==undefined)expect(value.length).toBeGreaterThanOrEqual(s.minItems);if(s.maxItems!==undefined)expect(value.length).toBeLessThanOrEqual(s.maxItems);if(s.items)for(const v of value)schemaCheck(v,s.items);if(s.uniqueItems)expect(new Set(value.map(canonical)).size).toBe(value.length);}
 if(s.type==='string'){expect(typeof value).toBe('string');if(s.minLength!==undefined)expect([...value].length).toBeGreaterThanOrEqual(s.minLength);if(s.maxLength!==undefined)expect([...value].length).toBeLessThanOrEqual(s.maxLength);if(s.pattern)expect(value).toMatch(new RegExp(s.pattern));}
 if(s.type==='integer') {expect(Number.isSafeInteger(value)).toBe(true);}
 if(s.type==='number')expect(typeof value==='number'&&Number.isFinite(value)).toBe(true);
 if(s.type==='null')expect(value).toBeNull();if(s.type==='boolean')expect(typeof value).toBe('boolean');
 if(s.minimum!==undefined)expect(value).toBeGreaterThanOrEqual(s.minimum);if(s.maximum!==undefined)expect(value).toBeLessThanOrEqual(s.maximum);
 for(const x of s.allOf??[]){if(x.if){let match=true;try{schemaCheck(value,x.if);}catch{match=false;}if(match&&x.then)schemaCheck(value,x.then);else if(!match&&x.else)schemaCheck(value,x.else);}else schemaCheck(value,x);}
 if(s.not){let accepted=true;try{schemaCheck(value,s.not);}catch{accepted=false;}expect(accepted,'forbidden schema').toBe(false);}
}
export class Service {
 record=agent();units:any[]=[unit()];groups:any[]=[group()];history:any[]=[];ledger:any[]=[];runs=new Map<string,any>();head=2;
 overrides=new Map<string,(args:any,options:CallOptions)=>any>();descriptors=clone(descriptors);mode:'live'|'fixture'='live';
 constructor(){this.ledger=[birth(this.record),event(2,'memory.put',{agent_id:OWNER,unit:this.units[0]})];this.history=[...this.ledger];}
 page(events:any[],args:any={}){const after=args.after??0;if(after>this.head)return {events:[],next_after:0,head:this.head,has_more:false,resync:true};
  // Cursor progress covers scanned nonmatching events, as K0 requires.
  const end=Math.min(this.head,after+(args.limit??100));const selected=events.filter(e=>e.lamport>after&&e.lamport<=end&&(!args.kinds||args.kinds.includes(e.kind)));
  return {events:clone(selected),next_after:end,head:this.head,has_more:end<this.head,resync:false};}
 transport:any={mode:'live',fixtureId:null,presentation:null,tools:vi.fn(async()=>clone(this.descriptors)),
  events:vi.fn(async(after:number)=>this.page(this.ledger,{after})),
  call:vi.fn(async(tool:string,args:JsonObject,options:CallOptions)=>{
   const descriptor=this.descriptors.find(d=>d.name===tool);expect(descriptor,'only documented tool '+tool).toBeDefined();schemaCheck(args,descriptor!.inputSchema);
   const write=Service.mutations.has(tool);expect(options.mutation).toBe(write);expect(options.signal).toBeInstanceOf(AbortSignal);
   if(this.mode==='fixture'&&write)refuse('fixture_readonly');
   const override=this.overrides.get(tool);if(override)return override(args,options);
   return this.read(tool,args);
  })};
 static mutations=new Set(['memory_put','run_open','run_beat','run_close','agent_clone','agent_distill','agent_cross','agent_mutate','agent_specialize','agent_retire','agent_promote']);
 calls(tool:string){return this.transport.call.mock.calls.filter((x:any[])=>x[0]===tool);}
 read(tool:string,args:any):any {switch(tool){
  case 'agent_get':if(args.agent_id!==this.record.agent_id)refuse('no_agent');return {record:clone(this.record)};
  case 'ledger_events':return this.page(this.ledger,args);
  case 'memory_history':return this.page(this.history,args);
  case 'memory_get':{const u=this.units.find(x=>x.id===args.unit_id);if(!u)refuse('bad_args');return {unit:clone(u),head:this.head};}
  case 'scorecard_get':return {agent_id:this.record.agent_id,groups:clone(this.groups),head:this.head};
  case 'reference_get':return {reference:{id:args.ref_id,sha256:args.ref_id==='gold_s1'?H:OTHER,bytes:100,rules:args.ref_id==='gold_s1'?[{id:'I1',section:'§1',text:'Synthetic rule [CITED; §1:L1-L2].'}]:[]}};
  case 'reference_verify':return {ref_id:args.ref_id,sha256:args.ref_id==='gold_s1'?H:OTHER,bytes:100,valid:true};
  case 'skill_list':return {skills:[{skill_id:'review-skill',sha256:H,retired:false}]};
  case 'skill_get':return {skill:{skill_id:args.skill_id,sha256:args.sha256,retired:true,files:[{path:'SKILL.md',content:'Synthetic skill content'}]}};
  case 'agent_brief':return {agent_id:this.record.agent_id,agent_version:this.record.agent_version,text:'SERVER BRIEF\n',sha256:hash('SERVER BRIEF\n'),memory_gen:this.record.memory_gen};
  case 'memory_route':return {units:[],answer:'NOT IN MEMORY',head:this.head};
  case 'memory_bootcheck':return {passed:true,code:'OK',checks:[{id:'synthetic-check',passed:true}],head:this.head};
  case 'run_get':{const r=this.runs.get(args.run_id);if(!r)refuse('no_run');return {...clone(r),head:this.head};}
  case 'agent_list':return {agents:[clone(this.record),agent({agent_id:'other-parent',language:'general'})],next_after:null,head:this.head};
  default:refuse('internal','Unexpected synthetic mutation; test must define its authoritative result.');}}
 addRun(){const opened=opening();this.ledger.push(opened);this.head=3;this.runs.set(RUN,{opened,closed:null});return opened;}
 commit(tool:string,args:any,payload:any,kind:string,n=this.head+1){const e=event(n,kind,payload,{agent:args.agent,op_id:args.op_id,request_sha256:hash(canonical({tool,args}))});this.ledger.push(e);this.head=n;return {event:e,commit:{event_ids:[e.id],head:n,sha256:e.sha256}};}
}
const owned:{dispose():void}[]=[];
export function isolate(){beforeEach(()=>{document.body.replaceChildren();document.documentElement.dataset.linReady='false';document.documentElement.removeAttribute('data-lin-rev');vi.useFakeTimers();vi.setSystemTime(CLOCK);vi.stubGlobal('fetch',vi.fn(()=>{throw Error('Network forbidden in oracle');}));});
 afterEach(()=>{for(const m of owned.splice(0).reverse())m.dispose();document.body.replaceChildren();vi.restoreAllMocks();vi.unstubAllGlobals();vi.useRealTimers();});}
export async function mount(service=new Service(),query:Record<string,string>={},actor:string|null=OWNER){
 const {screen}=await import('../../src/screens/agent/index.ts');
 const shell=document.createElement('div'),host=document.createElement('main');host.dataset.linScreen='agent';host.id='main-content';host.tabIndex=-1;
 let actorSelect:HTMLSelectElement|null=null;
 if(actor!==null){actorSelect=document.createElement('select');actorSelect.dataset.linAction='select-actor';actorSelect.setAttribute('aria-label','Acting agent');
  for(const a of new Set([OWNER,'other-owner','operator','system',actor])){const o=document.createElement('option');o.value=a;o.textContent=a;actorSelect.append(o);}actorSelect.value=actor;shell.append(actorSelect);}
 const status=document.createElement('div');status.setAttribute('role','status');status.setAttribute('aria-label','Application updates');shell.append(host,status);document.body.append(shell);
 const controller=new AbortController();let state:AppState={phase:'ready',stale:false,route:{screen:'agent',agentId:service.record.agent_id,query},mode:service.mode,fixtureId:null,tools:service.descriptors,events:[],head:service.head,error:null,selection:{},expanded:[]};
 const listeners=new Set<(s:AppState)=>void>();
 const store:AppStore={getState:()=>state,subscribe:vi.fn(listener=>{listeners.add(listener);return()=>listeners.delete(listener);}),refresh:vi.fn(async()=>{state={...state,head:service.head};for(const l of listeners)l(state);}),setRoute:r=>{state={...state,route:r};},
  setSelection:vi.fn(),setExpanded:vi.fn(),dispose:()=>listeners.clear()};
 const navigate=vi.fn((r:Route)=>{state={...state,route:r};});const announce=vi.fn((_key:string,message:string)=>{status.textContent=message;});
 service.transport.mode=service.mode;service.transport.fixtureId=service.mode==='fixture'?'demo':null;
 service.transport.presentation=service.mode==='fixture'?{clockMs:CLOCK,locale:'en-GB',timezone:'UTC',theme:'light'}:null;
 const context:ScreenContext={route:state.route,transport:service.transport,store,signal:controller.signal,navigate,announce};
 const mounted=screen.mount(host,context);owned.push(mounted);const readiness=mounted.ready.then(()=>({ok:true as const}),error=>({ok:false as const,error}));
 await flush();
 return {host,shell,status,service,store,context,mounted,readiness,controller,actorSelect,navigate,announce,listeners,
  emit(changes:Partial<AppState>){state={...state,...changes};for(const l of listeners)l(state);},
  async update(query2=query){const c={...context,route:{screen:'agent' as const,agentId:service.record.agent_id,query:query2}};await mounted.update(c);await flush();}};
}
export type View=Awaited<ReturnType<typeof mount>>;
export async function ready(v:View){const r=await v.readiness;if(!r.ok)throw r.error;await flush();}
export function action(root:ParentNode,name:string,id?:string):HTMLElement {
 const all=Array.from(root.querySelectorAll<HTMLElement>('[data-lin-action]')).filter(e=>e.dataset.linAction===name&&(!id||e.closest('[data-lin-id]')?.getAttribute('data-lin-id')===id)&&!e.closest('[hidden]'));
 expect(all,'Missing/ambiguous U23 feature: '+name+(id?' '+id:'')).toHaveLength(1);return all[0];
}
export async function click(root:ParentNode,name:string,id?:string){const el=action(root,name,id);el.click();await flush();return el;}
export function name(el:Element):string {if(el.hasAttribute('aria-label'))return el.getAttribute('aria-label')!;if(el.hasAttribute('aria-labelledby'))return el.getAttribute('aria-labelledby')!.split(/\s+/).map(x=>document.getElementById(x)?.textContent??'').join(' ');if(el instanceof HTMLInputElement||el instanceof HTMLSelectElement)return Array.from(el.labels??[]).map(l=>l.textContent).join(' ');return el.textContent??'';}
export function set(root:ParentNode,path:string,value:any){const nodes=Array.from(root.querySelectorAll<HTMLInputElement|HTMLSelectElement>('[name]')).filter(n=>n.name===path);expect(nodes,'K0 field '+path).toHaveLength(1);const n=nodes[0];if(n instanceof HTMLInputElement&&n.type==='checkbox')n.checked=Boolean(value);else n.value=String(value);n.dispatchEvent(new Event('input',{bubbles:true}));n.dispatchEvent(new Event('change',{bubbles:true}));return n;}
export function dialog(v:View){const ds=Array.from(v.host.querySelectorAll<HTMLDialogElement>('dialog')).filter(e=>e.open||e.hasAttribute('open'));expect(ds,'one exposed shared dialog').toHaveLength(1);return ds[0];}
export async function submit(v:View){await click(dialog(v),'submit-dialog');}
export async function closeDraft(v:View){await click(v.host,'close-run',RUN);const d=dialog(v);set(d,'outcome.verdict','HOLD');set(d,'outcome.repair_loops',1);set(d,'outcome.findings.confirmed',1);set(d,'outcome.findings.refuted',0);
 for(const k of Object.keys(cost)){const f=d.querySelector(`[name="cost.${k}"]`);expect(f,'explicit unknown '+k).not.toBeNull();if(f instanceof HTMLSelectElement){const unknown=Array.from(f.options).find(o=>/unknown|not measured|null/i.test(o.label));expect(unknown).toBeDefined();set(d,'cost.'+k,unknown!.value);}else if(f instanceof HTMLInputElement)set(d,'cost.'+k,'');}return d;}
export async function memoryDraft(v:View,kind='lesson'){await click(v.host,'write-memory');const d=dialog(v);const u=unit(kind);set(d,'unit.kind',kind);await flush();
 for(const [path,value] of Object.entries({'unit.id':UNIT,'unit.level':u.level,'unit.statement':u.statement,'unit.privacy':u.privacy,'unit.status':u.status,'unit.scope.workflow':'review','unit.scope.language':'python','unit.provenance.origin':'synthetic fixture'}))set(d,path,value);
 return d;}
export function writes(v:View,tool?:string){return v.service.transport.call.mock.calls.filter((x:any[])=>x[2]?.mutation&&(!tool||x[0]===tool));}
export function messages(v:View){return v.announce.mock.calls.map(x=>x[1]);}
export function noSuccess(v:View){expect(messages(v).filter(m=>/recorded for/u.test(m))).toEqual([]);}

export function installUnits(s:Service,units:any[]){s.units=units;s.ledger=[birth(s.record),...units.map((u,i)=>event(i+2,'memory.put',{agent_id:s.record.agent_id,unit:u}))];s.history=[...s.ledger];s.head=units.length+1;}
export function record(root:ParentNode,id:string){const nodes=Array.from(root.querySelectorAll<HTMLElement>('[data-lin-entity][data-lin-id]')).filter(e=>e.dataset.linId===id&&!e.closest('[hidden]'));expect(nodes.length,'record '+id).toBeGreaterThan(0);return nodes.find(e=>e.querySelector('[data-lin-action]'))??nodes[0];}

export async function addEvidence(d:HTMLElement,prefix='receipt',path=evidence.path){set(d,prefix+'.path',path);set(d,prefix+'.sha256',H);const add=Array.from(d.querySelectorAll<HTMLButtonElement>('[data-lin-action="add-item"]')).filter(b=>name(b).trim()==='Add evidence');expect(add).toHaveLength(1);add[0].click();await flush();}
export async function completeMemory(v:View,kind='lesson'){
 const d=await memoryDraft(v,kind),u=unit(kind);
 if(kind==='episode'){set(d,'run_id',RUN);await flush();}
 for(const [k,val] of Object.entries(u.body)){
  if(Array.isArray(val)){if(k==='steps'){const editor=Array.from(d.querySelectorAll<HTMLInputElement>('[name]')).find(e=>e.name==='steps.new'||e.name==='unit.body.steps.new');expect(editor,'native step item editor').toBeDefined();editor!.value='Read the witness';editor!.dispatchEvent(new Event('input',{bubbles:true}));const add=Array.from(d.querySelectorAll<HTMLButtonElement>('[data-lin-action="add-item"]')).find(e=>name(e).trim()==='Add steps');expect(add).toBeDefined();add!.click();await flush();}continue;}
  if(val&&typeof val==='object'){for(const [leaf,x] of Object.entries(val)){if(x&&typeof x==='object')continue;const path='unit.body.'+k+'.'+leaf;const el=Array.from(d.querySelectorAll<HTMLInputElement|HTMLSelectElement>('[name]')).find(e=>e.name===path);if(kind==='episode'&&(k==='seat')){expect(el?.value).toBe(String(x));expect(el?.hasAttribute('readonly')||(el as HTMLSelectElement)?.disabled).toBe(true);}else if(x!==null)set(d,path,x);}}
  else if(kind==='episode'&&(k==='run_id'||k==='task_id')){const el=d.querySelector(`[name="unit.body.${k}"]`) as HTMLInputElement;expect(el?.value).toBe(val);expect(el.readOnly||el.disabled).toBe(true);}
  else set(d,'unit.body.'+k,val);
 }
 await addEvidence(d);return d;
}
export function failureMemory(s:Service){for(const kind of ['episode','lesson','negative']){const u=unit(kind,{id:'unit-'+kind,provenance:{origin:'synthetic failure',actor:OWNER,run_id:RUN}});s.units.push(u);s.ledger.push(event(++s.head,'memory.put',{agent_id:OWNER,run_id:RUN,unit:u}));}s.history=[...s.ledger];}
