#!/usr/bin/env python3
"""Process a day's conversation log into memory candidates via OpenAI."""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from openai import OpenAI

ROBOT_NAME = os.environ.get("ROBOT_NAME", "Aiden")
OWNER_NAME = os.environ.get("OWNER_NAME", "User")
MODEL = os.environ.get("SUMMARIZER_MODEL", "gpt-5.4-mini")
LOG_DIR = Path(os.environ.get("CONVERSATION_LOG_DIR", "/home/pollen/conversation-logs"))
MEMORY_DIR = Path(os.environ.get("MEMORY_DIR", "/home/pollen/companion-memories"))
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_FILE = Path("/home/pollen/profiles") / ROBOT_NAME / "extraction-prompt.txt"

def _load_prompt():
    try:
        return PROMPT_FILE.read_text().strip()
    except Exception as e:
        print(f"Could not read prompt file {PROMPT_FILE}: {e}", file=sys.stderr)
        sys.exit(1)

def load_conversation(log_path):
    turns = []
    with open(log_path) as f:
        for i, line in enumerate(f, 1):
            line = line.strip().lstrip("\x00")
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception as e:
                print(f"Skipping malformed line {i}: {e}")
                continue
            role = OWNER_NAME if entry["role"] == "user" else ROBOT_NAME
            turns.append(f"{role}: {entry['content']}")
    return "\n".join(turns)

def extract_memories(transcript):
    client = OpenAI()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _load_prompt()},
            {"role": "user", "content": transcript},
        ],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    parsed = json.loads(raw)
    return parsed.get("memories", [])

def save_memories(memories, source_date):
    if not memories:
        print(f"No memories extracted for {source_date}")
        return
    memory_file = MEMORY_DIR / "memories.jsonl"
    timestamp = datetime.now().isoformat()
    with open(memory_file, "a") as f:
        for mem in memories:
            mem["extracted_at"] = timestamp
            mem["source_date"] = source_date
            f.write(json.dumps(mem) + "\n")
    print(f"Saved {len(memories)} memories from {source_date}")

def main():
    if os.environ.get("MEMORY_ENABLED", "1") == "0":
        print("MEMORY_ENABLED=0, skipping.")
        return
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set in companion.env; memory extraction skipped.")
        return
    target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    log_path = LOG_DIR / f"conversation-{target_date}.jsonl"
    if not log_path.exists():
        print(f"No log file for {target_date}")
        return
    transcript = load_conversation(log_path)
    if not transcript.strip():
        print(f"Empty conversation log for {target_date}")
        return
    print(f"Processing {target_date} ({len(transcript)} characters)...")
    memories = extract_memories(transcript)
    save_memories(memories, target_date)

if __name__ == "__main__":
    main()
