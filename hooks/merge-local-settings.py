#!/usr/bin/env python3
"""
Merge global hooks into project-local settings

Usage:
    python3 merge-local-settings.py [project_dir]

If project_dir not provided, uses current directory
"""
import sys
import os
import json
from pathlib import Path

def merge_settings(project_dir):
    """Merge global hooks into project-local settings"""

    # Paths
    global_settings = Path.home() / ".claude" / "settings.json"
    local_settings = Path(project_dir) / ".claude" / "settings.local.json"

    # Load global settings
    if not global_settings.exists():
        print("❌ Global settings not found:", global_settings)
        return False

    with open(global_settings) as f:
        global_config = json.load(f)

    # Load or create local settings
    if local_settings.exists():
        with open(local_settings) as f:
            local_config = json.load(f)
    else:
        local_config = {}

    # Merge permissions from global into local (if not set locally)
    if "permissions" not in local_config:
        global_permissions = global_config.get("permissions", {})
        if global_permissions:
            local_config["permissions"] = global_permissions
            print(f"✓ Added permissions from global: {global_permissions}")

    # Merge hooks from global into local (don't overwrite existing local hooks)
    if "hooks" not in local_config:
        local_config["hooks"] = {}

    global_hooks = global_config.get("hooks", {})

    for hook_type, hook_configs in global_hooks.items():
        if hook_type not in local_config["hooks"]:
            # No local hooks for this type, use global
            local_config["hooks"][hook_type] = hook_configs
            print(f"✓ Added {hook_type} hooks from global")
        else:
            print(f"⚠ {hook_type} already exists in local, keeping local version")

    # Ensure directory exists
    local_settings.parent.mkdir(parents=True, exist_ok=True)

    # Write merged settings
    with open(local_settings, "w") as f:
        json.dump(local_config, f, indent=2)
        f.write("\n")

    print(f"\n✓ Merged settings saved to {local_settings}")
    return True

if __name__ == "__main__":
    project_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    print(f"Merging hooks for project: {project_dir}")
    print()

    if merge_settings(project_dir):
        print("\n✅ Done! Hooks are now active for this project.")
        print("\nRestart Claude Code to apply changes.")
    else:
        sys.exit(1)
