-- Migration 004: Upgrade to HNSW indexes for 100K+ scale
--
-- HNSW (Hierarchical Navigable Small World) provides:
-- - Better recall at scale (100K+ vectors)
-- - Faster build time than ivfflat
-- - No training required (no need to ANALYZE table first)
-- - Better memory efficiency
--
-- Trade-offs:
-- - Slightly larger index size (~1.5x)
-- - Build time: O(n log n) vs ivfflat O(n)
-- - But query time is much better at scale
--
-- References:
-- - https://github.com/pgvector/pgvector#hnsw
-- - Recommended for >100K vectors, especially with high-dimensional embeddings

-- Drop old ivfflat index
DROP INDEX IF EXISTS documents_embedding_idx;

-- Create HNSW index with optimized parameters
-- m = 16: number of bi-directional links (default, good balance)
-- ef_construction = 64: higher = better recall, slower build (default)
CREATE INDEX documents_embedding_hnsw_idx ON documents
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Optional: Add GIN index on meta for faster JSON queries
-- Useful for filtering by category, tags, problem_type, etc.
CREATE INDEX IF NOT EXISTS documents_meta_gin_idx ON documents USING gin(meta);

-- Optional: Add index on updated_at for time decay ranking (Phase 3)
CREATE INDEX IF NOT EXISTS documents_updated_at_idx ON documents(updated_at DESC);

-- Add comment for future reference
COMMENT ON INDEX documents_embedding_hnsw_idx IS 'HNSW index optimized for 100K+ vectors with cosine similarity. m=16, ef_construction=64';
