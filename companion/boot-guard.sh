#!/bin/bash
# Runs at every boot, before the conversation app starts.
# If a Pollen update replaced any companion change, put it back.
# apply_patches.py exits 2 when it changed something.
/venvs/apps_venv/bin/python /home/pollen/companion/apply_patches.py
rc=$?
if [ "$rc" = "2" ]; then
    logger -t companion-boot-guard "Companion changes were re-applied after an update. Restarting the daemon to load them."
    # The launcher settings only take effect when the daemon starts.
    systemctl restart reachy-mini-daemon.service
    exit 0
fi
exit $rc
