import time
import uuid

def build_setup_snapshot(signal):
    """
    Immutable setup snapshot builder.

    This captures the exact market setup state BEFORE execution 
    mutates anything. It now includes enriched features from the 
    Feature Engine for deep performance analysis.
    """

    snapshot = {
        # --- Core Identity ---
        "setup_id": str(uuid.uuid4()),
        "created_at": time.time(),

        # --- Signal Identity ---
        "runtime_setup_id": signal.get("setup_id"),
        "decision_id": signal.get("decision_id"),
        "symbol": signal.get("symbol"),
        "bias": signal.get("bias"),

        # --- Price Structure ---
        "entry": signal.get("entry"),
        "sl": signal.get("sl"),
        "tp": signal.get("tp"),

        # --- Risk ---
        "risk_pct": signal.get("risk_pct"),
        "rr_ratio": signal.get("rr_ratio"),

        # --- Market Structure ---
        "bos": signal.get("bos"),
        "liquidity_state": signal.get("liquidity_state"),
        "fvg_state": signal.get("fvg_state"),

        # --- Volume / Flow ---
        "volume_score": signal.get("volume_score"),
        "orderflow_score": signal.get("orderflow_score"),
        "flowpulse_score": signal.get("flowpulse_score"),

        # --- Feature Enrichment (New in Step 5) ---
        "session": signal.get("session"),
        "market_regime": signal.get("market_regime"),

        "atr": signal.get("atr"),
        "volatility_state": signal.get("volatility_state"),
        "range_expansion": signal.get("range_expansion"),

        "liquidity_strength": signal.get("liquidity_strength"),
        "fvg_quality": signal.get("fvg_quality"),
        "htf_alignment": signal.get("htf_alignment"),

        # --- Future Outcome Fields (Placeholders) ---
        "status": "PENDING",
        "outcome": None,
        "pnl": None,
        "mfe": None,
        "mae": None,
        "time_to_target": None,

        # --- Meta ---
        "execution_type": signal.get("execution_type", "LIVE"),
        "archetype": signal.get("archetype"),
        "confluence_score": signal.get("confluence_score"),
        "setup_grade": signal.get("setup_grade"),
        "expected_value_r": signal.get("expected_value_r"),
        "approval_threshold_r": signal.get("approval_threshold_r"),
        "win_probability": signal.get("win_probability"),
        "trend_quality": signal.get("trend_quality"),
        "chop_score": signal.get("chop_score"),
        "squeeze_risk": signal.get("squeeze_risk"),
        "cascade_risk": signal.get("cascade_risk"),
        "funding_rate": signal.get("funding_rate"),
        "spread_bps": signal.get("spread_bps"),
        "book_imbalance": signal.get("book_imbalance"),
        "open_interest_change_pct": signal.get("open_interest_change_pct"),
    }

    return snapshot
