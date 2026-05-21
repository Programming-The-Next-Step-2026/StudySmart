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