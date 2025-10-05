/**
 * Embedding service - generates vector embeddings using OpenAI
 * Integrates with Redis cache to reduce API costs by ~70%
 */

import OpenAI from 'openai';
import { RedisCacheService } from './redis-cache.service.js';

export class EmbeddingService {
  private openai: OpenAI;
  private model: string;
  private dimensions: number;
  private cache?: RedisCacheService;
  private projectId?: string;

  constructor(
    apiKey?: string,
    model: string = 'text-embedding-3-small',
    cache?: RedisCacheService,
    projectId?: string
  ) {
    this.openai = new OpenAI({
      apiKey: apiKey || process.env.OPENAI_API_KEY,
    });
    this.model = model;
    this.dimensions = model === 'text-embedding-3-small' ? 1536 : 1536;
    this.cache = cache;
    this.projectId = projectId;
  }

  /**
   * Generate embedding for a single text
   * Checks Redis cache first, falls back to OpenAI API on cache miss
   */
  async embed(text: string): Promise<number[]> {
    if (!text || text.trim().length === 0) {
      throw new Error('Cannot embed empty text');
    }

    // Check cache first (if available)
    if (this.cache) {
      const cached = await this.cache.getCachedEmbedding(text, this.model);
      if (cached) {
        return cached;
      }
    }

    // Cache miss - call OpenAI API
    try {
      const startTime = Date.now();
      const response = await this.openai.embeddings.create({
        model: this.model,
        input: text,
        encoding_format: 'float',
      });

      const embedding = response.data[0].embedding;
      const latency = Date.now() - startTime;

      // Track token usage if projectId provided
      if (this.cache && this.projectId && response.usage) {
        const totalTokens = await this.cache.incrementTokenUsage(
          this.projectId,
          response.usage.total_tokens
        );
        console.log(
          `[OpenAI] Embedding generated (${response.usage.total_tokens} tokens, ${latency}ms) - Project total today: ${totalTokens} tokens`
        );
      } else {
        console.log(`[OpenAI] Embedding generated (${latency}ms)`);
      }

      // Store in cache with 60-day TTL
      if (this.cache) {
        await this.cache.setCachedEmbedding(text, this.model, embedding, 60 * 24 * 3600);
      }

      return embedding;
    } catch (error) {
      console.error('[OpenAI] Embedding error:', error);
      throw new Error(`Failed to generate embedding: ${error}`);
    }
  }

  /**
   * Generate embeddings for multiple texts (batch)
   * Checks cache for each text individually, batches API calls for cache misses
   */
  async embedBatch(texts: string[]): Promise<number[][]> {
    if (texts.length === 0) {
      return [];
    }

    // Filter out empty texts
    const validTexts = texts.filter((t) => t && t.trim().length > 0);

    if (validTexts.length === 0) {
      return [];
    }

    // Check cache for each text (if cache available)
    const results: (number[] | null)[] = [];
    const uncachedIndices: number[] = [];
    const uncachedTexts: string[] = [];

    for (let i = 0; i < validTexts.length; i++) {
      const text = validTexts[i];
      let cached: number[] | null = null;

      if (this.cache) {
        cached = await this.cache.getCachedEmbedding(text, this.model);
      }

      results.push(cached);

      if (!cached) {
        uncachedIndices.push(i);
        uncachedTexts.push(text);
      }
    }

    // If all texts were cached, return immediately
    if (uncachedTexts.length === 0) {
      console.log(`[Redis] All ${validTexts.length} embeddings retrieved from cache`);
      return results as number[][];
    }

    // Batch call OpenAI for uncached texts
    console.log(
      `[OpenAI] Generating ${uncachedTexts.length}/${validTexts.length} embeddings (${validTexts.length - uncachedTexts.length} cached)`
    );

    try {
      const startTime = Date.now();
      const response = await this.openai.embeddings.create({
        model: this.model,
        input: uncachedTexts,
        encoding_format: 'float',
      });

      const latency = Date.now() - startTime;

      // Track token usage
      if (this.cache && this.projectId && response.usage) {
        const totalTokens = await this.cache.incrementTokenUsage(
          this.projectId,
          response.usage.total_tokens
        );
        console.log(
          `[OpenAI] Batch embeddings generated (${response.usage.total_tokens} tokens, ${latency}ms) - Project total today: ${totalTokens} tokens`
        );
      } else {
        console.log(`[OpenAI] Batch embeddings generated (${latency}ms)`);
      }

      // Store each embedding in cache and fill results
      for (let i = 0; i < uncachedIndices.length; i++) {
        const resultIndex = uncachedIndices[i];
        const embedding = response.data[i].embedding;
        results[resultIndex] = embedding;

        // Cache each embedding
        if (this.cache) {
          await this.cache.setCachedEmbedding(
            uncachedTexts[i],
            this.model,
            embedding,
            60 * 24 * 3600
          );
        }
      }

      return results as number[][];
    } catch (error) {
      console.error('[OpenAI] Batch embedding error:', error);
      throw new Error(`Failed to generate batch embeddings: ${error}`);
    }
  }

  /**
   * Get embedding dimensions for this model
   */
  getDimensions(): number {
    return this.dimensions;
  }

  /**
   * Get model name
   */
  getModel(): string {
    return this.model;
  }
}
