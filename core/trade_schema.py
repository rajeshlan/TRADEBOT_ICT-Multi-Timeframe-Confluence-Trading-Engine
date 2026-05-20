import time
import uuid
from copy import deepcopy
from datetime import datetime

# ✅ MASTER TRADE SCHEMA
# This serves as the single source of truth for all trade objects in the system.
BASE_TRADE_SCHEMA = {
    # Identity
    "trade_uuid": None,
    "setup_id": None,
    "decision_id": None,
    "order_intent_id": None,
    "exchange_fingerprint": None,    # Deterministic key for exchange matching
    "exchange_position_id": None,    # ID provided by the exchange (e.g., Bybit)
    "exchange_order_id": None,
    "position_id": None,
    "id": None,
    "order_id": None,

    # Core
    "symbol": None,
    "bias": None,
    "status": "PENDING",
    "is_active": False,

    # ✅ EXECUTION STATE MACHINE (RETRY METADATA)
    "execution_state": "PENDING",          # Current step in the execution lifecycle
    "execution_attempts": 0,               # Counter for retry logic
    "last_execution_error": None,          # String storage for the last API failure
    "last_execution_attempt_at": None,     # Unix timestamp of the last attempt
    "retry_after": None,                   # Backoff timestamp for the next valid attempt

    # Pricing
    "entry": None,
    "filled_price": None,
    "entry_price_real": None,
    "exit_price": None,

    # Risk
    "sl": None,
    "tp": None,
    "rr_ratio": 0.0,
    "risk_pct": None,
    "risk_pct_distance": None,

    # Signal Intelligence
    "confluence_score": None,
    "setup_grade": None,
    "archetype": None,
    "expected_value_r": None,
    "approval_threshold_r": None,
    "win_probability": None,
    "quality_reasons": [],
    "trend_quality": None,
    "chop_score": None,
    "squeeze_risk": None,
    "cascade_risk": None,
    "liquidity_vacuum": False,
    "funding_rate": None,
    "spread_bps": None,
    "book_imbalance": None,
    "open_interest_change_pct": None,
    "market_regime": None,
    "session": None,
    
    # Order Tracking (Order Sync Patch)
    "tp_order_exists": False,
    "sl_order_exists": False,
    "tp_order_id": None,
    "sl_order_id": None,
    "tp_trigger_price": None,
    "sl_trigger_price": None,
    "exchange_orders_synced": False,
    
    # ✅ PROTECTION INTEGRITY (Persistent Fields)
    "protection_broken": False,
    "missing_protection": [],
    "protection_status": "UNKNOWN",

    # Size
    "qty": 0.0,

    # PnL
    "pnl": 0.0,
    "unrealized_pnl": 0.0,
    "peak_pnl": 0.0,
    "worst_pnl": 0.0,

    # Lifecycle
    "created_at": None,
    "updated_at": None,
    "opened_at": None,
    "closed_at": None,
    "first_seen_at": None,           # Unix timestamp of first system detection
    "last_synced_at": None,          # Unix timestamp of last exchange update

    # Recovery
    "recovered_from_exchange": False,

    # Metadata
    "timeframes": [],
    "exchange": "BYBIT",
}

def normalize_trade_schema(trade: dict) -> dict:
    """
    Standardizes a trade dictionary against the base schema.
    Ensures missing keys are populated and identity is established.
    """
    # Create a fresh copy of the base schema
    normalized = deepcopy(BASE_TRADE_SCHEMA)

    # Update with provided trade data
    if trade:
        normalized.update(trade)

    # ✅ UUID GENERATION
    # Use standard UUID4 for guaranteed uniqueness
    if not normalized.get("trade_uuid"):
        normalized["trade_uuid"] = str(uuid.uuid4())

    # ✅ IMPROVED FINGERPRINTING
    # Build deterministic exchange fingerprint using Symbol, Bias, and Qty
    symbol = normalized.get("symbol", "UNKNOWN")
    side = normalized.get("bias", "UNKNOWN")

    try:
        qty_val = float(normalized.get("qty") or 0)
    except (ValueError, TypeError):
        qty_val = 0.0

    qty_str = round(qty_val, 4)
    existing_fingerprint = normalized.get("exchange_fingerprint")
    stale_zero_fingerprint = (
        existing_fingerprint
        and existing_fingerprint.endswith("_0.0")
        and qty_val > 0
    )

    if not existing_fingerprint or stale_zero_fingerprint:
        normalized["exchange_fingerprint"] = (
            f"{symbol}_{side}_{qty_str}"
        )

    return normalized
