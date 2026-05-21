from datetime import date, timedelta
import pandas as pd
from study_smart.schedule import (
    _available_hours_per_day,
    _round_to_half,
    _distribute_hours,
    build_schedule,
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
    """Test that available hours are calculated correctly."""
    commitments = {date(2026, 5, 13): 3}
    result = _available_hours_per_day(date(2026, 5, 13), commitments=commitments)
    assert result == 4.0

# Tests for _round_to_half
def test__round_to_half():
    """Test that it rounds to the nearest 0.5."""
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
    """Test that a fully blocked day is excluded from distribution."""
    study_days = [date(2026, 5, 13), date(2026, 5, 14), date(2026, 5, 15)]
    commitments = {date(2026, 5, 13): 7}  # May 13 fully blocked
    result = _distribute_hours(10, study_days, commitments=commitments)
    assert date(2026, 5, 13) not in result  # blocked day excluded

def test__distribute_hours_all_days_blocked():
    """Test that empty dict returned when all days are fully blocked."""
    study_days = [date(2026, 5, 13), date(2026, 5, 14)]
    commitments = {date(2026, 5, 13): 7, date(2026, 5, 14): 7}
    result = _distribute_hours(10, study_days, commitments=commitments)
    assert result == {}

# Tests for build_schedule

# Basic structure 
def test_build_schedule_no_exam():
    """Test that an empty DataFrame is returned when there are no exams."""
    result, _ = build_schedule([], start_date=date(2026, 6, 1))
    assert result.empty

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

# Build_schedule: Single exam scheduling
def test_build_schedule_no_study_on_exam_day():
    """Test that no hours are scheduled on or after the exam date."""
    exams = [{"name": "Neuroimaging", "date": date(2026, 6, 5), "hours": 4}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1))
    assert all(d < date(2026, 6, 5) for d in result["date"])

def test_build_schedule_single_exam_exact_hours():
    """Test: 14h over 2 equal days always gives 7h per day."""
    exams = [{"name": "Stats", "date": date(2026, 6, 3), "hours": 14}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1))
    assert result[result["date"] == date(2026, 6, 1)]["hours"].values[0] == 7.0
    assert result[result["date"] == date(2026, 6, 2)]["hours"].values[0] == 7.0

def test_build_schedule_respects_commitments():
    """Test that commitments reduce available study hours on that day."""
    exams = [{"name": "Stats", "date": date(2026, 6, 3), "hours": 14}]
    commitments = {date(2026, 6, 1): 3}  # 4hrs available June 1, 7hrs June 2
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1), commitments=commitments)
    assert result[result["date"] == date(2026, 6, 1)]["hours"].sum() <= 4

# Multiple exams
def test_build_schedule_two_exams():
    """Test that total scheduled hours match the sum of hours needed for two exams."""
    exams = [
        {"name": "Stats", "date": date(2026, 6, 4), "hours": 21},
        {"name": "Neuroimaging", "date": date(2026, 6, 7), "hours": 21}
    ]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1))
    assert result["hours"].sum() == 42

# Topics
def test_build_schedule_topic_order():
    """Test that topics are studied in order — Chapter 1 before Chapter 2."""
    exams = [{"name": "Stats", "date": date(2026, 6, 20), "hours": 14,
              "topics": ["Chapter 1", "Chapter 2"]}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1))
    last_ch1 = result[result["subject"] == "Chapter 1"]["date"].max()
    first_ch2 = result[result["subject"] == "Chapter 2"]["date"].min()
    assert last_ch1 <= first_ch2 

# Overload handling
def test_build_schedule_overload_schedules_maximum():
    """Test that overload schedules maximum available hours and returns a warning."""
    exams = [{"name": "Neuroimaging", "date": date(2026, 6, 2), "hours": 100}]
    result, warnings = build_schedule(exams, start_date=date(2026, 6, 1))
    assert not result.empty
    assert result["hours"].sum() <= 7
    assert len(warnings) == 1
    assert "Neuroimaging" in warnings[0]

def test_build_schedule_overload_reduces_topics_equally():
    """Test that when overloaded all topics get equal reduced hours."""
    exams = [{"name": "Stats", "date": date(2026, 6, 2), "hours": 20,
              "topics": ["A", "B", "C", "D"]}]
    result, warnings = build_schedule(exams, start_date=date(2026, 6, 1))
    # two warnings expected: one for overload (topics reduced) and one for topic D not fully scheduled
    assert len(warnings) == 2
    assert any("Each topic reduced" in w for w in warnings) 
    assert any("could not be fully scheduled" in w for w in warnings)

def test_build_schedule_no_usable_days():
    """Test warning when all days before exam are fully blocked."""
    exams = [{"name": "Stats", "date": date(2026, 6, 2), "hours": 7}]
    commitments = {date(2026, 6, 1): 7}  # only day fully blocked
    result, warnings = build_schedule(exams, start_date=date(2026, 6, 1), commitments=commitments)
    assert any("No available days" in w for w in warnings)

# Second pass scheduling
def test_build_schedule_second_pass_fills_capacity():
    """Test that leftover capacity is used when topics can't fit in first pass."""
    exams = [{"name": "Stats", "date": date(2026, 6, 10), "hours": 20,
              "topics": ["Chapter 1", "Chapter 2", "Chapter 3", "Chapter 4"]}]
    commitments = {date(2026, 6, 5): 6}  # nearly block one day
    result, warnings = build_schedule(exams, start_date=date(2026, 6, 1), commitments=commitments)
    assert "Chapter 4" in result["subject"].values  # all topics scheduled

# Tests with spaced repetition
def test_spaced_repetition_review_intervals():
    """Test that reviews are scheduled at day+1, +3, +7, +14 after last study day."""
    exams = [{"name": "Stats", "date": date(2026, 7, 1), "hours": 14}]
    result, _ = build_schedule(exams, start_date=date(2026, 6, 1), spaced_repetition=True)
    last_study_day = result[result["type"] == "initial"]["date"].max()
    review_dates = set(result[result["type"] == "review"]["date"].tolist())
    for offset in [1, 3, 7, 14]:
        assert last_study_day + timedelta(days=offset) in review_dates

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

def test_generate_tips_light_load():
    """Test that light load tip is generated when average hours are low."""
    schedule = pd.DataFrame({
        "date": [date(2026, 5, 13)],
        "subject": ["Stats"],
        "hours": [1.0]
    })
    exam_dates = {"Stats": date(2026, 6, 13)}
    tips = generate_tips(schedule, exam_dates, start_date=date(2026, 5, 13), default_hours=7)
    found = any("plenty of time" in tip for tip in tips)
    assert found
 


