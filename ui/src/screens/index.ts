import type { Route, ScreenModule, ScreenModuleId } from '../ui/contracts.ts';
import { screen as agents } from './agents/index.ts';
import { screen as agent } from './agent/index.ts';
import { screen as lineage } from './lineage/index.ts';
import { screen as arena } from './arena/index.ts';
import { screen as ledger } from './ledger/index.ts';
export const screens:Readonly<Record<ScreenModuleId,ScreenModule>> = {agents,agent,lineage,arena,ledger};
export function getScreen(route:Route):ScreenModule {return screens[route.screen==='bench'?'arena':route.screen];}
