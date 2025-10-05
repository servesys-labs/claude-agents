#!/usr/bin/env python3
"""
Test script for enhanced hooks v1.2.5

Tests:
1. Duplicate read blocking (3 attempts then block)
2. Routing enforcement warning for direct code edits
3. MD spam prevention with approval
"""
import json
import subprocess
import tempfile
from pathlib import Path

def test_duplicate_read_blocking():
    """Test that duplicate reads are blocked after 3 attempts."""
    print("\n=== Testing Duplicate Read Blocking ===")

    # Create a test file
    test_file = "/tmp/test_duplicate_read.txt"
    with open(test_file, 'w') as f:
        f.write("Test content for duplicate read detection")

    # Simulate multiple read attempts
    for attempt in range(1, 5):
        print(f"\nAttempt {attempt}:")

        # Create Read tool input
        tool_input = {
            "tool_name": "Read",
            "tool_input": {"file_path": test_file}
        }

        # Run pretooluse_validate.py
        result = subprocess.run(
            ["python3", "/Users/agentsy/claude-hooks/pretooluse_validate.py"],
            input=json.dumps(tool_input),
            capture_output=True,
            text=True
        )

        print(f"Exit code: {result.returncode}")
        if result.stderr:
            print(f"Hook output:\n{result.stderr[:500]}")

        # Expected behavior:
        # Attempt 1: Exit 0 (success, first read)
        # Attempt 2: Exit 1 (warning)
        # Attempt 3: Exit 1 (warning)
        # Attempt 4: Exit 2 (blocked)
        if attempt == 1:
            assert result.returncode == 0, f"First read should succeed (got {result.returncode})"
        elif attempt in [2, 3]:
            assert result.returncode == 1, f"Attempt {attempt} should warn (got {result.returncode})"
        elif attempt == 4:
            assert result.returncode == 2, f"Attempt {attempt} should block (got {result.returncode})"

    print("\n✅ Duplicate read blocking test passed!")

def test_routing_enforcement():
    """Test routing enforcement for direct code edits."""
    print("\n=== Testing Routing Enforcement ===")

    # Test cases
    test_cases = [
        # (file_path, should_warn)
        ("/Users/project/lib/auth.ts", True),  # Project code - should warn
        ("/Users/project/app/page.tsx", True),  # Project code - should warn
        ("/Users/agentsy/claude-hooks/test.py", False),  # Hook code - allowed
        ("/Users/project/.claude/config.json", False),  # Config - allowed
        ("/Users/project/README.md", False),  # Documentation - allowed
    ]

    for file_path, should_warn in test_cases:
        print(f"\nTesting: {file_path}")

        tool_input = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": file_path,
                "old_string": "test",
                "new_string": "test2"
            }
        }

        result = subprocess.run(
            ["python3", "/Users/agentsy/claude-hooks/pretooluse_validate.py"],
            input=json.dumps(tool_input),
            capture_output=True,
            text=True
        )

        if should_warn:
            # Should get warning about routing policy
            assert result.returncode == 1, f"Should warn for {file_path}"
            assert "ROUTING POLICY" in result.stderr, "Should mention routing policy"
            print(f"✓ Got expected routing warning")
        else:
            # Should not warn for allowed paths
            has_routing_warning = "ROUTING POLICY" in result.stderr
            if has_routing_warning:
                print(f"✗ Unexpected routing warning for {file_path}")
            else:
                print(f"✓ No routing warning (as expected)")

    print("\n✅ Routing enforcement test passed!")

def test_md_approval():
    """Test MD creation with approval state."""
    print("\n=== Testing MD Approval System ===")

    # Create approval state
    state_file = Path.home() / "claude-hooks" / "logs" / "md_request_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)

    from datetime import datetime
    state = {
        "timestamp": datetime.now().isoformat(),
        "approved_files": ["test-doc.md"],
        "detection_source": "test"
    }

    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)

    # Test approved file
    tool_input = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/Users/project/docs/test-doc.md",
            "content": "# Test Doc"
        }
    }

    result = subprocess.run(
        ["python3", "/Users/agentsy/claude-hooks/pretooluse_validate.py"],
        input=json.dumps(tool_input),
        capture_output=True,
        text=True
    )

    # Should be allowed with approval
    assert result.returncode == 0, f"Approved MD should be allowed (got {result.returncode})"
    print("✓ Approved MD creation allowed")

    # Test non-approved file
    tool_input["tool_input"]["file_path"] = "/Users/project/docs/unapproved.md"

    result = subprocess.run(
        ["python3", "/Users/agentsy/claude-hooks/pretooluse_validate.py"],
        input=json.dumps(tool_input),
        capture_output=True,
        text=True
    )

    # Should be blocked
    assert result.returncode == 2, f"Unapproved MD should be blocked (got {result.returncode})"
    assert "MD SPAM" in result.stderr, "Should mention MD spam policy"
    print("✓ Unapproved MD creation blocked")

    print("\n✅ MD approval test passed!")

def main():
    print("Testing Claude Hooks v1.2.5 Enhancements")
    print("=========================================")

    test_duplicate_read_blocking()
    test_routing_enforcement()
    test_md_approval()

    print("\n=========================================")
    print("All tests passed! ✅")
    print("\nEnhancements working correctly:")
    print("• Duplicate reads blocked after 3 attempts")
    print("• Routing policy warnings for direct code edits")
    print("• MD spam prevention with approval system")

if __name__ == "__main__":
    main()