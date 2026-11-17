// @vitest-environment jsdom
import { it, expect, vi } from 'vitest';
import { source, response, descriptor, event, page, isolateDom, deferred, flush } from './helpers.ts';
isolateDom();
const load = () => source('transport.ts', ['createHttpTransport', 'createFixtureTransport', 'TransportError']);
const secret = 'synthetic-session-secret';
async function http(fetchImpl: any, sessionToken: string | null = null, timeoutMs = 100) {
  const {createHttpTransport} = await load(); return createHttpTransport({fetchImpl, sessionToken, timeoutMs});
}
const invalid = {name: 'TransportError', source: 'transport', code: 'invalid_response'};
it('A13 A33 uses K0 discovery envelope, exact URLs and one POST wrapper', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(response({tools: [descriptor]}))
    .mockResolvedValueOnce(response(page())).mockResolvedValueOnce(response({untrusted: {synthetic: true}}));
  const t = await http(fetch);
  expect(await t.tools()).toEqual([descriptor]); expect(await t.events(0)).toEqual(page());
  expect(await t.call('agent_list', {}, {mutation: false})).toEqual({synthetic: true});
  const calls = fetch.mock.calls;
  expect(String(calls[0][0])).toBe('/api/tools'); expect(calls[0][1]?.method ?? 'GET').toBe('GET');
  expect(String(calls[1][0])).toBe('/api/events?after=0&wait_ms=0');
  expect(String(calls[2][0])).toBe('/api/call'); expect(calls[2][1].method).toBe('POST');
  expect(JSON.parse(calls[2][1].body)).toEqual({tool: 'agent_list', args: {}});
  expect(new Headers(calls[2][1].headers).get('content-type')).toBe('application/json');
  for (const [, init] of calls) {
    expect(init.credentials).toBe('same-origin'); expect(init.redirect).toBe('error');
    expect(new Headers(init.headers).has('Origin')).toBe(false);
  }
});
it('A13 passes a bounded long-poll cursor explicitly', async () => {
  const fetch = vi.fn(async (_url: any, _init: any) => response(page([], {head: 7, next_after: 7})));
  const t = await http(fetch); await t.events(7, {waitMs: 30});
  expect(String(fetch.mock.calls[0][0])).toBe('/api/events?after=7&wait_ms=30');
});
it.each([{ok: false}, {untrusted: {untrusted: 'passive'}}, {code: 'memory_required', ok: false}])
  ('A14 unwraps exactly once and preserves passive handler data %j', async inner => {
    const t = await http(vi.fn(async () => response({untrusted: inner})));
    expect(await t.call('agent_list', {}, {mutation: false})).toEqual(inner);
  });
it.each([{untrusted: {}, ok: false, code: 'bad_op'}, {}, {agents: []},
  {ok: false, code: 'invented'}, {ok: true}, {untrusted: Infinity},
  {untrusted: {}, extra: true}, {ok: false, code: 'bad_op', extra: true},
  {untrusted: {nested: NaN}}, {untrusted: String.fromCharCode(0xd800)},
  JSON.parse('{"untrusted":{"__proto__":{"polluted":true}}}'),
  {untrusted: {nested: {constructor: 'x'}}}, {untrusted: {prototype: 'x'}}])
  ('A14 rejects invalid wrapper or unsafe JSON %j', async body => {
    const t = await http(vi.fn(async () => response(body)));
    await expect(t.call('agent_list', {}, {mutation: false})).rejects.toMatchObject(invalid);
  });
it.each([[], {tools: [{name: 3, description: 'x', inputSchema: {}}]},
  {tools: [{name: 'x', description: 'x', inputSchema: []}]},
  {tools: [{...descriptor, extra: true}]}, {tools: [descriptor], extra: true}])
  ('A14 refuses malformed K0 descriptors %j', async body => {
    const t = await http(vi.fn(async () => response(body))); await expect(t.tools()).rejects.toMatchObject(invalid);
  });
it.each([page([], {head: -1}), page([], {head: Number.MAX_SAFE_INTEGER + 1}),
  page([], {next_after: 2, head: 1}), page([event(1)], {resync: true}),
  page([event(1, {lamport: true})]), page([event(1, {sha256: 'ABC'})]),
  page([event(1, {ts: NaN})]), page([event(1, {payload: []})]),
  page([], {has_more: 'true'}), {...page(), extra: true}])
  ('A14 rejects malformed event/cursor %j', async body => {
    const t = await http(vi.fn(async () => response(body))); await expect(t.events(0)).rejects.toMatchObject(invalid);
  });
it('A14 refuses malformed JSON with a sanitized diagnostic', async () => {
  const fetch = vi.fn(async () => ({...response(null), json: async () => {throw new SyntaxError('private raw body');},
    text: async () => '{broken'}));
  const t = await http(fetch); const error = await t.tools().catch((e: any) => e);
  expect(error).toMatchObject(invalid); expect(error.message).not.toContain('private raw body');
});
it.each(['bad_args','bad_op','stale_rev','busy','internal','conflict','no_agent','no_run','run_closed',
  'memory_required','memory_debt','forbidden_level','not_inheritable','hash_mismatch','rule_not_declared',
  'no_benchmark','heldout_forbidden','seat_not_allowed','fixture_readonly','timeout'])
  ('A15 preserves domain refusal %s and HTTP status', async code => {
    const t = await http(vi.fn(async () => response({ok: false, code}, 409)));
    await expect(t.call('agent_list', {}, {mutation: false})).rejects.toMatchObject({name: 'TransportError', source: 'domain', code, httpStatus: 409});
  });
it('A15 distinguishes network from unstructured HTTP failure without leaking token/body', async () => {
  for (const [fetch, code] of [
    [vi.fn(async () => {throw new Error(`${secret} private implementation trace`);}), 'network'],
    [vi.fn(async () => ({...response(null, 503), json: async () => {throw Error(secret);}, text: async () => secret})), 'http']
  ] as const) {
    const t = await http(fetch, secret); const error = await t.tools().catch((e: any) => e);
    expect(error).toMatchObject({source: 'transport', code});
    expect(JSON.stringify(error)).not.toContain(secret); expect(error.message).not.toContain('implementation');
  }
});
it('A15 maps timeout separately from caller abort with fake time', async () => {
  vi.useFakeTimers();
  const fetch = vi.fn((_url: any, init: any) => new Promise((_yes, no) =>
    init.signal.addEventListener('abort', () => no(new DOMException('Aborted', 'AbortError')), {once: true})));
  const t = await http(fetch); const timed = t.tools().catch((e: any) => e);
  await vi.advanceTimersByTimeAsync(101); expect(await timed).toMatchObject({source: 'transport', code: 'timeout'});
  const controller = new AbortController(); const cancelled = t.tools({signal: controller.signal}).catch((e: any) => e);
  await flush(); controller.abort(); expect(await cancelled).toMatchObject({source: 'transport', code: 'aborted'});
});
it.each([0, -1, 0.1, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1])('A15 rejects invalid timeout %s', async timeoutMs => {
  const {createHttpTransport} = await load();
  expect(() => createHttpTransport({fetchImpl: vi.fn(), sessionToken: null, timeoutMs})).toThrow();
});
it('A16 A33 sends the K0 session header, preserving args and op_id on explicit retry', async () => {
  const fetch = vi.fn().mockRejectedValueOnce(Error('lost response')).mockResolvedValue(response({untrusted: {synthetic: true}}));
  const t = await http(fetch, secret);
  const args = {agent: 'aurora-root', agent_id: 'synthetic-child', op_id: 'stable-operation'};
  await expect(t.call('agent_create', args, {mutation: true})).rejects.toMatchObject({code: 'network'});
  expect(fetch).toHaveBeenCalledOnce(); await t.call('agent_create', args, {mutation: true});
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls[0][1].body).toBe(fetch.mock.calls[1][1].body);
  const init = fetch.mock.calls[1][1]; const headers = new Headers(init.headers);
  expect(headers.get('X-Lineage-Session')).toBe(secret); expect(headers.has('X-Lineage-Session-Token')).toBe(false);
  expect(headers.has('Origin')).toBe(false); expect(init.credentials).toBe('same-origin'); expect(init.redirect).toBe('error');
  expect(JSON.parse(init.body)).toEqual({tool: 'agent_create', args});
});
it('A16 rejects missing-token mutation before fetch', async () => {
  const fetch = vi.fn(); const t = await http(fetch);
  await expect(t.call('memory_put', {agent: 'aurora-root', op_id: 'one'}, {mutation: true}))
    .rejects.toMatchObject({source: 'transport', code: 'session_required'});
  expect(fetch).not.toHaveBeenCalled();
});
export const mutations = ['agent_create','agent_clone','agent_distill','agent_cross','agent_mutate','agent_specialize',
  'agent_retire','agent_promote','skill_publish','skill_retire','memory_put','run_open','run_beat','run_close',
  'bench_declare','bench_run','bench_verdict','ledger_export','openfresnel_probe','openfresnel_spawn'];
it.each(mutations)('A16 rejects dishonest read classification for %s', async tool => {
  const fetch = vi.fn(); const t = await http(fetch, secret);
  await expect(t.call(tool, {agent: 'aurora-root', op_id: 'one'}, {mutation: false})).rejects.toMatchObject({code: 'bad_args'});
  expect(fetch).not.toHaveBeenCalled();
});
it('A16 rejects an operator actor without invoking fetch', async () => {
  const fetch = vi.fn(); const t = await http(fetch, secret);
  await expect(t.call('memory_put', {agent: 'operator', op_id: 'one'}, {mutation: true})).rejects.toBeDefined();
  expect(fetch).not.toHaveBeenCalled();
});
it('A29 pre-aborted requests issue no fetch and late cancellation stays aborted', async () => {
  const fetch = vi.fn(); const t = await http(fetch); const c = new AbortController(); c.abort();
  await expect(t.events(0, {signal: c.signal})).rejects.toMatchObject({code: 'aborted'});
  expect(fetch).not.toHaveBeenCalled();
});
