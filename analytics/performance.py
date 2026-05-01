from storage.trade_logger import load_trades

def get_stats():
    """
    🚀 PERFORMANCE ENGINE (v2.0)
    Calculates win rates, equity growth, and tracks the account curve
    based on dynamic risk parameters.
    """
    trades = load_trades()
    
    # Filter only for trades that have reached a final resolution
    closed = [t for t in trades if t["status"] == "CLOSED"]

    if not closed:
        print("[INFO] No closed trades found for analytics.")
        return None

    # 📈 Core Metrics
    wins = sum(1 for t in closed if t["result"] == "WIN")
    losses = sum(1 for t in closed if t["result"] == "LOSS")
    total = len(closed)
    
    # Mathematical stats
    winrate = wins / total if total else 0
    rr = 2  # Fixed Risk:Reward target used by the ICT Engine

    # 💰 Equity Simulation
    pnl = 0
    equity_curve = []
    equity = 100  # Theoretical starting capital for percentage tracking

    for t in closed:
        # Pull the actual risk used at the time of signal generation
        # Falls back to 2% if missing
        risk_pct = t.get("risk", 2) / 100 

        if t["result"] == "WIN":
            # Gain = Equity * Risk % * RR
            gain = equity * risk_pct * rr
            equity += gain
        elif t["result"] == "LOSS":
            # Loss = Equity * Risk %
            loss = equity * risk_pct
            equity -= loss

        equity_curve.append(round(equity, 2))

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "winrate": round(winrate * 100, 2),
        "rr": rr,
        "final_equity": round(equity, 2),
        "total_return_pct": round(equity - 100, 2),
        "equity_curve": equity_curve
    }