import time
import os
from storage.trade_logger import (
    save_active_trades,
    load_active_trades,
    append_closed_trade,
    log_trade
)
from storage.excel_logger import append_trade_to_excel
from core.trade_state import TradeStateManager

# ✅ Centralized singleton executor from core
from core.executor import executor

# --- INITIALIZATION ---
state = TradeStateManager()

def normalize_qty(qty, step=0.001):
    """Ensures quantity matches exchange step size to avoid 'Invalid Qty' errors."""
    return round((qty // step) * step, 3)

def calculate_position_size(trade):
    """Calculates position size with a 5x Notional Safety Cap."""
    balance = trade.get("balance_snapshot", 100)
    risk_pct = trade.get("risk_pct", 2) / 100

    risk_amount = balance * risk_pct
    entry = trade["entry"]
    sl = trade["sl"]

    sl_distance = abs(entry - sl)
    if sl_distance <= 0:
        return 0

    qty = risk_amount / sl_distance
    max_notional = balance * 5    
    max_qty_allowed = max_notional / entry
    
    final_qty = min(qty, max_qty_allowed)
    normalized_qty = normalize_qty(final_qty)

    if normalized_qty <= 0:
        print(f"⚠️ [REJECTED] {trade['symbol']} - Qty too small after normalization.")
        return 0
        
    return normalized_qty

def close_trade(trade, exit_price, result):
    """Finalizes trade data and calculates final PnL."""
    trade["status"] = "CLOSED"
    trade["is_active"] = False
    trade["closed_at"] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    trade["exit_price"] = exit_price
    trade["result"] = result

    entry = trade.get("filled_price", trade["entry"])
    balance = trade.get("balance_snapshot", 100)

    pnl_value = trade.get("qty", 0) * (exit_price - entry)
    if trade["bias"] == "BEARISH":
        pnl_value = -pnl_value

    trade["pnl"] = round(pnl_value, 4)
    trade["pnl_pct"] = round((pnl_value / balance) * 100, 4)

    return trade

def resolve_trades(get_candle_func):
    """
    Core Engine Loop:
    Handles execution of pending trades and synchronization of active positions.
    """
    active_list = load_active_trades()
    if not active_list:
        return

    new_active = []
    changes_made = False

    for trade in active_list:
        symbol = trade["symbol"]

        # --- STEP 1: EXECUTE PENDING TRADES ---
        if not trade.get("order_id"):
            candle = get_candle_func(symbol)
            if candle is None:
                new_active.append(trade)
                continue

            entry = trade["entry"]
            sl = trade["sl"]
            
            # Risk Guard: Minimum 0.2% Stop Loss distance
            stop_dist_pct = abs(entry - sl) / entry
            if stop_dist_pct < 0.002:
                print(f"⚠️ [REJECTED] {symbol} - Stop Loss distance too small.")
                state.close_trade(symbol)
                changes_made = True
                continue

            # ✅ STEP 6 FIX: PRE-EXECUTION POSITION CHECK
            # Check if we already have a position open on the exchange for this symbol
            try:
                remote_positions = executor.get_positions(symbol)
                if remote_positions and remote_positions.get("retCode") == 0:
                    # Check if any position in the list has a size > 0
                    has_open = any(float(p.get("size", 0)) > 0 for p in remote_positions["result"]["list"])
                    if has_open:
                        print(f"⚠️ [SKIP] {symbol} already has an active position on Bybit. Skipping duplicate order.")
                        state.close_trade(symbol)
                        changes_made = True
                        continue
            except Exception as e:
                print(f"⚠️ [CHECK_FAILED] Could not verify existing positions for {symbol}: {e}")

            side = "Buy" if trade["bias"] == "BULLISH" else "Sell"
            qty = calculate_position_size(trade)

            if qty <= 0:
                state.close_trade(symbol)
                changes_made = True
                continue

            try:
                # 🚀 EXECUTION: Attempting live order via Bybit
                order = executor.place_market_order(
                    symbol=symbol,
                    side=side,
                    qty=qty
                )

                if order and order.get("retCode") == 0:
                    trade["order_id"] = order["result"]["orderId"]
                    trade["is_active"] = True
                    trade["status"] = "OPEN"
                    trade["qty"] = qty
                    trade["activated_at"] = time.time()
                    trade["filled_price"] = candle["close"] 
                    
                    current_balance = executor.get_balance()
                    log_trade(trade, current_balance)
                    
                    print(f"✅ BYBIT ORDER EXECUTED & LOGGED: {symbol} | Qty: {qty}")
                else:
                    trade["is_active"] = False
                    trade["status"] = "REJECTED"
                    
                    error_msg = order.get("retMsg") if order else "Connection Timeout"
                    print(f"❌ BYBIT ORDER FAILED: {symbol} | {error_msg}")
                    
                    state.close_trade(symbol)
                    changes_made = True
                    continue

                changes_made = True

            except Exception as e:
                trade["is_active"] = False
                print(f"❌ BYBIT API EXCEPTION {symbol}: {e}")
                state.close_trade(symbol)
                changes_made = True
                continue

        # --- STEP 2: SYNC ACTIVE POSITIONS ---
        if trade.get("is_active"):
            try:
                positions = executor.get_positions(symbol)
                position_found = False

                if positions and positions.get("retCode") == 0:
                    for pos in positions["result"]["list"]:
                        size = float(pos["size"])
                        if size > 0:
                            position_found = True
                            trade["unrealized_pnl"] = float(pos["unrealisedPnl"])
                            trade["entry_price_real"] = float(pos["avgPrice"])
                            break 

                if not position_found:
                    print(f"🏁 POSITION CLOSED: {symbol} (TP/SL Triggered)")
                    exit_price = trade.get("tp", trade["entry"])
                    closed_trade = close_trade(trade, exit_price, "CLOSED")
                    
                    append_closed_trade(closed_trade)
                    append_trade_to_excel(closed_trade)
                    state.close_trade(symbol)
                    changes_made = True
                    continue 

            except Exception as e:
                print(f"❌ POSITION SYNC ERROR {symbol}: {e}")

        new_active.append(trade)

    # --- STEP 3: PERSIST UPDATED STATE ---
    if changes_made:
        try:
            save_active_trades(new_active)
        except Exception as e:
            print(f"❌ STORAGE ERROR: {e}")