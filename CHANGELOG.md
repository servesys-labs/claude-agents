# Changelog

## [1.4.4] - 2025-10-05

### Fixed
- **NOTES.md Path**: Now correctly writes to `.claude/logs/NOTES.md` instead of project root
- **Environment Variable Injection**: Added `WSI_PATH` and `LOGS_DIR` injection to all hooks in settings.json
- **Per-Project Logs**: Each project now gets its own `.claude/logs/` directory with NOTES.md and wsi.json
- **Auto-Setup Hook**: Added `auto_project_setup.py` to PreToolUse hooks for automatic directory creation

### Changed
- **Stop Hook**: Updated to use `.claude/logs/` path with proper environment variable injection
- **Settings.json**: All hooks now inject `CLAUDE_PROJECT_DIR/.claude/logs/` paths for per-project isolation
- **.gitignore**: Auto-updated by hooks to ignore `.claude/logs/` and `.envrc`

## [1.4.3] - 2025-10-04

### Fixed
- **Repository URL Correction**: Updated from `ai-memory` to `claude-orchestration-framework` to match renamed GitHub repo
- **package.json**: Repository, bugs, and homepage URLs now point to correct repo

## [1.4.2] - 2025-10-04

### Changed
- **Repository Links Updated**: Now pointing to public repo at `github.com/eshbtc/ai-memory`
- **package.json**: Updated repository, bugs, and homepage URLs
- **Public Repository**: Framework source code now publicly available

## [1.4.1] - 2025-10-04

### Changed
- **README Overhaul**: Vector RAG Memory now prominently featured as killer feature
- **5-Minute Setup Guide**: Step-by-step instructions for Supabase, Pinecone, and pgvector backends
- **Drop-in Vector Backends**: Just paste API keys - zero vector DB knowledge required
- **Highlighted Benefits**: Auto-ingestion, smart retrieval, cross-project memory, privacy-first options

### Added
- **DIGEST_REMINDER_MINUTES**: Optional environment variable for gentle DIGEST reminders (default: 0 = disabled)
- **digest_reminder.py**: New hook for optional DIGEST nudges after N minutes

### Documentation
- Expanded "What's Included" section to highlight Vector RAG Memory system
- Added concrete examples of how RAG suggestions work
- Clarified supported backends (Supabase, Pinecone, self-hosted pgvector)

## [1.4.0] - 2025-10-04

### Added
- **Zero-Config Per-Project Setup**: New `auto_project_setup.py` hook automatically sets up new projects
- **Automatic .gitignore Updates**: Auto-adds `.claude/logs/` and `.envrc` to .gitignore (if git repo)
- **Automatic NOTES.md Creation**: Creates NOTES.md with header on first use
- **Setup Marker**: Creates `.claude/.setup_complete` to run once per project
- **Production Safety Hardening**: auto_project_setup.py now includes:
  - Project root guards (refuses to run in $HOME or /)
  - Atomic .gitignore writes (temp file + rename)
  - Fail-open exception handling (never blocks tool execution)
  - CRLF/LF normalization and deduplication
  - Git root detection via `git rev-parse`
  - Error logging to `.claude/logs/auto_setup_errors.log`

### Changed
- **Corrected environment variable documentation**: Removed misleading `.claude/.env` recommendations
- **Documented proper env patterns**: direnv (recommended), shell config, or settings.json injection
- **Updated QUICK_START.md**: Now shows zero-config workflow + correct env var patterns
- **Updated .gitignore**: Added `.envrc` (direnv), removed `.claude/.env` references
- **Updated settings.json**: Added auto_project_setup.py as first PreToolUse hook

### How It Works
1. User installs framework globally (one-time)
2. User opens Claude Code in any project
3. **First tool use** triggers auto_project_setup.py
4. Framework auto-creates `.claude/logs/`, updates `.gitignore`, creates `NOTES.md`
5. Marker file (`.claude/.setup_complete`) prevents re-running
6. **Zero manual configuration required!**

### Documentation
- **Option 1 (Recommended)**: Use direnv with `.envrc` in project root for auto-loading per-project env vars
- **Option 2 (Simple)**: Export in shell config (~/.zshrc) for global env vars
- **Option 3 (Explicit)**: Inject via `.claude/settings.json` commands (no secrets)
- **Clarified**: App runtime `.env` files (backend/.env, mobile/.env) are NOT used by Claude hooks/MCP

### Security
- **postgres-bridge verified safe**: Uses `EXPLAIN (FORMAT JSON)` without ANALYZE (no execution), all queries wrapped in `BEGIN READ ONLY; ... ROLLBACK;`
- **Multi-statement blocking**: Detects and rejects semicolons to prevent SQL injection chains
- **DDL/DML blocking**: Prevents CREATE, ALTER, DROP, DELETE, UPDATE, INSERT, TRUNCATE operations

## [1.3.9] - 2025-10-04

### Changed
- **Hooks now read environment variables**: All hooks updated to honor `WSI_PATH` and `LOGS_DIR` from settings.json
- **Updated hooks**: stop_digest.py, pretooluse_validate.py, task_digest_capture.py, precompact_summary.py, checkpoint_manager.py
- **Auto-create logs directory**: Hooks automatically create `LOGS_DIR` if missing (no manual `mkdir` required)
- **Backward compatible fallback**: If `WSI_PATH`/`LOGS_DIR` not set, hooks fall back to global `~/claude-hooks/logs/`

### Fixed
- stop_digest.py: Now uses `LOGS_DIR` for debug log instead of hardcoded path
- pretooluse_validate.py: Now uses `LOGS_DIR` for turn count, WSI, file hashes
- task_digest_capture.py: Now uses `LOGS_DIR` for debug log
- precompact_summary.py: Now uses `WSI_PATH` from environment
- checkpoint_manager.py: Now uses `LOGS_DIR` for checkpoints directory

### Migration
- **No action required**: Hooks auto-create directories and fall back to global paths if env vars missing
- **Per-project logs**: Just `mkdir -p .claude/logs` in your project (hooks handle the rest)
- **Settings behavior**: Global settings.json injects env vars → hooks read them → per-project isolation

## [1.3.8] - 2025-10-04

### Changed
- **Per-Project Logs by Default**: Global settings.json now uses per-project WSI/logs paths
- **PreToolUse**: Injects `WSI_PATH="$CLAUDE_PROJECT_DIR/.claude/logs/wsi.json"` and `LOGS_DIR`
- **PostToolUse (Task)**: Injects per-project WSI_PATH
- **Stop**: Injects per-project WSI_PATH
- **PreCompact**: Injects per-project LOGS_DIR
- **Proper Quoting**: All hook paths use double quotes (`"$HOME"`) to handle spaces

### Benefits
- Users get per-project logs out of the box (no configuration needed)
- NOTES.md in repo root (committed), .claude/logs/* gitignored
- WSI/logs reproducible and isolated per project
- Works immediately after `mkdir -p .claude/logs` in project

## [1.3.7] - 2025-10-04

### Added
- **Installation Validation Guide**: Comprehensive post-install checklist (INSTALLATION_VALIDATION.md)
- **Smoke Test Script**: Automated validation script (smoke-test.sh) checks paths, settings, and project setup
- **Project Settings Template**: Complete `.claude/settings.json` example with proper quoting

### Changed
- LOGS_MIGRATION.md now includes project-scoped settings example with UserPromptSubmit hooks
- Updated settings template to use double quotes for `$HOME` and `$CLAUDE_PROJECT_DIR` (handles spaces)

### Documentation
- 6 manual smoke tests for validating hook behavior
- Common gotchas section (stray paths, quote paths, debug routes, MCP registration)
- Troubleshooting guide for hook failures, WSI issues, type checking, MCP servers
- Validation one-liner script for quick checks

## [1.3.6] - 2025-10-04

### Added
- **Logs Migration Guide**: Comprehensive guide for per-project log configuration (LOGS_MIGRATION.md)
- **.gitignore Template**: Pre-configured to exclude `.claude/logs/` directory
- **Per-Project Logs Support**: Documentation for isolated, gitignored logs per project

### Changed
- README now references LOGS_MIGRATION.md for advanced log configuration
- Package now includes .gitignore and LOGS_MIGRATION.md in distribution

### Documentation
- Explained global vs per-project log trade-offs
- Step-by-step migration guide with environment variables
- Hybrid approach documentation (canonical + mirror logs)

## [1.3.5] - 2025-10-04

### Added
- **Configuration Docs**: Added embedding model standardization section to vector-bridge README
- **Redis TTL Recommendations**: Documented cache TTL guidelines (embeddings 60-90d, queries 2-10m, schema 1-6h)
- **Cache Hit Rate Logging**: Added example monitoring code for Redis cache performance

### Documentation
- Explained why 1536-dim is standard (cost, performance, pgvector compatibility)
- Warning about dimension mismatch when mixing embedding models
- Redis integration marked as optional (vector-bridge works without it)

## [1.3.4] - 2025-10-04

### Added
- **Windows Support**: PowerShell installer script (install.ps1) for Windows users
- **Cross-Platform Docs**: Updated README with Windows-specific instructions
- **Platform Detection**: Both installers handle their respective platforms

### Changed
- README now shows installation commands for both Windows and Linux/macOS
- Post-installation steps documented for both platforms

## [1.3.3] - 2025-10-04

### Fixed
- **Install Script**: Now correctly installs hooks to `~/.claude/hooks/` instead of `~/claude-hooks/`
- **Install Script**: Simplified hook copying to use entire hooks directory
- **Documentation**: Updated all paths in install output to use `~/.claude/hooks/`

### Added
- **Install Instructions**: Added RAG loop setup instructions (ENABLE_VECTOR_RAG, DATABASE_URL_MEMORY, etc.)

## [1.3.2] - 2025-10-04

### Changed
- **Hooks Location**: Moved all hooks from global ~/claude-hooks to versioned ~/.claude/hooks
- **settings.json**: Updated hook paths to use $HOME/.claude/hooks (repo-tracked)
- **RAG Loop**: Completed implementation with opt-in via ENABLE_VECTOR_RAG=true
- **Graceful Degradation**: RAG/ingest failures no longer block stop hook execution
- **Version Control**: All hooks now tracked in git for reproducibility

### Added
- **call_vector_bridge_mcp()**: MCP protocol integration for vector memory calls
- **get_rag_suggestions()**: Vector search functionality for DIGEST context
- **ingest_digest_to_vector()**: DIGEST ingestion to pgvector for future retrieval
- **Timeout Protection**: 10-second timeout on MCP subprocess calls
- **Debug Logging**: Comprehensive logging for RAG search and ingest operations

### Security
- **Opt-in RAG**: Disabled by default, requires explicit ENABLE_VECTOR_RAG=true
- **Environment Validation**: Requires DATABASE_URL_MEMORY, REDIS_URL, OPENAI_API_KEY

## [1.3.1] - 2025-10-04

### Added
- Main Agent DIGEST Policy
- pgvector Ingest Policy
- postgres-bridge and vector-bridge MCP servers

## [1.3.0] - 2025-10-04

### Added
- **Main Agent DIGEST Policy**: Main Agent now emits lightweight DIGESTs at decision points
- **pgvector Ingest Policy**: Comprehensive guidelines for curated, high-signal data ingestion
- **postgres-bridge MCP Server**: PostgreSQL query execution with schema caching (1-hour TTL)
- **vector-bridge MCP Server**: Global vector memory with pgvector, Redis caching, and fixpack automation
- **solution_preview tool**: Dry-run preview for fixpack application safety
- **WSI Timestamps**: Added `last_access` field to WSI items for better pruning
- **RAG Integration**: Stop hook now prepares RAG suggestions from DIGEST content

### Enhanced
- **Security**: Production gating for debug endpoints (DEBUG_SECRET requirement)
- **Stop Hook**: Enhanced with RAG query composition and timestamp tracking
- **Schema Caching**: postgres-bridge now caches schema queries for 1 hour
- **Embedding Model Policy**: Documented OpenAI text-embedding-3-small (1536-dim) as standard

### Fixed
- postgres-bridge EXPLAIN description (was misleading about ANALYZE)
- vector-bridge null project_root handling for global search
- MCP server registration in settings.json

### Documentation
- Added Main Agent DIGEST format and emission triggers
- Added pgvector ingest guardrails and monitoring targets
- Added embedding model standardization policy
- Added MCP server configuration examples

## [1.2.5] - 2025-10-03
- Initial npm release with core framework

