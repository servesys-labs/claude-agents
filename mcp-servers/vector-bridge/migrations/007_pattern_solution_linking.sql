-- Migration 007: Pattern-Solution Linking & Smart Discovery
--
-- Links detected patterns to solution fixpacks for intelligent problem-solving.
-- Tracks pattern-solution success rates and provides smart recommendations.

-- Table: pattern_solution_links
-- Tracks which solutions are effective for which patterns
CREATE TABLE IF NOT EXISTS pattern_solutions (
  id bigserial PRIMARY KEY,
  pattern_tag text NOT NULL,
  pattern_category text NOT NULL,
  solution_id bigint NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  success_count integer DEFAULT 0,
  failure_count integer DEFAULT 0,
  avg_helpful_ratio numeric DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),

  UNIQUE(pattern_tag, pattern_category, solution_id)
);

CREATE INDEX IF NOT EXISTS pattern_solutions_tag_idx ON pattern_solutions(pattern_tag, pattern_category);
CREATE INDEX IF NOT EXISTS pattern_solutions_solution_idx ON pattern_solutions(solution_id);
CREATE INDEX IF NOT EXISTS pattern_solutions_success_rate_idx ON pattern_solutions((success_count::numeric / NULLIF(success_count + failure_count, 0)));

-- Function: Link a solution to a pattern
-- Called when a solution is applied to a problem matching a pattern
CREATE OR REPLACE FUNCTION link_pattern_to_solution(
  p_pattern_tag text,
  p_pattern_category text,
  p_solution_id bigint,
  p_success boolean
)
RETURNS void AS $$
BEGIN
  INSERT INTO pattern_solutions (pattern_tag, pattern_category, solution_id, success_count, failure_count)
  VALUES (
    p_pattern_tag,
    p_pattern_category,
    p_solution_id,
    CASE WHEN p_success THEN 1 ELSE 0 END,
    CASE WHEN p_success THEN 0 ELSE 1 END
  )
  ON CONFLICT (pattern_tag, pattern_category, solution_id) DO UPDATE
  SET
    success_count = pattern_solutions.success_count + CASE WHEN p_success THEN 1 ELSE 0 END,
    failure_count = pattern_solutions.failure_count + CASE WHEN p_success THEN 0 ELSE 1 END,
    updated_at = now();
END;
$$ LANGUAGE plpgsql;

-- Function: Get solutions for a pattern (ranked by success rate)
CREATE OR REPLACE FUNCTION get_solutions_for_pattern(
  p_pattern_tag text,
  p_pattern_category text DEFAULT NULL,
  p_limit integer DEFAULT 5
)
RETURNS TABLE (
  solution_id bigint,
  title text,
  description text,
  category text,
  success_rate numeric,
  applications integer,
  avg_helpful_ratio numeric
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    s.id AS solution_id,
    s.title,
    s.description,
    s.category,
    CASE
      WHEN (ps.success_count + ps.failure_count) > 0 THEN
        (ps.success_count::numeric / (ps.success_count + ps.failure_count))
      ELSE 0
    END AS success_rate,
    (ps.success_count + ps.failure_count) AS applications,
    ps.avg_helpful_ratio
  FROM pattern_solutions ps
  JOIN solutions s ON ps.solution_id = s.id
  WHERE ps.pattern_tag = p_pattern_tag
    AND (p_pattern_category IS NULL OR ps.pattern_category = p_pattern_category)
    AND (ps.success_count + ps.failure_count) >= 1  -- At least 1 application
  ORDER BY
    -- Rank by: success rate (60%) + applications (30%) + helpfulness (10%)
    (
      CASE WHEN (ps.success_count + ps.failure_count) > 0
        THEN (ps.success_count::numeric / (ps.success_count + ps.failure_count)) * 0.6
        ELSE 0
      END +
      LEAST((ps.success_count + ps.failure_count)::numeric / 10.0, 1.0) * 0.3 +
      COALESCE(ps.avg_helpful_ratio, 0) * 0.1
    ) DESC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function: Detect patterns in query text and suggest solutions
-- Analyzes query text to find matching patterns and return linked solutions
CREATE OR REPLACE FUNCTION detect_patterns_in_query(
  p_query_text text,
  p_limit integer DEFAULT 3
)
RETURNS TABLE (
  pattern_tag text,
  pattern_category text,
  match_score numeric,
  solution_count bigint,
  top_solution_id bigint,
  top_solution_title text,
  top_solution_success_rate numeric
) AS $$
BEGIN
  RETURN QUERY
  WITH query_tags AS (
    -- Extract potential tags from query text (lowercase words)
    SELECT DISTINCT
      lower(unnest(string_to_array(regexp_replace(p_query_text, '[^a-zA-Z0-9\s]', '', 'g'), ' '))) AS tag
  ),
  pattern_matches AS (
    -- Find patterns where tags appear in documents
    SELECT
      d.tags[1] AS pattern_tag,  -- Use first tag as pattern identifier
      d.category AS pattern_category,
      COUNT(DISTINCT d.id) AS doc_count,
      -- Match score based on how many query tags appear in this pattern's docs
      COUNT(DISTINCT qt.tag) AS matching_tags
    FROM documents d
    CROSS JOIN query_tags qt
    WHERE d.tags && ARRAY[qt.tag]  -- Pattern docs contain query tags
      AND array_length(d.tags, 1) > 0
    GROUP BY d.tags[1], d.category
    HAVING COUNT(DISTINCT d.id) >= 3  -- Pattern appears at least 3 times
  ),
  pattern_with_solutions AS (
    -- Join patterns with their linked solutions
    SELECT
      pm.pattern_tag,
      pm.pattern_category,
      pm.matching_tags::numeric / GREATEST(array_length(string_to_array(p_query_text, ' '), 1), 1) AS match_score,
      COUNT(DISTINCT ps.solution_id) AS solution_count,
      (
        SELECT ps2.solution_id
        FROM pattern_solutions ps2
        WHERE ps2.pattern_tag = pm.pattern_tag
          AND ps2.pattern_category = pm.pattern_category
        ORDER BY (ps2.success_count::numeric / NULLIF(ps2.success_count + ps2.failure_count, 0)) DESC
        LIMIT 1
      ) AS top_solution_id
    FROM pattern_matches pm
    LEFT JOIN pattern_solutions ps ON ps.pattern_tag = pm.pattern_tag
      AND ps.pattern_category = pm.pattern_category
    GROUP BY pm.pattern_tag, pm.pattern_category, pm.matching_tags
  )
  SELECT
    pws.pattern_tag,
    pws.pattern_category,
    pws.match_score,
    pws.solution_count,
    pws.top_solution_id,
    s.title AS top_solution_title,
    CASE
      WHEN (s.success_count + s.failure_count) > 0 THEN
        (s.success_count::numeric / (s.success_count + s.failure_count))
      ELSE 0
    END AS top_solution_success_rate
  FROM pattern_with_solutions pws
  LEFT JOIN solutions s ON s.id = pws.top_solution_id
  WHERE pws.match_score > 0.1  -- At least 10% tag overlap
  ORDER BY pws.match_score DESC, pws.solution_count DESC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function: Get golden paths (best pattern-solution combinations)
-- Returns the most successful pattern-solution pairs across all projects
CREATE OR REPLACE FUNCTION get_golden_paths(
  p_min_applications integer DEFAULT 3,
  p_limit integer DEFAULT 20
)
RETURNS TABLE (
  pattern_tag text,
  pattern_category text,
  solution_id bigint,
  solution_title text,
  success_rate numeric,
  applications integer,
  avg_helpful_ratio numeric,
  projects_count bigint
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    ps.pattern_tag,
    ps.pattern_category,
    s.id AS solution_id,
    s.title AS solution_title,
    CASE
      WHEN (ps.success_count + ps.failure_count) > 0 THEN
        (ps.success_count::numeric / (ps.success_count + ps.failure_count))
      ELSE 0
    END AS success_rate,
    (ps.success_count + ps.failure_count) AS applications,
    ps.avg_helpful_ratio,
    -- Count how many projects this pattern appears in
    (
      SELECT COUNT(DISTINCT d.project_id)
      FROM documents d
      WHERE d.tags && ARRAY[ps.pattern_tag]
    ) AS projects_count
  FROM pattern_solutions ps
  JOIN solutions s ON ps.solution_id = s.id
  WHERE (ps.success_count + ps.failure_count) >= p_min_applications
    AND ps.success_count > ps.failure_count  -- More successes than failures
  ORDER BY
    -- Rank by success rate and application count
    (ps.success_count::numeric / (ps.success_count + ps.failure_count)) * 0.7 +
    LEAST((ps.success_count + ps.failure_count)::numeric / 10.0, 1.0) * 0.3
    DESC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function: Update pattern-solution avg_helpful_ratio based on feedback
-- Should be called periodically or after feedback is recorded
CREATE OR REPLACE FUNCTION update_pattern_solution_helpfulness()
RETURNS void AS $$
BEGIN
  UPDATE pattern_solutions ps
  SET
    avg_helpful_ratio = (
      SELECT AVG(CASE WHEN mf.helpful THEN 1.0 ELSE 0.0 END)
      FROM memory_feedback mf
      JOIN documents d ON mf.chunk_id = d.id
      JOIN solutions s ON ps.solution_id = s.id
      WHERE d.tags && ARRAY[ps.pattern_tag]
        AND d.category = ps.pattern_category
        AND mf.helpful IS NOT NULL
    ),
    updated_at = now()
  WHERE EXISTS (
    SELECT 1
    FROM memory_feedback mf
    JOIN documents d ON mf.chunk_id = d.id
    WHERE d.tags && ARRAY[ps.pattern_tag]
      AND d.category = ps.pattern_category
  );
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE pattern_solutions IS 'Links patterns to solutions with success tracking';
COMMENT ON FUNCTION link_pattern_to_solution IS 'Record a solution application for a pattern';
COMMENT ON FUNCTION get_solutions_for_pattern IS 'Get best solutions for a specific pattern';
COMMENT ON FUNCTION detect_patterns_in_query IS 'Detect patterns in query text and suggest solutions';
COMMENT ON FUNCTION get_golden_paths IS 'Get most successful pattern-solution combinations';
COMMENT ON FUNCTION update_pattern_solution_helpfulness IS 'Update helpfulness scores from feedback';
