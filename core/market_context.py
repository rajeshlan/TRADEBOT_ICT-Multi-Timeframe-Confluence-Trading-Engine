import time

import requests


BASE_URL = "https://api.bybit.com"
PUBLIC_TIMEOUT = 5
CONTEXT_TTL_SECONDS = 30

_CACHE = {}


def _get(endpoint, params):
    response = requests.get(
        f"{BASE_URL}{endpoint}",
        params=params,
        timeout=PUBLIC_TIMEOUT,
    )
    payload = response.json()
    if payload.get("retCode") != 0:
        return {}
    return payload.get("result", {})


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _orderbook_context(symbol):
    result = _get(
        "/v5/market/orderbook",
        {"category": "linear", "symbol": symbol, "limit": 25},
    )
    bids = result.get("b", []) or []
    asks = result.get("a", []) or []

    if not bids or not asks:
        return {
            "spread_bps": None,
            "book_imbalance": 0.0,
            "bid_depth": 0.0,
            "ask_depth": 0.0,
        }

    best_bid = _safe_float(bids[0][0])
    best_ask = _safe_float(asks[0][0])
    mid = (best_bid + best_ask) / 2 if best_bid and best_ask else 0
    spread_bps = ((best_ask - best_bid) / mid) * 10000 if mid else None

    bid_depth = sum(_safe_float(level[0]) * _safe_float(level[1]) for level in bids)
    ask_depth = sum(_safe_float(level[0]) * _safe_float(level[1]) for level in asks)
    total_depth = bid_depth + ask_depth
    imbalance = (bid_depth - ask_depth) / total_depth if total_depth else 0.0

    return {
        "spread_bps": round(spread_bps, 4) if spread_bps is not None else None,
        "book_imbalance": round(imbalance, 4),
        "bid_depth": round(bid_depth, 2),
        "ask_depth": round(ask_depth, 2),
    }


def _ticker_context(symbol):
    result = _get(
        "/v5/market/tickers",
        {"category": "linear", "symbol": symbol},
    )
    items = result.get("list", []) or []
    item = items[0] if items else {}

    mark = _safe_float(item.get("markPrice"))
    index = _safe_float(item.get("indexPrice"))
    basis_bps = ((mark - index) / index) * 10000 if index else 0.0

    return {
        "funding_rate": _safe_float(item.get("fundingRate")),
        "mark_price": mark,
        "index_price": index,
        "basis_bps": round(basis_bps, 4),
        "price_24h_pct": _safe_float(item.get("price24hPcnt")),
        "turnover_24h": _safe_float(item.get("turnover24h")),
        "open_interest_value": _safe_float(item.get("openInterestValue")),
    }


def _open_interest_context(symbol):
    result = _get(
        "/v5/market/open-interest",
        {
            "category": "linear",
            "symbol": symbol,
            "intervalTime": "5min",
            "limit": 2,
        },
    )
    rows = result.get("list", []) or []
    if len(rows) < 2:
        return {"open_interest_change_pct": 0.0}

    # Bybit returns newest first.
    latest = _safe_float(rows[0].get("openInterest"))
    previous = _safe_float(rows[1].get("openInterest"))
    change = ((latest - previous) / previous) * 100 if previous else 0.0
    return {"open_interest_change_pct": round(change, 4)}


def get_market_context(symbol):
    """Fetch lightweight public execution context with defensive fallbacks."""
    now = time.time()
    cached = _CACHE.get(symbol)
    if cached and now - cached["timestamp"] < CONTEXT_TTL_SECONDS:
        return cached["data"]

    context = {
        "symbol": symbol,
        "context_ok": False,
        "spread_bps": None,
        "book_imbalance": 0.0,
        "funding_rate": 0.0,
        "basis_bps": 0.0,
        "price_24h_pct": 0.0,
        "turnover_24h": 0.0,
        "open_interest_value": 0.0,
        "open_interest_change_pct": 0.0,
    }

    try:
        context.update(_ticker_context(symbol))
        context.update(_orderbook_context(symbol))
        context.update(_open_interest_context(symbol))
        context["context_ok"] = True
    except Exception as exc:
        context["context_error"] = str(exc)

    _CACHE[symbol] = {"timestamp": now, "data": context}
    return context
