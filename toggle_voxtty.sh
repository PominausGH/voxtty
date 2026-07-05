#!/bin/bash
# Toggle dictation on/off — assign to a keyboard shortcut in GNOME Settings

PID_FILE="/tmp/voxtty.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill -SIGUSR1 "$PID"
        exit 0
    fi
fi

# Service not running — start it
systemctl --user start voxtty.service
