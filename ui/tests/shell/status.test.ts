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
