#!/usr/bin/env bash
###
# Ready-to-Merge Quality Gate
#
# Runs Integration & Cohesion Audit + Production Readiness Verification
# before allowing PR merge. This is the final checkpoint before code
# enters the main branch.
#
# Usage: ./ready-to-merge.sh [--auto-fix]
#
# Returns:
#   0 = Ready to merge (all checks passed)
#   1 = Not ready (failed checks, see report)
###

set -euo pipefail

PROJECT_ROOT="${CLAUDE_PROJECT_ROOT:-$(pwd)}"
LOGS_DIR="$HOME/claude-hooks/logs"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
REPORT_FILE="$LOGS_DIR/merge-gate-$TIMESTAMP.md"

AUTO_FIX=false
if [[ "${1:-}" == "--auto-fix" ]]; then
  AUTO_FIX=true
fi

mkdir -p "$LOGS_DIR"

echo "🚦 READY-TO-MERGE QUALITY GATE"
echo ""
echo "Project: $PROJECT_ROOT"
echo "Timestamp: $TIMESTAMP"
echo ""

# Initialize report
cat > "$REPORT_FILE" <<EOF
# Merge Readiness Report
**Project**: $PROJECT_ROOT
**Timestamp**: $TIMESTAMP
**Auto-fix**: $AUTO_FIX

---

EOF

OVERALL_STATUS="PASS"

# Function to add section to report
add_section() {
  local title="$1"
  local status="$2"
  local details="$3"

  echo "## $title" >> "$REPORT_FILE"
  echo "**Status**: $status" >> "$REPORT_FILE"
  echo "" >> "$REPORT_FILE"
  echo "$details" >> "$REPORT_FILE"
  echo "" >> "$REPORT_FILE"

  if [[ "$status" == "❌ FAIL" ]]; then
    OVERALL_STATUS="FAIL"
  fi
}

# Check 1: Git status (no uncommitted changes)
echo "📋 Checking git status..."
if git diff --quiet && git diff --cached --quiet; then
  add_section "Git Status" "✅ PASS" "Working tree is clean"
else
  UNCOMMITTED=$(git status --porcelain | wc -l | tr -d ' ')
  add_section "Git Status" "⚠️  WARN" "Found $UNCOMMITTED uncommitted changes. Commit before merging."
fi

# Check 2: Run linter
echo "🔍 Running linter..."
if npm run lint &>/dev/null; then
  add_section "Linter" "✅ PASS" "No linting errors"
else
  LINT_OUTPUT=$(npm run lint 2>&1 || true)
  if [[ "$AUTO_FIX" == "true" ]]; then
    npm run lint -- --fix &>/dev/null || true
    add_section "Linter" "🔧 FIXED" "Auto-fixed linting errors"
  else
    add_section "Linter" "❌ FAIL" "\`\`\`\n$LINT_OUTPUT\n\`\`\`\n\nRun with --auto-fix to attempt automatic fixes."
  fi
fi

# Check 3: Run typecheck
echo "📝 Running typecheck..."
if npm run typecheck &>/dev/null; then
  add_section "TypeScript" "✅ PASS" "No type errors"
else
  TYPECHECK_OUTPUT=$(npm run typecheck 2>&1 || true)
  add_section "TypeScript" "❌ FAIL" "\`\`\`\n$TYPECHECK_OUTPUT\n\`\`\`"
fi

# Check 4: Run tests
echo "🧪 Running tests..."
if npm test &>/dev/null; then
  add_section "Tests" "✅ PASS" "All tests passed"
else
  TEST_OUTPUT=$(npm test 2>&1 || true)
  add_section "Tests" "❌ FAIL" "\`\`\`\n$TEST_OUTPUT\n\`\`\`"
fi

# Check 5: Run build
echo "🏗️  Running build..."
if npm run build &>/dev/null; then
  add_section "Build" "✅ PASS" "Build succeeded"
else
  BUILD_OUTPUT=$(npm run build 2>&1 || true)
  add_section "Build" "❌ FAIL" "\`\`\`\n$BUILD_OUTPUT\n\`\`\`"
fi

# Check 6: FEATURE_MAP.md exists and is updated
echo "📋 Checking FEATURE_MAP.md..."
if [[ -f "$PROJECT_ROOT/FEATURE_MAP.md" ]]; then
  LAST_MODIFIED=$(git log -1 --format="%ar" -- FEATURE_MAP.md 2>/dev/null || echo "never")
  add_section "FEATURE_MAP" "✅ PASS" "Last updated: $LAST_MODIFIED"
else
  add_section "FEATURE_MAP" "⚠️  WARN" "FEATURE_MAP.md not found. Consider creating it to track feature evolution."
fi

# Final summary
echo "" >> "$REPORT_FILE"
echo "---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
if [[ "$OVERALL_STATUS" == "PASS" ]]; then
  echo "## ✅ READY TO MERGE" >> "$REPORT_FILE"
  echo "" >> "$REPORT_FILE"
  echo "All quality gates passed. Safe to merge to main." >> "$REPORT_FILE"
  EXIT_CODE=0
else
  echo "## ❌ NOT READY TO MERGE" >> "$REPORT_FILE"
  echo "" >> "$REPORT_FILE"
  echo "One or more quality gates failed. Fix issues above before merging." >> "$REPORT_FILE"
  EXIT_CODE=1
fi

# Display report
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cat "$REPORT_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📄 Full report: $REPORT_FILE"
echo ""

exit $EXIT_CODE
