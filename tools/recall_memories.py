"""Let the robot retrieve his own memories from the memory store on demand."""
import json
import logging
import os
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
MEMORY_DIR = Path(_cfg("MEMORY_DIR", "/home/pollen/companion-memories"))
MEMORY_FILES = [
    MEMORY_DIR / "permanent-memories.jsonl",
    MEMORY_DIR / "memories.jsonl",
]


def _load_memories():
    memories = []
    for path in MEMORY_FILES:
        if not path.exists():
            continue
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    memories.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return memories


def _format(m):
    date = m.get("source_date") or m.get("extracted_at") or ""
    text = m.get("memory") or m.get("text") or m.get("content") or ""
    return f"[{date}] {text}".strip()


class RecallMemories(Tool):
    name = "recall_memories"
    description = (
        f"Retrieve your own memories of past conversations with {OWNER} and others. "
        f"Use this when {OWNER} refers to the past with cues like 'remember when', "
        "'last week', 'yesterday', or asks what you recall about a topic, person, or event. "
        "Pass query='<keywords>' to search your memories for a topic, "
        "or query='recent' to get your most recent memories. "
        "Use the results naturally as your own recollection. Do not list or recite them mechanically."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keywords to search memories for, or 'recent' for the latest memories.",
            },
        },
        "required": ["query"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        query = kwargs.get("query", "").strip()
        if not query:
            return {"error": "query is required. Use keywords or 'recent'."}
        try:
            memories = _load_memories()
            if not memories:
                return {"error": "No memories found in the store."}
            if query.lower() == "recent":
                selected = memories[-3:]
                logger.info(f"Tool call: recall_memories recent returned {len(selected)}")
                return {"memories": [_format(m) for m in selected]}
            terms = [t for t in query.lower().split() if len(t) > 1]
            scored = []
            for m in memories:
                blob = _format(m).lower()
                hits = sum(1 for t in terms if t in blob)
                if hits > 0:
                    scored.append((hits, _format(m)))
            scored.sort(key=lambda x: x[0], reverse=True)
            matches = [text for _, text in scored[:5]]
            logger.info(f"Tool call: recall_memories query='{query}' returned {len(matches)}")
            if not matches:
                return {"result": f"No memories found matching '{query}'."}
            return {"memories": matches}
        except Exception as e:
            logger.error(f"recall_memories failed: {e}")
            return {"error": f"Could not retrieve memories: {e}"}
