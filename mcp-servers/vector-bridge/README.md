# Vector Bridge MCP Server

Global vector memory service for Claude Code across all projects.

## Features

- **Multi-tenant**: Projects are isolated by `project_root` path
- **Automatic chunking**: Splits text into 500-800 token chunks with overlap
- **OpenAI embeddings**: Uses `text-embedding-3-small` (1536 dimensions)
- **Postgres + pgvector**: Scalable vector storage with cosine similarity search
- **MCP tools**: `memory_ingest`, `memory_search`, `memory_projects`

## Setup

### 1. Create Railway Postgres Service

```bash
# In Railway dashboard:
# 1. New Project → "ai-memory"
# 2. Add Postgres service
# 3. Copy DATABASE_URL
```

### 2. Set Environment Variables

Add to `~/.zshrc` or `~/.bashrc`:

```bash
export DATABASE_URL_MEMORY="postgresql://user:pass@host:port/ai_memory"
export OPENAI_API_KEY="sk-..."
```

### 3. Install Dependencies

```bash
cd ~/.claude/mcp-servers/vector-bridge
npm install
npm run build
```

### 4. Run Migration

```bash
# Connect to Railway Postgres and run:
psql $DATABASE_URL_MEMORY < migrations/001_init.sql
```

### 5. Register in Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "vector-bridge": {
      "command": "node",
      "args": ["/Users/agentsy/.claude/mcp-servers/vector-bridge/dist/index.js"],
      "env": {
        "DATABASE_URL": "${DATABASE_URL_MEMORY}",
        "OPENAI_API_KEY": "${OPENAI_API_KEY}"
      }
    }
  }
}
```

## MCP Tools

### memory_ingest

Ingest text content into vector store.

```typescript
{
  project_root: "/Users/name/my-project",
  path: "src/utils/helper.ts",
  text: "function add(a, b) { return a + b; }",
  meta: { type: "code", language: "typescript" }
}
```

### memory_search

Search for similar chunks.

```typescript
{
  project_root: "/Users/name/my-project",
  query: "how to add two numbers",
  k: 8,
  global: false
}
```

### memory_projects

List all indexed projects.

```typescript
{}
```

## Schema

```sql
projects(id, root_path, label, created_at, updated_at)
documents(id, project_id, path, chunk, embedding, meta, content_sha, updated_at)
```

## Hook Integration

The `stop_digest.py` hook automatically ingests DIGEST blocks after each turn.

## Cost

- Embeddings: ~$0.00002 per 1K tokens (OpenAI text-embedding-3-small)
- Storage: ~$0.25/GB/month (Railway Postgres)
- Typical usage: ~$0.10-0.50/month for 10K chunks

## Future: Swap to Pinecone

The `MemoryProvider` interface allows swapping to Pinecone:

1. Implement `PineconeProvider` class
2. Set `MEMORY_PROVIDER=pinecone` env var
3. No changes to MCP tools or hooks
