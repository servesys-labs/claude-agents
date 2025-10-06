# PM Agent Quick Start

**Version 1.2.1** - Manual + Autonomous Modes

## TL;DR

```bash
# Setup (one-time)
export OPENAI_API_KEY=sk-proj-...
export ENABLE_PM_AGENT=true

# Use PM manually when agent asks question
# 1. Copy agent's question to clipboard
# 2. Run:
bash ~/.claude/hooks/pm_answer_now.sh

# (Optional) Enable autonomous mode
export ENABLE_PM_AUTONOMOUS=true
```

## Two Modes

### Mode 1: Manual (Default) 👈 Start Here

**Good for:**
- Testing PM for first time
- POC projects where you want control
- Learning how PM makes decisions

**How it works:**
1. Agent asks question (e.g., "Should I use Docker or GCP?")
2. You copy question to clipboard
3. Run `bash ~/.claude/hooks/pm_answer_now.sh`
4. PM gathers context (reads files, checks git, searches code)
5. PM makes decision and copies to clipboard
6. You paste decision into new session

**Enable:**
```bash
export ENABLE_PM_AGENT=true
# That's it! PM ready for manual triggering
```

### Mode 2: Autonomous (Opt-In)

**Good for:**
- Once you trust PM's decisions
- Overnight development workflow
- Fully automated "vibe coding"

**How it works:**
1. Agent asks question at session end
2. Stop hook triggers automatically
3. PM analyzes and decides
4. Resume file created in `~/.claude/logs/pm-resume/`
5. Next session: paste resume instructions

**Enable:**
```bash
export ENABLE_PM_AGENT=true
export ENABLE_PM_AUTONOMOUS=true  # 👈 Enables auto-trigger
```

## Example Workflow (Manual Mode)

**Project Nexus - IPSA asks infrastructure question:**

```
┌─────────────────────────────────────────┐
│ IPSA in Claude:                         │
├─────────────────────────────────────────┤
│ What would you like to do next?         │
│                                          │
│ 1. Begin Phase 1 (GCP infrastructure)   │
│ 2. Setup Local Development (Docker)     │
│ 3. Additional Planning                  │
│ 4. Review Specific Document             │
│ 5. Something Else                       │
└─────────────────────────────────────────┘

You: [Copy question to clipboard]

Terminal:
$ bash ~/.claude/hooks/pm_answer_now.sh

🤖 PM will analyze this question:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
What would you like to do next?
1. Begin Phase 1 (GCP infrastructure)
...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Creating conversation...
🧠 PM analyzing and gathering context...

Round 1: PM reads AGENTS.md
Round 2: PM checks package.json (no GCP deps)
Round 3: PM greps for docker-compose (found!)
Round 4: PM checks git status
Round 5: PM makes decision

✅ PM Decision Complete!
   Decision: local_dev_first
   Reasoning: Prototyping phase, no GCP creds, docker-compose exists

   Actions:
     1. Use existing docker-compose.yml
     2. Add local PostgreSQL service
     3. Document environment setup
     4. Defer GCP to Phase 3

📋 Decision copied to clipboard!

You: [Paste into new Claude session]

Claude: *continues with PM's decision*
```

## Cost

- **Manual trigger**: $0.005-0.02 per decision (3-7 rounds typically)
- **Autonomous**: Same cost, just triggers automatically
- **No cost** if PM not triggered

## Migration Path

```bash
# Week 1: Manual mode (learn PM's reasoning)
export ENABLE_PM_AGENT=true

# Review decisions in ~/.claude/logs/pm-resume/
# Check conversation history in .claude/pm-queue/processed/

# Week 2+: Enable autonomous (if satisfied)
export ENABLE_PM_AUTONOMOUS=true
```

## Files

- **`pm_answer_now.sh`**: Quick manual trigger (clipboard-based)
- **`pm_inline_trigger.py`**: Manual trigger (argument-based)
- **`pm_dialogue_processor.py`**: Multi-round dialogue engine
- **`pm_conversation.py`**: Conversation manager + tools
- **`pm_decision_hook.py`**: Stop hook integration

## Configuration

```bash
# ~/.zshrc or ~/.bashrc

# Required
export OPENAI_API_KEY=sk-proj-...

# PM Agent (manual mode by default)
export ENABLE_PM_AGENT=true

# Optional: Autonomous mode (automatic session-end trigger)
# export ENABLE_PM_AUTONOMOUS=true

# Optional: Model override (default: gpt-4o)
# export PM_DIALOGUE_MODEL=gpt-4o
# export PM_DIALOGUE_MODEL=o3  # For complex decisions
```

## Troubleshooting

### "PM Agent available for manual triggering"
✅ Expected! This means PM is working but not in autonomous mode.
Use `bash ~/.claude/hooks/pm_answer_now.sh` to trigger.

### "ENABLE_PM_AGENT not set"
```bash
export ENABLE_PM_AGENT=true
```

### "OPENAI_API_KEY not set"
```bash
export OPENAI_API_KEY=sk-proj-...
```

### PM makes poor decisions
1. Update `AGENTS.md` with clearer vision
2. Review conversation history (`.claude/pm-queue/processed/`)
3. Try `PM_DIALOGUE_MODEL=o3` for complex decisions

### Want fully automatic mode
```bash
export ENABLE_PM_AUTONOMOUS=true
```

## See Also

- **PM_DIALOGUE_SYSTEM.md** - Full documentation (400+ lines)
- **CLAUDE.md** - Hook #11 system integration
- **CHANGELOG.md** - Version history

## Philosophy

> Start manual, trust builds, enable autonomous

- **Manual mode**: Control when PM intervenes (testing/POC)
- **Autonomous mode**: PM handles overnight decisions (production)
- **Progressive enhancement**: You decide when to upgrade
