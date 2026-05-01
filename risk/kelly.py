def kelly_fraction(winrate, rr):
    """
    Kelly formula:
    f = W - (1-W)/R
    """

    if rr == 0:
        return 0

    f = winrate - (1 - winrate) / rr

    # safety clamp
    return max(0, min(f, 0.25))  # cap at 25%