# Test Setup Instructions

## Quick Start (10 minutes)

### 1. Install Test Dependencies

```bash
# Install Vitest and coverage tools
npm install -D vitest @vitest/ui @vitest/coverage-v8

# Install type definitions (if needed)
npm install -D @types/node
```

### 2. Verify Configuration

The following files should already exist:
- ✅ `vitest.config.ts` - Vitest configuration
- ✅ `tests/unit/component-extractor.test.ts` - Unit tests for extraction
- ✅ `tests/unit/page-composer.test.ts` - Unit tests for composition
- ✅ `tests/unit/bug-reproductions.test.ts` - Bug reproduction tests
- ✅ `tests/integration/extract-compose-workflow.test.ts` - Integration tests
- ✅ `tests/acceptance.test.ts` - Existing acceptance tests

### 3. Update package.json Scripts

Add these scripts to your `package.json`:

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

### 4. Run Tests

```bash
# Run all tests once
npm test

# Run tests in watch mode (auto-rerun on changes)
npm run test:watch

# Run with coverage report
npm run test:coverage

# Run with interactive UI
npm run test:ui
```

## Expected Initial Results

### Phase 1: Setup Validation

After installation, run `npm test` to verify setup:

**Expected Output:**
```
✓ tests/unit/component-extractor.test.ts (10 tests)
✓ tests/unit/page-composer.test.ts (12 tests)
✓ tests/unit/bug-reproductions.test.ts (8 tests)
✓ tests/integration/extract-compose-workflow.test.ts (8 tests)

Test Files  4 passed (4)
Tests  38 passed (38)
Duration  1.23s
```

### Phase 2: Coverage Validation

Run `npm run test:coverage`:

**Expected Coverage (Target: ≥80%):**
```
----------------------|---------|---------|---------|---------|
File                  | % Stmts | % Branch| % Funcs | % Lines |
----------------------|---------|---------|---------|---------|
component-extractor.ts|   85.2  |   80.5  |   88.9  |   85.0  |
page-composer.ts      |   82.7  |   78.3  |   85.0  |   82.5  |
----------------------|---------|---------|---------|---------|
All files             |   84.0  |   79.4  |   87.0  |   83.8  |
----------------------|---------|---------|---------|---------|
```

## Troubleshooting

### Issue 1: ESM Import Errors

**Error:**
```
Cannot find module './component-extractor.js'
```

**Fix:**
1. Ensure all imports use `.js` extension (TypeScript ESM requirement)
2. Verify `"type": "module"` in `package.json`
3. Check `tsconfig.json` has `"module": "ESNext"`

### Issue 2: Mock ZIP Not Found

**Error:**
```
Template not found: test-template
```

**Fix:**
The tests use internal mock functions. If template cache integration is needed:

```typescript
// In test setup
import { registerMockTemplate } from '../helpers/mock-template-cache';

beforeAll(async () => {
  await registerMockTemplate('test-template', mockZipBuffer);
});
```

### Issue 3: Coverage Below Threshold

**Error:**
```
ERROR: Coverage for lines (78%) does not meet threshold (80%)
```

**Fix:**
1. Review uncovered lines: `open coverage/index.html`
2. Add tests for missing scenarios
3. Temporarily lower threshold in `vitest.config.ts` (not recommended)

### Issue 4: Timeout Errors

**Error:**
```
Test timeout of 10000ms exceeded
```

**Fix:**
1. Increase timeout in specific test:
   ```typescript
   it('slow test', async () => { ... }, 20000); // 20s timeout
   ```

2. Or globally in `vitest.config.ts`:
   ```typescript
   testTimeout: 20000
   ```

### Issue 5: File System Permission Errors

**Error:**
```
EACCES: permission denied, mkdir '/tmp/test'
```

**Fix:**
```bash
# Ensure temp directory is writable
sudo chmod 777 /tmp
```

Or use user-specific temp directory:
```typescript
const TEST_DIR = path.join(os.tmpdir(), 'ui-template-bridge-tests');
```

## Test Execution Order

Tests run in this order (by default):

1. **Unit Tests** (fast, no external deps)
   - `component-extractor.test.ts`
   - `page-composer.test.ts`
   - `bug-reproductions.test.ts`

2. **Integration Tests** (slower, requires setup)
   - `extract-compose-workflow.test.ts`

3. **Acceptance Tests** (full system validation)
   - `acceptance.test.ts`

To run specific suites:
```bash
# Unit tests only
npm test -- tests/unit/

# Integration tests only
npm test -- tests/integration/

# Specific file
npm test -- component-extractor.test.ts

# Specific test case
npm test -- -t "should detect circular dependencies"
```

## Coverage Workflow

### Step 1: Generate Coverage Report
```bash
npm run test:coverage
```

### Step 2: Open HTML Report
```bash
# macOS
open coverage/index.html

# Linux
xdg-open coverage/index.html

# Windows
start coverage/index.html
```

### Step 3: Identify Gaps
Look for red (uncovered) lines in the report:
- **Red lines** = Not executed by any test
- **Yellow lines** = Partially covered (some branches missed)
- **Green lines** = Fully covered

### Step 4: Add Tests for Gaps
Focus on:
1. Error handling paths
2. Edge cases (empty input, null, undefined)
3. Boundary conditions (maxDepth=0, empty arrays)

### Step 5: Re-run Coverage
```bash
npm run test:coverage
```

Repeat until ≥80% coverage achieved.

## CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'

      - name: Install dependencies
        run: npm ci

      - name: Build
        run: npm run build

      - name: Run tests with coverage
        run: npm run test:coverage

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/lcov.info
          fail_ci_if_error: true
```

## Maintenance Tasks

### Weekly
- [ ] Run `npm run test:coverage` and verify ≥80%
- [ ] Review flaky tests (intermittent failures)
- [ ] Update test data if schemas change

### Monthly
- [ ] Review test execution time (goal: <5s for unit tests)
- [ ] Update mock data to match production patterns
- [ ] Audit test coverage for new features

### Per Release
- [ ] Run full acceptance test suite
- [ ] Verify all bug reproduction tests pass
- [ ] Update test documentation

## Performance Benchmarks

### Target Metrics

| Test Suite | Files | Tests | Duration |
|------------|-------|-------|----------|
| Unit       | 3     | 30    | <2s      |
| Integration| 1     | 8     | <3s      |
| Acceptance | 1     | 10    | <10s     |
| **Total**  | **5** | **48**| **<15s** |

### Profiling Slow Tests

```bash
# Run with time tracking
npm test -- --reporter=verbose

# Identify slow tests (>1s)
npm test -- --reporter=json | jq '.testResults[].assertionResults[] | select(.duration > 1000)'
```

## Next Steps

After initial setup:

1. ✅ **Run tests** - Verify all pass
2. ✅ **Check coverage** - Ensure ≥80% for Phase 1 code
3. ✅ **Review failures** - Fix any failing tests
4. ✅ **Add missing tests** - Cover gaps identified in coverage report
5. ✅ **Integrate CI** - Add to GitHub Actions workflow
6. ✅ **Document findings** - Update this file with any issues encountered

## Resources

- [Vitest Documentation](https://vitest.dev)
- [Coverage Thresholds Guide](https://vitest.dev/guide/coverage.html#coverage-thresholds)
- [Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
- [Mocking Guide](https://vitest.dev/guide/mocking.html)

## Support

If you encounter issues not covered here:

1. Check Vitest GitHub issues: https://github.com/vitest-dev/vitest/issues
2. Review test logs in `tests/logs/` (if configured)
3. Ask in project Slack/Discord
4. Update this document with solution for future reference
