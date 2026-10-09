#!/usr/bin/env python3
"""Tail the systemd journal, buffer assistant chunks, write structured log."""
import subprocess
import re
import json
import os
import select
from datetime import datetime

# Reads the conversation app's "role=... content=..." journal lines.
# Needs the full-length logging patch in console.py (companion-reapply applies it).
LOG_DIR = os.environ.get("CONVERSATION_LOG_DIR", "/home/pollen/conversation-logs")
os.makedirs(LOG_DIR, exist_ok=True)

PATTERN = re.compile(
    r"(\w+ \d+ \d+:\d+:\d+) .*role=(user|user_partial|assistant) content=(.*)$"
)

QUIET_FLUSH_SECONDS = 1.5


def get_log_path():
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(LOG_DIR, f"conversation-{today}.jsonl")


def write_entry(role, content):
    if not content.strip():
        return
    if content.startswith("\U0001F6E0") or content.startswith('{"status":'):
        return
    entry = {
        "timestamp": datetime.now().isoformat(),
        "role": role,
        "content": content.strip(),
    }
    with open(get_log_path(), "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    proc = subprocess.Popen(
        ["journalctl", "-f", "-n", "0", "--no-pager"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    buffer_role = None
    buffer_content = []
    try:
        while True:
            ready, _, _ = select.select([proc.stdout], [], [], QUIET_FLUSH_SECONDS)
            if not ready:
                if buffer_role and buffer_content:
                    write_entry(buffer_role, " ".join(buffer_content))
                    buffer_role = None
                    buffer_content = []
                continue
            line = proc.stdout.readline()
            if not line:
                break
            match = PATTERN.search(line)
            if not match:
                continue
            _, role, content = match.groups()
            content = content.strip()
            if role == "user_partial":
                continue
            if buffer_role and role != buffer_role:
                write_entry(buffer_role, " ".join(buffer_content))
                buffer_role = None
                buffer_content = []
            if role == "assistant":
                buffer_role = "assistant"
                buffer_content.append(content)
            else:
                write_entry(role, content)
    finally:
        if buffer_role and buffer_content:
            write_entry(buffer_role, " ".join(buffer_content))
        proc.terminate()


if __name__ == "__main__":
    main()
