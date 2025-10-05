# Claude Code Orchestration Framework

**Production-ready orchestration with Vector RAG Memory**

**Version**: 1.4.0 | **[📖 Quick Start →](QUICK_START.md)** | **[⚡ 5-Minute Setup](#5-minute-setup-with-vector-rag)**

---

## 🎯 The Killer Feature: Vector RAG Memory

**Claude remembers everything across sessions.** Your agents build institutional knowledge.

```
You: "Add authentication to the API"
Agent: Searches past work → Finds "We use JWT with refresh tokens (users.service.ts)"
       ↓
Agent: Implements auth matching your existing patterns (no reinventing the wheel)
```

**How it works:**
1. 📝 Subagents return structured DIGEST blocks (decisions, files changed, contracts)
2. 💾 DIGEST auto-stored in pgvector/Supabase/Pinecone (your choice)
3. 🔍 New tasks → RAG search suggests relevant past work
4. ✨ Agents build on what you already have (coherent codebase, no drift)

**Supported Backends (drop-in):**
- ✅ **pgvector** (PostgreSQL + pgvector extension) - Self-hosted, free
- ✅ **Supabase** (Managed pgvector) - Just add SUPABASE_URL + SUPABASE_KEY
- ✅ **Pinecone** (Managed vector DB) - Just add PINECONE_API_KEY

**Zero vector DB knowledge required.** Just paste an API key and go.

---

## 🚀 New in v1.4.0 - Zero Configuration!
- **Automatic Per-Project Setup**: First use auto-creates `.claude/logs/`, updates `.gitignore`, creates `NOTES.md`
- **Zero Manual Work**: Just install globally once, then use Claude Code in any project
- **Smart Detection**: Auto-detects projects (git repos, package.json, pyproject.toml, etc.)
- **Runs Once**: Creates `.claude/.setup_complete` marker to skip future setup
- **Vector RAG Ready**: Auto-configures memory ingestion and retrieval hooks

## What's Included

### 🎯 Vector RAG Memory System (The Star Feature)
- **Auto-Ingestion**: Every DIGEST block automatically stored in vector DB
- **Smart Retrieval**: RAG search suggests relevant past work on every new task
- **Multi-Backend**: Drop-in support for Supabase, Pinecone, or self-hosted pgvector
- **Zero Config**: Just set environment variables - framework handles the rest
- **Cross-Project Memory**: Search across all your projects (global knowledge base)
- **Privacy First**: Self-hosted option (pgvector) keeps your data on your infrastructure

### Core Components
- **40+ Specialized Agents**: Implementation planner, requirements clarifier, code navigator, implementation engineer, test author, security auditor, and more
- **DIGEST-Based Context**: Structured JSON summaries (not giant transcript dumps)
- **12+ Automation Hooks**: Pre/Post tool use hooks for validation, cost tracking, DIGEST capture, and quality gates
- **Pivot Tracking System**: Detect direction changes, validate FEATURE_MAP updates, auto-audit obsolete code
- **Multi-Model Brainstorming**: Claude + GPT-5 dialogue for strategic planning
- **Cost Tracking**: Automatic cost display for OpenAI and Perplexity API calls
- **Pre-Merge Quality Gate**: Bash script for comprehensive pre-merge validation
- **MD Spam Prevention**: Enforces documentation policy to prevent file sprawl

### Hook Scripts (`hooks/`)
- `pretooluse_validate.py` - Validate permissions, check budgets
- `posttooluse_validate.py` - Lint/typecheck after edits
- `checkpoint_manager.py` - Auto-checkpoint before risky operations
- `pivot_detector.py` - Detect direction changes
- `feature_map_validator.py` - Validate FEATURE_MAP updates
- `log_analyzer.py` - Suggest specialized agents
- `task_digest_capture.py` - Capture subagent DIGEST blocks
- `precompact_summary.py` - Generate compaction summaries
- `gpt5_cost_tracker.py` - Track OpenAI API costs
- `perplexity_tracker.py` - Track Perplexity API costs
- `md_spam_preventer.py` - Prevent documentation sprawl
- `ready-to-merge.sh` - Pre-merge quality gate script

### Agent Definitions (`agents/`)
All 40+ specialized agent definitions for routing and delegation.

### Configuration
- `CLAUDE.md` - Global orchestration instructions
- `settings.json` - Hook registrations
- `FEATURE_MAP.template.md` - Project template

### MCP Servers (Optional)
- `openai-bridge` - Multi-model brainstorming with GPT-5
- `postgres-bridge` - Read-only database queries with AI-generated SQL
- `vector-bridge` - **Vector RAG memory** (pgvector/Supabase/Pinecone backends)

---

## 5-Minute Setup with Vector RAG

### Option 1: Supabase (Easiest - Managed, Free Tier)

```bash
# 1. Install framework
npm install -g claude-orchestration-framework
bash ~/.npm-global/lib/node_modules/claude-orchestration-framework/install.sh

# 2. Create Supabase project at https://supabase.com (free tier)
#    Enable pgvector extension in Database → Extensions

# 3. Add to ~/.zshrc or ~/.bashrc (or use .envrc with direnv)
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_KEY="your-service-role-key"
export ENABLE_VECTOR_RAG=true

# 4. Reload shell
source ~/.zshrc

# 5. Done! Open Claude Code in any project - RAG memory is active
```

**Get your keys:**
- SUPABASE_URL: Project Settings → API → Project URL
- SUPABASE_SERVICE_KEY: Project Settings → API → service_role key (keep secret!)

### Option 2: Pinecone (Serverless, Simple API)

```bash
# 1. Install framework (same as above)
npm install -g claude-orchestration-framework
bash ~/.npm-global/lib/node_modules/claude-orchestration-framework/install.sh

# 2. Create Pinecone index at https://www.pinecone.io (free tier)
#    Index name: "claude-memory"
#    Dimensions: 1536 (OpenAI embeddings)
#    Metric: cosine

# 3. Add to ~/.zshrc or ~/.bashrc
export PINECONE_API_KEY="your-api-key"
export PINECONE_INDEX="claude-memory"
export ENABLE_VECTOR_RAG=true

# 4. Reload and go
source ~/.zshrc
```

**Get your API key:**
- Pinecone Dashboard → API Keys → Create Key

### Option 3: Self-Hosted pgvector (Full Control)

```bash
# 1. Install framework (same as above)

# 2. Set up PostgreSQL with pgvector
docker run -d \
  -e POSTGRES_PASSWORD=yourpassword \
  -e POSTGRES_DB=claude_memory \
  -p 5432:5432 \
  ankane/pgvector

# 3. Add to ~/.zshrc or ~/.bashrc
export DATABASE_URL_MEMORY="postgresql://postgres:yourpassword@localhost:5432/claude_memory"
export ENABLE_VECTOR_RAG=true

# 4. Reload
source ~/.zshrc
```

### Verify RAG is Working

```bash
# In any project, run a task with subagent
# Example: Ask Claude to "implement user authentication"
# After task completes, check NOTES.md - you'll see DIGEST blocks
cat NOTES.md

# Future sessions will reference past work automatically!
```

---

## Installation

### NPM Installation (Recommended)

**Linux/macOS:**
```bash
npm install -g claude-orchestration-framework
bash ~/.npm-global/lib/node_modules/claude-orchestration-framework/install.sh
```

**Windows (PowerShell):**
```powershell
npm install -g claude-orchestration-framework
powershell -ExecutionPolicy Bypass -File "$env:APPDATA\npm\node_modules\claude-orchestration-framework\install.ps1"
```

### What the Installer Does
1. **Backs up** existing installation (if any)
2. **Installs hooks** to `~/.claude/hooks/` (version-controlled)
3. **Installs agents** to `~/.claude/agents/`
4. **Configures** settings.json (with merge option)
5. **Sets up** environment variables
6. **Optionally installs** MCP servers (postgres-bridge, vector-bridge, openai-bridge)

### Manual Installation
If you prefer manual installation:

**Linux/macOS:**
1. Clone or download the package
2. Run: `bash install.sh`

**Windows:**
1. Clone or download the package
2. Run: `powershell -ExecutionPolicy Bypass -File install.ps1`

## Post-Installation

### 1. Validate Installation

**Quick automated check:**
```bash
bash smoke-test.sh
```

**Comprehensive validation:**
See [INSTALLATION_VALIDATION.md](INSTALLATION_VALIDATION.md) for detailed checklist and smoke tests.

### 2. Set Up API Keys (Optional)
For multi-model brainstorming and live data searches:

```bash
export OPENAI_API_KEY='sk-...'
export PERPLEXITY_API_KEY='pplx-...'
```

### 2. Enable RAG Loop (Optional)
For vector memory and DIGEST ingestion:

**Linux/macOS:**
```bash
export ENABLE_VECTOR_RAG=true
export DATABASE_URL_MEMORY='postgresql://user:pass@host:port/database'
export REDIS_URL='redis://host:port'
```

**Windows:**
```powershell
$env:ENABLE_VECTOR_RAG = 'true'
$env:DATABASE_URL_MEMORY = 'postgresql://user:pass@host:port/database'
$env:REDIS_URL = 'redis://host:port'
```

### 3. Create FEATURE_MAP.md in Your Project

**Linux/macOS:**
```bash
cd ~/your-project
cp ~/.claude/FEATURE_MAP.template.md FEATURE_MAP.md
```

**Windows:**
```powershell
cd C:\your-project
Copy-Item "$env:USERPROFILE\.claude\FEATURE_MAP.template.md" ".\FEATURE_MAP.md"
```

Edit FEATURE_MAP.md to track your project's features and pivots.

### 4. Test the Installation

**Linux/macOS:**
```bash
# Check hooks are working
python3 ~/.claude/hooks/checkpoint_manager.py list

# Run pre-merge check
cd ~/your-project
bash ~/.claude/hooks/ready-to-merge.sh
```

**Windows:**
```powershell
# Check hooks are working
python "$env:USERPROFILE\.claude\hooks\checkpoint_manager.py" list

# Run pre-merge check (requires Git Bash or WSL)
cd C:\your-project
bash "$env:USERPROFILE\.claude\hooks\ready-to-merge.sh"
```

## Usage

### Main Agent Routing
The Main Agent automatically routes tasks to specialized subagents:
- Complex features → Implementation Planner
- Vague requests → Requirements Clarifier
- Code changes → Code Navigator + Implementation Engineer
- Testing → Test Author
- Security → Security Auditor
- Performance → Performance Optimizer

### Pivot Workflow
1. Change direction: "Actually, let's use Railway instead of Supabase"
2. Hook detects pivot, shows warning
3. Update FEATURE_MAP.md manually
4. Say: "I've updated FEATURE_MAP. Run the pivot cleanup workflow."
5. Main Agent auto-invokes Relevance Auditor → Auto-Doc Updater

### Pre-Merge Quality Gate
```bash
cd ~/your-project
bash ~/claude-hooks/ready-to-merge.sh

# With auto-fix for linting
bash ~/claude-hooks/ready-to-merge.sh --auto-fix
```

### Multi-Model Brainstorming
Say "brainstorm alternatives" or mention comparing approaches.
Main Agent will invoke Multi-Model Brainstormer (Claude + GPT-5 dialogue).

### Checkpoint Management
```bash
# List checkpoints
python3 ~/claude-hooks/checkpoint_manager.py list

# Restore a checkpoint
python3 ~/claude-hooks/checkpoint_manager.py restore <checkpoint-id>
```

## Features

### Automatic Hooks
- **PreToolUse**: Permission validation, budget checks
- **PostToolUse**: Lint/typecheck after edits, cost tracking, DIGEST capture
- **UserPromptSubmit**: Agent suggestions, pivot detection, FEATURE_MAP validation
- **PreCompact**: Generate summary before compaction
- **Stop**: Extract final DIGEST (fallback)

### Pivot Tracking (4 Layers)
1. **FEATURE_MAP.md** - Single source of truth
2. **pivot_detector.py** - Auto-detect direction changes
3. **Relevance Auditor** - Find obsolete code
4. **Auto-Doc Updater** - Sync all documentation

### Cost Tracking
Automatically displays costs for:
- OpenAI API calls (GPT-5, GPT-4o, etc.)
- Perplexity API calls (sonar, sonar-pro, sonar-reasoning)

### Quality Gates
- Pre-merge validation (lint, typecheck, tests, build)
- Integration cohesion audits
- Production readiness verification

## Documentation

- **Global Config**: `~/.claude/CLAUDE.md`
- **Agent Roster**: `~/.claude/agents/*.md`
- **Hook Scripts**: `~/.claude/hooks/*.py`
- **Project Template**: `~/.claude/FEATURE_MAP.template.md`
- **Logs Migration**: See [LOGS_MIGRATION.md](LOGS_MIGRATION.md) for per-project log configuration

## Troubleshooting

### Hooks Not Running
1. Check `~/.claude/settings.json` has hook registrations
2. Verify scripts are executable: `chmod +x ~/claude-hooks/*.py`
3. Check Python version: `python3 --version` (need 3.8+)

### MCP Servers Not Working
1. Rebuild: `cd ~/.claude/mcp-servers/openai-bridge && npm install && npm run build`
2. Check API keys are set in environment
3. Restart Claude Code

### DIGEST Blocks Not Captured
1. Check NOTES.md exists in project root
2. Verify task_digest_capture.py hook is registered
3. Run subagents via Task tool (not direct work)

## Updating

To update to a new version:
1. Download new package
2. Run `bash install.sh` (will backup existing)
3. Review changes in `~/.claude/settings.json.backup`

## Uninstalling

```bash
rm -rf ~/claude-hooks
rm -rf ~/.claude/agents
# Manually remove hook registrations from ~/.claude/settings.json
# Manually remove CLAUDE.md from ~/.claude/
```

## Support

For issues or questions:
- Check documentation in `~/.claude/CLAUDE.md`
- Review agent definitions in `~/.claude/agents/`
- Check hook debug logs in `~/claude-hooks/logs/`

## Version History

### 1.0.0 (October 2025)
- Initial release
- 40+ agents
- 12+ hooks
- Pivot tracking system
- Multi-model brainstorming
- Cost tracking
- Pre-merge quality gates

## License

[Your License Here]

---

**Happy Coding! 🚀**
