#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stop hook: extract a DIGEST block from the model's reply, append to NOTES.md, and refresh wsi.json.

Exit code semantics (per Claude Code hooks):
- 0: success; stdout/stderr hidden.
- 2: show stderr to model and block tool call (we won't block at Stop; use 0 or 1).
- other non-zero: show stderr to USER but continue (Stop continues anyway).
"""
import sys, os, re, json, uuid, time, random, hashlib, subprocess
from datetime import datetime

# --- Config ---
# Use official CLAUDE_PROJECT_DIR env var for project-specific files
PROJECT_ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
CLAUDE_DIR   = os.path.join(PROJECT_ROOT, ".claude")
NOTES_PATH   = os.path.join(CLAUDE_DIR, "logs", "NOTES.md")
WSI_CAP      = int(os.environ.get("WSI_CAP", "10"))
QUEUE_DIR    = os.path.join(CLAUDE_DIR, "ingest-queue")
DEAD_DIR     = os.path.join(QUEUE_DIR, "dead")
LAUNCHD_DIR  = os.path.join(CLAUDE_DIR, "launchd")
MAX_ATTEMPTS = int(os.environ.get("INGEST_MAX_ATTEMPTS", "6"))
BACKOFF_BASE = float(os.environ.get("INGEST_BACKOFF_BASE", "5"))  # seconds
BACKOFF_CAP  = float(os.environ.get("INGEST_BACKOFF_CAP", "900"))  # 15 minutes

# Stop-hook performance tuning (env toggles)
# - STOP_TAIL_WINDOW_BYTES: how many bytes to tail-read from transcript (default 512KB)
# - STOP_HOOK_MAX_TRANSCRIPT_BYTES: if transcript exceeds this, avoid full parse unless overridden
# - STOP_TAIL_FAST_ONLY: if true, only tail-scan; skip full parse when no tail DIGEST
# - STOP_DEBUG: gate verbose debug logging (default true to preserve current behavior)
# - STOP_TIME_BUDGET_MS: soft time budget; if set (>0) and exceeded before finding DIGEST, exit early
STOP_TAIL_WINDOW_BYTES = int(os.environ.get("STOP_TAIL_WINDOW_BYTES", str(512 * 1024)))
STOP_HOOK_MAX_TRANSCRIPT_BYTES = int(os.environ.get("STOP_HOOK_MAX_TRANSCRIPT_BYTES", str(512 * 1024)))
STOP_TAIL_FAST_ONLY = os.environ.get("STOP_TAIL_FAST_ONLY", "false").lower() == "true"
STOP_DEBUG = os.environ.get("STOP_DEBUG", "true").lower() == "true"
STOP_TIME_BUDGET_MS = int(os.environ.get("STOP_TIME_BUDGET_MS", "0"))  # 0 disables

# Per-project logs by default; allow override via LOGS_DIR
# This aligns debug logs with NOTES.md by default for easier discovery.
DEFAULT_LOGS_DIR = os.path.join(CLAUDE_DIR, "logs")
LOGS_DIR = os.environ.get("LOGS_DIR", DEFAULT_LOGS_DIR)
WSI_PATH = os.environ.get("WSI_PATH", os.path.join(LOGS_DIR, "wsi.json"))
WARNINGS_PATH = os.path.join(LOGS_DIR, "WARNINGS.md")

# Auto-create logs directories if needed
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(os.path.join(CLAUDE_DIR, "logs"), exist_ok=True)
os.makedirs(QUEUE_DIR, exist_ok=True)
os.makedirs(DEAD_DIR, exist_ok=True)
os.makedirs(LAUNCHD_DIR, exist_ok=True)
# -------------------------------------------

# Accept codefences like:
# ```json DIGEST { ... }
# ```DIGEST { ... }
# ``` json\nDIGEST\n{ ... }
DIGEST_RE = re.compile(r"```[a-zA-Z0-9]*\s*DIGEST\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)

def get_project_id_hash(project_root=None):
    """
    Generate a stable project_id hash based on git remote URL.
    Falls back to project_root path if not a git repository.

    Returns: SHA256 hash (first 16 chars) for use as project_id
    """
    if project_root is None:
        project_root = PROJECT_ROOT

    try:
        # Try to get git remote URL
        result = subprocess.run(
            ["git", "-C", project_root, "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            # Normalize git URL (remove .git suffix, handle SSH vs HTTPS)
            git_url = result.stdout.strip()
            git_url = re.sub(r'\.git$', '', git_url)  # Remove .git
            git_url = re.sub(r'^git@([^:]+):', r'https://\1/', git_url)  # SSH to HTTPS
            source = git_url
        else:
            # Not a git repo, use absolute path
            source = os.path.abspath(project_root)
    except Exception:
        # Fallback to project path
        source = os.path.abspath(project_root)

    # Generate SHA256 hash and take first 16 characters
    hash_obj = hashlib.sha256(source.encode('utf-8'))
    return hash_obj.hexdigest()[:16]

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, obj):
    # Ensure directory exists for WSI in logs/
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")

def ensure_file(path, header=None, debug_log_path=None):
    try:
        # Ensure parent directory exists
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
            if debug_log_path:
                with open(debug_log_path, "a") as f:
                    f.write(f"Created parent directory: {parent_dir}\n")

        if not os.path.exists(path):
            if debug_log_path:
                with open(debug_log_path, "a") as f:
                    f.write(f"Creating new file: {path}\n")
            with open(path, "w", encoding="utf-8") as f:
                if header:
                    f.write(header + "\n")
        else:
            if debug_log_path:
                with open(debug_log_path, "a") as f:
                    f.write(f"File exists: {path}\n")
    except Exception as e:
        if debug_log_path:
            with open(debug_log_path, "a") as f:
                f.write(f"❌ ERROR in ensure_file: {e}\n")
                f.write(f"   Path attempted: {path}\n")
                f.write(f"   Parent dir: {os.path.dirname(path)}\n")
        raise

def append_warning(message: str):
    """Append a user-facing warning to WARNINGS.md with a timestamp."""
    try:
        ensure_file(WARNINGS_PATH, "# WARNINGS\n\nUser-facing warnings and setup notices.\n")
        ts = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        with open(WARNINGS_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n## [{ts}]\n{message}\n")
    except Exception:
        pass

def extract_digest_from_text(text):
    m = DIGEST_RE.search(text or "")
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None

def _now_iso():
    return datetime.now().isoformat()

def _log(debug_log_path, msg):
    if not STOP_DEBUG:
        return
    try:
        with open(debug_log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

def extract_latest_digest_from_transcript(transcript, debug_log_path=None):
    """
    From a transcript (list of messages), find the most recent assistant message
    that contains a DIGEST block. Returns parsed digest dict or None.
    """
    try:
        assistant_texts = []
        if isinstance(transcript, list):
            for msg in transcript:
                if isinstance(msg, dict) and msg.get("type") == "assistant":
                    message_obj = msg.get("message", {})
                    content_blocks = message_obj.get("content", [])
                    if isinstance(content_blocks, list):
                        text_parts = []
                        for block in content_blocks:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text_parts.append(block.get("text", "") or "")
                        if text_parts:
                            assistant_texts.append("\n".join(text_parts))

        # Scan from last to first for a DIGEST block
        for idx in range(len(assistant_texts) - 1, -1, -1):
            cand = assistant_texts[idx]
            d = extract_digest_from_text(cand)
            if d:
                if debug_log_path:
                    try:
                        with open(debug_log_path, "a") as f:
                            f.write(f"🔎 DIGEST found in assistant message index {idx} (from end)\n")
                    except Exception:
                        pass
                return d

        if debug_log_path:
            try:
                with open(debug_log_path, "a") as f:
                    f.write("🔎 No DIGEST found across assistant messages in transcript\n")
            except Exception:
                pass
        return None
    except Exception as e:
        if debug_log_path:
            try:
                with open(debug_log_path, "a") as f:
                    f.write(f"⚠️  extract_latest_digest_from_transcript error: {e}\n")
            except Exception:
                pass
        return None

def rotate_notes():
    """Keep only last 20 digests, archive older ones."""
    if not os.path.exists(NOTES_PATH):
        return

    with open(NOTES_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    # Find all digest sections
    sections = re.findall(
        r'## \[\d{4}-\d{2}-\d{2}.*?\].*?(?=\n## |\Z)',
        text,
        re.DOTALL
    )

    if len(sections) <= 20:
        return  # No rotation needed

    # Archive older digests
    logs_dir = os.path.join(PROJECT_ROOT, "logs", "notes-archive")
    os.makedirs(logs_dir, exist_ok=True)

    archive_file = os.path.join(
        logs_dir,
        f"notes-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    )

    # Keep last 20, archive the rest
    to_archive = sections[:-20]
    to_keep = sections[-20:]

    # Write archive
    with open(archive_file, "w", encoding="utf-8") as f:
        f.write("# Archived NOTES\n\n")
        f.write("".join(to_archive))

    # Rewrite NOTES.md with header + kept sections
    header = "# NOTES (living state)\n\nLast 20 digests. Older entries archived to logs/notes-archive/.\n\n"
    with open(NOTES_PATH, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("".join(to_keep))

def call_vector_bridge_mcp(tool_name, params):
    """Call vector-bridge MCP server via stdio (same as Claude uses)."""
    import subprocess
    import json

    try:
        # MCP server command (matches ~/.config/claude/mcp.json)
        mcp_cmd = ["node", os.path.expanduser("~/.claude/mcp-servers/vector-bridge/dist/index.js")]

        # MCP protocol: send initialize, then tool call
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "stop-digest-hook", "version": "1.0.0"}
            }
        }

        tool_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params
            }
        }

        # Start MCP server
        proc = subprocess.Popen(
            mcp_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "DATABASE_URL_MEMORY": os.environ.get("DATABASE_URL_MEMORY", ""), "REDIS_URL": os.environ.get("REDIS_URL", ""), "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "")}
        )

        # Send requests with configurable timeout (default 60s)
        requests = f"{json.dumps(init_request)}\n{json.dumps(tool_request)}\n"
        try:
            timeout_sec = int(os.environ.get("INGEST_MCP_TIMEOUT_SEC", "60"))
            if os.environ.get("INGEST_DEBUG", "").lower() == "true":
                print(f"[DEBUG] Calling MCP memory_ingest with {timeout_sec}s timeout...", file=sys.stderr)
            stdout, stderr = proc.communicate(input=requests, timeout=timeout_sec)
            if os.environ.get("INGEST_DEBUG", "").lower() == "true":
                print(f"[DEBUG] MCP call completed", file=sys.stderr)
                if stderr:
                    print(f"[DEBUG] MCP stderr output:", file=sys.stderr)
                    print(stderr, file=sys.stderr)
        except subprocess.TimeoutExpired as e:
            proc.kill()
            stdout_output = e.stdout or ""
            stderr_output = e.stderr or ""
            if os.environ.get("INGEST_DEBUG", "").lower() == "true":
                print(f"[DEBUG] MCP timeout - captured stderr before kill:", file=sys.stderr)
                if stderr_output:
                    print(stderr_output, file=sys.stderr)

            # Check if ingestion actually completed successfully (check stderr for success markers)
            stderr_str = stderr_output.decode() if isinstance(stderr_output, bytes) else stderr_output
            if "Total ingestion time:" in stderr_str or "All chunks were duplicates" in stderr_str:
                # Ingestion completed, just didn't get MCP response - treat as success
                if os.environ.get("INGEST_DEBUG", "").lower() == "true":
                    print(f"[DEBUG] Ingestion completed successfully despite timeout (MCP protocol issue)", file=sys.stderr)
                return {"success": True, "chunks": 0, "note": "completed_but_mcp_timeout"}

            return {"error": f"MCP call timed out after {os.environ.get('INGEST_MCP_TIMEOUT_SEC', '60')}s"}

        # Parse responses (MCP returns multiple JSON objects)
        responses = []
        for line in stdout.strip().split('\n'):
            if line.strip():
                try:
                    responses.append(json.loads(line))
                except:
                    pass

        # Find tool call response (id=2)
        for resp in responses:
            if resp.get("id") == 2:
                return resp.get("result", {})

        return None

    except subprocess.TimeoutExpired:
        return {"error": "MCP subprocess timeout"}
    except Exception as e:
        return {"error": str(e)}

def get_rag_suggestions(digest):
    """Query vector-bridge for relevant suggestions based on digest content."""
    try:
        # Build query from decisions and files
        decisions = digest.get("decisions", [])
        files = digest.get("files", [])

        query_parts = []
        if decisions:
            query_parts.append(" ".join(decisions[:3]))  # First 3 decisions
        if files:
            file_paths = [f.get("path", "") for f in files[:3]]  # First 3 files
            query_parts.append(" ".join(file_paths))

        if not query_parts:
            return None

        query = " ".join(query_parts)[:500]  # Limit to 500 chars

        # Call memory_search via MCP
        result = call_vector_bridge_mcp("memory_search", {
            "project_root": None,  # Global search
            "query": query,
            "k": 3,  # Top 3 results
            "global": True
        })

        if result and "content" in result:
            # Parse MCP response
            content = result["content"][0] if isinstance(result["content"], list) else result["content"]
            text = content.get("text", "") if isinstance(content, dict) else str(content)

            try:
                search_results = json.loads(text)
                return {
                    "query": query,
                    "results": search_results.get("results", [])[:3],
                    "success": True
                }
            except:
                return {"query": query, "note": text[:200]}

        return {"query": query, "note": "No results from vector-bridge"}

    except Exception as e:
        return {"error": str(e), "query": query_parts if query_parts else "none"}

def check_and_setup_vector_rag():
    """Check if Vector RAG credentials exist. If not, trigger auto-setup."""
    db_url = os.environ.get("DATABASE_URL_MEMORY")
    redis_url = os.environ.get("REDIS_URL")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if db_url and redis_url and openai_key:
        return True  # All credentials exist

    # Credentials missing - create flag file to trigger setup
    setup_needed_flag = os.path.join(CLAUDE_DIR, ".needs_vector_rag_setup")

    # Only show message once per project
    if not os.path.exists(setup_needed_flag):
        # Create flag file so Claude knows to run setup
        try:
            with open(setup_needed_flag, "w") as f:
                f.write("Vector RAG setup needed - will auto-run on next interaction\n")
        except Exception:
            pass

        # Append visible warning for the user to configure env vars
        append_warning(
            "Vector RAG is not configured. DIGESTs will be queued but not ingested until you set environment variables: "
            "`DATABASE_URL_MEMORY`, `REDIS_URL`, `OPENAI_API_KEY`. Then run `python hooks/stop_digest.py --process-queue`."
        )

    return False  # Skip ingestion until setup complete

def enqueue_digest_job(digest, debug_log_path=None):
    """Write a queued ingestion job file to disk for eventual processing."""
    try:
        job = {
            "id": f"{int(time.time()*1000)}-{uuid.uuid4().hex[:8]}",
            "type": "digest",
            "project_root": PROJECT_ROOT,
            "enqueued_at": datetime.now().isoformat(),
            "attempt_count": 0,
            "last_attempt": None,
            "last_error": None,
            "status": "queued",
            "payload": {"digest": digest},
        }
        job_path = os.path.join(QUEUE_DIR, f"{job['id']}.json")
        with open(job_path, "w", encoding="utf-8") as f:
            json.dump(job, f, indent=2)
            f.write("\n")
        if debug_log_path:
            try:
                with open(debug_log_path, "a") as logf:
                    logf.write(f"📬 Enqueued ingest job: {os.path.basename(job_path)}\n")
            except Exception:
                pass
        return job_path
    except Exception as e:
        if debug_log_path:
            try:
                with open(debug_log_path, "a") as logf:
                    logf.write(f"❌ Failed to enqueue ingest job: {e}\n")
            except Exception:
                pass
        return None

def _compute_backoff_seconds(attempt_count: int) -> float:
    if attempt_count <= 0:
        return 0.0
    # Exponential backoff with jitter, capped
    base = BACKOFF_BASE * (2 ** (attempt_count - 1))
    jitter = base * 0.25 * (random.random() - 0.5)  # +/-12.5%
    return min(max(base + jitter, BACKOFF_BASE), BACKOFF_CAP)

def process_ingest_queue(max_jobs=3, time_budget_sec=5, debug_log_path=None):
    """Process up to max_jobs from the ingest queue within a small time budget."""
    start = time.time()
    processed = 0
    succeeded = 0
    failed = 0
    skipped_backoff = 0
    skipped_no_creds = 0

    enable_rag = os.environ.get("ENABLE_VECTOR_RAG", "false").lower() == "true"
    if not enable_rag:
        if debug_log_path:
            try:
                with open(debug_log_path, "a") as logf:
                    logf.write("⏸️  Skipping queue processing; ENABLE_VECTOR_RAG=false\n")
            except Exception:
                pass
        append_warning(
            "Vector ingestion is disabled (`ENABLE_VECTOR_RAG=false`). DIGESTs are being queued in `.claude/ingest-queue` and will ingest once enabled."
        )
        return {"processed": 0, "succeeded": 0, "failed": 0}

    try:
        files = [f for f in os.listdir(QUEUE_DIR) if f.endswith('.json')]
        files.sort(key=lambda name: os.path.getmtime(os.path.join(QUEUE_DIR, name)))
    except Exception:
        files = []

    for name in files:
        if processed >= max_jobs or (time.time() - start) > time_budget_sec:
            break
        job_path = os.path.join(QUEUE_DIR, name)
        try:
            with open(job_path, "r", encoding="utf-8") as f:
                job = json.load(f)
        except Exception as e:
            # Corrupt job; remove
            try:
                os.remove(job_path)
            except Exception:
                pass
            if debug_log_path:
                try:
                    with open(debug_log_path, "a") as logf:
                        logf.write(f"🧹 Removed corrupt job {name}: {e}\n")
                except Exception:
                    pass
            continue

        job.setdefault("attempt_count", 0)
        # Respect backoff based on last attempt
        last_attempt_iso = job.get("last_attempt")
        if last_attempt_iso:
            try:
                last_ts = datetime.fromisoformat(last_attempt_iso).timestamp()
            except Exception:
                last_ts = 0
        else:
            last_ts = 0
        backoff_needed = _compute_backoff_seconds(job.get("attempt_count", 0))
        elapsed = time.time() - last_ts if last_ts else float('inf')
        if elapsed < backoff_needed:
            skipped_backoff += 1
            # Do not count as processed this run
            continue

        processed += 1
        job["last_attempt"] = datetime.now().isoformat()
        job["attempt_count"] += 1

        digest = (job.get("payload") or {}).get("digest")
        result = None
        try:
            result = ingest_digest_to_vector(digest)
        except Exception as e:
            result = {"error": str(e)}

        # Success only if there is no error and not explicitly skipped
        ok = bool(result) and (not result.get("error")) and (not result.get("skipped"))
        is_missing_creds = result and result.get("skipped") and "not configured" in str(result.get("skipped", ""))
        # Classify retryable (transient) errors by regex (timeouts, transient network)
        err_text = (result or {}).get("error", "") if isinstance(result, dict) else ""
        try:
            import re as _re
            nonfatal_pat = os.environ.get("INGEST_NONFATAL_ERRORS_PATTERN", r"timed out|ECONN|ENETUNREACH|ETIMEDOUT|EAI_AGAIN|connection reset|timeout")
            is_retryable = bool(err_text and _re.search(nonfatal_pat, str(err_text), _re.IGNORECASE))
        except Exception:
            is_retryable = False

        if ok:
            succeeded += 1
            try:
                os.remove(job_path)
            except Exception:
                pass
            if debug_log_path:
                try:
                    with open(debug_log_path, "a") as logf:
                        logf.write(f"✅ Ingested and removed job: {name}\n")
                except Exception:
                    pass
        elif is_missing_creds:
            # Missing credentials - keep job queued but don't increment attempt count
            skipped_no_creds += 1
            job["last_error"] = result.get("skipped", "Vector RAG not configured")
            job["status"] = "queued"
            job["attempt_count"] -= 1  # Undo the increment since this isn't a real failure
            try:
                with open(job_path, "w", encoding="utf-8") as f:
                    json.dump(job, f, indent=2)
                    f.write("\n")
            except Exception:
                pass
            if debug_log_path:
                try:
                    with open(debug_log_path, "a") as logf:
                        logf.write(f"⏸️  Skipped job {name} (missing credentials): {job['last_error']}\n")
                except Exception:
                    pass
            append_warning(
                "Vector RAG credentials are missing. Set `DATABASE_URL_MEMORY`, `REDIS_URL`, and `OPENAI_API_KEY`, then run `python hooks/stop_digest.py --process-queue` to ingest queued DIGESTs."
            )
        elif is_retryable:
            # Transient error - keep queued, undo attempt increment, and back off
            job["last_error"] = err_text or "retryable error"
            job["status"] = "queued"
            job["attempt_count"] -= 1
            try:
                with open(job_path, "w", encoding="utf-8") as f:
                    json.dump(job, f, indent=2)
                    f.write("\n")
            except Exception:
                pass
            if debug_log_path:
                try:
                    with open(debug_log_path, "a") as logf:
                        logf.write(f"⏳ Retryable ingest error for {name}: {job['last_error']}\n")
                except Exception:
                    pass
        else:
            failed += 1
            job["last_error"] = (result or {}).get("error", "unknown error")
            if job["attempt_count"] >= MAX_ATTEMPTS:
                # Move to dead letter queue
                try:
                    dead_path = os.path.join(DEAD_DIR, name)
                    os.replace(job_path, dead_path)
                except Exception:
                    # fallback: rewrite in place tagged as dead
                    job["status"] = "dead"
                    try:
                        with open(job_path, "w", encoding="utf-8") as f:
                            json.dump(job, f, indent=2)
                            f.write("\n")
                    except Exception:
                        pass
                if debug_log_path:
                    try:
                        with open(debug_log_path, "a") as logf:
                            logf.write(f"💀 Moved job to dead: {name} (attempts={job['attempt_count']})\n")
                    except Exception:
                        pass
            else:
                job["status"] = "queued"
                try:
                    with open(job_path, "w", encoding="utf-8") as f:
                        json.dump(job, f, indent=2)
                        f.write("\n")
                except Exception:
                    pass
                if debug_log_path:
                    try:
                        with open(debug_log_path, "a") as logf:
                            logf.write(f"↩️  Re-queued job {name}: {job['last_error']} (attempts={job['attempt_count']})\n")
                    except Exception:
                        pass

    if debug_log_path:
        try:
            with open(debug_log_path, "a") as logf:
                logf.write(f"📦 Queue summary: processed={processed}, succeeded={succeeded}, failed={failed}, skipped_backoff={skipped_backoff}, skipped_no_creds={skipped_no_creds}\n")
        except Exception:
            pass
    return {"processed": processed, "succeeded": succeeded, "failed": failed, "skipped_backoff": skipped_backoff, "skipped_no_creds": skipped_no_creds}

def retry_dead_jobs(limit=None, debug_log_path=None):
    """Move jobs from dead letter queue back into live queue, resetting metadata."""
    try:
        dead_files = [f for f in os.listdir(DEAD_DIR) if f.endswith('.json')]
        dead_files.sort(key=lambda n: os.path.getmtime(os.path.join(DEAD_DIR, n)))
    except Exception:
        dead_files = []

    moved = 0
    errors = 0
    items = []
    for name in dead_files:
        if limit is not None and moved >= limit:
            break
        src = os.path.join(DEAD_DIR, name)
        try:
            with open(src, 'r', encoding='utf-8') as f:
                job = json.load(f)
        except Exception as e:
            errors += 1
            if debug_log_path:
                try:
                    with open(debug_log_path, 'a') as logf:
                        logf.write(f"⚠️  Could not read dead job {name}: {e}\n")
                except Exception:
                    pass
            continue

        # Reset metadata
        job['status'] = 'queued'
        job['attempt_count'] = 0
        job['last_error'] = None
        job['last_attempt'] = None
        job['enqueued_at'] = datetime.now().isoformat()

        # Choose destination path (avoid clobber)
        dest = os.path.join(QUEUE_DIR, name)
        if os.path.exists(dest):
            base, ext = os.path.splitext(name)
            dest = os.path.join(QUEUE_DIR, f"{base}-retry-{uuid.uuid4().hex[:6]}{ext}")

        try:
            with open(dest, 'w', encoding='utf-8') as f:
                json.dump(job, f, indent=2)
                f.write('\n')
            # Remove dead file
            try:
                os.remove(src)
            except Exception:
                pass
            moved += 1
            items.append(os.path.basename(dest))
            if debug_log_path:
                try:
                    with open(debug_log_path, 'a') as logf:
                        logf.write(f"🔁 Retried dead job -> {os.path.basename(dest)}\n")
                except Exception:
                    pass
        except Exception as e:
            errors += 1
            if debug_log_path:
                try:
                    with open(debug_log_path, 'a') as logf:
                        logf.write(f"❌ Failed to retry dead job {name}: {e}\n")
                except Exception:
                    pass

    return {"moved": moved, "errors": errors, "queued": items}

def _sanitize_label(s: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\.-]+", "-", s or "project")
    cleaned = re.sub(r"[\.-]{2,}", "-", cleaned)  # collapse repeats
    cleaned = cleaned.strip(".-")  # trim edge dots/dashes
    return cleaned or "project"

def build_launchd_plist(interval_sec=300):
    """Return (label, plist_text, plist_filename) for a launchd agent that processes the queue periodically."""
    project_name = os.path.basename(PROJECT_ROOT) or "project"
    label = f"com.agentsy.claude.stopdigest.queue.{_sanitize_label(project_name)}"
    python_bin = "/usr/bin/python3"
    script_path = os.path.abspath(__file__)
    working_dir = PROJECT_ROOT
    out_log = os.path.join(CLAUDE_DIR, "logs", "launchd.stopdigest.out.log")
    err_log = os.path.join(CLAUDE_DIR, "logs", "launchd.stopdigest.err.log")

    # Compose EnvironmentVariables (allow missing -> empty string)
    env = {
        "ENABLE_VECTOR_RAG": os.environ.get("ENABLE_VECTOR_RAG", "true"),
        "DATABASE_URL_MEMORY": os.environ.get("DATABASE_URL_MEMORY", ""),
        "REDIS_URL": os.environ.get("REDIS_URL", ""),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "WSI_CAP": os.environ.get("WSI_CAP", str(WSI_CAP)),
        "LOGS_DIR": LOGS_DIR,
        "CLAUDE_PROJECT_DIR": PROJECT_ROOT,
    }

    def _xml_escape(s):
        return (
            s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace("\"", "&quot;")
             .replace("'", "&apos;")
        )

    env_items = "".join(
        f"<key>{_xml_escape(k)}</key><string>{_xml_escape(str(v))}</string>" for k, v in env.items()
    )

    plist = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
  <dict>
    <key>Label</key>
    <string>{_xml_escape(label)}</string>
    <key>ProgramArguments</key>
    <array>
      <string>{_xml_escape(python_bin)}</string>
      <string>{_xml_escape(script_path)}</string>
      <string>--process-queue</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{_xml_escape(working_dir)}</string>
    <key>StartInterval</key>
    <integer>{int(interval_sec)}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{_xml_escape(out_log)}</string>
    <key>StandardErrorPath</key>
    <string>{_xml_escape(err_log)}</string>
    <key>EnvironmentVariables</key>
    <dict>
      {env_items}
    </dict>
  </dict>
</plist>
"""
    plist_filename = f"{label}.plist"
    return label, plist, plist_filename

def ingest_digest_to_vector(digest):
    """Ingest DIGEST into vector-bridge for future RAG retrieval."""
    try:
        # Auto-setup Vector RAG if credentials are missing
        if not check_and_setup_vector_rag():
            return {"skipped": "Vector RAG not configured yet (setup in progress)"}

        # Quality gates: Ensure DIGEST meets minimum requirements
        agent = digest.get("agent", "UNKNOWN")
        task = digest.get("task_id", "untagged")

        # Gate 1: Must have at least summary OR (problem + solution) OR decisions
        has_summary = bool(digest.get("summary"))
        has_problem_solution = bool(digest.get("problem") or digest.get("symptom")) and \
                              bool(digest.get("solution") or digest.get("fix"))
        has_decisions = bool(digest.get("decisions"))

        if not (has_summary or has_problem_solution or has_decisions):
            return {
                "skipped": "Quality gate failed: DIGEST must have summary, problem+solution, or decisions",
                "reason": "insufficient_content"
            }

        # Gate 2: Agent must be specified
        if agent == "UNKNOWN":
            return {
                "skipped": "Quality gate failed: DIGEST must specify agent",
                "reason": "missing_agent"
            }

        # Gate 3: Task ID must be meaningful (not "untagged")
        if task == "untagged" or not task:
            return {
                "skipped": "Quality gate failed: DIGEST must have meaningful task_id",
                "reason": "missing_task_id"
            }
        decisions = digest.get("decisions", [])
        files = digest.get("files", [])
        contracts = digest.get("contracts", [])
        next_steps = digest.get("next", [])
        evidence = digest.get("evidence", {})

        # Extract digest type and fields (flexible archetype support)
        digest_type = digest.get("type", "decision")  # decision | investigation | incident | experiment | design | status | knowledge
        summary = digest.get("summary", "")

        # Optional universal fields with safe fallbacks
        problem = (
            digest.get("problem")
            or digest.get("symptom")
            or digest.get("question")
            or ""
        )
        root_cause = (
            digest.get("root_cause")
            or digest.get("cause")
            or ""
        )
        solution = (
            digest.get("solution")
            or digest.get("fix")
            or ""
        )
        outcome = (
            digest.get("outcome")
            or digest.get("results")
            or digest.get("impact")
            or ""
        )
        cross_project_lesson = (
            digest.get("cross_project_lesson")
            or digest.get("lesson")
            or ""
        )

        # Metadata for filtering and search
        problem_type = digest.get("problem_type", "")
        solution_pattern = digest.get("solution_pattern", "")
        tech_stack = digest.get("tech_stack", [])
        keywords = digest.get("keywords", [])
        stage = digest.get("stage", "implemented")  # observed | proposed | implemented | validated | deprecated
        outcome_status = digest.get("outcome_status", "none")  # none | expected | partial | success | failed
        confidence = digest.get("confidence", 0.95)

        # Build Problem-Root Cause-Solution-Outcome format (universal, searchable)
        text_parts = []

        # Session header
        text_parts.append(f"Session Summary: {agent} agent completed task '{task}'")
        text_parts.append("")

        # Optional summary
        if summary:
            text_parts.append(f"Summary: {summary}")
            text_parts.append("")

        # Problem statement (WHAT was wrong/needed)
        if problem:
            text_parts.append(f"Problem: {problem}")
        elif decisions:
            # Fallback: infer problem from first decision
            text_parts.append(f"Problem: {decisions[0]}")

        # Root cause (WHY it happened)
        if root_cause:
            text_parts.append(f"Root Cause: {root_cause}")

        # Solution (WHAT fixed it / decision made)
        if solution:
            text_parts.append(f"Solution: {solution}")
        elif decisions:
            # Fallback: use decisions as solution
            text_parts.append("Solution:")
            for i, decision in enumerate(decisions, 1):
                text_parts.append(f"  {i}. {decision}")

        # Outcome (RESULTS / what improved)
        if outcome:
            text_parts.append(f"Outcome: {outcome}")
        elif evidence:
            outcome_parts = [f"{k}: {v}" for k, v in evidence.items()]
            text_parts.append(f"Outcome: {', '.join(outcome_parts)}")

        # Cross-project lesson (generalized takeaway)
        if cross_project_lesson:
            text_parts.append(f"\nCross-Project Lesson: {cross_project_lesson}")

        # Project context (appendix - brief mention of files)
        if files:
            file_mentions = [f.get("path", "").split("/")[-1] for f in files[:3]]  # Just filenames
            text_parts.append(f"\nProject Context: Modified {', '.join(file_mentions)}")
            if len(files) > 3:
                text_parts.append(f"  (and {len(files) - 3} more files)")

        # Contracts (if any)
        if contracts:
            text_parts.append("\nAPI Contracts Affected:")
            for contract in contracts[:3]:
                text_parts.append(f"  - {contract}")

        # Next steps (future work)
        if next_steps:
            text_parts.append("\nRecommended Next Steps:")
            for i, step in enumerate(next_steps[:3], 1):
                text_parts.append(f"  {i}. {step}")

        digest_text = "\n".join(text_parts)

        # Gate 4: Minimum text length (must have substantial content)
        MIN_DIGEST_LENGTH = 50  # characters
        if len(digest_text) < MIN_DIGEST_LENGTH:
            return {
                "skipped": f"Quality gate failed: DIGEST text too short ({len(digest_text)} < {MIN_DIGEST_LENGTH} chars)",
                "reason": "insufficient_length"
            }

        # Build rich metadata for filtering and search
        project_id_hash = get_project_id_hash(PROJECT_ROOT)
        meta = {
            "source": "digest",
            "agent": agent,
            "task_id": task,
            "component": "orchestration",
            "category": "digest",
            "type": digest_type,
            "stage": stage,
            "outcome_status": outcome_status,
            "confidence": confidence,
            "project_root": PROJECT_ROOT,
            "project_name": os.path.basename(PROJECT_ROOT) or "unknown",
            "project_id_hash": project_id_hash,  # Stable hash for cross-machine search
        }

        # Add problem classification (for global search)
        if problem_type:
            meta["problem_type"] = problem_type
        if solution_pattern:
            meta["solution_pattern"] = solution_pattern
        if tech_stack:
            meta["tech_stack"] = tech_stack
        if keywords:
            meta["keywords"] = keywords

        # Add status
        meta["status"] = "valid"

        # Ingest via MCP
        result = call_vector_bridge_mcp("memory_ingest", {
            "project_root": PROJECT_ROOT,
            "path": f"NOTES.md#digest-{task}",
            "text": digest_text,
            "meta": meta
        })

        return result

    except Exception as e:
        return {"error": str(e)}

def append_notes(digest, rag_suggestions=None, debug_log_path=None):
    if debug_log_path:
        with open(debug_log_path, "a") as f:
            f.write(f"📝 append_notes called - NOTES_PATH: {NOTES_PATH}\n")
            f.write(f"   Project root: {PROJECT_ROOT}\n")
            f.write(f"   CLAUDE_DIR: {CLAUDE_DIR}\n")

    ensure_file(NOTES_PATH, "# NOTES (living state)\n\nLast 20 digests. Older entries archived to logs/notes-archive/.\n", debug_log_path=debug_log_path)
    ts = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    agent = digest.get("agent", "UNKNOWN")
    task  = digest.get("task_id", "untagged")
    decisions = digest.get("decisions", [])
    contracts = digest.get("contracts", [])
    next_steps= digest.get("next", [])
    evidence  = digest.get("evidence", {})

    files = digest.get("files", [])
    files_lines = "\n".join(
        f"- {f.get('path')} — {f.get('reason','')} "
        + (f"anchors={f.get('anchors')}" if f.get('anchors') else "")
        for f in files
    )

    decisions_text = "".join([f"- {d}\n" for d in decisions]) or "- n/a\n"
    contracts_text = "".join([f"- {c}\n" for c in contracts]) or "- n/a\n"
    next_text = "".join([f"- {n}\n" for n in next_steps]) or "- n/a\n"
    evidence_text = "".join([f"- {k}: {v}\n" for k, v in evidence.items()]) or "- n/a\n"

    # Use RAG suggestions passed as parameter (already fetched in main)
    rag_text = ""
    if rag_suggestions and not rag_suggestions.get("error"):
        rag_text = f"\n**RAG Suggestions**\n- Query: {rag_suggestions.get('query', 'n/a')}\n- {rag_suggestions.get('note', 'n/a')}\n"

    block = (
        f"## [{ts}] Subagent Digest — {agent} — task:{task}\n\n"
        f"**Decisions**\n{decisions_text}\n"
        f"**Files**\n{files_lines or '- n/a'}\n\n"
        f"**Contracts Affected**\n{contracts_text}\n"
        f"**Next Steps**\n{next_text}\n"
        f"**Evidence**\n{evidence_text}"
        f"{rag_text}"
    )

    try:
        if debug_log_path:
            with open(debug_log_path, "a") as f:
                f.write(f"✍️  Writing DIGEST block to {NOTES_PATH}\n")
                f.write(f"   Agent: {agent}, Task: {task}\n")
                f.write(f"   Block size: {len(block)} bytes\n")

        with open(NOTES_PATH, "a", encoding="utf-8") as f:
            f.write(block)

        if debug_log_path:
            with open(debug_log_path, "a") as f:
                f.write(f"✅ Successfully wrote DIGEST to NOTES.md\n")
    except Exception as e:
        if debug_log_path:
            with open(debug_log_path, "a") as f:
                f.write(f"❌ ERROR writing to NOTES.md: {e}\n")
                f.write(f"   Path: {NOTES_PATH}\n")
        raise

    # Rotate after appending
    rotate_notes()

def refresh_wsi(digest, rag_suggestions=None):
    wsi = load_json(WSI_PATH, {"items": []})
    current = wsi.get("items", [])
    # Deduplicate by path, keep most recent reason/anchors + update timestamp
    seen = { item.get("path"): i for i, item in enumerate(current) if item.get("path") }
    timestamp = datetime.now().isoformat()

    for f in digest.get("files", []):
        path = f.get("path")
        if not path:
            continue
        item = {
            "path": path,
            "reason": f.get("reason", "touched"),
            "anchors": f.get("anchors", []),
            "last_access": timestamp
        }
        if path in seen:
            current[ seen[path] ] = item
        else:
            current.append(item)

    # Add RAG suggestions to WSI if available
    if rag_suggestions and "results" in rag_suggestions:
        for result in rag_suggestions["results"][:3]:  # Top 3 suggestions
            path = result.get("path", "")
            if path and path not in seen:
                current.append({
                    "path": path,
                    "reason": "rag-suggest",
                    "anchors": [],
                    "last_access": timestamp
                })

    # Rotate to cap (keep most recent last N)
    if len(current) > WSI_CAP:
        current = current[-WSI_CAP:]

    wsi["items"] = current
    save_json(WSI_PATH, wsi)

def main():
    # Optional CLI: process queue and exit
    if len(sys.argv) > 1 and sys.argv[1] in {"--process-queue", "-q"}:
        # Ensure logs dir exists
        os.makedirs(LOGS_DIR, exist_ok=True)
        debug_log = os.path.join(LOGS_DIR, "stop_hook_debug.log")
        summary = process_ingest_queue(max_jobs=999, time_budget_sec=30, debug_log_path=debug_log)
        print(json.dumps({"ok": True, "summary": summary}, indent=2))
        return
    if len(sys.argv) > 1 and sys.argv[1] in {"--queue-status", "-s"}:
        # Report queue/dead counts and a few recent errors
        try:
            q_files = [f for f in os.listdir(QUEUE_DIR) if f.endswith('.json')]
        except Exception:
            q_files = []
        try:
            d_files = [f for f in os.listdir(DEAD_DIR) if f.endswith('.json')]
        except Exception:
            d_files = []

        errors = []
        for name in sorted(d_files, key=lambda n: os.path.getmtime(os.path.join(DEAD_DIR, n)), reverse=True)[:5]:
            try:
                with open(os.path.join(DEAD_DIR, name), 'r', encoding='utf-8') as f:
                    job = json.load(f)
                    errors.append({
                        "job": name,
                        "attempts": job.get("attempt_count"),
                        "last_error": job.get("last_error"),
                        "last_attempt": job.get("last_attempt"),
                    })
            except Exception:
                pass

        print(json.dumps({
            "ok": True,
            "queue_dir": QUEUE_DIR,
            "dead_dir": DEAD_DIR,
            "queued": len(q_files),
            "dead": len(d_files),
            "recent_dead_errors": errors,
            "config": {
                "ENABLE_VECTOR_RAG": os.environ.get("ENABLE_VECTOR_RAG", "false"),
                "INGEST_MAX_ATTEMPTS": MAX_ATTEMPTS,
                "INGEST_BACKOFF_BASE": BACKOFF_BASE,
                "INGEST_BACKOFF_CAP": BACKOFF_CAP,
            }
        }, indent=2))
        return
    if len(sys.argv) > 1 and sys.argv[1] in {"--retry-dead", "-r"}:
        # Move dead jobs back to queue
        limit = None
        if len(sys.argv) > 2:
            try:
                limit = int(sys.argv[2])
            except Exception:
                limit = None
        debug_log = os.path.join(LOGS_DIR, "stop_hook_debug.log")
        res = retry_dead_jobs(limit=limit, debug_log_path=debug_log)
        print(json.dumps({"ok": True, "result": res}, indent=2))
        return
    if len(sys.argv) > 1 and sys.argv[1] in {"--emit-launchd-plist", "--emit-launchd", "-L"}:
        # Emit a launchd plist for periodic queue processing (write under .claude/launchd and print path)
        interval = 300
        # Optional: parse interval from argv[2]
        if len(sys.argv) > 2:
            try:
                interval = int(sys.argv[2])
            except Exception:
                interval = 300
        label, plist_text, plist_filename = build_launchd_plist(interval_sec=interval)
        plist_path = os.path.join(LAUNCHD_DIR, plist_filename)
        try:
            with open(plist_path, 'w', encoding='utf-8') as f:
                f.write(plist_text)
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"Failed to write plist: {e}"}, indent=2))
            return
        print(json.dumps({
            "ok": True,
            "label": label,
            "plist_path": plist_path,
            "interval_sec": interval
        }, indent=2))
        return
    if len(sys.argv) > 1 and sys.argv[1] in {"--uninstall-launchd", "-U"}:
        # Unload and remove the LaunchAgent from LaunchAgents and local plist copy
        label, _, plist_filename = build_launchd_plist()
        dest = os.path.join(os.path.expanduser("~/Library/LaunchAgents"), plist_filename)
        # Try unload
        try:
            subprocess.run(["launchctl", "unload", "-w", dest], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception:
            pass
        # Remove from LaunchAgents
        removed = False
        if os.path.exists(dest):
            try:
                os.remove(dest)
                removed = True
            except Exception:
                removed = False
        # Remove local plist copy
        local_plist = os.path.join(LAUNCHD_DIR, plist_filename)
        try:
            if os.path.exists(local_plist):
                os.remove(local_plist)
        except Exception:
            pass
        print(json.dumps({
            "ok": True,
            "unloaded": True,
            "removed_from_LaunchAgents": removed,
            "label": label,
            "plist_filename": plist_filename
        }, indent=2))
        return
    # Ensure placeholders exist even when no DIGEST is present
    try:
        ensure_file(NOTES_PATH, "# NOTES (living state)\n\nLast 20 digests. Older entries archived to logs/notes-archive/.\n")
    except Exception:
        pass

    try:
        # Create empty WSI if missing
        if not os.path.exists(WSI_PATH):
            os.makedirs(os.path.dirname(WSI_PATH), exist_ok=True)
            save_json(WSI_PATH, {"items": []})
    except Exception:
        pass

    # Debug: Log that Stop hook was triggered
    debug_log = os.path.join(LOGS_DIR, "stop_hook_debug.log")
    if STOP_DEBUG:
        _log(debug_log, f"\n[{_now_iso()}] Stop hook triggered")

    # Track time budget for the stop hook
    start_ts = time.time()

    # The Stop hook input varies; we expect at least the final assistant text under one of these keys.
    raw = sys.stdin.read()

    # Debug: Log payload keys
    if STOP_DEBUG:
        _log(debug_log, f"Raw input length: {len(raw)} bytes")

    try:
        payload = json.loads(raw)
        if STOP_DEBUG:
            _log(debug_log, f"Payload keys: {list(payload.keys())}")
    except Exception as e:
        if STOP_DEBUG:
            _log(debug_log, f"JSON parse error: {e}")
        print("Stop hook: invalid JSON payload", file=sys.stderr)
        sys.exit(1)

    # Fast path: check payload text for DIGEST before any transcript I/O
    text = (
        payload.get("assistant_text")
        or payload.get("final_message")
        or payload.get("content")
        or ""
    )
    digest = None
    if text:
        digest = extract_digest_from_text(text)
        if digest:
            if STOP_DEBUG:
                _log(debug_log, "⚡ Fast DIGEST path: found in payload text")
            try:
                append_notes(digest, None, debug_log_path=(debug_log if STOP_DEBUG else None))
                refresh_wsi(digest, None)
                job_path = enqueue_digest_job(digest, debug_log if STOP_DEBUG else None)
                if STOP_DEBUG:
                    _log(debug_log, f"✅ Wrote NOTES/WSI; queued job: {os.path.basename(job_path) if job_path else 'none'}")
                # Fire-and-forget: project status update (respect protections)
                try:
                    disable = os.environ.get("DISABLE_CLAUDE_MD_UPDATE", "false").lower() == "true"
                    is_global = os.path.realpath(PROJECT_ROOT) == os.path.realpath(os.path.expanduser("~/.claude"))
                    allow_global = os.environ.get("ALLOW_GLOBAL_CLAUDE_MD_UPDATE", "false").lower() == "true"
                    if not disable and (not is_global or allow_global):
                        subprocess.Popen(
                            [sys.executable, os.path.join(os.path.dirname(__file__), 'project_status.py'), '--update-claude-md', '--fast-local'],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                except Exception:
                    pass
                sys.exit(0)
            except Exception:
                # If anything fails here, fall through to transcript scan
                pass
    transcript_path = payload.get("transcript_path")

    if transcript_path and os.path.exists(transcript_path):
        try:
            # Fast path: tail-scan large transcripts to find DIGEST without loading entire file
            try:
                fsize = os.path.getsize(transcript_path)
            except Exception:
                fsize = 0
            if fsize and fsize > STOP_TAIL_WINDOW_BYTES:
                try:
                    with open(transcript_path, "rb") as tf:
                        tf.seek(max(0, fsize - STOP_TAIL_WINDOW_BYTES))
                        tail_bytes = tf.read()
                    tail_text = tail_bytes.decode("utf-8", errors="ignore")
                    m_fast = DIGEST_RE.search(tail_text)
                    if m_fast:
                        try:
                            fast_digest = json.loads(m_fast.group(1))
                            if STOP_DEBUG:
                                _log(debug_log, f"⚡ Fast DIGEST path: found in tail (size={fsize} bytes, window={STOP_TAIL_WINDOW_BYTES})")
                            # Process immediately and exit to keep Stop hook fast
                            append_notes(fast_digest, None, debug_log_path=(debug_log if STOP_DEBUG else None))
                            refresh_wsi(fast_digest, None)
                            job_path = enqueue_digest_job(fast_digest, debug_log if STOP_DEBUG else None)
                            if STOP_DEBUG:
                                _log(debug_log, f"✅ Wrote NOTES/WSI; queued job: {os.path.basename(job_path) if job_path else 'none'}")
                            # Fire-and-forget: fast-local project status update (respects global protection)
                            try:
                                disable = os.environ.get("DISABLE_CLAUDE_MD_UPDATE", "false").lower() == "true"
                                is_global = os.path.realpath(PROJECT_ROOT) == os.path.realpath(os.path.expanduser("~/.claude"))
                                allow_global = os.environ.get("ALLOW_GLOBAL_CLAUDE_MD_UPDATE", "false").lower() == "true"
                                if not disable and (not is_global or allow_global):
                                    subprocess.Popen(
                                        [sys.executable, os.path.join(os.path.dirname(__file__), 'project_status.py'), '--update-claude-md', '--fast-local'],
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL,
                                    )
                            except Exception:
                                pass
                            sys.exit(0)
                        except Exception:
                            # Fall through to full parse
                            pass
                except Exception:
                    # Fall through to full parse on any error
                    pass
            # Skip full parse for very large transcripts when configured
            if (
                fsize and STOP_TAIL_FAST_ONLY and STOP_HOOK_MAX_TRANSCRIPT_BYTES and fsize > STOP_HOOK_MAX_TRANSCRIPT_BYTES
            ):
                if STOP_DEBUG:
                    _log(debug_log, f"⏭️  Skipping full transcript parse (size={fsize} > limit={STOP_HOOK_MAX_TRANSCRIPT_BYTES})")
                sys.exit(0)
            # Transcript can be either JSON array or JSONL (one JSON per line)
            with open(transcript_path, "r", encoding="utf-8") as f:
                content = f.read().strip()

            # Try JSON array first
            try:
                transcript = json.loads(content)
            except json.JSONDecodeError:
                # Try JSONL (one JSON object per line)
                transcript = []
                for line in content.split('\n'):
                    if line.strip():
                        try:
                            transcript.append(json.loads(line))
                        except:
                            pass

            # Extract assistant messages, scanning from the end for fastest DIGEST detection
            # Claude Code format: messages have "type": "assistant" and "message": {"content": [...]}
            assistant_messages = []
            type_counts = {}  # Track what types we see

            found_inline_digest = False
            if isinstance(transcript, list):
                for msg in reversed(transcript):
                    if isinstance(msg, dict):
                        msg_type = msg.get("type", "unknown")
                        type_counts[msg_type] = type_counts.get(msg_type, 0) + 1

                        if msg_type == "assistant":
                            message_obj = msg.get("message", {})
                            content_blocks = message_obj.get("content", [])
                            if isinstance(content_blocks, list):
                                text_parts = []
                                for block in content_blocks:
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        text_parts.append(block.get("text", ""))
                                if text_parts:
                                    combined = "\n".join(text_parts)
                                    # Try to parse DIGEST quickly from the most recent assistant message
                                    m_inline = DIGEST_RE.search(combined)
                                    if m_inline:
                                        try:
                                            digest = json.loads(m_inline.group(1))
                                            text = combined
                                            found_inline_digest = True
                                            break
                                        except Exception:
                                            pass
                                    assistant_messages.append(combined)

            if not found_inline_digest and assistant_messages:
                # Fallback to most recent assistant message text
                text = assistant_messages[0]

            if STOP_DEBUG:
                _log(debug_log, f"📄 Read transcript: {len(transcript)} messages")
                _log(debug_log, f"   Type distribution: {type_counts}")
                _log(debug_log, f"   Assistant messages: {len(assistant_messages)}")
                _log(debug_log, f"   Last assistant message length: {len(text)}")
                if 'fsize' in locals() and fsize and fsize <= 2 * STOP_TAIL_WINDOW_BYTES and len(transcript) > 0:
                    sample = transcript[0] if len(transcript) > 0 else {}
                    _log(debug_log, f"   Sample message keys: {list(sample.keys()) if isinstance(sample, dict) else 'not a dict'}")

        except Exception as e:
            if STOP_DEBUG:
                _log(debug_log, f"⚠️  Failed to read transcript: {e}")
    else:
        # Fallback to direct payload keys (legacy/testing)
        # 'text' already set from payload earlier
        if STOP_DEBUG:
            _log(debug_log, f"⚠️  No transcript_path, using fallback (text length: {len(text)})")

    # Prefer: scan entire transcript for most recent DIGEST; fallback to last text
    digest = None
    try:
        if 'transcript' in locals() and transcript:
            digest = extract_latest_digest_from_transcript(transcript, debug_log)
    except Exception:
        pass
    if not digest:
        digest = extract_digest_from_text(text)

    # Time budget guard: if configured and no digest found yet, exit early
    if not digest and STOP_TIME_BUDGET_MS > 0:
        elapsed_ms = int((time.time() - start_ts) * 1000)
        if elapsed_ms >= STOP_TIME_BUDGET_MS:
            if STOP_DEBUG:
                _log(debug_log, f"⏱️  Exiting early due to time budget ({elapsed_ms}ms >= {STOP_TIME_BUDGET_MS}ms)")
            sys.exit(0)

    # Debug: Log digest detection
    if STOP_DEBUG:
        if digest:
            _log(debug_log, f"✅ DIGEST found: agent={digest.get('agent')}, task={digest.get('task_id')}")
            _log(debug_log, f"   Writing to: {NOTES_PATH}")
            _log(debug_log, f"   WSI path: {WSI_PATH}")
        else:
            _log(debug_log, f"ℹ️  No DIGEST block found in assistant text (length: {len(text)})")

    if not digest:
        # Not all turns will have a digest; don't fail noisily.
        sys.exit(0)

    try:
        # Skip RAG suggestions to avoid timeout - write NOTES.md immediately
        # RAG suggestions can be slow (MCP call + search), causing Stop hook timeout
        rag_suggestions = None
        enable_rag = os.environ.get("ENABLE_VECTOR_RAG", "false").lower() == "true"

        if STOP_DEBUG:
            if enable_rag:
                _log(debug_log, "ℹ️  RAG enabled - will ingest after writing NOTES.md")
            else:
                _log(debug_log, "ℹ️  RAG disabled (set ENABLE_VECTOR_RAG=true to enable)")

        # Write NOTES.md and WSI immediately (fast, critical)
        if STOP_DEBUG:
            _log(debug_log, "📝 About to call append_notes...")
        try:
            append_notes(digest, rag_suggestions, debug_log_path=(debug_log if STOP_DEBUG else None))
            if STOP_DEBUG:
                _log(debug_log, "📝 append_notes completed")
        except Exception as e:
            if STOP_DEBUG:
                _log(debug_log, f"❌ append_notes failed: {e}")
            raise

        if STOP_DEBUG:
            _log(debug_log, "📝 About to call refresh_wsi...")
        try:
            refresh_wsi(digest, rag_suggestions)
            if STOP_DEBUG:
                _log(debug_log, "📝 refresh_wsi completed")
        except Exception as e:
            if STOP_DEBUG:
                _log(debug_log, f"❌ refresh_wsi failed: {e}")
            raise

        # Enqueue this digest for ingestion (always)
        job_path = enqueue_digest_job(digest, debug_log if STOP_DEBUG else None)

        # Skip queue processing in Stop hook to avoid timeout
        # Let the launchd queue processor agent handle all ingestion (every 15 min)
        # This keeps Stop hook fast (<1s) and prevents cancellation
        q_summary = {"processed": 0, "succeeded": 0, "failed": 0, "skipped_no_creds": 0}

        if STOP_DEBUG:
            _log(debug_log, "✅ Successfully wrote NOTES and refreshed WSI")
            if job_path:
                _log(debug_log, f"   📌 Ingest job queued: {os.path.basename(job_path)}")
            _log(debug_log, "   ⏩ Queue processing deferred to launchd agent (prevents Stop hook timeout)")

        # Fire-and-forget: update CLAUDE.md <project_status> (fast-local, no vector)
        # Respect opt-out and do not touch global ~/.claude unless explicitly allowed
        try:
            disable = os.environ.get("DISABLE_CLAUDE_MD_UPDATE", "false").lower() == "true"
            is_global = os.path.realpath(PROJECT_ROOT) == os.path.realpath(os.path.expanduser("~/.claude"))
            allow_global = os.environ.get("ALLOW_GLOBAL_CLAUDE_MD_UPDATE", "false").lower() == "true"
            if not disable and (not is_global or allow_global):
                subprocess.Popen(
                    [sys.executable, os.path.join(os.path.dirname(__file__), 'project_status.py'), '--update-claude-md', '--fast-local'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if STOP_DEBUG:
                    _log(debug_log, "🧭 Triggered CLAUDE.md project status update (fast-local)")
            else:
                if STOP_DEBUG:
                    reason = "env opt-out" if disable else "global root protected"
                    _log(debug_log, f"🛑 Skipped CLAUDE.md status update ({reason})")
        except Exception as e:
            if STOP_DEBUG:
                _log(debug_log, f"⚠️  Failed to trigger CLAUDE.md update: {e}")

        # Call PM decision hook if enabled
        # This allows GPT-5 to make strategic decisions when agent encounters decision points
        enable_pm = os.environ.get("ENABLE_PM_AGENT", "false").lower() == "true"
        if enable_pm and text:
            if STOP_DEBUG:
                _log(debug_log, "🤖 PM Agent enabled - checking for decision points...")
            try:
                pm_hook_path = os.path.join(os.path.dirname(__file__), "pm_decision_hook.py")
                # Pass last message text to PM hook (don't block on it - run async)
                # Note: We're not waiting for result to keep Stop hook fast
                subprocess.Popen(
                    [sys.executable, pm_hook_path, "--async"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                # Feed decision context via stdin
                input_data = json.dumps({
                    "last_message": text[-1000:],  # Last 1000 chars
                    "digest": digest,
                    "debug_log": debug_log
                })
                if STOP_DEBUG:
                    _log(debug_log, "   ✅ PM hook spawned (async)")
            except Exception as e:
                if STOP_DEBUG:
                    _log(debug_log, f"   ⚠️  PM hook failed: {e}")

        # Fire-and-forget: Implementation Validator (IV) to check completeness before TA
        try:
            enable_iv = os.environ.get("ENABLE_IV", "false").lower() == "true"
            if enable_iv:
                iv_path = os.path.join(os.path.dirname(__file__), "implementation_validator.py")
                subprocess.Popen(
                    [sys.executable, iv_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if STOP_DEBUG:
                    _log(debug_log, "🧪 Spawned Implementation Validator (IV)")
        except Exception as e:
            if STOP_DEBUG:
                _log(debug_log, f"⚠️  Failed to spawn IV: {e}")

        # Show user-visible warning if credentials are missing (check via env var instead)
        enable_rag = os.environ.get("ENABLE_VECTOR_RAG", "false").lower() == "true"
        if not enable_rag:
            print(
                f"\n⚠️  Vector RAG ingestion skipped ({q_summary['skipped_no_creds']} job(s)) - missing credentials.\n"
                f"To enable automatic DIGEST ingestion to AI memory:\n"
                f"  1. Ensure DATABASE_URL_MEMORY, REDIS_URL, and OPENAI_API_KEY are set\n"
                f"  2. Or run: python hooks/stop_digest.py --process-queue (after credentials are configured)\n"
                f"  3. Check status: python hooks/stop_digest.py --queue-status\n",
                file=sys.stderr
            )
    except Exception as e:
        if STOP_DEBUG:
            _log(debug_log, f"❌ Error writing NOTES/WSI: {e}")
        print(f"Stop hook: failed to write NOTES/WSI: {e}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    main()
