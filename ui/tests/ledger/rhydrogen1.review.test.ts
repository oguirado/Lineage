// @vitest-environment jsdom
import { expect, it, vi } from 'vitest';
import type { JsonObject } from '../../src/ui/contracts.ts';
import {
  ACTOR, action, assertRead, deferred, event, flush, id, ids, isolate,
  mount, networkError, page, record, retry, scripted, sourceText, visibleText,
} from './fixtures.ts';

isolate();

it('review 1 resolves ready after one page and automatically continues a deep link sequentially', async () => {
  vi.useFakeTimers();
  const next = deferred<unknown>();
  const t = scripted([page([event(1)], {head:300, next_after:100, has_more:true}),
    next.promise, page([event(261)], {head:300, next_after:300})]);
  const h = await mount(t.transport, {event:id(261), agent:ACTOR, kind:'run.beat'}, 300);
  await h.ready;
  expect(t.calls).toHaveLength(1);
  await vi.advanceTimersToNextTimerAsync();
  expect(t.calls).toHaveLength(2);
  assertRead(t.calls[1], 100, {agent_id:ACTOR, kinds:['run.beat']});
  expect(visibleText(h.main)).toMatch(/looking|search/i);
  next.resolve(page([], {head:300, next_after:200, has_more:true}));
  await flush();
  await vi.advanceTimersToNextTimerAsync();
  await flush();
  assertRead(t.calls[2], 200, {agent_id:ACTOR, kinds:['run.beat']});
  expect(h.store.getState().selection.ledger).toBe(id(261));
  expect(ids(h.main)).toEqual([id(1), id(261)]);
  await vi.runOnlyPendingTimersAsync();
  expect(t.calls).toHaveLength(3);
});

it.each(['event', 'filter', 'dispose'] as const)('review 1 cancels an in-flight lookup on %s change', async change => {
  vi.useFakeTimers();
  const next = deferred<unknown>();
  const t = scripted([page([event(1)], {head:300, next_after:100, has_more:true}),
    next.promise, page([event(2)], {head:300, next_after:300})]);
  const h = await mount(t.transport, {event:id(261)}, 300);
  await h.ready;
  await vi.advanceTimersToNextTimerAsync();
  expect(t.calls).toHaveLength(2);
  if(change === 'dispose') h.dispose();
  else await h.update(change === 'event' ? {event:id(1)} : {agent:ACTOR});
  expect(t.calls[1].options.signal?.aborted).toBe(true);
  const text = h.main.textContent, announcements = h.announcements.mock.calls.length;
  next.resolve(page([event(261)], {head:300, next_after:300}));
  await flush();
  await vi.runOnlyPendingTimersAsync();
  expect(h.main.textContent).toBe(text);
  expect(h.announcements.mock.calls).toHaveLength(announcements);
});

it('review 1 cancels queued lookup work before it dispatches', async () => {
  vi.useFakeTimers();
  const t = scripted([page([event(1)], {head:300, next_after:100, has_more:true})]);
  const h = await mount(t.transport, {event:id(261)}, 300);
  await h.ready;
  await h.update({});
  await vi.runOnlyPendingTimersAsync();
  expect(t.calls).toHaveLength(1);
});

it('review 1 stops on resync without silently restarting', async () => {
  vi.useFakeTimers();
  const t = scripted([page([event(1)], {head:300, next_after:100, has_more:true}),
    page([], {head:2, next_after:0, resync:true})]);
  const h = await mount(t.transport, {event:id(261)}, 300);
  await h.ready;
  await vi.runAllTimersAsync();
  expect(t.calls).toHaveLength(2);
  expect(ids(h.main)).toEqual([id(1)]);
  expect(visibleText(h.main)).toContain('Ledger changed. Resync required; filters kept.');
});

it('review 1 stops a failed lookup until an explicit retry using the same cursor', async () => {
  vi.useFakeTimers();
  const t = scripted([page([event(1)], {head:300, next_after:100, has_more:true}),
    networkError(), page([event(261)], {head:300, next_after:300})]);
  const h = await mount(t.transport, {event:id(261)}, 300);
  await h.ready;
  await vi.runAllTimersAsync();
  expect(t.calls).toHaveLength(2);
  retry(h.main).click(); await flush();
  expect(t.calls[2].args).toEqual(t.calls[1].args);
  expect(h.store.getState().selection.ledger).toBe(id(261));
});

it('review 1 exhausts filtered lookup without bypassing its filters', async () => {
  vi.useFakeTimers();
  const t = scripted([page([], {head:300, next_after:100, has_more:true}),
    page([], {head:300, next_after:300})]);
  const h = await mount(t.transport, {event:id(261), agent:ACTOR}, 300);
  await h.ready;
  await vi.runAllTimersAsync();
  expect(t.calls).toHaveLength(2);
  assertRead(t.calls[1], 100, {agent_id:ACTOR});
  expect(visibleText(h.main)).toContain(`Event ${id(261)} not found under active filters.`);
});

it.each([
  ['cursor beyond head', page([], {next_after:999, head:5})],
  ['descending Lamports', page([event(5), event(3)], {next_after:5, head:5})],
  ['event beyond head', page([event(6)], {next_after:5, head:5})],
  ['resync with events', page([event(1)], {next_after:0, head:0, resync:true})],
  ['resync with continuation', page([], {next_after:0, head:0, resync:true, has_more:true})],
  ['resync with cursor', page([], {next_after:1, head:1, resync:true})],
])('review 2 rejects %s without changing confirmed records', async (_label, invalid) => {
  const t = scripted([page([event(1)], {head:10, next_after:7, has_more:true}), invalid]);
  const h = await mount(t.transport, {}, 10); await h.ready;
  action(h.main, 'page-events').click(); await flush();
  expect(ids(h.main)).toEqual([id(1)]);
  expect(visibleText(h.main)).toContain('invalid_response');
  expect(visibleText(h.main)).not.toContain('Ledger changed. Resync required; filters kept.');
  expect(visibleText(h.main)).toContain('Scan cursor 7.');
});

it('review 3 rejects excessive payload nesting through the integrated validation boundary', async () => {
  let payload:JsonObject = {progress:'deep'};
  for(let i=0; i<10000; i++) payload = {nested:payload};
  const h = await mount(scripted([page([event(1, {payload})])]).transport);
  await expect(h.ready).rejects.toMatchObject({code:'invalid_response'});
  expect(ids(h.main)).toEqual([]);
});

it('review 3 expands accepted nested passive payload without losing identity', async () => {
  let payload:JsonObject = {progress:'deep'};
  for(let i=0; i<100; i++) payload = {nested:payload};
  const h = await mount(scripted([page([event(1, {payload})])]).transport); await h.ready;
  action(record(h.main, id(1)), 'toggle-event-payload').click();
  expect(visibleText(h.main)).toContain('deep');
  expect(action(record(h.main, id(1)), 'toggle-event-payload').getAttribute('aria-expanded')).toBe('true');
});

it('review 4 restores heading focus and announces removal of an unselected focused event', async () => {
  const t = scripted([page([event(1), event(2)]), page([event(1)], {head:2, next_after:2})]);
  const h = await mount(t.transport, {}, 2); await h.ready;
  action(record(h.main, id(2)), 'open-event-agent').focus();
  expect(h.store.getState().selection.ledger).toBeUndefined();
  await h.update();
  expect(document.activeElement).toBe(h.main.querySelector('h1'));
  expect(h.announcements.mock.calls.filter(c => c[1] === `${id(2)} is no longer in this view.`)).toHaveLength(1);
});

it('review 5 gives operation and payload definition text a wrapping rule', () => {
  const css = sourceText('ui/styles/ledger.css');
  for(const selector of ['.ledger-operation', '.ledger-payload dl', '.ledger-payload dt', '.ledger-payload dd']) {
    expect(css).toMatch(new RegExp(selector.replaceAll('.', '\\.') + '[^{}]*\\{[^}]*overflow-wrap:\\s*anywhere'));
  }
});

it('review 6 announces same-head recovery after each actual failure without duplicate success updates', async () => {
  const initial = page([event(1)], {head:5, next_after:2, has_more:true});
  const t = scripted([initial, networkError(), page([event(5)]), initial,
    networkError(), page([event(5)]), page([event(1), event(5)], {head:5, next_after:5})]);
  const h = await mount(t.transport, {}, 5); await h.ready;
  const successes = () => h.announcements.mock.calls.filter(c => c[1] === 'Ledger ready. Head 5.');
  for(let cycle=0; cycle<2; cycle++) {
    if(cycle) await h.update();
    action(h.main, 'page-events').click(); await flush();
    retry(h.main).click(); await flush();
    expect(successes()).toHaveLength(cycle+2);
  }
  await h.update();
  expect(successes()).toHaveLength(3);
});
