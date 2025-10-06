/**
 * PgVectorProvider - Postgres + pgvector implementation of MemoryProvider
 */

import pg from 'pg';
import crypto from 'crypto';
import {
  MemoryProvider,
  MemoryChunk,
  IngestResult,
  SearchResult,
  ProjectInfo,
} from './memory-provider.interface.js';
import { EmbeddingService } from '../services/embedding.service.js';
import { ChunkingService } from '../services/chunking.service.js';
import { CategoryInferenceService } from '../services/category-inference.service.js';
import { RedisCacheService } from '../services/redis-cache.service.js';

const { Pool } = pg;

export class PgVectorProvider implements MemoryProvider {
  private pool: pg.Pool;
  private embedding: EmbeddingService;
  private chunking: ChunkingService;
  private categoryInference: CategoryInferenceService;
  private cache?: RedisCacheService;

  constructor(databaseUrl?: string, redisUrl?: string) {
    this.pool = new Pool({
      connectionString: databaseUrl || process.env.DATABASE_URL,
    });

    // Initialize Redis cache if URL provided
    if (redisUrl || process.env.REDIS_URL) {
      this.cache = new RedisCacheService(redisUrl);
      console.error('[PgVectorProvider] Redis cache enabled');
    } else {
      console.warn('[PgVectorProvider] No Redis URL provided, running without cache');
    }

    // Note: EmbeddingService will be created per-project to track token usage
    this.embedding = new EmbeddingService(undefined, undefined, this.cache);
    this.chunking = new ChunkingService();
    this.categoryInference = new CategoryInferenceService();
  }

  /**
   * Generate SHA256 hash of text for deduplication
   */
  private hashContent(text: string): string {
    return crypto.createHash('sha256').update(text).digest('hex');
  }

  /**
   * Get or create project by root_path
   */
  private async getOrCreateProject(
    project_root: string
  ): Promise<number> {
    const result = await this.pool.query(
      'SELECT get_or_create_project($1, $2) as id',
      [project_root, project_root.split('/').pop() || project_root]
    );
    return result.rows[0].id;
  }

  /**
   * Ingest text content into vector store
   */
  async ingest(
    project_root: string,
    path: string,
    text: string,
    meta?: Record<string, any>
  ): Promise<IngestResult> {
    const startTime = Date.now();
    console.error(`[Ingest] Starting ingestion: ${path} (${text.length} bytes)`);

    // Get or create project
    const t1 = Date.now();
    const project_id = await this.getOrCreateProject(project_root);
    console.error(`[Ingest] Project ID: ${project_id} (${Date.now() - t1}ms)`);
    const repo_name = project_root.split('/').pop() || project_root;

    // Infer metadata (allow override via meta)
    const t2 = Date.now();
    const component = meta?.component || this.categoryInference.inferComponent(path);
    const category = meta?.category || this.categoryInference.inferCategory(path, text);
    const tags = meta?.tags || this.categoryInference.extractTags(text);
    console.error(`[Ingest] Metadata inferred (${Date.now() - t2}ms): component=${component}, category=${category}`);

    // Chunk the text
    const t3 = Date.now();
    const { chunks } = this.chunking.chunk(text);
    console.error(`[Ingest] Chunked into ${chunks.length} pieces (${Date.now() - t3}ms)`);

    if (chunks.length === 0) {
      return { chunks: 0, project_id };
    }

    // Check dedupe for each chunk (if cache available)
    const t4 = Date.now();
    const deduplicatedChunks: string[] = [];
    const chunkShas: string[] = [];

    for (const chunk of chunks) {
      const chunkSha = this.hashContent(chunk);

      // Check if this chunk was recently ingested
      if (this.cache) {
        const isDuplicate = await this.cache.checkDedupe(project_id.toString(), chunkSha);
        if (isDuplicate) {
          console.error(`[Dedupe] Skipping duplicate chunk: ${chunk.substring(0, 50)}...`);
          continue;
        }
      }

      deduplicatedChunks.push(chunk);
      chunkShas.push(chunkSha);
    }
    console.error(`[Ingest] Dedupe check completed (${Date.now() - t4}ms): ${deduplicatedChunks.length}/${chunks.length} unique`);

    if (deduplicatedChunks.length === 0) {
      console.error('[Dedupe] All chunks were duplicates, skipping ingestion');
      return { chunks: 0, project_id };
    }

    console.error(
      `[Ingest] Processing ${deduplicatedChunks.length}/${chunks.length} chunks (${chunks.length - deduplicatedChunks.length} duplicates skipped)`
    );

    // Create project-specific embedding service for token tracking
    const embeddingService = new EmbeddingService(
      undefined,
      undefined,
      this.cache,
      project_id.toString()
    );

    // Generate embeddings for deduplicated chunks
    const t5 = Date.now();
    console.error(`[Ingest] Calling OpenAI embedBatch for ${deduplicatedChunks.length} chunks...`);
    const embeddings = await embeddingService.embedBatch(deduplicatedChunks);
    console.error(`[Ingest] ✅ Embeddings generated (${Date.now() - t5}ms, ${((Date.now() - t5) / deduplicatedChunks.length).toFixed(0)}ms/chunk)`);

    // Insert chunks into database
    const t6 = Date.now();
    const client = await this.pool.connect();
    console.error(`[Ingest] Database connection acquired (${Date.now() - t6}ms)`);
    try {
      await client.query('BEGIN');

      let inserted = 0;
      for (let i = 0; i < deduplicatedChunks.length; i++) {
        const chunk = deduplicatedChunks[i];
        const embedding = embeddings[i];
        const content_sha = chunkShas[i];

        await client.query(
          `INSERT INTO documents (
             project_id, repo_name, path, chunk, embedding,
             component, category, tags, meta, content_sha, updated_at
           )
           VALUES ($1, $2, $3, $4, $5::vector, $6, $7, $8, $9, $10, NOW())
           ON CONFLICT (project_id, path, content_sha)
           DO UPDATE SET
             chunk = EXCLUDED.chunk,
             embedding = EXCLUDED.embedding,
             component = EXCLUDED.component,
             category = EXCLUDED.category,
             tags = EXCLUDED.tags,
             meta = EXCLUDED.meta,
             updated_at = NOW()`,
          [
            project_id,
            repo_name,
            path,
            chunk,
            `[${embedding.join(',')}]`,
            component,
            category,
            tags,
            JSON.stringify(meta || {}),
            content_sha,
          ]
        );
        inserted++;

        // Mark chunk as ingested for dedupe (48h TTL)
        if (this.cache) {
          await this.cache.setDedupe(project_id.toString(), content_sha, 48 * 3600);
        }
      }

      const t7 = Date.now();
      await client.query('COMMIT');
      console.error(`[Ingest] Database COMMIT completed (${Date.now() - t7}ms)`);
      console.error(`[Ingest] ✅ Total ingestion time: ${Date.now() - startTime}ms for ${inserted} chunks`);
      return { chunks: inserted, project_id };
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  /**
   * Search for similar chunks with filters
   *
   * Uses hybrid search combining:
   * - Vector similarity (semantic search) - 60%
   * - BM25 text search (keyword matching) - 30%
   * - Time decay (recency boost) - 10%
   *
   * Plus outcome bonus: +10% for success outcomes
   */
  async search(
    project_root: string | null,
    query: string,
    k: number = 8,
    global: boolean = false,
    component?: string,
    category?: string,
    tags?: string[]
  ): Promise<SearchResult> {
    // Cap k at 20
    const limit = Math.min(k, 20);

    // Get project ID for cache key (null for global search)
    const project_id = project_root ? await this.getOrCreateProject(project_root) : null;

    // Build cache parameters (include hybrid flag for cache key)
    const cacheParams = {
      k: limit,
      global,
      component: component || null,
      category: category || null,
      tags: tags || null,
      hybrid: true, // differentiate from old vector-only cache
    };

    // Check cache for query results (5-minute TTL)
    if (this.cache && project_id) {
      const cachedResults = await this.cache.getCachedQuery(
        project_id.toString(),
        query,
        cacheParams
      );

      if (cachedResults) {
        console.error('[Cache] Returning cached hybrid search results');
        return { results: cachedResults, project_id };
      }
    }

    // Cache miss - generate query embedding
    const queryEmbedding = await this.embedding.embed(query);

    let searchResult: SearchResult;

    if (global) {
      // Global hybrid search across all projects with feedback
      const result = await this.pool.query(
        `SELECT * FROM search_hybrid_global_with_feedback($1::vector, $2, $3, $4, $5, $6)`,
        [
          `[${queryEmbedding.join(',')}]`,
          query, // query text for BM25
          limit,
          0.6, // vector weight
          0.3, // BM25 weight
          0.1, // time decay weight (feedback weight is 15% in SQL function)
        ]
      );

      searchResult = {
        results: result.rows.map((row) => {
          // Apply outcome bonus: +10% for success, -5% for failure
          const outcomeBonus = this.calculateOutcomeBonus(row.meta);
          const finalScore = parseFloat(row.combined_score) + outcomeBonus;

          return {
            path: `${row.root_path}/${row.path}`,
            chunk: row.chunk,
            score: finalScore,
            component: row.component,
            category: row.category,
            tags: row.tags,
            meta: {
              ...row.meta,
              chunk_id: row.id, // Include for feedback
              project_root: row.root_path,
              repo_name: row.repo_name,
              vector_score: parseFloat(row.vector_score),
              bm25_score: parseFloat(row.bm25_score),
              time_score: parseFloat(row.time_score),
              feedback_score: parseFloat(row.feedback_score || 0),
              outcome_bonus: outcomeBonus,
            },
          };
        })
        // Re-sort after applying outcome bonus
        .sort((a, b) => b.score - a.score)
        .slice(0, limit),
      };
    } else {
      // Project-scoped hybrid search with feedback
      const result = await this.pool.query(
        `SELECT * FROM search_hybrid_with_feedback($1, $2::vector, $3, $4, $5, $6, $7)`,
        [
          project_id,
          `[${queryEmbedding.join(',')}]`,
          query, // query text for BM25
          limit * 2, // Fetch more candidates before applying outcome bonus
          0.6, // vector weight
          0.3, // BM25 weight
          0.1, // time decay weight (feedback weight is 15% in SQL function)
        ]
      );

      searchResult = {
        results: result.rows.map((row) => {
          // Apply outcome bonus
          const outcomeBonus = this.calculateOutcomeBonus(row.meta);
          const finalScore = parseFloat(row.combined_score) + outcomeBonus;

          return {
            path: row.path,
            chunk: row.chunk,
            score: finalScore,
            component: row.component,
            category: row.category,
            tags: row.tags,
            meta: {
              ...row.meta,
              chunk_id: row.id, // Include for feedback
              vector_score: parseFloat(row.vector_score),
              bm25_score: parseFloat(row.bm25_score),
              time_score: parseFloat(row.time_score),
              feedback_score: parseFloat(row.feedback_score || 0),
              outcome_bonus: outcomeBonus,
            },
          };
        })
        // Re-sort after applying outcome bonus
        .sort((a, b) => b.score - a.score)
        .slice(0, limit),
        project_id: project_id || undefined,
      };
    }

    // Cache the search results (5-minute TTL)
    if (this.cache && project_id) {
      await this.cache.setCachedQuery(
        project_id.toString(),
        query,
        searchResult.results,
        cacheParams,
        300 // 5 minutes
      );
    }

    return searchResult;
  }

  /**
   * Calculate outcome bonus based on metadata
   * +10% for success outcomes, -5% for failures, 0% otherwise
   */
  private calculateOutcomeBonus(meta: Record<string, any>): number {
    const outcome = meta?.outcome_status || meta?.outcome;

    if (outcome === 'success') {
      return 0.10;
    } else if (outcome === 'failure') {
      return -0.05;
    }

    return 0.0;
  }

  /**
   * Delete all chunks for a specific path
   */
  async deleteByPath(
    project_root: string,
    path: string
  ): Promise<{ deleted: number }> {
    const project_id = await this.getOrCreateProject(project_root);

    const result = await this.pool.query(
      'DELETE FROM documents WHERE project_id = $1 AND path = $2',
      [project_id, path]
    );

    return { deleted: result.rowCount || 0 };
  }

  /**
   * Reindex entire project (delete all + re-ingest)
   */
  async reindexProject(project_root: string): Promise<{ indexed: number }> {
    const project_id = await this.getOrCreateProject(project_root);

    const result = await this.pool.query(
      'DELETE FROM documents WHERE project_id = $1',
      [project_id]
    );

    return { indexed: 0 }; // Actual re-ingestion would be handled by caller
  }

  /**
   * List all indexed projects with stats
   */
  async listProjects(): Promise<ProjectInfo[]> {
    const result = await this.pool.query(`
      SELECT
        p.id,
        p.root_path,
        p.label,
        COUNT(d.id) as doc_count
      FROM projects p
      LEFT JOIN documents d ON p.id = d.project_id
      GROUP BY p.id, p.root_path, p.label
      ORDER BY p.updated_at DESC
    `);

    return result.rows.map((row) => ({
      id: row.id,
      root_path: row.root_path,
      label: row.label,
      doc_count: parseInt(row.doc_count, 10),
    }));
  }

  /**
   * Record feedback on memory helpfulness
   */
  async recordFeedback(
    chunk_id: number,
    helpful: boolean,
    context?: string | null
  ): Promise<void> {
    await this.pool.query(
      'SELECT record_feedback($1, $2, $3)',
      [chunk_id, helpful, context || null]
    );
  }

  /**
   * Get top helpful memories across projects
   */
  async getTopHelpfulMemories(limit: number = 20): Promise<MemoryChunk[]> {
    const result = await this.pool.query(
      'SELECT * FROM get_top_helpful_memories($1)',
      [limit]
    );

    return result.rows.map((row) => ({
      path: `${row.project_root}/${row.path}`,
      chunk: row.chunk,
      score: parseFloat(row.helpful_ratio),
      meta: {
        chunk_id: row.chunk_id,
        helpful_count: parseInt(row.helpful_count, 10),
        helpful_ratio: parseFloat(row.helpful_ratio),
        project_root: row.project_root,
      },
    }));
  }

  /**
   * Get cache metrics (if cache enabled)
   */
  getCacheMetrics() {
    return this.cache?.getMetrics();
  }

  /**
   * Close database connection pool and Redis connection
   */
  async close(): Promise<void> {
    await this.pool.end();
    if (this.cache) {
      await this.cache.close();
    }
  }
}
