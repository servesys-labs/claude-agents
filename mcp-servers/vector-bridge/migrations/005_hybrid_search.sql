-- Migration 005: Add hybrid search capabilities (BM25 + time decay)
--
-- Hybrid search combines:
-- 1. Vector similarity (semantic search)
-- 2. BM25 full-text search (keyword matching)
-- 3. Time decay (recency boost)
--
-- This provides better results than vector search alone, especially for:
-- - Technical queries with specific keywords
-- - Recent/relevant results prioritization
-- - Mixing semantic understanding with exact keyword matches

-- Add tsvector column for full-text search
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS chunk_tsv tsvector;

-- Create index on tsvector for fast BM25 search
CREATE INDEX IF NOT EXISTS documents_chunk_tsv_idx ON documents USING gin(chunk_tsv);

-- Update tsvector for existing rows (one-time backfill)
UPDATE documents
SET chunk_tsv = to_tsvector('english', chunk)
WHERE chunk_tsv IS NULL;

-- Trigger to automatically update tsvector on INSERT/UPDATE
CREATE OR REPLACE FUNCTION documents_chunk_tsv_trigger() RETURNS trigger AS $$
BEGIN
  NEW.chunk_tsv := to_tsvector('english', NEW.chunk);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS documents_chunk_tsv_update ON documents;
CREATE TRIGGER documents_chunk_tsv_update
  BEFORE INSERT OR UPDATE ON documents
  FOR EACH ROW
  EXECUTE FUNCTION documents_chunk_tsv_trigger();

-- Hybrid search function: vector + BM25 + time decay
--
-- Scoring formula:
--   score = (vector_score * 0.6) + (bm25_score * 0.3) + (time_decay * 0.1)
--
-- Parameters:
--   vector_score: cosine similarity (0-1)
--   bm25_score: ts_rank_cd normalized (0-1)
--   time_decay: exponential decay based on age (0-1)
--
CREATE OR REPLACE FUNCTION search_hybrid(
  p_project_id bigint,
  p_embedding vector(1536),
  p_query_text text,
  p_limit integer DEFAULT 8,
  p_vector_weight numeric DEFAULT 0.6,
  p_bm25_weight numeric DEFAULT 0.3,
  p_time_weight numeric DEFAULT 0.1
)
RETURNS TABLE (
  id bigint,
  path text,
  chunk text,
  meta jsonb,
  vector_score numeric,
  bm25_score numeric,
  time_score numeric,
  combined_score numeric
) AS $$
DECLARE
  v_tsquery tsquery;
  v_now timestamptz := now();
BEGIN
  -- Parse query text to tsquery
  v_tsquery := plainto_tsquery('english', p_query_text);

  RETURN QUERY
  SELECT
    d.id,
    d.path,
    d.chunk,
    d.meta,
    -- Vector similarity score (0-1, higher is better)
    (1 - (d.embedding <=> p_embedding))::numeric AS vector_score,
    -- BM25 score normalized to 0-1 range
    CASE
      WHEN v_tsquery IS NOT NULL THEN
        LEAST(ts_rank_cd(d.chunk_tsv, v_tsquery) / 0.1, 1.0)::numeric
      ELSE 0::numeric
    END AS bm25_score,
    -- Time decay score (exponential decay, 30-day half-life)
    EXP(-0.023 * EXTRACT(EPOCH FROM (v_now - d.updated_at)) / 86400)::numeric AS time_score,
    -- Combined score (weighted sum)
    (
      (1 - (d.embedding <=> p_embedding)) * p_vector_weight +
      CASE
        WHEN v_tsquery IS NOT NULL THEN
          LEAST(ts_rank_cd(d.chunk_tsv, v_tsquery) / 0.1, 1.0) * p_bm25_weight
        ELSE 0
      END +
      EXP(-0.023 * EXTRACT(EPOCH FROM (v_now - d.updated_at)) / 86400) * p_time_weight
    )::numeric AS combined_score
  FROM documents d
  WHERE d.project_id = p_project_id
    -- Optional: filter by BM25 relevance if query text provided
    AND (v_tsquery IS NULL OR d.chunk_tsv @@ v_tsquery)
  ORDER BY combined_score DESC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Global hybrid search (across all projects)
CREATE OR REPLACE FUNCTION search_hybrid_global(
  p_embedding vector(1536),
  p_query_text text,
  p_limit integer DEFAULT 8,
  p_vector_weight numeric DEFAULT 0.6,
  p_bm25_weight numeric DEFAULT 0.3,
  p_time_weight numeric DEFAULT 0.1
)
RETURNS TABLE (
  id bigint,
  project_id bigint,
  root_path text,
  path text,
  chunk text,
  meta jsonb,
  vector_score numeric,
  bm25_score numeric,
  time_score numeric,
  combined_score numeric
) AS $$
DECLARE
  v_tsquery tsquery;
  v_now timestamptz := now();
BEGIN
  v_tsquery := plainto_tsquery('english', p_query_text);

  RETURN QUERY
  SELECT
    d.id,
    d.project_id,
    p.root_path,
    d.path,
    d.chunk,
    d.meta,
    (1 - (d.embedding <=> p_embedding))::numeric AS vector_score,
    CASE
      WHEN v_tsquery IS NOT NULL THEN
        LEAST(ts_rank_cd(d.chunk_tsv, v_tsquery) / 0.1, 1.0)::numeric
      ELSE 0::numeric
    END AS bm25_score,
    EXP(-0.023 * EXTRACT(EPOCH FROM (v_now - d.updated_at)) / 86400)::numeric AS time_score,
    (
      (1 - (d.embedding <=> p_embedding)) * p_vector_weight +
      CASE
        WHEN v_tsquery IS NOT NULL THEN
          LEAST(ts_rank_cd(d.chunk_tsv, v_tsquery) / 0.1, 1.0) * p_bm25_weight
        ELSE 0
      END +
      EXP(-0.023 * EXTRACT(EPOCH FROM (v_now - d.updated_at)) / 86400) * p_time_weight
    )::numeric AS combined_score
  FROM documents d
  JOIN projects p ON d.project_id = p.id
  WHERE v_tsquery IS NULL OR d.chunk_tsv @@ v_tsquery
  ORDER BY combined_score DESC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Add comments for documentation
COMMENT ON COLUMN documents.chunk_tsv IS 'Full-text search vector for BM25 ranking in hybrid search';
COMMENT ON FUNCTION search_hybrid IS 'Hybrid search combining vector similarity (60%), BM25 text search (30%), and time decay (10%)';
COMMENT ON FUNCTION search_hybrid_global IS 'Global hybrid search across all projects with combined scoring';
