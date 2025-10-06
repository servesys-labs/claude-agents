import { promises as fs } from 'fs';
import path from 'path';

/**
 * Slot filling service - replaces content between comment markers in TSX/MDX
 */

export interface SlotMarker {
  slotId: string;
  startLine: number;
  endLine: number;
  currentContent: string;
}

export interface FillSlotOptions {
  sitePath: string;
  pageId: string;
  slotId: string;
  content: string;
  type?: 'text' | 'richtext' | 'markdown' | 'component';
  dryRun?: boolean;
}

export interface FillSlotResult {
  success: boolean;
  changed: boolean;
  changedFiles: string[];
  warnings: string[];
  errors: string[];
  preview?: string;
}

/**
 * Find slot markers in file content
 */
export function findSlotMarkers(content: string): Map<string, SlotMarker> {
  const markers = new Map<string, SlotMarker>();
  const lines = content.split('\n');

  let currentSlot: { slotId: string; startLine: number } | null = null;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Match: {/* SLOT:slot-id:START */} or {/* SLOT:slot-id */}
    const startMatch = line.match(/\{\/\*\s*SLOT:([a-z0-9-]+)(:START)?\s*\*\/\}/);
    if (startMatch) {
      currentSlot = { slotId: startMatch[1], startLine: i };
      continue;
    }

    // Match: {/* SLOT:slot-id:END */} or {/* /SLOT */}
    const endMatch = line.match(/\{\/\*\s*(SLOT:[a-z0-9-]+:END|\/SLOT)\s*\*\/\}/);
    if (endMatch && currentSlot) {
      const slotContent = lines.slice(currentSlot.startLine + 1, i).join('\n');
      markers.set(currentSlot.slotId, {
        slotId: currentSlot.slotId,
        startLine: currentSlot.startLine,
        endLine: i,
        currentContent: slotContent,
      });
      currentSlot = null;
    }
  }

  return markers;
}

/**
 * Replace content between slot markers
 */
export function replaceSlotContent(
  fileContent: string,
  slotId: string,
  newContent: string
): { success: boolean; content: string; error?: string } {
  const lines = fileContent.split('\n');
  const markers = findSlotMarkers(fileContent);

  const marker = markers.get(slotId);
  if (!marker) {
    return {
      success: false,
      content: fileContent,
      error: `SLOT_NOT_FOUND: Slot '${slotId}' not found in file`,
    };
  }

  // Replace content between markers
  const before = lines.slice(0, marker.startLine + 1);
  const after = lines.slice(marker.endLine);

  // Preserve indentation from original content
  const indentMatch = lines[marker.startLine + 1]?.match(/^(\s*)/);
  const indent = indentMatch ? indentMatch[1] : '';

  // Indent new content
  const indentedContent = newContent
    .split('\n')
    .map((line) => (line.trim() ? indent + line : line))
    .join('\n');

  const newLines = [...before, indentedContent, ...after];

  return {
    success: true,
    content: newLines.join('\n'),
  };
}

/**
 * Find files containing a specific page ID
 */
export async function findPageFiles(
  sitePath: string,
  pageId: string
): Promise<string[]> {
  const searchPaths = [
    path.join(sitePath, 'app', `${pageId}.tsx`),
    path.join(sitePath, 'app', `${pageId}.jsx`),
    path.join(sitePath, 'app', `${pageId}.mdx`),
    path.join(sitePath, 'app', pageId, 'page.tsx'),
    path.join(sitePath, 'app', pageId, 'page.jsx'),
    path.join(sitePath, 'app', pageId, 'page.mdx'),
    path.join(sitePath, 'src', 'app', `${pageId}.tsx`),
    path.join(sitePath, 'src', 'app', pageId, 'page.tsx'),
    path.join(sitePath, 'pages', `${pageId}.tsx`),
    path.join(sitePath, 'pages', `${pageId}.jsx`),
    path.join(sitePath, 'pages', `${pageId}.mdx`),
  ];

  const existingFiles: string[] = [];

  for (const filePath of searchPaths) {
    try {
      await fs.access(filePath);
      existingFiles.push(filePath);
    } catch {
      // File doesn't exist, skip
    }
  }

  return existingFiles;
}

/**
 * Fill a content slot with new content
 */
export async function fillSlot(
  options: FillSlotOptions
): Promise<FillSlotResult> {
  const { sitePath, pageId, slotId, content, dryRun = false } = options;

  const result: FillSlotResult = {
    success: false,
    changed: false,
    changedFiles: [],
    warnings: [],
    errors: [],
  };

  try {
    // Find page files
    const pageFiles = await findPageFiles(sitePath, pageId);

    if (pageFiles.length === 0) {
      result.errors.push(`PAGE_NOT_FOUND: No files found for page '${pageId}'`);
      return result;
    }

    if (pageFiles.length > 1) {
      result.warnings.push(
        `MULTIPLE_FILES: Found ${pageFiles.length} files for page '${pageId}', using first match`
      );
    }

    const targetFile = pageFiles[0];

    // Read file content
    const fileContent = await fs.readFile(targetFile, 'utf-8');

    // Find slot markers
    const markers = findSlotMarkers(fileContent);

    if (!markers.has(slotId)) {
      result.errors.push(
        `SLOT_NOT_FOUND: Slot '${slotId}' not found in ${path.relative(sitePath, targetFile)}`
      );
      result.warnings.push(
        `Available slots: ${Array.from(markers.keys()).join(', ') || 'none'}`
      );
      return result;
    }

    // Replace content
    const { success, content: newContent, error } = replaceSlotContent(
      fileContent,
      slotId,
      content
    );

    if (!success) {
      result.errors.push(error || 'Unknown error');
      return result;
    }

    // Check if content actually changed
    if (newContent === fileContent) {
      result.success = true;
      result.changed = false;
      result.warnings.push('NO_CHANGES: Content is identical to existing slot content');
      return result;
    }

    // Dry run: return preview
    if (dryRun) {
      result.success = true;
      result.changed = true;
      result.changedFiles = [path.relative(sitePath, targetFile)];
      result.warnings.push('DRY_RUN: No files were modified');
      result.preview = newContent;
      return result;
    }

    // Write updated content
    await fs.writeFile(targetFile, newContent, 'utf-8');

    result.success = true;
    result.changed = true;
    result.changedFiles = [path.relative(sitePath, targetFile)];

    return result;
  } catch (error: any) {
    result.errors.push(`FILL_SLOT_ERROR: ${error.message}`);
    return result;
  }
}

/**
 * List all slots in a file
 */
export async function listSlotsInFile(filePath: string): Promise<string[]> {
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    const markers = findSlotMarkers(content);
    return Array.from(markers.keys());
  } catch {
    return [];
  }
}

/**
 * List all slots in a site
 */
export async function listAllSlots(sitePath: string): Promise<Map<string, string[]>> {
  const slotsByFile = new Map<string, string[]>();

  async function scanDir(dir: string) {
    try {
      const entries = await fs.readdir(dir, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
          if (!entry.name.startsWith('.') && entry.name !== 'node_modules') {
            await scanDir(fullPath);
          }
        } else if (entry.name.match(/\.(tsx|jsx|mdx)$/)) {
          const slots = await listSlotsInFile(fullPath);
          if (slots.length > 0) {
            slotsByFile.set(path.relative(sitePath, fullPath), slots);
          }
        }
      }
    } catch {
      // Skip directories we can't access
    }
  }

  await scanDir(sitePath);
  return slotsByFile;
}
