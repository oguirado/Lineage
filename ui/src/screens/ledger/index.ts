import '../../../styles/ledger.css';
import type { EventsPage, JsonObject, JsonValue, LedgerEvent, Query, ScreenContext, ScreenModule, ToolDescriptor } from '../../ui/contracts.ts';
import { canonical, invalidResponse, isObject, keysExactly, TransportError, validateJson, validatePage, validateTools } from '../../transport.ts';
import { createButton, createLink, identityKey } from '../../ui/primitives.ts';
import { closeDialogsWithin, openDialog } from '../../ui/dialog.ts';

const kinds = ['reference.pinned','skill.published','skill.retired','agent.born','agent.status','memory.put','memory.retire','run.open','run.beat','run.close','bench.declared','bench.result','bench.verdict'];
const agentPattern = /^[a-z][a-z0-9-]{2,63}$/u;
const eventPattern = /^e-[0-9a-f]{16}$/u;
const hash = (v:unknown):v is string => typeof v==='string' && /^[0-9a-f]{64}$/u.test(v);
const integer = (v:unknown):v is number => typeof v==='number' && Number.isSafeInteger(v) && v>=0;
const relativePath = (v:unknown):v is string => typeof v==='string' && v.length>=1 && v.length<=512 && /^[A-Za-z0-9_./-]+$/u.test(v) && v.split('/').every(s=>!!s && s!=='.' && s!=='..');
const exportPath = (v:unknown):v is string => relativePath(v) && /^exports\/.+/u.test(v);
interface Verification {valid:true;head:number;sha256:string|null;torn_tail_bytes:number;issues:{path:string;line:number|null;code:string;detail:string}[]}
interface Exported {out:string;head:number;manifest:{path:string;sha256:string}[]}
function validateVerification(value:unknown):asserts value is Verification {
  validateJson(value);
  if(!isObject(value)||!keysExactly(value,['valid','head','sha256','torn_tail_bytes','issues'])||value.valid!==true||!integer(value.head)||!(value.sha256===null||hash(value.sha256))||!integer(value.torn_tail_bytes)||!Array.isArray(value.issues)) throw invalidResponse();
  for(const issue of value.issues) if(!isObject(issue)||!keysExactly(issue,['path','line','code','detail'])||!relativePath(issue.path)||!(issue.line===null||integer(issue.line)&&issue.line>=1)||!['hash_mismatch','bad_args','projection_drift','torn_tail'].includes(String(issue.code))||typeof issue.detail!=='string'||!issue.detail) throw invalidResponse();
}
function validateExport(value:unknown):asserts value is Exported {
  validateJson(value);
  if(!isObject(value)||!keysExactly(value,['out','head','manifest'])||!exportPath(value.out)||!integer(value.head)||!Array.isArray(value.manifest)||!value.manifest.length) throw invalidResponse();
  for(const item of value.manifest) if(!isObject(item)||!keysExactly(item,['path','sha256'])||!relativePath(item.path)||!hash(item.sha256)) throw invalidResponse();
}
function validateLedger(value:unknown):asserts value is EventsPage {
  // The shared boundary validates closed envelopes, hashes and passive JSON,
  // including prototype-sensitive keys. Kind-specific payload rules belong to
  // the authoritative journal validators.
  validatePage(value);
  if(value.events.length>100) throw invalidResponse();
  for(const event of value.events) {
    if(!eventPattern.test(event.id)||!agentPattern.test(event.agent)||!kinds.includes(event.kind)||!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/u.test(event.op_id)||event.evidence.length>64||event.evidence.some(e=>!relativePath(e.path))) throw invalidResponse();
  }
}
/** Refuse a discovered legacy tool before attempting a current-contract call. */
function compatibleTools(descriptors:readonly ToolDescriptor[]):Set<string> {
  validateTools(descriptors);
  const fields:Record<string,string[]>={ledger_events:['after','limit','wait_ms','agent_id','kinds','agent'],ledger_verify:['agent'],ledger_export:['out','agent']};
  const result=new Set<string>();
  for(const descriptor of descriptors) {
    const allowed=fields[descriptor.name];if(!allowed) continue;
    const schema=descriptor.inputSchema;
    if(schema.type!=='object'||schema.additionalProperties!==false||!isObject(schema.properties)||!Array.isArray(schema.required)) continue;
    const required=descriptor.name==='ledger_export'?['out']:[];
    if(Object.keys(schema.properties).length!==allowed.length||!allowed.every(key=>Object.hasOwn(schema.properties as JsonObject,key))||schema.required.length!==required.length||!required.every(key=>(schema.required as JsonValue[]).includes(key))) continue;
    result.add(descriptor.name);
  }
  return result;
}
function queryOf(query:Query):Record<string,string> {
  const result:Record<string,string>={};
  if(query.q) result.q=query.q;
  if(query.agent && agentPattern.test(query.agent)) result.agent=query.agent;
  if(kinds.includes(query.kind)) result.kind=query.kind;
  if(query.event && eventPattern.test(query.event)) result.event=query.event;
  return result;
}
function errorText(error:unknown):string {
  if(error instanceof TransportError) return `${error.source}: ${error.code}. ${error.message}${typeof error.detail==='string'?' '+error.detail:''}`;
  return error instanceof Error?error.message:'The request could not be completed.';
}
function element<K extends keyof HTMLElementTagNameMap>(tag:K,text?:string,className?:string):HTMLElementTagNameMap[K] {
  const node=document.createElement(tag);if(text!==undefined) node.textContent=text;if(className) node.className=className;return node;
}
interface RecordView {event:LedgerEvent;signature:string;key:string;node:HTMLElement;hashButton:HTMLButtonElement;payloadButton:HTMLButtonElement;hashes:HTMLElement;payload:HTMLElement;search?:string}

export const screen:ScreenModule={
  id:'ledger',title:'Ledger',
  mount(host,initialContext) {
    let context=initialContext,query=queryOf(context.route.query),disposed=false;
    let generation=0,actionGeneration=0,controller=new AbortController();
    let lookupTimer:ReturnType<typeof setTimeout>|null=null,lookupReading=false;
    // The first fold plus nine asynchronous continuations bounds automatic lookup.
    // Further pages require the existing Load more events action.
    let lookupRemaining=9;
    let pending:Promise<void>|null=null,loading=false,confirmed=false,cursor=0,pageHead:number|null=null,hasMore=false,resync=false;
    let failed:unknown=null,failedReplacement=true,verification:Verification|null=null,verificationError:unknown=null,verifying=false;
    let exporting=false,draft='',exported:Exported|null=null;
    let records=new Map<string,RecordView>(),positions=new Map<number,string>(),keys=new Map<string,string>();
    const actors=new Set<string>(),hashExpanded=new Set<string>(),payloadExpanded=new Set<string>();
    let signalCleanup=()=>{};
    const messages=new Map<string,string>();
    const heading=element('h1','Ledger');heading.tabIndex=-1;
    const intro=element('p','Inspect the authoritative journal, its immutable records and evidence.','ledger-intro');
    const toolbar=element('div',undefined,'ledger-toolbar');
    const filters=element('div',undefined,'ledger-filters');
    const search=element('input');search.type='search';search.dataset.linAction='filter-ledger-query';search.setAttribute('aria-label','Find ledger events');
    const agent=element('select');agent.dataset.linAction='filter-ledger-agent';agent.setAttribute('aria-label','Filter ledger by agent');
    const kind=element('select');kind.dataset.linAction='filter-ledger-kind';kind.setAttribute('aria-label','Filter ledger by kind');
    function label(text:string,control:HTMLElement) {const label=element('label',text);label.append(control);return label;}
    const clear=createButton({name:'Clear ledger filters',action:'clear-ledger-filters',onActivate:()=>navigate(query.event?{event:query.event}:{})});
    filters.append(label('Find ledger events',search),label('Filter ledger by agent',agent),label('Filter ledger by kind',kind),clear);
    const actions=element('div',undefined,'ledger-actions');
    const verifyButton=createButton({name:'Verify ledger chain',action:'verify-ledger',onActivate:()=>{void verify();}});
    const exportButton=createButton({name:'Export ledger',action:'export-ledger',onActivate:()=>openExport()});
    actions.append(verifyButton,exportButton);toolbar.append(filters,actions);
    const progress=element('div',undefined,'ledger-progress');
    const warning=element('div',undefined,'ledger-warning');
    const failure=element('section',undefined,'ledger-error');failure.setAttribute('aria-label','Ledger error');
    const coverage=element('p',undefined,'ledger-coverage');
    const targetMessage=element('p',undefined,'ledger-target');
    const empty=element('p',undefined,'ledger-empty');
    const list=element('ol',undefined,'ledger-events');list.setAttribute('aria-label','Ledger events');
    const moreArea=element('div',undefined,'ledger-pagination');
    const more=createButton({name:'Load more events',action:'page-events',onActivate:()=>{void read(false).catch(()=>{});}});moreArea.append(more);
    const verificationPanel=element('section',undefined,'ledger-verification');verificationPanel.setAttribute('aria-label','Verification');
    const exportPanel=element('section',undefined,'ledger-export');exportPanel.setAttribute('aria-label','Export result');
    host.replaceChildren(heading,intro,toolbar,progress,warning,failure,coverage,targetMessage,empty,list,moreArea,verificationPanel,exportPanel);

    function alive() {return !disposed&&!context.signal.aborted;}
    function announce(topic:string,message:string) {
      if(!alive()||messages.get(topic)===message) return;messages.set(topic,message);context.announce(`ledger:${topic}:${message}`,message);
    }
    function bindSignal() {
      signalCleanup();const signal=context.signal;
      const abort=()=>{cancelLookup();controller.abort();};signal.addEventListener('abort',abort,{once:true});signalCleanup=()=>signal.removeEventListener('abort',abort);
      if(signal.aborted) abort();
    }
    bindSignal();
    let tools=new Set<string>(),discoveryState:'pending'|'ready'|'error'='pending';
    async function discover(signal:AbortSignal) {
      const known=context.store.getState().tools;
      return compatibleTools(known.length?known:await context.transport.tools({signal}));
    }
    function navigate(next:Record<string,string>) {if(alive()) context.navigate({screen:'ledger',query:next});}
    search.addEventListener('input',()=>navigate({...query,q:search.value}));
    agent.addEventListener('change',()=>{const next={...query};if(agent.value) next.agent=agent.value;else delete next.agent;navigate(next);});
    kind.addEventListener('change',()=>{const next={...query};if(kind.value) next.kind=kind.value;else delete next.kind;navigate(next);});
    function options(select:HTMLSelectElement,values:readonly string[],first:string,selected:string) {
      const all=['',...new Set(values)];
      if(Array.from(select.options).map(o=>o.value).join('\0')!==all.join('\0')) {
        select.replaceChildren(...all.map(v=>{const option=element('option',v||first);option.value=v;return option;}));
      }
      select.value=selected;
    }
    function renderControls() {
      search.value=query.q??'';
      options(agent,[...new Set([...actors,...(query.agent?[query.agent]:[])])].sort(),'All observed agents',query.agent??'');
      options(kind,kinds,'All kinds',query.kind??'');
      more.disabled=loading||resync||!hasMore;more.hidden=!hasMore||resync;moreArea.hidden=more.hidden;
      verifyButton.disabled=verifying||discoveryState!=='ready'||!tools.has('ledger_verify');
      exportButton.disabled=exporting||discoveryState!=='ready'||context.transport.mode==='fixture'||!tools.has('ledger_export');
    }
    function renderVerification() {
      verificationPanel.setAttribute('aria-busy',String(verifying));
      verificationPanel.replaceChildren(element('h2','Verification'));
      if(discoveryState==='pending') verificationPanel.append(element('p','Checking ledger action dependencies.'));
      else if(discoveryState==='error') verificationPanel.append(element('p','Verification unavailable: dependency discovery failed. See Ledger error.'));
      else if(!tools.has('ledger_verify')) verificationPanel.append(element('p','Verification unavailable: missing or incompatible ledger_verify dependency.'));
      if(verifying) verificationPanel.append(element('p','Verification pending.'));
      if(verification) {
        verificationPanel.append(element('p',`Verified at head ${verification.head}.`),element('p',`SHA-256: ${verification.sha256??'Not measured'}`,'ledger-digest'));
        if(pageHead!==null&&pageHead!==verification.head) verificationPanel.append(element('p',`This verification applies only to head ${verification.head}; page head ${pageHead} is separate.`));
        if(verification.torn_tail_bytes) verificationPanel.append(element('p',`Warning: torn_tail — ${verification.torn_tail_bytes} uncommitted tail bytes.`));
        for(const issue of verification.issues) verificationPanel.append(element('p',`${issue.code}: ${issue.path}; line ${issue.line??'unknown'}. ${issue.detail}`));
      } else verificationPanel.append(element('p','Not verified'));
      if(verificationError) {
        verificationPanel.append(element('h3','Verification unavailable. Retry to continue.'),element('p',errorText(verificationError)));
        verificationPanel.append(createButton({name:'Retry Verification',action:'retry-panel',disabled:verifying,onActivate:()=>{void verify();}}));
      }
    }
    function renderExport() {
      exportPanel.setAttribute('aria-busy',String(exporting));
      exportPanel.replaceChildren();exportPanel.hidden=!exported&&!exporting&&discoveryState==='ready'&&tools.has('ledger_export')&&context.transport.mode!=='fixture';
      if(context.transport.mode==='fixture') exportPanel.append(element('p','Synthetic fixtures. Changes are unavailable.'));
      else if(discoveryState==='pending') exportPanel.append(element('p','Checking ledger action dependencies.'));
      else if(discoveryState==='error') exportPanel.append(element('p','Export unavailable: dependency discovery failed. See Ledger error.'));
      else if(!tools.has('ledger_export')) exportPanel.append(element('p','Export unavailable: missing or incompatible ledger_export dependency.'));
      if(exporting) exportPanel.append(element('p','Export ledger pending.'));
      if(exported) {
        exportPanel.append(element('h2','Export manifest'),element('p',`Full authoritative history exported at head ${exported.head} to ${exported.out}.`));
        exportPanel.append(element('p','Reported manifest; file contents require a separate integrity check.'));
        for(const item of exported.manifest) exportPanel.append(element('p',`${item.path} — SHA-256 ${item.sha256}`,'ledger-digest'));
      }
    }
    function renderState() {
      if(!alive()) return;
      host.setAttribute('aria-busy',String(loading));renderControls();
      progress.replaceChildren();progress.hidden=!loading&&!confirmed;
      if(loading) progress.append(element('p',confirmed?'Loading ledger events. Prior records remain stale until this read completes.':'Loading Ledger.'));
      if(pageHead!==null) progress.append(element('p',`Page head ${pageHead}. Scan cursor ${cursor}.`));
      warning.replaceChildren();warning.hidden=!resync;
      if(resync) {
        warning.append(element('h2','Ledger changed. Resync required; filters kept.'),element('p','Stale records. Restart the cursor to inspect the replacement history.'));
        warning.append(createButton({name:'Resync ledger',action:'resync-ledger',disabled:loading,onActivate:()=>{restart();}}));
      }
      failure.replaceChildren();failure.hidden=!failed;
      if(failed) {
        failure.append(element('h2','Ledger unavailable. Retry to continue.'),element('p',errorText(failed)));
        if(confirmed) failure.append(element('p',`Data is stale. Last confirmed revision ${pageHead}.`));
        failure.append(createButton({name:'Retry Ledger',action:'retry-panel',disabled:loading,onActivate:()=>{void read(failedReplacement).catch(()=>{});}}));
      }
      coverage.hidden=!confirmed;
      coverage.textContent=hasMore?'Partial coverage: search applies to loaded events only. Unscanned history remains; agent options are observed choices, not a complete catalogue.':'All history under the current server filters has been scanned. Agent options are observed choices.';
      targetMessage.hidden=!query.event||!confirmed;
      if(query.event) {
        if(records.has(query.event)) targetMessage.textContent=`Requested event ${query.event} is loaded.`;
        else if(resync||failed) targetMessage.textContent=`Search for event ${query.event} paused. Use the named recovery action to continue.`;
        else if(hasMore&&lookupRemaining===0&&!loading) targetMessage.textContent=`Search paused for event ${query.event} at cursor ${cursor}. Load more events to continue; unscanned history remains.`;
        else if(hasMore) targetMessage.textContent=`Looking for event ${query.event}. Sequential search in progress; scanned through cursor ${cursor}.`;
        else targetMessage.textContent=`Event ${query.event} not found${query.agent||query.kind?' under active filters':''}.`;
      }
      const anyVisible=Array.from(records.values()).some(matches);
      empty.hidden=!confirmed||anyVisible;
      empty.textContent=confirmed&&pageHead===0&&!query.q&&!query.agent&&!query.kind?'No ledger events yet.':'No matching events. Clear filters to see all loaded records.';
      renderVerification();renderExport();
    }
    function matches(record:RecordView):boolean {
      if(!query.q) return true;
      record.search??=[record.event.id,record.event.lamport,record.event.ts,record.event.agent,record.event.kind,record.event.op_id,record.event.sha256,record.event.prev_sha256,record.event.request_sha256,JSON.stringify(record.event.payload),JSON.stringify(record.event.evidence)].join(' ').toLowerCase();
      return record.search.includes(query.q.toLowerCase());
    }
    function selected(id:string) {if(context.store.getState().selection.ledger!==id) context.store.setSelection('ledger',id);}
    function disclosure(record:RecordView,which:'hash'|'payload',expanded:boolean) {
      const button=which==='hash'?record.hashButton:record.payloadButton;
      const panel=which==='hash'?record.hashes:record.payload;
      button.setAttribute('aria-expanded',String(expanded));panel.hidden=!expanded;
      if(expanded&&!panel.childNodes.length) {
        if(which==='hash') {
          for(const [label,value] of [['sha256',record.event.sha256],['prev_sha256',record.event.prev_sha256],['request_sha256',record.event.request_sha256]]) panel.append(element('p',`${label}: ${value}`,'ledger-digest'));
        } else {
          panel.append(element('h3','Payload'));
          const values=element('dl');
          const stack:{value:JsonValue;path:string}[]=[{value:record.event.payload,path:''}];
          while(stack.length) {
            const {value,path}=stack.pop()!;
            if(value!==null&&typeof value==='object') {
              const entries=Object.entries(value);
              if(!entries.length) values.append(element('dt',path),element('dd',Array.isArray(value)?'[]':'{}'));
              for(let i=entries.length-1;i>=0;i--) {
                const [key,child]=entries[i];stack.push({value:child,path:path?`${path}.${key}`:key});
              }
            } else values.append(element('dt',path),element('dd',typeof value==='string'?value:JSON.stringify(value)));
          }
          panel.append(values,element('h3','Evidence'));
          if(!record.event.evidence.length) panel.append(element('p','No evidence recorded.'));
          for(const item of record.event.evidence) panel.append(element('p',`${item.path} — SHA-256 ${item.sha256}`,'ledger-digest'));
        }
      }
    }
    function makeRecord(event:LedgerEvent,signature:string,key:string):RecordView {
      const node=element('li',undefined,'ledger-event');node.dataset.linEntity='event';node.dataset.linId=event.id;
      const title=element('h2',`Event ${key}`);title.id=`ledger-title-${event.id}`;node.setAttribute('aria-labelledby',title.id);
      const identity=element('p',event.id,'full-identity');identity.id=`ledger-identity-${event.id}`;
      // Journal timestamps and the fixture presentation clock are milliseconds.
      const stamp=Number.isFinite(new Date(event.ts).getTime())?new Intl.DateTimeFormat('en-GB',{timeZone:'UTC',dateStyle:'medium',timeStyle:'medium'}).format(event.ts)+' UTC':`Timestamp ${event.ts} ms`;
      const meta=element('p',`Lamport ${event.lamport} · ${stamp} · Actor ${event.agent} · ${event.kind}`,'ledger-metadata');
      const op=element('p',`Operation ${event.op_id}`,'ledger-operation');
      const controls=element('div',undefined,'ledger-record-actions');
      let record:RecordView;
      const hashButton=createButton({name:`Event hashes ${key}`,action:'toggle-event-hash',onActivate:()=>{
        if(!alive()) return;const expanded=!hashExpanded.has(event.id);expanded?hashExpanded.add(event.id):hashExpanded.delete(event.id);
        context.store.setExpanded('event',event.id,expanded);selected(event.id);disclosure(record,'hash',expanded);
      }});
      const payloadButton=createButton({name:`Event payload ${key}`,action:'toggle-event-payload',onActivate:()=>{
        if(!alive()) return;const expanded=!payloadExpanded.has(event.id);expanded?payloadExpanded.add(event.id):payloadExpanded.delete(event.id);selected(event.id);disclosure(record,'payload',expanded);
      }});
      const hashes=element('div',undefined,'ledger-hashes');hashes.id=`ledger-hashes-${event.id}`;
      const payload=element('div',undefined,'ledger-payload');payload.id=`ledger-payload-${event.id}`;
      for(const [button,panel] of [[hashButton,hashes],[payloadButton,payload]] as const) {button.setAttribute('aria-controls',panel.id);button.setAttribute('aria-describedby',identity.id);}
      controls.append(hashButton,payloadButton);
      if(event.agent!=='operator'&&event.agent!=='system') {
        const link=createLink({name:`Agent for event ${key}`,action:'open-event-agent',href:`#/agents/${event.agent}`});link.setAttribute('aria-describedby',identity.id);
        link.addEventListener('click',e=>{if(alive()&&e.button===0&&!e.ctrlKey&&!e.metaKey&&!e.shiftKey&&!e.altKey) {e.preventDefault();context.navigate({screen:'agent',agentId:event.agent,query:{}});}});controls.append(link);
      }
      node.append(title,identity,meta,op,controls,hashes,payload);
      record={event,signature,key,node,hashButton,payloadButton,hashes,payload};
      if(context.store.getState().expanded.includes(JSON.stringify(['event',event.id]))) hashExpanded.add(event.id);
      disclosure(record,'hash',hashExpanded.has(event.id));disclosure(record,'payload',payloadExpanded.has(event.id));return record;
    }
    function filterRows() {
      const active=document.activeElement;
      const focused=active instanceof HTMLElement?active.closest<HTMLElement>('[data-lin-entity="event"]')?.dataset.linId:undefined;
      const fragment=document.createDocumentFragment();for(const record of records.values()) if(matches(record)) fragment.append(record.node);
      list.replaceChildren(fragment);renderState();
      if(focused&&active instanceof HTMLElement) {
        if(active.isConnected) active.focus();
        else {heading.focus();announce('focus',`${identityKey('event',focused)} is hidden by the current filters.`);}
      }
    }
    function abortOperations() {
      ++actionGeneration;verifying=false;exporting=false;closeDialogsWithin(host);
    }
    function cancelLookup() {
      if(lookupTimer!==null) clearTimeout(lookupTimer);lookupTimer=null;
    }
    function scheduleLookup() {
      cancelLookup();
      const target=query.event,turn=generation;
      if(!alive()||!confirmed||pending||loading||failed||resync||!hasMore||!target||records.has(target)||lookupRemaining===0) return;
      // Yield a browser turn between cursor responses; readiness belongs to the first fold.
      lookupTimer=setTimeout(()=>{
        lookupTimer=null;
        if(!alive()||turn!==generation||query.event!==target||pending||loading||failed||resync||!hasMore||records.has(target)) return;
        lookupRemaining--;lookupReading=true;void read(false).catch(()=>{});
      },0);
    }
    function restart() {
      if(!alive()) return;
      cancelLookup();lookupReading=false;
      ++generation;controller.abort();controller=new AbortController();abortOperations();pending=null;loading=false;
      void read(true).catch(()=>{});
    }
    let initialSettled=false;
    let resolveReady!:()=>void,rejectReady!:(error:unknown)=>void;
    const ready=new Promise<void>((resolve,reject)=>{resolveReady=resolve;rejectReady=reject;});
    // A consumer may dispose synchronously before subscribing to initial failure.
    void ready.catch(()=>{});
    function settle(error?:unknown) {
      if(initialSettled) return;initialSettled=true;if(error!==undefined) rejectReady(error);else resolveReady();
    }
    async function fold(page:EventsPage,replace:boolean,after:number,turn:number) {
      validateLedger(page);
      if(page.resync) {
        if(after<=page.head||page.events.length>0||page.next_after!==0||page.has_more) throw invalidResponse();
        resync=true;announce('resync','Ledger changed. Resync required; filters kept.');return;
      }
      if(page.next_after>page.head||page.has_more!==(page.next_after<page.head)||page.next_after<after||((page.has_more||page.events.length>0)&&page.next_after<=after)||(!replace&&pageHead!==null&&page.head<pageHead)||page.events.some(e=>e.lamport<=after)) throw invalidResponse();
      // Validate the complete prospective fold before publishing any record or cursor.
      const replacingHistory=replace&&resync;
      const nextKeys=replace?new Map<string,string>():new Map(keys);
      const nextPositions=replace?new Map<number,string>():new Map(positions);
      const staged:{event:LedgerEvent;signature:string;key:string}[]=[];
      let previous=after;
      for(const event of page.events) {
        if(event.lamport<1||event.lamport<=previous||event.lamport>page.head||event.lamport>page.next_after) throw invalidResponse();
        previous=event.lamport;
        const signature=canonical(event as unknown as JsonValue),prior=records.get(event.id),at=nextPositions.get(event.lamport);
        if(!replacingHistory&&prior&&prior.signature!==signature||at&&at!==event.id) throw invalidResponse();
        const key=identityKey('event',event.id),collision=nextKeys.get(key);
        if(collision&&collision!==event.id) throw Error('Identity key collision. Actions unavailable.');
        nextKeys.set(key,event.id);nextPositions.set(event.lamport,event.id);staged.push({event,signature,key});
      }
      if(context.store.getState().head!==page.head) {
        await context.store.refresh();
        if(!alive()||turn!==generation) return;
        if(context.store.getState().head!==page.head) throw Error('Ledger snapshot unavailable: shared revision does not acknowledge the page head.');
      }
      if(!alive()||turn!==generation) return;
      const oldSelected=context.store.getState().selection.ledger??(confirmed?query.event:undefined);
      const active=document.activeElement;
      const focusRecord=active instanceof HTMLElement?active.closest<HTMLElement>('[data-lin-entity="event"]')?.dataset.linId:undefined;
      const next=replace?new Map<string,RecordView>():records;
      const fragment=document.createDocumentFragment();
      for(const item of staged) {
        let record=records.get(item.event.id);
        if(!record||record.signature!==item.signature) record=makeRecord(item.event,item.signature,item.key);
        next.set(item.event.id,record);actors.add(item.event.agent);
        if(matches(record)&&(replace||!record.node.isConnected)) fragment.append(record.node);
      }
      records=next;positions=nextPositions;keys=nextKeys;
      if(replace) list.replaceChildren(fragment);else list.append(fragment);
      cursor=page.next_after;pageHead=page.head;hasMore=page.has_more;confirmed=true;failed=null;
      if(replace) resync=false;
      const removedSelection=oldSelected&&!records.has(oldSelected)?oldSelected:undefined;
      const removedFocus=focusRecord&&!records.has(focusRecord)?focusRecord:undefined;
      if(removedSelection) {
        context.store.setSelection('ledger',null);hashExpanded.delete(removedSelection);payloadExpanded.delete(removedSelection);
      }
      if(removedFocus||removedSelection) {
        heading.focus();announce('removal',`${identityKey('event',(removedFocus??removedSelection)!)} is no longer in this view.`);
      } else if(active instanceof HTMLElement&&focusRecord) {
        const record=records.get(focusRecord);
        if(record?.node.isConnected) {
          const action=active.dataset.linAction;
          const replacement=action?record.node.querySelector<HTMLElement>(`[data-lin-action="${action}"]`):null;
          if(active.isConnected) active.focus();else (replacement??heading).focus();
        } else heading.focus();
      }
      if(query.event&&records.has(query.event)) selected(query.event);
      messages.delete('read-error');if(replace) messages.delete('resync');
      announce('fold',`Ledger ready. Head ${page.head}.`);
    }
    function read(replace:boolean):Promise<void> {
      if(!alive()) return Promise.resolve();
      if(pending) return pending;
      const turn=generation,after=replace?0:cursor;
      const args:JsonObject={after,limit:100,wait_ms:0};
      if(query.agent) args.agent_id=query.agent;if(query.kind) args.kinds=[query.kind];
      if(replace) lookupRemaining=9;
      failedReplacement=replace;loading=true;discoveryState='pending';renderState();
      const current=()=>alive()&&generation===turn&&!controller.signal.aborted;
      const work=(async()=>{
        try {
          let discovered:Set<string>;
          try {discovered=await discover(controller.signal);}
          catch(error) {if(current()) discoveryState='error';throw error;}
          if(!current()) return;tools=discovered;discoveryState='ready';renderState();
          if(!tools.has('ledger_events')) throw Error('Ledger unavailable: missing or incompatible ledger_events dependency.');
          const value=await context.transport.call('ledger_events',args,{mutation:false,signal:controller.signal});
          if(!current()) return;
          await fold(value as unknown as EventsPage,replace,after,turn);
          if(current()) {loading=false;renderState();if(!resync) settle();}
        } catch(error) {
          if(!current()) return;
          failed=error;messages.delete('fold');loading=false;renderState();announce('read-error','Ledger unavailable. Retry to continue.');settle(error);throw error;
        } finally {if(turn===generation) {pending=null;loading=false;lookupReading=false;scheduleLookup();}}
      })();pending=work;return work;
    }
    async function verify() {
      if(!alive()||verifying||!tools.has('ledger_verify')) return;
      const turn=actionGeneration;verifying=true;verificationError=null;renderControls();renderVerification();
      const current=()=>alive()&&turn===actionGeneration&&!controller.signal.aborted;
      try {
        const result=await context.transport.call('ledger_verify',{}, {mutation:false,signal:controller.signal});if(!current()) return;
        validateVerification(result);verification=result;announce('verification',`Verification reported at head ${result.head}.`);
      } catch(error) {if(!current()) return;verificationError=error;announce('verify-error',`Verification unavailable. ${errorText(error)}`);}
      finally {if(current()) {verifying=false;renderControls();renderVerification();}}
    }
    function openExport() {
      if(!alive()||exportButton.disabled||host.querySelector('dialog[open]')) return;
      const form=element('form');form.noValidate=true;
      const title=element('h2','Export ledger');
      const explanation=element('p','Export the full authoritative history, independent of these filters. The destination is relative to runtime home and must be beneath exports/. The service enforces filesystem confinement.');
      const field=element('input');field.name='out';field.dataset.linAction='edit-field';field.setAttribute('aria-label','Export Export directory');field.value=draft;field.autocomplete='off';
      const help=element('p','Use a non-empty directory beneath exports/, with no empty, dot or traversal segments.');help.id='ledger-export-help';
      const error=element('p');error.id='ledger-export-error';field.setAttribute('aria-describedby',`${help.id} ${error.id}`);
      const submit=element('button','Confirm Export ledger');submit.type='submit';submit.dataset.linAction='submit-dialog';
      form.append(title,explanation,label('Export directory',field),help,error,submit);
      field.addEventListener('input',()=>{draft=field.value;field.removeAttribute('aria-invalid');});
      const dialog=openDialog({name:'Export ledger',content:form,trigger:exportButton,fallback:heading,closeName:'Cancel Export ledger',closeAction:'cancel-dialog',host});
      form.addEventListener('submit',event=>{
        event.preventDefault();if(!alive()||exporting) return;
        draft=field.value;
        if(!exportPath(draft)) {
          field.setAttribute('aria-invalid','true');error.textContent='Invalid export directory. Enter a relative directory beneath exports/.';field.focus();announce('export-validation','Export ledger refused: bad_args.');return;
        }
        const turn=actionGeneration;
        exporting=true;exported=null;submit.disabled=true;error.textContent='Export ledger pending.';renderControls();renderExport();announce('export-pending','Export ledger pending.');
        const current=()=>alive()&&turn===actionGeneration&&dialog.element.isConnected&&!controller.signal.aborted;
        void (async()=>{
          try {
            const result=await context.transport.call('ledger_export',{out:draft},{mutation:true,signal:controller.signal});
            if(!current()) return;
            validateExport(result);exported=result;announce('export-result',`Export manifest reported at head ${result.head}.`);dialog.close();
          } catch(reason) {
            if(!current()) return;error.textContent=`Export ledger refused or uncertain. ${errorText(reason)}`;announce('export-error',`Export ledger refused or uncertain. ${errorText(reason)}`);
          } finally {if(alive()&&turn===actionGeneration) {exporting=false;submit.disabled=false;renderControls();renderExport();}}
        })();
      });
    }
    renderState();void read(true).catch(()=>{});
    return {
      ready,
      update(next:ScreenContext):Promise<void> {
        if(disposed) return Promise.resolve();
        const previous=query;context=next;query=queryOf(next.route.query);bindSignal();
        const serverChanged=previous.agent!==query.agent||previous.kind!==query.kind;
        const localChanged=previous.q!==query.q||previous.event!==query.event;
        if(!alive()) return Promise.resolve();
        if(serverChanged) {
          cancelLookup();lookupReading=false;
          ++generation;controller.abort();controller=new AbortController();abortOperations();pending=null;loading=false;exported=null;
          return read(true);
        }
        if(localChanged) {
          cancelLookup();
          if(previous.event!==query.event) lookupRemaining=9;
          if(previous.event!==query.event||lookupReading) {
            ++generation;controller.abort();controller=new AbortController();pending=null;loading=false;lookupReading=false;
          }
          abortOperations();exported=null;if(controller.signal.aborted) {++generation;controller=new AbortController();pending=null;loading=false;}
          filterRows();
          if(!confirmed) return pending??read(true);
          if(query.event&&records.has(query.event)) selected(query.event);scheduleLookup();return Promise.resolve();
        }
        if(pending&&!confirmed) return pending;
        cancelLookup();lookupReading=false;
        ++generation;controller.abort();controller=new AbortController();abortOperations();pending=null;loading=false;
        return read(true);
      },
      dispose() {if(disposed) return;disposed=true;++generation;++actionGeneration;cancelLookup();controller.abort();signalCleanup();closeDialogsWithin(host);},
    };
  },
};
