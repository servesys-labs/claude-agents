#!/bin/bash
# Bootstrap Claude Code project with global MCP servers
# Run this once from any project root directory

set -e

PROJECT_ROOT=$(pwd)
echo "🚀 Bootstrapping Claude Code project: $PROJECT_ROOT"

# Copy global MCP template
if [ ! -f .mcp.json ]; then
  echo "📋 Creating .mcp.json from global template..."
  cp ~/.claude/mcp-template.json .mcp.json
  echo "✅ Created .mcp.json"
else
  echo "⚠️  .mcp.json already exists, skipping..."
fi

# Create NOTES.md if missing
if [ ! -f NOTES.md ]; then
  echo "📝 Creating NOTES.md..."
  cat > NOTES.md << 'EOF'
# NOTES (living state)

Last 20 digests. Older entries archived to logs/notes-archive/.

EOF
  echo "✅ Created NOTES.md"
else
  echo "⚠️  NOTES.md already exists, skipping..."
fi

# Create minimal CLAUDE.md if missing
if [ ! -f CLAUDE.md ]; then
  echo "📖 Creating CLAUDE.md..."
  cat > CLAUDE.md << 'EOF'
# Project Configuration

See global orchestration framework: ~/.claude/CLAUDE.md

## Project-Specific Notes

Add any project-specific conventions, patterns, or constraints here.
EOF
  echo "✅ Created CLAUDE.md"
else
  echo "⚠️  CLAUDE.md already exists, skipping..."
fi

echo ""
echo "✨ Project bootstrapped successfully!"
echo ""
echo "Next steps:"
echo "1. Restart Claude Code from this directory"
echo "2. Approve vector-bridge MCP server when prompted"
echo "3. Start coding - DIGESTs will auto-index to global memory!"
