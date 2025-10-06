#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for PM Multi-Round Dialogue System

Simulates IPSA scenario:
"Which approach would you like to take for Phase 1?
A. Full GCP infrastructure setup
B. Local development environment first
C. Continue with detailed planning
D. Something else?"

Expected PM behavior:
1. Read AGENTS.md to understand project vision
2. Check package.json for dependencies
3. Get git status to see current state
4. Grep for existing Docker/GCP config
5. Make informed decision based on gathered context
"""

import os
import sys
import json
from pathlib import Path

# Add hooks directory to path
sys.path.insert(0, str(Path(__file__).parent))

from pm_conversation import create_conversation, load_conversation
from pm_dialogue_processor import process_dialogue_request


def create_test_scenario():
    """Create a test decision point like IPSA would ask."""

    # Simulate IPSA's question
    decision_point = """Which approach would you like to take for Phase 1 infrastructure setup?

A. Full GCP infrastructure setup (requires credentials and billing)
   - Cloud SQL for PostgreSQL
   - Cloud Storage for assets
   - Cloud Run for services
   - Full production-ready deployment

B. Local development environment first (Docker Compose + local PostgreSQL)
   - Quick iteration cycle
   - No cloud costs during development
   - Migrate to GCP in Phase 3

C. Continue with detailed planning and architecture refinement
   - Define all requirements first
   - Create detailed diagrams
   - Review alternatives

D. Something else?

Please provide your strategic recommendation."""

    # Simulate last DIGEST from IPSA
    last_digest = {
        "agent": "IPSA",
        "task_id": "infra-planning-phase1",
        "phase": "Phase 1 - Infrastructure Planning",
        "decisions": [
            "Need to choose infrastructure approach before implementation",
            "Options range from full cloud setup to local development",
            "User vision unclear - need PM strategic guidance"
        ],
        "files": [],
        "next": ["Waiting for PM decision on infrastructure approach"]
    }

    # Create conversation
    project_root = str(Path(__file__).parent.parent)
    request_id = create_conversation(decision_point, project_root, last_digest)

    print(f"✅ Test conversation created: {request_id}")
    print(f"📂 Location: .claude/pm-queue/{request_id}/")
    print()

    return request_id


def run_test_dialogue(request_id: str):
    """Run the dialogue processor on test conversation."""

    print("="*60)
    print("PM DIALOGUE TEST - Multi-Round Strategic Decision")
    print("="*60)
    print()
    print("Scenario: IPSA asks about infrastructure approach (A/B/C/D)")
    print("Expected: PM reads AGENTS.md, checks git, greps for config, then decides")
    print()
    print("Starting dialogue processor...")
    print("="*60)
    print()

    # Check if OPENAI_API_KEY is set
    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ ERROR: OPENAI_API_KEY not set")
        print("   Please run: export OPENAI_API_KEY=sk-proj-...")
        return

    # Check if ENABLE_PM_AGENT is true
    if os.environ.get("ENABLE_PM_AGENT", "").lower() != "true":
        print("⚠️  WARNING: ENABLE_PM_AGENT not set to true")
        print("   PM Agent may not trigger automatically")
        print("   This test will still work though")
        print()

    # Process dialogue
    result = process_dialogue_request(request_id, max_rounds=10)

    print()
    print("="*60)
    print("RESULT")
    print("="*60)
    print()

    if result["ok"]:
        print(f"✅ Success!")
        print(f"   Decision ID: {result['decision_id']}")
        print(f"   Decision: {result['decision']}")
        print(f"   Rounds: {result.get('rounds', 0)}")
        print(f"   Resume: {result['resume_file']}")
        if result.get("escalate"):
            print(f"   ⚠️  ESCALATION REQUIRED")
        print()
        print(f"View full decision: cat {result['resume_file']}")
        print()
        print(f"View conversation history:")
        print(f"  cat .claude/pm-queue/processed/{request_id}/{request_id}/conversation.json")
    else:
        print(f"❌ Failed: {result.get('error', 'Unknown error')}")
        print(f"   Rounds completed: {result.get('rounds', 0)}")

    print()
    print("="*60)


def main():
    """Run test."""
    # Create test scenario
    request_id = create_test_scenario()

    # Ask user to proceed
    print("This will call OpenAI GPT-4o API (cost: ~$0.005-0.02)")
    print()
    response = input("Proceed with test? [y/N]: ")

    if response.lower() != "y":
        print("Test cancelled.")
        print(f"To run later: python {__file__} --run {request_id}")
        return

    # Run dialogue
    run_test_dialogue(request_id)


if __name__ == "__main__":
    # Allow running specific conversation
    if len(sys.argv) > 2 and sys.argv[1] == "--run":
        run_test_dialogue(sys.argv[2])
    else:
        main()
