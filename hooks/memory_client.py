#!/usr/bin/env python3
"""
Memory client - calls vector-bridge MCP server tools
Used by hooks to auto-index content
"""

import json
import subprocess
import sys

def call_mcp_tool(tool_name: str, args: dict) -> dict:
    """
    Call an MCP tool via the MCP CLI (if available) or direct node invocation
    """
    # For now, we'll use direct subprocess to call the MCP server
    # In production, this would use the MCP SDK or CLI

    # Prepare the request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": args
        }
    }

    try:
        # Call the MCP server via stdio
        result = subprocess.run(
            ['node', '/Users/agentsy/.claude/mcp-servers/vector-bridge/dist/index.js'],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return {
                'success': False,
                'error': f'MCP call failed: {result.stderr}'
            }

        response = json.loads(result.stdout)
        return json.loads(response.get('result', {}).get('content', [{}])[0].get('text', '{}'))

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def memory_ingest(project_root: str, path: str, text: str, meta: dict | None = None) -> dict:
    """
    Ingest text into vector memory
    """
    return call_mcp_tool('memory_ingest', {
        'project_root': project_root,
        'path': path,
        'text': text,
        'meta': meta or {}
    })

def memory_search(project_root: str, query: str, k: int = 8, global_search: bool = False) -> dict:
    """
    Search vector memory
    """
    return call_mcp_tool('memory_search', {
        'project_root': project_root,
        'query': query,
        'k': k,
        'global': global_search
    })

if __name__ == '__main__':
    # Test usage
    if len(sys.argv) > 1:
        if sys.argv[1] == 'ingest':
            result = memory_ingest(
                project_root='/Users/agentsy/vibe/game-start',
                path='test.md',
                text='This is a test document for vector ingestion.',
                meta={'type': 'test'}
            )
            print(json.dumps(result, indent=2))

        elif sys.argv[1] == 'search':
            result = memory_search(
                project_root='/Users/agentsy/vibe/game-start',
                query='test document',
                k=5
            )
            print(json.dumps(result, indent=2))
