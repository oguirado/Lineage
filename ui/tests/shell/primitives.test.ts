// @vitest-environment jsdom
import { it, expect, vi } from 'vitest';
import { source, host, isolateDom, accessibleName } from './helpers.ts';
isolateDom();
const load = () => source('ui/primitives.ts', ['createButton', 'createLink', 'renderStatePanel', 'formatMeasurement']);
it.each(['a'.repeat(64), 'é'.repeat(32)])('A8 accepts exact UTF-8 byte boundary %s', async name => {
  const p = await load(); expect(accessibleName(p.createButton({name, action: 'open-unit', onActivate: vi.fn()}))).toBe(name);
});
it.each(['', '   ', 'a'.repeat(65), 'é'.repeat(33)])('A8 rejects invalid name %s without truncation', async name => {
  const p = await load();
  expect(() => p.createButton({name, action: 'open-unit', onActivate: vi.fn()})).toThrow(Error);
  expect(() => p.createLink({name, action: 'open-agent', href: '#/agents'})).toThrow(Error);
});
it('A7 preserves full punctuated identities, duplicate display text and stable actions', async () => {
  const p = await load(); const parent = host(); const ids = ['unit:one["x"]', 'unit:two\\y'];
  const nodes = ids.map((id, index) => p.createButton({name: `Open unit key-${index ? 'beta' : 'alpha'}`,
    action: 'open-unit', identity: {entity: 'unit', id}, onActivate: vi.fn()}));
  parent.append(...nodes); parent.prepend(nodes[1]);
  for (const [index, node] of nodes.entries()) {
    expect(node.dataset.linId).toBe(ids[index]); expect(node.dataset.linEntity).toBe('unit');
    expect(node.dataset.linAction).toBe('open-unit');
  }
  expect(new Set(nodes.map(accessibleName)).size).toBe(2);
});
it('A9 renders hostile text literally and disabled activation is inert', async () => {
  const p = await load(); const callback = vi.fn(); const value = '<img src=x onerror="alert(1)">';
  const button = p.createButton({name: value, action: 'open-unit', disabled: true, onActivate: callback});
  host().append(button); button.click(); button.dispatchEvent(new MouseEvent('click', {bubbles: true}));
  expect(button.type).toBe('button'); expect(callback).not.toHaveBeenCalled();
  expect(button.querySelector('img')).toBeNull(); expect(accessibleName(button)).toBe(value);
  const panel = p.renderStatePanel({state: 'error', title: 'Data error', detail: value});
  expect(panel.textContent).toContain(value); expect(panel.querySelector('img')).toBeNull();
});
it.each(['javascript:alert(1)', 'data:text/html,x', 'https://invalid.example/path', '//invalid.example',
  '/safe//bad', '/safe\\bad', '/safe\npath', 'https://lineage.invalid/local'])
  ('A9 refuses unsafe link %s', async href => {
    const p = await load(); expect(() => p.createLink({name: 'Read evidence', action: 'open-task-evidence', href})).toThrow();
  });
it.each(['#/agents', 'docs/UI_GUIDE.md', '/docs/UI_GUIDE.md'])('A9 accepts local target %s', async href => {
  const p = await load(); expect(p.createLink({name: 'Read guide', action: 'open-task-evidence', href}).getAttribute('href')).toBe(href);
});
it('A12 differentiates every panel state with text and no extra live region', async () => {
  const p = await load();
  const states = ['loading','empty','no-match','ready','busy','queued','running','stalled','stale','error','completed','not-built'];
  const texts = states.map(state => {
    const node = p.renderStatePanel({state, title: 'Synthetic panel'});
    expect(node.matches('[role="status"],[role="alert"],[aria-live]')).toBe(false);
    expect(node.querySelector('[role="status"],[role="alert"],[aria-live]')).toBeNull();
    return node.textContent?.trim();
  });
  expect(texts.every(Boolean)).toBe(true); expect(new Set(texts).size).toBe(states.length);
});
it('A12 supports independently named error/retry panels', async () => {
  const p = await load(); const retry = vi.fn();
  const panel = p.renderStatePanel({state: 'error', title: 'Unavailable', detail: 'bad_op',
    regionName: 'Memory error', retryName: 'Retry Memory', retryAction: 'retry-panel', onRetry: retry});
  expect(panel.getAttribute('role')).toBe('region'); expect(accessibleName(panel)).toBe('Memory error');
  const button = panel.querySelector('button')!; expect(accessibleName(button)).toBe('Retry Memory');
  button.click(); expect(retry).toHaveBeenCalledOnce(); expect(panel.textContent).toContain('bad_op');
});
it('A28 preserves unknown measurements and actual zero', async () => {
  const {formatMeasurement} = await load();
  expect(formatMeasurement(null)).toBe('not measured'); expect(formatMeasurement(undefined)).toBe('not measured');
  expect(formatMeasurement(0)).toBe('0'); expect(formatMeasurement(12, 'ms')).toBe('12 ms');
  for (const value of [NaN, Infinity, -Infinity]) expect(() => formatMeasurement(value)).toThrow();
});
