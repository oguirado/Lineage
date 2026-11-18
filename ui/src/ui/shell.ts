import { type AppStore, type Transport, type AppState, type Theme, type ScreenContext, type MountedScreen, type ScreenModule, screenLabels } from './contracts.ts';
import { type Router, formatRoute } from '../router.ts';
import { getScreen } from '../screens/index.ts';
import { createButton, createLink, renderStatePanel, identityKey } from './primitives.ts';
import { createStatusRegion } from './status.ts';
import { captureFocus, restoreFocus, focusMain, type FocusSnapshot } from './keyboard.ts';
import { lintOperability } from './operability.ts';
import { closeDialogsWithin } from './dialog.ts';
export function mountShell(root:HTMLElement,store:AppStore,router:Router,transport:Transport,storage:Storage|null) {
  const doc=root.ownerDocument;const html=doc.documentElement;
  html.dataset.linReady='false';html.removeAttribute('data-lin-rev');
  const header=doc.createElement('header');header.className='app-banner';
  const brand=doc.createElement('strong');brand.textContent='Lineage';brand.className='brand';
  const subtitle=doc.createElement('p');subtitle.className='brand-caption';subtitle.textContent='Agents, with a history.';
  header.append(brand,subtitle);
  const skip=doc.createElement('a');skip.href='#main-content';skip.dataset.linAction='skip-main';skip.textContent='Skip to main content';skip.className='skip-link';
  const navigation=doc.createElement('nav');navigation.setAttribute('aria-label','Primary');
  const links=new Map<string,HTMLAnchorElement>();
  for(const id of ['agents','lineage','arena','ledger'] as const) {
    const title=screenLabels[id];const link=createLink({name:`${title} navigation`,action:`nav-${id}`,href:`#/${id}`});link.textContent=title;link.setAttribute('aria-label',`${title} navigation`);
    link.addEventListener('click',event=>{if(event.button===0&&!event.ctrlKey&&!event.metaKey&&!event.shiftKey&&!event.altKey) {event.preventDefault();router.navigate({screen:id,query:{}});}});
    links.set(id,link);navigation.append(link);
  }
  const toolbar=doc.createElement('div');toolbar.className='shell-toolbar';
  let disposed=false;let theme:Theme='light';let explicitTheme=false;
  const media=typeof matchMedia==='function'?matchMedia('(prefers-color-scheme: dark)'):null;
  if(transport.mode==='fixture') theme=transport.presentation?.theme??'light';
  else {
    let saved:string|null=null;try{saved=storage?.getItem('lineage-theme')??null;}catch{/* storage is optional */}
    explicitTheme=saved==='light'||saved==='dark';theme=explicitTheme?saved as Theme:media?.matches?'dark':'light';
  }
  const themeButtons=new Map<Theme,HTMLButtonElement>();
  const applyTheme=(next:Theme,persist=false)=>{
    if(disposed) return;theme=next;html.classList.toggle('theme-dark',theme==='dark');html.classList.toggle('theme-light',theme==='light');
    for(const [id,button] of themeButtons) button.setAttribute('aria-pressed',String(id===theme));
    if(persist) {explicitTheme=true;try{storage?.setItem('lineage-theme',theme);}catch{/* storage denial is nonfatal */}}
  };
  for(const id of ['light','dark'] as const) {const button=createButton({name:`Use ${id} theme`,action:`theme-${id}`,onActivate:()=>applyTheme(id,true)});themeButtons.set(id,button);toolbar.append(button);}
  applyTheme(theme);
  const mediaChanged=()=>{if(transport.mode==='live'&&!explicitTheme) applyTheme(media?.matches?'dark':'light');};media?.addEventListener('change',mediaChanged);
  const refresh=createButton({name:'Refresh Agents',action:'refresh-screen',onActivate:()=>{void store.refresh();}});toolbar.append(refresh);
  const actorLabel=doc.createElement('label');actorLabel.textContent='Acting agent';
  const actor=doc.createElement('select');actor.dataset.linAction='select-actor';actor.disabled=true;actor.setAttribute('aria-label','Acting agent');actor.setAttribute('aria-describedby','actor-unavailable');
  const option=doc.createElement('option');option.textContent='Unavailable';actor.append(option);actorLabel.append(actor);
  const actorReason=doc.createElement('p');actorReason.id='actor-unavailable';actorReason.className='muted';actorReason.textContent='Acting agent selection is unavailable in the shell placeholder.';
  toolbar.append(actorLabel,actorReason);
  const fixtureInfo=doc.createElement('div');fixtureInfo.className='fixture-info';
  if(transport.mode==='fixture') {
    const label=doc.createElement('p');label.textContent=`Fixture: ${transport.fixtureId} — read-only`;
    const explanation=doc.createElement('p');explanation.textContent='Synthetic fixtures. Changes are unavailable.';
    const detail=doc.createElement('p');detail.id='fixture-details';detail.hidden=true;detail.textContent=`Fixed presentation: ${transport.presentation?.locale??'en-GB'}, ${transport.presentation?.timezone??'UTC'}. Synthetic data does not establish domain completion.`;
    const toggle=createButton({name:'Fixture details',action:'toggle-fixture-info',onActivate:()=>{detail.hidden=!detail.hidden;toggle.setAttribute('aria-expanded',String(!detail.hidden));}});toggle.setAttribute('aria-expanded','false');toggle.setAttribute('aria-controls',detail.id);
    fixtureInfo.append(label,explanation,toggle,detail);
  }
  const notice=doc.createElement('div');notice.className='notice';notice.hidden=true;
  const noticeText=doc.createElement('p');const dismiss=createButton({name:'Dismiss message',action:'dismiss-message',onActivate:()=>{notice.hidden=true;}});notice.append(noticeText,dismiss);
  const main=doc.createElement('main');main.id='main-content';main.tabIndex=-1;
  const diagnostics=doc.createElement('div');diagnostics.className='diagnostics';
  root.replaceChildren(skip,header,navigation,toolbar,fixtureInfo,notice,main,diagnostics);
  const footer=doc.createElement('footer');footer.textContent='Lineage · Agent history';root.append(footer);
  const screenStatus=doc.createElement('output');screenStatus.className='screen-readiness';screenStatus.hidden=true;footer.append(screenStatus);
  const progress=doc.createElement('div');progress.setAttribute('role','progressbar');progress.hidden=true;footer.append(progress);
  const status=createStatusRegion(root);
  const announceFocus=(key:string,message:string)=>status.announce(key,message,'update');
  let lastReadState='';
  const announceReadState=(key:string,message:string)=>{
    // Repeated render acknowledgements should leave a newer focus message intact.
    if(key===lastReadState) return;
    lastReadState=key;
    status.announce(key,message,'update');
  };
  let screenName='agents',screenCanBeReady=false;
  function labelOptions() {
    for(const select of root.querySelectorAll<HTMLSelectElement>('select')) {
      const label=select.getAttribute('aria-label')??select.labels?.[0]?.textContent??'Choice';
      for(const option of select.options) {
        let name=`${label}: ${option.textContent??option.value}`;
        if(new TextEncoder().encode(name).length>64) name=`${identityKey('field',label)}: ${identityKey('item',option.value||option.textContent||'All')}`;
        option.setAttribute('aria-label',name);
      }
    }
  }
  const mirrorBusy=()=>{
    labelOptions();
    const busy=main.getAttribute('aria-busy')==='true'||!!main.querySelector('[aria-busy="true"]');
    progress.hidden=!busy;progress.setAttribute('aria-label',`Loading ${screenName}`);
    const ready=screenCanBeReady&&!busy;screenStatus.hidden=!ready;
    const name=`Screen ${screenName} ready`;screenStatus.textContent=name;screenStatus.setAttribute('aria-label',name);
    html.dataset.linReady=String(ready);
  };
  const busyObserver=new MutationObserver(mirrorBusy);busyObserver.observe(main,{attributes:true,subtree:true,childList:true,attributeFilter:['aria-busy']});
  const beginAction=(event:Event)=>{
    const target=event.target;if(!(target instanceof HTMLElement)||!target.closest('button,a,input,select,textarea')) return;
    status.clear();
  };
  const echoValue=(event:Event)=>{
    const control=event.target;
    if(!(control instanceof HTMLInputElement||control instanceof HTMLSelectElement||control instanceof HTMLTextAreaElement)||control instanceof HTMLInputElement&&control.type==='password') return;
    const name=control.getAttribute('aria-label')??control.labels?.[0]?.textContent??'Field';
    const value=control instanceof HTMLInputElement&&control.type==='checkbox'?String(control.checked):control.value;
    status.announce(`field:${name}:${value}`,`${name}: ${value||'empty'}`,'status');
  };
  root.addEventListener('click',beginAction,true);root.addEventListener('input',echoValue);root.addEventListener('change',echoValue);
  const skipClick=(event:MouseEvent)=>{event.preventDefault();focusMain(main);};skip.addEventListener('click',skipClick);
  let module:ScreenModule|null=null,mounted:MountedScreen|null=null,controller:AbortController|null=null;
  let routeKey='',focusPathKey='',rendered=false,renderFailure:string|null=null,epoch=0,initialReady:Promise<void>=Promise.resolve();
  let pendingUpdate=false;
  let lastEvents:AppState['events']|null=null;let lastHead:number|null=null;let navigateFocus=true;let refreshFocus:FocusSnapshot|null=null;
  const focusHistory=new Map<string,FocusSnapshot|null>();
  const panelLabel=(state:AppState)=>state.route.screen==='arena'?'Benchmarks':state.route.screen==='bench'?'Rule':screenLabels[state.route.screen];
  function viewState(state:AppState) {
    if(disposed) return;
    const route=state.route,label=screenLabels[route.screen],owner=route.screen==='agent'?'agents':route.screen==='bench'?'arena':route.screen;
    doc.title=`Lineage · ${label}`;main.dataset.linScreen=route.screen;
    screenName=route.screen==='agent'?`agent ${identityKey('agent',route.agentId)}`:route.screen==='bench'?`arena ${identityKey('bench',route.benchId)}`:route.screen;
    main.setAttribute('aria-label',`Screen ${screenName}`);
    for(const [id,link] of links) {if(id===owner) link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');}
    refresh.textContent=`Refresh ${label}`;
    const message=state.notice??router.current().notice;
    if(message && noticeText.textContent!==message) {noticeText.textContent=message;notice.hidden=false;status.announce('notice:'+message,message);}
    else if(!message) notice.hidden=true;
    main.setAttribute('aria-busy',String(state.phase==='loading'||!rendered&&!renderFailure&&!state.error));
    diagnostics.replaceChildren();
    if(state.head===null&&state.phase==='loading') diagnostics.append(renderStatePanel({state:'loading',title:`Loading ${label}.`}));
    if(state.stale&&state.head!==null) {
      const stale=renderStatePanel({state:'stale',title:'Stale data',detail:`Data is stale. Last confirmed revision ${state.head}.`});diagnostics.append(stale);
    }
    if(state.error||renderFailure) {
      const panel=panelLabel(state);diagnostics.append(renderStatePanel({state:'error',title:'Data error',regionName:'Data error',detail:renderFailure??`${state.error!.message} ${state.error!.code}`,retryName:`Retry ${panel}`,onRetry:()=>{if(renderFailure) {controller?.abort();closeDialogsWithin(main);const previous=mounted;mounted=null;module=null;previous?.dispose();renderFailure=null;routeKey='';}void store.refresh();}}));
      status.announce(`error:${routeKey}:${state.head}:${state.error?.code??renderFailure}`,`${panel} unavailable (${state.error?.code??'render_error'}). Retry to continue.`);
    }
    if(state.head!==null) html.dataset.linRev=String(state.head);else html.removeAttribute('data-lin-rev');
    labelOptions();
    const issues=rendered?lintOperability(root):[];
    if(issues.some(issue=>issue.message==='Identity key collision. Actions unavailable.')) {
      const warning=renderStatePanel({state:'error',title:'Identity key collision. Actions unavailable.'});diagnostics.append(warning);
      for(const button of main.querySelectorAll<HTMLButtonElement>('button,input,select')) button.disabled=true;
      rendered=false;
    }
    const ready=state.head!==null&&state.phase!=='loading'&&rendered&&!renderFailure&&issues.length===0;
    screenCanBeReady=ready;mirrorBusy();
    if(ready) {
      // A refresh can keep the previous view ready while its replacement is pending.
      if(pendingUpdate) return;
      if(!state.error&&!state.notice) announceReadState(`ready:${routeKey}:${state.head}`,`${label} ready.`);
      else if(state.stale) announceReadState(`stale:${routeKey}:${state.head}`,`Data is stale. Last confirmed revision ${state.head}.`);
      if(navigateFocus) {
        const previous=focusHistory.get(focusPathKey);
        if(previous) restoreFocus(root,previous,main,announceFocus);else focusMain(main.querySelector<HTMLElement>('h1')??main);
        navigateFocus=false;
      } else if(refreshFocus) {restoreFocus(root,refreshFocus,main,announceFocus);refreshFocus=null;}
    } else if(!state.error&&!renderFailure&&!state.notice) announceReadState(`loading:${routeKey}`,`Loading ${label}.`);
  }
  function render(state:AppState) {
    if(disposed) return;
    const key=formatRoute(state.route),pathKey=formatRoute({...state.route,query:{}});const routeChanged=key!==routeKey;const dataChanged=state.events!==lastEvents||state.head!==lastHead;
    if(state.phase==='loading'&&state.head!==null&&!refreshFocus) refreshFocus=captureFocus(root);
    if(routeChanged||dataChanged) {
      const token=++epoch;
      pendingUpdate=true;
      if(routeChanged) {
        // Query edits retain the active control; path history restores entity focus.
        if(pathKey!==focusPathKey) {
          if(focusPathKey) focusHistory.set(focusPathKey,captureFocus(root));
          focusPathKey=pathKey;navigateFocus=true;refreshFocus=null;
        } else if(!navigateFocus) refreshFocus=captureFocus(root);
        controller?.abort();closeDialogsWithin(main);controller=new AbortController();
        rendered=false;renderFailure=null;routeKey=key;
      }
      lastEvents=state.events;lastHead=state.head;
      const context:ScreenContext={route:state.route,store,transport,signal:controller!.signal,navigate:route=>router.navigate(route),announce:status.announce};
      try {
        const next=getScreen(state.route);let update:Promise<void>|void;
        if(next!==module) {
          const previous=mounted;mounted=null;module=null;previous?.dispose();
          mounted=next.mount(main,context);module=next;initialReady=Promise.resolve(mounted.ready);
        }
        else update=mounted!.update(context);
        Promise.all([initialReady,update!]).then(()=>{
          if(disposed||token!==epoch||context.signal.aborted) return;
          pendingUpdate=false;rendered=true;viewState(store.getState());
        }).catch(()=>{
          if(disposed||token!==epoch||context.signal.aborted) return;
          pendingUpdate=false;renderFailure='The screen could not be rendered.';rendered=false;viewState(store.getState());
        });
      } catch {
        pendingUpdate=false;
        controller?.abort();closeDialogsWithin(main);const previous=mounted;mounted=null;module=null;previous?.dispose();
        renderFailure='The screen could not be rendered.';rendered=false;
      }
    }
    viewState(state);
  }
  const unsubscribe=store.subscribe(render);render(store.getState());
  return {dispose() {
    if(disposed) return;disposed=true;++epoch;controller?.abort();unsubscribe();closeDialogsWithin(root);mounted?.dispose();
    busyObserver.disconnect();root.removeEventListener('click',beginAction,true);root.removeEventListener('input',echoValue);root.removeEventListener('change',echoValue);status.dispose();media?.removeEventListener('change',mediaChanged);skip.removeEventListener('click',skipClick);
    root.replaceChildren();html.dataset.linReady='false';html.removeAttribute('data-lin-rev');
  }};
}
