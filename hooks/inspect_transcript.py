#!/usr/bin/env python3
"""One-time inspection script to dump full transcript structure"""
import json
import sys
import os

payload = json.loads(sys.stdin.read())
transcript_path = payload.get('transcript_path')

output_file = os.path.expanduser("~/claude-hooks/logs/transcript_dump.json")

if transcript_path and os.path.exists(transcript_path):
    with open(transcript_path, 'r') as f:
        content = f.read().strip()

    # Try parsing
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

    # Save first 5 messages with full structure
    sample = transcript[:5] if len(transcript) > 5 else transcript

    with open(output_file, 'w') as f:
        json.dump({
            'total_messages': len(transcript),
            'sample_messages': sample,
            'transcript_path': transcript_path
        }, f, indent=2)

    print(f"Dumped to {output_file}", file=sys.stderr)
else:
    with open(output_file, 'w') as f:
        json.dump({'error': 'No transcript path', 'payload': payload}, f, indent=2)

sys.exit(0)
