#!/bin/bash
# Setup PM Queue Processor launchd agent

set -e

CLAUDE_DIR="${CLAUDE_PROJECT_DIR:-$PWD/.claude}"
LAUNCHD_DIR="$CLAUDE_DIR/launchd"
SCRIPT_PATH="$HOME/.claude/hooks/pm_queue_processor.py"
PYTHON_BIN=$(which python3)

# Label for launchd agent
LABEL="com.claude.pm-queue-processor"
PLIST_NAME="${LABEL}.plist"
PLIST_PATH="$LAUNCHD_DIR/$PLIST_NAME"

# Create launchd directory
mkdir -p "$LAUNCHD_DIR"

# Generate plist
cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>$SCRIPT_PATH</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$CLAUDE_DIR/..</string>
    <key>StartInterval</key>
    <integer>600</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$CLAUDE_DIR/logs/pm-queue-processor-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$CLAUDE_DIR/logs/pm-queue-processor-stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>OPENAI_API_KEY</key>
        <string>${OPENAI_API_KEY}</string>
        <key>CLAUDE_PROJECT_DIR</key>
        <string>$CLAUDE_DIR/..</string>
        <key>LOGS_DIR</key>
        <string>$CLAUDE_DIR/logs</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ Created plist: $PLIST_PATH"

# Copy to ~/Library/LaunchAgents (standard location, consistent with auto-setup agents)
USER_LAUNCHD_DIR="$HOME/Library/LaunchAgents"
USER_PLIST_PATH="$USER_LAUNCHD_DIR/$PLIST_NAME"

mkdir -p "$USER_LAUNCHD_DIR"
cp "$PLIST_PATH" "$USER_PLIST_PATH"

echo "✅ Copied to: $USER_PLIST_PATH"

# Load into launchd from standard location
launchctl unload "$USER_PLIST_PATH" 2>/dev/null || true
launchctl load "$USER_PLIST_PATH"

echo "✅ Loaded launchd agent: $LABEL"
echo ""
echo "PM Queue Processor is now running every 10 minutes (600 seconds)"
echo ""
echo "Commands:"
echo "  Check status:  launchctl list | grep pm-queue"
echo "  View logs:     tail -f $CLAUDE_DIR/logs/pm-queue-processor-stdout.log"
echo "  Manual run:    python3 $SCRIPT_PATH"
echo "  Unload:        launchctl unload $USER_PLIST_PATH"
