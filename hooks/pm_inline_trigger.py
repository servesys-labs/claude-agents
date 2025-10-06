#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Inline Trigger - Immediate intervention on agent questions

This script can be called manually or via hook to trigger PM immediately
when an agent asks a question, without waiting for session end.

Usage:
1. Enable: export ENABLE_PM_INLINE=true
2. When agent asks question, run: python pm_inline_trigger.py "question text"
3. PM will analyze and create decision in ~/.claude/logs/pm-resume/

Or call programmatically:
    from pm_inline_trigger import trigger_inline_decision
    trigger_inline_decision("Should I use Docker or GCP?")
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add hooks directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from pm_conversation import create_conversation
    from pm_dialogue_processor import process_dialogue_request
except ImportError as e:
    print(f"Error: Required modules not found: {e}", file=sys.stderr)
    print("Make sure pm_conversation.py and pm_dialogue_processor.py exist", file=sys.stderr)
    sys.exit(1)


def trigger_inline_decision(question: str, project_root: Optional[str] = None) -> dict:
    """
    Trigger PM decision immediately (inline, not waiting for session end).

    Args:
        question: The decision point / question from agent
        project_root: Project directory (default: current directory)

    Returns:
        dict: Result from PM dialogue processor
    """
    if not project_root:
        project_root = os.getcwd()

    print(f"\n{'='*60}")
    print(f"🤖 PM INLINE INTERVENTION")
    print(f"{'='*60}\n")

    # Create conversation
    print(f"📋 Creating conversation for question:")
    print(f"   {question[:150]}{'...' if len(question) > 150 else ''}\n")

    request_id = create_conversation(question, project_root, digest=None)
    print(f"✅ Conversation created: {request_id}\n")

    # Process immediately
    print(f"🧠 PM analyzing and gathering context...")
    print(f"   (This may take 10-60 seconds)\n")

    result = process_dialogue_request(request_id, max_rounds=10)

    print(f"\n{'='*60}")
    print(f"📊 RESULT")
    print(f"{'='*60}\n")

    if result["ok"]:
        print(f"✅ PM Decision Complete!")
        print(f"   Decision ID: {result['decision_id']}")
        print(f"   Decision: {result['decision']}")
        print(f"   Rounds: {result.get('rounds', 0)}")
        print(f"   Resume file: {result['resume_file']}\n")

        # Show decision summary
        resume_file = Path(result['resume_file'])
        if resume_file.exists():
            content = resume_file.read_text(encoding="utf-8")

            # Extract key sections
            print(f"{'─'*60}")
            for line in content.splitlines():
                if line.startswith("**Decision:**"):
                    print(f"   {line}")
                elif line.startswith("**Reasoning:**"):
                    print(f"   {line[:100]}{'...' if len(line) > 100 else ''}")
                elif line.startswith("## Actions to Execute"):
                    # Print next 5 lines
                    idx = content.splitlines().index(line)
                    print(f"\n   Actions:")
                    for action_line in content.splitlines()[idx+1:idx+6]:
                        if action_line.strip():
                            print(f"     {action_line}")
                    break
            print(f"{'─'*60}\n")

        if result.get("escalate"):
            print(f"⚠️  ESCALATION: User input required\n")

        print(f"View full decision:")
        print(f"  cat {result['resume_file']}\n")

    else:
        print(f"❌ PM Decision Failed")
        print(f"   Error: {result.get('error', 'Unknown error')}")
        print(f"   Rounds completed: {result.get('rounds', 0)}\n")

    print(f"{'='*60}\n")

    return result


def main():
    """CLI entry point."""
    # Check environment
    if os.environ.get("ENABLE_PM_AGENT", "").lower() != "true":
        print("Error: ENABLE_PM_AGENT not set to true", file=sys.stderr)
        print("Run: export ENABLE_PM_AGENT=true", file=sys.stderr)
        sys.exit(1)

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set", file=sys.stderr)
        print("Run: export OPENAI_API_KEY=sk-proj-...", file=sys.stderr)
        sys.exit(1)

    # Get question from args or stdin
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        print("Enter question for PM (end with Ctrl+D):")
        question = sys.stdin.read().strip()

    if not question:
        print("Error: No question provided", file=sys.stderr)
        sys.exit(1)

    # Trigger decision
    result = trigger_inline_decision(question)

    # Exit with appropriate code
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
