import json
from collections import defaultdict
from pathlib import Path


SETUP_OUTCOMES_FILE = Path("storage/setup_outcomes.jsonl")


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_jsonl(path):
    if not path.exists():
        return []

    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def build_research_summary(closed_trades=None):
    """Aggregate expectancy by side/archetype/regime/session."""
    closed_trades = closed_trades or []
    groups = defaultdict(
        lambda: {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "pnl": 0.0,
            "mfe": 0.0,
            "mae": 0.0,
        }
    )

    for trade in closed_trades:
        key = (
            trade.get("bias") or "UNKNOWN",
            trade.get("archetype") or "UNKNOWN",
            trade.get("market_regime") or "UNKNOWN",
            trade.get("session") or "UNKNOWN",
        )
        bucket = groups[key]
        bucket["trades"] += 1
        bucket["wins"] += 1 if trade.get("result") == "WIN" else 0
        bucket["losses"] += 1 if trade.get("result") == "LOSS" else 0
        bucket["pnl"] += _safe_float(trade.get("pnl"))
        bucket["mfe"] += _safe_float(trade.get("mfe"))
        bucket["mae"] += _safe_float(trade.get("mae"))

    rows = []
    for (bias, archetype, regime, session), stats in groups.items():
        trades = stats["trades"]
        rows.append(
            {
                "bias": bias,
                "archetype": archetype,
                "market_regime": regime,
                "session": session,
                "trades": trades,
                "winrate": round((stats["wins"] / trades) * 100, 2) if trades else 0,
                "net_pnl": round(stats["pnl"], 4),
                "avg_pnl": round(stats["pnl"] / trades, 4) if trades else 0,
                "avg_mfe": round(stats["mfe"] / trades, 4) if trades else 0,
                "avg_mae": round(stats["mae"] / trades, 4) if trades else 0,
            }
        )

    rows.sort(key=lambda row: (row["net_pnl"], row["trades"]), reverse=True)
    return rows


def empirical_prior_for(signal, closed_trades=None):
    closed_trades = closed_trades or []
    archetype = signal.get("archetype")
    bias = signal.get("bias")
    symbol = signal.get("symbol")

    matches = [
        trade for trade in closed_trades
        if trade.get("archetype") == archetype
        and trade.get("bias") == bias
        and (trade.get("symbol") == symbol or len(closed_trades) < 50)
    ]

    if not matches:
        return {"sample_size": 0, "winrate": None, "avg_pnl": 0.0}

    wins = sum(1 for trade in matches if trade.get("result") == "WIN")
    pnl = sum(_safe_float(trade.get("pnl")) for trade in matches)
    return {
        "sample_size": len(matches),
        "winrate": round((wins / len(matches)) * 100, 2),
        "avg_pnl": round(pnl / len(matches), 4),
    }
