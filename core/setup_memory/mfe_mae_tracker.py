import time


def initialize_tracking(trade):
    """
    Initializes behavioral telemetry fields
    when trade becomes active.
    """

    trade["mfe"] = 0.0
    trade["mae"] = 0.0

    trade["peak_pnl"] = 0.0
    trade["worst_pnl"] = 0.0

    trade["max_roi"] = 0.0
    trade["min_roi"] = 0.0

    trade["telemetry_initialized_at"] = time.time()

    return trade


def update_tracking(trade):
    """
    Updates MFE / MAE behavioral telemetry.
    """

    pnl = float(trade.get("unrealized_pnl", 0))

    entry = float(trade.get("filled_price") or trade.get("entry") or 0)

    qty = float(trade.get("qty", 0))

    if entry <= 0 or qty <= 0:
        return trade

    position_value = entry * qty

    roi = (pnl / position_value) * 100 if position_value > 0 else 0

    # -------------------------------------------------
    # MFE / MAE
    # -------------------------------------------------

    trade["mfe"] = max(
        float(trade.get("mfe", 0)),
        pnl
    )

    trade["mae"] = min(
        float(trade.get("mae", 0)),
        pnl
    )

    # -------------------------------------------------
    # PNL EXTREMES
    # -------------------------------------------------

    trade["peak_pnl"] = max(
        float(trade.get("peak_pnl", 0)),
        pnl
    )

    trade["worst_pnl"] = min(
        float(trade.get("worst_pnl", 0)),
        pnl
    )

    # -------------------------------------------------
    # ROI EXTREMES
    # -------------------------------------------------

    trade["max_roi"] = max(
        float(trade.get("max_roi", 0)),
        roi
    )

    trade["min_roi"] = min(
        float(trade.get("min_roi", 0)),
        roi
    )

    # -------------------------------------------------
    # DURATION
    # -------------------------------------------------

    executed_at = trade.get("executed_at")

    if executed_at:
        trade["duration_sec"] = round(
            time.time() - executed_at,
            2
        )

    return trade


def finalize_tracking(trade):
    """
    Final cleanup before trade closure.
    """

    trade["finalized_at"] = time.time()

    return trade