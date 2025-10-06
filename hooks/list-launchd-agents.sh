#!/usr/bin/env bash
###
# List all Claude launchd agents with project info
#
# Usage:
#   bash list-launchd-agents.sh
###

set -eo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}Claude Agents - Launchd Status${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

LAUNCHD_DIR="$HOME/Library/LaunchAgents"
FOUND=false

# Find all Claude agents
for plist in "$LAUNCHD_DIR"/com.claude.agents.*.plist; do
    if [ ! -f "$plist" ]; then
        continue
    fi

    FOUND=true
    filename=$(basename "$plist")

    # Extract project name and hash from filename
    # Format: com.claude.agents.{type}.{project-name}.{hash}.plist
    if [[ "$filename" =~ com\.claude\.agents\.(queue|projectstatus)\.([^.]+)\.([a-f0-9]{8})\.plist ]]; then
        agent_type="${BASH_REMATCH[1]}"
        project_name="${BASH_REMATCH[2]}"
        project_hash="${BASH_REMATCH[3]}"

        # Get CLAUDE_PROJECT_DIR from plist (it's the last entry in EnvironmentVariables)
        project_dir=$(grep -A 1 "CLAUDE_PROJECT_DIR" "$plist" | tail -1 | sed 's/.*<string>\(.*\)<\/string>/\1/' || echo "unknown")

        # Check if loaded
        label="com.claude.agents.${agent_type}.${project_name}.${project_hash}"
        if launchctl list "$label" &>/dev/null; then
            status="${GREEN}✓ Running${NC}"
        else
            status="${YELLOW}✗ Stopped${NC}"
        fi

        # Pretty print
        if [ "$agent_type" = "queue" ]; then
            type_label="Queue Processor"
        else
            type_label="Status Updater"
        fi

        echo -e "${CYAN}${BOLD}${project_name}${NC} ${BLUE}(${project_hash})${NC}"
        echo -e "  Type:    ${type_label}"
        echo -e "  Status:  ${status}"
        echo -e "  Path:    ${project_dir}"
        echo -e "  Label:   ${label}"
        echo ""
    else
        # Old format or unrecognized
        echo -e "${YELLOW}${BOLD}$(basename "$plist")${NC}"
        echo -e "  ${YELLOW}⚠ Unrecognized format (old agent?)${NC}"
        echo ""
    fi
done

if [ "$FOUND" = false ]; then
    echo -e "${YELLOW}No Claude launchd agents found${NC}"
    echo ""
    echo "To create agents for a project:"
    echo "  1. cd /path/to/project"
    echo "  2. rm .claude/.setup_complete  # if already set up"
    echo "  3. Open project in Claude Code"
    echo ""
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Commands:"
echo "  List all:     launchctl list | grep claude"
echo "  Unload agent: launchctl unload ~/Library/LaunchAgents/{label}.plist"
echo "  Load agent:   launchctl load ~/Library/LaunchAgents/{label}.plist"
echo ""
