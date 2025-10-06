#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PreCompact hook: produce a compact, durable summary before the conversation is compacted.

Inputs: JSON on stdin (may contain recent messages or assistant text).
Outputs:
- .claude/logs/compaction-summary.json (machine-readable)
- .claude/logs/COMPACTION.md (human-readable)
- (optional) gzip older logs in ./logs

Exit codes:
- 0: success (quiet)
- 1: soft failure (show to user, continue)
- 2: reserved for hard block (not used here)
"""

import sys, os, re, json, gzip, shutil
from datetime import datetime
from pathlib import Path

# Per-project logs (injected by settings.json), fallback to global
LOGS_DIR_STR = os.environ.get("LOGS_DIR", os.path.expanduser("~/claude-hooks/logs"))
WSI_PATH = Path(os.environ.get("WSI_PATH", str(Path(LOGS_DIR_STR) / "wsi.json")))

# Auto-create logs directory
CLAUDE_LOGS_DIR = Path(LOGS_DIR_STR)
CLAUDE_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Use official CLAUDE_PROJECT_DIR env var
PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
NOTES_PATH   = CLAUDE_LOGS_DIR / "NOTES.md"
SUMMARY_JSON = CLAUDE_LOGS_DIR / "compaction-summary.json"
SUMMARY_MD   = CLAUDE_LOGS_DIR / "COMPACTION.md"
LOGS_DIR     = PROJECT_ROOT / "logs"  # Old logs in project (different from CLAUDE_LOGS_DIR)
MAX_DIGESTS  = int(os.environ.get("COMPACT_MAX_DIGESTS", "8"))
GZIP_OLD_LOGS = os.environ.get("COMPACT_GZIP_OLD_LOGS", "0") == "1"

DIGEST_RE = re.compile(r"```json\s*DIGEST\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)

def read_stdin_json():
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def read_file(path):
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def get_recent_hook_changes():
    """Get recently modified files in ~/claude-hooks/ (last 2 hours)."""
    from datetime import timedelta
    import time

    hooks_dir = Path.home() / "claude-hooks"
    if not hooks_dir.exists():
        return []

    cutoff_time = time.time() - (2 * 3600)  # 2 hours ago
    recent_files = []

    # Ignore patterns
    ignore_patterns = [
        '.mypy_cache',
        '__pycache__',
        '.pytest_cache',
        'logs/read_cache.json',
        'logs/context-metrics.jsonl',
        'logs/stop_hook_debug.log',
        'logs/task_digest_debug.log',
        'logs/checkpoints',
        '.DS_Store',
        'COMPACTION.md',  # Recursion!
        'compaction-summary.json'  # Recursion!
    ]

    try:
        for filepath in hooks_dir.rglob("*"):
            if not filepath.is_file() or filepath.stat().st_mtime <= cutoff_time:
                continue

            # Skip ignored patterns
            rel_path = filepath.relative_to(hooks_dir)
            if any(pattern in str(rel_path) for pattern in ignore_patterns):
                continue

            recent_files.append(f"~/claude-hooks/{rel_path}")
    except:
        pass

    return recent_files

def get_git_changes():
    """Fallback: extract changes from recent commits + uncommitted when no DIGEST blocks available."""
    import subprocess
    changes = {
        "modified_files": [],
        "new_files": [],
        "summary": []
    }

    try:
        # Strategy 1: Get uncommitted changes (if any)
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=PROJECT_ROOT
        )

        uncommitted_count = 0
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                status = line[:2].strip()
                filepath = line[3:].strip()

                if status == 'M':
                    changes["modified_files"].append(filepath)
                    uncommitted_count += 1
                elif status in ('A', '??'):
                    changes["new_files"].append(filepath)
                    uncommitted_count += 1

        # Strategy 2: If no uncommitted changes, look at recent commits (last 3)
        if uncommitted_count == 0:
            result = subprocess.run(
                ["git", "log", "-3", "--name-status", "--pretty=format:COMMIT:%s"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=PROJECT_ROOT
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if not line.strip():
                        continue

                    # Parse commit messages
                    if line.startswith('COMMIT:'):
                        commit_msg = line.replace('COMMIT:', '').strip()
                        if commit_msg not in changes["summary"]:
                            changes["summary"].append(commit_msg)
                        continue

                    # Parse git log output (M/A/D<tab>filename)
                    if '\t' in line:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            status, filepath = parts[0].strip(), parts[1].strip()
                            if status == 'M' and filepath not in changes["modified_files"]:
                                changes["modified_files"].append(filepath)
                            elif status == 'A' and filepath not in changes["new_files"]:
                                changes["new_files"].append(filepath)

    except:
        pass

    return changes

def extract_feature_map_updates():
    """Extract recent updates from FEATURE_MAP.md if it exists."""
    feature_map_path = PROJECT_ROOT / "FEATURE_MAP.md"
    if not feature_map_path.exists():
        return []

    content = read_file(feature_map_path)
    updates = []

    # Extract active features from table
    in_active_section = False
    for line in content.split('\n'):
        if '## 🎯 Active Features' in line:
            in_active_section = True
            continue
        if in_active_section and line.startswith('##'):
            break
        if in_active_section and line.strip().startswith('|') and '✅ Active' in line:
            # Extract feature name from table row
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2:
                feature = parts[0].replace('**', '').strip()
                if feature and feature != 'Feature':
                    updates.append(feature)

    return updates

def extract_digests_from_text(text):
    digests = []
    for m in DIGEST_RE.finditer(text or ""):
        try:
            digests.append(json.loads(m.group(1)))
        except Exception:
            continue
    return digests

def extract_digests_from_payload(payload):
    digests = []
    # Common shapes: messages list with role/content; or assistant_text/final_message fields
    if isinstance(payload, dict):
        # try flat text fields
        for k in ("assistant_text", "final_message", "content"):
            if k in payload and isinstance(payload[k], str):
                digests += extract_digests_from_text(payload[k])

        # try messages array
        msgs = payload.get("messages") or payload.get("history") or []
        for m in msgs:
            if isinstance(m, dict):
                for k in ("text", "content", "message", "assistant_text"):
                    v = m.get(k)
                    if isinstance(v, str):
                        digests += extract_digests_from_text(v)
    return digests[-MAX_DIGESTS:]

def build_summary(digests, notes_text, wsi):
    # Roll-up fields from digests
    decisions, open_qs, owned_artifacts, risks, next_steps = [], [], [], [], []
    contracts, files = [], []
    agents_seen = set()

    for d in digests:
        agent = d.get("agent") or "UNKNOWN"
        agents_seen.add(agent)
        decisions += (d.get("decisions") or [])
        next_steps += (d.get("next") or [])
        contracts += (d.get("contracts") or [])
        for f in (d.get("files") or []):
            path = f.get("path")
            if path:
                reason = f.get("reason","")
                owned_artifacts.append(path)
                files.append({"path": path, "reason": reason, "anchors": f.get("anchors", [])})

    # Heuristic: pull Open Questions / Risks sections from NOTES.md if present
    def scrape_section(title):
        if not notes_text:
            return []
        # very simple markdown section scraper
        pattern = rf"^##\s*{re.escape(title)}\s*\n(.*?)(?:\n## |\Z)"
        m = re.search(pattern, notes_text, re.DOTALL | re.MULTILINE | re.IGNORECASE)
        if not m:
            return []
        body = m.group(1).strip()
        items = [ln.strip("-* ").strip() for ln in body.splitlines() if ln.strip()]
        return items

    open_qs = scrape_section("Open Questions")
    risks   = scrape_section("Risks") or scrape_section("Risks / Assumptions") or scrape_section("Risk/Assumptions")

    # Deduplicate while preserving order
    def dedupe(seq):
        seen = set(); out=[]
        for x in seq:
            if x in seen: continue
            seen.add(x); out.append(x)
        return out

    decisions       = dedupe(decisions)
    next_steps      = dedupe(next_steps)
    contracts       = dedupe(contracts)
    owned_artifacts = dedupe(owned_artifacts)

    wsi_items = (wsi or {}).get("items", [])
    ts = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

    summary = {
        "timestamp": ts,
        "agents_seen": sorted(list(agents_seen)),
        "decisions": decisions,
        "open_questions": open_qs,
        "owned_artifacts": owned_artifacts,
        "contracts_touched": contracts,
        "files_touched": files,
        "risks": risks,
        "next_steps": next_steps,
        "wsi_snapshot": wsi_items
    }
    return summary

def write_summary_files(summary):
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Human-readable markdown with Anthropic-recommended structure
    md = [f"# Compaction Summary — {summary['timestamp']}\n\n"]

    # Add high-level context first (per Anthropic: "right altitude")
    md.append("## Executive Summary\n")
    md.append(f"- Agents active: {', '.join(summary.get('agents_seen', ['none']))}\n")
    md.append(f"- Files modified: {len(summary.get('owned_artifacts', []))}\n")
    md.append(f"- Contracts affected: {len(summary.get('contracts_touched', []))}\n")
    md.append(f"- Open questions: {len(summary.get('open_questions', []))}\n")
    md.append("\n")

    # Critical decisions (most important for resumption)
    md.append("## Key Decisions (retain for context)\n")
    decisions = summary.get("decisions", [])
    if not decisions:
        md.append("- n/a\n")
    else:
        for d in decisions[:5]:  # Limit to top 5 most recent
            md.append(f"- {d}\n")
    md.append("\n")

    # Next steps (actionable items)
    md.append("## Next Steps (actionable)\n")
    next_steps = summary.get("next_steps", [])
    if not next_steps:
        md.append("- n/a\n")
    else:
        for n in next_steps:
            md.append(f"- [ ] {n}\n")  # Checklist format
    md.append("\n")

    # Critical paths (lightweight identifiers for JIT retrieval)
    md.append("## Critical Paths (for JIT retrieval)\n")
    owned = summary.get("owned_artifacts", [])
    if not owned:
        md.append("- n/a\n")
    else:
        for path in owned[:10]:  # Limit to top 10 most relevant
            md.append(f"- `{path}`\n")
    md.append("\n")

    # Contracts (API/schema stability)
    md.append("## Contracts Touched (verify stability)\n")
    contracts = summary.get("contracts_touched", [])
    if not contracts:
        md.append("- n/a\n")
    else:
        for c in contracts:
            md.append(f"- {c}\n")
    md.append("\n")

    # Open questions (blockers)
    md.append("## Open Questions (needs resolution)\n")
    open_qs = summary.get("open_questions", [])
    if not open_qs:
        md.append("- n/a\n")
    else:
        for q in open_qs:
            md.append(f"- ❓ {q}\n")
    md.append("\n")

    # Risks (awareness)
    md.append("## Risks / Assumptions\n")
    risks = summary.get("risks", [])
    if not risks:
        md.append("- n/a\n")
    else:
        for r in risks:
            md.append(f"- ⚠️ {r}\n")
    md.append("\n")

    # WSI snapshot (minimal, for reference)
    md.append("<details>\n<summary>WSI Snapshot (expand if needed)</summary>\n\n")
    wsi_items = summary.get("wsi_snapshot", [])
    if not wsi_items:
        md.append("- n/a\n")
    else:
        for it in wsi_items:
            if isinstance(it, dict):
                path = it.get("path", "")
                reason = it.get("reason", "")
                md.append(f"- {path} — {reason}\n")
            else:
                md.append(f"- {it}\n")
    md.append("</details>\n\n")

    SUMMARY_MD.write_text("".join(md), encoding="utf-8")

def gzip_old_logs():
    if not LOGS_DIR.exists():
        return
    for p in LOGS_DIR.glob("**/*"):
        if p.is_file() and not p.suffix.endswith(".gz") and p.stat().st_size > 0:
            gz = p.with_suffix(p.suffix + ".gz")
            try:
                with open(p, "rb") as f_in, gzip.open(gz, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                p.unlink(missing_ok=True)
            except Exception:
                # best-effort; ignore failures
                pass

def main():
    payload = read_stdin_json()
    notes_text = read_file(NOTES_PATH)
    wsi = load_json(WSI_PATH, {"items": []})

    # Strategy 1: Extract DIGESTs from NOTES.md (primary source - populated by Task hook)
    digests = extract_digests_from_text(notes_text) if notes_text else []

    # Strategy 2: Try extracting from payload (may not work in Claude Code)
    if not digests:
        digests = extract_digests_from_payload(payload)

    # Strategy 3 (FALLBACK): If no digests found anywhere, use git changes + hook changes + FEATURE_MAP
    if not digests:
        git_changes = get_git_changes()
        hook_changes = get_recent_hook_changes()
        feature_updates = extract_feature_map_updates()

        # Create a synthetic digest from git changes + hook changes
        all_files = git_changes["modified_files"] + git_changes["new_files"] + hook_changes
        if all_files or feature_updates:
            synthetic_digest = {
                "agent": "Main Agent (Direct Work)",
                "decisions": feature_updates[:8] if feature_updates else git_changes["summary"][:3] if git_changes["summary"] else ["Configuration and hook updates"],
                "files": [],
                "next": [],
                "contracts": []
            }

            # Add git modified files
            for filepath in git_changes["modified_files"][:10]:
                synthetic_digest["files"].append({
                    "path": filepath,
                    "reason": "modified",
                    "anchors": []
                })

            # Add git new files
            for filepath in git_changes["new_files"][:10]:
                synthetic_digest["files"].append({
                    "path": filepath,
                    "reason": "created",
                    "anchors": []
                })

            # Add hook changes
            for filepath in hook_changes[:15]:
                synthetic_digest["files"].append({
                    "path": filepath,
                    "reason": "updated hook",
                    "anchors": []
                })

            digests = [synthetic_digest]

    summary = build_summary(digests, notes_text, wsi)
    try:
        write_summary_files(summary)
        if GZIP_OLD_LOGS:
            gzip_old_logs()

        # Run context metrics tracker
        import subprocess
        metrics_script = Path(__file__).parent / "context_metrics.py"
        if metrics_script.exists():
            try:
                subprocess.run(
                    ["python3", str(metrics_script)],
                    input=json.dumps(payload, ensure_ascii=False),
                    text=True,
                    capture_output=True,
                    timeout=5
                )
            except:
                pass  # Non-critical, continue

    except Exception as e:
        print(f"PreCompact hook: failed to write summaries: {e}", file=sys.stderr)
        sys.exit(1)

    # quiet success
    sys.exit(0)

if __name__ == "__main__":
    main()
