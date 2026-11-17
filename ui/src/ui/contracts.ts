/** Public browser seam. Domain data stays passive; the server owns all decisions. */
export type JsonValue = null | boolean | number | string | JsonValue[] | JsonObject;
export type JsonObject = { [key: string]: JsonValue };
export type ScreenId = 'agents' | 'agent' | 'lineage' | 'arena' | 'bench' | 'ledger';
export type ScreenModuleId = Exclude<ScreenId, 'bench'>;
export type EntityKind = 'agent' | 'run' | 'bench' | 'event' | 'unit' | 'skill';
export type Theme = 'light' | 'dark';
export type Query = Readonly<Record<string, string>>;
export type Route = ({screen:'agents'} | {screen:'agent';agentId:string} | {screen:'lineage'} | {screen:'arena'} | {screen:'bench';benchId:string} | {screen:'ledger'}) & {query:Query};
export interface ToolDescriptor {name:string;description:string;inputSchema:JsonObject;annotations?:JsonObject}
export type DomainCode = 'bad_args'|'bad_op'|'stale_rev'|'busy'|'internal'|'conflict'|'no_agent'|'no_run'|'run_closed'|'memory_required'|'memory_debt'|'forbidden_level'|'not_inheritable'|'hash_mismatch'|'rule_not_declared'|'no_benchmark'|'heldout_forbidden'|'seat_not_allowed'|'fixture_readonly'|'timeout';
export type WireReply<T extends JsonValue> = {untrusted:T} | {ok:false;code:DomainCode;detail?:string};
export interface EventEvidence {path:string;sha256:string}
export interface LedgerEvent {
  schema:'lineage.event/v1';id:string;lamport:number;ts:number;ledger:'main';agent:string;kind:string;
  payload:JsonObject;op_id:string;request_sha256:string;evidence:EventEvidence[];prev_sha256:string;sha256:string;
}
export interface EventsPage {events:LedgerEvent[];next_after:number;head:number;has_more:boolean;resync:boolean}
export interface RequestOptions {signal?:AbortSignal}
export interface CallOptions extends RequestOptions {mutation:boolean}
export interface Transport {
  readonly mode:'live'|'fixture';readonly fixtureId:string|null;
  readonly presentation:{clockMs:number;locale:'en-GB';timezone:'UTC';theme:Theme}|null;
  tools(options?:RequestOptions):Promise<readonly ToolDescriptor[]>;
  events(after:number,options?:RequestOptions & {waitMs?:number}):Promise<EventsPage>;
  call<T extends JsonValue>(tool:string,args:JsonObject,options:CallOptions):Promise<T>;
}
export interface ViewError {readonly source:'transport'|'domain';readonly code:string;readonly message:string}
export interface AppState {
  readonly phase:'loading'|'ready'|'error';readonly stale:boolean;readonly route:Route;
  readonly mode:'live'|'fixture';readonly fixtureId:string|null;readonly tools:readonly ToolDescriptor[];
  readonly events:readonly LedgerEvent[];readonly head:number|null;readonly error:ViewError|null;
  readonly selection:Readonly<Partial<Record<ScreenId,string>>>;readonly expanded:readonly string[];
  /** A transient cursor warning, never authoritative domain state. */
  readonly notice?:string|null;
}
export interface AppStore {
  getState():AppState;subscribe(listener:(state:AppState)=>void):()=>void;refresh():Promise<void>;
  setRoute(route:Route):void;setSelection(screen:ScreenId,id:string|null):void;
  setExpanded(entity:EntityKind,id:string,expanded:boolean):void;dispose():void;
}
export interface ScreenContext {
  readonly route:Route;readonly transport:Transport;readonly store:AppStore;readonly signal:AbortSignal;
  navigate(route:Route):void;announce(key:string,message:string):void;
}
export interface MountedScreen {readonly ready:Promise<void>;update(context:ScreenContext):Promise<void>;dispose():void}
export interface ScreenModule {readonly id:ScreenModuleId;readonly title:string;mount(host:HTMLElement,context:ScreenContext):MountedScreen}
export interface AppOptions {root:HTMLElement;transport:Transport;storage:Storage|null;initialHash:string}
export interface AppHandle {store:AppStore;dispose():void}
export type PanelState = 'loading'|'empty'|'no-match'|'ready'|'busy'|'queued'|'running'|'stalled'|'stale'|'error'|'completed'|'not-built';
export interface UiFixture {
  schema:'lineage.ui.fixture/v1';id:'demo'|'empty'|'hostile';clock_ms:number;
  locale?:'en-GB';timezone?:'UTC';theme?:Theme;tools:ToolDescriptor[];page:EventsPage;
  results:{tool:string;args:JsonObject;reply:WireReply<JsonValue>}[];
  panels:{id:string;state:PanelState;title:string;detail?:string}[];
}
export const panelStates: readonly PanelState[] = ['loading','empty','no-match','ready','busy','queued','running','stalled','stale','error','completed','not-built'];
export const entityKinds: readonly EntityKind[] = ['agent','run','bench','event','unit','skill'];
export const screenLabels:Readonly<Record<ScreenId,string>> = {agents:'Agents',agent:'Agent',lineage:'Lineage',arena:'Arena',bench:'Benchmark',ledger:'Ledger'};
export const forbiddenKeys = new Set(['__proto__','constructor','prototype']);

/** Closed K0 action vocabulary. */
export const actions = new Set(["skip-main", "nav-agents", "nav-lineage", "nav-arena", "nav-ledger", "theme-light", "theme-dark", "refresh-screen", "retry-panel", "dismiss-message", "select-actor", "toggle-fixture-info", "filter-agent-query", "filter-agent-workflow", "filter-agent-language", "filter-agent-status", "include-retired", "sort-agents", "clear-agent-filters", "create-agent", "open-agent", "compare-agent", "compare-agents", "clear-comparison", "page-agents", "show-constitution", "show-skills", "show-memory", "show-scorecard", "show-runs", "view-brief", "get-reference", "verify-reference", "open-skill", "filter-memory-query", "filter-memory-kind", "filter-memory-level", "filter-memory-privacy", "filter-memory-inheritable", "clear-memory-filters", "open-unit", "toggle-unit-details", "memory-history", "route-memory", "bootcheck-memory", "write-memory", "filter-scorecard-seat", "filter-scorecard-arm", "open-run", "open-run-form", "heartbeat-run", "close-run", "derive-agent", "retire-agent", "promote-agent", "page-memory", "page-runs", "filter-lineage-query", "filter-lineage-root", "select-lineage-agent", "expand-lineage-agent", "collapse-lineage-agent", "open-lineage-agent", "reset-lineage", "expand-next-generation", "filter-bench-query", "filter-bench-purpose", "filter-bench-state", "clear-bench-filters", "declare-benchmark", "open-benchmark", "page-benches", "show-bench-rule", "launch-benchmark", "refresh-benchmark", "inspect-bench-result", "open-bench-run", "open-task-evidence", "evaluate-benchmark", "promote-candidate", "filter-ledger-query", "filter-ledger-agent", "filter-ledger-kind", "clear-ledger-filters", "page-events", "toggle-event-hash", "toggle-event-payload", "verify-ledger", "export-ledger", "resync-ledger", "open-event-agent", "submit-dialog", "cancel-dialog", "edit-field", "add-item", "remove-item", "select-unit", "select-skill", "select-rule", "select-parent", "select-bench-agent", "select-seat", "close-inspector"]);
