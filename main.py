import yaml
import time
import datetime

# ✅ DATA SOURCE: Using full OHLC candle data for precision
from data.candles import get_candles, get_current_candle 
from engine.evaluator import Evaluator
from engine.signal_manager import SignalManager
from engine.trade_resolver import resolve_trades
from core.setup_memory import SetupMemory
from alerts.telegram import TelegramAlerter
from alerts.formatter import format_signal
from storage.trade_logger import log_trade
from analytics.performance import get_stats
from risk.kelly import kelly_fraction

# 🔧 STEP 2A — IMPORT STATE
from core.trade_state import TradeStateManager

# 🔐 SECURE CREDENTIALS
BOT_TOKEN = "8638812072:AAGygbCOKHkRH3UYbHpQ38bkuBXL1HxXOKs"
CHAT_ID = "1041385548"

# --- INITIALIZATION ---
state = TradeStateManager()  # 🔧 Initialize State Manager
alerter = TelegramAlerter(BOT_TOKEN, CHAT_ID)
evaluator = Evaluator()
manager = SignalManager()
setup_memory = SetupMemory(cooldown_seconds=3600)

# Load monitoring configuration
with open("config/pairs.yaml") as f:
    config = yaml.safe_load(f)

pairs = config["pairs"]

def run_cycle():
    """
    Encapsulates a single scanning and resolution pass.
    """
    print(f"\n⏱ New cycle starting at {time.strftime('%H:%M:%S')}...")

    for pair in pairs:
        symbol = pair["symbol"]
        timeframes = pair["timeframes"]
        results = {}

        for tf in timeframes:
            # ✅ DATA GUARD: Fetch data for analysis
            candles = get_candles(symbol, tf)
            
            if not candles:
                print(f"[SKIP] {symbol}-{tf} returned no data.")
                continue
            
            # Run ICT Analysis (MSS, FVG, Liquidity)
            result = evaluator.run(symbol, tf, candles)
            results[tf] = result

            # MICRO-THROTTLE to respect Binance IP limits
            time.sleep(0.3)

        # 🧠 Confluence Engine: Process multi-timeframe results
        decision = manager.process(symbol, results)

        if decision:
            # 🚫 DUPLICATION FILTER (Cool-down based)
            if setup_memory.is_duplicate(decision):
                print(f"[SKIP] Duplicate setup detected: {decision['symbol']}")
                continue

            # 📊 PERFORMANCE-BASED RISK CALCULATION
            stats = get_stats()
            
            # 1. Kelly Criterion sizing based on historical winrate/RR
            if stats and stats.get("winrate") and stats.get("rr"):
                kelly = kelly_fraction(stats["winrate"], stats["rr"])
            else:
                kelly = 0.02 # Conservative 2% fallback

            # 🔧 STEP 4 — FIX RISK (HARD CAP)
            kelly_pct = kelly * 100
            
            # 🔒 HARD CAP (CRITICAL)
            MAX_RISK = 2.0
            risk = min(kelly_pct, MAX_RISK)
            
            decision["risk"] = round(risk, 2)

            # 📡 TRANSMISSION
            msg = format_signal(decision)

            # 🔧 STEP 2B — BLOCK DUPLICATE TRADES
            # 🚫 BLOCK duplicate trades per symbol if already active in state
            if state.is_symbol_active(symbol):
                print(f"[BLOCKED] {symbol} already active")
                continue

            print(f"🔥 SIGNAL DETECTED: \n{msg}")
            
            print("📡 Sending alert to Telegram...") 
            alerter.send(msg)

            # 📊 LOG TRADE (With Dynamic Balance Snapshot)
            current_balance = stats["final_balance"] if stats else 100.0
            
            log_trade(decision, current_balance)
            
            # 🔧 STEP 2C — LOCK TRADE AFTER LOG
            state.open_trade(symbol) 
            
            print(f"✅ Trade logged to storage (Risk: {decision['risk']}% | Base: ${current_balance}).")

    # ⚖️ TRADE RESOLVER: Sync active/closed trades using Wick-Precision
    print("⚖️ Running Trade Resolver...")
    resolve_trades(get_current_candle)

    print(f"💤 Scan complete. Resting for 25 seconds...")
    time.sleep(25)

# --- 🔥 GLOBAL WATCHDOG LOOP ---
print("🚀 TRADEBOT_ICT is running... Monitoring markets.")

while True:
    try:
        run_cycle()
    except Exception as e:
        # 🛡️ ANTI-CRASH PROTECTION
        print(f"\n🛑 [CRASH] System Error encountered: {e}")
        print("🛠️ Restarting engine in 10 seconds...")
        time.sleep(10)