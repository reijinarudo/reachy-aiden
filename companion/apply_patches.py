#!/usr/bin/env python3
"""Apply (or re-apply) the reachy-aiden changes to a Reachy Mini Wireless.

Pollen Robotics app and firmware updates replace the conversation app's
files and the daemon launcher. This script puts the companion changes back.
Every step checks the current file first, so running it twice is safe.

Usage (on the robot):
    sudo companion-reapply            apply everything, then report
    sudo companion-reapply --check    report only, change nothing

What it touches:
    1. The conversation app's .env    (backend, model, API keys)
    2. The profile's voice.txt         (voice that matches the backend)
    3. The daemon launcher.sh          (profile, tools folder, wake-up flag)
    4. Seven small code changes in the conversation app (see patches/reference)

Before changing a file for the first time in a run, a copy goes to
/home/pollen/companion-backups/<timestamp>/.
"""
import argparse
import hashlib
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

CONFIG_FILE = Path("/etc/reachy-companion/companion.env")
SITE = Path("/venvs/apps_venv/lib/python3.12/site-packages")
APP = SITE / "reachy_mini_conversation_app"
APP_ENV = APP / ".env"
LAUNCHER = Path(
    "/venvs/mini_daemon/lib/python3.12/site-packages/reachy_mini/daemon/app/services/wireless/launcher.sh"
)
PROFILES_DIR = Path("/home/pollen/profiles")
TOOLS_DIR = Path("/home/pollen/tools")
BACKUP_ROOT = Path("/home/pollen/companion-backups")
REPO_FILES = Path(__file__).resolve().parent.parent / "patches" / "files"
INSTALLED_FILES = Path("/home/pollen/companion/patch-files")

TESTED_APP_VERSION = "0.6.2"
UPSTREAM_MOVE_HEAD_SHA256 = "e41ca2eb514d5e5fe027b7d265c5761ade6d07c52f23a9986f6ff7700eb592af"

DEFAULT_VOICES = {"openai": "cedar", "huggingface": "Aiden", "gemini": "Kore"}

RESULTS = []
BACKUP_DIR = None
CHECK_ONLY = False


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def read_config(path=CONFIG_FILE):
    """Parse KEY=VALUE lines. Quotes around values are removed."""
    cfg = {}
    if not path.exists():
        return cfg
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        cfg[key.strip()] = value
    return cfg


def report(name, state, detail=""):
    RESULTS.append((name, state, detail))
    print(f"  [{state:<7}] {name}{(' - ' + detail) if detail else ''}")


def backup(path):
    global BACKUP_DIR
    if CHECK_ONLY or not path.exists():
        return
    if BACKUP_DIR is None:
        BACKUP_DIR = BACKUP_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / path.name
    if not dest.exists():
        shutil.copy2(path, dest)


def write(path, text):
    if CHECK_ONLY:
        return
    backup(path)
    path.write_text(text, encoding="utf-8")


def installed_app_version():
    for d in SITE.glob("reachy_mini_conversation_app-*.dist-info"):
        return d.name[len("reachy_mini_conversation_app-"):-len(".dist-info")]
    return "unknown"


# --------------------------------------------------------------------------
# 1. App .env and voice
# --------------------------------------------------------------------------
def sync_app_env(cfg):
    backend = cfg.get("BACKEND_PROVIDER", "huggingface").strip().lower() or "huggingface"
    if backend not in DEFAULT_VOICES:
        report("App .env", "ERROR", f"BACKEND_PROVIDER={backend!r} must be openai, huggingface, or gemini")
        return

    wanted = {"BACKEND_PROVIDER": backend}
    if backend == "openai":
        wanted["MODEL_NAME"] = cfg.get("OPENAI_MODEL", "")
    elif backend == "gemini":
        wanted["MODEL_NAME"] = cfg.get("GEMINI_MODEL", "")
    else:
        wanted["MODEL_NAME"] = ""
        # The Hugging Face provider name says nothing about where traffic goes.
        # The connection mode decides it: deployed = Pollen's cloud server,
        # local = your own server at HF_REALTIME_WS_URL.
        wanted["HF_REALTIME_CONNECTION_MODE"] = cfg.get("HF_REALTIME_CONNECTION_MODE", "deployed") or "deployed"
        if wanted["HF_REALTIME_CONNECTION_MODE"] == "local":
            wanted["HF_REALTIME_WS_URL"] = cfg.get("HF_REALTIME_WS_URL", "")
    for key in ("OPENAI_API_KEY", "GEMINI_API_KEY", "HF_TOKEN"):
        if cfg.get(key):
            wanted[key] = cfg[key]

    lines = APP_ENV.read_text(encoding="utf-8").splitlines() if APP_ENV.exists() else []
    seen = set()
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in wanted:
            out.append(f"{key}={wanted[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in wanted.items():
        if key not in seen:
            out.append(f"{key}={value}")
    new_text = "\n".join(out) + "\n"

    if APP_ENV.exists() and APP_ENV.read_text(encoding="utf-8") == new_text:
        report("App .env", "OK", f"backend={backend}")
    else:
        write(APP_ENV, new_text)
        report("App .env", "APPLIED", f"backend={backend}")


def sync_voice(cfg):
    backend = cfg.get("BACKEND_PROVIDER", "huggingface").strip().lower() or "huggingface"
    name = cfg.get("ROBOT_NAME", "")
    if not name or backend not in DEFAULT_VOICES:
        report("Profile voice.txt", "SKIPPED", "ROBOT_NAME or BACKEND_PROVIDER missing")
        return
    voice = cfg.get(f"VOICE_{backend.upper()}", "") or DEFAULT_VOICES[backend]
    voice_file = PROFILES_DIR / name / "voice.txt"
    if not voice_file.parent.exists():
        report("Profile voice.txt", "ERROR", f"profile folder {voice_file.parent} not found")
        return
    if voice_file.exists() and voice_file.read_text(encoding="utf-8").strip() == voice:
        report("Profile voice.txt", "OK", voice)
        return
    write(voice_file, voice + "\n")
    report("Profile voice.txt", "APPLIED", voice)


# --------------------------------------------------------------------------
# 2. Daemon launcher
# --------------------------------------------------------------------------
BLOCK_START = "# >>> reachy-companion >>>"
BLOCK_END = "# <<< reachy-companion <<<"


def patch_launcher(cfg):
    if not LAUNCHER.exists():
        report("Daemon launcher", "ERROR", f"{LAUNCHER} not found")
        return
    name = cfg.get("ROBOT_NAME", "")
    greeting = cfg.get("COMPANION_GREETING", "Hello world.").replace('"', "")
    block = "\n".join([
        BLOCK_START,
        f"export REACHY_MINI_CUSTOM_PROFILE={name}",
        f"export REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY={PROFILES_DIR}",
        f"export REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY={TOOLS_DIR}",
        "export AUTOLOAD_EXTERNAL_TOOLS=1",
        f'export COMPANION_GREETING="{greeting}"',
        BLOCK_END,
    ]) + "\n"

    body = LAUNCHER.read_text(encoding="utf-8")
    original = body
    body = body.replace("--no-wake-up-on-start", "--wake-up-on-start")
    body = re.sub(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END) + r"\n?", "", body, flags=re.S)
    anchor = "# Run Python in unbuffered mode"
    if anchor in body:
        body = body.replace(anchor, block + anchor, 1)
    else:
        first_newline = body.find("\n") + 1 if body.startswith("#!") else 0
        body = body[:first_newline] + block + body[first_newline:]

    if body == original:
        report("Daemon launcher", "OK", f"profile={name}, wake-up on start")
    else:
        write(LAUNCHER, body)
        report("Daemon launcher", "APPLIED", f"profile={name}, wake-up on start")


# --------------------------------------------------------------------------
# 3. Code changes in the conversation app
# --------------------------------------------------------------------------
def replace_once(label, path, done_marker, old, new, legacy_marker=None):
    """Swap `old` for `new` in `path` unless `done_marker` is already there."""
    if not path.exists():
        report(label, "ERROR", f"{path.name} not found")
        return
    text = path.read_text(encoding="utf-8")
    if done_marker in text or (legacy_marker and legacy_marker in text):
        report(label, "OK")
        return
    if old not in text:
        report(label, "WARNING", f"expected code not found in {path.name}; app version changed? Left unchanged")
        return
    write(path, text.replace(old, new, 1))
    report(label, "APPLIED")


GREETING_OLD = (
    '                response_sender_task = asyncio.create_task(self._response_sender_loop(), name="response-sender")\n'
    "\n"
)
GREETING_NEW = (
    '                response_sender_task = asyncio.create_task(self._response_sender_loop(), name="response-sender")\n'
    "                # reachy-companion: speak a fixed greeting when a session opens (COMPANION_GREETING).\n"
    '                _companion_greeting = __import__("os").getenv("COMPANION_GREETING", "").strip()\n'
    "                if _companion_greeting:\n"
    "                    await self._safe_response_create(response={\"instructions\": f\"Say exactly: {_companion_greeting} Nothing else. No commentary. No additional words.\"})\n"
    "\n"
)

TRACKING_OLD = """                            with self.face_tracking_lock:
                                self.face_tracking_offsets = [
                                    translation[0],
                                    translation[1],
                                    translation[2],
                                    rotation[0],
                                    rotation[1],
                                    rotation[2],
                                ]
"""
TRACKING_NEW = """                            smoothing = 0.15  # reachy-companion: ease toward the face instead of jumping
                            with self.face_tracking_lock:
                                self.face_tracking_offsets = [
                                    self.face_tracking_offsets[0] * (1 - smoothing) + translation[0] * smoothing,
                                    self.face_tracking_offsets[1] * (1 - smoothing) + translation[1] * smoothing,
                                    self.face_tracking_offsets[2] * (1 - smoothing) + translation[2] * smoothing,
                                    self.face_tracking_offsets[3] * (1 - smoothing) + rotation[0] * smoothing,
                                    self.face_tracking_offsets[4] * (1 - smoothing) + rotation[1] * smoothing,
                                    self.face_tracking_offsets[5] * (1 - smoothing) + rotation[2] * smoothing,
                                ]
"""


def patch_vad(label, path, settings):
    """Set the server voice-activity-detection values (turn-taking timing)."""
    if not path.exists():
        report(label, "ERROR", f"{path.name} not found")
        return
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r'ServerVad\(type="server_vad", interrupt_response=True[^)]*\)')
    match = pattern.search(text)
    if not match:
        report(label, "WARNING", f"turn detection code not found in {path.name}; left unchanged")
        return
    wanted = 'ServerVad(type="server_vad", interrupt_response=True, ' + ", ".join(
        f"{k}={v}" for k, v in settings
    ) + ")"
    if match.group(0) == wanted:
        report(label, "OK", ", ".join(f"{k}={v}" for k, v in settings))
        return
    write(path, text[: match.start()] + wanted + text[match.end():])
    report(label, "APPLIED", ", ".join(f"{k}={v}" for k, v in settings))


def patch_move_head():
    label = "move_head tool (center first, gentler down)"
    target = APP / "tools" / "move_head.py"
    source = INSTALLED_FILES / "move_head.py"
    if not source.exists():
        source = REPO_FILES / "move_head.py"
    if not target.exists() or not source.exists():
        report(label, "ERROR", "file missing")
        return
    current = target.read_bytes()
    ours = source.read_bytes()
    if current == ours or b"HOME_DURATION" in current:
        report(label, "OK")
        return
    if hashlib.sha256(current).hexdigest() != UPSTREAM_MOVE_HEAD_SHA256:
        report(label, "WARNING", "move_head.py differs from the tested 0.6.2 version; left unchanged")
        return
    if not CHECK_ONLY:
        backup(target)
        target.write_bytes(ours)
    report(label, "APPLIED")


def apply_code_patches(cfg):
    replace_once(
        "Session greeting (COMPANION_GREETING)",
        APP / "base_realtime.py",
        "COMPANION_GREETING",
        GREETING_OLD,
        GREETING_NEW,
        legacy_marker="Say exactly: Hello world",
    )
    patch_vad(
        "OpenAI turn-taking",
        APP / "openai_realtime.py",
        [
            ("silence_duration_ms", cfg.get("OPENAI_SILENCE_MS", "800")),
            ("threshold", cfg.get("OPENAI_VAD_THRESHOLD", "0.7")),
        ],
    )
    patch_vad(
        "Hugging Face turn-taking",
        APP / "huggingface_realtime.py",
        [
            ("threshold", cfg.get("HF_VAD_THRESHOLD", "0.7")),
            ("prefix_padding_ms", cfg.get("HF_PREFIX_PADDING_MS", "300")),
            ("silence_duration_ms", cfg.get("HF_SILENCE_MS", "1200")),
        ],
    )
    replace_once(
        "Face tracking off at start",
        APP / "camera_worker.py",
        "self.is_head_tracking_enabled = False",
        "self.is_head_tracking_enabled = True",
        "self.is_head_tracking_enabled = False",
    )
    replace_once(
        "Face tracking smoothing",
        APP / "camera_worker.py",
        "smoothing = 0.15",
        TRACKING_OLD,
        TRACKING_NEW,
    )
    replace_once(
        "Full-length transcript logging (needed by the conversation logger)",
        APP / "console.py",
        "                            content,\n                        )",
        '                            content if len(content) < 500 else content[:500] + "…",\n',
        "                            content,\n",
    )
    replace_once(
        "Head tracker default = mediapipe",
        APP / "utils.py",
        'choices=["yolo", "mediapipe"],\n        default="mediapipe",',
        'choices=["yolo", "mediapipe"],\n        default=None,',
        'choices=["yolo", "mediapipe"],\n        default="mediapipe",',
    )
    patch_move_head()


# --------------------------------------------------------------------------
def main():
    global CHECK_ONLY
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report only, change nothing")
    args = parser.parse_args()
    CHECK_ONLY = args.check

    cfg = read_config(CONFIG_FILE)
    if not cfg:
        print(f"ERROR: {CONFIG_FILE} is missing or empty. Run install.sh first.")
        sys.exit(1)

    version = installed_app_version()
    print("reachy-companion patch check" + (" (report only)" if CHECK_ONLY else ""))
    print(f"Conversation app version: {version} (tested with {TESTED_APP_VERSION})")
    if version != TESTED_APP_VERSION:
        print("  Note: the app version differs. Each change below is applied only where the")
        print("  expected code is found; anything else is reported as WARNING and left alone.")
    print()

    sync_app_env(cfg)
    sync_voice(cfg)
    patch_launcher(cfg)
    apply_code_patches(cfg)

    applied = [r for r in RESULTS if r[1] == "APPLIED"]
    problems = [r for r in RESULTS if r[1] in ("WARNING", "ERROR")]
    print()
    if CHECK_ONLY:
        print(f"{len(applied)} change(s) would be made. {len(problems)} item(s) need attention.")
    else:
        print(f"{len(applied)} change(s) made. {len(problems)} item(s) need attention.")
        if BACKUP_DIR:
            print(f"Backups of changed files: {BACKUP_DIR}")
    if applied and not CHECK_ONLY:
        print("Restart to load the changes:  sudo systemctl restart reachy-mini-daemon")
    # Exit code 2 tells the boot guard that something changed.
    sys.exit(2 if (applied and not CHECK_ONLY) else 0)


if __name__ == "__main__":
    main()
