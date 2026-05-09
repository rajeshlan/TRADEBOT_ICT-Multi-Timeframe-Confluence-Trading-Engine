def detect_market_regime(candles):
    """
    Primitive regime detector.
    """

    if len(candles) < 30:
        return "UNKNOWN"

    closes = [c["close"] for c in candles[-20:]]

    direction = closes[-1] - closes[0]

    total_movement = sum(
        abs(closes[i] - closes[i - 1])
        for i in range(1, len(closes))
    )

    efficiency = abs(direction) / total_movement if total_movement else 0

    if efficiency > 0.6:
        return "TRENDING"

    elif efficiency < 0.25:
        return "RANGING"

    return "MIXED"