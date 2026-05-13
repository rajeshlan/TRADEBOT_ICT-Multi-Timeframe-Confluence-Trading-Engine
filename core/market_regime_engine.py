import statistics


def classify_market_regime(candles):
    """
    Simple adaptive market regime classifier.

    Returns:
        TRENDING
        RANGING
        VOLATILE
        COMPRESSED
    """

    if not candles or len(candles) < 20:
        return "UNKNOWN"

    closes = [float(c["close"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]

    recent_close = closes[-1]
    avg_close = statistics.mean(closes)

    total_range = max(highs) - min(lows)

    avg_candle_range = statistics.mean([
        h - l for h, l in zip(highs, lows)
    ])

    price_deviation = abs(recent_close - avg_close)

    volatility_ratio = (
        avg_candle_range / avg_close
        if avg_close > 0 else 0
    )

    trend_ratio = (
        price_deviation / total_range
        if total_range > 0 else 0
    )

    if volatility_ratio > 0.015:
        return "VOLATILE"

    if trend_ratio > 0.35:
        return "TRENDING"

    if volatility_ratio < 0.003:
        return "COMPRESSED"

    return "RANGING"