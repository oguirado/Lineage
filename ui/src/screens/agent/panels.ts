import type {ScreenContext} from '../../ui/contracts.ts';
import {checkedName,identityKey,formatMeasurement} from '../../ui/primitives.ts';
import {openDialog} from '../../ui/dialog.ts';
import {closed,ensure,isHash,record,sha256,canonical,validPath} from './wire.ts';
export const panels=['constitution','skills','memory','scorecard','runs'] as const;
export type Panel=typeof panels[number];
export interface Runtime {
 host:HTMLElement;context:ScreenContext;a:any;referenceId?:string;head:number|null;query:Record<string,string>;search:string;expanded:Set<string>;
 states:Partial<Record<Panel,{data?:any;error?:string}>>;signal:AbortSignal;
 call(tool:string,args?:any,mutation?:boolean):Promise<any>;checkHead(head:number):void;
 announce(key:string,text:string):void;feedback(text:string):void;render():void;
 load(panel:Panel,append?:boolean):Promise<void>;change(key:string,value:string):void;
 button(action:string,name:string,fn:(button:HTMLButtonElement)=>void):HTMLButtonElement;
 openForm(kind:string,trigger:HTMLElement,runId?:string):void;beat(runId:string,trigger:HTMLElement):void;
 available(tool:string,ownerBound?:boolean):string|null;
}
export function el<K extends keyof HTMLElementTagNameMap>(tag:K,text?:string):HTMLElementTagNameMap[K] {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
export function text(root:HTMLElement,value:string){root.append(el('p',value+'\n'));}
export function passive(value:any):HTMLElement {
 const root=el('div');root.className='agent-metadata';
 const append=(host:HTMLElement,v:any):void=>{if(v===null||typeof v!=='object'){host.append(el('pre',v===null?'not measured':String(v)));return;}if(Array.isArray(v)){const list=el('ul');for(const item of v){const row=el('li');append(row,item);list.append(row);}if(!v.length)list.append(el('li','None'));host.append(list);}else{const dl=el('dl');for(const [key,item]of Object.entries(v)){const dd=el('dd');append(dd,item);dl.append(el('dt',key),dd);}host.append(dl);}};
 append(root,value);return root;
}
export function scope(kind:string,id:string):HTMLElement {const n=el('section');n.dataset.linEntity=kind;n.dataset.linId=id;n.className='agent-record';const desc=el('p',id);desc.id='agent-'+identityKey('field',kind+':'+id);desc.className='full-identity';n.append(desc);return n;}
export function described(control:HTMLElement,wrapper:HTMLElement):void {const p=wrapper.querySelector<HTMLElement>('[id]');if(p)control.setAttribute('aria-describedby',p.id);}
export function field(root:HTMLElement,action:string,label:string,options?:string[],value=''):HTMLInputElement|HTMLSelectElement {const wrap=el('label',label);let input:HTMLInputElement|HTMLSelectElement;if(options){input=el('select');for(const val of options){const o=el('option',val||'All');o.value=val;input.append(o);}}else{input=el('input');input.type='search';}input.dataset.linAction=action;input.setAttribute('aria-label',checkedName(label));input.value=value;wrap.append(input);root.append(wrap);return input;}
function referenceText(ref:any):string {return ['id: '+ref.id,'sha256: '+ref.sha256,'bytes: '+ref.bytes,...ref.rules.map((rule:any)=>rule.id+' · '+rule.section+'\n'+rule.text)].join('\n\n');}
export function inspector(r:Runtime,label:string,id:string,data:any,trigger:HTMLElement):void {openDialog({name:checkedName(label[0].toUpperCase()+label.slice(1)+(id?' '+identityKey(label==='memory unit'?'unit':label==='agent brief'?'agent':label==='reference'?'reference':label==='skill'?'skill':label==='run'?'run':'agent',id):'')),content:label==='reference'?el('pre',referenceText(data.reference)):typeof data==='string'?el('pre',data):passive(data),trigger,fallback:r.host.querySelector<HTMLElement>('h2')??r.host,closeName:'Close '+label,host:r.host});}
export async function readInspector(r:Runtime,label:string,id:string,tool:string,args:any,trigger:HTMLElement,guard?:(data:any)=>void):Promise<void> {try{const d=await r.call(tool,args);guard?.(d);if('head' in d)r.checkHead(d.head);inspector(r,label,id,d,trigger);}catch(e){if(!r.signal.aborted)r.feedback(errorText(e));}}
export function outcome(node:HTMLElement,message:string,failed=false):void {
 if(node.textContent!==message)node.textContent=message;node.hidden=!message;const error=failed||/refused|unconfirmed|uncertainty|mismatch|invalid|unavailable|^internal:|^bad_args:|^hash_mismatch:/iu.test(message);node.setAttribute('role',error?'alert':'status');node.setAttribute('aria-label',(error?'Error: ':'')+message);
}
export function errorText(e:unknown):string {return e instanceof Error?('code' in e?String(e.code)+': ':'')+e.message:String(e);}
export async function constitution(r:Runtime):Promise<any> {
 let after=0,born:any=null;
 for(let page=0;page<1000;page++) {const p=await r.call('ledger_events',{after,limit:100,kinds:['agent.born']});r.checkHead(p.head);if(p.resync)throw Error('Ledger changed. Resync required; filters kept.');born=p.events.find((e:any)=>e.id===r.a.born.event_id);if(born)break;if(!p.has_more)break;ensure(p.next_after>after,'Stalled birth cursor');after=p.next_after;}
 ensure(born&&born.payload.record.agent_id===r.a.agent_id,'Constitution owner mismatch or missing birth');const c=born.payload.constitution;ensure(c&&sha256(c.text)===r.a.constitution_sha256&&born.payload.record.constitution_sha256===r.a.constitution_sha256,'Constitution digest mismatch');
 const refs:any[]=[];for(const pin of r.a.references){const d=await r.call('reference_get',{ref_id:pin.id});reference(d,pin);refs.push(d.reference);}
 const citations=[...c.text.matchAll(/\[GOLD-S1\/PM-1001\.1\/([^;\]\r\n]+); (§[^\]\r\n]+)\]/gu)];
 ensure(canonical(citations.map(m=>m[1]).sort())===canonical([...c.rule_ids].sort())&&citations.every((m:any)=>refs.some(ref=>ref.rules.some((rule:any)=>rule.id===m[1]&&(m[2]===rule.section||m[2].startsWith(rule.section+':L')&&rule.text.endsWith('[CITED; '+m[2]+'].'))))),'Constitution citation missing or mismatched rule');return {constitution:c,references:refs,born};
}
export function reference(d:any,pin:any):void {closed(d,['reference']);closed(d.reference,['id','sha256','bytes','rules']);ensure(d.reference.id===pin.id&&d.reference.sha256===pin.sha256,'Reference pin mismatch');ensure(Number.isSafeInteger(d.reference.bytes)&&d.reference.bytes>0&&Array.isArray(d.reference.rules));for(const x of d.reference.rules){closed(x,['id','section','text']);ensure([x.id,x.section,x.text].every(v=>typeof v==='string'&&v.length>0));}}
export function renderConstitution(r:Runtime,root:HTMLElement,data:any):void {
 if(!data)return;
 root.append(el('pre',data.constitution.text),passive({overlays:data.constitution.overlays,rule_ids:data.constitution.rule_ids}));
 // One action pair stays unambiguous under the shared agent action scope.
 const group=el('section');group.setAttribute('aria-label','Founding references');
 const choice=field(group,'edit-field','Constitution reference',r.a.references.map((p:any)=>p.id),r.referenceId??r.a.references[0].id) as HTMLSelectElement;
 choice.name='gold_s1';const selected=el('div');group.append(selected);root.append(group);
 function draw(){
  selected.replaceChildren();const pin=r.a.references.find((p:any)=>p.id===choice.value),key=identityKey('reference',pin.id);choice.name=pin.id;
  const read=r.button('get-reference','Read reference '+key,b=>void readInspector(r,'reference',pin.id,'reference_get',{ref_id:pin.id},b,d=>reference(d,pin)));read.name=pin.id;
  const verify=r.button('verify-reference','Verify reference '+key,async()=>{try{const d=await r.call('reference_verify',{ref_id:pin.id});closed(d,['ref_id','sha256','bytes','valid']);ensure(d.ref_id===pin.id&&d.sha256===pin.sha256&&d.valid===true,'Reference verification mismatch');r.feedback('Reference '+pin.id+' verified: '+d.sha256);}catch(e){r.feedback(errorText(e));}});verify.name=pin.id;
  const ref=data.references.find((v:any)=>v.id===pin.id);selected.append(read,verify,passive({id:ref.id,sha256:ref.sha256,bytes:ref.bytes}));text(selected,'Read reference to inspect its rules and source citations.');
 }
 choice.addEventListener('change',()=>{r.referenceId=choice.value;draw();});draw();
}
export function renderSkills(r:Runtime,root:HTMLElement):void {if(!r.a.skills.length)text(root,'No pinned skills.');for(const pin of r.a.skills){const id=pin.skill_id+'@'+pin.sha256;const row=scope('skill',id);row.prepend(el('h3','Skill '+identityKey('skill',id)));const open=r.button('open-skill','Open skill '+identityKey('skill',id),b=>void readInspector(r,'skill',id,'skill_get',{skill_id:pin.skill_id,sha256:pin.sha256},b,d=>{closed(d,['skill']);closed(d.skill,['skill_id','sha256','retired','files']);ensure(d.skill.skill_id===pin.skill_id&&d.skill.sha256===pin.sha256,'Skill pin mismatch');ensure(typeof d.skill.retired==='boolean'&&Array.isArray(d.skill.files));const paths=new Set<string>();for(const file of d.skill.files){closed(file,['path','content']);ensure(validPath(file.path,false)&&typeof file.content==='string'&&!paths.has(file.path),'Invalid skill path');paths.add(file.path);}ensure(paths.has('SKILL.md'),'Missing SKILL.md');}));described(open,row);row.append(open);root.append(row);}}
export function brief(r:Runtime,b:HTMLElement):void {void readInspector(r,'agent brief',r.a.agent_id,'agent_brief',{agent_id:r.a.agent_id,memory_arm:'own'},b,d=>{closed(d,['agent_id','agent_version','text','sha256','memory_gen']);ensure(d.agent_id===r.a.agent_id&&isHash(d.agent_version)&&isHash(d.sha256)&&typeof d.text==='string'&&sha256(d.text)===d.sha256,'Brief mismatch');});}
export function identity(r:Runtime,root:HTMLElement):void {const a=r.a;const header=el('section');header.className='agent-identity';const h=el('h1','Agent '+identityKey('agent',a.agent_id));h.tabIndex=-1;const id=el('p',a.agent_id);id.id='screen-identity';id.className='full-identity';h.setAttribute('aria-describedby',id.id);header.append(h,id,el('p',a.display_name));const dl=el('dl');for(const [name,v] of Object.entries({Workflow:a.workflow,Language:a.language,Status:a.status,Version:a.agent_version,'Memory generation':a.memory_gen,Generation:a.generation,'Birth operator':a.born.op,Parents:a.parents.join(', ')||'Genesis','Promoted seat':a.promoted_seat?canonical(a.promoted_seat):'Not measured'})){dl.append(el('dt',name),el('dd',String(v)));}header.append(dl);text(header,'Allowed seats');header.append(passive(a.allowed_seats));text(header,'Founding references');header.append(passive(a.references));root.append(header);}
export {formatMeasurement};
