import pytest
from datetime import date, timedelta
import pandas as pd
from study_smart.schedule import (
    _available_hours_per_day,
    _round_to_half,
    _distribute_hours,
    _detect_overload,
    build_schedule,
    update_schedule,
    generate_tips
)


# Tests for _available_hours_per_day
def test_available_hours_no_commitments():
    """Test that default hours are returned when no commitments."""
    result = _available_hours_per_day(date(2026, 5, 13))
    assert result == 7

def test_available_hours_with_commitments():
    """Test that commitments reduce available hours."""
    commitments = {date(2026, 5, 13): 2}
    result = _available_hours_per_day(date(2026, 5, 13), commitments=commitments)
    assert result == 5

def test_available_hours_minimum():
    """Test that available hours never go below 0."""
    commitments = {date(2026, 5, 13): 9}
    result = _available_hours_per_day(date(2026, 5, 13), commitments=commitments)
    assert result == 0

def test_available_hours_exact():
    """Test: 7 default minus 3 commitment always gives 4."""
    commitments = {date(2026, 5, 13): 3}
    result = _available_hours_per_day(date(2026, 5, 13), commitments=commitments)
    assert result == 4.0

# Tests for _round_to_half
def test__round_to_half():
    """Test: 3.7 rounds to 3.5, 3.2 rounds to 3.0, 2.0 stays 2.0."""
    assert _round_to_half(3.7) == 3.5
    assert _round_to_half(3.2) == 3.0
    assert _round_to_half(2.0) == 2.0

# Tests for _distribute_hours
def test__distribute_hours():
    """Test that hours are distributed proportionally."""
    study_days = [date(2026, 5, 13), date(2026, 5, 14)]
    commitments = {date(2026, 5, 13): 2}  # 5 hours available on 13th, 7 on 14th
    result = _distribute_hours(12, study_days, commitments)
    assert result[date(2026, 5, 13)] == 5.0
    assert result[date(2026, 5, 14)] == 7.0

def test__distribute_hours_rounding():
    """Test that total hours are exact even when individual days don't divide evenly."""
    study_days = [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]
    result = _distribute_hours(10, study_days)  # 10/3 = 3.33 per day, doesn't divide evenly
    for hours in result.values():
        assert hours % 0.5 == 0.0  # all values must be rounded to nearest 0.5
    assert sum(result.values()) == 10

def test__distribute_hours_no_study_days():
    """Test that an empty dictionary is returned when there are no study days available."""
    result = _distribute_hours(10, [], commitments={})
    assert result == {}
    
def test__distribute_hours_with_fully_blocked_day():
    """Test that a fully blocked day gets 0 hours assigned."""
    study_days = [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]
    commitments = {date(2026, 5, 13): 7}  # May 13 fully blocked
    result = _distribute_hours(10, study_days, commitments=commitments)
    assert result[date(2026, 5, 13)] == 0

# Tests for _detect_overload
def test__detect_overload_true():
    """Test that overload is detected correctly."""
    hours_per_day = {date(2026, 5, 13): 3, date(2026, 5, 14): 3}
    overloaded, total = _detect_overload(hours_per_day, hours_needed=10)
    assert overloaded
    assert total == 6

def test__detect_overload_false():
    """Test that no overload is detected when there are enough hours."""
    hours_per_day = {date(2026, 5, 13): 7, date(2026, 5, 14): 7}
    overloaded, total = _detect_overload(hours_per_day, hours_needed=10)
    assert not overloaded
    assert total == 14

# Tests for build_schedule
def test_build_schedule_columns():
    """Test that the schedule has the correct columns."""
    exams = [{"name": "Stats", "date": date(2026, 6, 5), "hours": 6}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1))
    assert list(result.columns) == ["date", "subject", "hours", "type"]

def test_build_schedule_correct_subject():
    """Test that the correct subject appears in the schedule."""
    exams = [{"name": "Neuroimaging", "date": date(2026, 6, 5), "hours": 4}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1))
    assert set(result["subject"].unique()) == {"Neuroimaging"}

def test_build_schedule_no_study_on_exam_day():
    """Test that no hours are scheduled on or after the exam date."""
    exams = [{"name": "Neuroimaging", "date": date(2026, 6, 5), "hours": 4}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1))
    assert all(d < date(2026, 6, 5) for d in result["date"])

def test_build_schedule_overload_schedules_maximum():
    """Test that overload schedules maximum available hours and returns a warning."""
    exams = [{"name": "Neuroimaging", "date": date(2026, 6, 2), "hours": 100}]
    result, warnings = build_schedule(exams, start_date=date(2026, 6, 1))
    assert not result.empty
    assert result["hours"].sum() <= 7
    assert len(warnings) == 1
    assert "Neuroimaging" in warnings[0]

def test_build_schedule_no_exam():
    """Test that an empty DataFrame is returned when there are no exams."""
    result, _ = build_schedule([], start_date=date(2026, 6, 1))
    assert result.empty

def test_build_schedule_single_exam_exact_hours():
    """Test: 14h over 2 equal days always gives 7h per day."""
    exams = [{"name": "Stats", "date": date(2026, 6, 3), "hours": 14}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1))
    assert result[result["date"] == date(2026, 6, 1)]["hours"].values[0] == 7.0
    assert result[result["date"] == date(2026, 6, 2)]["hours"].values[0] == 7.0

def test_build_schedule_two_exams():
    """Test that total scheduled hours match the sum of hours needed for two exams."""
    exams = [
        {"name": "Stats", "date": date(2026, 6, 4), "hours": 21},
        {"name": "Neuroimaging", "date": date(2026, 6, 7), "hours": 21}
    ]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1))
    assert result["hours"].sum() == 42

def test_build_schedule_exact_hours_three_days():
    """Test: 14h over 3 equal days gives exact hours per day."""
    exams = [{"name": "Stats", "date": date(2026, 6, 4), "hours": 14}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1))
    assert result[result["date"] == date(2026, 6, 1)]["hours"].values[0] == 4.5
    assert result[result["date"] == date(2026, 6, 2)]["hours"].values[0] == 4.5
    assert result[result["date"] == date(2026, 6, 3)]["hours"].values[0] == 5.0

def test_build_schedule_exact_hours_with_commitment():
    """Test: 12h over 2 days with a commitment gives exact hours per day."""
    exams = [{"name": "Stats", "date": date(2026, 6, 3), "hours": 12}]
    commitments = {date(2026, 6, 1): 2}  # 5h available June 1, 7h June 2
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1), commitments=commitments)
    assert result[result["date"] == date(2026, 6, 1)]["hours"].values[0] == 5.0
    assert result[result["date"] == date(2026, 6, 2)]["hours"].values[0] == 7.0

# Tests for build_schedule with spaced repetition
    
def test_spaced_repetition_review_intervals():
    """Test that reviews are scheduled at day+1, +3, +7, +14 after first study day."""
    exams = [{"name": "Stats", "date": date(2026, 7, 1), "hours": 14}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1), spaced_repetition=True)
    first_study_day = result[result["type"] == "initial"]["date"].min()
    review_dates = set(result[result["type"] == "review"]["date"].tolist())
    for offset in [1, 3, 7, 14]:
        assert first_study_day + timedelta(days=offset) in review_dates

def test_spaced_repetition_no_review_after_exam_date():
    """Test that no reviews are scheduled on or after the exam date."""
    exams = [{"name": "Stats", "date": date(2026, 6, 20), "hours": 10}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1), spaced_repetition=True)
    reviews = result[result["type"] == "review"]
    assert all(d < date(2026, 6, 20) for d in reviews["date"])

def test_spaced_repetition_topics_used():
    """Test that provided topic names appear as subjects in the schedule."""
    exams = [{"name": "Stats", "date": date(2026, 6, 30), "hours": 14,
              "topics": ["Chapter 1", "Chapter 2", "Chapter 3"]}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1), spaced_repetition=True)
    for topic in ["Chapter 1", "Chapter 2", "Chapter 3"]:
        assert topic in result["subject"].values

def test_spaced_repetition_no_topics_defaults():
    """Test that exam name is used as subject when no topics are provided."""
    exams = [{"name": "Stats", "date": date(2026, 6, 20), "hours": 10}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1), spaced_repetition=True)
    assert set(result["subject"].unique()) == {"Stats"}

def test_spaced_repetition_review_skipped():
    """Test that reviews are silently skipped when all review dates fall on or after the exam."""
    # Only 1 study day before exam — all review offsets land on or after exam date
    exams = [{"name": "Stats", "date": date(2026, 6, 2), "hours": 7}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1), spaced_repetition=True)
    reviews = result[result["type"] == "review"]
    assert reviews.empty

def test_spaced_repetition_exact_split():
    """Test: 10h with spaced repetition always gives 7h initial and 3h reviews."""
    exams = [{"name": "Stats", "date": date(2026, 6, 8), "hours": 10}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1), spaced_repetition=True)
    initial_total = result[result["type"] == "initial"]["hours"].sum()
    review_total = result[result["type"] == "review"]["hours"].sum()
    assert initial_total == 7.0
    assert initial_total + review_total <= 10.0

# Tests for update_schedule
def test_update_schedule_returns_dataframe():
    """Test that update_schedule returns a DataFrame with correct columns."""
    exams = [{"name": "Psych", "date": date(2026, 6, 6), "hours": 14}]
    schedule, _ = build_schedule(exams, start_date=date(2026, 6, 1))
    exam_dates = {"Psych": date(2026, 6, 6)}
    updated = update_schedule(schedule, date(2026, 6, 3), 3, {}, exam_dates)
    assert list(updated.columns) == ["date", "subject", "hours", "type"]

def test_update_schedule_old_part_unchanged():
    """Test that days before changed_date are not changed after update."""
    exams = [{"name": "Psych", "date": date(2026, 6, 6), "hours": 14}]
    schedule, _ = build_schedule(exams, start_date=date(2026, 6, 1))
    exam_dates = {"Psych": date(2026, 6, 6)}
    updated = update_schedule(schedule, date(2026, 6, 3), 3, {}, exam_dates)
    old_before = schedule[schedule["date"] < date(2026, 6, 3)]
    updated_before = updated[updated["date"] < date(2026, 6, 3)]
    assert old_before["hours"].sum() == updated_before["hours"].sum()

def test_update_schedule_commitments_not_mutated():
    """Test that the original commitments are not modified."""
    exams = [{"name": "Psych", "date": date(2026, 6, 6), "hours": 14}]
    schedule, _ = build_schedule(exams, start_date=date(2026, 6, 1))
    exam_dates = {"Psych": date(2026, 6, 6)}
    original_commitments = {}
    update_schedule(schedule, date(2026, 6, 3), 3, original_commitments, exam_dates)
    assert original_commitments == {}

def test_update_schedule_cancelled_commitment_frees_hours():
    """Test that cancelling a commitment (negative hours_change) frees up hours."""
    exams = [{"name": "Psych", "date": date(2026, 6, 6), "hours": 14}]
    commitments = {date(2026, 6, 3): 4}
    schedule, _ = build_schedule(exams, start_date=date(2026, 6, 1), commitments=commitments)
    exam_dates = {"Psych": date(2026, 6, 6)}
    updated = update_schedule(schedule, date(2026, 6, 3), -4, commitments, exam_dates)
    assert updated["hours"].sum() >= schedule["hours"].sum()
    
def test_update_schedule_spaced_repetition_rebuilds_reviews():
    """Test that update_schedule with spaced_repetition=True rebuilds review sessions after changed date."""
    exams = [{"name": "Psych", "date": date(2026, 6, 20), "hours": 14}]
    schedule, _ = build_schedule(exams, start_date=date(2026, 6, 1), spaced_repetition=True)
    exam_dates = {"Psych": date(2026, 6, 20)}
    
    # add a commitment on June 5 — should trigger schedule rebuild
    updated = update_schedule(schedule, date(2026, 6, 5), 3, {}, exam_dates, spaced_repetition=True)
    
    # old part before June 5 should be unchanged
    old_before = schedule[schedule["date"] < date(2026, 6, 5)]
    updated_before = updated[updated["date"] < date(2026, 6, 5)]
    assert old_before["hours"].sum() == updated_before["hours"].sum()
    
    # new part should still have reviews
    updated_after = updated[updated["date"] >= date(2026, 6, 5)]
    assert "review" in updated_after["type"].values

# Tests for generate_tips
def test_generate_tips_active_recall():
    """Test that active recall tip is generated when time to exam is short."""
    schedule = pd.DataFrame({
        "date": [date(2026, 5, 13)],
        "subject": ["Stats"],
        "hours": [7]
    })
    exam_dates = {"Stats": date(2026, 5, 20)}  # 7 days away
    tips = generate_tips(schedule, exam_dates, start_date=date(2026, 5, 13))
    found = False
    for tip in tips:
        if "active recall" in tip:
            found = True
    assert found

def test_generate_tips_deep_understanding():
    """Test that deep understanding tip is generated when time to exam is long."""
    schedule = pd.DataFrame({
        "date": [date(2026, 5, 13)],
        "subject": ["Stats"],
        "hours": [7]
    })
    exam_dates = {"Stats": date(2026, 6, 13)}  # 31 days away
    tips = generate_tips(schedule, exam_dates, start_date=date(2026, 5, 13))
    found = False
    for tip in tips:
        if "deep understanding" in tip:
            found = True
    assert found

def test_generate_tips_interleaving():
    """Test that interleaving tip is generated when exams are close together."""
    schedule = pd.DataFrame({
        "date": [date(2026, 5, 13), date(2026, 5, 14)],
        "subject": ["Stats", "Psych"],
        "hours": [7, 7]
    })
    exam_dates = {"Stats": date(2026, 5, 20), "Psych": date(2026, 5, 22)}  # 2 days apart
    tips = generate_tips(schedule, exam_dates, start_date=date(2026, 5, 13))
    found = False
    for tip in tips:
        if "interleaving" in tip:
            found = True
    assert found

def test_generate_tips_breaks():
    """Test that break tip is generated when a day has heavy study hours."""
    schedule = pd.DataFrame({
        "date": [date(2026, 5, 13)],
        "subject": ["Stats"],
        "hours": [6]  # 6/7 = about 85% of available time
    })
    exam_dates = {"Stats": date(2026, 5, 20)}
    tips = generate_tips(schedule, exam_dates, start_date=date(2026, 5, 13), default_hours=7)
    found = False
    for tip in tips:
        if "take short breaks" in tip:
            found = True
    assert found

