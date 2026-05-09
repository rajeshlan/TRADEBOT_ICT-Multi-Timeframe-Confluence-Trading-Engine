from datetime import datetime, timezone


def classify_session(timestamp=None):
    """
    Simple UTC session classifier.
    """

    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    hour = timestamp.hour

    # UTC sessions
    if 0 <= hour < 7:
        return "ASIA"

    elif 7 <= hour < 13:
        return "LONDON"

    elif 13 <= hour < 17:
        return "NY_OPEN"

    elif 17 <= hour < 22:
        return "NEW_YORK"

    return "OFF_HOURS"