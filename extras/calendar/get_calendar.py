"""
get_calendar.py: read-only Google Calendar tool for a Reachy Mini companion.

Reads today's events from Google Calendar and returns a trimmed, read-only
summary. Matches the Tool interface used by get_time.py and weather.py:
  - subclasses Tool from core_tools.py
  - declares a parameters_schema attribute (empty: takes no arguments)
  - implements async __call__(self, deps, **kwargs) returning a dict

Design principles:
  - READ ONLY. Scope is calendar.readonly. No insert/delete exists.
  - TRIMMED VIEW. Only title + time reach the model. Location, notes,
    attendees, and description are dropped before anything enters context
    (and therefore before anything is sent to the HF provider).
  - VISIBILITY FILTER. Events whose Google "visibility" is "private" are
    hidden entirely. Set per-event in the Google Calendar UI.

Credential files (created by you, not by the robot):
  /home/pollen/secrets/gcal_client.json   (OAuth client, downloaded from Google)
  /home/pollen/secrets/gcal_token.json    (written by the --authorize step)

Authorize once (headless, via SSH tunnel):
  /venvs/apps_venv/bin/python /home/pollen/tools/get_calendar.py --authorize
See extras/calendar/README.md in the reachy-aiden repository.
"""

import os
import sys
import logging
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any, Dict

from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies

logger = logging.getLogger(__name__)

# --- Configuration ----------------------------------------------------------
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


SECRETS_DIR = Path(_cfg("CALENDAR_SECRETS_DIR", "/home/pollen/secrets"))
CLIENT_SECRET = SECRETS_DIR / "gcal_client.json"
TOKEN_FILE = SECRETS_DIR / "gcal_token.json"

# Read-only. Do not widen. If changed, delete the token and re-authorize.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

LOCAL_TZ = ZoneInfo(_cfg("CALENDAR_TIMEZONE", "America/New_York"))

# Which calendar to read. "primary" is the main calendar. To limit what the
# robot can see, create a separate calendar and put its ID in CALENDAR_ID.
CALENDAR_ID = _cfg("CALENDAR_ID", "primary")


def _get_service():
    """Build an authenticated, read-only Calendar service from the stored token."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    if not TOKEN_FILE.exists():
        raise RuntimeError(
            "No calendar token found. Run with --authorize once to grant "
            "read-only access."
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _trim_event(event):
    """Reduce a raw Google event to title and time only. Drop private events."""
    if event.get("visibility") == "private":
        return None

    summary = event.get("summary", "(untitled)")

    start = event.get("start", {})
    if "dateTime" in start:
        dt = datetime.datetime.fromisoformat(start["dateTime"])
        when = dt.astimezone(LOCAL_TZ).strftime("%-I:%M %p")
    elif "date" in start:
        when = "all day"
    else:
        when = "time unknown"

    return {"title": summary, "when": when}


MAX_DAYS = 14
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _resolve_start_date(date_str):
    """Map 'today', 'tomorrow', a weekday name, or YYYY-MM-DD to a local date. Raises ValueError."""
    today = datetime.datetime.now(LOCAL_TZ).date()
    value = (date_str or "today").strip().lower()
    if value in ("", "today"):
        return today
    if value == "tomorrow":
        return today + datetime.timedelta(days=1)
    if value == "yesterday":
        return today - datetime.timedelta(days=1)
    if value.startswith("next "):
        value = value[5:].strip()
    if value in WEEKDAYS:
        # Next occurrence of that weekday, counting today.
        ahead = (WEEKDAYS.index(value) - today.weekday()) % 7
        return today + datetime.timedelta(days=ahead)
    return datetime.date.fromisoformat(value)


def _day_label(day, today):
    if day == today:
        return "Today"
    if day == today + datetime.timedelta(days=1):
        return "Tomorrow"
    return day.strftime("%A, %B %-d")


def _event_date(event):
    start = event.get("start", {})
    if "dateTime" in start:
        return datetime.datetime.fromisoformat(start["dateTime"]).astimezone(LOCAL_TZ).date()
    if "date" in start:
        return datetime.date.fromisoformat(start["date"])
    return None


def _events_between(start_date, days):
    """Return trimmed, visibility-filtered events for `days` days from start_date, each tagged with its day."""
    service = _get_service()
    today = datetime.datetime.now(LOCAL_TZ).date()

    start = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=LOCAL_TZ)
    end = start + datetime.timedelta(days=days)

    result = (
        service.events()
        .list(
            calendarId=CALENDAR_ID,
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    trimmed = []
    for ev in result.get("items", []):
        t = _trim_event(ev)
        if t is not None:
            day = _event_date(ev) or start_date
            # Multi-day all-day events that began earlier are reported on the first requested day.
            t["day"] = _day_label(max(day, start_date), today)
            trimmed.append(t)
    return trimmed


def _todays_events():
    """Return today's trimmed, visibility-filtered events as a list of dicts."""
    return _events_between(datetime.datetime.now(LOCAL_TZ).date(), 1)


def _format_for_speech(events, start_label="Today", days=1):
    """Turn the trimmed list into a short natural string for the robot to read."""
    if not events:
        if days == 1:
            return f"Nothing is on the calendar {start_label.lower() if start_label in ('Today', 'Tomorrow') else 'on ' + start_label}."
        return f"Nothing is on the calendar for the {days} days starting {start_label.lower() if start_label in ('Today', 'Tomorrow') else start_label}."
    by_day = {}
    for e in events:
        if e["when"] == "all day":
            by_day.setdefault(e["day"], []).append(f"{e['title']}, all day")
        else:
            by_day.setdefault(e["day"], []).append(f"{e['title']} at {e['when']}")
    return " ".join(f"{day}: " + "; ".join(parts) + "." for day, parts in by_day.items())


class GetCalendar(Tool):
    """Get the user's schedule for a day or a span of days, read only, trimmed to titles and times."""

    name = "get_calendar"
    description = (
        "Get the user's schedule as a short summary of event titles and times. Read only. "
        "Use when the user mentions their day, plans, what they have coming up, or asks what is on their "
        "calendar. Defaults to today. Pass date='tomorrow', a weekday like 'friday', or 'YYYY-MM-DD' for "
        "another day, and days=7 for 'this week' or a longer stretch (up to 14)."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "First day to read: 'today' (default), 'tomorrow', a weekday name, or YYYY-MM-DD.",
            },
            "days": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_DAYS,
                "description": "How many days to read starting at date (default 1).",
            },
        },
        "required": [],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        """Return the requested day(s) of calendar as a trimmed summary."""
        try:
            start_date = _resolve_start_date(kwargs.get("date"))
        except ValueError:
            return {"error": f"Unrecognized date {kwargs.get('date')!r}. Use today, tomorrow, a weekday, or YYYY-MM-DD."}
        try:
            days = max(1, min(MAX_DAYS, int(kwargs.get("days") or 1)))
        except (TypeError, ValueError):
            days = 1
        try:
            events = _events_between(start_date, days)
            start_label = _day_label(start_date, datetime.datetime.now(LOCAL_TZ).date())
            summary = _format_for_speech(events, start_label, days)
            logger.info(f"Tool call: get_calendar {start_date} +{days}d -> {len(events)} event(s)")
            return {"summary": summary, "events": events}
        except Exception as e:
            logger.exception("get_calendar failed: %s", e)
            return {"summary": "I could not reach the calendar just now."}


# --- One-time interactive authorization ------------------------------------
def _authorize():
    """Run the OAuth consent flow and write the read-only token. You run this."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CLIENT_SECRET.exists():
        print(f"Missing client secret at {CLIENT_SECRET}", file=sys.stderr)
        sys.exit(1)

    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=8765, open_browser=False)
    TOKEN_FILE.write_text(creds.to_json())
    os.chmod(TOKEN_FILE, 0o600)
    print(f"Token written to {TOKEN_FILE} (read-only scope).")


if __name__ == "__main__":
    if "--authorize" in sys.argv:
        _authorize()
    else:
        for e in _todays_events():
            print(e)
        print(_format_for_speech(_todays_events()))