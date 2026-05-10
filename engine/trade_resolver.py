import os
import time

# STEP 1: Imports
from storage.trade_logger import (
    save_active_trades,
    load_active_trades,
    append_closed_trade
)

from storage.excel_logger import append_trade_to_excel
from core.trade_state import TradeStateManager
from core.executor import executor

# ✅ STEP 4: IMPORT SCHEMA NORMALIZER
from core.trade_schema import normalize_trade_schema

# Outcome Updater Imports
from core.setup_memory.outcome_updater import (
    register_execution_event,
    register_telemetry_event,
    register_close_event
)

# MFE/MAE Tracker Imports
from core.setup_memory.mfe_mae_tracker import (
    initialize_tracking,
    update_tracking,
    finalize_tracking
)

# -------------------------------------------------
# ENV CONFIG
# -------------------------------------------------

MAX_MARGIN_PER_TRADE = float(os.getenv("MAX_MARGIN_PER_TRADE", 2.0))
LEVERAGE = int(os.getenv("LEVERAGE", 10))
MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", 2))

# -------------------------------------------------
# STATE & HELPERS
# -------------------------------------------------

state = TradeStateManager()

def normalize_qty(qty, symbol=None):
    """Adjusts quantity to meet exchange decimal requirements."""
    if qty <= 0: return 0
    if symbol in ["BTCUSDT"]: return round(qty, 3)
    elif symbol in ["ETHUSDT", "BNBUSDT", "SOLUSDT", "TAOUSDT"]: return round(qty, 2)
    elif symbol in ["AVAXUSDT", "LINKUSDT", "FILUSDT"]: return round(qty, 1)
    return float(int(qty))

def calculate_position_size(trade):
    """Calculates position size based on margin and leverage."""
    entry = trade.get("entry", 0)
    symbol = trade.get("symbol")
    if entry <= 0: return 0

    try:
        position_value = MAX_MARGIN_PER_TRADE * LEVERAGE
        raw_qty = position_value / entry
        normalized_qty = normalize_qty(raw_qty, symbol)
        if normalized_qty <= 0: return 0
        return normalized_qty
    except Exception as e:
        print(f"❌ SIZE ERROR {symbol}: {e}")
        return 0

def close_trade(trade, exit_price, result):
    """Finalizes trade data for logging and calculates PnL."""
    trade["status"] = "CLOSED"
    trade["is_active"] = False
    trade["closed_at"] = time.strftime('%Y-%m-%d %H:%M:%S')
    trade["exit_price"] = exit_price
    trade["result"] = result

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
    
    active_list = load_active_trades() or []
    new_active = []
    
    # ✅ STEP 1: UUID TRACKER SET
    tracked_trade_uuids = set()
    
    changes_made = False

    # 1. POSITION COUNT SYNC & RECONCILIATION
    try:
        all_positions = executor.get_all_positions()
        exchange_count = len(all_positions)

        # AUTHORITATIVE EXCHANGE RECONCILIATION
        existing_symbols = {
            t.get("symbol")
            for t in active_list
            if t.get("status") in ["OPEN", "ACTIVE"]
        }

        for pos in all_positions:
            symbol = pos.get("symbol")
            size = abs(float(pos.get("size", 0)))

            if size <= 0 or symbol in existing_symbols:
                continue

            print(f"🔄 REBUILDING MISSING TRADE: {symbol}")
            
            # Extract basics for fingerprinting
            side = "BULLISH" if pos.get("side") == "Buy" else "BEARISH"
            entry_price = float(pos.get("avgPrice", 0))

            # ✅ STEP 4: ACTIVE TRADE RECOVERY MATCHING
            matched_trade = None
            exchange_fingerprint = f"{symbol}_{side}_{round(entry_price, 4)}"

            for existing_trade in active_list:
                existing_fp = existing_trade.get("exchange_fingerprint")
                if existing_fp == exchange_fingerprint:
                    matched_trade = existing_trade
                    break

            if matched_trade:
                reconstructed_trade = normalize_trade_schema(matched_trade)
                reconstructed_trade["status"] = "ACTIVE"
                reconstructed_trade["is_active"] = True
                reconstructed_trade["last_synced_at"] = int(time.time())
            else:
                reconstructed_trade = normalize_trade_schema({
                    "id": f"recovered_{symbol}_{int(time.time())}",
                    "symbol": symbol,
                    "status": "ACTIVE",
                    "is_active": True,
                    "qty": size,
                    "bias": side,
                    "entry_price_real": entry_price,
                    "filled_price": entry_price,
                    "executed_at": time.time(),
                    "recovered_from_exchange": True,
                })

            # ✅ STEP 2: UUID TRACKING IN RECONSTRUCTION
            reconstructed_trade = normalize_trade_schema(reconstructed_trade)
            trade_uuid = reconstructed_trade.get("trade_uuid")

            if trade_uuid not in tracked_trade_uuids:
                tracked_trade_uuids.add(trade_uuid)
                new_active.append(reconstructed_trade)
            
            existing_symbols.add(symbol)
            changes_made = True 

        json_active_count = len([t for t in active_list if t.get("status") in ["OPEN", "ACTIVE"]])
        live_open_count = max(exchange_count, json_active_count)

    except Exception as e:
        print(f"⚠️ [RECONCILIATION_FAIL] {e}")
        live_open_count = 0

    # 2. PROCESS LOOP
    for trade in active_list:
        symbol = trade["symbol"]

        # -----------------------------------------
        # PENDING TTL CLEANUP
        # -----------------------------------------
        if trade.get("status") == "PENDING":
            age_sec = time.time() - trade.get("created_at", time.time())

            if not trade.get("order_id") and age_sec > 300:
                print(f"🧹 EXPIRED PENDING SIGNAL: {symbol}")
                trade["status"] = "CANCELLED"
                trade["cancel_reason"] = "PENDING_TIMEOUT"
                trade["closed_at"] = time.strftime('%Y-%m-%d %H:%M:%S')

                append_closed_trade(trade)
                changes_made = True
                continue

        # CLEAN STALE ORDERS WITH IDs
        if trade.get("status") == "PENDING" and trade.get("order_id"):
            try:
                open_orders = executor.get_open_orders(symbol)
                if open_orders and open_orders.get("retCode") == 0:
                    order_list = open_orders["result"].get("list", [])
                    if not any(o.get("orderId") == trade.get("order_id") for o in order_list):
                        print(f"🧹 REMOVING STALE PENDING: {symbol}")
                        changes_made = True
                        continue
            except Exception as e:
                print(f"❌ PENDING CLEAN FAIL {symbol}: {e}")

        # 3. EXECUTION PHASE
        if not trade.get("order_id") and not trade.get("recovered_from_exchange"):
            if live_open_count >= MAX_OPEN_TRADES:
                # ✅ STEP 3: PREVENT DUPLICATES USING UUID
                trade = normalize_trade_schema(trade)
                trade_uuid = trade.get("trade_uuid")
                if trade_uuid not in tracked_trade_uuids:
                    tracked_trade_uuids.add(trade_uuid)
                    new_active.append(trade)
                continue

            candle = get_candle_func(symbol)
            if candle is None:
                # ✅ STEP 3: PREVENT DUPLICATES USING UUID
                trade = normalize_trade_schema(trade)
                trade_uuid = trade.get("trade_uuid")
                if trade_uuid not in tracked_trade_uuids:
                    tracked_trade_uuids.add(trade_uuid)
                    new_active.append(trade)
                continue

            side = "Buy" if trade["bias"] == "BULLISH" else "Sell"
            qty = calculate_position_size(trade)
            if qty <= 0: continue

            try:
                order = executor.place_market_order(symbol=symbol, side=side, qty=qty)
                if order and order.get("retCode") == 0:
                    trade["order_id"] = order["result"]["orderId"]
                    trade["status"] = "ACTIVE"
                    # ✅ STEP 5: STATUS TRANSITIONS
                    trade["opened_at"] = int(time.time())
                    trade["last_synced_at"] = int(time.time())
                    
                    trade["is_active"] = True
                    trade["qty"] = qty
                    trade["filled_price"] = float(candle["close"])
                    trade["executed_at"] = time.time() 

                    initialize_tracking(trade)

                    risk_dist = abs(trade["entry"] - trade["sl"])
                    if trade["bias"] == "BULLISH":
                        sl, tp = trade["filled_price"] - risk_dist, trade["filled_price"] + (risk_dist * trade["rr_ratio"])
                    else:
                        sl, tp = trade["filled_price"] + risk_dist, trade["filled_price"] - (risk_dist * trade["rr_ratio"])

                    executor.set_trading_stop(symbol=symbol, stop_loss=round(sl, 6), take_profit=round(tp, 6))
                    register_execution_event(trade)
                    
                    print(f"✅ EXECUTED {symbol}")
                    
                    # ✅ STEP 3: PREVENT DUPLICATES USING UUID
                    trade = normalize_trade_schema(trade)
                    trade_uuid = trade.get("trade_uuid")
                    if trade_uuid not in tracked_trade_uuids:
                        tracked_trade_uuids.add(trade_uuid)
                        new_active.append(trade)
                    
                    live_open_count += 1
                    changes_made = True
                    continue
            except Exception as e:
                print(f"❌ EXECUTION ERROR {symbol}: {e}")
                continue

        # 4. POSITION SYNC & TRACKING
        if trade.get("is_active"):
            try:
                positions = executor.get_positions(symbol)
                exchange_found = False

                if positions and positions.get("retCode") == 0:
                    for pos in positions["result"]["list"]:
                        if pos.get("symbol") != symbol: continue
                        size = abs(float(pos.get("size", 0)))
                        if size > 0:
                            exchange_found = True
                            trade["unrealized_pnl"] = float(pos.get("unrealisedPnl", 0))
                            # ✅ STEP 6: ACTIVE SYNC TIMESTAMPS
                            trade["last_synced_at"] = int(time.time())
                            trade["entry_price_real"] = float(pos.get("avgPrice", 0))
                            update_tracking(trade)
                            register_telemetry_event(trade)
                            break

                if not exchange_found:
                    if (time.time() - trade.get("executed_at", 0)) < 20:
                        # ✅ STEP 3: PREVENT DUPLICATES USING UUID
                        trade = normalize_trade_schema(trade)
                        trade_uuid = trade.get("trade_uuid")
                        if trade_uuid not in tracked_trade_uuids:
                            tracked_trade_uuids.add(trade_uuid)
                            new_active.append(trade)
                        continue

                    trade["missing_counter"] = trade.get("missing_counter", 0) + 1
                    if trade["missing_counter"] < 3:
                        # ✅ STEP 3: PREVENT DUPLICATES USING UUID
                        trade = normalize_trade_schema(trade)
                        trade_uuid = trade.get("trade_uuid")
                        if trade_uuid not in tracked_trade_uuids:
                            tracked_trade_uuids.add(trade_uuid)
                            new_active.append(trade)
                        continue
                    else:
                        print(f"✅ POSITION CLOSED DETECTED: {symbol}")
                        latest_candle = get_candle_func(symbol)
                        exit_price = float(latest_candle["close"]) if latest_candle else trade.get("entry_price_real", trade["entry"])
                        finalize_tracking(trade)
                        pnl = float(trade.get("unrealized_pnl", 0))
                        result_label = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BREAKEVEN")
                        closed_trade = close_trade(trade, exit_price, result_label)
                        
                        register_close_event(closed_trade)
                        append_closed_trade(closed_trade)
                        append_trade_to_excel(closed_trade)
                        changes_made = True
                        continue 
                else:
                    trade["missing_counter"] = 0 
            except Exception as e:
                print(f"❌ POSITION SYNC FAIL {symbol}: {e}")

        # -----------------------------------------
        # PREVENT DOUBLE APPEND
        # -----------------------------------------
        # ✅ STEP 3: PREVENT DUPLICATES USING UUID
        trade = normalize_trade_schema(trade)
        trade_uuid = trade.get("trade_uuid")
        if trade_uuid not in tracked_trade_uuids:
            tracked_trade_uuids.add(trade_uuid)
            new_active.append(trade)

    if changes_made:
        save_active_trades(new_active)