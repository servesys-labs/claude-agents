#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM Conversation Manager - Multi-round dialogue system for PM Agent

Enables PM to have back-and-forth conversations with subagents:
1. PM asks clarifying questions
2. Subagent/tools provide context (file reads, grep, etc.)
3. PM makes informed strategic decisions
4. All conversation rounds stored for context

This enables "vibe coding" - user sets vision, PM + agents execute autonomously.
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import subprocess
import sys

# Paths
CLAUDE_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())) / ".claude"
PM_QUEUE_DIR = CLAUDE_DIR / "pm-queue"


class ConversationRound:
    """A single round in PM dialogue."""

    def __init__(self, role: str, content: str, tools_used: Optional[List[Dict]] = None):
        self.role = role  # "pm" | "system" | "tool"
        self.content = content
        self.tools_used = tools_used or []
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "tools_used": self.tools_used,
            "timestamp": self.timestamp
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ConversationRound':
        round_obj = ConversationRound(
            role=data["role"],
            content=data["content"],
            tools_used=data.get("tools_used", [])
        )
        round_obj.timestamp = data["timestamp"]
        return round_obj


class PMConversation:
    """
    Manages multi-round PM dialogue for a single decision request.

    Storage: .claude/pm-queue/{request-id}/
    - request.json (original decision point)
    - conversation.json (all rounds)
    - context/ (tool outputs - files, grep results)
    """

    def __init__(self, request_id: str):
        self.request_id = request_id
        self.conversation_dir = PM_QUEUE_DIR / request_id
        self.conversation_dir.mkdir(parents=True, exist_ok=True)

        self.context_dir = self.conversation_dir / "context"
        self.context_dir.mkdir(exist_ok=True)

        self.request_file = self.conversation_dir / "request.json"
        self.conversation_file = self.conversation_dir / "conversation.json"

        self.rounds: List[ConversationRound] = []
        self.request_data: Dict[str, Any] = {}

        # Load existing conversation if any
        self._load()

    def _load(self):
        """Load existing conversation state."""
        # Load request
        if self.request_file.exists():
            with open(self.request_file, "r", encoding="utf-8") as f:
                self.request_data = json.load(f)

        # Load conversation rounds
        if self.conversation_file.exists():
            with open(self.conversation_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.rounds = [ConversationRound.from_dict(r) for r in data.get("rounds", [])]

    def _save(self):
        """Persist conversation state."""
        data = {
            "request_id": self.request_id,
            "rounds": [r.to_dict() for r in self.rounds],
            "started_at": self.rounds[0].timestamp if self.rounds else None,
            "last_updated": datetime.now().isoformat()
        }
        with open(self.conversation_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add_round(self, role: str, content: str, tools_used: Optional[List[Dict]] = None):
        """Add a conversation round and persist."""
        round_obj = ConversationRound(role, content, tools_used)
        self.rounds.append(round_obj)
        self._save()

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """
        Get conversation history formatted for OpenAI API.

        Returns list of {"role": "user"|"assistant", "content": "..."}
        """
        messages = []
        for round_obj in self.rounds:
            if round_obj.role == "pm":
                messages.append({"role": "assistant", "content": round_obj.content})
            elif round_obj.role == "system":
                # Tool outputs, context - as user message
                messages.append({"role": "user", "content": round_obj.content})
            elif round_obj.role == "tool":
                # Tool results - as user message
                messages.append({"role": "user", "content": round_obj.content})
        return messages

    def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Execute a tool request from PM and return results.

        Supported tools:
        - read_file: Read file contents
        - grep: Search codebase
        - list_files: List directory contents
        - get_git_status: Get git status
        - get_git_log: Get recent commits
        """
        try:
            if tool_name == "read_file":
                return self._read_file(tool_args.get("path", ""))
            elif tool_name == "grep":
                return self._grep(tool_args.get("pattern", ""), tool_args.get("path", "."))
            elif tool_name == "list_files":
                return self._list_files(tool_args.get("path", "."))
            elif tool_name == "get_git_status":
                return self._get_git_status()
            elif tool_name == "get_git_log":
                return self._get_git_log(tool_args.get("limit", 10))
            else:
                return False, f"Unknown tool: {tool_name}"
        except Exception as e:
            return False, f"Tool execution failed: {e}"

    def _read_file(self, path: str) -> Tuple[bool, str]:
        """Read file contents (max 500 lines)."""
        project_root = self.request_data.get("project_root", str(CLAUDE_DIR.parent))
        file_path = Path(project_root) / path

        if not file_path.exists():
            return False, f"File not found: {path}"

        if not file_path.is_file():
            return False, f"Not a file: {path}"

        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
            # Limit to 500 lines to avoid token explosion
            if len(lines) > 500:
                content = "\n".join(lines[:500])
                content += f"\n... (truncated, {len(lines) - 500} more lines)"
            else:
                content = "\n".join(lines)

            # Save to context dir
            context_file = self.context_dir / f"read_{hashlib.sha256(path.encode()).hexdigest()[:8]}.txt"
            context_file.write_text(content, encoding="utf-8")

            return True, f"File: {path}\n\n{content}"
        except Exception as e:
            return False, f"Error reading file: {e}"

    def _grep(self, pattern: str, path: str = ".") -> Tuple[bool, str]:
        """Search codebase with grep."""
        project_root = self.request_data.get("project_root", str(CLAUDE_DIR.parent))

        try:
            result = subprocess.run(
                ["grep", "-rn", "--include=*.ts", "--include=*.tsx", "--include=*.js",
                 "--include=*.jsx", "--include=*.py", "--include=*.md",
                 pattern, path],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                lines = result.stdout.splitlines()
                # Limit results
                if len(lines) > 100:
                    output = "\n".join(lines[:100])
                    output += f"\n... (truncated, {len(lines) - 100} more matches)"
                else:
                    output = result.stdout

                # Save to context
                context_file = self.context_dir / f"grep_{hashlib.sha256(pattern.encode()).hexdigest()[:8]}.txt"
                context_file.write_text(output, encoding="utf-8")

                return True, f"Grep results for '{pattern}':\n\n{output}"
            else:
                return True, f"No matches found for '{pattern}'"
        except subprocess.TimeoutExpired:
            return False, "Grep timed out (10s limit)"
        except Exception as e:
            return False, f"Grep failed: {e}"

    def _list_files(self, path: str = ".") -> Tuple[bool, str]:
        """List directory contents."""
        project_root = self.request_data.get("project_root", str(CLAUDE_DIR.parent))
        dir_path = Path(project_root) / path

        if not dir_path.exists():
            return False, f"Directory not found: {path}"

        if not dir_path.is_dir():
            return False, f"Not a directory: {path}"

        try:
            # List files (not recursive, max 200 items)
            items = []
            for item in sorted(dir_path.iterdir())[:200]:
                if item.name.startswith("."):
                    continue
                item_type = "dir" if item.is_dir() else "file"
                items.append(f"  {item_type:4} {item.name}")

            output = f"Directory: {path}\n\n" + "\n".join(items)

            if len(list(dir_path.iterdir())) > 200:
                output += f"\n... (truncated, {len(list(dir_path.iterdir())) - 200} more items)"

            return True, output
        except Exception as e:
            return False, f"Error listing directory: {e}"

    def _get_git_status(self) -> Tuple[bool, str]:
        """Get git status."""
        project_root = self.request_data.get("project_root", str(CLAUDE_DIR.parent))

        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                return True, f"Git status:\n\n{result.stdout}"
            else:
                return False, f"Git status failed: {result.stderr}"
        except Exception as e:
            return False, f"Git status failed: {e}"

    def _get_git_log(self, limit: int = 10) -> Tuple[bool, str]:
        """Get recent git commits."""
        project_root = self.request_data.get("project_root", str(CLAUDE_DIR.parent))

        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--oneline"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                return True, f"Recent commits (last {limit}):\n\n{result.stdout}"
            else:
                return False, f"Git log failed: {result.stderr}"
        except Exception as e:
            return False, f"Git log failed: {e}"


def create_conversation(decision_point: str, project_root: str, digest: Optional[Dict] = None) -> str:
    """
    Create a new PM conversation.

    Returns conversation ID.
    """
    # Generate unique ID
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    request_id = f"pm-{timestamp}-{hashlib.sha256(decision_point.encode()).hexdigest()[:8]}"

    # Create conversation
    conversation = PMConversation(request_id)

    # Save request data
    request_data = {
        "decision_point": decision_point,
        "project_root": project_root,
        "digest": digest,
        "created_at": datetime.now().isoformat()
    }

    with open(conversation.request_file, "w", encoding="utf-8") as f:
        json.dump(request_data, f, indent=2)

    # Initialize conversation with decision point
    conversation.request_data = request_data
    conversation.add_round("system", f"Decision point:\n\n{decision_point}")

    return request_id


def load_conversation(request_id: str) -> PMConversation:
    """Load existing conversation."""
    return PMConversation(request_id)


def list_active_conversations() -> List[str]:
    """List all active conversation IDs."""
    if not PM_QUEUE_DIR.exists():
        return []

    conversations = []
    for item in PM_QUEUE_DIR.iterdir():
        if item.is_dir() and (item / "conversation.json").exists():
            conversations.append(item.name)

    return sorted(conversations)
