import time
import uuid


def build_setup_snapshot(signal):
    """
    Immutable setup snapshot builder.

    This captures the exact market setup state
    BEFORE execution mutates anything.
    """

    snapshot = {
        # Core Identity
        "setup_id": str(uuid.uuid4()),
        "created_at": time.time(),

        # Signal Identity
        "symbol": signal.get("symbol"),
        "bias": signal.get("bias"),

        # Price Structure
        "entry": signal.get("entry"),
        "sl": signal.get("sl"),
        "tp": signal.get("tp"),

        # Risk
        "risk_pct": signal.get("risk_pct"),
        "rr_ratio": signal.get("rr_ratio"),

        # Market Structure
        "bos": signal.get("bos"),
        "liquidity_state": signal.get("liquidity_state"),
        "fvg_state": signal.get("fvg_state"),

        # Volume / Flow
        "volume_score": signal.get("volume_score"),
        "orderflow_score": signal.get("orderflow_score"),
        "flowpulse_score": signal.get("flowpulse_score"),

        # Future Outcome Fields
        "status": "PENDING",
        "outcome": None,
        "pnl": None,
        "mfe": None,
        "mae": None,
        "time_to_target": None,

        # Meta
        "execution_type": signal.get("execution_type", "LIVE"),
    }

    return snapshot