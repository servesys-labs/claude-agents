/**
 * MemoryProvider interface - abstraction for swappable vector backends
 * Implementations: PgVectorProvider, PineconeProvider (future)
 */

export interface MemoryChunk {
  path: string;
  chunk: string;
  score?: number;
  meta?: Record<string, any>;
  component?: string;
  category?: string;
  tags?: string[];
}

export interface IngestResult {
  chunks: number;
  project_id?: string | number;
}

export interface SearchResult {
  results: MemoryChunk[];
  project_id?: string | number;
}

export interface ProjectInfo {
  id: number;
  root_path: string;
  label: string;
  doc_count: number;
}

export interface MemoryProvider {
  /**
   * Ingest text content into vector store
   * @param project_root - Absolute path to project root (tenancy key)
   * @param path - Relative path within project
   * @param text - Text content to chunk and embed
   * @param meta - Optional metadata to attach to chunks
   */
  ingest(
    project_root: string | null,
    path: string,
    text: string,
    meta?: Record<string, any>
  ): Promise<IngestResult>;

  /**
   * Search for similar chunks
   * @param project_root - Project root to search within
   * @param query - Search query text
   * @param k - Number of results to return (default: 8, max: 20)
   * @param global - If true, search across all projects (default: false)
   * @param component - Filter by component (backend|mobile|web|infra|data|docs|tests)
   * @param category - Filter by category (code|docs|ops|tests|data-model|decision)
   * @param tags - Filter by tags (must overlap)
   */
  search(
    project_root: string | null,
    query: string,
    k?: number,
    global?: boolean,
    component?: string,
    category?: string,
    tags?: string[]
  ): Promise<SearchResult>;

  /**
   * Delete all chunks for a specific path
   * @param project_root - Project root
   * @param path - Path to delete
   */
  deleteByPath(
    project_root: string | null,
    path: string
  ): Promise<{ deleted: number }>;

  /**
   * Reindex entire project (delete all + re-ingest)
   * @param project_root - Project root to reindex
   */
  reindexProject(project_root: string): Promise<{ indexed: number }>;

  /**
   * List all indexed projects with stats
   */
  listProjects(): Promise<ProjectInfo[]>;
}
