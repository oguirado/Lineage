// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { startApp } from '../../main.ts';
import { TransportError } from '../../transport.ts';
import { statusReply } from './model.ts';
import {
  BENCH, OTHER, Script, action, click, conforms, declaration, deferred,
  detailRoute, flush, isolate, listRoute, mount, ready, record, result,
  status, text, toolSchema, verdict,
} from '../../../tests/arena/helpers.ts';

isolate();
const apps: ReturnType<typeof startApp>[] = [];
afterEach(() => { for (const app of apps.splice(0)) app.dispose(); });

function appAt(hash: string, script = new Script()) {
  const root = document.createElement('div');
  document.body.append(root);
  apps.push(startApp({ root, initialHash: hash, storage: null, transport: script.useMode() }));
  return root;
}
function settled(root: HTMLElement, name: string) {
  const output = root.querySelector<HTMLOutputElement>(`output[aria-label="${name}"]`);
  expect(output).not.toBeNull();
  expect(output!.hidden).toBe(false);
  expect(document.documentElement.dataset.linReady).toBe('true');
  expect(root.querySelector('main')!.getAttribute('aria-busy')).toBe('false');
  expect([...root.querySelectorAll<HTMLElement>('[role="progressbar"]')].filter(el => !el.hidden)).toEqual([]);
}

it.each([
  { hash: '#/arena', name: 'Screen arena ready' },
  { hash: `#/arena/${BENCH}`, name: `Screen arena ${BENCH} ready` },
])('settles the integrated declared result on $hash', async ({ hash, name }) => {
  const root = appAt(hash);
  await flush();
  settled(root, name);
  expect(text(root)).toContain(BENCH);
});

it('settles an empty journal-backed benchmark list without inventing records', async () => {
  const script = new Script(); script.benches.clear(); script.head = 0;
  const root = appAt('#/arena', script);
  await flush();
  settled(root, 'Screen arena ready');
  expect(text(root)).toContain('No benchmarks yet.');
  expect(root.querySelector('[data-lin-action="open-benchmark"]')).toBeNull();
});

it.each(['absent01', 'OPS1bench'])('keeps the real refusal alert and settled status for %s', async benchId => {
  const script = new Script();
  script.transport.call = vi.fn(async tool => {
    if (tool === 'bench_status') throw new TransportError('domain', 'no_benchmark', 'benchmark declaration unavailable');
    return script.dispatch(tool, {}, { mutation: false });
  }) as typeof script.transport.call;
  const root = appAt(`#/arena/${benchId}`, script);
  await flush();
  settled(root, `Screen arena ${benchId} ready`);
  const alert = root.querySelector<HTMLElement>('main [role="alert"]');
  expect(alert?.getAttribute('aria-label')).toContain('Error:');
  expect(alert?.getAttribute('aria-label')).toContain('no_benchmark');
  expect(alert?.textContent).toContain('benchmark declaration unavailable');
  expect(text(root)).not.toContain('render_error');
  expect(root.querySelector('[data-lin-action="launch-benchmark"]')).toBeNull();
  await flush();
  expect(root.querySelector('main [role="alert"]')).toBe(alert);
  expect(script.mutationCalls()).toHaveLength(0);
});

it.each(['bench_status', 'bench_list'])('settles a failed %s read with the actual error and Retry', async tool => {
  const script = new Script();
  script.transport.call = vi.fn(async (name, args, options) => {
    if (name === tool) throw new TransportError('domain', 'internal', 'Read failed');
    return script.dispatch(name, args, options);
  }) as typeof script.transport.call;
  const root = appAt(tool === 'bench_list' ? '#/arena' : `#/arena/${BENCH}`, script);
  await flush();
  settled(root, tool === 'bench_list' ? 'Screen arena ready' : `Screen arena ${BENCH} ready`);
  expect(root.querySelector('main [role="alert"]')?.textContent).toContain('internal');
  expect(text(root)).not.toContain('render_error');
  expect(root.querySelector('[data-lin-action="retry-panel"]')).not.toBeNull();
});

it('settles a malformed result as an invalid response, without claiming benchmark success', async () => {
  const script = new Script();
  script.transport.call = vi.fn(async (tool, args, options) => tool === 'bench_status'
    ? { synthetic: true } : script.dispatch(tool, args, options)) as typeof script.transport.call;
  const root = appAt(`#/arena/${BENCH}`, script);
  await flush();
  settled(root, `Screen arena ${BENCH} ready`);
  expect(root.querySelector('main [role="alert"]')?.textContent).toContain('invalid_response');
  expect(root.querySelector('[data-lin-action="launch-benchmark"]')).toBeNull();
});

it('stays busy until the read completes, then retries a refused read into real data', async () => {
  const pending = deferred();
  const script = new Script(); let retry = false;
  script.transport.call = vi.fn(async (tool, args, options) => tool === 'bench_status' && !retry
    ? pending.promise : script.dispatch(tool, args, options)) as typeof script.transport.call;
  const root = appAt(`#/arena/${BENCH}`, script);
  await flush();
  expect(document.documentElement.dataset.linReady).toBe('false');
  expect(root.querySelector<HTMLElement>('[role="progressbar"]')?.hidden).toBe(false);
  pending.reject(new TransportError('domain', 'no_benchmark', 'benchmark declaration unavailable'));
  await flush();
  settled(root, `Screen arena ${BENCH} ready`);
  retry = true;
  await click(root, 'retry-panel');
  settled(root, `Screen arena ${BENCH} ready`);
  expect(root.querySelector('main [role="alert"]')).toBeNull();
  expect(text(root)).toContain(BENCH);
});

it('accepts the declared, result and verdict wire shapes from the integrated contract', () => {
  const b = status({ state: 'complete', results: [result()], verdict: verdict() });
  expect(conforms({ bench: b }, toolSchema('bench_status', true))).toBe(true);
  expect(statusReply({ bench: b }, BENCH)).toEqual(b);
  expect(conforms({ benches: [b], next_after: null, head: b.head }, toolSchema('bench_list', true))).toBe(true);
  expect(() => statusReply({ bench: { ...b, results: [{ acknowledged: true }] } }, BENCH)).toThrow();
});

it('offers unique Run actions only with a real tool and explicit actor, opening review without dispatch', async () => {
  const script = new Script();
  script.benches.set(OTHER, status({ declaration: declaration({ bench_id: OTHER }) }));
  const h = mount(script, listRoute()); await ready(h);
  const run = action(record(h.host, 'bench', BENCH), 'launch-benchmark');
  expect(run.getAttribute('aria-label') ?? run.textContent).toBe(`Run benchmark ${BENCH}`);
  await click(record(h.host, 'bench', BENCH), 'launch-benchmark');
  expect(h.navigate).toHaveBeenCalledWith(detailRoute(BENCH, { rule: '1' }));
  expect(script.mutationCalls()).toHaveLength(0);
  await h.update(listRoute());
  h.actor.disabled = true; h.actor.dispatchEvent(new Event('change', { bubbles: true }));
  expect(h.host.querySelector('[data-lin-action="launch-benchmark"]')).toBeNull();
  h.actor.disabled = false;
  h.emit({ tools: h.state.tools.filter(t => t.name !== 'bench_run') });
  h.actor.dispatchEvent(new Event('change', { bubbles: true }));
  expect(h.host.querySelector('[data-lin-action="launch-benchmark"]')).toBeNull();
});
