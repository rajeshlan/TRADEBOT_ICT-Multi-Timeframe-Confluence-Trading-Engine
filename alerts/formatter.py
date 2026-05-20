def escape(text):
    """
    Escapes Markdown special characters to prevent Telegram 
    from misinterpreting signal details.
    """
    return str(text).replace("_", "\\_").replace("*", "\\*")

def format_signal(signal):
    """
    Formats the confluence signal into a professional trading alert
    with execution levels, quality tags, and dynamic risk management.
    """
    # Extract score for quality tagging
    score = signal.get("confluence_score", 0)

    # Assign visual tags based on score thresholds
    if score >= 90:
        tag = "🟢 BEST SETUP"
    elif score >= 75:
        tag = "🟡 GOOD SETUP"
    elif score >= 55:
        tag = "🔵 DECENT SETUP"
    else:
        tag = "⚪ WEAK SETUP"

    # Format the timeframes list for readability
    tf_str = ", ".join(signal['timeframes'])
    
    # Extract risk (calculated via Kelly in main.py) or default to 2%
    risk = signal.get("risk_pct", signal.get("risk", 2))
    archetype = signal.get("archetype", "UNKNOWN")
    expected_value = signal.get("expected_value_r", "n/a")
    win_probability = signal.get("win_probability", "n/a")
    
    return f"""
{tag} 🚨 *CONFLUENCE ALERT*

**Pair:** {signal['symbol']}
**Bias:** {signal['bias']}
**Timeframes:** {tf_str}

**Score:** {score}
**Archetype:** {archetype}
**Expected R:** {expected_value}
**Win Prob:** {win_probability}
📊 **Risk per trade:** {risk}%

📍 **Entry:** {signal.get('entry')}
🛑 **Stop Loss:** {signal.get('sl')}
🎯 **Take Profit:** {signal.get('tp')}
📊 **RR:** {signal.get('rr')}

**Details:**
{escape(signal.get('details', ''))}
"""
