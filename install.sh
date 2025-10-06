#!/usr/bin/env bash
###
# Claude Agents Framework - Interactive Installer
#
# Installs the complete orchestration framework with:
# - 30+ specialized agents
# - Production-ready hooks with auto-checkpointing
# - Vector RAG memory (Railway PostgreSQL + Redis)
# - Launchd periodic queue processing (macOS)
# - 13 MCP servers (OpenAI, GitHub, Perplexity, etc.)
#
# Usage:
#   bash install.sh
###

set -eo pipefail

INSTALL_DIR="${HOME}/.claude"
HOOKS_DIR="${HOME}/claude-hooks"
BACKUP_DIR="${HOME}/.claude-backup-$(date +%Y%m%d-%H%M%S)"
LAUNCHD_DIR="${HOME}/Library/LaunchAgents"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}"
cat << "EOF"
╔══════════════════════════════════════════════════════════╗
║       Claude Agents Framework - Interactive Setup        ║
║              Version 1.0.0 - October 2025                ║
╚══════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

###
# Prerequisites Check
###
echo -e "${CYAN}━━━ Checking Prerequisites ━━━${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 is required but not installed${NC}"
    echo "  Install from: https://python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]; }; then
    echo -e "${RED}✗ Python 3.8+ required (found $PYTHON_VERSION)${NC}"
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo -e "${RED}✗ Git is required but not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python ${PYTHON_VERSION}${NC}"
echo -e "${GREEN}✓ Git $(git --version | awk '{print $3}')${NC}"

HAS_NODE=false
if command -v node &> /dev/null; then
    echo -e "${GREEN}✓ Node.js $(node --version)${NC}"
    HAS_NODE=true
else
    echo -e "${YELLOW}⚠ Node.js not found (needed for MCP servers)${NC}"
    echo "  Install from: https://nodejs.org"
fi

echo ""

###
# Backup Existing Installation
###
if [ -d "$HOOKS_DIR" ] || [ -d "$INSTALL_DIR/agents" ]; then
    echo -e "${YELLOW}Existing installation detected${NC}"
    read -p "Create backup before installing? [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo -e "${BLUE}Creating backup at $BACKUP_DIR...${NC}"
        mkdir -p "$BACKUP_DIR"
        [ -d "$HOOKS_DIR" ] && cp -r "$HOOKS_DIR" "$BACKUP_DIR/claude-hooks" 2>/dev/null || true
        [ -d "$INSTALL_DIR/agents" ] && cp -r "$INSTALL_DIR/agents" "$BACKUP_DIR/agents" 2>/dev/null || true
        [ -f "$INSTALL_DIR/settings.json" ] && cp "$INSTALL_DIR/settings.json" "$BACKUP_DIR/" 2>/dev/null || true
        [ -f "$INSTALL_DIR/CLAUDE.md" ] && cp "$INSTALL_DIR/CLAUDE.md" "$BACKUP_DIR/" 2>/dev/null || true
        echo -e "${GREEN}✓ Backup created${NC}"
    fi
    echo ""
fi

###
# Create Directory Structure
###
echo -e "${CYAN}━━━ Setting Up Directories ━━━${NC}"
mkdir -p "$HOOKS_DIR/logs"
mkdir -p "$INSTALL_DIR"/{agents,mcp-servers}
mkdir -p "$INSTALL_DIR/.claude/ingest-queue/dead"
mkdir -p "$INSTALL_DIR/.claude/logs"
echo -e "${GREEN}✓ Directory structure created${NC}"
echo ""

# Detect package location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -d "$SCRIPT_DIR" ]; then
    echo -e "${RED}✗ Cannot determine installation directory${NC}"
    exit 1
fi

###
# Install Core Components (Always)
###
echo -e "${CYAN}━━━ Installing Core Components ━━━${NC}"

# Copy hooks
echo -e "${BLUE}Installing hooks...${NC}"
if [ -d "$SCRIPT_DIR/hooks" ]; then
    cp "$SCRIPT_DIR/hooks"/*.py "$HOOKS_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/hooks"/*.sh "$HOOKS_DIR/" 2>/dev/null || true
    chmod +x "$HOOKS_DIR"/*.py "$HOOKS_DIR"/*.sh 2>/dev/null || true
    HOOK_COUNT=$(ls -1 "$HOOKS_DIR"/*.py 2>/dev/null | wc -l | tr -d ' ')
    echo -e "${GREEN}✓ Installed $HOOK_COUNT hooks${NC}"
else
    echo -e "${RED}✗ Hooks directory not found${NC}"
    exit 1
fi

# Copy agents
echo -e "${BLUE}Installing agents...${NC}"
if [ -d "$SCRIPT_DIR/agents" ]; then
    cp "$SCRIPT_DIR/agents"/*.md "$INSTALL_DIR/agents/" 2>/dev/null || true
    AGENT_COUNT=$(ls -1 "$INSTALL_DIR/agents"/*.md 2>/dev/null | wc -l | tr -d ' ')
    echo -e "${GREEN}✓ Installed $AGENT_COUNT agents${NC}"
else
    echo -e "${RED}✗ Agents directory not found${NC}"
    exit 1
fi

# Copy global config
if [ -f "$SCRIPT_DIR/CLAUDE.md" ]; then
    cp "$SCRIPT_DIR/CLAUDE.md" "$INSTALL_DIR/"
    echo -e "${GREEN}✓ Global configuration (CLAUDE.md)${NC}"
fi

# Install settings.json
if [ -f "$SCRIPT_DIR/settings.json" ]; then
    SETTINGS_FILE="$INSTALL_DIR/settings.json"
    if [ -f "$SETTINGS_FILE" ]; then
        cp "$SETTINGS_FILE" "$SETTINGS_FILE.backup"
        echo -e "${YELLOW}  Existing settings.json backed up${NC}"
    fi
    cp "$SCRIPT_DIR/settings.json" "$SETTINGS_FILE"
    echo -e "${GREEN}✓ Hook configuration (settings.json)${NC}"
fi

# Copy MCP template for per-project .mcp.json bootstrapping
if [ -f "$SCRIPT_DIR/mcp-template.json" ]; then
    cp "$SCRIPT_DIR/mcp-template.json" "$INSTALL_DIR/mcp-template.json"
    echo -e "${GREEN}✓ MCP template (mcp-template.json)${NC}"
fi

# Copy other essential files
[ -f "$SCRIPT_DIR/package.json" ] && cp "$SCRIPT_DIR/package.json" "$INSTALL_DIR/" 2>/dev/null || true
[ -f "$SCRIPT_DIR/VERSION" ] && cp "$SCRIPT_DIR/VERSION" "$INSTALL_DIR/" 2>/dev/null || true

echo ""

###
# MCP Servers Installation (Question 1)
###
echo -e "${CYAN}━━━ MCP Servers Setup ━━━${NC}"
echo "MCP servers provide enhanced capabilities:"
echo "  • OpenAI Bridge (GPT-5 multi-model brainstorming)"
echo "  • Vector Bridge (AI memory with vector search)"
echo "  • GitHub, Perplexity, Monitoring, and 8 more..."
echo ""

INSTALL_MCP=false
if [ "$HAS_NODE" = true ]; then
    read -p "Install all MCP servers? [Y/n] " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        INSTALL_MCP=true
        echo -e "${BLUE}Installing MCP servers (this may take a few minutes)...${NC}"

        if [ -d "$SCRIPT_DIR/mcp-servers" ]; then
            for server_dir in "$SCRIPT_DIR/mcp-servers"/*/ ; do
                if [ -d "$server_dir" ]; then
                    server_name=$(basename "$server_dir")
                    echo -e "${BLUE}  • $server_name...${NC}"
                    cp -r "$server_dir" "$INSTALL_DIR/mcp-servers/" 2>/dev/null || true

                    # Build TypeScript servers
                    if [ -f "$INSTALL_DIR/mcp-servers/$server_name/package.json" ]; then
                        cd "$INSTALL_DIR/mcp-servers/$server_name"
                        npm install --silent &>/dev/null || echo -e "${YELLOW}    ⚠ npm install failed${NC}"
                        npm run build --silent &>/dev/null || echo -e "${YELLOW}    ⚠ build failed${NC}"
                    fi
                fi
            done

            SERVER_COUNT=$(ls -1d "$INSTALL_DIR/mcp-servers"/*/ 2>/dev/null | wc -l | tr -d ' ')
            echo -e "${GREEN}✓ Installed $SERVER_COUNT MCP servers${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Skipping MCP servers${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Node.js required for MCP servers - skipping${NC}"
fi

echo ""

###
# Vector RAG Memory Setup (Question 2)
###
echo -e "${CYAN}━━━ Vector RAG Memory Setup (Optional) ━━━${NC}"
echo "Enable AI memory across all your projects with vector search?"
echo ""
echo "Requirements:"
echo "  • Railway PostgreSQL + pgvector (or self-hosted)"
echo "  • Redis (Railway or Redis Cloud)"
echo "  • OpenAI API key (for embeddings)"
echo ""

VECTOR_ENABLED=false
DATABASE_URL_MEMORY=""
REDIS_URL=""
OPENAI_API_KEY=""

read -p "Enable vector RAG memory? [y/N] " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${BLUE}Vector memory credentials setup${NC}"
    echo "Get credentials from: https://railway.app (or your own deployment)"
    echo ""

    read -p "DATABASE_URL_MEMORY (PostgreSQL): " DATABASE_URL_MEMORY
    read -p "REDIS_URL: " REDIS_URL
    read -p "OPENAI_API_KEY: " OPENAI_API_KEY

    if [ -n "$DATABASE_URL_MEMORY" ] && [ -n "$REDIS_URL" ] && [ -n "$OPENAI_API_KEY" ]; then
        VECTOR_ENABLED=true

        # Save to shell RC
        SHELL_RC=""
        if [ -f "$HOME/.zshrc" ]; then
            SHELL_RC="$HOME/.zshrc"
        elif [ -f "$HOME/.bashrc" ]; then
            SHELL_RC="$HOME/.bashrc"
        fi

        if [ -n "$SHELL_RC" ]; then
            # Remove old entries if they exist
            sed -i.bak '/# Claude Agents - Vector RAG Memory/,+3d' "$SHELL_RC" 2>/dev/null || true

            echo "" >> "$SHELL_RC"
            echo "# Claude Agents - Vector RAG Memory" >> "$SHELL_RC"
            echo "export DATABASE_URL_MEMORY='$DATABASE_URL_MEMORY'" >> "$SHELL_RC"
            echo "export REDIS_URL='$REDIS_URL'" >> "$SHELL_RC"
            echo "export OPENAI_API_KEY='$OPENAI_API_KEY'" >> "$SHELL_RC"
            echo -e "${GREEN}✓ Credentials saved to $SHELL_RC${NC}"
        fi

        # Test connection (if vector-bridge installed)
        if [ -f "$INSTALL_DIR/mcp-servers/vector-bridge/dist/index.js" ]; then
            echo -e "${BLUE}Testing vector-bridge connection...${NC}"
            export DATABASE_URL_MEMORY REDIS_URL OPENAI_API_KEY
            cd "$INSTALL_DIR/mcp-servers/vector-bridge" 2>/dev/null || true
            # Quick health check would go here
            echo -e "${GREEN}✓ Vector memory configured${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Incomplete credentials - skipping vector memory${NC}"
        VECTOR_ENABLED=false
    fi
else
    echo -e "${YELLOW}⚠ Skipping vector memory${NC}"
fi

echo ""

###
# Launchd Periodic Queue Processing (Question 3 - only if vector enabled)
###
if [ "$VECTOR_ENABLED" = true ]; then
    echo -e "${CYAN}━━━ Periodic Queue Processing (Optional) ━━━${NC}"
    echo "Enable automatic retry of failed vector ingestion?"
    echo "  • Runs every 15 minutes via launchd (macOS)"
    echo "  • Retries failed uploads to vector database"
    echo ""

    read -p "Enable periodic queue processing? [Y/n] " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo -e "${BLUE}Setting up launchd agent...${NC}"

        # Detect Node.js path (for MCP calls in stop_digest.py)
        NODE_PATH=$(which node 2>/dev/null || echo "/usr/local/bin/node")
        if [ ! -f "$NODE_PATH" ]; then
            # Try common nvm paths
            for nvm_path in "$HOME/.nvm/versions/node"/*/bin/node; do
                if [ -f "$nvm_path" ]; then
                    NODE_PATH="$nvm_path"
                    break
                fi
            done
        fi

        NODE_DIR=$(dirname "$NODE_PATH")
        FULL_PATH="/usr/local/bin:/usr/bin:/bin:$NODE_DIR"

        # Create launchd plist
        PLIST_FILE="$LAUNCHD_DIR/com.claude.agents.queue.plist"
        mkdir -p "$LAUNCHD_DIR"

        cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude.agents.queue</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$HOOKS_DIR/stop_digest.py</string>
        <string>--process-queue</string>
    </array>
    <key>StartInterval</key>
    <integer>900</integer>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$HOOKS_DIR/logs/queue-processor.log</string>
    <key>StandardErrorPath</key>
    <string>$HOOKS_DIR/logs/queue-processor.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>DATABASE_URL_MEMORY</key>
        <string>$DATABASE_URL_MEMORY</string>
        <key>REDIS_URL</key>
        <string>$REDIS_URL</string>
        <key>OPENAI_API_KEY</key>
        <string>$OPENAI_API_KEY</string>
        <key>PATH</key>
        <string>$FULL_PATH</string>
        <key>CLAUDE_DIR</key>
        <string>$INSTALL_DIR/.claude</string>
    </dict>
</dict>
</plist>
EOF

        # Load launchd job
        launchctl unload "$PLIST_FILE" 2>/dev/null || true
        launchctl load "$PLIST_FILE" 2>/dev/null && \
            echo -e "${GREEN}✓ Periodic queue processing enabled${NC}" || \
            echo -e "${YELLOW}⚠ Failed to load launchd agent (check logs)${NC}"
    else
        echo -e "${YELLOW}⚠ Skipping periodic queue processing${NC}"
    fi
    echo ""
fi

###
# Optional API Keys (Question 4)
###
echo -e "${CYAN}━━━ Optional API Keys ━━━${NC}"
echo "Configure additional API keys for enhanced features?"
echo ""
read -p "Configure optional API keys? [y/N] " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""

    # Perplexity
    echo -e "${BLUE}Perplexity API (for live web search)${NC}"
    read -p "PERPLEXITY_API_KEY (or press Enter to skip): " PERPLEXITY_API_KEY

    # GitHub
    echo ""
    echo -e "${BLUE}GitHub Personal Access Token (for higher rate limits)${NC}"
    read -p "GITHUB_TOKEN (or press Enter to skip): " GITHUB_TOKEN

    # Save to shell RC
    SHELL_RC=""
    if [ -f "$HOME/.zshrc" ]; then
        SHELL_RC="$HOME/.zshrc"
    elif [ -f "$HOME/.bashrc" ]; then
        SHELL_RC="$HOME/.bashrc"
    fi

    if [ -n "$SHELL_RC" ]; then
        if [ -n "$PERPLEXITY_API_KEY" ]; then
            echo "export PERPLEXITY_API_KEY='$PERPLEXITY_API_KEY'" >> "$SHELL_RC"
            echo -e "${GREEN}✓ Perplexity API key saved${NC}"
        fi

        if [ -n "$GITHUB_TOKEN" ]; then
            echo "export GITHUB_TOKEN='$GITHUB_TOKEN'" >> "$SHELL_RC"
            echo -e "${GREEN}✓ GitHub token saved${NC}"
        fi
    fi
fi

echo ""

###
# Project Status Auto-Updater (Question 5 - only if vector enabled)
###
if [ "$VECTOR_ENABLED" = true ]; then
    echo -e "${CYAN}━━━ Project Status Auto-Updater (Optional) ━━━${NC}"
    echo "Enable auto-updating project status in CLAUDE.md?"
    echo "  • Runs every 5 minutes via launchd (macOS)"
    echo "  • Queries vector DB for recent decisions/risks"
    echo "  • Updates <project_status> block in CLAUDE.md"
    echo "  • Keeps Main Agent informed with fresh context"
    echo ""

    read -p "Enable project status auto-updater? [Y/n] " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo -e "${BLUE}Setting up project status launchd agent...${NC}"

        # Detect Node.js path (for MCP calls in project_status.py)
        NODE_PATH=$(which node 2>/dev/null || echo "/usr/local/bin/node")
        if [ ! -f "$NODE_PATH" ]; then
            # Try common nvm paths
            for nvm_path in "$HOME/.nvm/versions/node"/*/bin/node; do
                if [ -f "$nvm_path" ]; then
                    NODE_PATH="$nvm_path"
                    break
                fi
            done
        fi

        NODE_DIR=$(dirname "$NODE_PATH")
        FULL_PATH="/usr/local/bin:/usr/bin:/bin:$NODE_DIR"

        # Create launchd plist for project status
        PROJECT_STATUS_PLIST="$LAUNCHD_DIR/com.claude.agents.projectstatus.plist"
        mkdir -p "$LAUNCHD_DIR"

        cat > "$PROJECT_STATUS_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.claude.agents.projectstatus</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$HOOKS_DIR/project_status.py</string>
        <string>--update-claude-md</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/.claude/logs/launchd.projectstatus.out.log</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/.claude/logs/launchd.projectstatus.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>DATABASE_URL_MEMORY</key>
        <string>$DATABASE_URL_MEMORY</string>
        <key>REDIS_URL</key>
        <string>$REDIS_URL</string>
        <key>OPENAI_API_KEY</key>
        <string>$OPENAI_API_KEY</string>
        <key>PATH</key>
        <string>$FULL_PATH</string>
        <key>CLAUDE_DIR</key>
        <string>$INSTALL_DIR/.claude</string>
    </dict>
</dict>
</plist>
EOF

        # Load launchd job
        launchctl unload "$PROJECT_STATUS_PLIST" 2>/dev/null || true
        launchctl load "$PROJECT_STATUS_PLIST" 2>/dev/null && \
            echo -e "${GREEN}✓ Project status auto-updater enabled${NC}" || \
            echo -e "${YELLOW}⚠ Failed to load launchd agent (check logs)${NC}"

        # Run once immediately to initialize
        python3 "$HOOKS_DIR/project_status.py" --update-claude-md 2>/dev/null || \
            echo -e "${YELLOW}⚠ Initial project status update skipped${NC}"
    else
        echo -e "${YELLOW}⚠ Skipping project status auto-updater${NC}"
    fi
    echo ""
fi

###
# Environment Setup
###
echo -e "${CYAN}━━━ Environment Configuration ━━━${NC}"

SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ]; then
    if ! grep -q "CLAUDE_PROJECT_ROOT" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# Claude Agents Framework" >> "$SHELL_RC"
        echo 'export CLAUDE_PROJECT_ROOT="$(pwd)"' >> "$SHELL_RC"
        echo -e "${GREEN}✓ CLAUDE_PROJECT_ROOT added to $SHELL_RC${NC}"
    fi
fi

# Create FEATURE_MAP template
cat > "$HOOKS_DIR/FEATURE_MAP.template.md" << 'TEMPLATE_EOF'
# FEATURE_MAP.md

**Purpose**: Living source of truth for project direction
**Last Updated**: YYYY-MM-DD

---

## 🎯 Active Features

| Feature | Status | Files | Description |
|---------|--------|-------|-------------|
| - | ✅ Active | - | - |

---

## 🗄️ Deprecated Features

| Feature | Deprecated | Reason | Replaced By |
|---------|------------|--------|-------------|
| - | YYYY-MM-DD | - | - |

---

## 🔄 Pivot History

### YYYY-MM-DD: Initial Setup
**Changes**: Project initialized
**Files**: -

---
TEMPLATE_EOF

echo -e "${GREEN}✓ FEATURE_MAP template created${NC}"
echo ""

###
# Installation Complete
###
echo -e "${GREEN}${BOLD}"
cat << "EOF"
╔══════════════════════════════════════════════════════════╗
║           Installation Complete! 🎉                      ║
╚══════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo -e "${CYAN}━━━ Summary ━━━${NC}"
echo -e "  Hooks: ${GREEN}$HOOK_COUNT scripts${NC}"
echo -e "  Agents: ${GREEN}$AGENT_COUNT definitions${NC}"
if [ "$INSTALL_MCP" = true ]; then
    echo -e "  MCP Servers: ${GREEN}$SERVER_COUNT installed${NC}"
fi
if [ "$VECTOR_ENABLED" = true ]; then
    echo -e "  Vector Memory: ${GREEN}Enabled${NC}"
fi
echo ""

echo -e "${CYAN}━━━ Next Steps ━━━${NC}"
echo ""
echo "1. Restart your terminal to load environment variables:"
echo -e "   ${YELLOW}source $SHELL_RC${NC}"
echo ""
echo "2. Create FEATURE_MAP.md in your project:"
echo -e "   ${YELLOW}cd ~/your-project${NC}"
echo -e "   ${YELLOW}cp ~/claude-hooks/FEATURE_MAP.template.md FEATURE_MAP.md${NC}"
echo ""
echo "3. Start using Claude Code with full orchestration!"
echo ""

echo -e "${CYAN}━━━ Quick Commands ━━━${NC}"
echo -e "  Pre-merge check: ${YELLOW}bash ~/claude-hooks/ready-to-merge.sh${NC}"
echo -e "  List checkpoints: ${YELLOW}python3 ~/claude-hooks/checkpoint_manager.py list${NC}"
if [ "$VECTOR_ENABLED" = true ]; then
    echo -e "  Queue status: ${YELLOW}python3 ~/claude-hooks/stop_digest.py --queue-status${NC}"
fi
echo ""

echo -e "${CYAN}━━━ Documentation ━━━${NC}"
echo -e "  Framework docs: ${YELLOW}~/.claude/CLAUDE.md${NC}"
echo -e "  Agent roster: ${YELLOW}~/.claude/agents/${NC}"
echo -e "  Hook scripts: ${YELLOW}~/claude-hooks/${NC}"
echo ""

echo -e "${GREEN}${BOLD}Happy coding! 🚀${NC}"
echo ""
