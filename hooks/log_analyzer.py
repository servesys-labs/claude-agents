#!/usr/bin/env python3
"""
Log Analyzer Hook - Automatically extract error summaries from large diagnostic logs.

Triggered: When user message contains log-like content (stacktraces, build errors, etc.)
Purpose: Prevent context pollution by summarizing only relevant errors
Exit codes:
  0 = Allow (log is small or already summarized)
  1 = Modified (extracted error summary, show to user)
"""

import sys
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

# Thresholds
MIN_LOG_LINES = 15  # Only analyze if paste has 15+ lines
MAX_CONTEXT_LINES = 40  # If log > 40 lines, definitely summarize

# Persistent error tracking
ERROR_TRACKER_DIR = Path.home() / 'claude-hooks' / 'logs' / 'errors'
ERROR_TRACKER_FILE = ERROR_TRACKER_DIR / 'error_tracker.json'
ERROR_WINDOW_MINUTES = 60  # Reset counters after one hour
PERPLEXITY_THRESHOLD = 2   # After N occurrences, force Perplexity lookup

# Error patterns to detect
ERROR_PATTERNS = [
    (r'(?:Error|Exception|Fatal|Critical):\s*(.+)', 'error'),
    (r'^\s*at\s+(.+)\s+\((.+):(\d+):(\d+)\)', 'stacktrace'),
    (r'FAIL(?:ED)?.*?(?:test|spec).*', 'test_failure'),
    (r'(?:npm|yarn|pnpm)\s+ERR!\s*(.+)', 'package_error'),
    (r'(?:TS|Type)\s*Error:\s*(.+)', 'type_error'),
    (r'Module not found:\s*(.+)', 'missing_module'),
    (r'Cannot find (?:module|name):\s*(.+)', 'missing_symbol'),
    (r'Syntax(?:Error)?:\s*(.+)', 'syntax_error'),
    (r'ENOENT.*?[\'"]([^\'"]+)[\'"]', 'file_not_found'),
    (r'Exit code:?\s*(\d+)', 'exit_code'),
]

# Build tool signatures
BUILD_TOOLS = {
    'typescript': ['tsc', 'TS2', 'TypeScript'],
    'eslint': ['ESLint', 'eslint'],
    'jest': ['FAIL', 'Jest', 'Test Suites'],
    'vitest': ['FAIL', 'Vitest', '✗'],
    'webpack': ['webpack', 'Module build failed'],
    'vite': ['vite', '[vite]'],
    'npm': ['npm ERR!', 'npm error'],
    'prisma': ['Prisma', 'prisma'],
}

def detect_log_type(content: str) -> str | None:
    """Detect what kind of log this is."""
    content_lower = content.lower()

    for tool, signatures in BUILD_TOOLS.items():
        if any(sig.lower() in content_lower for sig in signatures):
            return tool

    return None

def extract_errors(content: str) -> list[dict]:
    """Extract structured error information."""
    errors = []
    lines = content.split('\n')

    for i, line in enumerate(lines):
        for pattern, error_type in ERROR_PATTERNS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                errors.append({
                    'type': error_type,
                    'line_num': i + 1,
                    'content': line.strip(),
                    'match': match.group(1) if match.groups() else match.group(0),
                })

    return errors

def extract_stacktrace_summary(content: str) -> list[str]:
    """Extract just the top 3 stack frames."""
    frames = []
    lines = content.split('\n')

    for line in lines:
        if re.match(r'^\s*at\s+', line):
            frames.append(line.strip())
            if len(frames) >= 3:
                break

    return frames

def summarize_typescript_errors(content: str) -> str:
    """Summarize TypeScript compiler errors."""
    errors = re.findall(r'(.+\.tsx?)\((\d+),(\d+)\):\s*error\s+(TS\d+):\s*(.+)', content)

    if not errors:
        return ""

    summary = ["**TypeScript Errors:**\n"]

    # Group by error code
    by_code: dict[str, list] = {}
    for file, line, col, code, msg in errors:
        if code not in by_code:
            by_code[code] = []
        by_code[code].append((file, line, msg))

    for code, occurrences in list(by_code.items())[:5]:  # Top 5 error types
        summary.append(f"- `{code}`: {occurrences[0][2]}")
        summary.append(f"  - {len(occurrences)} occurrence(s)")
        for file, line, _ in occurrences[:3]:  # Top 3 files
            summary.append(f"    - [{Path(file).name}:{line}]({file}#L{line})")

    return '\n'.join(summary)

def summarize_test_failures(content: str) -> str:
    """Summarize test failures."""
    # Find FAIL lines
    failures = re.findall(r'FAIL\s+(.+?)(?:\n|$)', content)

    if not failures:
        return ""

    summary = ["**Test Failures:**\n"]
    for failure in failures[:5]:  # Top 5 failures
        summary.append(f"- {failure}")

    # Extract assertion errors
    assertions = re.findall(r'(Expected|Received):\s*(.+)', content)
    if assertions:
        summary.append("\n**Assertion Details:**")
        for label, value in assertions[:3]:
            summary.append(f"- {label}: `{value}`")

    return '\n'.join(summary)

def create_error_summary(content: str) -> str:
    """Create a compact error summary from diagnostic log."""
    lines = content.split('\n')
    log_type = detect_log_type(content)

    summary = [
        "🔍 **Log Analysis Summary**",
        f"_(Auto-extracted from {len(lines)}-line diagnostic log)_\n",
    ]

    if log_type:
        summary.append(f"**Tool**: {log_type.title()}\n")

    # Try specialized summarizers first
    if log_type == 'typescript':
        ts_summary = summarize_typescript_errors(content)
        if ts_summary:
            summary.append(ts_summary)
            summary.append(f"\n_Full log archived to: `logs/diagnostics/{datetime.now().strftime('%Y%m%d-%H%M%S')}.log`_")
            return '\n'.join(summary)

    if log_type in ('jest', 'vitest'):
        test_summary = summarize_test_failures(content)
        if test_summary:
            summary.append(test_summary)
            summary.append(f"\n_Full log archived to: `logs/diagnostics/{datetime.now().strftime('%Y%m%d-%H%M%S')}.log`_")
            return '\n'.join(summary)

    # Generic error extraction
    errors = extract_errors(content)

    if not errors:
        return ""  # No errors detected, allow full paste

    # Group by error type
    by_type: dict[str, list] = {}
    for err in errors:
        err_type = err['type']
        if err_type not in by_type:
            by_type[err_type] = []
        by_type[err_type].append(err)

    summary.append(f"**Errors Found**: {len(errors)} total\n")

    for err_type, errs in list(by_type.items())[:5]:  # Top 5 error types
        summary.append(f"**{err_type.replace('_', ' ').title()}** ({len(errs)} occurrences):")
        for err in errs[:3]:  # Top 3 of each type
            summary.append(f"- L{err['line_num']}: `{err['match'][:80]}`")
        summary.append("")

    # Add stacktrace snippet if present
    stacktrace = extract_stacktrace_summary(content)
    if stacktrace:
        summary.append("**Stack Trace (top 3 frames):**")
        for frame in stacktrace:
            summary.append(f"- {frame}")
        summary.append("")

    summary.append(f"_Full log archived to: `logs/diagnostics/{datetime.now().strftime('%Y%m%d-%H%M%S')}.log`_")

    return '\n'.join(summary)

def archive_full_log(content: str) -> Path:
    """Archive the full log for later reference."""
    log_dir = Path.home() / 'claude-hooks' / 'logs' / 'diagnostics'
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    log_file = log_dir / f'{timestamp}.log'

    log_file.write_text(content)
    return log_file


def normalize_json_payload() -> dict:
    raw = sys.stdin.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("log_analyzer: invalid JSON payload", file=sys.stderr)
        sys.exit(0)


def compute_error_signature(content: str) -> str:
    """Create a stable signature for repeated log detection."""
    # Focus on the first 2000 characters to ignore appended timestamps.
    trimmed = content.strip()[:2000]
    # Normalize whitespace to reduce noise.
    normalized = re.sub(r'\s+', ' ', trimmed)
    digest = hashlib.sha256(normalized.encode('utf-8', errors='ignore')).hexdigest()
    return digest


def load_error_tracker() -> dict:
    ERROR_TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    if ERROR_TRACKER_FILE.exists():
        try:
            with open(ERROR_TRACKER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def save_error_tracker(data: dict) -> None:
    ERROR_TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    with open(ERROR_TRACKER_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def register_error_occurrence(signature: str) -> int:
    """Increment error occurrence count and return the new total."""
    tracker = load_error_tracker()
    now = datetime.now().isoformat()
    window_start = datetime.now() - timedelta(minutes=ERROR_WINDOW_MINUTES)

    entry = tracker.get(signature, {"count": 0, "last_seen": now})

    # Reset count if outside time window
    try:
        last_seen_dt = datetime.fromisoformat(entry.get("last_seen", now))
    except ValueError:
        last_seen_dt = datetime.now()

    if last_seen_dt < window_start:
        entry["count"] = 0

    entry["count"] = int(entry.get("count", 0)) + 1
    entry["last_seen"] = now
    tracker[signature] = entry

    # Prune stale entries
    pruned = {
        sig: info
        for sig, info in tracker.items()
        if datetime.fromisoformat(info.get("last_seen", now)) >= window_start
    }

    save_error_tracker(pruned)
    return entry["count"]


def build_perplexity_query(summary: str, content: str) -> str:
    """Generate a concise search query for Perplexity."""
    if summary:
        base = summary.split('\n')[0]
    else:
        base = content.strip().split('\n')[0]
    return base[:180]

def detect_web_content(content: str) -> tuple[bool, str]:
    """Detect if content contains web URLs or looks like web fetch results."""
    web_indicators = [
        'http://', 'https://',
        'WebFetch', 'WebSearch',
        '<html', '<body', '<div',
        '<!DOCTYPE', '<head>',
        'fetch', 'GET ', 'POST ',
    ]

    # Check for URL patterns
    has_url = any(indicator in content for indicator in web_indicators[:2])
    has_web_tool = any(indicator in content for indicator in web_indicators[2:4])
    has_html = any(indicator in content.lower() for indicator in web_indicators[4:])

    if has_url or has_web_tool or has_html:
        # Extract URL if present
        import re
        url_match = re.search(r'https?://[^\s<>"]+', content)
        url = url_match.group(0) if url_match else ""
        return (True, url)

    return (False, "")

def should_invoke_web_summarizer(content: str, lines: list) -> tuple[bool, str]:
    """Determine if web content summarizer should be invoked."""
    is_web, url = detect_web_content(content)

    if not is_web:
        return (False, "")

    # Invoke summarizer if:
    # 1. Content is very long (>150 lines)
    # 2. Content has HTML tags and is >50 lines
    # 3. Content is from WebFetch/WebSearch and is >80 lines

    has_html = '<html' in content.lower() or '<body' in content.lower()
    is_web_tool = 'WebFetch' in content or 'WebSearch' in content

    should_summarize = (
        len(lines) > 150 or
        (has_html and len(lines) > 50) or
        (is_web_tool and len(lines) > 80)
    )

    return (should_summarize, url)

def main():
    # Read hook payload
    payload = normalize_json_payload()

    # Only process user messages
    if payload.get("role") != "user":
        sys.exit(0)

    raw_content = payload.get("content", "")

    # Claude user messages sometimes arrive as rich content blocks rather than a plain string.
    # Normalize to a single string so downstream log detection doesn't crash.
    content_parts: list[str] = []

    if isinstance(raw_content, str):
        content_parts.append(raw_content)
    elif isinstance(raw_content, list):
        for block in raw_content:
            if isinstance(block, str):
                content_parts.append(block)
            elif isinstance(block, dict):
                # Standard Claude blocks: {"type": "text", "text": "..."}
                text = block.get("text") or block.get("content")
                if isinstance(text, str):
                    content_parts.append(text)
            # Ignore other block types (attachments, images, etc.)
    elif isinstance(raw_content, dict):
        # Occasionally content is wrapped once more under {"type": "text", "text": "..."}
        text = raw_content.get("text") or raw_content.get("content")
        if isinstance(text, str):
            content_parts.append(text)

    content = "\n".join(part for part in content_parts if part)

    if not content.strip():
        sys.exit(0)

    # Check if this looks like a diagnostic log
    lines = content.split('\n')

    # Skip if too short
    if len(lines) < MIN_LOG_LINES:
        sys.exit(0)

    # Skip if user explicitly says "full log" or "complete output"
    if any(phrase in content.lower() for phrase in ['full log', 'complete output', 'entire log', 'show all']):
        sys.exit(0)

    # CHECK FOR BRAINSTORM REQUEST FIRST (highest priority)
    brainstorm_triggers = [
        'brainstorm', 'compare models', 'multi-agent',
        'get both perspectives', 'explore alternatives',
        '@gpt5', 'gpt-5', 'ask openai'
    ]

    is_brainstorm = any(trigger in content.lower() for trigger in brainstorm_triggers)

    # Also check if current context suggests high-level planning
    planning_keywords = [
        'architecture', 'design', 'approach', 'strategy',
        'should i', 'how to', 'what are the', 'trade-offs',
        'pros and cons', 'alternatives', 'options'
    ]

    is_planning = any(keyword in content.lower() for keyword in planning_keywords)

    if is_brainstorm and is_planning:
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("🧠 MULTI-MODEL BRAINSTORMING OPPORTUNITY", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("", file=sys.stderr)
        print("Detected brainstorming request for strategic planning.", file=sys.stderr)
        print("", file=sys.stderr)
        print("💡 RECOMMENDATION: Invoke multi-model-brainstormer agent", file=sys.stderr)
        print("", file=sys.stderr)
        print("This will:", file=sys.stderr)
        print("  1. Get Claude's initial perspective (this session)", file=sys.stderr)
        print("  2. Call GPT-5 for alternative viewpoints", file=sys.stderr)
        print("  3. Facilitate 2-4 rounds of dialogue", file=sys.stderr)
        print("  4. Synthesize insights from both models", file=sys.stderr)
        print("", file=sys.stderr)
        print("Command:", file=sys.stderr)
        print("  Task tool → subagent: 'multi-model-brainstormer'", file=sys.stderr)
        print("  Prompt: [your brainstorming question]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Cost: ~$0.08-0.14 per brainstorm session", file=sys.stderr)
        print("", file=sys.stderr)
        print("Best for: IPSA, RC, CN, API Architect, DB Modeler, UX Designer", file=sys.stderr)
        print("Skip for: IE, TA, PRV (execution tasks)", file=sys.stderr)
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("", file=sys.stderr)

        # Non-blocking suggestion
        sys.exit(1)

    # CHECK FOR LONG ERROR MESSAGES
    error_indicators = [
        'error', 'exception', 'traceback', 'stack trace', 'failed',
        'TypeError', 'ValueError', 'SyntaxError', 'Error:',
        'at line', 'at column', 'compilation failed', 'build failed'
    ]

    content_lower = content.lower()
    has_error = any(indicator in content_lower for indicator in error_indicators)

    # If it's a long error message (>50 lines with error indicators)
    if has_error and len(lines) > 50:
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("🚨 LONG ERROR MESSAGE DETECTED", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("", file=sys.stderr)
        print(f"Detected {len(lines)}-line error output.", file=sys.stderr)
        print("", file=sys.stderr)
        print("💡 RECOMMENDATION: Use error-summarizer pattern", file=sys.stderr)
        print("", file=sys.stderr)
        print("Main Agent should:", file=sys.stderr)
        print("  1. Save full error to a temporary file", file=sys.stderr)
        print("  2. Create a concise summary (key errors + line numbers)", file=sys.stderr)
        print("  3. Keep reference to full error for deep investigation", file=sys.stderr)
        print("", file=sys.stderr)
        print("Or invoke a specialized agent:", file=sys.stderr)
        print("  Task tool → subagent: 'implementation-engineer'", file=sys.stderr)
        print("  Prompt: 'Fix these errors: [error summary]'", file=sys.stderr)
        print("", file=sys.stderr)
        print("Benefits:", file=sys.stderr)
        print("  • Saves ~70% context tokens", file=sys.stderr)
        print("  • Focuses on actionable errors", file=sys.stderr)
        print("  • Preserves full trace for debugging", file=sys.stderr)
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("", file=sys.stderr)

        # Non-blocking suggestion
        sys.exit(1)

    # CHECK FOR WEB CONTENT
    should_summarize_web, url = should_invoke_web_summarizer(content, lines)
    if should_summarize_web:
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("🌐 WEB CONTENT DETECTED", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("", file=sys.stderr)
        print(f"Detected {len(lines)}-line web content.", file=sys.stderr)
        if url:
            print(f"URL: {url}", file=sys.stderr)
        print("", file=sys.stderr)
        print("💡 RECOMMENDATION: Invoke web-content-summarizer agent", file=sys.stderr)
        print("", file=sys.stderr)
        print("Command:", file=sys.stderr)
        print(f"  Task tool → subagent: 'web-content-summarizer'", file=sys.stderr)
        print(f"  Prompt: 'Summarize this web content: {url}'", file=sys.stderr)
        print("", file=sys.stderr)
        print("Benefits:", file=sys.stderr)
        print("  • ~80-90% token reduction", file=sys.stderr)
        print("  • Extract key code examples and concepts", file=sys.stderr)
        print("  • Remove marketing fluff and navigation", file=sys.stderr)
        print("  • Preserve links to deep-dive sections", file=sys.stderr)
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("", file=sys.stderr)

        # Non-blocking suggestion
        sys.exit(1)

    # Detect if this is a diagnostic paste (has error patterns or build tool output)
    log_type = detect_log_type(content)
    errors = extract_errors(content)

    # Summarize if:
    # 1. Log is huge (>100 lines) regardless of content, OR
    # 2. Log has errors and is moderately large (>40 lines), OR
    # 3. Log has 5+ errors even if small
    should_summarize = (
        len(lines) > 100 or
        ((log_type or errors) and len(lines) > MAX_CONTEXT_LINES) or
        len(errors) >= 5
    )

    if should_summarize:
        summary = create_error_summary(content)

        if summary:
            # Archive full log
            log_file = archive_full_log(content)

            # Track repeated occurrences and determine required action
            signature = compute_error_signature(content)
            occurrence = register_error_occurrence(signature)

            # Output summary to stderr (will be shown to user)
            print("", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print("📊 AUTOMATIC LOG ANALYSIS", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print("", file=sys.stderr)
            print(f"Detected {len(lines)}-line diagnostic log.", file=sys.stderr)
            print(f"Extracted error summary to save context tokens.", file=sys.stderr)
            print("", file=sys.stderr)
            print(summary, file=sys.stderr)
            print("", file=sys.stderr)
            print(f"💾 Full log saved to: {log_file}", file=sys.stderr)
            print("", file=sys.stderr)

            if occurrence >= PERPLEXITY_THRESHOLD:
                query = build_perplexity_query(summary, content)
                print("🚨 Repeated failure detected ({} occurrences within {} minutes).".format(
                    occurrence, ERROR_WINDOW_MINUTES
                ), file=sys.stderr)
                print("", file=sys.stderr)
                print("➡️  Invoke Perplexity for fresh context:", file=sys.stderr)
                print("    Task tool → subagent: 'perplexity-research'", file=sys.stderr)
                print(f"    Prompt: \"Investigate this error: {query}\"", file=sys.stderr)
                print("", file=sys.stderr)
                print("This action is required before retrying the same fix.", file=sys.stderr)
                print("", file=sys.stderr)
                print("=" * 60, file=sys.stderr)
                print("", file=sys.stderr)

                # Hard block so Claude must follow instructions
                sys.exit(2)

            print("To include full log anyway, start message with: 'full log:'", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print("", file=sys.stderr)

            # Exit with 1 to show the summary (non-blocking warning)
            sys.exit(1)

    # Allow full paste
    sys.exit(0)

if __name__ == "__main__":
    main()
