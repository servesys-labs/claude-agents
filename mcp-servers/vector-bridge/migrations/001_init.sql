-- Migration 001: Initialize pgvector with multi-tenant schema
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Projects table (tenancy boundary)
CREATE TABLE IF NOT EXISTS projects (
  id bigserial PRIMARY KEY,
  root_path text UNIQUE NOT NULL,
  label text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Documents table (vector chunks)
CREATE TABLE IF NOT EXISTS documents (
  id bigserial PRIMARY KEY,
  project_id bigint NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  path text NOT NULL,
  chunk text NOT NULL,
  embedding vector(1536) NOT NULL,
  meta jsonb DEFAULT '{}',
  content_sha text NOT NULL,
  updated_at timestamptz DEFAULT now(),
  UNIQUE(project_id, path, content_sha)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS documents_embedding_idx ON documents
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

CREATE INDEX IF NOT EXISTS documents_project_path_idx ON documents(project_id, path);
CREATE INDEX IF NOT EXISTS documents_project_id_idx ON documents(project_id);

-- Helper function: get or create project
CREATE OR REPLACE FUNCTION get_or_create_project(p_root_path text, p_label text DEFAULT NULL)
RETURNS bigint AS $$
DECLARE
  v_project_id bigint;
BEGIN
  INSERT INTO projects (root_path, label)
  VALUES (p_root_path, COALESCE(p_label, p_root_path))
  ON CONFLICT (root_path) DO UPDATE SET updated_at = now()
  RETURNING id INTO v_project_id;

  RETURN v_project_id;
END;
$$ LANGUAGE plpgsql;

-- Helper function: search with cosine similarity
-- Usage: SELECT * FROM search_documents(project_id, embedding_vector, limit)
CREATE OR REPLACE FUNCTION search_documents(
  p_project_id bigint,
  p_embedding vector(1536),
  p_limit integer DEFAULT 8
)
RETURNS TABLE (
  id bigint,
  path text,
  chunk text,
  meta jsonb,
  score numeric
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.id,
    d.path,
    d.chunk,
    d.meta,
    (1 - (d.embedding <=> p_embedding))::numeric AS score
  FROM documents d
  WHERE d.project_id = p_project_id
  ORDER BY d.embedding <=> p_embedding
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Helper function: global search across all projects
CREATE OR REPLACE FUNCTION search_documents_global(
  p_embedding vector(1536),
  p_limit integer DEFAULT 8
)
RETURNS TABLE (
  id bigint,
  project_id bigint,
  root_path text,
  path text,
  chunk text,
  meta jsonb,
  score numeric
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.id,
    d.project_id,
    p.root_path,
    d.path,
    d.chunk,
    d.meta,
    (1 - (d.embedding <=> p_embedding))::numeric AS score
  FROM documents d
  JOIN projects p ON d.project_id = p.id
  ORDER BY d.embedding <=> p_embedding
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;
