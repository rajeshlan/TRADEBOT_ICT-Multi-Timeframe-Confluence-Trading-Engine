import os
import time

from storage.trade_logger import (
    save_active_trades,
    load_active_trades,
    append_closed_trade
)

from storage.excel_logger import append_trade_to_excel
from core.trade_state import TradeStateManager
from core.executor import executor

# -------------------------------------------------
# ENV CONFIG
# -------------------------------------------------

MAX_MARGIN_PER_TRADE = float(os.getenv("MAX_MARGIN_PER_TRADE", 2.0))
LEVERAGE = int(os.getenv("LEVERAGE", 10))
MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", 2))

# -------------------------------------------------
# STATE
# -------------------------------------------------

state = TradeStateManager()

# -------------------------------------------------
# QTY NORMALIZATION
# -------------------------------------------------

def normalize_qty(qty, symbol=None):
    """Adjusts quantity to meet exchange decimal requirements."""
    if qty <= 0:
        return 0

    if symbol in ["BTCUSDT"]:
        return round(qty, 3)
    elif symbol in ["ETHUSDT", "BNBUSDT", "SOLUSDT", "TAOUSDT"]:
        return round(qty, 2)
    elif symbol in ["AVAXUSDT", "LINKUSDT", "FILUSDT"]:
        return round(qty, 1)

    return float(int(qty))

# -------------------------------------------------
# POSITION SIZING
# -------------------------------------------------

def calculate_position_size(trade):
    """Calculates position size based on margin and leverage."""
    entry = trade.get("entry", 0)
    symbol = trade.get("symbol")

    if entry <= 0:
        print(f"⚠️ [REJECTED] {symbol} Invalid entry.")
        return 0

    try:
        position_value = MAX_MARGIN_PER_TRADE * LEVERAGE
        raw_qty = position_value / entry
        normalized_qty = normalize_qty(raw_qty, symbol)

        if normalized_qty <= 0:
            print(f"⚠️ [REJECTED] {symbol} Qty too small.")
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
        print(f"❌ SIZE ERROR {symbol}: {e}")
        return 0

# -------------------------------------------------
# CLOSE TRADE
# -------------------------------------------------

def close_trade(trade, exit_price, result):
    """Finalizes trade data for logging and calculates PnL."""
    trade["status"] = "CLOSED"
    trade["is_active"] = False
    trade["closed_at"] = time.strftime('%Y-%m-%d %H:%M:%S')
    trade["exit_price"] = exit_price
    trade["result"] = result

    # Calculate PnL based on the actual filled entry vs the market exit
    entry = trade.get("filled_price", trade["entry"])
    pnl_value = trade.get("qty", 0) * (exit_price - entry)

    if trade["bias"] == "BEARISH":
        pnl_value = -pnl_value

    trade["pnl"] = round(pnl_value, 4)
    return trade

# -------------------------------------------------
# MAIN RESOLVER
# -------------------------------------------------

def resolve_trades(get_candle_func):
    """Main logic for executing pending trades and syncing active positions."""
    active_list = load_active_trades()

    if not active_list:
        return

    new_active = []
    changes_made = False

    # 1. Calculate current global position count (Exchange vs JSON)
    try:
        all_positions = executor.get_all_positions()
        exchange_count = len(all_positions)
        
        json_active_count = len([
            t for t in active_list 
            if t.get("status") in ["PENDING", "OPEN", "ACTIVE"]
        ])

        live_open_count = max(exchange_count, json_active_count)
        
        print(f"📡 POSITIONS -> Exchange: {exchange_count} | Local: {json_active_count} | Effective: {live_open_count}")
    except Exception as e:
        print(f"⚠️ [LIVE_COUNT_FAIL] {e}")
        live_open_count = 0

    for trade in active_list:
        symbol = trade["symbol"]

        # 2. CLEAN STALE PENDING ORDERS
        if trade.get("status") == "PENDING" and trade.get("order_id"):
            try:
                open_orders = executor.get_open_orders(symbol)
                exchange_order_exists = False

                if open_orders and open_orders.get("retCode") == 0:
                    order_list = open_orders["result"].get("list", [])
                    local_order_id = trade.get("order_id")
                    for order in order_list:
                        if order.get("orderId") == local_order_id:
                            exchange_order_exists = True
                            break

                if not exchange_order_exists:
                    print(f"🧹 REMOVING STALE PENDING: {symbol}")
                    changes_made = True
                    state.close_trade(symbol)
                    continue
            except Exception as e:
                print(f"❌ PENDING CLEAN FAIL {symbol}: {e}")

        # 3. EXECUTION PHASE (Opening new trades)
        if not trade.get("order_id"):
            if live_open_count >= MAX_OPEN_TRADES:
                print(f"🛑 HARD LIMIT REACHED ({live_open_count}/{MAX_OPEN_TRADES})")
                new_active.append(trade)
                continue

            candle = get_candle_func(symbol)
            if candle is None:
                new_active.append(trade)
                continue

            side = "Buy" if trade["bias"] == "BULLISH" else "Sell"
            qty = calculate_position_size(trade)

            if qty <= 0:
                continue

            try:
                order = executor.place_market_order(symbol=symbol, side=side, qty=qty)

                if order and order.get("retCode") == 0:
                    trade["order_id"] = order["result"]["orderId"]
                    trade["status"] = "OPEN"
                    trade["is_active"] = True
                    trade["qty"] = qty
                    trade["filled_price"] = float(candle["close"])
                    trade["executed_at"] = time.time() 

                    filled_price = trade["filled_price"]
                    risk_distance = abs(trade["entry"] - trade["sl"])

                    if trade["bias"] == "BULLISH":
                        live_sl = filled_price - risk_distance
                        live_tp = filled_price + (risk_distance * trade["rr_ratio"])
                    else:
                        live_sl = filled_price + risk_distance
                        live_tp = filled_price - (risk_distance * trade["rr_ratio"])

                    executor.set_trading_stop(
                        symbol=symbol,
                        stop_loss=round(live_sl, 6),
                        take_profit=round(live_tp, 6)
                    )

                    print(f"✅ EXECUTED {symbol}")
                    live_open_count += 1
                    changes_made = True
                else:
                    print(f"❌ ORDER FAILED {symbol}: {order.get('retMsg') if order else 'No Response'}")
                    continue
            except Exception as e:
                print(f"❌ EXECUTION ERROR {symbol}: {e}")
                continue

        # 4. POSITION SYNC (FIX 4: REAL MARKET PRICE EXIT)
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
                    # Grace period to prevent immediate sync errors after entry
                    grace_period = 20
                    if trade.get("executed_at"):
                        age = time.time() - trade["executed_at"]
                        if age < grace_period:
                            print(f"⏳ POSITION SYNC GRACE: {symbol} ({round(age,1)}s)")
                            new_active.append(trade)
                            continue

                    # Strike system to confirm position is actually gone
                    trade["missing_counter"] = trade.get("missing_counter", 0) + 1

                    if trade["missing_counter"] < 3:
                        print(f"⌛ POSITION NOT CONFIRMED CLOSED: {symbol} ({trade['missing_counter']}/3)")
                        new_active.append(trade)
                        continue

                    # ✅ FIX 4: Final Closure using REAL MARKET price
                    print(f"📕 POSITION CLOSED: {symbol}")
                    
                    latest_candle = get_candle_func(symbol)
                    if latest_candle:
                        exit_price = float(latest_candle["close"])
                        print(f"📈 Exit captured at market price: {exit_price}")
                    else:
                        exit_price = trade.get("entry_price_real", trade["entry"])
                        print(f"⚠️ Candle fetch failed, using fallback exit price: {exit_price}")

                    closed_trade = close_trade(trade, exit_price, "EXCHANGE_EXIT")
                    append_closed_trade(closed_trade)
                    append_trade_to_excel(closed_trade)
                    changes_made = True
                    continue

                else:
                    # Reset counter if position is still found on exchange
                    trade["missing_counter"] = 0 

            except Exception as e:
                print(f"❌ POSITION SYNC FAIL {symbol}: {e}")

        new_active.append(trade)

    if changes_made:
        try:
            save_active_trades(new_active)
        except Exception as e:
            print(f"❌ SAVE FAIL: {e}")