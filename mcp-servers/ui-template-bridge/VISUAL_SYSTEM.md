# Visual Reference System for AI Agents

## Overview

The UI Template Bridge now includes a **visual reference system** that gives AI agents visual memory of each template. This enables design-aware modifications and better decision-making when working with templates.

## 🎯 Problem Solved

Without screenshots, agents working on templates:
- ❌ Don't know what the template looks like
- ❌ Can't understand layout structure
- ❌ Make blind decisions about slot content
- ❌ Can't validate design consistency
- ❌ Have no visual context for component placement

**With screenshots**, agents can:
- ✅ See the template before modifying
- ✅ Understand hero sections, features, CTAs
- ✅ Make informed slot filling decisions
- ✅ Maintain design consistency
- ✅ Know where components are visually positioned

## 📸 What Gets Captured

For each Next.js template, we capture:

### Desktop View (1280x800)
- Full homepage layout
- Key sections (hero, features, pricing, CTA)
- Navigation and footer
- Blog/login pages (if available)

### Mobile View (375x667)
- Responsive layout
- Mobile navigation
- Touch-optimized components
- Mobile-specific sections

### Example Coverage

**dillionverma-portfolio**:
- `dillionverma-portfolio-home.png` (desktop)
- `dillionverma-portfolio-home-mobile.png` (mobile)
- `dillionverma-portfolio-blog.png` (desktop)
- `dillionverma-portfolio-blog-mobile.png` (mobile)

**Total**: 2 pages × 2 viewports = 4 screenshots per template

## 📂 Storage Architecture

### Dual-Location Strategy

Screenshots are saved to **two locations** for redundancy:

```
1. Project Directory (Development)
   └── ~/.claude/mcp-servers/ui-template-bridge/screenshots/
       ├── catalog.json          (metadata)
       ├── INDEX.md              (visual index)
       └── *.png                 (screenshots)

2. Permanent Storage (Production)
   └── ~/vibe/ui-screenshots/
       ├── catalog.json          (same metadata)
       ├── INDEX.md              (same index)
       └── *.png                 (same screenshots)
```

**Why Dual Storage?**
- **Project dir**: Quick access during development
- **Permanent dir**: Persists across MCP server reinstalls
- **Redundancy**: If one location fails, other is available
- **Agent access**: Agents can use whichever path is more reliable

## 📋 Catalog Format

The `catalog.json` provides programmatic access:

```json
{
  "generated": "2025-10-06T09:30:00.000Z",
  "total": 20,
  "locations": {
    "primary": "/Users/agentsy/.claude/mcp-servers/ui-template-bridge/screenshots",
    "permanent": "/Users/agentsy/vibe/ui-screenshots"
  },
  "templates": {
    "dillionverma-portfolio": {
      "screenshots": [
        {
          "filename": "dillionverma-portfolio-home.png",
          "page": "home",
          "viewport": "desktop",
          "dimensions": "1280x800",
          "path": "/Users/agentsy/.claude/mcp-servers/ui-template-bridge/screenshots/dillionverma-portfolio-home.png",
          "permanentPath": "/Users/agentsy/vibe/ui-screenshots/dillionverma-portfolio-home.png"
        },
        {
          "filename": "dillionverma-portfolio-home-mobile.png",
          "page": "home",
          "viewport": "mobile",
          "dimensions": "375x667",
          "path": "...",
          "permanentPath": "..."
        }
      ]
    }
  }
}
```

## 🤖 How Agents Use This

### 1. Before Filling a Slot

```typescript
// Agent workflow: Modify hero section

// Step 1: Load catalog to find screenshot
const catalog = JSON.parse(
  await fs.readFile('~/vibe/ui-screenshots/catalog.json', 'utf-8')
);

// Step 2: Find hero section screenshot
const heroView = catalog.templates['dillionverma-portfolio']
  .screenshots.find(s => s.page === 'home' && s.viewport === 'desktop');

console.log(`📸 Reference: ${heroView.permanentPath}`);

// Step 3: Agent reads screenshot
const screenshot = await fs.readFile(heroView.permanentPath);

// Step 4: Agent sees:
//   - Hero has large heading + subtitle + CTA button
//   - Color scheme is dark mode with accent colors
//   - Layout is centered with max-width container
//   - CTA button is prominent green

// Step 5: Make informed decision
await fillSlot({
  sitePath: '/path/to/site',
  pageId: 'home',
  slotId: 'hero',
  content: `
    <div className="flex flex-col items-center text-center">
      <h1 className="text-5xl font-bold">New Headline</h1>
      <p className="text-xl text-muted-foreground">Supporting text</p>
      <Button className="mt-8">Call to Action</Button>
    </div>
  `,
});

// Agent's decision is now visually informed:
//   ✅ Knows to center content
//   ✅ Knows heading size should be large
//   ✅ Knows button should be prominent
//   ✅ Matches existing layout structure
```

### 2. Component Identification

```typescript
// Agent workflow: Add missing component

// Load screenshot
const desktopHome = catalog.templates['magicuidesign-agent-template']
  .screenshots.find(s => s.page === 'home' && s.viewport === 'desktop');

// Agent sees screenshot and identifies:
//   - Uses marquee component for logos
//   - Uses bento grid for features
//   - Uses particles for background
//   - Uses hero-video-dialog for demo

// Agent can now accurately suggest components
await insertComponent({
  sitePath,
  pageId: 'features',
  componentId: 'magicui.marquee',
  elementId: 'client-logos',
  position: 'after',
});
```

### 3. Design Consistency Validation

```typescript
// Agent workflow: Validate modifications

// Before modification
const originalScreenshot = await fs.readFile(
  catalog.templates['template-id'].screenshots[0].permanentPath
);

// After modification (user generates new screenshot)
const modifiedScreenshot = await generateScreenshot({
  templateId: 'template-id',
  route: '/',
});

// Agent can visually compare:
//   - Color scheme unchanged ✅
//   - Typography consistent ✅
//   - Layout structure preserved ✅
//   - Component spacing maintained ✅
```

### 4. Mobile Responsiveness Check

```typescript
// Agent checks both viewports

const desktopView = screenshots.find(s => s.viewport === 'desktop');
const mobileView = screenshots.find(s => s.viewport === 'mobile');

// Agent sees:
//   - Desktop: 3-column grid
//   - Mobile: Stacked single column
//
// Agent ensures modifications respect both:
await fillSlot({
  content: `
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {/* Responsive grid matches screenshot behavior */}
    </div>
  `,
});
```

## 🚀 Generation Workflow

### Automatic Process

The script `scripts/generate-screenshots.ts` automates everything:

1. **Extract template** from ZIP
2. **Install dependencies** (`npm install`)
3. **Start dev server** (random port to avoid conflicts)
4. **Wait for server** to be ready (up to 60 seconds)
5. **Capture desktop screenshot** (1280x800)
6. **Capture mobile screenshot** (375x667)
7. **Save to both locations** (project + permanent)
8. **Kill dev server** and cleanup
9. **Generate catalog.json** with all metadata
10. **Generate INDEX.md** with visual index

### Manual Run

```bash
cd ~/.claude/mcp-servers/ui-template-bridge
npx tsx scripts/generate-screenshots.ts
```

**Expected time**: ~5-10 minutes per Next.js template

**Requirements**:
- Node.js installed
- Playwright installed (`npm install playwright`)
- Templates in `~/vibe/ui-templates/`
- Sufficient disk space (~50MB for 20 screenshots)

## 📊 Coverage Status

### Next.js Templates (Auto-Generated) ✅

| Template | Pages | Screenshots |
|----------|-------|-------------|
| dillionverma-portfolio | home, blog | 4 |
| dillionverma-startup-template | home, login | 4 |
| magicuidesign-agent-template | home | 2 |
| magicuidesign-devtool-template | home, blog | 4 |
| magicuidesign-saas-template | home | 2 |

**Total**: 5 templates, 16 screenshots

### React Native Templates (Manual) ⏸️

| Template | Status | Notes |
|----------|--------|-------|
| luna | Not captured | Requires Expo Go |
| multia | Not captured | Requires Expo Go |
| feedy | Not captured | Requires Expo Go |
| velora | Not captured | Requires Expo Go |
| propia | Not captured | Requires Expo Go |
| caloria-v2 | Not captured | Requires Expo Go |
| walley | Not captured | Requires Expo Go |

**Manual process**:
1. Extract template
2. Run `npm start` (Expo)
3. Open in iOS Simulator or Expo Go
4. Take screenshots manually
5. Save to `~/vibe/ui-screenshots/`

## 🎨 Use Cases

### 1. Slot Content Generation

**Before**: Agent guesses slot content structure
**After**: Agent sees layout and generates appropriate content

```typescript
// Agent sees hero has: large title + subtitle + 2 CTA buttons
// Agent generates matching structure instead of generic placeholder
```

### 2. Component Placement

**Before**: Agent places components without knowing where they fit visually
**After**: Agent knows section layouts and places components appropriately

```typescript
// Agent sees "features" section uses 3-column grid with cards
// Agent places new feature card in same style
```

### 3. Theme Understanding

**Before**: Agent doesn't know color scheme or visual style
**After**: Agent sees dark/light mode usage and maintains consistency

```typescript
// Agent sees template uses dark mode by default
// Agent ensures modifications use appropriate colors
```

### 4. Layout Validation

**Before**: Agent can't verify layout correctness
**After**: Agent compares modifications against original

```typescript
// Agent checks: "Does my modification maintain the visual hierarchy?"
```

## 🔍 Future Enhancements

### Potential Additions

1. **Hover States**: Capture component interactions
2. **Animation Frames**: Capture key animation states
3. **Form States**: Empty, filled, error states
4. **Modal/Dialog Views**: Overlay components
5. **Loading States**: Skeleton screens, spinners
6. **Component Library**: Individual component screenshots
7. **Color Palette**: Extracted color scheme reference
8. **Typography Guide**: Font samples from template

### Advanced Analysis

1. **AI Vision Analysis**: Automatic component detection
2. **Layout Patterns**: Identify grid systems, spacing rules
3. **Accessibility**: Color contrast, text sizes
4. **Design Tokens**: Extract from screenshots

## 📖 Documentation

- **Agent Guide**: `screenshots/README.md`
- **Catalog Reference**: `catalog.json` (self-documenting)
- **Visual Index**: `INDEX.md` (human-readable)
- **This Document**: Complete system overview

## ✅ Benefits Summary

For AI agents working with templates:

1. **Visual Context** ✅
   - Know what template looks like
   - Understand layout structure
   - See component placement

2. **Better Decisions** ✅
   - Informed slot filling
   - Appropriate component selection
   - Consistent design choices

3. **Quality Assurance** ✅
   - Validate modifications
   - Maintain visual consistency
   - Catch layout regressions

4. **Efficiency** ✅
   - Fewer iterations needed
   - Reduce back-and-forth with user
   - Faster development

5. **Design Awareness** ✅
   - Understand color schemes
   - Respect typography
   - Maintain spacing rules

---

**The visual reference system transforms agents from "code-only" to "design-aware" developers.**

🎨 Screenshots give agents **eyes** to see what they're building.
