#!/bin/bash
# Diagnostic tool for Stop hook issues

echo "🔍 Stop Hook Diagnostics"
echo "========================"
echo ""

# Check if Stop hook exists and is executable
echo "1. Stop Hook File:"
if [ -f ~/claude-hooks/stop_digest.py ]; then
    echo "   ✅ Found: ~/claude-hooks/stop_digest.py"
    if [ -x ~/claude-hooks/stop_digest.py ]; then
        echo "   ✅ Executable"
    else
        echo "   ⚠️  Not executable (chmod +x needed)"
    fi
else
    echo "   ❌ NOT FOUND"
fi
echo ""

# Check if registered in settings.json
echo "2. Settings Registration:"
if grep -q "stop_digest.py" ~/.claude/settings.json; then
    echo "   ✅ Registered in settings.json"
    grep -A 2 '"Stop"' ~/.claude/settings.json | head -5
else
    echo "   ❌ NOT registered in settings.json"
fi
echo ""

# Check debug log
echo "3. Debug Log:"
if [ -f ~/claude-hooks/logs/stop_hook_debug.log ]; then
    echo "   ✅ Log exists: ~/claude-hooks/logs/stop_hook_debug.log"
    echo "   Last 5 entries:"
    tail -15 ~/claude-hooks/logs/stop_hook_debug.log | head -15
    echo ""
    echo "   Total triggers: $(grep -c 'Stop hook triggered' ~/claude-hooks/logs/stop_hook_debug.log)"
    echo "   Successful DIGEST captures: $(grep -c '✅ DIGEST found' ~/claude-hooks/logs/stop_hook_debug.log)"
else
    echo "   ❌ No log file (hook never executed)"
fi
echo ""

# Check NOTES.md
echo "4. NOTES.md Files:"
for notes in ~/claude-hooks/NOTES.md ~/Desktop/developer/*/NOTES.md; do
    if [ -f "$notes" ]; then
        size=$(wc -l < "$notes")
        echo "   📄 $notes ($size lines)"
        if [ $size -gt 20 ]; then
            echo "      ✅ Has content (digests captured)"
        else
            echo "      ⚠️  Empty/header only"
        fi
    fi
done
echo ""

# Check wsi.json
echo "5. WSI Files:"
for wsi in ~/claude-hooks/logs/wsi.json ~/Desktop/developer/*/wsi.json; do
    if [ -f "$wsi" ]; then
        items=$(jq '.items | length' "$wsi" 2>/dev/null || echo "0")
        echo "   📄 $wsi ($items items)"
        if [ "$items" -gt 0 ]; then
            echo "      ✅ Has tracked files"
        else
            echo "      ⚠️  Empty"
        fi
    fi
done
echo ""

# Test the hook
echo "6. Manual Test:"
echo "   Testing with sample payload..."
echo '{"session_id":"test","transcript_path":"/tmp/test-transcript.json","cwd":"'$(pwd)'"}' | python3 ~/claude-hooks/stop_digest.py 2>&1
echo ""

echo "✅ Diagnostics complete"
echo ""
echo "💡 If 'Total triggers' is 0:"
echo "   → Stop hook is NOT being called by Claude Code"
echo "   → Check Claude Code version or hook configuration"
echo ""
echo "💡 If triggers > 0 but DIGEST captures = 0:"
echo "   → Transcript format issue (check Role distribution in log)"
echo "   → Subagents may not be outputting DIGEST blocks"
