import os
import time
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Load environment variables for secure API access
load_dotenv()

class ServerTimeSync:
    """
    Helper utility to calculate and maintain the offset 
    between local system time and Bybit server time.
    Used for monitoring and diagnostics.
    """
    def __init__(self, client):
        self.client = client
        self.local_offset = 0
        self.refresh_offset()

    def refresh_offset(self):
        """Calculates the millisecond difference between local and server time."""
        try:
            res = self.client.get_server_time()
            # Support for both standard and fallback result structures
            server_time_ms = int(res.get("result", {}).get("timeSecond", 0)) * 1000
            if server_time_ms == 0:
                server_time_ms = int(res.get("time_now", 0)) * 1000 
            
            local_time_ms = int(time.time() * 1000)
            self.local_offset = server_time_ms - local_time_ms
            print(f"⏰ [TIME_SYNC] Clock Offset Detected: {self.local_offset}ms")
        except Exception as e:
            print(f"⚠️ [TIME_SYNC] Diagnostic sync failed: {e}")

    def get_time(self):
        """Returns the synchronized server time for external monitoring."""
        return int(time.time() * 1000) + self.local_offset

class BybitExecutor:
    """
    Bybit V5 Executor: Clean Library Mode.
    Relies on pybit internal timestamping while maintaining 
    pre-trade validation logic.
    """

    def __init__(self, api_key=None, api_secret=None):
        # 1. Credentials Setup
        self.api_key = api_key or os.getenv("BYBIT_API_KEY")
        self.api_secret = api_secret or os.getenv("BYBIT_API_SECRET")

        # 2. Client Initialization
        # recv_window remains at 20s to account for potential drift/latency
        self.client = HTTP(
            testnet=False,
            api_key=self.api_key,
            api_secret=self.api_secret,
            recv_window=20000 
        )
        
        # 3. Diagnostic Time Synchronization
        # Initialized to monitor drift, but not injected into requests.
        self.time_sync = ServerTimeSync(self.client)
        
        # 4. State Management for Throttling
        self._last_balance_call = 0
        self._cached_balance = 0.0

        print("✅ Bybit Executor: Clean Library Mode initialized.")

    def get_balance(self):
        """
        Retrieves USDT balance with 5s throttling. 
        Library handles timestamping internally.
        """
        current_time = time.time()
        if current_time - self._last_balance_call < 5:
            return self._cached_balance
            
        self._last_balance_call = current_time

        try:
            res = self.client.get_wallet_balance(
                accountType="UNIFIED"
            )

            if res.get("retCode") == 0:
                coins = res["result"]["list"][0]["coin"]
                for c in coins:
                    if c["coin"] == "USDT":
                        self._cached_balance = float(c["walletBalance"])
                        return self._cached_balance
            else:
                print(f"❌ Balance API Error: {res.get('retMsg')}")
                return self._cached_balance
        except Exception as e:
            print(f"❌ Balance Exception: {e}")
            return self._cached_balance

    def place_market_order(self, symbol, side, qty):
        """
        Places a Market Order with Qty validation.
        Library handles timestamping internally.
        """
        # Safeguard: Prevent orders with 0 or negative quantity
        if qty <= 0:
            print(f"⚠️ [REJECTED] {symbol} Qty is {qty}. Skipping API call.")
            return None

        formatted_side = "Buy" if side.upper() == "BUY" else "Sell"

        try:
            response = self.client.place_order(
                category="linear",
                symbol=symbol,
                side=formatted_side,
                orderType="Market",
                qty=str(qty),
                timeInForce="IOC"
            )
            
            if response.get("retCode") == 0:
                print(f"🚀 ORDER PLACED: {symbol} {formatted_side} {qty}")
            else:
                print(f"⚠️ ORDER REJECTED: {response.get('retMsg')}")
                
            return response
            
        except Exception as e:
            print(f"❌ [ORDER_FAIL] {symbol}: {e}")
            return None

    def get_positions(self, symbol):
        """
        Retrieves active positions. 
        Library handles timestamping internally.
        """
        try:
            return self.client.get_positions(
                category="linear",
                symbol=symbol
            )
        except Exception as e:
            print(f"❌ [FETCH_FAIL] {symbol}: {e}")
            return None