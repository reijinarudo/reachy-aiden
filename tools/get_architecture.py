"""Retrieve sections from the robot's architecture reference (architecture-details.txt)."""
import logging
import os
import re
from pathlib import Path
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
ARCHITECTURE_FILE = Path("/home/pollen/profiles") / _cfg("ROBOT_NAME", "Aiden") / "architecture-details.txt"


def _parse_sections(content):
    sections = {}
    current_topic = None
    current_lines = []
    current_updated = None
    for line in content.splitlines():
        topic_match = re.match(r"^##\s*TOPIC:\s*(\w+)\s*$", line)
        if topic_match:
            if current_topic:
                sections[current_topic] = {
                    "content": "\n".join(current_lines).strip(),
                    "last_updated": current_updated or "unknown",
                }
            current_topic = topic_match.group(1)
            current_lines = []
            current_updated = None
            continue
        updated_match = re.match(r"^LAST_UPDATED:\s*(.+)$", line)
        if updated_match:
            current_updated = updated_match.group(1).strip()
            continue
        if current_topic:
            current_lines.append(line)
    if current_topic:
        sections[current_topic] = {
            "content": "\n".join(current_lines).strip(),
            "last_updated": current_updated or "unknown",
        }
    return sections


class GetArchitecture(Tool):
    name = "get_architecture"
    description = (
        "Retrieve technical details about your own architecture. "
        f"Use this when {OWNER} asks about your systems, services, tools, memory pipeline, "
        "recovery procedures, patches, safety limits, logging, history, network, or hardware. "
        "Pass topic='list' to see all available topics. "
        "Pass topic='<name>' to get details on a specific topic."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The topic to retrieve, or 'list' to see available topics.",
            },
        },
        "required": ["topic"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        topic = kwargs.get("topic", "").strip().lower()
        if not topic:
            return {"error": "topic is required. Use 'list' to see available topics."}
        try:
            if not ARCHITECTURE_FILE.exists():
                return {"error": f"Architecture file not found at {ARCHITECTURE_FILE}"}
            content = ARCHITECTURE_FILE.read_text()
            sections = _parse_sections(content)
            if topic == "list":
                topic_summary = []
                for name, data in sections.items():
                    first_line = data["content"].split("\n", 1)[0][:80]
                    topic_summary.append({
                        "topic": name,
                        "last_updated": data["last_updated"],
                        "preview": first_line,
                    })
                logger.info(f"Tool call: get_architecture list returned {len(topic_summary)} topics")
                return {"topics": topic_summary}
            if topic in sections:
                logger.info(f"Tool call: get_architecture topic={topic}")
                return {
                    "topic": topic,
                    "last_updated": sections[topic]["last_updated"],
                    "content": sections[topic]["content"],
                }
            return {
                "error": f"Topic '{topic}' not found",
                "available_topics": list(sections.keys()),
            }
        except Exception as e:
            logger.error(f"get_architecture failed: {e}")
            return {"error": f"Could not retrieve architecture: {e}"}
