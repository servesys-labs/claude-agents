#!/usr/bin/env python3
"""
Unified Pivot Manager Hook (UserPromptSubmit)

Combines pivot detection and FEATURE_MAP validation in a single hook
to avoid race conditions between parallel execution.

This hook:
1. Detects pivot language in user prompts
2. Checks if FEATURE_MAP.md was recently updated
3. Provides appropriate guidance based on state
"""
import sys
import json
import re
import os
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# Pivot detection patterns
PIVOT_TRIGGERS = [
    # Direct pivot language
    r'\b(actually|instead|pivot|change\s+direction|change\s+course)\b',
    r'\b(scrap|deprecate|remove|no\s+longer\s+need|abandon)\b',
    r'\b(rethink|reconsider|different\s+approach|new\s+direction)\b',

    # Negation of previous work
    r'\b(nevermind|never\s+mind|forget\s+(that|it|about))\b',
    r'\b(don\'t\s+need|doesn\'t\s+make\s+sense|not\s+worth\s+it)\b',

    # Replacement language
    r'\b(replace|swap|switch\s+to|migrate\s+to|move\s+to)\b',
]

DOCUMENTATION_TRIGGERS = [
    r'\b(update\s+docs?|fix\s+docs?|documentation|readme)\b',
    r'\b(out\s+of\s+date|stale|obsolete|old\s+docs?)\b',
]

# Acknowledgment patterns
ACKNOWLEDGMENT_TRIGGERS = [
    "i've updated feature_map",
    "updated feature_map",
    "run pivot cleanup",
    "audit relevance",
    "feature_map is updated"
]

def get_feature_map_path() -> Path:
    """Get FEATURE_MAP.md path from working directory."""
    # Use official CLAUDE_PROJECT_DIR env var
    project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    return Path(project_root) / "FEATURE_MAP.md"

def detect_pivot(content: str) -> tuple[bool, list[str]]:
    """Detect if user is pivoting or changing direction."""
    content_lower = content.lower()

    matches = []
    for pattern in PIVOT_TRIGGERS:
        if re.search(pattern, content_lower):
            matches.append(pattern)

    return (len(matches) > 0, matches)

def detect_doc_concern(content: str) -> bool:
    """Detect if user mentions documentation issues."""
    content_lower = content.lower()
    return any(re.search(pattern, content_lower) for pattern in DOCUMENTATION_TRIGGERS)

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
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)

def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except:
        sys.exit(0)  # Not valid JSON, skip

    content = data.get("content", "")
    if not content:
        sys.exit(0)

    content_lower = content.lower()

    # Load persistent state
    state = load_pivot_state()

    # Check if user is acknowledging the pivot workflow
    if any(trigger in content_lower for trigger in ACKNOWLEDGMENT_TRIGGERS):
        # User is running the workflow - mark as acknowledged
        state["acknowledged"] = True
        save_pivot_state(state)
        sys.exit(0)

    # Check for expiration of old pivot state (5 minutes)
    if state.get("last_pivot_time"):
        try:
            pivot_time = datetime.fromisoformat(state["last_pivot_time"])
            if datetime.now() - pivot_time > timedelta(minutes=5):
                # Pivot was too long ago, reset state
                state = {"last_pivot_time": None, "acknowledged": False}
                save_pivot_state(state)
        except:
            pass

    # Check for new pivot detection
    is_pivot, pivot_matches = detect_pivot(content)
    has_doc_concern = detect_doc_concern(content)

    feature_map = get_feature_map_path()
    feature_map_exists = feature_map.exists()

    # Handle new pivot detection
    if is_pivot:
        # Save pivot state
        state = {
            "last_pivot_time": datetime.now().isoformat(),
            "acknowledged": False
        }
        save_pivot_state(state)

        # Check if FEATURE_MAP was already updated
        was_updated, details = check_recent_feature_map_updates()

        if was_updated:
            # FEATURE_MAP already updated - good!
            print("\n✅ PIVOT DETECTED + FEATURE_MAP ALREADY UPDATED", file=sys.stderr)
            print(f"   {details}", file=sys.stderr)
            print("", file=sys.stderr)
            print("💡 Say: \"Run the pivot cleanup workflow\" to:", file=sys.stderr)
            print("   → Auto-invoke RA (Relevance Auditor) to find obsolete code", file=sys.stderr)
            print("   → Auto-invoke ADU (Auto-Doc Updater) to sync documentation", file=sys.stderr)
            print("", file=sys.stderr)
            sys.exit(1)
        else:
            # Show pivot workflow
            print("\n🔄 PIVOT DETECTED", file=sys.stderr)
            print("", file=sys.stderr)
            print("Detected language suggesting direction change:", file=sys.stderr)
            print(f"  • {len(pivot_matches)} pivot indicator(s) found", file=sys.stderr)
            print("", file=sys.stderr)

            if feature_map_exists:
                print("📋 AUTOMATED PIVOT WORKFLOW:", file=sys.stderr)
                print("", file=sys.stderr)
                print("   STEP 1: Update FEATURE_MAP.md manually", file=sys.stderr)
                print("     • Move deprecated features to 'Deprecated Features' section", file=sys.stderr)
                print("     • Add new features to 'Active Features' section", file=sys.stderr)
                print("     • Update 'Pivot History' with reasoning", file=sys.stderr)
                print("", file=sys.stderr)
                print("   STEP 2: After updating FEATURE_MAP, say:", file=sys.stderr)
                print("     \"I've updated FEATURE_MAP. Run the pivot cleanup workflow.\"", file=sys.stderr)
                print("", file=sys.stderr)
                print("   Main Agent will then:", file=sys.stderr)
                print("     → Auto-invoke RA (Relevance Auditor) to find obsolete code", file=sys.stderr)
                print("     → Auto-invoke ADU (Auto-Doc Updater) to sync documentation", file=sys.stderr)
                print("     → Show you reports for review/approval", file=sys.stderr)
            else:
                print("⚠️  FEATURE_MAP.md not found in project root", file=sys.stderr)
                print("   Consider creating it to track feature evolution", file=sys.stderr)

            print("", file=sys.stderr)
            sys.exit(1)

    # Check for unacknowledged pivot requiring validation
    elif state.get("last_pivot_time") and not state.get("acknowledged"):
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
            sys.exit(1)

    # Handle documentation concerns (no pivot)
    elif has_doc_concern:
        print("\n📚 DOCUMENTATION CONCERN DETECTED", file=sys.stderr)
        print("", file=sys.stderr)
        print("User mentioned documentation issues.", file=sys.stderr)
        print("", file=sys.stderr)
        print("💡 OPTIONS:", file=sys.stderr)
        print("   • Use doc-consolidator agent to merge fragmented docs", file=sys.stderr)
        print("   • Use relevance-auditor agent to find stale docs", file=sys.stderr)
        print("   • Update FEATURE_MAP.md to mark obsolete features", file=sys.stderr)
        print("", file=sys.stderr)
        sys.exit(1)

    # No issues detected
    sys.exit(0)

if __name__ == "__main__":
    main()