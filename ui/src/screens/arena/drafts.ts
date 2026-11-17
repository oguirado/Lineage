import type { JsonObject, ToolDescriptor } from '../../ui/contracts.ts';
import { isObject, keysExactly, validateJson } from '../../transport.ts';
import { agentId, id, integer, matches } from './model.ts';
import { emptyDraft, validateDraft, type Draft } from './forms.ts';
export type MutationTool='bench_declare'|'bench_run'|'bench_verdict'|'agent_promote';
export type Pending={tool:MutationTool;actor:string;op_id:string;expected_head:number;args:JsonObject};
export type Saved={version:1;scope:string;tool:MutationTool;draft:Draft;pending?:Pending};
/** Only safe drafts and exact operation arguments may cross a reload. */
export class Drafts {
  private records=new Map<string,Saved>();
  notice='';
  constructor(private descriptors:()=>readonly ToolDescriptor[]) {}
  private key(tool:MutationTool,scope:string) {return `lineage-arena-v1:${tool}:${scope}`;}
  get(tool:MutationTool,scope:string):Saved {
    const key=this.key(tool,scope),known=this.records.get(key);if(known) return known;
    let record:Saved={version:1,tool,scope,draft:emptyDraft()};
    try {
      const raw=localStorage.getItem(key);
      if(raw) {
        const parsed=JSON.parse(raw);validateJson(parsed);
        if(raw.length>65536||!this.valid(parsed,tool,scope)) this.notice='Unsafe or invalid saved draft is unavailable for recovery.';
        else {record=parsed;this.notice='Saved draft or pending operation available. Open its named action to recover; Confirm explicitly retries.';}
      }
    } catch {this.notice='Draft storage unavailable; recovery is not confirmed.';}
    this.records.set(key,record);return record;
  }
  private valid(v:any,tool:MutationTool,scope:string):v is Saved {
    if(!isObject(v)||!keysExactly(v,['version','scope','tool','draft'],['pending'])||v.version!==1||v.scope!==scope||v.tool!==tool||!validateDraft(v.draft)) return false;
    if(scope!=='arena'&&!id(scope)) return false;
    if(tool==='bench_run'&&v.draft.fields.bench_id!==scope) return false;
    if(v.pending!==undefined) {
      const p:any=v.pending;if(!isObject(p)||!keysExactly(p,['tool','actor','op_id','expected_head','args'])||p.tool!==tool||!agentId(p.actor)||typeof p.op_id!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/u.test(p.op_id)||!integer(p.expected_head)||!isObject(p.args)) return false;
      const descriptor=this.descriptors().find(d=>d.name===tool);
      if(!descriptor||!matches(p.args,descriptor.inputSchema)||p.args.agent!==p.actor||p.args.op_id!==p.op_id||p.args.expected_head!==p.expected_head) return false;
      if(tool!=='bench_declare'&&p.args.bench_id!==scope) return false;
      if(tool==='bench_run'&&(!isObject(p.args.runner)||p.args.runner.kind!=='fake')) return false;
    }
    return true;
  }
  save(record:Saved):void {
    this.records.set(this.key(record.tool,record.scope),record);
    try {localStorage.setItem(this.key(record.tool,record.scope),JSON.stringify(record));}
    catch {this.notice='Draft storage unavailable. Could not save this draft; persistence is not confirmed.';}
  }
  complete(record:Saved):void {
    delete record.pending;
    try {localStorage.removeItem(this.key(record.tool,record.scope));}
    catch {this.notice='Draft storage unavailable; saved pending operation could not be cleared.';}
  }
}
