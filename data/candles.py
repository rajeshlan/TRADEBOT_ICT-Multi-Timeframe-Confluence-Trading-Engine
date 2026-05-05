import time
from pybit.unified_trading import HTTP

# ✅ Bybit session
session = HTTP(testnet=False)

# Optional: Add a strict request timeout to the session to prevent indefinite hangs
session._request_timeout = 10 

def get_candles(symbol, timeframe, limit=200):
    """
    Fetches historical OHLCV candle data from Bybit.
    Includes a 3-attempt retry mechanism to handle network timeouts and freezes.
    """
    tf_map = {
        "1m": "1",
        "3m": "3",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "2h": "120",
        "4h": "240",
        "1d": "D",
        "1w": "W"
    }

    interval = tf_map.get(timeframe)
    if not interval:
        print(f"❌ [TF_ERROR] Unsupported timeframe: {timeframe}")
        return None

    response = None
    
    # 🔥 HARDENING: 3-Attempt Retry Mechanism
    for i in range(3):
        try:
            response = session.get_kline(
                category="linear",
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            # If successful, break out of the retry loop immediately
            break 
            
        except Exception as e:
            print(f"⚠️ [TIMEOUT] {symbol} fetch failed (Attempt {i+1}/3): {e}")
            time.sleep(0.5) # Wait half a second before trying again

    # If response is still None after all 3 retries, exit safely
    if not response:
        print(f"❌ [CANDLE_ERROR] {symbol} completely failed after 3 attempts.")
        return None

    try:
        # Check Bybit's internal return code for API-level errors
        if response.get("retCode") != 0:
            print(f"❌ [BYBIT_ERROR] {response.get('retMsg')}")
            return None

        raw = response.get("result", {}).get("list", [])
        if not raw:
            return None

        candles = []
        # Bybit returns newest to oldest. We reverse it for standard chronological order.
        for c in reversed(raw):
            candles.append({
                "timestamp": int(c[0]),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
            })

        return candles

    except Exception as e:
        print(f"⚠️ [PROCESSING_ERROR] Error formatting data for {symbol}: {e}")
        return None

def get_current_candle(symbol):
    """
    Fetches the most recent 1-minute candle.
    Used by the resolver to check current market conditions.
    """
    candles = get_candles(symbol, "1m", limit=1)
    if not candles:
        return None
    return candles[-1]