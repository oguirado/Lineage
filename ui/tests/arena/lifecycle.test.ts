// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { screen } from '../../src/screens/arena/index.ts';
import { getScreen } from '../../src/screens/index.ts';
import { startApp } from '../../src/main.ts';
import * as primitives from '../../src/ui/primitives.ts';
import { actions } from '../../src/ui/contracts.ts';
import { ACTOR, BENCH, OTHER, HASH, SEAT, SECOND_SEAT, repoRoot, Script, action, allActions, click, copy, declaration, deferred, detailRoute, event, flush, isolate, key, listRoute, mount, nameOf, ready, record, result, reveal, status, text, verdict, refusal } from './helpers.ts';
isolate();

describe('U25 snapshot, identity and lifecycle', () => {
  it('A01 list and detail use the registered screen and preserve shell ownership', async () => {
    const h = mount(new Script(), listRoute()); await ready(h);
    expect(getScreen(detailRoute())).toBe(screen); expect(screen.id).toBe('arena'); expect(screen.title).toBe('Arena');
    expect(h.script.calls('bench_list')).toHaveLength(1);
    expect(h.host.querySelectorAll('h1')).toHaveLength(1); expect(text(h.host.querySelector('h1')!)).toBe('Arena');
    const persistent = h.statusNode; await h.update(detailRoute());
    expect(text(h.host.querySelector('h1')!)).toBe(`Benchmark ${key('bench', BENCH)}`);
    for (const label of ['Declared rule', 'Task results', 'Verdict']) expect([...h.host.querySelectorAll('h2,h3')].some(el => text(el) === label)).toBe(true);
    expect(h.root.querySelector('[role="status"]')).toBe(persistent);
    expect(h.host.querySelector('main,header,nav,[role="status"]')).toBeNull();
  });

  it('A01 A32 the screen imports its owned stylesheet without a registry edit', async () => {
    const h = mount(new Script(), listRoute()); await ready(h); action(h.host, 'declare-benchmark');
    const source = readFileSync(resolve(repoRoot, 'ui/src/screens/arena/index.ts'), 'utf8');
    // The entry may delegate CSS loading to an owned support module.
    const visit = (pathOnDisk: string, seen = new Set<string>()): boolean => {
      if (seen.has(pathOnDisk)) return false; seen.add(pathOnDisk);
      const code = readFileSync(pathOnDisk, 'utf8');
      const imports = [...code.matchAll(/(?:from\s*|import\s*(?:\(\s*)?)["']([^"']+)["']/g)].map(m => m[1]);
      return imports.some(path => path.endsWith('/arena.css') && existsSync(resolve(dirname(pathOnDisk), path)) ||
        path.startsWith('./') && path.endsWith('.ts') && visit(resolve(dirname(pathOnDisk), path), seen));
    };
    expect(source.length).toBeGreaterThan(0); expect(visit(resolve(repoRoot, 'ui/src/screens/arena/index.ts'))).toBe(true);
  });

  it('A02 ready remains unsettled until the matching initial list read folds', async () => {
    const pending = deferred(); const script = new Script().queue('bench_list', () => pending.promise);
    const h = mount(script, listRoute()); let settled = false; void h.mounted.ready.then(() => { settled = true; });
    await flush(); expect(settled, 'An immediate placeholder promise is not a data fold').toBe(false);
    expect(text(h.host)).toMatch(/Loading/iu);
    pending.resolve({ benches: [status()], next_after: null, head: 10 }); await ready(h);
    expect(settled).toBe(true); expect(text(h.host)).toContain(BENCH);
  });

  it('A02 actual U21 readiness waits for the screen fold at the published snapshot', async () => {
    const pending = deferred(); const script = new Script().queue('bench_list', () => pending.promise);
    script.transport.events = vi.fn(async () => ({ events: [event(10, 'bench.declared', declaration())], next_after: 10, head: 10, has_more: false, resync: false }));
    const root = document.createElement('div'); document.body.append(root);
    const app = startApp({ root, initialHash: '#/arena', storage: null, transport: script.useMode() });
    try {
      await flush(); expect(document.documentElement.dataset.linReady).toBe('false');
      pending.resolve({ benches: [status()], next_after: null, head: 10 }); await flush();
      expect(document.documentElement.dataset.linReady).toBe('true'); expect(document.documentElement.dataset.linRev).toBe('10');
      expect(text(root)).toContain(BENCH); expect(root.querySelectorAll('h1')).toHaveLength(1);
    } finally { app.dispose(); }
  });

  it('A02 A21 initial failure renders Rule and Retry before rejecting ready', async () => {
    const h = mount(new Script().queue('bench_status', refusal('internal')));
    await expect(h.mounted.ready).rejects.toBeDefined();
    expect(text(h.host)).toContain('Rule unavailable. Retry to continue.');
    expect(nameOf(action(h.host, 'retry-panel'))).toBe('Retry Rule');
    expect(text(h.host)).not.toContain('No benchmarks yet.');
  });

  it('A02 route changes discard an older benchmark reply delivered last', async () => {
    const old = deferred(); const script = new Script().queue('bench_status', () => old.promise, { bench: status({ declaration: declaration({ bench_id: OTHER }) }) });
    const h = mount(script); const update = h.update(detailRoute(OTHER)); await update;
    expect(text(h.host)).toContain(OTHER);
    old.resolve({ bench: status() }); await flush();
    expect(text(h.host)).not.toContain(`Benchmark ${key('bench', BENCH)}`);
    expect(text(h.host)).toContain(OTHER); expect(h.script.calls('bench_status').map(c => c[1].bench_id)).toEqual([BENCH, OTHER]);
  });

  it('A02 A23 abort and dispose discard callbacks and announcements', async () => {
    const pending = deferred(); const script = new Script().queue('bench_status', () => pending.promise); const h = mount(script);
    await flush(); expect(script.calls('bench_status')).toHaveLength(1);
    h.abort.abort(); h.mounted.dispose(); const before = h.host.innerHTML, count = h.announcements.length;
    pending.resolve({ bench: status({ state: 'complete', verdict: verdict() }) }); await flush();
    expect(h.host.innerHTML).toBe(before); expect(h.announcements).toHaveLength(count);
  });

  it('A03 lexical paging deduplicates identities and filters only loaded records', async () => {
    const second = status({ declaration: declaration({ bench_id: OTHER, purpose: 'confirm' }), state: 'running' });
    const script = new Script().queue('bench_list', { benches: [status()], next_after: BENCH, head: 10 },
      { benches: [status(), second], next_after: null, head: 10 });
    const h = mount(script, listRoute({ q: OTHER, purpose: 'confirm', state: 'running' })); await ready(h);
    expect(text(h.host)).toContain('No matching benchmarks. Clear filters to see all loaded records.');
    expect(text(h.host)).toMatch(/loaded|partial/iu); expect(text(h.host)).not.toContain('No benchmarks yet.');
    await click(h.host, 'page-benches');
    record(h.host, 'bench', OTHER); expect(allActions(h.host).filter(el => el.dataset.linAction === 'open-benchmark')).toHaveLength(1);
    expect(script.calls('bench_list')).toHaveLength(2); expect(script.calls('bench_list')[1][1].after).toBe(BENCH);
    for (const [, args, options] of script.calls('bench_list')) {
      expect(Object.keys(args).every(k => ['after', 'limit', 'agent'].includes(k))).toBe(true); expect(options.mutation).toBe(false);
    }
    expect((action(h.host, 'filter-bench-query') as HTMLInputElement).value).toBe(OTHER);
    await click(h.host, 'clear-bench-filters');
    expect(allActions(h.host).filter(el => el.dataset.linAction === 'open-benchmark')).toHaveLength(2);
    expect(h.navigate).toHaveBeenCalledWith(listRoute());
  });

  it('A03 an empty confirmed list is distinct from a filtered no-match', async () => {
    const script = new Script(); script.benches.clear(); const h = mount(script, listRoute()); await ready(h);
    expect(text(h.host)).toContain('No benchmarks yet.'); expect(text(h.host)).not.toContain('No matching benchmarks.');
    action(h.host, 'declare-benchmark');
  });

  it('A03 failed paging retries its cursor once and retains filters', async () => {
    const script = new Script().queue('bench_list', { benches: [status()], next_after: BENCH, head: 10 }, refusal('busy'),
      { benches: [status({ declaration: declaration({ bench_id: OTHER }) })], next_after: null, head: 10 });
    const h = mount(script, listRoute({ q: 'bench' })); await ready(h); await click(h.host, 'page-benches');
    expect(text(h.host)).toMatch(/busy|unavailable/iu); expect((action(h.host, 'filter-bench-query') as HTMLInputElement).value).toBe('bench');
    await click(h.host, 'retry-panel', 'Retry Benchmarks');
    expect(script.calls('bench_list').slice(1).map(c => c[1].after)).toEqual([BENCH, BENCH]);
    record(h.host, 'bench', BENCH); record(h.host, 'bench', OTHER);
    expect(allActions(h.host).filter(el => el.dataset.linAction === 'page-benches' && !(el as HTMLButtonElement).disabled)).toHaveLength(0);
  });

  it('A04 names are bounded content keys and actions survive article pruning', async () => {
    const long = 'benchmark_' + 'x'.repeat(54); const script = new Script(); script.benches.clear();
    script.benches.set(long, status({ declaration: declaration({ bench_id: long }) })); script.benches.set(OTHER, status({ declaration: declaration({ bench_id: OTHER }) }));
    const h = mount(script, listRoute()); await ready(h);
    const target = record(h.host, 'bench', long); const open = action(target, 'open-benchmark');
    expect(nameOf(open)).toBe(`Open benchmark ${key('bench', long)}`); expect(open.getAttribute('href')).toBe(`#/arena/${encodeURIComponent(long)}`);
    const descriptions = (open.getAttribute('aria-describedby') ?? '').split(/\s+/u).map(id => document.getElementById(id)?.textContent ?? '').join(' ');
    expect(descriptions).toContain(long); expect(text(target)).toContain(long);
    const inventory = allActions(h.host).map(el => [el.dataset.linAction, nameOf(el)]);
    for (const el of allActions(h.host)) { expect(Buffer.byteLength(nameOf(el))).toBeLessThanOrEqual(64); expect(el.closest('article')).toBeNull(); }
    expect(new Set(inventory.map(([, name]) => name)).size).toBe(inventory.length);
    const pruned = h.host.cloneNode(true) as HTMLElement; pruned.querySelectorAll('article').forEach(el => el.remove());
    expect(allActions(pruned).map(el => [el.dataset.linAction, nameOf(el)])).toEqual(inventory);
    await h.update(listRoute()); expect(nameOf(action(record(h.host, 'bench', long), 'open-benchmark'))).toBe(nameOf(open));
  });

  it('A04 a forced key collision disables affected controls but settles the visible error', async () => {
    const original = primitives.identityKey;
    vi.spyOn(primitives, 'identityKey').mockImplementation((kind, id) => kind === 'bench' ? 'collision-key' : original(kind, id));
    const script = new Script(); script.benches.set(OTHER, status({ declaration: declaration({ bench_id: OTHER }) }));
    const h = mount(script, listRoute()); await ready(h);
    expect(text(h.host)).toContain('Identity key collision. Actions unavailable.');
    const targets = [...h.host.querySelectorAll<HTMLElement>('[data-lin-action="open-benchmark"]')];
    for (const el of targets) expect(el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true' || !el.hasAttribute('href')).toBe(true);
    expect(h.navigate).not.toHaveBeenCalled(); expect(script.mutationCalls()).toHaveLength(0);
  });

  it('A05 separate task agent seat arm and actual run identities remain visible', async () => {
    const cells = [result('run_base_0001', { agent_id: 'baseline-agent' }), result('run_own_00002'), result('run_inherit_03', { seat: SECOND_SEAT, memory_arm: 'inherited' })];
    const s = status({ declaration: declaration({ seats: [copy(SEAT), SECOND_SEAT] }), results: cells });
    const script = new Script(); script.benches.set(BENCH, s); const h = mount(script); await ready(h); await reveal(h);
    expect(text(h.host)).toMatch(/Baseline.*baseline-agent.*Candidate.*candidate-agent/u);
    for (const cell of cells) {
      const row = record(h.host, 'run', cell.run_id);
      for (const value of [cell.task_id, cell.agent_id, cell.seat.model, cell.seat.effort, cell.seat.mode, cell.memory_arm, cell.verdict]) expect(text(row)).toContain(value);
      expect(nameOf(action(row, 'inspect-bench-result'))).toBe(`Task result ${key('run', cell.run_id)}`);
    }
  });

  it('A08 omitted rule is collapsed and requires explicit display before launch', async () => {
    const h = mount(); await ready(h);
    const toggle = action(h.host, 'show-bench-rule'); expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect((action(h.host, 'launch-benchmark') as HTMLButtonElement).disabled).toBe(true);
    action(h.host, 'launch-benchmark').dispatchEvent(new MouseEvent('click', { bubbles: true })); await flush();
    expect(h.script.calls('bench_run')).toHaveLength(0);
    await reveal(h); expect((action(h.host, 'launch-benchmark') as HTMLButtonElement).disabled).toBe(false);
    await click(h.host, 'show-bench-rule'); expect(text(h.host)).toContain(HASH);
    expect((action(h.host, 'launch-benchmark') as HTMLButtonElement).disabled).toBe(false);
    expect(h.navigate.mock.calls.some(([r]) => r.query.rule === '0')).toBe(true);
  });

  it('A08 changed declaration or selected identity invalidates the display prerequisite', async () => {
    const script = new Script(); const h = mount(script); await ready(h); await reveal(h);
    script.benches.set(OTHER, status({ declaration: declaration({ bench_id: OTHER, purpose: 'confirm' }) }));
    await h.update(detailRoute(OTHER)); expect((action(h.host, 'launch-benchmark') as HTMLButtonElement).disabled).toBe(true);
    await reveal(h); const changed = copy(script.benches.get(OTHER)); changed.declaration.bank_sha256 = 'c'.repeat(64); script.benches.set(OTHER, changed);
    await h.update(detailRoute(OTHER)); expect((action(h.host, 'launch-benchmark') as HTMLButtonElement).disabled).toBe(true);
  });

  it.each(['declared', 'queued', 'running', 'stalled', 'complete'])('A15 actual %s lifecycle is rendered distinctly', async state => {
    const script = new Script(); script.benches.set(BENCH, status({ state })); const h = mount(script); await ready(h);
    expect(text(h.host)).toContain(state[0].toUpperCase() + state.slice(1)); action(h.host, 'refresh-benchmark');
    expect(h.script.mutationCalls()).toHaveLength(0);
  });

  it('A15 named refresh folds delayed results and never manufactures completion', async () => {
    const delayed = deferred(); const script = new Script().queue('bench_status', { bench: status({ state: 'running' }) }, () => delayed.promise);
    const h = mount(script); await ready(h); await click(h.host, 'refresh-benchmark');
    expect(text(h.host)).toContain('Running'); expect(text(h.host)).not.toContain('Complete');
    delayed.resolve({ bench: status({ state: 'stalled', results: [result()] }) }); await flush();
    expect(text(h.host)).toContain('Stalled'); record(h.host, 'run', 'run_alpha_0001');
  });

  it('A19 unrelated head changes and unchanged polls never repeat verdict announcements', async () => {
    const script = new Script(); script.benches.set(BENCH, status({ state: 'complete', verdict: verdict() }));
    const h = mount(script); await ready(h);
    expect(h.announcements.map(([, m]) => m)).not.toContain(`Benchmark ${key('bench', BENCH)}: not_superior.`);
    const node = h.statusNode; script.benches.set(BENCH, status({ state: 'complete', verdict: verdict(), head: 11 }));
    await h.update(detailRoute(), 11); await click(h.host, 'refresh-benchmark');
    expect(h.announcements.map(([, m]) => m).filter(m => /: not_superior\./u.test(m))).toHaveLength(0);
    expect(h.root.querySelectorAll('[role="status"]')).toHaveLength(1); expect(h.root.querySelector('[role="status"]')).toBe(node);
  });

  it('A19 one poll announces state before verdict once and in observed order', async () => {
    const script = new Script(); const h = mount(script); await ready(h);
    script.benches.set(BENCH, status({ state: 'running', head: 11 })); await click(h.host, 'refresh-benchmark');
    script.benches.set(BENCH, status({ state: 'complete', verdict: verdict({ decision: 'superior' }), head: 12 })); await click(h.host, 'refresh-benchmark');
    await click(h.host, 'refresh-benchmark');
    const messages = h.announcements.map(([, m]) => m).filter(m => m.startsWith(`Benchmark ${key('bench', BENCH)}:`));
    expect(messages).toHaveLength(3); expect(messages[0]).toMatch(/running/iu); expect(messages[1]).toMatch(/complete/iu);
    expect(messages[2]).toBe(`Benchmark ${key('bench', BENCH)}: superior.`);
  });

  it('A21 later Rule failure retains the confirmed fold with stale revision and disables launch', async () => {
    const script = new Script(); const h = mount(script); await ready(h); await reveal(h);
    script.queue('bench_status', refusal('busy')); await click(h.host, 'refresh-benchmark');
    expect(text(h.host)).toContain('Data is stale. Last confirmed revision 10.'); expect(text(h.host)).toContain(HASH);
    expect(text(h.host)).toContain('Rule unavailable. Retry to continue.'); action(h.host, 'retry-panel', 'Retry Rule');
    expect((action(h.host, 'launch-benchmark') as HTMLButtonElement).disabled).toBe(true);
  });

  it('A23 query restoration resets only unsupported values and retains valid filters', async () => {
    const h = mount(new Script(), listRoute({ q: 'alpha', purpose: 'bogus', state: 'running', payload: '<script>' })); await ready(h);
    expect((action(h.host, 'filter-bench-query') as HTMLInputElement).value).toBe('alpha');
    expect((action(h.host, 'filter-bench-state') as HTMLSelectElement).value).toBe('running');
    expect((action(h.host, 'filter-bench-purpose') as HTMLSelectElement).value).toBe('');
    expect(text(h.root)).toMatch(/unknown|invalid|ignored/iu);
    expect(h.script.mutationCalls()).toHaveLength(0);
  });

  it('A23 refresh reorder preserves full run identity focus and disclosure', async () => {
    const script = new Script(); const first = result(), second = result('run_other_0002');
    script.benches.set(BENCH, status({ results: [first, second] })); const h = mount(script); await ready(h); await reveal(h);
    action(record(h.host, 'run', first.run_id), 'open-bench-run').focus();
    script.benches.set(BENCH, status({ results: [second, first] })); await h.update();
    expect(nameOf(document.activeElement!)).toBe(`Inspect benchmark run ${key('run', first.run_id)}`);
    expect(action(h.host, 'show-bench-rule').getAttribute('aria-expanded')).toBe('true');
    script.benches.set(BENCH, status({ results: [second] })); await h.update();
    expect(text(document.activeElement!)).toBe('Task results');
    expect(h.announcements.some(([, m]) => m === `${key('run', first.run_id)} is no longer in this view.`)).toBe(true);
  });

  it('A27 the unimplemented placeholder cannot satisfy a rendered Arena oracle', async () => {
    const h = mount(new Script(), listRoute()); await ready(h);
    expect(text(h.host), 'A missing-feature assertion, never an import failure').not.toContain('Arena: not built yet.');
    expect(h.host.querySelector('[data-lin-action="declare-benchmark"]')).not.toBeNull();
    for (const el of allActions(h.host)) expect(actions.has(el.dataset.linAction!)).toBe(true);
  });
});
