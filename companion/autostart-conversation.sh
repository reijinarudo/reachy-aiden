#!/bin/bash
# Wait for the daemon API to be reachable
for i in $(seq 1 60); do
    if curl -sf http://localhost:8000/api/daemon/status >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

# Poll until motor control is enabled, with timeout
for i in $(seq 1 60); do
    motor_mode=$(curl -s http://localhost:8000/api/daemon/status | python3 -c "import json,sys; print(json.load(sys.stdin).get('backend_status',{}).get('motor_control_mode','disabled'))" 2>/dev/null)
    if [ "$motor_mode" = "enabled" ]; then
        break
    fi
    sleep 2
done

# Extra buffer to ensure motors are fully ready and head is up
sleep 5

# Start the conversation app
curl -s -X POST http://localhost:8000/api/apps/start-app/reachy_mini_conversation_app
