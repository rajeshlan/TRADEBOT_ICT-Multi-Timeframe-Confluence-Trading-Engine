from storage.trade_logger import load_closed_trades

def get_stats(closed=None):
    """
    🚀 PERFORMANCE ENGINE (v3.2)
    Calculates metrics using actual Dollar PnL data.
    Ensures the dashboard reflects real capital growth rather than just trade counts.
    """
    try:
        # ✅ DATA FALLBACK: Use provided list (from Dashboard memory) or load from disk
        if closed is None:
            closed = load_closed_trades()
    except Exception as e:
        # Silently fail to let the Dashboard's refresh cycle try again
        print(f"⚠️ [ANALYTICS] Error loading trades: {e}")
        return None

    # --- 1. HANDLE EMPTY STATE ---
    # Prevents division by zero or errors on a fresh account
    if not closed:
        return {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "winrate": 0,
            "rr": 2.0,
            "final_balance": 100.0,
            "total_return_pct": 0.0,
            "equity_curve": [100.0]
        }

    # --- 2. CORE PERFORMANCE METRICS ---
    # Count occurrences of results for winrate calculation
    wins = sum(1 for t in closed if t.get("result") == "WIN")
    losses = sum(1 for t in closed if t.get("result") == "LOSS")
    total = len(closed)
    
    winrate = (wins / total) * 100 if total > 0 else 0
    rr_target = 2.0  # Default ICT Risk:Reward target

    # --- 3. REAL CAPITAL TRACKING (STEP 9 FIX) ---
    # Starting balance is initialized at $100.00
    initial_balance = 100.0
    current_balance = initial_balance
    equity_curve = [initial_balance]

    for trade in closed:
        # ✅ CRITICAL FIX: Extract actual dollar PnL
        # This ensures that even if a "WIN" is small, the balance reflects the truth.
        pnl_value = trade.get("pnl", 0.0)

        # Update the running account balance
        current_balance += pnl_value

        # Append to the curve list for Streamlit's line_chart
        equity_curve.append(round(current_balance, 2))

    # --- 4. OUTPUT CONSOLIDATION ---
    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "winrate": round(winrate, 2),
        "rr": rr_target,
        "final_balance": round(current_balance, 2),
        "total_return_pct": round(((current_balance - initial_balance) / initial_balance) * 100, 2),
        "equity_curve": equity_curve
    }