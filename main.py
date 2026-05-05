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

# ✅ SHARED EXECUTOR: Import the singleton instance
from core.executor import executor

from alerts.telegram import TelegramAlerter
from alerts.formatter import format_signal
from storage.trade_logger import log_trade, load_active_trades
from analytics.performance import get_stats
from risk.kelly import kelly_fraction
from core.trade_state import TradeStateManager

# --- 1. CONFIGURATION & CONSTRAINTS (FETCHED FROM .ENV) ---
MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", 2))
MAX_RISK_PER_TRADE = float(os.getenv("MAX_RISK_PER_TRADE", 2.0))
MIN_SIGNAL_SCORE = int(os.getenv("MIN_SIGNAL_SCORE", 60))

# 🔐 SECURE CREDENTIALS
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# --- 2. INITIALIZATION ---
# All components now use the shared 'executor' imported from core.executor
state = TradeStateManager()  # Tracks symbol activity and counts
alerter = TelegramAlerter(BOT_TOKEN, CHAT_ID)
evaluator = Evaluator()
manager = SignalManager()
setup_memory = SetupMemory(cooldown_seconds=3600)

# Load pairs from configuration
with open("config/pairs.yaml") as f:
    config = yaml.safe_load(f)
pairs = config["pairs"]

def run_cycle():
    """
    Encapsulates a single scanning and resolution pass.
    """
    print(f"\n⏱ Cycle started at {time.strftime('%H:%M:%S')}...")

    # --- PHASE A: RESOLUTION ---
    # Sync with exchange to update existing trade states
    print("⚖️ Running Trade Resolver & Exchange Sync...")
    resolve_trades(get_current_candle)

    # --- PHASE B: SCANNING ---
    for pair in pairs:
        symbol = pair["symbol"]
        timeframes = pair["timeframes"]
        results = {}

        # 1. Check Global Portfolio Limits
        active_list = load_active_trades()
        # Count only trades that are actually live on the exchange
        active_count = len([t for t in active_list if t.get("is_active")]) if active_list else 0
        
        if active_count >= MAX_OPEN_TRADES:
            print(f"🛑 [LIMIT] Max trades reached ({active_count}/{MAX_OPEN_TRADES}). Skipping scan.")
            break

        # 2. Check Symbol-Specific State (Local Guard)
        if state.is_symbol_active(symbol):
            print(f"⏳ [ACTIVE] {symbol} already has an open position. Skipping.")
            continue

        for tf in timeframes:
            # Fetch data for ICT Analysis (MSS, FVG, Liquidity)
            candles = get_candles(symbol, tf)
            if not candles:
                print(f"[SKIP] {symbol}-{tf} returned no data.")
                continue
            
            result = evaluator.run(symbol, tf, candles)
            results[tf] = result

        # 3. Confluence & Decision Engine
        decision = manager.process(symbol, results)

        if decision:
            # QUALITY FILTER
            score = decision.get("confluence_score", 0)
            if score < MIN_SIGNAL_SCORE:
                print(f"❌ [REJECTED] {symbol} setup too weak (Score: {score}/{MIN_SIGNAL_SCORE})")
                continue

            # 4. Duplication Cooldown (Time-based filter)
            if setup_memory.is_duplicate(decision):
                print(f"[SKIP] Duplicate setup detected: {symbol}")
                continue

            # 5. Risk Calculation (Kelly + Hard Cap)
            stats = get_stats()
            if stats and stats.get("winrate") and stats.get("rr"):
                kelly = kelly_fraction(stats["winrate"], stats["rr"])
            else:
                kelly = 0.02 # Conservative fallback

            # Apply Risk Limits
            risk = min(kelly * 100, MAX_RISK_PER_TRADE)
            decision["risk_pct"] = round(risk, 2)
            
            # 6. Final Execution Guard (Re-check before logging)
            if state.is_symbol_active(symbol):
                continue

            # 7. Transmission & Logging
            msg = format_signal(decision)
            print(f"🔥 HIGH QUALITY SIGNAL: \n{msg}")
            
            # Send Telegram Alert
            alerter.send(msg)

            # Log Trade (Initializes balance snapshot for PnL tracking)
            # ✅ CORRECTED: Uses the shared singleton 'executor'
            current_balance = executor.get_balance() 
            log_trade(decision, current_balance)
            
            # Lock State locally to prevent duplicate scanning for this symbol
            state.open_trade(symbol) 
            print(f"✅ Trade sent to Resolver (Risk: {decision['risk_pct']}%).")

    print(f"💤 Scan complete. Resting for 25 seconds...")
    time.sleep(25)

# --- 🔥 GLOBAL WATCHDOG LOOP ---
print("🚀 TRADEBOT_ICT IS LIVE | Monitoring Markets...")

while True:
    try:
        run_cycle()
    except Exception as e:
        # 🛡️ ANTI-CRASH PROTECTION
        print(f"\n🛑 [CRASH] System Error: {e}")
        print("🛠️ Restarting engine in 10 seconds...")
        time.sleep(10)