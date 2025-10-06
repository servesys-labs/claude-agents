#!/usr/bin/env npx tsx

/**
 * Generate templates manifest (index.json)
 * Scans all templates and creates metadata with checksums
 */

import { promises as fs } from 'fs';
import path from 'path';
import crypto from 'crypto';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const TEMPLATES_DIR = process.env.TEMPLATES_DIR ||
  path.join(process.env.HOME!, 'vibe', 'ui-templates');
const MANIFEST_PATH = path.join(TEMPLATES_DIR, 'index.json');

interface TemplateManifestEntry {
  id: string;
  name: string;
  version: string;
  sha256: string;
  size: number;
  localPath: string;
  lastUpdated: string;
  framework?: string;
  stack?: string;
}

interface TemplateManifest {
  schemaVersion: string;
  lastUpdated: string;
  templates: Record<string, TemplateManifestEntry>;
}

/**
 * Compute SHA256 checksum of file
 */
async function computeChecksum(filePath: string): Promise<string> {
  const buffer = await fs.readFile(filePath);
  return crypto.createHash('sha256').update(buffer).digest('hex');
}

/**
 * Extract template ID from filename
 */
function extractTemplateId(filename: string): string {
  // Remove .zip extension
  const base = filename.replace(/\.zip$/, '');

  // Common patterns:
  // - dillionverma-portfolio-f1bdbdb.zip → dillionverma-portfolio
  // - magicuidesign-agent-template-67c4ec6bf25256173c4d6a87d3033f21d3200443.zip → magicuidesign-agent-template
  // - caloria-v2-main.zip → caloria-v2
  // - luna-main.zip → luna

  // Remove -main suffix
  const withoutMain = base.replace(/-main$/, '');

  // Remove git commit hashes (long hex strings)
  const withoutHash = withoutMain.replace(/-[a-f0-9]{7,}$/, '');

  return withoutHash;
}

/**
 * Extract metadata from template name
 */
function extractMetadata(templateId: string): Partial<TemplateManifestEntry> {
  const metadata: Partial<TemplateManifestEntry> = {
    name: templateId.split('-').map(w =>
      w.charAt(0).toUpperCase() + w.slice(1)
    ).join(' '),
    version: '1.0.0',
  };

  // Detect framework from template ID
  if (templateId.includes('mobile') ||
      ['luna', 'multia', 'feedy', 'velora', 'propia', 'caloria', 'walley'].includes(templateId)) {
    metadata.framework = 'react-native';
    metadata.stack = 'react-native+expo+nativewind';
  } else {
    metadata.framework = 'next.js';
    metadata.stack = 'next.js+shadcn+magicui';
  }

  return metadata;
}

/**
 * Generate manifest from templates directory
 */
async function generateManifest(): Promise<void> {
  console.log('🔍 Scanning templates directory:', TEMPLATES_DIR);

  const manifest: TemplateManifest = {
    schemaVersion: '1.0.0',
    lastUpdated: new Date().toISOString(),
    templates: {},
  };

  // Find all .zip files
  const files = await fs.readdir(TEMPLATES_DIR);
  const zipFiles = files.filter(f => f.endsWith('.zip'));

  console.log(`📦 Found ${zipFiles.length} template archives\n`);

  for (const filename of zipFiles) {
    const filePath = path.join(TEMPLATES_DIR, filename);
    const stats = await fs.stat(filePath);

    // Extract template ID
    const templateId = extractTemplateId(filename);

    console.log(`Processing: ${templateId}`);
    console.log(`  File: ${filename}`);
    console.log(`  Size: ${Math.round(stats.size / 1024 / 1024)}MB`);

    // Compute checksum
    console.log('  Computing SHA256...');
    const sha256 = await computeChecksum(filePath);
    console.log(`  SHA256: ${sha256.substring(0, 16)}...`);

    // Extract metadata
    const metadata = extractMetadata(templateId);

    // Create manifest entry
    manifest.templates[templateId] = {
      id: templateId,
      name: metadata.name!,
      version: metadata.version!,
      sha256,
      size: stats.size,
      localPath: filePath,
      lastUpdated: stats.mtime.toISOString(),
      framework: metadata.framework,
      stack: metadata.stack,
    };

    console.log(`  ✅ Added to manifest\n`);
  }

  // Write manifest
  await fs.writeFile(MANIFEST_PATH, JSON.stringify(manifest, null, 2));

  console.log('📝 Manifest generated successfully!');
  console.log(`   Location: ${MANIFEST_PATH}`);
  console.log(`   Templates: ${Object.keys(manifest.templates).length}`);
  console.log(`   Total size: ${Math.round(
    Object.values(manifest.templates).reduce((sum, t) => sum + t.size, 0) / 1024 / 1024
  )}MB`);
}

generateManifest().catch((error) => {
  console.error('❌ Error generating manifest:', error);
  process.exit(1);
});
