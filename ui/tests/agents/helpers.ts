import { afterEach, beforeEach, expect, vi } from 'vitest';
import { setImmediate } from 'node:timers';
const nextDomTurn = setImmediate;
import type { AppState, AppStore, CallOptions, JsonObject, JsonValue, MountedScreen, Route, ScreenContext, ToolDescriptor, Transport } from '../../src/ui/contracts.ts';
import { actions } from '../../src/ui/contracts.ts';
import { screen } from '../../src/screens/agents/index.ts';
import { getScreen } from '../../src/screens/index.ts';
import { TransportError, canonical, createHttpTransport } from '../../src/transport.ts';
import { identityKey } from '../../src/ui/primitives.ts';
import { closeDialogsWithin } from '../../src/ui/dialog.ts';
import { CLOCK, DRAFT_KEY, agent, args, clone, creation, descriptors, hash, page, refs, sampleAgents, skill } from './fixtures.ts';

vi.setConfig({testTimeout:4000,hookTimeout:4000});
export function deferred<T = JsonObject>() {
  let resolve!: (value: T) => void; let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes,no) => {resolve=yes;reject=no;});
  return {promise,resolve,reject};
}
export async function flush(): Promise<void> { for(let i=0;i<80;i++) await Promise.resolve(); }
const owned: (() => void)[] = [];
export function isolate(): void {
  beforeEach(() => {
    document.body.replaceChildren();window.localStorage.clear();window.history.replaceState(null,'','/#/agents');
    document.documentElement.dataset.linReady='false';document.documentElement.removeAttribute('data-lin-rev');
    vi.useFakeTimers();vi.setSystemTime(CLOCK);
    vi.stubGlobal('fetch',vi.fn(() => {throw Error('Real network is forbidden by the oracle.');}));
    vi.stubGlobal('matchMedia',vi.fn((query: string) => ({matches:false,media:query,addEventListener:vi.fn(),removeEventListener:vi.fn()})));
    let random=0;
    vi.spyOn(window.crypto,'getRandomValues').mockImplementation((value: any) => {for(let i=0;i<value.length;i++) value[i]=(++random)%256;return value;});
    vi.spyOn(window.crypto,'randomUUID').mockImplementation(() => `00000000-0000-4000-8000-${String(++random).padStart(12,'0')}`);
  });
  afterEach(async () => {
    for(const cleanup of owned.splice(0).reverse()) cleanup();
    closeDialogsWithin(document.body);vi.useRealTimers();vi.restoreAllMocks();vi.unstubAllGlobals();document.body.replaceChildren();
    // Drain jsdom's already queued DOM callbacks before the next test's clock spies.
    // This advances the event loop without a sleep or elapsed-time condition.
    await new Promise<void>(done => nextDomTurn(done));
  });
}
export const failure = (code = 'network', source: 'domain'|'transport' = 'transport', detail = '<img src=x onerror=attack()>') =>
  new TransportError(source,code,`Synthetic ${code}`,{detail});
export interface Call {tool: string; args: JsonObject; options: CallOptions}
export class Service {
  records = sampleAgents();head = 7;mode: 'live'|'fixture' = 'live';tools = descriptors();
  scorecards = new Map<string, JsonObject[]>();events: import('../../src/ui/contracts.ts').LedgerEvent[] = [];
  calls: Call[] = [];overrides = new Map<string,(args: JsonObject,options: CallOptions) => unknown>();
  replays = new Map<string,{digest: string; result: JsonObject}>();
  transport: Transport;
  constructor() {
    this.transport = {get mode(){return self.mode;},get fixtureId(){return self.mode==='fixture'?'demo':null;},
      get presentation(){return self.mode==='fixture'?{clockMs:CLOCK,locale:'en-GB',timezone:'UTC',theme:'light'} as const:null;},
      tools:vi.fn(async () => clone(this.tools)),events:vi.fn(async () => clone(page([],this.head)) as any),
      call:vi.fn(async <T extends JsonValue>(tool: string,values: JsonObject,options: CallOptions): Promise<T> => {
        this.calls.push({tool,args:clone(values),options});
        if(this.mode==='fixture' && options.mutation) throw failure('fixture_readonly','domain');
        const handler=this.overrides.get(tool);
        return clone(await (handler?handler(values,options):this.reply(tool,values))) as T;
      }) as Transport['call']};
    const self = this;
  }
  reply(tool: string, a: JsonObject): JsonObject {
    if(tool==='agent_list') {
      let records=this.records.filter(r => (!a.workflow||r.workflow===a.workflow)&&(!a.language||r.language===a.language)&&(!a.status||r.status===a.status)&&
        (a.include_retired===true||a.status==='retired'||r.status!=='retired')).sort((x,y) => String(x.agent_id)<String(y.agent_id)?-1:1);
      if(a.after) records=records.filter(r => String(r.agent_id)>String(a.after));
      const limit=typeof a.limit==='number'?a.limit:100;const selected=records.slice(0,limit);
      return {agents:selected,next_after:records.length>limit?selected.at(-1)!.agent_id:null,head:this.head};
    }
    if(tool==='agent_get') {const record=this.records.find(r => r.agent_id===a.agent_id);if(!record) throw failure('no_agent','domain');return {record};}
    if(tool==='scorecard_get') return {agent_id:a.agent_id,groups:this.scorecards.get(String(a.agent_id))??[],head:this.head};
    if(tool==='reference_get') return {reference:{id:a.ref_id,sha256:refs().find(r => r.id===a.ref_id)!.sha256,bytes:64,rules:[{id:'synthetic-rule',section:'synthetic',text:'Passive synthetic rule.'}]}};
    if(tool==='reference_verify') return {ref_id:a.ref_id,sha256:refs().find(r => r.id===a.ref_id)!.sha256,bytes:64,valid:true};
    if(tool==='skill_list') return {skills:[{...skill(),retired:false}]};
    if(tool==='agent_create') {
      const key=JSON.stringify([a.agent,a.op_id]);const effective={...a};delete effective.op_id;delete effective.expected_head;
      const digest=canonical(effective),prior=this.replays.get(key);
      if(prior) {if(prior.digest!==digest) throw failure('bad_op','domain');return prior.result;}
      if(a.expected_head!==undefined&&a.expected_head!==this.head) throw failure('stale_rev','domain');
      if(this.records.some(r => r.agent_id===a.agent_id)) throw failure('conflict','domain');
      const result=creation(a,++this.head);this.records.push(result.record);this.events.push(result.event);
      const response={record:result.record,commit:result.commit};this.replays.set(key,{digest,result:response});return response;
    }
    if(tool==='ledger_events') {
      const after=Number(a.after??0);if(after>this.head) return page([],this.head,0,false,true);
      const scanned=this.events.filter(e => e.lamport>after).slice(0,Number(a.limit??100));
      const next=scanned.at(-1)?.lamport??this.head;const more=this.events.some(e => e.lamport>next);
      return page(scanned.filter(e => (!a.agent_id||e.payload.record && (e.payload.record as JsonObject).agent_id===a.agent_id)&&
        (!a.kinds||(a.kinds as JsonValue[]).includes(e.kind))),this.head,more?next:this.head,more);
    }
    throw Error(`Unexpected public tool ${tool}`);
  }
  for(tool: string): Call[] {return this.calls.filter(c => c.tool===tool);}
  mutations(): Call[] {return this.calls.filter(c => c.options.mutation);}
}
export interface HarnessOptions {service?: Service;query?: Record<string,string>;head?: number|null;actor?: string|null;actorDisabled?: boolean;refresh?: () => Promise<void>}
export function mount(options: HarnessOptions = {}) {
  const service=options.service??new Service();
  const root=document.createElement('div');
  root.innerHTML='<header>Lineage</header><nav aria-label="Primary"><a href="#/agents" aria-current="page" aria-label="Agents navigation" data-lin-action="nav-agents">Agents</a></nav><a href="#main-content" data-lin-action="skip-main">Skip to main content</a><button type="button" data-lin-action="refresh-screen">Refresh Agents</button><main id="main-content" tabindex="-1" data-lin-screen="agents"></main><div role="status" aria-label="Application updates" aria-live="polite" aria-atomic="true"></div>';
  document.body.append(root);
  let actor: HTMLSelectElement|null=null;
  if(options.actor!==null) {
    actor=document.createElement('select');actor.dataset.linAction='select-actor';actor.setAttribute('aria-label','Acting agent');
    for(const value of ['',options.actor??'acting-root','other-actor','operator']) {const option=document.createElement('option');option.value=value;option.textContent=value||'Choose actor';actor.append(option);}
    actor.value=options.actor??'acting-root';actor.disabled=options.actorDisabled??false;root.insertBefore(actor,root.querySelector('main'));
  }
  const host=root.querySelector('main')!;const controller=new AbortController();const listeners=new Set<(state: AppState) => void>();
  let state: AppState={phase:'ready',stale:false,route:{screen:'agents',query:options.query??{}},mode:service.mode,fixtureId:service.transport.fixtureId,
    tools:clone(service.tools),events:[],head:options.head===undefined?service.head:options.head,error:null,selection:{},expanded:[]};
  const publish=(patch: Partial<AppState>) => {state={...state,...patch};for(const listener of listeners) listener(state);};
  const store: AppStore={getState:() => state,subscribe:vi.fn(listener => {listeners.add(listener);return () => {listeners.delete(listener);};}),
    refresh:vi.fn(async () => {if(options.refresh) {await options.refresh();return;}publish({head:service.head,tools:clone(service.tools),phase:'ready',events:clone(service.events)});}),
    setRoute:vi.fn(),setSelection:vi.fn(),setExpanded:vi.fn(),dispose:vi.fn()};
  const announcements: {key: string;message: string}[]=[];const status=root.querySelector('[role="status"]')!;
  const announce=vi.fn((key: string,message: string) => {announcements.push({key,message});status.textContent=message;});
  const context: ScreenContext={route:state.route,transport:service.transport,store,signal:controller.signal,navigate:vi.fn(),announce};
  let mounted: MountedScreen;const updates: Promise<void>[]=[];
  const navigate=vi.fn((route: Route) => {Object.assign(context,{route});publish({route});if(route.screen==='agents') {const work=Promise.resolve(mounted.update({...context,route}));updates.push(work);void work.catch(() => {});}});
  Object.assign(context,{navigate});
  expect(getScreen(context.route),'U21 registry must retain the public Agents entry').toBe(screen);
  mounted=screen.mount(host,context);
  let initial: 'pending'|'fulfilled'|'rejected'='pending';let initialError: unknown;
  void mounted.ready.then(() => {initial='fulfilled';},error => {initial='rejected';initialError=error;});
  let disposed=false;
  const dispose=() => {if(disposed) return;disposed=true;controller.abort();mounted.dispose();closeDialogsWithin(root);};
  owned.push(dispose);
  root.querySelector('[data-lin-action="refresh-screen"]')!.addEventListener('click',() => {void refresh();});
  async function update(query: Record<string,string>): Promise<void> {
    const route: Route={screen:'agents',query};Object.assign(context,{route});publish({route});await mounted.update({...context,route});await flush();
  }
  async function refresh(): Promise<void> {await store.refresh();await mounted.update({...context});await flush();}
  return {root,host,service,context,store,actor,mounted,navigate,announce,announcements,controller,publish,update,refresh,dispose,
    listeners,updates,get initial(){return initial;},get initialError(){return initialError;},get state(){return state;}};
}
export type Harness = ReturnType<typeof mount>;
export async function boot(options: HarnessOptions = {}): Promise<Harness> {const h=mount(options);await flush();await h.mounted.ready;await flush();return h;}
export function name(el: Element): string {
  const refs=el.getAttribute('aria-labelledby');if(refs) return refs.split(/\s+/u).map(id => document.getElementById(id)?.textContent??'').join(' ').trim();
  if(el.hasAttribute('aria-label')) return el.getAttribute('aria-label')!;
  if(el instanceof HTMLInputElement||el instanceof HTMLSelectElement) return Array.from(el.labels??[]).map(l => l.textContent).join(' ').trim();
  return el.textContent?.trim()??'';
}
export function controls(root: ParentNode): HTMLElement[] {return Array.from(root.querySelectorAll<HTMLElement>('button,a[href],input,select')).filter(el => !el.closest('[hidden],[inert]'));}
export function action<T extends HTMLElement = HTMLButtonElement>(root: ParentNode,key: string,accessible?: string): T {
  const matches=Array.from(root.querySelectorAll<HTMLElement>('[data-lin-action]')).filter(el => el.dataset.linAction===key&&!el.closest('[hidden],[inert]')&&(!accessible||name(el)===accessible));
  expect(matches,`Missing or ambiguous public action ${key}${accessible?' / '+accessible:''}; U22 placeholder has no domain controls.`).toHaveLength(1);
  return matches[0] as T;
}
export function card(h: Harness,id: string): HTMLElement {
  const found=Array.from(h.host.querySelectorAll<HTMLElement>('[data-lin-entity="agent"][data-lin-id]')).filter(el => el.dataset.linId===id);
  expect(found,`Missing identity-bearing agent card ${id}`).toHaveLength(1);return found[0];
}
export const ids = (h: Harness): string[] => Array.from(h.host.querySelectorAll<HTMLElement>('[data-lin-entity="agent"]')).map(el => el.dataset.linId!);
export async function enter(root: ParentNode,key: string,value: string): Promise<void> {
  const el=action<HTMLInputElement|HTMLSelectElement>(root,key);el.value=value;el.dispatchEvent(new Event(el instanceof HTMLSelectElement?'change':'input',{bubbles:true}));await flush();
}
export function dialog(): HTMLDialogElement {
  const all=Array.from(document.querySelectorAll<HTMLDialogElement>('dialog')).filter(el => el.open&&!el.closest('[hidden],[inert]'));
  expect(all,'The operation must expose one native modal').toHaveLength(1);return all[0];
}
export async function openCreate(h: Harness): Promise<HTMLDialogElement> {action(h.host,'create-agent','Create agent').click();await flush();const d=dialog();expect(name(d)).toBe('Create agent');return d;}
export function field(root: ParentNode,key: string): HTMLInputElement|HTMLSelectElement {
  const candidates=Array.from(root.querySelectorAll<HTMLInputElement|HTMLSelectElement>('[data-lin-action="edit-field"][name]')).filter(el => el.name===key);
  expect(candidates,`Create must expose the native field ${key}`).toHaveLength(1);return candidates[0];
}
export async function fill(root: ParentNode,key: string,value: string): Promise<void> {
  const el=field(root,key);el.value=value;el.dispatchEvent(new Event(el instanceof HTMLSelectElement?'change':'input',{bubbles:true}));await flush();
}
export async function seatDraft(root: ParentNode,model='synthetic-model',effort='medium',mode='headless'): Promise<void> {
  await fill(root,'seat.model',model);await fill(root,'seat.effort',effort);await fill(root,'seat.mode',mode);
  action(root,'add-item','Add seats').click();await flush();
}
export async function fillCreate(d: ParentNode,changes: Record<string,string> = {}): Promise<void> {
  for(const [key,value] of Object.entries({agent_id:'new-child',display_name:'New child',workflow:'develop',language:'general',...changes})) await fill(d,key,value);
  await seatDraft(d);
}
export async function confirm(d: ParentNode): Promise<void> {const button=action<HTMLButtonElement>(d,'submit-dialog','Confirm Create agent');expect(button.disabled,'Valid explicit draft must be submittable').toBe(false);button.click();await flush();}
export function saved(): JsonObject {const raw=window.localStorage.getItem(DRAFT_KEY);expect(raw,'Creation draft must survive independently of rendered nodes').not.toBeNull();return JSON.parse(raw!) as JsonObject;}
export function expectNoSuccess(h: Harness): void {expect(h.announcements.some(e => e.message.startsWith('Create agent recorded for '))).toBe(false);}
export function expectReads(h: Harness): void {expect(h.service.for('agent_list').length,'U22 must read the authoritative agent_list, not resolve an empty placeholder').toBeGreaterThan(0);}
export function unresolvedControl(root: ParentNode,kind: 'retry'|'abandon'): HTMLButtonElement {
  const re=kind==='retry'?/(?:retry|verify|reconcile).*(?:attempt|creation|create|verification)/iu:/(?:abandon|discard).*(?:attempt|creation|create)/iu;
  const found=controls(root).filter(el => el instanceof HTMLButtonElement&&el.type==='button'&&re.test(name(el)));
  expect(found,`Amendment B requires a separate registered ${kind} control for the unresolved attempt`).toHaveLength(1);expect(actions.has(found[0].dataset.linAction!),'Unresolved-attempt controls must have a registered K0 action').toBe(true);return found[0] as HTMLButtonElement;
}
export function expectPins(values: JsonValue,expected: JsonObject[]): void {expect(values).toEqual(expect.arrayContaining(expected));expect(values).toHaveLength(expected.length);}
export const key = identityKey;

/** Exercise the real U21 HTTP decoder against an entirely in-memory server. */
export function viaHttp(service: Service, sessionToken: string|null = 'synthetic-session-value') {
  const direct=service.transport;
  const requests: {path: string;init: RequestInit}[]=[];
  const fetchImpl=vi.fn(async (input: RequestInfo|URL,init: RequestInit = {}) => {
    const path=String(input);requests.push({path,init});let value: unknown;
    if(path==='/api/tools') value={tools:clone(service.tools)};
    else if(path.startsWith('/api/events?')) value=page([],service.head);
    else if(path==='/api/call') {
      const body=JSON.parse(String(init.body)) as {tool: string;args: JsonObject};
      try {value={untrusted:await direct.call(body.tool,body.args,{mutation:body.tool==='agent_create',signal:init.signal??undefined})};}
      catch(error) {const e=error as TransportError;value={ok:false,code:e.code,...(e.detail===undefined?{}:{detail:e.detail})};}
    } else throw Error('Undeclared in-memory HTTP route');
    return {ok:true,status:200,headers:new Headers({'content-type':'application/json'}),json:async () => clone(value)} as Response;
  });
  service.transport=createHttpTransport({fetchImpl:fetchImpl as typeof fetch,sessionToken,timeoutMs:1000});
  return {requests,fetchImpl};
}
