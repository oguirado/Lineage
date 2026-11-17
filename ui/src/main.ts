import '../styles/tokens.css';
import '../styles/base.css';
import '../styles/shell.css';
import { type AppOptions, type AppHandle, type UiFixture } from './ui/contracts.ts';
import { createRouter } from './router.ts';
import { createStore } from './store.ts';
import { mountShell } from './ui/shell.ts';
import { createFixtureTransport, createHttpTransport, TransportError } from './transport.ts';
import demo from '../../fixtures/ui/demo.json';
import empty from '../../fixtures/ui/empty.json';
import hostile from '../../fixtures/ui/hostile.json';
export type { AppOptions, AppHandle } from './ui/contracts.ts';
export function startApp(options:AppOptions):AppHandle {
  const router=createRouter(result=>store.setRoute(result.route),options.initialHash);
  const store=createStore(options.transport,router.current().route);
  const shell=mountShell(options.root,store,router,options.transport,options.storage);
  void store.refresh();let disposed=false;
  return {store,dispose() {if(disposed) return;disposed=true;store.dispose();router.dispose();shell.dispose();}};
}
/** The only module with a browser-entry side effect. Library imports remain inert. */
function bootstrap(root:HTMLElement):void {
  const slot=document.querySelector<HTMLMetaElement>('meta[name="lineage-session-token"]');const token=slot?.content||null;slot?.remove();
  try {
    const selectors=new URLSearchParams(window.location.search).getAll('fixture');
    if(selectors.length>1||selectors.length===1&&!['demo','empty','hostile'].includes(selectors[0])) throw new TransportError('transport','invalid_config','Invalid fixture selection.');
    const fixtures={demo,empty,hostile};
    const transport=selectors.length?createFixtureTransport(fixtures[selectors[0] as keyof typeof fixtures] as UiFixture):createHttpTransport({fetchImpl:window.fetch.bind(window),sessionToken:token,timeoutMs:15000});
    let storage:Storage|null=null;try{storage=window.localStorage;}catch{/* optional adapter */}
    startApp({root,transport,storage,initialHash:window.location.hash});
  } catch {
    document.documentElement.dataset.linReady='false';document.documentElement.removeAttribute('data-lin-rev');
    const heading=document.createElement('h1');heading.textContent='Configuration error';const explanation=document.createElement('p');explanation.textContent='invalid_config';root.replaceChildren(heading,explanation);
  }
}
if(typeof document!=='undefined') {const root=document.getElementById('app');if(root) bootstrap(root);}
