"""
Unit tests for google_calendar.py.

Tests cover:
- import_commitments_from_google_calendar: event parsing and commitment calculation
    - All-day events (no dateTime) are skipped
    - Multiple events on the same day have their hours summed
    - Events without a summary fall back to 'Unnamed event'

Note: _get_calendar_service is not tested as it requires live OAuth credentials.
All tests mock the calendar service to avoid network calls.
"""

from unittest.mock import patch
from datetime import date
from study_smart.google_calendar import import_commitments_from_google_calendar

def test_import_skips_allday_events():
    """Test that all-day events are skipped."""
    with patch("study_smart.google_calendar._get_calendar_service") as mock_service:
        mock_service.return_value.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "summary": "Birthday",
                    "start": {"date": "2026-05-13"},
                    "end": {"date": "2026-05-14"}
                }
            ]
        }
        commitments, _ = import_commitments_from_google_calendar(
            start_date=date(2026, 5, 13),
            end_date=date(2026, 5, 14)
        )
        assert len(commitments) == 0


def test_import_sums_multiple_events_same_day():
    """Test that multiple events on the same day are summed."""
    with patch("study_smart.google_calendar._get_calendar_service") as mock_service:
        mock_service.return_value.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "summary": "Lecture",
                    "start": {"dateTime": "2026-05-13T09:00:00+00:00"},
                    "end": {"dateTime": "2026-05-13T11:00:00+00:00"}
                },
                {
                    "summary": "Gym",
                    "start": {"dateTime": "2026-05-13T17:00:00+00:00"},
                    "end": {"dateTime": "2026-05-13T18:00:00+00:00"}
                }
            ]
        }
        commitments, event_names = import_commitments_from_google_calendar(
            start_date=date(2026, 5, 13),
            end_date=date(2026, 5, 14)
        )
        assert commitments[date(2026, 5, 13)] == 3.0
        assert event_names[date(2026, 5, 13)] == ["Lecture", "Gym"]


def test_import_unnamed_event_fallback():
    """Test that events without a summary get 'Unnamed event' as title."""
    with patch("study_smart.google_calendar._get_calendar_service") as mock_service:
        mock_service.return_value.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "start": {"dateTime": "2026-05-13T09:00:00+00:00"},
                    "end": {"dateTime": "2026-05-13T11:00:00+00:00"}
                    # no "summary" key
                }
            ]
        }
        commitments, event_names = import_commitments_from_google_calendar(
            start_date=date(2026, 5, 13),
            end_date=date(2026, 5, 14)
        )
        assert event_names[date(2026, 5, 13)] == ["Unnamed event"]