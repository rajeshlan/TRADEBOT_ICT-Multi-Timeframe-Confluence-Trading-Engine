import yaml
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# DATA SOURCE & ENGINE IMPORTS
from data.candles import get_candles, get_current_candle 
from engine.evaluator import Evaluator
from engine.signal_manager import SignalManager
from engine.trade_resolver import resolve_trades
from core.setup_memory import SetupMemory

# SHARED EXECUTOR
from core.executor import executor

from alerts.telegram import TelegramAlerter
from alerts.formatter import format_signal
from storage.trade_logger import log_trade, load_active_trades
from analytics.performance import get_stats
from risk.kelly import kelly_fraction

# --- 1. CONFIGURATION ---
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
    print(f"\n⏱ Cycle started at {time.strftime('%H:%M:%S')}...")

    # --- PHASE A: RESOLUTION & EXCHANGE SYNC ---
    # Reconciles local JSON with the exchange fingerprinting logic
    print("⚖️ Running Trade Resolver & Exchange Sync...")
    resolve_trades(get_current_candle)

    # --- PHASE B: AUTHORITATIVE STATE RECONCILIATION ---
    try:
        # 1. Fetch REAL LIVE EXCHANGE POSITIONS (The Ground Truth)
        real_open_positions = executor.get_all_positions()
        exchange_active_count = len(real_open_positions)

        # 2. Fetch LOCAL RESERVED INTENTS
        # We only count what the exchange doesn't know about yet
        active_list = load_active_trades() or []
        
        # ✅ UPDATED: Only count "fresh" pending trades (less than 120s old)
        # This prevents "phantom" trades from permanently blocking slots.
        pending_reservations = [
            t for t in active_list
            if (
                t.get("status") in ["PENDING", "EXECUTING"]
                and (time.time() - t.get("created_at", 0)) < 120
            )
        ]

        # ✅ HYBRID CALCULATION: Exchange (Active) + Local (Fresh Pending)
        reserved_slots = exchange_active_count + len(pending_reservations)

        print(
            f"📡 EXCHANGE CHECK: {exchange_active_count} live | "
            f"🧠 FRESH PENDING: {len(pending_reservations)} | "
            f"📦 TOTAL RESERVED: {reserved_slots}"
        )

    except Exception as e:
        print(f"⚠️ [EXCHANGE_ERROR] Falling back to local state: {e}")
        active_list = load_active_trades() or []
        # Fallback logic also applies the 120s rule for pending items
        reserved_slots = len([
            t for t in active_list
            if t.get("status") in ["OPEN", "ACTIVE"] or 
            (t.get("status") in ["PENDING", "EXECUTING"] and (time.time() - t.get("created_at", 0)) < 120)
        ])

    # --- PHASE C: SCANNING ---
    for pair in pairs:
        symbol = pair["symbol"]
        timeframes = pair["timeframes"]
        results = {}

        # 1. Global Portfolio Limit Check
        if reserved_slots >= MAX_OPEN_TRADES:
            print(
                f"🛑 [LIMIT] Max reserved slots reached "
                f"({reserved_slots}/{MAX_OPEN_TRADES}). Skipping scan."
            )
            break

        # 2. Check Symbol-Specific State
        existing_trade = next(
            (t for t in active_list if t.get("symbol") == symbol and t.get("status") in ["PENDING", "EXECUTING", "OPEN", "ACTIVE"]),
            None
        )

        if existing_trade:
            print(f"⏳ [SKIP] {symbol} is already active or being processed.")
            continue

        for tf in timeframes:
            candles = get_candles(symbol, tf)
            if not candles: continue
            
            result = evaluator.run(symbol, tf, candles)
            results[tf] = result

        # 3. Decision Engine
        decision = manager.process(symbol, results)

        if decision:
            score = decision.get("confluence_score", 0)
            if score < MIN_SIGNAL_SCORE or setup_memory.is_duplicate(decision):
                print(f"❌ [REJECTED] {symbol} (Score: {score}) or Duplicate.")
                continue

            # 4. Risk Management (Kelly Criterion)
            stats = get_stats()
            # Default to 2% if stats are missing
            kelly_val = kelly_fraction(stats["winrate"], stats["rr"]) if stats else 0.02
            risk = min(kelly_val * 100, MAX_RISK_PER_TRADE)
            decision["risk_pct"] = round(risk, 2)

            # --- PHASE D: SIGNAL NOTIFICATION & LOGGING ---
            msg = format_signal(decision)
            print(f"🔥 HIGH QUALITY SIGNAL: {symbol}")
            alerter.send(msg)

            current_balance = executor.get_balance()
            # Ensure decision object includes a 'created_at' timestamp for future loops
            decision["created_at"] = time.time()
            log_trade(decision, current_balance)
            
            # 🚀 TEMPORARY INCREMENT
            reserved_slots += 1
            print(f"📡 SIGNAL LOGGED: {symbol}")

    print(f"💤 Scan complete. Resting...")
    time.sleep(25)

print("🚀 TRADEBOT_ICT IS LIVE")
while True:
    try:
        run_cycle()
    except Exception as e:
        print(f"\n🛑 [CRASH] System Error: {e}")
        time.sleep(10)