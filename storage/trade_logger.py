import json
import time
from pathlib import Path

# Path to the JSON storage file
FILE = Path("storage/trades.json")

def load_trades():
    """
    🚀 PRODUCTION-SAFE LOADER
    Handles missing, empty, or corrupted files to prevent system crashes.
    """
    if not FILE.exists():
        return []

    content = FILE.read_text().strip()

    if not content:
        return []  # ✅ handle empty file safely

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        print(f"[WARNING] trade_logger: Corrupted JSON detected. Falling back to empty list.")
        return []  # ✅ fallback if corrupted 

def save_trades(trades):
    """
    Writes the trade list back to the local JSON file with clean formatting.
    """
    # Ensure the storage directory exists
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(trades, indent=2))

def log_trade(signal):
    """
    Captures a new signal and appends it to the history as an 'OPEN' trade.
    """
    trades = load_trades()

    trade = {
        "id": f"{signal['symbol']}_{int(time.time())}",
        "symbol": signal["symbol"],
        "bias": signal["bias"],
        "entry": signal["entry"],
        "sl": signal["sl"],
        "tp": signal["tp"],
        "rr": 2,
        "risk": signal.get("risk", 2), # Persist the Kelly risk for later ROI analysis
        "status": "OPEN",
        "created_at": time.time(),
        "closed_at": None,
        "result": None
    }

    trades.append(trade)
    save_trades(trades)