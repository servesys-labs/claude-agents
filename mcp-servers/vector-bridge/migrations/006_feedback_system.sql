-- Migration 006: Add feedback system for learning
--
-- Tracks which memories were helpful to improve future rankings.
-- Feedback influences outcome_bonus and can be used for A/B testing.

-- Feedback table: tracks user/agent feedback on memory helpfulness
CREATE TABLE IF NOT EXISTS memory_feedback (
  id bigserial PRIMARY KEY,
  chunk_id bigint NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  helpful boolean NOT NULL,
  context text,
  created_at timestamptz DEFAULT now(),

  -- Prevent duplicate feedback (one feedback per chunk, update if needed)
  UNIQUE(chunk_id)
);

-- Index for aggregating feedback by chunk
CREATE INDEX IF NOT EXISTS memory_feedback_chunk_id_idx ON memory_feedback(chunk_id);
CREATE INDEX IF NOT EXISTS memory_feedback_helpful_idx ON memory_feedback(helpful);

-- Function: Get feedback stats for a chunk
CREATE OR REPLACE FUNCTION get_feedback_stats(p_chunk_id bigint)
RETURNS TABLE (
  helpful_count bigint,
  unhelpful_count bigint,
  helpful_ratio numeric
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    COUNT(*) FILTER (WHERE helpful = true) AS helpful_count,
    COUNT(*) FILTER (WHERE helpful = false) AS unhelpful_count,
    CASE
      WHEN COUNT(*) > 0 THEN
        (COUNT(*) FILTER (WHERE helpful = true)::numeric / COUNT(*)::numeric)
      ELSE 0
    END AS helpful_ratio
  FROM memory_feedback
  WHERE chunk_id = p_chunk_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Get top helpful memories across projects
CREATE OR REPLACE FUNCTION get_top_helpful_memories(
  p_limit integer DEFAULT 20
)
RETURNS TABLE (
  chunk_id bigint,
  path text,
  chunk text,
  helpful_count bigint,
  helpful_ratio numeric,
  project_root text
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.id AS chunk_id,
    d.path,
    d.chunk,
    COUNT(*) FILTER (WHERE f.helpful = true) AS helpful_count,
    (COUNT(*) FILTER (WHERE f.helpful = true)::numeric / COUNT(*)::numeric) AS helpful_ratio,
    p.root_path AS project_root
  FROM documents d
  JOIN memory_feedback f ON d.id = f.chunk_id
  JOIN projects p ON d.project_id = p.id
  GROUP BY d.id, d.path, d.chunk, p.root_path
  HAVING COUNT(*) >= 2  -- At least 2 feedbacks
  ORDER BY helpful_ratio DESC, helpful_count DESC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function: Record or update feedback
CREATE OR REPLACE FUNCTION record_feedback(
  p_chunk_id bigint,
  p_helpful boolean,
  p_context text DEFAULT NULL
)
RETURNS void AS $$
BEGIN
  INSERT INTO memory_feedback (chunk_id, helpful, context)
  VALUES (p_chunk_id, p_helpful, p_context)
  ON CONFLICT (chunk_id) DO UPDATE
  SET
    helpful = EXCLUDED.helpful,
    context = EXCLUDED.context,
    created_at = now();
END;
$$ LANGUAGE plpgsql;

-- Enhanced hybrid search with feedback boost
-- Adds feedback bonus: +15% for consistently helpful memories
CREATE OR REPLACE FUNCTION search_hybrid_with_feedback(
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
  feedback_score numeric,
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
    -- Feedback score: helpful ratio (0-1) if feedback exists, else 0
    COALESCE(
      (SELECT helpful_ratio FROM get_feedback_stats(d.id)),
      0
    )::numeric AS feedback_score,
    -- Combined score with feedback bonus (15% weight)
    (
      (1 - (d.embedding <=> p_embedding)) * p_vector_weight +
      CASE
        WHEN v_tsquery IS NOT NULL THEN
          LEAST(ts_rank_cd(d.chunk_tsv, v_tsquery) / 0.1, 1.0) * p_bm25_weight
        ELSE 0
      END +
      EXP(-0.023 * EXTRACT(EPOCH FROM (v_now - d.updated_at)) / 86400) * p_time_weight +
      COALESCE(
        (SELECT helpful_ratio FROM get_feedback_stats(d.id)),
        0
      ) * 0.15  -- 15% feedback bonus
    )::numeric AS combined_score
  FROM documents d
  WHERE d.project_id = p_project_id
    AND (v_tsquery IS NULL OR d.chunk_tsv @@ v_tsquery)
  ORDER BY combined_score DESC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Global hybrid search with feedback
CREATE OR REPLACE FUNCTION search_hybrid_global_with_feedback(
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
  feedback_score numeric,
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
    COALESCE(
      (SELECT helpful_ratio FROM get_feedback_stats(d.id)),
      0
    )::numeric AS feedback_score,
    (
      (1 - (d.embedding <=> p_embedding)) * p_vector_weight +
      CASE
        WHEN v_tsquery IS NOT NULL THEN
          LEAST(ts_rank_cd(d.chunk_tsv, v_tsquery) / 0.1, 1.0) * p_bm25_weight
        ELSE 0
      END +
      EXP(-0.023 * EXTRACT(EPOCH FROM (v_now - d.updated_at)) / 86400) * p_time_weight +
      COALESCE(
        (SELECT helpful_ratio FROM get_feedback_stats(d.id)),
        0
      ) * 0.15
    )::numeric AS combined_score
  FROM documents d
  JOIN projects p ON d.project_id = p.id
  WHERE v_tsquery IS NULL OR d.chunk_tsv @@ v_tsquery
  ORDER BY combined_score DESC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function: Detect recurring patterns across projects
-- Finds common tags/categories that appear frequently with high helpfulness
CREATE OR REPLACE FUNCTION detect_patterns(
  p_min_occurrences integer DEFAULT 3,
  p_category text DEFAULT NULL
)
RETURNS TABLE (
  pattern text,
  category text,
  occurrences bigint,
  projects bigint,
  avg_helpfulness numeric,
  example_chunks text[]
) AS $$
BEGIN
  RETURN QUERY
  WITH pattern_stats AS (
    SELECT
      d.category,
      UNNEST(d.tags) AS tag,
      COUNT(*) AS occurrence_count,
      COUNT(DISTINCT d.project_id) AS project_count,
      AVG(COALESCE((SELECT helpful_ratio FROM get_feedback_stats(d.id)), 0)) AS avg_helpful_ratio,
      ARRAY_AGG(d.chunk ORDER BY d.updated_at DESC) FILTER (WHERE d.chunk IS NOT NULL) AS chunks
    FROM documents d
    WHERE (p_category IS NULL OR d.category = p_category)
      AND array_length(d.tags, 1) > 0  -- Has tags
    GROUP BY d.category, UNNEST(d.tags)
    HAVING COUNT(*) >= p_min_occurrences
      AND COUNT(DISTINCT d.project_id) >= 2  -- Appears in multiple projects
  )
  SELECT
    ps.tag AS pattern,
    ps.category,
    ps.occurrence_count AS occurrences,
    ps.project_count AS projects,
    ps.avg_helpful_ratio AS avg_helpfulness,
    ps.chunks[1:3] AS example_chunks  -- Top 3 most recent
  FROM pattern_stats ps
  ORDER BY ps.occurrence_count DESC, ps.avg_helpful_ratio DESC
  LIMIT 50;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE memory_feedback IS 'Tracks user/agent feedback on memory helpfulness for learning';
COMMENT ON FUNCTION get_feedback_stats IS 'Get helpful/unhelpful counts and ratio for a chunk';
COMMENT ON FUNCTION get_top_helpful_memories IS 'Find most helpful memories across projects';
COMMENT ON FUNCTION search_hybrid_with_feedback IS 'Hybrid search with 15% feedback bonus for helpful memories';
COMMENT ON FUNCTION detect_patterns IS 'Find recurring patterns (tags/categories) across multiple projects with high helpfulness';
