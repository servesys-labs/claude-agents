#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Dialogue Processor - Multi-round strategic decision system

Enables PM Agent to have back-and-forth conversations with tools/context:
1. Receive initial decision point
2. Ask clarifying questions
3. Execute tools (read files, grep, git status, etc.)
4. Gather sufficient context
5. Make informed strategic decision

Uses GPT-4o for strategic steering (not mini - this requires deep reasoning).

Flow:
1. Load conversation state
2. Build messages array with all rounds
3. Call GPT-4o with tool schema
4. If PM requests tools → execute and continue dialogue
5. If PM makes final decision → save and create resume instructions
6. Max 10 rounds to prevent infinite loops
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import hashlib

# Import conversation manager
try:
    from pm_conversation import (
        PMConversation,
        create_conversation,
        load_conversation,
        list_active_conversations
    )
except ImportError:
    # If running from different directory
    sys.path.insert(0, str(Path(__file__).parent))
    from pm_conversation import (
        PMConversation,
        create_conversation,
        load_conversation,
        list_active_conversations
    )

# Paths
CLAUDE_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())) / ".claude"
LOGS_DIR = CLAUDE_DIR / "logs"
PM_QUEUE_DIR = CLAUDE_DIR / "pm-queue"
PM_PROCESSED_DIR = PM_QUEUE_DIR / "processed"
PM_FAILED_DIR = PM_QUEUE_DIR / "failed"
AGENTS_MD = CLAUDE_DIR.parent / "AGENTS.md"
PM_DECISIONS_LOG = LOGS_DIR / "pm-decisions.json"
PM_RESUME_DIR = LOGS_DIR / "pm-resume"

# Ensure directories
LOGS_DIR.mkdir(parents=True, exist_ok=True)
PM_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
PM_FAILED_DIR.mkdir(parents=True, exist_ok=True)
PM_RESUME_DIR.mkdir(parents=True, exist_ok=True)

# Tool definitions for GPT-4o function calling
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file in the project",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to file from project root"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search codebase for pattern using grep",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (regex supported)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Path to search in (default: '.')",
                        "default": "."
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (default: '.')",
                        "default": "."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_git_status",
            "description": "Get current git status",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_git_log",
            "description": "Get recent git commits",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of commits to show (default: 10)",
                        "default": 10
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "make_decision",
            "description": "Make final strategic decision after gathering sufficient context",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "description": "Short decision ID (e.g., 'local_dev_first', 'gcp_infra_setup')"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Why this decision aligns with project goals"
                    },
                    "actions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Concrete steps for agent to execute"
                    },
                    "risks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Potential risks"
                    },
                    "mitigation": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Risk mitigation strategies"
                    },
                    "escalate_to_user": {
                        "type": "boolean",
                        "description": "Whether user input required",
                        "default": False
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional context for agent"
                    }
                },
                "required": ["decision", "reasoning", "actions"]
            }
        }
    }
]


def load_agents_md() -> str:
    """Load AGENTS.md for PM context."""
    if not AGENTS_MD.exists():
        return "# AGENTS.md not found\n\nNo project context available."
    return AGENTS_MD.read_text(encoding="utf-8")


def load_past_decisions(limit: int = 5) -> List[Dict[str, Any]]:
    """Load last N PM decisions (fewer for dialogue mode)."""
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


def call_gpt4o_dialogue(
    conversation: PMConversation,
    agents_md: str,
    past_decisions: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Call GPT-4o for multi-round dialogue with tool support.

    Returns:
    - {"type": "tool_calls", "calls": [...]} if PM requests tools
    - {"type": "decision", "decision": {...}} if PM makes final decision
    - None on error
    """
    try:
        import openai
    except ImportError:
        print("Error: openai package not installed. Run: pip install openai", file=sys.stderr)
        return None

    # Get API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set", file=sys.stderr)
        return None

    # Build system message
    system_message = f"""You are the GPT-4o Product Manager for this AI orchestration framework.

An agent has encountered a decision point. You can ask clarifying questions and gather context before making a strategic decision.

## Project Context (from AGENTS.md):
{agents_md[:3000]}  # Limit to 3k chars to save tokens

## Past Decisions (for learning):
{json.dumps(past_decisions, indent=2)[:2000]}  # Limit past decisions

## Your Capabilities:
1. **read_file**: Read any file in the project
2. **grep**: Search codebase for patterns
3. **list_files**: List directory contents
4. **get_git_status**: Check current git state
5. **get_git_log**: Review recent commits
6. **make_decision**: Make final strategic decision (call this when you have enough context)

## Your Process:
1. Understand the decision point
2. Ask clarifying questions via tools (read files, grep code, check git status)
3. Gather sufficient context (2-5 tool calls usually enough)
4. Make final decision using make_decision tool

## Decision Principles (from AGENTS.md):
- NO-REGRESSION: Never remove features
- ADDITIVE-FIRST: Add missing functionality
- PROD-READY BIAS: All code must be shippable
- VIBE CODING: User sets vision, you ensure execution aligns

Be strategic, decisive, and thorough. Gather context first, then decide.
"""

    # Build conversation history
    messages = [{"role": "system", "content": system_message}]
    messages.extend(conversation.get_conversation_history())

    try:
        client = openai.OpenAI(api_key=api_key)

        # Always use GPT-4o for dialogue (strategic reasoning requires it)
        # Can override with PM_DIALOGUE_MODEL env var
        model = os.environ.get("PM_DIALOGUE_MODEL", "gpt-4o")

        response = client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore
            tools=TOOL_DEFINITIONS,  # type: ignore
            tool_choice="auto",  # Let GPT-4o decide when to call tools vs make decision
            temperature=0.4,  # Slightly higher for creative problem-solving
            max_tokens=2000
        )

        choice = response.choices[0]

        # Check if PM made decision (via make_decision tool call)
        # MUST check this FIRST before processing other tool calls
        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            for tool_call in choice.message.tool_calls:
                if tool_call.function.name == "make_decision":
                    decision = json.loads(tool_call.function.arguments)
                    decision["_meta"] = {
                        "model": response.model,
                        "tokens": {
                            "prompt": response.usage.prompt_tokens if response.usage else 0,
                            "completion": response.usage.completion_tokens if response.usage else 0,
                            "total": response.usage.total_tokens if response.usage else 0
                        }
                    }
                    return {"type": "decision", "decision": decision}

        # Check if PM wants to call other tools (read_file, grep, etc.)
        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            tool_calls = []
            for tool_call in choice.message.tool_calls:
                tool_calls.append({
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "arguments": json.loads(tool_call.function.arguments)
                })

            return {
                "type": "tool_calls",
                "calls": tool_calls,
                "message": choice.message.content,
                "_meta": {
                    "model": response.model,
                    "tokens": {
                        "prompt": response.usage.prompt_tokens if response.usage else 0,
                        "completion": response.usage.completion_tokens if response.usage else 0,
                        "total": response.usage.total_tokens if response.usage else 0
                    }
                }
            }

        # If normal message (no tools), add to conversation and continue
        if choice.message.content:
            return {
                "type": "message",
                "content": choice.message.content,
                "_meta": {
                    "model": response.model,
                    "tokens": {
                        "prompt": response.usage.prompt_tokens if response.usage else 0,
                        "completion": response.usage.completion_tokens if response.usage else 0,
                        "total": response.usage.total_tokens if response.usage else 0
                    }
                }
            }

        return None

    except Exception as e:
        print(f"Error calling GPT-4o: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def create_resume_instructions(
    decision: Dict[str, Any],
    decision_point: str,
    project_root: str,
    conversation_rounds: int
) -> str:
    """Create resume instructions after PM decision."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    resume_file = PM_RESUME_DIR / f"resume-{timestamp}.md"

    content = f"""# PM Decision: Resume Instructions (Multi-round Dialogue)

**Decision ID:** {decision.get('id', 'unknown')}
**Timestamp:** {decision.get('timestamp', 'unknown')}
**Decision:** {decision.get('decision', 'unknown')}
**Project:** {project_root}
**Dialogue Rounds:** {conversation_rounds}

## Original Decision Point
```
{decision_point[:500]}
```

## PM Strategic Decision (After {conversation_rounds} rounds of context gathering)

**Reasoning:** {decision.get('reasoning', 'No reasoning provided')}

**Escalate to User:** {decision.get('escalate_to_user', False)}

## Actions to Execute
{chr(10).join(f"{i+1}. {action}" for i, action in enumerate(decision.get('actions', [])))}

## Risks & Mitigation
**Risks:**
{chr(10).join(f"- {risk}" for risk in decision.get('risks', []))}

**Mitigation:**
{chr(10).join(f"- {mitigation}" for mitigation in decision.get('mitigation', []))}

## Additional Notes
{decision.get('notes', 'No additional notes')}

---

## To Resume Development

1. Start new Claude session in: `{project_root}`
2. Reference this file or paste actions above
3. Main Agent should delegate to appropriate subagent (likely IPSA or IE)
4. Execute autonomously following PM decision

---

**Token Usage:** {decision.get('_meta', {}).get('tokens', {}).get('total', 'unknown')} tokens
**Model:** {decision.get('_meta', {}).get('model', 'unknown')}
**Dialogue Mode:** Multi-round strategic analysis (vibe coding enabled)
"""

    resume_file.write_text(content, encoding="utf-8")
    return str(resume_file)


def process_dialogue_request(request_id: str, max_rounds: int = 10) -> Dict[str, Any]:
    """
    Process a PM request using multi-round dialogue.

    Continues until:
    - PM makes final decision via make_decision tool
    - Max rounds reached (default: 10)
    - Error occurs
    """
    try:
        # Load conversation
        conversation = load_conversation(request_id)

        # Load context
        agents_md = load_agents_md()
        past_decisions = load_past_decisions(limit=5)

        round_num = len(conversation.rounds)

        print(f"📋 Processing conversation: {request_id} (Round {round_num + 1})")

        # Multi-round dialogue loop
        while round_num < max_rounds:
            # Call GPT-4o
            response = call_gpt4o_dialogue(conversation, agents_md, past_decisions)

            if not response:
                return {
                    "ok": False,
                    "error": "GPT-4o API call failed",
                    "request_id": request_id,
                    "rounds": round_num
                }

            # Handle response type
            if response["type"] == "decision":
                # Final decision made!
                decision = response["decision"]

                print(f"✅ PM Decision: {decision.get('decision', 'unknown')}")

                # Save decision
                save_decision(decision)

                # Create resume instructions
                resume_file = create_resume_instructions(
                    decision,
                    conversation.request_data.get("decision_point", ""),
                    conversation.request_data.get("project_root", ""),
                    round_num + 1
                )

                # Archive conversation
                archive_dir = PM_PROCESSED_DIR / request_id
                archive_dir.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.move(str(conversation.conversation_dir), str(archive_dir))

                return {
                    "ok": True,
                    "decision_id": decision.get("id"),
                    "decision": decision.get("decision"),
                    "resume_file": resume_file,
                    "escalate": decision.get("escalate_to_user", False),
                    "rounds": round_num + 1,
                    "request_id": request_id
                }

            elif response["type"] == "tool_calls":
                # Execute tools
                print(f"🔧 PM requested {len(response['calls'])} tools:")
                tools_used = []

                for tool_call in response["calls"]:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["arguments"]

                    print(f"   - {tool_name}({json.dumps(tool_args)})")

                    # Execute tool
                    success, result = conversation.execute_tool(tool_name, tool_args)

                    tools_used.append({
                        "name": tool_name,
                        "arguments": tool_args,
                        "success": success,
                        "result_preview": result[:200] + "..." if len(result) > 200 else result
                    })

                    # Add tool result to conversation
                    conversation.add_round("tool", f"Tool: {tool_name}\nResult:\n{result}")

                # Add PM message if any
                if response.get("message"):
                    conversation.add_round("pm", response["message"], tools_used)

                round_num += 1

            elif response["type"] == "message":
                # PM sent message (no tools, no decision) - add to conversation
                conversation.add_round("pm", response["content"])
                round_num += 1

            else:
                return {
                    "ok": False,
                    "error": f"Unknown response type: {response['type']}",
                    "request_id": request_id,
                    "rounds": round_num
                }

        # Max rounds reached without decision
        return {
            "ok": False,
            "error": f"Max rounds ({max_rounds}) reached without decision",
            "request_id": request_id,
            "rounds": round_num
        }

    except Exception as e:
        import traceback
        traceback.print_exc()

        # Archive to failed
        try:
            conversation = load_conversation(request_id)
            failed_dir = PM_FAILED_DIR / request_id
            failed_dir.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.move(str(conversation.conversation_dir), str(failed_dir))
        except Exception:
            pass

        return {
            "ok": False,
            "error": str(e),
            "request_id": request_id
        }


def main():
    """Main entry point - process all active conversations."""
    conversations = list_active_conversations()

    if not conversations:
        print(json.dumps({"ok": True, "processed": 0, "message": "No active conversations"}))
        return

    results = []
    for conv_id in conversations:
        print(f"\n{'='*60}")
        print(f"Processing: {conv_id}")
        print(f"{'='*60}\n")

        result = process_dialogue_request(conv_id, max_rounds=10)
        results.append(result)

        # Log result
        if result["ok"]:
            print(f"\n✅ Success: {result['decision_id']} - {result['decision']}")
            print(f"   Rounds: {result.get('rounds', 0)}")
            print(f"   Resume: {result['resume_file']}")
            if result.get("escalate"):
                print(f"   ⚠️  ESCALATION REQUIRED")
        else:
            print(f"\n❌ Failed: {result.get('error', 'Unknown error')}")
            print(f"   Rounds completed: {result.get('rounds', 0)}")

    # Summary
    succeeded = sum(1 for r in results if r["ok"])
    failed = len(results) - succeeded
    escalations = sum(1 for r in results if r.get("escalate"))

    summary = {
        "ok": True,
        "processed": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "escalations": escalations,
        "results": results
    }

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
