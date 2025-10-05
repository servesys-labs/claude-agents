#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Context budget visualization: show token usage breakdown at strategic points.

Can be invoked standalone or integrated into PreToolUse for budget warnings.
"""
import sys, os, json
from pathlib import Path

WSI_PATH = Path(os.path.expanduser("~/claude-hooks/wsi.json"))
NOTES_PATH = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())) / "NOTES.md"

def estimate_tokens(text):
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4

def load_wsi():
    try:
        with open(WSI_PATH) as f:
            return json.load(f)
    except:
        return {"items": []}

def estimate_file_tokens(path):
    """Estimate tokens for a file."""
    try:
        p = Path(path)
        if not p.exists():
            return 0
        text = p.read_text(encoding="utf-8", errors="ignore")
        return estimate_tokens(text)
    except:
        return 0

def visualize_budget():
    """Show context budget breakdown."""
    wsi = load_wsi()
    items = wsi.get("items", [])

    # Estimate WSI tokens
    wsi_tokens = 0
    for item in items:
        path = item.get("path", "")
        if path:
            wsi_tokens += estimate_file_tokens(path)

    # Estimate NOTES.md tokens
    notes_tokens = 0
    if NOTES_PATH.exists():
        notes_tokens = estimate_file_tokens(NOTES_PATH)

    # Rough estimate of framework overhead
    # Global CLAUDE.md: ~2900 tokens (now cached)
    # Project CLAUDE.md: ~600 tokens (now cached)
    # With caching, these cost ~0 tokens after first use
    framework_overhead = 0  # Assuming caching is effective

    # Total budget (200k for Sonnet 3.5, but practical limit is lower)
    total_budget = 200000
    practical_limit = 150000  # Leave room for responses
    current_usage = wsi_tokens + notes_tokens + framework_overhead

    # Available for actual work
    available = practical_limit - current_usage

    # Utilization percentage
    utilization = (current_usage / practical_limit) * 100

    print("\n" + "="*60, file=sys.stderr)
    print("📊 CONTEXT BUDGET BREAKDOWN", file=sys.stderr)
    print("="*60, file=sys.stderr)

    print(f"\n💾 Working Set Index (WSI):", file=sys.stderr)
    print(f"   Files: {len(items)}/10", file=sys.stderr)
    print(f"   Tokens: ~{wsi_tokens:,}", file=sys.stderr)

    print(f"\n📝 NOTES.md:", file=sys.stderr)
    print(f"   Tokens: ~{notes_tokens:,}", file=sys.stderr)

    print(f"\n📦 Framework Overhead (cached):", file=sys.stderr)
    print(f"   Tokens: ~{framework_overhead:,} (0 after cache)", file=sys.stderr)

    print(f"\n📊 Total Usage:", file=sys.stderr)
    print(f"   Current: ~{current_usage:,} tokens", file=sys.stderr)
    print(f"   Available: ~{available:,} tokens", file=sys.stderr)
    print(f"   Utilization: {utilization:.1f}%", file=sys.stderr)

    # Progress bar
    bar_width = 40
    filled = int(bar_width * utilization / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    print(f"\n   [{bar}] {utilization:.1f}%", file=sys.stderr)

    # Warnings
    if utilization > 80:
        print(f"\n   ⚠️  HIGH: Context >80% - consider PreCompact", file=sys.stderr)
    elif utilization > 60:
        print(f"\n   ⚡ MODERATE: Context >60% - watch carefully", file=sys.stderr)
    else:
        print(f"\n   ✅ HEALTHY: Plenty of budget remaining", file=sys.stderr)

    # Recommendations
    if wsi_tokens > 50000:
        print(f"\n   💡 Tip: WSI is large. Use Grep/Read for targeted retrieval.", file=sys.stderr)

    if notes_tokens > 20000:
        print(f"\n   💡 Tip: NOTES.md is large. Check rotation (should be <20 digests).", file=sys.stderr)

    print("\n" + "="*60 + "\n", file=sys.stderr)

    return {
        "wsi_tokens": wsi_tokens,
        "notes_tokens": notes_tokens,
        "framework_tokens": framework_overhead,
        "current_usage": current_usage,
        "available": available,
        "utilization_pct": utilization
    }

def main():
    # Can be called standalone or with payload on stdin
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""

    budget = visualize_budget()

    # Exit with warning code if utilization is high
    if budget["utilization_pct"] > 80:
        sys.exit(1)  # Warning (shows to user, continues)

    sys.exit(0)

if __name__ == "__main__":
    main()
