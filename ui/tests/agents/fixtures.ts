/** Synthetic wire records only. These are not live creation or measurement receipts. */
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { JsonObject, JsonValue, LedgerEvent, ToolDescriptor } from '../../src/ui/contracts.ts';
import { canonical } from '../../src/transport.ts';

export const DRAFT_KEY = 'lineage.u22.create-draft.v1';
export const CLOCK = 1_700_000_000_000;
export const workflows = ['develop','test','review','harden','research','orchestrate'] as const;
export const statuses = ['draft','shadow','promoted','retired'] as const;
export const sha = (value: string) => createHash('sha256').update(value).digest('hex');
export const constitutionText = 'Synthetic constitution.\n';
export const hash = sha(constitutionText);
export const eventId = (n: number) => `e-${n.toString(16).padStart(16,'0')}`;
export const seat = (changes: JsonObject = {}): JsonObject => ({model:'synthetic-model',effort:'medium',mode:'headless',...changes});
export const refs = (): JsonObject[] => ['gold_s1','memory_v21'].map(id => ({id,sha256:sha(id)}));
export const skill = (): JsonObject => ({skill_id:'test-skill',sha256:sha('test-skill')});
export function agent(id = 'alpha-root', changes: JsonObject = {}): JsonObject {
  const base: JsonObject = {schema:'lineage.agent/v1',agent_id:id,display_name:'Shared name',workflow:'develop',language:'general',
    allowed_seats:[seat()],references:refs(),constitution_sha256:hash,skills:[],memory_gen:0,brief_head_sha256:hash,
    agent_version:sha(canonical({constitution_sha256:hash,skills:[],memory_gen:0})),generation:0,parents:[],
    born:{op:'genesis',event_id:eventId(1)},status:'draft'};
  return {...base,...changes};
}
export const longIds = ['agent-'+ 'a'.repeat(58),'agent-'+ 'b'.repeat(58)];
export const sampleAgents = (): JsonObject[] => [agent(),agent('beta-root'),agent('gamma-root',{display_name:'Éclair <script>passive</script>',language:'日本語'}),agent('retired-root',{status:'retired'})];
export function group(changes: JsonObject = {}): JsonObject {
  return {seat:seat(),memory_arm:'own',runs:2,successes:1,unknown_costs:1,mean_cost_micro_usd:0,mean_duration_ms:null,...changes};
}
export const repositoryPath = (relative: string): string => resolve(dirname(fileURLToPath(import.meta.url)),'../../..',relative);
const contract = readFileSync(repositoryPath('docs/CONTRACT.md'),'utf8');
export function descriptors(): ToolDescriptor[] {
  return ['agent_list','agent_get','reference_get','reference_verify','skill_list','scorecard_get','agent_create','ledger_events'].map(name => {
    const heading='### `'+name+'`';
    const section=contract.slice(contract.indexOf(heading));
    const fence=section.indexOf('```json\n');
    const end=section.indexOf('\n```',fence+8);
    const inputSchema=JSON.parse(section.slice(fence+8,end)) as JsonObject;
    return {name,description:`Synthetic ${name} contract capability`,inputSchema};
  });
}
export function args(changes: JsonObject = {}): JsonObject {
  return {agent_id:'new-child',display_name:'New child',workflow:'develop',language:'general',allowed_seats:[seat()],references:refs(),skills:[],
    agent:'acting-root',op_id:'synthetic-create-0001',expected_head:7,...changes};
}
export function born(record: JsonObject, submitted: JsonObject, n = 8): LedgerEvent {
  const effective = {...submitted}; delete effective.op_id; delete effective.expected_head;
  const body = {schema:'lineage.event/v1' as const,id:eventId(n),lamport:n,ts:CLOCK+n,ledger:'main' as const,
    agent:String(submitted.agent),kind:'agent.born',payload:{record,inherited_units:[],rejected_units:[],constitution:{text:constitutionText,overlays:[],rule_ids:[]}},
    op_id:String(submitted.op_id),request_sha256:sha(canonical({tool:'agent_create',args:effective})),evidence:[],prev_sha256:'0'.repeat(64)};
  return {...body,sha256:sha(canonical(body))};
}
export function creation(submitted: JsonObject, n = 8): {record: JsonObject; commit: JsonObject; event: LedgerEvent} {
  const record = agent(String(submitted.agent_id),Object.fromEntries(['agent_id','display_name','workflow','language','allowed_seats','references','skills'].map(key => [key,submitted[key]])));
  record.born = {op:'genesis',event_id:eventId(n)};
  record.agent_version = sha(canonical({constitution_sha256:record.constitution_sha256,skills:record.skills,memory_gen:record.memory_gen}));
  const event = born(record,submitted,n);
  return {record,event,commit:{event_ids:[event.id],head:n,sha256:sha(canonical(event as unknown as JsonObject)+'\n')}};
}
export function draft(changes: JsonObject = {}): JsonObject {
  const submitted = args();
  return {schema:'lineage.ui.create-draft/v1',fields:Object.fromEntries(['agent_id','display_name','workflow','language','allowed_seats','references','skills'].map(k => [k,submitted[k]])),
    seat_draft:{model:'',effort:'',mode:'headless'},actor:'acting-root',op_id:submitted.op_id,phase:'editing',submitted:null,unresolved:null,...changes};
}
export function clone<T>(value: T): T { return structuredClone(value); }
export function page(events: LedgerEvent[] = [], head = 7, next_after = head, has_more = false, resync = false): JsonObject {
  return {events:events as unknown as JsonValue[],head,next_after,has_more,resync};
}
