def compute_pair_stats(trades):
    """
    📊 ANALYTICS ENGINE (v2.3)
    Aggregates performance metrics per trading pair.
    Now supports PnL tracking and winrate distribution.
    """
    if not trades:
        return {}

    stats = {}

    for t in trades:
        pair = t["symbol"]

        # Initialize pair entry if not exists
        if pair not in stats:
            stats[pair] = {
                "total": 0,
                "wins": 0,
                "losses": 0,
                "pnl_list": []
            }

        stats[pair]["total"] += 1

        # Calculate Win/Loss distribution
        if t.get("result") == "WIN":
            stats[pair]["wins"] += 1
        elif t.get("result") == "LOSS":
            stats[pair]["losses"] += 1

        # 🧱 PnL GUARD: Handle legacy trades missing the 'pnl' key
        # Uses 0.0 as a fallback to keep averages mathematically sound
        pnl_val = t.get("pnl", 0.0)
        stats[pair]["pnl_list"].append(pnl_val)

    # Finalize calculations for each pair
    for pair in stats:
        s = stats[pair]
        total = s["total"]
        
        # Calculate Winrate percentage
        s["winrate"] = round((s["wins"] / total) * 100, 2) if total > 0 else 0
        
        # Calculate Average PnL per trade for this asset
        if s["pnl_list"]:
            s["avg_pnl"] = round(sum(s["pnl_list"]) / len(s["pnl_list"]), 4)
        else:
            s["avg_pnl"] = 0.0
            
        # Optional: Cleanup raw list to keep the return object lightweight for Streamlit
        del s["pnl_list"]

    return stats