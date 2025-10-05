#!/usr/bin/env python3
"""
Markdown Spam Prevention Hook (PostToolUse)

Enforces the NO MD SPAM policy from CLAUDE.md:
- NEVER create new .md files unless explicitly requested by user
- If Write tool is used on .md file, check if user explicitly requested it
- Suggest alternatives: update existing docs, add code comments, or explain in conversation

This prevents documentation sprawl and keeps the codebase clean.
"""
import sys
import json
import re
from pathlib import Path

def is_md_file(file_path: str) -> bool:
    """Check if file is a markdown file."""
    return file_path.lower().endswith('.md')

def is_explicit_request(conversation_context: str) -> bool:
    """
    Detect if user explicitly requested documentation file creation.

    Explicit requests include:
    - "create a README"
    - "write documentation for X"
    - "make a markdown file"
    - "document this in a new file"
    """
    if not conversation_context:
        return False

    context_lower = conversation_context.lower()

    # Explicit creation requests
    explicit_patterns = [
        r'\bcreate.*\.md\b',
        r'\bwrite.*\.md\b',
        r'\bmake.*\.md\b',
        r'\bcreate.*readme\b',
        r'\bwrite.*readme\b',
        r'\bcreate.*documentation.*file\b',
        r'\bwrite.*documentation.*file\b',
        r'\bmake.*markdown\b',
        r'\bnew.*\.md\b',
        r'\badd.*\.md.*file\b',
    ]

    return any(re.search(pattern, context_lower) for pattern in explicit_patterns)

def get_existing_docs(project_root: str) -> list[str]:
    """Find existing documentation files in project."""
    docs = []
    project_path = Path(project_root)

    # Common doc files
    common_docs = ['README.md', 'CLAUDE.md', 'CHANGELOG.md', 'CONTRIBUTING.md',
                   'LICENSE.md', 'FEATURE_MAP.md']

    for doc in common_docs:
        if (project_path / doc).exists():
            docs.append(doc)

    # Check docs/ directory
    docs_dir = project_path / 'docs'
    if docs_dir.exists() and docs_dir.is_dir():
        for md_file in docs_dir.glob('*.md'):
            docs.append(f'docs/{md_file.name}')

    return docs

def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Only intercept Write tool on .md files
    if tool_name != "Write":
        sys.exit(0)

    file_path = tool_input.get("file_path", "")

    if not is_md_file(file_path):
        sys.exit(0)

    # For PostToolUse, we can't block (file already created)
    # But we can warn and remind the policy
    # Skip system files that are auto-created

    # Check if user explicitly requested this
    # Note: We don't have access to full conversation context in PreToolUse hook,
    # so we use a heuristic based on common doc file names
    file_name = Path(file_path).name.lower()

    # Allowed automatic creation for project-critical files
    allowed_auto_create = [
        'feature_map.md',  # Pivot tracking
        'notes.md',        # Digest archive
        'compaction.md',   # Pre-compaction summary
    ]

    if any(allowed in file_name for allowed in allowed_auto_create):
        # These are system files, allow creation
        sys.exit(0)

    # Get project root
    project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    # Get existing docs
    existing_docs = get_existing_docs(project_root)

    # Warn about policy violation (can't block in PostToolUse, file already created)
    print("\n⚠️  MARKDOWN SPAM DETECTED", file=sys.stderr)
    print("", file=sys.stderr)
    print(f"Attempted to create: {file_path}", file=sys.stderr)
    print("", file=sys.stderr)
    print("📋 NO MD SPAM POLICY:", file=sys.stderr)
    print("   NEVER create new .md files unless explicitly requested by user", file=sys.stderr)
    print("", file=sys.stderr)
    print("💡 ALTERNATIVES (in order of preference):", file=sys.stderr)

    if existing_docs:
        print("", file=sys.stderr)
        print("   1. UPDATE EXISTING DOCS:", file=sys.stderr)
        for doc in existing_docs[:5]:  # Show max 5
            print(f"      • {doc}", file=sys.stderr)

    print("", file=sys.stderr)
    print("   2. ADD CODE COMMENTS:", file=sys.stderr)
    print("      • Inline documentation in source files", file=sys.stderr)
    print("", file=sys.stderr)
    print("   3. EXPLAIN IN CONVERSATION:", file=sys.stderr)
    print("      • Just tell the user directly", file=sys.stderr)
    print("", file=sys.stderr)
    print("❓ DID USER EXPLICITLY REQUEST THIS FILE?", file=sys.stderr)
    print("   If yes, user should say: \"Create a [filename].md file\"", file=sys.stderr)
    print("   If no, use alternatives above", file=sys.stderr)
    print("", file=sys.stderr)

    # Exit 1 to show warning (PostToolUse can't block, only warn)
    sys.exit(1)

if __name__ == "__main__":
    import os
    main()
