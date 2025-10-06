# Vector Bridge MCP Server

Global vector memory service for Claude Code with **intelligent learning and feedback**.

## ✨ Key Features

### Core Capabilities
- **Multi-tenant**: Projects isolated by `project_root` path
- **Automatic chunking**: Splits text into 500-800 token chunks with overlap
- **OpenAI embeddings**: `text-embedding-3-small` (1536 dimensions, $0.02/1M tokens)
- **Postgres + pgvector**: Scalable vector storage with HNSW indexes
- **Redis cache**: 60-day embedding cache + 5-minute query cache (14.6x speedup)

### 🚀 Phase 2: Hybrid Search (v1.1.0)
- **Multi-signal ranking**: Vector similarity (60%) + BM25 text search (30%) + time decay (10%)
- **Outcome bonus**: +10% for successful solutions, -5% for failures
- **Conversation summaries**: Automatic ingestion after compaction
- **Better relevance**: Technical keywords + semantic understanding + recency

### 🎯 Phase 3: Learning System (v1.2.0)
- **Memory feedback**: `memory_feedback` tool to record helpful/unhelpful memories
- **Feedback bonus**: +15% ranking boost for consistently helpful memories
- **Pattern detection**: `detect_patterns` finds recurring solutions across projects
- **Self-improving**: Rankings improve over time based on actual usefulness

### 🧠 Phase 4: Smart Solution Discovery (v1.3.0)
- **Pattern-Solution Linking**: Automatically connect error patterns to proven solutions
- **Pattern Detection**: Analyze error messages to find matching patterns (`pattern_detect`)
- **Pattern-Specific Rankings**: Solutions ranked by success rate for specific patterns
- **Golden Paths**: Discover most successful pattern-solution combinations (`golden_paths`)
- **Cross-Project Intelligence**: Learn which solutions work best across all projects

## MCP Tools

### memory_ingest
Ingest text content into vector store with metadata.

```typescript
{
  project_root: "/Users/name/my-project",
  path: "src/utils/helper.ts",
  text: "function add(a, b) { return a + b; }",
  meta: {
    type: "code",
    language: "typescript",
    outcome_status: "success" // optional: success|failure|unknown
  }
}
```

### memory_search
Hybrid search with vector + BM25 + time decay + feedback bonus.

```typescript
{
  project_root: "/Users/name/my-project",
  query: "how to add two numbers",
  k: 8,  // max 20
  global: false,  // true = search across all projects
  component: "backend",  // optional filter
  category: "code"  // optional filter
}
```

Returns:
```json
{
  "results": [
    {
      "path": "src/utils/math.ts",
      "chunk": "function add(a, b) { return a + b; }",
      "score": 0.92,
      "meta": {
        "chunk_id": 123,  // for feedback
        "vector_score": 0.85,
        "bm25_score": 0.45,
        "time_score": 0.98,
        "feedback_score": 1.0,  // 100% helpful
        "outcome_bonus": 0.10
      }
    }
  ]
}
```

### memory_feedback (NEW in v1.2.0)
Record whether a memory was helpful.

```typescript
{
  chunk_id: 123,  // from search result meta
  helpful: true,
  context: "Solved my addition function bug"  // optional
}
```

### memory_projects
List all indexed projects with stats.

```typescript
{}
```

### solution_search
Search for solution fixpacks matching error messages.

```typescript
{
  error_message: "ENOTFOUND redis.railway.internal",
  category: "deploy",  // optional
  limit: 5
}
```

### solution_apply
Record success/failure of applied solutions.

```typescript
{
  solution_id: 16,
  success: true
}
```

### pattern_detect (NEW in v1.3.0)
Detect patterns in error messages and suggest linked solutions.

```typescript
{
  query_text: "Redis connection failing with ENOTFOUND redis.railway.internal",
  limit: 3
}
```

Returns patterns with match scores and top solutions.

### pattern_solutions (NEW in v1.3.0)
Get solutions ranked for a specific pattern.

```typescript
{
  pattern_tag: "redis-connection",
  pattern_category: "runtime",  // optional
  limit: 5
}
```

Returns solutions ranked by pattern-specific success rates.

### pattern_link (NEW in v1.3.0)
Link a pattern to a solution after applying it.

```typescript
{
  pattern_tag: "redis-connection",
  pattern_category: "runtime",
  solution_id: 16,
  success: true
}
```

### golden_paths (NEW in v1.3.0)
Get proven pattern-solution combinations.

```typescript
{
  min_applications: 3,  // minimum # of times pattern+solution succeeded
  limit: 20
}
```

Returns most successful pattern-solution pairs across all projects.

## Setup

### Quick Start (Railway)

```bash
# 1. Install dependencies
cd ~/.claude/mcp-servers/vector-bridge
npm install
npm run build

# 2. Set environment variables
export DATABASE_URL_MEMORY="postgresql://user:pass@host:port/railway"
export REDIS_URL="redis://default:pass@host:port"  # optional, for caching
export OPENAI_API_KEY="sk-proj-..."

# 3. Run all migrations
for f in migrations/*.sql; do
  psql $DATABASE_URL_MEMORY < $f
done

# 4. Configure Claude Code
# Add to ~/.claude/settings.json:
{
  "mcpServers": {
    "vector-bridge": {
      "command": "node",
      "args": ["/Users/YOU/.claude/mcp-servers/vector-bridge/dist/index.js"],
      "env": {
        "DATABASE_URL": "${DATABASE_URL_MEMORY}",
        "REDIS_URL": "${REDIS_URL}",
        "OPENAI_API_KEY": "${OPENAI_API_KEY}"
      }
    }
  }
}
```

### Migrations

Run in order:
1. `001_init.sql` - Base schema (projects, documents, search functions)
2. `002_add_metadata.sql` - Categorization (component, category, tags)
3. `003_solution_memory.sql` - Solution fixpacks
4. `004_hnsw_indexes.sql` - Performance (HNSW indexes)
5. `005_hybrid_search.sql` - BM25 + time decay
6. `006_feedback_system.sql` - Feedback + pattern detection
7. `007_pattern_solution_linking.sql` - Pattern-solution linking (v1.3.0)

## Schema

```sql
-- Core tables
projects(id, root_path, label, created_at, updated_at)
documents(id, project_id, path, chunk, embedding, component, category, tags, meta, content_sha, chunk_tsv, updated_at)

-- Learning system (v1.2.0)
memory_feedback(id, chunk_id, helpful, context, created_at)

-- Solution memory
solutions(id, title, description, category, signatures, steps, checks, success_rate, ...)
signatures(id, solution_id, text, regexes, embedding, meta)
steps(id, solution_id, step_order, kind, payload, description, timeout_ms)
checks(id, solution_id, check_order, cmd, expect_substring, expect_exit_code, timeout_ms)

-- Pattern-solution linking (v1.3.0)
pattern_solutions(id, pattern_tag, pattern_category, solution_id, success_count, failure_count, avg_helpful_ratio)
```

## Hook Integration

### Stop Hook (Automatic Ingestion)
`stop_digest.py` automatically ingests DIGEST blocks after each session:
- Extracts decisions, files, contracts, next steps
- Chunks and embeds content
- Stores with metadata (agent, task_id, outcome_status)

### PostCompact Hook (Conversation Summaries)
`conversation_summary_ingest.py` ingests conversation summaries after compaction:
- Summarizes key decisions and outcomes
- Infers success/failure status
- Creates persistent memory across sessions

### PreToolUse Hook (Auto Context Injection)
`memory_context_inject.py` automatically injects relevant memories before Task tool:
- Searches vector memory for similar work
- Injects top 2-3 results as compact bullets
- Guardrails: queue ≤5, context <70%, score ≥25%

## Ranking Algorithm

Final score combines multiple signals:

```
combined_score =
  vector_similarity * 0.60 +
  bm25_rank * 0.30 +
  time_decay * 0.10 +
  feedback_ratio * 0.15 +  // Phase 3
  outcome_bonus            // +10% success, -5% failure
```

### Vector Similarity (60%)
Cosine similarity between query embedding and document embedding.

### BM25 Text Search (30%)
Keyword matching using PostgreSQL full-text search.

### Time Decay (10%)
Exponential decay with 30-day half-life: `exp(-0.023 * days_old)`

### Feedback Bonus (15%)
Ratio of helpful feedback: `helpful_count / total_feedback`

### Outcome Bonus
- Success: +10%
- Failure: -5%
- Unknown: 0%

## Performance

### Cache Performance
- **Embedding cache**: 60-day TTL, ~70% cost savings
- **Query cache**: 5-minute TTL, 14.6x speedup
- **Dedupe cache**: 48-hour TTL, prevents duplicate ingestion

### Graceful Degradation
System continues if Redis unavailable (fallback mode without cache).

## Cost Estimate

**Monthly costs for typical usage (10K chunks, 1K searches):**
- OpenAI embeddings: $0.10-0.20
- Railway Postgres: $5-10
- Railway Redis: $5
- **Total: ~$10-15/month**

With cache:
- Embedding cost: -70% (cached hits)
- Search latency: -93% (14.6x faster)

## Usage Examples

### Basic Workflow

```typescript
// 1. Ingest code snippet
await memory_ingest({
  project_root: "/Users/me/my-app",
  path: "src/auth.ts",
  text: "export async function login(email, password) { ... }",
  meta: {
    component: "backend",
    category: "code",
    outcome_status: "success"
  }
});

// 2. Search for similar code
const results = await memory_search({
  project_root: "/Users/me/my-app",
  query: "user authentication with email",
  k: 5
});

// 3. Record feedback on helpful result
await memory_feedback({
  chunk_id: results.results[0].meta.chunk_id,
  helpful: true,
  context: "Solved login bug"
});

// 4. Future searches will rank this result higher (+15% feedback bonus)
```

### Cross-Project Patterns

```typescript
// Find recurring solutions across all projects
const results = await memory_search({
  project_root: "/Users/me/project-a",
  query: "Redis connection Docker",
  global: true,  // search all projects
  k: 10
});

// Detect patterns
const patterns = await detect_patterns({
  min_occurrences: 3,
  category: "decision"
});
```

## Development

```bash
# Install
npm install

# Build
npm run build

# Watch mode
npm run dev

# Test connection
node dist/index.js
```

## Architecture

```
┌─────────────────────┐
│   Claude Code       │
│   (MCP Client)      │
└──────────┬──────────┘
           │ stdio
           ▼
┌─────────────────────┐
│  Vector Bridge MCP  │
│  (Node.js server)   │
├─────────────────────┤
│ - memory_ingest     │
│ - memory_search     │
│ - memory_feedback   │
│ - detect_patterns   │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌─────────┐  ┌─────────┐
│ Postgres│  │  Redis  │
│ pgvector│  │  Cache  │
└─────────┘  └─────────┘
```

## Roadmap

### ✅ Phase 1: Foundation
- Multi-tenant architecture
- OpenAI embeddings
- Basic vector search

### ✅ Phase 2: Hybrid Search (v1.1.0)
- BM25 text search
- Time decay
- Outcome bonus
- Conversation summaries

### ✅ Phase 3: Learning System (v1.2.0)
- Memory feedback tool
- Feedback bonus (+15%)
- Pattern detection
- Self-improving rankings

### 🔜 Phase 4: Advanced Features
- A/B testing framework
- Temporal reasoning ("what worked last month?")
- Multi-modal memory (code + diagrams + screenshots)
- Personalized rankings per user

## Contributing

This is part of the [Claude Agents Framework](https://github.com/servesys-labs/claude-agents).

## License

MIT
