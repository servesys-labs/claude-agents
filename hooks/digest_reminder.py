#!/usr/bin/env python3
"""
DIGEST Reminder Hook (PostToolUse for Task tool)

Gently reminds Main Agent to request DIGEST blocks from subagents after N minutes.

Environment variables:
- DIGEST_REMINDER_MINUTES: Minutes to wait before reminding (default: 0 = disabled)

Exit codes:
- 0: No reminder (within time window or disabled)
- 1: Gentle reminder shown (non-blocking)
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta

# Config
REMINDER_MINUTES = int(os.environ.get("DIGEST_REMINDER_MINUTES", "0"))
LOGS_DIR = Path(os.environ.get("LOGS_DIR", os.path.expanduser("~/claude-hooks/logs")))
STATE_FILE = LOGS_DIR / "digest_reminder_state.json"

# Auto-create logs directory
LOGS_DIR.mkdir(parents=True, exist_ok=True)

def load_state():
    """Load last Task invocation timestamp."""
    if not STATE_FILE.exists():
        return None
    try:
        with STATE_FILE.open("r") as f:
            data = json.load(f)
            return datetime.fromisoformat(data["last_task_time"])
    except Exception:
        return None

def save_state():
    """Save current timestamp."""
    try:
        with STATE_FILE.open("w") as f:
            json.dump({"last_task_time": datetime.now().isoformat()}, f)
    except Exception:
        pass

def main():
    """Check if reminder is due."""
    # Skip if disabled
    if REMINDER_MINUTES == 0:
        sys.exit(0)

    last_task_time = load_state()
    now = datetime.now()

    # First Task invocation or state file missing
    if last_task_time is None:
        save_state()
        sys.exit(0)

    # Check if enough time has passed
    elapsed = now - last_task_time
    threshold = timedelta(minutes=REMINDER_MINUTES)

    if elapsed >= threshold:
        # Show reminder
        print(
            f"\n💡 Reminder: It's been {REMINDER_MINUTES} minutes since last Task invocation. "
            "Have you requested DIGEST blocks from subagents? "
            "Subagents should return structured JSON DIGESTs for context efficiency.\n",
            file=sys.stderr
        )
        # Reset timer
        save_state()
        sys.exit(1)  # Non-blocking, just shows message
    else:
        # Within time window, no reminder
        sys.exit(0)

if __name__ == "__main__":
    main()
