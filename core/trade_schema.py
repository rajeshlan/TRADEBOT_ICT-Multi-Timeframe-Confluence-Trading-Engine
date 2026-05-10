import time
import uuid
from copy import deepcopy
from datetime import datetime

# ✅ MASTER TRADE SCHEMA
# This serves as the single source of truth for all trade objects in the system.
BASE_TRADE_SCHEMA = {
    # Identity
    "trade_uuid": None,
    "exchange_fingerprint": None,    # Deterministic key for exchange matching
    "exchange_position_id": None,    # ID provided by the exchange (e.g., Bybit)
    "id": None,
    "order_id": None,

    # Core
    "symbol": None,
    "bias": None,
    "status": "PENDING",

    # Pricing
    "entry": None,
    "filled_price": None,
    "entry_price_real": None,
    "exit_price": None,

    # Risk
    "sl": None,
    "tp": None,
    "rr_ratio": 0.0,

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

    # ✅ DETERMINISTIC ID GENERATION
    # ONLY generate UUID for brand new trades.
    if not normalized.get("trade_uuid"):
        symbol = normalized.get("symbol", "UNKNOWN")
        side = normalized.get("bias", "UNKNOWN")
        
        # Capture current unix timestamp for the ID suffix
        created_ts = int(time.time())

        normalized["trade_uuid"] = (
            f"TRD_{symbol}_{side}_{created_ts}"
        )

    # ✅ EXCHANGE FINGERPRINTING
    # Build deterministic exchange fingerprint if missing
    if not normalized.get("exchange_fingerprint"):
        symbol = normalized.get("symbol", "UNKNOWN")
        side = normalized.get("bias", "UNKNOWN")
        
        # Ensure entry is treated as a float for consistent rounding
        try:
            entry_val = float(normalized.get("entry") or 0)
        except (ValueError, TypeError):
            entry_val = 0.0
            
        entry_str = round(entry_val, 4)

        normalized["exchange_fingerprint"] = (
            f"{symbol}_{side}_{entry_str}"
        )

    # ✅ LIFECYCLE TIMESTAMPS
    now_iso = datetime.utcnow().isoformat()
    now_ts = int(time.time())

    # ISO strings for logs/human readability
    if not normalized["created_at"]:
        normalized["created_at"] = now_iso
    normalized["updated_at"] = now_iso

    # Unix timestamps for logic and syncing
    if not normalized.get("first_seen_at"):
        normalized["first_seen_at"] = now_ts
    
    normalized["last_synced_at"] = now_ts

    return normalized