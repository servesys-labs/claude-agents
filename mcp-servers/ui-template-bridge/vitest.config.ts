import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  test: {
    // Enable global test APIs (describe, it, expect)
    globals: true,

    // Test environment (node for backend services)
    environment: 'node',

    // Include patterns
    include: [
      'tests/**/*.test.ts',
      'tests/**/*.spec.ts',
    ],

    // Exclude patterns
    exclude: [
      'node_modules/**',
      'dist/**',
      '.test-output/**',
    ],

    // Coverage configuration
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      reportsDirectory: './coverage',

      // Files to include in coverage
      include: [
        'src/**/*.ts',
      ],

      // Files to exclude from coverage
      exclude: [
        'src/index.ts', // MCP entry point (integration tested)
        'src/**/*.d.ts', // Type definitions
        'src/types.ts', // Type-only file
      ],

      // Coverage thresholds (Phase 1 goal: ≥80%)
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 75, // slightly lower for branch coverage
        statements: 80,
      },

      // Fail if coverage falls below thresholds
      skipFull: false,
      all: true,
    },

    // Test timeout (10s for integration tests)
    testTimeout: 10000,

    // Hook timeout
    hookTimeout: 10000,

    // Retry failed tests (helps with flaky tests)
    retry: 1,

    // Parallel execution
    threads: true,
    maxThreads: 4,

    // Reporter
    reporters: ['default', 'verbose'],

    // Alias resolution (match tsconfig paths)
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
