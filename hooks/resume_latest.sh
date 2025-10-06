#!/bin/bash
# Quick resume helper - shows latest PM decision and copies to clipboard

RESUME_DIR="${CLAUDE_PROJECT_DIR:-$HOME/.claude}/.claude/logs/pm-resume"

# Find latest resume file
LATEST=$(ls -t "$RESUME_DIR"/*.md 2>/dev/null | head -1)

if [ -z "$LATEST" ]; then
    echo "❌ No PM decisions found in $RESUME_DIR"
    exit 1
fi

echo "📋 Latest PM Decision: $(basename "$LATEST")"
echo ""

# Extract the key parts
PROJECT=$(grep "^**Project:**" "$LATEST" | cut -d: -f2- | xargs)
DECISION=$(grep "^**Decision:**" "$LATEST" | cut -d: -f2- | xargs)
REASONING=$(grep "^**Reasoning:**" "$LATEST" | cut -d: -f2- | xargs)

echo "Project: $PROJECT"
echo "Decision: $DECISION"
echo ""
echo "Reasoning: $REASONING"
echo ""
echo "Actions to Take:"
sed -n '/## Actions to Take/,/## Risks/p' "$LATEST" | grep -E '^[0-9]+\.' | head -10

echo ""
echo "---"
echo ""

# Create resume prompt for Claude
RESUME_PROMPT="Continue development based on PM decision.

**Context**: Previous session ended with a question. PM agent decided: $DECISION

**Actions to execute**:
$(sed -n '/## Actions to Take/,/## Risks/p' "$LATEST" | grep -E '^[0-9]+\.')

**Risks to mitigate**:
$(sed -n '/## Risks & Mitigation/,/## Notes/p' "$LATEST" | grep '^- Risk:' | sed 's/^- Risk: //')

**Mitigation**:
$(sed -n '/## Risks & Mitigation/,/## Notes/p' "$LATEST" | grep '^- Mitigation:' | sed 's/^- Mitigation: //')

Proceed with the actions above autonomously."

# Copy to clipboard (macOS)
echo "$RESUME_PROMPT" | pbcopy

echo "✅ Resume prompt copied to clipboard!"
echo ""
echo "Next steps:"
echo "1. cd $PROJECT"
echo "2. Start new Claude Code session"
echo "3. Paste (Cmd+V) to give Claude the PM decision"
echo ""
echo "Or view full decision:"
echo "cat $LATEST"
