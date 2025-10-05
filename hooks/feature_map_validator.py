#!/usr/bin/env python3
"""
FEATURE_MAP Validation Hook (UserPromptSubmit)

Triggered after pivot_detector.py detects a pivot.
Checks if user updated FEATURE_MAP.md in recent commits or working tree.
Warns if they're proceeding without updating the source of truth.

This ensures the pivot workflow is followed correctly.
"""
import sys
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

def get_feature_map_path() -> Path:
    """Get FEATURE_MAP.md path from working directory."""
    project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    return Path(project_root) / "FEATURE_MAP.md"

def check_recent_feature_map_updates() -> tuple[bool, str]:
    """
    Check if FEATURE_MAP.md was updated in:
    1. Working tree (uncommitted changes)
    2. Last 3 commits (recent history)

    Returns: (was_updated, details_message)
    """
    feature_map = get_feature_map_path()

    # Check 1: Uncommitted changes
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", str(feature_map)],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            status = result.stdout.strip()
            if status.startswith("M") or status.startswith("A"):
                return (True, "FEATURE_MAP.md has uncommitted changes")
    except:
        pass

    # Check 2: Last 3 commits
    try:
        result = subprocess.run(
            ["git", "log", "-3", "--oneline", "--", str(feature_map)],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            commits = result.stdout.strip().split('\n')
            return (True, f"FEATURE_MAP.md updated in last {len(commits)} commit(s)")
    except:
        pass

    return (False, "No recent FEATURE_MAP.md updates detected")

def load_pivot_state() -> dict:
    """Load persistent pivot detection state."""
    state_file = Path.home() / "claude-hooks" / "logs" / "pivot_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)

    if state_file.exists():
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except:
            pass

    return {"last_pivot_time": None, "acknowledged": False}

def save_pivot_state(state: dict):
    """Save persistent pivot detection state."""
    state_file = Path.home() / "claude-hooks" / "logs" / "pivot_state.json"
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)

def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except:
        sys.exit(0)

    content = data.get("content", "")
    if not content:
        sys.exit(0)

    # Load pivot state
    state = load_pivot_state()

    # Check if user is acknowledging the pivot workflow
    content_lower = content.lower()
    acknowledgment_triggers = [
        "i've updated feature_map",
        "updated feature_map",
        "run pivot cleanup",
        "audit relevance",
        "feature_map is updated"
    ]

    if any(trigger in content_lower for trigger in acknowledgment_triggers):
        # User is running the workflow - mark as acknowledged
        state["acknowledged"] = True
        save_pivot_state(state)
        sys.exit(0)

    # Check if there was a recent pivot detection (within last 5 minutes)
    if state.get("last_pivot_time"):
        try:
            pivot_time = datetime.fromisoformat(state["last_pivot_time"])
            if datetime.now() - pivot_time > timedelta(minutes=5):
                # Pivot was too long ago, reset state
                state = {"last_pivot_time": None, "acknowledged": False}
                save_pivot_state(state)
        except:
            pass

    # If there was a recent pivot and it wasn't acknowledged
    if state.get("last_pivot_time") and not state.get("acknowledged"):
        # Check if FEATURE_MAP was updated
        was_updated, details = check_recent_feature_map_updates()

        if not was_updated:
            print("\n⚠️  FEATURE_MAP VALIDATION WARNING", file=sys.stderr)
            print("", file=sys.stderr)
            print("A pivot was detected but FEATURE_MAP.md hasn't been updated.", file=sys.stderr)
            print("", file=sys.stderr)
            print("📋 RECOMMENDED WORKFLOW:", file=sys.stderr)
            print("   1. Update FEATURE_MAP.md first:", file=sys.stderr)
            print("      • Move deprecated features → 'Deprecated Features' section", file=sys.stderr)
            print("      • Add new features → 'Active Features' section", file=sys.stderr)
            print("      • Document reasoning in 'Pivot History'", file=sys.stderr)
            print("", file=sys.stderr)
            print("   2. Then say: \"I've updated FEATURE_MAP. Run the pivot cleanup workflow.\"", file=sys.stderr)
            print("", file=sys.stderr)
            print("💡 This ensures documentation stays in sync with your current direction.", file=sys.stderr)
            print("", file=sys.stderr)
            # Non-blocking warning (exit 1)
            sys.exit(1)
        else:
            # FEATURE_MAP was updated, acknowledge the pivot
            state["acknowledged"] = True
            save_pivot_state(state)

            print("\n✅ FEATURE_MAP Updated", file=sys.stderr)
            print(f"   {details}", file=sys.stderr)
            print("", file=sys.stderr)
            print("💡 When ready, say: \"Run the pivot cleanup workflow.\"", file=sys.stderr)
            print("", file=sys.stderr)
            # Non-blocking info (exit 1 to show message)
            sys.exit(1)

    # No validation issues
    sys.exit(0)

if __name__ == "__main__":
    main()
