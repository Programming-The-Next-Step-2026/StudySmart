def available_hours_per_day(study_day, default=7, commitments=None):
    """
    Returns how many study hours are available on a given day.

    Args:
        study_day (str or date): The day to check.
        default (int): Default available study hours per day.
        commitments (dict): Dict mapping days to hours already committed (e.g. lectures, gym).

    Returns:
        float: Available study hours after subtracting commitments (minimum 0).
    """
    if commitments is None:
        commitments = {}
    blocked = commitments.get(study_day, 0)
    return max(0, default - blocked)
