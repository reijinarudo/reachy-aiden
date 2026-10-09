"""Gracefully shut down the Reachy."""
import logging
import os
import asyncio
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
ROBOT = _cfg("ROBOT_NAME", "Reachy")

class Shutdown(Tool):
    name = "shutdown"
    description = (
        "Gracefully shut down the Reachy at the end of the day. "
        f"Use this when {OWNER} says goodnight, asks you to shut down, "
        "or tells you to go to sleep for the night. "
        "The system will power off about 30 seconds after this is called. "
        "A brief spoken acknowledgment is sufficient. "
        "The tool itself is silent."
    )
    parameters_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        logger.info("Tool call: shutdown initiated by %s", ROBOT)
        try:
            await asyncio.sleep(3)
            subprocess.Popen(
                ["sudo", "/sbin/shutdown", "-P", "+1", f"{ROBOT} going to sleep"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Shutdown scheduled for +1 minute")
            return {"status": "scheduled"}
        except Exception as e:
            logger.error(f"Shutdown failed: {e}")
            return {"error": f"Could not shut down: {e}"}
