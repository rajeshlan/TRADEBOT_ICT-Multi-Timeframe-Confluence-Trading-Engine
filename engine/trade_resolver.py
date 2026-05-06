import time
import os
from storage.trade_logger import (
    save_active_trades,
    load_active_trades,
    append_closed_trade
)
from storage.excel_logger import append_trade_to_excel
from core.trade_state import TradeStateManager

# ✅ Centralized singleton executor from core
from core.executor import executor

# --- INITIALIZATION ---
state = TradeStateManager()

# ✅ STEP 1: Load Environment Constraints
# Defaulting to 2 USDT margin and 3x leverage if not found in .env
MAX_MARGIN_PER_TRADE = float(os.getenv("MAX_MARGIN_PER_TRADE", 2.0))
LEVERAGE = int(os.getenv("LEVERAGE", 3))

def normalize_qty(qty, symbol=None):
    """
    Temporary safe quantity normalization to avoid 'Invalid Qty' errors.
    """
    if qty <= 0:
        return 0

    # High-price assets: Allow 3 decimal places
    if symbol in ["BTCUSDT", "ETHUSDT"]:
        return round(qty, 3)

    # Mid-price assets: Allow 2 decimal places
    if symbol in ["BNBUSDT", "SOLUSDT"]:
        return round(qty, 2)

    # Cheap assets / Fallback: Allow 1 decimal place
    return round(qty, 1)

def calculate_position_size(trade):
    """
    Calculates position size based on Fixed Margin and Leverage.
    
    Formula:
    $$Notional = Margin \times Leverage$$
    $$Quantity = \frac{Notional}{Entry Price}$$
    """
    entry = trade.get("entry", 0)
    symbol = trade.get("symbol")

    if entry <= 0:
        print(f"⚠️ [REJECTED] {symbol} - Invalid entry price for sizing.")
        return 0

    # Step 2: Calculate Notional Value
    max_position_notional = MAX_MARGIN_PER_TRADE * LEVERAGE

    # Step 3: Calculate Raw Quantity
    qty = max_position_notional / entry
    
    # Step 4: Normalize based on asset type
    normalized_qty = normalize_qty(qty, symbol)

    if normalized_qty <= 0:
        print(f"⚠️ [REJECTED] {symbol} - Qty too small after normalization ($Margin: {MAX_MARGIN_PER_TRADE}).")
        return 0
        
    return normalized_qty

def close_trade(trade, exit_price, result):
    """
    Finalizes trade data and calculates final PnL.
    """
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

            try:
                # Check for existing positions to avoid duplicates
                remote_positions = executor.get_positions(symbol)
                if remote_positions and remote_positions.get("retCode") == 0:
                    has_open = any(float(p.get("size", 0)) > 0 for p in remote_positions["result"]["list"])
                    if has_open:
                        print(f"⚠️ [SKIP] {symbol} already has an active position on Bybit.")
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
                # 🚀 EXECUTION
                order = executor.place_market_order(symbol=symbol, side=side, qty=qty)

                if order and order.get("retCode") == 0:
                    # Update local trade object state
                    trade["order_id"] = order["result"]["orderId"]
                    trade["is_active"] = True
                    trade["status"] = "OPEN"
                    trade["qty"] = qty
                    trade["activated_at"] = time.time()
                    trade["filled_price"] = candle["close"] 
                    
                    print(f"✅ BYBIT ORDER EXECUTED: {symbol} | Qty: {qty} (Margin: ${MAX_MARGIN_PER_TRADE})")
                    changes_made = True
                else:
                    trade["status"] = "REJECTED"
                    trade["is_active"] = False
                    error_msg = order.get("retMsg") if order else "Connection Timeout"
                    print(f"❌ BYBIT ORDER FAILED: {symbol} | {error_msg}")
                    state.close_trade(symbol)
                    changes_made = True
                    continue

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
                exchange_position_found = False

                if positions and positions.get("retCode") == 0:
                    for pos in positions["result"]["list"]:
                        size = float(pos.get("size", 0))
                        if size > 0:
                            exchange_position_found = True
                            trade["unrealized_pnl"] = float(pos.get("unrealisedPnl", 0))
                            trade["entry_price_real"] = float(pos.get("avgPrice", 0))
                            break 

                if not exchange_position_found:
                    print(f"📕 POSITION CLOSED ON EXCHANGE: {symbol}")
                    
                    exit_price = trade.get("entry_price_real", trade["entry"])
                    closed_trade = close_trade(trade, exit_price, "MANUAL_CLOSE")
                    
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