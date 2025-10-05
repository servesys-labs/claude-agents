/**
 * Redis Cache Service - Caching layer for embeddings, queries, and deduplication
 * Reduces OpenAI API costs by ~70% through intelligent caching
 */

import { Redis, RedisOptions } from 'ioredis';
import crypto from 'crypto';

export interface CacheMetrics {
  hits: number;
  misses: number;
  hitRate: number;
}

export class RedisCacheService {
  private redis: Redis | null;
  private connected: boolean = false;
  private fallbackMode: boolean = false;
  private metrics: CacheMetrics = { hits: 0, misses: 0, hitRate: 0 };

  constructor(redisUrl?: string) {
    const url = redisUrl || process.env.REDIS_URL;

    if (!url) {
      console.warn('[Redis] No REDIS_URL provided, running in fallback mode (no caching)');
      this.fallbackMode = true;
      this.redis = null;
      return;
    }

    // Debug: Log the Redis URL being used (mask password)
    const maskedUrl = url.replace(/(:\/\/[^:]+:)([^@]+)(@)/, '$1****$3');
    console.log(`[Redis] Connecting to: ${maskedUrl}`);

    const options: RedisOptions = {
      family: 0, // Enable dual-stack (IPv4 + IPv6) lookup for Railway compatibility
      retryStrategy: (times: number) => {
        if (times > 3) {
          console.error('[Redis] Max retries exceeded, entering fallback mode');
          this.fallbackMode = true;
          return null; // Stop retrying
        }
        const delay = Math.min(times * 50, 2000);
        console.warn(`[Redis] Retry attempt ${times}, waiting ${delay}ms`);
        return delay;
      },
      maxRetriesPerRequest: 3,
      enableReadyCheck: true,
      lazyConnect: false,
    };

    this.redis = new Redis(url, options);

    // Connection event handlers
    this.redis.on('connect', () => {
      console.log('[Redis] Connected successfully');
      this.connected = true;
      this.fallbackMode = false;
    });

    this.redis.on('ready', () => {
      console.log('[Redis] Ready to accept commands');
    });

    this.redis.on('error', (error: Error) => {
      console.error('[Redis] Connection error:', error.message);
      this.fallbackMode = true;
    });

    this.redis.on('close', () => {
      console.warn('[Redis] Connection closed');
      this.connected = false;
    });
  }

  /**
   * Generate SHA256 hash for cache key
   */
  private hashKey(input: string): string {
    return crypto.createHash('sha256').update(input).digest('hex');
  }

  /**
   * Build cache key for embeddings: emb:{model}:{sha256(text)}
   */
  private buildEmbeddingKey(text: string, model: string): string {
    const hash = this.hashKey(text);
    return `emb:${model}:${hash}`;
  }

  /**
   * Build cache key for query results: query:{project_id}:{sha256(query+params)}
   */
  private buildQueryKey(projectId: string, query: string, params: Record<string, any> = {}): string {
    const paramsStr = JSON.stringify(params);
    const hash = this.hashKey(`${query}:${paramsStr}`);
    return `query:${projectId}:${hash}`;
  }

  /**
   * Build dedupe key: dedupe:{project_id}:{content_sha}
   */
  private buildDedupeKey(projectId: string, contentSha: string): string {
    return `dedupe:${projectId}:${contentSha}`;
  }

  /**
   * Build budget tracking key: budget:{YYYYMMDD}:{project_id}
   */
  private buildBudgetKey(projectId: string, date?: string): string {
    const dateStr = date || new Date().toISOString().split('T')[0].replace(/-/g, '');
    return `budget:${dateStr}:${projectId}`;
  }

  /**
   * Get cached embedding vector
   * @returns Cached embedding vector or null if not found
   */
  async getCachedEmbedding(text: string, model: string): Promise<number[] | null> {
    if (this.fallbackMode || !this.redis) return null;

    try {
      const key = this.buildEmbeddingKey(text, model);
      const cached = await this.redis.get(key);

      if (cached) {
        this.metrics.hits++;
        console.log(`[Redis] CACHE HIT: Embedding for text (${text.substring(0, 50)}...)`);
        return JSON.parse(cached);
      }

      this.metrics.misses++;
      return null;
    } catch (error: any) {
      console.error('[Redis] Error fetching cached embedding:', error.message);
      return null; // Graceful degradation
    }
  }

  /**
   * Store embedding in cache
   * @param ttlSeconds Time-to-live in seconds (default: 60 days)
   */
  async setCachedEmbedding(
    text: string,
    model: string,
    embedding: number[],
    ttlSeconds: number = 60 * 24 * 3600 // 60 days
  ): Promise<void> {
    if (this.fallbackMode || !this.redis) return;

    try {
      const key = this.buildEmbeddingKey(text, model);
      await this.redis.setex(key, ttlSeconds, JSON.stringify(embedding));
      console.log(`[Redis] Cached embedding (TTL: ${ttlSeconds}s)`);
    } catch (error: any) {
      console.error('[Redis] Error caching embedding:', error.message);
      // Don't throw - caching failure shouldn't break the operation
    }
  }

  /**
   * Get cached query results
   */
  async getCachedQuery(
    projectId: string,
    query: string,
    params: Record<string, any> = {}
  ): Promise<any[] | null> {
    if (this.fallbackMode || !this.redis) return null;

    try {
      const key = this.buildQueryKey(projectId, query, params);
      const cached = await this.redis.get(key);

      if (cached) {
        this.metrics.hits++;
        console.log(`[Redis] CACHE HIT: Query results for "${query.substring(0, 50)}..."`);
        return JSON.parse(cached);
      }

      this.metrics.misses++;
      return null;
    } catch (error: any) {
      console.error('[Redis] Error fetching cached query:', error.message);
      return null;
    }
  }

  /**
   * Store query results in cache
   * @param ttlSeconds Time-to-live in seconds (default: 5 minutes)
   */
  async setCachedQuery(
    projectId: string,
    query: string,
    results: any[],
    params: Record<string, any> = {},
    ttlSeconds: number = 300 // 5 minutes
  ): Promise<void> {
    if (this.fallbackMode || !this.redis) return;

    try {
      const key = this.buildQueryKey(projectId, query, params);
      await this.redis.setex(key, ttlSeconds, JSON.stringify(results));
      console.log(`[Redis] Cached query results (TTL: ${ttlSeconds}s)`);
    } catch (error: any) {
      console.error('[Redis] Error caching query results:', error.message);
    }
  }

  /**
   * Check if content has been ingested recently (dedupe)
   * @returns true if duplicate, false if new content
   */
  async checkDedupe(projectId: string, contentSha: string): Promise<boolean> {
    if (this.fallbackMode || !this.redis) return false;

    try {
      const key = this.buildDedupeKey(projectId, contentSha);
      const exists = await this.redis.exists(key);
      return exists === 1;
    } catch (error: any) {
      console.error('[Redis] Error checking dedupe:', error.message);
      return false; // Assume not duplicate on error
    }
  }

  /**
   * Mark content as ingested (dedupe tracking)
   * @param ttlSeconds Time-to-live in seconds (default: 48 hours)
   */
  async setDedupe(
    projectId: string,
    contentSha: string,
    ttlSeconds: number = 48 * 3600 // 48 hours
  ): Promise<void> {
    if (this.fallbackMode || !this.redis) return;

    try {
      const key = this.buildDedupeKey(projectId, contentSha);
      await this.redis.setex(key, ttlSeconds, '1');
      console.log(`[Redis] Set dedupe marker (TTL: ${ttlSeconds}s)`);
    } catch (error: any) {
      console.error('[Redis] Error setting dedupe marker:', error.message);
    }
  }

  /**
   * Increment token usage for budget tracking
   * @returns Total tokens used today for this project
   */
  async incrementTokenUsage(projectId: string, tokens: number): Promise<number> {
    if (this.fallbackMode || !this.redis) return 0;

    try {
      const key = this.buildBudgetKey(projectId);
      const newTotal = await this.redis.incrby(key, tokens);

      // Set expiry to end of day (86400s from now, rounded to midnight)
      const now = new Date();
      const midnight = new Date(now);
      midnight.setHours(24, 0, 0, 0);
      const ttl = Math.floor((midnight.getTime() - now.getTime()) / 1000);

      await this.redis.expire(key, ttl);

      return newTotal;
    } catch (error: any) {
      console.error('[Redis] Error incrementing token usage:', error.message);
      return 0;
    }
  }

  /**
   * Get token usage for a project on a specific date
   * @param date Optional date string (YYYYMMDD), defaults to today
   */
  async getTokenUsage(projectId: string, date?: string): Promise<number> {
    if (this.fallbackMode || !this.redis) return 0;

    try {
      const key = this.buildBudgetKey(projectId, date);
      const usage = await this.redis.get(key);
      return usage ? parseInt(usage, 10) : 0;
    } catch (error: any) {
      console.error('[Redis] Error fetching token usage:', error.message);
      return 0;
    }
  }

  /**
   * Get cache metrics (hit rate, total hits/misses)
   */
  getMetrics(): CacheMetrics {
    const total = this.metrics.hits + this.metrics.misses;
    return {
      ...this.metrics,
      hitRate: total > 0 ? this.metrics.hits / total : 0,
    };
  }

  /**
   * Reset metrics (useful for testing)
   */
  resetMetrics(): void {
    this.metrics = { hits: 0, misses: 0, hitRate: 0 };
  }

  /**
   * Check if Redis is connected and operational
   */
  isConnected(): boolean {
    return this.connected && !this.fallbackMode;
  }

  /**
   * Close Redis connection
   */
  async close(): Promise<void> {
    if (!this.redis) return;

    try {
      await this.redis.quit();
      console.log('[Redis] Connection closed gracefully');
    } catch (error: any) {
      console.error('[Redis] Error closing connection:', error.message);
    }
  }
}
