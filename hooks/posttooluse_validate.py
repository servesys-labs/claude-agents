#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PostToolUse hook: run typecheck after file edits and warn (non-blocking).

Exit code semantics:
- 0: success (quiet)
- 1: warning (show to user, continue)
- 2: block (not used here, we only warn)
"""
import sys, json, subprocess, os
from pathlib import Path

def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception:
        # Invalid JSON, skip silently
        sys.exit(0)

    tool = payload.get("tool_name")
    args = payload.get("tool_input", {})

    # Only run on file writes
    if tool not in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        sys.exit(0)

    file_path = args.get("file_path", "")
    cwd = os.getcwd()

    # Check file type and run appropriate typecheck
    is_ts_js = file_path.endswith((".ts", ".tsx", ".js", ".jsx"))
    is_python = file_path.endswith(".py")

    if not (is_ts_js or is_python):
        sys.exit(0)

    # TypeScript/JavaScript typecheck (try common script names)
    if is_ts_js and (Path(cwd) / "package.json").exists():
        for script_name in ["type-check", "typecheck", "tsc"]:
            try:
                result = subprocess.run(
                    ["npm", "run", script_name],
                    cwd=cwd,
                    capture_output=True,
                    timeout=10,
                    text=True
                )

                # If script exists and completed (success or failure)
                if "Missing script" not in result.stderr:
                    if result.returncode != 0:
                        file_name = Path(file_path).name
                        print(f"\n❌ TypeScript typecheck FAILED after editing {file_name}", file=sys.stderr)
                        print("=============================================================", file=sys.stderr)
                        stderr = result.stderr[:500] if result.stderr else result.stdout[:500]
                        if stderr:
                            print(stderr, file=sys.stderr)
                        print("", file=sys.stderr)
                        print("🚫 BLOCKED: Fix type errors before continuing", file=sys.stderr)
                        print("", file=sys.stderr)
                        print("Main Agent should:", file=sys.stderr)
                        print("1. Review the type errors above", file=sys.stderr)
                        print("2. Either revert the change OR", file=sys.stderr)
                        print("3. Fix the type issues immediately", file=sys.stderr)
                        print("=============================================================", file=sys.stderr)
                        print("", file=sys.stderr)

                        # Hard block (exit 2) - force immediate fix
                        sys.exit(2)
                    # Script succeeded, done
                    sys.exit(0)
            except subprocess.TimeoutExpired:
                print("⚠️  Typecheck timed out (>10s)", file=sys.stderr)
                sys.exit(1)
            except FileNotFoundError:
                continue  # npm not found, try next script name
            except Exception:
                continue  # Other error, try next script name

    # Python typecheck (try mypy, then pyright)
    elif is_python:
        for tool, cmd in [("mypy", ["mypy", file_path]), ("pyright", ["pyright", file_path])]:
            try:
                result = subprocess.run(
                    cmd,
                    cwd=cwd,
                    capture_output=True,
                    timeout=10,
                    text=True
                )

                if result.returncode != 0:
                    file_name = Path(file_path).name
                    print(f"\n❌ Python typecheck FAILED ({tool}) after editing {file_name}", file=sys.stderr)
                    print("=============================================================", file=sys.stderr)
                    stderr = result.stderr[:500] if result.stderr else result.stdout[:500]
                    if stderr:
                        print(stderr, file=sys.stderr)
                    print("", file=sys.stderr)
                    print("🚫 BLOCKED: Fix type errors before continuing", file=sys.stderr)
                    print("", file=sys.stderr)
                    print("Main Agent should:", file=sys.stderr)
                    print("1. Review the type errors above", file=sys.stderr)
                    print("2. Either revert the change OR", file=sys.stderr)
                    print("3. Fix the type issues immediately", file=sys.stderr)
                    print("=============================================================", file=sys.stderr)
                    print("", file=sys.stderr)

                    # Hard block (exit 2) - force immediate fix
                    sys.exit(2)
                # Tool succeeded, don't try others
                break
            except FileNotFoundError:
                continue  # Tool not installed, try next
            except subprocess.TimeoutExpired:
                print(f"⚠️  {tool} timed out (>10s)", file=sys.stderr)
                sys.exit(1)
            except Exception:
                continue

    # Success - typecheck passed
    sys.exit(0)

if __name__ == "__main__":
    main()
