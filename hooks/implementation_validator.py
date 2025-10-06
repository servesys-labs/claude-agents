#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Implementation Validator (IV)

Purpose:
- Validate that IE work aligns with the change plan and recent DIGEST
- Surface pending items before handoff to TA
- Keep output compact; default is fast, local-only checks

Inputs:
- .claude/logs/NOTES.md (last Subagent DIGEST)
- .claude/logs/wsi.json (recently touched files)

Outputs:
- Appends a compact IV result to WARNINGS.md (if gaps)
- Optionally appends a small validation note block to NOTES.md

Env toggles:
- ENABLE_IV (handled by caller; this script is safe to run anytime)
- IV_FAST_ONLY=true (default): do not call network/vector
- IV_WRITE_NOTES=true|false (default: true): append a compact IV note into NOTES.md

Exit codes:
- 0 always (fail-open, never block tool chain)
"""
import os, re, json, sys
from datetime import datetime
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
CLAUDE_DIR = os.path.join(PROJECT_ROOT, ".claude")
LOGS_DIR = os.environ.get("LOGS_DIR", os.path.join(CLAUDE_DIR, "logs"))
NOTES_PATH = os.path.join(LOGS_DIR, "NOTES.md")
WSI_PATH = os.path.join(LOGS_DIR, "wsi.json")
WARNINGS_PATH = os.path.join(LOGS_DIR, "WARNINGS.md")

IV_FAST_ONLY = os.environ.get("IV_FAST_ONLY", "true").lower() == "true"
IV_WRITE_NOTES = os.environ.get("IV_WRITE_NOTES", "true").lower() == "true"

def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def _load_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _ensure_file(path: str, header: Optional[str] = None) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            if header:
                f.write(header + "\n")

def _compact_line(s: str, limit: int = 100) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return (s[: limit - 1] + "…") if len(s) > limit else s

def _parse_last_digest(notes_text: str) -> Optional[Dict[str, Any]]:
    if not notes_text:
        return None
    try:
        # Find last header
        hdr_matches = re.findall(r"## \[(?P<ts>[^\]]+)\]\s+Subagent Digest\s+—\s+(?P<agent>[^—]+?)\s+—\s+task:(?P<task>[^\n]+)", notes_text)
        if not hdr_matches:
            return None
        ts, agent, task = hdr_matches[-1]
        header = f"## [{ts}] Subagent Digest — {agent} — task:{task}"
        mblock = re.search(re.escape(header) + r"(.*?)(?=\n## |\Z)", notes_text, re.DOTALL)
        block = mblock.group(1) if mblock else ""

        def _section(name: str) -> str:
            m = re.search(rf"\*\*{re.escape(name)}\*\*[\r\n]+(.*?)(?:\n\*\*|\Z)", block, re.DOTALL | re.IGNORECASE)
            return m.group(1) if m else ""

        def _bullets(txt: str) -> List[str]:
            out: List[str] = []
            for line in (txt or "").splitlines():
                s = line.strip()
                if s.startswith("- "):
                    out.append(s[2:].strip())
            return out

        decisions = _bullets(_section("Decisions"))
        files_lines = _bullets(_section("Files"))
        files = []
        for l in files_lines:
            # Format: path — reason … (anchors=...)
            p = l.split(" — ")[0].strip()
            if p:
                files.append(p)
        next_steps = _bullets(_section("Next Steps"))

        return {
            "timestamp": ts,
            "agent": agent.strip(),
            "task_id": task.strip(),
            "decisions": decisions,
            "files": files,
            "next": next_steps,
        }
    except Exception:
        return None

def _append_warning(message: str) -> None:
    _ensure_file(WARNINGS_PATH, "# WARNINGS\n\nUser-facing warnings and setup notices.")
    ts = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    try:
        with open(WARNINGS_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n## [{ts}]\n{message}\n")
    except Exception:
        pass

def _append_iv_note(task_id: str, summary: str, gaps: Dict[str, Any]) -> None:
    if not IV_WRITE_NOTES:
        return
    _ensure_file(NOTES_PATH, "# NOTES (living state)\n\nLast 20 digests. Older entries archived to logs/notes-archive/.\n")
    ts = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    decisions_text = f"- {summary}\n"
    missing_files = gaps.get("missing_files", [])
    pending_next = gaps.get("pending_next", [])
    files_lines = "\n".join(f"- {p}" for p in missing_files) or "- n/a"
    next_lines = "\n".join(f"- {n}" for n in pending_next) or "- n/a"

    block = (
        f"## [{ts}] Subagent Digest — IV — task:{task_id}-validation\n\n"
        f"**Decisions**\n{decisions_text}\n"
        f"**Files (missing from WSI)**\n{files_lines}\n\n"
        f"**Next Steps (pending)**\n{next_lines}\n"
    )
    try:
        with open(NOTES_PATH, "a", encoding="utf-8") as f:
            f.write(block)
    except Exception:
        pass

def main():
    try:
        notes = _read_text(NOTES_PATH)
        last = _parse_last_digest(notes)
        wsi = _load_json(WSI_PATH, {"items": []})
        touched = set()
        if isinstance(wsi, dict):
            for it in wsi.get("items", []) or []:
                p = (it or {}).get("path")
                if p:
                    touched.add(p)

        summary = "Validation passed"
        gaps: Dict[str, Any] = {"missing_files": [], "pending_next": []}

        if last:
            # Files expected by digest but not seen in WSI (recent activity)
            missing = [p for p in (last.get("files") or []) if p not in touched]
            if missing:
                gaps["missing_files"] = missing
            # Pending next steps
            if last.get("next"):
                gaps["pending_next"] = list(last["next"])

        # Decide output
        has_gaps = bool(gaps["missing_files"]) or bool(gaps["pending_next"])
        if has_gaps:
            summary = _compact_line(
                f"Validation needs follow-up — missing_files={len(gaps['missing_files'])}, pending_next={len(gaps['pending_next'])}"
            )
            _append_warning(
                f"IV: {summary}\n"
                f"Task: {(last or {}).get('task_id', 'unknown')}\n"
                f"Missing files: {gaps['missing_files'][:5]}{' …' if len(gaps['missing_files'])>5 else ''}\n"
                f"Pending next: {gaps['pending_next'][:5]}{' …' if len(gaps['pending_next'])>5 else ''}"
            )
        else:
            summary = "Validation passed — ready for TA"

        # Append compact IV note to NOTES
        _append_iv_note((last or {}).get("task_id", "unknown"), summary, gaps)

    except Exception:
        # Fail-open
        pass
    finally:
        # Never block the pipeline
        sys.exit(0)

if __name__ == "__main__":
    main()

