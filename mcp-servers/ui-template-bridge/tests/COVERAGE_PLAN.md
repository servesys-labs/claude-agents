# Test Coverage Plan - Phase 1

## Overview

This document maps Phase 1 features to test coverage, ensuring ≥80% coverage for all new code from IE implementation.

## Coverage Summary

| Service | Functions | Tests | Coverage Target | Status |
|---------|-----------|-------|-----------------|--------|
| component-extractor.ts | 8 | 22 | 80% | ✅ Ready |
| page-composer.ts | 4 | 16 | 80% | ✅ Ready |
| Integration | - | 10 | N/A | ✅ Ready |
| **Total** | **12** | **48** | **80%** | **✅ Ready** |

## Feature Coverage Matrix

### Component Extractor

#### 1. `collectDependencies()` - Recursive Dependency Tracking

**Lines of Code:** ~70 (lines 171-244)

**Test Coverage:**

| Scenario | Test File | Test Name | Type | Priority |
|----------|-----------|-----------|------|----------|
| Depth limiting | component-extractor.test.ts | "should limit depth to maxDepth parameter" | Unit | HIGH |
| Circular dependencies | component-extractor.test.ts | "should detect circular dependencies without infinite loop" | Unit | HIGH |
| Relative imports only | component-extractor.test.ts | "should follow relative imports only" | Unit | HIGH |
| Missing dependencies | component-extractor.test.ts | "should warn about missing dependencies" | Unit | MEDIUM |
| Extension resolution | component-extractor.test.ts | (implicit in above tests) | Unit | MEDIUM |
| Zero depth | component-extractor.test.ts | "should extract only primary component with maxDepth=0" | Unit | LOW |

**Edge Cases Covered:**
- ✅ maxDepth=0 (no dependencies)
- ✅ maxDepth=1 (direct deps only)
- ✅ maxDepth=3 (default)
- ✅ Circular A→B→A
- ✅ Missing file in chain
- ✅ Multiple extension candidates (.ts, .tsx, .js, .jsx, .css)

**Bug Reproductions:**
- BUG-001: Infinite loop on circular deps
- BUG-002: maxDepth not respected

---

#### 2. `detectAliases()` - Import Alias Detection

**Lines of Code:** ~10 (lines 125-133)

**Test Coverage:**

| Scenario | Test File | Test Name | Type | Priority |
|----------|-----------|-----------|------|----------|
| @/ alias | component-extractor.test.ts | "should detect @/ aliases in imports" | Unit | HIGH |
| ~/ alias | component-extractor.test.ts | "should detect ~/ aliases in imports" | Unit | HIGH |
| Multiple aliases | component-extractor.test.ts | "should detect multiple alias types in same file" | Unit | MEDIUM |
| No false positives | component-extractor.test.ts | "should not flag external packages as aliases" | Unit | MEDIUM |

**Edge Cases Covered:**
- ✅ @/ prefix
- ✅ ~/ prefix
- ✅ Multiple types in same file
- ✅ External packages (react, framer-motion)
- ✅ Scoped packages (@radix-ui/react-dialog)

**Bug Reproductions:**
- BUG-003: Alias imports followed as dependencies

---

#### 3. `remapImportPaths()` - Alias Warning System

**Lines of Code:** ~8 (lines 139-147)

**Test Coverage:**

| Scenario | Test File | Test Name | Type | Priority |
|----------|-----------|-----------|------|----------|
| Warning generation | component-extractor.test.ts | (implicit in detectAliases tests) | Unit | HIGH |
| Warning message format | integration/extract-compose-workflow.test.ts | "should warn about path aliases" | Integration | MEDIUM |
| No modification in Phase 1 | component-extractor.test.ts | (verify content unchanged) | Unit | LOW |

**Edge Cases Covered:**
- ✅ Warning includes all detected aliases
- ✅ Warning mentions tsconfig.json requirement
- ✅ Content preserved (no transformations)

---

#### 4. `extractAssetImports()` - Static Asset Detection

**Lines of Code:** ~10 (lines 153-161)

**Test Coverage:**

| Scenario | Test File | Test Name | Type | Priority |
|----------|-----------|-----------|------|----------|
| Image imports | component-extractor.test.ts | "should detect image imports (jpg, png, svg)" | Unit | HIGH |
| CSS imports | component-extractor.test.ts | "should detect CSS module imports" | Unit | MEDIUM |
| External URLs ignored | component-extractor.test.ts | "should not flag external URLs as assets" | Unit | MEDIUM |
| Uppercase extensions | bug-reproductions.test.ts | BUG-005: "should detect uppercase extensions" | Unit | LOW |

**Edge Cases Covered:**
- ✅ .jpg, .jpeg, .png, .gif, .svg, .webp, .ico
- ✅ Uppercase extensions (.JPG, .PNG)
- ✅ CSS module imports (./hero.module.css)
- ✅ External URLs (https://example.com/hero.jpg)

**Bug Reproductions:**
- BUG-005: Uppercase extensions not detected

---

#### 5. `listComponents()` - Component Discovery

**Lines of Code:** ~30 (lines 68-94)

**Test Coverage:**

| Scenario | Test File | Test Name | Type | Priority |
|----------|-----------|-----------|------|----------|
| List all components | component-extractor.test.ts | "should list all .tsx/.jsx files under components/" | Unit | HIGH |
| Type detection | component-extractor.test.ts | "should detect component types (section, ui, component)" | Unit | MEDIUM |
| Empty template warning | component-extractor.test.ts | "should warn if no components found" | Unit | MEDIUM |
| Nested directories | bug-reproductions.test.ts | BUG-006: "should list deeply nested components" | Unit | HIGH |

**Edge Cases Covered:**
- ✅ components/ and src/components/
- ✅ Nested directories (components/ui/button.tsx)
- ✅ Type detection (sections, ui, generic)
- ✅ Empty template (no components)

**Bug Reproductions:**
- BUG-006: Nested directories not listed

---

#### 6. `extractComponent()` - Full Extraction Flow

**Lines of Code:** ~95 (lines 250-343)

**Test Coverage:**

| Scenario | Test File | Test Name | Type | Priority |
|----------|-----------|-----------|------|----------|
| Component not found | component-extractor.test.ts | "should error if component path does not exist" | Unit | HIGH |
| Multiple matches warning | component-extractor.test.ts | "should warn if multiple files match suffix" | Unit | MEDIUM |
| Dry run preview | component-extractor.test.ts | "should return preview in dry run mode without writing" | Unit | HIGH |
| Full workflow | integration/extract-compose-workflow.test.ts | "should complete full workflow: list → extract → compose" | Integration | HIGH |

**Edge Cases Covered:**
- ✅ Component not found (error)
- ✅ Multiple matches (warning, use first)
- ✅ Dry run (no writes, preview only)
- ✅ Actual write (files created)
- ✅ Overwrite protection

---

### Page Composer

#### 1. `extractAssetImports()` - Asset Detection Helper

**Lines of Code:** ~10 (lines 53-62)

**Test Coverage:**

| Scenario | Test File | Test Name | Type | Priority |
|----------|-----------|-----------|------|----------|
| Image detection | page-composer.test.ts | "should detect image imports (jpg, png, svg, webp)" | Unit | HIGH |
| External URLs ignored | page-composer.test.ts | "should not detect external URLs as assets" | Unit | MEDIUM |

**Edge Cases Covered:**
- ✅ Common image formats
- ✅ External URLs (not detected)

---

#### 2. `copyReferencedAssets()` - Asset Copy Helper (Phase 2 Ready)

**Lines of Code:** ~35 (lines 71-108)

**Test Coverage:**

| Scenario | Test File | Test Name | Type | Priority |
|----------|-----------|-----------|------|----------|
| Copy to public/assets/ | page-composer.test.ts | "should copy assets to public/assets/" | Unit | MEDIUM |
| Duplicate asset warning | page-composer.test.ts | "should warn if asset already exists" | Unit | LOW |
| Missing asset warning | page-composer.test.ts | "should warn if asset file not found" | Unit | LOW |

**Edge Cases Covered:**
- ✅ Asset already exists (warn, don't copy)
- ✅ Asset not found (warn, continue)
- ✅ Multiple assets in same component

**Note:** Not used in Phase 1, but tested for Phase 2 readiness.

---

#### 3. `composePage()` - Page Generation

**Lines of Code:** ~65 (lines 110-173)

**Test Coverage:**

| Scenario | Test File | Test Name | Type | Priority |
|----------|-----------|-----------|------|----------|
| Single section | page-composer.test.ts | "should generate page with single section" | Unit | HIGH |
| Multiple sections | page-composer.test.ts | "should generate page with multiple sections" | Unit | HIGH |
| PascalCase conversion | page-composer.test.ts | "should convert import paths to PascalCase component names" | Unit | HIGH |
| Explicit component name | page-composer.test.ts | "should use explicit component name when provided" | Unit | MEDIUM |
| Props serialization | page-composer.test.ts | "should serialize props correctly" | Unit | HIGH |
| Boolean props | page-composer.test.ts | "should handle boolean props (true/false)" | Unit | MEDIUM |
| Overwrite protection | page-composer.test.ts | "should block overwrite when overwrite=false" | Unit | HIGH |
| Overwrite allowed | page-composer.test.ts | "should allow overwrite when overwrite=true" | Unit | MEDIUM |
| Dry run | page-composer.test.ts | "should return preview in dry run mode without writing" | Unit | HIGH |
| Path handling | page-composer.test.ts | "should handle both absolute and relative paths" | Unit | MEDIUM |
| Empty sections | page-composer.test.ts | "should handle empty sections array" | Unit | LOW |
| Auto-generated comment | page-composer.test.ts | "should include auto-generated comment header" | Unit | LOW |

**Edge Cases Covered:**
- ✅ Empty sections array
- ✅ Single section
- ✅ Multiple sections
- ✅ Duplicate sections (same component twice)
- ✅ Props with special characters
- ✅ Nested object props
- ✅ Component names with numbers
- ✅ Overwrite protection
- ✅ Absolute vs relative paths
- ✅ Dry run vs actual write

**Bug Reproductions:**
- BUG-004: Import deduplication missing
- BUG-007: Special characters in props

---

## Integration Tests

### Extract & Compose Workflow

| Scenario | Test File | Priority |
|----------|-----------|----------|
| Full workflow (list → extract → compose) | extract-compose-workflow.test.ts | HIGH |
| Multi-component extraction | extract-compose-workflow.test.ts | HIGH |
| Dependency chain extraction | extract-compose-workflow.test.ts | MEDIUM |
| Standalone extraction (no deps) | extract-compose-workflow.test.ts | LOW |
| Missing component error | extract-compose-workflow.test.ts | MEDIUM |
| Missing template error | extract-compose-workflow.test.ts | LOW |
| Invalid dependency handling | extract-compose-workflow.test.ts | MEDIUM |
| Alias detection workflow | extract-compose-workflow.test.ts | MEDIUM |
| Asset handling workflow | extract-compose-workflow.test.ts | LOW |
| Dry run validation | extract-compose-workflow.test.ts | HIGH |

---

## Bug Reproduction Tests

All bugs from RC requirements and IE implementation:

| Bug ID | Description | Test | Status |
|--------|-------------|------|--------|
| BUG-001 | Infinite loop on circular deps | bug-reproductions.test.ts | ✅ Ready |
| BUG-002 | maxDepth not respected | bug-reproductions.test.ts | ✅ Ready |
| BUG-003 | Alias imports followed as deps | bug-reproductions.test.ts | ✅ Ready |
| BUG-004 | Import deduplication missing | bug-reproductions.test.ts | ✅ Ready |
| BUG-005 | Uppercase extensions not detected | bug-reproductions.test.ts | ✅ Ready |
| BUG-006 | Nested directories not listed | bug-reproductions.test.ts | ✅ Ready |
| BUG-007 | Special characters in props | bug-reproductions.test.ts | ✅ Ready |
| BUG-008 | Dynamic imports not supported | bug-reproductions.test.ts | ✅ Ready |

---

## Coverage Gaps (if any)

After running `npm run test:coverage`, check for:

### Expected Gaps (Acceptable)
- Error handling paths (hard to reproduce)
- TypeScript type guards (compile-time only)
- MCP server boilerplate (integration tested)

### Unacceptable Gaps
- Core logic paths (extraction, composition)
- Edge case handling (depth limits, circular deps)
- User-facing errors (warnings, error messages)

---

## Test Execution Plan

### Phase 1: Setup (5 minutes)
1. Install vitest dependencies
2. Verify vitest.config.ts
3. Update package.json scripts

### Phase 2: Initial Run (2 minutes)
1. Run `npm test`
2. Verify all tests pass
3. Check for any setup issues

### Phase 3: Coverage Analysis (5 minutes)
1. Run `npm run test:coverage`
2. Open `coverage/index.html`
3. Identify uncovered lines
4. Verify ≥80% coverage

### Phase 4: Gap Filling (if needed)
1. Add tests for uncovered lines
2. Focus on critical paths first
3. Re-run coverage
4. Repeat until ≥80%

### Phase 5: CI Integration (10 minutes)
1. Add GitHub Actions workflow
2. Configure coverage uploads
3. Test on pull request

---

## Success Criteria

✅ All 48 tests pass
✅ Coverage ≥80% on lines, functions, statements
✅ Coverage ≥75% on branches
✅ No critical paths uncovered
✅ All bug reproduction tests pass
✅ Full workflow integration test passes
✅ Test execution time <15 seconds
✅ CI/CD integration configured

---

## Next Steps

After TA completes testing:

1. **PRV (Prod Readiness Verifier)** - Validate quality gates
2. **ICA (Integration & Cohesion Auditor)** - Verify integration points
3. **CRA (Code Review Agent)** - Review test quality
4. **RM (Release Manager)** - Prepare Phase 1 release notes

---

## Maintenance Plan

### Weekly
- Run `npm run test:coverage` and verify ≥80%
- Review test execution time (goal: <15s)

### Per Release
- Update tests for new features
- Add bug reproduction tests for fixes
- Update this coverage plan

### Quarterly
- Audit test quality (clear names, no duplication)
- Review and remove obsolete tests
- Update mock data to match production patterns
