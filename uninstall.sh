#!/bin/bash
# Remove the reachy-aiden services and commands from the robot.
# Run ON THE ROBOT as the pollen user:  bash uninstall.sh
#
# Kept on purpose (delete by hand if you want them gone):
#   /home/pollen/profiles/<ROBOT_NAME>   your persona
#   /home/pollen/companion-memories     memories
#   /home/pollen/conversation-logs      conversation logs
#   /etc/reachy-companion               config with your API keys
#
# The small code changes inside the conversation app stay until the app is
# reinstalled or updated from the Reachy Mini desktop app. Backups of the
# original files are in /home/pollen/companion-backups/.
set -u
UNITS="companion-boot-guard.service reachy-mini-conversation-autostart.service companion-mic-unmute.service
conversation-logger.service instructions-watcher.service memory-catchup.service memory-summarizer.service
memory-summarizer.timer wifi-reconnect-watchdog.service"
for u in $UNITS; do
    sudo systemctl disable --now "$u" >/dev/null 2>&1
    sudo rm -f "/etc/systemd/system/$u"
done
sudo systemctl daemon-reload
for c in companion-switch companion-reapply companion-status companion-add-memory; do
    sudo rm -f "/usr/local/bin/$c"
done
LAUNCHER=/venvs/mini_daemon/lib/python3.12/site-packages/reachy_mini/daemon/app/services/wireless/launcher.sh
if [ -f "$LAUNCHER" ]; then
    sudo sed -i '/# >>> reachy-companion >>>/,/# <<< reachy-companion <<</d' "$LAUNCHER"
fi
echo "Services and commands removed. The companion tools in /home/pollen/tools and"
echo "scripts in /home/pollen/companion are still there; delete them by hand if you wish."
echo "Restart the robot software:  sudo systemctl restart reachy-mini-daemon"
