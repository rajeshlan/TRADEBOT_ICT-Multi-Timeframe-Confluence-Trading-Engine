import requests
import time

BASE_URL = "https://api.binance.com/api/v3/klines"

# 🔥 GLOBAL SESSION: Reuses the same TCP connection for all requests
# Reduces overhead, CPU usage, and prevents "Too many open files" errors
session = requests.Session()

def get_candles(symbol, interval, limit=100):
    """
    Fetches candlestick data using a persistent session. 
    Fails fast to prevent blocking the main execution loop.
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    try:
        # Using session.get instead of requests.get for speed
        response = session.get(BASE_URL, params=params, timeout=10)

        # Handle API-level errors
        if response.status_code != 200:
            print(f"[Binance Error] Status {response.status_code} for {symbol}")
            
            # If rate limited (429), we take a brief forced nap
            if response.status_code == 429:
                print("⚠️ Rate limit hit! Cooling down...")
                time.sleep(5)
            return []

        data = response.json()

        # Parse data into the standard format for the evaluator
        candles = []
        for k in data:
            candles.append({
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4])
            })

        return candles

    except Exception as e:
        # ⚡ FAIL FAST: Don't retry, don't block. Just skip and move to the next.
        print(f"[Skip] {symbol}-{interval} failed: {e}")
        return []

def get_current_price(symbol):
    """
    🧱 STEP 5 — Fetches the most recent close price for a symbol.
    Uses a 1-candle limit to keep the payload tiny and fast.
    """
    candles = get_candles(symbol, "5m", limit=1)
    
    if not candles:
        return None
        
    return candles[-1]["close"]