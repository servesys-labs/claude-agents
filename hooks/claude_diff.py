#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compare the current CLAUDE.md with the backed up version and report drift.

Backups are expected at: .claude/logs/CLAUDE.md.backup

Usage examples:
  - Show summary JSON:
      python hooks/claude_diff.py --summary
  - Write a markdown report:
      python hooks/claude_diff.py --report
  - Initialize backup from current CLAUDE.md (if missing):
      python hooks/claude_diff.py --init-backup
  - Exit non‑zero if differences are detected:
      python hooks/claude_diff.py --summary --exit-on-change
"""
import os
import sys
import json
from typing import Dict, Any
import difflib

PROJECT_ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
CLAUDE_DIR = os.path.join(PROJECT_ROOT, ".claude")
LOGS_DIR = os.path.join(CLAUDE_DIR, "logs")
CUR_PATH = os.path.join(PROJECT_ROOT, "CLAUDE.md")
BACKUP_PATH = os.path.join(LOGS_DIR, "CLAUDE.md.backup")
REPORT_PATH = os.path.join(LOGS_DIR, "CLAUDE_DIFF.md")

def read_text(p: str) -> str:
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def write_text(p: str, s: str) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)

def compute_diff(old: str, new: str) -> Dict[str, Any]:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile='CLAUDE.md.backup', tofile='CLAUDE.md'))
    added = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
    removed = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))
    changed = (added + removed) > 0
    return {
        "changed": changed,
        "added_lines": added,
        "removed_lines": removed,
        "diff": "".join(diff)
    }

def as_markdown(summary: Dict[str, Any]) -> str:
    lines = ["# CLAUDE.md Drift Report\n"]
    lines.append(f"Changed: {'YES' if summary['changed'] else 'NO'}\n")
    lines.append(f"Added lines: {summary['added_lines']}\n")
    lines.append(f"Removed lines: {summary['removed_lines']}\n\n")
    lines.append("## Unified Diff\n")
    lines.append("```diff\n")
    # Trim extremely long diffs for readability
    diff_text = summary.get("diff", "")
    lines.append(diff_text)
    lines.append("\n```\n")
    return "".join(lines)

def main():
    args = set(sys.argv[1:])
    init_backup = "--init-backup" in args
    want_summary = "--summary" in args
    want_report = "--report" in args
    exit_on_change = "--exit-on-change" in args

    cur = read_text(CUR_PATH)
    if not cur:
        print(json.dumps({"ok": False, "error": f"Missing {CUR_PATH}"}, indent=2))
        sys.exit(1)

    backup = read_text(BACKUP_PATH)
    if not backup:
        if init_backup:
            os.makedirs(LOGS_DIR, exist_ok=True)
            write_text(BACKUP_PATH, cur)
            print(json.dumps({"ok": True, "initialized_backup": True, "path": BACKUP_PATH}, indent=2))
            return
        else:
            print(json.dumps({"ok": False, "error": f"Missing backup at {BACKUP_PATH}", "hint": "Run with --init-backup to create from current"}, indent=2))
            sys.exit(1)

    summary = compute_diff(backup, cur)

    if want_report:
        report_md = as_markdown(summary)
        write_text(REPORT_PATH, report_md)

    if want_summary or not want_report:
        out = {
            "ok": True,
            "changed": summary["changed"],
            "added_lines": summary["added_lines"],
            "removed_lines": summary["removed_lines"],
            "report_path": (REPORT_PATH if want_report else None)
        }
        print(json.dumps(out, indent=2))

    if exit_on_change and summary["changed"]:
        sys.exit(2)

if __name__ == "__main__":
    main()

