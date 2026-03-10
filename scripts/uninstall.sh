#!/bin/bash
# Uninstall MyAgent launchd service
set -e

PLIST_NAME="com.ying.myagent.plist"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "Uninstalling MyAgent launchd service..."
launchctl unload "$PLIST_DST" 2>/dev/null || true
rm -f "$PLIST_DST"
echo "MyAgent service uninstalled."
