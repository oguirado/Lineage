import { type EntityKind, type PanelState, entityKinds } from './contracts.ts';
export type { PanelState } from './contracts.ts';
export interface IdentityAttrs {entity:EntityKind;id:string}
export interface ButtonOptions {name:string;action:string;identity?:IdentityAttrs;disabled?:boolean;onActivate:(event:MouseEvent)=>void}
export interface LinkOptions {name:string;action:string;href:string;identity?:IdentityAttrs}
export interface StatePanelOptions {state:PanelState;title:string;detail?:string;onRetry?:()=>void;regionName?:string;retryName?:string;retryAction?:string}
export function normalizeName(name:string):string {return name.normalize('NFC').replace(/\s+/gu,' ').trim();}
export function checkedName(name:string):string {
  const normalized=normalizeName(name);if(!normalized||new TextEncoder().encode(normalized).length>64) throw Error('Control name must fit the accessible name budget.');return normalized;
}
function attributes(node:HTMLElement,options:{name:string;action:string;identity?:IdentityAttrs}) {
  node.textContent=checkedName(options.name);node.dataset.linAction=options.action;
  if(options.identity) {if(!entityKinds.includes(options.identity.entity)||!options.identity.id) throw Error('Invalid entity identity');node.dataset.linEntity=options.identity.entity;node.dataset.linId=options.identity.id;}
}
export function createButton(options:ButtonOptions):HTMLButtonElement {
  const button=document.createElement('button');button.type='button';attributes(button,options);button.disabled=options.disabled??false;
  button.addEventListener('click',event=>{if(!button.disabled&&button.getAttribute('aria-disabled')!=='true') options.onActivate(event);});return button;
}
export function createLink(options:LinkOptions):HTMLAnchorElement {
  const invalid=(value:string)=>/^[a-z][a-z0-9+.-]*:|\/\/|\\|[\u0000-\u001f\u007f]/iu.test(value);
  let decoded:string;try{decoded=decodeURIComponent(options.href);}catch{throw Error('Invalid local link');}
  if(invalid(options.href)||invalid(decoded)) throw Error('Invalid local link');
  if(options.href.startsWith('#')&&!options.href.startsWith('#/')) throw Error('Invalid application link');
  if(options.href.startsWith('#/')) {
    // Route identity and known query validation remain the router's responsibility.
    if(!/^#\/(?:agents(?:\/[^/?#]+)?|lineage|arena(?:\/[^/?#]+)?|ledger)(?:\?[^#]*)?$/u.test(options.href)) throw Error('Invalid application link');
  }
  const resolved=new URL(options.href,window.location.href);if(resolved.origin!==window.location.origin) throw Error('Invalid link origin');
  const link=document.createElement('a');attributes(link,options);link.setAttribute('href',options.href);return link;
}
const stateText:Record<PanelState,string>={loading:'Loading',empty:'Empty', 'no-match':'No matches',ready:'Ready',busy:'Busy',queued:'Queued',running:'Running',stalled:'Stalled',stale:'Stale',error:'Unavailable',completed:'Completed','not-built':'Not built yet'};
export function renderStatePanel(options:StatePanelOptions):HTMLElement {
  const panel=document.createElement('section');panel.className=`state-panel state-${options.state}`;
  const heading=document.createElement('h2');heading.textContent=options.title;
  const description=document.createElement('p');description.textContent=stateText[options.state];
  panel.append(heading,description);
  if(options.detail) {const detail=document.createElement('p');detail.textContent=options.detail;panel.append(detail);}
  if(options.regionName||options.state==='error') {panel.setAttribute('role','region');panel.setAttribute('aria-label',options.regionName??'Data error');}
  if(options.onRetry) {
    if(options.retryAction&&options.retryAction!=='retry-panel') throw Error('Retry must use the registered action.');
    panel.append(createButton({name:options.retryName??`Retry ${options.title}`,action:'retry-panel',onActivate:()=>options.onRetry?.()}));
  }
  return panel;
}
export function formatMeasurement(value:number|null|undefined,unit?:string):string {
  if(value==null) return 'not measured';if(!Number.isFinite(value)) throw Error('Non-finite measurement');return String(value)+(unit?' '+unit:'');
}
/** SHA-256, synchronous so identity keys are available before render readiness. */
function sha256(text:string):string {
  const bytes=new TextEncoder().encode(text);const padded=new Uint8Array(Math.ceil((bytes.length+9)/64)*64);padded.set(bytes);padded[bytes.length]=0x80;
  const view=new DataView(padded.buffer);const bits=bytes.length*8;view.setUint32(padded.length-8,Math.floor(bits/4294967296));view.setUint32(padded.length-4,bits>>>0);
  const h=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
  const k=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
  const rotate=(x:number,n:number)=>(x>>>n)|(x<<(32-n));
  const w=new Uint32Array(64);
  for(let offset=0;offset<padded.length;offset+=64) {
    for(let i=0;i<16;i++) w[i]=view.getUint32(offset+i*4);
    for(let i=16;i<64;i++) {const a=w[i-15],b=w[i-2];w[i]=(rotate(a,7)^rotate(a,18)^(a>>>3))+w[i-16]+(rotate(b,17)^rotate(b,19)^(b>>>10))+w[i-7];}
    let [a,b,c,d,e,f,g,j]=h;
    for(let i=0;i<64;i++) {const t1=(j+(rotate(e,6)^rotate(e,11)^rotate(e,25))+((e&f)^(~e&g))+k[i]+w[i])|0;const t2=((rotate(a,2)^rotate(a,13)^rotate(a,22))+((a&b)^(a&c)^(b&c)))|0;j=g;g=f;f=e;e=(d+t1)|0;d=c;c=b;b=a;a=(t1+t2)|0;}
    [a,b,c,d,e,f,g,j].forEach((v,i)=>h[i]=(h[i]+v)>>>0);
  }
  return h.map(v=>v.toString(16).padStart(8,'0')).join('');
}
export function identityKey(kind:EntityKind|'reference'|'rule'|'seat'|'field'|'item',identity:string):string {
  if(new TextEncoder().encode(identity).length<=20) return identity;
  return [...identity].filter(c=>/^[\x20-\x7e]$/u.test(c)).slice(0,7).join('')+'-'+sha256(kind+'\0'+identity).slice(0,12);
}
