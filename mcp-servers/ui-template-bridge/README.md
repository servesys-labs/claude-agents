# UI Template Bridge MCP Server

> **Pick template → stamp → fill → ship** workflow for Next.js + shadcn/ui + MagicUI templates

MCP server that provides tools for stamping out production-ready UI templates from a Railway-hosted template API. Includes theme tokens, slot filling, component addition, and Playwright screenshot generation.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Code (MCP Client)                                    │
│  ├─ list_templates()                                         │
│  ├─ init_site(templateId, destination)                       │
│  ├─ apply_blueprint(site.json)                               │
│  ├─ fill_slot(pageId, slotId, content)                       │
│  ├─ update_theme(tokens)                                     │
│  ├─ add_component(componentId, location)                     │
│  └─ generate_screenshot(templateId)                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  UI Template Bridge MCP Server (Local)                       │
│  ├─ Fetches from Railway API                                 │
│  ├─ Downloads & extracts templates                           │
│  ├─ Applies blueprints with slot filling                     │
│  ├─ Updates theme tokens (CSS variables)                     │
│  ├─ Inserts components at stable IDs                         │
│  └─ Generates screenshots with Playwright                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Railway API (Production)                                    │
│  URL: ui-template-api-production-production.up.railway.app   │
│  ├─ GET /api/templates (list all)                            │
│  ├─ GET /api/templates/:id (metadata)                        │
│  ├─ GET /api/templates/:id/download (ZIP)                    │
│  └─ GET /api/templates/:id/files (file list)                 │
└─────────────────────────────────────────────────────────────┘
```

## Templates Available

### 9 Production Templates

1. **ai-saas-template** - AI-powered SaaS with landing, dashboard, blog, auth
2. **dillionverma-portfolio** - Portfolio with blog and project showcase
3. **dillionverma-startup-template** - Startup landing page with marketing sections
4. **magicuidesign-agent-template** - AI agent landing with chat interface
5. **magicuidesign-devtool-template** - Developer tool with docs and changelog
6. **magicuidesign-mobile-template** - Mobile-first PWA template
7. **magicuidesign-saas-template** - SaaS landing + dashboard + auth
8. **nodus-agent-template** - AI agent interface with playground and pricing
9. **startup-landing-page-template** - Minimal startup landing page

**Tech Stack**: Next.js 14/15 + TypeScript + Tailwind CSS + shadcn/ui + MagicUI

## Installation

```bash
cd ~/.claude/mcp-servers/ui-template-bridge
npm install
npm run build
```

### Add to Claude Code

Edit `~/.claude/mcp-template.json`:

```json
{
  "mcpServers": {
    "ui-template-bridge": {
      "command": "node",
      "args": ["/Users/agentsy/.claude/mcp-servers/ui-template-bridge/dist/index.js"],
      "env": {
        "UI_TEMPLATE_API_URL": "https://ui-template-api-production-production.up.railway.app"
      }
    }
  }
}
```

Restart Claude Code to activate the server.

## MCP Tools

### 1. `list_templates`

List all available UI templates from the registry.

**Parameters:**
- `filter.capability` (optional): Filter by capability (landing, dashboard, auth, etc.)
- `filter.author` (optional): Filter by author name

**Example:**
```typescript
// List all templates
list_templates({})

// Filter by capability
list_templates({ filter: { capability: "auth" } })

// Filter by author
list_templates({ filter: { author: "Dillion Verma" } })
```

**Response:**
```json
{
  "ok": true,
  "count": 9,
  "templates": [
    {
      "id": "ai-saas-template",
      "name": "AI SaaS Template",
      "description": "landing + dashboard + auth template",
      "capabilities": ["landing", "dashboard", "auth"],
      "author": "MagicUI Design",
      "stack": "next+tailwind+shadcn+magicui"
    }
  ]
}
```

### 2. `get_template`

Get detailed metadata for a specific template.

**Parameters:**
- `templateId` (required): Template ID

**Example:**
```typescript
get_template({ templateId: "ai-saas-template" })
```

**Response:**
```json
{
  "ok": true,
  "template": {
    "id": "ai-saas-template",
    "name": "AI SaaS Template",
    "description": "landing + dashboard + auth template built with Next.js, shadcn/ui, and MagicUI",
    "stack": "next+tailwind+shadcn+magicui",
    "capabilities": ["landing", "dashboard", "auth"],
    "author": "MagicUI Design",
    "preview_url": "https://ui-template-api-production.up.railway.app/screenshots/ai-saas-template-preview.png"
  }
}
```

### 3. `init_site`

Initialize a new site from a template (stamp out template to destination).

**Parameters:**
- `templateId` (required): Template ID to use
- `destination` (required): Destination directory path
- `siteId` (required): Unique site identifier (kebab-case)
- `siteName` (optional): Display name for the site

**Example:**
```typescript
init_site({
  templateId: "ai-saas-template",
  destination: "/Users/me/projects",
  siteId: "my-startup",
  siteName: "My Startup"
})
```

**What it does:**
1. Downloads template ZIP from Railway API
2. Extracts to `destination/siteId/`
3. Creates initial `site.json` blueprint
4. Ready for customization with other tools

**Response:**
```json
{
  "ok": true,
  "message": "Site initialized at /Users/me/projects/my-startup",
  "siteId": "my-startup",
  "templateId": "ai-saas-template",
  "path": "/Users/me/projects/my-startup"
}
```

### 4. `apply_blueprint`

Apply a `site.json` blueprint to fill slots and configure a site.

**Parameters:**
- `blueprintPath` (required): Path to site.json blueprint file
- `destination` (required): Site directory to apply blueprint to
- `overwrite` (optional): Overwrite existing slot content (default: false)

**Example:**
```typescript
apply_blueprint({
  blueprintPath: "/Users/me/my-site-blueprint.json",
  destination: "/Users/me/projects/my-startup",
  overwrite: true
})
```

**Blueprint Format (site.json):**
```json
{
  "templateId": "ai-saas-template",
  "siteId": "my-startup",
  "siteName": "My Startup",
  "brand": {
    "name": "Acme Inc",
    "tagline": "Ship faster, build better",
    "tokens": {
      "colors": {
        "primary": "#0070f3",
        "accent": "#ff0080"
      }
    }
  },
  "pages": [
    {
      "pageId": "home",
      "enabled": true,
      "slots": {
        "hero-heading": {
          "content": "Build AI-powered products faster",
          "type": "text"
        },
        "hero-description": {
          "content": "Ship production-ready SaaS in days, not months",
          "type": "text"
        }
      }
    }
  ],
  "defaults": {
    "recipe": "saas-with-auth",
    "autoFill": true,
    "autoSEO": true
  }
}
```

### 5. `fill_slot`

Fill a content slot in a page with text, markdown, or component config.

**Parameters:**
- `sitePath` (required): Path to site directory
- `pageId` (required): Page ID to modify
- `slotId` (required): Slot ID to fill
- `content` (required): Content to insert

**Example:**
```typescript
fill_slot({
  sitePath: "/Users/me/projects/my-startup",
  pageId: "home",
  slotId: "hero-heading",
  content: "Build AI-powered products faster"
})
```

**Slot Filling Strategy:**
Templates use comment markers in TSX/MDX:
```tsx
{/* SLOT:hero-heading:START */}
<h1>Default Heading</h1>
{/* SLOT:hero-heading:END */}
```

Tool replaces content between markers.

### 6. `update_theme`

Update theme tokens (colors, typography) for a site.

**Parameters:**
- `sitePath` (required): Path to site directory
- `tokens` (required): Token overrides

**Example:**
```typescript
update_theme({
  sitePath: "/Users/me/projects/my-startup",
  tokens: {
    colors: {
      primary: "#8b5cf6",
      secondary: "#ec4899"
    },
    typography: {
      fontFamily: {
        sans: "Inter, sans-serif",
        display: "Cal Sans, sans-serif"
      }
    }
  }
})
```

**How it works:**
Updates CSS variables in `app/globals.css`:
```css
:root {
  --primary: 262 83% 58%; /* #8b5cf6 */
  --secondary: 330 81% 60%; /* #ec4899 */
}
```

### 7. `add_component`

Add a component to a page at a specific location.

**Parameters:**
- `sitePath` (required): Path to site directory
- `componentId` (required): Component ID from template registry
- `location` (required): Where to insert the component
  - `pageId` (required): Page ID to add component to
  - `after` (optional): Insert after this element ID
  - `before` (optional): Insert before this element ID
- `props` (optional): Component props configuration

**Example:**
```typescript
add_component({
  sitePath: "/Users/me/projects/my-startup",
  componentId: "testimonials-grid",
  location: {
    pageId: "home",
    after: "features-section"
  },
  props: {
    columns: 3,
    variant: "modern"
  }
})
```

### 8. `generate_screenshot`

Generate a screenshot preview of a template using Playwright.

**Parameters:**
- `templateId` (required): Template ID to screenshot
- `outputPath` (optional): Output path for screenshot

**Example:**
```typescript
generate_screenshot({
  templateId: "ai-saas-template",
  outputPath: "/Users/me/screenshots/ai-saas-preview.png"
})
```

## Don't Think About Anything Defaults

### Recipe System

6 pre-configured recipes with sensible defaults:

1. **minimal-landing** - Clean landing page with hero and CTA
2. **saas-with-auth** - SaaS with landing, dashboard, auth, payments
3. **portfolio-with-blog** - Personal portfolio with blog and projects
4. **ai-agent-interface** - AI agent landing with chat playground
5. **devtool-with-docs** - Developer tool with documentation
6. **mobile-first-pwa** - Mobile-first progressive web app

**Usage:**
```json
{
  "defaults": {
    "recipe": "saas-with-auth",
    "autoFill": true,
    "autoSEO": true,
    "autoScreenshots": true
  }
}
```

### Theme Presets

6 color schemes:
- `neutral` - Black/white/blue
- `brand` - Blue/purple/pink
- `creative` - Purple/pink/orange
- `futuristic` - Cyan/indigo/violet
- `technical` - Green/teal/orange
- `vibrant` - Red/orange/yellow

## Stable Component IDs

Each template provides stable component IDs for consistent references:

```json
{
  "components": {
    "hero-section": {
      "id": "hero-section",
      "type": "hero",
      "category": "marketing",
      "variants": ["default", "centered", "split"],
      "slots": ["hero-heading", "hero-description", "hero-cta"]
    },
    "testimonials-grid": {
      "id": "testimonials-grid",
      "type": "testimonials",
      "category": "marketing",
      "variants": ["grid", "carousel", "featured"],
      "props": {
        "columns": 3,
        "autoplay": true
      }
    }
  }
}
```

## Migration Notes

### Template Updates

When templates are updated on Railway, this MCP server automatically fetches the latest version. No manual intervention required.

### Breaking Changes

If a template has breaking changes (e.g., slot IDs renamed), the `meta.json` includes migration notes:

```json
{
  "migration": {
    "from": ["1.0.0", "1.1.0"],
    "breaking": [
      {
        "version": "2.0.0",
        "description": "Renamed 'hero-title' slot to 'hero-heading'",
        "guide": "Update site.json to use 'hero-heading' instead of 'hero-title'"
      }
    ]
  }
}
```

## Development

### Build
```bash
npm run build
```

### Watch Mode
```bash
npm run dev
```

### Test
```bash
# Test MCP server with Claude Code
# Use list_templates tool in Claude Code UI
```

## Directory Structure

```
ui-template-bridge/
├── src/
│   ├── index.ts                    # Main MCP server
│   ├── schemas/
│   │   ├── meta.json               # Template metadata schema
│   │   ├── site.json               # Site blueprint schema
│   │   └── default-theme-tokens.json
│   ├── tools/                      # MCP tool implementations
│   └── services/
│       ├── screenshot.ts           # Playwright screenshot service
│       └── slot-filler.ts          # Slot filling with comment markers
├── templates-registry/             # Cached template metadata
├── screenshots/                    # Generated screenshots
└── package.json
```

## Future Enhancements

- [ ] Implement slot filling with comment markers
- [ ] Implement theme token updates (CSS variables)
- [ ] Implement component insertion
- [ ] Generate template meta.json with stable IDs
- [ ] Playwright screenshot service
- [ ] Auto-generate SEO metadata from content
- [ ] Deploy to Vercel/Netlify/Railway integration
- [ ] Component marketplace with MagicUI/shadcn registry

---

## Phase 1: Component Extraction Tools

Phase 1 transforms UI Template Bridge from "template stamping" to "component remixing". Instead of copying entire templates, AI agents can now extract individual components (hero, pricing, features) from multiple templates and compose custom pages.

### 9. `list_components`

List all extractable components from a template.

**Parameters:**
- `templateId` (required): Template ID to scan

**Example:**
```typescript
list_components({ templateId: "ai-saas-template" })
```

**Response:**
```json
{
  "ok": true,
  "components": [
    {
      "path": "src/components/sections/hero.tsx",
      "name": "hero.tsx",
      "directory": "src/components/sections",
      "imports": ["framer-motion", "@/components/icons", "@/components/ui/button"]
    },
    {
      "path": "src/components/sections/pricing.tsx",
      "name": "pricing.tsx",
      "directory": "src/components/sections",
      "imports": ["@/components/ui/card", "lucide-react"]
    }
  ],
  "count": 15
}
```

### 10. `extract_component`

Extract a component from a template with its dependencies.

**Parameters:**
- `templateId` (required): Template ID
- `componentPath` (required): Component path (e.g., `src/components/hero.tsx`)
- `destination` (required): Destination directory
- `withDependencies` (optional): Include relative imports (default: `true`)
- `maxDepth` (optional): Max dependency depth (default: `3`)
- `overwrite` (optional): Overwrite existing files (default: `false`)
- `dryRun` (optional): Preview without writing (default: `false`)

**Example:**
```typescript
extract_component({
  templateId: "ai-saas-template",
  componentPath: "src/components/sections/hero.tsx",
  destination: "./my-app/components/",
  withDependencies: true,
  maxDepth: 3
})
```

**Response:**
```json
{
  "success": true,
  "filesWritten": [
    "./my-app/components/hero.tsx",
    "./my-app/components/icons.tsx",
    "./my-app/lib/utils.ts"
  ],
  "warnings": [
    "ALIAS_DETECTED: Found @/ - ensure target has matching tsconfig paths",
    "ASSET_IMPORTS: Found 2 asset import(s) - manual copy required in Phase 1"
  ]
}
```

**Features:**
- **Depth-limited dependency tracking**: Follows relative imports up to `maxDepth` levels (default: 3)
- **Circular dependency detection**: Prevents infinite loops with visited Set
- **Alias detection**: Warns about `@/` and `~/` imports (requires matching tsconfig)
- **Asset detection**: Identifies image/CSS imports (Phase 2 will auto-copy)
- **Dry-run mode**: Preview extraction without writing files

### 11. `compose_page`

Compose a Next.js page from component sections.

**Parameters:**
- `sitePath` (required): Site root directory
- `pagePath` (required): Page file path (e.g., `app/page.tsx`)
- `sections` (required): Array of component sections
  - `importPath` (required): Import path (e.g., `@/components/hero`)
  - `componentName` (optional): Component name (auto-detected if omitted)
  - `props` (optional): Component props as JSON object
- `overwrite` (optional): Overwrite existing page (default: `false`)
- `dryRun` (optional): Preview without writing (default: `false`)

**Example:**
```typescript
compose_page({
  sitePath: "./my-app",
  pagePath: "app/page.tsx",
  sections: [
    {
      importPath: "@/components/hero",
      props: { title: "DevFlow AI", subtitle: "Automate your workflow" }
    },
    {
      importPath: "@/components/features"
    },
    {
      importPath: "@/components/pricing",
      componentName: "PricingTable"
    }
  ]
})
```

**Response:**
```json
{
  "success": true,
  "path": "./my-app/app/page.tsx",
  "preview": "import Hero from '@/components/hero';\nimport Features from '@/components/features';\n\nexport default function Page() {\n  return (\n    <>\n      <Hero title=\"DevFlow AI\" subtitle=\"Automate your workflow\" />\n      <Features />\n      <PricingTable />\n    </>\n  );\n}"
}
```

**Features:**
- **Auto-detects component names**: Converts `@/components/hero` → `Hero`
- **Props serialization**: Converts JSON objects to JSX props
- **Multiple sections**: Compose pages from mixed components
- **Dry-run mode**: Preview generated JSX without writing

---

### Phase 1 Workflow Example

```typescript
// 1. Discover available components
const { components } = await list_components({
  templateId: "ai-saas-template"
});

// 2. Extract hero from ai-saas-template
await extract_component({
  templateId: "ai-saas-template",
  componentPath: "src/components/sections/hero.tsx",
  destination: "./my-app/components/",
  withDependencies: true
});

// 3. Extract pricing from different template
await extract_component({
  templateId: "startup-template",
  componentPath: "src/components/pricing.tsx",
  destination: "./my-app/components/",
  withDependencies: true
});

// 4. Compose custom landing page
await compose_page({
  sitePath: "./my-app",
  pagePath: "app/page.tsx",
  sections: [
    { importPath: "@/components/hero" },
    { importPath: "@/components/pricing" }
  ]
});
```

**Result**: Custom landing page with hero from Template A + pricing from Template B, no full template duplication.

---

## License

MIT

## Credits

- **Templates**: Dillion Verma, MagicUI Design, Nodus
- **Components**: shadcn/ui, MagicUI
- **Framework**: Next.js, Tailwind CSS
- **Infrastructure**: Railway
