// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { ACTOR, BENCH, Script, agent, conforms, cursor, declaration, event, isolate, repoRoot, result, runReply, status, toolSchema, verdict } from './helpers.ts';
import { recordLaunch } from './forms.helpers.ts';
isolate();

describe('Oracle data and freeze checks, independent of product acceptance', () => {
  it('A27 scripted public replies and records conform to the frozen wire schemas', () => {
    const check = (tool: string, value: any) => expect(conforms(value, toolSchema(tool, true)), `${tool} scripted result schema`).toBe(true);
    check('bench_list', { benches: [status()], next_after: null, head: 10 }); check('bench_status', { bench: status({ verdict: verdict(), results: [result()] }) });
    check('agent_get', { record: agent() }); check('agent_list', { agents: [agent()], next_after: null, head: 10 });
    check('run_get', runReply()); check('run_get', runReply(result(), 'heldout', false));
    check('ledger_events', cursor([event(5, 'bench.result', result())]));
  });
  it('A27 the scripted compound launch has closed public replies and actual run wrappers', async () => {
    const script = new Script(); recordLaunch(script);
    const response = await script.dispatch('bench_run', { bench_id: BENCH, runner: { kind: 'fake', seed: 17 }, agent: ACTOR, op_id: 'oracle-launch', expected_head: 10 }, { mutation: true });
    expect(conforms(response, toolSchema('bench_run', true))).toBe(true);
    for (const value of script.runs.values()) expect(conforms(value, toolSchema('run_get', true))).toBe(true);
    expect(conforms(cursor(script.journal, { head: 13, next_after: 13 }), toolSchema('ledger_events', true))).toBe(true);
  });
  it('A27 malformed scripted shapes are discriminated by the public schema check', () => {
    expect(conforms({ bench: { ...status(), synthetic: true } }, toolSchema('bench_status', true))).toBe(false);
    expect(conforms({ run: runReply() }, toolSchema('run_get', true))).toBe(false);
    expect(conforms({ ...declaration(), agents: ['same-agent', 'same-agent'] }, JSON.parse(readFileSync(resolve(repoRoot, 'schemas/bench_declared.schema.json'), 'utf8')))).toBe(false);
    expect(conforms({ bench: { ...status(), head: null } }, toolSchema('bench_status', true))).toBe(false);
  });
  it('A32 frozen oracle bytes match the published relative-path SHA-256 manifest', () => {
    const freeze = JSON.parse(readFileSync(resolve(repoRoot, 'ui/tests/arena/freeze.json'), 'utf8'));
    expect(freeze.schema).toBe('lineage.u25.oracle.freeze/v1'); expect(freeze.spec_sha256).toMatch(/^[a-f0-9]{64}$/u);
    expect(Object.keys(freeze.files).length).toBeGreaterThan(0);
    for (const [path, digest] of Object.entries(freeze.files)) {
      expect(path.startsWith('ui/tests/arena/') && !path.includes('..')).toBe(true);
      expect(createHash('sha256').update(readFileSync(resolve(repoRoot, path))).digest('hex'), `Frozen ${path}`).toBe(digest);
    }
  });
});
