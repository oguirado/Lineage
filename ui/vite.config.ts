import { defineConfig } from 'vitest/config';

export default defineConfig({
  cacheDir: 'dist/.vite',
  build: { outDir: 'dist' },
  test: { environment: 'jsdom', include: ['tests/**/*.test.ts'], cache: false, fsModuleCache: false, maxWorkers: 1 },
});
