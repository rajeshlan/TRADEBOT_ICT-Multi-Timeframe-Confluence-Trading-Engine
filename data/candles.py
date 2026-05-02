import requests
import time

BASE_URL = "https://api.binance.com/api/v3/klines"

# 🔥 GLOBAL SESSION: Reuses TCP connections to avoid handshake overhead
# This is critical for high-frequency scanning across multiple pairs.
session = requests.Session()

def get_candles(symbol, interval, limit=100):
    """
    Fetches candlestick data using a persistent session. 
    Implements a 3-attempt retry logic (Phase 8.3) to handle transient network errors.
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    # ✅ RETRY LOOP: Resilience against network blips
    for attempt in range(3):
        try:
            # 5s timeout prevents a single slow pair from hanging the entire bot
            response = session.get(BASE_URL, params=params, timeout=5)

            # Handle Rate Limiting (HTTP 429) immediately to avoid IP ban
            if response.status_code == 429:
                print(f"⚠️ [RATELIMIT] {symbol} cooling down... (Attempt {attempt+1}/3)")
                time.sleep(2)
                continue

            if response.status_code != 200:
                print(f"[ERROR] API Status {response.status_code} for {symbol}")
                continue

            data = response.json()

            # 🛠️ DATA VALIDATION FIX
            # If API returns empty list or null data, fail fast
            if not data or len(data) == 0:
                return None

            # Parse data into standard ICT Engine format
            candles = []
            for k in data:
                # Ensure we have a full candle entry (standard kline is 12 elements)
                if len(k) < 5:
                    continue

                candles.append({
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4])
                })

            # Double-check result list isn't empty after parsing
            if not candles:
                return None

            return candles

        except (requests.exceptions.RequestException, ValueError) as e:
            # ⚡ FAIL FAST & RETRY: Brief pause before trying again
            print(f"[RETRY] Candle fetch failed ({symbol} {interval}) {attempt+1}/3: {e}")
            time.sleep(1)

    # 🔥 FINAL FAIL: Trigger skip logic in the Main Loop
    print(f"❌ [FAIL] Skipping {symbol} {interval} after 3 attempts.")
    return None

def get_current_candle(symbol):
    """
    🚀 UPGRADE (PHASE 8.4): Fetches full OHLC for the latest 1m candle.
    Essential for the Resolver to detect SL/TP hits via wicks (High/Low).
    """
    # Request only 1 candle to keep the payload extremely light
    candles = get_candles(symbol, "1m", limit=1)
    
    # ✅ GUARD: Ensure we don't return an index error on empty results
    if candles is None or len(candles) == 0:
        return None
        
    # Return the dictionary containing open, high, low, close
    return candles[-1]