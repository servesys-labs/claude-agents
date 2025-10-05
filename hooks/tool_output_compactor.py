#!/usr/bin/env python3
"""
Tool Output Compactor Hook - Compress verbose tool output.

Triggered: PostToolUse after Bash tool
Purpose: Prevent context pollution from verbose CLI tools (npm, git, docker, etc.)
Exit codes:
  0 = Allow (output is concise)
  1 = Modified (compacted output, show to user)
"""

import sys
import json
import re
from datetime import datetime
from pathlib import Path

# Thresholds
MAX_OUTPUT_LINES = 30  # If output >30 lines, try to compact
MAX_COMPACT_LINES = 15  # Target compact output length

# Tool-specific compaction rules
COMPACTION_RULES = {
    'npm': {
        'install': {
            'success_pattern': r'added (\d+) packages.*in ([\d.]+s)',
            'success_template': '✅ npm install: Added {packages} packages in {time}',
            'keep_warnings': True,
            'keep_errors': True,
        },
        'test': {
            'success_pattern': r'(\d+) passing',
            'failure_pattern': r'(\d+) failing',
            'success_template': '✅ Tests: {passing} passing',
            'failure_template': '❌ Tests: {passing} passing, {failing} failing',
            'keep_failures': True,
        },
        'run build': {
            'success_pattern': r'successfully compiled',
            'success_template': '✅ Build successful',
            'keep_errors': True,
        },
    },
    'git': {
        'status': {
            'pattern': r'^(On branch|Changes|Untracked)',
            'summary_lines': 5,
        },
        'diff': {
            'max_lines': 50,
            'show_summary': True,
        },
        'log': {
            'max_commits': 5,
        },
    },
    'docker': {
        'build': {
            'success_pattern': r'Successfully built (\w+)',
            'success_template': '✅ Docker build: Image {image_id}',
            'keep_errors': True,
        },
        'ps': {
            'max_containers': 10,
        },
    },
    'prisma': {
        'migrate': {
            'success_pattern': r'migration.*applied',
            'success_template': '✅ Prisma migration applied',
            'keep_warnings': True,
        },
        'generate': {
            'success_pattern': r'Generated Prisma Client',
            'success_template': '✅ Prisma Client generated',
        },
    },
    'python': {
        'pytest': {
            'success_pattern': r'(\d+) passed',
            'failure_pattern': r'(\d+) failed',
            'success_template': '✅ Tests: {passed} passed',
            'failure_template': '❌ Tests: {passed} passed, {failed} failed',
            'keep_failures': True,
        },
        'pip': {
            'success_pattern': r'Successfully installed (.+)',
            'success_template': '✅ pip install: {packages}',
            'keep_warnings': True,
        },
        'mypy': {
            'success_pattern': r'Success: no issues found',
            'success_template': '✅ mypy: No type errors',
            'keep_errors': True,
        },
        'ruff': {
            'success_pattern': r'All checks passed',
            'success_template': '✅ ruff: All checks passed',
            'keep_errors': True,
        },
    },
}

def detect_tool_command(command: str) -> tuple[str, str] | None:
    """Detect which tool and subcommand was run."""

    # npm commands
    if command.startswith('npm '):
        if 'install' in command or 'i ' in command:
            return ('npm', 'install')
        elif 'test' in command:
            return ('npm', 'test')
        elif 'run build' in command or 'build' in command:
            return ('npm', 'run build')

    # git commands
    elif command.startswith('git '):
        if 'status' in command:
            return ('git', 'status')
        elif 'diff' in command:
            return ('git', 'diff')
        elif 'log' in command:
            return ('git', 'log')

    # docker commands
    elif command.startswith('docker '):
        if 'build' in command:
            return ('docker', 'build')
        elif 'ps' in command:
            return ('docker', 'ps')

    # prisma commands
    elif 'prisma' in command:
        if 'migrate' in command:
            return ('prisma', 'migrate')
        elif 'generate' in command:
            return ('prisma', 'generate')

    # python commands
    elif command.startswith('pytest') or ' pytest' in command:
        return ('python', 'pytest')
    elif command.startswith('pip '):
        if 'install' in command:
            return ('python', 'pip')
    elif command.startswith('mypy') or ' mypy' in command:
        return ('python', 'mypy')
    elif command.startswith('ruff') or ' ruff' in command:
        return ('python', 'ruff')

    return None

def extract_errors_warnings(output: str) -> dict:
    """Extract error and warning lines from output."""
    lines = output.split('\n')

    errors = []
    warnings = []

    for i, line in enumerate(lines):
        line_lower = line.lower()

        if any(x in line_lower for x in ['error:', 'error ', 'err!', 'failed', 'failure']):
            # Include context (line before and after)
            start = max(0, i - 1)
            end = min(len(lines), i + 2)
            errors.extend(lines[start:end])

        elif any(x in line_lower for x in ['warn:', 'warning:', 'warn ']):
            warnings.append(line)

    return {
        'errors': list(set(errors)),
        'warnings': list(set(warnings))
    }

def compact_npm_output(command: str, output: str, subcommand: str) -> str | None:
    """Compact npm command output."""
    rules = COMPACTION_RULES['npm'].get(subcommand, {})

    if not rules:
        return None

    lines = output.split('\n')
    exit_code = 0  # Assume success unless we detect failure

    # Check for errors
    issues = extract_errors_warnings(output)

    if issues['errors']:
        exit_code = 1

    # Build compact output
    compact = []

    # Try to match success pattern
    if exit_code == 0 and 'success_pattern' in rules:
        for line in lines:
            match = re.search(rules['success_pattern'], line, re.IGNORECASE)
            if match:
                # Fill template
                template = rules['success_template']
                if subcommand == 'install':
                    compact.append(template.format(packages=match.group(1), time=match.group(2)))
                elif subcommand == 'test':
                    compact.append(template.format(passing=match.group(1)))
                else:
                    compact.append(template)
                break

    # Add warnings if requested
    if rules.get('keep_warnings') and issues['warnings']:
        compact.append(f"\n⚠️  Warnings ({len(issues['warnings'])}):")
        for warning in issues['warnings'][:3]:
            compact.append(f"  {warning.strip()}")
        if len(issues['warnings']) > 3:
            compact.append(f"  ... {len(issues['warnings']) - 3} more warnings")

    # Add errors if present
    if issues['errors']:
        compact.append(f"\n❌ Errors ({len(issues['errors'])}):")
        for error in issues['errors'][:5]:
            compact.append(f"  {error.strip()}")
        if len(issues['errors']) > 5:
            compact.append(f"  ... {len(issues['errors']) - 5} more errors")

    if compact:
        return '\n'.join(compact)

    return None

def compact_git_status(output: str) -> str | None:
    """Compact git status output."""
    lines = output.split('\n')

    if len(lines) <= 10:
        return None  # Already concise

    compact = []

    # Extract summary info
    branch_line = next((l for l in lines if l.startswith('On branch')), None)
    if branch_line:
        compact.append(branch_line)

    # Count changes
    modified = len([l for l in lines if l.strip().startswith('modified:')])
    untracked = len([l for l in lines if l.strip().startswith('??') or 'Untracked' in l])
    staged = len([l for l in lines if l.strip().startswith('new file:') or l.strip().startswith('deleted:')])

    if staged > 0:
        compact.append(f"Staged: {staged} files")
    if modified > 0:
        compact.append(f"Modified: {modified} files")
    if untracked > 0:
        compact.append(f"Untracked: {untracked} files")

    compact.append("\n💡 Run 'git status' for full list")

    return '\n'.join(compact)

def compact_docker_build(output: str) -> str | None:
    """Compact docker build output."""
    lines = output.split('\n')

    if len(lines) <= 20:
        return None

    # Look for success
    for line in lines:
        match = re.search(r'Successfully built (\w+)', line)
        if match:
            image_id = match.group(1)

            # Also check for tag
            tag_match = re.search(r'Successfully tagged (.+)', '\n'.join(lines))
            if tag_match:
                return f"✅ Docker build successful\nImage: {tag_match.group(1)}\nID: {image_id}"
            return f"✅ Docker build successful\nImage ID: {image_id}"

    # Check for errors
    issues = extract_errors_warnings(output)
    if issues['errors']:
        compact = ["❌ Docker build failed\n"]
        compact.extend(issues['errors'][:5])
        return '\n'.join(compact)

    return None

def should_compact(output: str, command: str) -> bool:
    """Determine if output should be compacted."""

    lines = output.split('\n')

    # Don't compact if already short
    if len(lines) <= MAX_OUTPUT_LINES:
        return False

    # Don't compact if it's interactive output
    if any(x in output.lower() for x in ['[y/n]', 'press enter', 'continue?']):
        return False

    # Compact if detected tool matches rules
    tool_info = detect_tool_command(command)
    if tool_info:
        return True

    # Compact if output is very long
    if len(lines) > 100:
        return True

    return False

def compact_output(command: str, output: str) -> str | None:
    """Compact tool output based on command."""

    tool_info = detect_tool_command(command)

    if not tool_info:
        # Generic compaction for unknown tools
        lines = output.split('\n')
        if len(lines) > 100:
            # Show first 10 and last 10 lines
            compact = lines[:10]
            compact.append(f"\n... ({len(lines) - 20} lines omitted) ...\n")
            compact.extend(lines[-10:])
            return '\n'.join(compact)
        return None

    tool, subcommand = tool_info

    # Tool-specific compaction
    if tool == 'npm':
        return compact_npm_output(command, output, subcommand)
    elif tool == 'git' and subcommand == 'status':
        return compact_git_status(output)
    elif tool == 'docker' and subcommand == 'build':
        return compact_docker_build(output)
    elif tool == 'python':
        return compact_python_output(command, output, subcommand)

    return None

def compact_python_output(command: str, output: str, subcommand: str) -> str | None:
    """Compact Python tool output."""
    rules = COMPACTION_RULES['python'].get(subcommand, {})

    if not rules:
        return None

    lines = output.split('\n')
    issues = extract_errors_warnings(output)
    compact = []

    # pytest
    if subcommand == 'pytest':
        passed = re.search(r'(\d+) passed', output)
        failed = re.search(r'(\d+) failed', output)

        if passed and not failed:
            compact.append(f"✅ pytest: {passed.group(1)} tests passed")
        elif failed:
            compact.append(f"❌ pytest: {passed.group(1) if passed else '0'} passed, {failed.group(1)} failed")
            # Show failed test names
            for line in lines:
                if 'FAILED' in line:
                    compact.append(f"  {line.strip()}")

    # pip install
    elif subcommand == 'pip':
        installed = re.search(r'Successfully installed (.+)', output)
        if installed:
            packages = installed.group(1)
            # Shorten long package lists
            if len(packages) > 100:
                packages = packages[:100] + "..."
            compact.append(f"✅ pip install: {packages}")

    # mypy/ruff
    elif subcommand in ('mypy', 'ruff'):
        if issues['errors']:
            compact.append(f"❌ {subcommand} errors ({len(issues['errors'])}):")
            for error in issues['errors'][:5]:
                compact.append(f"  {error.strip()}")
        else:
            compact.append(f"✅ {subcommand}: No issues found")

    if issues['warnings']:
        compact.append(f"\n⚠️  Warnings ({len(issues['warnings'])}):")
        for warning in issues['warnings'][:3]:
            compact.append(f"  {warning.strip()}")

    if compact:
        return '\n'.join(compact)

    return None

def archive_full_output(command: str, output: str) -> Path:
    """Archive full tool output."""
    log_dir = Path.home() / 'claude-hooks' / 'logs' / 'tool-output'
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    # Sanitize command for filename
    safe_cmd = re.sub(r'[^\w\-]', '_', command[:50])
    log_file = log_dir / f'{timestamp}_{safe_cmd}.txt'

    content = f"Command: {command}\n"
    content += f"Timestamp: {datetime.now().isoformat()}\n"
    content += "=" * 60 + "\n\n"
    content += output

    log_file.write_text(content)
    return log_file

def main():
    # Read hook payload
    payload = json.loads(sys.stdin.read())

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input", {})
    tool_result = payload.get("tool_result", "")

    # Only process Bash tool
    if tool_name != "Bash":
        sys.exit(0)

    command = tool_input.get("command", "")

    # Check if we should compact
    if not should_compact(tool_result, command):
        sys.exit(0)

    # Try to compact
    compacted = compact_output(command, tool_result)

    if not compacted:
        sys.exit(0)  # No compaction possible

    # Archive full output
    log_file = archive_full_output(command, tool_result)

    # Output compacted version to stderr
    print("", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("📦 TOOL OUTPUT COMPACTED", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("", file=sys.stderr)
    print(compacted, file=sys.stderr)
    print("", file=sys.stderr)
    print(f"💾 Full output: {log_file}", file=sys.stderr)
    print("", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("", file=sys.stderr)

    # Exit with 1 to show compacted version
    sys.exit(1)

if __name__ == "__main__":
    main()
