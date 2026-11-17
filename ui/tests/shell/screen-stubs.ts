// A-U21R: Deterministic screen doubles isolate shell contracts from later-unit data flows.
import type { ScreenContext, ScreenModule, ScreenModuleId } from '../../src/ui/contracts.ts';
import { identityKey } from '../../src/ui/primitives.ts';

function stub(id: ScreenModuleId, title: string, copy: string): ScreenModule {
  return {id, title, mount(host, context) {
    let disposed = false;
    const heading = document.createElement('h1'); heading.tabIndex = -1;
    const identity = document.createElement('p'); identity.id = 'stub-screen-identity';
    const message = document.createElement('p'); message.textContent = copy;
    host.replaceChildren(heading, identity, message);
    function render(next: ScreenContext) {
      if (disposed || next.signal.aborted) return;
      const route = next.route;
      const selected = route.screen === 'agent' ? route.agentId : route.screen === 'bench' ? route.benchId : null;
      heading.textContent = route.screen === 'agent' ? `Agent ${identityKey('agent', route.agentId)}`
        : route.screen === 'bench' ? `Benchmark ${identityKey('bench', route.benchId)}` : title;
      identity.textContent = selected ?? ''; identity.hidden = selected === null;
      if (selected !== null) heading.setAttribute('aria-describedby', identity.id);
      else heading.removeAttribute('aria-describedby');
    }
    render(context);
    return {ready: Promise.resolve(), async update(next) {render(next);}, dispose() {disposed = true;}};
  }};
}

export const stubScreens: Readonly<Record<ScreenModuleId, ScreenModule>> = {
  agents: stub('agents', 'Agents', 'Agents: not built yet.'),
  agent: stub('agent', 'Agent', 'Agent detail: not built yet.'),
  lineage: stub('lineage', 'Lineage', 'Lineage: not built yet.'),
  arena: stub('arena', 'Arena', 'Arena: not built yet.'),
  ledger: stub('ledger', 'Ledger', 'Ledger: not built yet.'),
};
