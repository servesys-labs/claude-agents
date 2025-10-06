import AdmZip from 'adm-zip';
import path from 'path';
import { promises as fs } from 'fs';
import { getTemplate } from './template-cache.js';
import { writeFilesAtomic } from './atomic-writer.js';

export interface ListComponentsResult {
  ok: boolean;
  templateId: string;
  count: number;
  components: Array<{
    path: string; // path inside archive
    name: string;
    type: 'section' | 'ui' | 'component' | 'unknown';
    size: number;
  }>;
  warnings?: string[];
}

export interface ExtractComponentParams {
  templateId: string;
  componentPath: string; // path in template (e.g., src/components/sections/hero.tsx)
  destination: string; // file or directory on disk
  withDependencies?: boolean; // copy relative imports
  maxDepth?: number; // max depth for dependency tracking (default: 3)
  overwrite?: boolean;
  dryRun?: boolean;
}

export interface ExtractComponentResult {
  success: boolean;
  filesWritten: string[];
  preview?: Array<{ path: string; bytes: number }>;
  warnings: string[];
  errors: string[];
}

function isComponentFile(entryName: string): boolean {
  if (!entryName) return false;
  const lowered = entryName.toLowerCase();
  if (lowered.endsWith('.tsx') || lowered.endsWith('.jsx')) {
    return (
      lowered.includes('/components/') ||
      lowered.includes('/src/components/') ||
      lowered.startsWith('components/') ||
      lowered.startsWith('src/components/')
    );
  }
  return false;
}

function guessComponentType(entryName: string): 'section' | 'ui' | 'component' | 'unknown' {
  const lowered = entryName.toLowerCase();
  if (lowered.includes('/sections/')) return 'section';
  if (lowered.includes('/ui/')) return 'ui';
  if (lowered.includes('/components/')) return 'component';
  return 'unknown';
}

function toBasenameNoExt(entryName: string): string {
  const base = path.basename(entryName);
  return base.replace(/\.(tsx|jsx)$/i, '');
}

/**
 * List extractable components inside a template archive
 */
export async function listComponents(templateId: string): Promise<ListComponentsResult> {
  const warnings: string[] = [];
  const { buffer } = await getTemplate(templateId);
  const zip = new AdmZip(buffer);
  const entries = zip.getEntries();

  const components = entries
    .filter((e) => !e.isDirectory && isComponentFile(e.entryName))
    .map((e) => ({
      path: e.entryName,
      name: toBasenameNoExt(e.entryName),
      type: guessComponentType(e.entryName),
      size: e.header.size || e.getData().length,
    }));

  if (components.length === 0) {
    warnings.push('NO_COMPONENTS_FOUND: No files under components/ or src/components/');
  }

  return {
    ok: true,
    templateId,
    count: components.length,
    components,
    warnings: warnings.length ? warnings : undefined,
  };
}

function normalizeArchivePath(p: string): string {
  return p.replace(/^\.\//, '').replace(/\\/g, '/');
}

/**
 * Resolve a relative import specifier within the archive
 */
function resolveRelativeImport(baseEntry: string, spec: string): string {
  const baseDir = path.posix.dirname(normalizeArchivePath(baseEntry));
  const candidate = normalizeArchivePath(path.posix.join(baseDir, spec));
  return candidate;
}

/**
 * Parse import specifiers from TS/JS content
 */
function parseImportSpecifiers(content: string): string[] {
  const specs = new Set<string>();
  const importRegex = /import\s+(?:[^'"\n]+\s+from\s+)?["']([^"']+)["'];?/g;
  let m: RegExpExecArray | null;
  while ((m = importRegex.exec(content))) {
    specs.add(m[1]);
  }
  return Array.from(specs);
}

/**
 * Detect alias prefixes used in imports (e.g., @/ or ~/)
 */
function detectAliases(content: string): Set<string> {
  const aliases = new Set<string>();
  const specs = parseImportSpecifiers(content);
  for (const spec of specs) {
    const match = spec.match(/^(@[^/]+\/|~\/)/);
    if (match) aliases.add(match[1]);
  }
  return aliases;
}

/**
 * Remap import paths from template aliases to target paths
 * For now, we keep @/ aliases as-is and warn about them
 */
function remapImportPaths(content: string, warnings: string[]): string {
  const aliases = detectAliases(content);
  if (aliases.size > 0) {
    warnings.push(`ALIAS_DETECTED: Found import aliases [${Array.from(aliases).join(', ')}]. Ensure target project has matching tsconfig paths.`);
  }
  // In Phase 1, we preserve aliases as-is
  // Phase 2 could add conversion logic based on target tsconfig.json
  return content;
}

/**
 * Extract static asset imports from JSX/TSX content
 * Matches: import heroImg from './hero.jpg'
 */
function extractAssetImports(content: string): string[] {
  const assets: string[] = [];
  const importRegex = /import\s+\w+\s+from\s+['"](\.[^'"]+\.(jpg|jpeg|png|gif|svg|webp|ico))['"];?/gi;
  let m: RegExpExecArray | null;
  while ((m = importRegex.exec(content))) {
    assets.push(m[1]);
  }
  return assets;
}

/**
 * Recursively collect dependencies up to maxDepth
 * @param entries - ZIP entries from template
 * @param entryPath - Starting archive path
 * @param maxDepth - Max recursion depth (0 = no deps, 1 = direct deps only)
 * @param visited - Set of already visited paths (prevents cycles)
 * @param warnings - Warnings array to populate
 */
function collectDependencies(
  entries: AdmZip.IZipEntry[],
  entryPath: string,
  maxDepth: number,
  visited: Set<string>,
  warnings: string[]
): Map<string, string> {
  const collected = new Map<string, string>(); // archive path -> content

  if (maxDepth < 0 || visited.has(entryPath)) return collected;
  visited.add(entryPath);

  // Find the entry
  const normalized = normalizeArchivePath(entryPath);
  const entry = entries.find(e => normalizeArchivePath(e.entryName) === normalized);
  if (!entry || entry.isDirectory) return collected;

  const content = entry.getData().toString('utf-8');
  collected.set(entry.entryName, content);

  // If maxDepth is 0, don't recurse into dependencies
  if (maxDepth === 0) return collected;

  // Parse imports and recurse
  const specs = parseImportSpecifiers(content);
  for (const spec of specs) {
    // Only follow relative imports
    if (!(spec.startsWith('./') || spec.startsWith('../'))) continue;

    const resolved = resolveRelativeImport(entry.entryName, spec);
    const candidates = [
      resolved,
      `${resolved}.ts`,
      `${resolved}.tsx`,
      `${resolved}.js`,
      `${resolved}.jsx`,
      `${resolved}.css`,
      `${resolved}.scss`
    ];

    let found: AdmZip.IZipEntry | null = null;
    for (const c of candidates) {
      const match = entries.find(e => normalizeArchivePath(e.entryName) === normalizeArchivePath(c));
      if (match && !match.isDirectory) {
        found = match;
        break;
      }
    }

    if (found) {
      // Recurse with reduced depth
      const subDeps = collectDependencies(entries, found.entryName, maxDepth - 1, visited, warnings);
      for (const [path, cont] of subDeps) {
        if (!collected.has(path)) {
          collected.set(path, cont);
        }
      }
    } else {
      warnings.push(`DEPENDENCY_NOT_FOUND: ${spec} (referenced from ${path.basename(entry.entryName)})`);
    }
  }

  // Note: Asset imports (images, etc.) are detected but not auto-copied in Phase 1
  // Phase 2 will add asset extraction to public/assets/
  // For now, we just warn if assets are detected
  if (entry.entryName.match(/\.(tsx|jsx)$/i)) {
    const assetPaths = extractAssetImports(content);
    if (assetPaths.length > 0) {
      warnings.push(`ASSET_IMPORTS_DETECTED: ${assetPaths.length} asset(s) referenced in ${path.basename(entry.entryName)}. Manual copy may be required.`);
    }
  }

  return collected;
}

/**
 * Extract a component file (and optionally its relative dependencies) from the template archive
 * Now with depth-limited recursive dependency tracking and import remapping
 */
export async function extractComponent(
  params: ExtractComponentParams
): Promise<ExtractComponentResult> {
  const {
    templateId,
    componentPath,
    destination,
    withDependencies = true,
    maxDepth = 3,
    dryRun = false
  } = params;

  const result: ExtractComponentResult = {
    success: false,
    filesWritten: [],
    warnings: [],
    errors: [],
  };

  const { buffer } = await getTemplate(templateId);
  const zip = new AdmZip(buffer);
  const entries = zip.getEntries();

  // Find matching entry by suffix (to ignore repo root folder prefixes in ZIP)
  const wantedSuffix = normalizeArchivePath(componentPath);
  const matches = entries.filter((e) => !e.isDirectory && normalizeArchivePath(e.entryName).endsWith(wantedSuffix));

  if (matches.length === 0) {
    result.errors.push(`COMPONENT_NOT_FOUND: ${componentPath}`);
    return result;
  }
  if (matches.length > 1) {
    result.warnings.push(`MULTIPLE_MATCHES: ${matches.length} files end with '${componentPath}', using first.`);
  }

  const targetEntry = matches[0];
  const filesToWrite: Array<{ path: string; content: string }> = [];

  // Helper to queue a file write, computing proper destination
  const queueWrite = (archivePath: string, content: string) => {
    let destPath = destination;
    const looksLikeFile = /\.(tsx|jsx|ts|js|css|scss)$/i.test(destination);
    if (!looksLikeFile) {
      // Preserve relative path under components/ subtree if present, else use basename
      const normalized = normalizeArchivePath(archivePath);
      const idx = normalized.toLowerCase().lastIndexOf('/components/');
      const rel = idx >= 0 ? normalized.slice(idx + 1) : path.posix.basename(normalized);
      destPath = path.join(destination, rel);
    }
    filesToWrite.push({ path: destPath, content });
  };

  // Collect component and dependencies recursively (if enabled)
  let allFiles: Map<string, string>;

  if (withDependencies) {
    // Use depth-limited recursive collection
    const visited = new Set<string>();
    allFiles = collectDependencies(entries, targetEntry.entryName, maxDepth, visited, result.warnings);
  } else {
    // Just the primary component
    const primaryContent = targetEntry.getData().toString('utf-8');
    allFiles = new Map([[targetEntry.entryName, primaryContent]]);
  }

  // Remap imports and queue writes
  for (const [archivePath, content] of allFiles) {
    const remapped = remapImportPaths(content, result.warnings);
    queueWrite(archivePath, remapped);
  }

  // Dry run preview
  if (dryRun) {
    return {
      success: true,
      filesWritten: [],
      preview: filesToWrite.map((f) => ({ path: f.path, bytes: Buffer.byteLength(f.content) })),
      warnings: result.warnings,
      errors: [],
    };
  }

  // Write files atomically
  const writePlan = filesToWrite.map((f) => ({ path: f.path, content: f.content }));
  const writeRes = await writeFilesAtomic(writePlan);
  if (!writeRes.success) {
    result.errors.push(...writeRes.failed.map((f) => `WRITE_FAILED: ${f.path}: ${f.error}`));
    return result;
  }

  result.success = true;
  result.filesWritten = writeRes.written;
  return result;
}

