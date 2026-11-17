import type { AppStore, AppState, Route, Transport, LedgerEvent } from './ui/contracts.ts';
import { canonical, invalidResponse, TransportError, validatePage, validateTools } from './transport.ts';
export type { AppStore, AppState } from './ui/contracts.ts';
function immutable<T>(value:T):T {
  if(value && typeof value==='object') {Object.values(value).forEach(immutable);Object.freeze(value);}return value;
}
export function createStore(transport:Transport,initialRoute:Route):AppStore {
  let state:AppState=immutable({phase:'loading',stale:false,route:structuredClone(initialRoute),mode:transport.mode,fixtureId:transport.fixtureId,tools:[],events:[],head:null,error:null,selection:{},expanded:[],notice:null});
  const listeners=new Set<(state:AppState)=>void>();let disposed=false;let generation=0;let active:AbortController|null=null;
  const publish=(patch:Partial<AppState>)=>{if(disposed) return;state=immutable({...state,...structuredClone(patch)});for(const listener of listeners) listener(state);};
  return {getState:()=>state,subscribe(listener) {if(disposed) return ()=>{};listeners.add(listener);return ()=>{listeners.delete(listener);};},
    async refresh() {
      if(disposed) return;
      active?.abort();const controller=new AbortController();active=controller;const turn=++generation;
      const current=()=>!disposed&&turn===generation&&!controller.signal.aborted;
      const baseline=state;publish({phase:'loading',error:null,notice:null});
      try {
        const tools=await transport.tools({signal:controller.signal});if(!current()) return;
        validateTools(tools);const descriptors=structuredClone(tools);
        let staged=structuredClone([...baseline.events]);let cursor=baseline.head??0;let expectedHead=cursor;let resynced=false;
        while(current()) {
          const page=await transport.events(cursor,{signal:controller.signal});if(!current()) return;
          validatePage(page);
          if(page.resync) {
            if(resynced) throw invalidResponse();resynced=true;staged=[];cursor=0;expectedHead=0;
            publish({notice:'Ledger changed. Resync required; filters kept.',selection:{},expanded:[]});continue;
          }
          if(page.next_after<cursor||page.head<expectedHead||page.has_more&&page.next_after<=cursor||!page.has_more&&page.next_after!==page.head) throw invalidResponse();
          const byId=new Map(staged.map(e=>[e.id,e]));const byLamport=new Map(staged.map(e=>[e.lamport,e]));let last=staged.at(-1)?.lamport??0;
          for(const event of page.events) {
            const prior=byId.get(event.id);const at=byLamport.get(event.lamport);
            if(prior||at) {if(!prior||!at||canonical(prior as unknown as import('./ui/contracts.ts').JsonValue)!==canonical(event as unknown as import('./ui/contracts.ts').JsonValue)) throw invalidResponse();continue;}
            if(event.lamport<=cursor||event.lamport<=last) throw invalidResponse();
            const detached=structuredClone(event) as LedgerEvent;staged.push(detached);byId.set(detached.id,detached);byLamport.set(detached.lamport,detached);last=detached.lamport;
          }
          cursor=page.next_after;expectedHead=page.head;
          if(!page.has_more&&cursor===page.head) {
            publish({phase:'ready',stale:false,head:cursor,events:staged,tools:descriptors,error:null,notice:null,...(resynced?{selection:{},expanded:[]}: {})});return;
          }
        }
      } catch(error) {
        if(!current()||(error instanceof TransportError&&error.code==='aborted')) return;
        const e=error as {source?:string;code?:string};
        publish({phase:'error',stale:state.head!==null,notice:null,error:{source:e.source==='domain'?'domain':'transport',code:e.code??'invalid_response',message:e.source==='domain'?`Request refused: ${e.code??'internal'}.`:'Data could not be refreshed.'}});
      }
    },
    setRoute(route) {publish({route,selection:{}});},
    setSelection(screen,id) {const selection={...state.selection};if(id===null) delete selection[screen];else selection[screen]=id;publish({selection});},
    setExpanded(entity,id,expanded) {const key=JSON.stringify([entity,id]);publish({expanded:expanded?[...new Set([...state.expanded,key])]:state.expanded.filter(k=>k!==key)});},
    dispose() {if(disposed) return;disposed=true;++generation;active?.abort();listeners.clear();},
  };
}
