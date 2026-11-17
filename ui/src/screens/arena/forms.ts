import type { JsonObject, ScreenContext } from '../../ui/contracts.ts';
import { openDialog } from '../../ui/dialog.ts';
import { checkedName, createButton, identityKey } from '../../ui/primitives.ts';
import { agentId, errorText, id, integer, matches, seatId, validAgent, validDeclaration, validSeat, type Declaration, type Seat } from './model.ts';

export const declarationFields:readonly [string,string,string,(readonly string[])?][] = [
  ['declaration.bench_id','Benchmark ID','text'],['declaration.bank_id','Bank ID','text'],['declaration.bank_sha256','Bank hash','text'],
  ['declaration.protocol','Protocol','select',['paired','crossed']],['declaration.purpose','Purpose','select',['select','confirm']],
  ['declaration.credit_rule.minimum_gain','Credit rule minimum gain','number'],['declaration.credit_rule.cost_tiebreaker','Credit rule cost tiebreaker','checkbox'],
  ['declaration.sprt.p0','Null probability','number'],['declaration.sprt.p1','Alternative probability','number'],['declaration.sprt.alpha','Alpha','number'],['declaration.sprt.beta','Beta','number'],['declaration.sprt.cap','Task cap','number'],['declaration.promotion.n_shadow_runs','Clean shadow runs','number'],
];
export const allowedFields = new Set([...declarationFields.map(([path])=>path),'agents.new','seats.new.model','seats.new.effort','seats.new.mode','memory arms.new','runner.kind','runner.seed','bench_id']);
export type Draft={fields:Record<string,string|boolean>;agents:string[];seats:Seat[];arms:string[]};
export const emptyDraft=():Draft=>({fields:{},agents:[],seats:[],arms:[]});
export function validateDraft(v:any):v is Draft {
  if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).sort().join(',')!=='agents,arms,fields,seats'||!v.fields||typeof v.fields!=='object'||Array.isArray(v.fields)) return false;
  return Object.entries(v.fields).every(([k,x])=>allowedFields.has(k)&&(typeof x==='boolean'||typeof x==='string'&&x.length<=2048))&&Array.isArray(v.agents)&&v.agents.length<=2&&v.agents.every(agentId)&&new Set(v.agents).size===v.agents.length&&Array.isArray(v.seats)&&v.seats.length<=16&&v.seats.every(validSeat)&&new Set(v.seats.map(seatId)).size===v.seats.length&&Array.isArray(v.arms)&&v.arms.length<=3&&v.arms.every((x:string)=>['none','own','inherited'].includes(x))&&new Set(v.arms).size===v.arms.length;
}
export function fromDeclaration(d:Declaration):Draft {
  const draft=emptyDraft();draft.agents=[...d.agents];draft.seats=structuredClone(d.seats);draft.arms=[...d.memory_arms];
  for(const [path] of declarationFields) {let value:any=d;for(const k of path.split('.').slice(1)) value=value[k];draft.fields[path]=typeof value==='boolean'?value:String(value);}
  return draft;
}
export function buildDeclaration(draft:Draft):Declaration {
  const f=draft.fields, n=(path:string)=>String(f[path]??'').trim()===''?NaN:Number(f[path]);
  return {schema:'lineage.bench.declared/v1',bench_id:String(f['declaration.bench_id']??''),bank_id:String(f['declaration.bank_id']??''),bank_sha256:String(f['declaration.bank_sha256']??''),protocol:f['declaration.protocol'] as Declaration['protocol'],purpose:f['declaration.purpose'] as Declaration['purpose'],agents:[...draft.agents],seats:structuredClone(draft.seats),memory_arms:[...draft.arms],credit_rule:{metric:'correctness_first',dispersion:'population_stddev',minimum_gain:n('declaration.credit_rule.minimum_gain'),cost_tiebreaker:f['declaration.credit_rule.cost_tiebreaker']===true},sprt:{p0:n('declaration.sprt.p0'),p1:n('declaration.sprt.p1'),alpha:n('declaration.sprt.alpha'),beta:n('declaration.sprt.beta'),cap:n('declaration.sprt.cap')},promotion:{n_shadow_runs:n('declaration.promotion.n_shadow_runs')}};
}
export function paragraph(text:string):HTMLParagraphElement {const p=document.createElement('p');p.textContent=text;return p;}
function node<K extends keyof HTMLElementTagNameMap>(tag:K,text?:string):HTMLElementTagNameMap[K] {const el=document.createElement(tag);if(text!==undefined) el.textContent=text;return el;}
export interface FormOptions {
  tool:'bench_declare'|'bench_run'|'agent_promote';context:ScreenContext;host:HTMLElement;trigger:HTMLElement;fallback:HTMLElement;
  declaration?:Declaration;draft:Draft;notice:string;save():void;
  submit(args:JsonObject,feedback:(message:string)=>void):Promise<boolean>;
  onRecorded():void;
}
export function openForm(options:FormOptions):void {
  const {draft,tool,context}=options;
  const declare=tool==='bench_declare',launch=tool==='bench_run';const label=declare?'Declare benchmark':launch?'Launch benchmark':'Promote agent';const prefix=declare?'Declare':launch?'Launch':'Promote';
  const target=options.declaration;const targetKey=target?identityKey(launch?'bench':'agent',launch?target.bench_id:target.agents[1]):'';
  const content=node('div');content.className='arena-form';const heading=node('h2',label);const form=node('form');form.noValidate=true;form.setAttribute('aria-label',label+' form');
  const message=paragraph(options.notice);message.className='arena-error';message.id=`arena-${prefix}-feedback`;
  const fields=new Map<string,HTMLInputElement|HTMLSelectElement>();
  const confirm=createButton({name:`Confirm ${label}`,action:'submit-dialog',onActivate:()=>{}});confirm.type='submit';
  let pending=false,closed=false;
  const field=(path:string,human:string,kind='text',choices:readonly string[]=[]):HTMLInputElement|HTMLSelectElement=>{
    const wrapper=node('label');const name=`${prefix} ${human}`;const display=new TextEncoder().encode(name).length<=64?name:`${prefix} Field ${identityKey('field',path)}`;
    wrapper.append(node('span',human));const input=kind==='select'?node('select'):node('input');input.name=path;input.dataset.linAction='edit-field';input.setAttribute('aria-label',checkedName(display));input.setAttribute('aria-describedby',message.id);
    if(input instanceof HTMLSelectElement) {for(const value of choices) {const option=node('option',value);option.value=value;input.append(option);}input.value=String(draft.fields[path]??'');}
    else {input.type=kind;if(kind==='number') input.step='any';if(kind==='checkbox') input.checked=draft.fields[path]===true;else input.value=String(draft.fields[path]??'');}
    const changed=()=>{draft.fields[path]=input instanceof HTMLInputElement&&input.type==='checkbox'?input.checked:input.value;input.removeAttribute('aria-invalid');options.save();if(launch) confirm.disabled=pending||draft.fields['runner.kind']!=='fake';};
    input.addEventListener('input',changed);input.addEventListener('change',changed);wrapper.append(input);form.append(wrapper);fields.set(path,input);return input;
  };
  const reject=(path:string,reason:string)=>{message.textContent=reason;const input=fields.get(path);if(input) {input.setAttribute('aria-invalid','true');input.focus();}context.announce(`validation:${tool}:${path}:${reason}`,`${label} refused: bad_args.`);};
  if(target) {
    form.append(paragraph(`Baseline ${target.agents[0]} · Candidate ${target.agents[1]}`),paragraph(`Benchmark ${target.bench_id} · Bank ${target.bank_id} · ${target.bank_sha256} · ${target.purpose}`),paragraph(`Declared credit ${JSON.stringify(target.credit_rule)} · Memory arms ${target.memory_arms.join(', ')} · Seats ${target.seats.map(seatId).join('; ')}`));
  }
  if(declare) {
    form.append(paragraph('lineage.bench.declared/v1 · correctness_first · population_stddev'),paragraph('Enter a bank ID and its exact hash. Select measures selection tasks; confirm is confirmation only. none omits recalled context; own recalls own context; inherited adds eligible inherited context. Inherited memory benefit is not assumed. All arms still require closing memory.'));
    for(const [path,human,kind,choices] of declarationFields) field(path,human,kind,choices);
    const role=node('p');form.append(role);
    const roles=()=>{role.textContent=`Baseline ${draft.agents[0]??'Not selected'} · Candidate ${draft.agents[1]??'Not selected'}`;options.save();};
    const agentChoices=node('fieldset');agentChoices.append(node('legend','Participants — choose Baseline, then Candidate'));form.append(agentChoices);
    const seatChoices=node('fieldset');seatChoices.append(node('legend','Full seats'));form.append(seatChoices);
    const selectedAgents=new Set<string>(),selectedSeats=new Set<string>();
    function agentChoice(agent:any) {
      const full=agent.agent_id;if(selectedAgents.has(full)) return;selectedAgents.add(full);
      const wrapper=node('label');const input=node('input');input.type='checkbox';input.dataset.linAction='select-bench-agent';input.setAttribute('aria-label',`Benchmark agent ${identityKey('agent',full)}`);input.checked=draft.agents.includes(full);
      const description=paragraph(full);description.id=`arena-participant-${full}`;input.setAttribute('aria-describedby',description.id);
      input.addEventListener('change',()=>{if(input.checked&&!draft.agents.includes(full)) {if(draft.agents.length>=2) {input.checked=false;message.textContent='Exactly two distinct agents are required.';return;}draft.agents.push(full);}else if(!input.checked) draft.agents=draft.agents.filter(x=>x!==full);roles();});
      wrapper.append(input,node('span',full),description);agentChoices.append(wrapper);
      for(const seat of agent.allowed_seats as Seat[]) seatChoice(seat);
    }
    function seatChoice(seat:Seat) {
      const identity=seatId(seat);if(selectedSeats.has(identity)) return;selectedSeats.add(identity);
      const key=identityKey('seat',identity),wrapper=node('label'),input=node('input');input.type='checkbox';input.dataset.linAction='select-seat';input.setAttribute('aria-label',`Allow seat ${key}`);input.checked=draft.seats.some(s=>seatId(s)===identity);
      const description=paragraph(`${seat.model} · ${seat.effort} · ${seat.mode}`);description.id=`arena-seat-${key}`;input.setAttribute('aria-describedby',description.id);
      input.addEventListener('change',()=>{draft.seats=draft.seats.filter(s=>seatId(s)!==identity);if(input.checked) draft.seats.push(seat);options.save();});wrapper.append(input,description);seatChoices.append(wrapper);
    }
    field('agents.new','New agent ID');form.append(createButton({name:'Add agents',action:'add-item',onActivate:()=>{void (async()=>{
      const full=String(draft.fields['agents.new']??'');if(!agentId(full)) return reject('agents.new','Invalid agent ID.');if(draft.agents.includes(full)) {message.textContent='Duplicate agent already selected.';return;}
      if(draft.agents.length>=2) {message.textContent='Exactly two distinct agents are required.';return;}
      try {const reply=await context.transport.call<any>('agent_get',{agent_id:full},{mutation:false,signal:context.signal});if(closed||context.signal.aborted) return;if(!validAgent(reply.record)||reply.record.agent_id!==full) throw Error('Invalid agent response.');draft.agents.push(full);agentChoice(reply.record);for(const input of agentChoices.querySelectorAll<HTMLInputElement>('input')) if(input.getAttribute('aria-label')===`Benchmark agent ${identityKey('agent',full)}`) input.checked=true;roles();}catch(e) {if(!closed) message.textContent=errorText(e);}
    })();}}));
    field('seats.new.model','New seat model');field('seats.new.effort','New seat effort');field('seats.new.mode','New seat mode','select',['headless','interactive']);
    form.append(createButton({name:'Add seats',action:'add-item',onActivate:()=>{
      const seat={model:String(draft.fields['seats.new.model']??''),effort:String(draft.fields['seats.new.effort']??''),mode:draft.fields['seats.new.mode']} as Seat;
      if(!validSeat(seat)) return reject('seats.new.model','Invalid full seat tuple.');if(draft.seats.some(s=>seatId(s)===seatId(seat))) {message.textContent='Duplicate seat already selected.';return;}if(draft.seats.length>=16) {message.textContent='Seat limit reached.';return;}draft.seats.push(seat);seatChoice(seat);for(const input of seatChoices.querySelectorAll<HTMLInputElement>('input')) if(input.getAttribute('aria-label')===`Allow seat ${identityKey('seat',seatId(seat))}`) input.checked=true;options.save();
    }}));
    const arms=node('fieldset');arms.append(node('legend','Memory arms'));form.append(arms);
    for(const arm of ['none','own','inherited']) {const label=node('label'),input=node('input');input.type='checkbox';input.name=`memory arms.${arm}`;input.value=arm;input.dataset.linAction='edit-field';input.setAttribute('aria-label',`Declare Memory arm ${arm}`);input.checked=draft.arms.includes(arm);input.addEventListener('change',()=>{draft.arms=draft.arms.filter(a=>a!==arm);if(input.checked) draft.arms.push(arm);options.save();});label.append(input,node('span',arm));arms.append(label);}
    for(const full of draft.agents) {void context.transport.call<any>('agent_get',{agent_id:full},{mutation:false,signal:context.signal}).then(reply=>{if(!closed&&validAgent(reply.record)) agentChoice(reply.record);}).catch(()=>{});}
    for(const seat of draft.seats) seatChoice(seat);roles();
    void context.transport.call<any>('agent_list',{}, {mutation:false,signal:context.signal}).then(reply=>{if(closed||context.signal.aborted) return;for(const agent of reply.agents??[]) if(validAgent(agent)) agentChoice(agent);}).catch(e=>{if(!closed) message.textContent=errorText(e);});
  } else if(launch) {
    field('runner.kind','Runner kind','select',['fake','command']);field('runner.seed','Runner seed','number');
    form.append(paragraph('Use an explicit fake runner seed. Command execution is unavailable in this form; it remains available headlessly. Synthetic results do not prove real-agent fitness.'));
    confirm.disabled=draft.fields['runner.kind']!=='fake';
  } else {
    draft.fields.bench_id=target!.bench_id;const input=field('bench_id','Benchmark ID');if(input instanceof HTMLInputElement) input.readOnly=true;
    form.append(paragraph(`Candidate fixed: ${target!.agents[1]}. The server checks the declared seat, snapshot and credited evidence. Multiple seats cannot qualify; the server reports its refusal.`));
  }
  form.append(message,confirm);content.append(heading,form);
  const modal=openDialog({name:`${label}${targetKey?' '+targetKey:''}`,content,trigger:options.trigger,fallback:options.fallback,host:options.host,closeName:`Cancel ${label}`,closeAction:'cancel-dialog'});
  // Shared dismissal owns focus/inert semantics. Detached forms never apply asynchronous replies.
  const live=()=>!context.signal.aborted&&modal.element.isConnected;
  modal.element.addEventListener('keydown',e=>{if(e.key==='Escape') closed=true;});
  form.addEventListener('submit',event=>{event.preventDefault();if(pending||!live()) return;
    let args:JsonObject;
    if(declare) {
      const d=buildDeclaration(draft),f=draft.fields;
      const invalid=declarationFields.find(([path])=>{
        const value=f[path];if(path==='declaration.bench_id') return !id(value);if(path==='declaration.bank_id') return !agentId(value);if(path==='declaration.bank_sha256') return typeof value!=='string'||!/^[a-f0-9]{64}$/u.test(value);
        if(path==='declaration.protocol') return !['paired','crossed'].includes(String(value));if(path==='declaration.purpose') return !['select','confirm'].includes(String(value));
        if(path==='declaration.credit_rule.cost_tiebreaker') return typeof value!=='boolean';
        const n=String(value??'').trim()===''?NaN:Number(value);if(path.endsWith('minimum_gain')) return !Number.isFinite(n)||n<0||n>1;
        if(path.endsWith('.cap')||path.endsWith('n_shadow_runs')) return !integer(n)||n<1||n>1000000;
        if(!Number.isFinite(n)||n<=0||n>=1) return true;return path.endsWith('.p1')&&n<=d.sprt.p0;
      });
      if(invalid) return reject(invalid[0],'Invalid field: check hash, bounds, integer or probability; alternative probability must be greater than null probability.');
      if(!validDeclaration(d)) return reject('agents.new','Two distinct agents, unique full seats and nonempty unique memory arms are required.');args={declaration:d};
    } else if(launch) {
      if(draft.fields['runner.kind']!=='fake') return reject('runner.kind','Command runner is unavailable here; use the headless interface.');
      const raw=String(draft.fields['runner.seed']??''),seed=Number(raw);if(raw.trim()===''||!integer(seed)||seed>4294967295) return reject('runner.seed','Invalid seed: a bounded nonnegative integer is required.');args={bench_id:target!.bench_id,runner:{kind:'fake',seed}};
    } else args={agent_id:target!.agents[1],bench_id:target!.bench_id};
    pending=true;form.setAttribute('aria-busy','true');confirm.disabled=true;options.save();
    void options.submit(args,text=>{if(live()) message.textContent=text;}).then(success=>{if(!live()) return;if(success) {closed=true;modal.close();options.onRecorded();}}).finally(()=>{pending=false;form.setAttribute('aria-busy','false');if(live()) confirm.disabled=launch&&draft.fields['runner.kind']!=='fake';});
  });
}
