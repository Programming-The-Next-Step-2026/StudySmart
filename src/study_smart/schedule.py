"""
Core scheduling logic for StudySmart.

Provides functions to build personalised study schedules from exam
deadlines and commitments, with optional spaced repetition based on
the Ebbinghaus forgetting curve.
"""

from datetime import timedelta
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

        #skip if review date is on or after exam date
        if review_date >= exam_date:
            continue
        #check remaining hours on review date
        available = _available_hours_per_day(review_date, commitments=commitments)
        remaining = available - allocated.get(review_date, 0.0)

        #no room - skip this review 
        if remaining <= 0:
            continue

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

    Hours are distributed evenly across available days.
    Topics of each exam are studied in order — finish one before starting the next.
    Different exams are studied in parallel.
    Reviews are scheduled after all initial study is complete,
    using only leftover hours at 0.5hr per session.

    If spaced_repetition is True, review sessions are scheduled at 1, 3, 7,
    and 14 days after the last initial study session for each topic, based on the
    Ebbinghaus forgetting curve (Ebbinghaus, 1885; Murre & Dros, 2015).
    Reviews are lowest priority — they never block initial study.

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
              and 'type' ('initial' or 'review').
            - warnings (list of str): Warnings for exams that could not be
              fully scheduled due to insufficient time.

    Example:
        >>> from datetime import date
        >>> exams = [
        ...     {"name": "Stats", "date": date(2026, 6, 5), "hours": 10,
        ...      "topics": ["Chapter 1", "Chapter 2", "Chapter 3"]},
        ... ]
        >>> schedule, warnings = build_schedule(exams, start_date=date(2026, 6, 1),
        ...                                     spaced_repetition=True)
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

    # track allocated hours per day
    allocated = {}
    for day in all_days:
        allocated[day] = 0.0

    rows = []
    warnings = []
    pending_reviews = []

    for exam in exams:
        # days available before this exam
        exam_days = []
        for d in all_days:
            if start_date <= d < exam["date"]:
                exam_days.append(d)

        # warn if exam is too close for full spaced repetition
        days_until_exam = (exam["date"] - start_date).days
        if spaced_repetition and days_until_exam < 14:
            warnings.append(
                f"'{exam['name']}' is only {days_until_exam} days away — "
                f"not enough time for full spaced repetition. "
                f"Some reviews may be skipped."
            )

        # get topics — default to exam name if not provided
        topics = exam.get("topics", None)
        if not topics:
            topics = [exam["name"]]

        # all initial hours are divided among topics — reviews come later if default hours are enough
        initial_hours = exam["hours"]

        # build flat queue of topics in order
        hours_per_topic = _round_to_half(initial_hours / len(topics))
        topic_queue = []
        for topic in topics:
            topic_queue.append([topic, hours_per_topic])

        # total hours needed for this exam
        total_needed = sum(h for _, h in topic_queue)

        # usable days — at least 1hr remaining
        usable_days = []
        for d in exam_days:
            remaining = _available_hours_per_day(d, commitments=commitments) - allocated[d]
            if remaining >= 1.0:
                usable_days.append(d)

        if not usable_days:
            warnings.append(f"No available days for '{exam['name']}'.")
            continue

        # total available hours across usable days
        total_available = sum(
            _available_hours_per_day(d, commitments=commitments) - allocated[d]
            for d in usable_days
        )

        if total_needed > total_available:
            # reduce hours per topic proportionally so all topics get equal study time
            hours_per_topic = _round_to_half(total_available / len(topics))
            topic_queue = []
            for topic in topics:
                topic_queue.append([topic, hours_per_topic])
            total_needed = sum(h for _, h in topic_queue)
            warnings.append(
                f"'{exam['name']}' needs {exam['hours']}h but only {total_available:.0f}h available. "
                f"Each topic reduced to {hours_per_topic}h. Consider starting earlier."
            )

        # spread evenly across all usable days
        target_per_day = _round_to_half(total_needed / len(usable_days))
        target_per_day = max(1.0, target_per_day)

        # track last study day per topic for reviews
        topic_last_study_day = {}

        # first pass — fill days up to target per day
        for day in usable_days:
            available_today = _available_hours_per_day(day, commitments=commitments) - allocated[day]
            hours_to_fill = min(target_per_day, available_today)
            hours_filled = 0.0

            while topic_queue and hours_filled < hours_to_fill:
                topic, remaining = topic_queue[0]  # unpack topic name and hours remaining

                can_fit = _round_to_half(min(remaining, hours_to_fill - hours_filled))

                if can_fit < 1.0:
                    # not enough room for a full session — move to next day
                    break

                rows.append({
                    "date": day,
                    "subject": topic,
                    "hours": can_fit,
                    "type": "initial"
                })
                allocated[day] += can_fit
                hours_filled += can_fit
                topic_queue[0][1] -= can_fit
                topic_last_study_day[topic] = day

                # topic finished — move to next
                if topic_queue[0][1] < 1.0:
                    topic_queue.pop(0)

        # second pass — fill leftover capacity in order, keeping topic sequence intact
        if topic_queue:
            last_scheduled_day = max(topic_last_study_day.values()) if topic_last_study_day else usable_days[0]
            remaining_days = [d for d in usable_days if d >= last_scheduled_day]

            for day in remaining_days:
                available_today = _available_hours_per_day(day, commitments=commitments) - allocated[day]
                if available_today < 1.0:
                    continue
                if not topic_queue:
                    break
                topic, remaining = topic_queue[0]
                can_fit = _round_to_half(min(remaining, available_today))
                if can_fit < 1.0:
                    continue
                rows.append({
                    "date": day,
                    "subject": topic,
                    "hours": can_fit,
                    "type": "initial"
                })
                allocated[day] += can_fit
                topic_queue[0][1] -= can_fit
                topic_last_study_day[topic] = day
                if topic_queue[0][1] < 1.0:
                    topic_queue.pop(0)

        # warn if topics still not fully scheduled after both passes
        for topic, remaining in topic_queue:
            warnings.append(
                f"'{topic}' could not be fully scheduled — {remaining:.1f}h missing. "
                f"Consider starting earlier."
            )

        # store reviews for later — after ALL initial study is done
        if spaced_repetition:
            for topic in topics:
                if topic in topic_last_study_day:
                    pending_reviews.append({
                        "topic": topic,
                        "last_study_day": topic_last_study_day[topic],
                        "exam_date": exam["date"]
                    })

    # schedule all reviews after all initial study is done
    # reviews are 0.5hr fixed and lowest priority — only use if leftover hours are available
    for r in pending_reviews:
        reviews = _schedule_reviews(
            topic_name=r["topic"],
            first_study_day=r["last_study_day"],
            exam_date=r["exam_date"],
            review_hours_per_session=0.5,
            allocated=allocated,
            commitments=commitments
        )
        for review in reviews:
            rows.append(review)
            allocated[review["date"]] += review["hours"]

    return pd.DataFrame(rows), warnings


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
        ...     "date": [date(2026, 5, 13)],
        ...     "subject": ["Statistics"],
        ...     "hours": [6.0],
        ... })
        >>> exam_dates = {"Statistics": date(2026, 5, 20)}
        >>> tips = generate_tips(schedule, exam_dates, start_date=date(2026, 5, 13))
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

        # if there is little time:  active recall
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

    # if days are lightly loaded:  suggest studying more per day
    daily_totals = schedule.groupby("date")["hours"].sum()
    avg_hours = daily_totals.mean()
    if avg_hours < default_hours * 0.5:
        tips.append(
            f"Your average study load is only {avg_hours:.1f}h/day — "
            f"you have plenty of time! Consider increasing hours per topic "
            f"or adding more practice sessions to strengthen retention."
        )

    return tips

