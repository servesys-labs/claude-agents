# Vector Bridge Setup Guide

Complete setup instructions for global RAG architecture.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│ Multiple Projects (any directory)                       │
├─────────────────────────────────────────────────────────┤
│ Project A  │  Project B  │  Project C                   │
│ .mcp.json  │  .mcp.json  │  .mcp.json                   │
│ NOTES.md   │  NOTES.md   │  NOTES.md                    │
└──────┬──────────┬──────────┬────────────────────────────┘
       │          │          │
       └──────────┴──────────┘
                  │
         ┌────────▼────────┐
         │ Vector Bridge   │
         │ MCP Server      │
         │ (Global)        │
         └────────┬────────┘
                  │
         ┌────────▼────────┐
         │ Railway Postgres│
         │ + pgvector      │
         │ (ai-memory)     │
         └─────────────────┘
```

**Key Principles:**
- **One vector store for all projects** (multi-tenant with `project_id`)
- **Global MCP server** installed in `~/.claude/mcp-servers/`
- **Per-project activation** via `.mcp.json` (copied from template)
- **Automatic ingestion** via `stop_digest.py` hook

## Step-by-Step Setup

### 1. Create Railway Postgres Service

```bash
# In Railway dashboard (https://railway.app):
1. Create new project: "ai-memory"
2. Add service: Postgres
3. Copy DATABASE_URL from variables tab
```

### 2. Set Global Environment Variables

Add to `~/.zshrc` (or `~/.bashrc`):

```bash
export DATABASE_URL_MEMORY="postgresql://postgres:PASSWORD@HOST:PORT/railway"
export OPENAI_API_KEY="sk-proj-..."
```

Reload shell:
```bash
source ~/.zshrc
```

### 3. Install Vector Bridge Dependencies

```bash
cd ~/.claude/mcp-servers/vector-bridge
npm install
npm run build
```

### 4. Run Database Migration

```bash
# Connect to Railway Postgres
psql $DATABASE_URL_MEMORY < migrations/001_init.sql
```

Verify:
```bash
psql $DATABASE_URL_MEMORY -c "\dx"  # Should show 'vector' extension
psql $DATABASE_URL_MEMORY -c "\dt"  # Should show 'projects' and 'documents'
```

### 5. Bootstrap Your First Project

```bash
cd /path/to/your/project
bash ~/claude-hooks/bootstrap_project.sh
```

This creates:
- `.mcp.json` (vector-bridge registration)
- `NOTES.md` (digest storage)
- `CLAUDE.md` (project config)

### 6. Restart Claude Code

1. Quit Claude Code completely
2. Reopen from project directory
3. When prompted, **approve vector-bridge MCP server**

### 7. Test Manual Ingestion

In Claude Code, use the MCP tool:

```typescript
// Use memory_ingest tool
{
  project_root: "/Users/agentsy/your-project",
  path: "README.md",
  text: "# My Project\n\nThis is a test project.",
  meta: { type: "documentation" }
}
```

### 8. Test Search

```typescript
// Use memory_search tool
{
  project_root: "/Users/agentsy/your-project",
  query: "test project",
  k: 5,
  global: false
}
```

### 9. Verify Auto-Ingestion

Send a message with a DIGEST block:

````markdown
```json DIGEST
{
  "agent": "Test",
  "task_id": "test-auto-ingest",
  "decisions": ["Testing automatic ingestion"],
  "files": [{"path": "test.md", "reason": "test"}],
  "contracts": [],
  "next": [],
  "evidence": {}
}
```
````

Check if it was ingested:

```bash
psql $DATABASE_URL_MEMORY -c "SELECT COUNT(*) FROM documents;"
```

## Troubleshooting

### MCP Server Not Starting

```bash
# Check logs
cat ~/.claude/logs/mcp-vector-bridge.log

# Test manually
cd ~/.claude/mcp-servers/vector-bridge
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | node dist/index.js
```

### Database Connection Issues

```bash
# Test connection
psql $DATABASE_URL_MEMORY -c "SELECT 1;"

# Check environment variable
echo $DATABASE_URL_MEMORY
```

### Migration Errors

```bash
# Check if extension exists
psql $DATABASE_URL_MEMORY -c "SELECT * FROM pg_extension WHERE extname='vector';"

# If missing, ensure pgvector is installed on Railway
# (Railway Postgres should have it by default)
```

### Type Errors in memory_client.py

```bash
# Run typecheck
mypy ~/claude-hooks/memory_client.py

# Common fix: use `dict | None` instead of `dict = None`
```

## Usage Examples

### Ingest Code Files

```typescript
memory_ingest({
  project_root: "/Users/name/my-app",
  path: "src/auth/login.ts",
  text: "<file contents>",
  meta: { language: "typescript", type: "code" }
})
```

### Search Across All Projects

```typescript
memory_search({
  project_root: "/Users/name/my-app",  // Still required but ignored
  query: "authentication flow",
  k: 10,
  global: true  // Search all projects
})
```

### List Indexed Projects

```typescript
memory_projects({})
```

## Cost Estimates

- **Embeddings**: $0.00002 per 1K tokens (OpenAI text-embedding-3-small)
- **Storage**: ~$0.25/GB/month (Railway Postgres)
- **Typical monthly cost**: $0.10-0.50 for 10,000 chunks

## Future Enhancements

1. **Pinecone Migration**: Implement `PineconeProvider` class
2. **Batch Reindexing**: CLI tool to reindex entire projects
3. **RAG Suggestions**: UserPromptSubmit hook for context hints
4. **Hybrid Search**: Combine vector + BM25 full-text search
5. **Metadata Filtering**: Search within file types, date ranges, etc.

## File Structure

```
~/.claude/
├── mcp-servers/
│   └── vector-bridge/
│       ├── dist/                 # Compiled JS
│       ├── migrations/
│       │   └── 001_init.sql     # Database schema
│       ├── src/
│       │   ├── index.ts          # MCP server entry
│       │   ├── providers/
│       │   │   ├── memory-provider.interface.ts
│       │   │   └── pgvector.provider.ts
│       │   ├── services/
│       │   │   ├── embedding.service.ts
│       │   │   └── chunking.service.ts
│       │   └── tools/
│       │       ├── memory-ingest.tool.ts
│       │       ├── memory-search.tool.ts
│       │       └── memory-projects.tool.ts
│       ├── package.json
│       ├── tsconfig.json
│       └── README.md
├── mcp-template.json            # Template for new projects
└── settings.json                # Global hooks config

~/claude-hooks/
├── stop_digest.py               # Auto-captures DIGESTs
├── memory_client.py             # Python wrapper for MCP tools
└── bootstrap_project.sh         # Project setup script
```

## Support

- GitHub Issues: https://github.com/anthropics/claude-code/issues
- Railway Docs: https://docs.railway.app/
- pgvector Docs: https://github.com/pgvector/pgvector
