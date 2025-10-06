# Component-Level Screenshot Plan

## Problem
Agents need visual references for individual components (buttons, cards, forms, etc.) to:
- Understand component variants and states
- See styling patterns and design tokens
- Make informed decisions when adding components

## Current State
- ✅ Full-page screenshots (desktop + mobile)
- ❌ No component-level screenshots
- ❌ No Storybook in templates

## Solution: Two-Phase Approach

### Phase 1: Component Discovery & Extraction (NOW)
1. **Discover components** via `generate-meta.ts` (already built)
   - Scans `components/ui/` for shadcn components
   - Detects magicui components
   - Finds custom components

2. **Create dynamic showcase page**
   - Generate temp route: `app/_component-showcase/page.tsx`
   - Imports all discovered components
   - Renders each with common variants:
     - Buttons: default, primary, secondary, outline, ghost
     - Inputs: empty, filled, error, disabled
     - Cards: with/without image, with/without actions
     - Etc.

3. **Screenshot showcase page**
   - Navigate to `/_ component-showcase`
   - Capture full page
   - Extract individual component screenshots via cropping (optional)

4. **Catalog**
   - Add `components` section to catalog.json
   - Link each component to screenshot

### Phase 2: Storybook Integration (FUTURE)
1. **Auto-generate Storybook**
   - Add Storybook to template during `init_site`
   - Generate stories for discovered components
   - Screenshot each story variant

2. **Storybook server**
   - Start Storybook dev server
   - Capture iframe screenshots of each story
   - More granular control

## Implementation for Phase 1

### 1. Enhance `generate-meta.ts`
```typescript
// Already discovers components, now add:
interface ComponentMeta {
  name: string;
  path: string;
  type: 'shadcn' | 'magicui' | 'custom';
  props?: Record<string, any>; // Extract from TypeScript
}
```

### 2. Create `generate-component-showcase.ts`
```typescript
async function createShowcasePage(
  projectPath: string,
  components: ComponentMeta[]
): Promise<string> {
  const showcasePath = path.join(projectPath, 'app/_component-showcase/page.tsx');

  const content = `
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
// ... more imports

export default function ComponentShowcase() {
  return (
    <div className="p-8 space-y-12">
      <section>
        <h2>Buttons</h2>
        <div className="flex gap-4">
          <Button>Default</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
        </div>
      </section>

      <section>
        <h2>Cards</h2>
        <div className="grid grid-cols-3 gap-4">
          <Card>Basic Card</Card>
          <Card className="p-6">With Padding</Card>
        </div>
      </section>

      {/* Auto-generated for all discovered components */}
    </div>
  );
}
`;

  await fs.writeFile(showcasePath, content);
  return '/_component-showcase';
}
```

### 3. Update `generate-screenshots.ts`
```typescript
// After page screenshots, add:
if (hasComponents) {
  const showcaseRoute = await createShowcasePage(projectPath, components);
  await captureScreenshot(showcaseRoute, 'components-showcase');
  await cleanupShowcasePage(projectPath); // Remove temp route
}
```

### 4. Catalog Structure
```json
{
  "templates": {
    "template-id": {
      "screenshots": [...],
      "components": [
        {
          "name": "Button",
          "type": "shadcn",
          "screenshot": "template-id-button.png",
          "variants": ["default", "secondary", "outline", "ghost"]
        }
      ]
    }
  }
}
```

## Benefits

**Phase 1 (Quick Win)**:
- No Storybook dependency
- Works with existing templates
- Single screenshot per template showing all components
- Minimal setup time

**Phase 2 (Future)**:
- Isolated component screenshots
- Interactive documentation
- Better variant coverage
- Industry-standard tooling

## Timeline

- **Phase 1**: 2-3 hours (implement showcase generation)
- **Phase 2**: 1-2 days (Storybook integration + story generation)

## Decision

Start with Phase 1 to get immediate value. Migrate to Phase 2 after validating the approach.
