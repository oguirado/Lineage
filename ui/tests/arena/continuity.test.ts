// @vitest-environment jsdom
import { expect, it, vi } from 'vitest';
import { ACTOR, BASELINE, BENCH, CANDIDATE, HASH, Script, action, allActions, click, commit, copy, cursor, declaration, deferred, detailRoute, dialog, edit, event, flush, isolate, key, launchForm, listRoute, mount, nameOf, noRecorded, promoteForm, ready, record, refusal, restoreStorage, result, reveal, runReply, snapshotStorage, status, submit, text } from './helpers.ts';
import { declareForm, recordDeclaration, recordLaunch } from './forms.helpers.ts';
isolate();

it('A02 newer refresh wins when the older same-benchmark reply arrives last', async () => {
  const old = deferred(); const script = new Script(); const h = mount(script); await ready(h);
  script.queue('bench_status', () => old.promise, { bench: status({ state: 'complete', results: [result()], head: 12 }) });
  await click(h.host, 'refresh-benchmark'); await h.update(detailRoute(), 12);
  expect(text(h.host)).toContain('Complete');
  old.resolve({ bench: status({ state: 'running', head: 11 }) }); await flush();
  expect(text(h.host)).toContain('Complete'); record(h.host, 'run', 'run_alpha_0001');
  expect(h.announcements.map(([, m]) => m).at(-1)).not.toMatch(/running/iu);
});

it.each(['extra-status-key', 'unknown-state', 'null-head', 'double-wrapper'])('A02 malformed %s read renders recovery before rejecting readiness', async variant => {
  const s = status(); if (variant === 'extra-status-key') s.synthetic = true;
  if (variant === 'unknown-state') s.state = 'finished'; if (variant === 'null-head') s.head = null;
  const reply = variant === 'double-wrapper' ? { untrusted: { bench: s } } : { bench: s };
  const h = mount(new Script().queue('bench_status', reply));
  await expect(h.mounted.ready).rejects.toBeDefined(); action(h.host, 'retry-panel', 'Retry Rule');
  expect(text(h.host)).toContain('Rule unavailable. Retry to continue.');
});

it('A02 A21 initial list failure shows Benchmarks recovery rather than false emptiness', async () => {
  const h = mount(new Script().queue('bench_list', refusal('internal')), listRoute());
  await expect(h.mounted.ready).rejects.toBeDefined(); expect(text(h.host)).toContain('Benchmarks unavailable. Retry to continue.');
  action(h.host, 'retry-panel', 'Retry Benchmarks'); expect(text(h.host)).not.toContain('No benchmarks yet.');
});

it('A03 pending lexical page cannot be submitted twice and repeated cursor cannot loop', async () => {
  const waiting = deferred(); const script = new Script().queue('bench_list', { benches: [status()], next_after: BENCH, head: 10 }, () => waiting.promise);
  const h = mount(script, listRoute()); await ready(h); const next = await click(h.host, 'page-benches');
  next.dispatchEvent(new MouseEvent('click', { bubbles: true })); await flush(); expect(script.calls('bench_list')).toHaveLength(2);
  waiting.resolve({ benches: [], next_after: BENCH, head: 10 }); await flush();
  expect(text(h.host)).toMatch(/cursor|unavailable|invalid/iu); expect(script.calls('bench_list')).toHaveLength(2);
});

it('A06 an explicitly entered participant absent from loaded choices is checked with agent_get', async () => {
  const script = new Script(); const extra = { ...copy(script.agents.get(CANDIDATE)), agent_id: 'manual-candidate' };
  script.queue('agent_list', { agents: [...script.agents.values()].map(copy), next_after: null, head: 10 }); script.agents.set(extra.agent_id, extra); recordDeclaration(script);
  const h = mount(script, listRoute()); await ready(h); const modal = await declareForm(h);
  await click(modal, 'select-bench-agent', `Benchmark agent ${key('agent', CANDIDATE)}`);
  edit(modal, 'agents.new', extra.agent_id); await click(modal, 'add-item', 'Add agents'); await submit(modal, 'Declare benchmark');
  expect(script.calls('agent_get').some(([, args]) => args.agent_id === extra.agent_id)).toBe(true);
  expect(script.calls('bench_declare')[0][1].declaration.agents).toEqual([BASELINE, extra.agent_id]);
});

it('A06 repeated memory-arm entry cannot create duplicate declared arms', async () => {
  const h = mount(new Script(), listRoute()); await ready(h); const modal = await declareForm(h);
  const editor = [...modal.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-lin-action="edit-field"][name]')].find(el => /^(?:declaration\.)?memory(?:_| )arms\.new$/u.test(el.name));
  if (editor) {
    edit(modal, editor.name, 'own'); await click(modal, 'add-item', 'Add memory arms'); expect(text(modal)).toMatch(/duplicate|already|unique/iu);
  } else {
    const arm = [...modal.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')].find(el => el.value === 'own' && el.name.includes('memory'));
    expect(arm).toBeDefined(); expect(arm!.checked).toBe(true); arm!.dispatchEvent(new Event('change', { bubbles: true }));
  }
  await submit(modal, 'Declare benchmark');
  for (const [, args] of h.script.calls('bench_declare')) expect(new Set(args.declaration.memory_arms).size).toBe(args.declaration.memory_arms.length);
});

it('A09 fixture list Declare cannot dispatch even through programmatic activation', async () => {
  const script = new Script('fixture'); const h = mount(script, listRoute()); await ready(h);
  const control = action(h.host, 'declare-benchmark') as HTMLButtonElement; expect(control.disabled).toBe(true);
  control.dispatchEvent(new MouseEvent('click', { bubbles: true })); await flush(); expect(script.mutationCalls()).toHaveLength(0);
  expect(text(h.host)).toContain('Synthetic fixtures. Changes are unavailable.');
});

it('A11 a lost already-committed launch replays its exact operation without duplicate journal events', async () => {
  const script = new Script(); recordLaunch(script); const record = script.queues.get('bench_run')!.shift() as Function;
  let recorded: any, original: any;
  script.queue('bench_run', async (args: any) => { original = copy(args); recorded = await record(args); throw new Error('Committed reply lost'); },
    (args: any) => { expect(args).toEqual(original); return copy(recorded); });
  script.queue('ledger_events', refusal('busy'));
  const h = mount(script); await ready(h); const modal = await launchForm(h); await submit(modal, 'Launch benchmark');
  expect(script.journal).toHaveLength(3); const ids = script.journal.map(e => e.id); noRecorded(h);
  await submit(dialog(h.root, 'Launch benchmark'), 'Launch benchmark');
  expect(script.journal.map(e => e.id)).toEqual(ids); expect(script.calls('bench_run')).toHaveLength(2);
  expect(h.announcements.some(([, m]) => m === `Launch benchmark recorded for ${key('bench', BENCH)}.`)).toBe(true);
});

it.each(['Declare benchmark', 'Promote agent'])('A11 %s draft reload uses explicit existing controls and preserves exact pending tuple', async label => {
  const tool = label === 'Declare benchmark' ? 'bench_declare' : 'agent_promote';
  const script = new Script().queue(tool, new Error('Lost response')); const selected = label === 'Declare benchmark' ? listRoute() : detailRoute();
  const h = mount(script, selected); await ready(h); const modal = label === 'Declare benchmark' ? await declareForm(h) : await promoteForm(h);
  await submit(modal, label); const original = copy(script.calls(tool)[0][1]); const saved = snapshotStorage(); expect(JSON.stringify(saved)).toContain(original.op_id);
  h.abort.abort(); h.mounted.dispose(); h.root.remove(); restoreStorage(saved);
  const later = mount(new Script().queue(tool, refusal('conflict')), selected); await ready(later); expect(later.script.mutationCalls()).toHaveLength(0);
  await click(later.host, label === 'Declare benchmark' ? 'declare-benchmark' : 'promote-candidate'); await submit(dialog(later.root, label), label);
  expect(later.script.calls(tool)[0][1]).toEqual(original);
});

it('A11 recovered pending evaluate stays inert until explicit Evaluate retry', async () => {
  const script = new Script().queue('bench_verdict', new Error('Lost response')); const h = mount(script); await ready(h); await click(h.host, 'evaluate-benchmark');
  const original = copy(script.calls('bench_verdict')[0][1]); const saved = snapshotStorage();
  h.abort.abort(); h.mounted.dispose(); h.root.remove(); restoreStorage(saved);
  const later = mount(new Script().queue('bench_verdict', refusal('conflict'))); await ready(later); expect(later.script.mutationCalls()).toHaveLength(0);
  await click(later.host, 'evaluate-benchmark'); expect(later.script.calls('bench_verdict')[0][1]).toEqual(original);
});

it('A11 persisted drafts omit response projections tokens and memory bodies', async () => {
  const script = new Script().queue('bench_run', new Error('Lost response')); const h = mount(script); await ready(h); await submit(await launchForm(h), 'Launch benchmark');
  const saved = snapshotStorage(); expect(Object.keys(saved).length).toBeGreaterThan(0);
  const forbidden = new Set(['token', 'sessionToken', 'session_token', 'results', 'record', 'memory', 'payload', 'closed', 'opened', '__proto__', 'constructor', 'prototype']);
  const visit = (value: any): void => {
    if (!value || typeof value !== 'object') return;
    for (const [name, child] of Object.entries(value)) { expect(forbidden.has(name), `Unsafe stored ${name}`).toBe(false); visit(child); }
  };
  for (const value of Object.values(saved)) visit(JSON.parse(value));
  expect(Object.entries(saved).some(([key, value]) => /v[0-9]|version|schema/iu.test(key + value))).toBe(true);
});

it('A12 compound commit with a changed task payload cannot certify launch', async () => {
  const script = new Script(); recordLaunch(script); const build = script.queues.get('bench_run')!.shift() as Function;
  script.queue('bench_run', async (args: any) => {
    const reply = await build(args); script.journal.at(-1)!.payload = { ...script.journal.at(-1)!.payload, memory_arm: 'none' }; return reply;
  });
  const h = mount(script); await ready(h); await submit(await launchForm(h), 'Launch benchmark'); noRecorded(h);
  expect(text(h.root)).toMatch(/uncertain|not confirmed|witness|evidence/iu);
});

it('A14 failed backend task stays inspectable with its actual failure-memory closing gate', async () => {
  const script = new Script().queue('bench_run', () => {
    const cell = result(); script.benches.set(BENCH, status({ state: 'stalled', results: [cell] }));
    script.runs.set(cell.run_id, runReply(cell)); script.journal = [event(5, 'bench.result', cell)]; throw refusal('timeout');
  });
  const h = mount(script); await ready(h); const modal = await launchForm(h); await submit(modal, 'Launch benchmark');
  expect(text(modal)).toContain('timeout'); await click(modal, 'cancel-dialog', 'Cancel Launch benchmark'); await click(h.host, 'refresh-benchmark');
  await click(record(h.host, 'run', 'run_alpha_0001'), 'open-bench-run'); const run = dialog(h.root, 'run');
  expect(text(run)).toContain('error'); expect(text(run)).toMatch(/gate.*pass|pass.*gate/iu); expect(script.mutationCalls()).toHaveLength(1);
});

it('A17 stale benchmark read retains the failed task existing witness URL', async () => {
  const script = new Script(); const cell = result(); script.benches.set(BENCH, status({ results: [cell] })); script.journal = [event(5, 'bench.result', cell)];
  const h = mount(script); await ready(h); const href = action(record(h.host, 'run', cell.run_id), 'open-task-evidence').getAttribute('href');
  script.queue('bench_status', refusal('internal')); await click(h.host, 'refresh-benchmark');
  expect(action(record(h.host, 'run', cell.run_id), 'open-task-evidence').getAttribute('href')).toBe(href); expect(text(h.host)).toContain('Data is stale.');
});

it.each(['Declare benchmark', 'Promote agent'])('A22 %s native modal is keyboard-contained and Escape restores its invoker', async label => {
  const h = mount(new Script(), label === 'Declare benchmark' ? listRoute() : detailRoute()); await ready(h);
  const literal = label === 'Declare benchmark' ? 'declare-benchmark' : 'promote-candidate'; const invoker = await click(h.host, literal);
  const modal = dialog(h.root, label); expect(modal.contains(document.activeElement)).toBe(true);
  const controls = allActions(modal).filter(el => !(el as HTMLInputElement).disabled); controls[0].focus();
  controls[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true }));
  expect(modal.contains(document.activeElement)).toBe(true); expect(document.activeElement).toBe(controls.at(-1));
  modal.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })); await flush();
  expect(h.root.querySelector('dialog,[role="dialog"]')).toBeNull(); expect(document.activeElement).toBe(invoker); expect(h.script.mutationCalls()).toHaveLength(0);
});
