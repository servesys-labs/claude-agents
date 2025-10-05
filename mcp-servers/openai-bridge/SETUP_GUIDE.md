# Multi-Model Brainstorming Setup Guide

This guide will help you set up Claude + GPT-5 multi-model brainstorming.

## Step 1: Get OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with `sk-...`)
4. **Note:** ChatGPT Plus/Max subscription is separate from API access - you need to add credits separately

## Step 2: Add API Credits (if needed)

1. Go to https://platform.openai.com/account/billing
2. Click "Add to credit balance"
3. Add $10-20 (will last for hundreds of brainstorm sessions)

**Cost estimate:**
- GPT-4o (default): ~$0.08 per brainstorm session
- GPT-5-turbo: ~$0.12 per session
- GPT-5: ~$0.20 per session

## Step 3: Install MCP Server

```bash
cd ~/.claude/mcp-servers/openai-bridge
npm install
npm run build
```

## Step 4: Configure Environment Variable

Add to your shell profile (`~/.zshrc` or `~/.bashrc`):

```bash
export OPENAI_API_KEY="sk-your-key-here"
```

Then reload:
```bash
source ~/.zshrc  # or source ~/.bashrc
```

Verify:
```bash
echo $OPENAI_API_KEY  # Should print your key
```

## Step 5: Configure Claude Settings

The MCP server should already be configured in `~/.claude/settings.json`. Verify it exists:

```bash
cat ~/.claude/settings.json | grep -A 10 "mcpServers"
```

Should show:
```json
{
  "mcpServers": {
    "openai-bridge": {
      "command": "node",
      "args": ["/Users/agentsy/.claude/mcp-servers/openai-bridge/dist/index.js"],
      "env": {
        "OPENAI_API_KEY": "${OPENAI_API_KEY}"
      }
    }
  }
}
```

If not present, add it.

## Step 6: Restart Claude Code

Close and reopen Claude Code (web or Cursor extension).

## Step 7: Test the Setup

In Claude Code, type:

```
Brainstorm: What's the best approach for implementing a rate limiter?
```

You should see:
```
============================================================
🧠 MULTI-MODEL BRAINSTORMING OPPORTUNITY
============================================================

Detected brainstorming request for strategic planning.

💡 RECOMMENDATION: Invoke multi-model-brainstormer agent

This will:
  1. Get Claude's initial perspective (this session)
  2. Call GPT-5 for alternative viewpoints
  3. Facilitate 2-4 rounds of dialogue
  4. Synthesize insights from both models

Command:
  Task tool → subagent: 'multi-model-brainstormer'
  Prompt: [your brainstorming question]

Cost: ~$0.08-0.14 per brainstorm session

Best for: IPSA, RC, CN, API Architect, DB Modeler, UX Designer
Skip for: IE, TA, PRV (execution tasks)

============================================================
```

## How to Use

### Automatic Detection

The log_analyzer hook automatically detects brainstorming requests when you use trigger words:

**Trigger words:**
- "brainstorm"
- "@gpt5"
- "compare models"
- "get both perspectives"
- "explore alternatives"

**Combined with planning keywords:**
- "architecture"
- "design"
- "approach"
- "trade-offs"
- "pros and cons"

### Manual Invocation

You can also manually invoke the agent:

```
Please use the multi-model-brainstormer agent to explore different approaches for [your question]
```

### Example Sessions

**Example 1: Architecture Decision**
```
User: "Brainstorm: Should I use microservices or monolith for my SaaS?"

Claude Code:
1. Detects "brainstorm" + "should i"
2. Suggests multi-model-brainstormer
3. You confirm
4. Agent orchestrates:
   - Claude: Initial analysis (monolith first, migrate later)
   - GPT-5: Alternative view (microservices from start if team is distributed)
   - Claude: Refinement (hybrid - modular monolith)
   - Synthesis: Modular monolith with clear service boundaries
```

**Example 2: Database Design**
```
User: "What are the trade-offs between PostgreSQL and MongoDB for our analytics platform?"

Claude Code:
1. Detects "trade-offs" (planning keyword)
2. Suggests multi-model-brainstormer
3. Agent orchestrates:
   - Claude: PostgreSQL for ACID + timescale extension
   - GPT-5: MongoDB for flexible schema + aggregation pipeline
   - Synthesis: PostgreSQL for core data + MongoDB for unstructured logs
```

## Troubleshooting

### Error: "OpenAI API error: Incorrect API key"

**Solution:**
```bash
# Check if env var is set
echo $OPENAI_API_KEY

# If empty, add to shell profile
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.zshrc
source ~/.zshrc

# Restart Claude Code
```

### Error: "Insufficient credits"

**Solution:**
- Go to https://platform.openai.com/account/billing
- Add credits ($10-20 recommended)
- Note: ChatGPT subscription doesn't include API credits

### Error: "Model gpt-5 not found"

**Solution:**
- GPT-5 might not be released yet
- Edit `~/.claude/agents/multi-model-brainstormer.md`
- Change default model from "gpt-5" to "gpt-4o"
- Or wait for GPT-5 official release

### MCP Server Not Showing Up

**Solution:**
```bash
# Verify build succeeded
cd ~/.claude/mcp-servers/openai-bridge
npm run build

# Check dist folder exists
ls -la dist/

# Restart Claude Code completely
```

### Hook Not Detecting Brainstorm

**Solution:**
- Make sure you use trigger words: "brainstorm", "@gpt5", etc.
- Must also include planning keywords: "architecture", "should i", "trade-offs"
- Example: "Brainstorm: What architecture should I use?" ✅
- Example: "brainstorm" (alone) ❌

## Cost Monitoring

Check your usage anytime:

```
Use the mcp__openai-bridge__get_usage_stats tool
```

Returns:
```json
{
  "total_tokens": 5230,
  "total_cost": 0.1846,
  "formatted_cost": "$0.1846"
}
```

## Best Practices

1. **Use for strategic decisions only** - Don't waste tokens on simple questions
2. **High-level agents only** - IPSA, RC, CN, API Architect, DB Modeler, UX Designer
3. **Skip for execution** - Don't use for IE, TA, PRV (just write the code)
4. **Monitor costs** - Check `get_usage_stats` regularly
5. **Use GPT-4o by default** - 3x cheaper than GPT-5, excellent quality

## Next Steps

Now that setup is complete, try brainstorming on:
- Architecture decisions
- Database schema design
- API design patterns
- UX flow alternatives
- Technical trade-offs

The multi-model approach will give you richer, more thoroughly explored solutions!
