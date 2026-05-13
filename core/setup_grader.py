def grade_trade_setup(score, market_regime, rr_ratio):
    """
    Grades trade quality.

    Returns:
        A+
        A
        B
        C
    """

    if (
        score >= 85
        and market_regime == "TRENDING"
        and rr_ratio >= 2.5
    ):
        return "A+"

    if score >= 70:
        return "A"

    if score >= 55:
        return "B"

    return "C"