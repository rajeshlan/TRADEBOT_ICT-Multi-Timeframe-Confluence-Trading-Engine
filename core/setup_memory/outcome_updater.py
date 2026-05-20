import time

from core.setup_memory.outcome_logger import append_outcome_event


def register_execution_event(trade):
    """
    Fired when order successfully executes.
    Captures initial entry data and trade parameters.
    """

    event = {
        "event_type": "EXECUTED",
        "timestamp": time.time(),

        "trade_id": trade.get("id"),
        "trade_uuid": trade.get("trade_uuid"),
        "setup_id": trade.get("setup_id"),
        "decision_id": trade.get("decision_id"),
        "order_intent_id": trade.get("order_intent_id"),
        "symbol": trade.get("symbol"),

        "status": trade.get("status"),

        "side": trade.get("bias"),

        "entry": trade.get("entry"),
        "filled_price": trade.get("filled_price"),

        "qty": trade.get("qty"),

        "sl": trade.get("sl"),
        "tp": trade.get("tp"),

        "rr_ratio": trade.get("rr_ratio"),

        "execution_type": trade.get("execution_type")
    }

    append_outcome_event(event)


def register_telemetry_event(trade):
    """
    Fired during active position synchronization.
    Tracks live unrealized PnL and price fluctuations.
    """

    event = {
        "event_type": "TELEMETRY",
        "timestamp": time.time(),

        "trade_id": trade.get("id"),
        "trade_uuid": trade.get("trade_uuid"),
        "setup_id": trade.get("setup_id"),
        "decision_id": trade.get("decision_id"),
        "order_intent_id": trade.get("order_intent_id"),
        "symbol": trade.get("symbol"),

        "unrealized_pnl": trade.get("unrealized_pnl"),

        "entry_price_real": trade.get("entry_price_real"),

        "status": trade.get("status")
    }

    append_outcome_event(event)


def register_close_event(trade):
    """
    Fired when position fully closes.
    Captures final result and enriched tracking metrics (MFE, MAE, ROI, etc.).
    """

    event = {
        "event_type": "CLOSED",
        "timestamp": time.time(),

        "trade_id": trade.get("id"),
        "trade_uuid": trade.get("trade_uuid"),
        "setup_id": trade.get("setup_id"),
        "decision_id": trade.get("decision_id"),
        "order_intent_id": trade.get("order_intent_id"),
        "symbol": trade.get("symbol"),

        "result": trade.get("result"),

        "pnl": trade.get("pnl"),

        "entry": trade.get("entry"),
        "exit_price": trade.get("exit_price"),

        "closed_at": trade.get("closed_at"),

        "status": trade.get("status"),

        # ENRICHED METRICS (Added in Step 6)
        "mfe": trade.get("mfe"),
        "mae": trade.get("mae"),

        "max_roi": trade.get("max_roi"),
        "min_roi": trade.get("min_roi"),

        "duration_sec": trade.get("duration_sec"),

        "peak_pnl": trade.get("peak_pnl"),
        "worst_pnl": trade.get("worst_pnl")
    }

    append_outcome_event(event)
