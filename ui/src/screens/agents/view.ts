import { formatMeasurement, identityKey, createButton } from '../../ui/primitives.ts';
import type { Agent, ScoreGroup } from './types.ts';
export function node<K extends keyof HTMLElementTagNameMap>(tag:K,text?:string,className?:string):HTMLElementTagNameMap[K] {const n=document.createElement(tag);if(text!==undefined) n.textContent=text;if(className) n.className=className;return n;}
export function button(action:string,name:string,run:()=>void,disabled=false):HTMLButtonElement {return createButton({action,name,onActivate:run,disabled});}
export function panel(title:string,message:string,retry?:()=>void):HTMLElement {const p=node('section',undefined,'agents-error');p.append(node('h2',title),node('p',message));if(retry) p.append(button('retry-panel',`Retry ${title}`,retry));return p;}
export const measurement=(value:number|null|undefined,unit?:string)=>value==null?'Not measured':formatMeasurement(value,unit);
export function scoreTable(records:{record:Agent;groups:ScoreGroup[]|undefined}[],label:string):HTMLElement {
  const container=node('div',undefined,'agents-table-scroll');container.tabIndex=0;container.setAttribute('role','region');container.setAttribute('aria-label',label);
  const table=node('table');table.append(node('caption',label));const header=node('tr');for(const name of ['Agent','Seat model','Effort','Mode','Memory arm','Runs','Successes','Unknown costs','Mean cost (micro USD)','Mean duration (ms)']) {const th=node('th',name);th.scope='col';header.append(th);}const thead=node('thead');thead.append(header);table.append(thead);
  const body=node('tbody');for(const {record,groups} of records) {
    const rows=groups?.length?groups:[null];for(const group of rows) {
      const row=node('tr');const identity=node('th',record.agent_id);identity.scope='row';row.append(identity);
      const cells=group?[group.seat.model,group.seat.effort,group.seat.mode,group.memory_arm,measurement(group.runs),measurement(group.successes),measurement(group.unknown_costs),measurement(group.mean_cost_micro_usd),measurement(group.mean_duration_ms)]:Array(9).fill('Not measured');
      for(const value of cells) row.append(node('td',value));body.append(row);
    }
  }table.append(body);container.append(table);return container;
}
export function agentCard(record:Agent,groups:ScoreGroup[]|undefined,selected:boolean,collision:boolean,onOpen:()=>void,onCompare:(checked:boolean)=>void):HTMLElement {
  const key=identityKey('agent',record.agent_id),card=node('li',undefined,'agent-card');card.dataset.linEntity='agent';card.dataset.linId=record.agent_id;
  const heading=node('h2',`Agent ${key}`);heading.id=`agent-${record.agent_id}-heading`;card.setAttribute('aria-labelledby',heading.id);
  const identity=node('p',record.agent_id,'agent-identity');identity.id=`agent-${record.agent_id}-identity`;
  const version=node('p',`Current version ${record.agent_version}`,'agent-version');
  const name=node('p',record.display_name.normalize('NFC'),'agent-display-name');
  const description=node('p',`Workflow ${record.workflow} · Language ${record.language} · Status ${record.status}`);
  const seats=node('ul');for(const seat of record.allowed_seats) seats.append(node('li',`Seat ${seat.model} / ${seat.effort} / ${seat.mode}`));
  const link=node('a',`Open agent ${key}`);link.dataset.linAction='open-agent';link.setAttribute('aria-describedby',identity.id);
  if(collision) link.setAttribute('aria-disabled','true');else link.href=`#/agents/${encodeURIComponent(record.agent_id)}`;
  link.addEventListener('click',e=>{e.preventDefault();if(!collision) onOpen();});
  const compare=node('input');compare.type='checkbox';compare.checked=selected;compare.disabled=collision;compare.dataset.linAction='compare-agent';compare.setAttribute('aria-label',`Compare agent ${key}`);compare.setAttribute('aria-describedby',identity.id);compare.addEventListener('change',()=>onCompare(compare.checked));
  const label=node('label',`Compare ${key} `);label.append(compare);const actions=node('div',undefined,'agent-actions');actions.append(link,label);
  card.append(heading,identity,version,name,description,seats,scoreTable([{record,groups}],`Measurements for ${key}`),actions);return card;
}
