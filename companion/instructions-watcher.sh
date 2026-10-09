#!/bin/bash
# Restart the conversation app a few seconds after the persona file is saved,
# so edits take effect without a reboot.
#
# inotify watches the file itself. Save edits in place (an SFTP editor, or
# a sed -i one-liner). Replacing the file with "mv" breaks the watch until
# this service restarts.
INSTRUCTIONS="/home/pollen/profiles/${ROBOT_NAME:?ROBOT_NAME not set}/instructions.txt"
while inotifywait -e modify "$INSTRUCTIONS" >/dev/null 2>&1; do
    sleep 2
    curl -s -X POST http://localhost:8000/api/apps/restart-current-app >/dev/null
done
