// @vitest-environment jsdom
import { it, expect } from 'vitest';
import { source, host, isolateDom, accessibleName } from './helpers.ts';
isolateDom();
async function setup() {
  const {openDialog} = await source('ui/dialog.ts', ['openDialog']); const root = host();
  const trigger = document.createElement('button'); trigger.textContent = 'Open inspector';
  const fallback = document.createElement('h1'); fallback.textContent = 'Agents'; fallback.tabIndex = -1;
  root.append(trigger, fallback); const content = document.createElement('div');
  const input = document.createElement('input'); input.setAttribute('aria-label', 'Draft value'); input.value = 'recoverable draft'; content.append(input);
  return {openDialog, root, trigger, fallback, content, input};
}
it('A11 names a native modal, contains focus, refuses nesting and restores the invoker', async () => {
  const x = await setup(); x.trigger.focus(); const d = x.openDialog({name: 'Synthetic inspector', content: x.content,
    trigger: x.trigger, fallback: x.fallback, host: x.root});
  try {
    expect(d.element).toBeInstanceOf(HTMLDialogElement); expect(accessibleName(d.element)).toBe('Synthetic inspector');
    expect(d.element.contains(document.activeElement)).toBe(true);
    expect(() => x.openDialog({name: 'Second modal', content: document.createElement('div'), trigger: x.trigger, fallback: x.fallback})).toThrow(Error);
    const enabled = Array.from((d.element as HTMLDialogElement).querySelectorAll<HTMLElement>('input:not(:disabled),button:not(:disabled),select:not(:disabled),a[href]'));
    enabled.at(-1)!.focus(); enabled.at(-1)!.dispatchEvent(new KeyboardEvent('keydown', {key: 'Tab', bubbles: true, cancelable: true}));
    expect(document.activeElement).toBe(enabled[0]);
    enabled[0].dispatchEvent(new KeyboardEvent('keydown', {key: 'Tab', shiftKey: true, bubbles: true, cancelable: true}));
    expect(document.activeElement).toBe(enabled.at(-1));
    d.element.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));
    expect(document.activeElement).toBe(x.trigger); expect(x.input.value).toBe('recoverable draft');
  } finally { d.close(); }
});
it('A11 A29 close control restores fallback after trigger removal and releases singleton/listeners', async () => {
  const x = await setup(); const options = {name: 'Synthetic inspector', content: x.content, trigger: x.trigger, fallback: x.fallback, host: x.root};
  const d = x.openDialog(options); x.trigger.remove();
  const close = Array.from((d.element as HTMLDialogElement).querySelectorAll('button')).find(b => accessibleName(b) === 'Close dialog');
  expect(close).toBeDefined(); close!.click(); expect(document.activeElement).toBe(x.fallback);
  const reopened = x.openDialog(options); reopened.close();
  const before = document.activeElement;
  d.element.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
  expect(document.activeElement).toBe(before); expect(x.input.value).toBe('recoverable draft');
});
