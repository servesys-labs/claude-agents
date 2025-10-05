# Solution Memory (Fixpacks)

Turn every solved issue into a reusable fixpack. Never waste time re-deriving the same solution twice.

## Problem

You spend hours fixing the same issues across repos:
- Monorepo deployment conflicts (lockfile mismatches, workspace linking)
- Shared folder sync (rsync specs, file counts)
- Package manager migrations (npm→pnpm)
- CI environment quirks (Railway, Vercel, GitHub Actions)

**Current State:** Rely on LLM to re-solve every time → waste hours

**Goal:** Capture fix once, retrieve in seconds, apply with preview

## Solution: Global Fixpack Memory

### Architecture

```
┌─────────────────────────────────────────────┐
│ Working on project → encounter error        │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ Hook detects error pattern                  │
│ Searches solution memory (vector + metadata)│
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ "Apply Fixpack #3? (92% success rate)"     │
│ Shows: title, steps, diffs, checks          │
└──────────────┬──────────────────────────────┘
               │
               ▼ (user approves)
┌─────────────────────────────────────────────┐
│ Execute steps (dry-run → preview → apply)   │
│ Record outcome (success/failure)            │
└─────────────────────────────────────────────┘
```

### What Gets Captured

**Per Fixpack:**
1. **Problem Signature**
   - Compact error text
   - Regex patterns
   - Vector embedding (for semantic search)

2. **Context Metadata**
   - `category`: devops|deploy|workspace|tsconfig|migration
   - `component`: backend|mobile|infra|data
   - `package_manager`: npm|pnpm|yarn|bun
   - `monorepo_tool`: turbo|nx|lerna|rush
   - `tags`: ["monorepo", "lockfile", "Railway"]

3. **Actions (Steps)**
   - `cmd`: Shell commands with cwd/env
   - `patch`: Git diffs to apply
   - `copy`: rsync specs (src/dst/flags/includes/excludes)
   - `script`: Inline scripts
   - `env`: Environment variable changes

4. **Verification (Checks)**
   - Commands to run
   - Expected output (substring or exit code)
   - Timeout limits

5. **Success Metrics**
   - `success_count` / `failure_count`
   - `last_applied_at`
   - `verified_on` (last successful apply)

## Database Schema

```sql
solutions (
  id, title, description,
  category, component, tags[],
  project_root, repo_name,
  package_manager, monorepo_tool,
  success_count, failure_count,
  last_applied_at, verified_on
)

signatures (
  id, solution_id,
  text, regexes[], embedding,
  meta
)

steps (
  id, solution_id, step_order,
  kind (cmd|patch|copy|script|env),
  payload, description, timeout_ms
)

checks (
  id, solution_id, check_order,
  cmd, expect_substring, expect_exit_code,
  timeout_ms
)
```

## Usage

### 1. Search for Fixpacks

**CLI:**
```bash
fixpack search "ERR_PNPM_WORKSPACES"
```

**Output:**
```
[1] Monorepo build fix — mismatched workspace and lockfile (score: 95%, success: 92%)
  Fixes ERR_PNPM_WORKSPACES when lockfile doesn't match package manager...

[2] Package manager migration (npm → pnpm) (score: 78%, success: 87%)
  Migrates existing npm monorepo to pnpm with workspace support...
```

**Via Hook (Automatic):**
When you paste an error, `log_analyzer` hook searches and suggests:
```
⚠️  Detected known error pattern
💡 Suggested fixpack: #1 "Monorepo build fix" (92% success rate)

Run: fixpack apply 1
```

### 2. Preview Fixpack

```bash
fixpack apply 1
```

**Output (Dry-Run):**
```
Solution: Monorepo build fix — mismatched workspace and lockfile
Steps to execute (4):

[1] CMD: Remove conflicting lockfiles
  Command: rm -f package-lock.json yarn.lock

[2] CMD: Reinstall with pnpm
  Command: pnpm install

[3] PATCH: Add packageManager field to package.json
  File: package.json

[4] CMD: Rebuild with pnpm
  Command: pnpm build

This was a DRY RUN. No changes were made.

To apply for real, run:
  fixpack apply 1 --no-dry-run
```

### 3. Apply Fixpack

```bash
fixpack apply 1 --no-dry-run
```

**Output:**
```
Executing step [1/4]: Remove conflicting lockfiles
  Running: rm -f package-lock.json yarn.lock
  ✅ Success (0.1s)

Executing step [2/4]: Reinstall with pnpm
  Running: pnpm install
  ✅ Success (12.3s)

Executing step [3/4]: Add packageManager field to package.json
  Applying patch to: package.json
  ✅ Success (0.2s)

Executing step [4/4]: Rebuild with pnpm
  Running: pnpm build
  ✅ Success (34.5s)

Running verification checks...
  ✅ Check 1: pnpm-lock.yaml exists
  ✅ Check 2: Build completed

Solution applied successfully!

Did the fix work? (y/n): y
Recording success... ✅
```

### 4. Save New Fixpack

**Create fixpack JSON:**
```json
{
  "title": "Railway deployment fix — missing env vars",
  "description": "Adds required env vars for Railway deployment",
  "category": "deploy",
  "component": "infra",
  "tags": ["railway", "env", "deployment"],
  "signatures": [
    {
      "text": "Missing environment variable: DATABASE_URL",
      "regexes": ["Missing environment variable", "Env.*not found"]
    }
  ],
  "steps": [
    {
      "kind": "env",
      "payload": {
        "set": {
          "DATABASE_URL": "${DATABASE_URL_FROM_RAILWAY}",
          "NODE_ENV": "production"
        }
      },
      "description": "Set required environment variables"
    }
  ],
  "checks": [
    {
      "cmd": "echo $DATABASE_URL",
      "expect_substring": "postgres://",
      "timeout_ms": 5000
    }
  ]
}
```

**Save:**
```bash
fixpack save fixpacks/railway-env-fix.json
```

## Hook Integration

### log_analyzer (UserPromptSubmit)

**Before:**
```
User: <pastes 500-line build error>
Agent: Let me analyze this... <spends 2 minutes>
```

**After (with Solution Memory):**
```
User: <pastes error>
Hook: Detected known pattern "ERR_PNPM_WORKSPACES"
Hook: 💡 Fixpack #1 available (92% success)
Agent: I found a fixpack for this. Run: fixpack apply 1
```

### PostToolUse (Failed Builds)

**Trigger:** 2nd consecutive build failure

**Action:**
```
⚠️  Build failed 2x in a row
💡 Suggested fixpack: #3 "TypeScript build fix — missing types"
Run: fixpack apply 3
```

### Stop Hook (Save on Success)

**Trigger:** Sequence of steps solved an error

**Action:**
```
✅ Issue resolved!
💾 Save as fixpack? (y/n): y

Title: <auto-suggested>
Description: <auto-generated from steps>
Save? (y/n): y
Saved as fixpack #7
```

## Example Fixpacks

### 1. Monorepo Lockfile Mismatch

**Signatures:**
- `ERR_PNPM_WORKSPACES`
- `workspaces detected but npm lockfile present`

**Steps:**
1. `rm -f package-lock.json yarn.lock`
2. `pnpm install`
3. Patch `package.json` (add `packageManager` field)
4. `pnpm build`

**Success Rate:** 92% (23/25)

### 2. Shared Folder Sync

**Signatures:**
- `Cannot find module.*shared`
- `Module not found.*@shared`

**Steps:**
1. `rsync -av --delete packages/shared/src/ packages/backend/src/shared/`
2. `rsync -av --delete --exclude='*.node.ts' packages/shared/src/ packages/mobile/src/shared/`
3. `pnpm typecheck`

**Success Rate:** 95% (19/20)

### 3. Railway Deployment Failure

**Signatures:**
- `Build failed on Railway`
- `nixpacks.*failed`

**Steps:**
1. Add `nixpacks.toml` with Node version
2. Set `NODE_ENV=production`
3. Add build command override
4. Redeploy

**Success Rate:** 87% (13/15)

## Retrieval Strategy

### Phase 1: Filter by Metadata

```sql
WHERE
  (project_root IS NULL OR project_root = $current_project)
  AND (package_manager IS NULL OR package_manager = $detected_pm)
  AND (monorepo_tool IS NULL OR monorepo_tool = $detected_tool)
  AND category = $inferred_category
```

### Phase 2: Vector Rank

```sql
ORDER BY embedding <=> $error_embedding
```

### Phase 3: Boost by Success

```sql
, success_count DESC
, verified_on DESC NULLS LAST
```

### Phase 4: Fallback

If `results < 3`:
1. Relax `project_root` (search globally)
2. Relax `monorepo_tool`
3. Relax `package_manager`

## Safety Guardrails

✅ **Always preview** - Never auto-apply without showing steps
✅ **Dry-run default** - Must explicitly pass `--no-dry-run`
✅ **Permission gates** - Claude Code permissions + PreToolUse hooks
✅ **Rollback support** - Each fixpack includes rollback steps (TODO)
✅ **Success tracking** - Record outcomes to boost/demote fixpacks

## MCP Tools

### solution_search

```typescript
{
  query: "ERR_PNPM_WORKSPACES",
  project_root: "/Users/name/my-project",
  category: "workspace",
  package_manager: "pnpm",
  k: 5
}
```

**Returns:**
```json
{
  "results": [
    {
      "solution_id": 1,
      "title": "Monorepo build fix",
      "score": 0.95,
      "success_rate": 0.92,
      "step_count": 4
    }
  ]
}
```

### solution_apply

```typescript
{
  solution_id: 1,
  dry_run: true,
  project_root: "/Users/name/my-project"
}
```

**Returns:**
```json
{
  "title": "Monorepo build fix",
  "steps": [
    {
      "order": 1,
      "kind": "cmd",
      "description": "Remove conflicting lockfiles",
      "payload": {
        "run": "rm -f package-lock.json yarn.lock"
      }
    }
  ],
  "checks": [...]
}
```

### solution_upsert

```typescript
{
  fixpack: {
    title: "My fix",
    signatures: [...],
    steps: [...]
  }
}
```

## Cost Savings

**Before (manual fix, every time):**
- 30-60 minutes per occurrence
- 5 occurrences/week = 2.5-5 hours/week
- **10-20 hours/month wasted**

**After (with fixpacks):**
- 2 minutes to search + preview + apply
- First-time capture: +5 minutes (one-time cost)
- **~30 minutes/month total**

**Time Saved:** 9.5-19.5 hours/month = **~95% reduction**

## Getting Started (This Week)

1. **Run migration:**
   ```bash
   psql $DATABASE_URL_MEMORY < migrations/003_solution_memory.sql
   ```

2. **Save your first 5 fixpacks:**
   ```bash
   fixpack save fixpacks/001_monorepo_lockfile_mismatch.json
   fixpack save fixpacks/002_shared_folder_sync.json
   # ... add 3 more from your recurring issues
   ```

3. **Test search:**
   ```bash
   fixpack search "ERR_PNPM_WORKSPACES"
   ```

4. **Test apply (dry-run):**
   ```bash
   fixpack apply 1
   ```

5. **Enable hook integration:**
   - Update `log_analyzer.py` to call `solution_search`
   - Add PostToolUse hook for failed builds

## Next Steps

- [ ] Implement MCP tools (solution_search, solution_apply, solution_upsert)
- [ ] Update log_analyzer to auto-suggest fixpacks
- [ ] Add rollback support to fixpacks
- [ ] Create web UI for browsing/editing fixpacks
- [ ] Add auto-tagging from content analysis
- [ ] Implement hybrid search (vector + BM25)
