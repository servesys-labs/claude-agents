#!/usr/bin/env python3
"""
Task DIGEST Capture Hook (PostToolUse)

Runs after Task tool completes. Scans the subagent's output for DIGEST blocks
and automatically appends them to NOTES.md.

This solves the Stop hook limitation by capturing DIGEST blocks in real-time
as subagents complete their work.
"""
import sys
import json
import re
import os
from datetime import datetime
from pathlib import Path

# Config
# Per-project logs (injected by settings.json), fallback to global
LOGS_DIR = os.environ.get("LOGS_DIR", os.path.expanduser("~/claude-hooks/logs"))
WSI_PATH = os.environ.get("WSI_PATH", os.path.join(LOGS_DIR, "wsi.json"))

# Auto-create logs directory
os.makedirs(LOGS_DIR, exist_ok=True)

# Use official CLAUDE_PROJECT_DIR env var for project-specific files
PROJECT_ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
NOTES_PATH = os.path.join(PROJECT_ROOT, "NOTES.md")
WSI_CAP = 10

DIGEST_RE = re.compile(r"```json\s*DIGEST\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)

debug_log = os.path.join(LOGS_DIR, "task_digest_debug.log")

def log_debug(message):
    """Write to debug log."""
    with open(debug_log, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {message}\n")

def extract_digest(text):
    """Extract DIGEST block from text."""
    m = DIGEST_RE.search(text or "")
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception as e:
        log_debug(f"Failed to parse DIGEST JSON: {e}")
        return None

def append_to_notes(digest):
    """Append DIGEST to NOTES.md."""
    # Ensure NOTES.md exists
    Path(NOTES_PATH).parent.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(NOTES_PATH):
        with open(NOTES_PATH, "w", encoding="utf-8") as f:
            f.write("# NOTES.md - Agent Digest Archive\n\n")
            f.write("Last 20 digests. Auto-captured from subagent work.\n\n---\n\n")

    ts = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    agent = digest.get("agent", "UNKNOWN")
    task_id = digest.get("task_id", "untagged")
    decisions = digest.get("decisions", [])
    files = digest.get("files", [])
    contracts = digest.get("contracts", [])
    next_steps = digest.get("next", [])
    evidence = digest.get("evidence", {})

    # Format files list
    files_text = "\n".join(
        f"  - {f.get('path')} — {f.get('reason', 'modified')}"
        for f in files
    ) or "  - n/a"

    block = f"""
## [{ts}] {agent} — {task_id}

**Decisions**
{chr(10).join(f'  - {d}' for d in decisions) or '  - n/a'}

**Files**
{files_text}

**Contracts Affected**
{chr(10).join(f'  - {c}' for c in contracts) or '  - n/a'}

**Next Steps**
{chr(10).join(f'  - {n}' for n in next_steps) or '  - n/a'}

**Evidence**
{chr(10).join(f'  - {k}: {v}' for k, v in evidence.items()) or '  - n/a'}

---
"""

    with open(NOTES_PATH, "a", encoding="utf-8") as f:
        f.write(block)

    log_debug(f"✅ Appended {agent} digest to NOTES.md")

def update_wsi(digest):
    """Update WSI with files from DIGEST."""
    # Load existing WSI
    wsi = {"items": []}
    if os.path.exists(WSI_PATH):
        try:
            with open(WSI_PATH, "r") as f:
                wsi = json.load(f)
        except:
            pass

    items = wsi.get("items", [])

    # Add files from this digest
    for f in digest.get("files", []):
        path = f.get("path")
        if path:
            # Remove duplicates
            items = [item for item in items if item.get("path") != path]
            # Add new entry
            items.append({
                "path": path,
                "reason": f.get("reason", "touched"),
                "anchors": f.get("anchors", [])
            })

    # Keep last N items
    items = items[-WSI_CAP:]
    wsi["items"] = items

    # Save
    Path(WSI_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(WSI_PATH, "w") as f:
        json.dump(wsi, f, indent=2)

    log_debug(f"✅ Updated WSI with {len(digest.get('files', []))} files")

def main():
    # Read hook input
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except:
        log_debug("Invalid JSON input")
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_output = data.get("tool_output", "")

    # Only process Task tool completions
    if tool_name != "Task":
        sys.exit(0)

    log_debug(f"Task tool completed, scanning for DIGEST...")

    # Extract DIGEST from tool output
    # tool_output might be string or dict
    if isinstance(tool_output, dict):
        # Look for common keys that might contain the response
        text = (
            tool_output.get("response", "")
            or tool_output.get("result", "")
            or tool_output.get("output", "")
            or str(tool_output)
        )
    else:
        text = str(tool_output)

    digest = extract_digest(text)

    if digest:
        log_debug(f"🎯 DIGEST found: agent={digest.get('agent')}, task={digest.get('task_id')}")

        try:
            append_to_notes(digest)
            update_wsi(digest)

            # Show success message to user
            print("", file=sys.stderr)
            print(f"✅ Captured DIGEST from {digest.get('agent')} agent", file=sys.stderr)
            print(f"   → Added to NOTES.md", file=sys.stderr)
            print(f"   → Updated WSI with {len(digest.get('files', []))} files", file=sys.stderr)
            print("", file=sys.stderr)

        except Exception as e:
            log_debug(f"❌ Failed to write DIGEST: {e}")
            print(f"⚠️ Failed to capture DIGEST: {e}", file=sys.stderr)
    else:
        log_debug("No DIGEST block found in Task output")

    # Exit 0 (non-blocking)
    sys.exit(0)

if __name__ == "__main__":
    main()
