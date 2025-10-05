-- Migration 002: Add categorization metadata
-- Adds component, category, repo_name, and tags for filtered retrieval

-- Add new columns to documents
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS repo_name text,
  ADD COLUMN IF NOT EXISTS component text,
  ADD COLUMN IF NOT EXISTS category text,
  ADD COLUMN IF NOT EXISTS tags text[] DEFAULT '{}';

-- Backfill repo_name from project_root (basename of path)
UPDATE documents
SET repo_name = (
  SELECT regexp_replace(p.root_path, '^.*/', '')
  FROM projects p
  WHERE p.id = documents.project_id
)
WHERE repo_name IS NULL;

-- Set NOT NULL after backfill
ALTER TABLE documents
  ALTER COLUMN repo_name SET NOT NULL,
  ALTER COLUMN component SET NOT NULL,
  ALTER COLUMN category SET NOT NULL;

-- Create indexes for filtered queries
CREATE INDEX IF NOT EXISTS documents_component_category_idx
  ON documents(project_id, component, category);

CREATE INDEX IF NOT EXISTS documents_tags_idx
  ON documents USING gin(tags);

-- Update search function to support filtering
CREATE OR REPLACE FUNCTION search_documents(
  p_project_id bigint,
  p_embedding vector(1536),
  p_limit integer DEFAULT 8,
  p_component text DEFAULT NULL,
  p_category text DEFAULT NULL,
  p_tags text[] DEFAULT NULL
)
RETURNS TABLE (
  id bigint,
  path text,
  chunk text,
  meta jsonb,
  score numeric,
  component text,
  category text,
  tags text[]
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.id,
    d.path,
    d.chunk,
    d.meta,
    (1 - (d.embedding <=> p_embedding))::numeric AS score,
    d.component,
    d.category,
    d.tags
  FROM documents d
  WHERE d.project_id = p_project_id
    AND (p_component IS NULL OR d.component = p_component)
    AND (p_category IS NULL OR d.category = p_category)
    AND (p_tags IS NULL OR d.tags && p_tags)  -- Overlaps operator
  ORDER BY d.embedding <=> p_embedding
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Update global search function
CREATE OR REPLACE FUNCTION search_documents_global(
  p_embedding vector(1536),
  p_limit integer DEFAULT 8,
  p_component text DEFAULT NULL,
  p_category text DEFAULT NULL,
  p_tags text[] DEFAULT NULL
)
RETURNS TABLE (
  id bigint,
  project_id bigint,
  root_path text,
  repo_name text,
  path text,
  chunk text,
  meta jsonb,
  score numeric,
  component text,
  category text,
  tags text[]
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.id,
    d.project_id,
    p.root_path,
    d.repo_name,
    d.path,
    d.chunk,
    d.meta,
    (1 - (d.embedding <=> p_embedding))::numeric AS score,
    d.component,
    d.category,
    d.tags
  FROM documents d
  JOIN projects p ON d.project_id = p.id
  WHERE (p_component IS NULL OR d.component = p_component)
    AND (p_category IS NULL OR d.category = p_category)
    AND (p_tags IS NULL OR d.tags && p_tags)
  ORDER BY d.embedding <=> p_embedding
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Helper: infer component from file path
CREATE OR REPLACE FUNCTION infer_component(file_path text) RETURNS text AS $$
BEGIN
  -- Categorize by common directory patterns
  IF file_path ~ '^(mobile|app|ios|android)/' THEN RETURN 'mobile';
  ELSIF file_path ~ '^(backend|server|api)/' THEN RETURN 'backend';
  ELSIF file_path ~ '^(web|frontend|client)/' THEN RETURN 'web';
  ELSIF file_path ~ '^(infra|infrastructure|deploy|docker|k8s)/' THEN RETURN 'infra';
  ELSIF file_path ~ '^(data|migrations|seeds)/' THEN RETURN 'data';
  ELSIF file_path ~ '^(docs|documentation)/' THEN RETURN 'docs';
  ELSIF file_path ~ '^(test|spec|__tests__)/' THEN RETURN 'tests';
  ELSE RETURN 'other';
  END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Helper: infer category from content/path
CREATE OR REPLACE FUNCTION infer_category(file_path text, chunk text) RETURNS text AS $$
BEGIN
  -- Prioritize by file extension and content patterns
  IF file_path ~ '\.(md|txt|rst)$' THEN RETURN 'docs';
  ELSIF file_path ~ '\.(test|spec)\.(ts|js|py)$' THEN RETURN 'tests';
  ELSIF file_path ~ '\.(sql|prisma|schema)' THEN RETURN 'data-model';
  ELSIF chunk ~ 'DIGEST' THEN RETURN 'decision';  -- DIGEST blocks are decisions
  ELSIF file_path ~ '\.(ya?ml|json|toml|conf)$' THEN RETURN 'ops';
  ELSE RETURN 'code';
  END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON COLUMN documents.repo_name IS 'Basename of project_root (e.g., game-start)';
COMMENT ON COLUMN documents.component IS 'Code area: backend|mobile|web|infra|data|docs|tests|other';
COMMENT ON COLUMN documents.category IS 'Content type: code|docs|ops|tests|data-model|decision';
COMMENT ON COLUMN documents.tags IS 'Free-form topic tags (e.g., [auth, api, database])';
