import { promises as fs } from 'fs';
import path from 'path';
import crypto from 'crypto';

/**
 * Atomic file writer with temp + swap pattern
 * Ensures files are written atomically (all-or-nothing)
 */

export interface AtomicWriteOptions {
  content: string;
  encoding?: BufferEncoding;
}

export interface AtomicWriteResult {
  success: boolean;
  path: string;
  tempPath?: string;
  error?: string;
}

/**
 * Write file atomically using temp + atomic rename
 *
 * Pattern:
 * 1. Write to temp file (.tmp-<random>)
 * 2. Verify write succeeded
 * 3. Atomic rename to target path
 * 4. On failure, leave original untouched
 */
export async function writeFileAtomic(
  filePath: string,
  options: AtomicWriteOptions
): Promise<AtomicWriteResult> {
  const { content, encoding = 'utf-8' } = options;

  // Generate temp file path in same directory (required for atomic rename)
  const dir = path.dirname(filePath);
  const basename = path.basename(filePath);
  const randomSuffix = crypto.randomBytes(8).toString('hex');
  const tempPath = path.join(dir, `.tmp-${basename}-${randomSuffix}`);

  try {
    // Ensure directory exists
    await fs.mkdir(dir, { recursive: true });

    // Write to temp file
    await fs.writeFile(tempPath, content, encoding);

    // Verify temp file exists and has correct content
    const written = await fs.readFile(tempPath, encoding);
    if (written !== content) {
      throw new Error('Content verification failed after write');
    }

    // Atomic rename (replaces existing file if present)
    await fs.rename(tempPath, filePath);

    return {
      success: true,
      path: filePath,
      tempPath,
    };
  } catch (error: any) {
    // Cleanup temp file on failure
    try {
      await fs.unlink(tempPath);
    } catch {
      // Ignore cleanup errors
    }

    return {
      success: false,
      path: filePath,
      tempPath,
      error: error.message,
    };
  }
}

/**
 * Write multiple files atomically
 * Either all succeed or none are written
 */
export async function writeFilesAtomic(
  files: Array<{ path: string; content: string; encoding?: BufferEncoding }>
): Promise<{
  success: boolean;
  written: string[];
  failed: Array<{ path: string; error: string }>;
}> {
  const results: AtomicWriteResult[] = [];
  const tempPaths: string[] = [];

  try {
    // Write all files to temp locations
    for (const file of files) {
      const result = await writeFileAtomic(file.path, {
        content: file.content,
        encoding: file.encoding,
      });

      results.push(result);

      if (!result.success) {
        throw new Error(`Failed to write ${file.path}: ${result.error}`);
      }

      if (result.tempPath) {
        tempPaths.push(result.tempPath);
      }
    }

    return {
      success: true,
      written: results.map(r => r.path),
      failed: [],
    };
  } catch (error: any) {
    // Rollback: delete all successfully written files
    const written: string[] = [];
    const failed: Array<{ path: string; error: string }> = [];

    for (const result of results) {
      if (result.success) {
        try {
          await fs.unlink(result.path);
        } catch (rollbackError: any) {
          failed.push({
            path: result.path,
            error: `Rollback failed: ${rollbackError.message}`,
          });
        }
      } else {
        failed.push({
          path: result.path,
          error: result.error || 'Unknown error',
        });
      }
    }

    // Cleanup any remaining temp files
    for (const tempPath of tempPaths) {
      try {
        await fs.unlink(tempPath);
      } catch {
        // Ignore cleanup errors
      }
    }

    return {
      success: false,
      written,
      failed,
    };
  }
}

/**
 * Copy directory atomically using temp + swap
 */
export async function copyDirectoryAtomic(
  srcDir: string,
  destDir: string
): Promise<AtomicWriteResult> {
  const randomSuffix = crypto.randomBytes(8).toString('hex');
  const tempDir = `${destDir}.tmp-${randomSuffix}`;

  try {
    // Copy to temp directory
    await fs.cp(srcDir, tempDir, { recursive: true });

    // Verify temp directory exists
    await fs.access(tempDir);

    // If dest exists, create backup
    let backupDir: string | null = null;
    try {
      await fs.access(destDir);
      backupDir = `${destDir}.backup-${randomSuffix}`;
      await fs.rename(destDir, backupDir);
    } catch {
      // Dest doesn't exist, no backup needed
    }

    // Atomic rename temp to dest
    await fs.rename(tempDir, destDir);

    // Remove backup if successful
    if (backupDir) {
      await fs.rm(backupDir, { recursive: true, force: true });
    }

    return {
      success: true,
      path: destDir,
      tempPath: tempDir,
    };
  } catch (error: any) {
    // Cleanup temp directory
    try {
      await fs.rm(tempDir, { recursive: true, force: true });
    } catch {
      // Ignore cleanup errors
    }

    return {
      success: false,
      path: destDir,
      tempPath: tempDir,
      error: error.message,
    };
  }
}
