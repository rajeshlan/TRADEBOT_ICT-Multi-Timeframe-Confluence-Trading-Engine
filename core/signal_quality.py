import math


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _latest_result(results_by_tf):
    for tf in ("5m", "30m", "2h", "4h", "1d", "1M"):
        result = results_by_tf.get(tf)
        if result:
            return result
    return {}


def _trend_quality(candles, lookback=30):
    if not candles or len(candles) < 8:
        return 0.0

    window = candles[-lookback:]
    closes = [_safe_float(c["close"]) for c in window]
    net_move = abs(closes[-1] - closes[0])
    path = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
    return round(net_move / path, 4) if path else 0.0


def _wick_noise(candles, lookback=20):
    if not candles or len(candles) < 5:
        return 0.0

    ratios = []
    for candle in candles[-lookback:]:
        high = _safe_float(candle["high"])
        low = _safe_float(candle["low"])
        open_ = _safe_float(candle["open"])
        close = _safe_float(candle["close"])
        candle_range = high - low
        if candle_range <= 0:
            continue
        body = abs(close - open_)
        wick = max(candle_range - body, 0)
        ratios.append(wick / candle_range)

    return round(sum(ratios) / len(ratios), 4) if ratios else 0.0


def _volume_expansion(candles, lookback=20):
    if not candles or len(candles) < lookback:
        return 1.0

    volumes = [_safe_float(c.get("volume")) for c in candles[-lookback:]]
    baseline = sum(volumes[:-1]) / max(len(volumes) - 1, 1)
    return round(volumes[-1] / baseline, 4) if baseline else 1.0


def _reclaim_speed_score(candles, bias):
    if not candles or len(candles) < 5:
        return 0.0

    latest = candles[-1]
    open_ = _safe_float(latest["open"])
    close = _safe_float(latest["close"])
    high = _safe_float(latest["high"])
    low = _safe_float(latest["low"])
    candle_range = high - low
    if candle_range <= 0:
        return 0.0

    if bias == "BULLISH":
        return round((close - low) / candle_range, 4)
    return round((high - close) / candle_range, 4)


def classify_archetype(signal, results_by_tf, candles_by_tf):
    bias = signal.get("bias")
    result = _latest_result(results_by_tf)
    liq = result.get("liquidity") or {}
    fvg = result.get("fvg") or {}
    regime = signal.get("market_regime")

    correct_sweep = (
        (bias == "BULLISH" and liq.get("swept") and liq.get("type") == "SELL_SIDE")
        or (bias == "BEARISH" and liq.get("swept") and liq.get("type") == "BUY_SIDE")
    )
    fvg_aligned = bool(fvg.get("type") and bias in fvg.get("type", ""))

    ltf = candles_by_tf.get("5m") or candles_by_tf.get("30m") or []
    trend_quality = _trend_quality(ltf)

    if correct_sweep and fvg_aligned:
        return "SWEEP_FVG_REVERSAL"
    if fvg_aligned and trend_quality >= 0.55:
        return "FVG_CONTINUATION"
    if regime in {"COMPRESSED", "LOW_VOL_COMPRESSION"}:
        return "COMPRESSION_BREAKOUT"
    if correct_sweep:
        return "SWEEP_REVERSAL"
    return "BOS_PULLBACK"


def assess_signal_quality(signal, results_by_tf, candles_by_tf, market_context=None):
    """Add institutional-style filters without requiring private data."""
    market_context = market_context or {}
    bias = signal.get("bias")
    ltf = candles_by_tf.get("5m") or candles_by_tf.get("30m") or []

    trend_quality = _trend_quality(ltf)
    wick_noise = _wick_noise(ltf)
    volume_expansion = _volume_expansion(ltf)
    reclaim_speed = _reclaim_speed_score(ltf, bias)
    chop_score = max(0.0, min(1.0, (1 - trend_quality) * 0.65 + wick_noise * 0.35))

    funding = _safe_float(market_context.get("funding_rate"))
    book_imbalance = _safe_float(market_context.get("book_imbalance"))
    spread_bps = market_context.get("spread_bps")
    spread_bps_val = _safe_float(spread_bps)
    oi_change_pct = _safe_float(market_context.get("open_interest_change_pct"))
    price_24h_pct = _safe_float(market_context.get("price_24h_pct"))

    squeeze_risk = 0.0
    cascade_risk = 0.0
    if bias == "BEARISH":
        squeeze_risk = max(0.0, min(1.0, (-funding * 1400) + max(book_imbalance, 0) * 0.6 + max(price_24h_pct, 0) * 1.2))
    elif bias == "BULLISH":
        cascade_risk = max(0.0, min(1.0, (funding * 1400) + max(-book_imbalance, 0) * 0.6 + max(-price_24h_pct, 0) * 1.2))

    liquidity_vacuum = bool(spread_bps is not None and spread_bps_val > 8)
    trend_acceleration = trend_quality >= 0.62 and volume_expansion >= 1.25 and abs(oi_change_pct) >= 0.3

    score_delta = 0
    reasons = []

    if trend_quality >= 0.55:
        score_delta += 8
    elif trend_quality < 0.25:
        score_delta -= 10
        reasons.append("LOW_TREND_QUALITY")

    if chop_score >= 0.72:
        score_delta -= 14
        reasons.append("ANTI_CHOP_SUPPRESSION")

    if reclaim_speed >= 0.72:
        score_delta += 6
    elif reclaim_speed < 0.38:
        score_delta -= 7
        reasons.append("WEAK_RECLAIM_OR_REJECTION")

    if volume_expansion >= 1.5:
        score_delta += 5
    elif volume_expansion < 0.65:
        score_delta -= 4
        reasons.append("LOW_PARTICIPATION")

    if liquidity_vacuum:
        score_delta -= 12
        reasons.append("LIQUIDITY_VACUUM")

    if squeeze_risk >= 0.65:
        score_delta -= 16
        reasons.append("SHORT_SQUEEZE_RISK")
    if cascade_risk >= 0.65:
        score_delta -= 14
        reasons.append("LONG_LIQUIDATION_CASCADE_RISK")

    if trend_acceleration:
        score_delta += 5

    hard_reject = liquidity_vacuum and trend_quality < 0.45
    hard_reject = hard_reject or (chop_score >= 0.82 and trend_quality < 0.35)

    return {
        "score_delta": score_delta,
        "hard_reject": hard_reject,
        "reject_reasons": reasons,
        "trend_quality": trend_quality,
        "chop_score": round(chop_score, 4),
        "wick_noise": wick_noise,
        "volume_expansion": volume_expansion,
        "reclaim_speed": reclaim_speed,
        "squeeze_risk": round(squeeze_risk, 4),
        "cascade_risk": round(cascade_risk, 4),
        "liquidity_vacuum": liquidity_vacuum,
        "trend_acceleration": trend_acceleration,
    }


def expected_value_assessment(signal, quality, empirical_prior=None):
    """Estimate R expectancy conservatively. This is a gate, not a prediction oracle."""
    empirical_prior = empirical_prior or {}
    score = _safe_float(signal.get("confluence_score"))
    rr = _safe_float(signal.get("rr_ratio"), 2.0)
    archetype_winrate = empirical_prior.get("winrate")
    sample_size = int(empirical_prior.get("sample_size", 0) or 0)

    score_component = max(0.0, min(1.0, score / 100))
    model_win_prob = (
        0.34
        + score_component * 0.22
        + quality.get("trend_quality", 0) * 0.08
        + quality.get("reclaim_speed", 0) * 0.05
        - quality.get("chop_score", 0) * 0.08
        - quality.get("squeeze_risk", 0) * 0.05
        - quality.get("cascade_risk", 0) * 0.05
    )

    if sample_size >= 20 and archetype_winrate is not None:
        empirical = max(0.15, min(0.75, _safe_float(archetype_winrate) / 100))
        weight = min(0.55, math.sqrt(sample_size) / 20)
        model_win_prob = model_win_prob * (1 - weight) + empirical * weight

    win_prob = max(0.22, min(0.68, model_win_prob))
    expected_r = win_prob * rr - (1 - win_prob) - 0.08

    threshold = 0.12
    if quality.get("chop_score", 0) >= 0.65:
        threshold += 0.08
    if quality.get("liquidity_vacuum"):
        threshold += 0.1
    if signal.get("correlated_exposure", 0) >= 1:
        threshold += 0.05

    return {
        "win_probability": round(win_prob, 4),
        "expected_value_r": round(expected_r, 4),
        "approval_threshold_r": round(threshold, 4),
        "approved": expected_r >= threshold,
    }
