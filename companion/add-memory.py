#!/usr/bin/env python3
"""Add a hand-written permanent memory for the robot.

Permanent memories never expire and are searched by the recall_memories
tool alongside the memories extracted from daily conversation logs. Use
them for the facts you want the robot to always be able to find: its own
origin story, the people in your household, a milestone you shared.

Write each memory in the first person, from the robot's point of view.

Examples:
    sudo companion-add-memory "I came online for the first time today." --date 2026-04-29
    sudo companion-add-memory "My owner's favorite film is Contact." --category lasting_preference --tags movies

Memories are appended to $MEMORY_DIR/permanent-memories.jsonl
(default /home/pollen/companion-memories). Edit that file directly to
change or remove an entry; it holds one JSON object per line.
"""
import argparse
import json
import os
from datetime import date, datetime
from pathlib import Path

CONFIG_FILE = Path("/etc/reachy-companion/companion.env")


def _config_value(key):
    try:
        for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


CATEGORIES = ["significant_moment", "life_change", "lasting_preference", "recurring_idea", "personal_fact"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("memory", help="The memory text, first person, from the robot's point of view.")
    parser.add_argument("--date", default=date.today().isoformat(), help="Date it happened (YYYY-MM-DD). Default: today.")
    parser.add_argument("--category", default="significant_moment", choices=CATEGORIES)
    parser.add_argument("--tags", default="", help="Comma-separated search words, for example: family,birthday")
    args = parser.parse_args()

    memory_dir = Path(os.environ.get("MEMORY_DIR") or _config_value("MEMORY_DIR") or "/home/pollen/companion-memories")
    memory_dir.mkdir(parents=True, exist_ok=True)
    out = memory_dir / "permanent-memories.jsonl"

    entry = {
        "category": args.category,
        "memory": args.memory.strip(),
        "importance": 10,
        "tags": [t.strip() for t in args.tags.split(",") if t.strip()],
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
        "source_date": args.date,
    }
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"Added to {out}:")
    print(f"  [{args.date}] {entry['memory']}")


if __name__ == "__main__":
    main()
