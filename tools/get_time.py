"""Get current local time and date."""
import logging
from datetime import datetime
from typing import Any, Dict

from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies

logger = logging.getLogger(__name__)


class GetTime(Tool):
    """Get the current local time and date."""

    name = "get_time"
    description = (
        "Get the current local time and date. "
        "Use this when the user asks what time it is, what day it is, "
        "or for any date or time information."
    )
    parameters_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        """Return the current local time and date."""
        now = datetime.now()
        time_str = now.strftime("%I:%M %p")
        date_str = now.strftime("%A, %B %d, %Y")
        logger.info(f"Tool call: get_time -> {time_str} on {date_str}")
        return {
            "time": time_str,
            "date": date_str,
        }
