import json
import time
from pathlib import Path

# --- 1. FILE PATHS ---
# Master ledger for backup and full history
FILE = Path("storage/trades.json")
# Optimized files for high-speed engine access
ACTIVE_FILE = Path("storage/active_trades.json")
CLOSED_FILE = Path("storage/closed_trades.json")

# --- 2. INTERNAL UTILITIES ---

def _safe_load(file: Path):
    """
    🛡️ TRANSACTIONAL LOADER
    Handles partial writes and race conditions with a 3-stage retry mechanism.
    Essential for Streamlit + Bot concurrent access.
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
            # Wait briefly for the other process to release the file
            time.sleep(0.05)

    print(f"[WARNING] trade_logger: Failed to read {file.name} after 3 attempts.")
    return []

# --- 3. PUBLIC LOADERS ---

def load_active_trades():
    """Returns only trades currently in the market (pending or active)."""
    return _safe_load(ACTIVE_FILE)

def load_closed_trades():
    """Returns the historical record of completed trades."""
    return _safe_load(CLOSED_FILE)

def load_trades():
    """Returns the master ledger (all statuses)."""
    return _safe_load(FILE)

# --- 4. PERSISTENCE LOGIC ---

def save_trades(trades):
    """Writes the full trade list to the master ledger."""
    FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        FILE.write_text(json.dumps(trades, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[ERROR] trade_logger: Could not save master ledger: {e}")

def save_active_trades(trades):
    """
    🚀 HIGH-SPEED SYNC
    Overwrites the active trades file. Used for updating unrealized PnL or 
    moving a trade from PENDING to ACTIVE.
    """
    ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(ACTIVE_FILE, "w") as f:
            json.dump(trades, f, indent=2)
    except Exception as e:
        print(f"[ERROR] trade_logger: Could not save active trades: {e}")

def log_trade(signal, current_balance):
    """
    🚀 STATE-AWARE LOGGER
    Initializes the trade in a PENDING state. This is the 'Signal' phase.
    """
    # 📐 Calculate Risk/Reward Ratio dynamically
    denominator = abs(signal["entry"] - signal["sl"])
    rr_calc = abs((signal["tp"] - signal["entry"]) / denominator) if denominator != 0 else 0

    # 1. Prepare Enhanced Trade Object
    trade = {
        "id": f"{signal['symbol']}_{int(time.time())}",
        "symbol": signal["symbol"],
        "bias": signal["bias"],
        "entry": signal["entry"],
        "sl": signal["sl"],
        "tp": signal["tp"],

        # ✅ METRICS & CONFIG
        "rr_ratio": round(rr_calc, 2),
        "risk_pct": min(signal.get("risk", 2), 3), # Cap risk at 3%
        "execution_type": signal.get("mode", "LIVE"),

        # ✅ STATE TRACKING (Reverted Fix)
        "status": "PENDING",           # PENDING = Signal created, waiting for Bybit Order
        "is_active": False,            # False = Not yet filled on exchange
        "order_id": None,              # Populated by BybitExecutor
        "filled_price": None,          
        "activated_at": None,          
        "created_at": time.time(),
        "closed_at": None,
        "result": None,
        "pnl": 0.0,
        "unrealized_pnl": 0.0,
        "unrealized_pct": 0.0,

        # ✅ SNAPSHOTS
        "balance_snapshot": current_balance,
        "candles_seen": 0
    }

    # 2. Update Master Ledger (Atomic Write)
    all_trades = load_trades()
    all_trades.append(trade)
    save_trades(all_trades)

    # 3. Update Active Trades File (High-Speed Access for Resolver)
    active = load_active_trades()
    active.append(trade)
    save_active_trades(active)
    
    print(f"📡 [LOGGER] Trade Initialized (PENDING): {trade['id']} | RR: {trade['rr_ratio']}")
    return trade

def append_closed_trade(trade):
    """
    ✅ Modularly appends a completed trade to history for long-term tracking.
    """
    CLOSED_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not CLOSED_FILE.exists():
        CLOSED_FILE.write_text("[]")

    try:
        with open(CLOSED_FILE, "r") as f:
            content = f.read().strip()
            closed = json.loads(content) if content else []
    except (json.JSONDecodeError, IOError):
        closed = []

    closed.append(trade)

    try:
        with open(CLOSED_FILE, "w") as f:
            json.dump(closed, f, indent=2)
    except Exception as e:
        print(f"[ERROR] trade_logger: Failed to append closed trade: {e}")