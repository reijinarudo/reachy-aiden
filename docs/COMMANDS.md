# Command reference

Run these on the robot after `ssh pollen@reachy-mini.local`.

## Everyday

| Task | Command |
| --- | --- |
| Health check | `companion-status` |
| Current backend | `companion-switch` |
| Switch backend | `companion-switch huggingface`, `companion-switch openai`, `companion-switch gemini` |
| Restart the conversation app | `curl -s -X POST http://localhost:8000/api/apps/restart-current-app` |
| Start the app when none is running | `curl -s -X POST http://localhost:8000/api/apps/start-app/reachy_mini_conversation_app` |
| Stop the app | `curl -s -X POST http://localhost:8000/api/apps/stop-current-app` |
| Unmute the microphone | `amixer -c 0 sset 'Headset',0 cap` |
| Watch the conversation live | `tail -f /home/pollen/conversation-logs/conversation-$(date +%Y-%m-%d).jsonl` |

## Persona and memory

| Task | Command |
| --- | --- |
| Edit the persona (reloads on save) | `nano /home/pollen/profiles/<ROBOT_NAME>/instructions.txt` |
| Add a permanent memory | `companion-add-memory "I met my owner's sister today." --tags family` |
| Read extracted memories | `cat /home/pollen/companion-memories/memories.jsonl` |
| Refresh memories now | `sudo systemctl start memory-catchup.service` |
| Summarize a specific day | `sudo systemctl start memory-summarizer.service` (yesterday), or `sudo bash -c 'set -a; . /etc/reachy-companion/companion.env; /venvs/apps_venv/bin/python /home/pollen/companion/memory-summarizer.py 2026-10-01'` |
| Next scheduled summary | `systemctl list-timers \| grep memory` |

## After an update

| Task | Command |
| --- | --- |
| Check what an update removed | `sudo companion-reapply --check` |
| Put the changes back | `sudo companion-reapply` |
| Load them | `sudo systemctl restart reachy-mini-daemon` |

## Recovery, in order from lightest to heaviest

1. `curl -s -X POST http://localhost:8000/api/apps/restart-current-app`
2. `curl -s -X POST http://localhost:8000/api/apps/start-app/reachy_mini_conversation_app`
3. `sudo systemctl restart reachy-mini-daemon` (wait a minute; the autostart service starts the app)
4. `sudo reboot`

## Diagnostics

| Task | Command |
| --- | --- |
| Recent system log | `sudo journalctl --since "5 minutes ago" --no-pager \| tail -40` |
| Daemon log | `sudo journalctl -u reachy-mini-daemon --since "10 minutes ago" --no-pager` |
| Which backend loaded | `sudo journalctl --since "2 minutes ago" --no-pager \| grep -i backend` |
| Tool calls | `sudo journalctl --since "5 minutes ago" --no-pager \| grep "Tool call"` |
| App status | `curl -s http://localhost:8000/api/apps/current-app-status \| python3 -m json.tool` |
| Daemon status | `curl -s http://localhost:8000/api/daemon/status \| python3 -m json.tool` |
| All daemon API endpoints | `curl -s http://localhost:8000/openapi.json \| python3 -c "import sys,json;[print(p) for p in sorted(json.load(sys.stdin)['paths'])]"` |
| Motor errors in the last hour | `sudo journalctl --since "1 hour ago" --no-pager \| grep -c "Motor communication error"` |
| Memory and CPU | `free -h` and `top -bn1 \| head -20` |
| Microphone test (5 s) | `arecord -D reachymini_audio_src -d 5 -f S16_LE -r 16000 -c 2 /tmp/mic.wav && aplay /tmp/mic.wav` |

## Wi-Fi

| Task | Command |
| --- | --- |
| Active connection | `sudo nmcli connection show --active` |
| Networks in range | `sudo nmcli device wifi list` |
| Join a network | `sudo nmcli device wifi connect "Name" password "password"` |
| Prefer one network | `sudo nmcli connection modify "Name" connection.autoconnect-priority 100` |

## Power

| Task | Command |
| --- | --- |
| Reboot | `sudo reboot` |
| Shut down | `sudo shutdown -h now` |
