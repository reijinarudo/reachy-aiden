#!/bin/bash
# reachy-aiden installer. Run ON THE ROBOT, as the pollen user, from the
# folder this file is in:
#
#     cd ~/reachy-aiden
#     cp .env.example companion.env      # then edit companion.env
#     bash install.sh
#
# Safe to run again. It never overwrites an existing persona, memories, or
# /etc/reachy-companion/companion.env (unless you pass --replace-config).
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
CONF_DIR=/etc/reachy-companion
CONF="$CONF_DIR/companion.env"
HOME_DIR=/home/pollen
COMPANION_DIR="$HOME_DIR/companion"
TOOLS_DIR="$HOME_DIR/tools"
PROFILES_DIR="$HOME_DIR/profiles"
APPS_PY=/venvs/apps_venv/bin/python

say()  { printf '\n== %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
say "Checking that this is a Reachy Mini Wireless"
[ -d /venvs/apps_venv ] || fail "/venvs/apps_venv not found. Run this on the robot (ssh pollen@reachy-mini.local)."
[ -x "$APPS_PY" ] || fail "$APPS_PY not found."
[ "$(id -un)" = "pollen" ] || fail "Run as the pollen user (not with sudo). The script asks for sudo when it needs it."
ls /venvs/apps_venv/lib/python3.12/site-packages/reachy_mini_conversation_app >/dev/null 2>&1 \
    || fail "The conversation app is not installed. Install 'Reachy Mini Conversation App' from the Reachy Mini desktop app first, run it once, then try again."
systemctl list-unit-files reachy-mini-daemon.service >/dev/null 2>&1 || fail "reachy-mini-daemon.service not found."
echo "OK"

# ---------------------------------------------------------------------------
say "Configuration"
sudo mkdir -p "$CONF_DIR"
if sudo test -f "$CONF" && [ "${1:-}" != "--replace-config" ]; then
    echo "Using existing $CONF (edit that file to change settings)."
    echo "To overwrite it with ./companion.env instead, run: bash install.sh --replace-config"
elif [ -f "$REPO/companion.env" ]; then
    if sudo test -f "$CONF"; then
        sudo cp "$CONF" "$CONF.bak.$(date +%Y%m%d-%H%M%S)"
        echo "Existing $CONF backed up."
    fi
    sudo cp "$REPO/companion.env" "$CONF"
    echo "Copied companion.env to $CONF"
    echo "You can now delete ./companion.env from this folder; the robot uses $CONF."
else
    fail "No companion.env found. Run: cp .env.example companion.env, edit it, then run bash install.sh again."
fi
sudo chown root:pollen "$CONF"
sudo chmod 640 "$CONF"

# Read the few values the installer needs.
cfg() { sudo grep -E "^$1=" "$CONF" | tail -1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//'; }
ROBOT_NAME="$(cfg ROBOT_NAME)"
OWNER_NAME="$(cfg OWNER_NAME)"
[ -n "$ROBOT_NAME" ] || fail "ROBOT_NAME is empty in companion.env."
[[ "$ROBOT_NAME" =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]] || fail "ROBOT_NAME must be one word (letters, numbers, - or _)."
[ -n "$OWNER_NAME" ] || OWNER_NAME="my owner"
echo "Robot: $ROBOT_NAME   Owner: $OWNER_NAME   Backend: $(cfg BACKEND_PROVIDER)"

# ---------------------------------------------------------------------------
say "Installing system packages (inotify-tools for the persona watcher)"
if ! command -v inotifywait >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y -qq inotify-tools
fi
echo "OK"

# ---------------------------------------------------------------------------
say "Creating folders"
mkdir -p "$COMPANION_DIR/patch-files" "$TOOLS_DIR" "$PROFILES_DIR" \
         "$HOME_DIR/conversation-logs" "$HOME_DIR/companion-memories"
echo "OK"

# ---------------------------------------------------------------------------
say "Profile (persona) for $ROBOT_NAME"
PROFILE="$PROFILES_DIR/$ROBOT_NAME"
if [ -f "$PROFILE/instructions.txt" ]; then
    echo "$PROFILE already exists. Leaving your persona untouched."
else
    mkdir -p "$PROFILE"
    for f in instructions.txt extraction-prompt.txt architecture-details.txt tools.txt voice.txt; do
        ROBOT_NAME="$ROBOT_NAME" OWNER_NAME="$OWNER_NAME" "$APPS_PY" - "$REPO/profile_template/$f" "$PROFILE/$f" <<'PY'
import os, sys, datetime
text = open(sys.argv[1], encoding="utf-8").read()
text = (text.replace("{ROBOT_NAME}", os.environ["ROBOT_NAME"])
            .replace("{OWNER_NAME}", os.environ["OWNER_NAME"])
            .replace("{DATE}", datetime.date.today().isoformat()))
open(sys.argv[2], "w", encoding="utf-8").write(text)
PY
    done
    echo "Created $PROFILE from the template."
    echo "Edit $PROFILE/instructions.txt and fill in every {PLACEHOLDER}."
fi

# ---------------------------------------------------------------------------
say "Companion tools -> $TOOLS_DIR"
for f in "$REPO"/tools/*.py; do
    name="$(basename "$f")"
    if [ -f "$TOOLS_DIR/$name" ] && ! cmp -s "$f" "$TOOLS_DIR/$name"; then
        cp "$TOOLS_DIR/$name" "$TOOLS_DIR/$name.bak.$(date +%Y%m%d-%H%M%S)"
        echo "  backed up your existing $name"
    fi
    cp "$f" "$TOOLS_DIR/$name"
    echo "  $name"
done
# Backup copies must not end in .py, or the app would try to load them as tools.

# ---------------------------------------------------------------------------
say "Companion scripts -> $COMPANION_DIR"
cp "$REPO"/companion/*.py "$REPO"/companion/*.sh "$COMPANION_DIR/"
cp "$REPO"/patches/files/* "$COMPANION_DIR/patch-files/"
chmod +x "$COMPANION_DIR"/*.sh "$COMPANION_DIR"/*.py
echo "OK"

# ---------------------------------------------------------------------------
say "Commands -> /usr/local/bin"
for f in "$REPO"/bin/*; do
    sudo install -m 755 "$f" "/usr/local/bin/$(basename "$f")"
    echo "  $(basename "$f")"
done

# ---------------------------------------------------------------------------
say "System services"
for f in "$REPO"/systemd/*; do
    sudo install -m 644 "$f" "/etc/systemd/system/$(basename "$f")"
    echo "  $(basename "$f")"
done
sudo systemctl daemon-reload
sudo systemctl enable companion-boot-guard.service reachy-mini-conversation-autostart.service \
    companion-mic-unmute.service conversation-logger.service instructions-watcher.service \
    memory-catchup.service memory-summarizer.timer >/dev/null 2>&1
sudo systemctl restart conversation-logger.service instructions-watcher.service
sudo systemctl start memory-summarizer.timer
echo "Enabled."

# ---------------------------------------------------------------------------
say "Applying changes to the conversation app"
set +e
sudo "$APPS_PY" "$COMPANION_DIR/apply_patches.py"
rc=$?
set -e
[ "$rc" = "0" ] || [ "$rc" = "2" ] || fail "apply_patches.py reported an error (exit $rc). See the messages above."

# ---------------------------------------------------------------------------
say "Done"
cat <<EOF
Next steps:
  1. Edit your persona:  $PROFILE/instructions.txt
     (fill in every {PLACEHOLDER}; keep the "When I Speak" and "Closing Anchor" sections)
  2. Restart the robot software so everything loads:
       sudo systemctl restart reachy-mini-daemon
     Then wait about a minute. The app starts on its own and $ROBOT_NAME
     says "$(cfg COMPANION_GREETING)".
  3. Check health any time:   companion-status
     Switch backend:          companion-switch huggingface | openai | gemini
     After a Pollen update:   sudo companion-reapply
EOF
