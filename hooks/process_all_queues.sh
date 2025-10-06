#!/usr/bin/env bash
###
# Multi-Project Queue Processor
#
# Scans all projects with .claude/ingest-queue/ directories
# and processes them with stop_digest.py --process-queue
#
# Usage:
#   bash process_all_queues.sh
###

set -eo pipefail

# Find all .claude directories (excluding ~/.claude itself to avoid double-processing)
# Search in common project locations
PROJECT_DIRS=(
    "$HOME/projects"
    "$HOME/code"
    "$HOME/work"
    "$HOME/repos"
    "$HOME/Documents"
    "$HOME/Desktop"
)

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}[$(date)] Multi-project queue processor started${NC}"

# Process global ~/.claude queue first
if [ -d "$HOME/.claude/ingest-queue" ]; then
    echo -e "${BLUE}Processing global queue: ~/.claude${NC}"
    CLAUDE_PROJECT_DIR="$HOME/.claude" python3 "$HOME/.claude/hooks/stop_digest.py" --process-queue
fi

# Find and process all project-level .claude directories
for base_dir in "${PROJECT_DIRS[@]}"; do
    if [ ! -d "$base_dir" ]; then
        continue
    fi

    # Find all .claude/ingest-queue directories (max depth 4 to avoid deep scans)
    find "$base_dir" -maxdepth 4 -type d -name "ingest-queue" -path "*/.claude/ingest-queue" 2>/dev/null | while read -r queue_dir; do
        # Extract project root (parent of .claude)
        project_root=$(dirname "$(dirname "$queue_dir")")

        # Skip if it's the global ~/.claude
        if [ "$project_root" = "$HOME/.claude" ]; then
            continue
        fi

        # Count pending jobs
        pending_count=$(find "$queue_dir" -name "*.json" -not -path "*/dead/*" 2>/dev/null | wc -l | xargs)

        if [ "$pending_count" -gt 0 ]; then
            echo -e "${YELLOW}Processing queue: $project_root ($pending_count jobs)${NC}"
            CLAUDE_PROJECT_DIR="$project_root" python3 "$HOME/.claude/hooks/stop_digest.py" --process-queue
        fi
    done
done

echo -e "${GREEN}[$(date)] Multi-project queue processor completed${NC}"
