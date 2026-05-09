from datetime import datetime, timezone

from core.setup_memory.session_classifier import classify_session
from core.setup_memory.market_regime import detect_market_regime
from core.setup_memory.volatility_engine import compute_volatility_state
from core.setup_memory.structure_metrics import calculate_structure_metrics


def build_features(signal, results_by_tf, candles_by_tf):
    """
    Central intelligence feature builder.
    """

    highest_tf = None

    for tf in ["1M", "1d", "4h", "2h", "30m", "5m"]:
        if tf in candles_by_tf:
            highest_tf = candles_by_tf[tf]
            break

    if not highest_tf:
        return {}

    volatility_data = compute_volatility_state(highest_tf)

    structure_data = calculate_structure_metrics(
        results_by_tf,
        signal["bias"]
    )

    return {
        "session": classify_session(datetime.now(timezone.utc)),
        "market_regime": detect_market_regime(highest_tf),

        "atr": volatility_data["atr"],
        "volatility_state": volatility_data["volatility_state"],
        "range_expansion": volatility_data["range_expansion"],

        "liquidity_strength": structure_data["liquidity_strength"],
        "fvg_quality": structure_data["fvg_quality"],
        "htf_alignment": structure_data["htf_alignment"],
    }