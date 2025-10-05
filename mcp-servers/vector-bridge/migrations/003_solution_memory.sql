-- Migration 003: Solution Memory (Fixpacks)
-- Store recurring fixes as reusable, searchable solutions

-- Solutions table: top-level fixpack record
CREATE TABLE IF NOT EXISTS solutions (
  id bigserial PRIMARY KEY,
  title text NOT NULL,
  description text,
  category text NOT NULL,  -- devops|deploy|workspace|tsconfig|migration
  component text,  -- backend|mobile|infra|data
  tags text[] DEFAULT '{}',
  project_root text,  -- Optional: specific project or NULL for global
  repo_name text,
  package_manager text,  -- npm|pnpm|yarn|bun
  monorepo_tool text,  -- turbo|nx|lerna|rush
  success_count integer DEFAULT 0,
  failure_count integer DEFAULT 0,
  last_applied_at timestamptz,
  verified_on timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Signatures table: error patterns that trigger this solution
CREATE TABLE IF NOT EXISTS signatures (
  id bigserial PRIMARY KEY,
  solution_id bigint NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  text text NOT NULL,  -- Human-readable signature
  regexes text[] DEFAULT '{}',  -- Regex patterns to match
  embedding vector(1536),  -- Vector embedding of signature text
  meta jsonb DEFAULT '{}',
  created_at timestamptz DEFAULT now()
);

-- Steps table: ordered actions to execute
CREATE TABLE IF NOT EXISTS steps (
  id bigserial PRIMARY KEY,
  solution_id bigint NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  step_order integer NOT NULL,
  kind text NOT NULL,  -- cmd|patch|copy|script|env
  payload jsonb NOT NULL,
  description text,
  timeout_ms integer DEFAULT 120000,
  created_at timestamptz DEFAULT now(),
  UNIQUE(solution_id, step_order)
);

-- Checks table: verification steps
CREATE TABLE IF NOT EXISTS checks (
  id bigserial PRIMARY KEY,
  solution_id bigint NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  check_order integer NOT NULL,
  cmd text NOT NULL,
  expect_substring text,
  expect_exit_code integer DEFAULT 0,
  timeout_ms integer DEFAULT 30000,
  created_at timestamptz DEFAULT now(),
  UNIQUE(solution_id, check_order)
);

-- Indexes
CREATE INDEX IF NOT EXISTS solutions_category_component_idx
  ON solutions(category, component);

CREATE INDEX IF NOT EXISTS solutions_tags_idx
  ON solutions USING gin(tags);

CREATE INDEX IF NOT EXISTS solutions_project_root_idx
  ON solutions(project_root);

CREATE INDEX IF NOT EXISTS signatures_embedding_idx
  ON signatures USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);

CREATE INDEX IF NOT EXISTS signatures_solution_id_idx
  ON signatures(solution_id);

CREATE INDEX IF NOT EXISTS steps_solution_order_idx
  ON steps(solution_id, step_order);

-- Search function: find solutions by error text + metadata
CREATE OR REPLACE FUNCTION search_solutions(
  p_query_embedding vector(1536),
  p_limit integer DEFAULT 5,
  p_project_root text DEFAULT NULL,
  p_category text DEFAULT NULL,
  p_component text DEFAULT NULL,
  p_package_manager text DEFAULT NULL,
  p_monorepo_tool text DEFAULT NULL
)
RETURNS TABLE (
  solution_id bigint,
  title text,
  description text,
  category text,
  component text,
  tags text[],
  score numeric,
  success_rate numeric,
  signature_text text,
  step_count bigint
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    s.id,
    s.title,
    s.description,
    s.category,
    s.component,
    s.tags,
    (1 - (sig.embedding <=> p_query_embedding))::numeric AS score,
    CASE
      WHEN (s.success_count + s.failure_count) > 0
      THEN (s.success_count::numeric / (s.success_count + s.failure_count))
      ELSE 0.0
    END AS success_rate,
    sig.text AS signature_text,
    (SELECT COUNT(*) FROM steps WHERE solution_id = s.id) AS step_count
  FROM solutions s
  JOIN signatures sig ON s.id = sig.solution_id
  WHERE
    (p_project_root IS NULL OR s.project_root IS NULL OR s.project_root = p_project_root)
    AND (p_category IS NULL OR s.category = p_category)
    AND (p_component IS NULL OR s.component = p_component OR s.component IS NULL)
    AND (p_package_manager IS NULL OR s.package_manager = p_package_manager OR s.package_manager IS NULL)
    AND (p_monorepo_tool IS NULL OR s.monorepo_tool = p_monorepo_tool OR s.monorepo_tool IS NULL)
  ORDER BY
    sig.embedding <=> p_query_embedding,
    s.success_count DESC,
    s.verified_on DESC NULLS LAST
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Get solution details with steps and checks
CREATE OR REPLACE FUNCTION get_solution_details(p_solution_id bigint)
RETURNS TABLE (
  solution jsonb,
  steps jsonb[],
  checks jsonb[]
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    jsonb_build_object(
      'id', s.id,
      'title', s.title,
      'description', s.description,
      'category', s.category,
      'component', s.component,
      'tags', s.tags,
      'success_count', s.success_count,
      'failure_count', s.failure_count,
      'verified_on', s.verified_on
    ),
    ARRAY(
      SELECT jsonb_build_object(
        'order', step_order,
        'kind', kind,
        'payload', payload,
        'description', description,
        'timeout_ms', timeout_ms
      )
      FROM steps
      WHERE solution_id = p_solution_id
      ORDER BY step_order
    ),
    ARRAY(
      SELECT jsonb_build_object(
        'order', check_order,
        'cmd', cmd,
        'expect_substring', expect_substring,
        'expect_exit_code', expect_exit_code,
        'timeout_ms', timeout_ms
      )
      FROM checks
      WHERE solution_id = p_solution_id
      ORDER BY check_order
    )
  FROM solutions s
  WHERE s.id = p_solution_id;
END;
$$ LANGUAGE plpgsql;

-- Record solution application (success/failure)
CREATE OR REPLACE FUNCTION record_solution_outcome(
  p_solution_id bigint,
  p_success boolean
)
RETURNS void AS $$
BEGIN
  IF p_success THEN
    UPDATE solutions
    SET
      success_count = success_count + 1,
      last_applied_at = now(),
      verified_on = now(),
      updated_at = now()
    WHERE id = p_solution_id;
  ELSE
    UPDATE solutions
    SET
      failure_count = failure_count + 1,
      last_applied_at = now(),
      updated_at = now()
    WHERE id = p_solution_id;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- Helper: extract error signature from log text
CREATE OR REPLACE FUNCTION extract_error_signature(log_text text)
RETURNS text AS $$
DECLARE
  signature text;
BEGIN
  -- Extract first error line
  signature := substring(log_text FROM '(?:ERROR|error|Error|FAIL|fail|Failed)[^\n]*');

  -- If no match, try common build error patterns
  IF signature IS NULL THEN
    signature := substring(log_text FROM '(?:npm ERR!|Command failed|Build failed)[^\n]*');
  END IF;

  -- Fallback: first line
  IF signature IS NULL THEN
    signature := substring(log_text FROM '^[^\n]+');
  END IF;

  RETURN signature;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON TABLE solutions IS 'Reusable fixpacks for recurring issues';
COMMENT ON TABLE signatures IS 'Error patterns that trigger solutions';
COMMENT ON TABLE steps IS 'Ordered actions to execute (cmd, patch, copy, etc)';
COMMENT ON TABLE checks IS 'Verification steps to confirm fix worked';
COMMENT ON COLUMN steps.kind IS 'Action type: cmd|patch|copy|script|env';
COMMENT ON COLUMN steps.payload IS 'JSON payload varies by kind: {run, cwd, env} for cmd, {diff, file} for patch, {src, dst, flags} for copy';
