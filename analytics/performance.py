from storage.trade_logger import load_closed_trades

def get_stats(closed=None):
    """
    🚀 PERFORMANCE ENGINE (v3.1) - Dynamic Context Edition
    Calculates metrics using actual Dollar PnL data.
    Now accepts an optional list of trades for flexible data analysis.
    """
    try:
        # ✅ FIX: Use provided list or fallback to loading from disk
        if closed is None:
            closed = load_closed_trades()
    except Exception:
        # Silently fail to allow the Dashboard's retry mechanism to trigger
        return None

    # Handle cases where no trades have been resolved yet
    if not closed:
        return {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "winrate": 0,
            "rr": 2,
            "final_balance": 100.0,
            "total_return_pct": 0.0,
            "equity_curve": [100.0]
        }

    # 📈 1. CORE PERFORMANCE METRICS
    wins = sum(1 for t in closed if t.get("result") == "WIN")
    losses = sum(1 for t in closed if t.get("result") == "LOSS")
    total = len(closed)
    
    winrate = (wins / total) * 100 if total > 0 else 0
    rr_target = 2  # Standard ICT Strategy Risk:Reward

    # 💰 2. REAL CAPITAL TRACKING (PHASE 9.2)
    # Starting balance initialized at 100 for clear growth visualization
    initial_balance = 100.0
    balance = initial_balance
    equity_curve = [initial_balance]

    for t in closed:
        # ✅ PnL RESOLUTION:
        # Extract the absolute dollar PnL provided by the trade_resolver
        pnl_value = t.get("pnl", 0.0)

        # Apply Linear Growth:
        # New Balance = Current Balance + Dollar PnL
        balance += pnl_value

        # Log for Line Charting
        equity_curve.append(round(balance, 2))

    # 📊 3. OUTPUT CONSOLIDATION
    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "winrate": round(winrate, 2),
        "rr": rr_target,
        "final_balance": round(balance, 2),
        "total_return_pct": round(((balance - initial_balance) / initial_balance) * 100, 2),
        "equity_curve": equity_curve
    }