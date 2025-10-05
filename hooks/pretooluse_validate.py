#!/usr/bin/env python3
"""
PreToolUse validation hook - comprehensive guardrails.

Enforces policies BEFORE tools execute:
1. Checkpoint before risky operations
2. Block schema changes without DME agent
3. Prune WSI (working set index) to cap
4. Periodic typecheck (every N turns)
5. Block duplicate file reads
6. MD spam prevention

Exit codes:
- 0: allow (silent)
- 1: allow with warning (show stderr to user)
- 2: block (show stderr, prevent tool execution)
"""
import sys
import json
import os
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

# --- Config ---
# Per-project logs (injected by settings.json), fallback to global
LOGS_DIR = Path(os.environ.get("LOGS_DIR", os.path.expanduser("~/claude-hooks/logs")))
WSI_PATH = Path(os.environ.get("WSI_PATH", str(LOGS_DIR / "wsi.json")))

# Auto-create logs directory
LOGS_DIR.mkdir(parents=True, exist_ok=True)

TURN_COUNT_FILE = LOGS_DIR / "turn_count.txt"
TYPECHECK_INTERVAL = 20  # Run typecheck every N tool uses
WSI_CAP = 10
FILE_HASH_CACHE = LOGS_DIR / "file_hashes.json"
CACHE_TURNS = 10  # Warn if re-reading within N turns
# --------------

def load_turn_count():
    """Load or initialize turn counter."""
    TURN_COUNT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TURN_COUNT_FILE.exists():
        return int(TURN_COUNT_FILE.read_text().strip() or "0")
    return 0

def save_turn_count(count):
    """Save turn counter."""
    TURN_COUNT_FILE.write_text(str(count))

def run_checkpoint(reason, details):
    """Trigger checkpoint creation."""
    checkpoint_script = Path.home() / "claude-hooks" / "checkpoint_manager.py"
    if not checkpoint_script.exists():
        return

    cmd = ["python3", str(checkpoint_script), "create", reason]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout:
            checkpoint_data = json.loads(result.stdout)
            checkpoint_id = checkpoint_data.get("checkpoint_id", "unknown")
            print(f"\n🔄 Checkpoint created: {checkpoint_id}", file=sys.stderr)
            print(f"   Reason: {reason}", file=sys.stderr)
            print(f"   Details: {details}", file=sys.stderr)
            print(f"   Restore: python ~/claude-hooks/checkpoint_manager.py restore {checkpoint_id}", file=sys.stderr)
            print("", file=sys.stderr)
    except Exception as e:
        print(f"⚠️  Checkpoint failed: {e}", file=sys.stderr)

def load_json(path, default):
    """Safely load JSON file."""
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except:
        pass
    return default

def save_json(path, data):
    """Save JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def prune_wsi():
    """Prune Working Set Index to cap."""
    wsi = load_json(WSI_PATH, {"items": []})
    items = wsi.get("items", [])

    if len(items) > WSI_CAP:
        # Archive old items
        archived = items[:-WSI_CAP]
        kept = items[-WSI_CAP:]

        # Log what was pruned
        archive_file = Path.home() / "claude-hooks" / "logs" / f"wsi_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_json(str(archive_file), {"archived": archived, "timestamp": datetime.now().isoformat()})

        # Update WSI
        wsi["items"] = kept
        save_json(WSI_PATH, wsi)

        print(f"   📦 WSI pruned: {len(archived)} items archived", file=sys.stderr)

def check_duplicate_read(file_path):
    """Check if file was recently read with same content."""
    cache = load_json(str(FILE_HASH_CACHE), {})
    current_turn = load_turn_count()

    # Clean old entries
    cache = {k: v for k, v in cache.items() if current_turn - v.get("turn", 0) <= CACHE_TURNS}

    # Check if file exists and get its hash
    if os.path.exists(file_path):
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                file_hash = hashlib.md5(content).hexdigest()

            # Check cache
            if file_path in cache:
                cached = cache[file_path]
                if cached.get("hash") == file_hash:
                    turns_ago = current_turn - cached.get("turn", 0)
                    if turns_ago <= CACHE_TURNS:
                        # Track duplicate read attempts
                        duplicate_count = cached.get("duplicate_attempts", 0) + 1

                        # Update attempt count in cache
                        cache[file_path]["duplicate_attempts"] = duplicate_count
                        save_json(str(FILE_HASH_CACHE), cache)

                        # Block after 3 duplicate attempts
                        if duplicate_count >= 3:
                            print("", file=sys.stderr)
                            print("=============================================================", file=sys.stderr)
                            print("🚫 DUPLICATE READ BLOCKED", file=sys.stderr)
                            print("=============================================================", file=sys.stderr)
                            print(f"File: {file_path}", file=sys.stderr)
                            print(f"Duplicate read attempts: {duplicate_count}", file=sys.stderr)
                            print("", file=sys.stderr)
                            print("This file was already read and hasn't changed.", file=sys.stderr)
                            print("", file=sys.stderr)
                            print("Main Agent should:", file=sys.stderr)
                            print("1. Reference the previous read content", file=sys.stderr)
                            print("2. Use Grep to search for specific patterns", file=sys.stderr)
                            print("3. Use Read with offset/limit for specific sections", file=sys.stderr)
                            print("", file=sys.stderr)
                            print("=============================================================", file=sys.stderr)
                            print("", file=sys.stderr)
                            # Hard block (exit 2)
                            return "BLOCK"
                        else:
                            # Warning for attempts 1-2
                            print(f"\n⚠️  Duplicate Read Warning ({duplicate_count}/3)", file=sys.stderr)
                            print(f"   File: {file_path}", file=sys.stderr)
                            print(f"   Previously read: {turns_ago} turns ago", file=sys.stderr)
                            print(f"   Content unchanged - reference previous read instead", file=sys.stderr)
                            print(f"   Will BLOCK after {3 - duplicate_count} more attempts", file=sys.stderr)
                            print("", file=sys.stderr)
                            return "WARN"

            # Update cache (reset duplicate attempts on successful read)
            cache[file_path] = {"hash": file_hash, "turn": current_turn, "duplicate_attempts": 0}
            save_json(str(FILE_HASH_CACHE), cache)
        except:
            pass

    return False

def main():
    # Read input from Claude Code (some commands may not provide JSON payloads)
    raw = sys.stdin.read()

    if not raw.strip():  # Allow empty payloads (manual Bash, etc.)
        sys.exit(0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("⚠️  PreToolUse: non-JSON payload detected; allowing command.", file=sys.stderr)
        sys.exit(0)
    except Exception as exc:
        print(f"⚠️  PreToolUse: failed to parse payload ({exc}); allowing command.", file=sys.stderr)
        sys.exit(0)

    tool = data.get("tool_name", "")
    args = data.get("tool_input", {})

    # Get working directory
    cwd = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    # Increment turn counter
    turn_count = load_turn_count()
    turn_count += 1
    save_turn_count(turn_count)

    # Prune WSI periodically (every 10 turns)
    if turn_count % 10 == 0:
        prune_wsi()

    # === CHECKPOINT TRIGGERS ===
    checkpoint_needed = False
    checkpoint_reason = ""
    checkpoint_details = ""

    # Schema/migration changes
    if tool in ["Edit", "Write", "MultiEdit"]:
        file_path = args.get("file_path", "")
        if any(critical in file_path.lower() for critical in [
            "schema.prisma", "migrations/", ".sql",
            "alembic", "migrate", "models.py", "models.ts"
        ]):
            checkpoint_needed = True
            checkpoint_reason = "Schema/migration change"
            checkpoint_details = f"Modifying {file_path}"

    # Critical config files
    if tool in ["Edit", "Write"]:
        file_path = args.get("file_path", "")
        if any(critical in file_path.lower() for critical in [
            "package.json", "pyproject.toml", "requirements.txt",
            ".env", "config.json", "settings.json"
        ]):
            checkpoint_needed = True
            checkpoint_reason = "Critical config change"
            checkpoint_details = f"Modifying {file_path}"

    # Destructive bash commands
    if tool == "Bash":
        command = args.get("command", "").lower()
        if any(danger in command for danger in [
            "rm -rf", "rm -fr", "drop table", "drop database",
            "delete from", "truncate", "prisma migrate",
            "> /dev/null 2>&1", "sudo", "chmod 777"
        ]):
            checkpoint_needed = True
            checkpoint_reason = "Destructive command"
            checkpoint_details = command[:100]

        # Dependency removal
        if any(removal in command for removal in [
            "npm uninstall", "pip uninstall", "pnpm remove",
            "yarn remove", "apt remove", "brew uninstall"
        ]):
            checkpoint_needed = True
            checkpoint_reason = "Dependency removal"
            checkpoint_details = command[:100]

    # Periodic checkpoint (every 50 turns)
    if turn_count % 50 == 0:
        checkpoint_needed = True
        checkpoint_reason = "Periodic checkpoint"
        checkpoint_details = f"Turn {turn_count}"

    # Execute checkpoint if needed (non-blocking)
    if checkpoint_needed and not any(safe in args.get("command", "") for safe in ["git", "ls", "cat", "grep", "find"]):
        run_checkpoint(checkpoint_reason, checkpoint_details)

    # === SCHEMA CHANGE BLOCK ===
    if tool in ["Edit", "Write", "MultiEdit"]:
        file_path = args.get("file_path", "")
        if "schema.prisma" in file_path.lower() or "/migrations/" in file_path.lower():
            # Check if DME agent was used recently
            notes_path = os.path.join(cwd, "NOTES.md")
            dme_used = False
            if os.path.exists(notes_path):
                try:
                    with open(notes_path, 'r') as f:
                        content = f.read()
                        # Check last 500 chars for DME mention
                        if "agent\": \"DME\"" in content[-500:]:
                            dme_used = True
                except:
                    pass

            if not dme_used:
                print("", file=sys.stderr)
                print("=============================================================", file=sys.stderr)
                print("🚫 SCHEMA CHANGE BLOCKED", file=sys.stderr)
                print("=============================================================", file=sys.stderr)
                print(f"Attempting to modify: {file_path}", file=sys.stderr)
                print("", file=sys.stderr)
                print("Schema/migration changes REQUIRE using the DME agent.", file=sys.stderr)
                print("", file=sys.stderr)
                print("Main Agent should:", file=sys.stderr)
                print("1. Invoke Task(dme-schema-migration) for schema changes", file=sys.stderr)
                print("2. Let DME handle migrations, rollback plans, backfills", file=sys.stderr)
                print("3. Never edit schema files directly", file=sys.stderr)
                print("", file=sys.stderr)
                print("=============================================================", file=sys.stderr)
                print("", file=sys.stderr)

                # Hard block
                sys.exit(2)

    # === PERIODIC TYPECHECK ===
    if turn_count % TYPECHECK_INTERVAL == 0:
        # Find all modified TS/JS/Python files
        modified_files = []

        if tool in ["Edit", "Write", "MultiEdit"]:
            file_path = args.get("file_path", "")
            if any(ext in file_path.lower() for ext in ['.ts', '.tsx', '.js', '.jsx', '.py']):
                modified_files.append(file_path)

        if modified_files or turn_count % (TYPECHECK_INTERVAL * 2) == 0:
            print(f"\n📋 Periodic typecheck (turn {turn_count})", file=sys.stderr)

            # Detect project type
            is_node = (Path(cwd) / "package.json").exists()
            is_python = (Path(cwd) / "pyproject.toml").exists() or (Path(cwd) / "setup.py").exists()

            # Try Node.js first (try common script names)
            if is_node:
                for script_name in ["type-check", "typecheck", "tsc"]:
                    try:
                        result = subprocess.run(
                            ["npm", "run", script_name],
                            cwd=cwd,
                            capture_output=True,
                            timeout=10,
                            text=True
                        )

                        # If script exists and completed (success or failure)
                        if "Missing script" not in result.stderr:
                            if result.returncode != 0:
                                # Show typecheck errors
                                print(f"\n❌ TypeScript errors found:", file=sys.stderr)
                                print(result.stdout[:500], file=sys.stderr)
                                print("\nFix these before continuing.", file=sys.stderr)
                                # Warning only (exit 1)
                                sys.exit(1)
                            else:
                                print("   ✅ TypeScript check passed", file=sys.stderr)
                            break
                    except subprocess.TimeoutExpired:
                        print("   ⏱️ Typecheck timed out", file=sys.stderr)
                        break
                    except FileNotFoundError:
                        continue  # Try next script name

            # Try Python
            if is_python:
                try:
                    result = subprocess.run(
                        ["python", "-m", "pyright"],
                        cwd=cwd,
                        capture_output=True,
                        timeout=10,
                        text=True
                    )
                    if result.returncode != 0 and "no issues found" not in result.stdout.lower():
                        print(f"\n❌ Python type errors found:", file=sys.stderr)
                        print(result.stdout[:500], file=sys.stderr)
                        # Warning only
                        sys.exit(1)
                    else:
                        print("   ✅ Python typecheck passed", file=sys.stderr)
                except:
                    # Try mypy as fallback
                    try:
                        result = subprocess.run(
                            ["python", "-m", "mypy", "."],
                            cwd=cwd,
                            capture_output=True,
                            timeout=10,
                            text=True
                        )
                        if result.returncode != 0:
                            print(f"\n❌ Mypy errors found:", file=sys.stderr)
                            print(result.stdout[:500], file=sys.stderr)
                            sys.exit(1)
                    except:
                        pass

    # === DUPLICATE READ CHECK ===
    if tool == "Read":
        file_path = args.get("file_path", "")
        result = check_duplicate_read(file_path)
        if result == "BLOCK":
            # Hard block after 3 attempts
            sys.exit(2)
        elif result == "WARN":
            # Warning for attempts 1-2
            sys.exit(1)

    # === DEPENDENCY SAFETY ===
    if tool == "Bash":
        command = args.get("command", "").lower()

        # Block removal without IDS review
        if any(cmd in command for cmd in ["npm uninstall", "pip uninstall", "pnpm remove"]):
            # Check if IDS was consulted
            notes_path = os.path.join(cwd, "NOTES.md")
            ids_consulted = False
            if os.path.exists(notes_path):
                try:
                    with open(notes_path, 'r') as f:
                        content = f.read()
                        if "agent\": \"IDS\"" in content[-500:]:
                            ids_consulted = True
                except:
                    pass

            if not ids_consulted:
                print("", file=sys.stderr)
                print("=============================================================", file=sys.stderr)
                print("🚫 DEPENDENCY REMOVAL BLOCKED", file=sys.stderr)
                print("=============================================================", file=sys.stderr)
                print(f"Command: {command[:100]}", file=sys.stderr)
                print("", file=sys.stderr)
                print("Dependency removal requires IDS agent review:", file=sys.stderr)
                print("1. Invoke Task(ids-interface-dependency-steward)", file=sys.stderr)
                print("2. Let IDS analyze impact on contracts/interfaces", file=sys.stderr)
                print("3. Only proceed if IDS approves", file=sys.stderr)
                print("", file=sys.stderr)
                print("=============================================================", file=sys.stderr)
                print("", file=sys.stderr)

                # Hard block
                sys.exit(2)

    # === ROUTING ENFORCEMENT ===
    # Warn about direct Edit/Write on code files that should use subagents
    if tool in ["Edit", "Write", "MultiEdit", "NotebookEdit"]:
        file_path = args.get("file_path", "")

        # Check if it's a code file
        code_extensions = ['.ts', '.tsx', '.js', '.jsx', '.py', '.java', '.cpp', '.c', '.rs', '.go', '.rb']
        is_code_file = any(file_path.endswith(ext) for ext in code_extensions)

        # Also check for specific project code paths to be more targeted
        project_code_paths = ['/lib/', '/app/', '/components/', '/src/', '/packages/']
        is_project_code = any(path in file_path for path in project_code_paths)

        if is_code_file and is_project_code:
            # Check if this is hook/script code (allowed for Main Agent)
            allowed_direct_paths = ['/claude-hooks/', '/.claude/', '/scripts/']
            is_allowed_direct = any(path in file_path for path in allowed_direct_paths)

            if not is_allowed_direct:
                print("", file=sys.stderr)
                print("=============================================================", file=sys.stderr)
                print("⚠️  ROUTING POLICY REMINDER", file=sys.stderr)
                print("=============================================================", file=sys.stderr)
                print(f"", file=sys.stderr)
                print(f"Direct edit detected on: {file_path}", file=sys.stderr)
                print("", file=sys.stderr)
                print("📋 ROUTING POLICY:", file=sys.stderr)
                print("Main Agent should delegate code changes to subagents:", file=sys.stderr)
                print("", file=sys.stderr)
                print("• Code changes → Task(code-navigator-impact) + Task(implementation-engineer)", file=sys.stderr)
                print("• Bug fixes → Task(requirements-clarifier) first", file=sys.stderr)
                print("• New features → Task(implementation-planner-sprint-architect) first", file=sys.stderr)
                print("", file=sys.stderr)
                print("💡 Exceptions (direct work allowed):", file=sys.stderr)
                print("• Hook/script files (claude-hooks/, .claude/, scripts/)", file=sys.stderr)
                print("• Documentation files (.md)", file=sys.stderr)
                print("• Configuration files (.json, .env, .yaml)", file=sys.stderr)
                print("", file=sys.stderr)
                print("Proceeding with direct edit (warning only)...", file=sys.stderr)
                print("=============================================================", file=sys.stderr)
                print("", file=sys.stderr)

                # Warning only - don't block for now
                # Can upgrade to exit(2) to block in future
                sys.exit(1)

    # MD SPAM PREVENTION (PreToolUse blocking)
    # Check for Write tool creating new .md files
    if tool == "Write":
        file_path = args.get("file_path", "")
        if file_path.lower().endswith('.md'):
            file_name = Path(file_path).name.lower()

            # Allowed automatic creation for project-critical files
            allowed_auto_create = [
                'feature_map.md',  # Pivot tracking
                'notes.md',        # Digest archive
                'compaction.md',   # Pre-compaction summary
                'changelog.md',    # Project history
                'readme.md',       # Project docs (if doesn't exist)
                'claude.md',       # Orchestration config
            ]

            # Check if this is an allowed system file
            is_system_file = any(allowed in file_name for allowed in allowed_auto_create)

            if not is_system_file:
                # Check if user explicitly requested this file

                md_state_file = Path.home() / "claude-hooks" / "logs" / "md_request_state.json"
                is_approved = False

                if md_state_file.exists():
                    try:
                        with open(md_state_file, 'r') as f:
                            state = json.load(f)

                        # Check if approval is recent (within 5 minutes)
                        if state.get("timestamp"):
                            timestamp = datetime.fromisoformat(state["timestamp"])
                            if datetime.now() - timestamp <= timedelta(minutes=5):
                                approved_files = state.get("approved_files", [])

                                # Check for exact match or permissive mode
                                if "*PERMISSIVE*" in approved_files:
                                    is_approved = True
                                    print(f"\n✅ MD Creation Approved (permissive mode): {file_path}", file=sys.stderr)
                                else:
                                    # Check exact filename or path match
                                    for approved in approved_files:
                                        if (file_path.endswith(approved) or
                                            file_name == approved.lower() or
                                            approved in file_path.lower()):
                                            is_approved = True
                                            print(f"\n✅ MD Creation Approved (explicit request): {file_path}", file=sys.stderr)

                                            # Remove this approval after use
                                            approved_files.remove(approved)
                                            state["approved_files"] = approved_files
                                            with open(md_state_file, 'w') as f:
                                                json.dump(state, f, indent=2)
                                            break
                    except:
                        pass

                if not is_approved:
                    # Block creation of non-approved .md files
                    print("", file=sys.stderr)
                    print("=============================================================", file=sys.stderr)
                    print("🚫 MARKDOWN SPAM PREVENTION", file=sys.stderr)
                    print("=============================================================", file=sys.stderr)
                    print(f"BLOCKED: Attempt to create: {file_path}", file=sys.stderr)
                    print("", file=sys.stderr)
                    print("📋 NO MD SPAM POLICY (enforced by PreToolUse):", file=sys.stderr)
                    print("   NEVER create new .md files unless explicitly requested", file=sys.stderr)
                    print("", file=sys.stderr)
                    print("💡 REQUIRED ALTERNATIVES:", file=sys.stderr)
                    print("   1. Update existing docs (README.md, CLAUDE.md, etc.)", file=sys.stderr)
                    print("   2. Add code comments in source files", file=sys.stderr)
                    print("   3. Explain in conversation only", file=sys.stderr)
                    print("", file=sys.stderr)
                    print("❓ IF USER EXPLICITLY WANTS THIS FILE:", file=sys.stderr)
                    print("   User must say: \"Create {filename}\" or \"Write documentation for X\"", file=sys.stderr)
                    print("   Examples: \"create docs/api.md\", \"write a changelog.md file\"", file=sys.stderr)
                    print("", file=sys.stderr)
                    print("=============================================================", file=sys.stderr)
                    print("", file=sys.stderr)

                    # Hard block (exit 2)
                    sys.exit(2)

    # Allow by default
    sys.exit(0)

if __name__ == "__main__":
    main()
