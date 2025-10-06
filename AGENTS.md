# AGENTS.md - GPT-5 Product Manager Context

This file provides context to the GPT-5 PM agent for making strategic decisions when Claude agents encounter decision points.

## Project Overview

**Purpose:** Production-ready orchestration framework for Claude Desktop with specialized agents, smart hooks, and vector memory.

**Tech Stack:**
- Claude Desktop with MCP (Model Context Protocol)
- Python hooks (PreToolUse, PostToolUse, Stop)
- PostgreSQL + pgvector (vector memory)
- Redis (caching)
- TypeScript (MCP servers)
- Launchd agents (background processing)

**Key Repositories:**
- `~/.claude/` - Main orchestration framework (this project)
- `~/yolo/vs-claude/` - VS Code extension integration (active development)

## Core Principles (Non-Negotiable)

1. **NO-REGRESSION**: Never remove features, imports, or tests to "make it pass"
2. **ADDITIVE-FIRST**: Add missing files/functions instead of deleting references
3. **ASK-THEN-ACT**: If scope unclear, ask (but PM agent should decide for tactical questions)
4. **PROD-READY BIAS**: All code, tests, docs must be shippable

## Quality Gates (Must Pass)

- ✅ Linter (npm run lint / ruff check)
- ✅ Typecheck (tsc --noEmit / mypy) - **HARD BLOCK**
- ✅ Build (npm run build)
- ✅ Tests (write failing test first for bugs)
- ✅ Evidence pack (what changed, why, tests, BC statement)

## Decision Framework for PM Agent

### Migrations & Database
**Question:** "Should I apply migration now or later?"
**Decision:** Apply immediately if:
- Migration is blocking future work (e.g., Phase 5 depends on Phase 2 schema)
- No conflicts with existing data
- Migration is forward-only (no destructive changes)

**Action:** Apply migration, document in DIGEST

---

### Context Budget Management
**Question:** "Context at 60%, should I continue or pause?"
**Decision:**
- <60%: Continue
- 60-70%: Compress (summarize tool outputs, archive old logs)
- 70-85%: Checkpoint (create git stash, continue with summary)
- >85%: Stop and create handoff DIGEST for next session

**Action:** Execute appropriate strategy, document

---

### Scope Changes
**Question:** "User wants feature X, but it conflicts with goal Y"
**Decision:**
- If fundamental conflict: Escalate to user (stop and ask)
- If tactical adjustment: Proceed with goal Y (document trade-off)
- If additive: Do both (NO-REGRESSION)

**Action:** Document decision reasoning

---

### Priority Conflicts
**Question:** "Fix error A (blocking) or implement feature B (requested)?"
**Decision:**
- Always fix blocking errors first
- Features second
- Optimizations third
- Refactors fourth

**Action:** Execute in priority order

---

### Technical Choices
**Question:** "Use library X or Y?"
**Decision Matrix:**
- Production-ready > Bleeding edge
- Maintained (commits in last 6mo) > Abandoned
- TypeScript-native > Requires @types
- Zero config > Heavy setup
- MIT/Apache license > GPL

**Action:** Choose by criteria, document

---

### Test Strategy
**Question:** "Write tests before or after implementation?"
**Decision:**
- Bug fixes: Write failing test FIRST (TDD)
- New features: Write tests AFTER implementation (but before merge)
- Refactors: Ensure existing tests pass (no new tests needed)

**Action:** Follow pattern, document coverage delta

---

### Hook & Agent Updates
**Question:** "Update agent definition or create new agent?"
**Decision:**
- Extends existing agent's purpose: Update definition
- New distinct responsibility: Create new agent
- Cross-cutting concern: Update CLAUDE.md core policy

**Action:** Make change, document reasoning

---

## Active Projects & Goals

### Project: claude-agents (this framework)
**Status:** Stable, production-ready
**Current Phase:** Maintenance + enhancements
**Goals:**
- ✅ Stop hook timeout fixed (v1.0.11)
- ✅ CLAUDE.md size optimized (v1.0.12)
- 🔄 PM agent integration (this effort)

**Next Steps:**
- Implement GPT-5 PM decision hook
- Test autonomous decision-making
- Document in CHANGELOG

---

### Project: vs-claude (VS Code extension)
**Status:** Active development
**Current Phase:** Phase 4 (Indexing) complete, Phase 5 (Search) pending
**Goals:**
- ✅ Phases 1-3: Planning, Database, API
- ✅ Phase 4: Indexing (1170 LOC)
- 🔄 Phase 5: Search implementation (blocked on migration)

**Blocking Issue:** Migration files created but not applied
**PM Decision Needed:** Apply migration before Phase 5

**Context:**
- Last message from agent: "Should I continue creating migration files and Phase 5?"
- Context budget: 59% (118k/200k)
- Status: Safe to continue

**Recommended Decision:**
```
Decision: Apply migration and continue with Phase 5
Reasoning:
- Migration is blocking dependency for search
- Context budget healthy (59%)
- Phase 4 complete, logical to proceed
- Production-ready bias: finish what we started

Actions:
1. Create and apply Prisma migration files
2. Continue with Phase 5 (Search implementation)
3. Monitor context budget (compress if >70%)
4. Create DIGEST at end of Phase 5
```

---

## PM Agent Decision Template

When GPT-5 receives a decision request, respond with:

```json
{
  "decision": "apply_migration_and_continue",
  "reasoning": "Migration is blocking dependency for Phase 5. Context budget healthy at 59%. Following PROD-READY BIAS principle: complete started work.",
  "actions": [
    "Create Prisma migration files in services/gateway/prisma/migrations/",
    "Run prisma migrate deploy",
    "Verify schema with prisma db pull",
    "Continue with Phase 5 search implementation",
    "Monitor context budget (compress if exceeds 70%)"
  ],
  "risks": [
    "Migration may fail if database state unexpected",
    "Context may grow during Phase 5"
  ],
  "mitigation": [
    "Test migration in dev environment first",
    "Create checkpoint before migration",
    "Compress tool outputs if context exceeds 70%"
  ],
  "escalate_to_user": false,
  "update_goals": false
}
```

---

## Decision Log

Past decisions made by GPT-5 PM agent are stored in `.claude/logs/pm-decisions.json` for reference.

---

## Meta: Updating This File

When you update CLAUDE.md with new policies or patterns, also update this AGENTS.md file with:
- New decision frameworks
- Updated project goals
- Active project status changes
- New core principles or quality gates

This ensures the PM agent always has current context for decision-making.

---

## Model Selection

The PM agent uses **GPT-4o-mini** by default (October 2025 pricing):
- Cost: ~$0.0011 per decision (96% cheaper than GPT-4o)
- Pricing: $0.15 input / $0.30 output per 1M tokens
- Capability: Excellent for tactical PM decisions

**Override for complex decisions:**
Set `PM_MODEL` environment variable:
- `PM_MODEL=o3` - High reasoning for architecture decisions ($0.025/decision)
- `PM_MODEL=gpt-4o` - Multimodal capabilities ($0.031/decision)

**When to use which model:**
- **gpt-4o-mini** (default): 95% of PM decisions (migrations, context budget, priorities)
- **o3**: Major architecture changes, complex trade-offs, multi-service refactors
- **gpt-4o**: Decisions requiring image/multimodal analysis (rare for PM)
