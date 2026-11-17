import type { ScreenContext } from '../../ui/contracts.ts';
import { openDialog } from '../../ui/dialog.ts';
import { identityKey } from '../../ui/primitives.ts';
import { getResult, scoreResult, errorText } from './model.ts';
import { node, panel, scoreTable } from './view.ts';
import type { Agent, ScoreGroup, Read } from './types.ts';
export function openComparison(host:HTMLElement,context:ScreenContext,ids:string[],trigger:HTMLElement,fallback:HTMLElement,read:Read):{close():void} {
  const content=node('section');content.append(node('h2','Agent comparison'),node('p','Loading comparison.'));
  const modal=openDialog({name:'agent comparison',content,trigger,fallback,closeName:'Close agent comparison',closeAction:'close-inspector',host});
  let turn=0;
  const records=new Map<string,Agent>(),scores=new Map<string,ScoreGroup[]>();let recordError='',scoreError='';
  const current=(t:number)=>t===turn&&modal.element.isConnected&&!context.signal.aborted;
  function render() {
    if(!modal.element.isConnected||context.signal.aborted) return;
    content.replaceChildren(node('h2','Agent comparison'));
    const keys=new Map<string,string>();let collision=false;
    for(const id of ids) {const key=identityKey('agent',id);if(keys.has(key)&&keys.get(key)!==id) collision=true;keys.set(key,id);content.append(node('p',id));}
    if(collision) content.append(node('p','Identity key collision. Actions unavailable.'));
    if(recordError) content.append(panel('Agent',recordError,()=>{void loadRecords();}));
    content.append(scoreTable(ids.flatMap(id=>records.has(id)?[{record:records.get(id)!,groups:scores.get(id)}]:[]),'Agent and seat comparison'));
    if(scoreError) content.append(panel('Scorecard',scoreError,()=>{void loadScores();}));
  }
  async function loadRecords() {
    const t=++turn;recordError='';
    await Promise.all(ids.map(async id=>{try {const record=getResult(await read('agent_get',{agent_id:id}),id);if(current(t)) records.set(id,record);}catch(e){if(current(t)) recordError=errorText(e);}}));
    if(!current(t)) return;render();await loadScores();
  }
  async function loadScores() {
    const t=turn;scoreError='';
    await Promise.all(ids.filter(id=>records.has(id)).map(async id=>{try {const groups=scoreResult(await read('scorecard_get',{agent_id:id}),id);if(current(t)) scores.set(id,groups);}catch(e){if(current(t)) scoreError=errorText(e);}}));if(current(t)) render();
  }
  void loadRecords();return {close(){++turn;modal.close();}};
}
