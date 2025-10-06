#!/usr/bin/env npx tsx

/**
 * Generate meta.json for all templates
 * Discovers slots, components, pages, and theme tokens
 */

import { promises as fs } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { extractZipSafely } from '../dist/services/zip-extractor.js';
import { findSlotMarkers } from '../dist/services/slot-filler.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const TEMPLATES_DIR = process.env.TEMPLATES_DIR ||
  path.join(process.env.HOME!, 'vibe', 'ui-templates');
const TEMP_DIR = path.join(__dirname, '../.temp');

interface MetaJson {
  id: string;
  name: string;
  version: string;
  description: string;
  stack: {
    framework: string;
    components: string[];
    styling: string[];
  };
  theme: {
    modes: string[];
    tokens: {
      colors: string[];
      typography: string[];
      spacing: string[];
    };
  };
  pages: Array<{
    id: string;
    path: string;
    file: string;
    slots: string[];
  }>;
  components: {
    shadcn: string[];
    magicui: string[];
    custom: string[];
  };
}

/**
 * Discover slots in a file
 */
async function discoverSlotsInFile(filePath: string): Promise<string[]> {
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    const markers = findSlotMarkers(content);
    return Array.from(markers.keys());
  } catch {
    return [];
  }
}

/**
 * Discover components in a file
 */
async function discoverComponentsInFile(filePath: string): Promise<{
  shadcn: string[];
  magicui: string[];
  custom: string[];
}> {
  const components = { shadcn: [] as string[], magicui: [] as string[], custom: [] as string[] };

  try {
    const content = await fs.readFile(filePath, 'utf-8');

    // Find shadcn imports: @/components/ui/button
    const shadcnMatches = content.matchAll(/from ['"]@\/components\/ui\/([^'"]+)['"]/g);
    for (const match of shadcnMatches) {
      const component = match[1];
      if (!components.shadcn.includes(component)) {
        components.shadcn.push(component);
      }
    }

    // Find magicui imports: @/components/magicui/marquee
    const magicuiMatches = content.matchAll(/from ['"]@\/components\/magicui\/([^'"]+)['"]/g);
    for (const match of magicuiMatches) {
      const component = match[1];
      if (!components.magicui.includes(component)) {
        components.magicui.push(component);
      }
    }

    // Find custom imports: @/components/landing/hero
    const customMatches = content.matchAll(/from ['"]@\/components\/(?!ui\/|magicui\/)([^'"]+)['"]/g);
    for (const match of customMatches) {
      const component = match[1];
      if (!components.custom.includes(component)) {
        components.custom.push(component);
      }
    }
  } catch {
    // Ignore errors
  }

  return components;
}

/**
 * Discover pages in extracted template
 */
async function discoverPages(extractPath: string): Promise<MetaJson['pages']> {
  const pages: MetaJson['pages'] = [];

  // Look for pages in common locations
  const searchPaths = [
    path.join(extractPath, 'app'),
    path.join(extractPath, 'src', 'app'),
    path.join(extractPath, 'pages'),
  ];

  for (const searchPath of searchPaths) {
    try {
      await fs.access(searchPath);
      const files = await fs.readdir(searchPath, { recursive: true, withFileTypes: true });

      for (const file of files) {
        if (!file.isFile()) continue;
        if (!['.tsx', '.jsx'].some(ext => file.name.endsWith(ext))) continue;

        const filePath = path.join(file.path || searchPath, file.name);
        const relativePath = path.relative(searchPath, filePath);

        // Extract page ID from path
        const pageId = relativePath
          .replace(/\/(page|index)\.(tsx|jsx)$/, '')
          .replace(/\//g, '-')
          .replace(/^-/, '')
          .toLowerCase() || 'home';

        // Discover slots
        const slots = await discoverSlotsInFile(filePath);

        // Discover components
        const components = await discoverComponentsInFile(filePath);

        pages.push({
          id: pageId,
          path: `/${relativePath.replace(/\/(page|index)\.(tsx|jsx)$/, '')}`,
          file: relativePath,
          slots,
        });
      }
    } catch {
      // Directory doesn't exist
    }
  }

  return pages;
}

/**
 * Discover all components in template
 */
async function discoverAllComponents(extractPath: string): Promise<MetaJson['components']> {
  const allComponents = { shadcn: [] as string[], magicui: [] as string[], custom: [] as string[] };

  // Look for components directory
  const componentsPaths = [
    path.join(extractPath, 'components'),
    path.join(extractPath, 'src', 'components'),
  ];

  for (const componentsPath of componentsPaths) {
    try {
      await fs.access(componentsPath);
      const files = await fs.readdir(componentsPath, { recursive: true, withFileTypes: true });

      for (const file of files) {
        if (!file.isFile()) continue;
        if (!['.tsx', '.jsx'].some(ext => file.name.endsWith(ext))) continue;

        const filePath = path.join(file.path || componentsPath, file.name);
        const relativePath = path.relative(componentsPath, filePath);

        // Categorize component
        if (relativePath.startsWith('ui/')) {
          const component = path.basename(file.name, path.extname(file.name));
          if (!allComponents.shadcn.includes(component)) {
            allComponents.shadcn.push(component);
          }
        } else if (relativePath.startsWith('magicui/')) {
          const component = path.basename(file.name, path.extname(file.name));
          if (!allComponents.magicui.includes(component)) {
            allComponents.magicui.push(component);
          }
        } else {
          const component = relativePath.replace(/\.(tsx|jsx)$/, '');
          if (!allComponents.custom.includes(component)) {
            allComponents.custom.push(component);
          }
        }
      }
    } catch {
      // Directory doesn't exist
    }
  }

  return allComponents;
}

/**
 * Generate meta.json for a template
 */
async function generateMetaForTemplate(templateId: string, zipPath: string): Promise<void> {
  console.log(`\n📦 Processing: ${templateId}`);

  // Extract to temp directory
  const extractPath = path.join(TEMP_DIR, templateId);
  console.log('  Extracting...');

  try {
    await fs.rm(extractPath, { recursive: true, force: true });
  } catch {}

  const buffer = await fs.readFile(zipPath);
  const result = await extractZipSafely(buffer, {
    destDir: extractPath,
    overwrite: true,
  });

  if (!result.success) {
    console.error(`  ❌ Extraction failed:`, result.errors);
    return;
  }

  console.log(`  ✅ Extracted ${result.filesExtracted.length} files`);

  // Discover pages
  console.log('  Discovering pages...');
  const pages = await discoverPages(extractPath);
  console.log(`  Found ${pages.length} pages`);

  // Discover components
  console.log('  Discovering components...');
  const components = await discoverAllComponents(extractPath);
  console.log(`  Found ${components.shadcn.length + components.magicui.length + components.custom.length} components`);

  // Detect framework
  const isReactNative = ['luna', 'multia', 'feedy', 'velora', 'propia', 'caloria', 'walley'].includes(templateId) ||
    templateId.includes('mobile');

  // Create meta.json
  const meta: MetaJson = {
    id: templateId,
    name: templateId.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
    version: '1.0.0',
    description: `${templateId} template`,
    stack: {
      framework: isReactNative ? 'react-native' : 'next.js',
      components: isReactNative ? ['nativewind'] : ['shadcn/ui', 'magicui'],
      styling: isReactNative ? ['nativewind', 'tailwindcss'] : ['tailwindcss', 'css-variables'],
    },
    theme: {
      modes: ['light', 'dark'],
      tokens: {
        colors: ['primary', 'secondary', 'accent', 'background', 'foreground'],
        typography: ['font-family', 'font-size', 'line-height'],
        spacing: ['container', 'section', 'component'],
      },
    },
    pages: pages.slice(0, 10), // Limit to first 10 pages
    components,
  };

  // Write meta.json
  const metaPath = path.join(extractPath, 'meta.json');
  await fs.writeFile(metaPath, JSON.stringify(meta, null, 2));

  console.log(`  ✅ Generated meta.json`);
  console.log(`     Pages: ${meta.pages.length}`);
  console.log(`     Slots: ${meta.pages.reduce((sum, p) => sum + p.slots.length, 0)}`);
  console.log(`     Components: ${meta.components.shadcn.length} shadcn, ${meta.components.magicui.length} magicui, ${meta.components.custom.length} custom`);

  // Copy meta.json back to templates dir
  const destMetaPath = path.join(TEMPLATES_DIR, `${templateId}-meta.json`);
  await fs.copyFile(metaPath, destMetaPath);
  console.log(`  📝 Saved to: ${destMetaPath}`);

  // Cleanup
  try {
    await fs.rm(extractPath, { recursive: true, force: true });
  } catch {}
}

/**
 * Main function
 */
async function main() {
  console.log('🔍 Generating meta.json for all templates...\n');

  // Ensure temp directory
  await fs.mkdir(TEMP_DIR, { recursive: true });

  // Load manifest
  const manifestPath = path.join(TEMPLATES_DIR, 'index.json');
  const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf-8'));

  const templates = Object.values(manifest.templates) as any[];
  console.log(`Found ${templates.length} templates`);

  // Process first 5 templates (to save time)
  const templatesToProcess = templates.slice(0, 5);
  console.log(`Processing ${templatesToProcess.length} templates...\n`);

  for (const template of templatesToProcess) {
    try {
      await generateMetaForTemplate(template.id, template.localPath);
    } catch (error: any) {
      console.error(`❌ Error processing ${template.id}:`, error.message);
    }
  }

  // Cleanup temp directory
  await fs.rm(TEMP_DIR, { recursive: true, force: true });

  console.log('\n✅ Meta generation complete!');
}

main().catch((error) => {
  console.error('❌ Error:', error);
  process.exit(1);
});
