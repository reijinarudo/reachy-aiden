#!/bin/bash
# Optional. When the robot rejoins Wi-Fi (for example, moving from home
# Wi-Fi to a phone hotspot), the realtime session is often left stale.
# This watches for reconnect events, refreshes memories, restarts the app,
# and checks that your profile loaded.
LAST_RESTART=0
DEBOUNCE_SECONDS=30
EXPECTED_PROFILE="profile='${ROBOT_NAME:?ROBOT_NAME not set}'"
sleep 60  # Skip the initial boot connection
journalctl -f -n 0 --no-pager | while read -r line; do
    if echo "$line" | grep -q "CTRL-EVENT-CONNECTED"; then
        NOW=$(date +%s)
        ELAPSED=$((NOW - LAST_RESTART))
        if [ $ELAPSED -gt $DEBOUNCE_SECONDS ]; then
            LAST_RESTART=$NOW
            logger -t wifi-reconnect-watchdog "Wi-Fi reconnection detected, restarting conversation app"
            sleep 5
            systemctl start memory-catchup.service
            curl -s -X POST http://localhost:8000/api/apps/restart-current-app > /dev/null
            sleep 20
            if journalctl --since "30 seconds ago" --no-pager | grep -q "$EXPECTED_PROFILE"; then
                logger -t wifi-reconnect-watchdog "Restart verified, profile loaded"
            else
                logger -t wifi-reconnect-watchdog "WARNING: profile not confirmed after restart, retrying"
                sleep 5
                curl -s -X POST http://localhost:8000/api/apps/restart-current-app > /dev/null
            fi
        fi
    fi
done
