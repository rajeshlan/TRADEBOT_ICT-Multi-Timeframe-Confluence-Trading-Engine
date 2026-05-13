from datetime import datetime
import pytz


UTC = pytz.utc


def get_current_session():
    """
    Returns current dominant trading session.
    """

    now = datetime.now(UTC)
    hour = now.hour

    # Asia Session
    if 0 <= hour < 7:
        return "ASIA"

    # London Session
    if 7 <= hour < 13:
        return "LONDON"

    # New York Session
    if 13 <= hour < 21:
        return "NEW_YORK"

    return "DEAD"