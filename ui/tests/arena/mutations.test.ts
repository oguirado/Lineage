// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { createHttpTransport } from '../../src/transport.ts';
import { ACTOR, BASELINE, BENCH, CANDIDATE, HASH, OTHER, Script, action, allActions, assertCall, click, commit, copy, declaration, deferred, detailRoute, dialog, edit, event, flush, isolate, key, launchForm, listRoute, mount, nameOf, noRecorded, promoteForm, ready, refusal, restoreStorage, reveal, snapshotStorage, status, submit, text, verdict } from './helpers.ts';
import { declareForm, recordDeclaration, recordLaunch, setActor } from './forms.helpers.ts';
isolate();

describe('U25 closed forms and protected mutations', () => {
  it('A06 all typed declaration leaves serialize exact closed arguments and explicit roles', async () => {
    const script = new Script(); recordDeclaration(script); const h = mount(script, listRoute()); await ready(h);
    const modal = await declareForm(h);
    expect(text(modal)).toContain('lineage.bench.declared/v1'); expect(text(modal)).toContain('correctness_first'); expect(text(modal)).toContain('population_stddev');
    expect(modal.querySelector('textarea')).toBeNull();
    const names = allActions(modal).map(nameOf);
    expect(new Set(names).size).toBe(names.length);
    for (const name of names) expect(Buffer.byteLength(name.normalize('NFC').replace(/\s+/gu, ' '))).toBeLessThanOrEqual(64);
    for (const field of modal.querySelectorAll('[data-lin-action="edit-field"]')) expect(['INPUT', 'SELECT']).toContain(field.tagName);
    await submit(modal, 'Declare benchmark');
    const args = assertCall(h, 'bench_declare', { declaration: declaration(), agent: ACTOR, expected_head: 10 });
    expect(args.declaration.agents).toEqual([BASELINE, CANDIDATE]);
    expect(script.calls('ledger_events').length).toBeGreaterThan(0);
    expect(h.announcements.some(([, m]) => m === `Declare benchmark recorded for ${key('bench', BENCH)}.`)).toBe(true);
  });

  it.each([
    ['declaration.bench_id', '../bad-id'], ['declaration.bank_id', 'Invalid!'], ['declaration.bank_sha256', 'A'.repeat(64)],
    ['declaration.bank_sha256', 'abc'], ['declaration.sprt.p0', '0'], ['declaration.sprt.p0', '1'],
    ['declaration.sprt.p1', '0.2'], ['declaration.sprt.alpha', 'NaN'], ['declaration.sprt.beta', 'Infinity'],
    ['declaration.sprt.cap', '1.5'], ['declaration.sprt.cap', '1000001'], ['declaration.sprt.cap', '9007199254740992'],
    ['declaration.promotion.n_shadow_runs', '0'], ['declaration.credit_rule.minimum_gain', '-0.1'], ['declaration.credit_rule.minimum_gain', '1.1'],
  ])('A06 malformed %s=%s is refused before dispatch with field focus', async (path, value) => {
    const h = mount(new Script(), listRoute()); await ready(h); const modal = await declareForm(h); const field = edit(modal, path, value);
    await submit(modal, 'Declare benchmark');
    expect(h.script.calls('bench_declare')).toHaveLength(0); expect(document.activeElement).toBe(field);
    expect(field.getAttribute('aria-invalid')).toBe('true');
    const description = [field.getAttribute('aria-describedby'), field.getAttribute('aria-errormessage')].filter(Boolean).join(' ');
    expect(description.length).toBeGreaterThan(0); expect(text(modal)).toMatch(/invalid|required|between|probability|hash|integer|greater/iu); noRecorded(h);
  });

  it('A06 natural-key agent collection rejects a duplicate without swapping roles', async () => {
    const h = mount(new Script(), listRoute()); await ready(h); const modal = await declareForm(h);
    edit(modal, 'agents.new', BASELINE); await click(modal, 'add-item', 'Add agents');
    expect(text(modal)).toMatch(/duplicate|distinct|already/iu); expect(text(modal)).toMatch(/Baseline.*baseline-agent.*Candidate.*candidate-agent/u);
    expect(allActions(modal).filter(el => nameOf(el) === `Benchmark agent ${key('agent', BASELINE)}`)).toHaveLength(1);
    expect(h.script.calls('bench_declare')).toHaveLength(0);
  });

  it('A06 natural-key seat collection rejects repeated complete tuples', async () => {
    const h = mount(new Script(), listRoute()); await ready(h); const modal = await declareForm(h);
    edit(modal, 'seats.new.model', 'test-model'); edit(modal, 'seats.new.effort', 'medium'); edit(modal, 'seats.new.mode', 'headless');
    await click(modal, 'add-item', 'Add seats'); expect(text(modal)).toMatch(/duplicate|unique|already/iu);
    expect(h.script.calls('bench_declare')).toHaveLength(0);
  });

  it.each(['heldout_forbidden', 'hash_mismatch'])('A07 %s preserves explicit bank purpose and credit draft', async code => {
    const script = new Script().queue('bench_declare', refusal(code)); const h = mount(script, listRoute()); await ready(h);
    const modal = await declareForm(h); await submit(modal, 'Declare benchmark');
    expect(text(modal)).toContain(code); expect((modal.querySelector('[name="declaration.bank_sha256"]') as HTMLInputElement).value).toBe(HASH);
    expect((modal.querySelector('[name="declaration.purpose"]') as HTMLSelectElement).value).toBe('select');
    expect(script.calls('bench_declare')[0][1].declaration.credit_rule).toEqual(declaration().credit_rule);
    expect(script.calls('bench_declare')[0][1].declaration.memory_arms).toEqual(['own', 'inherited']);
    expect(script.calls('bench_declare')[0][1].declaration.purpose).toBe('select'); noRecorded(h);
    expect(h.announcements.filter(([, m]) => m === `Declare benchmark refused: ${code}.`)).toHaveLength(1);
  });

  it('A07 existing declaration is read-only and discloses bank credit SPRT and memory meaning', async () => {
    const h = mount(); await ready(h); await reveal(h); const content = text(h.host);
    for (const value of ['scripted-bank', HASH, 'select', 'correctness_first', 'population_stddev', '0.125', '0.3', '0.7', '0.05', '0.1', '12', 'none', 'own', 'inherited']) expect(content).toContain(value);
    expect(content).toMatch(/confirm|confirmation/iu); expect(content).toMatch(/cost/iu);
    expect(h.host.querySelector('[name^="declaration."]')).toBeNull(); expect(h.script.mutationCalls()).toHaveLength(0);
  });

  it.each(['operator', 'system', 'Invalid actor', 'ab', '../actor', 'x'.repeat(65)])('A09 reserved or malformed actor %s cannot mutate', async id => {
    const h = mount(); setActor(h, id); await ready(h); await reveal(h);
    for (const literal of ['launch-benchmark', 'evaluate-benchmark', 'promote-candidate']) {
      const control = action(h.host, literal) as HTMLButtonElement; expect(control.disabled).toBe(true);
      control.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    }
    await flush(); expect(h.script.mutationCalls()).toHaveLength(0); expect(text(h.host)).toMatch(/actor|Acting agent/iu);
  });

  it.each(['missing', 'disabled', 'unknown-head', 'missing-tools', 'fixture'])('A09 %s precondition blocks all programmatic mutation attempts', async variant => {
    const script = new Script(variant === 'fixture' ? 'fixture' : 'live'); const h = mount(script);
    if (variant === 'missing') h.actor.remove(); if (variant === 'disabled') h.actor.disabled = true;
    if (variant === 'unknown-head') h.state = { ...h.state, head: null };
    if (variant === 'missing-tools') h.state = { ...h.state, tools: h.state.tools.filter(t => !['bench_run', 'bench_verdict', 'agent_promote'].includes(t.name)) };
    await ready(h); await reveal(h);
    for (const literal of ['launch-benchmark', 'evaluate-benchmark', 'promote-candidate']) {
      const control = action(h.host, literal) as HTMLButtonElement; expect(control.disabled).toBe(true);
      control.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    }
    await flush(); expect(script.mutationCalls()).toHaveLength(0);
  });

  it('A09 the actual shell disabled actor placeholder is an integration blocker', async () => {
    const script = new Script(); const h = mount(script); h.actor.disabled = true; await ready(h); await reveal(h);
    expect((action(h.host, 'launch-benchmark') as HTMLButtonElement).disabled).toBe(true);
    expect(text(h.host)).toMatch(/actor|Acting agent/iu); expect(script.calls('bench_run')).toHaveLength(0);
  });

  it('A10 A14 fake Launch uses shared transport exact args and dialog-open expected head', async () => {
    const script = new Script(); recordLaunch(script); const h = mount(script); await ready(h); const modal = await launchForm(h, '4294967295');
    expect(nameOf(modal)).toBe(`Launch benchmark ${key('bench', BENCH)}`); expect(text(modal)).toContain(HASH);
    h.emit({ head: 19 }); await submit(modal, 'Launch benchmark');
    assertCall(h, 'bench_run', { bench_id: BENCH, runner: { kind: 'fake', seed: 4294967295 }, agent: ACTOR, expected_head: 10 });
    expect(script.calls('ledger_events').length).toBeGreaterThan(0); expect(script.calls('bench_status').length).toBeGreaterThan(1);
    expect(text(h.host)).toContain('Running'); expect(text(h.host)).not.toContain('Complete');
    expect(script.mutationCalls().every(([tool]) => tool === 'bench_run')).toBe(true);
  });

  it('A10 semantic refusal through actual shared HTTP transport is never success', async () => {
    const script = new Script(); const h = mount(script); await ready(h); await reveal(h);
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body));
      const wire = body.tool === 'bench_run' ? { ok: false, code: 'memory_debt', detail: '<img src=x onerror=alert(1)>' } : { untrusted: await script.dispatch(body.tool, body.args, { mutation: false }) };
      return { ok: true, status: 200, redirected: false, headers: new Headers({ 'content-type': 'application/json' }), json: async () => wire } as Response;
    });
    const transport = createHttpTransport({ fetchImpl: fetchImpl as typeof fetch, sessionToken: 'synthetic-test-token', timeoutMs: 1000 });
    h.context = { ...h.context, transport }; await h.mounted.update(h.context); await flush();
    const modal = await launchForm(h); await submit(modal, 'Launch benchmark');
    expect(text(h.root)).toContain('memory_debt'); expect(h.root.querySelector('img')).toBeNull(); noRecorded(h);
    const request = fetchImpl.mock.calls.find(([, init]) => JSON.parse(String(init?.body)).tool === 'bench_run'); expect(request).toBeDefined();
    const headers = new Headers(request![1]?.headers); expect(headers.get('X-Lineage-Session')).toBe('synthetic-test-token');
    expect(JSON.stringify(snapshotStorage())).not.toContain('synthetic-test-token');
  });

  it('A11 pending submission blocks duplicate calls and exact retry retains operation identity', async () => {
    const lost = deferred(); const script = new Script().queue('bench_run', () => lost.promise, refusal('conflict'));
    const h = mount(script); await ready(h); const modal = await launchForm(h);
    await submit(modal, 'Launch benchmark'); await submit(modal, 'Launch benchmark'); expect(script.calls('bench_run')).toHaveLength(1);
    lost.reject(new Error('Response lost')); await flush(); expect(text(h.root)).toMatch(/uncertain|not confirmed|unknown/iu); noRecorded(h);
    await submit(dialog(h.root, 'Launch benchmark'), 'Launch benchmark');
    expect(script.calls('bench_run')).toHaveLength(2); expect(script.calls('bench_run')[1][1]).toEqual(script.calls('bench_run')[0][1]);
  });

  it('A11 editing or changing actor after uncertain submission starts a new operation', async () => {
    const script = new Script().queue('bench_run', new Error('Lost response'), refusal('conflict'));
    const h = mount(script); await ready(h); const modal = await launchForm(h); await submit(modal, 'Launch benchmark');
    const original = copy(script.calls('bench_run')[0][1]); setActor(h, 'other-actor'); edit(modal, 'runner.seed', '18');
    await submit(modal, 'Launch benchmark'); const later = script.calls('bench_run')[1][1];
    expect(later.op_id).not.toBe(original.op_id); expect(later.agent).toBe('other-actor'); expect(later.runner).toEqual({ kind: 'fake', seed: 18 });
    expect(text(h.root)).toMatch(/uncertain|previous|prior/iu);
  });

  it('A11 reload never auto-submits and explicit Launch recovery reuses the saved safe tuple', async () => {
    const script = new Script().queue('bench_run', new Error('Lost response')); const h = mount(script); await ready(h);
    await submit(await launchForm(h), 'Launch benchmark'); const original = copy(script.calls('bench_run')[0][1]); const saved = snapshotStorage();
    expect(Object.keys(saved).length).toBeGreaterThan(0); expect(JSON.stringify(saved)).toContain(original.op_id);
    h.abort.abort(); h.mounted.dispose(); h.root.remove(); restoreStorage(saved);
    const laterScript = new Script().queue('bench_run', refusal('conflict')); const later = mount(laterScript); await ready(later);
    expect(laterScript.mutationCalls()).toHaveLength(0); expect(text(later.root)).toMatch(/draft|recover|pending/iu);
    await reveal(later); await click(later.host, 'launch-benchmark');
    const modal = dialog(later.root, 'Launch benchmark'); expect((modal.querySelector('[name="runner.seed"]') as HTMLInputElement).value).toBe('17');
    await submit(modal, 'Launch benchmark'); expect(laterScript.calls('bench_run')[0][1]).toEqual(original);
  });

  it('A11 cancellation declines recovery without resubmission and keeps safe draft', async () => {
    const h = mount(); await ready(h); const modal = await launchForm(h, '23');
    await click(modal, 'cancel-dialog', 'Cancel Launch benchmark'); expect(h.script.mutationCalls()).toHaveLength(0);
    await click(h.host, 'launch-benchmark'); expect((dialog(h.root, 'Launch benchmark').querySelector('[name="runner.seed"]') as HTMLInputElement).value).toBe('23');
    for (const control of allActions(h.root)) expect(control.dataset.linAction).not.toMatch(/recover|discard|retry-operation/u);
  });

  it('A11 denied storage is visible and does not prevent an honest uncertain state', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Denied', 'SecurityError'); });
    const script = new Script().queue('bench_run', new Error('Lost response')); const h = mount(script); await ready(h);
    await submit(await launchForm(h), 'Launch benchmark');
    expect(script.calls('bench_run')).toHaveLength(1); expect(text(h.root)).toMatch(/storage|draft.*unavailable|could not.*save/iu); noRecorded(h);
  });

  it('A12 commit witness past the first cursor page is required before recorded completion', async () => {
    const script = new Script(); recordDeclaration(script); const later = deferred();
    script.queue('ledger_events', { events: [], next_after: 10, head: 11, has_more: true, resync: false }, () => later.promise);
    const h = mount(script, listRoute()); await ready(h); const modal = await declareForm(h); await submit(modal, 'Declare benchmark'); noRecorded(h);
    expect(script.calls('ledger_events').length).toBeGreaterThanOrEqual(2);
    const witness = script.journal[0]; later.resolve({ events: [witness], next_after: 11, head: 11, has_more: false, resync: false }); await flush();
    expect(script.calls('ledger_events')[1][1].after).toBe(10);
    expect(h.announcements.some(([, m]) => m === `Declare benchmark recorded for ${key('bench', BENCH)}.`)).toBe(true);
  });

  it.each(['absent', 'wrong-id', 'wrong-actor', 'wrong-operation', 'changed-payload'])('A12 %s single-event witness cannot certify declaration', async variant => {
    const script = new Script(); script.queue('bench_declare', (args: any) => {
      const genuine = event(11, 'bench.declared', args.declaration, { agent: args.agent, op_id: args.op_id }); const forged = copy(genuine);
      if (variant === 'wrong-id') forged.id = 'e-000000000000ffff'; if (variant === 'wrong-actor') forged.agent = 'other-actor';
      if (variant === 'wrong-operation') forged.op_id = 'other-operation'; if (variant === 'changed-payload') forged.payload = declaration({ bank_sha256: 'c'.repeat(64) });
      script.journal = variant === 'absent' ? [] : [forged]; script.head = 11;
      return { bench: status({ head: 11 }), commit: commit([genuine]) };
    });
    const h = mount(script, listRoute()); await ready(h); await submit(await declareForm(h), 'Declare benchmark');
    expect(script.calls('bench_declare')).toHaveLength(1); noRecorded(h); expect(text(h.root)).toMatch(/uncertain|not confirmed|witness|evidence/iu);
  });

  it('A12 compound launch verifies commit event IDs and payloads without guessing child op_ids', async () => {
    const script = new Script(); recordLaunch(script); const h = mount(script); await ready(h); await submit(await launchForm(h), 'Launch benchmark');
    const args = script.calls('bench_run')[0][1]; expect(script.journal.every(e => e.op_id !== args.op_id)).toBe(true);
    expect(script.calls('ledger_events').length).toBeGreaterThan(0);
    expect(h.announcements.some(([, m]) => m === `Launch benchmark recorded for ${key('bench', BENCH)}.`)).toBe(true);
    expect(text(h.host)).toContain('run_launch_0001');
  });

  it.each(['busy', 'stale_rev', 'memory_required', 'memory_debt', 'timeout'])('A13 A14 backend %s remains visible with no invented success', async code => {
    const script = new Script().queue('bench_run', refusal(code)); const h = mount(script); await ready(h); const modal = await launchForm(h);
    await submit(modal, 'Launch benchmark'); expect(text(h.root)).toContain(code); noRecorded(h);
    expect((modal.querySelector('[name="runner.seed"]') as HTMLInputElement).value).toBe('17');
    expect(script.mutationCalls().map(([tool]) => tool)).toEqual(['bench_run']); expect(script.calls('run_close')).toHaveLength(0);
  });

  it('A13 ledger resync makes acknowledged launch uncertain with named recovery', async () => {
    const script = new Script(); recordLaunch(script); const h = mount(script); await ready(h); const modal = await launchForm(h);
    script.queue('ledger_events', { events: [], next_after: 0, head: 13, has_more: false, resync: true });
    await submit(modal, 'Launch benchmark'); noRecorded(h); expect(text(h.root)).toMatch(/uncertain|resync|not confirmed/iu);
    expect(allActions(h.root).some(el => ['submit-dialog', 'retry-panel', 'refresh-benchmark'].includes(el.dataset.linAction!))).toBe(true);
  });

  it.each(['-1', '4294967296', '1.5', 'Infinity', ''])('A14 invalid fake seed %s submits nothing', async seed => {
    const h = mount(); await ready(h); const modal = await launchForm(h); const field = edit(modal, 'runner.seed', seed);
    await submit(modal, 'Launch benchmark'); expect(h.script.calls('bench_run')).toHaveLength(0); expect(document.activeElement).toBe(field);
  });

  it('A14 command runner is visibly unavailable and cannot submit browser shell text', async () => {
    const h = mount(); await ready(h); const modal = await launchForm(h); edit(modal, 'runner.kind', 'command');
    await submit(modal, 'Launch benchmark'); expect(h.script.calls('bench_run')).toHaveLength(0);
    expect(text(modal)).toMatch(/headless|unavailable|unsupported/iu); expect(modal.querySelector('[name*="argv"]')).toBeNull();
  });

  it('A18 evaluate displays server numbers exactly and verifies bench.verdict', async () => {
    const script = new Script(); script.queue('bench_verdict', (args: any) => {
      const v = verdict(); const e = event(11, 'bench.verdict', v, { op_id: args.op_id, agent: args.agent });
      script.journal.push(e); script.head = 11; script.benches.set(BENCH, status({ verdict: v, state: 'complete', head: 11 }));
      return { verdict: v, commit: commit([e]) };
    });
    const h = mount(script); await ready(h); await click(h.host, 'evaluate-benchmark');
    assertCall(h, 'bench_verdict', { bench_id: BENCH, agent: ACTOR, expected_head: 10 });
    const content = text(h.host); for (const value of ['not_superior', '-2.125', '3', '-0.25', '0.375', '-1']) expect(content).toContain(value);
    expect(script.calls('ledger_events').length).toBeGreaterThan(0); expect(h.announcements.some(([, m]) => m.includes('Evaluate benchmark recorded'))).toBe(true);
  });

  it('A11 A18 evaluate response loss is recoverable with its exact retained operation', async () => {
    const script = new Script().queue('bench_verdict', new Error('Lost reply'), refusal('conflict')); const h = mount(script); await ready(h);
    await click(h.host, 'evaluate-benchmark'); const original = copy(script.calls('bench_verdict')[0][1]);
    expect(JSON.stringify(snapshotStorage())).toContain(original.op_id); noRecorded(h);
    await click(h.host, 'evaluate-benchmark'); expect(script.calls('bench_verdict')[1][1]).toEqual(original);
  });

  it('A18 absent verdict witness never announces recorded or synthesizes superiority', async () => {
    const script = new Script().queue('bench_verdict', { verdict: verdict({ decision: 'superior' }), commit: { event_ids: ['e-000000000000000b'], head: 11, sha256: HASH } });
    const h = mount(script); await ready(h); await click(h.host, 'evaluate-benchmark'); noRecorded(h);
    expect(text(h.root)).toMatch(/uncertain|not confirmed|witness|evidence/iu);
    expect(h.announcements.map(([, m]) => m)).not.toContain(`Benchmark ${key('bench', BENCH)}: superior.`);
  });

  it.each(['no_benchmark', 'heldout_forbidden', 'bad_args', 'conflict'])('A20 promotion %s reaches the server and preserves candidate status', async code => {
    const script = new Script().queue('agent_promote', refusal(code));
    if (code === 'bad_args') script.benches.set(BENCH, status({ declaration: declaration({ seats: [declaration().seats[0], { model: 'other-model', effort: 'high', mode: 'headless' }] }) }));
    const h = mount(script); await ready(h); expect((action(h.host, 'promote-candidate') as HTMLButtonElement).disabled).toBe(false);
    const modal = await promoteForm(h); expect(text(modal)).toContain(CANDIDATE); expect((modal.querySelector('[name="bench_id"]') as HTMLInputElement).value).toBe(BENCH);
    h.emit({ head: 17 }); await submit(modal, 'Promote agent');
    assertCall(h, 'agent_promote', { agent_id: CANDIDATE, bench_id: BENCH, agent: ACTOR, expected_head: 10 });
    expect(text(h.root)).toContain(code); expect(script.agents.get(CANDIDATE).status).toBe('draft'); noRecorded(h);
  });

  it('A20 promotion accepts server-declared snapshot despite a newer observed memory version', async () => {
    const script = new Script(); script.queue('agent_promote', (args: any) => {
      const promoted = { ...script.agents.get(CANDIDATE), status: 'shadow', promoted_seat: declaration().seats[0] };
      const e = event(11, 'agent.status', { agent_id: CANDIDATE, from: 'draft', to: 'shadow', reason: 'credited', bench_id: BENCH }, { agent: args.agent, op_id: args.op_id });
      script.agents.set(CANDIDATE, promoted); script.journal.push(e); script.head = 11;
      return { record: promoted, commit: commit([e]) };
    });
    const h = mount(script); await ready(h); const modal = await promoteForm(h); await submit(modal, 'Promote agent');
    expect(script.calls('agent_promote')).toHaveLength(1); expect(script.calls('agent_get').some(([, a]) => a.agent_id === CANDIDATE)).toBe(true);
    expect(script.calls('ledger_events').length).toBeGreaterThan(0); expect(h.announcements.some(([, m]) => m === `Promote agent recorded for ${key('agent', CANDIDATE)}.`)).toBe(true);
  });

  it('A20 agent_get disagreement leaves acknowledged promotion uncertain', async () => {
    const script = new Script(); script.queue('agent_promote', (args: any) => {
      const e = event(11, 'agent.status', { agent_id: CANDIDATE, from: 'draft', to: 'shadow', reason: 'credit', bench_id: BENCH }, { agent: args.agent, op_id: args.op_id });
      script.journal.push(e); script.head = 11; return { record: { ...script.agents.get(CANDIDATE), status: 'shadow' }, commit: commit([e]) };
    });
    const h = mount(script); await ready(h); await submit(await promoteForm(h), 'Promote agent'); noRecorded(h);
    expect(script.calls('agent_get').some(([, args]) => args.agent_id === CANDIDATE)).toBe(true); expect(text(h.root)).toMatch(/uncertain|not confirmed|disagree/iu);
  });

  it('A22 modal focus contains keyboard traversal Escape restores invoker and controls are registered', async () => {
    const h = mount(); await ready(h); const modal = await launchForm(h); const triggerName = `Launch benchmark ${key('bench', BENCH)}`;
    expect(modal.contains(document.activeElement)).toBe(true); expect(modal.getAttribute('aria-modal')).toBe('true'); expect(h.actor.closest('[inert]')).not.toBeNull();
    const enabled = allActions(modal).filter(el => !(el as HTMLButtonElement).disabled && el.matches('button,input,select,a[href]'));
    enabled.at(-1)!.focus(); enabled.at(-1)!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }));
    expect(modal.contains(document.activeElement)).toBe(true); expect(document.activeElement).not.toBe(enabled.at(-1));
    enabled[0].focus(); enabled[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(enabled.at(-1));
    for (const button of modal.querySelectorAll<HTMLButtonElement>('button')) expect(button.type).toBe(button.dataset.linAction === 'submit-dialog' ? 'submit' : 'button');
    modal.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })); await flush();
    expect(h.root.querySelector('dialog,[role="dialog"]')).toBeNull(); expect(nameOf(document.activeElement!)).toBe(triggerName); expect(h.script.mutationCalls()).toHaveLength(0);
  });
});
