# GPT-5 Product Manager Agent - Setup & Usage

## Overview

The PM Agent system enables **autonomous decision-making** when Claude agents encounter decision points, using GPT-5 (via OpenAI MCP) as the strategic decision-maker.

**Problem Solved:** Conversations stop when agents ask "Should I do X or Y?" - this system allows GPT-5 to make those decisions based on project goals, keeping development flowing.

---

## Architecture

```
Claude Agent → Decision Point → Stop Hook → PM Hook → GPT-5 MCP → Decision
                                                         ↓
                                                  AGENTS.md (context)
                                                  pm-decisions.json (history)
                                                         ↓
                                                  Resume Instructions
```

### Components

1. **AGENTS.md** - Project context and decision framework for GPT-5
2. **pm_decision_hook.py** - Detects decision points and calls GPT-5
3. **stop_digest.py** - Integrated with PM hook (async call)
4. **.claude/logs/pm-decisions.json** - Decision log for learning
5. **.claude/logs/pm-resume/*.md** - Resume instructions for next session

---

## Current Status

### ✅ Implemented (Path B - Fully Automated)

- [x] AGENTS.md template with decision frameworks
- [x] pm_decision_hook.py with decision detection and queuing
- [x] pm_queue_processor.py with direct OpenAI API calling
- [x] stop_digest.py integration (async spawn)
- [x] Decision logging system (`.claude/logs/pm-decisions.json`)
- [x] Resume instructions generation (`.claude/logs/pm-resume/*.md`)
- [x] Launchd agent setup script (`setup_pm_launchd.sh`)
- [x] End-to-end testing with vs-claude scenario ✅
- [x] Test mode for validation

### 🔄 Pending

- [ ] Auto-resume next Claude session with PM decision (requires Claude Desktop feature)
- [ ] AGENTS.md sync automation with CLAUDE.md updates
- [ ] Notification system (Discord/Slack) for critical decisions

---

## Automated Usage (Path B - RECOMMENDED)

**✅ Now Fully Automated!** The PM agent runs automatically via launchd queue processor.

### Setup (One-Time)

1. **Install OpenAI Python SDK:**
   ```bash
   pip3 install --break-system-packages openai
   ```

2. **Set OpenAI API Key:**
   ```bash
   export OPENAI_API_KEY="sk-proj-..."
   # Add to ~/.zshrc or ~/.bashrc for persistence
   ```

3. **Enable PM Agent:**
   ```bash
   export ENABLE_PM_AGENT=true
   # Add to ~/.zshrc or ~/.bashrc for persistence
   ```

4. **Setup Launchd Agent:**
   ```bash
   cd ~/.claude
   bash hooks/setup_pm_launchd.sh
   ```

### How It Works

1. **Agent stops with question** → Stop hook detects decision point
2. **Request queued** → `.claude/pm-queue/request-*.json` created
3. **PM processor runs** (every 10 minutes via launchd)
4. **GPT-4o decides** → Based on AGENTS.md context
5. **Resume instructions created** → `.claude/logs/pm-resume/*.md`
6. **You come back** → Read resume file, start new session with decision

### Example

```bash
# Agent asks: "Should I apply migration now or wait?"
# Stop hook → Creates queue/request-20251005-225608.json

# 10 minutes later (or run manually):
python3 ~/.claude/hooks/pm_queue_processor.py

# Output:
# ✅ Processed: apply_migration_and_continue
# Resume file: .claude/logs/pm-resume/resume-20251005-225619.md

# You:
cat .claude/logs/pm-resume/resume-20251005-225619.md
# See: Apply migration, continue Phase 5, monitor context budget

# Start new session in vs-claude:
cd ~/yolo/vs-claude
# Paste actions from resume file or just say:
# "Continue Phase 5 - apply migration first per PM decision"
```

---

## Manual Usage (Optional Fallback)

If you prefer manual control or launchd is not running:

### When Agent Asks Question

1. **Agent stops with decision point:**
   ```
   "Should I apply migration now or wait?"
   ```

2. **Copy question to GPT-5 manually** (in Claude Desktop):
   ```
   Ask GPT-5 PM agent:

   [Paste agent's question]

   Context from AGENTS.md: [Paste relevant section]
   ```

3. **Use mcp__openai-bridge__ask_gpt5 tool:**
   - Prompt: Include decision point + AGENTS.md context
   - Model: gpt-4o (good balance) or gpt-5 (deep reasoning)
   - Temperature: 0.3 (consistent decisions)

4. **Get decision JSON:**
   ```json
   {
     "decision": "apply_migration",
     "reasoning": "...",
     "actions": ["Step 1", "Step 2"],
     "risks": ["..."],
     "mitigation": ["..."]
   }
   ```

5. **Continue development** with the decision

---

## Example: Your vs-claude Scenario

**Agent Question:**
```
"Excellent progress! Phase 4 (Indexing) complete with 1170 LOC.
However, before continuing with Phase 5, I notice we haven't applied the database migration yet.

Since the database migration is blocking and we're at 59% context usage (118k/200k), should I:
1. Continue creating the migration files and Phase 5 (Search implementation)?
2. Pause here and you can review Phase 4 implementation first?"
```

**GPT-5 PM Decision:**
```json
{
  "decision": "apply_migration",
  "reasoning": "Applying the database migration is necessary as it is blocking the start of Phase 5 (Search implementation). The context usage is at a healthy level, allowing us to proceed without compressing. This aligns with the production-ready bias of finishing what we started.",
  "actions": [
    "Apply the database migration to unblock Phase 5.",
    "Once the migration is applied, proceed with the implementation of Phase 5 (Search)."
  ],
  "risks": [
    "The migration might introduce unforeseen issues or bugs."
  ],
  "mitigation": [
    "Ensure thorough testing of the migration in a staging environment before applying it to production."
  ],
  "escalate_to_user": false,
  "notes": "Phase 4 is complete, and the context usage is well within limits, making it an optimal time to apply the migration."
}
```

**Resume with Decision:**
In the vs-claude project, start new session and say:
```
Continue Phase 5 implementation. Apply the database migration first (blocking dependency), then implement Search. Context budget is healthy (59%).
```

---

## Future Automation (Roadmap)

### Option A: MCP Client in Hook
- Add MCP client library to pm_decision_hook.py
- Initialize OpenAI MCP connection
- Call ask_gpt5 directly from hook
- **Complexity:** Medium
- **Benefit:** Fully automated in same session

### Option B: Queue + Launchd Processor
- PM hook writes decision request to queue (`.claude/pm-queue/*.json`)
- Launchd agent runs every 5 minutes
- Processes queue, calls GPT-5, writes resume instructions
- **Complexity:** Low (similar to digest queue)
- **Benefit:** Reliable, testable, async

### Option C: Cross-Session Resume
- PM decision written to `.claude/next-prompt.txt`
- Next Claude session auto-loads this file as first prompt
- Agent sees decision and continues autonomously
- **Complexity:** Requires Claude Desktop feature (not available)
- **Benefit:** Seamless user experience

**Recommended:** Option B (Queue + Launchd)

---

## Maintenance

### Updating AGENTS.md

When you update CLAUDE.md policies:
1. Also update AGENTS.md with matching decision frameworks
2. Test with `python hooks/pm_decision_hook.py --test`
3. Review past decisions in `.claude/logs/pm-decisions.json`

### Decision Framework Patterns

**Add new frameworks** to AGENTS.md when you encounter recurring decision types:

```markdown
### [Decision Type]
**Question:** "Should I..."
**Decision:**
- If condition A: Do X
- If condition B: Do Y

**Action:** Execute and document
```

---

## Testing

```bash
# Test PM hook with vs-claude scenario
python hooks/pm_decision_hook.py --test

# Check decision log
cat .claude/logs/pm-decisions.json | jq '.[-3:]'

# Check resume instructions
ls -la .claude/logs/pm-resume/

# Test in Claude (manual)
# Use mcp__openai-bridge__ask_gpt5 with AGENTS.md context
```

---

## Cost Tracking

- **GPT-4o:** ~$0.003 per decision (~500 tokens)
- **GPT-5:** ~$0.015 per decision (if using actual GPT-5)
- **Typical session:** 3-5 decisions = $0.01-0.08

Monitored via `mcp__openai-bridge__get_usage_stats` tool.

---

## Next Steps

1. **Immediate:** Use manual workflow for vs-claude (copy/paste to GPT-5)
2. **Short-term:** Implement Queue + Launchd processor (Option B)
3. **Long-term:** Explore MCP client in hooks (Option A)
4. **Documentation:** Sync AGENTS.md with CLAUDE.md on every policy update

---

## Files

- `AGENTS.md` - PM agent context and decision frameworks
- `hooks/pm_decision_hook.py` - Decision detection and GPT-5 calling
- `hooks/stop_digest.py` - Integration point (lines 1285-1314)
- `.claude/logs/pm-decisions.json` - Decision history
- `.claude/logs/pm-resume/*.md` - Resume instructions

---

---

## Quick Reference

### Commands
```bash
# Check launchd status
launchctl list | grep pm-queue

# View logs
tail -f .claude/logs/pm-queue-processor-stdout.log

# Process queue manually (don't wait for launchd)
python3 ~/.claude/hooks/pm_queue_processor.py

# Check for pending decisions
ls -la .claude/pm-queue/

# View latest decision
cat .claude/logs/pm-decisions.json | jq '.[-1]'

# View latest resume instructions
ls -t .claude/logs/pm-resume/ | head -1 | xargs -I {} cat .claude/logs/pm-resume/{}
```

### Environment Variables
- `ENABLE_PM_AGENT=true` - Enable PM decision detection in Stop hook
- `OPENAI_API_KEY=sk-proj-...` - Required for PM queue processor
- `CLAUDE_PROJECT_DIR=/path/to/project` - Project root (auto-detected)

### Cost Tracking
- ~$0.005 per decision (GPT-4o, ~2500 tokens avg)
- ~10 decisions = $0.05
- Monitor: Check `_meta.tokens` in pm-decisions.json

---

**Status:** ✅ Fully Automated (Path B Complete) - GPT-4o PM agent operational via launchd queue processor.
