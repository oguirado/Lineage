import { type EntityKind, entityKinds } from './contracts.ts';
import { identityKey } from './primitives.ts';
export interface FocusSnapshot {action:string;entity?:EntityKind;id?:string}
export function focusMain(main:HTMLElement):void {if(!main.hasAttribute('tabindex')) main.tabIndex=-1;main.focus();}
export function captureFocus(root:HTMLElement):FocusSnapshot|null {
  const active=document.activeElement;if(!(active instanceof HTMLElement)||!root.contains(active)||!active.dataset.linAction) return null;
  const wrapper=active.closest<HTMLElement>('[data-lin-entity][data-lin-id]');const result:FocusSnapshot={action:active.dataset.linAction};
  if(wrapper&&entityKinds.includes(wrapper.dataset.linEntity as EntityKind)) {result.entity=wrapper.dataset.linEntity as EntityKind;result.id=wrapper.dataset.linId;}
  return result;
}
export function restoreFocus(root:HTMLElement,snapshot:FocusSnapshot|null,fallback:HTMLElement,announce?:(key:string,message:string)=>void):void {
  if(!snapshot) return;
  const matches=Array.from(root.querySelectorAll<HTMLElement>('[data-lin-action]')).filter(node=>{
    if(node.dataset.linAction!==snapshot.action||node.closest('[hidden],[inert]')||(node as HTMLButtonElement).disabled) return false;
    const wrapper=node.closest<HTMLElement>('[data-lin-entity][data-lin-id]');return snapshot.entity?wrapper?.dataset.linEntity===snapshot.entity&&wrapper.dataset.linId===snapshot.id:!wrapper;
  });
  if(matches.length===1) matches[0].focus();else {
    focusMain(fallback);
    if(snapshot.entity&&snapshot.id) announce?.(JSON.stringify(['removed',snapshot.entity,snapshot.id]),`${identityKey(snapshot.entity,snapshot.id)} is no longer in this view.`);
  }
}
