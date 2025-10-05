#!/usr/bin/env python3
"""
Grep Summarizer Hook - Automatically summarize large grep results.

Triggered: PostToolUse after Grep tool
Purpose: Prevent context pollution from grep returning 100+ files
Exit codes:
  0 = Allow (grep results are reasonable)
  1 = Modified (summarized results, show to user)
"""

import sys
import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Thresholds
MAX_FILES_SHOWN = 20  # If grep returns >20 files, summarize
TOP_N_PER_DIR = 3  # Show top N files per directory in summary
MAX_CONTEXT_LINES = 50  # Max lines to show in summary

def parse_grep_output(output: str, mode: str) -> dict:
    """Parse grep output based on output_mode."""

    if mode == "files_with_matches":
        # Just file paths
        files = [line.strip() for line in output.strip().split('\n') if line.strip()]
        return {
            "mode": "files",
            "files": files,
            "total": len(files)
        }

    elif mode == "content":
        # File:line:content or File:line_number:content
        matches = []
        current_file = None

        for line in output.strip().split('\n'):
            if not line.strip():
                continue

            # Match format: path/to/file.ts:123:content
            match = re.match(r'^([^:]+):(\d+):(.+)$', line)
            if match:
                file_path, line_num, content = match.groups()
                matches.append({
                    "file": file_path,
                    "line": int(line_num),
                    "content": content.strip()
                })

        # Group by file
        by_file = defaultdict(list)
        for m in matches:
            by_file[m["file"]].append(m)

        return {
            "mode": "content",
            "matches": matches,
            "by_file": dict(by_file),
            "total_files": len(by_file),
            "total_matches": len(matches)
        }

    elif mode == "count":
        # File:count
        counts = {}
        for line in output.strip().split('\n'):
            if ':' in line:
                file_path, count = line.rsplit(':', 1)
                counts[file_path.strip()] = int(count.strip())

        return {
            "mode": "count",
            "counts": counts,
            "total_files": len(counts),
            "total_matches": sum(counts.values())
        }

    return {"mode": "unknown", "total": 0}

def group_by_directory(files: list[str]) -> dict[str, list[str]]:
    """Group files by parent directory."""
    by_dir = defaultdict(list)

    for file_path in files:
        path = Path(file_path)
        parent = str(path.parent) if str(path.parent) != '.' else '(root)'
        by_dir[parent].append(file_path)

    return dict(by_dir)

def score_file_relevance(file_path: str, wsi_paths: set[str]) -> int:
    """Score file relevance (0-100)."""
    score = 50  # baseline

    path = Path(file_path)

    # Boost if in same directory as WSI item
    for wsi_path in wsi_paths:
        if path.parent == Path(wsi_path).parent:
            score += 30
            break

    # Boost recently modified files (check if in git recent commits)
    # For now, just boost non-node_modules
    if 'node_modules' not in file_path:
        score += 20

    # Penalize deep paths
    depth = len(path.parts)
    if depth > 5:
        score -= min(20, (depth - 5) * 5)

    return max(0, min(100, score))

def create_grep_summary(parsed: dict, pattern: str, wsi_paths: set[str]) -> str:
    """Create a compact summary of grep results."""

    mode = parsed.get("mode")

    if mode == "files":
        files = parsed["files"]
        total = parsed["total"]

        # Group by directory
        by_dir = group_by_directory(files)

        # Score and sort
        scored_files = [(score_file_relevance(f, wsi_paths), f) for f in files]
        scored_files.sort(reverse=True, key=lambda x: x[0])

        summary = [
            "🔍 **Grep Results Summary**",
            f"_(Auto-summarized: {total} files matched)_\n",
            f"**Pattern**: `{pattern}`",
            f"**Total Matches**: {total} files\n",
        ]

        # Show top files by relevance
        summary.append("**Top Matches by Relevance:**")
        for score, file_path in scored_files[:10]:
            summary.append(f"- [{Path(file_path).name}]({file_path}) _(relevance: {score})_")

        summary.append("")

        # Show grouped by directory
        summary.append("**Grouped by Directory:**")
        for dir_path, dir_files in sorted(by_dir.items(), key=lambda x: -len(x[1]))[:5]:
            summary.append(f"- `{dir_path}/`: {len(dir_files)} matches")
            for f in dir_files[:TOP_N_PER_DIR]:
                summary.append(f"  - [{Path(f).name}]({f})")
            if len(dir_files) > TOP_N_PER_DIR:
                summary.append(f"  - _{len(dir_files) - TOP_N_PER_DIR} more..._")

        if len(by_dir) > 5:
            summary.append(f"- _{len(by_dir) - 5} more directories..._")

        summary.append(f"\n_Full results archived to: `logs/grep-results/{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt`_")

        return '\n'.join(summary)

    elif mode == "content":
        total_files = parsed["total_files"]
        total_matches = parsed["total_matches"]
        by_file = parsed["by_file"]

        summary = [
            "🔍 **Grep Results Summary**",
            f"_(Auto-summarized: {total_matches} matches across {total_files} files)_\n",
            f"**Pattern**: `{pattern}`",
            f"**Total Matches**: {total_matches} in {total_files} files\n",
        ]

        # Show top files by match count
        sorted_files = sorted(by_file.items(), key=lambda x: -len(x[1]))

        summary.append("**Top Files:**")
        for file_path, matches in sorted_files[:5]:
            summary.append(f"\n**[{Path(file_path).name}]({file_path})** ({len(matches)} matches):")
            for match in matches[:3]:
                summary.append(f"- L{match['line']}: `{match['content'][:80]}`")
            if len(matches) > 3:
                summary.append(f"  _{len(matches) - 3} more matches..._")

        if len(sorted_files) > 5:
            summary.append(f"\n_{len(sorted_files) - 5} more files..._")

        summary.append(f"\n_Full results archived to: `logs/grep-results/{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt`_")

        return '\n'.join(summary)

    elif mode == "count":
        counts = parsed["counts"]
        total_files = parsed["total_files"]
        total_matches = parsed["total_matches"]

        summary = [
            "🔍 **Grep Results Summary**",
            f"_(Auto-summarized: {total_matches} matches across {total_files} files)_\n",
            f"**Pattern**: `{pattern}`\n",
        ]

        # Sort by count
        sorted_counts = sorted(counts.items(), key=lambda x: -x[1])

        summary.append("**Match Counts:**")
        for file_path, count in sorted_counts[:10]:
            summary.append(f"- [{Path(file_path).name}]({file_path}): {count} matches")

        if len(sorted_counts) > 10:
            summary.append(f"- _{len(sorted_counts) - 10} more files..._")

        summary.append(f"\n_Full results archived to: `logs/grep-results/{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt`_")

        return '\n'.join(summary)

    return None

def archive_grep_results(output: str, pattern: str) -> Path:
    """Archive full grep results."""
    log_dir = Path.home() / 'claude-hooks' / 'logs' / 'grep-results'
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    log_file = log_dir / f'{timestamp}.txt'

    content = f"Pattern: {pattern}\n"
    content += f"Timestamp: {datetime.now().isoformat()}\n"
    content += "=" * 60 + "\n\n"
    content += output

    log_file.write_text(content)
    return log_file

def load_wsi_paths() -> set[str]:
    """Load WSI file paths for relevance scoring."""
    wsi_file = Path.home() / 'claude-hooks' / 'logs' / 'wsi.json'

    if not wsi_file.exists():
        return set()

    try:
        wsi_data = json.loads(wsi_file.read_text())
        return set(item.get("path", "") for item in wsi_data.get("items", []))
    except:
        return set()

def main():
    # Read hook payload
    payload = json.loads(sys.stdin.read())

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input", {})
    tool_result = payload.get("tool_result", "")

    # Only process Grep tool
    if tool_name != "Grep":
        sys.exit(0)

    # Extract pattern and mode
    pattern = tool_input.get("pattern", "")
    output_mode = tool_input.get("output_mode", "files_with_matches")

    # Parse grep output
    parsed = parse_grep_output(tool_result, output_mode)

    # Determine if we should summarize
    should_summarize = False

    if parsed["mode"] == "files" and parsed["total"] > MAX_FILES_SHOWN:
        should_summarize = True
    elif parsed["mode"] == "content" and parsed["total_files"] > MAX_FILES_SHOWN:
        should_summarize = True
    elif parsed["mode"] == "count" and parsed["total_files"] > MAX_FILES_SHOWN:
        should_summarize = True

    if not should_summarize:
        sys.exit(0)  # Results are reasonable, allow full output

    # Load WSI for relevance scoring
    wsi_paths = load_wsi_paths()

    # Create summary
    summary = create_grep_summary(parsed, pattern, wsi_paths)

    if not summary:
        sys.exit(0)

    # Archive full results
    log_file = archive_grep_results(tool_result, pattern)

    # Output summary to stderr
    print("", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("📊 GREP RESULTS SUMMARIZED", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("", file=sys.stderr)
    print(summary, file=sys.stderr)
    print("", file=sys.stderr)
    print(f"💾 Full results: {log_file}", file=sys.stderr)
    print("", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("", file=sys.stderr)

    # Exit with 1 to show summary (non-blocking)
    sys.exit(1)

if __name__ == "__main__":
    main()
