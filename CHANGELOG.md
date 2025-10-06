# Changelog

## [1.0.11] - 2025-10-05

### Fixed
- **Stop Hook Timeout**: Removed queue processing from `stop_digest.py` to prevent timeouts and cancellations during session end. All vector ingestion now deferred to launchd queue processor agent (runs every 15 minutes). Stop hook now completes in <1s.
- **CLAUDE.md Auto-Injection**: Added 10-minute modification window protection to `project_status.py` to prevent unwanted `<project_status>` section injection during manual edits.
- **CLAUDE.md Size**: Trimmed orchestration framework documentation from 55,368 to 39,331 characters (28.9% reduction) to meet 40k performance limit. Condensed verbose examples while preserving all critical functionality.
- **Type Safety**: Fixed mypy type error in `project_status.py` milestones assignment using `cast()`.

## [1.0.10] - 2025-10-05

### Added
- **Auto-create CLAUDE.md**: `auto_project_setup.py` now creates a default CLAUDE.md template for new projects
- **Project-Specific Instructions**: Each new project gets a template CLAUDE.md with sections for overview, development, architecture, and important notes

### Changed
- **Setup Script**: Updated to create CLAUDE.md alongside NOTES.md, .gitignore, and launchd agents

## [1.0.9] - 2025-10-05

### Changed
- **Comprehensive Permission Allow List**: Added explicit allow rules for all Claude Code tool types (Bash, Read, Write, Edit, MultiEdit, Grep, Glob, Task, NotebookEdit, TodoWrite, SlashCommand, KillShell, BashOutput, ExitPlanMode, WebFetch, WebSearch)
- **Settings Format**: Using bare tool names (e.g., `"Bash"`) to allow all commands of that type, following Claude Code schema requirements
- **Dual Strategy**: Combining `defaultMode: "bypassPermissions"` with explicit allow list for maximum compatibility across CLI and VS Code extension

### Fixed
- **VS Code Extension Prompts**: Should now work without permission popups by using the correct allow list format that the VS Code UI expects

## [1.0.8] - 2025-10-05

### Fixed
- **Permission Prompts**: Changed from `"allow": ["*"]` to `"defaultMode": "bypassPermissions"` (correct way to skip all prompts)
- **Settings Validation**: Fixed permission format to match Claude Code schema requirements

### Changed
- **Global Settings**: Updated to use `permissions.defaultMode: "bypassPermissions"` for true `--dangerously-skip-permissions` behavior
- **Local Settings**: vs-claude project now uses `defaultMode: "bypassPermissions"` instead of specific allow rules

## [1.0.7] - 2025-10-05

### Changed
- **Compaction Files Location**: Moved COMPACTION.md and compaction-summary.json to `.claude/logs/` for consistency
- **PreCompact Hook**: Updated `precompact_summary.py` to write compaction files to `.claude/logs/` instead of project root
- **Path Variables**: Renamed `LOGS_DIR_STR` → `CLAUDE_LOGS_DIR` for clarity in precompact_summary.py

### Migration
- Automatically moved existing compaction files from project root to `.claude/logs/` (vs-claude + global)

## [1.0.6] - 2025-10-05

### Fixed
- **NOTES.md Path**: Fixed `auto_project_setup.py` to create NOTES.md in `.claude/logs/` instead of project root (no more duplicates)
- **Vector Ingestion**: Added `ENABLE_VECTOR_RAG="true"` to Stop hook command so vector ingestion works by default
- **Template Format**: Updated NOTES.md template to match Stop hook format ("living state" header)

### Changed
- **NOTES_MD Path**: Changed from `PROJECT_ROOT / "NOTES.md"` to `LOGS_DIR / "NOTES.md"`
- **Stop Hook**: Now injects `ENABLE_VECTOR_RAG` environment variable alongside `WSI_PATH` and `LOGS_DIR`

## [1.0.5] - 2025-10-05

### Added
- **Allow All Commands**: Added `"permissions": { "allow": ["*"] }` to global settings
- **Orchestration Mode**: Framework now operates like `--dangerously-skip-permissions` by default

### Changed
- **Merge Script**: Updated to merge permissions from global settings into local settings
- **Auto-Setup Hook**: Now merges permissions along with hooks for new projects

## [1.0.4] - 2025-10-05

### Fixed
- **Auto-Hook Merging**: New `merge_global_hooks()` function automatically merges global hooks into project-local settings
- **Local Settings Override**: Fixed issue where `.claude/settings.local.json` prevented hooks (Stop, PreToolUse, etc.) from running
- **DIGEST Capture**: Projects with custom local settings now properly capture DIGESTs and queue for vector ingestion

### Changed
- **Auto-Setup Hook**: Now automatically merges global hooks into local settings when detected
- **Merge Script**: Created standalone `merge-local-settings.py` for manual hook merging when needed

## [1.0.3] - 2025-10-05

### Added
- **Reference Copies**: Launchd plists now copied to `.claude/launchd/` for documentation
- **Project README**: Auto-generated README.md in `.claude/launchd/` with management commands

### Fixed
- **Agent Location Clarity**: Clarified that actual agents in `~/Library/LaunchAgents/`, reference copies in project

## [1.0.2] - 2025-10-05

### Fixed
- **Queue Processor Auto-Start**: Changed `RunAtLoad` from `false` to `true` for queue processor
- **Persistence**: Both agents now auto-start on login/boot

### Added
- **Background Items Helper**: Created `identify-background-items.sh` to explain macOS background items

## [1.0.1] - 2025-10-05

### Added
- **Human-Readable Agent Names**: Launchd agents now include git repo name in label
- **Project Name Extraction**: New `get_project_name()` function extracts repo name from git remote
- **List Helper**: Created `list-launchd-agents.sh` to display all agents with project info

### Changed
- **Agent Naming Format**: `com.claude.agents.{type}.{project-name}.{hash}.plist`
- Example: `com.claude.agents.queue.vs-claude.2f665867.plist`

## [1.0.0] - 2025-10-05

### Added
- **Scoped Package**: Initial publish as `@servesys-labs/claude-agents`
- **Per-Project Launchd Agents**: Automatic background vector ingestion per project
- **Queue Processor**: Processes `.claude/ingest-queue/*.json` every 15 minutes
- **Status Updater**: Updates project-claude.md every 5 minutes

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

