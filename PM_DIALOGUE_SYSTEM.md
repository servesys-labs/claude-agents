# PM Multi-Round Strategic Dialogue System

**"Vibe Coding" - User sets vision, PM + agents execute autonomously**

Version: 1.2.0+

## Overview

The PM Agent now supports **multi-round strategic dialogue** using GPT-4o with function calling. Instead of making blind decisions, the PM can:

1. **Ask clarifying questions** about the project
2. **Read files** (AGENTS.md, package.json, code, etc.)
3. **Search codebase** (grep for patterns, check structure)
4. **Check git state** (status, recent commits)
5. **Make informed decisions** based on gathered context

This enables true **autonomous development** - you set the high-level vision, and PM + agents figure out execution through strategic dialogue.

## Example Flow

### Scenario: IPSA asks about infrastructure approach

**IPSA's Question:**
```
Which approach would you like to take for Phase 1?
A. Full GCP infrastructure setup
B. Local development environment first (Docker Compose)
C. Continue with detailed planning
D. Something else?
```

**PM's Multi-Round Dialogue:**

**Round 1**: PM analyzes question
```
PM thinks: "Need to understand project phase and constraints"
PM calls: read_file("AGENTS.md")
```

**Round 2**: PM checks dependencies
```
PM reads: AGENTS.md shows "prototyping phase, MVP focus"
PM calls: read_file("package.json")
```

**Round 3**: PM checks existing config
```
PM reads: package.json has no GCP dependencies
PM calls: grep("docker-compose|Dockerfile", ".")
```

**Round 4**: PM checks git state
```
PM finds: docker-compose.yml already in repo
PM calls: get_git_status()
```

**Round 5**: PM makes decision
```
PM decides: "B - Local development environment first"

Reasoning:
- AGENTS.md shows prototyping phase (not production yet)
- No GCP credentials in environment
- docker-compose.yml already exists in repo
- MVP focus suggests fast iteration over production setup
- Can defer GCP to Phase 3 when ready for production

Actions:
1. Use existing docker-compose.yml
2. Add local PostgreSQL service
3. Document environment setup
4. Create Phase 3 ticket for GCP migration

Risks:
- May need to restructure for cloud later
- Local dev differs from production environment

Mitigation:
- Use same PostgreSQL version as Cloud SQL
- Keep docker-compose close to production config
- Document cloud migration requirements
```

**Result**: Informed decision based on project context, not blind guessing.

## Architecture

### Files

- **`pm_conversation.py`**: Conversation manager
  - Creates conversation storage structure
  - Executes tools (read_file, grep, git, etc.)
  - Manages dialogue rounds and context

- **`pm_dialogue_processor.py`**: Multi-round processor
  - Calls GPT-4o with function calling
  - Orchestrates tool execution
  - Handles max rounds, timeouts, errors

- **`pm_decision_hook.py`**: Stop hook integration
  - Detects decision points in last message
  - Creates conversations (not simple queue files)
  - Triggers dialogue processor immediately

### Storage Structure

```
.claude/pm-queue/{request-id}/
├── request.json          # Original decision point + DIGEST
├── conversation.json     # All dialogue rounds with timestamps
└── context/              # Tool outputs
    ├── read_a3f2b1c8.txt     # File read results
    ├── grep_d7e4c5a2.txt     # Grep search results
    └── ...
```

**conversation.json** format:
```json
{
  "request_id": "pm-20251006-142530-a3f2b1c8",
  "rounds": [
    {
      "role": "system",
      "content": "Decision point:\n\nWhich approach...",
      "timestamp": "2025-10-06T14:25:30.123456"
    },
    {
      "role": "pm",
      "content": "Let me gather context before deciding...",
      "tools_used": [
        {"name": "read_file", "arguments": {"path": "AGENTS.md"}, "success": true}
      ],
      "timestamp": "2025-10-06T14:25:32.456789"
    },
    {
      "role": "tool",
      "content": "File: AGENTS.md\n\n# Project Vision...",
      "timestamp": "2025-10-06T14:25:33.123456"
    },
    ...
  ],
  "started_at": "2025-10-06T14:25:30.123456",
  "last_updated": "2025-10-06T14:25:45.789012"
}
```

## Available Tools

PM can call these tools during dialogue:

### 1. read_file
Read any file in the project (limited to 500 lines).

**Example:**
```python
read_file(path="AGENTS.md")
read_file(path="package.json")
read_file(path="src/services/auth.ts")
```

### 2. grep
Search codebase for patterns (regex supported, limited to 100 matches).

**Example:**
```python
grep(pattern="docker-compose", path=".")
grep(pattern="class.*Service", path="src/")
grep(pattern="TODO|FIXME", path=".")
```

### 3. list_files
List directory contents (max 200 items).

**Example:**
```python
list_files(path=".")
list_files(path="src/services/")
list_files(path=".claude/")
```

### 4. get_git_status
Check current git working tree state.

**Example:**
```python
get_git_status()
# Returns: Modified files, staged changes, untracked files
```

### 5. get_git_log
View recent commits (default: 10).

**Example:**
```python
get_git_log(limit=10)
get_git_log(limit=5)
```

### 6. make_decision
Make final strategic decision (ends dialogue).

**Example:**
```python
make_decision(
  decision="local_dev_first",
  reasoning="AGENTS.md shows prototyping phase...",
  actions=[
    "Use existing docker-compose.yml",
    "Add local PostgreSQL service",
    "Document environment setup"
  ],
  risks=["May need restructuring for cloud later"],
  mitigation=["Use same PostgreSQL version as Cloud SQL"],
  escalate_to_user=False,
  notes="Can defer GCP to Phase 3"
)
```

## Inline Intervention Mode (Proof-of-Concept)

For testing and POC projects, you can trigger PM **immediately** after any agent question, without waiting for session end.

### Quick Usage

```bash
# 1. Agent asks a question in Claude
# 2. Copy the question to clipboard
# 3. Run this command:
bash ~/.claude/hooks/pm_answer_now.sh

# PM will:
# - Read question from clipboard
# - Gather context (read files, grep, git status)
# - Make strategic decision
# - Copy resume instructions to clipboard
# - You paste into new session to continue
```

### Manual Trigger

```bash
# Trigger PM on specific question
python ~/.claude/hooks/pm_inline_trigger.py "Should I use Docker or GCP?"

# Or read from clipboard
python ~/.claude/hooks/pm_inline_trigger.py "$(pbpaste)"
```

### Use Cases

**Perfect for:**
- Proof-of-concept projects where you want rapid autonomous decisions
- Testing PM's reasoning capabilities
- Demonstrations of "vibe coding" workflow
- When you want PM to handle every agent question

**Not recommended for:**
- Production workflows (too disruptive)
- Interactive sessions where you're actively guiding
- When you want to answer some questions yourself

### Workflow

```
Agent: "Should I setup GCP (A) or Docker (B)?"
↓
You: Copy question → bash pm_answer_now.sh
↓
PM: Reads AGENTS.md, checks git, greps for config
↓
PM: Decides "B - Docker first" with reasoning
↓
You: Paste decision into new session
↓
Agent: Continues with PM's choice
```

## Configuration

### Environment Variables

```bash
# Required
export OPENAI_API_KEY=sk-proj-...

# PM Agent Control
export ENABLE_PM_AGENT=true              # Enable PM Agent (manual + autonomous modes)
export ENABLE_PM_AUTONOMOUS=true         # Enable automatic session-end triggering (optional)

# Optional
export PM_DIALOGUE_MODEL=gpt-4o          # Default: gpt-4o (can use o3 for complex)
export CLAUDE_PROJECT_DIR=/path/to/proj  # Default: current directory
```

### Feature Flag: ENABLE_PM_AUTONOMOUS

**Default behavior (ENABLE_PM_AUTONOMOUS not set or false):**
- PM Agent is available but does NOT trigger automatically
- Use `bash ~/.claude/hooks/pm_answer_now.sh` to trigger manually
- Perfect for POC/testing where you want control over when PM intervenes

**Autonomous mode (ENABLE_PM_AUTONOMOUS=true):**
- PM Agent triggers automatically when session ends with a question
- Original "vibe coding" vision - wake up to decisions, not questions
- Recommended once you trust PM's decision-making

**Migration path:**
```bash
# Phase 1: Test PM manually (default)
export ENABLE_PM_AGENT=true
# Use pm_answer_now.sh when agents ask questions

# Phase 2: Enable autonomous mode once confident
export ENABLE_PM_AUTONOMOUS=true
# PM now handles session-end questions automatically
```

### Model Selection

- **GPT-4o** (default): Strategic reasoning, tool orchestration
- **GPT-4o-mini**: Fallback if dialogue mode fails (single-round)
- **o3**: For extremely complex architectural decisions

Cost comparison:
- GPT-4o-mini (fallback): ~$0.0005 per decision (1 round)
- GPT-4o (dialogue): ~$0.005-0.02 per decision (3-7 rounds)
- o3 (complex): ~$0.05-0.15 per decision (higher reasoning)

## Testing

### Manual Test

```bash
cd ~/.claude/hooks
python test_pm_dialogue.py
```

This simulates IPSA asking about infrastructure approach (A/B/C/D).

Expected behavior:
1. PM reads AGENTS.md
2. PM checks package.json
3. PM greps for Docker/GCP config
4. PM checks git status
5. PM makes informed decision

### Review Conversation

After test:
```bash
# View decision
cat .claude/logs/pm-resume/resume-*.md

# View full conversation
cat .claude/pm-queue/processed/pm-*/conversation.json | jq .

# View tool outputs
ls .claude/pm-queue/processed/pm-*/context/
```

## Integration with Hooks

### Stop Hook Flow

1. **Session ends** with IPSA asking A/B/C/D question
2. **Stop hook** (`pm_decision_hook.py`) detects decision point
3. **Creates conversation** in `.claude/pm-queue/{id}/`
4. **Triggers dialogue processor** immediately (not launchd)
5. **PM reads context** (2-7 rounds typically)
6. **PM makes decision** and writes resume file
7. **Next session**: User pastes resume instructions

### Launchd Fallback

If immediate trigger fails:
- Launchd agent runs every 10 minutes
- Picks up conversations from `.claude/pm-queue/`
- Processes them using dialogue system
- Same multi-round capability

## Benefits

### 1. Context-Aware Decisions
- PM reads project files before deciding
- No blind guesses or generic advice
- Decisions align with actual codebase state

### 2. Strategic Reasoning
- GPT-4o for complex architectural choices
- Multi-round analysis (not rushed single-shot)
- Considers risks, mitigation, trade-offs

### 3. Transparent Process
- Full conversation history preserved
- Can review PM's reasoning chain
- Understand why decision was made

### 4. Vibe Coding Philosophy
- User sets high-level vision (AGENTS.md)
- PM handles strategic decisions
- Subagents handle implementation
- Autonomous overnight development

### 5. Graceful Degradation
- Falls back to single-round if dialogue fails
- Falls back to launchd if immediate trigger fails
- Robust error handling throughout

## Limitations

### Max Rounds: 10
Typically 3-7 rounds sufficient. Hard limit prevents infinite loops.

### Timeout: 120s
Enough for several tool calls. Prevents hanging indefinitely.

### Tool Constraints
- File reads: 500 lines max
- Grep results: 100 matches max
- All tools: 5-10s individual timeouts

### Sandboxing
- Tools only access files within project root
- No destructive operations (read-only)
- Safe for autonomous operation

## Cost Analysis

### Typical Decision Breakdown

**Simple decision** (3 rounds):
- Round 1: Read AGENTS.md (2k tokens)
- Round 2: Check package.json (1k tokens)
- Round 3: Make decision (1k tokens)
- **Total**: ~4k tokens = ~$0.005

**Complex decision** (7 rounds):
- Round 1: Read AGENTS.md (2k tokens)
- Round 2: Check package.json (1k tokens)
- Round 3: Grep for config (1k tokens)
- Round 4: Read docker-compose.yml (1k tokens)
- Round 5: Check git status (500 tokens)
- Round 6: Read src/services/* (2k tokens)
- Round 7: Make decision (2k tokens)
- **Total**: ~10k tokens = ~$0.015

### Cost Comparison

- **No PM Agent**: Free, but user must answer every question (breaks flow)
- **Single-round GPT-4o-mini**: $0.0005, but decisions lack context
- **Multi-round GPT-4o**: $0.005-0.02, but decisions are informed and strategic

**ROI**: One well-informed decision saves 10+ back-and-forth messages.

## Troubleshooting

### PM doesn't trigger

Check:
```bash
# Is ENABLE_PM_AGENT set?
echo $ENABLE_PM_AGENT  # Should be "true"

# Is OPENAI_API_KEY set?
echo $OPENAI_API_KEY | head -c 20  # Should show sk-proj-...

# Check hook logs
cat ~/.claude/logs/pm-decision-hook.log
```

### Dialogue fails immediately

Check:
```bash
# Type errors?
cd ~/.claude/hooks
mypy pm_dialogue_processor.py

# Import errors?
python -c "from pm_conversation import PMConversation"

# OpenAI package installed?
python -c "import openai; print(openai.__version__)"
```

### PM makes poor decisions

Improve context:
1. Update `AGENTS.md` with clearer vision
2. Add project-specific decision examples
3. Review past decisions in `.claude/logs/pm-decisions.json`
4. Consider switching to `PM_DIALOGUE_MODEL=o3` for complex cases

### Conversation too slow

Reduce rounds:
- PM may be gathering too much context
- Check conversation.json to see what tools were called
- Consider simplifying AGENTS.md (less to read)

### Timeout errors

Increase timeout:
```python
# In pm_decision_hook.py:
timeout=120  # Increase to 180 or 240 if needed
```

Or reduce tool outputs:
- File reads already limited to 500 lines
- Grep results limited to 100 matches
- Adjust in pm_conversation.py if needed

## Future Enhancements

### Potential Improvements

1. **Caching**: Cache file reads across conversations (avoid re-reading AGENTS.md every time)
2. **Streaming**: Show PM's thinking in real-time (not just final decision)
3. **Web search**: Add Perplexity tool for researching best practices
4. **Vector memory**: Search past decisions semantically
5. **User feedback loop**: Track decision quality, improve prompts

### Already Implemented (v1.2.0)

✅ Multi-round dialogue with tools
✅ GPT-4o function calling
✅ Conversation storage
✅ Graceful fallbacks
✅ Comprehensive testing
✅ Cost-optimized with limits

## See Also

- **CLAUDE.md** - Full orchestration framework (Hook #11)
- **CHANGELOG.md** - Version history (v1.2.0)
- **PM_AGENT_SETUP.md** - Setup instructions (deprecated by this doc)
- **test_pm_dialogue.py** - Test script

## Philosophy: Vibe Coding

> "The user sets the vibe (vision), the PM steers the ship, and the agents row the boat."

- **User**: High-level goals in AGENTS.md ("build MVP in 2 weeks")
- **PM**: Strategic decisions based on context ("start local, defer cloud")
- **Agents**: Implementation details (IPSA plans, IE codes, TA tests)

**Result**: Autonomous development without constant user input.

---

**Questions?** Check conversation history in `.claude/pm-queue/processed/` to see exactly what PM did.
