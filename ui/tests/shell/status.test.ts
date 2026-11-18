// @vitest-environment jsdom
import { it, expect } from 'vitest';
import { source, host, own, isolateDom } from './helpers.ts';
isolateDom();
it('A21 status transitions preserve node/focus and deduplicate actual DOM writes', async () => {
  const {createStatusRegion} = await source('ui/status.ts', ['createStatusRegion']);
  const container = host(); const status = own(createStatusRegion(container)); const element = status.element;
  expect(element.getAttribute('role')).toBe('status'); expect(element.getAttribute('aria-live')).toBe('polite');
  expect(element.getAttribute('aria-atomic')).toBe('true');
  const button = document.createElement('button'); button.textContent = 'Focus witness'; container.append(button); button.focus();
  const observer = new MutationObserver(() => {}); observer.observe(element, {subtree: true, childList: true, characterData: true});
  try {
    status.announce('ready:0', 'Agents ready.'); expect(observer.takeRecords().length).toBeGreaterThan(0);
    status.announce('ready:0', 'Agents ready.'); expect(observer.takeRecords()).toEqual([]);
    status.announce('error:1', 'Agents unavailable. Retry to continue.'); expect(observer.takeRecords().length).toBeGreaterThan(0);
    expect(status.element).toBe(element); expect(document.activeElement).toBe(button);
    status.dispose(); observer.takeRecords(); status.announce('late', 'Must not announce'); expect(observer.takeRecords()).toEqual([]);
  } finally { observer.disconnect(); }
});


it.each([
  ['created:error-handler:event', 'Create agent recorded.', null, 'Create agent recorded.'],
  ['verification:1', 'Verification reported. Server detail: conflict.', null, 'Verification reported. Server detail: conflict.'],
  ['validation:agent_create:agent_id', 'Enter a valid agent ID.', 'alert', 'Error: Enter a valid agent ID.'],
  ['arena:error:bench_status', 'Error: Benchmark unavailable (bad_args).', 'alert', 'Error: Benchmark unavailable (bad_args).'],
])('R49 derives outcome severity from the announcement channel %s', async (key, text, role, name) => {
  const {createStatusRegion} = await source('ui/status.ts', ['createStatusRegion']);
  const container = host();
  const status = own(createStatusRegion(container));
  const outcome = container.querySelector<HTMLOutputElement>('output.action-outcome')!;
  const writes = new MutationObserver(() => {});
  writes.observe(outcome, {attributes: true, childList: true});
  try {
    status.announce(key, text);
    expect(outcome.hidden).toBe(false);
    expect(outcome.getAttribute('role')).toBe(role);
    expect(outcome.getAttribute('aria-label')).toBe(name);
    expect(status.element.textContent).toBe(text);
    expect(writes.takeRecords().length).toBeGreaterThan(0);
    status.announce(key, text);
    expect(writes.takeRecords()).toEqual([]);
  } finally {
    writes.disconnect();
  }
});
