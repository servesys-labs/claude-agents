#!/usr/bin/env python3
"""
Conversation Summary Ingest Hook (PostCompact)

After compaction, reads the conversation summary and ingests it into vector RAG
for future retrieval. This creates a persistent memory of high-level decisions
and outcomes across sessions.

Triggered: After PreCompact hook creates COMPACTION.md
Ingests: Conversation summary with metadata (timestamp, agents, decisions, outcomes)
Output: Ingestion confirmation to stderr (non-blocking)
"""
import sys
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime

# Constants
LOGS_DIR_STR = os.environ.get("LOGS_DIR", os.path.expanduser("~/.claude/logs"))
CLAUDE_LOGS_DIR = Path(LOGS_DIR_STR)
PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
SUMMARY_JSON = CLAUDE_LOGS_DIR / "compaction-summary.json"
SUMMARY_MD = CLAUDE_LOGS_DIR / "COMPACTION.md"
DEBUG = os.environ.get("ENABLE_VECTOR_RAG_DEBUG", "").lower() == "true"

def call_memory_ingest(project_root, path, text, meta):
    """Call memory_ingest via MCP subprocess."""
    try:
        # MCP request format
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "capabilities": {},
                "clientInfo": {"name": "conversation-summary-ingest", "version": "1.0.0"}
            }
        }

        tool_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "memory_ingest",
                "arguments": {
                    "project_root": project_root,
                    "path": path,
                    "text": text,
                    "meta": meta
                }
            }
        }

        # Build MCP command
        node_path = os.environ.get("NODE_PATH", "/usr/local/bin/node")
        vector_bridge = Path.home() / ".claude" / "mcp-servers" / "vector-bridge" / "dist" / "index.js"

        env = os.environ.copy()
        env["DATABASE_URL_MEMORY"] = os.environ.get("DATABASE_URL_MEMORY", "")
        env["REDIS_URL"] = os.environ.get("REDIS_URL", "")
        env["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "")

        proc = subprocess.Popen(
            [node_path, str(vector_bridge)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True
        )

        requests = f"{json.dumps(init_request)}\n{json.dumps(tool_request)}\n"
        stdout, stderr = proc.communicate(input=requests, timeout=10)

        # Parse responses
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
                result = resp.get("result", {})
                if result and not result.get("error"):
                    return result

        return None
    except Exception as e:
        if DEBUG:
            print(f"[conv_ingest] MCP call failed: {e}", file=sys.stderr)
        return None

def extract_summary_for_ingestion(summary_json, summary_md):
    """Extract and format conversation summary for vector ingestion."""
    try:
        with open(summary_json, 'r') as f:
            summary = json.load(f)
    except:
        return None

    # Build compact text representation of the conversation
    lines = [
        f"Conversation Summary - {summary.get('timestamp', 'unknown')}",
        "",
        "Agents Active: " + ", ".join(summary.get('agents_seen', [])),
        "",
        "Key Decisions:",
    ]

    for decision in summary.get("decisions", [])[:5]:  # Top 5 decisions
        lines.append(f"  - {decision}")

    lines.append("")
    lines.append("Next Steps:")
    for step in summary.get("next_steps", [])[:5]:  # Top 5 next steps
        lines.append(f"  - {step}")

    lines.append("")
    lines.append("Files Modified:")
    for artifact in summary.get("owned_artifacts", [])[:10]:  # Top 10 files
        lines.append(f"  - {artifact}")

    if summary.get("contracts_touched"):
        lines.append("")
        lines.append("Contracts Affected:")
        for contract in summary.get("contracts_touched", [])[:5]:
            lines.append(f"  - {contract}")

    if summary.get("open_questions"):
        lines.append("")
        lines.append("Open Questions:")
        for question in summary.get("open_questions", [])[:3]:
            lines.append(f"  - {question}")

    if summary.get("risks"):
        lines.append("")
        lines.append("Risks:")
        for risk in summary.get("risks", [])[:3]:
            lines.append(f"  - {risk}")

    text = "\n".join(lines)

    # Build metadata for filtering and outcome tracking
    meta = {
        "source": "conversation-summary",
        "category": "decision",
        "component": "docs",
        "timestamp": summary.get("timestamp"),
        "agents": summary.get("agents_seen", []),
        "decision_count": len(summary.get("decisions", [])),
        "file_count": len(summary.get("owned_artifacts", [])),
        "has_open_questions": len(summary.get("open_questions", [])) > 0,
        "has_risks": len(summary.get("risks", [])) > 0,
        # Infer outcome status from summary
        "outcome_status": infer_outcome_status(summary)
    }

    return text, meta

def infer_outcome_status(summary):
    """
    Infer success/failure status from summary signals.

    Heuristics:
    - Success: Has next steps, no open questions/risks
    - Failure: Has risks or many open questions with no next steps
    - Unknown: Mixed signals
    """
    has_next_steps = len(summary.get("next_steps", [])) > 0
    has_open_questions = len(summary.get("open_questions", [])) > 0
    has_risks = len(summary.get("risks", [])) > 0
    decisions_count = len(summary.get("decisions", []))

    # Clear success: completed work with next steps, no blockers
    if has_next_steps and not has_open_questions and not has_risks and decisions_count > 0:
        return "success"

    # Clear failure: risks or questions without progress
    if (has_risks or has_open_questions) and not has_next_steps and decisions_count == 0:
        return "failure"

    # Mixed signals or unclear - mark as unknown
    return "unknown"

def main():
    # Check if Vector RAG is enabled
    if os.environ.get("ENABLE_VECTOR_RAG", "").lower() != "true":
        if DEBUG:
            print("[conv_ingest] Skipped: ENABLE_VECTOR_RAG not enabled", file=sys.stderr)
        sys.exit(0)

    # Check if summary files exist
    if not SUMMARY_JSON.exists() or not SUMMARY_MD.exists():
        if DEBUG:
            print("[conv_ingest] Skipped: No compaction summary found", file=sys.stderr)
        sys.exit(0)

    # Extract summary data
    result = extract_summary_for_ingestion(SUMMARY_JSON, SUMMARY_MD)
    if not result:
        if DEBUG:
            print("[conv_ingest] Skipped: Failed to parse summary", file=sys.stderr)
        sys.exit(0)

    text, meta = result

    # Validate content length (skip empty summaries)
    if len(text) < 50:
        if DEBUG:
            print("[conv_ingest] Skipped: Summary too short", file=sys.stderr)
        sys.exit(0)

    if DEBUG:
        print(f"[conv_ingest] Ingesting conversation summary ({len(text)} bytes)", file=sys.stderr)
        print(f"[conv_ingest] Outcome: {meta.get('outcome_status')}, Decisions: {meta.get('decision_count')}", file=sys.stderr)

    # Call memory_ingest
    ingest_result = call_memory_ingest(
        project_root=str(PROJECT_ROOT),
        path=f".claude/logs/conversations/{meta['timestamp'].replace(' ', '_').replace(':', '-')}.md",
        text=text,
        meta=meta
    )

    if ingest_result:
        chunks = ingest_result.get("chunks", 0)
        if DEBUG or chunks > 0:
            print(f"[conv_ingest] ✅ Ingested conversation summary: {chunks} chunks", file=sys.stderr)
    else:
        if DEBUG:
            print("[conv_ingest] ⚠️ Ingestion failed or returned no result", file=sys.stderr)

    # Non-blocking (always exit 0)
    sys.exit(0)

if __name__ == "__main__":
    main()
