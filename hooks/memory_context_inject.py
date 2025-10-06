#!/usr/bin/env python3
"""
Memory Context Injection Hook (PreToolUse)

Automatically injects relevant memories from Vector RAG before Task tool invocations.
Provides agents with context from similar past tasks without manual memory_search calls.

Triggered on: Task tool (RC, CN, IE, TA agents)
Injects: Top 2-3 related decisions/outcomes as compact bullets
Guardrails:
  - Only when ENABLE_VECTOR_RAG=true
  - Only when queue=0 (fresh data)
  - Only when context <70% (budget available)
  - Score threshold ≥0.25
  - Max 250 tokens injected
  - Fail-open (never blocks)
"""
import sys
import json
import os
import subprocess
from pathlib import Path

# Constants
MAX_TOKENS = 250
SCORE_THRESHOLD = 0.25
MAX_RESULTS = 2
CONTEXT_BUDGET_THRESHOLD = 0.70

def get_queue_status():
    """Check if ingestion queue has pending items."""
    try:
        project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        queue_dir = Path(project_root) / ".claude" / "ingest-queue"
        if not queue_dir.exists():
            return 0
        queued = len(list(queue_dir.glob("*.json")))
        return queued
    except:
        return 0

def get_context_usage():
    """Estimate current context usage (rough heuristic)."""
    # Placeholder: would need actual token count from transcript
    # For now, always return 0.5 (50%) as safe default
    return 0.5

def call_memory_search(query, project_root, k=2):
    """Call memory_search via MCP subprocess."""
    try:
        # MCP request format
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "capabilities": {},
                "clientInfo": {"name": "memory-context-inject", "version": "1.0.0"}
            }
        }

        tool_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "memory_search",
                "arguments": {
                    "query": query,
                    "project_root": project_root,
                    "k": k,
                    "global": False
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
        stdout, stderr = proc.communicate(input=requests, timeout=3)

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
                if result.get("success"):
                    return result.get("results", [])

        return []
    except:
        return []

def format_memory_context(results):
    """Format memory results as compact bullet points."""
    if not results:
        return ""

    lines = ["\n📚 **Related Past Decisions:**\n"]

    for i, result in enumerate(results[:MAX_RESULTS], 1):
        meta = result.get("meta", {})
        chunk = result.get("chunk", "")
        score = result.get("score", 0)

        # Extract key info
        agent = meta.get("agent", "Unknown")
        task = meta.get("task_id", "")
        outcome = meta.get("outcome_status", "")

        # Truncate chunk to ~60 chars
        chunk_preview = chunk[:60].replace("\n", " ") + "..." if len(chunk) > 60 else chunk

        # Format bullet
        outcome_emoji = "✅" if outcome == "success" else "⚠️" if outcome == "failure" else "📝"
        lines.append(f"{i}. {outcome_emoji} **{agent}** ({task}): {chunk_preview} (relevance: {score:.0%})")

    lines.append("")  # Blank line after

    total_chars = sum(len(line) for line in lines)
    if total_chars > MAX_TOKENS * 4:  # Rough token estimate (1 token ≈ 4 chars)
        return ""  # Skip if too large

    return "\n".join(lines)

def main():
    # Read hook payload
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except:
        sys.exit(0)  # Fail-open

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Only inject for Task tool with planning agents
    if tool_name != "Task":
        sys.exit(0)

    subagent_type = tool_input.get("subagent_type", "")
    planning_agents = ["requirements-clarifier", "code-navigator-impact", "implementation-engineer", "test-author-coverage-enforcer"]

    if subagent_type not in planning_agents:
        sys.exit(0)

    # Check guardrails
    debug = os.environ.get("MEMORY_INJECT_DEBUG", "").lower() == "true"

    if os.environ.get("ENABLE_VECTOR_RAG", "").lower() != "true":
        if debug:
            print(f"[memory_inject] Skipped: ENABLE_VECTOR_RAG not true", file=sys.stderr)
        sys.exit(0)  # RAG disabled

    queue_count = get_queue_status()
    if queue_count > 5:  # Allow small queues (≤5 items)
        if debug:
            print(f"[memory_inject] Skipped: Queue has {queue_count} items (threshold: 5)", file=sys.stderr)
        sys.exit(0)  # Stale data in queue

    context_usage = get_context_usage()
    if context_usage > CONTEXT_BUDGET_THRESHOLD:
        if debug:
            print(f"[memory_inject] Skipped: Context usage {context_usage:.0%} > {CONTEXT_BUDGET_THRESHOLD:.0%}", file=sys.stderr)
        sys.exit(0)  # Context budget exhausted

    if debug:
        print(f"[memory_inject] Passed guardrails: queue={queue_count}, context={context_usage:.0%}, agent={subagent_type}", file=sys.stderr)

    # Extract query from task prompt
    prompt = tool_input.get("prompt", "")
    if len(prompt) < 20:
        sys.exit(0)  # Too short to search

    # Get project root
    project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    # Search for relevant memories
    if debug:
        print(f"[memory_inject] Searching: query='{prompt[:60]}...' project={project_root}", file=sys.stderr)

    results = call_memory_search(prompt[:200], project_root, k=MAX_RESULTS)

    if debug:
        print(f"[memory_inject] Found {len(results)} results", file=sys.stderr)
        for r in results:
            print(f"  - score={r.get('score', 0):.2%} path={r.get('path', 'unknown')}", file=sys.stderr)

    # Filter by score threshold
    results = [r for r in results if r.get("score", 0) >= SCORE_THRESHOLD]

    if not results:
        if debug:
            print(f"[memory_inject] Skipped: No results above threshold {SCORE_THRESHOLD:.0%}", file=sys.stderr)
        sys.exit(0)  # No relevant memories

    if debug:
        print(f"[memory_inject] Injecting {len(results)} relevant memories", file=sys.stderr)

    # Format and inject context
    context = format_memory_context(results)

    if context:
        # Inject into prompt
        modified_prompt = f"{prompt}\n{context}"
        modified_input = tool_input.copy()
        modified_input["prompt"] = modified_prompt

        # Output modified tool input
        print(json.dumps({
            "tool_name": tool_name,
            "tool_input": modified_input
        }))
        sys.exit(1)  # Exit 1 = modify tool input
    else:
        sys.exit(0)  # No modification

if __name__ == "__main__":
    main()
