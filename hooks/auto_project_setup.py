#!/usr/bin/env python3
"""
Auto Project Setup Hook (PreToolUse)

Automatically sets up .claude/ infrastructure for new projects.
Runs once per project, then creates a marker file to skip future runs.

Creates:
- .claude/logs/ directory
- .gitignore entries for .claude/logs/ and .envrc
- NOTES.md (if doesn't exist)

Exit codes:
- 0: success (silent, fail-open on errors)
- 1: info message (non-blocking)

Safety:
- Guards against running in $HOME or /
- Atomic .gitignore writes
- Fail-open (never blocks tool execution)
"""
import sys
import os
import tempfile
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()
CLAUDE_DIR = PROJECT_ROOT / ".claude"
LOGS_DIR = CLAUDE_DIR / "logs"
SETUP_MARKER = CLAUDE_DIR / ".setup_complete"
GITIGNORE = PROJECT_ROOT / ".gitignore"
NOTES_MD = PROJECT_ROOT / "NOTES.md"

def is_safe_project_root():
    """
    Ensure PROJECT_ROOT is not $HOME or /.

    Returns:
        bool: True if safe to modify, False if dangerous location
    """
    unsafe_paths = [Path.home(), Path("/")]
    return PROJECT_ROOT not in unsafe_paths

def is_git_repo():
    """
    Check if current directory is a git repository.

    Uses fast filesystem check (.git directory exists) to avoid subprocess overhead.
    """
    return (PROJECT_ROOT / ".git").exists()

def setup_complete():
    """Check if setup has already been completed."""
    return SETUP_MARKER.exists()

def mark_setup_complete():
    """Create marker file to indicate setup is complete."""
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
    SETUP_MARKER.write_text(f"Setup completed at {os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())}\n")

def ensure_logs_directory():
    """Create .claude/logs/ directory."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return True

def update_gitignore():
    """
    Add .claude/logs/ and .envrc to .gitignore if not already present.

    Uses atomic write (temp file + rename) for safety.
    Handles CRLF vs LF, deduplicates lines.

    Returns:
        bool: True if changes were made, False otherwise
    """
    if not is_git_repo():
        return False  # Skip if not a git repo

    # Read existing gitignore (handle CRLF/LF)
    existing_lines = []
    if GITIGNORE.exists():
        content = GITIGNORE.read_text()
        existing_lines = content.splitlines()

    # Normalize: strip trailing whitespace, deduplicate
    normalized = []
    seen = set()
    for line in existing_lines:
        stripped = line.rstrip()
        if stripped not in seen:
            normalized.append(stripped)
            seen.add(stripped)

    # Entries to add
    entries_to_add = []

    # Check for .claude/logs/ (exact match or variant)
    if not any(".claude/logs" in line for line in normalized):
        entries_to_add.append(".claude/logs/")

    # Check for .envrc
    if ".envrc" not in normalized:
        entries_to_add.append(".envrc")

    if not entries_to_add:
        return False  # Nothing to add

    # Build new content
    new_lines = normalized.copy()
    if new_lines and new_lines[-1] != "":
        new_lines.append("")  # Blank line before comment
    new_lines.append("# Claude orchestration framework")
    new_lines.extend(entries_to_add)

    # Atomic write: write to temp file, then rename
    temp_fd, temp_path = tempfile.mkstemp(dir=PROJECT_ROOT, prefix=".gitignore.tmp")
    try:
        with os.fdopen(temp_fd, 'w') as f:
            f.write("\n".join(new_lines) + "\n")
        # Atomic rename
        os.replace(temp_path, GITIGNORE)
        return True
    except Exception as e:
        # Cleanup temp file on error
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        raise e

def ensure_notes_md():
    """Create NOTES.md if it doesn't exist."""
    if NOTES_MD.exists():
        return False

    NOTES_MD.write_text("""# Project Notes

This file contains DIGEST blocks from Claude Code orchestration agents.

DIGESTs are automatically appended by the Stop hook when agents complete their work.

---

""")
    return True

def check_vector_rag_credentials():
    """
    Check if Vector RAG credentials are configured.
    If missing, automatically trigger setup_vector_rag.

    Returns:
        bool: True if credentials exist, False otherwise
    """
    db_url = os.environ.get("DATABASE_URL_MEMORY")
    redis_url = os.environ.get("REDIS_URL")
    openai_key = os.environ.get("OPENAI_API_KEY")

    all_set = db_url and redis_url and openai_key

    if not all_set:
        # Automatically trigger setup via MCP tool
        import subprocess
        import json

        print("\n⚠️  Vector RAG Memory not configured. Running automatic setup...", file=sys.stderr)

        try:
            # Call the monitoring-bridge MCP tool to setup credentials
            # Note: This requires Claude Code to invoke the tool, so we output a special format
            setup_request = {
                "auto_setup_rag": True,
                "tool": "mcp__monitoring-bridge__setup_vector_rag",
                "message": "🚀 Automatically running Vector RAG setup...",
            }
            print(json.dumps(setup_request), file=sys.stderr)
            print("\n💡 To complete setup: Restart terminal and Claude Code after credentials are saved.\n", file=sys.stderr)
        except Exception as e:
            print(f"⚠️  Auto-setup failed: {e}", file=sys.stderr)
            print("💡 Manually run: mcp__monitoring-bridge__setup_vector_rag\n", file=sys.stderr)

    return all_set

def main():
    """
    Run auto project setup.

    Fail-open: catches all exceptions and exits 0 to never block tool execution.
    Fast short-circuit: exits immediately if setup already complete.
    """
    try:
        # Fast short-circuit: skip if setup already complete
        if setup_complete():
            # Check if Stop hook flagged that Vector RAG setup is needed
            setup_needed_flag = CLAUDE_DIR / ".needs_vector_rag_setup"
            if setup_needed_flag.exists():
                print("\n🚀 Auto-running Vector RAG setup (triggered by Stop hook)...", file=sys.stderr)
                print("💡 Claude will call mcp__monitoring-bridge__setup_vector_rag\n", file=sys.stderr)
                # Remove flag so we don't trigger again
                setup_needed_flag.unlink()
                sys.exit(1)  # Exit 1 to show message and let Claude see it

            sys.exit(0)  # Silent success

        # Safety: refuse to run in $HOME or /
        if not is_safe_project_root():
            # Silent fail-open (never block, but don't pollute $HOME)
            sys.exit(0)

        # Skip if not in a project directory (no package.json, pyproject.toml, etc.)
        is_project = any([
            (PROJECT_ROOT / "package.json").exists(),
            (PROJECT_ROOT / "pyproject.toml").exists(),
            (PROJECT_ROOT / "Cargo.toml").exists(),
            (PROJECT_ROOT / "pom.xml").exists(),
            (PROJECT_ROOT / "go.mod").exists(),
            is_git_repo()
        ])

        if not is_project:
            sys.exit(0)  # Not a project, skip silently

        # Run setup
        actions = []

        # 1. Create logs directory
        if ensure_logs_directory():
            actions.append("Created .claude/logs/")

        # 2. Update .gitignore
        if update_gitignore():
            actions.append("Updated .gitignore")

        # 3. Create NOTES.md
        if ensure_notes_md():
            actions.append("Created NOTES.md")

        # Mark setup complete
        mark_setup_complete()

        # Report what was done
        if actions:
            print(f"✨ Auto-setup complete: {', '.join(actions)}", file=sys.stderr)
            sys.exit(1)  # Exit 1 to show message to user (non-blocking)
        else:
            sys.exit(0)  # Silent success

    except Exception as e:
        # Fail-open: log error but never block tool execution
        try:
            error_log = CLAUDE_DIR / "logs" / "auto_setup_errors.log"
            error_log.parent.mkdir(parents=True, exist_ok=True)
            with error_log.open("a") as f:
                import datetime
                f.write(f"{datetime.datetime.now().isoformat()} - {type(e).__name__}: {e}\n")
        except Exception:
            pass  # Even error logging failed, still exit 0
        sys.exit(0)  # Always exit 0 on exception (fail-open)

if __name__ == "__main__":
    main()
