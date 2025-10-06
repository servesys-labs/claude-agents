#!/usr/bin/env python3
"""
MCP Cost Tracker Hook

PostToolUse hook that automatically displays cost and token usage
after vector-bridge MCP tool calls (memory_search, memory_ingest).

Triggered on: mcp__vector-bridge__* tool usage
Displays: Embeddings generated, tokens used, estimated cost
"""
import sys
import json

def main():
    # Read hook payload
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_output = data.get("tool_output", {})

    # Only track vector-bridge calls
    if not tool_name.startswith("mcp__vector-bridge__"):
        sys.exit(0)

    # Parse the response
    try:
        if isinstance(tool_output, str):
            response = json.loads(tool_output)
        elif isinstance(tool_output, dict):
            response = tool_output
        else:
            sys.exit(0)

        # Check if this is an error response
        if "error" in response or not response.get("success"):
            sys.exit(0)

        # memory_ingest: show chunks and estimated embedding cost
        if tool_name == "mcp__vector-bridge__memory_ingest":
            chunks = response.get("chunks", 0)
            project_id = response.get("project_id", "unknown")

            if chunks == 0:
                sys.exit(0)  # Skip if nothing was ingested

            # OpenAI text-embedding-3-small pricing: $0.02/1M tokens
            # Estimate ~500 tokens per chunk (conservative)
            estimated_tokens = chunks * 500
            estimated_cost = estimated_tokens * (0.02 / 1_000_000)

            print("", file=sys.stderr)
            print("🧠 Vector Memory Ingestion", file=sys.stderr)
            print(f"Chunks: {chunks} ingested", file=sys.stderr)
            print(f"Project: {project_id}", file=sys.stderr)
            print(f"Est. Tokens: ~{estimated_tokens:,}", file=sys.stderr)
            print(f"Est. Cost: ~${estimated_cost:.6f}", file=sys.stderr)
            print("Model: text-embedding-3-small ($0.02/1M tokens)", file=sys.stderr)
            print("", file=sys.stderr)

        # memory_search: show results and query cost
        elif tool_name == "mcp__vector-bridge__memory_search":
            results = response.get("results", [])
            total = response.get("total", len(results))

            if total == 0:
                sys.exit(0)  # Skip if no results

            # Query embeddings: typically 1 query = ~100-200 tokens
            estimated_tokens = 150
            estimated_cost = estimated_tokens * (0.02 / 1_000_000)

            print("", file=sys.stderr)
            print("🔍 Vector Memory Search", file=sys.stderr)
            print(f"Results: {total} chunks found", file=sys.stderr)
            print(f"Query Tokens: ~{estimated_tokens}", file=sys.stderr)
            print(f"Query Cost: ~${estimated_cost:.6f}", file=sys.stderr)

            # Show top result similarity
            if results and len(results) > 0:
                top_score = results[0].get("score", 0)
                print(f"Top Match: {top_score:.1%} similarity", file=sys.stderr)

            print("", file=sys.stderr)

        # memory_projects: just show project count (no cost)
        elif tool_name == "mcp__vector-bridge__memory_projects":
            projects = response.get("projects", [])
            total = response.get("total", len(projects))

            print("", file=sys.stderr)
            print("📊 Vector Memory Projects", file=sys.stderr)
            print(f"Projects: {total} indexed", file=sys.stderr)
            print("", file=sys.stderr)

        # Non-blocking (exit 0 = continue normally)
        sys.exit(0)

    except Exception as e:
        # Silently fail - don't block on parsing errors
        sys.exit(0)

if __name__ == "__main__":
    main()
