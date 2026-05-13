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

# ✅ STEP 3 — IMPORT SYSTEM STATE
from core.system_state import drawdown_guard

# SCHEMA & STATE MACHINE IMPORTS
from core.trade_schema import normalize_trade_schema
from core.state_machine import (
    transition_trade_status,
    set_execution_state
)

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

# ✅ STEP 5 — IMPORT RUNTIME LOGGER
from utils.runtime_logger import log_runtime_event

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
        return normalized_qty if normalized_qty > 0 else 0
    except Exception as e:
        print(f"❌ SIZE ERROR {symbol}: {e}")
        return 0

def close_trade(trade, exit_price, result):
    """Finalizes trade data for logging and calculates PnL."""
    trade = transition_trade_status(trade, "CLOSED")
    
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
    tracked_trade_uuids = set()
    changes_made = False

    # 1. POSITION COUNT SYNC & RECONCILIATION
    try:
        all_positions = executor.get_all_positions()
        cached_positions = all_positions
        exchange_count = len(cached_positions)

        existing_symbols = {
            t.get("symbol")
            for t in active_list
            if t.get("status") in ["OPEN", "ACTIVE", "EXECUTING"]
        }

        for pos in cached_positions:
            symbol = pos.get("symbol")
            size = abs(float(pos.get("size", 0)))

            if size <= 0 or symbol in existing_symbols:
                continue

            print(f"🔄 REBUILDING MISSING TRADE: {symbol}")
            side = "BULLISH" if pos.get("side") == "Buy" else "BEARISH"
            entry_price = float(pos.get("avgPrice", 0))

            matched_trade = None
            exchange_fingerprint = f"{symbol}_{side}_{round(size, 4)}" 

            for existing_trade in active_list:
                if existing_trade.get("exchange_fingerprint") == exchange_fingerprint:
                    matched_trade = existing_trade
                    break

            if matched_trade:
                reconstructed_trade = normalize_trade_schema(matched_trade)
                reconstructed_trade = transition_trade_status(reconstructed_trade, "ACTIVE")
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

            reconstructed_trade = normalize_trade_schema(reconstructed_trade)
            trade_uuid = reconstructed_trade.get("trade_uuid")
            if trade_uuid not in tracked_trade_uuids:
                tracked_trade_uuids.add(trade_uuid)
                new_active.append(reconstructed_trade)
            
            existing_symbols.add(symbol)
            changes_made = True 

        json_pending_count = len([t for t in active_list if t.get("status") in ["PENDING", "EXECUTING"]])
        live_open_count = exchange_count + json_pending_count
        print(f"📊 COUNTER RECONCILIATION: Exchange({exchange_count}) + LocalPending({json_pending_count}) = {live_open_count}")

    except Exception as e:
        print(f"⚠️ [RECONCILIATION_FAIL] {e}")

    # 2. PROCESS LOOP
    for trade in active_list:
        symbol = trade["symbol"]

        # --- STALE PENDING CLEANUP ---
        if trade.get("status") == "PENDING":
            age_sec = time.time() - trade.get("created_at", time.time())
            if not trade.get("order_id") and age_sec > 300:
                print(f"🧹 EXPIRED PENDING SIGNAL: {symbol}")
                trade = transition_trade_status(trade, "CANCELLED")
                trade["cancel_reason"] = "PENDING_TIMEOUT"
                trade["closed_at"] = time.strftime('%Y-%m-%d %H:%M:%S')
                append_closed_trade(trade)
                changes_made = True
                continue

        # 3. EXECUTION PHASE
        if (not trade.get("order_id") and not trade.get("recovered_from_exchange") and trade.get("status") != "CANCELLED"):
            execution_attempts = trade.get("execution_attempts", 0)
            
            if execution_attempts >= 3:
                print(f"❌ MAX EXECUTION RETRIES EXCEEDED: {symbol}")
                trade = transition_trade_status(trade, "FAILED")
                trade = set_execution_state(trade, "FAILED")
                trade["closed_at"] = time.strftime('%Y-%m-%d %H:%M:%S')
                append_closed_trade(trade)
                append_trade_to_excel(trade)
                changes_made = True
                continue

            if trade.get("retry_after") and time.time() < trade["retry_after"]:
                new_active.append(normalize_trade_schema(trade))
                continue

            # Execution Logic
            side = "Buy" if trade["bias"] == "BULLISH" else "Sell"
            qty = calculate_position_size(trade)
            if qty <= 0: continue

            try:
                trade = transition_trade_status(trade, "EXECUTING")
                trade = set_execution_state(trade, "EXECUTING")
                
                order = executor.place_market_order(symbol=symbol, side=side, qty=qty)
                
                if order and order.get("retCode") == 0:
                    trade["order_id"] = order["result"]["orderId"]
                    trade["filled_price"] = float(order.get("result", {}).get("avgPrice") or get_candle_func(symbol)["close"])

                    trade = transition_trade_status(trade, "ACTIVE")
                    trade = set_execution_state(trade, "ACTIVE")
                    trade["opened_at"] = int(time.time())
                    trade["qty"] = qty
                    trade["executed_at"] = time.time() 

                    initialize_tracking(trade)

                    # TP/SL Calculation
                    risk_dist = abs(trade["entry"] - trade["sl"])
                    if trade["bias"] == "BULLISH":
                        sl, tp = trade["filled_price"] - risk_dist, trade["filled_price"] + (risk_dist * trade["rr_ratio"])
                    else:
                        sl, tp = trade["filled_price"] + risk_dist, trade["filled_price"] - (risk_dist * trade["rr_ratio"])

                    executor.set_trading_stop(symbol=symbol, stop_loss=round(sl, 6), take_profit=round(tp, 6))
                    register_execution_event(trade)
                    
                    print(f"✅ EXECUTED {symbol} @ {trade['filled_price']}")
                    
                    # ✅ LOG EXECUTION SUCCESS
                    log_runtime_event(
                        event_type="TRADE_EXECUTED",
                        symbol=symbol,
                        data={
                            "filled_price": trade["filled_price"],
                            "qty": qty,
                            "bias": trade.get("bias"),
                            "tp": round(tp, 6),
                            "sl": round(sl, 6)
                        }
                    )
                    
                    new_active.append(normalize_trade_schema(trade))
                    changes_made = True
                    continue
                else:
                    err_msg = order.get("retMsg", "UNKNOWN_ERROR") if isinstance(order, dict) else "NO_RESP"
                    trade["execution_attempts"] = execution_attempts + 1
                    trade["last_execution_error"] = err_msg
                    trade["retry_after"] = time.time() + (30 * trade["execution_attempts"])
                    
                    # ✅ LOG EXECUTION FAILURE
                    log_runtime_event(
                        event_type="EXECUTION_FAILED",
                        symbol=symbol,
                        data={
                            "error": err_msg,
                            "attempt": trade["execution_attempts"]
                        }
                    )

                    trade = set_execution_state(trade, "RETRYING")
                    trade = transition_trade_status(trade, "PENDING")
                    new_active.append(normalize_trade_schema(trade))
                    changes_made = True
                    continue
                    
            except Exception as e:
                print(f"❌ EXECUTION EXCEPTION {symbol}: {e}")
                trade["execution_attempts"] = execution_attempts + 1
                trade["retry_after"] = time.time() + 60
                new_active.append(normalize_trade_schema(trade))
                continue

        # 4. POSITION SYNC & TRACKING
        if trade.get("is_active"):
            try:
                symbol_pos = [p for p in cached_positions if p.get("symbol") == symbol]
                exchange_found = False

                if symbol_pos:
                    pos = symbol_pos[0]
                    if abs(float(pos.get("size", 0))) > 0:
                        exchange_found = True
                        trade["unrealized_pnl"] = float(pos.get("unrealisedPnl", 0))
                        trade["entry_price_real"] = float(pos.get("avgPrice", 0))
                        update_tracking(trade)
                        register_telemetry_event(trade)

                if not exchange_found:
                    # Delay closing check to allow exchange state to propagate
                    if (time.time() - trade.get("executed_at", 0)) < 20:
                        new_active.append(normalize_trade_schema(trade))
                        continue

                    trade["missing_counter"] = trade.get("missing_counter", 0) + 1
                    if trade["missing_counter"] < 3:
                        new_active.append(normalize_trade_schema(trade))
                        continue
                    else:
                        print(f"✅ POSITION CLOSED: {symbol}")
                        
                        # ✅ LOG POSITION CLOSED
                        log_runtime_event(
                            event_type="TRADE_CLOSED",
                            symbol=symbol,
                            data={"pnl": trade.get("unrealized_pnl", 0)}
                        )

                        latest_candle = get_candle_func(symbol)
                        exit_price = float(latest_candle["close"]) if latest_candle else trade.get("entry_price_real", trade["entry"])
                        finalize_tracking(trade)
                        
                        closed_trade = close_trade(trade, exit_price, "WIN" if float(trade.get("unrealized_pnl", 0)) > 0 else "LOSS")
                        drawdown_guard.register_result(closed_trade.get("pnl", 0))
                        
                        register_close_event(closed_trade)
                        append_closed_trade(closed_trade)
                        append_trade_to_excel(closed_trade)
                        changes_made = True
                        continue 
            except Exception as e:
                print(f"❌ POSITION SYNC FAIL {symbol}: {e}")

        # Keep trade in active list if not closed
        new_active.append(normalize_trade_schema(trade))

    save_active_trades(new_active)