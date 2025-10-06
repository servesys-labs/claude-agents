#!/usr/bin/env python3
"""
Auto Project Setup Hook (PreToolUse)

Automatically sets up .claude/ infrastructure for new projects.
Runs once per project, then creates a marker file to skip future runs.

Creates:
- .claude/logs/ directory
- .gitignore entries for .claude/logs/ and .envrc
- .claude/logs/NOTES.md (if doesn't exist)
- CLAUDE.md with project-specific template (if doesn't exist)
- Per-project launchd agents (queue processor, project status updater)

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
import subprocess
import hashlib
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()
CLAUDE_DIR = PROJECT_ROOT / ".claude"
LOGS_DIR = CLAUDE_DIR / "logs"
SETUP_MARKER = CLAUDE_DIR / ".setup_complete"
GITIGNORE = PROJECT_ROOT / ".gitignore"
NOTES_MD = LOGS_DIR / "NOTES.md"

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
    """Create .claude/logs/NOTES.md if it doesn't exist."""
    if NOTES_MD.exists():
        return False

    NOTES_MD.write_text("""# NOTES (living state)

Last 20 digests. Older entries archived to logs/notes-archive/.

""")
    return True

def ensure_claude_md():
    """Create CLAUDE.md if it doesn't exist."""
    claude_md = PROJECT_ROOT / "CLAUDE.md"
    if claude_md.exists():
        return False

    project_name = PROJECT_ROOT.name
    claude_md.write_text(f"""# {project_name}

Project-specific instructions for Claude Code.

## Project Overview

[Brief description of what this project does]

## Development

[Setup instructions, build commands, test commands]

## Architecture

[Key architectural decisions, patterns used]

## Important Notes

[Things Claude should know when working on this codebase]

---

*This file is automatically created by the Claude Agents Framework.*
*Edit as needed for your project-specific requirements.*
""")
    return True

def merge_global_hooks():
    """
    Merge global hooks into project-local settings if local settings exist.
    This ensures hooks work even when project has custom permissions.

    Returns:
        bool: True if hooks were merged, False otherwise
    """
    import json

    local_settings = CLAUDE_DIR / "settings.local.json"

    # Skip if no local settings file
    if not local_settings.exists():
        return False

    # Load global settings
    global_settings = Path.home() / ".claude" / "settings.json"
    if not global_settings.exists():
        return False

    try:
        with open(global_settings) as f:
            global_config = json.load(f)

        with open(local_settings) as f:
            local_config = json.load(f)

        # Check if hooks already merged
        if "hooks" in local_config and local_config.get("hooks"):
            return False  # Already has hooks, don't overwrite

        # Merge permissions from global (if not set locally)
        if "permissions" not in local_config:
            global_permissions = global_config.get("permissions", {})
            if global_permissions:
                local_config["permissions"] = global_permissions

        # Merge hooks from global
        global_hooks = global_config.get("hooks", {})
        if not global_hooks:
            return False

        local_config["hooks"] = global_hooks

        # Write merged settings
        with open(local_settings, "w") as f:
            json.dump(local_config, f, indent=2)
            f.write("\n")

        return True
    except Exception:
        return False

def get_node_path():
    """
    Detect Node.js path for launchd agents.
    Handles nvm installations.
    """
    # Try which node first
    try:
        result = subprocess.run(["which", "node"], capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            node_path = result.stdout.strip()
            if os.path.isfile(node_path):
                return node_path
    except Exception:
        pass

    # Try common nvm paths
    home = str(Path.home())
    nvm_base = Path(home) / ".nvm" / "versions" / "node"
    if nvm_base.exists():
        for node_dir in nvm_base.iterdir():
            node_bin = node_dir / "bin" / "node"
            if node_bin.is_file():
                return str(node_bin)

    # Fallback
    return "/usr/local/bin/node"

def get_project_hash():
    """Generate stable hash for project (for unique launchd labels)."""
    project_str = str(PROJECT_ROOT)
    return hashlib.sha256(project_str.encode()).hexdigest()[:8]

def get_project_name():
    """
    Get human-readable project name.
    Uses git repo name, or falls back to directory name.
    Sanitized for use in filenames (no spaces, special chars).
    """
    try:
        # Try to get git remote URL and extract repo name
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            git_url = result.stdout.strip()
            # Extract repo name from URL
            # Examples:
            #   https://github.com/user/my-repo.git -> my-repo
            #   git@github.com:user/my-repo.git -> my-repo
            import re
            match = re.search(r'/([^/]+?)(?:\.git)?$', git_url)
            if match:
                repo_name = match.group(1)
                # Sanitize: lowercase, replace special chars with dash
                sanitized = re.sub(r'[^a-z0-9]+', '-', repo_name.lower())
                return sanitized.strip('-')
    except Exception:
        pass

    # Fallback to directory name
    dir_name = PROJECT_ROOT.name
    # Sanitize
    import re
    sanitized = re.sub(r'[^a-z0-9]+', '-', dir_name.lower())
    return sanitized.strip('-')

def setup_launchd_agents():
    """
    Create per-project launchd agents for:
    1. Queue processor (every 15 min)
    2. Project status updater (every 5 min)

    Returns:
        bool: True if agents were created, False otherwise
    """
    # Only create launchd agents if Vector RAG credentials exist
    db_url = os.environ.get("DATABASE_URL_MEMORY")
    redis_url = os.environ.get("REDIS_URL")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not (db_url and redis_url and openai_key):
        return False  # Skip if credentials not configured

    # macOS only
    if os.uname().sysname != "Darwin":
        return False

    launchd_dir = Path.home() / "Library" / "LaunchAgents"
    launchd_dir.mkdir(parents=True, exist_ok=True)

    project_hash = get_project_hash()
    project_name = get_project_name()
    hooks_dir = Path.home() / ".claude" / "hooks"
    node_path = get_node_path()
    node_dir = str(Path(node_path).parent)
    full_path = f"/usr/local/bin:/usr/bin:/bin:{node_dir}"

    # Agent 1: Queue Processor (every 15 min)
    # Format: com.claude.agents.queue.{repo-name}.{hash}
    queue_label = f"com.claude.agents.queue.{project_name}.{project_hash}"
    queue_plist = launchd_dir / f"{queue_label}.plist"

    queue_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{queue_label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>{hooks_dir}/stop_digest.py</string>
        <string>--process-queue</string>
    </array>
    <key>StartInterval</key>
    <integer>900</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{CLAUDE_DIR}/logs/launchd.queue.out.log</string>
    <key>StandardErrorPath</key>
    <string>{CLAUDE_DIR}/logs/launchd.queue.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>DATABASE_URL_MEMORY</key>
        <string>{db_url}</string>
        <key>REDIS_URL</key>
        <string>{redis_url}</string>
        <key>OPENAI_API_KEY</key>
        <string>{openai_key}</string>
        <key>ENABLE_VECTOR_RAG</key>
        <string>true</string>
        <key>PATH</key>
        <string>{full_path}</string>
        <key>CLAUDE_PROJECT_DIR</key>
        <string>{PROJECT_ROOT}</string>
    </dict>
</dict>
</plist>
"""

    # Agent 2: Project Status Updater (every 5 min)
    # Format: com.claude.agents.projectstatus.{repo-name}.{hash}
    status_label = f"com.claude.agents.projectstatus.{project_name}.{project_hash}"
    status_plist = launchd_dir / f"{status_label}.plist"

    status_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{status_label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>{hooks_dir}/project_status.py</string>
        <string>--update-claude-md</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{CLAUDE_DIR}/logs/launchd.projectstatus.out.log</string>
    <key>StandardErrorPath</key>
    <string>{CLAUDE_DIR}/logs/launchd.projectstatus.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>DATABASE_URL_MEMORY</key>
        <string>{db_url}</string>
        <key>REDIS_URL</key>
        <string>{redis_url}</string>
        <key>OPENAI_API_KEY</key>
        <string>{openai_key}</string>
        <key>ENABLE_VECTOR_RAG</key>
        <string>true</string>
        <key>PATH</key>
        <string>{full_path}</string>
        <key>CLAUDE_PROJECT_DIR</key>
        <string>{PROJECT_ROOT}</string>
    </dict>
</dict>
</plist>
"""

    created = False

    # Create project .claude/launchd directory for reference
    project_launchd_dir = CLAUDE_DIR / "launchd"
    project_launchd_dir.mkdir(parents=True, exist_ok=True)

    # Write queue processor plist
    if not queue_plist.exists():
        queue_plist.write_text(queue_content)
        # Create reference copy in project
        project_queue_ref = project_launchd_dir / queue_plist.name
        project_queue_ref.write_text(queue_content)
        # Load the agent
        try:
            subprocess.run(["launchctl", "load", str(queue_plist)],
                         capture_output=True, timeout=5)
            created = True
        except Exception:
            pass

    # Write project status plist
    if not status_plist.exists():
        status_plist.write_text(status_content)
        # Create reference copy in project
        project_status_ref = project_launchd_dir / status_plist.name
        project_status_ref.write_text(status_content)
        # Load the agent
        try:
            subprocess.run(["launchctl", "load", str(status_plist)],
                         capture_output=True, timeout=5)
            created = True
        except Exception:
            pass

    # Create README in launchd directory
    readme_path = project_launchd_dir / "README.md"
    if not readme_path.exists():
        readme_content = f"""# Launchd Agents for this Project

This directory contains **reference copies** of the launchd agents for this project.

## Active Agents

- `{queue_plist.name}` - Queue Processor (runs every 15 min)
- `{status_plist.name}` - Project Status Updater (runs every 5 min)

## Important

The **actual** plist files that macOS uses are in:
`~/Library/LaunchAgents/`

The files in this directory are just references for your convenience.

## Managing Agents

**List all agents:**
```bash
bash ~/.claude/hooks/list-launchd-agents.sh
```

**Check agent status:**
```bash
launchctl list | grep {project_name}
```

**View logs:**
```bash
tail -f {CLAUDE_DIR}/logs/launchd.queue.out.log
tail -f {CLAUDE_DIR}/logs/launchd.projectstatus.out.log
```

**Unload agents:**
```bash
launchctl unload ~/Library/LaunchAgents/{queue_label}.plist
launchctl unload ~/Library/LaunchAgents/{status_label}.plist
```

**Reload agents:**
```bash
launchctl load ~/Library/LaunchAgents/{queue_label}.plist
launchctl load ~/Library/LaunchAgents/{status_label}.plist
```
"""
        readme_path.write_text(readme_content)

    return created

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

        # 4. Create CLAUDE.md
        if ensure_claude_md():
            actions.append("Created CLAUDE.md")

        # 5. Setup per-project launchd agents (if Vector RAG credentials exist)
        if setup_launchd_agents():
            actions.append("Setup launchd agents")

        # 5. Merge global hooks into local settings (if local settings exist)
        if merge_global_hooks():
            actions.append("Merged global hooks into local settings")

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
