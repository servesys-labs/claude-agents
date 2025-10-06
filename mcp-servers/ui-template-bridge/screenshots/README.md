# Template Screenshots

Visual references for AI agents working with UI templates.

## 📍 Locations

Screenshots are stored in **two locations** for redundancy and agent access:

1. **Project Directory** (this folder):
   - Path: `~/.claude/mcp-servers/ui-template-bridge/screenshots/`
   - Purpose: Development and MCP server access
   - Contains: All screenshots + catalog.json + INDEX.md

2. **Permanent Storage** (recommended for agents):
   - Path: `~/vibe/ui-screenshots/`
   - Purpose: Persistent storage, accessible across sessions
   - Contains: Same files as project directory

## 📋 Files Generated

For each template, you'll find:
- `{template-id}-{page}-{viewport}.png` - Screenshot files
  - Example: `dillionverma-portfolio-home.png` (desktop)
  - Example: `dillionverma-portfolio-home-mobile.png` (mobile)

**Index Files**:
- `catalog.json` - Programmatic access to all screenshots with paths
- `INDEX.md` - Human-readable index with embedded images

## 🤖 Agent Usage

### Method 1: Load Catalog (Recommended)

```typescript
import { promises as fs } from 'fs';
import path from 'path';

// Load screenshot catalog
const catalogPath = path.join(
  process.env.HOME!,
  'vibe',
  'ui-screenshots',
  'catalog.json'
);

const catalog = JSON.parse(await fs.readFile(catalogPath, 'utf-8'));

// Get all screenshots for a template
const templateId = 'dillionverma-portfolio';
const screenshots = catalog.templates[templateId].screenshots;

// Find specific screenshot
const desktopHome = screenshots.find(
  s => s.page === 'home' && s.viewport === 'desktop'
);

console.log('Screenshot path:', desktopHome.permanentPath);
// Output: /Users/agentsy/vibe/ui-screenshots/dillionverma-portfolio-home.png

// Read screenshot for vision analysis
const imageBuffer = await fs.readFile(desktopHome.permanentPath);
```

### Method 2: Direct File Access

```typescript
const screenshotPath = path.join(
  process.env.HOME!,
  'vibe',
  'ui-screenshots',
  'dillionverma-portfolio-home.png'
);

const exists = await fs.access(screenshotPath).then(() => true).catch(() => false);
if (exists) {
  const image = await fs.readFile(screenshotPath);
  // Use image for vision analysis
}
```

### Method 3: List All Available

```typescript
const screenshotsDir = path.join(process.env.HOME!, 'vibe', 'ui-screenshots');
const files = await fs.readdir(screenshotsDir);
const screenshots = files.filter(f => f.endsWith('.png'));

console.log(`Found ${screenshots.length} screenshots`);
screenshots.forEach(file => console.log(`  - ${file}`));
```

## 📊 Catalog Structure

The `catalog.json` file has this structure:

```json
{
  "generated": "2025-10-06T...",
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

## 🎯 Use Cases

### 1. Visual Context for Slot Filling

When filling slots, agents can reference screenshots to understand:
- Layout structure
- Component placement
- Visual hierarchy
- Color schemes

```typescript
// Load screenshot to understand hero section layout
const catalog = await loadCatalog();
const screenshot = catalog.templates['template-id'].screenshots
  .find(s => s.page === 'home' && s.viewport === 'desktop');

console.log(`Reference this screenshot: ${screenshot.permanentPath}`);
// Agent can now see hero section layout before filling slot
```

### 2. Design Consistency Validation

```typescript
// Compare original template design vs modified version
const originalScreenshot = await fs.readFile(
  catalog.templates['template-id'].screenshots[0].permanentPath
);

// After modifications, take new screenshot and compare
```

### 3. Component Identification

```typescript
// Identify which components are used in a template by viewing screenshot
const desktopView = screenshots.find(s => s.viewport === 'desktop');
console.log(`View components at: ${desktopView.permanentPath}`);
```

## 🔄 Regeneration

To regenerate all screenshots:

```bash
cd ~/.claude/mcp-servers/ui-template-bridge
npx tsx scripts/generate-screenshots.ts
```

**Note**: This requires:
- All templates extracted
- `npm install` in each template
- Dev servers running (automatic)
- ~5-10 minutes per Next.js template

## 📝 Screenshot Coverage

Current templates with screenshots:
- dillionverma-portfolio (2 pages: home, blog)
- dillionverma-startup-template (2 pages: home, login)
- magicuidesign-agent-template (1 page: home)
- magicuidesign-devtool-template (2 pages: home, blog)
- magicuidesign-saas-template (1 page: home)

Each page captured in:
- 🖥️ Desktop viewport (1280x800)
- 📱 Mobile viewport (375x667)

**Total**: ~20 screenshots (5 templates × 2-4 pages × 2 viewports)

## 🚫 React Native Templates

React Native templates require Expo Go and are not automatically screenshot.
Manual process:
1. Extract template
2. Run `npm start`
3. Open in Expo Go or iOS Simulator
4. Take screenshots manually

## 💡 Tips for Agents

1. **Always check catalog first**: Use `catalog.json` to find available screenshots
2. **Use permanent path**: Reference `permanentPath` for cross-session access
3. **Desktop vs Mobile**: Choose viewport based on use case
4. **Page-specific**: Use `page` field to find relevant screenshots
5. **Fallback**: If screenshot missing, extract and run template locally

## 🔍 Example: Complete Workflow

```typescript
// 1. Load catalog
const catalog = JSON.parse(
  await fs.readFile('~/vibe/ui-screenshots/catalog.json', 'utf-8')
);

// 2. User asks to modify hero section of dillionverma-portfolio
const templateId = 'dillionverma-portfolio';
const screenshots = catalog.templates[templateId].screenshots;

// 3. Find relevant screenshot
const heroScreenshot = screenshots.find(
  s => s.page === 'home' && s.viewport === 'desktop'
);

console.log(`📸 Reference screenshot: ${heroScreenshot.permanentPath}`);

// 4. Agent reads screenshot for visual context
const imageBuffer = await fs.readFile(heroScreenshot.permanentPath);

// 5. Agent can now see:
//    - Hero section layout
//    - Color scheme
//    - Typography
//    - Component structure
//    - Spacing and alignment

// 6. Make informed modifications to hero slot
await fillSlot({
  sitePath: '/path/to/site',
  pageId: 'home',
  slotId: 'hero',
  content: '<HeroSection ...>', // Based on visual understanding
});
```

---

**Generated**: By `scripts/generate-screenshots.ts`

**Last Updated**: Run script to see current status
