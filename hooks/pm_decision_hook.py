#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Decision Hook - GPT-5 Product Manager Integration

Called by stop_digest.py when conversation ends with a decision point.
Passes context to GPT-5 PM agent via OpenAI MCP for autonomous decision-making.

Flow:
1. Detect decision point in last message (questions, options, "should I...")
2. Load AGENTS.md (project context) + pm-decisions.json (past decisions)
3. Call GPT-5 via OpenAI MCP with context
4. Receive decision JSON
5. Append to pm-decisions.json
6. Create resume instructions for next session
"""

import os
import sys
import json
import subprocess
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

# Paths
CLAUDE_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())) / ".claude"
LOGS_DIR = CLAUDE_DIR / "logs"
AGENTS_MD = CLAUDE_DIR.parent / "AGENTS.md"
PM_DECISIONS_LOG = LOGS_DIR / "pm-decisions.json"
PM_RESUME_DIR = LOGS_DIR / "pm-resume"

# Ensure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)
PM_RESUME_DIR.mkdir(parents=True, exist_ok=True)


def detect_decision_point(last_message: str) -> Optional[Dict[str, Any]]:
    """
    Detect if last message contains a decision point requiring PM intervention.

    Returns:
        Dict with decision point details, or None if no decision needed
    """
    # Decision indicators
    question_patterns = [
        "should i",
        "would you prefer",
        "what would you like",
        "continue or pause",
        "option a or b",
        "which approach",
        "apply now or later",
    ]

    last_lower = last_message.lower()

    # Check for question patterns
    has_question = any(pattern in last_lower for pattern in question_patterns)
    has_question_mark = "?" in last_message

    if not (has_question or has_question_mark):
        return None

    # Extract decision context (last 500 chars for context)
    context_snippet = last_message[-500:] if len(last_message) > 500 else last_message

    return {
        "detected": True,
        "type": "agent_question",
        "context_snippet": context_snippet,
        "full_message": last_message
    }


def load_agents_md() -> str:
    """Load AGENTS.md for PM context."""
    if not AGENTS_MD.exists():
        return "# AGENTS.md not found\n\nNo project context available."

    return AGENTS_MD.read_text(encoding="utf-8")


def load_past_decisions(limit: int = 10) -> List[Dict[str, Any]]:
    """Load last N PM decisions from log."""
    if not PM_DECISIONS_LOG.exists():
        return []

    try:
        with open(PM_DECISIONS_LOG, "r", encoding="utf-8") as f:
            decisions = json.load(f)
        return decisions[-limit:]  # Last N decisions
    except Exception:
        return []


def save_decision(decision: Dict[str, Any]) -> None:
    """Append decision to PM decisions log."""
    decisions = []
    if PM_DECISIONS_LOG.exists():
        try:
            with open(PM_DECISIONS_LOG, "r", encoding="utf-8") as f:
                decisions = json.load(f)
        except Exception:
            decisions = []

    decision["timestamp"] = datetime.now().isoformat()
    decision["id"] = hashlib.sha256(decision["timestamp"].encode()).hexdigest()[:8]
    decisions.append(decision)

    # Keep last 50 decisions (prune old ones)
    decisions = decisions[-50:]

    with open(PM_DECISIONS_LOG, "w", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2)


def call_gpt5_pm(
    decision_point: Dict[str, Any],
    agents_md: str,
    past_decisions: List[Dict[str, Any]],
    last_digest: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Call GPT-5 via OpenAI MCP to get PM decision.

    Args:
        decision_point: Detected decision point details
        agents_md: Content of AGENTS.md
        past_decisions: Recent PM decisions for context
        last_digest: Last DIGEST from conversation

    Returns:
        Decision dict from GPT-5, or None if call failed
    """
    # Build prompt for GPT-5
    prompt = f"""You are the GPT-5 Product Manager for this AI orchestration framework.

An agent has encountered a decision point and needs your guidance.

## Project Context (from AGENTS.md):
{agents_md}

## Past Decisions (for reference):
{json.dumps(past_decisions, indent=2)}

## Current State (Last DIGEST):
{json.dumps(last_digest, indent=2) if last_digest else "No DIGEST available"}

## Decision Point:
{decision_point['full_message']}

## Your Task:
Make a strategic decision following the decision framework in AGENTS.md.
Respond ONLY with valid JSON matching this schema:

{{
  "decision": "short_decision_id",
  "reasoning": "Why this decision aligns with project goals",
  "actions": ["Step 1", "Step 2", "Step 3"],
  "risks": ["Risk 1", "Risk 2"],
  "mitigation": ["Mitigation 1", "Mitigation 2"],
  "escalate_to_user": false,
  "update_goals": false,
  "notes": "Any additional context for the agent"
}}

Be decisive, production-ready, and follow the core principles (NO-REGRESSION, ADDITIVE-FIRST, PROD-READY BIAS).
"""

    # Call OpenAI MCP via ask_gpt5 tool
    try:
        # Use high reasoning model (o1 series or gpt-4)
        result = subprocess.run(
            [
                "node",
                os.path.expanduser("~/.claude/mcp-servers/openai-bridge/dist/index.js"),
            ],
            input=json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "ask_gpt5",
                    "arguments": {
                        "prompt": prompt,
                        "model": "gpt-4o",  # Use gpt-4o for cost efficiency with good reasoning
                        "temperature": 0.3,  # Lower temp for consistent decisions
                        "max_tokens": 2000
                    }
                }
            }),
            capture_output=True,
            text=True,
            timeout=30
        )

        # Parse response
        lines = result.stdout.strip().split("\n")
        for line in lines:
            try:
                msg = json.loads(line)
                if "result" in msg and "content" in msg["result"]:
                    content = msg["result"]["content"]
                    # Extract JSON from response (may be wrapped in markdown)
                    if isinstance(content, list) and len(content) > 0:
                        text = content[0].get("text", "")
                        # Try to extract JSON block
                        if "```json" in text:
                            json_str = text.split("```json")[1].split("```")[0].strip()
                        elif "```" in text:
                            json_str = text.split("```")[1].split("```")[0].strip()
                        else:
                            json_str = text.strip()

                        return json.loads(json_str)
            except Exception:
                continue

        return None

    except Exception as e:
        print(f"Error calling GPT-5 PM: {e}", file=sys.stderr)
        return None


def create_resume_instructions(decision: Dict[str, Any], decision_point: Dict[str, Any]) -> str:
    """
    Create resume instructions file for next Claude session.

    Returns:
        Path to resume instructions file
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    resume_file = PM_RESUME_DIR / f"resume-{timestamp}.md"

    content = f"""# PM Decision: Resume Instructions

**Decision ID:** {decision.get('id', 'unknown')}
**Timestamp:** {decision.get('timestamp', 'unknown')}
**Decision:** {decision.get('decision', 'unknown')}

## Context
The previous agent session ended with this decision point:

```
{decision_point.get('context_snippet', 'No context available')}
```

## PM Decision
**Reasoning:** {decision.get('reasoning', 'No reasoning provided')}

**Escalate to User:** {decision.get('escalate_to_user', False)}

## Actions to Take
{chr(10).join(f"{i+1}. {action}" for i, action in enumerate(decision.get('actions', [])))}

## Risks & Mitigation
{chr(10).join(f"- Risk: {risk}" for risk in decision.get('risks', []))}
{chr(10).join(f"- Mitigation: {mitigation}" for mitigation in decision.get('mitigation', []))}

## Notes
{decision.get('notes', 'No additional notes')}

---

**To resume:** Start new Claude session in the project directory and reference this file.
The agent should execute the actions listed above autonomously.
"""

    resume_file.write_text(content, encoding="utf-8")
    return str(resume_file)


def enqueue_pm_request(
    decision_point: Dict[str, Any],
    last_digest: Optional[Dict[str, Any]] = None,
    project_root: Optional[str] = None
) -> str:
    """
    Enqueue PM decision request for processing by pm_queue_processor.

    Args:
        decision_point: Detected decision point details
        last_digest: Last DIGEST from conversation
        project_root: Project root directory

    Returns:
        Path to queued request file
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    request_id = hashlib.sha256(timestamp.encode()).hexdigest()[:8]
    request_file = PM_RESUME_DIR.parent.parent / "pm-queue" / f"request-{timestamp}-{request_id}.json"

    # Ensure queue dir exists
    request_file.parent.mkdir(parents=True, exist_ok=True)

    request = {
        "request_id": request_id,
        "timestamp": timestamp,
        "decision_point": decision_point["full_message"],
        "digest": last_digest,
        "project_root": project_root or str(CLAUDE_DIR.parent)
    }

    with open(request_file, "w", encoding="utf-8") as f:
        json.dump(request, f, indent=2)

    return str(request_file)


def main(
    last_message: str,
    last_digest: Optional[Dict[str, Any]] = None,
    debug_log: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main PM decision hook entry point.

    Args:
        last_message: Last message from agent (may contain decision point)
        last_digest: Last DIGEST from conversation
        debug_log: Path to debug log file

    Returns:
        Result dict with decision details
    """
    log_file = open(debug_log, "a") if debug_log else None

    def log(msg: str):
        if log_file:
            log_file.write(f"{msg}\n")
        print(msg)

    # Feature flag check: ENABLE_PM_AUTONOMOUS
    # If false (default), PM only triggers when manually called (pm_answer_now.sh)
    # If true, PM triggers automatically on session end
    if os.environ.get("ENABLE_PM_AUTONOMOUS", "").lower() != "true":
        if log_file:
            log_file.close()
        return {
            "ok": True,
            "pm_autonomous_disabled": True,
            "message": "PM Agent available for manual triggering (use: bash ~/.claude/hooks/pm_answer_now.sh)"
        }

    # Detect decision point
    decision_point = detect_decision_point(last_message)
    if not decision_point:
        log("ℹ️  No decision point detected in last message")
        if log_file:
            log_file.close()
        return {"ok": True, "decision_needed": False}

    log("🤔 Decision point detected! Queuing for PM agent...")

    # Create dialogue-ready conversation instead of simple queue file
    try:
        # Import conversation manager
        sys.path.insert(0, os.path.dirname(__file__))
        from pm_conversation import create_conversation

        # Create conversation with proper structure
        project_root = os.getcwd()
        decision_text = decision_point.get("question", "") if isinstance(decision_point, dict) else str(decision_point)
        request_id = create_conversation(decision_text, project_root, last_digest)
        log(f"✅ PM conversation created: {request_id}")

        # Immediately trigger dialogue processor (multi-round capability)
        processor_path = os.path.join(os.path.dirname(__file__), "pm_dialogue_processor.py")
        subprocess.run(
            [sys.executable, processor_path],
            timeout=120,  # Longer timeout for multi-round dialogue
            capture_output=True,
            check=False
        )
        log(f"✅ PM dialogue processor triggered (multi-round strategic analysis)")

    except Exception as e:
        # Fallback to old single-round system
        log(f"⚠️  Dialogue mode failed, using fallback: {e}")
        request_file = enqueue_pm_request(decision_point, last_digest)
        log(f"✅ PM request queued (fallback): {os.path.basename(request_file)}")

        try:
            processor_path = os.path.join(os.path.dirname(__file__), "pm_queue_processor.py")
            subprocess.run(
                [sys.executable, processor_path],
                timeout=30,
                capture_output=True,
                check=False
            )
            log(f"✅ PM processor triggered (single-round fallback)")
        except Exception as inner_e:
            log(f"⚠️  Failed to trigger fallback processor: {inner_e}")

    if log_file:
        log_file.close()

    return {
        "ok": True,
        "decision_needed": True,
        "request_file": request_file
    }


if __name__ == "__main__":
    # Test mode
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_message = """Excellent progress! Phase 4 (Indexing) complete with 1170 LOC.
However, before continuing with Phase 5, I notice we haven't applied the database migration yet.

Since the database migration is blocking and we're at 59% context usage (118k/200k), should I:
1. Continue creating the migration files and Phase 5 (Search implementation)?
2. Pause here and you can review Phase 4 implementation first?

What would you prefer?"""

        result = main(
            last_message=test_message,
            last_digest={"agent": "IE", "phase": 4, "status": "complete"},
            debug_log=str(LOGS_DIR / "pm-decision-test.log")
        )
        print(json.dumps(result, indent=2))

    # Async mode (called from stop_digest.py)
    elif len(sys.argv) > 1 and sys.argv[1] == "--async":
        # Read context from stdin
        try:
            input_data = json.loads(sys.stdin.read())
            result = main(
                last_message=input_data.get("last_message", ""),
                last_digest=input_data.get("digest"),
                debug_log=input_data.get("debug_log")
            )
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}, indent=2), file=sys.stderr)
            sys.exit(1)

    else:
        print("Usage: pm_decision_hook.py --test | --async")
