import {identityKey} from '../../ui/primitives.ts';
import type {Runtime} from './panels.ts';
import {el,text,passive,scope,field,described,readInspector,inspector,errorText} from './panels.ts';
import {eligibility,levelNames,memoryKinds,unitResult,ensure,closed} from './wire.ts';
export async function memory(r:Runtime,previous?:any):Promise<any> {
 const after=previous?.after??0;const p=await r.call('memory_history',{agent_id:r.a.agent_id,after,limit:100});r.checkHead(p.head);if(p.resync)throw Error('Ledger changed. Resync required; filters kept.');
 const events=new Map<string,any>((previous?.events??[]).map((e:any)=>[e.id,e]));for(const e of p.events)events.set(e.id,e);
 const ids=new Set<string>();for(const e of events.values()){
  const payload=e.payload;if(e.kind==='agent.born'&&payload.record.agent_id===r.a.agent_id)for(const item of payload.inherited_units)ids.add(item.unit.id);
  if(payload.agent_id===r.a.agent_id){if(e.kind==='memory.put'){ids.add(payload.unit.id);for(const id of payload.unit.supersedes)ids.add(id);}if(e.kind==='memory.retire')ids.add(payload.unit_id);}
 }
 const units=[];for(const id of ids){const d=await r.call('memory_get',{agent_id:r.a.agent_id,unit_id:id});unitResult(d,r.a.agent_id,id);r.checkHead(d.head);units.push(d.unit);}
 return {units,events:[...events.values()].sort((a,b)=>a.lamport-b.lamport),after:p.next_after,more:p.has_more};
}
export function renderMemory(r:Runtime,root:HTMLElement,data:any):void {
 const filters=el('div');filters.className='agent-filters';const q=field(filters,'filter-memory-query','Find memory',undefined,r.search);q.addEventListener('input',()=>{r.search=q.value;draw();});
 for(const [key,label,options] of [['kind','kind',memoryKinds],['level','level',['1','2','3']],['privacy','privacy',['public','internal','private']]] as const){const f=field(filters,'filter-memory-'+key,'Filter memory by '+label,['',...options],r.query[key]??'');if(key==='level')for(const o of (f as HTMLSelectElement).options)if(o.value)o.textContent=levelNames[o.value];f.addEventListener('change',()=>r.change(key,f.value));}
 const wrap=el('label','Show inheritable memory');const eligible=el('input');eligible.type='checkbox';eligible.dataset.linAction='filter-memory-inheritable';eligible.setAttribute('aria-label','Show inheritable memory');eligible.checked=r.query.inheritable==='1';eligible.addEventListener('change',()=>r.change('inheritable',eligible.checked?'1':''));wrap.append(eligible);filters.append(wrap,r.button('clear-memory-filters','Clear memory filters',()=>{r.search='';for(const key of ['kind','level','privacy','inheritable'])delete r.query[key];r.change('panel','memory');}));root.append(filters);
 const tools=el('div');tools.className='agent-actions';tools.append(r.button('memory-history','Memory history '+identityKey('agent',r.a.agent_id),b=>void history(r,b)),r.button('route-memory','Search agent memory',async b=>{try{const d=await r.call('memory_route',{agent_id:r.a.agent_id,query:r.search});closed(d,['units','answer','head']);r.checkHead(d.head);ensure(typeof d.answer==='string'&&Array.isArray(d.units));ensure(d.units.every((u:any)=>u.privacy!=='private'),'Invalid private routing result');inspector(r,'memory history',r.a.agent_id,d,b);}catch(e){r.feedback(errorText(e));}}),r.button('bootcheck-memory','Check agent memory',b=>r.openForm('resume',b)),r.button('write-memory','Write agent memory',b=>r.openForm('memory',b)));root.append(tools);
 const records=el('div');root.append(records);
 function draw(){records.replaceChildren();if(!data)return;if(data.more)text(records,'Partial memory coverage. Filters apply to loaded records only.');const filtered=data.units.filter((u:any)=>(!r.search||u.statement.toLocaleLowerCase('en-GB').includes(r.search.toLocaleLowerCase('en-GB')))&&(!r.query.kind||u.kind===r.query.kind)&&(!r.query.level||String(u.level)===r.query.level)&&(!r.query.privacy||u.privacy===r.query.privacy)&&(r.query.inheritable!=='1'||!eligibility(u,r.a)));
  if(!filtered.length)text(records,!data.units.length&&!data.more&&!r.search&&!r.query.kind&&!r.query.level&&!r.query.privacy&&r.query.inheritable!=='1'?'No memory units yet.':'No matching memory units. Clear filters to see all loaded records.');
  for(const u of filtered){const row=scope('unit',u.id),key=identityKey('unit',u.id);row.prepend(el('h3','Unit '+key));text(row,u.statement);text(row,u.kind+' · '+levelNames[String(u.level)]+' · '+u.status+' · '+(u.privacy==='private'?'Private':u.privacy));text(row,'Scope: '+u.scope.workflow+' / '+u.scope.language);const reason=eligibility(u,r.a);text(row,reason?'Not inheritable: '+reason:'Inheritable');if(u.provenance.inherited_from)text(row,'Inherited context from '+u.provenance.inherited_from.agent_id+' / '+u.provenance.inherited_from.unit_id+' / '+u.provenance.inherited_from.unit_sha256);
   const detail=passive(u);detail.hidden=!r.expanded.has(u.id);const toggle=r.button('toggle-unit-details','Unit details '+key,b=>{const expanded=!r.expanded.has(u.id);if(expanded)r.expanded.add(u.id);else r.expanded.delete(u.id);b.setAttribute('aria-expanded',String(expanded));detail.hidden=!expanded;r.context.store.setExpanded('unit',u.id,expanded);});toggle.setAttribute('aria-expanded',String(!detail.hidden));
   const open=r.button('open-unit','Open unit '+key,b=>void readInspector(r,'memory unit',u.id,'memory_get',{agent_id:r.a.agent_id,unit_id:u.id},b,d=>unitResult(d,r.a.agent_id,u.id)));described(toggle,row);described(open,row);row.append(open,toggle,detail);records.append(row);
  }
  if(data.more)records.append(r.button('page-memory','Load more memory',()=>void r.load('memory',true)));
 }
 draw();
}
async function history(r:Runtime,trigger:HTMLElement){try{let after=0;const events=new Map<string,any>();for(let count=0;count<100;count++){const p=await r.call('memory_history',{agent_id:r.a.agent_id,after,limit:100});r.checkHead(p.head);ensure(!p.resync,'Ledger changed. Resync required; filters kept.');for(const e of p.events)events.set(e.id,e);if(!p.has_more)break;ensure(p.next_after>after,'Stalled history cursor');after=p.next_after;}inspector(r,'memory history',r.a.agent_id,[...events.values()],trigger);}catch(e){r.feedback(errorText(e));}}
