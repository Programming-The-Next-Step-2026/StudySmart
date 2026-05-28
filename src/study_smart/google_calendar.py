"""
Google Calendar integration for StudySmart.

Provides functions to import and export calendar events as study commitments
using the Google Calendar API with OAuth 2.0 authentication.

Note: Requires credentials.json in the repository root. See README
for setup instructions.
"""

import os
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def _find_repo_root():
    """Find repo root by looking for pyproject.toml."""
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.exists(os.path.join(current, "pyproject.toml")):
            return current
        current = os.path.dirname(current)
    return os.path.dirname(os.path.abspath(__file__))

ROOT_DIR = _find_repo_root()
CREDENTIALS_PATH = os.path.join(ROOT_DIR, "credentials.json")
TOKEN_PATH = os.path.join(ROOT_DIR, "token.json")


def _get_calendar_service():
    """Internal — authenticates and returns Google Calendar service."""
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)

def import_commitments_from_google_calendar(start_date, end_date):
    """
    Imports calendar events as commitments from Google Calendar.

    Fetches all events between start_date and end_date and converts
    them into a commitments dictionary mapping dates to blocked hours.

    Note: Requires a live Google Calendar connection and valid credentials.
    Authentication is handled via OAuth 2.0. On first run, a browser window
    will open asking the user to grant calendar access.

    Args:
        start_date (date): First day to fetch events from.
        end_date (date): Last day to fetch events until.

    Returns:
        tuple: A tuple containing two dictionaries:
            - commitments (dict): Mapping dates to total blocked hours that day.
            - event_name (dict): Mapping dates to lists of event titles.

    Example:
        >>> from datetime import date
        >>> from study_smart.google_calendar import import_commitments_from_google_calendar
        >>> commitments, event_name = import_commitments_from_google_calendar(
        ...     start_date=date(2026, 5, 13),
        ...     end_date=date(2026, 6, 5)
        ... )
    """
    service = _get_calendar_service()

    start = datetime.combine(start_date, datetime.min.time()).isoformat() + "Z"
    end = datetime.combine(end_date, datetime.min.time()).isoformat() + "Z"

    events_result = service.events().list(
        calendarId="primary",
        timeMin=start,
        timeMax=end,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])

    commitments = {}
    event_name = {}
    for event in events:
        if "dateTime" not in event["start"]:
            continue

        start_time = datetime.fromisoformat(
            event["start"]["dateTime"].replace("Z", "+00:00")
        )
        end_time = datetime.fromisoformat(
            event["end"]["dateTime"].replace("Z", "+00:00")
        )
        duration_hours = (end_time - start_time).seconds / 3600
        event_date = start_time.date()
        event_title = event.get("summary", "Unnamed event")

        #to prevent overwriting existing commitments, sum durations for events on the same day
        if event_date in commitments:
            commitments[event_date] += duration_hours
            event_name[event_date].append(event_title)
        else:
            commitments[event_date] = duration_hours
            event_name[event_date] = [event_title]

    return (commitments, event_name)


def export_schedule_to_google_calendar(schedule):
    """
    Export study schedule as events to Google Calendar.

    Creates one all-day event per study session in the user's primary calendar.

    Args:
        schedule (pd.DataFrame): Schedule with columns 'date', 'subject', 'hours', 'type'.

    Returns:
        int: Number of events created.

    Example:
        >>> from datetime import date
        >>> import pandas as pd
        >>> schedule = pd.DataFrame({
        ...     "date": [date(2026, 6, 1)],
        ...     "subject": ["Statistics"],
        ...     "hours": [3.0],
        ...     "type": ["initial"]
        ... })
        >>> count = export_schedule_to_google_calendar(schedule)
    """
    service = _get_calendar_service()
    count = 0

    for _, row in schedule.iterrows():
        label = f"📚 {row['subject']} — {row['hours']}hrs"
        if row["type"] == "review":
            label += " (review)"

        event = {
            "summary": label,
            "start": {"date": str(row["date"])},
            "end": {"date": str(row["date"])},
            "description": f"StudySmart study session — {row['type']}"
        }
        service.events().insert(calendarId="primary", body=event).execute()
        count += 1

    return count

