import { mergeConfig } from 'vitest/config';
import base from '../../../vite.config.ts';

export default mergeConfig(base, {
  test: { include: ['tests/**/*.test.ts', 'src/screens/arena/**/*.test.ts'] },
});
