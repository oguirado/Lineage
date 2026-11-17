// @vitest-environment jsdom
import { it, expect } from 'vitest';
import { existsSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { root, text, json, moduleAt } from './helpers.ts';
it('A1 A30 declares only supplied tooling and the prescribed relocatable scripts', () => {
  const pkg = json('ui/package.json');
  expect(pkg.scripts).toMatchObject({dev: 'vite', build: 'vite build', typecheck: 'tsc --noEmit', test: 'vitest run'});
  const dependencies = {...pkg.dependencies, ...pkg.devDependencies};
  expect(Object.keys(dependencies).every(name => ['typescript','vite','vitest','jsdom'].includes(name))).toBe(true);
  for (const name of Object.keys(dependencies)) expect(existsSync(resolve(root, 'node_modules', name, 'package.json'))).toBe(true);
  for (const file of ['ui/package-lock.json','ui/pnpm-lock.yaml','ui/yarn.lock','ui/vitest.config.ts'])
    expect(existsSync(resolve(root, file)), `${file} is outside U21 configuration contract`).toBe(false);
  expect(JSON.stringify(pkg)).not.toMatch(/file:|workspace:|(?:home|Users)\//u);
});
it('A1 A30 Vite config uses jsdom, discovers later-screen tests and builds to dist', async () => {
  const {default: exported} = await moduleAt('ui/vite.config.ts', ['default']);
  const config = typeof exported === 'function' ? await exported({command: 'serve', mode: 'test', isSsrBuild: false, isPreview: false}) : await exported;
  expect(config.test.environment).toBe('jsdom'); expect(config.test.include).toContain('tests/**/*.test.ts');
  expect(config.test.include.every((glob: string) => !glob.startsWith('tests/shell/'))).toBe(true);
  expect(config.build.outDir).toBe('dist');
});
it('A1 tsconfig enables strict DOM/JSON/extension imports and includes source plus tests', () => {
  const path = resolve(root, 'ui/tsconfig.json'); text('ui/tsconfig.json');
  // The supplied TypeScript CLI is the public interface; no compiler-library API is assumed.
  const result = spawnSync(resolve(root,'node_modules/.bin/tsc'), ['--showConfig','--project',path],
    {cwd: resolve(root,'ui'), encoding: 'utf8', timeout: 3000});
  expect(result.status, result.stderr || result.stdout).toBe(0);
  const parsed = JSON.parse(result.stdout); const o = parsed.compilerOptions;
  expect(o).toMatchObject({strict: true, noEmit: true, resolveJsonModule: true, allowImportingTsExtensions: true});
  expect(String(o.moduleResolution).toLowerCase()).toBe('bundler'); expect(o.lib.map((x: string) => x.toLowerCase())).toContain('dom');
  const files = parsed.files.map((file: string) => resolve(root,'ui',file));
  expect(files).toContain(resolve(root, 'ui/tests/shell/config.test.ts'));
  expect(files.some((file: string) => file.includes('/ui/src/'))).toBe(true);
});
it('A1 entry declares English, false readiness, metadata, empty token slot and module entry', () => {
  const doc = new DOMParser().parseFromString(text('ui/index.html'), 'text/html');
  expect(doc.documentElement.lang).toBe('en'); expect(doc.documentElement.dataset.linReady).toBe('false');
  expect(doc.querySelector('#app')).not.toBeNull(); expect(doc.title.trim()).not.toBe('');
  expect(doc.querySelector('meta[name="viewport"]')?.getAttribute('content')).toMatch(/width=device-width/u);
  expect(doc.querySelector('meta[name="lineage-session-token"]')?.getAttribute('content')).toBe('');
  expect(doc.querySelector('script[type="module"]')?.getAttribute('src')).toMatch(/(?:^|\/)src\/main\.ts$/u);
  const main = text('ui/src/main.ts');
  for (const sheet of ['tokens.css','base.css','shell.css']) expect(main).toContain(sheet);
});
it('A1 authored UI surface is confined and publishable without extra configuration', () => {
  text('ui/package.json');
  const allowed = new Set(['package.json','tsconfig.json','vite.config.ts','index.html',
    'src/main.ts','src/router.ts','src/transport.ts','src/store.ts','src/screens/index.ts',
    ...['contracts','shell','primitives','status','keyboard','dialog','operability'].map(n => `src/ui/${n}.ts`),
    ...['agents','agent','lineage','arena','ledger'].map(n => `src/screens/${n}/index.ts`),
    // A-U21R: Later screen units own these exact styles as well as their screen subtrees.
    ...['tokens','base','shell','agents','agent','lineage','arena','ledger'].map(n => `styles/${n}.css`)]);
  // A-U21R: Permit nested files only under the five assigned K0 screen directories.
  const allowedPath = (path: string) => allowed.has(path) ||
    (/^src\/screens\/(?:agents|agent|lineage|arena|ledger)\/[^\\]+$/u.test(path) &&
      path.split('/').every(segment => segment !== '' && segment !== '.' && segment !== '..'));
  // A-U21R: Discriminating controls preserve confinement outside those explicit handoff surfaces.
  for (const screen of ['agents','agent','lineage','arena','ledger']) {
    expect(allowedPath(`src/screens/${screen}/nested/view.ts`)).toBe(true);
    expect(allowedPath(`styles/${screen}.css`)).toBe(true);
  }
  for (const path of ['src/screens/unknown/index.ts','src/screens/agents-extra/view.ts',
    'src/screens/agents/../escape.ts','src/screens/agents/nested/../../escape.ts',
    'src/extra.ts','src/ui/extra.ts','styles/extra.css','extra.config.ts'])
    expect(allowedPath(path), `Unassigned authored ui/${path}`).toBe(false);
  function walk(dir: string, prefix = '') {
    for (const entry of readdirSync(resolve(root,'ui',dir), {withFileTypes:true})) {
      const path = [prefix,entry.name].filter(Boolean).join('/');
      if (path === 'tests' || path === 'dist' || path === 'node_modules') continue;
      if (entry.isDirectory()) walk([dir,entry.name].filter(Boolean).join('/'), path);
      else {
        // A-U21R: Keep the authored-file rejection and publication scan for every allowed screen file.
        expect(allowedPath(path), `Unexpected authored ui/${path}`).toBe(true);
        expect(text(`ui/${path}`)).not.toMatch(/(?:\/(?:home|Users)\/[^\s'"<>]+)|(?:[A-Za-z]:\\Users\\)/u);
      }
    }
  }
  walk('');
});
