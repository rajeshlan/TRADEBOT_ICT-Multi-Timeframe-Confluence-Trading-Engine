import yaml
import time
import datetime
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ✅ DATA SOURCE & ENGINE IMPORTS
from data.candles import get_candles, get_current_candle 
from engine.evaluator import Evaluator
from engine.signal_manager import SignalManager
from engine.trade_resolver import resolve_trades
from core.setup_memory import SetupMemory

# ✅ SHARED EXECUTOR: Singleton instance from core.executor
from core.executor import executor

from alerts.telegram import TelegramAlerter
from alerts.formatter import format_signal
from storage.trade_logger import log_trade, load_active_trades
from analytics.performance import get_stats
from risk.kelly import kelly_fraction

# --- 1. CONFIGURATION & CONSTRAINTS ---
MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", 2))
MAX_RISK_PER_TRADE = float(os.getenv("MAX_RISK_PER_TRADE", 2.0))
MIN_SIGNAL_SCORE = int(os.getenv("MIN_SIGNAL_SCORE", 60))

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# --- 2. INITIALIZATION ---
alerter = TelegramAlerter(BOT_TOKEN, CHAT_ID)
evaluator = Evaluator()
manager = SignalManager()
setup_memory = SetupMemory(cooldown_seconds=3600)

with open("config/pairs.yaml") as f:
    config = yaml.safe_load(f)
pairs = config["pairs"]

def run_cycle():
    """
    Encapsulates a single scanning and resolution pass.
    """
    print(f"\n⏱ Cycle started at {time.strftime('%H:%M:%S')}...")

    # --- PHASE A: RESOLUTION & EXECUTION ---
    # The resolver handles executing pending trades and syncing active ones.
    print("⚖️ Running Trade Resolver & Exchange Sync...")
    resolve_trades(get_current_candle)

    # --- PHASE B: SCANNING ---
    
    # ✅ STEP 2 FIX: Real-time Exchange Position Check
    # We query Bybit directly to see how many positions are actually open.
    try:
        exchange_positions = executor.get_positions() # Fetches all positions
        
        # Filter for positions where size > 0 (actually active)
        real_open_positions = [
            p for p in exchange_positions.get("result", {}).get("list", [])
            if float(p.get("size", 0)) > 0
        ]
        
        active_count = len(real_open_positions)
        print(f"📡 EXCHANGE CHECK: {active_count} active positions found on Bybit.")

    except Exception as e:
        print(f"⚠️ [EXCHANGE_ERROR] Could not fetch positions: {e}")
        # Fallback to JSON if exchange check fails to prevent over-leveraging
        active_list = load_active_trades() or []
        active_count = len([t for t in active_list if t.get("is_active")])

    for pair in pairs:
        symbol = pair["symbol"]
        timeframes = pair["timeframes"]
        results = {}

        # 1. Global Portfolio Limit Check (Exchange Truth)
        if active_count >= MAX_OPEN_TRADES:
            print(f"🛑 [LIMIT] Max trades reached ({active_count}/{MAX_OPEN_TRADES}). Skipping scan.")
            break

        # 2. Check Symbol-Specific State in JSON
        # This prevents opening a second trade for a symbol that is already PENDING or ACTIVE
        active_list = load_active_trades() or []
        existing_trade = next(
            (
                t for t in active_list
                if t.get("symbol") == symbol
                and t.get("status") in ["PENDING", "OPEN", "ACTIVE"]
            ),
            None
        )

        if existing_trade:
            print(f"⏳ [SKIP] {symbol} already exists in active_trades.")
            continue

        for tf in timeframes:
            candles = get_candles(symbol, tf)
            if not candles:
                continue
            
            result = evaluator.run(symbol, tf, candles)
            results[tf] = result

        # 3. Confluence & Decision Engine
        decision = manager.process(symbol, results)

        if decision:
            # 4. Filter Quality & Duplicates
            score = decision.get("confluence_score", 0)
            if score < MIN_SIGNAL_SCORE or setup_memory.is_duplicate(decision):
                print(f"❌ [REJECTED] {symbol} (Score: {score}) or Duplicate.")
                continue

            # 5. Risk Management
            stats = get_stats()
            kelly_val = kelly_fraction(stats["winrate"], stats["rr"]) if stats else 0.02
            risk = min(kelly_val * 100, MAX_RISK_PER_TRADE)
            decision["risk_pct"] = round(risk, 2)

            # --- PHASE C: SIGNAL NOTIFICATION & LOGGING ---
            
            # 1. Format and notify via Telegram
            msg = format_signal(decision)
            print(f"🔥 HIGH QUALITY SIGNAL FOUND: {symbol}")
            alerter.send(msg)

            # 2. DEFERRED EXECUTION LOGIC
            current_balance = executor.get_balance()
            
            # Record the intent in active_trades.json
            log_trade(decision, current_balance)
            
            # Since we just logged a trade that will become active, 
            # increment active_count to prevent multiple entries in one cycle
            active_count += 1
            
            print(f"📡 SIGNAL LOGGED: {symbol} | Awaiting resolver execution.")

    print(f"💤 Scan complete. Resting for 25 seconds...")
    time.sleep(25)

# --- GLOBAL WATCHDOG ---
print("🚀 TRADEBOT_ICT IS LIVE | Monitoring Markets...")

while True:
    try:
        run_cycle()
    except Exception as e:
        print(f"\n🛑 [CRASH] System Error: {e}")
        time.sleep(10)