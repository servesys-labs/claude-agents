# Screenshot Generation Script Enhancements

## Implementation Summary

Successfully implemented three enhancements to `scripts/generate-screenshots.ts`:

### 1. CLI Targeting (--template, --route)
**Status**: ✅ Complete

Added command-line argument parsing to selectively capture specific templates or routes:

- `--template <template-id>`: Process only the specified template
- `--route <route-path>`: Capture only the specified route
- `--help` / `-h`: Display comprehensive help text
- Filters can be combined (e.g., `--template X --route Y`)
- `--test-one` continues to work and can be combined with other filters

**Implementation Details**:
- Created `parseCLIArgs()` function to parse command-line arguments
- Created `showHelp()` function with detailed usage examples
- Applied filters in order: manifest → template → route → test-one
- Error handling for invalid template IDs or routes
- Shows active filters in console output

**Usage Examples**:
```bash
# Capture specific template only
npx tsx scripts/generate-screenshots.ts --template dillionverma-portfolio

# Capture specific route across all templates
npx tsx scripts/generate-screenshots.ts --route /blog

# Capture specific template + route combination
npx tsx scripts/generate-screenshots.ts --template dillionverma-portfolio --route /blog

# Test mode with template filter
npx tsx scripts/generate-screenshots.ts --test-one --template magicuidesign-saas-template
```

---

### 2. Better Wait Conditions
**Status**: ✅ Complete

Replaced `networkidle` with more reliable wait conditions to reduce noise in Next.js dev mode:

**Changes in `captureDesktopAndMobile()` function (lines 144-162)**:
- Primary strategy: `page.waitForSelector('h1, [data-hero], main', { timeout: 5000 })`
- Fallback: `waitUntil: 'domcontentloaded'` if selector timeout
- Additional 500ms delay after DOM ready for animations
- Logs wait strategy used for debugging

**Benefits**:
- More reliable in Next.js dev mode (avoids network noise)
- Faster screenshot capture (doesn't wait for all network idle)
- Graceful fallback for pages without hero elements
- Better handling of CSS animations and transitions

**Implementation Details**:
- Try-catch block for selector-based wait
- Fallback to domcontentloaded + fixed delay if hero not found
- Console logging of wait strategy used
- 30-second overall timeout maintained

---

### 3. WebP Format Support
**Status**: ✅ Complete

Added optional WebP encoding alongside PNG for smaller file sizes:

- `--webp` flag enables WebP output
- Saves both PNG and WebP when flag is present
- Updates `catalog.json` to include WebP paths
- Quality: 90% (balance between size and quality)

**Implementation Details**:
- Modified `captureDesktopAndMobile()` to accept `enableWebP` parameter
- Captures WebP after PNG for both desktop and mobile
- WebP filenames: `template-id-page-viewport.webp`
- Copies WebP to vibe directory (permanent storage)

**Catalog Updates**:
When `--webp` flag is used, catalog entries include:
```json
{
  "filename": "template-home.png",
  "webpFilename": "template-home.webp",
  "path": "/path/to/template-home.png",
  "permanentPath": "/permanent/path/to/template-home.png",
  "webpPath": "/path/to/template-home.webp",
  "webpPermanentPath": "/permanent/path/to/template-home.webp"
}
```

Also added `totalWebP` field to catalog root.

**Usage Example**:
```bash
# Generate WebP alongside PNG
npx tsx scripts/generate-screenshots.ts --test-one --webp

# WebP with template filter
npx tsx scripts/generate-screenshots.ts --template dillionverma-portfolio --webp
```

**File Size Benefits**:
- WebP typically 25-35% smaller than PNG
- Quality setting of 90% maintains visual fidelity
- Useful for web delivery (faster loading)
- PNG still generated for compatibility

---

## Testing

### Help Text
```bash
npx tsx scripts/generate-screenshots.ts --help
# Output: ✅ Displays comprehensive usage guide
```

### CLI Parsing
```bash
# All flags parse correctly without runtime errors
npx tsx scripts/generate-screenshots.ts --template dillionverma-portfolio --route / --webp --test-one
```

### Type Safety
Note: TypeScript errors shown are pre-existing configuration issues (esModuleInterop, import.meta, downlevelIteration), not related to these enhancements. The script runs correctly via `tsx`.

---

## Files Modified

1. **scripts/generate-screenshots.ts** (primary changes)
   - Added `parseCLIArgs()` function (lines 348-379)
   - Added `showHelp()` function (lines 384-424)
   - Modified `captureDesktopAndMobile()` signature and implementation (lines 108-199)
   - Modified `generateScreenshotsForTemplate()` to accept `enableWebP` (line 293)
   - Modified `main()` function for CLI parsing and filtering (lines 429-578)
   - Modified `generateScreenshotIndex()` to support WebP (lines 583+)

---

## Next Steps (Optional)

Potential future enhancements:
1. **Parallel screenshot capture**: Use Promise.all() for multiple routes
2. **Custom viewport sizes**: `--viewport 1920x1080` flag
3. **Dark mode screenshots**: `--dark` flag for dark theme variants
4. **Configurable wait strategies**: `--wait-strategy selector|networkidle|domcontentloaded`
5. **Screenshot comparison**: Compare with previous runs, highlight visual diffs
6. **CI/CD integration**: GitHub Actions workflow for automated screenshot updates

---

## Documentation Updates

Created this summary document (`SCREENSHOT_ENHANCEMENTS.md`) with:
- Implementation details for each enhancement
- Usage examples
- Testing verification
- File change locations
- Future enhancement suggestions
