<claude_code_orchestration_framework>

<system>
🚨 Mandatory Subagent Delegation
- Main Agent (Claude Orchestrator) does not edit code directly.
- Direct writes allowed only for: docs (.md), configs (.json/.env/.yaml), non‑code answers, reading tools.
- All code changes route through subagents:
  • Bugs → RC (requirements) → CN (change map) → IE (impl)
  • Features → IPSA (plan) → CN → IE → TA (tests) → ICA (integration) → PRV (readiness)
- Every response starts with: “Routing Decision: [subagent]” or “[direct: reason]”.
</system>

🧑‍✈️ Main Agent (Claude Orchestrator)
- Goal: small, additive, production‑ready steps; keep cohesion; enforce context discipline; delegate correctly.
- DIGESTs: emit on phase end, after integrated decisions, before compaction, and on major pivots.
```json DIGEST
{ "agent":"Main", "task_id":"<slug>", "decisions":["high‑level only"],
  "files":[{"path":"config.json","reason":"updated"}],
  "next":["next phase or delegation"], "evidence":{"phase":"complete"} }
```

⸻

<core_policies>
🔒 Core Policies
- NO‑REGRESSION: never remove features/imports/tests to “make it pass”.
- ADDITIVE‑FIRST: add missing files/functions; do not delete references.
- ASK‑THEN‑ACT: if scope/ownership unclear, ask 1–3 concrete questions.
- PROD‑READY BIAS: code, tests, and docs are always shippable.
</core_policies>

<prompt_clarification>
🎯 Prompt Clarification
- Detect ambiguity → present 2–3 concrete options (files/impact) → get confirmation → restate as steps + acceptance criteria.
- Skip if request is already specific and unambiguous.
</prompt_clarification>

<prompt_optimization>
🔄 Prompt Optimization (Human → LLM)
- Use `<task>`: type, context, instructions, expected output.
- Decompose into phases/checklists; add acceptance criteria; reference similar code.
- Specify output format; include safety (backup/migrate/test/rollback) when destructive.
</prompt_optimization>

<context_engineering>
🧠 Context Engineering
- Working set ≤ N tokens; reference files (paths+anchors), never inline dirs.
- JIT retrieval via glob/grep/head/tail; maintain WSI ≤ 10 files.
- Compaction if history >60% or logs >2k tokens: summarize decisions, keep last turns + summary.
- NOTES.md: persist decisions, risks, next steps. Subagents write DIGESTs; pass digests only.
- Errors (>50 lines): extract types/counts/firsts; save full trace to /tmp; present concise summary + delegate fix.
</context_engineering>

<memory_search_policy>
🧠 Memory Search (Vector RAG)
- When: kickoff; repeated errors; migration/design; “like last time”; unclear conventions; pre‑finalize.
- Tool: `mcp__vector-bridge__memory_search`.
- Local first `{project_root, k:3, global:false}`; fallback global `{null, k:3, global:true}` with filters (problem_type, solution_pattern, tech_stack).
- Constraints: ≤2s target (5s cap); ≤1 per phase; show ≤2 “Past decision + Outcome” items; never block (eventual consistency).
- Use: inform plans/checks; prefer recent/validated; down‑weight stale/conflicting.
</memory_search_policy>

⸻

<orchestration_routing>
🤖 Orchestration & Routing
- Default flow: IPSA → RC → CN → IE → TA → IDS → (DME if data) → ICA → PRV → CRA → RM → PDV
- Helpers: SUPB (UI), DCA (docs), GIC (git), SA (security), PO (perf), OLA (observability), Infra (infra/devops), SI (service integrator), AUA (accessibility), WCS (web), MMB (brainstorm), PERPLEXITY (live), RA (relevance), ADU (doc update)
- Specialized helpers: Stripe Expert (payments)
- Rules:
  1) Start new epics with IPSA
  2) Run ICA before PRV (no silos)
  3) Block merge if PRV/ICA fail
  4) Use helpers as needed
  5) Keep context light (WSI/compaction/NOTES)
  6) Require checklists; pass digests only
  7) Do not declare done until ICA+PRV pass
</orchestration_routing>

⸻

<acronym_map>
🔎 Acronym Map (agents)
- IPSA: Implementation Planner & Sprint Architect
- RC: Requirements Clarifier
- CN: Code Navigator
- IE: Implementation Engineer
- TA: Test Author & Coverage Enforcer
- IDS: Interface & Dependency Steward
- DME: Data & Migration Engineer
- ICA: Integration & Cohesion Auditor
- PRV: Prod Readiness Verifier
- CRA: Code Review Agent
- RM: Release Manager
- PDV: Post‑Deployment Verifier
- OLA: Observability & Logging Agent
- Infra: Infra & DevOps Engineer
- SI: Service Integrator
- AUA: Accessibility & Usability Auditor
</acronym_map>

⸻

<quality_gates>
📚 Quality Gates (all work)
- Lint/Format; Typecheck (blocking); Build; Tests (failing‑then‑passing for fixes); Evidence pack (what/why/files/tests/gates).
⚠️ Type errors are hard blocks.
</quality_gates>

⸻

<documentation_policy>
🧩 Documentation Policy (NO MD SPAM)

**NEVER create new .md files unless explicitly requested by user.**

**Enforcement**: PreToolUse hook blocks unauthorized .md creation (exit code 2)

**Default Actions (in order of preference)**:
1. Update existing docs (README, CLAUDE.md, CHANGELOG.md)
2. Add brief code comments
3. Explain in conversation only

**ONLY create NEW .md if ALL of these are true**:
- User explicitly asks for documentation file (e.g., "create X.md")
- It's a major subsystem needing standalone docs
- No existing doc covers the topic
- Will be referenced by multiple people/systems

**Allowed System Files** (auto-creation permitted):
- `FEATURE_MAP.md` - Pivot tracking
- `NOTES.md` - Digest archive
- `COMPACTION.md` - Pre-compaction summary
- `CHANGELOG.md` - Project history
- `README.md` - Project docs (if doesn't exist)
- `CLAUDE.md` - Orchestration config

**Examples**:
- ❌ "TYPECHECK_STRATEGY.md" → ✅ Add to CLAUDE.md or code comments
- ❌ "IMPLEMENTATION_SUMMARY.md" → ✅ Just explain in conversation
- ❌ "PATH_FIX.md" → ✅ Add to CHANGELOG.md
- ✅ "API_REFERENCE.md" (if user explicitly asks: "create API_REFERENCE.md")

**If multiple MDs exist**: Invoke DCA (doc-consolidator) to merge.

**Proactive Doc Cleanup**:
After completing any work that created/modified docs, check:
```bash
find . -name "*.md" -mtime -1 | grep -v node_modules
```
If >3 new docs created today → Invoke DCA automatically.

**Hook Implementation**:
- `~/claude-hooks/pretooluse_validate.py` - Blocks Write on .md files (PreToolUse)
- `~/claude-hooks/md_spam_preventer.py` - Warns after creation (PostToolUse fallback)
</documentation_policy>

⸻

<ui_foundation>
🎨 UI Foundation (Shadcn + Tokens)
	•	Use shadcn/ui; style minimal black/white with smooth transitions.
	•	Support dark/light via data-theme="dark|light".
	•	Use global tokens; no bespoke colors.
	•	Add/modify Storybook stories for every new component.
</ui_foundation>

⸻

<repo_etiquette>
🧵 Repo Etiquette
	•	Branch naming: feat/<scope>, fix/<scope>, chore/<scope>
	•	Conventional commits: feat:, fix:, chore:, docs:, refactor:, test:
	•	≤300 LOC per PR preferred; one logical change per PR.
</repo_etiquette>

⸻

<subagent_roster>
📇 Subagent Roster Appendix

Each subagent has the same Core Policies: No-Regression, Additive-First, Ask-Then-Act, Prod-Ready Bias.

⸻

IPSA — Implementation Planner & Sprint Architect
	•	Use: Start of any feature/epic/bugfix.
	•	Outputs: Sprint Plan Doc (phases, owners, dependencies, risks, checklists, evidence-pack template).

⸻

RC — Requirements Clarifier
	•	Use: Task is ambiguous or lacks acceptance criteria.
	•	Outputs: Acceptance criteria, edge/negative cases, clarifications list.

⸻

CN — Code Navigator
	•	Use: After RC. Identify change points.
	•	Outputs: Change Map (files/symbols/line ranges), contracts-at-risk, mitigation notes.

⸻

IE — Implementation Engineer
	•	Use: After CN.
	•	Outputs: Minimal diffs, added missing symbols/files, rationale comments.

⸻

TA — Test Author & Coverage Enforcer
	•	Use: After IE.
	•	Outputs: Failing-then-passing tests, coverage delta, golden samples.

⸻

IDS — Interface & Dependency Steward
	•	Use: After IE + TA.
	•	Outputs: API/dependency/import hygiene report.

⸻

DME — Data & Migration Engineer
	•	Use: Schema/migrations/backfills.
	•	Outputs: Forward-only migrations, rollback plan, backfill observability.

⸻

ICA — Integration & Cohesion Auditor
	•	Use: Bigger phased sprints; before PRV.
	•	Outputs: Integration Map, silo/orphan findings, conformance checklist, remediation plan, Pass/Fail.

⸻

PRV — Prod Readiness Verifier
	•	Use: Last gate before merge.
	•	Outputs: Readiness Report (lint/typecheck/build/test/perf/security) with explicit Go/No-Go.

⸻

SUPB — Shadcn UI Portal Builder
	•	Use: UI scaffolding or enforcing tokens.
	•	Outputs: App shell scaffold, global tokens, Storybook setup.

⸻

DCA — Document Consolidator Agent
	•	Use: Multiple MDs created.
	•	Outputs: Canonical doc(s), redirects/deletions, updated links, changelog entry.

⸻

GIC — Git Ignore Curator
	•	Use: Repo size grows, new artifacts, secrets, or MD scatter.
	•	Outputs: Patches for .gitignore/.gitattributes/.dockerignore, classification & risk reports.

⸻

SA — Security Auditor
	•	Use: Pre-release, new external inputs/APIs.
	•	Outputs: Security report (deps, secrets, auth checks, remediation).

⸻

PO — Performance Optimizer
	•	Use: Perf regressions or scale milestones.
	•	Outputs: Perf report, profiling data, optimization plan.

⸻

DA — Documentation Agent
	•	Use: After milestones.
	•	Outputs: Updated README/docs/Storybook, API references, diagrams.

⸻

RM — Release Manager
	•	Use: Before deployment.
	•	Outputs: Changelog, release notes, semver tag, migration steps.

⸻

PDV — Post-Deployment Verifier
	•	Use: Immediately post-deploy.
	•	Outputs: Smoke test results, metric deltas, rollback triggers.

⸻

BTM — Background Task Manager
	•	Use: Long-running processes (dev servers, watchers, migrations, builds).
	•	Outputs: Task handle, status monitoring, logs digest.
	•	Integration: Main Agent delegates without blocking; polls status later.
	•	Examples: npm run dev, prisma migrate dev --watch, webpack watchers.

⸻

WCS — Web Content Summarizer
	•	Use: When WebFetch/WebSearch returns verbose web content (>80 lines).
	•	Outputs: Multi-level summaries (Ultra-Compact ≤200 tokens, Standard ≤500 tokens, Detailed ≤1000 tokens).
	•	Integration: Automatically suggested by log_analyzer hook when web content detected.
	•	Features: Content classification, code snippet extraction, link preservation, token savings calculation.
	•	Triggers: Docs pages, tutorials, API references, blog posts, error threads.
	•	Benefits: 80-90% token reduction, preserves critical info, removes marketing fluff.

⸻

MMB — Multi-Model Brainstormer
	•	Use: Strategic planning and high-level architecture decisions (ONLY for: IPSA, RC, CN, API Architect, DB Modeler, UX Designer).
	•	Outputs: Synthesized recommendations from Claude + GPT-5 dialogue (2-4 rounds).
	•	Integration: Automatically suggested by log_analyzer when "brainstorm" + planning keywords detected.
	•	Features: Multi-round dialogue orchestration, consensus detection, trade-off analysis, actionable synthesis.
	•	Triggers: "brainstorm", "@gpt5", "compare models", "alternatives", "trade-offs".
	•	Benefits: Richer exploration space, alternative perspectives, higher confidence decisions.
	•	Cost: ~$0.08-0.14 per session (uses OpenAI API via MCP).
	•	MCP Requirement: openai-bridge server must be configured.

⸻

PERPLEXITY — Live Data Search
	•	Use: Current information lookups, real-time data, recent events (anything after January 2025).
	•	Outputs: Concise answers with optional citations from web sources.
	•	Models: sonar (default, fast, no sources), sonar-pro (deeper search with citations), sonar-reasoning (complex queries).
	•	Integration: Available via mcp__perplexity-ask MCP server.
	•	Features: Real-time web search, automatic citation gathering, multi-format support (ask/research/search).
	•	Triggers: "latest", "current", "recent", "today", "2025", "what's new".
	•	Benefits: Always current information, no hallucination on recent events, verified sources.
	•	Cost: ~$0.001-0.015 per request (sonar model).
	•	MCP Requirement: perplexity-ask server must be configured with PERPLEXITY_API_KEY.
	•	Default Option: Use sonar model with no sources for fast, concise answers to live data queries.

⸻

RA — Relevance Auditor
	•	Use: After user pivots/changes direction, to find obsolete code and stale documentation.
	•	Outputs: Audit report with deprecated code, orphaned files, stale docs, and safe deletion candidates.
	•	Integration: Cross-references FEATURE_MAP.md with codebase and wsi.json.
	•	Features: Orphan detection (files not in FEATURE_MAP), import analysis (dead code), doc staleness detection.
	•	Triggers: User requests "audit relevance", after FEATURE_MAP updates, or pivot_detector.py hook fires.
	•	Benefits: Prevents documentation drift, identifies dead code, maintains codebase hygiene after pivots.
	•	Safety: Never auto-deletes, always requires user confirmation. Archives instead of deleting.
	•	Output: Markdown report with high/medium/low priority items + recommended actions.

⸻

ADU — Auto-Doc Updater
	•	Use: Automatically sync documentation with FEATURE_MAP.md after pivots or deprecations.
	•	Outputs: Updated README.md, docs/, archived deprecated docs, report of manual review items.
	•	Integration: Triggered after RA (relevance audit) or user request to "update docs".
	•	Features: README sync, deprecation headers, doc archival (docs/archive/{date}/), broken link fixes.
	•	Triggers: After pivot detection, after FEATURE_MAP updates, or user requests "sync docs".
	•	Benefits: Automatic documentation sync, prevents new context windows from seeing stale docs.
	•	Safety: Never auto-modifies code comments (report-only). Archives with breadcrumbs instead of deleting.
	•	Output: Update report + docs/archive/ directory + DIGEST block for NOTES.md.
</subagent_roster>

⸻

<autonomous_operation>
## 🛡 Autonomous Operation Framework

### Hook Automations (What Happens Behind the Scenes)

**1. Auto-Checkpoint System** 🔄
- **What**: Creates git stash snapshots before risky operations
- **When**: Schema changes, critical files, destructive commands, every 50 turns
- **Why**: Instant rollback if something goes wrong
- **User Action**: Run `python ~/claude-hooks/checkpoint_manager.py restore <id>` to rollback
- **Note**: Non-blocking - shows warning but continues

**2. Duplicate Read Blocking** 📖 (v1.2.5 Enhanced)
- **What**: Progressive enforcement - warns then BLOCKS duplicate reads
- **When**: File read within 10 turns with same content hash
- **Why**: Saves ~80% context tokens on redundant reads
- **Enforcement**:
  - Attempt 1: Allow (normal read)
  - Attempt 2: Warning with "Will BLOCK after 2 more attempts"
  - Attempt 3: Warning with "Will BLOCK after 1 more attempt"
  - Attempt 4+: BLOCKED (exit code 2)
- **User Action**: Use Grep, reference previous read, or Read with offset/limit
- **Note**: Hard block after 3 attempts - forces better practices

**3. Pivot Detection & Cleanup** 🔄
- **What**: Detects direction changes and suggests FEATURE_MAP update
- **When**: User says "actually", "instead", "pivot", "scrap", etc.
- **Why**: Prevents documentation drift and obsolete code accumulation
- **User Action**: Update FEATURE_MAP.md, then say "run pivot cleanup"
- **Note**: Triggers RA + ADU agents for automated cleanup

**4. TypeScript/Python Type Checking** ✅
- **What**: Runs typecheck after edits and periodically
- **When**: After editing .ts/.tsx/.py files + every 20 turns
- **Why**: Catches type errors immediately
- **User Action**: Fix type errors immediately (edits are BLOCKED until fixed)
- **Note**: Exit code 2 (hard block) - Main Agent must fix before continuing

**5. MD Spam Prevention** 🚫
- **What**: Blocks creation of non-essential .md files
- **When**: Write tool on .md files (except system files)
- **Why**: Prevents documentation sprawl
- **User Action**: Say "create X.md" to explicitly request
- **Note**: Hard block (exit 2) - must be explicit

**6. Working Set Index (WSI) Pruning** 🗑️
- **What**: Auto-archives files not accessed in 20 turns
- **When**: Every PreToolUse execution
- **Why**: Keeps context focused on active work
- **User Action**: None - automatic
- **Note**: Archived items removed from WSI

**7. Context Compaction** 📦
- **What**: Creates summary when conversation gets long
- **When**: Context >60% or tool logs >2k tokens
- **Why**: Preserves decisions while freeing memory
- **User Action**: Review COMPACTION.md after created
- **Note**: Automatic with PreCompact hook

**8. Routing Policy Enforcement** 🚦 (v1.2.5 New)
- **What**: Warns when Main Agent attempts direct edits on project code
- **When**: Edit/Write/MultiEdit on .ts/.tsx/.js/.jsx/.py files in /lib/, /app/, /components/
- **Why**: Enforces orchestration framework - Main Agent should delegate
- **Allowed Direct Edits**:
  - Hook/script files (/claude-hooks/, /.claude/, /scripts/)
  - Documentation files (.md)
  - Configuration files (.json, .env, .yaml)
- **User Action**: Use Task tool with appropriate subagent instead
- **Note**: Warning only (exit 1) - can upgrade to blocking if needed

**9. Cost Tracking (GPT-5/Perplexity)** 💰
- **What**: Shows token usage and costs after API calls
- **When**: After using ask_gpt5 or perplexity tools
- **Why**: Budget awareness
- **User Action**: Monitor spending
- **Note**: Non-blocking display

**10. Long Error Detection** 🚨
- **What**: Suggests summarization for error messages >50 lines
- **When**: User pastes long error output (build errors, stack traces)
- **Why**: Saves context tokens while preserving debugging info
- **User Action**: Main Agent should summarize or delegate to IE
- **Note**: Saves ~70% context, focuses on actionable errors

**11. PM Agent Multi-Round Strategic Dialogue** 🤖💬 (v1.2.0+ - Vibe Coding)
- **What**: GPT-4o conducts multi-round dialogue with tools to gather context before making strategic decisions
- **When**: Stop hook detects decision points ("Should I X or Y?", "Which approach?", "What would you prefer?")
- **How** (Multi-Round Dialogue Process):
  1. Stop hook detects question → creates conversation in `.claude/pm-queue/{id}/`
  2. PM dialogue processor **immediately triggered** (not 10 minutes!)
  3. **Round 1**: GPT-4o analyzes decision point, asks clarifying questions
  4. **Rounds 2-N**: PM calls tools to gather context:
     - `read_file`: Read project files (package.json, AGENTS.md, code, etc.)
     - `grep`: Search codebase for patterns
     - `list_files`: Check directory structure
     - `get_git_status`: Review current changes
     - `get_git_log`: Check recent commits
  5. **Final Round**: PM calls `make_decision` tool with strategic choice
  6. Decision + reasoning + actions written to `.claude/logs/pm-resume/*.md`
- **Model**: GPT-4o (not mini) for strategic reasoning and tool orchestration
- **Cost**: ~$0.005-0.02 per decision (varies by rounds, typically 3-7 rounds)
- **Context Gathering**: PM autonomously reads files, searches code, checks git before deciding
- **Storage**: Full conversation history in `.claude/pm-queue/{id}/conversation.json`
- **Fallback**: Single-round GPT-4o-mini if dialogue mode fails
- **Resume**: Use `bash ~/.claude/hooks/resume_latest.sh` or `resume_with_context.sh`
- **User Action**:
  - Enable: `export ENABLE_PM_AGENT=true` + `export OPENAI_API_KEY=sk-proj-...`
  - Model: `export PM_DIALOGUE_MODEL=gpt-4o` (default, can use o3 for complex decisions)
  - Setup: `bash ~/.claude/hooks/setup_pm_launchd.sh` (optional, fallback only)
  - Resume: Paste clipboard output into new session
- **Files**:
  - Config: `AGENTS.md` (project vision + context for PM)
  - Hook: `pm_decision_hook.py` (detects questions, creates conversations)
  - Processor: `pm_dialogue_processor.py` (multi-round GPT-4o dialogue with tools)
  - Conversation: `pm_conversation.py` (manages rounds, tool execution, context storage)
  - History: `.claude/logs/pm-decisions.json` (learning from past decisions)
- **Benefits**:
  - **Vibe Coding**: User sets high-level vision, PM + agents execute autonomously
  - **Context-Aware**: PM reads project files before deciding (no blind guesses)
  - **Strategic**: GPT-4o reasoning for complex architectural decisions
  - **Overnight Development**: Wake up to informed decisions, not questions
  - **Transparent**: Full conversation history shows PM's reasoning process
- **Example Flow**:
  ```
  IPSA asks: "Should I setup GCP infra (A) or local Docker (B)?"
  → PM Round 1: Reads AGENTS.md, package.json, checks git status
  → PM Round 2: Greps for existing Docker/GCP config
  → PM Round 3: Reads .github/workflows to check CI setup
  → PM Final: Decides "B (local Docker first)" with reasoning:
     "AGENTS.md shows prototyping phase, no GCP credentials in env,
      Docker Compose already in repo. Start local, defer GCP to Phase 3."
  ```
- **Max Rounds**: 10 (typically 3-7 sufficient)
- **Timeout**: 120s (allows multiple tool calls)
- **Note**: See `PM_AGENT_SETUP.md` for full documentation

### Checkpoint System (✅ IMPLEMENTED)
**Auto-checkpoint triggers:**
- Schema/migration changes (database-modeler, dme-schema-migration agents)
- Critical file edits (prisma/schema.prisma, package.json, pyproject.toml)
- Destructive bash commands (rm -rf, DROP TABLE, DELETE FROM, prisma migrate)
- Dependency removals (npm uninstall, pip uninstall, pnpm remove)
- Every 50 turns (periodic safety checkpoint)

**Excluded from checkpoints (safe operations):**
- Git operations (git add, git commit, git push, git stash, git checkout)
- Read-only commands (ls, cat, grep, find, etc.)

**Implementation:**
- Hook: `~/claude-hooks/checkpoint_manager.py` integrated into `pretooluse_validate.py`
- Storage: Git stashes with metadata in `~/claude-hooks/logs/checkpoints/`
- Restore: `python ~/claude-hooks/checkpoint_manager.py restore <checkpoint_id>`
- List: `python ~/claude-hooks/checkpoint_manager.py list`
- Retention: Last 20 checkpoints, older auto-deleted

### Background Task Manager (BTM) (⚠️ AVAILABLE, NOT AUTO-INVOKED)
- **Purpose:** Run long-running tasks without blocking Main Agent
- **Use cases:** Dev servers, watchers, migrations, builds
- **Protocol:** BTM returns task handle; Main Agent polls status
- **Integration:** `invoke BTM → get handle → continue planning → check status later`
- **Status:** Agent definition exists, but must be manually invoked via Task tool
- **Path:** `~/.claude/agents/background-task-supervisor.md`

### Hook Enforcement (Automatic)
All hooks run automatically — Main Agent cannot bypass:

| Hook | Trigger | Action |
|------|---------|--------|
| PreToolUse | Before any tool | Validate permissions, check budget |
| PostToolUse (Edit/Write) | After file changes | Lint/typecheck |
| PostToolUse (GPT-5) | After OpenAI API call | Display cost/token usage |
| PostToolUse (Perplexity) | After Perplexity API call | Display cost/token usage |
| PostToolUse (Grep) | After grep search | Summarize results |
| PostToolUse (Bash) | After bash command | Compact output |
| UserPromptSubmit (log_analyzer) | Before each user message | Suggest specialized agents |
| UserPromptSubmit (pivot_detector) | Before each user message | Detect pivots, suggest FEATURE_MAP update |
| UserPromptSubmit (feature_map_validator) | Before each user message | Warn if pivot detected but FEATURE_MAP not updated |
| PostToolUse (Task) | After Task tool | Capture DIGEST blocks, update NOTES.md + wsi.json |
| SubagentStop | Subagent completes | (Limited by Claude Code - use Task hook instead) |
| PreCompact | Before compaction | Checkpoint state |
| Stop | Session end | Extract DIGEST from transcript, update NOTES.md + wsi.json |

### Permission Guards
- **Schema changes:** DME required + checkpoint
- **File deletion:** Explicit confirmation + checkpoint
- **Dependency removal:** IDS review + checkpoint
- **>10 files touched:** IPSA sprint plan + checkpoint

### Routing Rules with Checkpoints
```
If (risky operation detected):
  1. PreToolUse hook auto-creates git stash checkpoint
  2. Hook shows warning with checkpoint ID and restore command
  3. Operation proceeds (non-blocking warning)
  4. User can rollback anytime with checkpoint_manager.py

If (long-running task needed):
  1. Manually invoke BTM via Task tool
  2. BTM returns task handle
  3. Continue planning while task runs
  4. Poll BTM status later with Task tool
```

### Failure Recovery
- If hook fails → stop, remediate, retry
- If subagent fails → checkpoint rollback available
- If PRV fails → block merge, create remediation plan

### Pre-Merge Quality Gate (✅ IMPLEMENTED)

**Command**: `bash ~/claude-hooks/ready-to-merge.sh [--auto-fix]`

**Purpose**: Final quality gate before merging to main branch

**Checks**:
1. Git status (clean working tree)
2. Linter (npm run lint)
3. TypeScript (npm run typecheck)
4. Tests (npm test)
5. Build (npm run build)
6. FEATURE_MAP.md exists and updated

**Flags**:
- `--auto-fix`: Auto-fix linting errors if possible

**Output**: Markdown report with pass/fail status for each check

**Usage**:
```bash
# Before merging PR
bash ~/claude-hooks/ready-to-merge.sh

# With auto-fix
bash ~/claude-hooks/ready-to-merge.sh --auto-fix
```

**Exit Codes**:
- `0`: Ready to merge (all checks passed)
- `1`: Not ready (failed checks, see report)

**Integration**: Main Agent can run this command when user asks "ready to merge?" or "can I merge this?"

### Pivot & Direction Change Workflow (✅ IMPLEMENTED)

**Problem**: Rapid pivots leave obsolete code/docs in codebase, confusing new context windows.

**Solution**: 4-layer tracking system

**Layer 1: FEATURE_MAP.md** (Living Intent Document)
- **Location**: Project root (`FEATURE_MAP.md`)
- **Purpose**: Single source of truth for current project direction
- **Sections**: Active Features, Deprecated Features, Pivot History, Feature Mapping
- **Update**: ALWAYS update FIRST when changing direction

**Layer 2: Pivot Detection Hook** (Automatic)
- **Hook**: `pivot_detector.py` (UserPromptSubmit)
- **Triggers**: "actually", "instead", "pivot", "scrap", "deprecate", "rethink", etc.
- **Action**: Shows warning + suggests updating FEATURE_MAP.md
- **Output**: User sees recommendation to update FEATURE_MAP before proceeding

**Layer 3: Relevance Auditor Agent** (On-Demand)
- **Agent**: `relevance-auditor` (RA)
- **When**: After FEATURE_MAP updates, or user requests "audit relevance"
- **Action**: Cross-references FEATURE_MAP with codebase + wsi.json
- **Output**: Audit report with orphaned files, dead code, stale docs, safe deletions
- **Safety**: Never auto-deletes, requires user confirmation

**Layer 4: Auto-Doc Updater Agent** (On-Demand)
- **Agent**: `auto-doc-updater` (ADU)
- **When**: After RA audit, or user requests "sync docs"
- **Action**: Updates README.md, archives deprecated docs, fixes broken links
- **Output**: Update report + docs/archive/{date}/ + manual review items
- **Safety**: Code comments report-only (no auto-modify)

**Example Pivot Workflow**: Update FEATURE_MAP.md → run RA → run ADU → review + approve. Keeps docs/code in sync while preserving history.

### MCP External Model Integrations (✅ IMPLEMENTED)

OpenAI Bridge (GPT‑5) and Perplexity are configured via MCP. Hooks display model, tokens, and cost after each call. Configure servers in `~/.claude/mcp-servers` or project `.mcp.json`, and choose tools by task (GPT‑5 for brainstorming; Perplexity for live data/citations).
</autonomous_operation>

<digest_contract>
### Output Contract — Subagent Digest (Mandatory)

Every subagent MUST return a fenced JSON block labeled DIGEST before finishing:

```json DIGEST
{
  "agent": "<IPSA|RC|CN|IE|TA|IDS|DME|ICA|PRV|SUPB|DCA|GIC|SA|PO|DA|RM|PDV|BTM>",
  "task_id": "<stable id or short slug>",
  "decisions": ["..."],
  "files": [
    {"path":"apps/web/router.ts","reason":"added route","anchors":[{"start":1,"end":80}]},
    {"path":"packages/ui/Button.tsx","reason":"new prop","anchors":[{"symbol":"ButtonProps"}]}
  ],
  "contracts": ["openapi.yaml#/paths/POST /billing/sources","packages/api/src/types.ts#BillingSource"],
  "next": ["..."],
  "evidence": {
    "lint": "ok", "typecheck": "ok", "build": "ok",
    "tests": "7 added, 0 failed",
    "coverage": "+2.3%"
  }
}
```

If any field is not applicable, include it with an empty array or "n/a".

**Context Discipline:**
- PreCompact: Produce a compaction summary before window compaction. Ensure the final turn before compaction contains a DIGEST block for each active subagent; otherwise include decisions/owned artifacts in NOTES.md so the PreCompact hook can summarize accurately.
</digest_contract>

⸻

<solution_fixpack_workflow>
## 🔧 Solution Fixpack Automation (Vector Memory + AI Memory)

### Overview
Solution fixpacks are reusable templates for fixing recurring errors. They are stored in the **AI Memory** vector database (`~/.claude/mcp-servers/vector-bridge`) and searchable via semantic similarity.

### When to Create Fixpacks

**Triggers:**
- Deployment errors that required multiple steps to resolve
- Build/runtime errors that are likely to recur (e.g., platform-specific like Railway)
- Errors encountered 2+ times in same/different projects
- Complex debugging that produced a clear solution path

**Examples:**
- Railway deployment issues (IPv6 DNS, Dockerfile detection, TypeScript builds)
- Dependency conflicts (lockfile mismatches, missing dev deps)
- Platform-specific configuration (Redis, PostgreSQL, API integrations)

### Fixpack Creation Process

**Step 1: Identify the Error Pattern**
- Capture the exact error message (signatures)
- Note the context (category: build|runtime|deploy, component: infra|backend|mobile)
- Identify regex patterns for matching

**Step 2**: JSON schema with title, category, signatures (error patterns), remediation steps, validation checks

**Step 3: Save Fixpack**
- Location: `~/.claude/mcp-servers/vector-bridge/fixpacks/NNN_description.json`
- Naming: `001_monorepo_lockfile_mismatch.json`, `002_railway_wrong_dockerfile.json`
- Increment number for each new fixpack

**Step 4: Ingest into Database**
```bash
cd ~/.claude/mcp-servers/vector-bridge
npx tsx scripts/ingest-fixpacks.ts
```

This will:
- Read all `fixpacks/*.json` files
- Generate embeddings for signatures (OpenAI API)
- Store in PostgreSQL with vector search indexes
- Cache embeddings in Redis (60-day TTL)

### Using Fixpacks (Automatic via MCP Tools)

**MCP Tool: solution_search**
```typescript
// Search by error message (semantic similarity)
solution_search({
  error_message: "getaddrinfo ENOTFOUND redis.railway.internal",
  category: "runtime",  // optional filter
  component: "infra",   // optional filter
  limit: 5              // top N results
})
```

**Returns:**
- Ranked solutions with confidence scores (0-100%)
- Full remediation steps with commands
- Validation checks
- Success rate tracking (how often this fixpack worked)

**MCP Tool: solution_apply**
```typescript
// After applying a fixpack, record success/failure
solution_apply({
  solution_id: 16,
  success: true  // or false
})
```

This updates the success rate for future recommendations.

### Best Practices

1. **Be Specific**: Signatures should match exact error messages when possible
2. **Add Context**: Use `meta` fields to filter by platform, phase, etc.
3. **Test Steps**: Verify all remediation steps work before saving
4. **Include Checks**: Add validation commands to confirm the fix worked
5. **Update Success Rates**: Always call `solution_apply` after using a fixpack
6. **Avoid Duplication**: Search existing fixpacks before creating new ones

### Example Workflow

```
User encounters error: "sh: tsc: not found"
↓
Main Agent uses solution_search("sh: tsc: not found", category: "build")
↓
Finds: "Railway TypeScript build fails - tsc not found" (78% match)
↓
Presents remediation steps:
1. Convert to multi-stage Docker build
2. Commit and push to trigger rebuild
↓
User applies fix (or Main Agent with IE agent)
↓
Main Agent calls solution_apply(solution_id: 15, success: true)
↓
Success rate updated: 67% → 71%
```

### Integration Points

- **Stop Hook**: Could auto-create fixpacks from session debugging (future enhancement)
- **MCP Server**: Always available via `vector-bridge` MCP tools
- **Agents**: IE, DME, SUPB can all use `solution_search` to find relevant fixes
- **Documentation**: Fixpacks are versioned, searchable knowledge artifacts

</solution_fixpack_workflow>

⸻

<mcp_server_config>
## 🌐 MCP Server: Vector Bridge (AI Memory)

### Overview
The **Vector Bridge MCP Server** provides global vector memory across all projects using PostgreSQL + pgvector for semantic search.

### Services

**Location**: `~/.claude/mcp-servers/vector-bridge`
**Repository**: https://github.com/eshbtc/ai-memory.git
**Deployment**: Railway (auto-deploy from main branch)

**Production Services:**
- **PostgreSQL + pgvector**: `postgres://postgres:PASSWORD@maglev.proxy.rlwy.net:14116/railway`
- **Redis Cache**: `redis://default:PASSWORD@redis.railway.internal:6379` (internal) or `hopper.proxy.rlwy.net:26831` (public)

**Local Development:**
- **PostgreSQL**: Railway production (remote)
- **Redis**: `redis://localhost:6379` (local instance)

### Available Tools

**1. memory_ingest**
- Ingest documents into global vector store
- Auto-chunks text, generates embeddings, stores with metadata
- Returns: chunks created, project_id

**2. memory_search**
- Semantic search across project or globally
- Vector similarity using cosine distance
- Returns: ranked results with scores, metadata

**3. memory_projects**
- List all indexed projects with statistics
- Shows document count, last updated

**4. solution_search**
- Find fixpacks matching error messages
- Vector semantic search + regex patterns
- Returns: ranked solutions with remediation steps

**5. solution_apply**
- Record fixpack application success/failure
- Updates success rate tracking

**6. solution_upsert**
- Create new fixpacks programmatically
- Alternative to manual JSON files

### Configuration

**Environment Variables** (`.env`):
```bash
DATABASE_URL_MEMORY=postgres://...  # PostgreSQL + pgvector
REDIS_URL=redis://...               # Redis cache
OPENAI_API_KEY=sk-proj-...          # For embeddings
```

**Railway Environment Variables**:
```bash
DATABASE_URL_MEMORY=postgres://postgres:PASSWORD@maglev.proxy.rlwy.net:14116/railway
REDIS_URL=redis://default:PASSWORD@redis.railway.internal:6379
OPENAI_API_KEY=sk-proj-...
```

**Note**: Railway Redis requires `family: 0` in ioredis options for IPv6 compatibility.

### pgvector Ingest Policy (Curated, High-Signal Data)

**Philosophy**: Quality over quantity. Only ingest high-signal data (DIGESTs, fixpacks, core docs).

**Always Ingest**:
1. **DIGESTs** (Main Agent + Subagents)
   - Decisions, next steps, contracts affected
   - File paths touched (not full file contents)
   - Evidence (test results, build status)
   - Metadata: `source='digest'`, `agent`, `task_id`

2. **Fixpacks** (Solution Memory)
   - Problem signatures (error messages, symptoms)
   - Remediation steps (commands, patches, checks)
   - Success rate tracking
   - Metadata: `source='fixpack'`, `category`, `component`

3. **Core Documentation**
   - README.md, CLAUDE.md, architecture docs
   - API contracts (OpenAPI, GraphQL schemas)
   - Golden runbooks and onboarding guides
   - Metadata: `source='doc'`, `category='official'`

**Conditionally**: Code snippets (interfaces/types only), error signatures (3-5 lines), agent summaries (final only)
**Never**: Secrets, binaries, raw logs >100 lines, temp drafts
**Guardrails**: Dedupe by SHA256, chunk 2-4KB, metadata filter first, embed cache 60d, query cache 5m, retention: DIGESTs indefinite/code 90d/drafts 7d
**Ingest**: Stop hook (auto DIGESTs), fixpack creation (auto), doc updates (manual), code snippets (explicit only)

### Embedding Model Policy

**Model**: OpenAI text-embedding-3-small (1536-dim) ONLY. No mixing (breaks cosine similarity). Changing models = full DB rebuild.

### Cache Performance

- **Embedding Cache**: 60-day TTL, ~70% cost savings on OpenAI API
- **Query Cache**: 5-minute TTL, 14.6x speedup for repeated searches
- **Dedupe Cache**: 48-hour TTL, prevents duplicate ingestion
- **Graceful Degradation**: System continues if Redis unavailable (fallback mode)

### Health Checks

Server runs health checks on startup:
- **PostgreSQL**: Required (hard fail if unavailable)
- **Redis**: Optional (warns but continues in fallback mode)

**Expected Logs:**
```
[Health] ✅ PostgreSQL connected
[Health] ✅ Redis connected
[Health] Service ready (DB: ✅, Redis: ✅)
Vector Bridge MCP server running on stdio
```

### Testing

See vector-bridge repo for testing scripts. 

### Deployment

**Automatic Railway Deployment:**
1. Push to `main` branch: `git push origin main`
2. Railway detects changes and rebuilds
3. Multi-stage Docker build (TypeScript → Node.js runtime)
4. Health checks run on container start
5. MCP server available via stdio

Auto-deploys via Railway when pushed to main. 

**All solutions documented as fixpacks in `fixpacks/` directory.**

</mcp_server_config>

⸻

## 🚨 CRITICAL REMINDER: Main Agent DIGEST Requirement

**MANDATORY**: Main Agent MUST emit a DIGEST block at the end of ANY work session where you:
- Created or modified files (Write, Edit tools)
- Completed multi-step tasks (TodoWrite with completed items)
- Made architectural decisions
- Orchestrated subagents

**Why this matters**:
- Without DIGEST → No vector ingestion
- Without DIGEST → No WSI tracking
- Without DIGEST → No NOTES.md updates
- Without DIGEST → Session work is lost

**When to emit DIGEST**:
- ✅ After creating documentation/planning files
- ✅ After completing a phase of work
- ✅ Before ending session (if work was done)
- ❌ Not needed for simple Q&A or read-only sessions

**Main Agent DIGEST template**:
```json DIGEST
{
  "agent": "Main",
  "task_id": "project-nexus-planning",
  "decisions": ["Created implementation plan", "Documented architecture"],
  "files": [
    {"path": "docs/ARCHITECTURE.md", "reason": "created"},
    {"path": "docs/API_SPEC.md", "reason": "created"}
  ],
  "contracts": ["n/a"],
  "next": ["Ready for Phase 1 implementation"],
  "evidence": {"phase": "planning_complete", "files_created": 11}
}
```

**If you created files this session**: Emit DIGEST before responding "done" to user.

</claude_code_orchestration_framework>
