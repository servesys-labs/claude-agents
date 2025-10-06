import { promises as fs } from 'fs';
import path from 'path';
import axios from 'axios';
import { computeChecksum } from './zip-extractor.js';

/**
 * Local template cache with Railway API fallback
 */

export interface TemplateCacheEntry {
  id: string;
  name: string;
  version: string;
  sha256: string;
  size: number;
  localPath: string;
  lastUpdated: string;
}

export interface TemplateManifest {
  schemaVersion: string;
  lastUpdated: string;
  templates: Record<string, TemplateCacheEntry>;
}

const TEMPLATES_DIR = process.env.TEMPLATES_DIR || path.join(process.env.HOME || '~', 'vibe', 'ui-templates');
const MANIFEST_PATH = path.join(TEMPLATES_DIR, 'index.json');
const API_BASE_URL = process.env.UI_TEMPLATE_API_URL ||
  'https://ui-template-api-production-production.up.railway.app';

/**
 * Load template manifest
 */
export async function loadManifest(): Promise<TemplateManifest> {
  try {
    const content = await fs.readFile(MANIFEST_PATH, 'utf-8');
    return JSON.parse(content);
  } catch {
    // Manifest doesn't exist, create default
    return {
      schemaVersion: '1.0.0',
      lastUpdated: new Date().toISOString(),
      templates: {},
    };
  }
}

/**
 * Save template manifest
 */
export async function saveManifest(manifest: TemplateManifest): Promise<void> {
  await fs.mkdir(TEMPLATES_DIR, { recursive: true });
  manifest.lastUpdated = new Date().toISOString();
  await fs.writeFile(MANIFEST_PATH, JSON.stringify(manifest, null, 2));
}

/**
 * Check if template exists in local cache
 */
export async function isTemplateInCache(templateId: string): Promise<boolean> {
  const manifest = await loadManifest();
  const entry = manifest.templates[templateId];

  if (!entry) return false;

  try {
    await fs.access(entry.localPath);
    return true;
  } catch {
    return false;
  }
}

/**
 * Get template from cache
 */
export async function getTemplateFromCache(
  templateId: string
): Promise<TemplateCacheEntry | null> {
  const manifest = await loadManifest();
  const entry = manifest.templates[templateId];

  if (!entry) return null;

  try {
    await fs.access(entry.localPath);
    return entry;
  } catch {
    return null;
  }
}

/**
 * Download template from Railway API
 */
export async function downloadTemplateFromAPI(
  templateId: string
): Promise<{ buffer: Buffer; size: number }> {
  const url = `${API_BASE_URL}/api/templates/${templateId}/download`;

  try {
    const response = await axios.get(url, {
      responseType: 'arraybuffer',
      timeout: 120000, // 2 minute timeout for large templates
    });

    return {
      buffer: Buffer.from(response.data),
      size: response.data.length,
    };
  } catch (error: any) {
    throw new Error(`Failed to download template from API: ${error.message}`);
  }
}

/**
 * Add template to cache
 */
export async function addTemplateToCache(
  templateId: string,
  buffer: Buffer,
  metadata?: Partial<TemplateCacheEntry>
): Promise<TemplateCacheEntry> {
  const manifest = await loadManifest();

  // Ensure templates directory exists
  await fs.mkdir(TEMPLATES_DIR, { recursive: true });

  // Save ZIP file
  const zipPath = path.join(TEMPLATES_DIR, `${templateId}.zip`);
  await fs.writeFile(zipPath, buffer);

  // Compute checksum
  const sha256 = await computeChecksum(zipPath);

  // Create cache entry
  const entry: TemplateCacheEntry = {
    id: templateId,
    name: metadata?.name || templateId,
    version: metadata?.version || '1.0.0',
    sha256,
    size: buffer.length,
    localPath: zipPath,
    lastUpdated: new Date().toISOString(),
  };

  // Update manifest
  manifest.templates[templateId] = entry;
  await saveManifest(manifest);

  return entry;
}

/**
 * Get template with fallback (cache -> API)
 */
export async function getTemplate(
  templateId: string,
  forceRefresh = false
): Promise<{ buffer: Buffer; entry: TemplateCacheEntry; source: 'cache' | 'api' }> {
  // Try cache first (unless force refresh)
  if (!forceRefresh) {
    const cachedEntry = await getTemplateFromCache(templateId);

    if (cachedEntry) {
      try {
        const buffer = await fs.readFile(cachedEntry.localPath);

        // Verify checksum
        const actualChecksum = await computeChecksum(cachedEntry.localPath);
        if (actualChecksum === cachedEntry.sha256) {
          return { buffer, entry: cachedEntry, source: 'cache' };
        } else {
          console.warn(`[Cache] Checksum mismatch for ${templateId}, re-downloading`);
        }
      } catch (error) {
        console.warn(`[Cache] Failed to read cached template ${templateId}:`, error);
      }
    }
  }

  // Fallback to API
  console.log(`[API] Downloading template ${templateId} from Railway`);
  const { buffer, size } = await downloadTemplateFromAPI(templateId);

  // Add to cache
  const entry = await addTemplateToCache(templateId, buffer);

  return { buffer, entry, source: 'api' };
}

/**
 * List all templates (cache + API)
 */
export async function listAllTemplates(): Promise<{
  cached: TemplateCacheEntry[];
  available: any[];
}> {
  // Get cached templates
  const manifest = await loadManifest();
  const cached = Object.values(manifest.templates);

  // Get available templates from API
  let available: any[] = [];
  try {
    const response = await axios.get(`${API_BASE_URL}/api/templates`, {
      timeout: 10000,
    });
    available = response.data.templates || [];
  } catch (error) {
    console.warn('[API] Failed to fetch template list from Railway:', error);
  }

  return { cached, available };
}

/**
 * Refresh template cache (re-download from API)
 */
export async function refreshCache(templateId: string): Promise<TemplateCacheEntry> {
  console.log(`[Cache] Refreshing ${templateId} from API`);
  const { buffer, entry } = await getTemplate(templateId, true);
  return entry;
}

/**
 * Clear entire cache
 */
export async function clearCache(): Promise<void> {
  const manifest = await loadManifest();

  for (const entry of Object.values(manifest.templates)) {
    try {
      await fs.unlink(entry.localPath);
    } catch {
      // File may already be deleted
    }
  }

  // Reset manifest
  manifest.templates = {};
  await saveManifest(manifest);
}

/**
 * Get cache statistics
 */
export async function getCacheStats(): Promise<{
  totalTemplates: number;
  totalSize: number;
  oldestEntry: string | null;
  newestEntry: string | null;
}> {
  const manifest = await loadManifest();
  const entries = Object.values(manifest.templates);

  const totalSize = entries.reduce((sum, entry) => sum + entry.size, 0);

  let oldest: TemplateCacheEntry | null = null;
  let newest: TemplateCacheEntry | null = null;

  for (const entry of entries) {
    if (!oldest || entry.lastUpdated < oldest.lastUpdated) {
      oldest = entry;
    }
    if (!newest || entry.lastUpdated > newest.lastUpdated) {
      newest = entry;
    }
  }

  return {
    totalTemplates: entries.length,
    totalSize,
    oldestEntry: oldest?.id || null,
    newestEntry: newest?.id || null,
  };
}

/**
 * Verify cache integrity
 */
export async function verifyCacheIntegrity(): Promise<{
  valid: string[];
  corrupted: string[];
  missing: string[];
}> {
  const manifest = await loadManifest();
  const result = {
    valid: [] as string[],
    corrupted: [] as string[],
    missing: [] as string[],
  };

  for (const [templateId, entry] of Object.entries(manifest.templates)) {
    try {
      await fs.access(entry.localPath);

      const actualChecksum = await computeChecksum(entry.localPath);
      if (actualChecksum === entry.sha256) {
        result.valid.push(templateId);
      } else {
        result.corrupted.push(templateId);
      }
    } catch {
      result.missing.push(templateId);
    }
  }

  return result;
}
