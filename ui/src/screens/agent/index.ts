import '../../../styles/agent.css';
import type {ScreenModule,ScreenContext,ToolDescriptor} from '../../ui/contracts.ts';
import {checkedName,identityKey} from '../../ui/primitives.ts';
import {captureFocus,restoreFocus} from '../../ui/keyboard.ts';
import {closeDialogsWithin} from '../../ui/dialog.ts';
import {validateJson} from '../../transport.ts';
import {brief,constitution,el,errorText,identity,panels,renderConstitution,renderSkills,text,outcome,type Panel,type Runtime} from './panels.ts';
import {memory,renderMemory} from './memory.ts';
import {scorecard,renderScorecard} from './scorecard.ts';
import {runs,renderRuns} from './runs.ts';
import {canonical,closed,cursor,ensure,isAgentId,record,resultShape,validate} from './wire.ts';
import {openForm,type Drafts} from './forms.ts';
import {execute,type OperationDraft} from './actions.ts';
class HeadRace extends Error {constructor(){super('Data is stale. Ledger prefix changed; refresh required.');}}
class AgentScreen implements Runtime {
 a:any=null;referenceId?:string;head:number|null=null;query:Record<string,string>={};search='';expanded=new Set<string>();states:Runtime['states']={};
 context:ScreenContext;signal:AbortSignal;private owned=new AbortController();private epoch=0;private disposed=false;private unsubscribe:()=>void;private detach:()=>void=()=>{};
 private feedbackNode=el('p');private ack:number|null=null;private stale=false;private collision=false;private notice='';private feedbackText='';private drafts:Drafts=new Map();private announcements=new Set<string>();private tools:readonly ToolDescriptor[]=[];
 constructor(readonly host:HTMLElement,context:ScreenContext){this.feedbackNode.className='agent-feedback-global';this.context=context;this.signal=this.owned.signal;this.unsubscribe=context.store.subscribe(s=>{if(this.disposed||this.signal.aborted)return;if(this.ack!==null&&s.head!==this.ack){this.stale=true;if(!host.querySelector('dialog'))this.render();}});}
 button(action:string,name:string,fn:(button:HTMLButtonElement)=>void):HTMLButtonElement {const b=el('button',checkedName(name));b.type='button';b.dataset.linAction=action;b.disabled=this.collision;b.addEventListener('click',()=>{if(!b.disabled&&!this.disposed&&!this.signal.aborted)fn(b);});return b;}
 announce(key:string,message:string){if(this.disposed||this.signal.aborted||this.announcements.has(key))return;this.announcements.add(key);this.context.announce(key,message);}
 feedback(message:string){if(this.disposed||this.signal.aborted)return;this.feedbackText=message;outcome(this.feedbackNode,message);if(!this.host.contains(this.feedbackNode))this.host.append(this.feedbackNode);}
 checkHead(head:number){if(head!==this.head||this.context.store.getState().head!==this.head)throw new HeadRace();}
 async call(tool:string,args:any={},mutation=false):Promise<any>{const epoch=this.epoch,signal=this.signal,context=this.context;ensure(!this.disposed&&!signal.aborted,'Request cancelled');const data:any=await context.transport.call(tool,args,{mutation,signal});ensure(!this.disposed&&!signal.aborted&&epoch===this.epoch,'Obsolete request cancelled');resultShape(tool,data);if(['ledger_events','memory_history'].includes(tool))cursor(data,args.after??0);return data;}
 private async bracket(){const p=await this.call('ledger_events',{after:0,limit:1});ensure(!p.resync,'Ledger changed. Resync required; filters kept.');this.checkHead(p.head);}
 private readQuery(){const raw=this.context.route.query,query:Record<string,string>={};const enums:Record<string,readonly string[]>={panel:panels,kind:['ruling','lesson','negative','workflow','episode','decision','open_item'],level:['1','2','3'],privacy:['public','internal','private'],inheritable:['1'],arm:['none','own','inherited']};let invalid=false;for(const [k,v]of Object.entries(raw)){if(k==='seat'){try{const seat=JSON.parse(v);validate(seat,{type:'object',properties:{model:{type:'string',minLength:1,maxLength:128},effort:{type:'string',minLength:1,maxLength:32,pattern:'^[a-z0-9_-]+$'},mode:{enum:['headless','interactive']}},required:['model','effort','mode'],additionalProperties:false});query.seat=canonical(seat);}catch{invalid=true;}}else if(enums[k]){if(enums[k].includes(v))query[k]=v;else invalid=true;}}
 this.query=query;this.notice=invalid?'Invalid filters reset individually.':'';}
 async update(context:ScreenContext,initial=false,append=false):Promise<void>{
  if(this.disposed)return;this.owned.abort();this.detach();this.owned=new AbortController();this.signal=this.owned.signal;this.context=context;const onAbort=()=>this.owned.abort();context.signal.addEventListener('abort',onAbort,{once:true});this.detach=()=>context.signal.removeEventListener('abort',onAbort);if(context.signal.aborted)this.owned.abort();const request=++this.epoch;
  if(context.route.screen!=='agent')throw Error('Invalid Agent route');const changed=!this.a||this.a.agent_id!==context.route.agentId;if(changed){closeDialogsWithin(this.host);this.a=null;this.states={};this.ack=null;this.search='';this.referenceId=undefined;this.feedbackText='';this.expanded.clear();this.stale=false;delete this.host.dataset.linEntity;delete this.host.dataset.linId;}
  this.readQuery();const panel=(this.query.panel??'constitution') as Panel;this.head=context.store.getState().head;this.tools=context.store.getState().tools;this.host.setAttribute('aria-busy','true');if(!this.a){this.host.replaceChildren(el('h1','Agent '+identityKey('agent',context.route.agentId)),el('p','Loading Agent.'));}
  try{await this.fold(panel,append);}
  catch(error){if(initial&&error instanceof HeadRace&&request===this.epoch&&!this.signal.aborted){await context.store.refresh();this.head=context.store.getState().head;try{await this.fold(panel,append);return;}catch(next){error=next;}}
   if(this.disposed||this.signal.aborted||request!==this.epoch)throw error;
   if(error instanceof HeadRace){this.stale=true;this.feedbackText=(this.ack===null?'Data is stale.':`Data is stale. Last confirmed revision ${this.ack}.`)+' Refresh required.';}
   else{const previous=this.states[panel];this.states[panel]={...previous,error:errorText(error)};if(this.ack!==null)this.stale=true;}
   if(errorText(error).includes('Identity key collision'))this.collision=true;this.render();if(error instanceof HeadRace&&this.ack!==null){await context.store.refresh();return;}if(error instanceof HeadRace||this.collision)throw error;
  }finally{if(!this.disposed&&!this.signal.aborted&&request===this.epoch)this.host.setAttribute('aria-busy','false');}
 }
 private async fold(panel:Panel,append:boolean){ensure(this.head!==null,'Unknown ledger prefix');await this.bracket();const identityResult=await this.call('agent_get',{agent_id:(this.context.route as any).agentId});closed(identityResult,['record']);const nextAgent=record(identityResult.record,'agent');ensure(nextAgent.agent_id===(this.context.route as any).agentId,'Agent owner mismatch');await this.bracket();
  const oldAgent=this.a;this.a=nextAgent;let data:any;try{data=panel==='constitution'?await constitution(this):panel==='skills'?{}:panel==='memory'?await memory(this,append?this.states.memory?.data:undefined):panel==='scorecard'?await scorecard(this):await runs(this,append?this.states.runs?.data:undefined);await this.bracket();this.collisions(nextAgent,panel,data);}
  catch(error){if(this.ack!==null&&oldAgent)this.a=oldAgent;throw error;}
  this.a=nextAgent;this.states[panel]={data};this.ack=this.head;this.stale=false;this.collision=false;this.render();this.host.setAttribute('aria-busy','false');
  if(panel==='runs')for(const e of [...data.events].sort((a:any,b:any)=>a.lamport-b.lamport)){const p=e.payload;const id=e.kind==='run.close'?p.record.run_id:p.run_id;const owner=e.kind==='run.close'?p.record.agent_id:p.agent_id;if(owner===this.a.agent_id)this.announce('lifecycle:'+id+':'+e.id,'Run '+identityKey('run',id)+': '+(e.kind==='run.open'?'open':e.kind==='run.close'?'closed':p.progress)+'.');}
 }
 private collisions(agent:any,panel:Panel,data:any){const seen=new Map<string,string>();const add=(kind:any,id:string)=>{const key=kind+':'+identityKey(kind,id);ensure(!seen.has(key)||seen.get(key)===id,'Identity key collision. Actions unavailable.');seen.set(key,id);};add('agent',agent.agent_id);for(const s of agent.skills)add('skill',s.skill_id+'@'+s.sha256);for(const s of agent.allowed_seats)add('seat',canonical(s));const memoryData=panel==='memory'?data:this.states.memory?.data;for(const u of memoryData?.units??[])add('unit',u.id);const runData=panel==='runs'?data:this.states.runs?.data;for(const r of runData?.runs??[])add('run',r.opened.payload.run_id);}
 async load(panel:Panel,append=false){try{await this.update({...this.context,route:{screen:'agent',agentId:this.a.agent_id,query:{...this.query,panel}}},false,append);}catch{/* The named panel retains its last confirmed fold and Retry. */}}
 change(key:string,value:string){if(value)this.query[key]=value;else delete this.query[key];const route={screen:'agent' as const,agentId:this.a.agent_id,query:{...this.query}};const epoch=this.epoch;this.context.navigate(route);if(this.epoch===epoch)void this.update({...this.context,route}).catch(()=>{});}
 available(tool:string,ownerBound=false):string|null {if(this.collision)return 'Identity key collision. Actions unavailable.';if(this.context.transport.mode==='fixture')return 'Synthetic fixtures. Changes are unavailable.';const descriptor=this.context.store.getState().tools.find(t=>t.name===tool);if(!descriptor)return 'Tool descriptor unavailable: '+tool;const known:Record<string,string[]>={memory_put:['agent_id','unit','run_id'],run_open:['run_id','agent_id','seat','task','parents_context','memory_arm'],run_beat:['run_id','progress'],run_close:['run_id','outcome','cost','evidence'],agent_clone:['parent_id','child_id','display_name'],agent_distill:['parent_id','child_id','display_name','unit_ids'],agent_cross:['parent_ids','child_id','display_name'],agent_mutate:['parent_id','child_id','display_name','change'],agent_specialize:['parent_id','child_id','display_name','language'],agent_retire:['agent_id','reason'],agent_promote:['agent_id','bench_id']};const allowed=[...(known[tool]??[]),'agent','op_id','expected_head'];if((descriptor.inputSchema.required as string[]??[]).some(k=>!allowed.includes(k))||Object.keys(descriptor.inputSchema.properties??{}).some(k=>!allowed.includes(k)))return 'Unsupported tool descriptor shape. Changes are unavailable.';
 const actor=document.querySelector<HTMLSelectElement>('[data-lin-action="select-actor"]');if(!actor||actor.disabled||!isAgentId(actor.value))return 'Selected actor unavailable or reserved. Tool assertions grant no operator authority.';if(ownerBound&&actor.value!==this.a.agent_id)return 'actor_mismatch: selected actor must equal the target owner.';if(this.context.store.getState().head===null)return 'Acknowledged ledger head unavailable.';return null;}
 openForm(kind:string,trigger:HTMLElement,id?:string){openForm(this,this.drafts,kind,trigger,id);}
 beat(runId:string,trigger:HTMLElement){const draft:OperationDraft={};void execute(this,draft,'run_beat',{run_id:runId,progress:'Heartbeat requested from Agent detail.'},'Record heartbeat',runId,(_state,msg)=>{(trigger as HTMLButtonElement).disabled=_state==='pending';this.feedback(msg);}).then(result=>{if(result)void this.load('runs');});}
 render(){if(this.disposed||this.signal.aborted)return;const focus=captureFocus(this.host);if(!this.a){const id=(this.context.route as any).agentId,heading=el('h1','Agent '+identityKey('agent',id));heading.tabIndex=-1;const full=el('p',id);full.className='full-identity';full.id='screen-identity';heading.setAttribute('aria-describedby',full.id);this.host.replaceChildren(heading,full);const message=this.feedbackText||this.states[(this.query.panel??'constitution') as Panel]?.error||'Agent unavailable.';const alert=el('p');outcome(alert,message,true);this.host.append(alert,this.button('retry-panel','Retry Agent',()=>{void this.update(this.context).catch(()=>{});}));return;}
  // Refresh does not tear down an open modal or its volatile editor.
  if(this.host.querySelector('dialog'))return;
  this.host.replaceChildren();this.host.dataset.linEntity='agent';this.host.dataset.linId=this.a.agent_id;identity(this,this.host);const active=(this.query.panel??'constitution') as Panel;const nav=el('nav');nav.setAttribute('aria-label','Agent panels');nav.className='agent-panels';for(const p of panels){const b=this.button('show-'+p,p[0].toUpperCase()+p.slice(1)+' for '+identityKey('agent',this.a.agent_id),()=>this.change('panel',p));b.setAttribute('aria-pressed',String(p===active));nav.append(b);}this.host.append(nav);
  const toolbar=el('div');toolbar.className='agent-actions';toolbar.append(this.button('view-brief','Read brief '+identityKey('agent',this.a.agent_id),b=>brief(this,b)));for(const kind of ['derive','retire','promote'])toolbar.append(this.button(kind+'-agent',kind[0].toUpperCase()+kind.slice(1)+' agent '+identityKey('agent',this.a.agent_id),b=>this.openForm(kind,b)));
  if(active!=='memory')toolbar.append(this.button('write-memory','Write agent memory',b=>this.openForm('memory',b)));if(active!=='runs')toolbar.append(this.button('open-run-form','Open a run',b=>this.openForm('run',b)));this.host.append(toolbar);
  if(this.notice)text(this.host,this.notice);text(this.host,'Drafts are volatile. Reload discards unsent drafts; committed state is refetched.');if(this.collision)text(this.host,'Identity key collision. Actions unavailable.');if(this.stale)text(this.host,'Data is stale. Last confirmed revision '+(this.ack??'unknown')+'.');const region=el('section'),heading=el('h2',active[0].toUpperCase()+active.slice(1));heading.tabIndex=-1;region.append(heading);this.host.append(region);const state=this.states[active];if(state?.error){text(region,heading.textContent+' unavailable. Retry to continue.');const error=el('p');outcome(error,state.error,true);region.append(error);region.append(this.button('retry-panel','Retry '+heading.textContent,()=>void this.load(active)));}
  if(active==='constitution')renderConstitution(this,region,state?.data);if(active==='skills')renderSkills(this,region);if(active==='memory')renderMemory(this,region,state?.data);if(active==='scorecard')renderScorecard(this,region,state?.data);if(active==='runs')renderRuns(this,region,state?.data);
  const mutationMap:Record<string,string>={'write-memory':'memory_put','open-run-form':'run_open','heartbeat-run':'run_beat','close-run':'run_close','derive-agent':'agent_clone','retire-agent':'agent_retire','promote-agent':'agent_promote'};const reasons=new Set<string>();for(const button of this.host.querySelectorAll<HTMLButtonElement>('button[data-lin-action]')){let tool=mutationMap[button.dataset.linAction!];if(button.dataset.linAction==='derive-agent')tool=['agent_clone','agent_distill','agent_cross','agent_mutate','agent_specialize'].find(name=>this.context.store.getState().tools.some(t=>t.name===name))??'agent_clone';if(tool){const reason=this.available(tool,['memory_put','run_open','run_beat','run_close'].includes(tool));if(reason){button.disabled=true;reasons.add(reason);}}if(this.collision)button.disabled=true;}for(const reason of reasons)text(this.host,reason);
  outcome(this.feedbackNode,this.feedbackText);this.host.append(this.feedbackNode);restoreFocus(this.host,focus,heading,(k,m)=>this.announce(k,m));
 }
 dispose(){if(this.disposed)return;this.disposed=true;this.owned.abort();this.detach();this.unsubscribe();closeDialogsWithin(this.host);this.drafts.clear();delete this.host.dataset.linEntity;delete this.host.dataset.linId;}
}
export const screen: ScreenModule = {
 id: 'agent', title: 'Agent',
 mount(host, context) {
  const controller = new AgentScreen(host, context);
  const observe = (promise: Promise<void>) => { void promise.catch(() => {}); return promise; };
  const lifetime = new AbortController();
  let latest: Promise<void> | null = null;
  const update = (next: ScreenContext, initial = false) => {
   latest = observe(controller.update(next, initial));
   return latest;
  };
  // The shell mounts before its first store refresh. Keep that initial readiness
  // pending, and join the fold requested by the shell when the prefix arrives.
  const prefix = () => new Promise<void>((resolve, reject) => {
   let unsubscribe = () => {};
   const cleanup = () => {unsubscribe();context.signal.removeEventListener('abort',cancel);lifetime.signal.removeEventListener('abort',cancel);};
   const cancel = () => {cleanup();reject(Error('Request cancelled'));};
   const check = () => {
    const state = context.store.getState();
    if(context.signal.aborted || lifetime.signal.aborted){cancel();return;}
    if(state.head !== null){cleanup();resolve();}
    else if(state.phase === 'error'){cleanup();reject(Error('Acknowledged ledger head unavailable.'));}
   };
   unsubscribe = context.store.subscribe(check);
   context.signal.addEventListener('abort',cancel,{once:true});
   lifetime.signal.addEventListener('abort',cancel,{once:true});
   check();
  });
  let ready: Promise<void>;
  if(context.store.getState().head === null){
   const id = context.route.screen === 'agent' ? context.route.agentId : '';
   host.replaceChildren(el('h1','Agent '+identityKey('agent',id)),el('p','Loading Agent.'));
   ready = observe(prefix().then(() => latest ?? update(context,true)));
  }else ready = update(context,true);
  return { ready, update: next => update(next), dispose: () => {lifetime.abort();controller.dispose();} };
 }
};
