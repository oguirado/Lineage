import { actions, entityKinds, screenLabels, type EntityKind } from './contracts.ts';
import { identityKey, normalizeName } from './primitives.ts';
export interface OperabilityIssue {code:string;message:string}
function nameOf(el:Element):string {
  const refs=el.getAttribute('aria-labelledby');
  if(refs) return refs.split(/\s+/u).map(id=>document.getElementById(id)?.textContent??'').join(' ');
  if(el.hasAttribute('aria-label')) return el.getAttribute('aria-label')!;
  if(el instanceof HTMLInputElement||el instanceof HTMLSelectElement) return Array.from(el.labels??[]).map(label=>label.textContent).join(' ');
  return el.textContent??'';
}
export function lintOperability(root:ParentNode):readonly OperabilityIssue[] {
  const issues:OperabilityIssue[]=[];const issue=(code:string,message:string)=>issues.push({code,message});
  const all=Array.from(root.querySelectorAll<HTMLElement>('*'));
  const exposed=(el:HTMLElement)=>!el.closest('[hidden],[inert]');
  const controls=all.filter(el=>exposed(el)&&el.matches('button,a[href],input,select'));
  if(root.querySelectorAll('header,[role="banner"]').length!==1||root.querySelectorAll('nav[aria-label="Primary"]').length!==1||root.querySelectorAll('main').length!==1||root.querySelectorAll('[role="status"][aria-label="Application updates"]').length!==1||!root.querySelector('[data-lin-action="skip-main"]')) issue('missing_landmark','The persistent shell landmarks are required.');
  if(all.filter(el=>exposed(el)&&el.tagName==='H1').length!==1) issue('heading_count','The active screen requires exactly one heading.');
  const names=new Set<string>();const tuples=new Set<string>();const actionScopes=new Map<Element,Set<string>>();
  const keyIdentities=new Map<string,string>();
  for(const el of all) {
    if(!exposed(el)) continue;
    if(el.hasAttribute('onclick')||el.matches('[role="button"],[role="link"],[role="checkbox"],[role="textbox"],[role="combobox"],[data-lin-action]')) if(!el.matches('button,a,input,select')) issue('clickable_non_native','Actions require native controls.');
    if(el.tabIndex>0) issue('bad_state','Positive tabindex is not supported.');
    for(const attr of el.attributes) {
      if(attr.name.startsWith('aria-')&&!new Set(['aria-label','aria-labelledby','aria-describedby','aria-live','aria-atomic','aria-modal','aria-controls','aria-details','aria-errormessage','aria-haspopup','aria-orientation','aria-level','aria-posinset','aria-setsize','aria-valuemin','aria-valuemax','aria-valuenow','aria-valuetext','aria-invalid','aria-required','aria-readonly','aria-multiline','aria-autocomplete','aria-busy','aria-checked','aria-current','aria-disabled','aria-expanded','aria-hidden','aria-pressed','aria-selected']).has(attr.name)) issue('bad_state','Unknown ARIA state.');
      if(attr.name.startsWith('data-lin-')&&!['data-lin-screen','data-lin-entity','data-lin-id','data-lin-action','data-lin-ready','data-lin-rev'].includes(attr.name)) issue('bad_selector','Unknown observable selector.');
    }
    if(el.hasAttribute('data-lin-screen')&&(!Object.hasOwn(screenLabels,el.dataset.linScreen!)||el.tagName!=='MAIN')) issue('bad_selector','Invalid active screen.');
    if(el.hasAttribute('data-lin-entity')||el.hasAttribute('data-lin-id')) {
      const kind=el.dataset.linEntity as EntityKind,id=el.dataset.linId;
      if(!entityKinds.includes(kind)||!id||/^\d+$/u.test(id)) issue('bad_selector','A canonical entity tuple is required.');
      else {
        const tuple=JSON.stringify([kind,id]);if(tuples.has(tuple)) issue('bad_selector','Duplicate entity tuple.');tuples.add(tuple);
        const key=JSON.stringify([kind,identityKey(kind,id)]);const prior=keyIdentities.get(key);
        if(prior!==undefined&&prior!==id) issue('bad_selector','Identity key collision. Actions unavailable.');keyIdentities.set(key,id);
      }
    }
  }
  for(const control of controls) {
    if(control.closest('article')) issue('interactive_article','Interactive controls must survive the article boundary.');
    const name=normalizeName(nameOf(control));if(!name) issue('missing_name','Control requires a name.');
    else if(names.has(name)) issue('duplicate_name','Control names must be unique.');else names.add(name);
    if(new TextEncoder().encode(name).length>64) issue('name_too_long','Control name exceeds its byte budget.');
    const action=control.dataset.linAction;if(!action||!actions.has(action)) {issue('bad_selector','Control requires a registered action.');continue;}
    const scope=control.closest('[data-lin-entity][data-lin-id]')??root;
    const bucket=actionScopes.get(scope as Element)??new Set<string>();if(bucket.has(action)) issue('bad_selector','Ambiguous action within its scope.');bucket.add(action);actionScopes.set(scope as Element,bucket);
  }
  return issues;
}
