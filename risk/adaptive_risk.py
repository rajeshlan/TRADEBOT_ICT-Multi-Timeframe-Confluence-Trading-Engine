import math


def compute_atr(candles, period=14):
    """
    Lightweight ATR calculation using true range approximation.
    """

    if not candles or len(candles) < period + 1:
        return 0

    trs = []

    for i in range(1, period + 1):
        current = candles[-i]
        previous = candles[-i - 1]

        high = float(current["high"])
        low = float(current["low"])
        prev_close = float(previous["close"])

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )

        trs.append(tr)

    return sum(trs) / len(trs)


def build_adaptive_stop(
    bias,
    entry,
    structure_sl,
    atr,
    atr_multiplier=1.5,
    liquidity_buffer_pct=0.0015
):
    """
    Expands stop placement using ATR and liquidity sweep buffers.
    """

    atr_buffer = atr * atr_multiplier
    liquidity_buffer = entry * liquidity_buffer_pct

    total_buffer = atr_buffer + liquidity_buffer

    if bias == "BULLISH":
        adaptive_sl = structure_sl - total_buffer
    else:
        adaptive_sl = structure_sl + total_buffer

    stop_distance = abs(entry - adaptive_sl)

    return {
        "adaptive_sl": round(adaptive_sl, 6),
        "stop_distance": round(stop_distance, 6),
        "atr_buffer": round(atr_buffer, 6),
        "liquidity_buffer": round(liquidity_buffer, 6)
    }


def calculate_risk_based_position_size(
    account_balance,
    risk_pct,
    entry,
    stop_loss
):
    """
    Professional fixed-risk sizing.

    Risk remains constant regardless of stop width.
    """

    stop_distance = abs(entry - stop_loss)

    if stop_distance <= 0:
        return 0

    account_risk = account_balance * (risk_pct / 100)

    qty = account_risk / stop_distance

    return max(round(qty, 3), 0)


def volatility_is_tradeable(
    atr,
    entry,
    minimum_atr_pct=0.003
):
    """
    Reject compressed/noise environments.
    """

    if entry <= 0:
        return False

    atr_pct = atr / entry

    return atr_pct >= minimum_atr_pct