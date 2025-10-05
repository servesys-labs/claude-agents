#!/usr/bin/env python3
import json
import sys

payload = json.loads(sys.stdin.read())
path = payload.get('transcript_path', 'NO PATH')

with open('/tmp/transcript_path.txt', 'w') as f:
    f.write(path)

print(f"Captured: {path}", file=sys.stderr)
sys.exit(0)
