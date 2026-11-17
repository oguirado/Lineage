import '../../../styles/agents.css';
import type { ScreenModule, ScreenContext, JsonValue, JsonObject } from '../../ui/contracts.ts';
import { identityKey } from '../../ui/primitives.ts';
import { captureFocus, restoreFocus } from '../../ui/keyboard.ts';
import { invalidResponse, TransportError, validateJson } from '../../transport.ts';
import { parseQuery, queryOf, serverArgs, equal, visible, listResult, scoreResult, safeInt, errorText, workflows, statuses } from './model.ts';
import { node, button, panel, agentCard } from './view.ts';
import { openComparison } from './comparison.ts';
import { createWorkflow } from './create.ts';
import type { Agent, ScoreGroup, Filters } from './types.ts';
export const screen:ScreenModule={
  id:'agents',title:'Agents',
  mount(host,initial) {
    let lastQuery=structuredClone(initial.route.query);
    let context=initial,disposed=false,turn=0,scoreTurn=0,confirmedHead:number|null=null,nextAfter:string|null=null;
    let records:Agent[]=[],filters:Filters=parseQuery(initial.route.query).filters,notice=parseQuery(initial.route.query).notice;
    let listError='',scoreError='',loading=true,hasSnapshot=false,failedCursor:string|null=null,collision=false;
    let comparison:{close():void}|null=null;
    const waiting=new Set<()=>void>();
    const announced=new Set<string>();
    const announce=(key:string,message:string)=>{if(disposed||context.signal.aborted||announced.has(key)) return;announced.add(key);context.announce(key,message);};
    const heading=node('h1','Agents');heading.tabIndex=-1;
    const subtitle=node('p','Create agents with a traceable origin. Compare measured agent and seat pairs.','agents-intro');
    const toolbar=node('section',undefined,'agents-toolbar');toolbar.setAttribute('aria-label','Agent catalogue controls');
    const controls=new Map<string,HTMLInputElement|HTMLSelectElement>();
    function control(action:string,label:string,kind:'search'|'select'|'checkbox',choices:string[]=[]) {
      const wrapper=node('label',label),input=kind==='select'?node('select'):node('input');input.dataset.linAction=action;input.setAttribute('aria-label',label);
      if(input instanceof HTMLInputElement) input.type=kind;else for(const choice of choices) {const option=node('option',choice||'All');option.value=choice;input.append(option);}
      wrapper.append(input);toolbar.append(wrapper);controls.set(action,input);return input;
    }
    const search=control('filter-agent-query','Find agents','search') as HTMLInputElement;
    const workflow=control('filter-agent-workflow','Filter agents by workflow','select',['',...workflows]) as HTMLSelectElement;
    const language=control('filter-agent-language','Filter agents by language','select',['']) as HTMLSelectElement;
    const status=control('filter-agent-status','Filter agents by status','select',['',...statuses]) as HTMLSelectElement;
    const retired=control('include-retired','Include retired agents','checkbox') as HTMLInputElement;
    const sort=control('sort-agents','Sort agents','select',['id-asc','id-desc','name-asc']) as HTMLSelectElement;
    const clear=button('clear-agent-filters','Clear agent filters',()=>navigate({...filters,q:'',workflow:'',language:'',status:'',retired:false,sort:'id-asc'}));
    const create=button('create-agent','Create agent',()=>creation.open(create,heading));
    const compare=button('compare-agents','Compare selected agents',()=>{if(filters.compare.length===2&&!collision) comparison=openComparison(host,context,[...filters.compare],compare,heading,read);});
    const clearCompare=button('clear-comparison','Clear compared agents',()=>navigate({...filters,compare:[]}));
    toolbar.append(clear,create,compare,clearCompare);
    const messages=node('div'),catalogue=node('ul',undefined,'agents-grid'),scorePanel=node('div'),footer=node('div');
    host.dataset.linScreen='agents';host.replaceChildren(heading,subtitle,toolbar,messages,catalogue,scorePanel,footer);
    const mountHadHead=safeInt(initial.store.getState().head);
    let readyResolve!:()=>void,readyReject!:(error:unknown)=>void,settled=false;
    const ready=new Promise<void>((resolve,reject)=>{readyResolve=resolve;readyReject=reject;});
    const current=(t:number)=>!disposed&&!context.signal.aborted&&t===turn;
    async function read(tool:string,args:JsonObject):Promise<JsonValue> {
      if(disposed||context.signal.aborted) throw new TransportError('transport','aborted','Screen observation stopped.');
      const capabilities=context.store.getState().tools;
      if(capabilities.length&&!capabilities.some(t=>t.name===tool)) throw new TransportError('transport','invalid_config',`Tool ${tool} unavailable.`);
      const result=await context.transport.call<JsonValue>(tool,args,{mutation:false,signal:context.signal});validateJson(result);
      if(new TextEncoder().encode(JSON.stringify(result)).length>1048576) throw invalidResponse();
      if(result&&typeof result==='object'&&!Array.isArray(result)&&result.ok===false) throw new TransportError('domain',String(result.code),'Read refused.',{detail:result.detail});return result;
    }
    const creation=createWorkflow({host,context:()=>context,head:()=>confirmedHead!==null&&context.store.getState().head===confirmedHead?confirmedHead:null,read,refresh:async()=>{await context.store.refresh();await load(false);},announce});
    const unsubscribe=context.store.subscribe(()=>{for(const resolve of waiting) resolve();waiting.clear();creation.update();});
    function navigate(next:Filters) {context.navigate({screen:'agents',query:queryOf(next)});}
    search.addEventListener('input',()=>navigate({...filters,q:search.value}));
    workflow.addEventListener('change',()=>navigate({...filters,workflow:workflow.value}));
    language.addEventListener('change',()=>navigate({...filters,language:language.value}));
    status.addEventListener('change',()=>navigate({...filters,status:status.value}));
    retired.addEventListener('change',()=>navigate({...filters,retired:retired.checked}));
    sort.addEventListener('change',()=>navigate({...filters,sort:sort.value}));
    function syncControls() {
      if(search.value!==filters.q) search.value=filters.q;workflow.value=filters.workflow;status.value=filters.status;retired.checked=filters.retired;sort.value=filters.sort;
      const langs=[...new Set([...records.map(r=>r.language),...(filters.language?[filters.language]:[])])].sort();
      const wanted=['',...langs];if(!equal(Array.from(language.options).map(o=>o.value),wanted)) {language.replaceChildren();for(const v of wanted) {const o=node('option',v||'All languages');o.value=v;language.append(o);}}language.value=filters.language;
      compare.disabled=filters.compare.length!==2||collision;
    }
    function checkCollisions() {const keys=new Map<string,string>();collision=false;for(const r of records) {const key=identityKey('agent',r.agent_id);if(keys.has(key)&&keys.get(key)!==r.agent_id) collision=true;keys.set(key,r.agent_id);}}
    function render() {
      if(disposed||context.signal.aborted) return;
      host.setAttribute('aria-busy',String(loading));
      const modal=host.querySelector('dialog[open]'),snapshot=modal?null:captureFocus(host);
      checkCollisions();syncControls();messages.replaceChildren();footer.replaceChildren();
      if(context.transport.mode==='fixture') messages.append(node('p','Synthetic fixtures. Changes are unavailable.','agents-provenance'));
      if(notice) messages.append(node('p',notice));
      if(collision) messages.append(node('p','Identity key collision. Actions unavailable.'));
      if(loading&&!hasSnapshot) messages.append(node('p','Loading Agents.'));
      if(listError) {if(hasSnapshot) messages.append(node('p',`Data is stale. Last confirmed revision ${confirmedHead}.`));messages.append(panel('Agents','Agents unavailable. Retry to continue. '+listError,()=>{void load(failedCursor!==null,failedCursor??undefined);}));}
      const showing=visible(records,filters);catalogue.replaceChildren();
      for(const record of showing) catalogue.append(agentCard(record,scores.get(record.agent_id),filters.compare.includes(record.agent_id),collision,()=>context.navigate({screen:'agent',agentId:record.agent_id,query:{}}),checked=>{
        if(checked&&filters.compare.length>=2&&!filters.compare.includes(record.agent_id)) {notice='Select exactly two agents for comparison.';render();return;}
        const compare=filters.compare.filter(id=>id!==record.agent_id);if(checked) compare.push(record.agent_id);navigate({...filters,compare:compare.sort()});
      }));
      if(hasSnapshot&&!showing.length) messages.append(node('p',filters.q||filters.workflow||filters.language||filters.status||filters.retired?'No matching agents. Clear filters to see all loaded records.':'No agents yet.'));
      if(nextAfter!==null) {footer.append(node('p','Showing loaded agents. More agents are available.'));footer.append(button('page-agents','Load more agents',()=>{void load(true);},loading));}
      scorePanel.replaceChildren();if(scoreError) scorePanel.append(panel('Scorecard',scoreError,()=>{void loadScores();}));
      restoreFocus(host,snapshot,heading,announce);creation.update();
    }
    const scores=new Map<string,ScoreGroup[]>();
    async function loadScores() {
      const t=++scoreTurn,requestTurn=turn;scoreError='';
      await Promise.all(records.map(async record=>{try {const groups=scoreResult(await read('scorecard_get',{agent_id:record.agent_id}),record.agent_id);if(current(requestTurn)&&t===scoreTurn) scores.set(record.agent_id,groups);}catch(e){if(current(requestTurn)&&t===scoreTurn) scoreError=errorText(e);}}));
      if(current(requestTurn)&&t===scoreTurn) render();
    }
    async function load(paging:boolean,cursor?:string) {
      const t=++turn;++scoreTurn;loading=true;listError='';const after=paging?(cursor??nextAfter):null;failedCursor=after;render();
      announce('agents-loading','Loading Agents.');
      try {
        const args=serverArgs(filters);if(after!==null) args.after=after;
        let result=listResult(await read('agent_list',args));if(!current(t)) return;
        if(context.store.getState().head===null) {await new Promise<void>(resolve=>waiting.add(resolve));if(!current(t)) return;}
        if(result.head!==context.store.getState().head) {
          await context.store.refresh();if(!current(t)) return;
          result=listResult(await read('agent_list',args));if(!current(t)) return;
          if(result.head!==context.store.getState().head) throw invalidResponse();
        }
        if(confirmedHead!==null&&result.head<confirmedHead) throw invalidResponse();
        if(after!==null&&result.next_after!==null&&result.next_after<=after) throw invalidResponse();
        const merged=new Map<string,Agent>(paging?records.map(r=>[r.agent_id,r]):[]);
        for(const r of result.agents) {const prior=merged.get(r.agent_id);if(prior&&!equal(prior,r)) throw invalidResponse();merged.set(r.agent_id,r);}
        records=[...merged.values()];confirmedHead=result.head;nextAfter=result.next_after;loading=false;hasSnapshot=true;listError='';failedCursor=null;render();
        if(collision) {if(!settled) {settled=true;readyReject(invalidResponse());}return;}
        if(!settled) {settled=true;readyResolve();}announce('agents-ready:'+confirmedHead,'Agents ready.');void loadScores();
      }catch(e) {
        if(!current(t)) return;loading=false;listError=errorText(e);render();announce('agents-error:'+listError+':'+confirmedHead,'Agents unavailable. Retry to continue.');
        // The shell mounts before its store has an acknowledged fold. Keep that
        // bootstrap pending through a recoverable read failure; its cached ready
        // promise cannot be replaced by this unit after rejection.
        if(!settled&&mountHadHead) {settled=true;readyReject(e);}
      }
    }
    void load(false);
    return {ready,async update(next) {
      if(disposed) return;
      const old=filters,parsed=parseQuery(next.route.query),changed=!equal(serverArgs(old),serverArgs(parsed.filters)),sameQuery=equal(lastQuery,next.route.query),signalChanged=context.signal!==next.signal;
      context=next;lastQuery=structuredClone(next.route.query);filters=parsed.filters;notice=parsed.notice;
      if(changed) {nextAfter=null;await load(false);}
      else if(sameQuery||signalChanged&&!hasSnapshot) await load(false);
      else render();
    },dispose() {if(disposed) return;disposed=true;++turn;++scoreTurn;unsubscribe();for(const resolve of waiting) resolve();waiting.clear();creation.dispose();comparison?.close();}};
  },
};
