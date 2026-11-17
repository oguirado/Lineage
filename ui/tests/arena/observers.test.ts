// @vitest-environment jsdom
import { expect, it } from 'vitest';
import { actions } from '../../src/ui/contracts.ts';
import { BENCH, Script, action, allActions, isolate, mount, nameOf, ready, record, result, runReply, status, text } from './helpers.ts';
isolate();

function prune(root: HTMLElement): HTMLElement {
  const clean = root.cloneNode(true) as HTMLElement;
  clean.querySelectorAll('article,[hidden],[inert]').forEach(node => node.remove()); return clean;
}
it('A30 clean-room article pruning preserves actual task controls and rejects an article-contained action', async () => {
  const script = new Script(); const cell = result(); script.benches.set(BENCH, status({ results: [cell] })); script.runs.set(cell.run_id, runReply(cell));
  const h = mount(script); await ready(h); const row = record(h.host, 'run', cell.run_id);
  const required = [action(row, 'inspect-bench-result'), action(row, 'open-bench-run')].map(el => nameOf(el));
  const observe = (root: HTMLElement) => allActions(root).map(el => ({
    name: nameOf(el).normalize('NFC').replace(/\s+/gu, ' ').trim(), action: el.dataset.linAction,
    identity: el.closest('[data-lin-id]')?.getAttribute('data-lin-id'),
    states: Object.fromEntries(['aria-busy', 'aria-checked', 'aria-current', 'aria-disabled', 'aria-expanded', 'aria-hidden', 'aria-pressed', 'aria-selected', 'disabled'].filter(attr => el.hasAttribute(attr)).map(attr => [attr, el.getAttribute(attr)])),
  }));
  expect(observe(prune(h.host))).toEqual(observe(h.host));
  const surviving = allActions(prune(h.host)).map(el => nameOf(el)); for (const name of required) expect(surviving).toContain(name);
  const hostile = h.host.cloneNode(true) as HTMLElement; const target = hostile.querySelector('[data-lin-action="inspect-bench-result"]')!;
  const article = document.createElement('article'); target.replaceWith(article); article.append(target);
  expect(allActions(hostile).some(el => nameOf(el) === required[0])).toBe(true);
  expect(allActions(prune(hostile)).some(el => nameOf(el) === required[0])).toBe(false);
  expect([...prune(h.host).querySelectorAll('h1,h2,h3')].some(el => text(el) === 'Task results')).toBe(true);
});

it('A28 A29 A31 public observer inventory has native named bounded identity-bearing targets (unit prerequisite)', async () => {
  const h = mount(); await ready(h);
  for (const literal of ['show-bench-rule', 'launch-benchmark', 'refresh-benchmark', 'evaluate-benchmark', 'promote-candidate']) {
    const control = action(h.host, literal); expect(control.tagName).toBe('BUTTON');
    expect(actions.has(control.dataset.linAction!)).toBe(true); expect(Buffer.byteLength(nameOf(control))).toBeLessThanOrEqual(64);
    expect(control.closest('article')).toBeNull();
  }
  expect(h.root.querySelectorAll('[role="status"]')).toHaveLength(1);
});

// These observers cannot run in jsdom. Pending is deliberate, never a PASS receipt.
it.todo('A25 EXTERNAL browser geometry contrast focus themes reduced-motion and zoom matrix');
it.todo('A28 EXTERNAL CDP pipe live seeded-home keyboard journey with journal postconditions');
it.todo('A29 EXTERNAL independent native AT-SPI document action and raw/transformed tree witnesses');
it.todo('A30 EXTERNAL capsule frame hashes route revision prune comparison and semantic postcondition');
it.todo('A31 EXTERNAL separate public-doc-only junior and Big Tech scored persona capsules');
