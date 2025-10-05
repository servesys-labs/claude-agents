#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Context metrics tracker: measures context pollution, token efficiency, and attention budget.

Runs as part of PreCompact or Stop hooks to track context health over time.
"""
import sys, os, json, re
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
METRICS_FILE = PROJECT_ROOT / "logs" / "context-metrics.jsonl"
WSI_PATH = Path(os.path.expanduser("~/claude-hooks/wsi.json"))

def estimate_tokens(text):
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4

def load_wsi():
    try:
        with open(WSI_PATH) as f:
            return json.load(f)
    except:
        return {"items": []}

def calculate_metrics(payload):
    """Calculate context pollution and efficiency metrics."""
    metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "pollution_score": 0.0,
        "token_efficiency": 0.0,
        "wsi_utilization": 0.0,
        "context_reuse_rate": 0.0,
        "details": {}
    }

    # Try to extract conversation history
    messages = payload.get("messages", []) or payload.get("history", [])
    if not messages:
        # Try flat text fields
        text = (
            payload.get("assistant_text") or
            payload.get("final_message") or
            payload.get("content") or
            ""
        )
        if text:
            messages = [{"role": "assistant", "content": text}]

    if not messages:
        return metrics

    # Calculate total tokens
    total_tokens = sum(estimate_tokens(str(m.get("content", ""))) for m in messages)
    metrics["details"]["total_estimated_tokens"] = total_tokens

    # Extract unique file references
    all_text = " ".join(str(m.get("content", "")) for m in messages)
    file_refs = re.findall(r'[\w/.-]+\.(?:ts|tsx|js|jsx|py|md|json|prisma)', all_text)
    unique_files = set(file_refs)
    metrics["details"]["unique_file_refs"] = len(unique_files)
    metrics["details"]["total_file_mentions"] = len(file_refs)

    # Context reuse rate: how often files are mentioned multiple times
    if len(file_refs) > 0:
        metrics["context_reuse_rate"] = len(file_refs) / len(unique_files) if unique_files else 0

    # WSI utilization
    wsi = load_wsi()
    wsi_items = wsi.get("items", [])
    wsi_paths = {item.get("path") for item in wsi_items if item.get("path")}
    metrics["details"]["wsi_size"] = len(wsi_items)
    metrics["wsi_utilization"] = len(wsi_items) / 10.0  # Cap is 10

    # How many WSI files are actually referenced in conversation?
    wsi_refs_in_conv = len(wsi_paths & unique_files)
    metrics["details"]["wsi_refs_in_conversation"] = wsi_refs_in_conv

    # Pollution score: ratio of unreferenced tokens to total
    # Lower is better (more focused context)
    # Heuristic: if WSI has files not mentioned recently, that's pollution
    if len(wsi_items) > 0:
        pollution_files = len(wsi_paths) - wsi_refs_in_conv
        metrics["pollution_score"] = pollution_files / len(wsi_items)

    # Token efficiency: unique_files / total_tokens * 1000
    # Higher is better (more distinct files with fewer tokens)
    if total_tokens > 0:
        metrics["token_efficiency"] = (len(unique_files) / total_tokens) * 1000

    # Check for repeated tool calls (sign of inefficiency)
    tool_calls = re.findall(r'<invoke name="(\w+)">', all_text)
    unique_tools = set(tool_calls)
    metrics["details"]["total_tool_calls"] = len(tool_calls)
    metrics["details"]["unique_tools"] = len(unique_tools)

    # Attention budget: how many distinct "topics" (file paths + tools)
    attention_items = len(unique_files) + len(unique_tools)
    metrics["details"]["attention_items"] = attention_items

    # Warning if attention budget is high
    if attention_items > 20:
        metrics["details"]["warning"] = f"High attention budget ({attention_items} items)"

    return metrics

def save_metrics(metrics):
    """Append metrics to JSONL log."""
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(METRICS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(metrics, ensure_ascii=False) + "\n")

def print_summary(metrics):
    """Print human-readable summary to stderr."""
    print("\n📊 Context Health Metrics:", file=sys.stderr)
    print(f"  Pollution Score: {metrics['pollution_score']:.2f} (lower is better)", file=sys.stderr)
    print(f"  Token Efficiency: {metrics['token_efficiency']:.2f} (higher is better)", file=sys.stderr)
    print(f"  WSI Utilization: {metrics['wsi_utilization']*100:.0f}% ({metrics['details']['wsi_size']}/10 files)", file=sys.stderr)
    print(f"  Context Reuse: {metrics['context_reuse_rate']:.2f}x", file=sys.stderr)
    print(f"  Attention Items: {metrics['details'].get('attention_items', 0)}", file=sys.stderr)

    if "warning" in metrics["details"]:
        print(f"  ⚠️  {metrics['details']['warning']}", file=sys.stderr)

    print("", file=sys.stderr)

def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except:
        payload = {}

    metrics = calculate_metrics(payload)
    save_metrics(metrics)
    print_summary(metrics)

    sys.exit(0)

if __name__ == "__main__":
    main()
