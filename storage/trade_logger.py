import json
import time
from pathlib import Path

# ✅ IMPORT SCHEMA NORMALIZER
from core.trade_schema import normalize_trade_schema

# --- 1. FILE PATHS ---
FILE = Path("storage/trades.json")
ACTIVE_FILE = Path("storage/active_trades.json")
CLOSED_FILE = Path("storage/closed_trades.json")

# --- 2. INTERNAL UTILITIES ---

def _safe_load(file: Path):
    """
    🛡️ TRANSACTIONAL LOADER
    Handles partial writes and race conditions with a 3-stage retry mechanism.
    """
    if not file.exists():
        return []

    for _ in range(3):  # Retry loop for file-lock handling
        try:
            content = file.read_text(encoding="utf-8").strip()
            if not content:
                return []
            return json.loads(content)
        except (json.JSONDecodeError, IOError, PermissionError):
            time.sleep(0.05)

    print(f"[WARNING] trade_logger: Failed to read {file.name} after 3 attempts.")
    return []

def _atomic_write_json(file: Path, data):
    """
    🚀 ATOMIC JSON PERSISTENCE
    Prevents partial writes and corruption by using a temp-file swap.
    """
    tmp_file = file.with_suffix(".tmp")

    try:
        # Ensure directory exists
        file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        # Atomic rename/replace
        tmp_file.replace(file)
    except Exception as e:
        if tmp_file.exists():
            tmp_file.unlink()  # Clean up temp file on failure
        raise e

# --- 3. PUBLIC LOADERS ---

def load_active_trades():
    return _safe_load(ACTIVE_FILE)

def load_closed_trades():
    return _safe_load(CLOSED_FILE)

def load_trades():
    return _safe_load(FILE)

# --- 4. PERSISTENCE LOGIC ---

def save_trades(trades):
    """Writes the full trade list to the master ledger atomically."""
    try:
        # Normalize all trades before saving
        normalized_trades = [normalize_trade_schema(t) for t in trades]
        _atomic_write_json(FILE, normalized_trades)
    except Exception as e:
        print(f"[ERROR] trade_logger: Could not save master ledger: {e}")

def save_active_trades(trades):
    """
    🚀 ATOMIC ACTIVE TRADE PERSISTENCE
    Includes UUID deduplication to ensure state integrity.
    """
    try:
        # Normalize safely
        trades = [normalize_trade_schema(t) for t in trades]

        # ✅ UUID Deduplication Layer
        deduped = {}

        for trade in trades:
            trade_uuid = trade.get("trade_uuid")
            if not trade_uuid:
                continue

            existing = deduped.get(trade_uuid)

            # If it's a new UUID, add it. 
            # If it exists, keep the one with the most recent 'last_synced_at'
            if not existing:
                deduped[trade_uuid] = trade
                continue

            existing_sync = existing.get("last_synced_at", 0) or 0
            new_sync = trade.get("last_synced_at", 0) or 0

            if new_sync >= existing_sync:
                deduped[trade_uuid] = trade

        final_trades = list(deduped.values())
        _atomic_write_json(ACTIVE_FILE, final_trades)

    except Exception as e:
        print(f"[ERROR] trade_logger: Could not save active trades: {e}")

def log_trade(signal, current_balance):
    """
    🚀 STATE-AWARE LOGGER
    Initializes a new trade in PENDING state and persists it.
    """
    denominator = abs(signal["entry"] - signal["sl"])
    rr_calc = abs((signal["tp"] - signal["entry"]) / denominator) if denominator != 0 else 0

    trade = normalize_trade_schema({
        "symbol": signal["symbol"],
        "bias": signal["bias"],
        "entry": signal["entry"],
        "sl": signal["sl"],
        "tp": signal["tp"],
        "rr_ratio": round(rr_calc, 2),
        "setup_id": signal.get("setup_id"),
        "decision_id": signal.get("decision_id"),
        "timeframes": signal.get("timeframes", []),
        "confluence_score": signal.get("confluence_score"),
        "setup_grade": signal.get("setup_grade"),
        "archetype": signal.get("archetype"),
        "market_regime": signal.get("market_regime"),
        "session": signal.get("session"),
        "risk_pct": signal.get("risk_pct"),
        "risk_pct_distance": signal.get("risk_pct_distance"),
        "expected_value_r": signal.get("expected_value_r"),
        "approval_threshold_r": signal.get("approval_threshold_r"),
        "win_probability": signal.get("win_probability"),
        "quality_reasons": signal.get("quality_reasons", []),
        "trend_quality": signal.get("trend_quality"),
        "chop_score": signal.get("chop_score"),
        "squeeze_risk": signal.get("squeeze_risk"),
        "cascade_risk": signal.get("cascade_risk"),
        "liquidity_vacuum": signal.get("liquidity_vacuum", False),
        "funding_rate": signal.get("funding_rate"),
        "spread_bps": signal.get("spread_bps"),
        "book_imbalance": signal.get("book_imbalance"),
        "open_interest_change_pct": signal.get("open_interest_change_pct"),
        "status": "PENDING",
        "is_active": False,
        "created_at": time.time(),
        "balance_snapshot": current_balance,
        "bot_managed": True
    })

    # Setup Memory Snapshot
    try:
        from core.setup_memory import register_signal_setup
        register_signal_setup(trade)
    except Exception as e:
        print(f"[SETUP_MEMORY_ERROR] {e}")

    # Update Master Ledger
    all_trades = load_trades()
    all_trades.append(trade)
    save_trades(all_trades)

    # Update Active Trades
    active = load_active_trades()
    active.append(trade)
    save_active_trades(active)
    
    print(f"📡 [LOGGER] Trade Initialized: {trade['trade_uuid']} | Symbol: {trade['symbol']}")
    return trade

def append_closed_trade(trade):
    """Appends a completed trade to history atomically."""
    # Ensure current trade is normalized
    trade = normalize_trade_schema(trade)

    closed = _safe_load(CLOSED_FILE)
    trade_uuid = trade.get("trade_uuid")
    if trade_uuid and any(t.get("trade_uuid") == trade_uuid for t in closed):
        closed = [
            trade if t.get("trade_uuid") == trade_uuid else t
            for t in closed
        ]
    else:
        closed.append(trade)
    
    # Ensure the entire history list is normalized
    final_list = [normalize_trade_schema(t) for t in closed]

    try:
        _atomic_write_json(CLOSED_FILE, final_list)
    except Exception as e:
        print(f"[ERROR] trade_logger: Failed to append closed trade: {e}")
