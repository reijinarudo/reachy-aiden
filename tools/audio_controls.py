"""Control Reachy Mini's speaker volume and microphone state."""
import logging
import os
import re
import subprocess
from typing import Any, Dict, Optional, Tuple

from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies

logger = logging.getLogger(__name__)

CONFIG_FILE = "/etc/reachy-companion/companion.env"


def _cfg(key: str, default: str = "") -> str:
    """Read a setting from the environment, then from the companion config file."""
    value = os.environ.get(key)
    if value:
        return value
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip("\"'") or default
    except OSError:
        pass
    return default

OWNER = _cfg("OWNER_NAME", "your owner")


def _run(cmd: list) -> Tuple[int, str, str]:
    """Run a command, return (rc, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def _read_volume_percent() -> Optional[int]:
    """Read the speaker volume as 0-100 from the ALSA PCM control. None on failure.

    The robot's voice plays straight to ALSA hw:0 (alsasink), so PCM is the level it is heard at.
    PipeWire (wpctl) only runs while someone is logged in and is not in its audio path.
    """
    rc, out, _ = _run(["amixer", "get", "PCM"])
    if rc != 0 or not out:
        return None
    # Output lines look like: "Front Left: Playback 57 [95%] [-3.00dB] [on]"
    match = re.search(r"\[(\d+)%\]", out)
    return int(match.group(1)) if match else None


def _set_volume_percent(level: int) -> Tuple[bool, str]:
    """Set the speaker volume on the ALSA PCM control (the level the robot is heard at)."""
    level = max(0, min(100, level))
    rc, _, err = _run(["amixer", "-q", "set", "PCM", f"{level}%"])
    if rc == 0:
        return True, "amixer"
    return False, f"amixer: {err}"


class SetSpeakerVolume(Tool):
    name = "set_speaker_volume"
    description = (
        "Set Reachy Mini's speaker output volume to a specific level (0 to 100). "
        f"Use when {OWNER} asks to change volume, including vague requests like 'louder' "
        "or 'quieter'. For relative requests, call get_speaker_volume first, then add or "
        "subtract: 'louder' = +20, 'much louder' = +40, 'a bit louder' = +10. "
        f"If the requested level is below 20, briefly confirm verbally first since {OWNER} "
        "may not hear your next reply. Do not narrate the action itself."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "level": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Target volume from 0 (silent) to 100 (maximum).",
            }
        },
        "required": ["level"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        level = kwargs.get("level")
        if not isinstance(level, int) or not 0 <= level <= 100:
            return {"error": f"Invalid level {level}, must be an integer 0 to 100"}
        ok, info = _set_volume_percent(level)
        if ok:
            logger.info(f"Tool call: set_speaker_volume -> {level} via {info}")
            return {"status": f"speaker volume set to {level}"}
        logger.error(f"set_speaker_volume failed: {info}")
        return {"error": f"could not set volume: {info}"}


class GetSpeakerVolume(Tool):
    name = "get_speaker_volume"
    description = (
        "Read Reachy Mini's current speaker volume as a percentage from 0 to 100. "
        "Use this internally before applying relative changes like 'louder' or 'softer' "
        "so you can compute the new target level. Do not announce the result unless "
        f"{OWNER} asked for it directly."
    )
    parameters_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        level = _read_volume_percent()
        if level is None:
            return {"error": "could not read current volume"}
        logger.info(f"Tool call: get_speaker_volume -> {level}")
        return {"volume": level}

class SetMicrophoneMute(Tool):
    name = "set_microphone_mute"
    description = (
        "Mute or unmute Reachy Mini's microphone. "
        f"Use when {OWNER} asks you to mute yourself, stop listening, unmute, or start "
        "listening. Important: once muted by this tool, you cannot be voice-unmuted, "
        f"because you will not hear the unmute command. {OWNER} must unmute via the "
        "desktop app. Confirm verbally before muting. Do not narrate the action otherwise."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "muted": {
                "type": "boolean",
                "description": "True to mute the microphone, false to unmute it.",
            }
        },
        "required": ["muted"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        muted = kwargs.get("muted")
        if not isinstance(muted, bool):
            return {"error": f"Invalid muted value {muted}, must be true or false"}
        flag = "nocap" if muted else "cap"
        rc, _, err = _run(["amixer", "-c", "0", "sset", "Headset,0", flag])
        if rc == 0:
            state = "muted" if muted else "unmuted"
            logger.info(f"Tool call: set_microphone_mute -> {state}")
            return {"status": f"microphone {state}"}
        logger.error(f"set_microphone_mute failed: {err}")
        return {"error": f"could not set mute state: {err}"}