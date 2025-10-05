#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompt optimizer: Transforms casual user prompts into LLM-friendly structured prompts.

Hooks into UserPromptSubmit to automatically optimize before agent sees it.
"""
import sys, json, re
from pathlib import Path

def detect_prompt_type(prompt):
    """Categorize prompt to apply appropriate optimization."""
    prompt_lower = prompt.lower()

    # Bug fix request
    if any(word in prompt_lower for word in ['fix', 'bug', 'error', 'broken', 'issue']):
        return 'bugfix'

    # Feature request
    if any(word in prompt_lower for word in ['add', 'create', 'implement', 'build', 'new']):
        return 'feature'

    # Refactor/improvement
    if any(word in prompt_lower for word in ['improve', 'refactor', 'optimize', 'update', 'change']):
        return 'refactor'

    # Question/information
    if any(word in prompt_lower for word in ['how', 'what', 'why', 'when', 'where', 'explain', 'show']):
        return 'question'

    # Review/analysis
    if any(word in prompt_lower for word in ['review', 'check', 'analyze', 'audit', 'inspect']):
        return 'review'

    return 'general'

def extract_context_clues(prompt):
    """Extract file paths, technical terms, and scope indicators."""
    context = {
        'files': [],
        'tech_terms': [],
        'scope_indicators': []
    }

    # File paths (extensions: .ts, .tsx, .js, .jsx, .py, .md, etc.)
    file_pattern = r'[\w/.-]+\.(?:ts|tsx|js|jsx|py|md|json|prisma|sql|css|scss|html)'
    context['files'] = re.findall(file_pattern, prompt)

    # Technical terms (camelCase, PascalCase, snake_case)
    tech_pattern = r'\b(?:[A-Z][a-z]+){2,}|[a-z]+(?:[A-Z][a-z]+)+|[a-z]+_[a-z_]+\b'
    context['tech_terms'] = re.findall(tech_pattern, prompt)

    # Scope indicators
    if 'everywhere' in prompt.lower() or 'all' in prompt.lower():
        context['scope_indicators'].append('global')
    elif 'just' in prompt.lower() or 'only' in prompt.lower():
        context['scope_indicators'].append('minimal')

    return context

def transform_to_llm_friendly(prompt, prompt_type, context):
    """Transform casual prompt into structured LLM-friendly format."""

    optimized = []

    # Add role/context header
    optimized.append("<task>")

    # Add task type
    task_labels = {
        'bugfix': 'Bug Fix',
        'feature': 'Feature Implementation',
        'refactor': 'Code Refactoring',
        'question': 'Information Request',
        'review': 'Code Review',
        'general': 'Task'
    }
    optimized.append(f"**Type**: {task_labels.get(prompt_type, 'Task')}")
    optimized.append("")

    # Add original request
    optimized.append("**User Request**:")
    optimized.append(prompt)
    optimized.append("")

    # Add structured context if available
    if context['files'] or context['tech_terms'] or context['scope_indicators']:
        optimized.append("<context>")

        if context['files']:
            optimized.append("**Files Mentioned**:")
            for f in context['files']:
                optimized.append(f"- {f}")
            optimized.append("")

        if context['tech_terms']:
            optimized.append("**Technical Terms**:")
            optimized.append(", ".join(context['tech_terms'][:5]))  # Limit to 5
            optimized.append("")

        if context['scope_indicators']:
            optimized.append("**Scope**: " + ", ".join(context['scope_indicators']))
            optimized.append("")

        optimized.append("</context>")
        optimized.append("")

    # Add task-specific guidance
    if prompt_type == 'bugfix':
        optimized.append("<instructions>")
        optimized.append("1. Identify the root cause")
        optimized.append("2. Propose a fix")
        optimized.append("3. Write a test that reproduces the bug (should fail before fix)")
        optimized.append("4. Apply the fix")
        optimized.append("5. Verify the test now passes")
        optimized.append("</instructions>")

    elif prompt_type == 'feature':
        optimized.append("<instructions>")
        optimized.append("1. Clarify requirements if ambiguous (present options)")
        optimized.append("2. Identify files to modify/create")
        optimized.append("3. Implement the feature")
        optimized.append("4. Add tests")
        optimized.append("5. Update documentation if needed")
        optimized.append("</instructions>")

    elif prompt_type == 'refactor':
        optimized.append("<instructions>")
        optimized.append("1. Understand current implementation")
        optimized.append("2. Propose refactoring approach")
        optimized.append("3. Ensure tests exist (add if missing)")
        optimized.append("4. Apply refactoring incrementally")
        optimized.append("5. Verify tests still pass")
        optimized.append("</instructions>")

    elif prompt_type == 'question':
        optimized.append("<instructions>")
        optimized.append("1. Search relevant files/documentation")
        optimized.append("2. Provide clear, concise answer")
        optimized.append("3. Include code examples if applicable")
        optimized.append("4. Reference file paths with line numbers")
        optimized.append("</instructions>")

    elif prompt_type == 'review':
        optimized.append("<instructions>")
        optimized.append("1. Read specified files/code")
        optimized.append("2. Check for: bugs, performance issues, security vulnerabilities")
        optimized.append("3. Verify: type safety, test coverage, documentation")
        optimized.append("4. Provide actionable feedback with priorities")
        optimized.append("</instructions>")

    optimized.append("")
    optimized.append("</task>")

    return "\n".join(optimized)

def should_optimize(prompt):
    """Determine if prompt needs optimization."""
    # Skip if already structured (contains XML tags)
    if '<task>' in prompt or '<instructions>' in prompt:
        return False

    # Skip very short prompts (likely already clear)
    if len(prompt.split()) < 3:
        return False

    # Skip if very specific (contains file paths and line numbers)
    if re.search(r':\d+', prompt) and re.search(r'\.(?:ts|js|py)', prompt):
        return False

    return True

def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except:
        # If not JSON, treat as plain text
        payload = {"prompt": raw.strip()}

    original_prompt = payload.get("prompt", "")

    if not original_prompt or not should_optimize(original_prompt):
        # Pass through unchanged
        print(json.dumps(payload), file=sys.stdout)
        sys.exit(0)

    # Optimize the prompt
    prompt_type = detect_prompt_type(original_prompt)
    context = extract_context_clues(original_prompt)
    optimized_prompt = transform_to_llm_friendly(original_prompt, prompt_type, context)

    # Show optimization summary to stderr (visible to user)
    print(f"\n✨ Prompt optimized for better LLM understanding:", file=sys.stderr)
    print(f"   Type: {prompt_type}", file=sys.stderr)
    if context['files']:
        print(f"   Files: {', '.join(context['files'][:3])}", file=sys.stderr)
    print("", file=sys.stderr)

    # Output optimized payload
    payload["prompt"] = optimized_prompt
    payload["_original_prompt"] = original_prompt
    payload["_optimization_metadata"] = {
        "type": prompt_type,
        "context": context
    }

    print(json.dumps(payload), file=sys.stdout)
    sys.exit(0)

if __name__ == "__main__":
    main()
