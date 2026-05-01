from storage.trade_logger import load_trades, save_trades
import time

def resolve_trades(get_price_func):
    trades = load_trades()

    for trade in trades:
        if trade["status"] != "OPEN":
            continue

        price = get_price_func(trade["symbol"])

        if trade["bias"] == "BULLISH":
            if price <= trade["sl"]:
                trade["status"] = "CLOSED"
                trade["result"] = "LOSS"
            elif price >= trade["tp"]:
                trade["status"] = "CLOSED"
                trade["result"] = "WIN"

        else:
            if price >= trade["sl"]:
                trade["status"] = "CLOSED"
                trade["result"] = "LOSS"
            elif price <= trade["tp"]:
                trade["status"] = "CLOSED"
                trade["result"] = "WIN"

        if trade["status"] == "CLOSED":
            trade["closed_at"] = time.time()

    save_trades(trades)