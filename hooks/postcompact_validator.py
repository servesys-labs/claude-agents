#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PostCompact hook: Validate that compaction summary preserved critical context.

Exit code semantics:
- 0: success (summary quality verified)
- 1: warning (potential issues, non-blocking)
- 2: block (critical data loss detected)
"""
import sys
import json
import re
from pathlib import Path

# Critical elements that should be preserved
REQUIRED_ELEMENTS = [
    "decisions",
    "files",
    "next steps",
    "active",
]

CRITICAL_PATTERNS = [
    r"DIGEST",  # Subagent digest blocks
    r"TODO|FIXME|HACK",  # Action items
    r"BREAKING|CRITICAL|URGENT",  # Important markers
    r"file://|lib/|app/|components/",  # File references
    r"@\w+/",  # Package references
]


def load_compaction_data():
    """Load compaction input from stdin."""
    try:
        raw = sys.stdin.read()
        return json.loads(raw)
    except Exception:
        return None


def analyze_summary_quality(summary: str) -> dict:
    """
    Analyze compaction summary for quality and completeness.

    Returns:
        dict with score (0-100), issues (list), and warnings (list)
    """
    score = 100
    issues = []
    warnings = []

    if not summary or len(summary) < 100:
        issues.append("Summary too short (<100 chars) - likely incomplete")
        score -= 50
        return {"score": score, "issues": issues, "warnings": warnings}

    # Check for required elements
    summary_lower = summary.lower()
    missing_elements = []
    for element in REQUIRED_ELEMENTS:
        if element not in summary_lower:
            missing_elements.append(element)
            score -= 10

    if missing_elements:
        warnings.append(f"Missing recommended elements: {', '.join(missing_elements)}")

    # Check for critical patterns
    found_patterns = []
    for pattern in CRITICAL_PATTERNS:
        if re.search(pattern, summary, re.IGNORECASE):
            found_patterns.append(pattern)

    if len(found_patterns) < 2:
        warnings.append(f"Few critical patterns found ({len(found_patterns)}/7) - may have lost important context")
        score -= 15

    # Check summary length (should be substantial but not excessive)
    summary_length = len(summary)
    if summary_length < 500:
        warnings.append("Summary quite brief - verify all key decisions captured")
        score -= 10
    elif summary_length > 5000:
        warnings.append("Summary very long - may not have compacted effectively")
        score -= 5

    # Check for code snippets preservation
    code_blocks = len(re.findall(r"```[\w]*\n", summary))
    if code_blocks == 0:
        warnings.append("No code blocks found - verify code examples weren't needed")

    # Check for file references
    file_refs = len(re.findall(r'[`"][\w/.-]+\.(ts|tsx|js|jsx|py|md)[`"]', summary))
    if file_refs < 3:
        warnings.append(f"Few file references ({file_refs}) - may have lost file context")
        score -= 10

    # Check for structured sections
    sections = len(re.findall(r'^#{1,3}\s+\w+', summary, re.MULTILINE))
    if sections < 2:
        warnings.append("Few structured sections - summary may lack organization")
        score -= 5

    return {
        "score": max(0, score),
        "issues": issues,
        "warnings": warnings,
        "stats": {
            "length": summary_length,
            "code_blocks": code_blocks,
            "file_refs": file_refs,
            "sections": sections,
            "patterns_found": len(found_patterns)
        }
    }


def check_digest_preservation(summary: str) -> list:
    """Check if DIGEST blocks were preserved."""
    digest_blocks = re.findall(r'```json DIGEST\n(.*?)\n```', summary, re.DOTALL)
    digest_count = len(digest_blocks)

    issues = []
    if digest_count == 0:
        issues.append("No DIGEST blocks found - subagent outputs may be lost")

    return issues


def main():
    data = load_compaction_data()

    if not data:
        # No data to validate, skip
        sys.exit(0)

    # Extract summary from compaction data
    summary = data.get("summary", "") or data.get("compacted_summary", "")

    if not summary:
        print("\n⚠️  POSTCOMPACT WARNING: No summary found in compaction data", file=sys.stderr)
        sys.exit(1)

    # Analyze summary quality
    analysis = analyze_summary_quality(summary)
    digest_issues = check_digest_preservation(summary)

    # Combine all issues
    all_issues = analysis["issues"] + digest_issues
    all_warnings = analysis["warnings"]

    # Determine exit status
    if all_issues:
        print("\n" + "=" * 60, file=sys.stderr)
        print("🔴 POSTCOMPACT CRITICAL ISSUES", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        for issue in all_issues:
            print(f"  • {issue}", file=sys.stderr)
        print("", file=sys.stderr)
        print("⚠️  Summary quality severely compromised - consider manual review", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("", file=sys.stderr)
        sys.exit(2)  # Block

    if all_warnings or analysis["score"] < 70:
        print("\n" + "=" * 60, file=sys.stderr)
        print(f"⚠️  POSTCOMPACT QUALITY CHECK (Score: {analysis['score']}/100)", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

        if all_warnings:
            print("\nWarnings:", file=sys.stderr)
            for warning in all_warnings:
                print(f"  • {warning}", file=sys.stderr)

        print("\nSummary Stats:", file=sys.stderr)
        stats = analysis["stats"]
        print(f"  • Length: {stats['length']} chars", file=sys.stderr)
        print(f"  • Code blocks: {stats['code_blocks']}", file=sys.stderr)
        print(f"  • File references: {stats['file_refs']}", file=sys.stderr)
        print(f"  • Sections: {stats['sections']}", file=sys.stderr)
        print(f"  • Critical patterns: {stats['patterns_found']}/7", file=sys.stderr)

        if analysis["score"] < 70:
            print("\n💡 Recommendation: Review compaction summary before continuing", file=sys.stderr)
            print("   Summary may be missing important context", file=sys.stderr)

        print("=" * 60, file=sys.stderr)
        print("", file=sys.stderr)
        sys.exit(1)  # Warning

    # All good
    sys.exit(0)


if __name__ == "__main__":
    main()
