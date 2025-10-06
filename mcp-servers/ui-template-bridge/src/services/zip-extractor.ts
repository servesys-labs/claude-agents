import AdmZip from 'adm-zip';
import path from 'path';
import { promises as fs } from 'fs';

/**
 * Secure ZIP extraction with Zip Slip prevention
 */

// Safety limits to prevent decompression bombs
const MAX_TOTAL_SIZE = 200 * 1024 * 1024; // 200MB
const MAX_FILE_COUNT = 10000; // 10k files
const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB per file

export interface ExtractOptions {
  destDir: string;
  overwrite?: boolean;
  dryRun?: boolean;
}

export interface ExtractResult {
  success: boolean;
  filesExtracted: string[];
  warnings: string[];
  errors: string[];
  totalSize: number;
}

/**
 * Safely extract ZIP file with path traversal prevention
 */
export async function extractZipSafely(
  zipBuffer: Buffer,
  options: ExtractOptions
): Promise<ExtractResult> {
  const { destDir, overwrite = false, dryRun = false } = options;
  const result: ExtractResult = {
    success: false,
    filesExtracted: [],
    warnings: [],
    errors: [],
    totalSize: 0,
  };

  try {
    const zip = new AdmZip(zipBuffer);
    const entries = zip.getEntries();

    // Resolve destination directory to absolute path
    const resolvedDestDir = path.resolve(destDir);

    // Check if destination exists and is not empty (unless overwrite is true)
    try {
      const existingFiles = await fs.readdir(resolvedDestDir);
      if (existingFiles.length > 0 && !overwrite && !dryRun) {
        result.errors.push('CONFLICT_EXISTS: Destination directory is not empty. Use overwrite=true to replace.');
        return result;
      }
    } catch {
      // Directory doesn't exist, will be created
    }

    // Decompression bomb check: file count limit
    if (entries.length > MAX_FILE_COUNT) {
      result.errors.push(`FILE_COUNT_EXCEEDED: Archive contains ${entries.length} files (max ${MAX_FILE_COUNT})`);
      return result;
    }

    // Validate all entries before extraction
    for (const entry of entries) {
      if (entry.isDirectory) continue;

      const entryName = entry.entryName;

      // Resolve the full path where the entry would be extracted
      const fullPath = path.resolve(resolvedDestDir, entryName);

      // Security check: Ensure the path stays within destDir (prevent Zip Slip)
      if (!fullPath.startsWith(resolvedDestDir + path.sep)) {
        result.errors.push(`PATH_TRAVERSAL_BLOCKED: ${entryName} attempts path traversal`);
        continue;
      }

      // Check for absolute paths
      if (path.isAbsolute(entryName)) {
        result.errors.push(`ABSOLUTE_PATH_BLOCKED: ${entryName} uses absolute path`);
        continue;
      }

      // Check for suspicious patterns
      if (entryName.includes('..') || entryName.includes('~/')) {
        result.errors.push(`SUSPICIOUS_PATH: ${entryName} contains suspicious patterns`);
        continue;
      }

      // Note: Symlink detection would require checking file attributes
      // which aren't reliably exposed by adm-zip. We rely on path checks above.

      // Decompression bomb check: per-file size limit
      if (entry.header.size > MAX_FILE_SIZE) {
        result.errors.push(`FILE_SIZE_EXCEEDED: ${entryName} is ${Math.round(entry.header.size / 1024 / 1024)}MB (max ${MAX_FILE_SIZE / 1024 / 1024}MB)`);
        continue;
      }

      // Accumulate total size
      result.totalSize += entry.header.size;

      // Warn for large files (but don't block)
      if (entry.header.size > 50 * 1024 * 1024) {
        result.warnings.push(`LARGE_FILE: ${entryName} is ${Math.round(entry.header.size / 1024 / 1024)}MB`);
      }

      result.filesExtracted.push(entryName);
    }

    // If there were blocking errors, fail
    if (result.errors.length > 0) {
      return result;
    }

    // Decompression bomb check: total size limit
    if (result.totalSize > MAX_TOTAL_SIZE) {
      result.errors.push(`TOTAL_SIZE_EXCEEDED: Archive expands to ${Math.round(result.totalSize / 1024 / 1024)}MB (max ${MAX_TOTAL_SIZE / 1024 / 1024}MB)`);
      return result;
    }

    // Dry run: return preview without extracting
    if (dryRun) {
      result.success = true;
      result.warnings.push('DRY_RUN: No files were extracted');
      return result;
    }

    // Create destination directory
    await fs.mkdir(resolvedDestDir, { recursive: true });

    // Extract files safely
    for (const entry of entries) {
      if (entry.isDirectory) continue;

      const fullPath = path.resolve(resolvedDestDir, entry.entryName);

      // Create parent directory
      const dirName = path.dirname(fullPath);
      await fs.mkdir(dirName, { recursive: true });

      // Extract file
      const data = entry.getData();
      await fs.writeFile(fullPath, data);
    }

    result.success = true;
    return result;
  } catch (error: any) {
    result.errors.push(`EXTRACTION_FAILED: ${error.message}`);
    return result;
  }
}

/**
 * Extract ZIP from local file path
 */
export async function extractZipFromFile(
  zipPath: string,
  options: ExtractOptions
): Promise<ExtractResult> {
  try {
    const buffer = await fs.readFile(zipPath);
    return await extractZipSafely(buffer, options);
  } catch (error: any) {
    return {
      success: false,
      filesExtracted: [],
      warnings: [],
      errors: [`FILE_READ_ERROR: ${error.message}`],
      totalSize: 0,
    };
  }
}

/**
 * Compute SHA256 checksum of file
 */
export async function computeChecksum(filePath: string): Promise<string> {
  const crypto = await import('crypto');
  const buffer = await fs.readFile(filePath);
  return crypto.createHash('sha256').update(buffer).digest('hex');
}

/**
 * Verify ZIP integrity with checksum
 */
export async function verifyZipIntegrity(
  zipPath: string,
  expectedChecksum: string
): Promise<boolean> {
  const actualChecksum = await computeChecksum(zipPath);
  return actualChecksum === expectedChecksum;
}
