import hashlib
import time
import uuid


def short_hash(value, length=16):
    """Return a stable compact hash for exchange-safe identifiers."""
    raw = str(value or uuid.uuid4()).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]


def new_event_id(prefix="evt"):
    return f"{prefix}_{int(time.time() * 1000)}_{short_hash(uuid.uuid4(), 8)}"


def build_setup_id(signal):
    seed = "|".join(
        str(signal.get(k, ""))
        for k in ("symbol", "bias", "entry", "sl", "tp", "timeframes")
    )
    return f"setup_{short_hash(seed, 18)}"


def build_decision_id(signal):
    seed = "|".join(
        str(signal.get(k, ""))
        for k in ("setup_id", "symbol", "bias", "confluence_score", "created_at")
    )
    return f"decision_{short_hash(seed, 18)}"


def build_order_intent_id(trade):
    """Stable idempotency key for Bybit orderLinkId. Keep under 36 chars."""
    seed = "|".join(
        str(trade.get(k, ""))
        for k in ("trade_uuid", "symbol", "bias", "entry", "sl", "tp")
    )
    return f"tb_{short_hash(seed, 24)}"
