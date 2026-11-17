// @vitest-environment jsdom
import { expect, it, vi } from 'vitest';
import { screen } from '../../src/screens/ledger/index.ts';
import {
  action, assertRead, bank, deferred, event, flush, id, ids, isolate, mount,
  openExport, own, page, record, scripted, submitExport, transport, visibleText,
} from './fixtures.ts';

isolate();

it('review 1 restarts an unconfirmed fold after event navigation and settles both promises', async () => {
  const old = deferred<unknown>(), current = deferred<unknown>();
  const t = scripted([old.promise, current.promise]);
  const h = await mount(t.transport); await flush();
  let ready = false, updated = false;
  void h.ready.then(() => {ready = true;});
  const update = h.update({event:id(1)}).then(() => {updated = true;});
  await flush();
  expect(t.calls).toHaveLength(2);
  expect(t.calls[0].options.signal?.aborted).toBe(true);
  assertRead(t.calls[1], 0);
  expect(ready).toBe(false); expect(updated).toBe(false);
  current.resolve(page([event(1)])); await update; await h.ready;
  expect(ids(h.main)).toEqual([id(1)]);
  expect(h.store.getState().selection.ledger).toBe(id(1));
  const text = h.main.textContent, count = h.announcements.mock.calls.length;
  old.resolve(page([event(2)])); await flush();
  expect(h.main.textContent).toBe(text);
  expect(h.announcements.mock.calls).toHaveLength(count);
});

it('review 1 local text navigation waits for the active initial fold without an extra read', async () => {
  const first = deferred<unknown>(); const t = scripted([first.promise]);
  const h = await mount(t.transport); await flush();
  let updated = false;
  const update = h.update({q:'checkpoint'}).then(() => {updated = true;});
  await flush(); expect(updated).toBe(false); expect(t.calls).toHaveLength(1);
  first.resolve(page([event(1)])); await update; await h.ready;
  expect(ids(h.main)).toEqual([id(1)]);
});

it('review 1 replacement failure rejects readiness and leaves visible recovery', async () => {
  const first = deferred<unknown>();
  const t = scripted([first.promise, new Error('Replacement unavailable')]);
  const h = await mount(t.transport); await flush();
  await expect(h.update({event:id(1)})).rejects.toThrow('Replacement unavailable');
  await expect(h.ready).rejects.toThrow('Replacement unavailable');
  expect(visibleText(h.main)).toContain('Replacement unavailable');
  expect(h.main.querySelector('[data-lin-action="retry-panel"]')).not.toBeNull();
});

it('review M15 pauses an absent deep link before draining the bank and pages explicitly', async () => {
  vi.useFakeTimers(); const t = bank();
  const h = await mount(t.transport, {event:id(10001)}, 10000); await h.ready;
  await vi.runAllTimersAsync();
  expect(t.calls.length).toBeGreaterThan(1);
  expect(t.calls.length).toBeLessThan(100);
  expect(t.generated()).toBe(t.calls.length * 100);
  expect(visibleText(h.main)).toMatch(/Search paused.*Load more events/s);
  const count = t.calls.length, cursor = t.calls.at(-1)!.args.after as number;
  action(h.main, 'page-events').click(); await flush(); await vi.runAllTimersAsync();
  expect(t.calls).toHaveLength(count + 1); assertRead(t.calls.at(-1)!, cursor + 100);
});

it('review M12 restores heading focus when a literal query hides a surviving event', async () => {
  const h = await mount(scripted([page([event(1)])]).transport); await h.ready;
  action(record(h.main, id(1)), 'toggle-event-hash').focus();
  action(record(h.main, id(1)), 'toggle-event-hash').click();
  await h.update({q:'unmatched text'});
  expect(document.activeElement).toBe(h.main.querySelector('h1'));
  expect(h.store.getState().selection.ledger).toBe(id(1));
  await h.update({});
  expect(action(record(h.main, id(1)), 'toggle-event-hash').getAttribute('aria-expanded')).toBe('true');
});

it('review M2 refresh aborts a pending continuation and folds a replacement from zero', async () => {
  const next = deferred<unknown>();
  const t = scripted([page([event(1)], {head:3, next_after:1, has_more:true}), next.promise,
    page([event(2)], {head:3, next_after:3})]);
  const h = await mount(t.transport, {}, 3); await h.ready;
  action(h.main, 'page-events').click(); await flush();
  const update = h.update(); await flush();
  expect(t.calls).toHaveLength(3); assertRead(t.calls[2], 0);
  expect(t.calls[1].options.signal?.aborted).toBe(true);
  await update; expect(ids(h.main)).toEqual([id(2)]);
  next.resolve(page([event(3)], {head:3, next_after:3})); await flush();
  expect(ids(h.main)).toEqual([id(2)]);
});

it('review M14 distinguishes pending discovery and failure from a missing dependency', async () => {
  const discovery = deferred<never>();
  const h = await mount(scripted([page([event(1)])]).transport); await h.ready;
  const main = document.createElement('main'); document.body.append(main);
  const t = transport(); t.transport.tools = vi.fn(() => discovery.promise);
  const mounted = screen.mount(main, {...h.context, transport:t.transport,
    store:{...h.store, getState:() => ({...h.store.getState(), tools:[]})}});
  own(mounted); void mounted.ready.catch(() => {});
  expect(visibleText(main)).not.toContain('missing or incompatible');
  expect(visibleText(main)).toMatch(/Checking.*dependencies/i);
  discovery.reject(new Error('Discovery unavailable'));
  await expect(mounted.ready).rejects.toThrow('Discovery unavailable');
  expect(visibleText(main)).not.toContain('missing or incompatible');
  expect(visibleText(main)).toContain('Discovery unavailable');
});

it('review 2 explicit resync accepts reused identity from replacement history with fresh disclosures', async () => {
  const t = scripted([page([event(1)], {head:3, next_after:2, has_more:true}),
    page([], {head:1, next_after:0, resync:true}),
    page([event(1, {payload:{progress:'Replacement history'}})])]);
  const h = await mount(t.transport, {}, 3); await h.ready;
  action(record(h.main, id(1)), 'toggle-event-payload').click();
  action(h.main, 'page-events').click(); await flush();
  h.acknowledge(1);
  action(h.main, 'resync-ledger').click(); await flush();
  expect(ids(h.main)).toEqual([id(1)]);
  expect(visibleText(h.main)).toContain('Replacement history');
  expect(visibleText(h.main)).not.toContain('Checkpoint 1');
  expect(visibleText(h.main)).not.toContain('invalid_response');
});

it('review 4 export rejection preserves the error source without inventing invalid_response', async () => {
  const t = transport(tool => {
    if(tool === 'ledger_events') return page([event(1)]);
    throw new Error('socket closed');
  });
  const h = await mount(t.transport); await h.ready;
  const {dialog, field} = await openExport(h.main);
  await submitExport(dialog, field);
  expect(visibleText(h.main)).toContain('socket closed');
  expect(h.announcements.mock.calls.some(c => String(c[1]).includes('socket closed'))).toBe(true);
  expect(h.announcements.mock.calls.some(c => String(c[1]).includes('invalid_response'))).toBe(false);
  expect(field.value).toBe('exports/snapshot');
  expect(t.calls.filter(c => c.tool === 'ledger_export')).toHaveLength(1);
});
