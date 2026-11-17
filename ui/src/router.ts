import { forbiddenKeys, type Route, type ScreenId } from './ui/contracts.ts';
export interface RouteResolution {readonly route:Route;readonly canonicalHash:string;readonly notice:string|null}
const registry:Record<ScreenId,readonly string[]> = {
  agents:['q','workflow','language','status','retired','sort','compare'], agent:['panel','kind','level','privacy','inheritable','seat','arm'],
  lineage:['root','q','selected'],arena:['q','purpose','state'],bench:['rule'],ledger:['q','agent','kind','event'],
};
const unsafe = /[\u0000-\u001f\u007f\\]/u;
const fallback = ():RouteResolution => ({route:{screen:'agents',query:{}},canonicalHash:'#/agents',notice:'Unknown page. Showing Agents.'});
export function parseRoute(hash:string):RouteResolution {
  if (hash === '' || hash === '#' || hash === '#/') return {route:{screen:'agents',query:{}},canonicalHash:'#/agents',notice:null};
  try {
    if (!hash.startsWith('#/') || unsafe.test(hash)) return fallback();
    const [rawPath, ...queryParts] = hash.slice(1).split('?');
    if (queryParts.length > 1 || /%(?:2f|5c|2e)/iu.test(rawPath)) return fallback();
    const path = decodeURIComponent(rawPath); if (unsafe.test(path)) return fallback();
    const parts = path.split('/').slice(1); let route:Route;
    if (parts.length === 1 && ['agents','lineage','arena','ledger'].includes(parts[0])) route = {screen:parts[0],query:{}} as Route;
    else if (parts.length === 2 && parts[0] === 'agents' && /^[a-z][a-z0-9-]{2,63}$/u.test(parts[1])) route = {screen:'agent',agentId:parts[1],query:{}};
    else if (parts.length === 2 && parts[0] === 'arena' && /^[A-Za-z0-9_-]{8,64}$/u.test(parts[1])) route = {screen:'bench',benchId:parts[1],query:{}};
    else return fallback();
    const seen = new Set<string>(); const query:Record<string,string> = {}; let ignored = false;
    if (queryParts[0]) for (const pair of queryParts[0].split('&')) {
      const equals = pair.indexOf('='); const decode = (s:string) => decodeURIComponent(s.replace(/\+/gu,' '));
      const key = decode(equals < 0 ? pair : pair.slice(0,equals)); const value = decode(equals < 0 ? '' : pair.slice(equals+1));
      if (seen.has(key) || forbiddenKeys.has(key) || unsafe.test(key) || unsafe.test(value)) return fallback();
      seen.add(key); if (registry[route.screen].includes(key)) query[key]=value; else ignored=true;
    }
    route = {...route,query}; return {route,canonicalHash:formatRoute(route),notice:ignored?'Unknown query fields ignored.':null};
  } catch { return fallback(); }
}
export function formatRoute(route:Route):string {
  const path = route.screen==='agent' ? `agents/${encodeURIComponent(route.agentId)}` : route.screen==='bench' ? `arena/${encodeURIComponent(route.benchId)}` : route.screen;
  const entries = Object.keys(route.query).sort().map(key => {
    if (forbiddenKeys.has(key) || unsafe.test(key) || unsafe.test(route.query[key])) throw Error('Invalid route query');
    return `${encodeURIComponent(key)}=${encodeURIComponent(route.query[key])}`;
  });
  return `#/${path}${entries.length?'?'+entries.join('&'):''}`;
}
/** Callback-first public factory; initial-hash-first is retained for the original seam. */
export function createRouter(onChange:(result:RouteResolution)=>void,initialHash?:string):Router;
export function createRouter(initialHash:string,onChange:(result:RouteResolution)=>void):Router;
export function createRouter(first:string|((result:RouteResolution)=>void),second?:string|((result:RouteResolution)=>void)):Router {
  const callback = typeof first==='function' ? first : second as (result:RouteResolution)=>void;
  const initial = typeof first==='string' ? first : typeof second==='string' ? second : window.location.hash;
  let current = parseRoute(initial); let disposed=false;
  const canonicalize = () => {if (window.location.hash!==current.canonicalHash) window.history.replaceState(null,'',current.canonicalHash);};
  canonicalize();
  const changed = () => {
    if (disposed) return;
    const next = parseRoute(window.location.hash);
    if (next.canonicalHash===current.canonicalHash && next.notice===current.notice) return;
    current=next; canonicalize(); callback(current);
  };
  window.addEventListener('hashchange',changed);
  return {current:()=>current,navigate(route) {
    if (disposed) return;
    current=parseRoute(formatRoute(route));
    if (window.location.hash!==current.canonicalHash) window.history.pushState(null,'',current.canonicalHash);
    callback(current);
  },dispose() {if (!disposed) {disposed=true;window.removeEventListener('hashchange',changed);}}};
}
export interface Router {current():RouteResolution;navigate(route:Route):void;dispose():void}
