"""Query and set the Reachy Mini's microphone capture gain."""
import logging
import os
import re
import subprocess
from typing import Any, Dict
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


class MicGain(Tool):
    """Query or set the microphone capture gain on the Reachy Mini."""

    name = "mic_gain"
    description = (
        "Query or adjust the microphone capture gain on the Reachy Mini. "
        f"Use this when {OWNER} reports trouble being heard, asks about the "
        "current mic level, or asks to turn the mic up or down. Call with "
        "no arguments to report the current level. Pass a level between 0 "
        "and 100 to set it. Default is 100% (maximum sensitivity)."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "level": {
                "type": "integer",
                "description": (
                    "Optional. Target mic gain as a percentage from 0 to 100. "
                    "Omit to query the current level instead of setting it."
                ),
                "minimum": 0,
                "maximum": 100,
            },
        },
        "required": [],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        """Query the current mic gain, or set it if a level is provided."""
        level = kwargs.get("level")
        if level is None:
            return self._get_current_gain()
        return self._set_gain(int(level))

    def _get_current_gain(self) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                ["amixer", "get", "Headset,1"],
                capture_output=True, text=True, timeout=5,
            )
        except subprocess.TimeoutExpired:
            logger.warning("Tool call: mic_gain query -> timeout")
            return {"error": "Timed out reading mic gain."}
        except FileNotFoundError:
            logger.warning("Tool call: mic_gain query -> amixer not found")
            return {"error": "amixer is not available."}

        if result.returncode != 0:
            err = result.stderr.strip() or "unknown error"
            logger.warning(f"Tool call: mic_gain query -> {err}")
            return {"error": f"Could not read mic gain: {err}"}

        match = re.search(r"Capture \d+ \[(\d+)%\]", result.stdout)
        if not match:
            return {"error": "Could not parse mic gain output."}

        current = int(match.group(1))
        logger.info(f"Tool call: mic_gain query -> {current}%")
        return {"level": current, "status": "current"}

    def _set_gain(self, level: int) -> Dict[str, Any]:
        if not 0 <= level <= 100:
            return {"error": f"Level must be between 0 and 100, got {level}."}

        try:
            result = subprocess.run(
                ["amixer", "sset", "Headset,1", f"{level}%"],
                capture_output=True, text=True, timeout=5,
            )
        except subprocess.TimeoutExpired:
            logger.warning("Tool call: mic_gain set -> timeout")
            return {"error": "Timed out setting mic gain."}
        except FileNotFoundError:
            logger.warning("Tool call: mic_gain set -> amixer not found")
            return {"error": "amixer is not available."}

        if result.returncode != 0:
            err = result.stderr.strip() or "unknown error"
            logger.warning(f"Tool call: mic_gain set -> {err}")
            return {"error": f"Could not set mic gain: {err}"}

        match = re.search(r"Capture \d+ \[(\d+)%\]", result.stdout)
        actual = int(match.group(1)) if match else level
        logger.info(f"Tool call: mic_gain set -> requested {level}%, actual {actual}%")
        return {"requested_level": level, "actual_level": actual, "status": "set"}