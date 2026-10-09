#!/usr/bin/env python3
"""Catch up any missed summarization runs at boot, and refresh today's memories.

For each conversation log file:
  - Past days that have not been processed yet get summarized normally.
  - Today is always re-processed so memories reflect the latest transcript,
    not whatever was extracted in an earlier session.

Today's re-extraction is done safely: we capture a timestamp threshold before
running the summarizer, let it append the new entries, then remove any earlier
today entries whose extracted_at is older than the threshold. If the summarizer
call fails, no entries are removed, and the robot keeps the previous extraction
rather than losing today's memories.

Memories are read during conversation by the recall_memories tool, so
nothing needs to be written into the persona file.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(os.environ.get("CONVERSATION_LOG_DIR", "/home/pollen/conversation-logs"))
MEMORY_FILE = Path(os.environ.get("MEMORY_DIR", "/home/pollen/companion-memories")) / "memories.jsonl"
SUMMARIZER = str(Path(__file__).resolve().parent / "memory-summarizer.py")
PYTHON = "/venvs/apps_venv/bin/python"
TODAY = datetime.now().strftime("%Y-%m-%d")


def get_processed_dates():
    if not MEMORY_FILE.exists():
        return set()
    dates = set()
    with open(MEMORY_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if "source_date" in entry:
                    dates.add(entry["source_date"])
            except Exception:
                continue
    return dates


def purge_today_entries_before(threshold):
    """Remove entries with source_date == TODAY and extracted_at < threshold.

    Returns the number of entries removed. Leaves entries with later
    extracted_at timestamps (the fresh extraction we just ran) in place.
    """
    if not MEMORY_FILE.exists():
        return 0
    kept_lines = []
    removed = 0
    with open(MEMORY_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if (entry.get("source_date") == TODAY
                        and entry.get("extracted_at", "") < threshold):
                    removed += 1
                    continue
                kept_lines.append(line)
            except Exception:
                # Preserve unparseable lines so we never silently drop data
                kept_lines.append(line)
    with open(MEMORY_FILE, "w") as f:
        for line in kept_lines:
            f.write(line + "\n")
    return removed


def main():
    if os.environ.get("MEMORY_ENABLED", "1") == "0" or not os.environ.get("OPENAI_API_KEY"):
        print("Memory extraction is off (MEMORY_ENABLED=0 or no OPENAI_API_KEY).")
        return
    processed = get_processed_dates()
    pattern = re.compile(r"conversation-(\d{4}-\d{2}-\d{2})\.jsonl")
    log_files = sorted(LOG_DIR.glob("conversation-*.jsonl"))

    # Build the list of dates to process: any past day not yet in the memory
    # store, plus today (always, if its log exists).
    to_process = []
    for log_file in log_files:
        match = pattern.match(log_file.name)
        if not match:
            continue
        date = match.group(1)
        if date == TODAY:
            to_process.append(date)
        elif date not in processed:
            to_process.append(date)

    if not to_process:
        print("No days to process.")
    else:
        print(f"Processing {len(to_process)} day(s): {', '.join(to_process)}")

    # Capture the threshold BEFORE running the summarizer for today, so that
    # the new today entries (with extracted_at > threshold) survive the purge
    # and only the older today entries get removed.
    today_threshold = datetime.now().isoformat() if TODAY in to_process else None
    today_succeeded = False

    for date in to_process:
        print(f"Running summarizer for {date}...")
        result = subprocess.run(
            [PYTHON, SUMMARIZER, date],
            capture_output=True, text=True,
        )
        print(result.stdout.strip())
        if result.returncode != 0:
            print(f"Failed for {date}: {result.stderr.strip()}", file=sys.stderr)
        elif date == TODAY:
            today_succeeded = True

    # Only purge old today entries if the fresh extraction actually succeeded.
    # On failure we keep the previous extraction so the robot has something current.
    if today_threshold and today_succeeded:
        removed = purge_today_entries_before(today_threshold)
        if removed:
            print(f"Replaced {removed} older entries for {TODAY} with the fresh extraction.")


if __name__ == "__main__":
    main()