import { expect, it, vi } from 'vitest';
import { startApp } from '../../src/main.ts';
import { action, deferred, drain, ids, isolation, mount } from './fixtures.ts';

isolation();

it('H2-1 waits for the acknowledged U21 fold when topology arrives during startup', async () => {
  // A-U24: Exercise U21's integrated loading-to-committed store lifecycle.
  const h = mount({state: {phase: 'loading', head: null}});
  await drain();
  expect(h.readyState.value).toBe('pending');
  expect(h.host.textContent).toContain('Loading Lineage.');
  expect(ids(h.host)).toEqual([]);
  h.publish({phase: 'ready', head: h.events.length});
  await h.ready;
  expect(h.readyState.value).toBe('fulfilled');
  expect(ids(h.host)).toContain('root-a');
  expect(h.listenerCount()).toBe(0);
});

it('H2-2 a superseding fold releases startup readiness through the current render', async () => {
  // A-U24: Exercise U21's integrated loading-to-committed store lifecycle.
  const h = mount({state: {phase: 'loading', head: null}});
  await drain();
  h.publish({phase: 'ready', head: h.events.length});
  await h.update({selected: 'clone-c'});
  await h.ready;
  expect(action(h.host, 'select-lineage-agent', 'clone-c').getAttribute('aria-pressed')).toBe('true');
  expect(h.listenerCount()).toBe(0);
});

it.each(['abort', 'dispose'] as const)('H2-3 %s releases an outstanding prefix subscription without publishing', async how => {
  // A-U24: Exercise U21's integrated loading-to-committed store lifecycle.
  const h = mount({state: {phase: 'loading', head: null}});
  await drain();
  expect(h.readyState.value).toBe('pending');
  const before = h.host.innerHTML;
  if (how === 'abort') h.controller.abort(); else h.dispose();
  await drain();
  expect(h.readyState.value).toBe('rejected');
  expect(h.listenerCount()).toBe(0);
  h.publish({phase: 'ready', head: h.events.length});
  await drain();
  expect(h.host.innerHTML).toBe(before);
});

it('H2-4 the actual shell becomes ready after a delayed complete prefix', async () => {
  // A-U24: Verify actual shell readiness with contract-shaped topology and ledger reads.
  const seed = mount(); await seed.ready;
  const transport = seed.transport;
  const page = deferred<Awaited<ReturnType<typeof transport.events>>>();
  vi.mocked(transport.events).mockReturnValue(page.promise);
  seed.dispose();
  const root = document.createElement('div'); document.body.append(root);
  const app = startApp({root, transport, initialHash: '#/lineage', storage: null});
  try {
    await drain();
    expect(document.documentElement.dataset.linReady).toBe('false');
    expect(root.textContent).toContain('Loading Lineage.');
    const fold = app.store.refresh();
    page.resolve({events: seed.events, head: seed.events.length, next_after: seed.events.length, has_more: false, resync: false});
    await fold; await drain();
    expect(document.documentElement.dataset.linReady).toBe('true');
    expect(document.documentElement.dataset.linRev).toBe(String(seed.events.length));
    expect(ids(root)).toContain('root-a');
    expect(root.querySelectorAll('[role="status"]')).toHaveLength(1);
  } finally {app.dispose(); root.remove();}
});
