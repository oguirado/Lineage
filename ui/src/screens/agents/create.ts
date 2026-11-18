import type { JsonObject, JsonValue, ScreenContext } from '../../ui/contracts.ts';
import { openDialog } from '../../ui/dialog.ts';
import { identityKey } from '../../ui/primitives.ts';
import { TransportError, invalidResponse } from '../../transport.ts';
import { DRAFT_KEY, fieldsKeys, workflows, safeInt, id, validFields, validSeat, validArgs, admitDraft, equal, demand, errorText, skillsResult, referenceResult, creationResult, getResult, eventsResult, agrees, seatIdentity } from './model.ts';
import { node, button, panel } from './view.ts';
import type { CreateArgs, Draft, Fields, Pin, SkillPin, Seat, Read, Agent } from './types.ts';

export function createWorkflow(options:{host:HTMLElement;context:()=>ScreenContext;head:()=>number|null;read:Read;refresh:()=>Promise<void>;announce:(key:string,message:string)=>void}) {
  let draft:Draft|null=null,storageWarning='',loaded=false,session=0,disposed=false;
  let active:{element:HTMLDialogElement;close():void}|null=null;
  let updateDialog:()=>void=()=>{};
  const context=()=>options.context();
  const live=()=>context().transport.mode==='live';
  function acting():string|null {
    const el=document.querySelector<HTMLSelectElement>('[data-lin-action="select-actor"]');
    const selected=el?.selectedOptions[0];
    if(!el||el.matches(':disabled')||!selected||selected.disabled||selected.closest('optgroup')?.disabled) return null;
    return id(el.value)&&!['operator','system'].includes(el.value)?el.value:null;
  }
  function operation():string {return live()?'create-'+window.crypto.randomUUID():'';}
  function fresh():Draft {return {schema:'lineage.ui.create-draft/v1',fields:{agent_id:'',display_name:'',workflow:'',language:'',allowed_seats:[],references:[],skills:[]},seat_draft:{model:'',effort:'',mode:'headless'},actor:acting(),op_id:operation(),phase:'editing',submitted:null,unresolved:null};}
  function save() {
    if(!live()||!draft) return;
    try {const serialized=JSON.stringify(draft);demand(new TextEncoder().encode(serialized).length<=1048576);window.localStorage.setItem(DRAFT_KEY,serialized);}
    catch {storageWarning='Draft storage unavailable. Reload recovery cannot be guaranteed.';}
  }
  function recover() {
    if(loaded) return;loaded=true;
    if(live()) {try {const raw=window.localStorage.getItem(DRAFT_KEY);if(raw!==null) draft=admitDraft(raw);}catch {storageWarning='Saved draft invalid or recovery storage unavailable. Draft could not be recovered.';}}
    if(!draft) draft=fresh();
    else if(draft.phase==='editing'&&draft.actor===null&&draft.unresolved===null) draft.actor=acting();
    save();
  }
  function edit() {
    if(!draft) return;
    if(draft.submitted&&draft.op_id===draft.submitted.op_id) draft.op_id=operation();
    if(!draft.unresolved) draft.phase='editing';save();updateDialog();
  }
  const actorChanged=(event:Event)=>{if(!(event.target instanceof HTMLSelectElement)||event.target.dataset.linAction!=='select-actor'||!draft) return;draft.actor=acting();edit();};
  document.addEventListener('change',actorChanged);
  function leave() {if(draft?.unresolved&&(draft.phase==='pending'||draft.phase==='verifying')) {draft.phase='uncertain';save();}}
  function close() {leave();++session;active?.close();active=null;updateDialog=()=>{};}
  function open(trigger:HTMLElement,fallback:HTMLElement) {
    if(disposed||active?.element.isConnected) return;recover();const d=draft!;const currentSession=++session;
    let referencesReady=false,refsError='',skillsError='',message='',busy=false,refsPending=true,skillsPending=true,refsTurn=0,skillsTurn=0;
    let skills:(SkillPin&{retired:boolean})[]=[];
    const form=node('form');form.noValidate=true;form.className='agents-create';form.setAttribute('aria-label','Create agent form');
    form.append(node('h2','Create agent'),node('p','An agent has its own identity, constitution and memory. A seat is its model, effort and mode.','muted'));
    const inputs=new Map<string,HTMLInputElement|HTMLSelectElement>(),helps=new Map<string,HTMLElement>();
    const fieldset=node('fieldset');fieldset.append(node('legend','Identity and purpose'));
    function field(path:string,label:string,value:string,choices?:string[],parent:HTMLElement=fieldset) {
      const wrapper=node('div',undefined,'agents-field'),labelNode=node('label',label),input=choices?node('select'):node('input');
      input.name=path;input.dataset.linAction='edit-field';input.setAttribute('aria-label',`Create ${label}`);input.id='create-'+path.replaceAll('.','-');labelNode.htmlFor=input.id;
      if(input instanceof HTMLSelectElement) {const empty=node('option','Choose '+label.toLowerCase());empty.value='';input.append(empty);for(const v of choices??[]) {const o=node('option',v);o.value=v;input.append(o);}}
      input.value=value;const help=node('p','', 'agents-field-help');help.id=input.id+'-help';input.setAttribute('aria-describedby',help.id);wrapper.append(labelNode,input,help);parent.append(wrapper);inputs.set(path,input);helps.set(path,help);
      input.addEventListener(input instanceof HTMLSelectElement?'change':'input',()=>{
        if(path.startsWith('seat.')) (d.seat_draft as JsonObject)[path.slice(5)]=input.value;else d.fields[path]=input.value;
        input.removeAttribute('aria-invalid');help.textContent='';edit();
      });return input;
    }
    field('agent_id','Agent ID',d.fields.agent_id);field('display_name','Display name',d.fields.display_name);field('workflow','Workflow',d.fields.workflow,workflows);field('language','Language',d.fields.language);
    form.append(fieldset);
    const seats=node('fieldset');seats.append(node('legend','Allowed seats'));field('seat.model','Seat model',d.seat_draft.model,undefined,seats);field('seat.effort','Seat effort',d.seat_draft.effort,undefined,seats);field('seat.mode','Seat mode',d.seat_draft.mode,['headless','interactive'],seats);
    const seatList=node('ul');const add=button('add-item','Add seats',()=>{
      if(!validSeat(d.seat_draft)) {message='Enter a complete seat model, valid effort and mode.';updateDialog();return;}
      if(d.fields.allowed_seats.length>=16) {message='Maximum 16 seats.';updateDialog();return;}
      if(d.fields.allowed_seats.some(s=>equal(s,d.seat_draft))) {message='This complete seat tuple is already allowed.';updateDialog();return;}
      d.fields.allowed_seats.push({...d.seat_draft});message='';renderSeats();edit();
    });seats.append(add,seatList);form.append(seats);
    const referencePanel=node('section'),skillPanel=node('section'),statePanel=node('section');form.append(referencePanel,skillPanel,statePanel);
    const submit=node('button','Confirm Create agent');submit.type='submit';submit.dataset.linAction='submit-dialog';form.append(submit);
    active=openDialog({name:'Create agent',content:form,trigger,fallback,closeName:'Cancel Create agent',closeAction:'cancel-dialog',host:options.host});
    const modal=active;
    const current=()=>!disposed&&session===currentSession&&modal.element.isConnected&&!context().signal.aborted;
    const sameAttempt=()=>!!d.unresolved&&equal(d.fields,Object.fromEntries(fieldsKeys.map(k=>[k,d.unresolved![k]])))&&d.actor===d.unresolved.agent&&d.op_id===d.unresolved.op_id;
    function capability() {return context().store.getState().tools.some(t=>t.name==='agent_create');}
    function pinChoicesValid() {return d.fields.skills.length===0||!skillsError&&d.fields.skills.every(p=>skills.some(s=>!s.retired&&s.skill_id===p.skill_id&&s.sha256===p.sha256));}
    function collisions():boolean {
      for(const [kind,identities] of [['seat',d.fields.allowed_seats.map(seatIdentity)],['skill',skills.map(p=>p.skill_id+'@'+p.sha256)]] as const) {const keys=new Map<string,string>();for(const identity of identities) {const key=identityKey(kind,identity);if(keys.has(key)&&keys.get(key)!==identity) return true;keys.set(key,identity);}}return false;
    }
    function canSubmit() {return live()&&!busy&&referencesReady&&pinChoicesValid()&&!collisions()&&validFields(d.fields,true)&&!!acting()&&acting()===d.actor&&capability()&&safeInt(options.head())&&(!d.unresolved||sameAttempt());}
    function renderSeats() {
      seatList.replaceChildren();for(const seat of d.fields.allowed_seats) {
        const identity=seatIdentity(seat),key=identityKey('seat',identity),item=node('li');item.append(node('p',`${seat.model} / ${seat.effort} / ${seat.mode}`));
        item.append(button('remove-item',`Remove seats ${key}`,()=>{d.fields.allowed_seats=d.fields.allowed_seats.filter(s=>!equal(s,seat));renderSeats();edit();add.focus();}));seatList.append(item);
      }
    }
    function update() {
      if(!current()) return;
      form.setAttribute('aria-busy',String(busy||refsPending||skillsPending));
      submit.disabled=!canSubmit();for(const input of inputs.values()) input.disabled=busy;add.disabled=busy;
      statePanel.replaceChildren();
      if(storageWarning) statePanel.append(node('p',storageWarning));
      if(!live()) statePanel.append(node('p','Synthetic fixtures. Changes are unavailable.'));
      if(!acting()||acting()!==d.actor) statePanel.append(node('p','Choose an acting agent before creating. The draft actor must match the explicit acting agent.'));
      if(!capability()) statePanel.append(node('p','agent_create capability unavailable.'));
      if(!safeInt(options.head())) statePanel.append(node('p','Acknowledged revision unavailable. Refresh Agents before creating.'));
      if(!pinChoicesValid()) statePanel.append(node('p','Selected skill pins remain unresolved; retry Skills before submitting.'));
      if(collisions()) statePanel.append(node('p','Identity key collision. Actions unavailable.'));
      if(d.phase==='pending') statePanel.append(node('p','Create agent pending.'));
      else if(d.phase==='verifying') statePanel.append(node('p','Verifying the creation journal witness.'));
      else if(d.phase==='uncertain') statePanel.append(node('p','Create agent outcome uncertain and unverified. The original attempt is retained.'));
      if(message) statePanel.append(node('p',message));
      if(d.unresolved) {
        statePanel.append(node('p',`Unresolved creation ${d.unresolved.agent_id}; actor ${d.unresolved.agent}; operation ${d.unresolved.op_id}.`));
        // Amendment B adds separate reconciliation controls. K0's existing
        // registered retry and draft-item removal actions carry explicit local names.
        statePanel.append(button('retry-panel','Retry creation attempt',()=>{if(d.unresolved) void send(d.unresolved);},busy||!live()));
        statePanel.append(button('remove-item','Abandon creation attempt',()=>{void abandon();},busy||!live()));
      }
    }
    updateDialog=update;
    function renderReferences(descriptions:string[]=[]) {
      referencePanel.replaceChildren(node('h3','Founding references'));
      if(refsError) referencePanel.append(panel('References',refsError,()=>{void loadReferences();}));
      else if(!referencesReady) referencePanel.append(node('p','Verifying founding references.'));
      else for(const [i,pin] of d.fields.references.entries()) referencePanel.append(node('p',`${pin.id} ${pin.sha256} ${descriptions[i]??''}`));
    }
    function renderSkills() {
      skillPanel.replaceChildren(node('h3','Pinned skills'));
      if(skillsError) skillPanel.append(panel('Skills',skillsError+' You can continue with an empty skills selection; unresolved selected pins remain blocked.',()=>{void loadSkills();}));
      for(const pin of skills.filter(p=>!p.retired)) {
        const identity=pin.skill_id+'@'+pin.sha256,wrapper=node('div'),choice=node('input');wrapper.dataset.linEntity='skill';wrapper.dataset.linId=identity;
        choice.type='checkbox';choice.dataset.linAction='select-skill';choice.setAttribute('aria-label',`Pin skill ${identityKey('skill',identity)}`);choice.checked=d.fields.skills.some(p=>p.skill_id===pin.skill_id&&p.sha256===pin.sha256);choice.disabled=busy||!!skillsError;
        const description=node('p',identity);description.id='create-skill-'+identity;choice.setAttribute('aria-describedby',description.id);
        choice.addEventListener('change',()=>{d.fields.skills=d.fields.skills.filter(p=>!(p.skill_id===pin.skill_id&&p.sha256===pin.sha256));if(choice.checked) d.fields.skills.push({skill_id:pin.skill_id,sha256:pin.sha256});edit();});wrapper.append(choice,description);skillPanel.append(wrapper);
      }
    }
    async function loadReferences() {
      const t=++refsTurn;refsPending=true;referencesReady=false;refsError='';renderReferences();update();
      try {
        const results=await Promise.all(['gold_s1','memory_v21'].map(async refId=>{const [got,verified]=await Promise.all([options.read('reference_get',{ref_id:refId}),options.read('reference_verify',{ref_id:refId})]);return referenceResult(got,verified,refId);}));
        if(!current()||t!==refsTurn) return;
        d.fields.references=results.map(x=>x.pin);referencesReady=true;save();renderReferences(results.map(x=>x.description));
      }catch(e){if(!current()||t!==refsTurn) return;refsError=errorText(e);renderReferences();}refsPending=false;update();
    }
    async function loadSkills() {
      const t=++skillsTurn;skillsPending=true;skillsError='';update();
      try {const result=skillsResult(await options.read('skill_list',{}));if(!current()||t!==skillsTurn) return;skills=result;}
      catch(e){if(!current()||t!==skillsTurn) return;skills=[];skillsError=errorText(e);}
      skillsPending=false;renderSkills();update();
    }
    function invalidField() {
      const bad=!id(d.fields.agent_id)||['operator','system'].includes(d.fields.agent_id)?'agent_id':![...d.fields.display_name].length||[...d.fields.display_name].length>128?'display_name':!workflows.includes(d.fields.workflow)?'workflow':![...d.fields.language].length||[...d.fields.language].length>64?'language':d.fields.allowed_seats.length===0?'seat.model':null;
      if(bad) {const input=inputs.get(bad)!;input.setAttribute('aria-invalid','true');helps.get(bad)!.textContent='Enter a valid '+(input.labels?.[0]?.textContent??bad)+'.';input.focus();}return !!bad;
    }
    form.addEventListener('submit',event=>{event.preventDefault();if(invalidField()||!canSubmit()) return;
      if(d.unresolved) {void send(d.unresolved);return;}
      const head=options.head(),actor=acting();if(!safeInt(head)||!actor) return;
      // A refused unchanged request is explicitly re-confirmed against a fresh
      // baseline. Retaining op_id is legal: refusals have no journal entry.
      const args={...structuredClone(d.fields),agent:actor,op_id:d.op_id,expected_head:head};if(!validArgs(args)) return;void send(args);
    });
    form.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target!==submit) e.preventDefault();});
    modal.element.addEventListener('click',e=>{if(e.target instanceof HTMLElement&&e.target.dataset.linAction==='cancel-dialog'&&e.target.textContent==='Cancel Create agent') leave();});
    modal.element.addEventListener('keydown',e=>{if(e.key==='Escape') leave();});modal.element.addEventListener('cancel',leave);
    async function scan(a:CreateArgs,record?:Agent,commit?:{event_ids:string[];head:number}):Promise<boolean> {
      let after=commit?Math.max(0,commit.head-commit.event_ids.length):0,resynced=false;let found=false;
      // A bounded scan cannot silently prove absence when it exhausts its cap.
      for(let pages=0;pages<10000;pages++) {
        const page=eventsResult(await options.read('ledger_events',{after,limit:100,agent_id:a.agent_id,kinds:['agent.born']}));if(!current()) throw invalidResponse();
        if(page.resync) {message='Ledger changed. Resync required; filters kept.';update();if(resynced) throw invalidResponse();resynced=true;after=0;continue;}
        demand(page.next_after>=after&&(!page.has_more||page.next_after>after));
        for(const event of page.events) {
          if(event.kind!=='agent.born'||event.agent!==a.agent||event.op_id!==a.op_id) continue;
          const born=getResult({record:event.payload.record},a.agent_id);agrees(born,a);
          if(record) demand(equal(record,born)&&commit!.event_ids.includes(event.id)&&born.born.event_id===event.id&&event.lamport<=commit!.head);
          found=true;
        }
        if(commit&&page.next_after>=commit.head) return found;
        if(!page.has_more) return found;
        after=page.next_after;
      }throw invalidResponse();
    }
    async function complete(a:CreateArgs,eventId:string) {
      if(!current()) return;
      const edited=!sameAttempt();d.unresolved=null;d.phase='editing';
      options.announce(`created:${a.agent_id}:${eventId}`,`Create agent recorded for ${identityKey('agent',a.agent_id)}.`);
      if(edited) {d.submitted=null;save();message='Original creation recorded. Your edited draft is retained.';update();}
      else {
        try {if(live()) window.localStorage.removeItem(DRAFT_KEY);}catch{storageWarning='Draft storage unavailable; completed draft could not be removed.';}
        draft=null;loaded=false;modal.close();active=null;++session;updateDialog=()=>{};
      }
      await options.refresh();
    }
    async function send(a:CreateArgs) {
      if(!current()||busy||!live()) return;busy=true;message='';d.phase='pending';d.submitted=structuredClone(a);d.unresolved=structuredClone(a);save();update();renderSkills();
      options.announce(`create-pending:${a.agent}:${a.op_id}`,'Create agent pending.');
      let stage:'mutation'|'observation'='mutation';
      try {
        const raw=await context().transport.call<JsonValue>('agent_create',structuredClone(a),{mutation:true,signal:context().signal});if(!current()) return;
        if(raw&&typeof raw==='object'&&!Array.isArray(raw)&&raw.ok===false) throw new TransportError('domain',String(raw.code),'Create refused.',{detail:raw.detail});
        stage='observation';const {record,commit}=creationResult(raw,a);d.phase='verifying';save();update();
        const observed=getResult(await options.read('agent_get',{agent_id:a.agent_id}),a.agent_id);if(!current()) return;agrees(observed,a);demand(equal(record,observed));
        demand(await scan(a,record,commit));if(!current()) return;await complete(a,record.born.event_id);
      }catch(e) {
        if(!current()) return;
        if(stage==='mutation'&&e instanceof TransportError&&e.source==='domain') {
          d.phase='refused';d.unresolved=null;message=`Create agent refused: ${e.code}. ${errorText(e)}`;
          options.announce(`create-refused:${a.op_id}:${e.code}`,`Create agent refused: ${e.code}.`);
        }else {d.phase='uncertain';message=(message?message+' ':'')+'Create agent outcome uncertain and unverified. '+errorText(e);}
        save();
      }finally {busy=false;if(current()) {update();renderSkills();}}
    }
    async function abandon() {
      if(!d.unresolved||busy||!current()) return;busy=true;message='Checking the complete birth journal before abandoning the attempt.';update();
      try {
        const a=d.unresolved,found=await scan(a);if(!current()) return;
        if(found) {message='A matching birth exists. Retry creation attempt to verify its original commit; the attempt remains retained.';}
        else {d.unresolved=null;d.submitted=null;d.phase='editing';d.op_id=operation();message='Unverified attempt abandoned after a complete fresh negative birth scan.';save();}
      }catch(e){if(current()) message='Attempt remains unresolved. '+errorText(e);}finally{busy=false;if(current()) update();}
    }
    renderSeats();renderReferences();renderSkills();update();void loadReferences();void loadSkills();
  }
  return {open,close,update(){updateDialog();},dispose(){disposed=true;close();document.removeEventListener('change',actorChanged);}};
}
