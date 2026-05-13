import yaml
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ✅ STEP 1: IMPORT EXECUTION CONTEXT
from core.execution_context import execution_context

# DATA SOURCE & ENGINE IMPORTS
from data.candles import get_candles, get_current_candle 
from engine.evaluator import Evaluator
from engine.signal_manager import SignalManager
from engine.trade_resolver import resolve_trades
from core.setup_memory import SetupMemory

# ✅ SYSTEM STATE (Shared instance for drawdown protection)
from core.system_state import drawdown_guard

# SHARED EXECUTOR & ALERTS
from core.executor import executor
from alerts.telegram import TelegramAlerter
from alerts.formatter import format_signal
from storage.trade_logger import log_trade, load_active_trades
from analytics.performance import get_stats
from risk.kelly import kelly_fraction

# ✅ STEP 2: IMPORT RUNTIME LOGGER
from utils.runtime_logger import log_runtime_event

# --- 1. CONFIGURATION ---
MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", 2))
MAX_RISK_PER_TRADE = float(os.getenv("MAX_RISK_PER_TRADE", 2.0))
MIN_SIGNAL_SCORE = int(os.getenv("MIN_SIGNAL_SCORE", 60))

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# --- 2. INITIALIZATION ---
# ✅ SET EXECUTION MODE TO LIVE
execution_context.set_mode("LIVE")

alerter = TelegramAlerter(BOT_TOKEN, CHAT_ID)
evaluator = Evaluator()
manager = SignalManager()
setup_memory = SetupMemory(cooldown_seconds=3600)

# Load trading pairs
with open("config/pairs.yaml") as f:
    config = yaml.safe_load(f)
pairs = config["pairs"]

def run_cycle():
    """
    Main logic cycle: Resolve -> Sync -> Scan -> Execute
    """
    print(f"\n⏱ Cycle started at {time.strftime('%H:%M:%S')}...")
    print(f"🧠 EXECUTION MODE: {execution_context.mode}")

    # --- PHASE A: RESOLUTION & EXCHANGE SYNC ---
    print("⚖️ Running Trade Resolver & Exchange Sync...")
    resolve_trades(get_current_candle)

    # --- PHASE B: AUTHORITATIVE STATE RECONCILIATION ---
    try:
        real_open_positions = executor.get_all_positions()
        exchange_active_count = len(real_open_positions)
        active_list = load_active_trades() or []
        
        pending_reservations = [
            t for t in active_list
            if (
                t.get("status") in ["PENDING", "EXECUTING"]
                and (time.time() - t.get("created_at", 0)) < 120
            )
        ]

        reserved_slots = exchange_active_count + len(pending_reservations)

        print(
            f"📡 EXCHANGE CHECK: {exchange_active_count} live | "
            f"🧠 FRESH PENDING: {len(pending_reservations)} | "
            f"📦 TOTAL RESERVED: {reserved_slots}/{MAX_OPEN_TRADES}"
        )

    except Exception as e:
        print(f"⚠️ [EXCHANGE_ERROR] Falling back to local state: {e}")
        active_list = load_active_trades() or []
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
            print(f"🛑 [LIMIT] Max slots reached. Skipping scan.")
            # ✅ LOG SYSTEM LIMIT EVENT
            log_runtime_event(
                event_type="SYSTEM_LIMIT",
                data={
                    "reserved_slots": reserved_slots,
                    "max_open_trades": MAX_OPEN_TRADES
                }
            )
            break

        # 2. Check Symbol-Specific State
        existing_trade = next(
            (t for t in active_list if t.get("symbol") == symbol and t.get("status") in ["PENDING", "EXECUTING", "OPEN", "ACTIVE"]),
            None
        )

        if existing_trade:
            print(f"⏳ [SKIP] {symbol} is already active.")
            # ✅ LOG SYMBOL SKIP EVENT
            log_runtime_event(
                event_type="SYMBOL_SKIPPED",
                symbol=symbol,
                data={"reason": "ALREADY_ACTIVE"}
            )
            continue

        # 3. Timeframe Evaluation
        for tf in timeframes:
            candles = get_candles(symbol, tf)
            if not candles: continue
            result = evaluator.run(symbol, tf, candles)
            results[tf] = result

        # 4. Decision Engine
        decision = manager.process(symbol, results)

        if decision:
            score = decision.get("confluence_score", 0)
            
            if score < MIN_SIGNAL_SCORE or setup_memory.is_duplicate(decision):
                print(f"❌ [REJECTED] {symbol} (Score: {score}) or Duplicate Setup.")
                # ✅ LOG REJECTION EVENT
                log_runtime_event(
                    event_type="SETUP_REJECTED",
                    symbol=symbol,
                    data={
                        "reason": "LOW_SCORE_OR_DUPLICATE",
                        "score": score
                    }
                )
                continue

            # 5. Risk Management
            stats = get_stats()
            kelly_val = kelly_fraction(stats["winrate"], stats["rr"]) if stats else 0.02
            risk = min(kelly_val * 100, MAX_RISK_PER_TRADE)
            decision["risk_pct"] = round(risk, 2)

            # --- PHASE D: SIGNAL NOTIFICATION & LOGGING ---
            msg = format_signal(decision)
            print(f"🔥 HIGH QUALITY SIGNAL DETECTED: {symbol} (Score: {score})")
            
            # ✅ LOG SIGNAL CREATION EVENT
            log_runtime_event(
                event_type="SIGNAL_CREATED",
                symbol=symbol,
                data={
                    "score": score,
                    "grade": decision.get("setup_grade"),
                    "bias": decision.get("bias"),
                    "rr": decision.get("rr"),
                    "risk_pct": decision.get("risk_pct")
                }
            )

            alerter.send(msg)
            current_balance = executor.get_balance()
            decision["created_at"] = time.time()
            log_trade(decision, current_balance)
            
            reserved_slots += 1
            print(f"📡 SIGNAL LOGGED & SENT: {symbol}")

    print(f"💤 Scan complete. Resting...")
    time.sleep(25)

# --- STARTUP ---
print("""
🚀 =====================================
    TRADEBOT_ICT IS NOW LIVE
    Mode: ACTIVE EXECUTION
   =====================================
""")

while True:
    try:
        run_cycle()
    except Exception as e:
        print(f"\n🛑 [CRASH] System Error: {e}")
        time.sleep(10)