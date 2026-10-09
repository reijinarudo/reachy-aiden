# Optional: Google Calendar tool

Lets the robot answer "what is on my calendar today?" It reads event titles and start times only. Location, notes, and attendees are dropped before anything reaches the voice model. Events you mark as Private in Google Calendar are hidden.

This tool is optional. It is not installed by `install.sh`.

## Setup

1. In the [Google Cloud Console](https://console.cloud.google.com/), create a project, enable the **Google Calendar API**, and create an **OAuth client ID** of type **Desktop app**. Download the JSON file.
2. Copy the file to the robot:

   ```bash
   ssh pollen@reachy-mini.local "mkdir -p ~/secrets && chmod 700 ~/secrets"
   scp client_secret_XXXX.json pollen@reachy-mini.local:~/secrets/gcal_client.json
   ```

3. Install the Google libraries into the conversation app's Python environment:

   ```bash
   ssh pollen@reachy-mini.local
   sudo /venvs/apps_venv/bin/pip install -r ~/reachy-aiden/extras/calendar/requirements.txt
   ```

4. Copy the tool into the tools folder:

   ```bash
   cp ~/reachy-aiden/extras/calendar/get_calendar.py /home/pollen/tools/
   ```

5. Authorize once. The consent page runs on port 8765 of the robot, so open a second terminal on your computer with a tunnel first:

   ```bash
   ssh -L 8765:localhost:8765 pollen@reachy-mini.local
   /venvs/apps_venv/bin/python /home/pollen/tools/get_calendar.py --authorize
   ```

   Open the URL it prints in your browser and approve read-only access. The token is saved to `~/secrets/gcal_token.json`.

6. Add `get_calendar` to your profile's `tools.txt`, then restart the app:

   ```bash
   curl -s -X POST http://localhost:8000/api/apps/restart-current-app
   ```

Settings in `companion.env`: `CALENDAR_TIMEZONE`, `CALENDAR_ID`, and `CALENDAR_SECRETS_DIR` (default `/home/pollen/secrets`).

Consider pairing this tool with a privacy rule in your persona so the robot only reads your schedule aloud after it recognizes you. The persona template includes one.
