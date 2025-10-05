#!/usr/bin/env python3
"""
Perplexity Tracker Hook

PostToolUse hook that automatically displays cost and token usage
after every Perplexity API call via the mcp__perplexity-ask.

Triggered on: mcp__perplexity-ask__* tool usage
Displays: Request cost, session total, token breakdown, model info
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

    # Only track Perplexity calls
    if not tool_name.startswith("mcp__perplexity-ask__"):
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
        if "error" in response or "Error" in str(response):
            sys.exit(0)

        # Perplexity API response structure varies by endpoint
        # For perplexity_ask and perplexity_research
        usage = response.get("usage", {})
        model = response.get("model", "unknown")

        # For perplexity_search (no cost/usage)
        if tool_name == "mcp__perplexity-ask__perplexity_search":
            results = response.get("results", [])
            print("", file=sys.stderr)
            print("🔍 Perplexity Search", file=sys.stderr)
            print(f"Results: {len(results)} links found", file=sys.stderr)
            print("", file=sys.stderr)
            sys.exit(0)

        # Skip if no usage data
        if not usage:
            sys.exit(0)

        # Extract token counts
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        # Perplexity pricing (as of October 2025)
        # sonar-pro: $3/1M input, $15/1M output
        # sonar: $1/1M input, $5/1M output
        # sonar-reasoning: $1/1M input, $5/1M output
        pricing_map = {
            "sonar-pro": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000},
            "sonar": {"input": 1.0 / 1_000_000, "output": 5.0 / 1_000_000},
            "sonar-reasoning": {"input": 1.0 / 1_000_000, "output": 5.0 / 1_000_000},
        }

        pricing = pricing_map.get(model, {"input": 1.0 / 1_000_000, "output": 5.0 / 1_000_000})

        # Calculate costs
        input_cost = prompt_tokens * pricing["input"]
        output_cost = completion_tokens * pricing["output"]
        request_cost = input_cost + output_cost

        # Display compact summary
        print("", file=sys.stderr)
        print("🔮 Perplexity Usage", file=sys.stderr)
        print(f"Model: {model}", file=sys.stderr)
        print(f"Tokens: {total_tokens:,} ({prompt_tokens:,} input + {completion_tokens:,} output)", file=sys.stderr)
        print(f"Cost: ${request_cost:.4f}", file=sys.stderr)
        print(f"Rate: ${pricing['input'] * 1_000_000:.2f}/1M input, ${pricing['output'] * 1_000_000:.2f}/1M output", file=sys.stderr)

        # Show if citations/sources were used
        citations = response.get("citations", [])
        if citations:
            print(f"Sources: {len(citations)} citations", file=sys.stderr)

        print("", file=sys.stderr)

        # Non-blocking (exit 0 = continue normally)
        sys.exit(0)

    except Exception as e:
        # Silently fail - don't block on parsing errors
        sys.exit(0)

if __name__ == "__main__":
    main()
