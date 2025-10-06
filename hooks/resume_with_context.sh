#!/bin/bash
# Resume with full project context - for mid-development sessions

set -e

RESUME_DIR="${CLAUDE_PROJECT_DIR:-$HOME/.claude}/.claude/logs/pm-resume"
PROJECT_ROOT="${1:-$PWD}"

# Find latest resume file
LATEST=$(ls -t "$RESUME_DIR"/*.md 2>/dev/null | head -1)

if [ -z "$LATEST" ]; then
    echo "❌ No PM decisions found"
    exit 1
fi

echo "📋 Building context-rich resume prompt..."

# Extract PM decision
DECISION=$(grep "^**Decision:**" "$LATEST" | cut -d: -f2- | xargs)
REASONING=$(grep "^**Reasoning:**" "$LATEST" | cut -d: -f2- | xargs)

# Get project context
cd "$PROJECT_ROOT"

# Recent commits (what was done)
RECENT_COMMITS=$(git log --oneline -5 2>/dev/null || echo "No git history")

# Project structure
PROJECT_FILES=$(find . -type f -name "*.ts" -o -name "*.tsx" -o -name "*.prisma" 2>/dev/null | grep -v node_modules | head -20)

# Package.json for dependencies
DEPENDENCIES=$(cat package.json 2>/dev/null | jq -r '.dependencies | keys | .[]' 2>/dev/null || echo "No package.json")

# Check for common state files and extract last DIGEST
STATE_FILES=""
LAST_DIGEST=""

if [ -f ".claude/logs/NOTES.md" ]; then
    STATE_FILES="$STATE_FILES
- .claude/logs/NOTES.md exists (session history)"
    # Extract last DIGEST block
    LAST_DIGEST=$(tac ".claude/logs/NOTES.md" | awk '/^## \[/{p=1} p{print} /^---$/{if(p) exit}' | tac)
fi

if [ -f ".claude/logs/NOTES.md" ]; then
    STATE_FILES="$STATE_FILES
- .claude/logs/NOTES.md exists (project-specific notes)"
fi

if [ -f "FEATURE_MAP.md" ]; then
    STATE_FILES="$STATE_FILES
- FEATURE_MAP.md exists (feature tracking)"
fi

# Build comprehensive resume prompt
RESUME_PROMPT="# Resume Development - Mid-Project Context Restoration

## PM Decision
**Decision**: $DECISION
**Reasoning**: $REASONING

## Project State (Before You Left)

### Recent Work (Last 5 Commits)
\`\`\`
$RECENT_COMMITS
\`\`\`

### Project Structure
Key files in project:
\`\`\`
$PROJECT_FILES
\`\`\`

### Dependencies
\`\`\`
$DEPENDENCIES
\`\`\`

### State Files
$STATE_FILES

### Last Session DIGEST (What Was Just Completed)
$(if [ -n "$LAST_DIGEST" ]; then echo "$LAST_DIGEST"; else echo "No recent DIGEST found"; fi)

## Actions to Execute (PM Decision)
$(sed -n '/## Actions to Take/,/## Risks/p' "$LATEST" | grep -E '^[0-9]+\.')

## Risks & Mitigation
**Risks**:
$(sed -n '/## Risks & Mitigation/,/## Notes/p' "$LATEST" | grep '^- Risk:' | sed 's/^- Risk: /- /')

**Mitigation**:
$(sed -n '/## Risks & Mitigation/,/## Notes/p' "$LATEST" | grep '^- Mitigation:' | sed 's/^- Mitigation: /- /')

---

## Context Restoration Steps

Before executing PM actions, please:

1. **Read key state files** to understand current progress:
   \`\`\`bash
   # If they exist:
   cat NOTES.md
   cat FEATURE_MAP.md
   cat .claude/logs/NOTES.md
   \`\`\`

2. **Check recent changes** to see what was implemented:
   \`\`\`bash
   git diff HEAD~5..HEAD --stat
   git log -1 --patch  # Last commit details
   \`\`\`

3. **Review schema/API** if this is database/backend work:
   \`\`\`bash
   # Database
   cat prisma/schema.prisma 2>/dev/null || echo 'No schema'

   # API routes
   find . -name 'route.ts' -o -name 'api.ts' | grep -v node_modules
   \`\`\`

4. **Then proceed** with PM actions above, maintaining consistency with existing patterns

---

**Important**: This is an **ongoing project**. Don't start from scratch. Build on what's already there.
Assume previous work is production-ready. Your job: continue the plan, not redesign.

**Project Root**: $PROJECT_ROOT
"

# Copy to clipboard
echo "$RESUME_PROMPT" | pbcopy

echo ""
echo "✅ Context-rich resume prompt copied to clipboard!"
echo ""
echo "Next steps:"
echo "1. cd $PROJECT_ROOT"
echo "2. Start Claude Code session"
echo "3. Paste (Cmd+V)"
echo ""
echo "Claude will:"
echo "- Read state files (NOTES.md, git history)"
echo "- Understand what was already built"
echo "- Continue from where previous session left off"
echo ""
echo "View full PM decision: cat $LATEST"
