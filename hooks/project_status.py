#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Status updater:
- Queries local vector memory (via MCP) and local logs to synthesize a crisp status block
- Updates/inserts a <project_status> ... </project_status> block in CLAUDE.md idempotently
- Can be run periodically via launchd (see --emit-launchd-plist)
"""
import os, sys, json, re, hashlib, time, random
from datetime import datetime
from typing import List, Dict, Any, Optional, cast

PROJECT_ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
CLAUDE_DIR = os.path.join(PROJECT_ROOT, ".claude")
LOGS_DIR = os.environ.get("LOGS_DIR", os.path.join(CLAUDE_DIR, "logs"))
WSI_PATH = os.environ.get("WSI_PATH", os.path.join(LOGS_DIR, "wsi.json"))
WARNINGS_PATH = os.path.join(LOGS_DIR, "WARNINGS.md")
CLAUDE_MD_PATH = os.path.join(PROJECT_ROOT, "CLAUDE.md")

def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def _is_global_root() -> bool:
    try:
        return os.path.realpath(PROJECT_ROOT) == os.path.realpath(os.path.expanduser("~/.claude"))
    except Exception:
        return False

def _should_skip_update() -> Optional[str]:
    """Return reason string if CLAUDE.md project_status update should be skipped."""
    # Explicit environment opt-out
    if os.environ.get("DISABLE_CLAUDE_MD_UPDATE", "false").lower() == "true":
        return "env:DISABLE_CLAUDE_MD_UPDATE"
    # Global ~/.claude by default is stable — skip unless explicitly allowed
    if _is_global_root() and os.environ.get("ALLOW_GLOBAL_CLAUDE_MD_UPDATE", "false").lower() != "true":
        return "global_root_protected"
    return None

_ensure_dir(LOGS_DIR)

def call_vector_bridge_mcp(tool_name: str, params: Dict[str, Any], timeout_sec: int = 8) -> Optional[Dict[str, Any]]:
    import subprocess
    try:
        mcp_cmd = ["node", os.path.expanduser("~/.claude/mcp-servers/vector-bridge/dist/index.js")]

        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "project-status-updater", "version": "1.0.0"}
            }
        }
        tool_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": params}
        }

        proc = subprocess.Popen(
            mcp_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ}
        )
        requests = f"{json.dumps(init_request)}\n{json.dumps(tool_request)}\n"
        try:
            stdout, stderr = proc.communicate(input=requests, timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            return {"error": f"MCP call timed out after {timeout_sec}s"}

        responses = []
        for line in (stdout or "").strip().split('\n'):
            if line.strip():
                try:
                    responses.append(json.loads(line))
                except Exception:
                    pass
        for resp in responses:
            if resp.get("id") == 2:
                return resp.get("result", {})
        return None
    except Exception as e:
        return {"error": str(e)}

def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def _compact_line(s: str, limit: int = 85) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return (s[:limit-1] + "…") if len(s) > limit else s

def _extract_recent_from_notes(notes_text: str, count: int = 3) -> Dict[str, List[str]]:
    # Parse last N digest sections and return decisions + components
    if not notes_text:
        return {"decisions": [], "components": []}
    sections = re.findall(r"## \[.*?\](.*?)(?=\n## |\Z)", notes_text, re.DOTALL)
    sections = sections[-count:] if sections else []
    decisions: List[str] = []
    components: List[str] = []
    for sec in sections:
        # Decisions bullets
        m = re.search(r"\*\*Decisions\*\*[\r\n]+(.*?)(?:\n\*\*|\Z)", sec, re.DOTALL)
        if m:
            for line in m.group(1).splitlines():
                line = line.strip()
                if line.startswith("- "):
                    decisions.append(_compact_line(line[2:]))
        # Files list
        mf = re.search(r"\*\*Files\*\*[\r\n]+(.*?)(?:\n\*\*|\Z)", sec, re.DOTALL)
        if mf:
            for line in mf.group(1).splitlines():
                p = line.strip()
                if p.startswith("- "):
                    pth = p[2:].split(" — ")[0].strip()
                    if pth:
                        components.append(os.path.basename(pth))
    return {"decisions": decisions[:3], "components": list(dict.fromkeys(components))[:5]}

def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        # Support both naive and aware ISO strings
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None

def _vector_search_local(query: str, k: int = 6, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    enable = os.environ.get("ENABLE_VECTOR_RAG", "false").lower() == "true"
    if not enable:
        return []
    args = {"project_root": PROJECT_ROOT, "query": query, "k": k, "global": False}
    if filters:
        args["filters"] = filters
    result = call_vector_bridge_mcp("memory_search", args)
    if not result or "content" not in result:
        return []
    content = result["content"][0] if isinstance(result["content"], list) else result["content"]
    text = content.get("text", "") if isinstance(content, dict) else str(content)
    try:
        obj = json.loads(text)
        results = obj.get("results", [])
        # Normalize timestamps if present
        for r in results:
            if "updated_at" in r and isinstance(r["updated_at"], str):
                r["_updated_dt"] = _parse_iso(r["updated_at"]) or None
            elif "meta" in r and isinstance(r["meta"], dict):
                r["_updated_dt"] = _parse_iso(r["meta"].get("updated_at")) or None
        return results
    except Exception:
        return []

def _age_days(dt: Optional[datetime]) -> float:
    if not dt:
        return 0.0
    try:
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        return max(0.0, (now - dt).total_seconds() / 86400.0)
    except Exception:
        return 0.0

def _score_decision(r: Dict[str, Any]) -> float:
    meta = r.get("meta", {}) if isinstance(r.get("meta"), dict) else {}
    rtype = (meta.get("type") or meta.get("category") or "decision").lower()
    type_w = {"decision": 1.0, "incident": 0.9, "status": 0.8}.get(rtype, 0.7)
    age = _age_days(r.get("_updated_dt"))
    decay = 2.71828 ** (-0.05 * age)  # half-life ~14 days
    return type_w * decay

def _score_risk(r: Dict[str, Any]) -> float:
    meta = r.get("meta", {}) if isinstance(r.get("meta"), dict) else {}
    ptype = (meta.get("problem_type") or "").lower()
    sev_w = {
        "security": 1.0,
        "data": 0.95,
        "infra": 0.9,
        "regression": 0.88,
        "build": 0.8,
        "timeout": 0.7,
    }.get(ptype, 0.75)
    age = _age_days(r.get("_updated_dt"))
    decay = 2.71828 ** (-0.05 * age)
    return sev_w * decay

def _extract_next_steps_from_text(text: str, limit: int = 3) -> List[str]:
    out: List[str] = []
    if not text:
        return out
    # Look for "Next:" or "Next Steps:" sections and bullet lines
    m = re.search(r"Next(?:\s*Steps)?\s*:\s*(.*)", text, re.IGNORECASE | re.DOTALL)
    if m:
        block = m.group(1)
        for line in block.splitlines():
            s = line.strip()
            if s.startswith(("- ", "* ", "1.", "2.", "3.")):
                s = re.sub(r"^[\-*0-9\.\s]+", "", s)
                if s:
                    out.append(_compact_line(s))
            elif s and len(out) < limit:
                out.append(_compact_line(s))
            if len(out) >= limit:
                break
    # Fallback: look for "Next" phrases inline
    if not out:
        for line in text.splitlines():
            s = line.strip()
            if s.lower().startswith("next") and ":" in s:
                out.append(_compact_line(s.split(":", 1)[1].strip()))
            if len(out) >= limit:
                break
    # Dedup
    dd = []
    seen = set()
    for s in out:
        if s not in seen:
            seen.add(s)
            dd.append(s)
    return dd[:limit]

def _extract_eta_from_text(text: str) -> List[str]:
    if not text:
        return []
    out = []
    # Pattern: ETA: <text>
    for m in re.finditer(r"ETA\s*:\s*([^\n]+)", text, re.IGNORECASE):
        out.append(_compact_line(m.group(1)))
    # Pattern: by <date/weekday/time>
    for m in re.finditer(r"\bby\s+(\w{3,9}(?:\s+\d{1,2}(?:st|nd|rd|th)?|\s*EOD|\s*EOW|\s*tomorrow|\s*today)\b[\w\s:]*)", text, re.IGNORECASE):
        out.append(_compact_line(m.group(0)))
    # Dedup
    dd = []
    seen = set()
    for s in out:
        if s not in seen:
            seen.add(s)
            dd.append(s)
    return dd[:2]

def _mention_bonus(text: str, meta: Dict[str, Any], active: List[str], hot: Optional[List[str]] = None) -> float:
    try:
        blob = (text or "") + " " + " ".join(str(v) for v in meta.values() if isinstance(v, (str, int)))
        blob = blob.lower()
        if hot:
            for name in hot:
                n = (name or "").strip().lower()
                if len(n) >= 3 and n in blob:
                    return 1.25
        for name in active:
            n = (name or "").strip().lower()
            if len(n) >= 3 and n in blob:
                return 1.15
    except Exception:
        pass
    return 1.0

def _infer_phase(decisions: List[str], risks: List[str], next_steps: List[str], data_state: str, queued: int, vector_enabled: bool) -> str:
    d = " \n ".join(decisions).lower()
    r = " \n ".join(risks).lower()
    n = " \n ".join(next_steps).lower()
    if not vector_enabled or data_state != "fresh":
        if "credential" in r or "enable" in r or "setup" in d or "setup" in n:
            return "Onboarding"
    if queued > 0 or "ingest" in d or "ingest" in r:
        return "Stabilizing Vector RAG"
    if any(k in n for k in ["migrate", "refactor", "schema", "design"]):
        return "Implementing"
    if any(k in n for k in ["integrat", "wire", "router", "cohesion"]):
        return "Integrating"
    if any(k in n for k in ["verify", "test", "canary", "readiness", "release"]):
        return "Verifying"
    if any(k in r for k in ["security", "incident", "regression"]):
        return "Hardening"
    return "Executing"

def _collect_status(use_vector: bool = True) -> Dict[str, Any]:
    # Freshness / queue status
    queue_dir = os.path.join(CLAUDE_DIR, "ingest-queue")
    queued = 0
    try:
        queued = len([f for f in os.listdir(queue_dir) if f.endswith('.json')])
    except Exception:
        pass

    # Decide whether to use vector search: only if explicitly enabled and queue is empty
    vector_env_enabled = os.environ.get("ENABLE_VECTOR_RAG", "false").lower() == "true"
    do_vector = bool(use_vector and vector_env_enabled and queued == 0)

    # Vector-derived bullets
    decisions_results = _vector_search_local(
        "project status decisions recent",
        k=6,
        filters={"type": ["decision", "status", "incident"], "stage": ["implemented", "validated"]},
    ) if do_vector else []
    risks_results = _vector_search_local(
        "risk blocker incident regression",
        k=6,
        filters={"problem_type": ["timeout", "build", "security", "infra"]},
    ) if do_vector else []
    next_results = _vector_search_local("milestone next plan", k=6) if do_vector else []

    # Fallback from NOTES.md
    notes_text = _read_text(os.path.join(CLAUDE_DIR, "logs", "NOTES.md"))
    fb = _extract_recent_from_notes(notes_text)

    # Components from WSI
    wsi = _read_json(WSI_PATH, {"items": []})
    recent_components = [os.path.basename(i.get("path", "")) for i in wsi.get("items", []) if i.get("path")] \
                        if isinstance(wsi, dict) else []
    recent_components = [c for c in recent_components if c][:5]
    active_components = (fb.get("components", []) or []) + recent_components
    # Dedup while preserving order
    active_components = list(dict.fromkeys([c for c in active_components if c]))[:8]

    # Compute most-touched (hot) components from recent WSI entries
    hot_components: List[str] = []
    hot_focus: Optional[str] = None
    try:
        if isinstance(wsi, dict) and isinstance(wsi.get("items"), list):
            freq: Dict[str, int] = {}
            recent_items = wsi.get("items", [])[-20:]
            total_considered = 0
            for it in recent_items:
                p = os.path.basename((it.get("path") or ""))
                if p:
                    freq[p] = freq.get(p, 0) + 1
                    total_considered += 1
            if freq:
                # sort by count desc
                sorted_items = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
                hot_components = [k for k, _ in sorted_items[:3]]
                # Determine a single focus component if it dominates
                top_name, top_count = sorted_items[0]
                next_count = sorted_items[1][1] if len(sorted_items) > 1 else 0
                if total_considered > 0 and top_count >= 2 and top_count >= next_count + 1 and (top_count / max(1, total_considered)) >= 0.34:
                    hot_focus = top_name
    except Exception:
        hot_components = []
        hot_focus = None

    # WARNINGS
    warnings_text = _read_text(WARNINGS_PATH)
    has_creds_warning = bool(re.search(r"Vector RAG .*not configured|ENABLE_VECTOR_RAG=false", warnings_text or "", re.IGNORECASE))

    def _make_line(r: Dict[str, Any]) -> str:
        meta = r.get("meta", {}) if isinstance(r.get("meta"), dict) else {}
        title = meta.get("task_id") or r.get("path") or meta.get("category") or "item"
        snippet = r.get("text") or r.get("snippet") or ""
        return _compact_line(f"{title}: {snippet}")

    # Rank and select decisions
    if decisions_results:
        def _rank_dec(r: Dict[str, Any]) -> float:
            base = _score_decision(r)
            meta = r.get("meta", {}) if isinstance(r.get("meta"), dict) else {}
            text = r.get("text") or r.get("snippet") or ""
            return base * _mention_bonus(text, meta, active_components, hot_components)
        decisions_ranked = sorted(decisions_results, key=_rank_dec, reverse=True)
        decisions_b = []
        seen = set()
        for r in decisions_ranked:
            line = _make_line(r)
            key = line.split(":")[0]
            if key not in seen:
                seen.add(key)
                decisions_b.append(line)
            if len(decisions_b) >= 3:
                break
    else:
        decisions_b = fb.get("decisions", [])

    # Rank and select risks
    risks_b = []
    if risks_results:
        def _rank_risk(r: Dict[str, Any]) -> float:
            base = _score_risk(r)
            meta = r.get("meta", {}) if isinstance(r.get("meta"), dict) else {}
            text = r.get("text") or r.get("snippet") or ""
            return base * _mention_bonus(text, meta, active_components, hot_components)
        risks_ranked = sorted(risks_results, key=_rank_risk, reverse=True)
        seen = set()
        for r in risks_ranked:
            line = _make_line(r)
            key = line.split(":")[0]
            if key not in seen:
                seen.add(key)
                risks_b.append(line)
            if len(risks_b) >= 3:
                break

    # Extract next steps from next_results text blocks
    # Boost next_results by component mentions before extracting steps
    next_ranked = []
    for r in next_results:
        meta = r.get("meta", {}) if isinstance(r.get("meta"), dict) else {}
        text = r.get("text") or r.get("snippet") or ""
        bonus = _mention_bonus(text, meta, active_components, hot_components)
        next_ranked.append((bonus, r))
    next_ranked.sort(key=lambda t: t[0], reverse=True)

    next_b = []
    for _, r in next_ranked:
        text = r.get("text") or r.get("snippet") or ""
        steps = _extract_next_steps_from_text(text)
        for s in steps:
            if s not in next_b:
                next_b.append(s)
        if len(next_b) >= 3:
            break

    # Summary line with phase inference
    vector_enabled = do_vector
    data_state = "fresh" if (vector_enabled and not has_creds_warning and queued==0) else "stale"
    phase = _infer_phase(decisions_b, risks_b, next_b, data_state, queued, vector_enabled)
    if hot_focus:
        summary = f"Phase: {phase} — Focus: {hot_focus} — Status snapshot from vector digests + local logs"
    else:
        summary = f"Phase: {phase} — Status snapshot from vector digests + local logs"


    status = {
        "project": os.path.basename(PROJECT_ROOT) or "project",
        "updated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "data": {"state": data_state, "queue": queued},
        "mode": ("vector" if vector_enabled else "local"),
        "summary": summary,
        "milestones": {
            "done": decisions_b[:1] or [],
            "next": next_b[:1] or [],
            "eta": []
        },
        "decisions": decisions_b,
        "risks": risks_b,
        "open_questions": [],
        "activity": {
            "components": (fb.get("components", []) or recent_components)[:5],
            "agents": []
        }
    }

    # Try to infer ETA from next_results
    etas: List[str] = []
    for r in next_results:
        etas.extend(_extract_eta_from_text((r.get("text") or r.get("snippet") or "")))
        if len(etas) >= 2:
            break
    if etas:
        milestones = cast(Dict[str, Any], status["milestones"])
        milestones["eta"] = etas[:2]

    return status

PROJECT_STATUS_TAG_START = "<project_status>"
PROJECT_STATUS_TAG_END = "</project_status>"

def _render_status_block(status: Dict[str, Any]) -> str:
    project = status.get("project", "project")
    upd = status.get("updated_at", "")
    data = status.get("data", {})
    d_state = data.get("state", "stale")
    d_queue = data.get("queue", 0)
    lines = []
    lines.append(PROJECT_STATUS_TAG_START)
    lines.append(f"Project: {project} | Last Update: {upd} | Data: {d_state} (queue={d_queue})")
    lines.append("Summary:")
    lines.append(f"- {_compact_line(status.get('summary', '') or 'n/a')}")

    ms = status.get("milestones", {})
    lines.append("Milestones:")
    if ms.get("done"):
        lines.append(f"- Done: {_compact_line(ms['done'][0])}")
    if ms.get("next"):
        lines.append(f"- Next: {_compact_line(ms['next'][0])}")
    if ms.get("eta"):
        lines.append(f"- ETA: {_compact_line('; '.join(ms['eta']))}")

    decs = status.get("decisions", [])
    if decs:
        lines.append("Decisions (recent):")
        for d in decs[:3]:
            lines.append(f"- {_compact_line(d)}")

    risks = status.get("risks", [])
    if risks:
        lines.append("Risks/Blockers:")
        for r in risks[:3]:
            lines.append(f"- {_compact_line(r)}")

    oq = status.get("open_questions", [])
    if oq:
        lines.append("Open Questions:")
        for q in oq[:3]:
            lines.append(f"- {_compact_line(q)}")

    act = status.get("activity", {})
    comps = act.get("components", [])
    if comps:
        lines.append("Activity Snapshot:")
        lines.append(f"- Components: {', '.join(comps[:5])}")

    lines.append(PROJECT_STATUS_TAG_END)
    return "\n".join(lines) + "\n"

def _insert_or_replace_block(md_text: str, block_text: str) -> str:
    # Remove any existing project_status blocks (if multiple)
    cleaned = re.sub(rf"{re.escape(PROJECT_STATUS_TAG_START)}.*?{re.escape(PROJECT_STATUS_TAG_END)}",
                     "", md_text, flags=re.DOTALL)
    # Insert after </context_engineering>
    idx = cleaned.find("</context_engineering>")
    if idx != -1:
        insert_at = idx + len("</context_engineering>")
        return cleaned[:insert_at] + "\n\n" + block_text + "\n" + cleaned[insert_at:]
    # Fallback: prepend
    return block_text + "\n" + cleaned

def update_claude_md(use_vector: bool = True) -> Dict[str, Any]:
    """Update the <project_status> block inside CLAUDE.md (do not create file).
    Returns {ok, updated, status} and never rewrites other sections.
    """
    skip_reason = _should_skip_update()
    if skip_reason:
        return {"ok": True, "updated": False, "skipped": skip_reason}
    before = _read_text(CLAUDE_MD_PATH)
    if not before:
        return {"ok": False, "error": f"CLAUDE.md not found at {CLAUDE_MD_PATH}"}

    status = _collect_status(use_vector=use_vector)
    block = _render_status_block(status)
    new_text = _insert_or_replace_block(before, block)
    changed = hashlib.sha256(new_text.encode()).hexdigest() != hashlib.sha256(before.encode()).hexdigest()
    if changed:
        with open(CLAUDE_MD_PATH, "w", encoding="utf-8") as f:
            f.write(new_text)

    # Write a small health log for diagnostics
    try:
        health = {
            "updated_at": status.get("updated_at"),
            "mode": status.get("mode"),
            "updated": changed,
            "queue": status.get("data", {}).get("queue"),
            "data_state": status.get("data", {}).get("state"),
        }
        with open(os.path.join(LOGS_DIR, "project_status_health.json"), "w", encoding="utf-8") as hf:
            json.dump(health, hf, indent=2)
            hf.write("\n")
    except Exception:
        pass

    return {"ok": True, "updated": changed, "status": status}

def _sanitize_label(s: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\.-]+", "-", s or "project")
    cleaned = re.sub(r"[\.-]{2,}", "-", cleaned).strip(".-")
    return cleaned or "project"

def build_launchd_plist(interval_sec: int = 300):
    project_name = os.path.basename(PROJECT_ROOT) or "project"
    label = f"com.agentsy.claude.projectstatus.{_sanitize_label(project_name)}"
    python_bin = "/usr/bin/python3"
    script_path = os.path.abspath(__file__)
    out_log = os.path.join(CLAUDE_DIR, "logs", "launchd.projectstatus.out.log")
    err_log = os.path.join(CLAUDE_DIR, "logs", "launchd.projectstatus.err.log")
    env = {
        "ENABLE_VECTOR_RAG": os.environ.get("ENABLE_VECTOR_RAG", "true"),
        "DATABASE_URL_MEMORY": os.environ.get("DATABASE_URL_MEMORY", ""),
        "REDIS_URL": os.environ.get("REDIS_URL", ""),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "WSI_PATH": os.environ.get("WSI_PATH", WSI_PATH),
        "LOGS_DIR": LOGS_DIR,
        "CLAUDE_PROJECT_DIR": PROJECT_ROOT,
    }
    def _x(s: str) -> str:
        return (s.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
                 .replace('"', "&quot;")
                 .replace("'", "&apos;"))
    env_items = "".join(f"<key>{_x(k)}</key><string>{_x(str(v))}</string>" for k, v in env.items())
    plist = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
  <dict>
    <key>Label</key>
    <string>{_x(label)}</string>
    <key>ProgramArguments</key>
    <array>
      <string>{_x(python_bin)}</string>
      <string>{_x(script_path)}</string>
      <string>--update-claude-md</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{_x(PROJECT_ROOT)}</string>
    <key>StartInterval</key>
    <integer>{int(interval_sec)}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{_x(out_log)}</string>
    <key>StandardErrorPath</key>
    <string>{_x(err_log)}</string>
    <key>EnvironmentVariables</key>
    <dict>
      {env_items}
    </dict>
  </dict>
</plist>
"""
    plist_filename = f"{label}.plist"
    return label, plist, plist_filename

def main():
    if len(sys.argv) > 1 and sys.argv[1] in {"--update-claude-md", "-u"}:
        fast_local = ('--fast-local' in sys.argv)
        res = update_claude_md(use_vector=(not fast_local))
        print(json.dumps(res, indent=2))
        return
    if len(sys.argv) > 1 and sys.argv[1] in {"--emit-launchd-plist", "-L"}:
        interval = 300
        if len(sys.argv) > 2:
            try:
                interval = int(sys.argv[2])
            except Exception:
                interval = 300
        label, plist, plist_filename = build_launchd_plist(interval)
        launchd_dir = os.path.join(CLAUDE_DIR, "launchd")
        _ensure_dir(launchd_dir)
        plist_path = os.path.join(launchd_dir, plist_filename)
        with open(plist_path, "w", encoding="utf-8") as f:
            f.write(plist)
        print(json.dumps({"ok": True, "label": label, "plist_path": plist_path, "interval_sec": interval}, indent=2))
        return
    # Default: run update (vector enabled by env)
    res = update_claude_md()
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
