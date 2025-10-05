#!/usr/bin/env python3
"""
GPT-5 Cost Tracker Hook

PostToolUse hook that automatically displays cost and token usage
after every OpenAI API call via the mcp__openai-bridge.

Triggered on: mcp__openai-bridge__ask_gpt5 tool usage
Displays: Request cost, session total, token breakdown
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

    # Only track OpenAI bridge calls
    if not tool_name.startswith("mcp__openai-bridge__ask_gpt"):
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

        # Extract cost and token data
        cost_info = response.get("cost", {})
        tokens_info = response.get("tokens", {})
        model = response.get("model", "unknown")
        model_desc = response.get("model_description", "")

        if not cost_info or not tokens_info:
            sys.exit(0)

        # Display compact cost summary
        print("", file=sys.stderr)
        print("💰 GPT-5 Usage", file=sys.stderr)
        print(f"Model: {model}", file=sys.stderr)
        if model_desc:
            print(f"  ({model_desc})", file=sys.stderr)
        print(f"Tokens: {tokens_info.get('total', 0):,} ({tokens_info.get('prompt', 0):,} prompt + {tokens_info.get('completion', 0):,} completion)", file=sys.stderr)
        print(f"This request: {cost_info.get('this_request_formatted', 'N/A')}", file=sys.stderr)
        print(f"Session total: {cost_info.get('session_total_formatted', 'N/A')}", file=sys.stderr)

        # Show pricing info if available
        pricing = response.get("pricing_info", {})
        if pricing:
            print(f"Rate: {pricing.get('prompt_rate', 'N/A')} prompt, {pricing.get('completion_rate', 'N/A')} completion", file=sys.stderr)

        print("", file=sys.stderr)

        # Non-blocking (exit 0 = continue normally)
        sys.exit(0)

    except Exception as e:
        # Silently fail - don't block on parsing errors
        sys.exit(0)

if __name__ == "__main__":
    main()
