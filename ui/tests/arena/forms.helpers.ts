import { expect } from 'vitest';
import type { Harness } from './helpers.ts';
import { ACTOR, BASELINE, BENCH, CANDIDATE, SEAT, Script, action, allActions, click, commit, copy, declaration, dialog, edit, event, flush, key, nameOf, status, text } from './helpers.ts';

export function setActor(h: Harness, actor: string, disabled = false): void {
  const option = document.createElement('option'); option.value = actor; option.textContent = actor;
  h.actor.replaceChildren(option); h.actor.value = actor; h.actor.disabled = disabled;
  h.actor.dispatchEvent(new Event('change', { bubbles: true }));
}
export async function declareForm(h: Harness, draft = declaration()): Promise<HTMLElement> {
  await click(h.host, 'declare-benchmark'); const modal = dialog(h.root, 'Declare benchmark');
  for (const [path, value] of Object.entries({
    'declaration.bench_id': draft.bench_id, 'declaration.bank_id': draft.bank_id, 'declaration.bank_sha256': draft.bank_sha256,
    'declaration.protocol': draft.protocol, 'declaration.purpose': draft.purpose,
    'declaration.credit_rule.minimum_gain': draft.credit_rule.minimum_gain,
    'declaration.credit_rule.cost_tiebreaker': draft.credit_rule.cost_tiebreaker,
    'declaration.sprt.p0': draft.sprt.p0, 'declaration.sprt.p1': draft.sprt.p1,
    'declaration.sprt.alpha': draft.sprt.alpha, 'declaration.sprt.beta': draft.sprt.beta,
    'declaration.sprt.cap': draft.sprt.cap, 'declaration.promotion.n_shadow_runs': draft.promotion.n_shadow_runs,
  })) edit(modal, path, value as string | boolean);
  // Click full-ID participant choices in baseline/candidate order; no positional selector.
  for (const checkbox of allActions(modal).filter(el => el.dataset.linAction === 'select-bench-agent')) {
    if ((checkbox as HTMLInputElement).checked) checkbox.click();
  }
  for (const id of draft.agents) await click(modal, 'select-bench-agent', `Benchmark agent ${key('agent', id)}`);
  const seatChoices = allActions(modal).filter(el => el.dataset.linAction === 'select-seat');
  for (const input of seatChoices) if ((input as HTMLInputElement).checked) input.click();
  for (const seat of draft.seats) {
    const matches = seatChoices.filter(el => {
      const description = (el.getAttribute('aria-describedby') ?? '').split(/\s+/u).map(id => document.getElementById(id)?.textContent ?? '').join(' ');
      return Object.values(seat).every(value => description.includes(String(value)));
    });
    expect(matches, 'Seat choices describe each full tuple').toHaveLength(1); matches[0].click();
  }
  // Accept native enumerated choices or the registered Add/Remove collection editor.
  const armInputs = [...modal.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')].filter(el =>
    el.name === 'declaration.memory_arms' || /^(?:declaration\.)?memory(?:_| )arms\./u.test(el.name));
  if (armInputs.length) {
    for (const field of armInputs) {
      field.checked = draft.memory_arms.includes(field.value); field.dispatchEvent(new Event('change', { bubbles: true }));
    }
  } else {
    const removals = allActions(modal).filter(el => el.dataset.linAction === 'remove-item' && nameOf(el).startsWith('Remove memory arms '));
    for (const removal of removals) removal.click();
    for (const arm of draft.memory_arms) {
      const editor = [...modal.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-lin-action="edit-field"][name]')].find(el => /^(?:declaration\.)?memory(?:_| )arms\.new$/u.test(el.name));
      expect(editor, 'Registered memory arms.new editor').toBeDefined(); edit(modal, editor!.name, arm);
      await click(modal, 'add-item', 'Add memory arms');
    }
  }
  await flush();
  expect(text(modal)).toMatch(/Baseline.*baseline-agent.*Candidate.*candidate-agent/u);
  return modal;
}
export function recordDeclaration(script: Script): void {
  script.queue('bench_declare', (args: any) => {
    const s = status({ declaration: copy(args.declaration), head: 11 });
    const witness = event(11, 'bench.declared', args.declaration, { agent: args.agent, op_id: args.op_id });
    script.journal.push(witness); script.head = 11; script.benches.set(args.declaration.bench_id, s);
    return { bench: s, commit: commit([witness]) };
  });
}
export function recordLaunch(script: Script, patch: Record<string, any> = {}): void {
  script.queue('bench_run', (args: any) => {
    const cell = { bench_id: args.bench_id, task_id: 'task_launch_0001', agent_id: CANDIDATE, seat: copy(SEAT), memory_arm: 'own',
      run_id: 'run_launch_0001', verdict: 'green', correctness: 1,
      cost: { tokens_in: null, tokens_out: null, tokens_cache: null, duration_ms: null, cost_micro_usd: null } };
    const frozen = { run_id: cell.run_id, agent_id: cell.agent_id, agent_version: 'b'.repeat(64), seat: cell.seat,
      task: { id: cell.task_id, kind: 'scripted', language: 'general', bank_id: 'scripted-bank', bench_id: args.bench_id, split: 'select' }, parents_context: [], memory_arm: 'own' };
    const opened = event(11, 'run.open', frozen, { agent: CANDIDATE, op_id: 'backend-owned-open' });
    const done = { schema: 'lineage.run/v1', ...frozen, ts_open: 1_800_000_000_011, ts_close: 1_800_000_000_012,
      outcome: { verdict: 'green', repair_loops: 0, findings: { confirmed: 0, refuted: 0 } }, cost: cell.cost,
      memory: { unit_ids: ['memory_episode_001'], levels: [3], gate_passed: true }, evidence: [] };
    const closed = event(12, 'run.close', { record: done, memory_receipts: [], gate: { passed: true, checks: [{ id: 'memory', passed: true }] } },
      { agent: CANDIDATE, op_id: 'backend-owned-close' });
    const measured = event(13, 'bench.result', cell, { agent: ACTOR, op_id: 'backend-owned-result' });
    script.journal.push(opened, closed, measured); script.head = 13;
    script.runs.set(cell.run_id, { opened, closed: done, head: 13 });
    const s = status({ declaration: declaration({ bench_id: args.bench_id }), results: [cell], state: 'running', head: 13, ...patch });
    script.benches.set(args.bench_id, s);
    return { bench: s, commit: commit([opened, closed, measured]) };
  });
}
