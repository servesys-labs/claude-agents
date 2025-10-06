#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Queue Processor - Processes PM decision requests using GPT-5

Runs as launchd agent every 5-10 minutes.
Picks up decision requests from .claude/pm-queue/, calls OpenAI API directly,
writes decision to pm-decisions.json and creates resume instructions.

Flow:
1. Scan .claude/pm-queue/ for *.json files
2. Load request (decision_point + context)
3. Call OpenAI API with AGENTS.md context
4. Parse decision JSON
5. Save to pm-decisions.json
6. Create resume instructions
7. Move request to processed/
"""

import os
import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Paths
CLAUDE_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())) / ".claude"
LOGS_DIR = CLAUDE_DIR / "logs"
PM_QUEUE_DIR = CLAUDE_DIR / "pm-queue"
PM_PROCESSED_DIR = PM_QUEUE_DIR / "processed"
PM_FAILED_DIR = PM_QUEUE_DIR / "failed"
AGENTS_MD = CLAUDE_DIR.parent / "AGENTS.md"
PM_DECISIONS_LOG = LOGS_DIR / "pm-decisions.json"
PM_RESUME_DIR = LOGS_DIR / "pm-resume"

# Ensure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)
PM_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
PM_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
PM_FAILED_DIR.mkdir(parents=True, exist_ok=True)
PM_RESUME_DIR.mkdir(parents=True, exist_ok=True)


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
        return decisions[-limit:]
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

    # Keep last 50 decisions
    decisions = decisions[-50:]

    with open(PM_DECISIONS_LOG, "w", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2)


def call_openai_api(
    decision_point: str,
    agents_md: str,
    past_decisions: List[Dict[str, Any]],
    last_digest: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Call OpenAI API directly (not via MCP) to get PM decision.

    Uses OpenAI Python SDK.
    """
    try:
        import openai
    except ImportError:
        print("Error: openai package not installed. Run: pip install openai", file=sys.stderr)
        return None

    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set", file=sys.stderr)
        return None

    # Build prompt
    prompt = f"""You are the GPT-5 Product Manager for this AI orchestration framework.

An agent has encountered a decision point and needs your guidance.

## Project Context (from AGENTS.md):
{agents_md}

## Past Decisions (for reference):
{json.dumps(past_decisions, indent=2)}

## Current State (Last DIGEST):
{json.dumps(last_digest, indent=2) if last_digest else "No DIGEST available"}

## Decision Point:
{decision_point}

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

    try:
        client = openai.OpenAI(api_key=api_key)

        # Model selection based on decision complexity
        # Default: gpt-4o-mini ($0.15/$0.30 per 1M tokens, ~$0.0011/decision)
        # Override with env var for complex decisions: PM_MODEL=o3 or PM_MODEL=gpt-4o
        model = os.environ.get("PM_MODEL", "gpt-4o-mini")

        response = client.chat.completions.create(
            model=model,  # gpt-4o-mini for 96% cost savings vs gpt-4o
            messages=[
                {"role": "system", "content": "You are a strategic product manager for an AI development framework. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )

        # Extract JSON from response
        text = response.choices[0].message.content
        if not text:
            return None

        # Handle markdown code blocks
        if "```json" in text:
            json_str = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            json_str = text.split("```")[1].split("```")[0].strip()
        else:
            json_str = text.strip()

        decision = json.loads(json_str)

        # Add token usage info
        if response.usage:
            decision["_meta"] = {
                "model": response.model,
                "tokens": {
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                }
            }
        else:
            decision["_meta"] = {"model": response.model, "tokens": {}}

        return decision

    except Exception as e:
        print(f"Error calling OpenAI API: {e}", file=sys.stderr)
        return None


def create_resume_instructions(decision: Dict[str, Any], decision_point: str, project_root: str) -> str:
    """Create resume instructions file for next Claude session."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    resume_file = PM_RESUME_DIR / f"resume-{timestamp}.md"

    content = f"""# PM Decision: Resume Instructions

**Decision ID:** {decision.get('id', 'unknown')}
**Timestamp:** {decision.get('timestamp', 'unknown')}
**Decision:** {decision.get('decision', 'unknown')}
**Project:** {project_root}

## Context
The previous agent session ended with this decision point:

```
{decision_point[:500]}
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

## To Resume Development

1. Start new Claude session in project: `{project_root}`
2. Reference this file or paste actions above
3. Agent should execute autonomously following PM decision

---

**Token Usage:** {decision.get('_meta', {}).get('tokens', {}).get('total', 'unknown')} tokens
**Model:** {decision.get('_meta', {}).get('model', 'unknown')}
"""

    resume_file.write_text(content, encoding="utf-8")
    return str(resume_file)


def process_request(request_file: Path) -> Dict[str, Any]:
    """Process a single PM decision request."""
    try:
        # Load request
        with open(request_file, "r", encoding="utf-8") as f:
            request = json.load(f)

        decision_point = request.get("decision_point", "")
        last_digest = request.get("digest")
        project_root = request.get("project_root", str(CLAUDE_DIR.parent))

        # Load context
        agents_md = load_agents_md()
        past_decisions = load_past_decisions(limit=10)

        # Call OpenAI
        decision = call_openai_api(decision_point, agents_md, past_decisions, last_digest)

        if not decision:
            return {"ok": False, "error": "OpenAI API call failed", "file": str(request_file)}

        # Save decision
        save_decision(decision)

        # Create resume instructions
        resume_file = create_resume_instructions(decision, decision_point, project_root)

        # Move request to processed
        processed_file = PM_PROCESSED_DIR / request_file.name
        request_file.rename(processed_file)

        return {
            "ok": True,
            "decision_id": decision.get("id"),
            "decision": decision.get("decision"),
            "resume_file": resume_file,
            "escalate": decision.get("escalate_to_user", False),
            "file": str(processed_file)
        }

    except Exception as e:
        # Move to failed
        failed_file = PM_FAILED_DIR / request_file.name
        request_file.rename(failed_file)
        return {"ok": False, "error": str(e), "file": str(failed_file)}


def main():
    """Main entry point."""
    # Scan queue
    queue_files = sorted(PM_QUEUE_DIR.glob("*.json"))

    if not queue_files:
        print(json.dumps({"ok": True, "processed": 0, "message": "No requests in queue"}))
        return

    results = []
    for request_file in queue_files:
        result = process_request(request_file)
        results.append(result)

        # Log each result
        if result["ok"]:
            print(f"✅ Processed: {result['decision_id']} - {result['decision']}")
            if result.get("escalate"):
                print(f"   ⚠️  ESCALATION REQUIRED - See: {result['resume_file']}")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")

    # Summary
    succeeded = sum(1 for r in results if r["ok"])
    failed = sum(1 for r in results if not r["ok"])
    escalations = sum(1 for r in results if r.get("escalate"))

    summary = {
        "ok": True,
        "processed": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "escalations": escalations,
        "results": results
    }

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
