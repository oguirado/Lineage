import { it, expect } from 'vitest';
import { agent, statuses, workflows } from './fixtures.ts';
import { Service, action, boot, card, enter, expectReads, flush, ids, isolate } from './helpers.ts';
isolate();

it.each(workflows)('A5 workflow %s uses only the public server filter and resets its cursor', async workflow => {
  const service=new Service();service.records=[agent('chosen-root',{workflow})];const h=await boot({service});
  await enter(h.host,'filter-agent-workflow',workflow);expectReads(h);expect(ids(h)).toEqual(['chosen-root']);
  const call=service.for('agent_list').at(-1)!;expect(call.args.workflow).toBe(workflow);expect(call.args.after).toBeUndefined();
  expect(Object.keys(call.args).every(k => ['workflow','language','status','include_retired','after','limit','agent'].includes(k))).toBe(true);
  expect(call.options.mutation).toBe(false);expect(h.navigate).toHaveBeenCalledWith(expect.objectContaining({screen:'agents',query:expect.objectContaining({workflow})}));
});
it.each(statuses)('A5 A6 status %s remains effective with retirement unchecked', async status => {
  const service=new Service();service.records=[agent('chosen-root',{status})];const h=await boot({service,query:{status,retired:'false'}});
  card(h,'chosen-root');expect(service.for('agent_list').at(-1)!.args.status).toBe(status);
  expect(action<HTMLInputElement>(h.host,'include-retired').checked).toBe(false);expect(h.service.mutations()).toHaveLength(0);
});
it('A5 query matches NFC names and full IDs with fixed lowercase semantics', async () => {
  const service=new Service();service.records=[agent('accent-root',{display_name:'Ångström'}),agent('other-root',{display_name:'Different'})];const h=await boot({service});
  await enter(h.host,'filter-agent-query','A\u030aNG');expect(ids(h)).toEqual(['accent-root']);
  await enter(h.host,'filter-agent-query','OTHER-ROOT');expect(ids(h)).toEqual(['other-root']);
  expect(service.for('agent_list').every(c => !Object.hasOwn(c.args,'q')&&!Object.hasOwn(c.args,'sort'))).toBe(true);
  expect(service.mutations()).toHaveLength(0);
});
it('A5 language is an open Unicode string retained even when no page contains it', async () => {
  const language='日本語 / dialect';const h=await boot({query:{language}});const selector=action<HTMLSelectElement>(h.host,'filter-agent-language');
  expect(selector.value).toBe(language);expect(Array.from(selector.options).some(o => o.value===language)).toBe(true);
  expect(h.service.for('agent_list').at(-1)!.args.language).toBe(language);expect(h.host.textContent).toContain('No matching agents. Clear filters to see all loaded records.');
});
it.each([
  ['id-asc',['alpha-root','beta-root','gamma-root']],['id-desc',['gamma-root','beta-root','alpha-root']],['name-asc',['beta-root','gamma-root','alpha-root']],
] as const)('A5 A9 %s order uses full-ID tie breaks without host collation', async (sort,expected) => {
  const service=new Service();service.records=[agent('alpha-root',{display_name:'Zulu'}),agent('gamma-root',{display_name:'Alpha'}),agent('beta-root',{display_name:'Alpha'})];
  const h=await boot({service});await enter(h.host,'sort-agents',sort);expect(ids(h)).toEqual(expected);
  await h.refresh();expect(ids(h)).toEqual(expected);expect(service.mutations()).toHaveLength(0);
});
it('A5 invalid sort resets only sort and warns while valid q and workflow survive', async () => {
  const h=await boot({query:{q:'Shared',workflow:'develop',sort:'rank-fitness'}});
  expect(action<HTMLInputElement>(h.host,'filter-agent-query').value).toBe('Shared');expect(action<HTMLSelectElement>(h.host,'filter-agent-workflow').value).toBe('develop');
  expect(action<HTMLSelectElement>(h.host,'sort-agents').value).toBe('id-asc');expect(h.host.textContent).toMatch(/invalid|unknown|unrecognized/iu);
  expect(ids(h)).toEqual(['alpha-root','beta-root']);
});
it.each([
  'not-json','["alpha-root","beta-root","gamma-root"]','["alpha-root","alpha-root"]','["beta-root","alpha-root"]','["../escape","beta-root"]','[1,"beta-root"]','{"agent_id":"alpha-root"}',
])('A5 Amendment B invalid compare %s resets the whole field without losing q', async compare => {
  const h=await boot({query:{q:'Shared',compare}});expect(action<HTMLInputElement>(h.host,'filter-agent-query').value).toBe('Shared');
  expect(action<HTMLButtonElement>(h.host,'compare-agents').disabled).toBe(true);
  expect(Array.from(h.host.querySelectorAll<HTMLInputElement>('[data-lin-action="compare-agent"]')).every(el => !el.checked)).toBe(true);
  expect(h.host.textContent).toMatch(/compare|invalid|unknown/iu);expect(h.service.mutations()).toHaveLength(0);
});
it.each([['workflow','train'],['status','winner'],['retired','yes']])('A5 invalid %s resets its own field and leaves valid query untouched', async (field,value) => {
  const h=await boot({query:{q:'Shared',[field]:value}});expect(action<HTMLInputElement>(h.host,'filter-agent-query').value).toBe('Shared');expect(ids(h)).toEqual(['alpha-root','beta-root']);
  expect(h.host.textContent).toMatch(/invalid|unknown|unrecognized/iu);expect(h.service.mutations()).toHaveLength(0);
});
it('A5 unknown and prototype-sensitive query keys cannot alter objects or become tool arguments', async () => {
  const query=JSON.parse('{"q":"Shared","surprise":"passive","__proto__":"poison"}');const h=await boot({query});
  expect(action<HTMLInputElement>(h.host,'filter-agent-query').value).toBe('Shared');expect(h.host.textContent).toMatch(/unknown|unrecognized|ignored/iu);
  expect(({} as any).poison).toBeUndefined();expect(h.service.for('agent_list').every(c => !Object.hasOwn(c.args,'__proto__')&&!Object.hasOwn(c.args,'surprise'))).toBe(true);
});
it('A6 retirement defaults exclude retired agents and explicit include-retired opts in', async () => {
  const h=await boot();expect(ids(h)).toEqual(['alpha-root','beta-root','gamma-root']);const checkbox=action<HTMLInputElement>(h.host,'include-retired');checkbox.click();await flush();
  expect(card(h,'retired-root')).toBeDefined();expect(h.service.for('agent_list').at(-1)!.args.include_retired).toBe(true);expect(h.service.mutations()).toHaveLength(0);
});
it('A6 clear resets filters and sort but retains canonical comparison IDs until separate clear', async () => {
  const compare='["alpha-root","beta-root"]';const h=await boot({query:{q:'hidden',workflow:'review',language:'python',status:'shadow',retired:'true',sort:'id-desc',compare}});
  action(h.host,'clear-agent-filters','Clear agent filters').click();await flush();expect(ids(h)).toEqual(['alpha-root','beta-root','gamma-root']);
  expect(h.navigate).toHaveBeenLastCalledWith({screen:'agents',query:{compare}});expect(action<HTMLButtonElement>(h.host,'compare-agents').disabled).toBe(false);
  action(h.host,'clear-comparison','Clear compared agents').click();await flush();expect(h.navigate).toHaveBeenLastCalledWith({screen:'agents',query:{}});
  expect(h.service.mutations()).toHaveLength(0);
});
it('A6 URL filter edits contain no cursor, operation identity, token or saved draft', async () => {
  const h=await boot();await enter(h.host,'filter-agent-query','Shared');await enter(h.host,'sort-agents','name-asc');
  for(const [route] of h.navigate.mock.calls) expect(Object.keys(route.query).every(k => ['q','workflow','language','status','retired','sort','compare'].includes(k))).toBe(true);
  expect(h.service.mutations()).toHaveLength(0);
});
it('A8 server filter changes abandon the previous page cursor', async () => {
  const service=new Service();service.overrides.set('agent_list',a => a.workflow?{agents:[agent('review-root',{workflow:'review'})],next_after:null,head:7}:{agents:[agent()],next_after:'alpha-root',head:7});
  const h=await boot({service});action(h.host,'page-agents');await enter(h.host,'filter-agent-workflow','review');
  expect(service.for('agent_list').at(-1)!.args.after).toBeUndefined();expect(ids(h)).toEqual(['review-root']);expect(h.host.querySelector('[data-lin-action="page-agents"]')).toBeNull();
});
it('A11 history restores hidden comparison identities independently of visible rows', async () => {
  const h=await boot({query:{q:'nothing',compare:'["alpha-root","beta-root"]'}});expect(ids(h)).toEqual([]);expect(action<HTMLButtonElement>(h.host,'compare-agents').disabled).toBe(false);
  await h.update({q:'Shared',sort:'id-desc',compare:'["alpha-root","beta-root"]'});
  for(const id of ['alpha-root','beta-root']) expect(action<HTMLInputElement>(card(h,id),'compare-agent').checked).toBe(true);
});
