import { configDefaults, defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    testTimeout: 15000,
    exclude: [...configDefaults.exclude, '**/dist/**', '**/cdk.out/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['lib/**/*.ts'],
      exclude: ['**/*.d.ts', '**/*.spec.ts', '**/*.test.ts'],
    },
  },
});
