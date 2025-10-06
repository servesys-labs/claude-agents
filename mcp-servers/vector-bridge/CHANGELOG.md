# Changelog

All notable changes to the Vector Bridge MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2025-10-06

### Added - Phase 4: Smart Solution Discovery & Pattern Surfacing
- **Pattern-Solution Linking**: Automatic linking of detected patterns to proven solutions
- **Pattern Detection in Queries**: `detect_patterns_in_query()` analyzes error messages to find matching patterns
- **Pattern-Based Solution Ranking**: Solutions ranked by pattern-specific success rates
- **Golden Paths**: Discover most successful pattern-solution combinations across projects
- **Cross-Project Pattern Intelligence**: Learn which solutions work best for specific error patterns
- **Migration 007**: Pattern-solutions table and smart discovery functions

### New MCP Tools
- `pattern_detect`: Detect patterns in error messages and suggest linked solutions
- `pattern_solutions`: Get solutions ranked for a specific pattern (e.g., "redis-connection")
- `pattern_link`: Link a pattern to a solution and record success/failure for learning
- `golden_paths`: Get proven pattern-solution combinations with high success rates

### SolutionProvider API
- `detectPatternsInQuery()`: Analyze query text for patterns
- `getSolutionsForPattern()`: Get ranked solutions for a pattern tag
- `linkPatternToSolution()`: Record pattern-solution application with outcome
- `getGoldenPaths()`: Retrieve most successful pattern-solution pairs
- `updatePatternSolutionHelpfulness()`: Sync feedback scores to pattern rankings

### Changed
- Solutions now track pattern-specific success rates in addition to global success rates
- Pattern-solution ranking combines: success rate (60%) + applications (30%) + helpfulness (10%)
- Golden paths require 3+ applications by default to ensure statistical significance

### Technical Details
- Pattern tags derived from `documents.tags` field (first tag used as pattern identifier)
- Pattern categories align with solution categories (runtime, build, deploy, etc.)
- Pattern detection requires minimum 3 document occurrences to avoid noise
- Pattern matching uses tag overlap (minimum 10% match score required)
- Success tracking: `success_count` and `failure_count` per pattern-solution pair

## [1.2.0] - 2025-10-06

### Added - Phase 3: Learning System
- **Memory Feedback Tool** (`memory_feedback`): Record helpful/unhelpful feedback on search results
- **Feedback Bonus**: +15% ranking boost for memories with consistently helpful feedback
- **Pattern Detection**: SQL functions to detect recurring solutions across projects (`detect_patterns`)
- **Memory Feedback Table**: Tracks helpful/unhelpful ratings with context
- **Enhanced Search Functions**: `search_hybrid_with_feedback` and `search_hybrid_global_with_feedback`
- **Migration 006**: Feedback system and pattern detection

### Changed
- Search results now include `chunk_id` in meta for feedback tracking
- Search results include `feedback_score` showing helpful ratio (0-1)
- PgVectorProvider now uses feedback-enhanced search functions
- Search rankings self-improve over time based on actual usefulness

### Fixed
- Integrated feedback bonus into actual search queries (was calculated but not used)
- Cache keys now differentiate between feedback-enhanced and standard search

## [1.1.0] - 2025-10-06

### Added - Phase 2: Hybrid Search
- **Hybrid Search Ranking**: Combines vector similarity (60%) + BM25 text search (30%) + time decay (10%)
- **BM25 Full-Text Search**: PostgreSQL `tsvector` and `ts_rank_cd` for keyword matching
- **Time Decay**: Exponential decay with 30-day half-life favors recent memories
- **Outcome Bonus**: +10% for successful solutions, -5% for failures
- **Conversation Summary Ingestion**: PostCompact hook (`conversation_summary_ingest.py`)
- **Auto Context Injection**: PreToolUse hook (`memory_context_inject.py`)
- **Migration 005**: Hybrid search functions and `chunk_tsv` column

### Changed
- Search results now include detailed scoring breakdown: `vector_score`, `bm25_score`, `time_score`, `outcome_bonus`
- Cache parameters include `hybrid: true` flag to differentiate from old vector-only cache
- Query text now used for BM25 matching in addition to vector similarity

### Performance
- BM25 index (`documents_chunk_tsv_idx`) for fast full-text search
- Automatic `tsvector` updates via trigger
- Redis query cache (5-minute TTL, 14.6x speedup)

## [1.0.0] - 2024-10-04

### Added - Foundation
- Multi-tenant vector memory with project isolation
- OpenAI embeddings (`text-embedding-3-small`, 1536 dimensions)
- Postgres + pgvector for vector storage
- Redis cache for embeddings (60-day TTL, ~70% cost savings)
- Basic vector search with cosine similarity
- Automatic text chunking (500-800 tokens with overlap)
- Dedupe system (SHA256 content hashing, 48-hour cache)
- Solution memory system for error fixpacks

### MCP Tools
- `memory_ingest`: Ingest text content with metadata
- `memory_search`: Semantic search with filters
- `memory_projects`: List indexed projects
- `solution_search`: Find fixpacks for error messages
- `solution_apply`: Record success/failure of solutions
- `solution_preview`: DRY-RUN preview of solution steps
- `solution_upsert`: Create/update solution fixpacks

### Migrations
- `001_init.sql`: Base schema (projects, documents, search functions)
- `002_add_metadata.sql`: Categorization (component, category, tags)
- `003_solution_memory.sql`: Solution fixpacks
- `004_hnsw_indexes.sql`: HNSW indexes for performance

### Hook Integration
- `stop_digest.py`: Automatic DIGEST ingestion after each session
- Queue-based async ingestion with retry logic

### Performance
- HNSW indexes for fast approximate nearest neighbor search
- Redis embedding cache (60-day TTL)
- Dedupe cache (48-hour TTL)
- Graceful degradation when Redis unavailable

---

## Future Releases

### [1.3.0] - Planned
- A/B testing framework for ranking algorithms
- Temporal reasoning ("what worked last month?")
- Multi-modal memory (code + diagrams + screenshots)
- Personalized rankings per user
- Cross-project pattern catalog

---

## Migration Notes

### Upgrading from 1.1.0 to 1.2.0
Run migration 006:
```bash
psql $DATABASE_URL_MEMORY < migrations/006_feedback_system.sql
```

### Upgrading from 1.0.0 to 1.1.0
Run migration 005:
```bash
psql $DATABASE_URL_MEMORY < migrations/005_hybrid_search.sql
```

---

## Breaking Changes

### None in 1.2.0
- All changes are backward compatible
- Existing search queries work without modification
- Feedback system is opt-in

### None in 1.1.0
- All changes are backward compatible
- Old `search_documents` functions still work
- Hybrid search is used automatically for better results

---

## Contributors

- Main Agent (Claude Orchestrator)
- Implementation Engineer
- Database Modeler
- Test Author

Generated with [Claude Code](https://claude.com/claude-code)
