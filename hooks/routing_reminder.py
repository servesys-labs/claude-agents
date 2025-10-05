#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Routing Reminder hook: Display routing decision requirement.

Shows reminder to Main Agent about routing decision protocol.
Non-blocking, informational only.

Exit code: Always 0 (success, informational)
"""
import sys
import json
import random

REMINDERS = [
    "💡 Remember: Start response with **Routing Decision**: [subagent] or [direct: reason]",
    "🎯 Routing protocol: State which subagent you're using or why you're working directly",
    "🚨 Don't forget: **Routing Decision**: [agent-name] or [direct: exception-type]",
    "📋 Protocol reminder: Declare your routing decision before proceeding",
]


def main():
    # Only show reminder occasionally (20% of the time) to avoid spam
    if random.random() > 0.2:
        sys.exit(0)

    # Show random reminder
    reminder = random.choice(REMINDERS)
    print(f"\n{reminder}\n", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
