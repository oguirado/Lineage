import { afterEach, beforeEach, expect, vi } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type {
  AppState, AppStore, CallOptions, EventsPage, JsonObject, JsonValue, LedgerEvent,
  MountedScreen, Query, Route, ScreenContext, ToolDescriptor, Transport, UiFixture,
} from '../../src/ui/contracts.ts';
import { createFixtureTransport, createHttpTransport, TransportError } from '../../src/transport.ts';
import { createStatusRegion } from '../../src/ui/status.ts';

vi.setConfig({ testTimeout: 4000, hookTimeout: 4000 });
export const CLOCK = 1700000000000;
export const HASH = 'a'.repeat(64);
export const PREV = 'b'.repeat(64);
export const REQUEST = 'c'.repeat(64);
export const ACTOR = 'aurora-root';
export const KINDS = ['reference.pinned','skill.published','skill.retired','agent.born','agent.status',
  'memory.put','memory.retire','run.open','run.beat','run.close','bench.declared','bench.result','bench.verdict'];
export const id = (n: number) => `e-${n.toString(16).padStart(16, '0')}`;
export function event(n: number, patch: Partial<LedgerEvent> = {}): LedgerEvent {
  return {schema:'lineage.event/v1', id:id(n), lamport:n, ts:CLOCK+n, ledger:'main', agent:ACTOR,
    kind:'run.beat', payload:{run_id:'run_0001',agent_id:ACTOR,progress:`Checkpoint ${n}`},
    op_id:`beat-${n}`, request_sha256:REQUEST, evidence:[{path:'evidence/check.txt',sha256:HASH}],
    prev_sha256:PREV, sha256:HASH, ...patch};
}
export function page(events: LedgerEvent[] = [], patch: Partial<EventsPage> = {}): EventsPage {
  const last = events.at(-1)?.lamport ?? 0;
  return {events, next_after:last, head:last, has_more:false, resync:false, ...patch};
}
export function deferred<T>() {
  let resolve!: (value:T) => void; let reject!: (reason:unknown) => void;
  const promise = new Promise<T>((yes,no) => {resolve=yes;reject=no;});
  return {promise,resolve,reject};
}
// Drain only promises: no wall-clock waits, polling timers, network or process control.
export async function flush() { for(let i=0;i<48;i++) await Promise.resolve(); }
export function freeze<T>(value:T):T {
  if(value && typeof value==='object') {Object.values(value).forEach(freeze);Object.freeze(value);}
  return value;
}
const root=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
export const sourceText=(path:string)=>readFileSync(resolve(root,path),'utf8');
export const sourceExists=(path:string)=>existsSync(resolve(root,path));
const contract = sourceText('docs/CONTRACT.md');
export function descriptor(name:string): ToolDescriptor {
  const section = contract.split(`### \`${name}\``)[1];
  if(!section) throw Error(`Missing public tool contract: ${name}`);
  const args = section.match(/Arguments:\s*```json\s*([\s\S]*?)```/);
  if(!args) throw Error(`Missing public argument schema: ${name}`);
  return {name,description:`Synthetic ${name}`,inputSchema:JSON.parse(args[1]) as JsonObject};
}
export const descriptors = ['ledger_events','ledger_verify','ledger_export'].map(descriptor);
export type CallRecord = {tool:string;args:JsonObject;options:CallOptions};
export type Handler = (tool:string,args:JsonObject,options:CallOptions) => unknown | Promise<unknown>;
export function transport(handler:Handler = () => page(), changes:Partial<Transport> = {}) {
  const calls:CallRecord[]=[];
  const call = vi.fn(async (tool:string,args:JsonObject,options:CallOptions) => {
    calls.push({tool,args:structuredClone(args),options});
    return await handler(tool,args,options) as JsonValue;
  });
  const t:Transport = {mode:'live',fixtureId:null,presentation:null,
    tools:vi.fn(async () => structuredClone(descriptors)),
    events:vi.fn(async () => page()), call:call as Transport['call'], ...changes};
  return {transport:t,calls,call};
}
export function scripted(values:(unknown|Error|Promise<unknown>)[], head = 0) {
  let offset=0;
  const t=transport((tool) => {
    if(tool!=='ledger_events') throw Error(`Unexpected tool: ${tool}`);
    if(offset>=values.length) throw Error('Unexpected extra page read');
    const value=values[offset++]; if(value instanceof Error) throw value;return value;
  }, {events:vi.fn(async () => page([], {head,next_after:head}))});
  return t;
}
export const domainError = (code:string,detail='Synthetic refusal') =>
  new TransportError('domain',code,`Request refused: ${code}.`,{detail});
export const networkError = () => new TransportError('transport','network','The service could not be reached.');
export function response(value:unknown):Response {
  return {ok:true,status:200,redirected:false,headers:new Headers({'content-type':'application/json'}),
    json:async () => structuredClone(value)} as Response;
}
export function httpTransport(reply:(tool:string,args:JsonObject) => unknown, sessionToken:string|null='synthetic-session') {
  const fetchImpl=vi.fn(async (url:RequestInfo|URL,init?:RequestInit) => {
    if(String(url)==='/api/tools') return response({tools:descriptors});
    if(String(url).startsWith('/api/events?')) return response(page([event(1)]));
    if(String(url)!=='/api/call') throw Error('Unexpected endpoint');
    const request=JSON.parse(String(init?.body)) as {tool:string;args:JsonObject};
    return response(reply(request.tool,request.args));
  });
  return {transport:createHttpTransport({fetchImpl:fetchImpl as typeof fetch,sessionToken,timeoutMs:1000}),fetchImpl};
}
export function fixtureTransport(events = [event(1)]) {
  const p=page(events);
  const args:JsonObject={after:0,limit:100,wait_ms:0};
  const fixture:UiFixture={schema:'lineage.ui.fixture/v1',id:'demo',clock_ms:CLOCK,locale:'en-GB',timezone:'UTC',
    theme:'light',tools:structuredClone(descriptors),page:p,panels:[],
    results:[{tool:'ledger_events',args,reply:{untrusted:p as unknown as JsonValue}},
      {tool:'ledger_events',args:{...args,agent:'system'},reply:{untrusted:p as unknown as JsonValue}}]};
  return createFixtureTransport(fixture);
}
export function bank(size=10000) {
  let generated=0;
  const t=transport((tool,args) => {
    if(tool!=='ledger_events') throw Error('Large bank only supports cursor reads');
    const after=Number(args.after);const next=Math.min(after+100,size);
    const events=Array.from({length:next-after},(_,i)=>{generated++;return event(after+i+1);});
    return page(events,{head:size,next_after:next,has_more:next<size});
  });
  return {...t,generated:()=>generated};
}

const cleanup:(()=>void)[]=[];
export function own<T extends {dispose():void}>(object:T):T {cleanup.push(()=>object.dispose());return object;}
export function isolate() {
  beforeEach(()=>{
    document.body.replaceChildren();document.documentElement.dataset.linReady='false';
    document.documentElement.removeAttribute('data-lin-rev');
    window.history.replaceState(null,'','/#/ledger');
    vi.stubGlobal('fetch',vi.fn(()=>{throw Error('Oracle forbids network');}));
    vi.stubGlobal('matchMedia',vi.fn((query:string)=>({matches:false,media:query,onchange:null,
      addEventListener:vi.fn(),removeEventListener:vi.fn(),addListener:vi.fn(),removeListener:vi.fn(),dispatchEvent:()=>true})));
  });
  afterEach(()=>{
    for(const dispose of cleanup.splice(0).reverse()) dispose();
    vi.useRealTimers();vi.restoreAllMocks();vi.unstubAllGlobals();document.body.replaceChildren();
  });
}
export interface Harness {
  root:HTMLElement;main:HTMLElement;status:HTMLElement;store:AppStore;context:ScreenContext;
  mounted:MountedScreen;ready:Promise<void>;errors:unknown[];announcements:ReturnType<typeof vi.fn>;
  controller:AbortController;updates:Promise<void>[];
  update(query?:Query):Promise<void>;acknowledge(head:number,events?:LedgerEvent[]):void;
  dispose():void;
}
export async function mount(t:Transport, query:Query={}, head:number|null=1):Promise<Harness> {
  const {screen}=await import('../../src/screens/ledger/index.ts');
  const knownTools=await t.tools();
  const root=document.createElement('div');const main=document.createElement('main');main.id='main-content';
  main.tabIndex=-1;main.dataset.linScreen='ledger';root.append(main);document.body.append(root);
  const region=own(createStatusRegion(root));const status=root.querySelector<HTMLElement>('[role="status"]')!;
  const announcements=vi.fn(region.announce);const controller=new AbortController();
  let state:AppState=freeze({phase:head===null?'loading':'ready',stale:false,route:{screen:'ledger',query},
    mode:t.mode,fixtureId:t.fixtureId,tools:structuredClone(knownTools),events:[],head,error:null,selection:{},expanded:[]});
  const listeners=new Set<(s:AppState)=>void>();
  const publish=(patch:Partial<AppState>)=>{state=freeze({...state,...patch});for(const listener of listeners) listener(state);};
  const store:AppStore={getState:()=>state,subscribe:fn=>{listeners.add(fn);return ()=>{listeners.delete(fn);};},
    refresh:vi.fn(async ()=>{
      const p=await t.events(state.head??0);publish({phase:'ready',head:p.head,events:p.events});
    }),setRoute:route=>publish({route}),setSelection:(screen,id)=>{
      const selection={...state.selection};if(id===null) delete selection[screen];else selection[screen]=id;publish({selection});
    },setExpanded:(kind,id,on)=>{
      const key=JSON.stringify([kind,id]);publish({expanded:on?[...new Set([...state.expanded,key])]:state.expanded.filter(x=>x!==key)});
    },dispose:vi.fn(()=>listeners.clear())};
  const errors:unknown[]=[];const updates:Promise<void>[]=[];let h:Harness;
  const context:ScreenContext={route:state.route,transport:t,store,signal:controller.signal,
    navigate:vi.fn((route:Route)=>{
      publish({route});h.context={...h.context,route};const work=h.mounted.update(h.context);
      updates.push(work);void work.catch(e=>errors.push(e));
    }),announce:announcements};
  const mounted=screen.mount(main,context);void mounted.ready.catch(e=>errors.push(e));
  h={root,main,status,store,context,mounted,ready:mounted.ready,errors,announcements,controller,updates,
    update:async(next=query)=>{
      const route:Route={screen:'ledger',query:next};publish({route});h.context={...h.context,route};
      const work=mounted.update(h.context);updates.push(work);void work.catch(e=>errors.push(e));await work;
    },acknowledge:(newHead,events=[])=>publish({phase:'ready',head:newHead,events}),
    dispose:()=>{controller.abort();mounted.dispose();root.remove();}};
  own(h);return h;
}
export const visibleText=(root:ParentNode):string => {
  const clone=(root as HTMLElement).cloneNode(true) as HTMLElement;
  clone.querySelectorAll('[hidden],dialog:not([open])').forEach(el=>el.remove());return clone.textContent??'';
};
export const rows=(root:ParentNode) => Array.from(root.querySelectorAll<HTMLElement>('[data-lin-entity="event"][data-lin-id]'));
export const ids=(root:ParentNode) => rows(root).map(el=>el.dataset.linId);
export function action<T extends HTMLElement=HTMLButtonElement>(root:ParentNode,name:string):T {
  const found=root.querySelectorAll<T>(`[data-lin-action="${name}"]`);
  expect(found.length,`U26 must expose action ${name}; a placeholder is not a Ledger inspector`).toBe(1);
  return found[0];
}
export function record(root:ParentNode,eventId:string):HTMLElement {
  const found=rows(root).filter(el=>el.dataset.linId===eventId);
  expect(found.length,`U26 must render full event identity ${eventId}`).toBe(1);return found[0];
}
export function nameOf(el:Element):string {
  const refs=el.getAttribute('aria-labelledby');
  if(refs) return refs.split(/\s+/).map(id=>document.getElementById(id)?.textContent??'').join(' ').trim();
  if(el.hasAttribute('aria-label')) return el.getAttribute('aria-label')!;
  if(el instanceof HTMLInputElement||el instanceof HTMLSelectElement) return Array.from(el.labels??[]).map(l=>l.textContent).join(' ').trim();
  return el.textContent?.trim()??'';
}
export function controls(root:ParentNode):HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>('button,a[href],input,select')).filter(el=>!el.closest('[hidden],[inert],dialog:not([open])'));
}
export function input(root:ParentNode,name:string,value:string) {
  const el=action<HTMLInputElement|HTMLSelectElement>(root,name);el.value=value;
  el.dispatchEvent(new Event(el.tagName==='SELECT'?'change':'input',{bubbles:true}));return el;
}
export async function click(root:ParentNode,name:string) {action(root,name).click();await flush();}
export function assertRead(call:CallRecord,after:number,filters:JsonObject={}) {
  expect(call,'U26 must dispatch a cursor read before confirming a fold').toBeDefined();
  expect(call.tool).toBe('ledger_events');
  const args={...call.args};if(args.agent==='system') delete args.agent;
  expect(args).toEqual({after,limit:100,wait_ms:0,...filters});
  expect(call.options.mutation).toBe(false);expect(call.options.signal).toBeInstanceOf(AbortSignal);
}
export function reads(calls:CallRecord[]) {return calls.filter(c=>c.tool==='ledger_events');}
export function retry(root:ParentNode,panel='Ledger') {
  const matches=Array.from(root.querySelectorAll<HTMLElement>('[data-lin-action="retry-panel"]')).filter(el=>nameOf(el)===`Retry ${panel}`);
  expect(matches,`Expected named Retry ${panel} after an active failure`).toHaveLength(1);return matches[0];
}
export async function openExport(root:ParentNode) {
  const trigger=action(root,'export-ledger');trigger.focus();trigger.click();await flush();
  const dialog=root.querySelector<HTMLDialogElement>('dialog[open]');
  expect(dialog,'Export must expose a native modal').not.toBeNull();expect(nameOf(dialog!)).toBe('Export ledger');
  const field=dialog!.querySelector<HTMLInputElement>('[data-lin-action="edit-field"][name="out"]');
  expect(field,'Export requires the public out field').not.toBeNull();return {trigger,dialog:dialog!,field:field!};
}
export async function submitExport(dialog:HTMLDialogElement,field:HTMLInputElement,value='exports/snapshot') {
  field.value=value;field.dispatchEvent(new Event('input',{bubbles:true}));
  action<HTMLButtonElement>(dialog,'submit-dialog').click();await flush();
}
export function verifyResult(patch:Record<string,unknown>={}) {
  return {valid:true,head:1,sha256:HASH,torn_tail_bytes:0,issues:[],...patch};
}
export function exportResult(patch:Record<string,unknown>={}) {
  return {out:'exports/snapshot',head:1,manifest:[{path:'ledger/main/events.jsonl',sha256:HASH}],...patch};
}
