// @vitest-environment jsdom
import { it, expect } from 'vitest';
import { source, goodShell, app, isolateDom } from './helpers.ts';
isolateDom();
const load = () => source('ui/operability.ts', ['lintOperability']);
it('A27 accepts the actual good shell without weakening its negative fixtures', async () => {
  const {lintOperability} = await load(); const {root} = await app(); expect(lintOperability(root)).toEqual([]);
});
it.each(['button','a','input','select'])('A27 flags native %s under an opaque article', async tag => {
  const {lintOperability} = await load(); const root = goodShell(); const article = document.createElement('article');
  const el = document.createElement(tag); el.setAttribute('aria-label', 'Hostile action'); el.dataset.linAction = 'open-agent';
  if (tag === 'a') el.setAttribute('href', '#/agents'); article.append(el); root.querySelector('main')!.append(article);
  expect(lintOperability(root).map((i: any) => i.code)).toContain('interactive_article');
});
it.each([
  ['clickable_non_native', '<div role="button" tabindex="0" aria-label="Imposter" data-lin-action="open-agent">Open</div>'],
  ['clickable_non_native', '<div onclick="return false" data-lin-action="open-agent">Click me</div>'],
  ['missing_name', '<button data-lin-action="open-agent"></button>'],
  ['duplicate_name', '<button data-lin-action="open-agent">Open  agent</button><button data-lin-action="create-agent"> Open agent </button>'],
  ['duplicate_name', '<button data-lin-action="open-agent">Café</button><button data-lin-action="create-agent">Café</button>'],
  ['name_too_long', `<button data-lin-action="create-agent">${'é'.repeat(33)}</button>`],
  ['bad_selector', '<button data-lin-action="open-agent-0">Open agent one</button>'],
  ['bad_selector', '<button data-lin-action="open-agent" data-lin-entity="agent" data-lin-id="0">Open agent one</button>'],
  ['bad_selector', '<button data-lin-action="open-agent" data-lin-entity="alien" data-lin-id="aurora-root">Open alien</button>'],
  ['bad_state', '<button data-lin-action="create-agent" aria-running="true">Create agent</button>'],
  ['heading_count', '<h1>Extra heading</h1>'],
])('A7 A8 A27 emits %s for its hostile DOM witness', async (code, html) => {
  const {lintOperability} = await load(); const root = goodShell(); root.querySelector('main')!.insertAdjacentHTML('beforeend', html);
  expect(lintOperability(root).map((i: any) => i.code)).toContain(code);
});
it('A27 missing landmark is a failure and allowed ARIA states remain valid', async () => {
  const {lintOperability} = await load(); const root = goodShell(); root.querySelector('nav')!.remove();
  expect(lintOperability(root).map((i: any) => i.code)).toContain('missing_landmark');
  const valid = goodShell(); const b = document.createElement('button'); b.textContent = 'Create agent'; b.dataset.linAction = 'create-agent';
  b.setAttribute('aria-disabled', 'true'); b.setAttribute('aria-expanded', 'false'); valid.querySelector('main')!.append(b);
  expect(lintOperability(valid).filter((i: any) => i.code === 'bad_state')).toEqual([]);
});
it('A7 A27 rejects ambiguous scoped tuples/actions while accepting distinct identities', async () => {
  const {lintOperability} = await load(); const root = goodShell(); const main = root.querySelector('main')!;
  const build = (id: string, name: string) => {
    const section = document.createElement('section'); section.dataset.linEntity = 'agent'; section.dataset.linId = id;
    const h = document.createElement('h2'); h.textContent = id;
    const a = document.createElement('a'); a.href = `#/agents/${id}`; a.dataset.linAction = 'open-agent'; a.textContent = name;
    section.append(h,a); return section;
  };
  main.append(build('aurora-root','Open agent aurora-root'), build('aurora-child','Open agent aurora-child'));
  expect(lintOperability(root)).toEqual([]);
  main.append(build('aurora-root','Another action name'));
  expect(lintOperability(root).map((i: any) => i.code)).toContain('bad_selector');
});
