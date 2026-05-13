CORRELATED_GROUPS = {
    "MAJORS": [
        "BTCUSDT",
        "ETHUSDT"
    ],

    "L1": [
        "SOLUSDT",
        "AVAXUSDT",
        "ADAUSDT",
        "NEARUSDT"
    ],

    "AI": [
        "TAOUSDT",
        "FETUSDT",
        "RNDRUSDT"
    ],

    "DEFI": [
        "LINKUSDT",
        "UNIUSDT",
        "AAVEUSDT"
    ]
}


def find_correlation_group(symbol):
    for group, symbols in CORRELATED_GROUPS.items():
        if symbol in symbols:
            return group

    return None


def correlated_positions_count(symbol, active_trades):
    """
    Counts active correlated exposure.
    """

    group = find_correlation_group(symbol)

    if not group:
        return 0

    group_symbols = CORRELATED_GROUPS[group]

    count = 0

    for trade in active_trades:
        if (
            trade.get("symbol") in group_symbols
            and trade.get("is_active")
        ):
            count += 1

    return count