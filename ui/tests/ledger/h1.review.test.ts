// @vitest-environment jsdom
// A-U26: exercise review h1 recovery and snapshot agreement against the integrated AppStore API.
import { it, expect, vi } from 'vitest';
import type { ScreenContext, Transport } from '../../src/ui/contracts.ts';
import { createStore } from '../../src/store.ts';
import { screen } from '../../src/screens/ledger/index.ts';
import {
  action, click, deferred, event, flush, id, ids, isolate, own, page, retry,
  scripted, transport, verifyResult, visibleText,
} from './fixtures.ts';

isolate();

// A-U26: use the real store.refresh -> transport.events publication, without a test-only head setter.
function integrated(t: Transport) {
  const route = {screen: 'ledger' as const, query: {}};
  const store = createStore(t, route);
  const main = document.createElement('main');
  document.body.append(main);
  const controller = new AbortController();
  const context: ScreenContext = {
    route, store, transport: t, signal: controller.signal,
    navigate: vi.fn(), announce: vi.fn(),
  };
  const mounted = screen.mount(main, context);
  own({dispose() {controller.abort(); mounted.dispose(); store.dispose(); main.remove();}});
  return {store, main, mounted};
}

it('h1 A2 A18 retry waits for the real shared-store acknowledgement before folding recovered rows', async () => {
  const snapshot = deferred<ReturnType<typeof page>>();
  const t = scripted([new Error('Synthetic initial refusal'), page([event(1)])]);
  t.transport.events = vi.fn(() => snapshot.promise);
  const h = integrated(t.transport);
  await expect(h.mounted.ready).rejects.toThrow('Synthetic initial refusal');
  expect(h.store.getState().head).toBeNull();
  expect(visibleText(h.main)).not.toContain('No ledger events yet.');
  retry(h.main).click();
  await flush();
  expect(t.calls).toHaveLength(2);
  expect(t.transport.events).toHaveBeenCalledTimes(1);
  expect(h.store.getState().head).toBeNull();
  expect(ids(h.main)).toEqual([]);
  snapshot.resolve(page([event(1)]));
  await flush();
  expect(h.store.getState().head).toBe(1);
  expect(ids(h.main)).toEqual([id(1)]);
  expect(h.main.querySelector('[data-lin-action="retry-panel"]')).toBeNull();
});

it('h1 A2 refuses recovery when the real store cannot acknowledge the recovered page head', async () => {
  const t = scripted([new Error('Synthetic initial refusal'), page([event(1)])]);
  const h = integrated(t.transport);
  await expect(h.mounted.ready).rejects.toThrow('Synthetic initial refusal');
  retry(h.main).click();
  await flush();
  expect(h.store.getState().head).toBe(0);
  expect(ids(h.main)).toEqual([]);
  expect(visibleText(h.main)).toContain('shared revision does not acknowledge the page head');
  retry(h.main);
});

it('h1 A11 empty history verifies with an unknown digest through the real shared-store snapshot', async () => {
  const t = transport(tool => tool === 'ledger_events' ? page() : verifyResult({head: 0, sha256: null}));
  const h = integrated(t.transport);
  await h.mounted.ready;
  expect(h.store.getState().head).toBe(0);
  expect(visibleText(h.main)).toContain('No ledger events yet.');
  expect(visibleText(h.main)).toContain('Not verified');
  await click(h.main, 'verify-ledger');
  const verification = h.main.querySelector('[aria-label="Verification"]')!;
  expect(verification.textContent).toContain('Verified at head 0.');
  expect(verification.textContent).toContain('SHA-256: Not measured');
  expect(verification.textContent).not.toMatch(/[a-f0-9]{64}/u);
  expect(t.calls.find(call => call.tool === 'ledger_verify')?.args).toEqual({});
  expect(action<HTMLButtonElement>(h.main, 'verify-ledger').disabled).toBe(false);
});
