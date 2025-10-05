#!/usr/bin/env python3
"""
MD Request Detector Hook (UserPromptSubmit)

Detects when user explicitly requests creation of a markdown file.
Saves approved filenames to state for PreToolUse validation.

This enables the MD spam prevention to distinguish between:
- Unauthorized MD creation (blocked)
- Explicitly requested MD creation (allowed)
"""
import sys
import json
import re
import os
from pathlib import Path
from datetime import datetime, timedelta

def detect_md_creation_request(content: str) -> list[str]:
    """
    Detect explicit requests to create markdown files.

    Returns list of explicitly requested .md filenames.
    """
    if not content:
        return []

    content_lower = content.lower()
    requested_files = []

    # Patterns for explicit MD file creation requests
    patterns = [
        # "create X.md" or "create a X.md file"
        r'\bcreate\s+(?:a\s+)?([^\s]+\.md)\b',
        r'\bcreate\s+(?:a\s+)?(?:new\s+)?([^\s]+)\s+(?:markdown|md)\s+file\b',
        r'\bcreate\s+.*?(?:called|named)\s+([^\s]+\.md)\b',

        # "write X.md" or "write a X.md file"
        r'\bwrite\s+(?:a\s+)?([^\s]+\.md)\b',
        r'\bwrite\s+(?:a\s+)?(?:new\s+)?([^\s]+)\s+(?:markdown|md)\s+file\b',

        # "make X.md" or "make a X.md file"
        r'\bmake\s+(?:a\s+)?([^\s]+\.md)\b',
        r'\bmake\s+(?:a\s+)?(?:new\s+)?([^\s]+)\s+(?:markdown|md)\s+file\b',

        # "add X.md" or "add a X.md file"
        r'\badd\s+(?:a\s+)?([^\s]+\.md)\b',
        r'\badd\s+(?:a\s+)?(?:new\s+)?([^\s]+)\s+(?:markdown|md)\s+file\b',

        # "generate X.md"
        r'\bgenerate\s+(?:a\s+)?([^\s]+\.md)\b',

        # "document this in X.md"
        r'\bdocument\s+(?:this|it|that)\s+in\s+([^\s]+\.md)\b',

        # Generic patterns for documentation requests
        r'\bcreate\s+(?:a\s+)?(?:new\s+)?documentation\s+(?:file\s+)?(?:called|named)\s+([^\s]+)\b',
        r'\bwrite\s+(?:a\s+)?(?:new\s+)?documentation\s+(?:file\s+)?(?:called|named)\s+([^\s]+)\b',
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, content_lower, re.IGNORECASE)
        for match in matches:
            filename = match.group(1)
            # Ensure it has .md extension
            if not filename.endswith('.md'):
                filename += '.md'
            # Clean up the filename
            filename = filename.strip('.,;:!?"\'')
            if filename and filename != '.md':
                requested_files.append(filename)

    # Also check for explicit paths like "docs/new-feature.md"
    path_pattern = r'\b(?:create|write|make|add|generate)\s+(?:a\s+)?([a-zA-Z0-9_\-/]+\.md)\b'
    path_matches = re.finditer(path_pattern, content, re.IGNORECASE)
    for match in path_matches:
        filepath = match.group(1)
        if filepath and filepath not in requested_files:
            requested_files.append(filepath)

    # Check for generic documentation requests that should translate to specific files
    if any(phrase in content_lower for phrase in [
        "create documentation for",
        "write documentation for",
        "make documentation for",
        "document the",
        "add documentation about",
        "write a new",  # Often followed by ".md file"
        "create a new"  # Often followed by ".md file"
    ]):
        # Check if it's explicitly mentioning markdown or .md
        if any(term in content_lower for term in ['.md', 'markdown', 'md file']):
            # Extract potential filename from patterns like "write a new feature.md file"
            simple_pattern = r'(?:write|create|make)\s+a\s+new\s+(\w+)\.md\s+file'
            match = re.search(simple_pattern, content_lower)
            if match:
                filename = match.group(1) + '.md'
                if filename not in requested_files:
                    requested_files.append(filename)
        else:
            # These are vague but suggest user wants documentation
            # We'll be more permissive for the next few minutes
            return ["*PERMISSIVE*"]  # Special flag for temporary permissiveness

    return requested_files

def load_md_state() -> dict:
    """Load MD request state."""
    state_file = Path.home() / "claude-hooks" / "logs" / "md_request_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)

    if state_file.exists():
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except:
            pass

    return {"approved_files": [], "timestamp": None}

def save_md_state(state: dict):
    """Save MD request state."""
    state_file = Path.home() / "claude-hooks" / "logs" / "md_request_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)

def clean_old_approvals(state: dict) -> dict:
    """Remove approvals older than 5 minutes."""
    if state.get("timestamp"):
        try:
            timestamp = datetime.fromisoformat(state["timestamp"])
            if datetime.now() - timestamp > timedelta(minutes=5):
                # Too old, clear approvals
                return {"approved_files": [], "timestamp": None}
        except:
            pass
    return state

def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except:
        sys.exit(0)

    content = data.get("content", "")
    if not content:
        sys.exit(0)

    # Detect explicit MD creation requests
    requested_files = detect_md_creation_request(content)

    if requested_files:
        # Load and clean old state
        state = load_md_state()
        state = clean_old_approvals(state)

        # Add new approvals
        state["approved_files"].extend(requested_files)
        state["timestamp"] = datetime.now().isoformat()

        # Save state
        save_md_state(state)

        # Log what we detected (for debugging)
        if "*PERMISSIVE*" in requested_files:
            print(f"\n📝 MD Creation: Detected general documentation request", file=sys.stderr)
            print(f"   Being permissive for next 5 minutes", file=sys.stderr)
        else:
            print(f"\n📝 MD Creation: Detected explicit request for:", file=sys.stderr)
            for filename in requested_files:
                print(f"   • {filename}", file=sys.stderr)
        print(f"   These files are pre-approved for creation", file=sys.stderr)
        print("", file=sys.stderr)

        # Non-blocking info (exit 1 to show message)
        sys.exit(1)

    # No MD requests detected
    sys.exit(0)

if __name__ == "__main__":
    main()