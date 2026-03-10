#!/bin/bash
# Install MyAgent as a launchd service
set -e

PLIST_NAME="com.ying.myagent.plist"
PLIST_SRC="/Users/ying/Documents/MyAgent/$PLIST_NAME"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "Installing MyAgent launchd service..."

# Create logs directory
mkdir -p /Users/ying/Documents/MyAgent/logs

# Copy plist
cp "$PLIST_SRC" "$PLIST_DST"

# Load the service
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo "MyAgent service installed and started."
echo "  Status: launchctl list | grep myagent"
echo "  Logs:   tail -f /Users/ying/Documents/MyAgent/logs/myagent.out.log"
echo "  Stop:   launchctl unload $PLIST_DST"
echo "  Start:  launchctl load $PLIST_DST"
