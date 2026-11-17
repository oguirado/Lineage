// @vitest-environment jsdom
import { it, expect, vi } from 'vitest';
import { source, host, isolateDom } from './helpers.ts';
isolateDom();
it('A7 A10 restores punctuated full identity after reorder and announces removal', async () => {
  const k = await source('ui/keyboard.ts', ['focusMain', 'captureFocus', 'restoreFocus']);
  const root = host(); const main = document.createElement('main'); main.tabIndex = -1; root.append(main);
  const buttons = ['unit:[a]"b', 'unit:other'].map(id => {
    const button = document.createElement('button'); button.dataset.linEntity = 'unit'; button.dataset.linId = id;
    button.dataset.linAction = 'open-unit'; button.textContent = `Open ${id}`; return button;
  });
  main.append(...buttons); buttons[0].focus(); const snap = k.captureFocus(root);
  expect(snap).toEqual({action: 'open-unit', entity: 'unit', id: 'unit:[a]"b'});
  main.prepend(buttons[1]); main.focus(); k.restoreFocus(root, snap, main); expect(document.activeElement).toBe(buttons[0]);
  const announce = vi.fn(); buttons[0].remove(); k.restoreFocus(root, snap, main, announce);
  expect(document.activeElement).toBe(main); expect(announce).toHaveBeenCalledOnce();
  expect(announce.mock.calls[0][1]).toMatch(/no longer|removed/i);
});
it('A10 ambiguous identity restoration falls back instead of selecting the wrong record', async () => {
  const k = await source('ui/keyboard.ts', ['captureFocus', 'restoreFocus']); const root = host();
  const main = document.createElement('main'); main.tabIndex = -1; root.append(main);
  const node = document.createElement('button'); node.textContent = 'Open unit';
  node.dataset.linAction = 'open-unit'; node.dataset.linEntity = 'unit'; node.dataset.linId = 'unit-one';
  main.append(node); node.focus(); const snapshot = k.captureFocus(root); main.append(node.cloneNode(true));
  k.restoreFocus(root, snapshot, main, vi.fn()); expect(document.activeElement).toBe(main);
});
it('A10 focusMain supplies a programmatic target without a positive tabindex or typing interception', async () => {
  const {focusMain} = await source('ui/keyboard.ts', ['focusMain']); const main = host('main');
  focusMain(main); expect(main.contains(document.activeElement) || document.activeElement === main).toBe(true);
  expect(Array.from(main.querySelectorAll('[tabindex]')).every(e => Number(e.getAttribute('tabindex')) <= 0)).toBe(true);
  const input = document.createElement('input'); main.append(input); input.focus();
  const event = new KeyboardEvent('keydown', {key: 'a', bubbles: true, cancelable: true}); input.dispatchEvent(event);
  expect(event.defaultPrevented).toBe(false); expect(document.activeElement).toBe(input);
});
