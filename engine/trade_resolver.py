import time
import json
from storage.trade_logger import (
    save_trades, 
    load_active_trades, 
    load_closed_trades, 
    ACTIVE_FILE, 
    CLOSED_FILE
)
from storage.excel_logger import append_trade_to_excel

# 🔧 STEP 3A — IMPORT STATE
from core.trade_state import TradeStateManager

state = TradeStateManager()

def close_trade(trade, exit_price, result):
    """
    Standardizes trade closure with professional PnL modeling.
    Calculates PnL based on account-relative risk and updates final metadata.
    """
    trade["status"] = "CLOSED"
    trade["closed_at"] = time.time()
    trade["exit_price"] = exit_price
    trade["result"] = result

    # --- PnL POSITION MODEL ---
    entry = trade["entry"]
    balance = trade.get("balance_snapshot", 100)
    # Risk % converted to decimal (e.g., 2% -> 0.02)
    risk_pct = trade.get("risk_pct", 2) / 100 
    position_size = balance * risk_pct

    # Calculate price movement as a percentage of entry
    if trade["bias"] == "BULLISH":
        move = (exit_price - entry) / entry
    else:
        move = (entry - exit_price) / entry

    # PnL = Total Position Value * Price % Change
    pnl_value = position_size * move
    trade["pnl"] = round(pnl_value, 4)
    trade["pnl_pct"] = round((pnl_value / balance) * 100, 4)
    
    return trade

def resolve_trades(get_candle_func):
    """
    🚀 PROFESSIONAL EXECUTION RESOLVER (v3.7)
    Handles the full PENDING -> ACTIVE -> CLOSED lifecycle.
    Includes TTL timeouts, volatility buffers, and real-time Excel logging.
    """
    active_list = load_active_trades()
    closed_history = load_closed_trades()
    
    if not active_list:
        return

    new_active = []
    changes_made = False

    for trade in active_list:
        # --- 1. FETCH MARKET DATA ---
        symbol = trade["symbol"]
        candle = get_candle_func(symbol)
        
        if candle is None:
            new_active.append(trade)
            continue

        # --- 2. UPDATE AGE & STATE ---
        trade["candles_seen"] = trade.get("candles_seen", 0) + 1
        changes_made = True 

        high, low, close = candle["high"], candle["low"], candle["close"]
        entry = trade["entry"]
        
        # --- 3. TIME-TO-LIVE (TTL) FILTER ---
        # ⚠️ CASE: TIMEOUT
        if trade["candles_seen"] > 100:
            print(f"⏰ [TIMEOUT] {symbol} stale after 100 candles. Closing @ {close}")
            closed_trade = close_trade(trade, close, "TIMEOUT")
            closed_history.append(closed_trade)
            append_trade_to_excel(closed_trade)
            
            # 🔥 RELEASE LOCK
            state.close_trade(symbol)
            continue

        # --- 4. ENTRY ACTIVATION (PENDING -> ACTIVE) ---
        if trade["status"] == "PENDING":
            if low <= entry <= high:
                trade["status"] = "ACTIVE"
                trade["activated_at"] = time.time()
                print(f"✅ [ACTIVATED] {symbol} Limit Fill @ {entry}")
            else:
                new_active.append(trade)
                continue

        # --- 5. VOLATILITY BUFFER ---
        if trade["candles_seen"] < 3:
            new_active.append(trade)
            continue

        # --- 6. EXIT RESOLUTION (SL/TP) ---
        resolved = False
        sl, tp = trade["sl"], trade["tp"]

        if trade["bias"] == "BULLISH":
            # ⚠️ CASE: BULLISH SL hit
            if low <= sl:
                closed_trade = close_trade(trade, sl * 0.999, "LOSS")
                closed_history.append(closed_trade)
                append_trade_to_excel(closed_trade)
                
                # 🔥 RELEASE LOCK
                state.close_trade(symbol)
                resolved = True
            
            # ⚠️ CASE: BULLISH TP hit
            elif high >= tp:
                closed_trade = close_trade(trade, tp * 0.999, "WIN")
                closed_history.append(closed_trade)
                append_trade_to_excel(closed_trade)
                
                # 🔥 RELEASE LOCK
                state.close_trade(symbol)
                resolved = True

        else: # BEARISH
            # ⚠️ CASE: BEARISH SL hit
            if high >= sl:
                closed_trade = close_trade(trade, sl * 1.001, "LOSS")
                closed_history.append(closed_trade)
                append_trade_to_excel(closed_trade)
                
                # 🔥 RELEASE LOCK
                state.close_trade(symbol)
                resolved = True
            
            # ⚠️ CASE: BEARISH TP hit
            elif low <= tp:
                closed_trade = close_trade(trade, tp * 1.001, "WIN")
                closed_history.append(closed_trade)
                append_trade_to_excel(closed_trade)
                
                # 🔥 RELEASE LOCK
                state.close_trade(symbol)
                resolved = True

        if not resolved:
            new_active.append(trade)

    # --- 7. ATOMIC STORAGE UPDATE ---
    if changes_made:
        try:
            ACTIVE_FILE.write_text(json.dumps(new_active, indent=2))
            CLOSED_FILE.write_text(json.dumps(closed_history, indent=2))
            save_trades(new_active + closed_history)
            print(f"⚖️ [RESOLVER] Sync: {len(new_active)} Pending/Active | {len(closed_history)} Total History")
        except Exception as e:
            print(f"❌ [STORAGE ERROR] Failed to sync trade files: {e}")