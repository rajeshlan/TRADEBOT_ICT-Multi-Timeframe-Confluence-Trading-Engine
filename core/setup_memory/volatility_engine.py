import statistics


def compute_atr(candles, period=14):
    """
    Basic ATR approximation using candle ranges.
    """

    if len(candles) < period + 1:
        return 0.0

    ranges = []

    for c in candles[-period:]:
        ranges.append(abs(c["high"] - c["low"]))

    return round(sum(ranges) / len(ranges), 6)


def compute_volatility_state(candles):
    """
    Detects simple volatility regime.
    """

    if len(candles) < 20:
        return {
            "atr": 0,
            "volatility_state": "UNKNOWN",
            "range_expansion": 0
        }

    atr = compute_atr(candles)

    recent_ranges = [
        abs(c["high"] - c["low"])
        for c in candles[-20:]
    ]

    avg_range = statistics.mean(recent_ranges)

    latest_range = recent_ranges[-1]

    expansion_ratio = latest_range / avg_range if avg_range else 0

    if expansion_ratio > 1.8:
        state = "HIGH"

    elif expansion_ratio < 0.7:
        state = "LOW"

    else:
        state = "NORMAL"

    return {
        "atr": round(atr, 6),
        "volatility_state": state,
        "range_expansion": round(expansion_ratio, 3)
    }