import '../../../styles/lineage.css';
import type { ScreenModule, ScreenContext, LedgerEvent, Route, JsonValue } from '../../ui/contracts.ts';
import { identityKey, normalizeName, checkedName } from '../../ui/primitives.ts';
import { formatRoute } from '../../router.ts';
import { invalidResponse, TransportError } from '../../transport.ts';
import { drawTree } from './layout.ts';
import { agentId, validateTree, coherent, birthIndex, eligible, citedRules, rejectedReasons, type LineageTreeData, type LineageNode, type EvidenceObject } from './model.ts';

function element<K extends keyof HTMLElementTagNameMap>(tag:K,text?:string):HTMLElementTagNameMap[K] {
  const el=document.createElement(tag);if(text!==undefined) el.textContent=text;return el;
}
const aborted=()=>new TransportError('transport','aborted','Request cancelled.');
const folded=(value:string)=>normalizeName(value).toLowerCase();

export const screen:ScreenModule={id:'lineage',title:'Lineage',mount(host,initial) {
  let context=initial,disposed=false,generation=0;
  let tree:LineageTreeData|null=null,birthMap=new Map<string,LedgerEvent>();
  let root='',query='',selectedId:string|null=null,filterKey='',initialized=false;
  let revealed=new Set<string>(),collapsed=new Set<string>();
  let notice='';
  let controlsController=new AbortController();const feedbackController=new AbortController();
  const messages=new Set<string>();
  const heading=element('h1','Lineage');heading.tabIndex=-1;
  const body=element('div');body.className='lineage-body';
  const feedback=element('div');feedback.className='lineage-feedback';
  host.replaceChildren(heading,feedback,body);
  function announce(key:string,message:string) {
    if(disposed||context.signal.aborted||messages.has(key)) return;
    messages.add(key);context.announce(key,message);
  }
  function button(action:string,name:string,handler:()=>void,signal=controlsController.signal) {
    const control=element('button',checkedName(name));control.type='button';control.dataset.linAction=action;
    control.addEventListener('click',()=>{if(!disposed&&!context.signal.aborted) handler();},{signal});return control;
  }
  function scopeNodes():LineageNode[] {
    if(!tree) return [];
    if(!root) return tree.nodes;
    const wanted=new Set([root]);
    for(const n of tree.nodes) if(n.parents.some(p=>wanted.has(p))) wanted.add(n.agent_id);
    return tree.nodes.filter(n=>wanted.has(n.agent_id));
  }
  function candidates() {
    const scope=scopeNodes(),inScope=new Set(scope.map(n=>n.agent_id));
    const canonical=new Map(scope.map(n=>[n.agent_id,n.parents.find(p=>inScope.has(p))]));
    if(!query) return {scope,list:scope,canonical,matches:null};
    const matches=new Set(scope.filter(n=>folded(n.agent_id).includes(folded(query))||folded(String((birthMap.get(n.agent_id)?.payload.record as EvidenceObject|undefined)?.display_name??'')).includes(folded(query))).map(n=>n.agent_id));
    const wanted=new Set(matches);
    // All parent chains retain both relations of a shared child under search.
    for(let i=scope.length-1;i>=0;i--) if(wanted.has(scope[i].agent_id)) for(const p of scope[i].parents) if(inScope.has(p)) wanted.add(p);
    return {scope,list:scope.filter(n=>wanted.has(n.agent_id)),canonical,matches};
  }
  function resetBudget() {
    const {list,canonical}=candidates();
    const roots=new Set(list.filter(n=>!canonical.get(n.agent_id)).map(n=>n.agent_id));
    revealed=new Set(list.filter(n=>query||roots.has(n.agent_id)||roots.has(canonical.get(n.agent_id)??'')).slice(0,50).map(n=>n.agent_id));
    collapsed.clear();
  }
  function routeTo(next:{root?:string;q?:string;selected?:string}) {
    const route:Route={screen:'lineage',query:{...next}};context.navigate(route);
  }
  function currentQuery() {return {...(root?{root}:{}),...(query?{q:query}:{}),...(selectedId?{selected:selectedId}:{})};}
  function more(branch?:string) {
    const {list,canonical}=candidates();
    if(branch) {collapsed.delete(branch);context.store.setExpanded('agent',branch,true);}
    let count=0;
    for(const n of list) {
      if(revealed.has(n.agent_id)) continue;
      if(branch) {
        let p=canonical.get(n.agent_id),inside=false;
        while(p) {if(p===branch) {inside=true;break;}p=canonical.get(p);}
        if(!inside) continue;
      }
      // A continuation reveals canonical ancestors first, in generation order.
      revealed.add(n.agent_id);let p=canonical.get(n.agent_id);
      while(p) {collapsed.delete(p);p=canonical.get(p);}
      if(++count===50) break;
    }
    render();
  }
  function collapse(id:string) {
    const {canonical}=candidates();const active=document.activeElement as HTMLElement|null;
    const focused=active?.closest<HTMLElement>('[data-lin-entity="agent"]')?.dataset.linId;
    const below=(child:string)=>{let p=canonical.get(child);while(p) {if(p===id) return true;p=canonical.get(p);}return false;};
    const restore=focused&&below(focused);
    collapsed.add(id);context.store.setExpanded('agent',id,false);
    for(const child of revealed) if(below(child)) revealed.delete(child);
    render();if(restore) findControl('expand-lineage-agent',id)?.focus();
  }
  function findControl(action:string,id?:string) {
    return [...host.querySelectorAll<HTMLElement>('[data-lin-action]')].find(el=>el.dataset.linAction===action&&(id===undefined||el.closest<HTMLElement>('[data-lin-entity="agent"]')?.dataset.linId===id));
  }
  function evidence(container:HTMLElement,id:string) {
    const event=birthMap.get(id),payload=event?.payload as EvidenceObject|undefined,record=payload?.record;
    container.append(element('h2','Recorded inheritance'),element('p','Inheritance is context, never weights. Recorded hashes and receipts are references; eligibility and receipt admission are server-owned.'));
    if(!event||!record||!Array.isArray(payload?.inherited_units)||!Array.isArray(payload?.rejected_units)) {container.append(element('p','Birth and inheritance evidence unavailable.'));return;}
    container.append(element('p',`Child ${id}. Parents in recorded order: ${record.parents.join(', ')||'None — genesis'}. Birth operator ${record.born.op}. Birth event ${event.id}. Birth event hash ${event.sha256}. Child birth version ${record.agent_version}.`));
    container.append(element('p','Parent captured version at derivation: not recorded.'));
    const accepted=payload.inherited_units;
    if(!accepted.length) container.append(element('p','No recorded inherited units.'));
    for(const item of accepted) {
      if(!eligible(item,record)) {container.append(element('p','Accepted inheritance evidence invalid or unavailable.'));continue;}
      const section=element('section');section.append(element('h3',`Inherited unit ${item.unit.id}`),element('p','Inheritable'));
      // Only eligible nonprivate bodies reach presentation; all values remain text.
      section.append(element('pre',JSON.stringify(item,null,2)));container.append(section);
    }
    if(!payload.rejected_units.length) container.append(element('p','No rejected units.'));
    else {
      container.append(element('h3','Rejected context'));
      for(const r of payload.rejected_units) {
        if(!r||!agentId(r.agent_id)||typeof r.unit_id!=='string'||!rejectedReasons.has(r.reason)) {container.append(element('p','Rejected evidence unavailable.'));continue;}
        container.append(element('p',`${r.agent_id} / ${r.unit_id}: ${r.reason} — ${rejectedReasons.get(r.reason)}`));
      }
    }
    container.append(element('h2','Birth constitution'));
    if(payload.constitution&&typeof payload.constitution.text==='string') container.append(element('pre',payload.constitution.text));
    else container.append(element('p','Birth constitution unavailable.'));
    container.append(element('p',`Child constitution hash ${record.constitution_sha256}`));
    if(!record.parents.length) {container.append(element('p','Genesis has no parent comparison.'));return;}
    for(const parentId of record.parents) {
      const parent=birthMap.get(parentId)?.payload as EvidenceObject|undefined;
      const section=element('section');section.append(element('h3',`Parent comparison: ${parentId}`));
      const childRules=citedRules(payload.constitution),parentRules=citedRules(parent?.constitution);
      if(!parentRules||!childRules||!parent?.record) section.append(element('p','Parent constitution comparison unavailable.'));
      else {
        section.append(element('p',`Parent birth constitution hash ${parent.record.constitution_sha256}`),element('pre',parent.constitution.text));
        let changes=0;
        for(const [rule,text] of childRules) {
          if(!parentRules.has(rule)) {section.append(element('p',`Added ${rule}: ${text}`));changes++;}
          else if(parentRules.get(rule)!==text) {section.append(element('p',`Changed ${rule}: ${parentRules.get(rule)} → ${text}`));changes++;}
        }
        for(const [rule,text] of parentRules) if(!childRules.has(rule)) {section.append(element('p',`Removed ${rule}: ${text}`));changes++;}
        if(!changes) section.append(element('p',parent.constitution.text===payload.constitution.text&&parent.record.constitution_sha256===record.constitution_sha256?'No changed rules.':'Constitution hash/content difference without attributable rule changes.'));
      }
      for(const [label,source] of [['Child',record],['Parent',parent?.record]] as const) {
        const overrides=source?.rule_overrides;
        section.append(element('p',`${label} rule overrides: ${overrides?JSON.stringify(overrides):'not recorded'}`));
        if(overrides&&Object.keys(overrides).some(k=>['__proto__','constructor','prototype'].includes(k))) section.append(element('p','Invalid rule overrides; comparison unavailable.'));
      }
      container.append(section);
    }
  }
  function render() {
    if(disposed||context.signal.aborted||!tree) return;
    controlsController.abort();controlsController=new AbortController();
    const active=document.activeElement as HTMLInputElement|null;
    const focusAction=(active as HTMLElement|null)?.dataset.linAction;
    const focusId=active?.closest<HTMLElement>('[data-lin-entity="agent"]')?.dataset.linId;
    const caret=active instanceof HTMLInputElement?[active.selectionStart,active.selectionEnd,active.selectionDirection] as const:null;
    const scroll=host.scrollTop;
    const {scope,list,canonical,matches}=candidates();
    const visible=list.filter(n=>revealed.has(n.agent_id));const visibleIds=new Set(visible.map(n=>n.agent_id));
    const content=element('div');content.className='lineage-content';
    const toolbar=element('div');toolbar.className='lineage-filters';
    const label=element('label','Find lineage agent');const input=element('input');input.type='search';input.value=query;input.dataset.linAction='filter-lineage-query';input.setAttribute('aria-label','Find lineage agent');label.append(input);
    input.addEventListener('input',()=>{routeTo({...currentQuery(),q:input.value||undefined});},{signal:controlsController.signal});
    const rootLabel=element('label','Lineage root'),select=element('select');select.dataset.linAction='filter-lineage-root';select.setAttribute('aria-label','Lineage root');
    const all=element('option','All lineage roots');all.value='';select.append(all);
    for(const n of tree.nodes) {const option=element('option',n.agent_id);option.value=n.agent_id;select.append(option);}select.value=root;
    select.addEventListener('change',()=>{
      const nextRoot=select.value,wanted=new Set([nextRoot]);
      for(const n of tree!.nodes) if(n.parents.some(p=>wanted.has(p))) wanted.add(n.agent_id);
      if(selectedId&&nextRoot&&!wanted.has(selectedId)) {selectedId=null;notice='Selection cleared: outside the new root scope.';context.store.setSelection('lineage',null);}
      routeTo({...currentQuery(),root:nextRoot||undefined});
    },{signal:controlsController.signal});rootLabel.append(select);
    toolbar.append(label,rootLabel,button('reset-lineage','Reset lineage filters',()=>{
      const genesis=tree!.nodes.find(n=>!n.parents.length)?.agent_id;routeTo(genesis?{selected:genesis}:{});
    }));content.append(toolbar);
    if(notice) content.append(element('p',notice));
    if(context.store.getState().notice) content.append(element('p',context.store.getState().notice!));
    if(!tree.nodes.length) content.append(element('p','No lineage agents yet.'));
    else if(!list.length) content.append(element('p','No matching agents. Clear filters to see all loaded records.'));
    if(query&&list.length) content.append(element('p','Matching agents with ancestor context.'));
    const listRoot=element('ul');listRoot.className='lineage-list';
    const childrenLists=new Map<string,HTMLUListElement>();
    const inScope=new Set(scope.map(n=>n.agent_id));
    const childrenByParent=new Map<string,LineageNode[]>();
    for(const child of scope) for(const parent of child.parents) {
      const children=childrenByParent.get(parent)??[];children.push(child);childrenByParent.set(parent,children);
    }
    const visibleParents=new Set(visible.map(n=>canonical.get(n.agent_id)));
    const parentsWithChildren=new Set(tree.nodes.flatMap(n=>n.parents));
    for(const n of visible) {
      const key=identityKey('agent',n.agent_id),entry=element('li');entry.dataset.linEntity='agent';entry.dataset.linId=n.agent_id;
      const card=entry;card.className='lineage-card'+(n.agent_id===selectedId?' lineage-selected':'');
      const h=element('h3',`Lineage agent ${key}`),description=element('p');description.id=`lineage-${n.agent_id}-description`;
      description.textContent=`${n.agent_id} · ${n.status} · ${n.op} · Generation ${n.generation}`;
      const record=birthMap.get(n.agent_id)?.payload.record as EvidenceObject|undefined;
      description.append(document.createTextNode(' · '+(typeof record?.display_name==='string'?record.display_name:'Display name unavailable.')));card.append(h,description);
      for(const parent of n.parents) description.append(document.createTextNode(` · ${parent} → ${n.agent_id} (${n.op})${inScope.has(parent)?'':' — boundary parent outside scope'}`));
      if(!n.parents.length&&!parentsWithChildren.has(n.agent_id)) card.append(element('p','Genesis agent. No descendants yet.'));
      if(matches&&!matches.has(n.agent_id)) card.append(element('p','Ancestor context.'));
      const actions:HTMLElement[]=[];
      const selectButton=button('select-lineage-agent',`Select lineage ${key}`,()=>routeTo({...currentQuery(),selected:n.agent_id}));selectButton.setAttribute('aria-pressed',String(n.agent_id===selectedId));actions.push(selectButton);
      const hasChildren=childrenByParent.has(n.agent_id);
      if(hasChildren) {
        const expanded=!collapsed.has(n.agent_id)&&visibleParents.has(n.agent_id);
        const disclosure=button(expanded?'collapse-lineage-agent':'expand-lineage-agent',`${expanded?'Collapse':'Expand'} lineage ${key}`,()=>expanded?collapse(n.agent_id):more(n.agent_id));disclosure.setAttribute('aria-expanded',String(expanded));actions.push(disclosure);
      }
      const link=element('a',checkedName(`Inspect lineage ${key}`));link.dataset.linAction='open-lineage-agent';link.href=formatRoute({screen:'agent',agentId:n.agent_id,query:{}});
      link.addEventListener('click',event=>{if(event.button===0&&!event.ctrlKey&&!event.metaKey&&!event.shiftKey&&!event.altKey) {event.preventDefault();context.navigate({screen:'agent',agentId:n.agent_id,query:{}});}}, {signal:controlsController.signal});actions.push(link);
      for(const control of actions) control.setAttribute('aria-describedby',description.id);
      card.append(...actions);
      for(const child of childrenByParent.get(n.agent_id)??[]) if(canonical.get(child.agent_id)!==n.agent_id) card.append(element('p',`${n.agent_id} → ${child.agent_id} (${child.op}). Canonical parent ${canonical.get(child.agent_id)}. Reveal the canonical branch with Show next lineage generation if pending.`));
      const children=element('ul');children.className='lineage-children';entry.append(children);childrenLists.set(n.agent_id,children);
      const parent=canonical.get(n.agent_id);(parent&&childrenLists.get(parent)||listRoot).append(entry);
    }
    content.append(listRoot);
    const pending=list.length-visible.length;
    if(pending>0) content.append(element('p',`${pending} agents remaining.`),button('expand-next-generation','Show next lineage generation',()=>more()));
    if(selectedId) {
      if(!visibleIds.has(selectedId)) content.append(element('p',`Selected agent ${selectedId} is hidden by filters, collapsed ancestry or pending expansion.`));
      const inspector=element('section');inspector.className='lineage-inspector';try {evidence(inspector,selectedId);} catch {inspector.replaceChildren(element('h2','Recorded inheritance'),element('p','Birth and inheritance evidence unavailable.'));}content.append(inspector);
    }
    const drawing=element('section');drawing.className='lineage-drawing';
    try {
      const svg=drawTree(tree,visibleIds,selectedId);
      const box=svg.getAttribute('viewBox')?.trim().split(/[ ,]+/u).map(Number);
      if(!(svg instanceof SVGSVGElement)||!box||box.length!==4||box.some(v=>!Number.isFinite(v))||box[2]<=0||box[3]<=0) throw Error('Unusable geometry');
      drawing.append(svg);
    } catch {drawing.append(element('p','Tree drawing unavailable. Use the lineage list.'));}
    content.append(drawing);body.replaceChildren(content);host.scrollTop=scroll;
    if(focusAction) {
      const control=findControl(focusAction,focusId);if(control) {control.focus();if(caret&&control instanceof HTMLInputElement&&(control.selectionStart!==caret[0]||control.selectionEnd!==caret[1]||control.selectionDirection!==caret[2])) control.setSelectionRange(caret[0],caret[1],caret[2]??undefined);}
    }
  }
  function showFailure(error:unknown) {
    host.setAttribute('aria-busy','false');feedback.replaceChildren();
    if(tree) feedback.append(element('p',`Data is stale. Last confirmed revision ${tree.head}.`));
    const e=error instanceof TransportError?error:invalidResponse();
    feedback.append(element('p','Lineage unavailable. Retry to continue.'),element('p',`${e.source}: ${e.code}`));
    if(e.message==='Identity key collision. Actions unavailable.') feedback.append(element('p',e.message));
    if(typeof e.detail==='string') feedback.append(element('p',e.detail));
    feedback.append(button('retry-panel','Retry Lineage',()=>{void load(context).catch(()=>{});},feedbackController.signal));
    announce(`lineage:error:${tree?.head??'unknown'}:${e.source}:${e.code}:${e.message}`,`Lineage unavailable. Retry to continue. ${e.source}: ${e.code}`);
  }
  let latest:Promise<void>|null=null;
  const pendingFolds=new Set<()=>void>();
  function waitForFold(next:ScreenContext,current:()=>boolean):Promise<void> {
    return new Promise(resolve=>{
      let unsubscribe=()=>{};
      const finish=()=>{
        unsubscribe();next.signal.removeEventListener('abort',finish);
        pendingFolds.delete(finish);resolve();
      };
      pendingFolds.add(finish);
      unsubscribe=next.store.subscribe(state=>{if(!current()||state.phase!=='loading') finish();});
      next.signal.addEventListener('abort',finish,{once:true});
      if(!current()||next.store.getState().phase!=='loading') finish();
    });
  }
  async function perform(next:ScreenContext,turn:number) {
    context=next;const current=()=>!disposed&&!next.signal.aborted&&turn===generation;
    if(!current()) throw aborted();
    host.setAttribute('aria-busy','true');
    if(!tree) feedback.replaceChildren(element('p','Loading Lineage.'));
    try {
      // Integrated hosts may expose agent_list before the lineage_tree tool.
      // Use its folded records, never guess per-agent storage paths.
      if(next.store.getState().phase==='loading') await waitForFold(next,current);
      const capabilities=next.store.getState().tools;
      let data:JsonValue;
      if(capabilities.length&&!capabilities.some(t=>t.name==='lineage_tree')) {
        const nodes:JsonValue[]=[];let after:string|undefined;let head:number|null=null;
        for(let page=0;page<1000;page++) {
          const reply:any=await next.transport.call('agent_list',{include_retired:true,limit:1000,...(after?{after}:{})},{mutation:false,signal:next.signal});
          if(!reply||!Array.isArray(reply.agents)||!Number.isSafeInteger(reply.head)||head!==null&&reply.head!==head) throw invalidResponse();
          head=reply.head;
          for(const r of reply.agents) nodes.push({agent_id:r.agent_id,parents:r.parents,generation:r.generation,op:r.born.op,status:r.status});
          if(reply.next_after===null) break;
          if(typeof reply.next_after!=='string'||after!==undefined&&reply.next_after<=after||page===999) throw invalidResponse();
          after=reply.next_after;
        }
        data={nodes,head};
      } else data=await next.transport.call('lineage_tree',{include_retired:true},{mutation:false,signal:next.signal});
      if(!current()) {if(disposed||next.signal.aborted) throw aborted();return await latest!;}
      const nextTree=validateTree(data);
      // U21 starts the screen before its initial ledger fold has committed.
      // Wait for that in-flight fold; comparing an unknown head would poison ready.
      if(next.store.getState().phase==='loading') await waitForFold(next,current);
      if(!current()) {if(disposed||next.signal.aborted) throw aborted();return await latest!;}
      const state=next.store.getState();
      if(!coherent(state,nextTree.head)) throw invalidResponse();
      const keys=new Map<string,string>();for(const n of nextTree.nodes) {const key=identityKey('agent',n.agent_id);if(keys.has(key)&&keys.get(key)!==n.agent_id) throw new TransportError('transport','invalid_response','Identity key collision. Actions unavailable.');keys.set(key,n.agent_id);}
      const byId=new Map(nextTree.nodes.map(n=>[n.agent_id,n]));
      let nextRoot=next.route.query.root??'',nextQuery=next.route.query.q??'';let nextSelected:string|null=next.route.query.selected??null;
      const notices:string[]=[];
      if(nextRoot&&!agentId(nextRoot)) {nextRoot='';notices.push('Invalid root reset.');}
      if(nextSelected&&!agentId(nextSelected)) {nextSelected=null;notices.push('Invalid selected identity reset.');}
      if(nextRoot&&!byId.has(nextRoot)) throw new TransportError('domain','no_agent','Root unavailable.');
      if(Object.keys(next.route.query).some(k=>!['root','q','selected'].includes(k))) notices.push('Unknown query fields ignored.');
      if(nextSelected&&!byId.has(nextSelected)) {
        const id=nextSelected;nextSelected=null;notices.push('Selected identity unavailable.');
        announce(`lineage:removed:${id}:${nextTree.head}`,`${identityKey('agent',id)} is no longer in this view.`);heading.focus();
      }
      const activeId=(document.activeElement as HTMLElement|null)?.closest<HTMLElement>('[data-lin-entity="agent"]')?.dataset.linId;
      if(activeId&&!byId.has(activeId)) {announce(`lineage:removed:${activeId}:${nextTree.head}`,`${identityKey('agent',activeId)} is no longer in this view.`);heading.focus();}
      tree=nextTree;root=nextRoot;query=nextQuery;selectedId=nextSelected;
      birthMap=birthIndex(state.events);
      if(notices.length) notice=notices.join(' ');
      const nextFilter=JSON.stringify([root,query]);
      if(!initialized||filterKey!==nextFilter) {resetBudget();filterKey=nextFilter;initialized=true;}
      // Expanded IDs in the shared store are full identity tuples, not display keys.
      for(const n of tree.nodes) if(state.expanded.includes(JSON.stringify(['agent',n.agent_id]))) collapsed.delete(n.agent_id);
      if(selectedId&&root&&!scopeNodes().some(n=>n.agent_id===selectedId)) {selectedId=null;notice='Selection cleared: outside root scope.';}
      const selection=next.store.getState().selection.lineage??null;
      if(selection!==selectedId) next.store.setSelection('lineage',selectedId);
      if(!current()) return await latest!;
      feedback.replaceChildren();host.setAttribute('aria-busy','false');render();
    } catch(error) {
      if(!current()) {if(disposed||next.signal.aborted) throw aborted();return await latest!;}
      showFailure(error);throw error;
    }
  }
  function load(next:ScreenContext):Promise<void> {
    const turn=++generation;
    for(const finish of [...pendingFolds]) finish();
    const work=perform(next,turn);latest=work;void work.catch(()=>{});return work;
  }
  const ready=load(initial);
  return {ready,update:load,dispose() {disposed=true;++generation;for(const finish of [...pendingFolds]) finish();controlsController.abort();feedbackController.abort();}};
}};
