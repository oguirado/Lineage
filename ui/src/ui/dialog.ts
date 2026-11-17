import { checkedName, createButton } from './primitives.ts';
let active:{element:HTMLDialogElement;close():void}|null=null;
export interface DialogOptions {name:string;content:HTMLElement;trigger:HTMLElement;fallback:HTMLElement;closeName?:string;closeAction?:'cancel-dialog'|'close-inspector';host?:HTMLElement}
export function closeDialogsWithin(root:HTMLElement):void {if(active&&root.contains(active.element)) active.close();}
export function openDialog(options:DialogOptions):{element:HTMLDialogElement;close():void} {
  if(active) throw Error('Only one dialog may be open.');
  const host=options.host??document.getElementById('main-content');if(!host||host.closest('article')) throw Error('A dialog requires an active, non-article host.');
  const element=document.createElement('dialog');element.setAttribute('aria-label',checkedName(options.name));element.setAttribute('aria-modal','true');element.tabIndex=-1;
  const closeButton=createButton({name:options.closeName??'Close dialog',action:options.closeAction??'close-inspector',onActivate:()=>close()});
  element.append(options.content,closeButton);host.append(element);
  let closed=false;const backgrounds:{element:HTMLElement;inert:boolean}[]=[];
  let branch:HTMLElement=element;
  while(branch.parentElement) {
    for(const sibling of branch.parentElement.children) if(sibling!==branch&&sibling instanceof HTMLElement) {backgrounds.push({element:sibling,inert:sibling.hasAttribute('inert')});sibling.setAttribute('inert','');}
    branch=branch.parentElement;if(branch===document.body) break;
  }
  const enabled=()=>Array.from(element.querySelectorAll<HTMLElement>('input:not(:disabled),button:not(:disabled),select:not(:disabled),a[href]')).filter(el=>!el.closest('[hidden],[inert]'));
  const focusFirst=()=>{(enabled()[0]??element).focus();};
  const keydown=(event:KeyboardEvent)=>{
    if(closed) return;
    if(event.key==='Escape') {event.preventDefault();close();}
    if(event.key==='Tab') {
      const controls=enabled(),first=controls[0],last=controls.at(-1);
      if(!first) {event.preventDefault();element.focus();}
      else if(event.shiftKey&&(document.activeElement===first||document.activeElement===element)) {event.preventDefault();last?.focus();}
      else if(!event.shiftKey&&document.activeElement===last) {event.preventDefault();first.focus();}
    }
  };
  const contain=(event:FocusEvent)=>{if(!closed&&event.target instanceof Node&&!element.contains(event.target)) focusFirst();};
  const cancelled=(event:Event)=>{event.preventDefault();close();};
  const nativeClosed=()=>close();
  function close() {
    if(closed) return;closed=true;active=null;
    element.removeEventListener('keydown',keydown);element.removeEventListener('cancel',cancelled);element.removeEventListener('close',nativeClosed);document.removeEventListener('focusin',contain);
    if(typeof element.close==='function'&&element.open) element.close();element.removeAttribute('open');element.remove();
    for(const item of backgrounds) if(!item.inert) item.element.removeAttribute('inert');
    const target=options.trigger.isConnected?options.trigger:options.fallback;
    if(target.isConnected) {if(!target.matches('button,a,input,select,[tabindex]')) target.tabIndex=-1;target.focus();}
  }
  active={element,close};element.addEventListener('keydown',keydown);element.addEventListener('cancel',cancelled);element.addEventListener('close',nativeClosed);document.addEventListener('focusin',contain);
  try {if(typeof element.showModal==='function') element.showModal();else element.setAttribute('open','');focusFirst();}
  catch(error) {close();throw error;}
  return {element,close};
}
