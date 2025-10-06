import { promises as fs } from 'fs';
import path from 'path';
import crypto from 'crypto';

/**
 * Simple advisory lock system per dest_dir
 * Prevents concurrent writes to the same directory
 */

interface LockInfo {
  lockId: string;
  timestamp: number;
  pid: number;
}

const LOCK_TIMEOUT = 60000; // 60 seconds
const locks = new Map<string, LockInfo>();

/**
 * Acquire advisory lock for a directory
 */
export async function acquireLock(destDir: string): Promise<{
  acquired: boolean;
  lockId?: string;
  error?: string;
}> {
  const normalizedPath = path.resolve(destDir);
  const now = Date.now();

  // Check for existing lock
  const existingLock = locks.get(normalizedPath);

  if (existingLock) {
    // Check if lock is expired
    if (now - existingLock.timestamp > LOCK_TIMEOUT) {
      console.warn(`[Lock] Expired lock detected for ${normalizedPath}, forcibly releasing`);
      locks.delete(normalizedPath);
    } else {
      return {
        acquired: false,
        error: `Directory locked by another operation (lock ID: ${existingLock.lockId})`,
      };
    }
  }

  // Acquire lock
  const lockId = crypto.randomBytes(16).toString('hex');
  const lockInfo: LockInfo = {
    lockId,
    timestamp: now,
    pid: process.pid,
  };

  locks.set(normalizedPath, lockInfo);

  return {
    acquired: true,
    lockId,
  };
}

/**
 * Release advisory lock for a directory
 */
export function releaseLock(destDir: string, lockId: string): {
  released: boolean;
  error?: string;
} {
  const normalizedPath = path.resolve(destDir);
  const existingLock = locks.get(normalizedPath);

  if (!existingLock) {
    return {
      released: false,
      error: 'No lock exists for this directory',
    };
  }

  if (existingLock.lockId !== lockId) {
    return {
      released: false,
      error: 'Lock ID mismatch - cannot release lock owned by another operation',
    };
  }

  locks.delete(normalizedPath);

  return {
    released: true,
  };
}

/**
 * Execute operation with automatic locking
 */
export async function withLock<T>(
  destDir: string,
  operation: () => Promise<T>
): Promise<T> {
  const lockResult = await acquireLock(destDir);

  if (!lockResult.acquired) {
    throw new Error(lockResult.error || 'Failed to acquire lock');
  }

  const lockId = lockResult.lockId!;

  try {
    return await operation();
  } finally {
    const releaseResult = releaseLock(destDir, lockId);
    if (!releaseResult.released) {
      console.warn(`[Lock] Failed to release lock: ${releaseResult.error}`);
    }
  }
}

/**
 * Get all active locks (for debugging)
 */
export function getActiveLocks(): Array<{
  path: string;
  lockId: string;
  age: number;
  pid: number;
}> {
  const now = Date.now();
  return Array.from(locks.entries()).map(([path, info]) => ({
    path,
    lockId: info.lockId,
    age: now - info.timestamp,
    pid: info.pid,
  }));
}

/**
 * Force clear all locks (use with caution)
 */
export function clearAllLocks(): void {
  locks.clear();
}

/**
 * Cleanup expired locks (called periodically)
 */
export function cleanupExpiredLocks(): number {
  const now = Date.now();
  let cleaned = 0;

  for (const [path, info] of locks.entries()) {
    if (now - info.timestamp > LOCK_TIMEOUT) {
      locks.delete(path);
      cleaned++;
    }
  }

  return cleaned;
}

// Periodic cleanup every 30 seconds
setInterval(() => {
  const cleaned = cleanupExpiredLocks();
  if (cleaned > 0) {
    console.log(`[Lock] Cleaned up ${cleaned} expired locks`);
  }
}, 30000);
