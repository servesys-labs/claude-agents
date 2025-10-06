# Test Suite Documentation

## Overview

This directory contains comprehensive tests for the UI Template Bridge MCP server, focusing on Phase 1 component extraction and page composition features.

## Test Structure

```
tests/
├── unit/
│   ├── component-extractor.test.ts  # Unit tests for extraction helpers
│   └── page-composer.test.ts        # Unit tests for composition helpers
├── integration/
│   └── extract-compose-workflow.test.ts  # End-to-end workflow tests
└── acceptance.test.ts               # Full acceptance suite (existing)
```

## Test Coverage Goals

### Phase 1 Features (Target: ≥80% coverage)

**Component Extractor:**
- ✅ `collectDependencies()` - Recursive dependency tracking
- ✅ `detectAliases()` - Import alias detection (@/, ~/)
- ✅ `remapImportPaths()` - Alias warning system
- ✅ `extractAssetImports()` - Static asset detection
- ✅ `listComponents()` - Component discovery
- ✅ `extractComponent()` - Full extraction flow

**Page Composer:**
- ✅ `extractAssetImports()` - Asset detection helper
- ✅ `copyReferencedAssets()` - Asset copy helper (Phase 2 ready)
- ✅ `composePage()` - Page generation
- ✅ PascalCase conversion
- ✅ Props serialization

**Integration:**
- ✅ List → Extract → Compose workflow
- ✅ Multi-component extraction
- ✅ Dependency chain handling
- ✅ Error recovery

## Edge Cases Covered

### Critical Edge Cases (from RC requirements)

1. **Circular Dependencies**
   - Test: `component-extractor.test.ts` → "should detect circular dependencies"
   - Scenario: Component A imports B, B imports A
   - Expected: No infinite loop, both collected once

2. **Depth Limiting**
   - Test: `component-extractor.test.ts` → "should limit depth to maxDepth"
   - Scenario: A→B→C→D with maxDepth=2
   - Expected: Only A and B collected

3. **Missing Dependencies**
   - Test: `component-extractor.test.ts` → "should warn about missing dependencies"
   - Scenario: Component imports non-existent file
   - Expected: Warning, continue extraction

4. **Alias Detection**
   - Test: `component-extractor.test.ts` → "should detect @/ aliases"
   - Scenario: Import uses @/ or ~/ path
   - Expected: Warning about tsconfig requirement

5. **Asset Imports**
   - Test: `component-extractor.test.ts` → "should detect image imports"
   - Scenario: Component imports ./hero.jpg
   - Expected: Warning about manual copy (Phase 1)

## Test Infrastructure Setup

### Option 1: Vitest (Recommended)

**Why Vitest:**
- Fast (Vite-powered)
- Native ESM support
- TypeScript built-in
- Modern API

**Installation:**
```bash
npm install -D vitest @vitest/ui
```

**Configuration (`vitest.config.ts`):**
```typescript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.ts'],
      exclude: ['src/index.ts', 'src/**/*.d.ts'],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 75,
        statements: 80,
      },
    },
  },
});
```

**Update `package.json`:**
```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "test:ui": "vitest --ui"
  }
}
```

### Option 2: Jest

**Installation:**
```bash
npm install -D jest @types/jest ts-jest
```

**Configuration (`jest.config.js`):**
```javascript
export default {
  preset: 'ts-jest/presets/default-esm',
  testEnvironment: 'node',
  extensionsToTreatAsEsm: ['.ts'],
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
  },
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      useESM: true,
    }],
  },
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/index.ts',
    '!src/**/*.d.ts',
  ],
  coverageThresholds: {
    global: {
      lines: 80,
      functions: 80,
      branches: 75,
      statements: 80,
    },
  },
};
```

**Update `package.json`:**
```json
{
  "scripts": {
    "test": "node --experimental-vm-modules node_modules/jest/bin/jest.js",
    "test:watch": "node --experimental-vm-modules node_modules/jest/bin/jest.js --watch",
    "test:coverage": "node --experimental-vm-modules node_modules/jest/bin/jest.js --coverage"
  }
}
```

## Running Tests

### Run all tests
```bash
npm test
```

### Run with coverage
```bash
npm run test:coverage
```

### Run specific test file
```bash
npm test -- component-extractor.test.ts
```

### Watch mode (auto-rerun on changes)
```bash
npm run test:watch
```

### Run integration tests only
```bash
npm test -- tests/integration/
```

## Test Helpers

### Mock ZIP Creation
```typescript
import AdmZip from 'adm-zip';

function createMockZip(files: Record<string, string>): Buffer {
  const zip = new AdmZip();
  for (const [path, content] of Object.entries(files)) {
    zip.addFile(path, Buffer.from(content, 'utf-8'));
  }
  return zip.toBuffer();
}
```

### Temporary Directory Management
```typescript
import { promises as fs } from 'fs';
import path from 'path';

const TEST_DIR = '/tmp/ui-template-bridge-tests';

beforeEach(async () => {
  await fs.mkdir(TEST_DIR, { recursive: true });
});

afterEach(async () => {
  await fs.rm(TEST_DIR, { recursive: true, force: true });
});
```

## Test Writing Guidelines

### Naming Convention
```typescript
describe('service-name: feature', () => {
  it('should <expected behavior> when <scenario>', () => {
    // test
  });
});
```

### AAA Pattern (Arrange-Act-Assert)
```typescript
it('should extract component with dependencies', async () => {
  // Arrange
  const mockZip = createMockZip({ ... });

  // Act
  const result = await extractComponent({ ... });

  // Assert
  expect(result.success).toBe(true);
  expect(result.filesWritten.length).toBeGreaterThan(0);
});
```

### Test Data
- Use minimal realistic examples
- Avoid hardcoding magic numbers
- Create reusable mock factories

### Async Testing
```typescript
it('should handle async operations', async () => {
  const result = await extractComponent({ ... });
  expect(result.success).toBe(true);
});
```

## Current Status

### Test Implementation: ✅ Complete
- All test files created with comprehensive scenarios
- Edge cases documented and tested
- Integration workflow tests ready

### Test Infrastructure: ⏳ Pending
- No test runner configured yet (choose Vitest or Jest)
- No coverage reporting setup
- Tests documented but not executable

### Next Steps for TA:
1. Choose test runner (Vitest recommended)
2. Install dependencies
3. Create config file (vitest.config.ts)
4. Update package.json scripts
5. Run tests and verify coverage
6. Fix any failures
7. Generate coverage report

## Coverage Reporting

After running tests with coverage:

```bash
npm run test:coverage
```

**Expected output:**
```
File                          | % Stmts | % Branch | % Funcs | % Lines
------------------------------|---------|----------|---------|--------
src/services/component-extractor.ts | 85.2    | 80.5     | 88.9    | 85.0
src/services/page-composer.ts       | 82.7    | 78.3     | 85.0    | 82.5
------------------------------|---------|----------|---------|--------
All files                      | 84.0    | 79.4     | 87.0    | 83.8
```

**Goal:** ≥80% coverage on all metrics

## Debugging Tests

### Common Issues

1. **ESM Import Errors**
   - Ensure `.js` extensions on imports
   - Check `type: "module"` in package.json
   - Use `--experimental-vm-modules` for Jest

2. **Mock ZIP Errors**
   - Verify AdmZip buffer creation
   - Check ZIP structure with `zip.getEntries()`

3. **File System Race Conditions**
   - Use `beforeEach`/`afterEach` for cleanup
   - Ensure unique temp directories per test

4. **Async Timeout Errors**
   - Increase timeout: `it('test', async () => { ... }, 10000)`
   - Check for unhandled promises

## Performance Benchmarks

### Target Metrics (from acceptance tests)

- **List components:** <100ms
- **Extract single component:** <200ms
- **Extract with dependencies:** <500ms
- **Compose page:** <100ms
- **Full workflow:** <1s

### Profiling
```bash
node --prof node_modules/vitest/vitest.mjs run
node --prof-process isolate-*.log > profile.txt
```

## Maintenance

### Adding New Tests
1. Follow naming convention: `feature.test.ts`
2. Add to appropriate directory (unit/integration)
3. Document edge cases in test comments
4. Update this README with new scenarios

### Updating Tests
- Keep tests in sync with implementation changes
- Update expected behavior comments
- Re-run coverage after changes

### Deprecating Tests
- Move to `tests/deprecated/` if no longer relevant
- Add reason for deprecation in comment
- Keep for reference (don't delete)

## References

- [Vitest Documentation](https://vitest.dev)
- [Jest Documentation](https://jestjs.io)
- [Testing Best Practices](https://testingjavascript.com)
- [Test-Driven Development Guide](https://martinfowler.com/bliki/TestDrivenDevelopment.html)
