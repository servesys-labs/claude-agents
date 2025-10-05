#!/usr/bin/env python3
"""
Pivot Detector Hook (UserPromptSubmit)

Detects when user is changing direction/deprecating features mid-conversation.
Suggests updating FEATURE_MAP.md to prevent documentation drift.

Triggers:
- "actually", "instead", "pivot", "change direction"
- "scrap", "deprecate", "remove", "no longer need"
- "let's try a different approach", "rethinking"
"""
import sys
import json
import re
from pathlib import Path

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

def get_feature_map_path() -> Path:
    """Get FEATURE_MAP.md path from working directory."""
    import os
    project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    return Path(project_root) / "FEATURE_MAP.md"

def save_pivot_state():
    """Save pivot detection timestamp for validation hook."""
    from datetime import datetime
    state_file = Path.home() / "claude-hooks" / "logs" / "pivot_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)

    state = {
        "last_pivot_time": datetime.now().isoformat(),
        "acknowledged": False
    }

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

    # Check for pivot
    is_pivot, pivot_matches = detect_pivot(content)
    has_doc_concern = detect_doc_concern(content)

    feature_map = get_feature_map_path()
    feature_map_exists = feature_map.exists()

    # If pivot detected, suggest FEATURE_MAP update
    if is_pivot:
        # Save pivot state for validation hook
        save_pivot_state()

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
        # Exit 1 to show this to user (non-blocking)
        sys.exit(1)

    # If documentation concern, suggest doc audit
    if has_doc_concern:
        print("\n📚 DOCUMENTATION CONCERN DETECTED", file=sys.stderr)
        print("", file=sys.stderr)
        print("User mentioned documentation issues.", file=sys.stderr)
        print("", file=sys.stderr)
        print("💡 OPTIONS:", file=sys.stderr)
        print("   • Use doc-consolidator agent to merge fragmented docs", file=sys.stderr)
        print("   • Use relevance-auditor agent to find stale docs", file=sys.stderr)
        print("   • Update FEATURE_MAP.md to mark obsolete features", file=sys.stderr)
        print("", file=sys.stderr)
        # Exit 1 to show this to user
        sys.exit(1)

    # No issues detected
    sys.exit(0)

if __name__ == "__main__":
    main()
