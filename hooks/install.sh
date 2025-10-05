#!/usr/bin/env bash
###
# Claude Code Orchestration Framework - Installer
#
# Installs the complete orchestration framework with:
# - 40+ specialized agents
# - 12+ automation hooks
# - Pivot tracking system
# - Multi-model brainstorming
# - Cost tracking for external APIs
# - Pre-merge quality gates
# - And more!
#
# Usage:
#   curl -fsSL https://your-url/install.sh | bash
#   OR
#   bash install.sh
###

set -euo pipefail

INSTALL_DIR="${HOME}/.claude"
HOOKS_DIR="${HOME}/claude-hooks"
BACKUP_DIR="${HOME}/.claude-backup-$(date +%Y%m%d-%H%M%S)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════════════════╗
║   Claude Code Orchestration Framework Installer      ║
║   Version 1.0.0 - October 2025                        ║
╚═══════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is required but not installed${NC}"
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo -e "${RED}Error: git is required but not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}' | cut -d. -f1,2)
if (( $(echo "$PYTHON_VERSION < 3.8" | bc -l) )); then
    echo -e "${RED}Error: Python 3.8+ is required (found $PYTHON_VERSION)${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites met${NC}"
echo ""

# Backup existing installation
if [ -d "$HOOKS_DIR" ] || [ -d "$INSTALL_DIR/agents" ]; then
    echo -e "${YELLOW}Existing installation detected${NC}"
    read -p "Create backup before installing? (recommended) [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo -e "${BLUE}Creating backup at $BACKUP_DIR...${NC}"
        mkdir -p "$BACKUP_DIR"
        [ -d "$HOOKS_DIR" ] && cp -r "$HOOKS_DIR" "$BACKUP_DIR/claude-hooks"
        [ -d "$INSTALL_DIR/agents" ] && cp -r "$INSTALL_DIR/agents" "$BACKUP_DIR/agents"
        [ -f "$INSTALL_DIR/settings.json" ] && cp "$INSTALL_DIR/settings.json" "$BACKUP_DIR/"
        [ -f "$INSTALL_DIR/CLAUDE.md" ] && cp "$INSTALL_DIR/CLAUDE.md" "$BACKUP_DIR/"
        echo -e "${GREEN}✓ Backup created${NC}"
    fi
fi

# Create directories
echo -e "${BLUE}Creating directory structure...${NC}"
mkdir -p "$HOOKS_DIR"/{logs,agents}
mkdir -p "$INSTALL_DIR"/{agents,mcp-servers}

# Detect package location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Copy hook scripts
echo -e "${BLUE}Installing hook scripts...${NC}"
HOOK_FILES=(
    "pretooluse_validate.py"
    "posttooluse_validate.py"
    "checkpoint_manager.py"
    "pivot_detector.py"
    "feature_map_validator.py"
    "log_analyzer.py"
    "task_digest_capture.py"
    "precompact_summary.py"
    "stop_digest.py"
    "gpt5_cost_tracker.py"
    "perplexity_tracker.py"
    "md_spam_preventer.py"
    "grep_summarizer.py"
    "tool_output_compactor.py"
    "context_metrics.py"
)

for file in "${HOOK_FILES[@]}"; do
    if [ -f "$SCRIPT_DIR/$file" ]; then
        cp "$SCRIPT_DIR/$file" "$HOOKS_DIR/"
        chmod +x "$HOOKS_DIR/$file"
        echo "  ✓ $file"
    else
        echo -e "  ${YELLOW}⚠ $file not found (skipping)${NC}"
    fi
done

# Copy agent definitions
echo -e "${BLUE}Installing agent definitions...${NC}"
if [ -d "$SCRIPT_DIR/agents" ]; then
    cp -r "$SCRIPT_DIR/agents/"*.md "$INSTALL_DIR/agents/" 2>/dev/null || true
    AGENT_COUNT=$(ls -1 "$INSTALL_DIR/agents"/*.md 2>/dev/null | wc -l)
    echo "  ✓ Installed $AGENT_COUNT agents"
else
    echo -e "  ${YELLOW}⚠ No agents directory found${NC}"
fi

# Copy global CLAUDE.md
echo -e "${BLUE}Installing global configuration...${NC}"
if [ -f "$SCRIPT_DIR/CLAUDE.md" ]; then
    cp "$SCRIPT_DIR/CLAUDE.md" "$INSTALL_DIR/"
    echo "  ✓ CLAUDE.md"
else
    echo -e "  ${YELLOW}⚠ CLAUDE.md not found${NC}"
fi

# Install/update settings.json
echo -e "${BLUE}Configuring hooks...${NC}"
SETTINGS_FILE="$INSTALL_DIR/settings.json"

if [ -f "$SCRIPT_DIR/settings.json" ]; then
    if [ -f "$SETTINGS_FILE" ]; then
        echo -e "  ${YELLOW}Existing settings.json found${NC}"
        read -p "  Merge with existing settings? [Y/n] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
            # Backup existing
            cp "$SETTINGS_FILE" "$SETTINGS_FILE.backup"
            # Copy new (user can manually merge later)
            cp "$SCRIPT_DIR/settings.json" "$SETTINGS_FILE"
            echo -e "  ${GREEN}✓ Settings updated (backup saved as settings.json.backup)${NC}"
        fi
    else
        cp "$SCRIPT_DIR/settings.json" "$SETTINGS_FILE"
        echo "  ✓ settings.json"
    fi
fi

# Install ready-to-merge script
if [ -f "$SCRIPT_DIR/ready-to-merge.sh" ]; then
    cp "$SCRIPT_DIR/ready-to-merge.sh" "$HOOKS_DIR/"
    chmod +x "$HOOKS_DIR/ready-to-merge.sh"
    echo "  ✓ ready-to-merge.sh"
fi

# Set up environment variables
echo -e "${BLUE}Configuring environment...${NC}"

SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ]; then
    if ! grep -q "CLAUDE_PROJECT_ROOT" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# Claude Code Orchestration Framework" >> "$SHELL_RC"
        echo 'export CLAUDE_PROJECT_ROOT="$(pwd)"' >> "$SHELL_RC"
        echo -e "  ${GREEN}✓ Added CLAUDE_PROJECT_ROOT to $SHELL_RC${NC}"
    fi
fi

# Install MCP servers (optional)
echo ""
read -p "Install MCP servers (OpenAI Bridge, Perplexity)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Installing MCP servers...${NC}"

    # OpenAI Bridge
    if [ -d "$SCRIPT_DIR/mcp-servers/openai-bridge" ]; then
        cp -r "$SCRIPT_DIR/mcp-servers/openai-bridge" "$INSTALL_DIR/mcp-servers/"
        cd "$INSTALL_DIR/mcp-servers/openai-bridge"
        npm install --production &>/dev/null && npm run build &>/dev/null
        echo "  ✓ OpenAI Bridge MCP server"
    fi

    echo -e "${YELLOW}  Note: You'll need to configure API keys manually${NC}"
    echo "  - OPENAI_API_KEY for OpenAI Bridge"
    echo "  - PERPLEXITY_API_KEY for Perplexity"
fi

# Create example FEATURE_MAP.md template
echo -e "${BLUE}Creating project templates...${NC}"
cat > "$HOOKS_DIR/FEATURE_MAP.template.md" << 'TEMPLATE_EOF'
# FEATURE_MAP.md

**Purpose**: Living source of truth for project direction
**Last Updated**: $(date +%Y-%m-%d)

---

## 🎯 Active Features (Currently Supported)

| Feature | Status | Files | Description |
|---------|--------|-------|-------------|
| Example Feature | ✅ Active | `src/example.ts` | Description |

---

## 🗄️ Deprecated Features (No Longer Supported)

| Feature | Deprecated Date | Reason | Replaced By | Files to Remove |
|---------|----------------|--------|-------------|-----------------|
| - | - | - | - | - |

---

## 🔄 Pivot History

### YYYY-MM-DD: Initial Setup
**Changes**: Project initialized
**Files**: -

---

## 🗺️ Feature Mapping

(Add workflow diagrams, feature dependencies, etc.)
TEMPLATE_EOF

echo "  ✓ FEATURE_MAP.template.md"

# Final instructions
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          Installation Complete! 🎉                    ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo "1. Restart your terminal (or run: source $SHELL_RC)"
echo ""
echo "2. Copy FEATURE_MAP template to your project:"
echo "   ${YELLOW}cp ~/claude-hooks/FEATURE_MAP.template.md ~/your-project/FEATURE_MAP.md${NC}"
echo ""
echo "3. (Optional) Set up API keys for MCP servers:"
echo "   ${YELLOW}export OPENAI_API_KEY='sk-...'${NC}"
echo "   ${YELLOW}export PERPLEXITY_API_KEY='pplx-...'${NC}"
echo ""
echo "4. Start using Claude Code with orchestration framework!"
echo ""
echo -e "${BLUE}Documentation:${NC}"
echo "  - Global config: ${YELLOW}~/.claude/CLAUDE.md${NC}"
echo "  - Hooks: ${YELLOW}~/claude-hooks/*.py${NC}"
echo "  - Agents: ${YELLOW}~/.claude/agents/*.md${NC}"
echo ""
echo -e "${BLUE}Quick Commands:${NC}"
echo "  - Pre-merge check: ${YELLOW}bash ~/claude-hooks/ready-to-merge.sh${NC}"
echo "  - List checkpoints: ${YELLOW}python3 ~/claude-hooks/checkpoint_manager.py list${NC}"
echo ""
echo -e "${GREEN}Happy coding! 🚀${NC}"
echo ""
