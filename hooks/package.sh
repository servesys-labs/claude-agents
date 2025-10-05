#!/usr/bin/env bash
###
# Package Claude Code Orchestration Framework for distribution
#
# Creates a distributable tarball with all components
###

set -euo pipefail

PACKAGE_NAME="claude-orchestration-framework"
VERSION="1.2.5"
PACKAGE_DIR="/tmp/${PACKAGE_NAME}"
OUTPUT_FILE="${HOME}/Downloads/${PACKAGE_NAME}-${VERSION}.tar.gz"

echo "📦 Packaging Claude Code Orchestration Framework v${VERSION}"
echo ""

# Clean previous package
rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"

# Copy hook scripts
echo "Copying hook scripts..."
mkdir -p "$PACKAGE_DIR/hooks"
cp ~/claude-hooks/*.py "$PACKAGE_DIR/hooks/" 2>/dev/null || true
cp ~/claude-hooks/ready-to-merge.sh "$PACKAGE_DIR/hooks/" 2>/dev/null || true
chmod +x "$PACKAGE_DIR/hooks"/*.py
chmod +x "$PACKAGE_DIR/hooks"/*.sh

# Copy agent definitions
echo "Copying agent definitions..."
mkdir -p "$PACKAGE_DIR/agents"
cp ~/.claude/agents/*.md "$PACKAGE_DIR/agents/" 2>/dev/null || true

# Copy global CLAUDE.md
echo "Copying global configuration..."
cp ~/.claude/CLAUDE.md "$PACKAGE_DIR/" 2>/dev/null || true

# Copy settings.json
cp ~/.claude/settings.json "$PACKAGE_DIR/" 2>/dev/null || true

# Copy MCP servers
echo "Copying MCP servers..."
if [ -d ~/.claude/mcp-servers/openai-bridge ]; then
    mkdir -p "$PACKAGE_DIR/mcp-servers"
    cp -r ~/.claude/mcp-servers/openai-bridge "$PACKAGE_DIR/mcp-servers/"
    # Remove node_modules and build artifacts (user will rebuild)
    rm -rf "$PACKAGE_DIR/mcp-servers/openai-bridge/node_modules"
    rm -rf "$PACKAGE_DIR/mcp-servers/openai-bridge/dist"
fi

# Copy installer
cp ~/claude-hooks/install.sh "$PACKAGE_DIR/"
chmod +x "$PACKAGE_DIR/install.sh"

# Create README
cat > "$PACKAGE_DIR/README.md" << 'EOF'
# Claude Code Orchestration Framework

**Version**: 1.0.0
**Date**: October 2025

## What's Included

### Core Components
- **40+ Specialized Agents**: Implementation planner, requirements clarifier, code navigator, implementation engineer, test author, security auditor, and more
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

## Installation

### Quick Install
```bash
cd claude-orchestration-framework-1.0.0
bash install.sh
```

### What the Installer Does
1. **Backs up** existing installation (if any)
2. **Installs hooks** to `~/claude-hooks/`
3. **Installs agents** to `~/.claude/agents/`
4. **Configures** settings.json (with merge option)
5. **Sets up** environment variables
6. **Optionally installs** MCP servers

### Manual Installation
If you prefer manual installation:

1. Copy hooks:
   ```bash
   cp -r hooks/* ~/claude-hooks/
   chmod +x ~/claude-hooks/*.py ~/claude-hooks/*.sh
   ```

2. Copy agents:
   ```bash
   cp -r agents/* ~/.claude/agents/
   ```

3. Copy global config:
   ```bash
   cp CLAUDE.md ~/.claude/
   ```

4. Merge settings.json with your existing `~/.claude/settings.json`

5. Add to your shell RC file:
   ```bash
   export CLAUDE_PROJECT_ROOT="$(pwd)"
   ```

## Post-Installation

### 1. Set Up API Keys (Optional)
For multi-model brainstorming and live data searches:

```bash
export OPENAI_API_KEY='sk-...'
export PERPLEXITY_API_KEY='pplx-...'
```

### 2. Create FEATURE_MAP.md in Your Project
```bash
cd ~/your-project
cp ~/claude-hooks/FEATURE_MAP.template.md FEATURE_MAP.md
```

Edit FEATURE_MAP.md to track your project's features and pivots.

### 3. Test the Installation
```bash
# Check hooks are working
python3 ~/claude-hooks/checkpoint_manager.py list

# Run pre-merge check
cd ~/your-project
bash ~/claude-hooks/ready-to-merge.sh
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
- **Hook Scripts**: `~/claude-hooks/*.py`
- **Project Template**: `~/claude-hooks/FEATURE_MAP.template.md`

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
EOF

# Create version file
cat > "$PACKAGE_DIR/VERSION" << EOF
VERSION=1.0.0
DATE=$(date +%Y-%m-%d)
COMPONENTS=hooks,agents,mcp-servers,config
EOF

# Create archive
echo ""
echo "Creating archive..."
cd /tmp
tar -czf "$OUTPUT_FILE" "${PACKAGE_NAME}-${VERSION}"

# Cleanup
rm -rf "$PACKAGE_DIR"

# Summary
echo ""
echo "✅ Package created successfully!"
echo ""
echo "📦 Output: $OUTPUT_FILE"
echo "📊 Size: $(du -h "$OUTPUT_FILE" | cut -f1)"
echo ""
echo "To share with your team:"
echo "  1. Upload ${OUTPUT_FILE} to shared location"
echo "  2. Team members download and extract"
echo "  3. Run: bash install.sh"
echo ""
