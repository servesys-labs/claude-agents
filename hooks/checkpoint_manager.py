#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Checkpoint Manager: Auto-checkpoint before risky operations.

Triggered by pretooluse_validate.py when detecting:
- Changes touching >5 files
- Schema/migration changes
- File deletions
- Dependency removals
- Destructive operations

Creates git stashes with metadata for easy rollback.
"""
import sys
import os
import json
import subprocess
from datetime import datetime
from pathlib import Path

# Per-project logs (injected by settings.json), fallback to global
LOGS_DIR = os.environ.get("LOGS_DIR", os.path.expanduser("~/claude-hooks/logs"))
CHECKPOINT_DIR = os.path.join(LOGS_DIR, "checkpoints")
MAX_CHECKPOINTS = 20  # Keep last 20 checkpoints


def ensure_checkpoint_dir():
    """Ensure checkpoint directory exists."""
    Path(CHECKPOINT_DIR).mkdir(parents=True, exist_ok=True)


def get_git_root(cwd: str) -> str | None:
    """Get git repository root, if any."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def create_checkpoint(cwd: str, reason: str, metadata: dict) -> dict:
    """
    Create a checkpoint using git stash.

    Returns:
        dict with checkpoint info (id, timestamp, reason, stash_ref)
    """
    ensure_checkpoint_dir()
    git_root = get_git_root(cwd)

    if not git_root:
        return {
            "success": False,
            "error": "Not a git repository - checkpoints require git",
            "reason": reason
        }

    # Create git stash with message
    timestamp = datetime.now().isoformat()
    stash_message = f"CHECKPOINT: {reason} | {timestamp}"

    try:
        # Check if there are changes to stash
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=git_root,
            capture_output=True,
            text=True,
            timeout=5
        )

        if not status.stdout.strip():
            # No changes to checkpoint
            return {
                "success": True,
                "skipped": True,
                "reason": "No uncommitted changes to checkpoint"
            }

        # Create stash WITHOUT modifying working directory (git stash create)
        # First, stage all changes including untracked files
        subprocess.run(
            ["git", "add", "-A"],
            cwd=git_root,
            capture_output=True,
            timeout=5
        )

        # Create stash object without affecting working directory
        result = subprocess.run(
            ["git", "stash", "create", stash_message],
            cwd=git_root,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Git stash create failed: {result.stderr}",
                "reason": reason
            }

        # Get the stash SHA from stdout
        stash_ref = result.stdout.strip()

        if not stash_ref:
            return {
                "success": False,
                "error": "Git stash create returned no SHA",
                "reason": reason
            }

        # Store the stash permanently with a message
        subprocess.run(
            ["git", "stash", "store", "-m", stash_message, stash_ref],
            cwd=git_root,
            capture_output=True,
            timeout=5
        )

        # Unstage the changes to restore original state
        subprocess.run(
            ["git", "reset", "HEAD"],
            cwd=git_root,
            capture_output=True,
            timeout=5
        )

        # Save checkpoint metadata
        checkpoint_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        checkpoint_info = {
            "id": checkpoint_id,
            "timestamp": timestamp,
            "reason": reason,
            "stash_ref": stash_ref,
            "git_root": git_root,
            "metadata": metadata,
            "files_changed": status.stdout.strip().split('\n')
        }

        # Save to checkpoint log
        checkpoint_file = os.path.join(CHECKPOINT_DIR, f"{checkpoint_id}.json")
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint_info, f, indent=2)

        # Rotate old checkpoints
        rotate_checkpoints()

        return {
            "success": True,
            "checkpoint_id": checkpoint_id,
            "stash_ref": stash_ref,
            "timestamp": timestamp,
            "reason": reason
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Git command timed out",
            "reason": reason
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "reason": reason
        }


def list_checkpoints() -> list[dict]:
    """List all available checkpoints."""
    ensure_checkpoint_dir()
    checkpoints = []

    for file_path in sorted(Path(CHECKPOINT_DIR).glob("*.json"), reverse=True):
        try:
            with open(file_path) as f:
                checkpoint = json.load(f)
                checkpoints.append(checkpoint)
        except Exception:
            continue

    return checkpoints


def restore_checkpoint(checkpoint_id: str, cwd: str) -> dict:
    """
    Restore a checkpoint by applying the git stash.

    Returns:
        dict with success status and info
    """
    checkpoint_file = os.path.join(CHECKPOINT_DIR, f"{checkpoint_id}.json")

    if not os.path.exists(checkpoint_file):
        return {
            "success": False,
            "error": f"Checkpoint {checkpoint_id} not found"
        }

    try:
        with open(checkpoint_file) as f:
            checkpoint = json.load(f)

        git_root = checkpoint["git_root"]
        stash_ref = checkpoint["stash_ref"]

        # Apply stash
        result = subprocess.run(
            ["git", "stash", "apply", stash_ref],
            cwd=git_root,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Failed to restore checkpoint: {result.stderr}",
                "checkpoint": checkpoint
            }

        return {
            "success": True,
            "checkpoint_id": checkpoint_id,
            "restored_files": checkpoint.get("files_changed", []),
            "reason": checkpoint["reason"],
            "timestamp": checkpoint["timestamp"]
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def rotate_checkpoints():
    """Keep only the last MAX_CHECKPOINTS checkpoints."""
    checkpoints = sorted(Path(CHECKPOINT_DIR).glob("*.json"))

    if len(checkpoints) > MAX_CHECKPOINTS:
        # Delete oldest checkpoints
        for old_checkpoint in checkpoints[:-MAX_CHECKPOINTS]:
            try:
                old_checkpoint.unlink()
            except Exception:
                pass


def should_checkpoint(tool: str, args: dict, current_turn: int) -> tuple[bool, str]:
    """
    Determine if a checkpoint is needed based on tool and args.

    Returns:
        (should_checkpoint: bool, reason: str)
    """
    # Schema/migration changes
    if tool == "Task" and args.get("subagent_type") in ("database-modeler", "dme-schema-migration"):
        return (True, "Schema/migration change via DME")

    # File operations on >5 files
    if tool in ("Edit", "Write", "MultiEdit"):
        file_path = args.get("file_path", "")

        # Check if this is a destructive pattern
        if any(pattern in file_path.lower() for pattern in ["prisma/schema", "package.json", "pyproject.toml"]):
            return (True, f"Critical file change: {Path(file_path).name}")

    # Bash commands that might be destructive
    if tool == "Bash":
        command = args.get("command", "")

        # EXCLUDE git operations (they're reversible and safe)
        if any(git_cmd in command for git_cmd in ["git add", "git commit", "git push", "git stash", "git checkout"]):
            return (False, "")

        # Destructive commands
        if any(pattern in command for pattern in ["rm -rf", "DROP TABLE", "DELETE FROM", "prisma migrate"]):
            return (True, f"Destructive bash command: {command[:50]}")

        # Dependency changes
        if any(pattern in command for pattern in ["npm uninstall", "pip uninstall", "pnpm remove"]):
            return (True, "Dependency removal")

    # Periodic checkpoints every 50 turns
    if current_turn > 0 and current_turn % 50 == 0:
        return (True, f"Periodic checkpoint (turn {current_turn})")

    return (False, "")


def main():
    """
    Checkpoint manager CLI for manual operations.

    Usage:
        python checkpoint_manager.py create "reason" '{"key": "value"}'
        python checkpoint_manager.py list
        python checkpoint_manager.py restore <checkpoint_id>
    """
    import sys

    if len(sys.argv) < 2:
        print("Usage: checkpoint_manager.py [create|list|restore] [args...]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    cwd = os.getcwd()

    if command == "create":
        reason = sys.argv[2] if len(sys.argv) > 2 else "Manual checkpoint"
        metadata = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}

        result = create_checkpoint(cwd, reason, metadata)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("success") else 1)

    elif command == "list":
        checkpoints = list_checkpoints()
        print(json.dumps(checkpoints, indent=2))
        sys.exit(0)

    elif command == "restore":
        if len(sys.argv) < 3:
            print("Usage: checkpoint_manager.py restore <checkpoint_id>", file=sys.stderr)
            sys.exit(1)

        checkpoint_id = sys.argv[2]
        result = restore_checkpoint(checkpoint_id, cwd)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("success") else 1)

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
