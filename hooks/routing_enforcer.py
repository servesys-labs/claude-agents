#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Routing Enforcer hook: Ensure Main Agent states routing decision.

Checks assistant messages for mandatory "Routing Decision" statement.
Enforces subagent delegation rules from CLAUDE.md.

Exit code semantics:
- 0: routing decision present and valid
- 1: warning (missing routing decision, non-blocking)
- 2: block (code file edit without subagent delegation)
"""
import sys
import json
import re
from pathlib import Path

# Code file extensions requiring subagent delegation
CODE_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".py")

# Directories that are infrastructure (not application code)
INFRA_DIRECTORIES = [
    "claude-hooks",
    ".claude/agents",
    "hooks",
    "scripts",
    "mcp-servers"
]


def is_infrastructure_file(file_path: str) -> bool:
    """Check if file is infrastructure (allowed without subagent)."""
    if not file_path:
        return False

    # Check if in infrastructure directory
    for infra_dir in INFRA_DIRECTORIES:
        if infra_dir in file_path:
            return True

    return False


def is_code_file(file_path: str) -> bool:
    """Check if file is application code requiring subagent."""
    if not file_path:
        return False

    # Check extension
    if not any(file_path.endswith(ext) for ext in CODE_EXTENSIONS):
        return False

    # Exclude infrastructure
    if is_infrastructure_file(file_path):
        return False

    return True


def extract_routing_decision(assistant_message: str) -> tuple[str | None, str | None]:
    """
    Extract routing decision from assistant message.

    Returns:
        (decision_type, reason) or (None, None) if not found
    """
    # Look for "**Routing Decision**: ..."
    pattern = r'\*\*Routing Decision\*\*:\s*\[(.*?)\](?:\s*-\s*(.*))?'
    match = re.search(pattern, assistant_message)

    if match:
        decision_type = match.group(1).strip()
        reason = match.group(2).strip() if match.group(2) else None
        return decision_type, reason

    return None, None


def validate_routing_decision(decision_type: str, tool_name: str, file_path: str) -> dict:
    """
    Validate that routing decision matches action taken.

    Returns:
        {"valid": bool, "issue": str or None}
    """
    # If decision is a subagent name, tool should be Task
    if decision_type and not decision_type.startswith("direct:"):
        if tool_name != "Task":
            return {
                "valid": False,
                "issue": f"Routing decision says '{decision_type}' but used {tool_name} instead of Task tool"
            }

    # If decision is "direct", check if file is allowed
    if decision_type and decision_type.startswith("direct:"):
        if tool_name in ("Edit", "Write", "MultiEdit") and is_code_file(file_path):
            return {
                "valid": False,
                "issue": f"Direct edit on code file {file_path} - should use subagent"
            }

    return {"valid": True, "issue": None}


def main():
    raw = sys.stdin.read()

    try:
        data = json.loads(raw)
    except Exception:
        # Invalid JSON, skip
        sys.exit(0)

    # Only check on assistant messages (responses)
    message_type = data.get("message_type")
    if message_type != "assistant":
        sys.exit(0)

    assistant_message = data.get("message", "") or data.get("content", "")
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Skip if no tools used (just conversation)
    if not tool_name:
        sys.exit(0)

    # Skip for allowed tools (Read, Grep, Glob, Bash)
    allowed_without_routing = ["Read", "Grep", "Glob", "Bash", "WebFetch", "WebSearch"]
    if tool_name in allowed_without_routing:
        sys.exit(0)

    # Extract routing decision
    decision_type, reason = extract_routing_decision(assistant_message)

    # Check if routing decision is present
    if not decision_type:
        # Missing routing decision
        print("", file=sys.stderr)
        print("⚠️  ROUTING DECISION MISSING", file=sys.stderr)
        print("", file=sys.stderr)
        print(f"Tool used: {tool_name}", file=sys.stderr)
        if file_path:
            print(f"File: {file_path}", file=sys.stderr)
        print("", file=sys.stderr)
        print("💡 Every response using tools should start with:", file=sys.stderr)
        print("   **Routing Decision**: [subagent-name] or [direct: reason]", file=sys.stderr)
        print("", file=sys.stderr)
        # Warning only, non-blocking
        sys.exit(1)

    # Validate routing decision matches action
    validation = validate_routing_decision(decision_type, tool_name, file_path)

    if not validation["valid"]:
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("❌ ROUTING VIOLATION", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"Decision: {decision_type}", file=sys.stderr)
        print(f"Issue: {validation['issue']}", file=sys.stderr)
        print("", file=sys.stderr)
        print("💡 Either:", file=sys.stderr)
        print("   1. Use Task tool with appropriate subagent", file=sys.stderr)
        print("   2. Update routing decision to [direct: valid reason]", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("", file=sys.stderr)
        # Block invalid routing
        sys.exit(2)

    # Valid routing decision
    sys.exit(0)


if __name__ == "__main__":
    main()
