import yaml
import time

from data.candles import get_candles, get_current_price
from engine.evaluator import Evaluator
from engine.signal_manager import SignalManager
from engine.trade_resolver import resolve_trades
from core.setup_memory import SetupMemory
from alerts.telegram import TelegramAlerter
from alerts.formatter import format_signal
from storage.trade_logger import log_trade
from analytics.performance import get_stats     # ✅ Added Import
from risk.kelly import kelly_fraction           # ✅ Added Import

# 🔐 SECURE CREDENTIALS
BOT_TOKEN = "8638812072:AAGygbCOKHkRH3UYbHpQ38bkuBXL1HxXOKs"
CHAT_ID = "1041385548"

alerter = TelegramAlerter(BOT_TOKEN, CHAT_ID)
evaluator = Evaluator()
manager = SignalManager()
setup_memory = SetupMemory(cooldown_seconds=3600)

# Load monitoring configuration
with open("config/pairs.yaml") as f:
    config = yaml.safe_load(f)

pairs = config["pairs"]

print("🚀 TRADEBOT_ICT is running... Monitoring markets.")

while True:
    # ⏱ Watchdog: Terminal indicator for the start of a fresh market scan
    print(f"\n⏱ New cycle starting at {time.strftime('%H:%M:%S')}...")

    for pair in pairs:
        symbol = pair["symbol"]
        timeframes = pair["timeframes"]

        results = {}

        for tf in timeframes:
            # ✅ Protected Candle Fetch
            try:
                candles = get_candles(symbol, tf)
            except Exception as e:
                print(f"[MAIN ERROR] {symbol}-{tf}: {e}")
                continue
            
            if not candles:
                continue
            
            # Run ICT Analysis
            result = evaluator.run(symbol, tf, candles)
            results[tf] = result

            # 🔥 MICRO-THROTTLE
            time.sleep(0.3)

        # 🧠 Confluence Engine
        decision = manager.process(symbol, results)

        if decision:
            # 🚫 DUPLICATION FILTER
            if setup_memory.is_duplicate(decision):
                print(f"[SKIP] Duplicate setup: {decision['symbol']}")
                continue

            # 📊 DYNAMIC RISK CALCULATION (Kelly Criterion)
            # Fetch bot performance stats from storage
            stats = get_stats()

            if stats and stats.get("winrate") and stats.get("rr"):
                # Calculate optimal fraction based on historical edge
                kelly = kelly_fraction(stats["winrate"], stats["rr"])
            else:
                # Default to a safe 2% risk if stats aren't mature enough
                kelly = 0.02 

            # Inject calculated risk into the decision dictionary
            decision["risk"] = round(kelly * 100, 2)

            # 📡 Formatting and Transmission
            msg = format_signal(decision)
            print(f"🔥 SIGNAL DETECTED: \n{msg}")
            
            print("📡 Sending alert to Telegram...") 
            alerter.send(msg)

            # 📊 LOG TRADE
            log_trade(decision)
            print(f"✅ Trade logged to storage (Risk: {decision['risk']}%).")

    # ⚖️ TRADE RESOLVER: Check active trades against current prices
    print("⚖️ Running Trade Resolver...")
    resolve_trades(get_current_price)

    # 💤 LOOP PROTECTION
    print(f"💤 Scan complete. Resting for 25 seconds...")
    time.sleep(25)