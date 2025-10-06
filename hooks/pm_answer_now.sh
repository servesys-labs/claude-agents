#!/bin/bash
# PM Answer Now - Immediately trigger PM to answer the last agent question
#
# Usage: bash pm_answer_now.sh
#
# This script:
# 1. Reads the last agent message from clipboard (copy it first!)
# 2. Triggers PM dialogue immediately
# 3. Shows decision in terminal
#
# For proof-of-concept testing: get immediate PM decisions without waiting for session end

set -e

# Check requirements
if [ -z "$ENABLE_PM_AGENT" ] || [ "$ENABLE_PM_AGENT" != "true" ]; then
    echo "❌ Error: ENABLE_PM_AGENT not set to true"
    echo "   Run: export ENABLE_PM_AGENT=true"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: OPENAI_API_KEY not set"
    echo "   Run: export OPENAI_API_KEY=sk-proj-..."
    exit 1
fi

# Get question from clipboard or args
if [ $# -gt 0 ]; then
    QUESTION="$*"
else
    echo "📋 Reading question from clipboard..."
    QUESTION=$(pbpaste)
fi

if [ -z "$QUESTION" ]; then
    echo "❌ Error: No question provided"
    echo ""
    echo "Usage:"
    echo "  1. Copy agent's question to clipboard"
    echo "  2. Run: bash pm_answer_now.sh"
    echo ""
    echo "Or provide question as argument:"
    echo "  bash pm_answer_now.sh \"Should I use Docker or GCP?\""
    exit 1
fi

echo ""
echo "🤖 PM will analyze this question:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$QUESTION" | head -c 500
if [ ${#QUESTION} -gt 500 ]; then
    echo "..."
fi
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Trigger PM
cd "$(dirname "$0")"
python3 pm_inline_trigger.py "$QUESTION"

# Copy latest resume file to clipboard for easy pasting
RESUME_DIR="$CLAUDE_PROJECT_DIR/.claude/logs/pm-resume"
if [ -z "$CLAUDE_PROJECT_DIR" ]; then
    RESUME_DIR="$(pwd)/../.claude/logs/pm-resume"
fi

LATEST_RESUME=$(ls -t "$RESUME_DIR"/resume-*.md 2>/dev/null | head -1)

if [ -n "$LATEST_RESUME" ]; then
    echo ""
    echo "📋 Decision copied to clipboard!"
    echo "   Paste into next Claude session to continue"
    echo ""
    cat "$LATEST_RESUME" | pbcopy
fi

exit 0
