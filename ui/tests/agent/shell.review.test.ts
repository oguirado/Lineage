// @vitest-environment jsdom
// A-U23: exercise integrated U21 lifecycle APIs with valid domain fixtures instead of the retired placeholder.
import {expect, it} from 'vitest';
import {startApp} from '../../src/main.ts';
import {createStore} from '../../src/store.ts';
import {screen} from '../../src/screens/agent/index.ts';
import type {Route} from '../../src/ui/contracts.ts';
import {lintOperability} from '../../src/ui/operability.ts';
import {OWNER, constitution} from './fixtures.ts';
import {deferred, flush, isolate, refuse, Service} from './helpers.ts';

isolate();

it('h1 A4 screen waits for the integrated store first prefix and complete detail fold', async () => {
 const service = new Service(); const firstPage = deferred();
 service.transport.events.mockImplementationOnce(() => firstPage.promise);
 const route: Route = {screen: 'agent', agentId: OWNER, query: {}};
 const store = createStore(service.transport, route);
 const host = document.createElement('main'); host.dataset.linScreen = 'agent'; document.body.append(host);
 const controller = new AbortController();
 const mounted = screen.mount(host, {route, store, transport: service.transport, signal: controller.signal, navigate: () => {}, announce: () => {}});
 let settled = false; void mounted.ready.then(() => {settled = true;}, () => {settled = true;});
 try {
  const refreshing = store.refresh(); await flush();
  expect(settled).toBe(false);
  expect(service.calls('agent_get')).toHaveLength(0);
  firstPage.resolve(service.page(service.ledger)); await refreshing; await mounted.ready;
  expect(store.getState().phase).toBe('ready');
  expect(store.getState().head).toBe(service.head);
  expect(host.textContent).toContain(constitution.trim());
  expect(host.querySelectorAll('h1')).toHaveLength(1);
  expect(document.documentElement.dataset.linReady).toBe('false');
 } finally {mounted.dispose(); store.dispose();}
});

it('integrated shell publishes readiness with an unambiguous reference action pair', async () => {
 const service=new Service();const root=document.createElement('div');document.body.append(root);
 const app=startApp({root,transport:service.transport,initialHash:'#/agents/'+OWNER,storage:null});
 try {
  await flush();await flush();
  expect(root.querySelector('main')?.textContent).toContain(constitution.trim());
  expect(lintOperability(root)).toEqual([]);
  expect(document.documentElement.dataset.linReady).toBe('true');
  expect(root.querySelector('output[aria-label="Screen agent '+OWNER+' ready"]')?.hasAttribute('hidden')).toBe(false);
  expect(root.querySelector('[role="progressbar"]')?.hasAttribute('hidden')).toBe(true);
 } finally {app.dispose();}
});

it.each(['unavailable', 'malformed'])('integrated shell exposes %s as terminal ready with a named alert', async failure => {
 const service = new Service();
 service.overrides.set('agent_get', () => failure === 'unavailable' ? refuse('no_agent') : {synthetic: true});
 const root = document.createElement('div'); document.body.append(root);
 const app = startApp({root, transport: service.transport, initialHash: '#/agents/' + OWNER, storage: null});
 try {
  await flush(); await flush();
  expect(app.store.getState().phase).toBe('ready');
  expect(service.calls('agent_get').length).toBeGreaterThan(0);
  expect(document.documentElement.dataset.linReady).toBe('true');
  expect(root.querySelector('main [role="alert"]')?.getAttribute('aria-label')).toMatch(/^Error:/);
  expect(root.querySelector('output[aria-label="Screen agent '+OWNER+' ready"]')?.hasAttribute('hidden')).toBe(false);
  expect(root.querySelector('main')?.textContent).not.toContain(constitution.trim());
  expect(root.textContent).toContain(failure === 'unavailable' ? 'no_agent' : 'Required field record');
 } finally {app.dispose();}
});

// A-U23: the initial-prefix wait must also settle safely on disposal or failed store initialization.
it('h1 disposal before the first prefix prevents late DOM and domain requests', async () => {
 const service = new Service(); const firstPage = deferred();
 service.transport.events.mockImplementationOnce(() => firstPage.promise);
 const root = document.createElement('div'); document.body.append(root);
 const app = startApp({root, transport: service.transport, initialHash: '#/agents/' + OWNER, storage: null});
 await flush(); app.dispose();
 firstPage.resolve(service.page(service.ledger)); await flush(); await flush();
 expect(root.childNodes).toHaveLength(0);
 expect(service.calls('agent_get')).toHaveLength(0);
 expect(document.documentElement.dataset.linReady).toBe('false');
});

it('h1 a failed initial store read cannot supply an acknowledged prefix', async () => {
 const service = new Service();
 service.transport.events.mockRejectedValueOnce(Error('Synthetic initial cursor unavailable'));
 const root = document.createElement('div'); document.body.append(root);
 const app = startApp({root, transport: service.transport, initialHash: '#/agents/' + OWNER, storage: null});
 try {
  await flush(); await flush();
  expect(app.store.getState().phase).toBe('error');
  expect(app.store.getState().head).toBeNull();
  expect(document.documentElement.dataset.linReady).toBe('false');
  expect(service.calls('agent_get')).toHaveLength(0);
 } finally {app.dispose();}
});

it('shared routing keeps each selected panel ready and disposal clears only owned identity attributes',async()=>{
 const service=new Service();const root=document.createElement('div');document.body.append(root);
 const app=startApp({root,transport:service.transport,initialHash:'#/agents/'+OWNER,storage:null});
 try {
  await flush();await flush();
  for(const panel of ['memory','scorecard','runs','constitution']){
   root.querySelector<HTMLButtonElement>('[data-lin-action="show-'+panel+'"]')!.click();await flush();await flush();
   expect(root.querySelector('[data-lin-action="show-'+panel+'"]')?.getAttribute('aria-pressed')).toBe('true');
   expect(document.documentElement.dataset.linReady).toBe('true');
   expect(root.querySelectorAll('output[aria-label="Screen agent '+OWNER+' ready"]')).toHaveLength(1);
  }
  root.querySelector<HTMLAnchorElement>('[data-lin-action="nav-lineage"]')!.click();await flush();await flush();
  const main=root.querySelector('main')!;expect(main.dataset.linEntity).toBeUndefined();expect(main.dataset.linId).toBeUndefined();
  expect(document.documentElement.dataset.linReady).toBe('true');
 } finally {app.dispose();}
});
