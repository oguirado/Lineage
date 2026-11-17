// @vitest-environment jsdom
// A-U25: New h2 regressions; existing frozen tests and helpers stay unchanged.
import { expect, it } from 'vitest';
import { startApp } from '../../src/main.ts';
import { BENCH, Script, action, cursor, declaration, detailRoute, event, flush, isolate, listRoute, mount, ready, text } from './helpers.ts';

isolate();

// A-U25: M22 requires the active main heading to survive a confirmed refresh.
it.each([listRoute(), detailRoute()])('h2 A23 retains main heading focus after refreshing $screen', async route => {
  const h = mount(new Script(), route);
  await ready(h);
  h.host.querySelector<HTMLElement>('h1')!.focus();
  expect(document.activeElement).toBe(h.host.querySelector('h1'));
  await h.update();
  expect(document.activeElement).toBe(h.host.querySelector('h1'));
});

const routes = [
  { hash: '#/arena', tool: 'bench_list', panel: 'Benchmarks' },
  { hash: `#/arena/${BENCH}`, tool: 'bench_status', panel: 'Rule' },
] as const;

// A-U25: Exercise integrated U21 with public benchmark replies instead of placeholder-only fakes.
it.each(routes)('h2 A01 A02 A09 integrated shell becomes ready on $hash with a validated snapshot', async ({ hash, tool }) => {
  const script = new Script();
  script.transport.events = async () => cursor([event(10, 'bench.declared', declaration())]);
  const root = document.createElement('div');
  document.body.append(root);
  const app = startApp({ root, initialHash: hash, storage: null, transport: script.useMode() });
  try {
    await flush();
    expect(document.documentElement.dataset.linReady).toBe('true');
    expect(document.documentElement.dataset.linRev).toBe('10');
    expect(root.querySelectorAll('h1')).toHaveLength(1);
    expect(root.querySelectorAll('[role="status"]')).toHaveLength(1);
    expect(text(root)).toContain(BENCH);
    expect(script.calls(tool).length).toBeGreaterThan(0);
    const actor = action(root, 'select-actor') as HTMLSelectElement;
    expect(actor.disabled).toBe(true);
    expect((action(root, hash === '#/arena' ? 'declare-benchmark' : 'launch-benchmark') as HTMLButtonElement).disabled).toBe(true);
    expect(script.mutationCalls()).toHaveLength(0);
  } finally {
    app.dispose();
    root.remove();
  }
});

// A-U25: Missing benchmark data must render recovery and cannot publish successful readiness.
it.each(routes)('h2 A02 A21 integrated shell refuses a placeholder-only $tool reply', async ({ hash, tool, panel }) => {
  const script = new Script().queue(tool, { synthetic: true }, { synthetic: true }, { synthetic: true });
  script.transport.events = async () => cursor([event(10, 'bench.declared', declaration())]);
  const root = document.createElement('div');
  document.body.append(root);
  const app = startApp({ root, initialHash: hash, storage: null, transport: script.useMode() });
  try {
    await flush();
    expect(document.documentElement.dataset.linReady).toBe('false');
    const main = root.querySelector('main')!;
    expect(text(main)).toContain(`${panel} unavailable. Retry to continue.`);
    action(main, 'retry-panel', `Retry ${panel}`);
    expect(text(main)).not.toContain('No benchmarks yet.');
    expect(script.mutationCalls()).toHaveLength(0);
  } finally {
    app.dispose();
    root.remove();
  }
});
