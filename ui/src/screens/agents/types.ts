import type { JsonObject, JsonValue } from '../../ui/contracts.ts';
export type Seat = JsonObject & {model:string;effort:string;mode:'headless'|'interactive'};
export type Pin = JsonObject & {id:string;sha256:string};
export type SkillPin = JsonObject & {skill_id:string;sha256:string};
export type Agent = JsonObject & {agent_id:string;display_name:string;workflow:string;language:string;status:string;agent_version:string;allowed_seats:Seat[];references:Pin[];skills:SkillPin[];parents:string[];generation:number;born:{op:string;event_id:string}};
export type ScoreGroup = JsonObject & {seat:Seat;memory_arm:string;runs:number;successes:number;unknown_costs:number;mean_cost_micro_usd:number|null;mean_duration_ms:number|null};
export interface Filters {q:string;workflow:string;language:string;status:string;retired:boolean;sort:string;compare:string[]}
export type Fields = JsonObject & {agent_id:string;display_name:string;workflow:string;language:string;allowed_seats:Seat[];references:Pin[];skills:SkillPin[]};
export type CreateArgs = Fields & {agent:string;op_id:string;expected_head:number};
export interface Draft {schema:'lineage.ui.create-draft/v1';fields:Fields;seat_draft:Seat;actor:string|null;op_id:string;phase:'editing'|'pending'|'uncertain'|'verifying'|'refused';submitted:CreateArgs|null;unresolved:CreateArgs|null}
export type Read = (tool:string,args:JsonObject)=>Promise<JsonValue>;
