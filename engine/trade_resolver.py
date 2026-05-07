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

# ✅ Load Environment Constraints
MAX_MARGIN_PER_TRADE = float(os.getenv("MAX_MARGIN_PER_TRADE", 2.0))
LEVERAGE = int(os.getenv("LEVERAGE", 3))

def normalize_qty(qty, symbol=None):
    """
    Refined quantity normalization to prevent 'Invalid Qty' errors on Bybit.
    Categorizes assets by price tier to match exchange precision requirements.
    """
    if qty <= 0:
        return 0

    # 💎 HIGH PRICE TOKENS (Precise increments)
    if symbol in ["BTCUSDT"]:
        return round(qty, 3)

    # 🥈 TOP ALTS
    elif symbol in ["ETHUSDT", "BNBUSDT", "TAOUSDT", "SOLUSDT"]:
        return round(qty, 2)

    # 🥉 MID-TIER ALTS
    elif symbol in ["AVAXUSDT", "LINKUSDT", "FILUSDT", "DOTUSDT"]:
        return round(qty, 1)

    # 🪙 LOW PRICE / HIGH SUPPLY TOKENS (Commonly ADA, SEI, ONDO, XRP)
    # These typically require integer quantities or very low precision
    else:
        return float(int(qty))  # Returns as whole number (e.g., 5.0)

def calculate_position_size(trade):
    """
    Dynamic quantity calculation using:
    Qty = (Target Margin × Leverage) / Entry
    """
    entry = trade.get("entry", 0)
    symbol = trade.get("symbol")

    if entry <= 0:
        print(f"⚠️ [REJECTED] {symbol} - Invalid entry price.")
        return 0

    try:
        target_margin = MAX_MARGIN_PER_TRADE
        position_value = target_margin * LEVERAGE
        raw_qty = position_value / entry
        
        # Apply the new precision logic
        normalized_qty = normalize_qty(raw_qty, symbol)

        if normalized_qty <= 0:
            print(f"⚠️ [REJECTED] {symbol} - Calculated Qty ({raw_qty:.4f}) rounded to 0.")
            return 0

        estimated_margin = (normalized_qty * entry) / LEVERAGE
        print(
            f"📊 SIZE_CALC | {symbol} | "
            f"Lev={LEVERAGE}x | "
            f"Qty={normalized_qty} | "
            f"Expected Margin=${estimated_margin:.2f}"
        )
        return normalized_qty

    except Exception as e:
        print(f"❌ POSITION SIZE ERROR {symbol}: {e}")
        return 0

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

    # Standard PnL calculation
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

        # --- STEP 0: RECONCILE PENDING ORDERS ---
        if trade.get("status") == "PENDING":
            try:
                open_orders = executor.get_open_orders(symbol)
                exchange_order_exists = False

                if open_orders and open_orders.get("retCode") == 0:
                    order_list = open_orders["result"].get("list", [])
                    local_order_id = trade.get("order_id")

                    if not local_order_id:
                        exchange_order_exists = True
                    else:
                        for order in order_list:
                            if order.get("orderId") == local_order_id:
                                exchange_order_exists = True
                                break

                if not exchange_order_exists:
                    print(f"🧹 REMOVING STALE PENDING TRADE: {symbol}")
                    state.close_trade(symbol)
                    changes_made = True
                    continue

            except Exception as e:
                print(f"❌ PENDING RECONCILIATION ERROR {symbol}: {e}")

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
                    trade["order_id"] = order["result"]["orderId"]
                    trade["is_active"] = True
                    trade["status"] = "OPEN"
                    trade["qty"] = qty
                    trade["activated_at"] = time.time()
                    trade["filled_price"] = candle["close"] 
                    
                    executor.set_trading_stop(
                        symbol=symbol,
                        stop_loss=trade.get("sl"),
                        take_profit=trade.get("tp")
                    )
                    
                    print(f"✅ BYBIT ORDER EXECUTED: {symbol} | Qty: {qty}")
                    changes_made = True
                else:
                    # 🔴 PRUNE FAILED ORDERS IMMEDIATELY
                    error_msg = order.get("retMsg") if order else "Connection Timeout"
                    print(f"❌ BYBIT ORDER FAILED: {symbol} | {error_msg}")
                    print(f"🧹 REMOVING FAILED TRADE FROM ACTIVE STATE: {symbol}")
                    
                    state.close_trade(symbol)
                    changes_made = True
                    continue 

            except Exception as e:
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
                    closed_trade = close_trade(trade, exit_price, "EXCHANGE_EXIT")
                    
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