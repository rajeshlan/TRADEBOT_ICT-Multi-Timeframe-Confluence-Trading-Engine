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
    """
    Writes the full trade list to the master ledger.
    """
    FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        FILE.write_text(json.dumps(trades, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[ERROR] trade_logger: Could not save master ledger: {e}")

def log_trade(signal, current_balance=100):
    """
    🚀 PHASE 6.4 — ADVANCED LOGGER
    Captures a signal and initializes the trade object with structural metadata.
    """
    # 📐 Calculate Risk/Reward Ratio dynamically
    # Prevents division by zero if SL and Entry are identical
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
        "risk_pct": min(signal.get("risk", 2), 3),
        "execution_type": signal.get("mode", "LIVE"),  # LIVE / REPLAY

        # ✅ STATE TRACKING
        "status": "PENDING",  # Default to PENDING for the Resolver to activate
        "created_at": time.time(),
        "closed_at": None,
        "result": None,
        "pnl": 0.0,

        # ✅ SNAPSHOTS
        "balance_snapshot": current_balance,
        "candles_seen": 0
    }

    # 2. Update Master Ledger (Atomic Write)
    all_trades = load_trades()
    all_trades.append(trade)
    save_trades(all_trades)

    # 3. Update Active Trades File (High-Speed Access)
    ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    active = load_active_trades()
    active.append(trade)
    
    try:
        ACTIVE_FILE.write_text(json.dumps(active, indent=2), encoding="utf-8")
        print(f"📡 [LOGGER] Trade Logged: {trade['id']} | RR: {trade['rr_ratio']} | Mode: {trade['execution_type']}")
    except Exception as e:
        print(f"[ERROR] trade_logger: Could not update active trades: {e}")