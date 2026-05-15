import pytest
from datetime import date, timedelta
import pandas as pd


def _available_hours_per_day(study_day, default=7, commitments=None):
    """Returns available study hours on a given day after subtracting commitments (minimum 0)."""
    if commitments is None:
        commitments = {}
    blocked = commitments.get(study_day, 0)
    return max(0, default - blocked)


def _round_to_half(hours):
    """Rounds a number of hours to the nearest 0.5."""
    return round(hours * 2) / 2


def _distribute_hours(exam_hours, study_days, commitments=None):
    """Distributes study hours across days proportionally to each day's availability.

    Assumes overload has already been handled by the caller.
    """
    if commitments is None:
        commitments = {}

    if not study_days:
        return {}

    hours_per_day = {}
    for day in study_days:
        hours_per_day[day] = _available_hours_per_day(day, commitments=commitments)

    total_available = sum(hours_per_day.values())

    if total_available == 0:
        return {day: 0.0 for day in study_days}

    schedule = {}
    for day in study_days[:-1]:
        proportion = hours_per_day[day] / total_available
        schedule[day] = _round_to_half(exam_hours * proportion)

    schedule[study_days[-1]] = _round_to_half(exam_hours - sum(schedule.values()))

    return schedule


def _detect_overload(hours_per_day, hours_needed):
    """Returns (is_overloaded, total_available) — True if available hours are less than needed."""
    total = sum(hours_per_day.values())
    return total < hours_needed, total


def _schedule_reviews(topic_name, first_study_day, exam_date,
                      review_hours_per_session, allocated, commitments):
    """Internal — schedules review sessions for a topic after initial study.

    Review intervals are 1, 3, 7, 14 days after first study session.
    Reviews are skipped if exam has passed or no hours are available.
    Based on Ebbinghaus (1885) and Murre & Dros (2015).
    """
    review_intervals = [1, 3, 7, 14]
    reviews = []

    for interval in review_intervals:
        review_date = first_study_day + timedelta(days=interval)

        # skip if review falls on or after exam date
        if review_date >= exam_date:
            continue

        # check remaining hours on that day
        available = _available_hours_per_day(review_date, commitments=commitments)
        remaining = available - allocated.get(review_date, 0.0)

        if remaining <= 0:
            continue  # no room — skip this review

        # reduce review hours if not enough room
        actual_hours = _round_to_half(min(review_hours_per_session, remaining))

        if actual_hours > 0:
            reviews.append({
                "date": review_date,
                "subject": topic_name,
                "hours": actual_hours,
                "type": "review"
            })

    return reviews

def build_schedule(exams, start_date, commitments=None, spaced_repetition=False):
    """
    Build a study schedule working backwards from exam deadlines.

    Hours are distributed proportionally across available days for each exam.
    If there is not enough time, the maximum possible hours are scheduled and
    a warning is returned instead of crashing.

    If spaced_repetition is True, review sessions are scheduled at 1, 3, 7,
    and 14 days after the first study session for each topic, based on the
    Ebbinghaus forgetting curve (Ebbinghaus, 1885; Murre & Dros, 2015).
    30% of total hours are reserved for reviews, 70% for initial study.

    Args:
        exams (list): List of dicts, each with:
            - 'name' (str): Subject name.
            - 'date' (datetime.date): Exam date (study stops the day before).
            - 'hours' (float): Total study hours needed for this exam.
            - 'topics' (list of str, optional): List of topic names. If not
              provided, the exam name is used as a single topic.
        start_date (datetime.date): First day of the study schedule.
        commitments (dict): Optional. Maps datetime.date to hours already blocked
            (e.g. lectures, sport). Defaults to no commitments.
        spaced_repetition (bool): If True, schedule review sessions based on
            the Ebbinghaus forgetting curve. Defaults to False.

    Returns:
        tuple: A tuple of (schedule, warnings) where:
            - schedule (pd.DataFrame): Columns 'date', 'subject', 'hours',
              and 'type' ('initial' or 'review') if spaced_repetition is True.
            - warnings (list of str): One warning per exam that could not be
              fully scheduled due to insufficient time.

    Example:
        >>> from datetime import date
        >>> exams = [
        ...     {"name": "Stats", "date": date(2026, 6, 5), "hours": 10,
        ...      "topics": ["Chapter 1", "Chapter 2", "Chapter 3"]},
        ... ]
        >>> schedule, warnings = build_schedule(exams, start_date=date(2026, 6, 1),
        ...                                     spaced_repetition=True)
        >>> print(schedule)
        >>> print(warnings)
    """
    if commitments is None:
        commitments = {}

    if not exams:
        return pd.DataFrame(columns=["date", "subject", "hours", "type"]), []

    exams = sorted(exams, key=lambda x: x["date"])

    last_exam = exams[-1]["date"]
    all_days = []
    current_date = start_date
    while current_date <= last_exam:
        all_days.append(current_date)
        current_date += timedelta(days=1)

    allocated = {}
    for day in all_days:
        allocated[day] = 0.0

    rows = []
    warnings = []

    for exam in exams:
        exam_days = []
        for d in all_days:
            if start_date <= d < exam["date"]:
                exam_days.append(d)

        # get topics — default to exam name if not provided
        topics = exam.get("topics", None)
        if not topics:
            topics = [exam["name"]]

        if spaced_repetition:
            # 70% of hours for initial study, 30% for reviews
            initial_hours = _round_to_half(exam["hours"] * 0.7)
            review_total = exam["hours"] - initial_hours
            review_hours_per_session = _round_to_half(review_total / 4)
        else:
            initial_hours = exam["hours"]

        # distribute initial hours equally across topics
        hours_per_topic = _round_to_half(initial_hours / len(topics))

        for topic in topics:
            remaining_per_day = {}
            for d in exam_days:
                available = _available_hours_per_day(d, commitments=commitments)
                remaining_per_day[d] = available - allocated[d]

            overloaded, total = _detect_overload(remaining_per_day, hours_per_topic)
            if overloaded:
                warnings.append(
                    f"You need {hours_per_topic}h for '{topic}' but only have {total:.1f}h available. "
                    f"The maximum possible is scheduled. Consider starting earlier or reducing other subjects."
                )
                actual_hours = total
            else:
                actual_hours = hours_per_topic

            topic_schedule = _distribute_hours(actual_hours, exam_days, commitments)

            # track first study day for spaced repetition
            first_study_day = None

            for day, hours in topic_schedule.items():
                if hours > 0:
                    rows.append({
                        "date": day,
                        "subject": topic,
                        "hours": hours,
                        "type": "initial"
                    })
                    allocated[day] += hours

                    # record first study day
                    if first_study_day is None:
                        first_study_day = day

            # schedule reviews if spaced repetition is enabled
            if spaced_repetition and first_study_day is not None:
                reviews = _schedule_reviews(
                    topic_name=topic,
                    first_study_day=first_study_day,
                    exam_date=exam["date"],
                    review_hours_per_session=review_hours_per_session,
                    allocated=allocated,
                    commitments=commitments
                )

                for review in reviews:
                    rows.append(review)
                    allocated[review["date"]] += review["hours"]

    return pd.DataFrame(rows), warnings

def update_schedule(schedule, changed_date, hours_change, commitments, exam_dates, spaced_repetition=False):
    """
    Update the study schedule after a commitment is added or cancelled.

    Days before changed_date are kept as-is. From changed_date onwards, hours
    are redistributed based on the updated commitments. Pass a positive
    hours_change to add a commitment (less time available) or a negative value
    to cancel one (more time freed up).

    Args:
        schedule (pd.DataFrame): Current study schedule with columns 'date', 'subject', 'hours'.
        changed_date (datetime.date): The date from which the schedule should be rebuilt.
        hours_change (float): Hours to add (positive) or remove (negative) on changed_date.
        commitments (dict): Current commitments mapping datetime.date to blocked hours.
        exam_dates (dict): Maps subject name (str) to exam date (datetime.date).
        spaced_repetition (bool): If True, rebuild schedule with spaced repetition. Defaults to False.

    Returns:
        pd.DataFrame: Updated schedule with columns 'date', 'subject', 'hours'.

    Example:
        >>> from datetime import date
        >>> import pandas as pd
        >>> schedule = pd.DataFrame({
        ...     "date": [date(2025, 6, 1), date(2025, 6, 2)],
        ...     "subject": ["Stats", "Stats"],
        ...     "hours": [7.0, 7.0],
        ... })
        >>> exam_dates = {"Stats": date(2025, 6, 3)}
        >>> updated = update_schedule(schedule, date(2025, 6, 2), hours_change=3,
        ...                           commitments={}, exam_dates=exam_dates, spaced_repetition=False)
        >>> print(updated)
    """
    # copy commitments to avoid mutating the original
    commitments = commitments.copy()
    commitments[changed_date] = max(0, commitments.get(changed_date, 0) + hours_change)

    # get remaining exams from schedule
    remaining_exams = []
    for subject in schedule["subject"].unique():
        subject_data = schedule[schedule["subject"] == subject]
        hours_remaining = subject_data[
            subject_data["date"] >= changed_date
        ]["hours"].sum()
        remaining_exams.append({
            "name": subject,
            "date": exam_dates[subject],
            "hours": hours_remaining
        })

    # rebuild schedule from changed date onwards
    new_schedule, _ = build_schedule(
        remaining_exams,
        start_date=changed_date,
        commitments=commitments,
        spaced_repetition=spaced_repetition
    )

    # combine old schedule (before changed date) with new schedule
    old_part = schedule[schedule["date"] < changed_date]
    updated = pd.concat([old_part, new_schedule])
    updated = updated.reset_index(drop=True)
    return updated

def generate_tips(schedule, exam_dates, start_date, default_hours=7):
    """
    Generate personalized, evidence-based study tips from the current schedule.

    Tips are based on time remaining per exam, proximity of exam dates to each
    other, and daily study load. References to psychology research are included
    in each tip.

    Args:
        schedule (pd.DataFrame): Current study schedule with columns 'date', 'subject', 'hours'.
        exam_dates (dict): Maps subject name (str) to exam date (datetime.date).
        start_date (datetime.date): First day of the study schedule.
        default_hours (float): Default available study hours per day. Used to
            determine whether a day counts as heavily loaded. Defaults to 7.

    Returns:
        list of str: Personalised tips. May include tips on active recall,
            deep processing, interleaving, and taking breaks depending on the schedule.

    Example:
        >>> from datetime import date
        >>> import pandas as pd
        >>> schedule = pd.DataFrame({
        ...     "date": [date(2025, 5, 13)],
        ...     "subject": ["Stats"],
        ...     "hours": [6.0],
        ... })
        >>> exam_dates = {"Stats": date(2025, 5, 20)}
        >>> tips = generate_tips(schedule, exam_dates, start_date=date(2025, 5, 13))
        >>> for tip in tips:
        ...     print(tip)
    """
    tips = []
    sorted_exams = sorted(
        [{"name": name, "date": d} for name, d in exam_dates.items()],
        key=lambda x: x["date"]
    )

    # tip per exam based on time available
    for exam in sorted_exams:
        days_available = (exam["date"] - start_date).days
        name = exam["name"]

        # if there is little time: active recall
        if days_available <= 7:
            tips.append(
                f"Only {days_available} days left for '{name}'. "
                f"Use active recall — test yourself rather than re-reading notes. "
                f"(Roediger & Karpicke, 2006)"
            )

        # if there is a lot of time: focus on deeper understanding
        elif days_available >= 14:
            tips.append(
                f"{days_available} days until '{name}' — "
                f"aim for deep understanding. The deeper you process information, "
                f"the better your memory retention. (Craik & Lockhart, 1972)"
            )

    # if there are 2+ exams close together: suggest interleaving
    for i in range(len(sorted_exams) - 1):
        days_between = (sorted_exams[i + 1]["date"] - sorted_exams[i]["date"]).days
        if days_between <= 3:
            tips.append(
                f"'{sorted_exams[i]['name']}' and '{sorted_exams[i + 1]['name']}' are close together. "
                f"Try interleaving — mix both subjects in each session rather than studying one per day. "
                f"(Kornell & Bjork, 2008)"
            )

    # for heavy study days: suggest breaks
    daily_totals = schedule.groupby("date")["hours"].sum()
    for d, h in daily_totals.items():
        if h >= default_hours * 0.85: # if studying more than 85% of available time
            tips.append(
                f"On {d}, you have {h}h scheduled. "
                f"Remember to take short breaks every hour to maintain focus (Ariga & Lleras, 2011)."
            )

    return tips
