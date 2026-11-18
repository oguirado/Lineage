// @vitest-environment jsdom
import { createHash } from 'node:crypto';
import { describe, expect, it, vi } from 'vitest';
import { ACTOR, BENCH, CANDIDATE, FROZEN_VERSION, HASH, Script, action, allActions, click, copy, cursor, declaration, detailRoute, dialog, edit, event, eventId, flush, isolate, key, launchForm, listRoute, mount, nameOf, noRecorded, ready, record, refusal, restoreStorage, result, reveal, runReply, snapshotStorage, status, submit, text, verdict } from './helpers.ts';
import { recordLaunch } from './forms.helpers.ts';
isolate();

function withCells(cells = [result()]): Script {
  const script = new Script(); script.benches.set(BENCH, status({ results: cells }));
  for (const cell of cells) script.runs.set(cell.run_id, runReply(cell));
  script.journal = cells.map((cell, n) => event(n + 5, 'bench.result', cell)); return script;
}
const pagedJournal = Array.from({ length: 201 }, (_, index) => {
  const lamport = index + 1;
  const cell = lamport === 201 ? result() : result(`run_unrelated_${lamport}`);
  return event(lamport, 'bench.result', cell);
});

async function pagedDetail(cells: ReturnType<typeof result>[]) {
  const script = new Script();
  script.journal = copy(pagedJournal);
  script.head = pagedJournal.length;
  script.benches.set(BENCH, status({ results: cells, head: script.head }));
  const digest = createHash('sha256').update(JSON.stringify(script.journal)).digest('hex');
  expect(digest).toBe('0b15acbfdf9858c29aed689af8063f09c4eee452327c4737bf645465ef950892');

  const h = mount(script);
  await ready(h);
  expect(h.host.getAttribute('aria-busy')).toBe('false');
  expect(h.host.querySelector('[role="alert"]')).toBeNull();
  expect(script.calls('bench_status').map(([, args]) => args)).toEqual([{ bench_id: BENCH }]);
  return h;
}

async function inspect(script: Script, runId = 'run_alpha_0001', literal = 'inspect-bench-result') {
  const h = mount(script); await ready(h); await click(record(h.host, 'run', runId), literal);
  return { h, modal: dialog(h.root, literal === 'inspect-bench-result' ? 'task result' : 'run') };
}

describe('U25 actual runs, evidence and hostile inputs', () => {
  it('A05 A16 task inspector uses exact run_get frozen identity and null-safe cost', async () => {
    const { h, modal } = await inspect(withCells());
    expect(nameOf(modal)).toBe(`task result ${key('run', 'run_alpha_0001')}`);
    const content = text(modal);
    for (const value of ['run_alpha_0001', 'task_alpha_0001', CANDIDATE, 'test-model', 'medium', 'headless', 'own', 'error', FROZEN_VERSION, 'Not measured']) expect(content).toContain(value);
    expect(content).toMatch(/gate.*pass|pass.*gate/iu); expect(content).toContain('evidence/task-result.txt');
    expect(h.script.calls('run_get').some(([, args, options]) => args.run_id === 'run_alpha_0001' && options.mutation === false)).toBe(true);
    expect(content).not.toMatch(/cost.*(?:0 USD|0 tokens)/iu);
    expect(modal.querySelector('a[href="evidence/task-result.txt"]')).toBeNull();
  });

  it('A05 open run with closed null never displays a passed closing memory gate', async () => {
    const script = withCells(); script.runs.set('run_alpha_0001', runReply(result(), 'select', false));
    const { modal } = await inspect(script, 'run_alpha_0001', 'open-bench-run');
    expect(text(modal)).toContain(FROZEN_VERSION); expect(text(modal)).toMatch(/open|not closed|pending/iu);
    expect(text(modal)).not.toMatch(/gate passed|memory gate.*passed|completed task/iu);
  });

  it.each(['ADMIT', 'HOLD', 'red', 'green', 'error'])('A16 exact task outcome %s is preserved', async outcome => {
    const cell = result('run_outcome_0001', { verdict: outcome, correctness: ['ADMIT', 'green'].includes(outcome) ? 1 : 0 });
    const { h, modal } = await inspect(withCells([cell]), cell.run_id);
    expect(text(record(h.host, 'run', cell.run_id))).toContain(outcome); expect(text(modal)).toContain(outcome);
    expect(nameOf(action(modal, 'close-inspector'))).toBe('Close task result');
  });

  it('A16 inspector failure retains other cells and uses Task results recovery', async () => {
    const cells = [result(), result('run_second_0002')]; const script = withCells(cells).queue('run_get', refusal('no_run'));
    const { h, modal } = await inspect(script);
    expect(text(modal)).toContain('no_run'); action(modal, 'retry-panel', 'Retry Task results');
    await click(modal, 'close-inspector', 'Close task result');
    record(h.host, 'run', cells[0].run_id); record(h.host, 'run', cells[1].run_id);
    await click(record(h.host, 'run', cells[1].run_id), 'open-bench-run');
    expect(text(dialog(h.root, 'run'))).toContain(cells[1].run_id);
  });

  it('A17 failed task retains its verified event link after an evidence refresh error', async () => {
    const script = withCells(); const h = mount(script); await ready(h);
    const row = record(h.host, 'run', 'run_alpha_0001'); const original = action(row, 'open-task-evidence');
    expect(original.tagName).toBe('A'); const href = original.getAttribute('href'); expect(href).toBe(`#/ledger?event=${encodeURIComponent(eventId(5))}`);
    script.queue('ledger_events', refusal('busy')); await click(h.host, 'refresh-benchmark');
    const refreshed = record(h.host, 'run', 'run_alpha_0001'); expect(text(refreshed)).toContain('error');
    expect(action(refreshed, 'open-task-evidence').getAttribute('href')).toBe(href);
    expect(h.script.mutationCalls()).toHaveLength(0);
  });

  it('A17 empty detail settles without paging for evidence', async () => {
    const h = await pagedDetail([]);
    expect(text(h.host)).toContain('Task results pending. Not measured.');
    expect(h.host.querySelector('[data-lin-action="open-task-evidence"]')).toBeNull();
    expect(h.script.calls('ledger_events').map(([, args]) => args)).toEqual([]);
  });

  it.each([
    { name: 'a last-page witness', cell: result(), expectedHref: `#/ledger?event=${eventId(201)}` },
    { name: 'only unrelated witnesses', cell: result('run_missing_0001'), expectedHref: null },
  ])('A17 populated detail pages the same journal with $name', async ({ cell, expectedHref }) => {
    const h = await pagedDetail([cell]);
    const row = record(h.host, 'run', cell.run_id);
    if (expectedHref) {
      expect(action(row, 'open-task-evidence').getAttribute('href')).toBe(expectedHref);
    } else {
      expect(text(row)).toContain('Evidence: AUSENTE — no inventar. Refresh to retry resolution.');
      expect(row.querySelector('[data-lin-action="open-task-evidence"]')).toBeNull();
    }
    expect(h.script.calls('ledger_events').map(([, args]) => args)).toEqual([
      { after: 0, limit: 100 }, { after: 100, limit: 100 }, { after: 200, limit: 100 },
    ]);
  });

  it('A17 a later cursor page supplies a task witness without a guessed link', async () => {
    const cells = [result(), result('run_second_0002')]; const script = withCells(cells); const later = script.journal[1];
    script.queue('ledger_events', cursor([script.journal[0]], { next_after: 5, has_more: true }), cursor([later]));
    const h = mount(script); await ready(h);
    expect(action(record(h.host, 'run', cells[1].run_id), 'open-task-evidence').getAttribute('href')).toBe(`#/ledger?event=${encodeURIComponent(later.id)}`);
    expect(script.calls('ledger_events').some(([, args]) => args.after === 5)).toBe(true);
    for (const [, args] of script.calls('ledger_events')) expect(Object.keys(args).every(k => ['after', 'limit', 'wait_ms', 'agent_id', 'kinds', 'agent'].includes(k))).toBe(true);
  });

  it.each(['bench.result', 'run.close', 'run.open'])('A17 evidence fallback prefers %s over lower-priority witnesses', async preferred => {
    const cell = result(); const reply = runReply(cell); const script = withCells([cell]);
    const open = event(3, 'run.open', reply.opened.payload, { agent: cell.agent_id });
    const close = event(4, 'run.close', { record: reply.closed, memory_receipts: [], gate: { passed: true, checks: [{ id: 'memory', passed: true }] } }, { agent: cell.agent_id });
    const measured = event(5, 'bench.result', cell); script.journal = preferred === 'bench.result' ? [open, close, measured] : preferred === 'run.close' ? [open, close] : [open];
    const h = mount(script); await ready(h); const expected = preferred === 'bench.result' ? measured : preferred === 'run.close' ? close : open;
    expect(action(record(h.host, 'run', cell.run_id), 'open-task-evidence').getAttribute('href')).toBe(`#/ledger?event=${encodeURIComponent(expected.id)}`);
  });

  it('A17 missing witness retains the task and exposes absence with retry', async () => {
    const script = withCells(); script.journal = []; const h = mount(script); await ready(h);
    const row = record(h.host, 'run', 'run_alpha_0001'); expect(text(row)).toContain('AUSENTE — no inventar');
    expect(row.querySelector('a[data-lin-action="open-task-evidence"][href]')).toBeNull();
    script.journal = [event(5, 'bench.result', result())]; await click(h.host, 'refresh-benchmark');
    expect(action(record(h.host, 'run', 'run_alpha_0001'), 'open-task-evidence').getAttribute('href')).toBe(`#/ledger?event=${eventId(5)}`);
  });

  it('A17 unrelated run and changed cell payload cannot provide an evidence URL', async () => {
    const script = withCells(); script.journal = [event(5, 'bench.result', result('run_foreign_001')), event(6, 'bench.result', result('run_alpha_0001', { memory_arm: 'none' }))];
    const h = mount(script); await ready(h); const row = record(h.host, 'run', 'run_alpha_0001');
    expect(text(row)).toContain('AUSENTE — no inventar'); expect(row.querySelector('a[data-lin-action="open-task-evidence"][href]')).toBeNull();
  });

  it('A18 pending verdict is unmeasured rather than an invented inconclusive decision', async () => {
    const h = mount(); await ready(h); action(h.host, 'evaluate-benchmark');
    expect(text(h.host)).toMatch(/pending|Not measured|unmeasured/iu); expect(text(h.host)).not.toContain('inconclusive');
    expect(h.script.calls('bench_verdict')).toHaveLength(0);
  });

  it('A18 repeated task cells do not change the exact server verdict or credit', async () => {
    const script = withCells([result(), result('run_repeat_0002', { memory_arm: 'inherited' })]);
    script.benches.set(BENCH, status({ results: [...script.benches.get(BENCH).results], verdict: verdict({ n_discordant: 1 }) }));
    const h = mount(script); await ready(h); action(h.host, 'evaluate-benchmark');
    for (const value of ['not_superior', '-2.125', '-0.25', '0.375']) expect(text(h.host)).toContain(value);
    expect(text(h.host)).not.toMatch(/(?:^|\s)superior(?:[.\s]|$)/u); expect(script.calls('bench_verdict')).toHaveLength(0);
  });

  it('A21 Task results panel errors preserve Rule and Verdict confirmed panels', async () => {
    const script = withCells().queue('run_get', refusal('internal')); const h = mount(script); await ready(h); await reveal(h);
    await click(record(h.host, 'run', 'run_alpha_0001'), 'inspect-bench-result'); const modal = dialog(h.root, 'task result');
    expect(text(modal)).toContain('internal'); await click(modal, 'close-inspector');
    expect(text(h.host)).toContain(HASH); expect(text(h.host)).toContain('Verdict'); action(h.host, 'refresh-benchmark');
  });

  it('A21 Verdict refusal is isolated from usable Rule and actual task cells', async () => {
    const script = withCells().queue('bench_verdict', refusal('busy')); const h = mount(script); await ready(h); await reveal(h);
    await click(h.host, 'evaluate-benchmark'); expect(text(h.root)).toContain('busy'); expect(text(h.host)).toContain(HASH);
    record(h.host, 'run', 'run_alpha_0001'); action(h.host, 'retry-panel', 'Retry Verdict'); noRecorded(h);
  });

  it('A24 fixture provenance is visible and every mutation is disabled', async () => {
    const script = withCells(); script.mode = 'fixture'; const h = mount(script); await ready(h); await reveal(h);
    expect(text(h.root)).toContain('Synthetic fixtures. Changes are unavailable.');
    for (const literal of ['launch-benchmark', 'evaluate-benchmark', 'promote-candidate']) {
      const control = action(h.host, literal) as HTMLButtonElement; expect(control.disabled).toBe(true); control.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    }
    await flush(); expect(script.mutationCalls()).toHaveLength(0);
  });

  it('A24 successful live fake-runner provenance says Synthetic offline benchmark', async () => {
    const script = new Script(); recordLaunch(script); const h = mount(script); await ready(h);
    const modal = await launchForm(h);
    const calls = vi.mocked(script.transport.call).mock.calls;
    const from = calls.length;
    await submit(modal, 'Launch benchmark');
    expect(calls.slice(from, from + 2).map(([tool]) => tool)).toEqual(['bench_run', 'ledger_events']);
    expect(script.calls('bench_run')).toHaveLength(1); expect(text(h.host)).toContain('Synthetic offline benchmark');
    expect(text(h.host)).not.toMatch(/proves.*fitness|memory.*improves|inherited memory.*better/iu);
  });

  it('A24 heldout text comes from the frozen run split and never confirm purpose alone', async () => {
    const cell = result(); const script = withCells(); script.benches.set(BENCH, status({ declaration: declaration({ purpose: 'confirm' }), results: [cell] }));
    script.runs.set(cell.run_id, runReply(cell, 'heldout')); const { h, modal } = await inspect(script);
    expect(text(modal)).toContain('Held out — confirmation only'); await click(modal, 'close-inspector');
    script.runs.set(cell.run_id, runReply(cell, 'select')); await click(record(h.host, 'run', cell.run_id), 'open-bench-run');
    expect(text(dialog(h.root, 'run'))).not.toContain('Held out — confirmation only');
  });

  it('A26 hostile tool-error detail remains inert text and no evidence path is a URL', async () => {
    const hostile = '<img src=x onerror="globalThis.injected=true"><script>globalThis.injected=true</script>';
    const script = withCells().queue('bench_run', refusal('memory_debt', hostile)); const h = mount(script); await ready(h);
    const modal = await launchForm(h); await submit(modal, 'Launch benchmark');
    expect(text(h.root)).toContain(hostile); expect(h.root.querySelector('img,script,iframe')).toBeNull();
    expect((globalThis as any).injected).toBeUndefined(); expect(h.root.querySelector('a[href^="javascript:"],a[href^="https:"],a[href^="evidence/"]')).toBeNull();
    noRecorded(h);
  });

  it.each(['../escape', 'bench_valid_1?event=evil', 'bench_valid_1#foreign', '%2e%2e%2fescape', 'short'])('A26 invalid bench route %s dispatches no read or mutation', async id => {
    const h = mount(new Script(), detailRoute(id)); await h.mounted.ready.catch(() => {}); await flush();
    expect(h.script.calls('bench_status')).toHaveLength(0); expect(h.script.mutationCalls()).toHaveLength(0);
    expect(text(h.host)).toMatch(/invalid|unknown|unavailable/iu);
  });

  it.each(['e-0000000000000005&event=evil', 'javascript:alert(1)', '../e-0000000000000005', 'e-0000000000000005#other'])('A26 invalid event identity %s never becomes a link', async id => {
    const script = withCells(); script.journal = [event(5, 'bench.result', result(), { id })]; const h = mount(script); await ready(h);
    const row = record(h.host, 'run', 'run_alpha_0001'); expect(row.querySelector('a[data-lin-action="open-task-evidence"][href]')).toBeNull();
    expect(text(h.root)).toMatch(/AUSENTE|invalid|unavailable/iu); expect(h.navigate).not.toHaveBeenCalled();
  });

  it.each(['__proto__', 'constructor', 'operator', 'system', 'route', 'extra-argument'])('A11 A26 tampered stored %s cannot be recovered or automatically replayed', async attack => {
    const script = new Script().queue('bench_run', new Error('Lost response')); const h = mount(script); await ready(h); await submit(await launchForm(h), 'Launch benchmark');
    const saved = snapshotStorage(); expect(Object.keys(saved).length).toBeGreaterThan(0);
    const tamper = (value: any): any => {
      if (!value || typeof value !== 'object') return value;
      if (Array.isArray(value)) return value.map(tamper);
      const next = Object.fromEntries(Object.entries(value).map(([k, v]) => [k, tamper(v)]));
      if (attack === '__proto__' || attack === 'constructor') Object.defineProperty(next, attack, { value: { polluted: true }, enumerable: true });
      if (attack === 'operator' || attack === 'system') { if (Object.hasOwn(next, 'actor')) next.actor = attack; if (Object.hasOwn(next, 'agent')) next.agent = attack; }
      if (attack === 'route' && Object.hasOwn(next, 'bench_id')) next.bench_id = 'bench_foreign_001';
      if (attack === 'extra-argument' && Object.hasOwn(next, 'runner')) next.extra = 'forbidden';
      return next;
    };
    const poisoned = Object.fromEntries(Object.entries(saved).map(([k, v]) => [k, JSON.stringify(tamper(JSON.parse(v)))]));
    h.abort.abort(); h.mounted.dispose(); h.root.remove(); restoreStorage(poisoned);
    const later = mount(new Script()); await ready(later); expect(later.script.mutationCalls()).toHaveLength(0);
    await reveal(later); await click(later.host, 'launch-benchmark');
    expect(({} as any).polluted).toBeUndefined(); expect(text(later.root)).toMatch(/invalid|discard|unavailable|not.*recover|unsafe/iu);
    expect(later.script.mutationCalls()).toHaveLength(0);
  });
});

it('A26 schema-valid hostile seat model is displayed as passive rule text', async () => {
  const malicious = '<img src=x onerror="globalThis.injected=true">'; const script = new Script();
  script.benches.set(BENCH, status({ declaration: declaration({ seats: [{ model: malicious, effort: 'medium', mode: 'headless' }] }) }));
  const h = mount(script); await ready(h); await reveal(h); expect(text(h.host)).toContain(malicious);
  expect(h.host.querySelector('img,script')).toBeNull(); expect((globalThis as any).injected).toBeUndefined();
});

it('A26 hostile query is a native input value rather than executable markup', async () => {
  const hostile = '<svg onload="globalThis.injected=true">'; const h = mount(new Script(), listRoute({ q: hostile })); await ready(h);
  expect((action(h.host, 'filter-bench-query') as HTMLInputElement).value).toBe(hostile);
  expect(h.host.querySelector('svg,script')).toBeNull(); expect((globalThis as any).injected).toBeUndefined();
});
