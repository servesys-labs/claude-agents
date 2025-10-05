#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Error Recovery hook: Automatic remediation when hooks fail.

Triggered when any hook returns non-zero exit code.
Attempts common fixes and provides remediation guidance.

Exit code semantics:
- 0: error recovered successfully
- 1: partial recovery (warning)
- 2: unrecoverable error (escalate to user)
"""
import sys
import json
import os
import subprocess
import re
from pathlib import Path
from datetime import datetime

ERROR_LOG_DIR = Path.home() / "claude-hooks" / "logs" / "errors"
RECOVERY_STRATEGIES = {
    "permission_denied": {
        "pattern": r"permission denied|not permitted|eacces",
        "fix": "chmod_fix",
        "description": "Fix file permissions"
    },
    "command_not_found": {
        "pattern": r"command not found|no such file or directory.*bin/",
        "fix": "install_suggestion",
        "description": "Suggest tool installation"
    },
    "module_not_found": {
        "pattern": r"modulenotfounderror|no module named|cannot find module",
        "fix": "install_dependencies",
        "description": "Install missing Python/Node modules"
    },
    "timeout": {
        "pattern": r"timeout|timed out|deadline exceeded",
        "fix": "increase_timeout",
        "description": "Increase timeout threshold"
    },
    "network_error": {
        "pattern": r"connection refused|network unreachable|dns lookup failed",
        "fix": "network_check",
        "description": "Check network connectivity"
    },
    "disk_space": {
        "pattern": r"no space left|disk quota exceeded",
        "fix": "cleanup_suggestion",
        "description": "Free up disk space"
    },
    "syntax_error": {
        "pattern": r"syntaxerror|unexpected token|invalid syntax",
        "fix": "revert_recent_changes",
        "description": "Syntax error in recent changes"
    }
}


def ensure_error_log_dir():
    """Ensure error log directory exists."""
    ERROR_LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_error(hook_name: str, error_data: dict):
    """Log error to file for debugging."""
    ensure_error_log_dir()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = ERROR_LOG_DIR / f"{timestamp}_{hook_name}.json"

    with open(log_file, "w") as f:
        json.dump(error_data, f, indent=2)

    return log_file


def detect_error_type(error_output: str) -> tuple[str, dict] | tuple[None, None]:
    """
    Detect error type from output.

    Returns:
        (error_type, strategy) or (None, None) if unknown
    """
    error_lower = error_output.lower()

    for error_type, strategy in RECOVERY_STRATEGIES.items():
        if re.search(strategy["pattern"], error_lower):
            return error_type, strategy

    return None, None


def chmod_fix(hook_path: str, error_output: str) -> dict:
    """Fix permission errors by making file executable."""
    try:
        # Extract file path from error
        match = re.search(r"([/\w.-]+\.(?:py|sh))", error_output)
        if not match:
            return {"success": False, "reason": "Could not extract file path"}

        file_path = match.group(1)
        file_path = os.path.expanduser(file_path)

        if not os.path.exists(file_path):
            return {"success": False, "reason": f"File not found: {file_path}"}

        # Make executable
        subprocess.run(["chmod", "+x", file_path], check=True, timeout=5)

        return {
            "success": True,
            "action": f"Made {file_path} executable",
            "retry": True
        }
    except Exception as e:
        return {"success": False, "reason": str(e)}


def install_suggestion(hook_path: str, error_output: str) -> dict:
    """Suggest installation for missing commands."""
    # Extract command name
    match = re.search(r"command not found.*?([a-z0-9_-]+)", error_output, re.IGNORECASE)
    if not match:
        return {"success": False, "reason": "Could not extract command name"}

    command = match.group(1)

    suggestions = {
        "npm": "Install Node.js: https://nodejs.org/",
        "python3": "Install Python 3: https://python.org/",
        "git": "Install Git: https://git-scm.com/",
        "mypy": "Install mypy: pip install mypy",
        "pyright": "Install pyright: pip install pyright",
        "ruff": "Install ruff: pip install ruff",
        "tsc": "Install TypeScript: npm install -g typescript"
    }

    suggestion = suggestions.get(command, f"Install {command} manually")

    return {
        "success": False,
        "action": f"Install missing command: {command}",
        "suggestion": suggestion,
        "retry": False
    }


def install_dependencies(hook_path: str, error_output: str) -> dict:
    """Install missing Python modules."""
    # Extract module name
    match = re.search(r"no module named ['\"]([\w.]+)['\"]", error_output, re.IGNORECASE)
    if not match:
        return {"success": False, "reason": "Could not extract module name"}

    module = match.group(1)

    # Attempt to install
    try:
        subprocess.run(
            ["pip3", "install", module],
            check=True,
            capture_output=True,
            timeout=60
        )

        return {
            "success": True,
            "action": f"Installed missing module: {module}",
            "retry": True
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "action": f"Failed to install {module}",
            "suggestion": f"Manually install: pip3 install {module}",
            "retry": False
        }
    except Exception as e:
        return {"success": False, "reason": str(e)}


def increase_timeout(hook_path: str, error_output: str) -> dict:
    """Suggest increasing timeout in hook configuration."""
    return {
        "success": False,
        "action": "Timeout detected",
        "suggestion": "Increase timeout in hook script or disable slow checks",
        "retry": False
    }


def network_check(hook_path: str, error_output: str) -> dict:
    """Check network connectivity."""
    try:
        # Simple ping test
        result = subprocess.run(
            ["ping", "-c", "1", "8.8.8.8"],
            capture_output=True,
            timeout=5
        )

        if result.returncode == 0:
            return {
                "success": False,
                "action": "Network appears functional",
                "suggestion": "Check specific endpoint availability or firewall rules",
                "retry": False
            }
        else:
            return {
                "success": False,
                "action": "Network unreachable",
                "suggestion": "Check network connection, VPN, or proxy settings",
                "retry": False
            }
    except Exception:
        return {
            "success": False,
            "suggestion": "Unable to verify network - check connection manually",
            "retry": False
        }


def cleanup_suggestion(hook_path: str, error_output: str) -> dict:
    """Suggest disk cleanup."""
    try:
        # Check disk usage
        result = subprocess.run(
            ["df", "-h", "."],
            capture_output=True,
            text=True,
            timeout=5
        )

        return {
            "success": False,
            "action": "Disk space low",
            "suggestion": "Free up space:\n  • rm -rf node_modules && npm install\n  • Clean Docker: docker system prune -a\n  • Clear temp files: rm -rf /tmp/*",
            "disk_info": result.stdout.split('\n')[1] if result.stdout else "Unknown",
            "retry": False
        }
    except Exception:
        return {
            "success": False,
            "suggestion": "Check disk space manually: df -h",
            "retry": False
        }


def revert_recent_changes(hook_path: str, error_output: str) -> dict:
    """Suggest reverting recent changes."""
    return {
        "success": False,
        "action": "Syntax error detected",
        "suggestion": "Recent file changes contain syntax errors. Options:\n  1. Undo last edit\n  2. Restore from checkpoint: python ~/claude-hooks/checkpoint_manager.py list\n  3. Review syntax in your editor",
        "retry": False
    }


def apply_recovery(error_type: str, strategy: dict, hook_path: str, error_output: str) -> dict:
    """Apply recovery strategy."""
    fix_function_name = strategy["fix"]
    fix_function = globals().get(fix_function_name)

    if not fix_function:
        return {"success": False, "reason": f"Recovery function {fix_function_name} not found"}

    return fix_function(hook_path, error_output)


def main():
    raw = sys.stdin.read()

    try:
        data = json.loads(raw)
    except Exception:
        # Invalid JSON, cannot recover
        sys.exit(2)

    hook_name = data.get("hook_name", "unknown")
    hook_path = data.get("hook_path", "")
    exit_code = data.get("exit_code", 0)
    error_output = data.get("error_output", "") or data.get("stderr", "")

    # Log error
    log_file = log_error(hook_name, data)

    # Detect error type
    error_type, strategy = detect_error_type(error_output)

    if not error_type:
        # Unknown error type, cannot auto-recover
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"❌ HOOK ERROR: {hook_name}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"Exit code: {exit_code}", file=sys.stderr)
        print("", file=sys.stderr)
        if error_output:
            print("Error output:", file=sys.stderr)
            print(error_output[:500], file=sys.stderr)
        print("", file=sys.stderr)
        print(f"📝 Error logged to: {log_file}", file=sys.stderr)
        print("💡 Review log for details", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("", file=sys.stderr)
        sys.exit(2)

    # Attempt recovery
    print("", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"🔧 AUTO-RECOVERY: {strategy['description']}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Hook: {hook_name}", file=sys.stderr)
    print(f"Error type: {error_type}", file=sys.stderr)
    print("", file=sys.stderr)

    recovery_result = apply_recovery(error_type, strategy, hook_path, error_output)

    if recovery_result.get("success"):
        print(f"✅ {recovery_result['action']}", file=sys.stderr)
        if recovery_result.get("retry"):
            print("", file=sys.stderr)
            print("💡 Retry recommended - hook should succeed now", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("", file=sys.stderr)
        sys.exit(0)  # Success
    else:
        print(f"❌ {recovery_result.get('action', 'Recovery failed')}", file=sys.stderr)
        if recovery_result.get("suggestion"):
            print("", file=sys.stderr)
            print("💡 Manual fix required:", file=sys.stderr)
            print(recovery_result["suggestion"], file=sys.stderr)
        print("", file=sys.stderr)
        print(f"📝 Error logged to: {log_file}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("", file=sys.stderr)
        sys.exit(1 if recovery_result.get("retry") else 2)


if __name__ == "__main__":
    main()
