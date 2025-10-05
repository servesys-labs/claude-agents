#!/usr/bin/env python3
"""Debug script to examine transcript structure"""
import json
import sys

# Read stdin (payload from Stop hook)
payload = json.loads(sys.stdin.read())

transcript_path = payload.get("transcript_path")
print(f"Transcript path: {transcript_path}", file=sys.stderr)

if transcript_path:
    with open(transcript_path, 'r') as f:
        content = f.read().strip()

    # Try JSON array
    try:
        transcript = json.loads(content)
    except:
        # Try JSONL
        transcript = []
        for line in content.split('\n'):
            if line.strip():
                try:
                    transcript.append(json.loads(line))
                except:
                    pass

    print(f"\nTotal messages: {len(transcript)}", file=sys.stderr)

    # Sample a few message types
    types_seen = {}
    for msg in transcript[:50]:  # First 50 messages
        msg_type = msg.get('type', 'unknown')
        if msg_type not in types_seen:
            types_seen[msg_type] = msg

    print(f"\nMessage types found: {list(types_seen.keys())}", file=sys.stderr)

    # Dump full structure of each type
    for msg_type, msg in types_seen.items():
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"Type: {msg_type}", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(json.dumps(msg, indent=2)[:1000], file=sys.stderr)  # First 1000 chars

        # Show where content might be
        if 'content' in msg:
            print(f"\n[content field exists, length: {len(str(msg['content']))}]", file=sys.stderr)
        if 'message' in msg:
            print(f"[message field exists, length: {len(str(msg['message']))}]", file=sys.stderr)
        if 'text' in msg:
            print(f"[text field exists, length: {len(str(msg['text']))}]", file=sys.stderr)
