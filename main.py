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
from core.trade_state import TradeStateManager

# --- 1. CONFIGURATION & CONSTRAINTS ---
MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", 2))
MAX_RISK_PER_TRADE = float(os.getenv("MAX_RISK_PER_TRADE", 2.0))
MIN_SIGNAL_SCORE = int(os.getenv("MIN_SIGNAL_SCORE", 60))

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# --- 2. INITIALIZATION ---
state = TradeStateManager()  
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
    # The resolver now handles both executing pending trades and syncing active ones.
    print("⚖️ Running Trade Resolver & Exchange Sync...")
    resolve_trades(get_current_candle)

    # --- PHASE B: SCANNING ---
    for pair in pairs:
        symbol = pair["symbol"]
        timeframes = pair["timeframes"]
        results = {}

        # 1. Check Global Portfolio Limits
        active_list = load_active_trades()
        active_count = len([t for t in active_list if t.get("is_active")]) if active_list else 0
        
        if active_count >= MAX_OPEN_TRADES:
            print(f"🛑 [LIMIT] Max trades reached ({active_count}/{MAX_OPEN_TRADES}). Skipping scan.")
            break

        # 2. Check Symbol-Specific Local State
        if state.is_symbol_active(symbol):
            print(f"⏳ [ACTIVE] {symbol} already has an open position or pending signal. Skipping.")
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
            kelly = kelly_fraction(stats["winrate"], stats["rr"]) if stats else 0.02
            risk = min(kelly * 100, MAX_RISK_PER_TRADE)
            decision["risk_pct"] = round(risk, 2)
            
            # 6. Final State Check
            if state.is_symbol_active(symbol):
                continue

            # --- PHASE C: SIGNAL NOTIFICATION & LOGGING ---
            
            # 1. Format and notify via Telegram
            msg = format_signal(decision)
            print(f"🔥 HIGH QUALITY SIGNAL FOUND: {symbol}")
            alerter.send(msg)

            # 2. DEFERRED EXECUTION LOGIC
            # Instead of placing the order here, we log it and let the resolver handle it.
            current_balance = executor.get_balance()
            
            # Record the intent in active_trades.json
            log_trade(decision, current_balance)
            
            # Lock the local state so we don't double-signal
            state.open_trade(symbol)
            
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