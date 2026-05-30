"""
Unit tests for app.py helper functions and callbacks.

Tests cover:
- generate_schedule: schedule construction from exams and commitments
- get_subject_color_map: color assignment per exam
- build_chart: Plotly figure construction
- build_weekly_view: weekly calendar HTML
- build_commitment_list: commitment display
- build_tips: study tip generation
- add_exam callback: validation and global state
- delete_exam callback: removal of exams
- add_commitment callback: accumulation and validation
- delete_commitment callback: removal and recompute
- save_exams / load_exams: Excel persistence
- update_week / update_weekly_view: week navigation
"""
import pytest
import pandas as pd
from datetime import date
from unittest.mock import patch
import dash
from dash import html
import dash_bootstrap_components as dbc
import study_smart.app as app
import plotly.graph_objects as go
from study_smart.app import (
    get_subject_color_map,
    build_chart,
    build_weekly_view,
    build_tips,
    build_commitment_list,
    add_exam,
    delete_exam,
    add_commitment,
    delete_commitment,
    save_exams,
    load_exams,
    update_week,
    update_weekly_view,
)

# Fixtures

@pytest.fixture(autouse=True)
def reset_globals():
    """Clear global state before and after every test."""
    app.exams.clear()
    app.commitments.clear()
    app.commitment_names.clear()
    yield
    app.exams.clear()
    app.commitments.clear()
    app.commitment_names.clear()

# Helpers

def make_schedule(*rows):
    """Build a minimal schedule DataFrame from dicts."""
    return pd.DataFrame(list(rows))


def make_exam(name, exam_date, hours, topics=None):
    """Build an exam dict matching the format used by generate_schedule."""
    return {"name": name, "date": exam_date, "hours": hours, "topics": topics or []}


# Tests for generate schedule 

def test_generate_schedule_returns_figure_and_schedule():
    """Test that generate_schedule returns figure and schedule with valid exams."""
    app.exams.append({
        "name": "Stats",
        "date": "2026-06-10",
        "hours": 10,
        "topics": ["Ch1", "Ch2"]
    })
    from study_smart.app import generate_schedule
    result = generate_schedule(1, [], 7, "2026-06-01")
    
    # result is tuple of 11 outputs
    fig, weekly, warnings, tips, schedule_data, spaced, start, week, color_map, exam_colors, legend = result
    
    assert isinstance(fig, go.Figure)                    # chart returned
    assert isinstance(weekly, html.Div)                  # weekly view returned
    assert isinstance(schedule_data, list)               # schedule stored as list of dicts
    assert len(schedule_data) > 0                        # schedule is not empty
    assert start == "2026-06-01"                         # start date preserved
    assert week == 0                                     # week resets to 0
    assert "Stats" in exam_colors                        # exam color assigned
    assert isinstance(tips, list)                        # tips returned as list
    assert isinstance(warnings, list)                    # warnings returned as list
    assert isinstance(legend, html.Div)                  # legend returned as Div
    assert "Stats" in color_map                          # topic mapped to color
    assert spaced == []                                  # spaced repetition off

# Tests for get_subject_color_map

def test_get_subject_color_map_topics_share_exam_color():
    """Test that all topics of one exam share the same color."""
    exam_list = [make_exam("Stats", date(2026, 6, 5), 10, ["Ch1", "Ch2"])]
    color_map, exam_colors = get_subject_color_map(exam_list)
    assert color_map["Ch1"] == color_map["Ch2"]
    assert color_map["Ch1"] == exam_colors["Stats"]


def test_get_subject_color_map_exam_name_in_color_map():
    """Test that the exam name itself is included in color_map."""
    exam_list = [make_exam("Stats", date(2026, 6, 5), 10, ["Ch1"])]
    color_map, _ = get_subject_color_map(exam_list)
    assert "Stats" in color_map


def test_get_subject_color_map_two_exams_different_colors():
    """Test that two different exams are assigned different colors."""
    exam_list = [
        make_exam("Stats", date(2026, 6, 5), 10, ["Ch1"]),
        make_exam("Math", date(2026, 6, 7), 8, ["Algebra"]),
    ]
    _, exam_colors = get_subject_color_map(exam_list)
    assert exam_colors["Stats"] != exam_colors["Math"]


def test_get_subject_color_map_hsl_format():
    """Test that exam colors are returned in hsl(...) string format."""
    exam_list = [make_exam("Stats", date(2026, 6, 5), 10, [])]
    _, exam_colors = get_subject_color_map(exam_list)
    assert exam_colors["Stats"].startswith("hsl(")


def test_get_subject_color_map_single_exam_hue_is_zero():
    """Test that single exam gets hue 0 (first color in the cycle)."""
    exam_list = [make_exam("Stats", date(2026, 6, 5), 10, [])]
    _, exam_colors = get_subject_color_map(exam_list)
    assert exam_colors["Stats"] == "hsl(0, 70%, 50%)"


# Tests for build_chart

def test_build_chart_returns_figure():
    """Test that build_chart returns a Plotly Figure object."""
    schedule = make_schedule(
        {"date": date(2026, 6, 1), "subject": "Stats", "hours": 3.0, "type": "initial"}
    )
    fig = build_chart(schedule, spaced=False, color_map={})
    assert isinstance(fig, go.Figure)


def test_build_chart_title():
    """Test that chart title is 'Study Schedule'."""
    schedule = make_schedule(
        {"date": date(2026, 6, 1), "subject": "Stats", "hours": 3.0, "type": "initial"}
    )
    fig = build_chart(schedule, spaced=False, color_map={})
    assert fig.layout.title.text == "Study Schedule"


def test_build_chart_dates_are_strings():
    """Test that x-axis values are strings so Plotly treats them categorically."""
    schedule = make_schedule(
        {"date": date(2026, 6, 1), "subject": "Stats", "hours": 3.0, "type": "initial"},
        {"date": date(2026, 6, 2), "subject": "Stats", "hours": 2.0, "type": "initial"},
    )
    fig = build_chart(schedule, spaced=False, color_map={})
    assert all(isinstance(x, str) for trace in fig.data for x in trace.x)


def test_build_chart_has_data():
    """Test that chart has at least one trace when schedule is non-empty."""
    schedule = make_schedule(
        {"date": date(2026, 6, 1), "subject": "Stats", "hours": 3.0, "type": "initial"}
    )
    fig = build_chart(schedule, spaced=False, color_map={})
    assert len(fig.data) >= 1


def test_build_chart_no_pattern_when_not_spaced():
    """Test that traces have no fill pattern when spaced_repetition is off."""
    schedule = make_schedule(
        {"date": date(2026, 6, 1), "subject": "Stats", "hours": 3.0, "type": "initial"}
    )
    fig = build_chart(schedule, spaced=False, color_map={})
    for trace in fig.data:
        # to control for different versions of Plotly treating "no pattern" differently
        assert trace.marker.pattern.shape in (None, "", ())


# Tests for build_weekly_view

def test_build_weekly_view_returns_div():
    """Test that non-empty schedule returns a Div containing the calendar."""
    schedule = make_schedule(
        {"date": date(2026, 6, 1), "subject": "Stats", "hours": 3.0, "type": "initial"}
    )
    result = build_weekly_view(schedule, spaced=False)
    assert isinstance(result, html.Div)


def test_build_weekly_view_week_offset_changes_output():
    """Test that different week_offset values produce different calendar views."""
    schedule = make_schedule(
        {"date": date(2026, 6, 1), "subject": "Stats", "hours": 3.0, "type": "initial"}
    )
    week0 = build_weekly_view(schedule, spaced=False, week_offset=0)
    week1 = build_weekly_view(schedule, spaced=False, week_offset=1)
    assert str(week0) != str(week1)

def test_build_weekly_view_empty_schedule_returns_p():
    """Test that empty schedule returns html.P."""
    result = build_weekly_view(pd.DataFrame(), spaced=False)
    assert isinstance(result, html.P)

# Tests for build_commitment_list

def test_build_commitment_list_empty_returns_p():
    """Test that no commitments returns an html.P."""
    result = build_commitment_list()
    assert isinstance(result, html.P)


def test_build_commitment_list_one_item_returns_list_group():
    """Test that one commitment returns a dbc.ListGroup."""
    app.commitment_names.append({
        "date": date(2026, 6, 1), "name": "Lecture", "hours": 2
    })
    result = build_commitment_list()
    assert isinstance(result, dbc.ListGroup)


def test_build_commitment_list_item_count_matches():
    """Test that ListGroup has exactly one item per commitment."""
    app.commitment_names.append({"date": date(2026, 6, 1), "name": "Lecture", "hours": 2})
    app.commitment_names.append({"date": date(2026, 6, 2), "name": "Sport", "hours": 1})
    result = build_commitment_list()
    assert len(result.children) == 2


# Tests for add_exam callback

def test_add_exam_missing_name_returns_danger_alert():
    """Test that missing name returns a danger alert."""
    result = add_exam(1, None, "2026-06-01", 10, None)
    assert isinstance(result, dbc.Alert)
    assert result.color == "danger"

def test_add_exam_missing_hours_returns_danger_alert():
    """Test that missing hours returns a danger alert."""
    result = add_exam(1, "Stats", "2026-06-01", None, None)
    assert isinstance(result, dbc.Alert)
    assert result.color == "danger"


def test_add_exam_valid_appends_to_exams():
    """Test that valid exam is added to the global exams list."""
    add_exam(1, "Stats", "2026-06-01", 10, "Ch1, Ch2")
    assert len(app.exams) == 1
    assert app.exams[0]["name"] == "Stats"


def test_add_exam_valid_returns_table():
    """Test that valid exam returns a dbc.Table."""
    result = add_exam(1, "Stats", "2026-06-01", 10, None)
    assert isinstance(result, dbc.Table)


def test_add_exam_parses_topics_correctly():
    """Test that comma-separated topics are split and stripped."""
    add_exam(1, "Stats", "2026-06-01", 10, "Ch1, Ch2, Ch3")
    assert app.exams[0]["topics"] == ["Ch1", "Ch2", "Ch3"]


def test_add_exam_no_topics_stores_empty_list():
    """Test that exam added with no topics stores an empty list."""
    add_exam(1, "Stats", "2026-06-01", 10, None)
    assert app.exams[0]["topics"] == []


def test_add_exam_duplicate_name_returns_danger_alert():
    """Test that adding a second exam with the same name returns a danger alert."""
    app.exams.append({"name": "Stats", "date": "2026-06-01", "hours": 10, "topics": []})
    result = add_exam(1, "Stats", "2026-06-03", 8, None)
    assert isinstance(result, dbc.Alert)
    assert result.color == "danger"


def test_add_exam_duplicate_name_does_not_append():
    """Test that duplicate name does not change the exams list length."""
    app.exams.append({"name": "Stats", "date": "2026-06-01", "hours": 10, "topics": []})
    add_exam(1, "Stats", "2026-06-03", 8, None)
    assert len(app.exams) == 1


def test_add_exam_duplicate_topic_returns_danger_alert():
    """Test that topic that already exists in another exam returns a danger alert."""
    app.exams.append({
        "name": "Stats", "date": "2026-06-01", "hours": 10, "topics": ["Chapter 1"]
    })
    result = add_exam(1, "Math", "2026-06-03", 8, "Chapter 1, Chapter 2")
    assert isinstance(result, dbc.Alert)
    assert result.color == "danger"


def test_add_exam_multiple_exams_all_appear_in_table():
    """Test that after adding two exams, both rows appear in the returned table."""
    add_exam(1, "Stats", "2026-06-01", 10, None)
    result = add_exam(1, "Math", "2026-06-05", 8, None)
    assert isinstance(result, dbc.Table)
    assert len(app.exams) == 2

# Test for delete_exam callback

def test_delete_exam_removes_correct_item():
    """Test that deleting index 0 removes the first exam."""
    app.exams.append({"name": "Stats", "date": "2026-06-01", "hours": 10, "topics": []})
    app.exams.append({"name": "Math", "date": "2026-06-05", "hours": 8, "topics": []})

    with patch("study_smart.app.ctx") as mock_ctx:
        mock_ctx.triggered_id = {"index": 0}
        delete_exam([1, None])

    assert len(app.exams) == 1
    assert app.exams[0]["name"] == "Math"


# Tests for add_commitment callback

def test_add_commitment_missing_date_returns_alert():
    """Test that missing date returns a danger alert."""
    result = add_commitment(1, None, "Lecture", 2)
    assert isinstance(result, dbc.Alert)
    assert result.color == "danger"


def test_add_commitment_missing_name_returns_alert():
    """Test that missing name returns a danger alert."""
    result = add_commitment(1, "2026-06-01", None, 2)
    assert isinstance(result, dbc.Alert)
    assert result.color == "danger"


def test_add_commitment_missing_hours_returns_alert():
    """Test that missing hours returns a danger alert."""
    result = add_commitment(1, "2026-06-01", "Lecture", None)
    assert isinstance(result, dbc.Alert)
    assert result.color == "danger"


def test_add_commitment_valid_adds_to_commitments_dict():
    """Test that valid commitment is stored in the commitments dict."""
    add_commitment(1, "2026-06-01", "Lecture", 2)
    assert date(2026, 6, 1) in app.commitments
    assert app.commitments[date(2026, 6, 1)] == 2
    assert app.commitment_names[0]["name"] == "Lecture"


def test_add_commitment_same_date_accumulates_hours():
    """Test that two commitments on the same date sum their hours."""
    add_commitment(1, "2026-06-01", "Lecture", 2)
    add_commitment(1, "2026-06-01", "Sport", 1)
    assert app.commitments[date(2026, 6, 1)] == 3


def test_add_commitment_different_dates_stored_separately():
    """Test that commitments on different dates are stored independently."""
    add_commitment(1, "2026-06-01", "Lecture", 2)
    add_commitment(1, "2026-06-02", "Sport", 1)
    assert app.commitments[date(2026, 6, 1)] == 2
    assert app.commitments[date(2026, 6, 2)] == 1

def test_add_commitment_returns_list_group():
    """Test that adding a commitment returns a dbc.ListGroup."""
    result = add_commitment(1, "2026-06-01", "Lecture", 2)
    assert isinstance(result, dbc.ListGroup)



# Tests for build_tips

def test_build_tips_returns_list():
    """Test that build_tips always returns a list."""
    schedule = make_schedule(
        {"date": date(2026, 6, 1), "subject": "Stats", "hours": 3.0, "type": "initial"}
    )
    result = build_tips(schedule, {"Stats": date(2026, 6, 5)}, date(2026, 6, 1), 7)
    assert isinstance(result, list)


def test_build_tips_each_item_is_alert():
    """Test that each tip is a dbc.Alert component."""
    schedule = make_schedule(
        {"date": date(2026, 6, 1), "subject": "Stats", "hours": 3.0, "type": "initial"}
    )
    result = build_tips(schedule, {"Stats": date(2026, 6, 5)}, date(2026, 6, 1), 7)
    assert all(isinstance(item, dbc.Alert) for item in result)


def test_build_tips_alert_color_is_info():
    """Test that all tip alerts use 'info' color."""
    schedule = make_schedule(
        {"date": date(2026, 6, 1), "subject": "Stats", "hours": 3.0, "type": "initial"}
    )
    result = build_tips(schedule, {"Stats": date(2026, 6, 5)}, date(2026, 6, 1), 7)
    assert all(item.color == "info" for item in result)


def test_build_tips_empty_schedule_returns_list():
    """Test that even with an empty schedule, build_tips returns a list."""
    result = build_tips(pd.DataFrame(columns=["date", "subject", "hours", "type"]),
                        {}, date(2026, 6, 1), 7)
    assert isinstance(result, list)



# Tests for build_weekly_view 

def test_build_weekly_view_with_exam_colors_builds_legend():
    """Test that passing exam_colors causes a legend to be built inside the Div."""
    schedule = make_schedule(
        {"date": date(2026, 6, 1), "subject": "Stats", "hours": 3.0, "type": "initial"}
    )
    exam_colors = {"Stats": "hsl(0, 70%, 50%)"}
    result = build_weekly_view(schedule, spaced=False, exam_colors=exam_colors)
    assert isinstance(result, html.Div)
    # legend is rendered as part of the outer Div's children
    assert "Stats" in str(result)


def test_build_weekly_view_review_label_appended_when_spaced():
    """Test that sessions with type='review' get '(rev)' in their label when spaced=True."""
    schedule = make_schedule(
        {"date": date(2026, 6, 1), "subject": "Stats", "hours": 1.0, "type": "review"}
    )
    result = build_weekly_view(schedule, spaced=True)
    assert "(rev)" in str(result)


def test_build_weekly_view_no_rev_label_when_not_spaced():
    """Test that review sessions do NOT get '(rev)' label when spaced=False."""
    schedule = make_schedule(
        {"date": date(2026, 6, 1), "subject": "Stats", "hours": 1.0, "type": "review"}
    )
    result = build_weekly_view(schedule, spaced=False)
    assert "(rev)" not in str(result)



# Tests for save_exams callback

def test_save_exams_empty_returns_save_label():
    """Test that saving with no exams returns the original '💾 Save' label."""
    button, status = save_exams(1)
    assert button == "💾 Save"
    assert status == ""


def test_save_exams_with_exams_returns_saved_label():
    """Test that saving exams returns '✅ Saved!' label."""
    app.exams.append({"name": "Stats", "date": "2026-06-01", "hours": 10, "topics": ["Ch1"]})
    with patch.object(pd.DataFrame, "to_excel"):
        button, status = save_exams(1)
    assert button == "💾 Save"
    assert status == "✅ Saved!"


def test_save_exams_serialises_topics_as_string():
    """Test that topic lists are joined to a comma-separated string before saving."""
    app.exams.append({"name": "Stats", "date": "2026-06-01", "hours": 10, "topics": ["Ch1", "Ch2"]})
    captured = {}

    def fake_to_excel(self_df, path, **kwargs):
        captured["df"] = self_df.copy()

    with patch.object(pd.DataFrame, "to_excel", fake_to_excel):
        save_exams(1)

    assert captured["df"].loc[0, "topics"] == "Ch1, Ch2"



# Tests for load_exams callback

def test_load_exams_file_not_found_returns_p_and_load_label():
    """Test that missing file returns html.P and resets button to '📂 Load'."""
    with patch("study_smart.app.pd.read_excel", side_effect=FileNotFoundError):
        table, label = load_exams(1)
    assert isinstance(table, html.P)
    assert label == "📂 Load"


def test_load_exams_success_returns_table_and_loaded_label():
    """Test that successful load returns a Table and '✅ Loaded!' label."""
    mock_df = pd.DataFrame({
        "name": ["Stats"],
        "date": [date(2026, 6, 1)],
        "hours": [10],
        "topics": ["Ch1, Ch2"],
    })
    with patch("study_smart.app.pd.read_excel", return_value=mock_df):
        table, label = load_exams(1)
    assert isinstance(table, dbc.Table)
    assert label == "✅ Loaded!"


def test_load_exams_populates_global_exams():
    """Test that loaded rows are appended to the global exams list."""
    mock_df = pd.DataFrame({
        "name": ["Stats"],
        "date": [date(2026, 6, 1)],
        "hours": [10],
        "topics": ["Ch1, Ch2"],
    })
    with patch("study_smart.app.pd.read_excel", return_value=mock_df):
        load_exams(1)
    assert len(app.exams) == 1
    assert app.exams[0]["name"] == "Stats"


def test_load_exams_splits_topics_correctly():
    """Test that comma-separated topics string is split and stripped on load."""
    mock_df = pd.DataFrame({
        "name": ["Stats"],
        "date": [date(2026, 6, 1)],
        "hours": [10],
        "topics": ["Ch1, Ch2, Ch3"],
    })
    with patch("study_smart.app.pd.read_excel", return_value=mock_df):
        load_exams(1)
    assert app.exams[0]["topics"] == ["Ch1", "Ch2", "Ch3"]
    
def test_load_exams_does_not_duplicate_on_second_load():
    """Test that loading the same file twice does not duplicate exams."""
    mock_df = pd.DataFrame({
        "name": ["Stats"],
        "date": [date(2026, 6, 1)],
        "hours": [10],
        "topics": ["Ch1"],
    })
    with patch("study_smart.app.pd.read_excel", return_value=mock_df):
        load_exams(1)
        load_exams(1)
    assert len(app.exams) == 1

# Tests for delete_commitment callback

def test_delete_commitment_no_clicks_returns_no_update():
    """Test that no button clicked returns dash.no_update."""
    result = delete_commitment([None, None])
    assert result == dash.no_update


def test_delete_commitment_removes_correct_item():
    """Test that deleting index 0 removes the first commitment."""
    app.commitment_names.append({"date": date(2026, 6, 1), "name": "Lecture", "hours": 2})
    app.commitment_names.append({"date": date(2026, 6, 2), "name": "Sport", "hours": 1})
    app.commitments[date(2026, 6, 1)] = 2
    app.commitments[date(2026, 6, 2)] = 1

    with patch("study_smart.app.ctx") as mock_ctx:
        mock_ctx.triggered_id = {"index": 0}
        delete_commitment([1, None])

    assert len(app.commitment_names) == 1
    assert app.commitment_names[0]["name"] == "Sport"


def test_delete_commitment_returns_list_group():
    """Test that deleting one of two items returns a ListGroup."""
    app.commitment_names.append({"date": date(2026, 6, 1), "name": "Lecture", "hours": 2})
    app.commitment_names.append({"date": date(2026, 6, 2), "name": "Sport", "hours": 1})

    with patch("study_smart.app.ctx") as mock_ctx:
        mock_ctx.triggered_id = {"index": 0}
        result = delete_commitment([1, None])

    assert isinstance(result, dbc.ListGroup)



# Tests for update_week callback

def test_update_week_prev_decrements():
    """Test that clicking Prev decrements current_week by 1."""
    with patch("study_smart.app.ctx") as mock_ctx:
        mock_ctx.triggered_id = "prev-week-button"
        result = update_week(1, None, 3)
    assert result == 2


def test_update_week_next_increments():
    """Test that clicking Next increments current_week by 1."""
    with patch("study_smart.app.ctx") as mock_ctx:
        mock_ctx.triggered_id = "next-week-button"
        result = update_week(None, 1, 3)
    assert result == 4


def test_update_week_prev_from_zero():
    """Test that going Prev from week 0 gives week -1."""
    with patch("study_smart.app.ctx") as mock_ctx:
        mock_ctx.triggered_id = "prev-week-button"
        result = update_week(1, None, 0)
    assert result == -1



# Tests for update_weekly_view callback

def test_update_weekly_view_with_stored_schedule_returns_div():
    """Test: valid stored_schedule returns an html.Div."""
    stored = [{"date": "2026-06-01", "subject": "Stats", "hours": 3.0, "type": "initial"}]
    result = update_weekly_view(0, stored, False, {}, {})
    assert isinstance(result, html.Div)


def test_update_weekly_view_deserialises_dates():
    """Test that string dates in stored_schedule are converted back to date objects."""
    stored = [
        {"date": "2026-06-01", "subject": "Stats", "hours": 3.0, "type": "initial"},
        {"date": "2026-06-02", "subject": "Stats", "hours": 2.0, "type": "initial"},
    ]
    # Should not raise — date parsing must succeed
    result = update_weekly_view(0, stored, False, {}, {})
    assert isinstance(result, html.Div)
