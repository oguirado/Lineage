/** Persistent announcements plus an AX outcome whose name contains the result. */
export function createStatusRegion(host:HTMLElement) {
  const element=document.createElement('div');element.setAttribute('role','status');element.setAttribute('aria-label','Application updates');element.setAttribute('aria-live','polite');element.setAttribute('aria-atomic','true');element.className='application-status';host.append(element);
  // output has the native status role. Preserve the legacy announcement hook.
  const outcome=document.createElement('output');outcome.className='action-outcome';outcome.hidden=true;host.append(outcome);
  let disposed=false;let lastKey='';let lastMessage='';
  const clear=()=>{lastKey='';lastMessage='';outcome.hidden=true;outcome.textContent='';outcome.removeAttribute('aria-label');outcome.removeAttribute('role');};
  return {element,clear,announce(key:string,message:string) {
    if(disposed||key===lastKey&&message===lastMessage) return;lastKey=key;lastMessage=message;
    if(element.textContent!==message) element.textContent=message;
    if(/^(ready:|loading:)/u.test(key)) return;
    const error=/error|refused|unavailable|conflict|failed/iu.test(key+' '+message);
    const text=error&&!message.startsWith('Error:')?'Error: '+message:message;
    outcome.hidden=false;outcome.textContent=text;outcome.setAttribute('aria-label',text);
    if(error) outcome.setAttribute('role','alert');else outcome.removeAttribute('role');
  },dispose() {disposed=true;}};
}
