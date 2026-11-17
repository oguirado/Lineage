// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest';
import { source, isolateDom, own, route, flush } from './helpers.ts';
isolateDom();
const load = () => source('router.ts', ['parseRoute', 'formatRoute', 'createRouter']);
describe('U21 routing', () => {
  it.each(['#/agents', '#/agents/aurora-root', '#/lineage', '#/arena', '#/arena/bench_01', '#/ledger'])
    ('A4 round-trips %s without asserting record existence', async hash => {
      const r = await load(); const parsed = r.parseRoute(hash);
      expect(parsed.notice).toBeNull(); expect(parsed.canonicalHash).toBe(hash);
      expect(r.formatRoute(parsed.route)).toBe(hash);
      expect(r.parseRoute(r.formatRoute(parsed.route)).route).toEqual(parsed.route);
    });
  it('A4 canonicalizes known query keys and decodes values once', async () => {
    const r = await load();
    const parsed = r.parseRoute('#/agents?sort=id&q=a%252Fb%20%26%20%C3%A9');
    expect(parsed.route.query).toEqual({sort: 'id', q: 'a%2Fb & é'});
    expect(parsed.canonicalHash).toBe('#/agents?q=a%252Fb%20%26%20%C3%A9&sort=id');
  });
  it.each(['', '#', '#/'])('A4 empty entry %s canonicalizes to Agents', async hash => {
    const {parseRoute} = await load(); const value = parseRoute(hash);
    expect(value.route).toEqual(route()); expect(value.canonicalHash).toBe('#/agents');
  });
  it.each(['#/unknown', '#/agents/', '#/agents/ab', '#/agents/Agent-root',
    '#/agents/aurora-root/extra',
    '#/agents/a%2Fb', '#/agents/%2e%2e', '#/agents/%ZZ', '#/agents/<img>',
    '#/arena/short', '#/arena/bench_01/extra', '#/arena/bench%2F01', '#/arena/bench%5C01',
    '#/arena/%2e%2e', '#/arena/bench%0001', '#/agents?q=%ZZ', '#/agents?q=one&q=two', '#/agents?q=one&%71=two', '#/agents?q=%ED%A0%80',
    '#/agents?__proto__=x', '#/agents?constructor=x', '#/agents?prototype=x'])
    ('A5 rejects hostile route %s and clears query/identity', async hash => {
      const {parseRoute} = await load(); const result = parseRoute(hash);
      expect(result.route).toEqual(route()); expect(result.canonicalHash).toBe('#/agents');
      expect(result.notice).toBe('Unknown page. Showing Agents.');
    });
  it('A4 A6 uses amended callback-first initialHash and hashchange history', async () => {
    const {createRouter} = await load(); const changes = vi.fn();
    const router = own(createRouter(changes, '#/agents/aurora-root?panel=memory'));
    expect(router.current().route.agentId).toBe('aurora-root');
    router.navigate(route('lineage')); await flush();
    expect(router.current().canonicalHash).toBe('#/lineage');
    // Replay native history notifications deterministically, without jsdom timers.
    for (const hash of ['#/agents/aurora-root?panel=memory', '#/lineage']) {
      history.replaceState(null, '', hash); window.dispatchEvent(new HashChangeEvent('hashchange'));
      expect(router.current().canonicalHash).toBe(hash);
    }
    expect(changes).toHaveBeenCalled();
    router.dispose(); const count = changes.mock.calls.length;
    history.replaceState(null, '', '#/ledger'); window.dispatchEvent(new HashChangeEvent('hashchange'));
    expect(changes).toHaveBeenCalledTimes(count);
  });
  it('A5 ignores unknown query fields with a visible notice under K0', async () => {
    const {parseRoute} = await load(); const parsed = parseRoute('#/agents?mystery=%3Cimg%3E');
    expect(parsed.route.query).not.toHaveProperty('mystery'); expect(parsed.notice).toBeTruthy();
    expect(({} as any).polluted).toBeUndefined();
  });
});
