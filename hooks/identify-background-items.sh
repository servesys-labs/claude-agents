#!/usr/bin/env bash
###
# Identify Claude background items running on macOS
#
# Shows which "python3" background items are Claude agents
# and maps them to their projects
###

set -eo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}Claude Agents - Background Items Identification${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}macOS shows Claude agents as generic 'python3' entries.${NC}"
echo -e "${YELLOW}Here's what they actually are:${NC}"
echo ""

# Check currently running Claude processes
RUNNING_COUNT=0

if pgrep -f "stop_digest.py" &>/dev/null; then
    RUNNING_COUNT=$((RUNNING_COUNT + 1))
    echo -e "${GREEN}✓ Queue Processor (stop_digest.py) is running${NC}"
fi

if pgrep -f "project_status.py" &>/dev/null; then
    RUNNING_COUNT=$((RUNNING_COUNT + 1))
    echo -e "${GREEN}✓ Project Status Updater (project_status.py) is running${NC}"
fi

if [ $RUNNING_COUNT -eq 0 ]; then
    echo -e "${CYAN}No Claude agents currently executing${NC}"
    echo -e "${CYAN}(They run every 5-15 minutes)${NC}"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# List all configured launchd agents
echo -e "${CYAN}${BOLD}Configured Launchd Agents:${NC}"
echo ""

for plist in ~/Library/LaunchAgents/com.claude.agents.*.plist; do
    if [ ! -f "$plist" ]; then
        continue
    fi

    filename=$(basename "$plist")

    # Extract project name and hash
    if [[ "$filename" =~ com\.claude\.agents\.(queue|projectstatus)\.([^.]+)\.([a-f0-9]{8})\.plist ]]; then
        agent_type="${BASH_REMATCH[1]}"
        project_name="${BASH_REMATCH[2]}"
        project_hash="${BASH_REMATCH[3]}"

        # Get project path
        project_dir=$(grep -A 1 "CLAUDE_PROJECT_DIR" "$plist" | tail -1 | sed 's/.*<string>\(.*\)<\/string>/\1/')

        # Check if loaded
        label="com.claude.agents.${agent_type}.${project_name}.${project_hash}"
        if launchctl list "$label" &>/dev/null; then
            status="${GREEN}✓${NC}"
        else
            status="${YELLOW}✗${NC}"
        fi

        if [ "$agent_type" = "queue" ]; then
            type_label="Queue (every 15 min)"
        else
            type_label="Status (every 5 min)"
        fi

        echo -e "  ${status} ${BOLD}${project_name}${NC} - ${type_label}"
        echo -e "     ${CYAN}$project_dir${NC}"
    fi
done

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}${BOLD}Why you see 10+ 'python3' entries in System Settings:${NC}"
echo ""
echo "macOS System Settings shows ALL background processes by executable name."
echo "It cannot show custom labels for launchd agents - this is a macOS limitation."
echo ""
echo "The 'python3' entries include:"
echo "  • Claude queue processors (1 per project)"
echo "  • Claude status updaters (1 per project)"
echo "  • Other Python scripts running on your system"
echo "  • Old/duplicate entries from previous runs"
echo ""
echo -e "${CYAN}These entries are HARMLESS and don't affect startup time.${NC}"
echo -e "${CYAN}They only appear when the scripts are actively running.${NC}"
echo ""

echo -e "${BOLD}To clean up old background items:${NC}"
echo "  1. Restart your Mac (clears temporary process list)"
echo "  2. Remove unneeded launchd agents:"
echo "     bash ~/.claude/hooks/list-launchd-agents.sh"
echo ""
