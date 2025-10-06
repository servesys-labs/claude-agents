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
# Fixpack/MCP integration toggles
ENABLE_FIXPACK_SUGGEST = os.environ.get("ENABLE_FIXPACK_SUGGEST", "true").lower() == "true"
FIXPACK_MAX_SUGGESTIONS = int(os.environ.get("FIXPACK_MAX_SUGGESTIONS", "2"))
FIXPACK_SUGGEST_TIMEOUT_SEC = int(os.environ.get("FIXPACK_SUGGEST_TIMEOUT_SEC", "6"))
# Auto-preview top suggestion (DRY-RUN) to speed decisions
FIXPACK_AUTO_PREVIEW = os.environ.get("FIXPACK_AUTO_PREVIEW", "true").lower() == "true"
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


def _call_vector_bridge_mcp(tool_name: str, params: dict, timeout_sec: int) -> dict | None:
    """Call vector-bridge MCP server via stdio. Fail-open on any error."""
    try:
        mcp_cmd = [
            "node",
            os.path.expanduser("~/.claude/mcp-servers/vector-bridge/dist/index.js"),
        ]
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "error-recovery", "version": "1.0.0"},
            },
        }
        tool_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": params},
        }
        proc = subprocess.Popen(
            mcp_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={
                **os.environ,
                "DATABASE_URL_MEMORY": os.environ.get("DATABASE_URL_MEMORY", ""),
                "REDIS_URL": os.environ.get("REDIS_URL", ""),
                "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
            },
        )
        payload = f"{json.dumps(init_request)}\n{json.dumps(tool_request)}\n"
        try:
            stdout, stderr = proc.communicate(input=payload, timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            return {"error": f"MCP call timed out after {timeout_sec}s"}
        # Parse line-delimited JSON responses
        for line in (stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("id") == 2:
                return obj.get("result") or {}
        return None
    except Exception as e:
        return {"error": str(e)}


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

    # Optionally suggest fixpacks before attempting local recovery (non-blocking guidance)
    if ENABLE_FIXPACK_SUGGEST and error_output:
        try:
            # Limit error message length to keep requests small
            snippet = error_output[-2000:]
            res = _call_vector_bridge_mcp(
                "solution_search",
                {"error_message": snippet, "limit": max(1, min(5, FIXPACK_MAX_SUGGESTIONS))},
                timeout_sec=FIXPACK_SUGGEST_TIMEOUT_SEC,
            )
            text = None
            if res and isinstance(res, dict):
                content = res.get("content")
                if isinstance(content, list) and content:
                    first = content[0]
                    if isinstance(first, dict):
                        text = first.get("text")
            if text:
                print("", file=sys.stderr)
                print("🧩 Suggested Fixpacks (from solution memory):", file=sys.stderr)
                # Print only the first ~40 lines to keep hook output compact
                lines = (text.splitlines() if isinstance(text, str) else [])
                preview = "\n".join(lines[:40])
                print(preview, file=sys.stderr)
                if len(lines) > 40:
                    print("… (truncated)", file=sys.stderr)

                # Auto-preview the top suggestion in DRY-RUN mode (if enabled)
                if FIXPACK_AUTO_PREVIEW:
                    # Heuristic: extract first `solution_id=NNN` from the suggestion text
                    m = re.search(r"solution_id\s*=\s*(\d+)", text)
                    if not m:
                        # Fallback: look for "Solution #NNN"
                        m = re.search(r"Solution\s*#(\d+)", text, re.IGNORECASE)
                    if m:
                        sol_id = int(m.group(1))
                        prev = _call_vector_bridge_mcp(
                            "solution_preview",
                            {"solution_id": sol_id},
                            timeout_sec=max(6, FIXPACK_SUGGEST_TIMEOUT_SEC + 2),
                        )
                        prev_text = None
                        if prev and isinstance(prev, dict):
                            pc = prev.get("content")
                            if isinstance(pc, list) and pc:
                                pf = pc[0]
                                if isinstance(pf, dict):
                                    prev_text = pf.get("text")
                        if prev_text:
                            print("", file=sys.stderr)
                            print(f"🔍 DRY-RUN Preview (solution_id={sol_id}):", file=sys.stderr)
                            p_lines = prev_text.splitlines()
                            p_head = "\n".join(p_lines[:40])
                            print(p_head, file=sys.stderr)
                            if len(p_lines) > 40:
                                print("… (truncated)", file=sys.stderr)
                            print("", file=sys.stderr)
                            print("👉 To apply: manually execute the steps above, then call `mcp__vector-bridge__solution_apply` with { solution_id: "+str(sol_id)+", success: true|false }.", file=sys.stderr)
                        else:
                            print("", file=sys.stderr)
                            print("(Could not preview solution steps; try `solution_preview` manually.)", file=sys.stderr)
        except Exception:
            pass

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
