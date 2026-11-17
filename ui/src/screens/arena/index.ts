import type { ScreenContext, ScreenModule, JsonObject, JsonValue, LedgerEvent, Route } from '../../ui/contracts.ts';
import { createButton, createLink, identityKey } from '../../ui/primitives.ts';
import { captureFocus, restoreFocus } from '../../ui/keyboard.ts';
import { closeDialogsWithin, openDialog } from '../../ui/dialog.ts';
import { isObject, keysExactly, validateJson, validatePage, invalidResponse, TransportError } from '../../transport.ts';
import { agentId, bench, equal, errorText, eventId, id, integer, matches, runMatches, seatId, states, statusReply, validAgent, validRunReply, witnessMatches, type Bench, type Cell, type Declaration } from './model.ts';
import { openForm, paragraph, type Draft } from './forms.ts';
import { Drafts, type MutationTool, type Saved } from './drafts.ts';
import '../../../styles/arena.css';

function checkJson(value:unknown):void {validateJson(value);}
function element<K extends keyof HTMLElementTagNameMap>(tag:K,text?:string):HTMLElementTagNameMap[K] {const el=document.createElement(tag);if(text!==undefined) el.textContent=text;return el;}
const title=(s:string)=>s[0].toUpperCase()+s.slice(1);
const operation:Record<MutationTool,string>={bench_declare:'Declare benchmark',bench_run:'Launch benchmark',bench_verdict:'Evaluate benchmark',agent_promote:'Promote agent'};
const measurement=(value:unknown)=>value===null||value===undefined?'Not measured':String(value);
export const screen:ScreenModule={id:'arena',title:'Arena',mount(host,initial) {
  let context=initial,disposed=false,epoch=0,request:AbortController|null=null;
  let activeIdentity='',confirmed:Bench|null=null,list:Bench[]=[],nextAfter:string|null=null,loaded=false,pagePending=false;
  let head:number|null=null,ruleError='',listError='',resultsError='',verdictError='',queryNotice='',mutationNotice='';
  let expanded=false,displayed='',lastQuery='',collision=false;
  const seenTransitions=new Set<string>();const prior=new Map<string,{state:string;decision:string|null}>();
  const synthetic=new Set<string>();const evidence=new Map<string,{cell:Cell;event:LedgerEvent}>();
  const pendingTools=new Set<MutationTool>();const drafts=new Drafts(()=>context.store.getState().tools);
  let panelHeadings=new Map<string,HTMLElement>();
  const alive=(token?:number)=>!disposed&&!context.signal.aborted&&(token===undefined||token===epoch);
  const announce=(key:string,text:string)=>{if(alive()) context.announce(key,text);};
  const call=async(tool:string,args:JsonObject,signal=context.signal)=>context.transport.call<JsonValue>(tool,args,{mutation:false,signal});
  const currentActor=():string|null=>{
    const actor=host.ownerDocument.querySelector<HTMLSelectElement>('select[data-lin-action="select-actor"]');
    return actor&&!actor.disabled&&agentId(actor.value)?actor.value:null;
  };
  const reason=(tool:MutationTool):string=>{
    if(context.transport.mode==='fixture'||context.store.getState().mode==='fixture') return 'Synthetic fixtures. Changes are unavailable.';
    if(!currentActor()) return 'Acting agent unavailable. Select an explicit usable agent; operator and system are reserved.';
    if(!context.store.getState().tools.some(d=>d.name===tool)) return 'Tool unavailable in the registered capabilities.';
    if(context.store.getState().head===null||head===null) return 'Confirmed ledger head unavailable.';
    if(collision) return 'Identity key collision. Actions unavailable.';
    if(pendingTools.has(tool)) return 'Operation pending.';
    if(tool!=='bench_declare'&&(!confirmed||!id(confirmed.declaration.bench_id))) return 'Benchmark identity unavailable.';
    if(tool==='bench_run'&&(ruleError||!confirmed||displayed!==JSON.stringify(confirmed.declaration))) return 'Display the immutable declared rule before launch.';
    return '';
  };
  function section(label:string):HTMLElement {
    const section=element('section');section.className='arena-panel';const heading=element('h2',label);heading.tabIndex=-1;heading.id=`arena-heading-${label.toLowerCase().replace(/ /g,'-')}`;section.setAttribute('aria-labelledby',heading.id);section.append(heading);panelHeadings.set(label,heading);return section;
  }
  function button(action:string,name:string,fn:()=>void,disabled=false):HTMLButtonElement {return createButton({action,name,disabled,onActivate:()=>{if(alive()) fn();}});}
  function failure(parent:HTMLElement,label:string,error:string,retry:()=>void):void {
    const alert=paragraph(error);alert.setAttribute('role','alert');alert.setAttribute('aria-label',`Error: ${error}`);
    parent.append(paragraph(`${label} unavailable. Retry to continue.`),alert,button('retry-panel',`Retry ${label}`,retry));
  }
  function mutationButton(parent:HTMLElement,tool:MutationTool,action:string,name:string,fn:(trigger:HTMLElement)=>void):void {
    const why=reason(tool);const control=button(action,name,()=>{if(!reason(tool)) fn(control);},Boolean(why));parent.append(control);if(why) parent.append(paragraph(why));
  }
  function loadDrafts():void {
    if(context.route.screen==='bench'&&id(context.route.benchId)) for(const tool of ['bench_run','bench_verdict','agent_promote'] as const) drafts.get(tool,context.route.benchId);
    else if(context.route.screen==='arena') drafts.get('bench_declare','arena');
  }
  function queryValues():Record<string,string> {
    const q:Record<string,string>={};const allowed=context.route.screen==='arena'?['q','purpose','state']:['rule'];
    let invalid=false;for(const [key,value] of Object.entries(context.route.query)) {
      if(!allowed.includes(key)) {invalid=true;continue;}
      if(key==='purpose'&&!['','select','confirm'].includes(value)||key==='state'&&!['',...states].includes(value)||key==='rule'&&!['0','1'].includes(value)) {invalid=true;continue;}q[key]=value;
    }
    queryNotice=invalid?'Unknown or invalid query values ignored; valid filters retained.':'';return q;
  }
  function navigateQuery(query:Record<string,string>):void {context.navigate({...context.route,query} as Route);}
  function detectCollisions():void {
    collision=false;const keys=new Map<string,string>();const check=(kind:'bench'|'run',full:string)=>{const key=`${kind}:${identityKey(kind,full)}`,prior=keys.get(key);if(prior&&prior!==full) collision=true;keys.set(key,full);};
    if(context.route.screen==='arena') for(const b of list) check('bench',b.declaration.bench_id);
    else if(confirmed) {check('bench',confirmed.declaration.bench_id);for(const cell of confirmed.results) check('run',cell.run_id);}
  }
  function render():void {
    if(!alive()) return;
    // A modal keeps its own draft and invoker; never replace its ancestors during a read.
    if(host.querySelector('dialog[open]')) return;
    const focus=captureFocus(host);const headingFocus=!focus&&document.activeElement instanceof HTMLElement&&host.contains(document.activeElement)&&document.activeElement.matches('h1,h2,h3')?document.activeElement.id:null;panelHeadings=new Map();detectCollisions();const q=queryValues();
    const wrapper=element('div');wrapper.className='arena-workbench';const heading=element('h1',context.route.screen==='bench'&&id(context.route.benchId)?`Benchmark ${identityKey('bench',context.route.benchId)}`:'Arena');heading.tabIndex=-1;heading.id='arena-heading-main';wrapper.append(heading);
    if(context.transport.mode==='fixture') wrapper.append(paragraph('Synthetic fixtures. Changes are unavailable.'));
    for(const text of [queryNotice,drafts.notice,mutationNotice,collision?'Identity key collision. Actions unavailable.':'']) if(text) wrapper.append(paragraph(text));
    if(context.route.screen==='arena') renderList(wrapper,q);else renderDetail(wrapper);
    host.replaceChildren(wrapper);
    if(headingFocus) document.getElementById(headingFocus)?.focus();
    if(focus) restoreFocus(host,focus,panelHeadings.get(focus.entity==='run'?'Task results':context.route.screen==='arena'?'Benchmarks':'Rule')??heading,announce);
  }
  function renderList(wrapper:HTMLElement,q:Record<string,string>):void {
    wrapper.append(paragraph('Compare agents, seats and memory arms against a rule declared before execution.'));
    const filters=element('div');filters.className='arena-filters';
    const filter=(key:string,label:string,action:string,values?:readonly string[])=>{
      const holder=element('label');holder.append(element('span',label));const field=values?element('select'):element('input');field.dataset.linAction=action;field.setAttribute('aria-label',label);
      if(field instanceof HTMLSelectElement) for(const value of values!) {const opt=element('option',value?title(value):'All');opt.value=value;field.append(opt);}else field.type='search';
      field.value=q[key]??'';field.addEventListener(values?'change':'input',()=>{const query={...q};if(field.value) query[key]=field.value;else delete query[key];navigateQuery(query);});holder.append(field);filters.append(holder);
    };
    filter('q','Find benchmarks','filter-bench-query');filter('purpose','Filter benchmarks by purpose','filter-bench-purpose',['','select','confirm']);filter('state','Filter benchmarks by state','filter-bench-state',['',...states]);
    filters.append(button('clear-bench-filters','Clear benchmark filters',()=>navigateQuery({})));wrapper.append(filters);
    mutationButton(wrapper,'bench_declare','declare-benchmark','Declare benchmark',trigger=>showForm('bench_declare',trigger));
    const panel=section('Benchmarks');wrapper.append(panel);
    if(!loaded&&!listError) panel.append(paragraph('Loading Arena.'));
    if(listError) failure(panel,'Benchmarks',listError,()=>{void load(nextAfter!==null&&loaded).catch(()=>{});});
    if(nextAfter!==null) panel.append(paragraph('Filters cover loaded records only. More benchmarks are available; search coverage is incomplete.'));
    if(!loaded) return;
    const filtered=list.filter(b=>(!q.q||JSON.stringify(b.declaration).toLowerCase().includes(q.q.toLowerCase()))&&(!q.purpose||b.declaration.purpose===q.purpose)&&(!q.state||b.state===q.state));
    if(!list.length&&!listError) panel.append(paragraph('No benchmarks yet.'));else if(!filtered.length) panel.append(paragraph('No matching benchmarks. Clear filters to see all loaded records.'));
    const rows=element('ul');rows.className='arena-benchmarks';
    for(const b of filtered) {
      const d=b.declaration,key=identityKey('bench',d.bench_id),row=element('li');row.dataset.linEntity='bench';row.dataset.linId=d.bench_id;
      const heading=element('h3',`Benchmark ${key}`),description=paragraph(d.bench_id);description.id=`arena-bench-${d.bench_id}`;
      row.append(heading,description,paragraph(`Baseline ${d.agents[0]} · Candidate ${d.agents[1]}`),paragraph(`${title(b.state)} · ${d.protocol} · ${d.purpose}`));
      const link=createLink({name:`Open benchmark ${key}`,action:'open-benchmark',href:`#/arena/${encodeURIComponent(d.bench_id)}`});link.setAttribute('aria-describedby',description.id);
      if(collision) {link.removeAttribute('href');link.setAttribute('aria-disabled','true');}
      else link.addEventListener('click',event=>{if(event.button===0&&!event.ctrlKey&&!event.metaKey&&!event.shiftKey&&!event.altKey) {event.preventDefault();context.navigate({screen:'bench',benchId:d.bench_id,query:{}});}});
      row.append(link);
      if(context.transport.mode!=='fixture'&&context.store.getState().mode!=='fixture'&&currentActor()&&context.store.getState().tools.some(t=>t.name==='bench_run')) {
        const run=button('launch-benchmark',`Run benchmark ${key}`,()=>context.navigate({screen:'bench',benchId:d.bench_id,query:{rule:'1'}}),collision);
        run.setAttribute('aria-describedby',description.id);row.append(run,paragraph('Review the declared rule, then confirm launch.'));
      }
      rows.append(row);
    }
    panel.append(rows);
    if(nextAfter!==null) panel.append(button('page-benches','Load more benchmarks',()=>{if(!pagePending) void load(true).catch(()=>{});},pagePending));
  }
  function ruleSummary(parent:HTMLElement,d:Declaration,details:boolean):void {
    parent.append(paragraph(`Baseline ${d.agents[0]} · Candidate ${d.agents[1]}`),paragraph(`Bank ${d.bank_id} · ${d.bank_sha256}`),paragraph(`Protocol ${d.protocol} · Purpose ${d.purpose} · Memory arms ${d.memory_arms.join(', ')}`));
    for(const seat of d.seats) parent.append(paragraph(`Seat ${seat.model} · ${seat.effort} · ${seat.mode}`));
    parent.append(paragraph(`Credit: ${d.credit_rule.metric}; dispersion ${d.credit_rule.dispersion}; minimum gain ${d.credit_rule.minimum_gain}; cost tiebreaker ${d.credit_rule.cost_tiebreaker}. Unknown costs never break ties.`));
    if(details) parent.append(paragraph(`SPRT: p0 ${d.sprt.p0}; p1 ${d.sprt.p1}; alpha ${d.sprt.alpha}; beta ${d.sprt.beta}; task cap ${d.sprt.cap}. Clean shadow runs ${d.promotion.n_shadow_runs}.`),paragraph('select uses selection tasks; confirm uses confirmation tasks. none omits recalled context; own recalls own context; inherited adds eligible inherited context. Every arm requires closing memory. Inherited memory benefit must be measured.'),paragraph('Declaration version detail: AUSENTE — no inventar. Frozen run versions are available in run inspectors.'));
  }
  function renderDetail(wrapper:HTMLElement):void {
    const route=context.route;
    if(route.screen!=='bench'||!id(route.benchId)) {wrapper.append(paragraph('Invalid benchmark identity. No operation is available.'));return;}
    const identity=paragraph(route.benchId);identity.className='full-identity';identity.id='arena-full-identity';wrapper.append(identity);
    const rule=section('Declared rule'),tasks=section('Task results'),verdict=section('Verdict');wrapper.append(rule,tasks,verdict);
    if(ruleError) {
      if(confirmed) rule.append(paragraph(`Data is stale. Last confirmed revision ${confirmed.head}.`));
      failure(rule,'Rule',ruleError,()=>{void load().catch(()=>{});});
    }
    if(!confirmed) {if(!ruleError) rule.append(paragraph('Loading Benchmark.'));return;}
    const d=confirmed.declaration,key=identityKey('bench',d.bench_id);
    rule.append(paragraph(title(confirmed.state)));
    if(synthetic.has(d.bench_id)) rule.append(paragraph('Synthetic offline benchmark'));
    const toggle=button('show-bench-rule',`Benchmark rule ${key}`,()=>{
      expanded=!expanded;if(expanded) displayed=JSON.stringify(d);render();navigateQuery({rule:expanded?'1':'0'});
    },collision);toggle.setAttribute('aria-expanded',String(expanded));rule.append(toggle);
    // Keep the complete prerequisite summary after a successful explicit disclosure.
    ruleSummary(rule,d,expanded);
    mutationButton(rule,'bench_run','launch-benchmark',`Launch benchmark ${key}`,trigger=>showForm('bench_run',trigger));
    rule.append(button('refresh-benchmark',`Refresh benchmark ${key}`,()=>{void load().catch(()=>{});}));
    if(resultsError) failure(tasks,'Task results',resultsError,()=>{void load().catch(()=>{});});
    if(!confirmed.results.length) tasks.append(paragraph('Task results pending. Not measured.'));
    for(const cell of confirmed.results) {
      const row=element('section');row.className='arena-task';row.dataset.linEntity='run';row.dataset.linId=cell.run_id;
      const runKey=identityKey('run',cell.run_id),heading=element('h3',`Run ${runKey}`),description=paragraph(cell.run_id);description.id=`arena-run-${cell.run_id}`;row.setAttribute('aria-labelledby',`arena-task-${cell.run_id}`);heading.id=`arena-task-${cell.run_id}`;
      row.append(heading,description,paragraph(`Task ${cell.task_id} · Agent ${cell.agent_id}`),paragraph(`Seat ${cell.seat.model} · ${cell.seat.effort} · ${cell.seat.mode} · Memory arm ${cell.memory_arm}`),paragraph(`Outcome ${cell.verdict} · Correctness ${cell.correctness}`));
      for(const [name,value] of Object.entries(cell.cost)) row.append(paragraph(`${name}: ${measurement(value)}`));
      for(const [action,label] of [['inspect-bench-result','Task result'],['open-bench-run','Inspect benchmark run']]) {const control=button(action,`${label} ${runKey}`,()=>inspect(cell,action==='inspect-bench-result'?'task result':'run',control),collision);control.setAttribute('aria-describedby',description.id);row.append(control);}
      const known=evidence.get(cell.run_id);
      if(known&&equal(known.cell,cell)&&eventId(known.event.id)) {const link=createLink({name:`Task evidence ${runKey}`,action:'open-task-evidence',href:`#/ledger?event=${encodeURIComponent(known.event.id)}`});link.setAttribute('aria-describedby',description.id);row.append(link);}else row.append(paragraph('Evidence: AUSENTE — no inventar. Refresh to retry resolution.'));
      tasks.append(row);
    }
    if(verdictError) failure(verdict,'Verdict',verdictError,()=>{void evaluate();});
    if(confirmed.verdict) {
      const v=confirmed.verdict;verdict.append(paragraph(`Decision ${v.decision}`),paragraph(`LLR ${v.llr} · Discordant tasks ${v.n_discordant}`),paragraph(`Credit gain ${v.credit.gain} · Baseline dispersion ${v.credit.baseline_dispersion} · Minimum reward ${v.credit.minimum_reward} · Credited ${v.credit.credited}`));
    } else verdict.append(paragraph('Verdict pending. Not measured.'));
    mutationButton(verdict,'bench_verdict','evaluate-benchmark',`Evaluate benchmark ${key}`,()=>{void evaluate();});
    mutationButton(verdict,'agent_promote','promote-candidate',`Promote candidate ${identityKey('agent',d.agents[1])}`,trigger=>showForm('agent_promote',trigger));
  }
  function transitions(next:Bench):void {
    const full=next.declaration.bench_id,old=prior.get(full),decision=next.verdict?.decision??null,key=identityKey('bench',full);
    if(old) {
      for(const [kind,value,previous] of [['state',next.state,old.state],['verdict',decision,old.decision]]) if(value&&value!==previous) {const token=JSON.stringify([full,kind,value]);if(!seenTransitions.has(token)) {seenTransitions.add(token);announce(token,`Benchmark ${key}: ${value}.`);}}
    }
    prior.set(full,{state:next.state,decision});
  }
  async function scan(signal:AbortSignal,token?:number):Promise<LedgerEvent[]> {
    let after=0;const events:LedgerEvent[]=[];const seen=new Set<number>();
    for(;;) {
      const page:any=await call('ledger_events',{after,limit:100},signal);if(!alive(token)||signal.aborted) return [];
      validatePage(page);if(page.resync) throw Error('Ledger changed. Resync required; mutation remains uncertain.');
      events.push(...page.events);if(!page.has_more) return events;
      if(page.next_after<=after||seen.has(page.next_after)) throw Error('Invalid ledger cursor; witness not confirmed.');seen.add(after);after=page.next_after;
    }
  }
  async function resolveEvidence(b:Bench,signal:AbortSignal,token:number):Promise<void> {
    try {
      const events=await scan(signal,token);if(!alive(token)) return;
      for(const cell of b.results) {
        for(const kind of ['bench.result','run.close','run.open']) {const match=events.find(e=>e.kind===kind&&witnessMatches(e,cell));if(match) {evidence.set(cell.run_id,{cell:structuredClone(cell),event:match});break;}}
      }
      resultsError='';
    } catch(error) {if(alive(token)) resultsError=errorText(error);}
  }
  async function load(page=false,recovery=false):Promise<void> {
    if(!alive()||page&&pagePending) return;
    const route=context.route,identity=route.screen==='bench'?route.benchId:'arena';
    if(context.store.getState().head===null&&context.store.getState().phase==='loading') {
      await new Promise<void>(resolve=>{
        let unsubscribe=()=>{};
        const finish=()=>{unsubscribe();context.signal.removeEventListener('abort',finish);resolve();};
        unsubscribe=context.store.subscribe(state=>{if(state.phase!=='loading') finish();});
        context.signal.addEventListener('abort',finish,{once:true});
        if(context.signal.aborted||context.store.getState().phase!=='loading') finish();
      });
    }
    if(!alive()) return;
    const tools=context.store.getState().tools,required=route.screen==='bench'?'bench_status':'bench_list';
    if(tools.length&&!tools.some(t=>t.name===required)) {
      const message=`${required} is unavailable in registered capabilities (bad_args).`;
      if(route.screen==='bench') ruleError=message;else listError=message;
      head=context.store.getState().head;host.setAttribute('aria-busy','false');render();
      announce(`arena:error:${required}`,`Error: ${route.screen==='bench'?'Benchmark':'Benchmarks'} unavailable (bad_args).`);
      return;
    }
    if(route.screen==='bench'&&!id(route.benchId)) {render();return;}
    const token=++epoch;request?.abort();request=new AbortController();const controller=request;
    const abort=()=>controller.abort();context.signal.addEventListener('abort',abort,{once:true});
    if(page) pagePending=true;host.setAttribute('aria-busy','true');render();
    try {
      if(route.screen==='arena') {
        const after=page?nextAfter:null;const args:JsonObject=after?{after}:{};const reply:any=await call('bench_list',args,controller.signal);
        if(!alive(token)||controller.signal.aborted) return;
        checkJson(reply);if(!isObject(reply)||!keysExactly(reply,['benches','next_after','head'])||!Array.isArray(reply.benches)||!integer(reply.head)||reply.next_after!==null&&!id(reply.next_after)) throw invalidResponse();
        const received=reply.benches.map(bench);
        if(page&&reply.next_after!==null&&after!==null&&String(reply.next_after)<=after) throw Error('Invalid repeated lexical cursor.');
        const merged=new Map((page?list:[]).map(b=>[b.declaration.bench_id,b]));for(const b of received) merged.set(b.declaration.bench_id,b);
        list=[...merged.values()].sort((a,b)=>a.declaration.bench_id.localeCompare(b.declaration.bench_id));nextAfter=reply.next_after as string|null;head=reply.head as number;loaded=true;listError='';
      } else if(route.screen==='bench') {
        const reply=await call('bench_status',{bench_id:route.benchId},controller.signal);if(!alive(token)||controller.signal.aborted) return;
        const next=statusReply(reply,route.benchId);
        if(confirmed&&next.head<confirmed.head) throw Error('Stale benchmark response.');
        const changed=confirmed&&!equal(confirmed.declaration,next.declaration);
        if(changed) {displayed='';expanded=false;}
        confirmed=next;head=next.head;ruleError='';transitions(next);
        if(expanded&&!changed) displayed=JSON.stringify(next.declaration);
        await resolveEvidence(next,controller.signal,token);
      }
      if(!alive(token)) return;loadDrafts();render();
    } catch(error) {
      if(!alive(token)||controller.signal.aborted) return;
      if(route.screen==='arena') listError=errorText(error);else ruleError=errorText(error);
      // A-ARN1: an absence refusal from the tool (no_*: e.g. no_benchmark) is a valid,
      // settled screen state shown as a named alert: readiness resolves. A
      // transport failure or malformed reply is not: the initial readiness
      // still rejects (U25 A02/A21), and the shell renders recovery.
      render();
      const refusal=error instanceof TransportError&&error.source==='domain'&&/^no_[a-z_]+$/u.test(error.code);
      if(!refusal&&!loaded&&!confirmed&&!recovery) throw error;
    } finally {
      context.signal.removeEventListener('abort',abort);
      if(alive(token)) {pagePending=false;host.setAttribute('aria-busy','false');render();}
    }
  }
  function showForm(tool:'bench_declare'|'bench_run'|'agent_promote',trigger:HTMLElement):void {
    if(reason(tool)) return;
    const scope=tool==='bench_declare'?'arena':confirmed!.declaration.bench_id,saved=drafts.get(tool,scope);
    if(tool==='bench_run') {saved.draft.fields.bench_id=scope;if(saved.draft.fields['runner.kind']===undefined) saved.draft.fields['runner.kind']='fake';}
    const openedHead=head!,target=confirmed?.declaration,openContext=context;
    openForm({tool,context:openContext,host,trigger,fallback:panelHeadings.get(tool==='bench_declare'?'Benchmarks':'Rule')!,declaration:tool==='bench_declare'?undefined:target,draft:saved.draft,notice:drafts.notice,
      save:()=>{drafts.save(saved);},onRecorded:()=>render(),
      submit:async(payload,feedback)=>{
        if(!alive()||context.route.screen!==(scope==='arena'?'arena':'bench')||scope!=='arena'&&(context.route as {benchId?:string}).benchId!==scope) return false;
        const done=await mutate(tool,payload,openedHead,saved,feedback);
        return done;
      },
    });
  }
  async function evaluate():Promise<void> {
    if(reason('bench_verdict')) return;
    const full=confirmed!.declaration.bench_id,saved=drafts.get('bench_verdict',full);
    await mutate('bench_verdict',{bench_id:full},head!,saved,message=>{verdictError=message;render();});render();
  }
  async function verify(tool:MutationTool,args:JsonObject,reply:any,signal:AbortSignal):Promise<Bench|null> {
    checkJson(reply);
    const c=reply.commit;if(!isObject(c)||!keysExactly(c,['event_ids','head','sha256'])||!Array.isArray(c.event_ids)||!c.event_ids.length||!c.event_ids.every(eventId)||!integer(c.head)||c.head<1||typeof c.sha256!=='string'||!/^[a-f0-9]{64}$/u.test(c.sha256)) throw Error('Uncertain: invalid commit witness.');
    const events=await scan(signal);if(!alive()) throw Error('Uncertain: cancelled witness read.');
    const committed=c.event_ids.map(full=>events.find(e=>e.id===full));if(committed.some(e=>!e)||new Set(c.event_ids).size!==c.event_ids.length||committed.some(e=>e!.lamport>Number(c.head))) throw Error('Uncertain: committed evidence not confirmed.');
    const tx=committed as LedgerEvent[],single=tx.length===1;
    if(single&&(tx[0].agent!==args.agent||tx[0].op_id!==args.op_id)) throw Error('Uncertain: actor or operation witness mismatch.');
    const full=tool==='bench_declare'?(args.declaration as Declaration).bench_id:String(args.bench_id);
    if(tool==='bench_declare') {
      const ack=bench(reply.bench);if(!equal(ack.declaration,args.declaration)||!tx.some(e=>e.kind==='bench.declared'&&equal(e.payload,args.declaration))) throw Error('Uncertain: declaration payload witness mismatch.');
    } else if(tool==='bench_verdict') {
      if(!tx.some(e=>e.kind==='bench.verdict'&&equal(e.payload,reply.verdict)&&e.payload.bench_id===full)) throw Error('Uncertain: verdict witness mismatch.');
    } else if(tool==='agent_promote') {
      if(!validAgent(reply.record)||reply.record.agent_id!==args.agent_id||!tx.some(e=>e.kind==='agent.status'&&e.payload.agent_id===args.agent_id&&e.payload.bench_id===full&&e.payload.to===reply.record.status)) throw Error('Uncertain: promotion witness mismatch.');
      const observed:any=await call('agent_get',{agent_id:String(args.agent_id)},signal);if(!equal(observed.record,reply.record)) throw Error('Uncertain: agent_get disagreement.');
    } else {
      const ack=bench(reply.bench);if(ack.declaration.bench_id!==full) throw Error('Uncertain: benchmark identity mismatch.');
      for(const e of tx) {
        const cell=ack.results.find(r=>witnessMatches(e,r));
        if(!cell||!['run.open','run.close','bench.result'].includes(e.kind)) throw Error('Uncertain: task payload witness mismatch.');
        if(e.kind==='run.open'||e.kind==='run.close') {
          const observed:any=await call('run_get',{run_id:cell.run_id},signal);
          if(!validRunReply(observed,cell)||e.kind==='run.open'&&!equal(e.payload,observed.opened.payload)||e.kind==='run.close'&&!equal(e.payload.record,observed.closed)) throw Error('Uncertain: run payload mismatch.');
        }
      }
    }
    const observed=statusReply(await call('bench_status',{bench_id:full},signal),full);
    if(tool==='bench_declare'&&!equal(observed.declaration,args.declaration)||tool==='bench_run'&&!equal(observed,reply.bench)||tool==='bench_verdict'&&!equal(observed.verdict,reply.verdict)) throw Error('Uncertain: bench_status disagreement.');
    return observed;
  }
  async function mutate(tool:MutationTool,payload:JsonObject,openedHead:number,saved:Saved,feedback:(message:string)=>void):Promise<boolean> {
    if(reason(tool)) {feedback(reason(tool));return false;}
    const actor=currentActor()!;
    const previous=saved.pending;let args:JsonObject;
    const effective=(v:JsonObject)=>Object.fromEntries(Object.entries(v).filter(([k])=>!['agent','op_id','expected_head'].includes(k))) as JsonObject;
    if(previous&&previous.actor===actor&&equal(effective(previous.args),payload)) args=structuredClone(previous.args);
    else {
      if(previous) mutationNotice='Prior operation remains uncertain. Edited fields or actor start a new operation.';
      args={...payload,agent:actor,op_id:`arena-${crypto.randomUUID()}`,expected_head:openedHead};
      saved.pending={tool,actor,op_id:String(args.op_id),expected_head:openedHead,args:structuredClone(args)};
    }
    const descriptor=context.store.getState().tools.find(t=>t.name===tool);
    if(!descriptor||!matches(args,descriptor.inputSchema)) {feedback('Invalid or unsupported arguments.');return false;}
    pendingTools.add(tool);drafts.save(saved);feedback(`${operation[tool]} pending. ${drafts.notice}`);announce(`pending:${args.op_id}`,`${operation[tool]} pending.`);
    const opContext=context,scope=saved.scope;
    try {
      const reply=await opContext.transport.call<JsonValue>(tool,args,{mutation:true,signal:opContext.signal});
      if(!alive()||opContext.signal.aborted) return false;
      const observed=await verify(tool,args,reply,opContext.signal);if(!alive()||opContext.signal.aborted) return false;
      if(tool==='bench_run'&&(args.runner as JsonObject).kind==='fake') synthetic.add(String(args.bench_id));
      if(observed&&context.route.screen==='bench'&&context.route.benchId===scope) {confirmed=observed;head=observed.head;transitions(observed);await resolveEvidence(observed,opContext.signal,epoch);}
      if(tool==='bench_declare') {const record=observed!;list=[...list.filter(b=>b.declaration.bench_id!==record.declaration.bench_id),record];head=record.head;}
      verdictError='';mutationNotice=mutationNotice.includes('Prior')?mutationNotice:'';drafts.complete(saved);
      const entity=tool==='agent_promote'?String(args.agent_id):tool==='bench_declare'?(args.declaration as Declaration).bench_id:String(args.bench_id);
      announce(`recorded:${args.op_id}`,`${operation[tool]} recorded for ${identityKey(tool==='agent_promote'?'agent':'bench',entity)}.`);
      return true;
    } catch(error) {
      if(!alive()||opContext.signal.aborted) return false;
      const e=error as {source?:string;code?:string};const message=e.source==='domain'?`${operation[tool]} refused: ${e.code}. ${errorText(error)}`:`Uncertain: ${errorText(error)}. Not confirmed; retry the unchanged operation explicitly.`;
      feedback(`${message} ${mutationNotice} ${drafts.notice}`);
      if(tool==='bench_verdict') verdictError=message;
      if(e.source==='domain') announce(`refused:${args.op_id}:${e.code}`,`${operation[tool]} refused: ${e.code}.`);
      return false;
    } finally {pendingTools.delete(tool);}
  }
  function inspect(cell:Cell,label:'run'|'task result',trigger:HTMLElement):void {
    if(collision||!alive()) return;
    const content=element('div');content.append(element('h2',`${label} ${identityKey('run',cell.run_id)}`));
    const body=element('div');content.append(body);let ticket=0;
    const modal=openDialog({name:`${label} ${identityKey('run',cell.run_id)}`,content,trigger,fallback:panelHeadings.get('Task results')!,host:trigger.closest<HTMLElement>('[data-lin-entity="run"]')??host,closeName:`Close ${label}`,closeAction:'close-inspector'});
    async function read():Promise<void> {
      const token=++ticket;body.replaceChildren(paragraph('Loading run.'));
      try {
        const reply:any=await call('run_get',{run_id:cell.run_id});if(!alive()||!modal.element.isConnected||token!==ticket) return;
        checkJson(reply);if(!validRunReply(reply,cell)) throw invalidResponse();
        const record=reply.closed??reply.opened.payload;body.replaceChildren();
        body.append(paragraph(`Run ${record.run_id} · Task ${record.task.id} · Agent ${record.agent_id} · Frozen version ${record.agent_version}`),paragraph(`Seat ${record.seat.model} · ${record.seat.effort} · ${record.seat.mode} · Memory arm ${record.memory_arm}`));
        if(record.task.split==='heldout') body.append(paragraph('Held out — confirmation only'));
        if(reply.closed===null) body.append(paragraph('Run open. Closing memory gate pending; task not closed.'));
        else {
          body.append(paragraph(`Outcome ${record.outcome.verdict}`),paragraph(record.memory.gate_passed?'Memory gate passed.':'Memory gate did not pass.'));
          for(const [name,value] of Object.entries(record.cost)) body.append(paragraph(`${name}: ${measurement(value)}`));
          for(const evidence of record.evidence) body.append(paragraph(`Evidence ${evidence.path} · ${evidence.sha256}`));
        }
      } catch(error) {if(alive()&&modal.element.isConnected&&token===ticket) {body.replaceChildren();failure(body,'Task results',errorText(error),()=>{void read();});}}
    }
    void read();
  }
  async function update(next:ScreenContext):Promise<void> {
    if(disposed||next.signal.aborted) return;
    const identity=next.route.screen==='bench'?next.route.benchId:'arena',query=JSON.stringify(next.route.query),changed=identity!==activeIdentity;
    if(changed) {
      request?.abort();closeDialogsWithin(host);confirmed=null;loaded=false;list=[];nextAfter=null;head=null;ruleError='';listError='';resultsError='';verdictError='';mutationNotice='';displayed='';
      context=next;activeIdentity=identity;expanded=next.route.query.rule==='1';
    } else context=next;
    const queryOnly=!changed&&query!==lastQuery&&(next.route.screen==='arena'||next.route.query.rule!==undefined)&&(confirmed!==null||loaded);lastQuery=query;
    if(next.route.screen==='bench'&&!id(next.route.benchId)) {render();return;}
    if(queryOnly) {if(next.route.screen==='bench'&&['0','1'].includes(next.route.query.rule)) {expanded=next.route.query.rule==='1';if(expanded&&confirmed&&!ruleError) displayed=JSON.stringify(confirmed.declaration);}render();return;}
    await load();
  }
  const actorChanged=()=>{if(alive()&&!host.querySelector('dialog')) render();};
  document.addEventListener('change',actorChanged);
  const ready=update(initial);
  return {ready,update,dispose() {if(disposed) return;disposed=true;++epoch;request?.abort();document.removeEventListener('change',actorChanged);closeDialogsWithin(host);}};
}};
